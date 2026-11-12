# -*- coding: utf-8 -*-
"""Default recall: a small English retrieval encoder, with BM25 kept as fallback.

The pipeline used a TF-IDF cosine index, which cannot bridge the two hops of a
multi-hop question (the second paragraph rarely shares words with the query).
`recall()` now defaults to dense retrieval with BAAI/bge-small-en-v1.5 and
bm25 is opt-in.

Env:
  NBPW2_RECALL     dense | bm25      (default dense)
  NBPW2_RECALL_K   per-node depth    (default 20)
  NBPW2_RERANK     0 | 1             (default 0; sentence rerank is opt-in)
  NBPW2_EMBED      model id          (default BAAI/bge-small-en-v1.5)
"""
import os, threading
import numpy as np

MODEL = os.environ.get("NBPW2_EMBED", "BAAI/bge-small-en-v1.5")
QINSTR = "Represent this sentence for searching relevant passages: "
_LOCK = threading.Lock()
_ENC = None
_VEC = {}


def _encoder():
    """Load the encoder once.  CPU only; no GPU assumption in this repo."""
    global _ENC
    with _LOCK:
        if _ENC is None:
            import glob, torch
            from transformers import AutoTokenizer, AutoModel
            pat = os.path.expanduser(
                "~/.cache/huggingface/hub/models--%s/snapshots/*/" % MODEL.replace("/", "--"))
            hits = glob.glob(pat)
            if not hits:
                raise RuntimeError(
                    "encoder %s is not in the local HF cache; set HF_ENDPOINT "
                    "and download it, or run with NBPW2_RECALL=bm25" % MODEL)
            tok = AutoTokenizer.from_pretrained(hits[0])
            mdl = AutoModel.from_pretrained(hits[0]).eval()
            torch.set_num_threads(max(1, os.cpu_count() - 1))
            _ENC = (tok, mdl, torch)
    return _ENC


def encode(texts, batch=64):
    """CLS-pooled, L2-normalised embeddings, memoised per exact text."""
    todo = [t for t in dict.fromkeys(texts) if t not in _VEC]
    if todo:
        tok, mdl, torch = _encoder()
        with torch.no_grad():
            for i in range(0, len(todo), batch):
                b = tok(todo[i:i + batch], padding=True, truncation=True,
                        max_length=512, return_tensors="pt")
                h = mdl(**b).last_hidden_state[:, 0]
                h = torch.nn.functional.normalize(h, p=2, dim=1).cpu().numpy()
                for t, v in zip(todo[i:i + batch], h):
                    _VEC[t] = v.astype(np.float32)
    return np.stack([_VEC[t] for t in texts])


def _doc_text(d):
    return (d.get("title", "") + ". " + d.get("text", "")).strip()


class DenseIndex:
    """Cosine index over a node's paragraphs; ranks are raw 0-based."""

    def __init__(self, docs):
        self.docs = docs
        self.M = encode([_doc_text(d) for d in docs]) if docs else None

    def search(self, query, k=20):
        if not self.docs:
            return []
        q = encode([QINSTR + query])[0]
        s = self.M @ q
        order = np.argsort(-s)[:k]
        out = []
        for rank, i in enumerate(order):
            d = dict(self.docs[int(i)])
            d["local_score"] = float(s[int(i)])
            d["rank"] = rank
            out.append(d)
        return out


def recall(question, docs, k=None, mode=None):
    """The default recall path.  Returns hits carrying `rank` (raw) + `local_score`."""
    mode = mode or os.environ.get("NBPW2_RECALL", "dense")
    k = int(k if k is not None else os.environ.get("NBPW2_RECALL_K", 20))
    if mode == "bm25":
        from .retrieval import Index
        return Index(docs).search(question, k)
    return DenseIndex(docs).search(question, k)


# ---------------- optional sentence rerank (off by default) ----------------

def rerank_scores(question, hits, idf, sent_sets):
    """0.55*best_sentence + 0.30*doc_coverage + 0.15*title, idf weighted."""
    from .data import tokens
    qt = set(tokens(question))
    if not qt:
        return [0.0] * len(hits)
    qw = max(1e-6, sum(idf.get(t, 1.0) for t in qt))
    out = []
    for h in hits:
        best = 0.0
        for s in sent_sets.get(id(h), []):
            if s:
                best = max(best, sum(idf.get(t, 1.0) for t in (qt & s)) / qw)
        dt = set(tokens(h.get("text", "")))
        cov = sum(idf.get(t, 1.0) for t in (qt & dt)) / qw
        tt = set(tokens(h.get("title", "")))
        out.append(0.55 * best + 0.30 * cov + 0.15 * len(qt & tt) / max(1, len(qt)))
    return out

# -*- coding: utf-8 -*-
"""Readout dispatch: default fast path vs opt-in fusion path.

Modes
-----
fast   (default)  the original 11-feature numpy logistic verifier.  Identical
                  behaviour to nbpw2.verifier.train_verifier + score_candidates.
fusion (opt-in)   26 features = 11 fast + 8 NLI entailment + 7 answer-side
                  (extractive QA score/margin/vote/answer-type).  Needs the
                  cross-encoder signal cache and the fitted head on disk.

Switch
------
    NBPW2_READOUT=fast|fusion        (default fast)
    NBPW2_SIGNAL_CACHE=/path/to/scores_cache.json
    NBPW2_FUSION_HEAD=/path/to/fusion_head.json

Cost (measured on this machine, dmqa_dev, B=2, 10 candidate pairs/query)
    fast    0.97 ms/pair      ~10 ms/query
    fusion  126.8 ms/pair   ~1.27 s/query     131x
That is why fusion is an offline/high-budget option and NOT the default.
"""
import os, json, re, hashlib, math
import numpy as np

from .data import tokens
from .verifier import candidate_features, Verifier

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_SIGNALS = os.path.abspath(os.path.join(
    _HERE, "..", "..", "2026-11-09", "network-brain-verifier", "work", "scores_cache.json"))
_DEFAULT_HEAD = os.path.join(_HERE, "data", "fusion_head.json")

MODE = os.environ.get("NBPW2_READOUT", "fast").strip().lower()
COST = {"fast_ms_per_pair": 0.97, "fusion_ms_per_pair": 126.8, "ratio": 131.0}


def mode():
    return os.environ.get("NBPW2_READOUT", MODE).strip().lower()


def signal_cache_path():
    return os.environ.get("NBPW2_SIGNAL_CACHE", _DEFAULT_SIGNALS)


def fusion_head_path():
    return os.environ.get("NBPW2_FUSION_HEAD", _DEFAULT_HEAD)


# ---------------- cross-encoder signals (cache only) ----------------
_cache = None
_cache_miss = {"n": 0}


def _load_cache():
    global _cache
    if _cache is None:
        path = signal_cache_path()
        _cache = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    return _cache


def pkey(title, text):
    return hashlib.md5((title + "\x00" + (text or "")).encode("utf-8")).hexdigest()[:16]


def attach_signals(cands, qid):
    cch = _load_cache()
    hit = 0
    for c in cands:
        s = cch.get(qid + "|" + pkey(c["title"], c.get("text", "")))
        if s is None:
            _cache_miss["n"] += 1
            s = {"nli_ent": 0.0, "nli_neu": 1.0, "nli_con": 0.0,
                 "qa_score": -20.0, "qa_margin": 0.0, "qa_ans": ""}
        else:
            hit += 1
        c["_nli_ent"], c["_nli_neu"], c["_nli_con"] = s["nli_ent"], s["nli_neu"], s["nli_con"]
        c["_qa_score"], c["_qa_margin"], c["_qa_ans"] = s["qa_score"], s["qa_margin"], s.get("qa_ans", "")
    return hit, len(cands)


def signal_misses():
    return _cache_miss["n"]


# ---------------- answer-side helpers ----------------
MONTHS = set("january february march april may june july august september october november december".split())
DATE_RE = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")


def qtype_of(q):
    ql = q.lower().strip()
    if ql.startswith("when") or "what year" in ql or "which year" in ql or "what date" in ql:
        return "date"
    if ql.startswith("how many") or ql.startswith("how much") or "what number" in ql:
        return "number"
    if ql.startswith("who") or "whose" in ql:
        return "person"
    if ql.startswith("where") or "what city" in ql or "what country" in ql or "which country" in ql:
        return "place"
    if ql.startswith("which") or ql.startswith("what"):
        return "entity"
    return "other"


def ans_type_ok(qt, ans):
    if not ans:
        return 0.0
    toks = ans.strip().split()
    if qt == "date":
        return 1.0 if (DATE_RE.search(ans) or any(m in ans.lower() for m in MONTHS)) else 0.0
    if qt == "number":
        return 1.0 if re.search(r"\d", ans) else 0.0
    if qt in ("person", "place", "entity"):
        return 1.0 if sum(1 for t in toks if t[:1].isupper()) >= 1 else 0.0
    return 1.0


def norm_ans(a):
    a = re.sub(r"[^a-z0-9 ]+", " ", (a or "").lower())
    return " ".join(a.split())


def _minmax(v):
    v = np.asarray(v, dtype=float)
    lo, hi = v.min(), v.max()
    return np.zeros_like(v) if hi - lo < 1e-9 else (v - lo) / (hi - lo)


def _z(v):
    v = np.asarray(v, dtype=float)
    s = v.std()
    return (v - v.mean()) / (s if s > 1e-8 else 1.0)


# ---------------- global idf / sentence coverage / bm25 ----------------
_IDF = None
_SENT = re.compile(r"(?<=[.!?])\s+")


def set_pool(pool):
    """Compute document frequencies once; needed for the lexical fusion features."""
    global _IDF
    df = {}
    for p in pool:
        for t in set(tokens(p["title"] + " " + p["text"])):
            df[t] = df.get(t, 0) + 1
    n = len(pool)
    _IDF = {t: math.log((n + 1) / (v + 1)) + 1.0 for t, v in df.items()}


def _idf(t):
    return _IDF.get(t, 1.0) if _IDF else 1.0


def best_sent_cov(query, text):
    qt = set(tokens(query))
    if not qt:
        return 0.0
    denom = sum(_idf(t) for t in qt) or 1.0
    best = 0.0
    for s in [x.strip() for x in _SENT.split(text or "") if x.strip()][:12]:
        cov = sum(_idf(t) for t in (qt & set(tokens(s)))) / denom
        best = max(best, cov)
    return best


def bm25_global(query, title, text):
    qt = [t for t in tokens(query)]
    if not qt:
        return 0.0
    doc = tokens(title + " " + text)
    if not doc:
        return 0.0
    tf = {}
    for t in doc:
        tf[t] = tf.get(t, 0) + 1
    avg = 45.0
    s = 0.0
    for t in qt:
        f = tf.get(t, 0)
        if not f:
            continue
        s += _idf(t) * (f * 2.2) / (f + 1.2 * (0.25 + 0.75 * len(doc) / avg))
    return s / max(1.0, math.sqrt(len(qt)))


# ---------------- 26-dim fusion features ----------------
def _old_rows(cands, question, n_nodes):
    max_local = max([c.get("local_score", 0.0) for c in cands] + [1e-6])
    counts = {}
    for c in cands:
        counts[c["title"]] = counts.get(c["title"], 0) + 1
    for c in cands:
        c["agreement"] = counts[c["title"]] / n_nodes
    return [candidate_features(c, question, cands, n_nodes, max_local,
                               c.get("node_rel", 0.5), True) for c in cands]


def _nli_rows(cands, question):
    ent = [c["_nli_ent"] for c in cands]
    con = [c["_nli_con"] for c in cands]
    ent_r = _minmax(ent)
    bm = [bm25_global(question, c.get("title", ""), c.get("text", "")) for c in cands]
    bm_n = _minmax(bm)
    out = []
    for i, c in enumerate(cands):
        out.append([ent[i], c["_nli_neu"], con[i], ent[i] - con[i], ent_r[i],
                    best_sent_cov(question, c.get("text", "")), bm_n[i],
                    min(1.0, len(set(tokens(c.get("text", "")))) / 120.0)])
    return out


def _answer_rows(cands, question):
    qa = [c["_qa_score"] for c in cands]
    qn, qz = _minmax(qa), _z(qa)
    seen = {}
    for c in cands:
        seen.setdefault(c["title"], c)
    clusters = {}
    for c in seen.values():
        k = norm_ans(c["_qa_ans"])
        if not k:
            continue
        clusters.setdefault(k, {"titles": set(), "nodes": set()})
        clusters[k]["titles"].add(c["title"])
        clusters[k]["nodes"].add(c.get("node"))
    nt = max(1, len(seen))
    qt = qtype_of(question)
    out = []
    for i, c in enumerate(cands):
        k = norm_ans(c["_qa_ans"])
        cl = clusters.get(k) if k else None
        out.append([qn[i], qz[i], c["_qa_margin"],
                    (len(cl["titles"]) / nt) if cl else 0.0,
                    (len(cl["nodes"]) / 5.0) if cl else 0.0,
                    ans_type_ok(qt, c["_qa_ans"]),
                    min(1.0, len(set(tokens(c.get("text", "")))) / 120.0)])
    return out


def feats_fusion(cands, question, qid, n_nodes=5):
    a = _old_rows(cands, question, n_nodes)
    attach_signals(cands, qid)
    b = _nli_rows(cands, question)
    c = _answer_rows(cands, question)
    return [a[i] + b[i] + c[i] for i in range(len(cands))]


class FusionReadout:
    """Fitted 26-dim head, persisted to JSON so the opt-in mode is usable."""

    def __init__(self, head=None):
        self.head = head

    def fit(self, episodes, n_nodes=5):
        X, y = [], []
        for ep in episodes:
            cands = ep["candidates"]
            rows = feats_fusion(cands, ep["question"], ep["id"], n_nodes)
            for row, c in zip(rows, cands):
                X.append(row)
                y.append(1.0 if c.get("is_gold") else 0.0)
        v = Verifier(l2=2e-3, lr=0.15, epochs=600).fit(X, y)
        self.head = {"mu": v.mu.tolist(), "sd": v.sd.tolist(), "w": v.w.tolist(),
                     "dim": len(v.w)}
        return self

    @classmethod
    def load(cls, path=None):
        path = path or fusion_head_path()
        if not os.path.exists(path):
            raise RuntimeError(
                f"fusion readout head not found at {path}. Fit it first "
                f"(see 2026-11-10/network-brain-selector/work/fit_fusion.py).")
        d = json.load(open(path, encoding="utf-8"))
        return cls({"mu": np.asarray(d["mu"]), "sd": np.asarray(d["sd"]),
                    "w": np.asarray(d["w"]), "dim": d["dim"]})

    def predict(self, rows):
        h = self.head
        Z = (np.asarray(rows, dtype=float) - h["mu"]) / h["sd"]
        return 1.0 / (1.0 + np.exp(-np.clip(Z @ h["w"], -30, 30)))

    def save(self, path=None):
        path = path or fusion_head_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(self.head, open(path, "w", encoding="utf-8"))


def score_candidates(cands, question, qid, mode="fast", verifier=None, n_nodes=5):
    """Return per-candidate readout scores under the selected mode."""
    if not cands:
        return []
    if mode == "fast":
        if verifier is None:
            raise ValueError("fast mode needs a fitted Verifier")
        max_local = max([c.get("local_score", 0.0) for c in cands] + [1e-6])
        counts = {}
        for c in cands:
            counts[c["title"]] = counts.get(c["title"], 0) + 1
        for c in cands:
            c["agreement"] = counts[c["title"]] / n_nodes
        X = [candidate_features(c, question, cands, n_nodes, max_local,
                                c.get("node_rel", 0.5), True) for c in cands]
        return verifier.predict(X)
    if mode == "fusion":
        head = verifier if isinstance(verifier, FusionReadout) else FusionReadout.load()
        return head.predict(feats_fusion(cands, question, qid, n_nodes))
    raise ValueError(f"unknown readout mode: {mode}")

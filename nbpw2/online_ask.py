# -*- coding: utf-8 -*-
"""On-demand D1 question answering over the shipped dmqa_dev pool.

This is the same scoring chain the public trace was generated with: D1 dense
max-cosine node routing (independent top-2), dense recall k=10 per node,
shipped verifier + pair head, set selection K=5, extractive answer.  It exists
so the website can answer a visitor's own question instead of replaying a
frozen trace.

Privacy: the question is used in memory only.  Nothing here writes it to disk,
to a database, or to stdout/stderr.

Runtime: the first call loads the pool, trains the verifier/pair head on the
train split and encodes the query.  `load()` can be warmed from a thread.

Deployment: `bge_pool_nodes.npz` ships in `nbpw2/results/` (pool embeddings +
the deterministic topic-node assignment), so no research work directories are
needed next to the repo.
"""
import os
import re
import sys
import types
import threading
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
NB = os.path.dirname(HERE)

K = 3
B = 2
RECALL_K = 10
SET_K = 5
MAX_Q = 180
SENT = re.compile(r"(?<=[.!?])\s+")
ASSET = os.environ.get(
    "NBPW2_ASSET",
    os.path.join(HERE, "results", "bge_pool_nodes.npz"),
)

STATE = {"ready": False, "loading": False, "error": None, "load_ms": None}
_LOCK = threading.Lock()
_E = None


def _rank_all(idx, query):
    """Full BM25 ranking, same formula/order as the training harness."""
    import math
    from nbpw2.data import tokens
    qt = set(tokens(query))
    if not qt:
        return []
    qnorm = math.sqrt(sum(idx.idf.get(t, 1.0) ** 2 for t in qt)) or 1.0
    out = []
    for i, c in enumerate(idx.tfs):
        s = sum((c.get(t, 0) * idx.idf.get(t, 1.0)) for t in qt) / (idx.norms[i] * qnorm)
        if s > 0:
            tt = set(tokens(idx.docs[i]["title"]))
            s += 0.35 * len(qt & tt) / max(1, len(qt))
        out.append((s, i))
    out.sort(key=lambda x: -x[0])
    return out


def _train_pair(train, pool, assign, node_docs, idx, verifier_mod, network_mod,
                selector_mod):
    """Retrain exactly like the shipped default (BM25@5 train episodes)."""
    KQ = 5
    eps = []
    for r in train:
        hits = []
        for nid in range(K):
            order = _rank_all(idx[nid], r["question"])[:KQ]
            docs = node_docs[nid]
            for rk, (s, i) in enumerate(order):
                d = dict(docs[i])
                d["local_score"] = float(s)
                d["rank"] = rk
                d["node"] = nid
                hits.append(d)
        gold = {s["title"] for s in r["support"]}
        for h in hits:
            h["node_rel"] = 0.5
            h["agreement"] = 1.0 / K
            h["is_gold"] = h["title"] in gold
        eps.append({"candidates": hits, "question": r["question"],
                    "gold": gold, "id": r["id"], "type": r.get("type"),
                    "nodes": list(range(K))})
    ver = verifier_mod.train_verifier(eps, n_nodes=K)
    for ep in eps:
        network_mod.score_candidates(ep, ver, K)
    head, _, _ = selector_mod.fit_pair_head(eps, n_nodes=K)
    return ver, head


def _build():
    from nbpw2.data import load, build_pool
    from nbpw2.retrieval import Index
    from nbpw2 import network as network_mod
    from nbpw2 import verifier as verifier_mod
    from nbpw2 import selector_lib as selector_mod
    from nbpw2 import dense as D

    data_path = os.environ.get(
        "NBPW2_DATA", os.path.join(NB, "nbpw2", "data", "dmqa_dev.jsonl"))
    rows = load(data_path)
    pool = build_pool(rows)
    z = np.load(ASSET)
    E, assign = z["e"], z["assign"].tolist()
    if len(pool) != len(assign) or E.shape[0] != len(pool):
        raise RuntimeError("asset/pool mismatch: fix bge_pool_nodes.npz")
    node_docs = [[] for _ in range(K)]
    for i, a in enumerate(assign):
        node_docs[a].append({"title": pool[i]["title"],
                             "text": pool[i]["text"], "node": a})
    node_pos = [[i for i, a in enumerate(assign) if a == n] for n in range(K)]
    mat = [E[pos] for pos in node_pos]
    idx = [Index(d) for d in node_docs]
    idf = selector_mod.global_idf(pool)
    train = [r for r in rows if r["split"] == "train"]
    ver, head = _train_pair(train, pool, assign, node_docs, idx,
                            verifier_mod, network_mod, selector_mod)
    # Warm the encoder so the first visitor does not pay the model load.
    D.encode([D.QINSTR + "warm up"])
    return types.SimpleNamespace(
        D=D, pool=pool, node_docs=node_docs, idf=idf, mat=mat,
        ver=ver, head=head, score_candidates=network_mod.score_candidates,
        select_set=selector_mod.select_set,
        names=["节点 A", "节点 B", "节点 C"],
    )


def load():
    """Idempotent, thread-safe warm-up.  Raises the original error on failure."""
    global _E
    if _E is not None:
        return _E
    with _LOCK:
        if _E is not None:
            return _E
        STATE["loading"] = True
        STATE["error"] = None
        t0 = time.time()
        try:
            _E = _build()
        except Exception as e:  # keep the service alive; report on /health
            STATE["error"] = f"{type(e).__name__}: {e}"
            raise
        finally:
            STATE["loading"] = False
            STATE["load_ms"] = round((time.time() - t0) * 1000, 1)
        STATE["ready"] = True
        return _E


def health():
    return {"ready": STATE["ready"], "loading": STATE["loading"],
            "error": STATE["error"], "load_ms": STATE["load_ms"]}


def _answer_type(q):
    from nbpw2.readout import qtype_of
    ql = q.lower()
    if any(x in ql for x in ("how many", "how much", "what number", "population", "how old")):
        return "number"
    if "what year" in ql or "which year" in ql or ql.startswith("when"):
        return "date"
    return qtype_of(q)


def _extract(selected, question, idf):
    """Extractive reader: bridge paragraph first, then idf overlap + answer type."""
    from nbpw2.data import tokens
    from nbpw2.readout import ans_type_ok
    from nbpw2.verifier import caps

    qt = set(tokens(question))
    qw = max(1e-6, sum(idf.get(t, 1.0) for t in qt))
    tied = set()
    for c in selected:
        tied |= set(tokens(c.get("title", "")))
    focus = qt - tied
    fw = max(1e-6, sum(idf.get(t, 1.0) for t in focus))
    qtp = _answer_type(question)
    tmap = {c["title"].lower(): i for i, c in enumerate(selected)}
    bridge_idx = None
    for i, c in enumerate(selected):
        for ent in sorted(caps(c.get("text", "")), key=len, reverse=True):
            if ent in tmap and tmap[ent] != i:
                bridge_idx = tmap[ent]
                break
        if bridge_idx is not None:
            break
    rows = []
    order = ([bridge_idx] if bridge_idx is not None else []) + \
            [i for i in range(len(selected)) if i != bridge_idx]
    for ci in order:
        c = selected[ci]
        for sent in [x.strip() for x in SENT.split(c.get("text", "")) if x.strip()]:
            st = set(tokens(sent))
            cov = sum(idf.get(t, 1.0) for t in (qt & st)) / qw
            fcov = sum(idf.get(t, 1.0) for t in (focus & st)) / fw if focus else 0.0
            span = ""
            if qtp == "number":
                ns = re.findall(r"\b\d[\d,]*(?:\.\d+)?\b", sent)
                if ns:
                    span = max(ns, key=lambda x: (len(re.sub(r"\D", "", x)), "," in x))
            elif qtp == "date":
                m = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", sent)
                span = m.group(0) if m else ""
            elif qtp in ("person", "place", "entity"):
                runs = re.findall(r"\b[A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+)*", sent)
                runs = [w for w in runs if w.lower() not in qt and not w.lower().startswith("the ")]
                span = max(runs, key=len).strip() if runs else ""
            rank_bonus = 1.0 if (bridge_idx is not None and ci == bridge_idx) else 0.0
            score = rank_bonus + cov + 0.45 * fcov + (0.30 if span and ans_type_ok(qtp, span) else 0.0)
            rows.append((score, ci, sent, span, cov, fcov))
    if not rows:
        return {"span": "", "sentence": "", "cite": 0, "coverage": 0.0,
                "qtype": qtp, "bridge_paragraph": bridge_idx}
    best = max(rows, key=lambda x: x[0])
    return {"span": best[3], "sentence": best[2], "cite": best[1] + 1,
            "coverage": round(best[4], 3), "focus_coverage": round(best[5], 3),
            "qtype": qtp, "bridge_paragraph": bridge_idx}


def ask(question):
    """Run the shipped D1 chain once.  No persistence, no logging of `question`."""
    q = (question or "").strip()
    if not q:
        raise ValueError("empty question")
    if len(q) > MAX_Q:
        raise ValueError(f"question longer than {MAX_Q} chars")
    E = load()
    t_all = time.time()

    t0 = time.time()
    qv = E.D.encode([E.D.QINSTR + q])[0]
    encode_ms = (time.time() - t0) * 1000

    t0 = time.time()
    scores = {}
    for i in range(K):
        s = E.mat[i] @ qv
        top = np.argsort(-s)[:3]
        scores[i] = {
            "node": i, "name": E.names[i],
            "max_cos": round(float(s[top[0]]), 4),
            "top3_mean": round(float(s[top].mean()), 4),
            "best_title": E.node_docs[i][int(top[0])]["title"],
        }
    ranked = sorted(scores, key=lambda i: -scores[i]["max_cos"])
    route = []
    for hop, nid in enumerate(ranked[:B], start=1):
        route.append({"hop": hop, "chosen": nid,
                      "scores": [scores[i] for i in ranked]})
    route_ms = (time.time() - t0) * 1000

    t0 = time.time()
    hits, recall = [], []
    for nid in ranked[:B]:
        s = E.mat[nid] @ qv
        order = np.argsort(-s)[:RECALL_K]
        one = []
        for rank, i in enumerate(order):
            d = dict(E.node_docs[nid][int(i)])
            d["local_score"] = float(s[int(i)])
            d["rank"] = rank
            d["node"] = nid
            hits.append(d)
            one.append({"rank": rank, "score": round(float(s[int(i)]), 4),
                        "title": d["title"], "snippet": d["text"][:190]})
        recall.append({"node": nid, "name": E.names[nid], "hits": one})
    recall_ms = (time.time() - t0) * 1000

    t0 = time.time()
    for h in hits:
        h["node_rel"] = 0.5
        h["agreement"] = 1.0 / K
    ep = {"candidates": hits, "question": q, "gold": set(), "id": "live",
          "type": None, "nodes": ranked[:B]}
    E.score_candidates(ep, E.ver, K)
    sel = E.select_set(ep["candidates"], q, SET_K, E.head, 0.0)
    answer = _extract(sel, q, E.idf)
    select_ms = (time.time() - t0) * 1000

    selected = [{
        "n": i + 1, "rank": int(c.get("rank", 0)),
        "title": c.get("title", ""), "node": int(c.get("node", 0)),
        "name": E.names[int(c.get("node", 0))],
        "verifier": round(float(c.get("verifier", 0.0)), 4),
        "snippet": c.get("text", "")[:240],
    } for i, c in enumerate(sel)]

    return {
        "ok": True,
        "question": q,
        "route": route,
        "recall": recall,
        "selected": selected,
        "answer": answer,
        "latency": {
            "query_encode_ms": round(encode_ms, 1),
            "route_ms": round(route_ms, 1),
            "recall_ms": round(recall_ms, 1),
            "select_ms": round(select_ms, 1),
            "total_ms": round((time.time() - t_all) * 1000, 1),
        },
        "meta": {
            "route": "D1 dense max-cosine, independent top-2",
            "recall_k": RECALL_K, "budget": B, "set_k": SET_K,
            "answer": "extractive span from selected paragraphs; no LLM rewrite",
            "pool": "dmqa_dev pool (3975 paragraphs, 3 synthetic nodes)",
        },
    }

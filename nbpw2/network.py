# -*- coding: utf-8 -*-
"""NBPW-2 episode runner and baselines for DMQA."""
import math
from .data import make_shards, make_central
from .retrieval import Index
from .dense import recall
from .verifier import candidate_features
from .workspace import select

def _metrics(selected, gold, k2=2, k5=5):
    titles = [c.get("title") for c in selected]
    s2, s5 = set(titles[:k2]), set(titles[:k5])
    both2 = 1.0 if gold <= s2 else 0.0
    both5 = 1.0 if gold <= s5 else 0.0
    rec5 = len(gold & s5) / max(1, len(gold))
    mrr = 0.0
    for i, t in enumerate(titles[:k5]):
        if t in gold:
            mrr = 1.0 / (i + 1)
            break
    return {"both@2": both2, "both@5": both5, "recall@5": rec5, "mrr": mrr}

def _agreement(cands, n_nodes):
    counts = {}
    for c in cands:
        counts[c["title"]] = counts.get(c["title"], 0) + 1
    for c in cands:
        c["agreement"] = counts[c["title"]] / max(1, n_nodes)

def collect(row, pool, n_nodes=5, distractors=98, top_k=None, replicas=1, killed=(), seed=0, include_central=False, gold_nodes=None):
    nodes, gold = make_shards(row, pool, n_nodes=n_nodes, distractors_per_node=distractors,
                              top_k=top_k or 5, seed=seed, replicas=replicas, gold_nodes=gold_nodes)
    per_node, cands = [], []
    for n in nodes:
        if n["id"] in killed:
            per_node.append([])
            continue
        # default recall = dense @ NBPW2_RECALL_K (20); bm25 is opt-in
        hits = recall(row["question"], n["docs"], top_k)
        for h in hits:
            h["node"] = n["id"]
            h["node_rel"] = 0.5
            h["predict_open"] = True
        per_node.append(hits)
        cands.extend(hits)
    _agreement(cands, n_nodes)
    out = {"id": row["id"], "question": row["question"], "answer": row["answer"],
           "gold": gold, "per_node": per_node, "candidates": cands, "nodes": nodes}
    if include_central:
        for name, extra in (("central", 500), ("central_oracle", 0)):
            docs = make_central(row, pool, n_extra=extra, seed=seed)
            idx = Index(docs)
            ch = idx.search(row["question"], top_k * n_nodes)
            for i, h in enumerate(ch):
                h["node"] = -1; h["rank"] = i; h["agreement"] = 0.0
            out[name] = ch
    return out

def score_candidates(ep, verifier, n_nodes=5, use_agreement=True):
    cands = ep["candidates"]
    if not cands:
        return []
    max_local = max([c["local_score"] for c in cands] + [1e-6])
    X = []
    for c in cands:
        X.append(candidate_features(c, ep["question"], cands, n_nodes, max_local, c.get("node_rel", 0.5), use_agreement))
    p = verifier.predict(X)
    for c, v in zip(cands, p):
        c["verifier"] = float(v)
    return cands

def run_episode(row, pool, verifier, mode="workspace", n_nodes=5, distractors=98,
                top_k=None, replicas=1, killed=(), seed=0, include_central=False, use_agreement=True, gold_nodes=None):
    ep = collect(row, pool, n_nodes=n_nodes, distractors=distractors, top_k=top_k,
                 replicas=replicas, killed=killed, seed=seed, include_central=include_central, gold_nodes=gold_nodes)
    if mode == "best_node":
        best = {"both@2": 0.0, "both@5": 0.0, "recall@5": 0.0, "mrr": 0.0}
        for hits in ep["per_node"]:
            m = _metrics(hits, ep["gold"])
            if m["recall@5"] > best["recall@5"]:
                best = m
        return best, ep
    if mode in ("central", "central_oracle"):
        hits = ep.get(mode, [])
        return _metrics(hits, ep["gold"]), ep
    cands = score_candidates(ep, verifier, n_nodes, use_agreement) if mode not in ("flat_local",) else ep["candidates"]
    mode_map = {"nbpw": "workspace", "flat_verifier": "flat_verifier",
                "flat_local": "flat_local", "no_verifier": "no_verifier",
                "no_coalition": "no_coalition", "no_novelty": "no_novelty",
                "no_coverage": "no_coverage"}
    selected, _ = select(cands, row["question"], K=5, mode=mode_map.get(mode, "workspace"), n_nodes=n_nodes)
    return _metrics(selected, ep["gold"]), ep

def train_rows(rows, pool, n_nodes=5, distractors=98, top_k=None, replicas=1, seed=0):
    eps = []
    for r in rows:
        eps.append(collect(r, pool, n_nodes=n_nodes, distractors=distractors, top_k=top_k,
                           replicas=replicas, seed=seed))
    return eps

# -*- coding: utf-8 -*-
"""Capacity-limited global workspace with salience competition and coalition."""
from .data import tokens
from .verifier import caps

def _jacc(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

def _dedupe(cands):
    best = {}
    for c in cands:
        k = c.get("title") or c.get("text", "")[:60]
        if k not in best or c.get("verifier", 0.0) > best[k].get("verifier", 0.0):
            best[k] = c
    return list(best.values())

def select(cands, query, K=5, mode="workspace", n_nodes=5):
    """Return top-K candidates under a workspace/ablation rule.

    mode:
      workspace      full salience + coalition
      no_verifier    use local score instead of learned verifier
      no_coalition   coalition bonus = 0
      no_novelty     novelty = 0
      no_coverage    coverage = 0
      flat_verifier  sort by verifier only
      flat_local     sort by local score only
    """
    if not cands:
        return [], []
    cands = _dedupe(cands)
    qt = set(tokens(query))
    if mode == "flat_local":
        out = sorted(cands, key=lambda c: c.get("local_score", 0.0), reverse=True)[:K]
        return out, [c.get("local_score", 0.0) for c in out]
    if mode == "flat_verifier":
        out = sorted(cands, key=lambda c: c.get("verifier", 0.0), reverse=True)[:K]
        return out, [c.get("verifier", 0.0) for c in out]

    max_local = max([c.get("local_score", 0.0) for c in cands] + [1e-6])
    selected, scores = [], []
    pool = list(cands)
    while pool and len(selected) < K:
        best, best_s = None, -1e9
        for c in pool:
            rel = c.get("verifier", 0.0) if mode != "no_verifier" else c.get("local_score", 0.0) / max_local
            dt = set(tokens(c.get("text", "")))
            if selected:
                nov = 1.0 - max(_jacc(dt, set(tokens(s.get("text", "")))) for s in selected)
            else:
                nov = 1.0
            if mode == "no_novelty":
                nov = 0.0
            if selected:
                covered = set()
                for s in selected:
                    covered |= (qt & set(tokens(s.get("text", ""))))
                cov = len((qt & dt) - covered) / max(1, len(qt))
            else:
                cov = len(qt & dt) / max(1, len(qt))
            if mode == "no_coverage":
                cov = 0.0
            agree = c.get("agreement", 0.0)
            coal = 0.0
            if selected and mode != "no_coalition":
                seed = selected[0]
                sc = caps(seed.get("title", "") + " " + seed.get("text", ""))
                cc = caps(c.get("title", "") + " " + c.get("text", ""))
                coal = len(sc & cc) / max(1, len(sc))
            cost = 1.0 - min(1.0, c.get("local_score", 0.0) / max_local)
            s = 0.55 * rel + 0.15 * nov + 0.15 * cov + 0.10 * agree + 0.05 * coal - 0.02 * cost
            if s > best_s:
                best, best_s = c, s
        selected.append(best)
        scores.append(float(best_s))
        pool.remove(best)
    return selected, scores

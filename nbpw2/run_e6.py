# -*- coding: utf-8 -*-
"""E6: credit assignment — exact Shapley vs counterfactual contribution."""
import json, itertools, statistics, os
import numpy as np
from .data import load, build_pool
from .network import train_rows, collect, score_candidates, _metrics
from .verifier import train_verifier
from .workspace import select

def value(ep, ver, subset, n_nodes=5):
    cands = [c for c in ep["candidates"] if c["node"] in subset]
    if not cands:
        return 0.0
    tmp = dict(ep); tmp["candidates"] = cands
    sc = score_candidates(tmp, ver, n_nodes)
    sel, _ = select(sc, ep["question"], K=5, mode="workspace", n_nodes=n_nodes)
    return _metrics(sel, ep["gold"])["both@5"]

def spearman(a, b):
    if len(a) < 2:
        return 0.0
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    if ra.std() == 0 or rb.std() == 0:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])

def main():
    rows = load(); pool = build_pool(rows)
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"][:20]
    ver = train_verifier(train_rows(train, pool, distractors=100, top_k=5))
    all_nodes = list(range(5))
    per_q = []
    for r in test:
        ep = collect(r, pool, distractors=100, top_k=5)
        vals = {}
        for mask in range(1 << 5):
            S = tuple(i for i in range(5) if mask & (1 << i))
            vals[S] = value(ep, ver, set(S))
        shap = {}
        for i in all_nodes:
            others = [x for x in all_nodes if x != i]
            s = 0.0
            for k in range(5):
                for comb in itertools.combinations(others, k):
                    S = frozenset(comb)
                    w = math_fact(k) * math_fact(4 - k) / math_fact(5)
                    s += w * (vals[tuple(sorted(S | {i}))] - vals[tuple(sorted(S))])
            shap[i] = s
        full = vals[tuple(all_nodes)]
        cf = {i: full - vals[tuple(x for x in all_nodes if x != i)] for i in all_nodes}
        per_q.append({"id": r["id"], "shapley": shap, "counterfactual": cf})
    # aggregate
    nodes = list(range(5))
    shap_mean = {i: round(statistics.mean(q["shapley"][i] for q in per_q), 3) for i in nodes}
    cf_mean = {i: round(statistics.mean(q["counterfactual"][i] for q in per_q), 3) for i in nodes}
    cors = []
    for q in per_q:
        cors.append(spearman([q["shapley"][i] for i in nodes], [q["counterfactual"][i] for i in nodes]))
    out = {"n": len(per_q), "shapley_mean": shap_mean, "counterfactual_mean": cf_mean,
           "mean_spearman": round(statistics.mean(cors), 3),
           "nonzero_questions": sum(1 for q in per_q if max(q["shapley"].values()) > 0)}
    print(out)
    with open(os.path.join(os.path.dirname(__file__), "results", "e6_credit.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

def math_fact(n):
    r = 1
    for i in range(2, n + 1): r *= i
    return r

if __name__ == "__main__":
    main()

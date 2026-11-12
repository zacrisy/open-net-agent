# -*- coding: utf-8 -*-
"""E9: larger DMQA (1000 questions) active-selection replication."""
import json, random, statistics, os
from .data import load, build_pool
from .network import train_rows
from .verifier import train_verifier
from .active import run_policy, run_all_nodes

def bootstrap(diffs, n=5000, seed=7):
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        vals.append(statistics.mean(diffs[rng.randrange(len(diffs))] for _ in diffs))
    vals.sort()
    return [round(vals[int(0.025*n)], 4), round(vals[int(0.975*n)], 4)]

def main():
    path = os.path.join(os.path.dirname(__file__), "data", "dmqa_1000.jsonl")
    rows = load(path)
    pool = build_pool(rows)
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    ver = train_verifier(train_rows(train, pool, distractors=100, top_k=5), use_agreement=False)
    out = {}
    for budget in [2, 3]:
        for policy in ["random", "round_robin", "context_ucb", "active", "oracle"]:
            runs = [run_policy(test, pool, ver, policy, budget=budget, seed=s) for s in range(3)]
            ms = [m for run in runs for m in run]
            out[f"B={budget},{policy}"] = {k: round(statistics.mean(m[k] for m in ms), 4)
                                            for k in ("both@2", "both@5", "recall@5", "mrr", "bytes", "latency")}
            print(f"B={budget},{policy}", out[f"B={budget},{policy}"])
    all5 = run_all_nodes(test, pool, ver)
    out["all5"] = {k: round(statistics.mean(m[k] for m in all5), 4) for k in ("both@2", "both@5", "recall@5", "mrr", "bytes", "latency")}
    print("all5", out["all5"])
    # paired bootstrap active vs random at B=2 and B=3
    for budget in [2, 3]:
        a = run_policy(test, pool, ver, "active", budget=budget, seed=0)
        r = run_policy(test, pool, ver, "random", budget=budget, seed=0)
        diffs = [x["both@5"] - y["both@5"] for x, y in zip(a, r)]
        out[f"bootstrap_B={budget}"] = {"diff": round(statistics.mean(diffs), 4), "ci95": bootstrap(diffs),
                                         "win": sum(1 for d in diffs if d > 0), "loss": sum(1 for d in diffs if d < 0),
                                         "n": len(diffs)}
        print("bootstrap", budget, out[f"bootstrap_B={budget}"])
    with open(os.path.join(os.path.dirname(__file__), "results", "e9_large_active.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

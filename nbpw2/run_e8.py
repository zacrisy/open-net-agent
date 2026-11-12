# -*- coding: utf-8 -*-
"""E8: active evidence gathering under a node-query budget."""
import json, statistics, os
from .data import load, build_pool
from .network import train_rows
from .verifier import train_verifier
from .active import run_policy, run_all_nodes

def main():
    rows = load(); pool = build_pool(rows)
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    ver = train_verifier(train_rows(train, pool, distractors=100, top_k=5), use_agreement=False)
    out = {}
    for budget in [1, 2, 3]:
        for policy in ["random", "round_robin", "ucb", "context_ucb", "active", "oracle"]:
            runs = [run_policy(test, pool, ver, policy, budget=budget, seed=s) for s in range(3)]
            ms = [m for run in runs for m in run]
            key = f"B={budget},{policy}"
            out[key] = {k: round(statistics.mean(m[k] for m in ms), 4) for k in ("both@2", "both@5", "recall@5", "mrr", "bytes", "latency")}
            print(key, out[key])
    ms = run_all_nodes(test, pool, ver)
    out["all5"] = {k: round(statistics.mean(m[k] for m in ms), 4) for k in ("both@2", "both@5", "recall@5", "mrr", "bytes", "latency")}
    print("all5", out["all5"])
    with open(os.path.join(os.path.dirname(__file__), "results", "e8_active.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

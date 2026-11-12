# -*- coding: utf-8 -*-
"""E10: 10-node simulation — does active selection scale?"""
import json, statistics, os
from .data import load, build_pool
from .network import train_rows
from .verifier import train_verifier
from .active import run_policy, run_all_nodes

def main():
    rows = load(os.path.join(os.path.dirname(__file__), "data", "dmqa_dev.jsonl"))
    pool = build_pool(rows)
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    ver = train_verifier(train_rows(train, pool, distractors=50, top_k=5), use_agreement=False)
    out = {}
    for budget in [2, 4]:
        for policy in ["random", "active", "oracle"]:
            runs = [run_policy(test, pool, ver, policy, budget=budget, seed=s, n_nodes=10) for s in range(3)]
            ms = [m for run in runs for m in run]
            out[f"B={budget},{policy}"] = {k: round(statistics.mean(m[k] for m in ms), 4)
                                            for k in ("both@2", "both@5", "recall@5", "mrr", "bytes")}
            print(f"B={budget},{policy}", out[f"B={budget},{policy}"])
    alln = run_all_nodes(test, pool, ver, n_nodes=10)
    out["all10"] = {k: round(statistics.mean(m[k] for m in alln), 4) for k in ("both@2", "both@5", "recall@5", "mrr", "bytes")}
    print("all10", out["all10"])
    with open(os.path.join(os.path.dirname(__file__), "results", "e10_10nodes.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

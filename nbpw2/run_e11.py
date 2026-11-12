# -*- coding: utf-8 -*-
"""E11: learned node scorer (P1) + topic-split sharding (exclusive replicas)."""
import json, random, statistics, os
from .data import load, build_pool
from .network import train_rows
from .verifier import train_verifier
from .active import run_policy, gold_nodes_for, ActiveEnv
from .node_scorer import collect_training, node_features

def bootstrap(diffs, n=4000, seed=7):
    rng = random.Random(seed)
    v = sorted(statistics.mean(diffs[rng.randrange(len(diffs))] for _ in diffs) for _ in range(n))
    return [round(v[int(0.025*n)], 4), round(v[int(0.975*n)], 4)]

def main():
    path = os.path.join(os.path.dirname(__file__), "data", "dmqa_1000.jsonl")
    rows = load(path); pool = build_pool(rows)
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    ver = train_verifier(train_rows(train, pool, distractors=100, top_k=5), use_agreement=False)
    scorer = collect_training(train[:400], pool)
    out = {}
    for budget in [2, 3]:
        for policy in ["random", "active", "learned_node", "oracle"]:
            runs = [run_policy(test, pool, ver, policy, budget=budget, seed=s, scorer=scorer) for s in range(3)]
            ms = [m for run in runs for m in run]
            out[f"B={budget},{policy}"] = {k: round(statistics.mean(m[k] for m in ms), 4) for k in ("both@2", "both@5", "recall@5", "mrr", "bytes")}
            print(f"B={budget},{policy}", out[f"B={budget},{policy}"])
    a = run_policy(test, pool, ver, "learned_node", budget=2, seed=0, scorer=scorer)
    b = run_policy(test, pool, ver, "active", budget=2, seed=0, scorer=scorer)
    d = [x["both@5"] - y["both@5"] for x, y in zip(a, b)]
    out["bootstrap_learned_minus_active_B2"] = {"diff": round(statistics.mean(d), 4), "ci95": bootstrap(d), "n": len(d)}
    print(out["bootstrap_learned_minus_active_B2"])
    with open(os.path.join(os.path.dirname(__file__), "results", "e11_node_scorer.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

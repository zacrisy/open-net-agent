# -*- coding: utf-8 -*-
"""E13: 10 nodes x topic-split — does the learned selector scale?"""
import json, random, statistics, os
from .data import load, build_pool
from .network import train_rows
from .verifier import train_verifier
from .active import run_policy, run_all_nodes
from .node_scorer import collect_training

def main():
    path = os.path.join(os.path.dirname(__file__), "data", "dmqa_dev.jsonl")
    rows = load(path); pool = build_pool(rows)
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    ver = train_verifier(train_rows(train, pool, distractors=50, top_k=5), use_agreement=False)
    scorer = collect_training(train, pool)
    out = {}
    for budget in [2, 4]:
        for policy in ["random", "learned_node", "oracle"]:
            ms = []
            for s in range(2):
                ms.extend(run_policy(test, pool, ver, policy, budget=budget, seed=s,
                                     n_nodes=10, scorer=scorer, topic_split=True))
            key = f"n10,topic,B={budget},{policy}"
            out[key] = {k: round(statistics.mean(m[k] for m in ms), 4) for k in ("both@2", "both@5", "recall@5", "mrr", "bytes")}
            print(key, out[key])
    alln = run_all_nodes(test, pool, ver, n_nodes=10, topic_split=True)
    out["n10,topic,all10"] = {k: round(statistics.mean(m[k] for m in alln), 4) for k in ("both@2", "both@5", "recall@5", "mrr", "bytes")}
    print("n10,topic,all10", out["n10,topic,all10"])
    with open(os.path.join(os.path.dirname(__file__), "results", "e13_topic_10nodes.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

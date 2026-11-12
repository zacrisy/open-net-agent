# -*- coding: utf-8 -*-
"""E4: fault injection / graceful degradation with replicated gold evidence."""
import json, random, statistics, os
from .data import load, build_pool
from .network import train_rows, run_episode
from .verifier import train_verifier

def main():
    rows = load(); pool = build_pool(rows)
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    ver = train_verifier(train_rows(train, pool, distractors=100, top_k=5))
    out = {}
    for replicas in [1, 2, 3]:
        for kill_n in [0, 1, 2]:
            ms = []
            for i, r in enumerate(test):
                rng = random.Random(1234 + i)
                killed = set(rng.sample(range(5), kill_n))
                m, _ = run_episode(r, pool, ver, mode="nbpw", distractors=100,
                                   replicas=replicas, killed=killed)
                ms.append(m)
            key = f"replicas={replicas},kill={kill_n}/5"
            out[key] = {k: round(statistics.mean(x[k] for x in ms), 4) for k in ("both@2", "both@5", "recall@5", "mrr")}
            print(key, out[key])
    with open(os.path.join(os.path.dirname(__file__), "results", "e4_fault.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

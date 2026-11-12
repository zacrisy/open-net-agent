# -*- coding: utf-8 -*-
"""E1: DMQA workspace vs baselines."""
import json, statistics, time, os
from .data import load, build_pool
from .network import train_rows, run_episode
from .verifier import train_verifier

def main():
    rows = load()
    pool = build_pool(rows)
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    t0 = time.time()
    eps = train_rows(train, pool, distractors=100, top_k=5)
    ver = train_verifier(eps)
    print(f"trained verifier on {len(eps)} questions in {time.time()-t0:.1f}s")
    modes = ["best_node", "central", "central_oracle", "flat_local", "flat_verifier",
             "nbpw", "no_verifier", "no_coalition", "no_novelty", "no_coverage"]
    out = {}
    for mode in modes:
        ms = []
        for r in test:
            m, _ = run_episode(r, pool, ver, mode=mode, distractors=100,
                               include_central=(mode in ("central", "central_oracle")))
            ms.append(m)
        out[mode] = {k: round(statistics.mean(x[k] for x in ms), 4) for k in ms[0]}
        out[mode]["n"] = len(ms)
        print(f"{mode:16s}", out[mode])
    with open(os.path.join(os.path.dirname(__file__), "results", "e1_dmqa.json"), "w", encoding="utf-8") as f:
        json.dump({"config": {"n_train": len(train), "n_test": len(test), "nodes": 5,
                              "distractors_per_node": 100, "top_k_local": 5, "workspace_k": 5},
                   "results": out, "seconds": round(time.time()-t0, 1)}, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

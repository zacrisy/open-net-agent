# -*- coding: utf-8 -*-
"""E1b: fair workspace test — verifier without cross-node agreement."""
import json, statistics, os
from .data import load, build_pool
from .network import train_rows, run_episode
from .verifier import train_verifier

def main():
    rows = load(); pool = build_pool(rows)
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    eps = train_rows(train, pool, distractors=100, top_k=5)
    ver = train_verifier(eps, use_agreement=False)
    modes = ["flat_local", "flat_verifier", "nbpw", "no_coalition", "no_novelty", "no_coverage", "no_verifier"]
    out = {}
    for mode in modes:
        ms = []
        for r in test:
            m, _ = run_episode(r, pool, ver, mode=mode, distractors=100, use_agreement=False)
            ms.append(m)
        out[mode] = {k: round(statistics.mean(x[k] for x in ms), 4) for k in ms[0]}
        print(mode, out[mode])
    with open(os.path.join(os.path.dirname(__file__), "results", "e1b_dmqa_local_verifier.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

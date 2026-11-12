# -*- coding: utf-8 -*-
"""Paired bootstrap for E1b: NBPW vs flat verifier."""
import json, random, statistics, os
from .data import load, build_pool
from .network import train_rows, run_episode
from .verifier import train_verifier

def main():
    rows = load(); pool = build_pool(rows)
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    ver = train_verifier(train_rows(train, pool, distractors=100, top_k=5), use_agreement=False)
    a, b = [], []
    for r in test:
        ma, _ = run_episode(r, pool, ver, mode="nbpw", distractors=100, use_agreement=False)
        mb, _ = run_episode(r, pool, ver, mode="flat_verifier", distractors=100, use_agreement=False)
        a.append(ma["both@5"]); b.append(mb["both@5"])
    diffs = [x - y for x, y in zip(a, b)]
    rng = random.Random(7)
    boots = []
    for _ in range(5000):
        idx = [rng.randrange(len(diffs)) for _ in diffs]
        boots.append(statistics.mean(diffs[i] for i in idx))
    boots.sort()
    boots.sort()
    out = {"n": len(diffs), "nbpw": round(statistics.mean(a), 4), "flat": round(statistics.mean(b), 4),
           "diff": round(statistics.mean(diffs), 4), "ci95": [round(boots[125], 4), round(boots[4875], 4)],
           "win": sum(1 for d in diffs if d > 0), "loss": sum(1 for d in diffs if d < 0)}
    print(out)
    with open(os.path.join(os.path.dirname(__file__), "results", "e1b_bootstrap.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Convert HotpotQA parquet into a compact JSONL for DMQA.

Run with a Python that has pandas+pyarrow (e.g. Python 3.12).
"""
import json, random, sys
import pandas as pd

SRC = sys.argv[1] if len(sys.argv) > 1 else "../../reasoning_lab/data/hotpot_validation.parquet"
OUT = sys.argv[2] if len(sys.argv) > 2 else "data/dmqa_dev.jsonl"
N = int(sys.argv[3]) if len(sys.argv) > 3 else 400
SEED = 20261106

df = pd.read_parquet(SRC)
rng = random.Random(SEED)
rows = []
for _, r in df.iterrows():
    sf = r["supporting_facts"]
    titles = list(sf["title"])
    sids = list(sf["sent_id"])
    if len(titles) != 2 or len(set(titles)) < 2:
        continue
    ctx = r["context"]
    ctitles = list(ctx["title"])
    csents = list(ctx["sentences"])
    if len(ctitles) < 10:
        continue
    paras = []
    for t, sents in zip(ctitles, csents):
        paras.append({"title": str(t), "text": " ".join(str(s) for s in sents).strip()})
    if not r["answer"] or not r["question"]:
        continue
    rows.append({
        "id": str(r["id"]),
        "question": str(r["question"]),
        "answer": str(r["answer"]),
        "type": str(r.get("type", "")),
        "level": str(r.get("level", "")),
        "support": [{"title": str(t), "sent_id": int(s)} for t, s in zip(titles, sids)],
        "paragraphs": paras,
    })
    if len(rows) >= N:
        break

rng.shuffle(rows)
n_train = int(len(rows) * 0.75)
for i, row in enumerate(rows):
    row["split"] = "train" if i < n_train else "test"
with open(OUT, "w", encoding="utf-8") as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
print(f"wrote {len(rows)} questions -> {OUT} (train={n_train}, test={len(rows)-n_train})")

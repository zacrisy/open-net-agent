# -*- coding: utf-8 -*-
"""E2: predictive coding Pareto (bytes vs both@5)."""
import json, statistics, time, os
from .data import load, build_pool
from .network import train_rows, collect, score_candidates
from .verifier import train_verifier
from .workspace import select
from .predictive import Predictor
from .network import _metrics

def bytes_of(hits):
    return sum(len(h.get("text", "")) for h in hits) + 40 * max(1, len(hits))

def run_pc(row, pool, ver, pred, n_nodes=5, distractors=100, top_k=5):
    ep = collect(row, pool, n_nodes=n_nodes, distractors=distractors, top_k=top_k)
    sent = []
    for hits in ep["per_node"]:
        if not hits:
            continue
        mx = max(h["local_score"] for h in hits)
        full, residual, mu = pred.gate(hits[0]["node"], mx)
        if full:
            sent.extend(hits)
        else:
            sent.extend(hits[:1])
    pred.tick()
    # dedupe/agreement on sent candidates
    tmp = {"candidates": sent, "question": row["question"], "gold": ep["gold"], "id": row["id"], "per_node": ep["per_node"]}
    # agreement
    counts = {}
    for c in sent:
        counts[c["title"]] = counts.get(c["title"], 0) + 1
    for c in sent:
        c["agreement"] = counts[c["title"]] / n_nodes
    cands = score_candidates(tmp, ver, n_nodes)
    selected, _ = select(cands, row["question"], K=5, mode="workspace", n_nodes=n_nodes)
    m = _metrics(selected, ep["gold"])
    m["bytes"] = bytes_of(sent)
    m["sent"] = len(sent)
    return m

def main():
    rows = load(); pool = build_pool(rows)
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    ver = train_verifier(train_rows(train, pool, distractors=100, top_k=5))
    out = {}
    for theta in [0.0, 0.02, 0.05, 0.1, 0.2, 0.5]:
        pred = Predictor(theta=theta, warmup=10)
        ms = [run_pc(r, pool, ver, pred) for r in test]
        out[str(theta)] = {k: round(statistics.mean(x[k] for x in ms), 4) for k in ("both@5", "recall@5", "mrr", "bytes", "sent")}
        print(theta, out[str(theta)])
    with open(os.path.join(os.path.dirname(__file__), "results", "e2_predictive.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

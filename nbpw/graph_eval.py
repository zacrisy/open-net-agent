#!/usr/bin/env python3
"""Synthetic diagnostic: flat lexical retrieval vs graph PPR.

This is not a substitute for a human-labeled benchmark. It measures whether
graph diffusion helps recover cards that share a topic/entity when the query
is deliberately under-specified.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from graph_retrieval import build_graph, lexical_seed, ppr, tokens  # noqa

CARDS = json.load(open(os.path.join(os.path.dirname(__file__), "continual_cards.json"), encoding="utf-8"))


def flat(query, k=5):
    seeds = lexical_seed(query, CARDS)
    return [cid for cid, _ in sorted(seeds.items(), key=lambda x: x[1], reverse=True)[:k]]


def evaluate_masked():
    rows = []
    for card in CARDS:
        claim = card.get("claim", "")
        toks = sorted(tokens(claim), key=len, reverse=True)
        if len(toks) < 3:
            continue
        key = toks[0]
        query = card.get("topic", "") + " " + " ".join(t for t in claim.split() if key.lower() not in t.lower())
        rows.append({"id": card["id"], "query": query, "gold": card["id"]})
    return rows


def evaluate_multihop(max_pairs=20):
    by_topic = {}
    for c in CARDS:
        by_topic.setdefault(c.get("topic", ""), []).append(c)
    pairs = []
    for topic, items in by_topic.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = tokens(items[i].get("claim", "")), tokens(items[j].get("claim", ""))
                shared = a & b
                if len(shared) >= 2:
                    q = topic + " " + " ".join(list(a)[:4]) + " " + " ".join(list(b)[:4])
                    pairs.append({"query": q, "gold": [items[i]["id"], items[j]["id"]]})
                    if len(pairs) >= max_pairs:
                        return pairs
    return pairs


def evaluate_association(max_pairs=20):
    """Query card A, expect related card B that actually has a support edge."""
    graph = build_graph(CARDS)
    pairs = []
    seen = set()
    for e in graph["edges"]:
        if e["kind"] != "supports":
            continue
        a = graph["nodes"][e["source"]]
        b = graph["nodes"][e["target"]]
        key = (a["id"], b["id"])
        if key in seen:
            continue
        seen.add(key)
        q = a.get("topic", "") + " " + " ".join(list(tokens(a.get("claim", "")))[:6])
        pairs.append({"query": q, "gold": b["id"]})
        if len(pairs) >= max_pairs:
            break
    return pairs

def run():
    graph = build_graph(CARDS)
    masked = evaluate_masked()
    multi = evaluate_multihop()
    assoc = evaluate_association()
    out = {"cards": len(CARDS), "edges": len(graph["edges"]), "masked": {"n": len(masked)}, "multihop": {"n": len(multi)}, "association": {"n": len(assoc)}}
    for name, rows, key in (("masked", masked, "top1"), ("multihop", multi, "cover3"), ("association", assoc, "top3")):
        flat_hits = 0; ppr_hits = 0
        for r in rows:
            gold = r["gold"] if isinstance(r["gold"], list) else [r["gold"]]
            f = flat(r["query"], 5); p = [c["id"] for c in ppr(r["query"], CARDS, graph, k=5)["cards"]]
            if key == "top1":
                flat_hits += int(bool(f) and f[0] in gold)
                ppr_hits += int(bool(p) and p[0] in gold)
            elif key == "cover3":
                flat_hits += int(len(set(f[:3]) & set(gold)) == len(gold))
                ppr_hits += int(len(set(p[:3]) & set(gold)) == len(gold))
            else:
                flat_hits += int(len(set(f[:3]) & set(gold)) > 0)
                ppr_hits += int(len(set(p[:3]) & set(gold)) > 0)
        out[name][f"flat_{key}"] = round(flat_hits / max(1, len(rows)), 3)
        out[name][f"ppr_{key}"] = round(ppr_hits / max(1, len(rows)), 3)
    with open(os.path.join(os.path.dirname(__file__), "graph_results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    run()

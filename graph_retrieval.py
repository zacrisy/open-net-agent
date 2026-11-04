# -*- coding: utf-8 -*-
"""Typed knowledge graph + Personalized PageRank retrieval.

Cards are nodes; supports/contradicts/same_topic are edges. A query seeds
lexically matching cards, then PPR diffuses activation over the graph.
"""
import json, math, re, time

_TOKEN = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{2,}|[\u4e00-\u9fff]{2,}")


def tokens(text):
    return set(x.lower() for x in _TOKEN.findall(text or ""))


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def build_graph(cards, extra_edges=None):
    """Build an undirected weighted card graph. extra_edges: (src,dst,kind)."""
    nodes = {c["id"]: c for c in cards}
    by_topic = {}
    for c in cards:
        by_topic.setdefault(c.get("topic", ""), []).append(c)
    edges = []
    seen = set()

    def add(a, b, kind, w):
        if a == b or a not in nodes or b not in nodes:
            return
        key = (a, b) if a < b else (b, a)
        if (key, kind) in seen:
            return
        seen.add((key, kind))
        edges.append({"source": a, "target": b, "kind": kind, "weight": round(w, 4)})

    for topic, items in by_topic.items():
        for i in range(len(items)):
            ti = tokens(items[i].get("claim", "") + " " + items[i].get("evidence", ""))
            for j in range(i + 1, len(items)):
                tj = tokens(items[j].get("claim", "") + " " + items[j].get("evidence", ""))
                sim = _jaccard(ti, tj)
                if sim >= 0.08:
                    add(items[i]["id"], items[j]["id"], "supports", min(1.0, sim * 2))
    for src, dst, kind in (extra_edges or []):
        add(src, dst, "contradicts" if "contradict" in str(kind).lower() else "supports", 0.8 if "contradict" in str(kind).lower() else 0.5)
    adj = {n: [] for n in nodes}
    for e in edges:
        adj[e["source"]].append((e["target"], e["weight"]))
        adj[e["target"]].append((e["source"], e["weight"]))
    return {"nodes": nodes, "edges": edges, "adj": adj}


def lexical_seed(query, cards):
    qt = tokens(query)
    if not qt:
        return {}
    df = {}
    dts = {}
    for c in cards:
        text = " ".join([c.get("claim", ""), c.get("evidence", ""), c.get("topic", ""), (c.get("source") or {}).get("title", "")])
        ct = tokens(text)
        dts[c["id"]] = ct
        for t in ct:
            df[t] = df.get(t, 0) + 1
    import math
    idf = {t: math.log((len(cards) + 1) / (df.get(t, 0) + 1)) + 1 for t in qt}
    total = sum(idf.values()) or 1.0
    seeds = {}
    for c in cards:
        ct = dts[c["id"]]
        score = sum(idf[t] for t in (qt & ct)) / total
        topic_bonus = 0.15 if tokens(c.get("topic", "")) & qt else 0.0
        if score:
            seeds[c["id"]] = score + topic_bonus
    return seeds


def ppr(query, cards, graph=None, k=5, alpha=0.35, iters=15):
    graph = graph or build_graph(cards)
    seeds = lexical_seed(query, cards)
    if not seeds:
        return {"query": query, "cards": [], "seeds": [], "edges": len(graph["edges"]), "engine": "ppr-empty"}
    total = sum(seeds.values())
    seed = {nid: v / total for nid, v in seeds.items()}
    p = dict(seed)
    for _ in range(iters):
        new = {nid: (1 - alpha) * seed.get(nid, 0.0) for nid in graph["nodes"]}
        for u, nbrs in graph["adj"].items():
            if not nbrs:
                continue
            deg = sum(w for _, w in nbrs) or 1.0
            pu = p.get(u, 0.0)
            if not pu:
                continue
            for v, w in nbrs:
                new[v] += alpha * pu * w / deg
        s = sum(new.values()) or 1.0
        p = {nid: v / s for nid, v in new.items()}
    # hybrid: lexical seeds + one-hop associated cards + PPR mass
    seed_rank = sorted(seed.items(), key=lambda x: x[1], reverse=True)
    final = {}
    for nid, sv in seed_rank[:5]:
        final[nid] = max(final.get(nid, 0.0), sv * 1.0)
        for v, w in graph["adj"].get(nid, []):
            final[v] = max(final.get(v, 0.0), sv * w * 0.9)
    for nid, pv in p.items():
        final[nid] = final.get(nid, 0.0) + 0.25 * pv
    ranked = sorted(final.items(), key=lambda x: x[1], reverse=True)
    selected = []
    if seed_rank:
        selected.append(seed_rank[0][0])
        nbrs = graph["adj"].get(seed_rank[0][0], [])
        if nbrs:
            selected.append(max(nbrs, key=lambda x: x[1])[0])
    for nid, _ in ranked:
        if nid not in selected:
            selected.append(nid)
        if len(selected) >= k:
            break
    top = []
    for nid in selected[:k]:
        c = dict(graph["nodes"][nid])
        c["score"] = round(final.get(nid, 0.0), 5)
        top.append(c)
    return {"query": query, "cards": top, "seeds": [{"id": i, "score": round(v, 4)} for i, v in sorted(seeds.items(), key=lambda x: x[1], reverse=True)[:3]],
            "edges": len(graph["edges"]), "engine": "ppr"}


_CACHE = {"key": None, "graph": None, "ts": 0}


def retrieve(query, k=5):
    import brain
    cards = brain.cards(1000)
    key = (len(cards), cards[0]["id"] if cards else "")
    now = time.time()
    if _CACHE["key"] != key or now - _CACHE["ts"] > 60:
        c = brain._conn()
        rows = c.execute("SELECT src,dst,kind FROM edges").fetchall()
        c.close()
        _CACHE.update({"key": key, "graph": build_graph(cards, rows), "ts": now})
    return ppr(query, cards, _CACHE["graph"], k=k)

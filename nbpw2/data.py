# -*- coding: utf-8 -*-
"""DMQA data: HotpotQA questions with paragraph shards."""
import json, re, random, os, hashlib

STOP = set("""a an the and or of to in on for with by from at as is are was were be been being
this that these those it its their his her they he she we you i not no do does did
what which who whom whose when where why how many much more most other into than then
""".split())
TOKEN = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]+")

def stable_hash(text):
    return int(hashlib.md5(str(text).encode("utf-8")).hexdigest()[:8], 16)

def tokens(text):
    return [t.lower() for t in TOKEN.findall(text or "") if t.lower() not in STOP and len(t) > 1]

def load(path=None):
    path = path or os.path.join(os.path.dirname(__file__), "data", "dmqa_dev.jsonl")
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows

def paragraph_key(p):
    return (p.get("title", ""), p.get("text", ""))

def build_pool(rows):
    pool, seen = [], set()
    for r in rows:
        for p in r["paragraphs"]:
            k = paragraph_key(p)
            if k not in seen:
                seen.add(k)
                pool.append({"title": p["title"], "text": p["text"]})
    return pool

def make_shards(row, pool, n_nodes=5, distractors_per_node=98, top_k=5, seed=0, replicas=1, gold_nodes=None, topic_split=False):
    """Assign question paragraphs + distractors to nodes.

    Gold paragraphs are placed on distinct nodes (and optionally replicated)
    so that no single node can see both gold paragraphs.
    """
    rng = random.Random(stable_hash(row["id"]) ^ seed)
    gold_titles = []
    for s in row["support"]:
        if s["title"] not in gold_titles:
            gold_titles.append(s["title"])
    gold_titles = gold_titles[:2]
    paras = list(row["paragraphs"])
    by_title = {p["title"]: p for p in paras}
    gold_paras = [by_title[t] for t in gold_titles if t in by_title]
    other = [p for p in paras if p["title"] not in set(gold_titles)]
    rng.shuffle(other)

    nodes = [{"id": i, "docs": []} for i in range(n_nodes)]
    # gold placement: distinct nodes, replicated if requested
    for gi, p in enumerate(gold_paras):
        if gold_nodes:
            base = gold_nodes[gi % len(gold_nodes)]
            targets = [(base + r) % n_nodes for r in range(max(1, replicas))]
        else:
            targets = [(gi * max(1, replicas) + r) % n_nodes for r in range(max(1, replicas))]
        for nid in targets:
            nodes[nid]["docs"].append({"title": p["title"], "text": p["text"], "is_gold": True, "node": nid})
    # remaining question paragraphs round-robin
    for j, p in enumerate(other):
        nid = (len(gold_paras) + j) % n_nodes
        nodes[nid]["docs"].append({"title": p["title"], "text": p["text"], "is_gold": False, "node": nid})
    # distractors from pool (exclude current question paragraphs)
    cur = set(paragraph_key(p) for p in paras)
    cand = [p for p in pool if paragraph_key(p) not in cur]
    if topic_split:
        # realistic sharding: group distractors by title, assign whole topics to nodes
        by_topic = {}
        for p in cand:
            by_topic.setdefault(p["title"], []).append(p)
        topics = list(by_topic)
        rng.shuffle(topics)
        buckets = [[] for _ in range(n_nodes)]
        for i, t in enumerate(topics):
            buckets[i % n_nodes].extend(by_topic[t])
        for n in nodes:
            n["topic_pool"] = buckets[n["id"]]
    for n in nodes:
        need = max(0, distractors_per_node - len(n["docs"]))
        if topic_split:
            pool_n = n.pop("topic_pool", [])
            picks = rng.sample(pool_n, min(need, len(pool_n)))
        else:
            picks = rng.sample(cand, min(need, len(cand)))
        for p in picks:
            n["docs"].append({"title": p["title"], "text": p["text"], "is_gold": False, "node": n["id"]})
        rng.shuffle(n["docs"])
    return nodes, set(gold_titles)

def make_central(row, pool, n_extra=200, seed=0):
    """Centralized index: all question paragraphs + random global distractors."""
    rng = random.Random(stable_hash(row["id"]) ^ seed ^ 0x9e3779b9)
    docs = [{"title": p["title"], "text": p["text"], "is_gold": p["title"] in {s["title"] for s in row["support"]}, "node": -1} for p in row["paragraphs"]]
    cur = set(paragraph_key(p) for p in row["paragraphs"])
    cand = [p for p in pool if paragraph_key(p) not in cur]
    for p in rng.sample(cand, min(n_extra, len(cand))):
        docs.append({"title": p["title"], "text": p["text"], "is_gold": False, "node": -1})
    return docs

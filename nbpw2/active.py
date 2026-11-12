# -*- coding: utf-8 -*-
"""Active evidence gathering: choose which nodes to query under a budget."""
import random, math, statistics
from .data import make_shards, tokens
from .retrieval import Index
from .dense import recall
from .network import score_candidates, _metrics
from .workspace import select

def gold_nodes_for(row, n_nodes=5, seed=0):
    from .data import stable_hash
    rng = random.Random(stable_hash(row["id"]) ^ seed ^ 0xA11CE)
    return tuple(rng.sample(range(n_nodes), 2))

class ActiveEnv:
    def __init__(self, row, pool, n_nodes=5, distractors=100, top_k=5, seed=0, gold_nodes=None, scorer=None, topic_split=False):
        self.row = row
        self.scorer = scorer
        self.n_nodes = n_nodes
        self.top_k = top_k
        self.nodes, self.gold = make_shards(
            row, pool, n_nodes=n_nodes, distractors_per_node=distractors,
            top_k=top_k, seed=seed, replicas=1, gold_nodes=gold_nodes,
            topic_split=topic_split)
        self.idx = {}
        self.profile = {}
        self.title_profile = {}
        self.bm25_scores = {}  # node-local BM25 sum for active_hybrid policy
        self.node_top = {}     # node-local top-3 hits, reused by bridge_hop
        self.qt = set(tokens(row["question"]))
        for n in self.nodes:
            toks, titles = set(), set()
            for d in n["docs"]:
                titles |= set(tokens(d["title"]))
                toks |= set(tokens(d["title"]))
                toks |= set(tokens(d["text"][:160]))
            self.profile[n["id"]] = toks
            self.title_profile[n["id"]] = titles
            # Pre-build node-local BM25 index + score (used by active_hybrid)
            idx = Index(n["docs"])
            hits = idx.search(row["question"], k=3)
            self.node_top[n["id"]] = hits
            self.bm25_scores[n["id"]] = sum(h.get("local_score", 0) for h in hits)
            self.idx[n["id"]] = idx  # pre-build so query() is fast
        self.ok = {}
        self.fail = {}
        self.queried = []
        self.candidates = []
        self.bytes = 0.0
        self.latency = 0.0

    def query(self, nid):
        if nid in self.queried:
            return []
        self.queried.append(nid)
        hits = recall(self.row["question"], self.nodes[nid]["docs"], self.top_k)
        for h in hits:
            h["node"] = nid
            h["node_rel"] = 0.5
            h["agreement"] = 1.0 / max(1, self.n_nodes)
        self.candidates.extend(hits)
        self.bytes += sum(len(h.get("text", "")) for h in hits) + 40
        self.latency += 0.02 + 0.002 * len(hits)
        return hits

    def node_reliability(self, nid):
        ok, fail = self.ok.get(nid, 1), self.fail.get(nid, 1)
        return ok / (ok + fail)

    def finish(self, verifier, use_agreement=False, readout=None):
        if not self.candidates:
            return {"both@2": 0.0, "both@5": 0.0, "recall@5": 0.0, "mrr": 0.0,
                    "queries": len(self.queried), "bytes": self.bytes, "latency": self.latency}
        from . import readout as _ro
        mode = _ro.mode() if readout is None else readout
        if mode == "fast":
            tmp = {"candidates": self.candidates, "question": self.row["question"],
                   "gold": self.gold, "id": self.row["id"]}
            cands = score_candidates(tmp, verifier, self.n_nodes, use_agreement=use_agreement)
        else:
            p = _ro.score_candidates(self.candidates, self.row["question"], self.row["id"],
                                     mode=mode, verifier=verifier, n_nodes=self.n_nodes)
            cands = self.candidates
            for c, v in zip(cands, p):
                c["verifier"] = float(v)
        selected, _ = select(cands, self.row["question"], K=5, mode="workspace", n_nodes=self.n_nodes)
        m = _metrics(selected, self.gold)
        m.update({"queries": len(self.queried), "bytes": self.bytes, "latency": self.latency})
        return m

def qtype(q):
    q = q.lower()
    return 1 if any(k in q for k in ("same", "both", "which", "more", "less")) else 0

def choose(policy, env, rng, stats, ctx_stats, t):
    un = [i for i in range(env.n_nodes) if i not in env.queried]
    if not un:
        return None
    if policy == "random":
        return rng.choice(un)
    if policy == "round_robin":
        return min(un)
    if policy == "ucb":
        def sc(i):
            ok, fail = stats.get(i, (1, 1))
            return ok / (ok + fail) + 0.35 * math.sqrt(math.log(t + 2) / (ok + fail))
        return max(un, key=sc)
    if policy == "context_ucb":
        typ = qtype(env.row["question"])
        def sc(i):
            ok, fail = ctx_stats.get((typ, i), (1, 1))
            return ok / (ok + fail) + 0.35 * math.sqrt(math.log(t + 2) / (ok + fail))
        return max(un, key=sc)
    if policy == "active":
        qt = env.qt
        covered = set()
        for c in env.candidates:
            covered |= (qt & set(tokens(c.get("text", ""))))
        typ = qtype(env.row["question"])
        def sc(i):
            title_gain = len((qt & env.title_profile[i]) - covered) / max(1, len(qt))
            content_gain = len((qt & env.profile[i]) - covered) / max(1, len(qt))
            ok, fail = ctx_stats.get((typ, i), (1, 1))
            q = ok / (ok + fail)
            return 0.7 * title_gain + 0.3 * content_gain + 0.15 * q - 0.02
        return max(un, key=sc)
    if policy == "active_hybrid":
        """BM25 + token overlap hybrid: 0.35*title + 0.25*content + 0.4*bm25 + 0.15*q - 0.02"""
        qt = env.qt
        covered = set()
        for c in env.candidates:
            covered |= (qt & set(tokens(c.get("text", ""))))
        typ = qtype(env.row["question"])
        def sc(i):
            title_gain = len((qt & env.title_profile[i]) - covered) / max(1, len(qt))
            content_gain = len((qt & env.profile[i]) - covered) / max(1, len(qt))
            bm25 = env.bm25_scores.get(i, 0)
            ok, fail = ctx_stats.get((typ, i), (1, 1))
            q = ok / (ok + fail)
            return 0.35 * title_gain + 0.25 * content_gain + 0.4 * bm25 + 0.15 * q - 0.02
        return max(un, key=sc)
    if policy == "bridge_hop":
        """Second hop: condition the next node on the best paragraph already seen.

        Base score = active_hybrid.  Add bridge evidence: a capitalised entity
        from the anchor paragraph (minus query entities) that also appears in the
        candidate node's top hits.  The first query is identical to hybrid.
        """
        from .verifier import caps
        qt = env.qt
        covered = set()
        for c in env.candidates:
            covered |= (qt & set(tokens(c.get("text", ""))))
        typ = qtype(env.row["question"])
        anchor = max(env.candidates, key=lambda c: c.get("local_score", 0.0)) if env.candidates else None
        qcaps = caps(env.row["question"])
        acaps = (caps(anchor.get("title", "") + " " + anchor.get("text", "")) - qcaps) if anchor else set()

        def sc(i):
            title_gain = len((qt & env.title_profile[i]) - covered) / max(1, len(qt))
            content_gain = len((qt & env.profile[i]) - covered) / max(1, len(qt))
            bm25 = env.bm25_scores.get(i, 0)
            ok, fail = ctx_stats.get((typ, i), (1, 1))
            q = ok / (ok + fail)
            br = 0.0
            if acaps:
                for h in env.node_top.get(i, []):
                    hc = caps(h.get("title", "") + " " + h.get("text", "")) - qcaps
                    if hc:
                        br = max(br, len(acaps & hc) / max(1, len(acaps)),
                                 len(acaps & hc) / max(1, len(hc)))
            return 0.35 * title_gain + 0.25 * content_gain + 0.4 * bm25 + 0.15 * q - 0.02 + 0.35 * br
        return max(un, key=sc)
    if policy == "learned_node":
        from .node_scorer import node_features
        un = [i for i in range(env.n_nodes) if i not in env.queried]
        if not un:
            return None
        X = [node_features(env, i) for i in un]
        p = env.scorer.predict(X)
        return un[int(max(range(len(un)), key=lambda k: p[k]))]
    if policy == "oracle":
        gold_nodes = [i for i in range(env.n_nodes) if any(d.get("is_gold") for d in env.nodes[i]["docs"])]
        for i in gold_nodes:
            if i in un:
                return i
        return rng.choice(un)
    return rng.choice(un)

def update_stats(stats, ctx_stats, env, nid):
    gold_hit = any(h.get("title") in env.gold for h in env.candidates if h.get("node") == nid)
    ok, fail = stats.get(nid, (1, 1))
    stats[nid] = (ok + (1 if gold_hit else 0), fail + (0 if gold_hit else 1))
    typ = qtype(env.row["question"])
    ok, fail = ctx_stats.get((typ, nid), (1, 1))
    ctx_stats[(typ, nid)] = (ok + (1 if gold_hit else 0), fail + (0 if gold_hit else 1))

def run_policy(rows, pool, verifier, policy, budget=2, seed=0, n_nodes=5, scorer=None, topic_split=False):
    rng = random.Random(seed)
    stats, ctx_stats = {}, {}
    ms = []
    for t, row in enumerate(rows):
        env = ActiveEnv(row, pool, n_nodes=n_nodes, gold_nodes=gold_nodes_for(row, n_nodes=n_nodes, seed=seed), scorer=scorer, topic_split=topic_split)
        while len(env.queried) < budget:
            nid = choose(policy, env, rng, stats, ctx_stats, t)
            if nid is None:
                break
            hits = env.query(nid)
            gold_hit = any(h.get("title") in env.gold for h in hits)
            env.ok[nid] = env.ok.get(nid, 1) + (1 if gold_hit else 0)
            env.fail[nid] = env.fail.get(nid, 0) + (0 if gold_hit else 1)
            update_stats(stats, ctx_stats, env, nid)
        ms.append(env.finish(verifier))
    return ms

def run_all_nodes(rows, pool, verifier, n_nodes=5, topic_split=False):
    ms = []
    for row in rows:
        env = ActiveEnv(row, pool, n_nodes=n_nodes, gold_nodes=gold_nodes_for(row, n_nodes=n_nodes), topic_split=topic_split)
        for i in range(env.n_nodes):
            env.query(i)
        ms.append(env.finish(verifier))
    return ms

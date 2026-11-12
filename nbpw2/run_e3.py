# -*- coding: utf-8 -*-
"""E3: routing / active node selection on heterogeneous synthetic nodes."""
import json, math, random, statistics, os
from dataclasses import dataclass, field

TYPES = 3
NODES = 20
M = 3

@dataclass
class Node:
    id: int
    spec: list
    q: float
    lat: float
    cost: float
    rel: float
    ok: int = 0
    fail: int = 0
    alive: bool = True
    def p(self, t):
        return max(0.0, min(0.99, self.q * (0.55 + 0.45 * self.spec[t])))
    def qhat(self):
        return (self.ok + 1) / (self.ok + self.fail + 2)

def make_nodes(seed):
    rng = random.Random(seed)
    out = []
    for i in range(NODES):
        spec = [rng.random() for _ in range(TYPES)]
        out.append(Node(i, spec, rng.uniform(0.55, 0.95),
                        max(0.01, rng.lognormvariate(-3.5, 0.5)),
                        rng.uniform(1, 8), rng.uniform(0.85, 0.99)))
    return out

def select(policy, nodes, t, rng, state, typ):
    cap = [n for n in nodes if n.alive]
    if not cap:
        return []
    if policy == "random":
        return rng.sample(cap, min(M, len(cap)))
    if policy == "ucb":
        ranked = sorted(cap, key=lambda n: n.qhat() + 0.35 * math.sqrt(math.log(t + 2) / (n.ok + n.fail + 1)), reverse=True)
        return ranked[:M]
    if policy == "context_ucb":
        st = state.setdefault("ctx", {})
        ranked = sorted(cap, key=lambda n: st.get((typ, n.id), (1.0, 1.0)))
        # use per-type qhat with exploration
        def score(n):
            ok, fail = st.get((typ, n.id), (1.0, 1.0))
            return ok / (ok + fail) + 0.35 * math.sqrt(math.log(t + 2) / (ok + fail))
        return sorted(cap, key=score, reverse=True)[:M]
    if policy == "nbpw":
        st = state.setdefault("ctx", {})
        def score(n):
            ok, fail = st.get((typ, n.id), (1.0, 1.0))
            return ok / (ok + fail) + 0.30 * math.sqrt(math.log(t + 2) / (ok + fail)) - 0.12 * n.lat - 0.01 * n.cost
        return sorted(cap, key=score, reverse=True)[:M]
    if policy == "oracle":
        return sorted(cap, key=lambda n: n.p(typ), reverse=True)[:M]
    return cap[:M]

def run(policy, seed, n_queries=1000):
    rng = random.Random(seed)
    nodes = make_nodes(seed)
    state = {}
    succ, lat, byt = [], [], []
    for t in range(n_queries):
        if t == n_queries // 2:
            for n in rng.sample(nodes, NODES // 5):
                n.alive = False
        typ = rng.randrange(TYPES)
        sel = [n for n in select(policy, nodes, t, rng, state, typ) if rng.random() < n.rel]
        if not sel:
            succ.append(0); lat.append(1.0); byt.append(0.0); continue
        votes = []
        for n in sel:
            ok = rng.random() < n.p(typ)
            votes.append((n, ok))
            st = state.setdefault("ctx", {})
            k = (typ, n.id)
            a, b = st.get(k, (1.0, 1.0))
            st[k] = (a + (1 if ok else 0), b + (1 if not ok else 0))
            if ok: n.ok += 1
            else: n.fail += 1
        w_ok = sum(n.qhat() for n, ok in votes if ok)
        w_bad = sum(n.qhat() for n, ok in votes if not ok)
        correct = 1 if w_ok > w_bad else 0
        succ.append(correct)
        lat.append(max(n.lat for n, _ in votes) + 0.004 * len(votes))
        byt.append(sum(n.cost for n, _ in votes))
    def pct(xs, p):
        xs = sorted(xs); return xs[min(len(xs)-1, int(len(xs)*p))]
    return {"success": sum(succ)/len(succ), "p50": pct(lat,.5), "p95": pct(lat,.95),
            "bytes": sum(byt)/len(byt), "windows": [sum(succ[i:i+50])/len(succ[i:i+50]) for i in range(0,len(succ),50)]}

def main():
    policies = ["random", "ucb", "context_ucb", "nbpw", "oracle"]
    out = {}
    for p in policies:
        runs = [run(p, seed) for seed in range(5)]
        out[p] = {k: round(statistics.mean(r[k] for r in runs), 4) for k in ("success","p50","p95","bytes")}
        out[p]["success_sd"] = round(statistics.pstdev(r["success"] for r in runs), 4)
        out[p]["windows"] = [round(statistics.mean(r["windows"][i] for r in runs),3) for i in range(len(runs[0]["windows"]))]
        print(f"{p:12s}", out[p])
    with open(os.path.join(os.path.dirname(__file__), "results", "e3_routing.json"), "w", encoding="utf-8") as f:
        json.dump({"config": {"nodes": NODES, "m": M, "types": TYPES, "queries": 1000, "seeds": 5},
                   "results": out}, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

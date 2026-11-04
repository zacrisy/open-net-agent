# -*- coding: utf-8 -*-
"""NBPW simulation primitives: heterogeneous nodes, routing policies, workspace."""
import math, random
from dataclasses import dataclass, field

SKILLS = ["retrieval", "nli", "web"]


@dataclass
class Node:
    id: int
    skills: list
    quality: float
    latency: float
    cost: float
    reliability: float
    ok: int = 0
    fail: int = 0
    alive: bool = True

    def capable(self, skill):
        return self.alive and skill in self.skills

    def qhat(self):
        return (self.ok + 1) / (self.ok + self.fail + 2)

    def responds(self, rng):
        return self.alive and rng.random() < self.reliability


def make_nodes(n=30, seed=0):
    rng = random.Random(seed)
    nodes = []
    for i in range(n):
        skills = rng.sample(SKILLS, rng.randint(1, 3))
        nodes.append(Node(i, skills, rng.uniform(0.55, 0.95),
                          max(0.01, rng.lognormvariate(-3.6, 0.45)),
                          rng.uniform(1, 8), rng.uniform(0.85, 0.99)))
    return nodes


def choose(policy, query, nodes, t, rng, k=3):
    capable = [n for n in nodes if n.capable(query)]
    if not capable:
        return []
    if policy == "random":
        return [rng.choice(capable)]
    if policy == "ucb":
        best = max(capable, key=lambda n: n.qhat() + 0.35 * math.sqrt(math.log(t + 2) / (n.ok + n.fail + 1)))
        return [best]
    if policy == "moe":
        best = max(capable, key=lambda n: n.qhat() - 0.35 * n.latency - 0.01 * n.cost)
        return [best]
    # nbpw: capability + exploration - latency/cost, top-k workspace
    scored = sorted(capable, key=lambda n: n.qhat() + 0.18 * math.sqrt(math.log(t + 2) / (n.ok + n.fail + 1))
                    - 0.30 * n.latency - 0.008 * n.cost, reverse=True)
    return scored[:k]


def run(policy, n_queries=800, n_nodes=30, seed=0, k=3):
    rng = random.Random(seed)
    nodes = make_nodes(n_nodes, seed)
    success, lat, byt = [], [], []
    windows = {}
    for t in range(n_queries):
        if t == n_queries // 2:
            for n in rng.sample(nodes, max(1, n_nodes // 5)):
                n.alive = False
        query = rng.choice(SKILLS)
        selected = [n for n in choose(policy, query, nodes, t, rng, k) if n.responds(rng)]
        if not selected:
            success.append(0); lat.append(1.0); byt.append(0.0)
            windows.setdefault(t // 50, []).append(0)
            continue
        # each selected node answers; correctness is a latent probability
        answers = [(n, rng.random() < n.quality) for n in selected]
        if policy == "nbpw":
            w_ok = sum(n.qhat() for n, ok in answers if ok)
            w_bad = sum(n.qhat() for n, ok in answers if not ok)
            correct = w_ok > w_bad
            for n, ok in answers:
                if ok: n.ok += 1
                else: n.fail += 1
        else:
            n, ok = answers[0]
            correct = ok
            if ok: n.ok += 1
            else: n.fail += 1
        success.append(1 if correct else 0)
        lat.append(max(n.latency for n, _ in answers) + (0.005 if len(answers) > 1 else 0.0))
        byt.append(sum(n.cost for n, _ in answers))
        w = t // 50
        windows.setdefault(w, []).append(1 if correct else 0)
    def pct(xs, p):
        xs = sorted(xs); return xs[min(len(xs) - 1, int(len(xs) * p))]
    return {"policy": policy, "success": sum(success) / len(success),
            "p50": pct(lat, .5), "p95": pct(lat, .95), "p99": pct(lat, .99), "bytes": sum(byt) / len(byt),
            "windows": [sum(v) / len(v) for _, v in sorted(windows.items())]}

# -*- coding: utf-8 -*-
"""Learned node scorer: which node should we query next?

Replaces the hand-crafted profile heuristic with a small logistic model over
node-level features (topic-centroid similarity, title overlap, coverage gain,
reliability, load).
"""
import numpy as np
from .data import tokens

def _jacc(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

class NodeScorer:
    def __init__(self, l2=1e-3, lr=0.2, epochs=600):
        self.l2, self.lr, self.epochs = l2, lr, epochs
        self.w = None
        self.mu = None
        self.sd = None

    def fit(self, X, y):
        X = np.asarray(X, float); y = np.asarray(y, float)
        self.mu = X.mean(0); self.sd = X.std(0) + 1e-8
        Z = (X - self.mu) / self.sd
        pos = max(1.0, y.sum()); neg = max(1.0, len(y) - y.sum())
        sw = np.where(y > 0.5, len(y) / (2 * pos), len(y) / (2 * neg))
        w = np.zeros(Z.shape[1])
        for _ in range(self.epochs):
            p = 1.0 / (1.0 + np.exp(-np.clip(Z @ w, -30, 30)))
            w -= self.lr * (Z.T @ (sw * (p - y)) / len(y) + self.l2 * w)
        self.w = w
        return self

    def predict(self, X):
        X = np.atleast_2d(np.asarray(X, float))
        Z = (X - self.mu) / self.sd
        return 1.0 / (1.0 + np.exp(-np.clip(Z @ self.w, -30, 30)))

def node_features(env, nid):
    qt = set(tokens(env.row["question"]))
    qcap = set(t.lower() for t in qt if t[:1].isupper())
    titles = env.title_profile.get(nid, set())
    prof = env.profile.get(nid, set())
    covered = set()
    for c in env.candidates:
        covered |= (qt & set(tokens(c.get("text", ""))))
    # title centroid similarity: rank-0 title tokens
    title_gain = len((qt & titles) - covered) / max(1, len(qt))
    content_gain = len((qt & prof) - covered) / max(1, len(qt))
    jac = _jacc(qt, prof)
    # how many titles on this node contain >=2 query tokens
    strong = 0
    for d in env.nodes[nid]["docs"]:
        tt = set(tokens(d["title"]))
        if len(tt & qt) >= 2:
            strong += 1
    strong = min(1.0, strong / 5.0)
    reached = 1.0 if nid in env.queried else 0.0
    pos = env.queried.index(nid) / max(1, env.n_nodes) if reached else 1.0
    return [title_gain, content_gain, jac, strong, reached, pos,
            env.node_reliability(nid), len(env.nodes[nid]["docs"]) / 200.0]

def collect_training(rows, pool, n_nodes=5, seed=0):
    """Feature/label pairs from 'query every node' rollouts."""
    from .active import ActiveEnv, gold_nodes_for
    X, y = [], []
    for row in rows:
        env = ActiveEnv(row, pool, n_nodes=n_nodes, gold_nodes=gold_nodes_for(row, n_nodes=n_nodes, seed=seed))
        for nid in range(n_nodes):
            f = node_features(env, nid)
            hits = env.query(nid)
            label = 1.0 if any(h.get("title") in env.gold for h in hits) else 0.0
            X.append(f); y.append(label)
    return NodeScorer().fit(X, y)

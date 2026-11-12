# -*- coding: utf-8 -*-
"""Learned candidate verifier (logistic regression, numpy only)."""
import math, re
import numpy as np
from .data import tokens

CAP = re.compile(r"\b[A-Z][a-zA-Z0-9_-]{1,}\b")

def _jacc(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

def caps(text):
    return set(x.lower() for x in CAP.findall(text or ""))

def squash_rank(r):
    """Saturating map from raw 0-based rank to the k=5 feature range.

    The shipped rank features were linear in `rank` (`1 - rank/5` in the
    readout, `rank/5` in the pair head).  Both are only defined on a 5-item
    shortlist: at k=20 the readout feature reaches -3 and the head feature 3.8,
    at k=40 -7 / 7.8, i.e. pure extrapolation.  4r/(r+4) keeps rank 0..4 on
    {0,.8,1.33,1.71,2.0} and only reaches 3.7 at rank 50.
    """
    r = float(r)
    if r <= 0.0:
        return 0.0
    return 4.0 * r / (r + 4.0)

def candidate_features(c, query, all_cands, n_nodes, max_local, node_rel=0.5, use_agreement=True):
    qt = set(tokens(query))
    tt = set(tokens(c.get("title", "")))
    dt = set(tokens(c.get("text", "")))
    qcap = caps(query)
    tcap = caps(c.get("title", "") + " " + c.get("text", ""))
    overlap = len(qt & (tt | dt)) / max(1, len(qt))
    title_overlap = len(qt & tt) / max(1, len(qt))
    local_norm = float(c.get("local_score", 0.0)) / max(1e-6, max_local)
    rank_norm = 1.0 - squash_rank(c.get("rank", 0)) / 5.0
    len_norm = min(1.0, len(dt) / 120.0)
    # entity bridge: a capitalised span from the query that also appears in the
    # candidate (or, for the second hop, the title is a capitalised noun the
    # query refers back to).  Keep a weak bonus so it cannot swamp retrieval.
    ent = len(qcap & tcap) / max(1, len(qcap))
    ent = 0.5 * ent + 0.5 * (1.0 if (tcap and (tcap & qcap or tt & qt)) else 0.0)
    title_in_query = 1.0 if tt and tt <= qt else 0.0
    agreement = float(c.get("agreement", 0.0)) if use_agreement else 0.0
    # novelty against other candidates
    sims = [_jacc(dt, set(tokens(o.get("text", "")))) for o in all_cands if o is not c]
    nov = 1.0 - (max(sims) if sims else 0.0)
    has_num = 1.0 if re.search(r"\d", c.get("text", "")) else 0.0
    # absolute z-score of the local retrieval score (the only signal that keeps
    # gold near rank 0 when the shortlist is mostly gold-absent)
    z = float(c.get("local_z", 0.0))
    return [overlap, title_overlap, local_norm, rank_norm, len_norm, ent,
            title_in_query, agreement, nov, has_num, float(node_rel), z]

class Verifier:
    def __init__(self, l2=1e-3, lr=0.15, epochs=500):
        self.l2, self.lr, self.epochs = l2, lr, epochs
        self.w = None
        self.mu = None
        self.sd = None

    def fit(self, X, y):
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        self.mu = X.mean(axis=0)
        self.sd = X.std(axis=0) + 1e-8
        Z = (X - self.mu) / self.sd
        n, d = Z.shape
        pos = max(1.0, y.sum()); neg = max(1.0, n - y.sum())
        w = np.zeros(d)
        # class-balanced weights
        sw = np.where(y > 0.5, n / (2 * pos), n / (2 * neg))
        for _ in range(self.epochs):
            p = 1.0 / (1.0 + np.exp(-np.clip(Z @ w, -30, 30)))
            g = Z.T @ (sw * (p - y)) / n + self.l2 * w
            w -= self.lr * g
        self.w = w
        return self

    def predict(self, X):
        X = np.asarray(X, dtype=np.float64)
        Z = (X - self.mu) / self.sd
        return 1.0 / (1.0 + np.exp(-np.clip(Z @ self.w, -30, 30)))

def train_verifier(episodes, n_nodes=5, use_agreement=True):
    X, y = [], []
    for ep in episodes:
        cands = ep["candidates"]
        max_local = max([c["local_score"] for c in cands] + [1e-6])
        # agreement by title
        counts = {}
        for c in cands:
            counts[c["title"]] = counts.get(c["title"], 0) + 1
        for c in cands:
            c["agreement"] = counts[c["title"]] / n_nodes
            X.append(candidate_features(c, ep["question"], cands, n_nodes, max_local, c.get("node_rel", 0.5), use_agreement))
            y.append(1.0 if c.get("is_gold") else 0.0)
    return Verifier().fit(X, y)

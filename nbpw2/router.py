# -*- coding: utf-8 -*-
"""Reusable UCB / context-UCB routers."""
import math

class UCB:
    def __init__(self, arms, c=0.35):
        self.c = c
        self.stats = {a: [0.0, 0.0] for a in arms}
        self.t = 0

    def choose(self, allowed=None):
        arms = allowed or list(self.stats)
        self.t += 1
        best, bs = None, -1e9
        for a in arms:
            r, n = self.stats[a]
            q = r / (n + 1) + self.c * math.sqrt(math.log(self.t + 1) / (n + 1))
            if q > bs:
                best, bs = a, q
        return best

    def update(self, arm, reward):
        self.stats[arm][0] += reward
        self.stats[arm][1] += 1

class ContextUCB:
    def __init__(self, contexts, arms, c=0.35):
        self.c = c
        self.stats = {(x, a): [0.0, 0.0] for x in contexts for a in arms}
        self.t = 0

    def choose(self, ctx, allowed=None):
        arms = allowed or sorted({a for (_, a) in self.stats})
        self.t += 1
        best, bs = None, -1e9
        for a in arms:
            r, n = self.stats.get((ctx, a), [0.0, 0.0])
            q = r / (n + 1) + self.c * math.sqrt(math.log(self.t + 1) / (n + 1))
            if q > bs:
                best, bs = a, q
        return best

    def update(self, ctx, arm, reward):
        k = (ctx, arm)
        self.stats.setdefault(k, [0.0, 0.0])
        self.stats[k][0] += reward
        self.stats[k][1] += 1

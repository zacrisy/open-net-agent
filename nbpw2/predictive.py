# -*- coding: utf-8 -*-
"""Predictive-coding gate: send full candidates only when surprise is high."""
import math

class Predictor:
    def __init__(self, theta=0.1, warmup=10):
        self.theta = theta
        self.warmup = warmup
        self.mean = {}
        self.queries = 0

    def gate(self, node_id, max_score):
        """Return (send_full, residual, prediction)."""
        mu = self.mean.get(node_id, max_score)
        residual = max_score - mu
        open_full = (self.queries < self.warmup) or (abs(residual) >= self.theta)
        # online update
        self.mean[node_id] = 0.9 * mu + 0.1 * max_score
        return open_full, residual, mu

    def tick(self):
        self.queries += 1

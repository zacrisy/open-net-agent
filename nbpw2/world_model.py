# -*- coding: utf-8 -*-
"""Tiny linear world model for the synthetic research task (E5)."""
import numpy as np

class LinearWorldModel:
    def __init__(self, l2=1e-3):
        self.l2 = l2
        self.W = None
        self.mu = None
        self.sd = None

    def fit(self, X, Y):
        X = np.asarray(X, float); Y = np.asarray(Y, float)
        self.mu = X.mean(0); self.sd = X.std(0) + 1e-8
        Z = (X - self.mu) / self.sd
        Z = np.hstack([Z, np.ones((len(Z), 1))])
        A = Z.T @ Z + self.l2 * np.eye(Z.shape[1])
        self.W = np.linalg.solve(A, Z.T @ Y)
        return self

    def predict(self, x):
        z = (np.asarray(x, float) - self.mu) / self.sd
        z = np.r_[z, 1.0]
        return z @ self.W

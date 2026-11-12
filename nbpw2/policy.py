# -*- coding: utf-8 -*-
"""Policies for the synthetic research task."""
import numpy as np

ACTIONS = ["search", "verify", "synthesize"]

def state_features(facts, verified, step, budget, last_action):
    v = [facts / 5.0, float(verified), step / max(1, budget), (budget - step) / max(1, budget)]
    v += [1.0 if last_action == a else 0.0 for a in ACTIONS]
    return v

def action_features(state, action):
    return state + [1.0 if action == a else 0.0 for a in ACTIONS]

class WorldModelPolicy:
    def __init__(self, model):
        self.model = model

    def choose(self, facts, verified, step, budget, last_action):
        if facts >= 4 and not verified:
            return "verify"
        if facts >= 4 and verified:
            return "synthesize"
        st = state_features(facts, verified, step, budget, last_action)
        best, best_s = "synthesize", -1e9
        for a in ACTIONS:
            if a == "verify" and (verified or facts == 0):
                continue
            if a == "synthesize" and step < budget and facts < 4:
                # allow synth only near the end or when enough facts
                if (budget - step) > 1:
                    continue
            pred = self.model.predict(action_features(st, a))
            df, dv, succ = pred
            score = 0.5 * df + 0.4 * dv + 1.2 * succ - 0.05
            if score > best_s:
                best, best_s = a, score
        return best

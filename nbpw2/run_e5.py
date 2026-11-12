# -*- coding: utf-8 -*-
"""E5: world-model policy vs fixed/random/UCB on a synthetic research task."""
import json, random, statistics, os
import numpy as np
from .world_model import LinearWorldModel
from .policy import WorldModelPolicy, state_features, action_features, ACTIONS

def env_step(state, action, rng):
    facts, verified, step, budget = state
    cost = 1
    if action == "search":
        if facts < 5 and rng.random() < 0.72:
            facts += 1
    elif action == "verify":
        if facts > 0:
            verified = 1
    elif action == "synthesize":
        success = 1 if (facts >= 4 and verified) else 0
        return (facts, verified, step + 1, budget), {"success": success, "df": 0, "dv": 0, "cost": cost, "done": True}
    done = step + 1 >= budget
    success = 1 if (done and facts >= 4 and verified) else 0
    return (facts, verified, step + 1, budget), {"success": success, "df": int(action == "search" and facts > state[0]),
                                                 "dv": int(action == "verify" and verified > state[1]), "cost": cost, "done": done}

def run(policy, seed, n=500, budget=10):
    rng = random.Random(seed)
    succ, facts, steps, ver = [], [], [], []
    for _ in range(n):
        state = (0, 0, 0, budget); last = None
        stats = {"facts": 0, "verified": 0, "steps": 0}
        while state[2] < budget:
            a = policy(state[0], state[1], state[2], budget, last)
            state, r = env_step(state, a, rng)
            last = a; stats["steps"] += 1
            if r["done"]:
                break
        ok = 1 if (state[0] >= 4 and state[1] == 1) else 0
        succ.append(ok); facts.append(state[0]); steps.append(stats["steps"]); ver.append(state[1])
    return {"success": statistics.mean(succ), "facts": statistics.mean(facts),
            "steps": statistics.mean(steps), "verify_rate": statistics.mean(ver)}

def train_model(seed=0, episodes=3000, budget=10):
    rng = random.Random(seed); X, Y = [], []
    for _ in range(episodes):
        state = (0, 0, 0, budget); last = None
        while state[2] < budget:
            a = rng.choice(ACTIONS)
            st = state_features(state[0], state[1], state[2], budget, last)
            ns, r = env_step(state, a, rng)
            X.append(action_features(st, a)); Y.append([r["df"], r["dv"], r["success"]])
            state = ns; last = a
            if r["done"]:
                break
    return LinearWorldModel().fit(X, Y)

def fixed(facts, verified, step, budget, last=None):
    if facts < 5 and step < budget - 2: return "search"
    if not verified and facts > 0: return "verify"
    return "synthesize"

def random_policy(facts, verified, step, budget, last=None):
    return random.choice(ACTIONS)

def ucb_factory():
    stats = {a: [0.0, 0.0] for a in ACTIONS}
    def choose(state, *args):
        facts, verified, step, budget = state
        t = sum(v[1] for v in stats.values()) + 1
        best, bs = "search", -1e9
        for a in ACTIONS:
            if a == "verify" and (verified or facts == 0): continue
            r, n = stats[a]
            q = r / (n + 1) + 0.5 * np.sqrt(np.log(t + 1) / (n + 1))
            if q > bs: best, bs = a, q
        return best
    def update(a, reward):
        stats[a][0] += reward; stats[a][1] += 1
    return choose, update

def main():
    model = train_model()
    wm = WorldModelPolicy(model)
    out = {}
    for name in ["random", "fixed", "world_model"]:
        runs = []
        for seed in range(5):
            if name == "random": p = random_policy
            elif name == "fixed": p = fixed
            else: p = wm.choose
            runs.append(run(p, seed))
        out[name] = {k: round(statistics.mean(r[k] for r in runs), 4) for k in runs[0]}
        out[name]["success_sd"] = round(statistics.pstdev(r["success"] for r in runs), 4)
    # UCB with reward update wrapper
    runs = []
    for seed in range(5):
        choose, update = ucb_factory()
        rng = random.Random(seed)
        def ucb_policy(state, *args):
            return choose(state)
        # run inline to update
        succ, facts, steps, ver = [], [], [], []
        for _ in range(500):
            state = (0, 0, 0, 10); last = None
            while state[2] < 10:
                a = choose(state)
                ns, r = env_step(state, a, rng)
                update(a, r["df"] + r["dv"] + 2 * r["success"] - 0.05)
                state = ns; last = a
                if r["done"]: break
            succ.append(1 if (state[0] >= 4 and state[1] == 1) else 0)
            facts.append(state[0]); steps.append(state[2]); ver.append(state[1])
        runs.append({"success": statistics.mean(succ), "facts": statistics.mean(facts),
                     "steps": statistics.mean(steps), "verify_rate": statistics.mean(ver)})
    out["ucb"] = {k: round(statistics.mean(r[k] for r in runs), 4) for k in runs[0]}
    out["ucb"]["success_sd"] = round(statistics.pstdev(r["success"] for r in runs), 4)
    print(out)
    with open(os.path.join(os.path.dirname(__file__), "results", "e5_world_model.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

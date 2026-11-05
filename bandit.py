# -*- coding: utf-8 -*-
"""Context-free UCB bandit for agent action selection."""
import math
import brain

ACTIONS = ("search", "graph", "verify", "synthesize", "abstain")


def init():
    c = brain._conn()
    with c:
        c.execute("CREATE TABLE IF NOT EXISTS agent_policy (action TEXT PRIMARY KEY, pulls INTEGER DEFAULT 0, reward REAL DEFAULT 0)")
        for a in ACTIONS:
            c.execute("INSERT OR IGNORE INTO agent_policy VALUES (?,0,0)", (a,))
    c.close()


def stats():
    c = brain._conn()
    rows = c.execute("SELECT action,pulls,reward FROM agent_policy").fetchall()
    c.close()
    return {r[0]: {"pulls": r[1], "mean": round(r[2] / r[1], 3) if r[1] else 0.0} for r in rows}


def choose(allowed):
    init()
    c = brain._conn()
    rows = c.execute("SELECT action,pulls,reward FROM agent_policy").fetchall()
    c.close()
    d = {r[0]: (r[1], r[2]) for r in rows}
    total = sum(v[0] for v in d.values()) or 1
    for a in allowed:
        if d.get(a, (0, 0))[0] == 0:
            return a
    best, bv = allowed[0], -1e9
    for a in allowed:
        pulls, reward = d.get(a, (0, 0))
        mean = reward / pulls if pulls else 0
        v = mean + math.sqrt(2 * math.log(total + 1) / max(1, pulls))
        if v > bv: best, bv = a, v
    return best


def update(action, reward):
    init()
    c = brain._conn()
    with c:
        c.execute("INSERT INTO agent_policy(action,pulls,reward) VALUES (?,1,?) ON CONFLICT(action) DO UPDATE SET pulls=pulls+1, reward=reward+excluded.reward", (action, float(reward)))
    c.close()

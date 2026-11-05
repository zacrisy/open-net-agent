# -*- coding: utf-8 -*-
"""Small learned world model: kNN over historical agent steps."""
import json
import brain


def _target(obs):
    if "sources" in obs: return float(obs["sources"])
    if "cards" in obs: return float(obs["cards"])
    if "confidence" in obs: return float(obs["confidence"])
    return 1.0


def predict(action, state):
    c = brain._conn()
    rows = c.execute("SELECT step,observation FROM agent_steps WHERE action=? ORDER BY id DESC LIMIT 120", (action,)).fetchall()
    c.close()
    if not rows:
        return {"expected": {"search": 4.0, "graph": 4.0, "verify": .6, "synthesize": 1.0}.get(action, 1.0), "n": 0, "model": "prior"}
    step = int(state.get("step", 0))
    vals = []
    for s, raw in rows:
        try: obs = json.loads(raw)
        except Exception: continue
        dist = abs(int(s) - step)
        vals.append((dist, _target(obs)))
    vals.sort(key=lambda x: x[0])
    k = vals[:5]
    return {"expected": round(sum(v for _, v in k) / len(k), 3), "n": len(rows), "model": "knn"}

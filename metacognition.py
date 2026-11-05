# -*- coding: utf-8 -*-
"""Calibration + abstention policy from completed agent tasks."""
import json
import brain


def calibration():
    c = brain._conn()
    rows = c.execute("SELECT confidence,score FROM agent_tasks WHERE status='complete' AND score>0").fetchall()
    c.close()
    if not rows:
        return {"n": 0, "ece": None, "threshold": 0.45, "abstain_rate": 0.0}
    buckets = {}
    for conf, score in rows:
        b = min(4, max(0, int(float(conf) * 5)))
        buckets.setdefault(b, []).append((float(conf), float(score)))
    ece = sum(abs(sum(x[0] for x in v) / len(v) - sum(x[1] for x in v) / len(v)) * len(v) for v in buckets.values()) / len(rows)
    best_t, best_util = 0.45, -1
    for t in [i / 20 for i in range(4, 17)]:
        kept = [(c, s) for c, s in rows if c >= t]
        util = (sum(s for _, s in kept) / len(kept) if kept else 0) - 0.15 * (1 - len(kept) / len(rows))
        if util > best_util: best_t, best_util = t, util
    best_t = max(.45, best_t)
    kept = [1 for c, _ in rows if c >= best_t]
    return {"n": len(rows), "ece": round(ece, 3), "threshold": round(best_t, 2), "abstain_rate": round(1 - len(kept) / len(rows), 3)}


def should_abstain(conf):
    return float(conf) < calibration().get("threshold", 0.45)

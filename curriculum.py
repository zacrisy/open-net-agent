# -*- coding: utf-8 -*-
"""Generate low-retention practice tasks from cards."""
import json, re
import brain
try:
    from continual import mask_question
except Exception:
    from nbpw.continual import mask_question


def next_tasks(n=5):
    c = brain._conn()
    cards = c.execute("SELECT id,topic,claim,evidence FROM cards ORDER BY ts DESC LIMIT 200").fetchall()
    quiz = c.execute("SELECT card_id, AVG(correct) FROM quiz GROUP BY card_id").fetchall()
    c.close()
    weak = {r[0]: r[1] for r in quiz if (r[1] or 0) < .8}
    out = []
    for card_id, topic, claim, evidence in cards:
        mq = mask_question(claim)
        if not mq: continue
        pri = (1.0 - weak[card_id]) if card_id in weak else 0.5
        out.append({"card_id": card_id, "topic": topic, "question": mq[0], "answer": mq[1], "priority": round(pri, 2)})
    out.sort(key=lambda x: x["priority"], reverse=True)
    return out[:n]

#!/usr/bin/env python3
"""Small task-level comparison: fixed research pipeline vs agent loop."""
import json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import agent_core, agent_loop

TASKS = json.load(open(os.path.join(os.path.dirname(__file__), "agent_tasks.json"), encoding="utf-8"))


def fixed(task):
    t0 = time.time()
    res = agent_core.research(task["question"])
    check = agent_core.citation_report(res.get("answer", ""), res.get("sources", []))
    score = round(0.3 * (1 if check.get("ok") else 0) + 0.3 * min(1, len(res.get("sources", [])) / 4) + 0.4 * float(res.get("confidence", 0)), 3)
    return {"score": score, "sources": len(res.get("sources", [])), "citation_ok": bool(check.get("ok")), "elapsed": round(time.time() - t0, 1)}


def run():
    rows = []
    for task in TASKS:
        a = agent_loop.run_task(task["question"], task["budget"])
        s = agent_loop.task_status(a["task_id"])
        steps = len(s.get("steps", []))
        fixed_r = fixed(task)
        rows.append({"id": task["id"], "question": task["question"],
                     "agent": {"score": s.get("score"), "confidence": s.get("confidence"), "steps": steps},
                     "fixed": fixed_r})
        print(task["id"], "agent", s.get("score"), "fixed", fixed_r["score"], flush=True)
    out = {"n": len(rows), "agent_mean": round(sum(r["agent"]["score"] or 0 for r in rows) / len(rows), 3),
           "fixed_mean": round(sum(r["fixed"]["score"] for r in rows) / len(rows), 3), "rows": rows}
    json.dump(out, open(os.path.join(os.path.dirname(__file__), "agent_results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ("n", "agent_mean", "fixed_mean")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    run()

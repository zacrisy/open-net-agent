#!/usr/bin/env python3
"""Run NBCL learning/evolution on a GitHub Actions runner.

Persists to docs/cloud_brain.db and exports docs/cloud_brain.json for Pages.
"""
import json
import os
import sqlite3
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
os.environ["BRAIN_DB"] = os.path.join(ROOT, "docs", "cloud_brain.db")
os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)

import brain  # noqa: E402

TOPICS = [
    "retrieval augmented generation evaluation",
    "graph neural network advances",
    "LLM agent reliability evaluation",
    "continual learning catastrophic forgetting",
    "semaglutide cardiovascular outcomes",
    "knowledge graph construction",
    "Python asyncio event loop",
    "federated learning privacy",
]
TARGET_CYCLES = int(os.environ.get("CLOUD_CYCLES", "5"))


def wait(cid, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        s = brain.status()
        if s["learning"].get("cycle_id") == cid and s["learning"].get("stage") in ("complete", "error"):
            return s["learning"].get("stage")
        time.sleep(2)
    return "timeout"


def run_one(topic):
    r = brain.start(topic)
    cid = r.get("cycle_id")
    if not cid:
        return r
    stage = wait(cid)
    print(f"cycle {cid} {topic} -> {stage}", flush=True)
    return r


def main():
    for i in range(TARGET_CYCLES):
        fb = brain.next_feedback_topic()
        topic = fb["topic"] if fb else TOPICS[(brain.status()["metrics"]["cycles"] + i) % len(TOPICS)]
        run_one(topic)
        if i % 2 == 1:
            try:
                brain.consolidate()
                print("consolidated", flush=True)
            except Exception as e:
                print("consolidate failed", e, flush=True)

    c = sqlite3.connect(os.environ["BRAIN_DB"])
    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    c.close()

    data = brain.status()
    data["graph"] = brain.graph()
    data["feedback"] = brain.feedback_list(20)
    data["improvements"] = brain.improvement_list(20)
    data["cloud"] = {
        "updated": time.time(),
        "runner": os.environ.get("GITHUB_RUN_ID", "local"),
        "repo": os.environ.get("GITHUB_REPOSITORY", "zacrisy/open-net-agent"),
    }
    out = os.path.join(ROOT, "docs", "cloud_brain.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("wrote", out, "cards", data["metrics"]["cards"], "cycles", data["metrics"]["cycles"], flush=True)


if __name__ == "__main__":
    main()

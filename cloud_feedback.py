#!/usr/bin/env python3
"""Sync a GitHub issue labeled feedback into the cloud brain DB."""
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.abspath(__file__))
os.environ["BRAIN_DB"] = os.path.join(ROOT, "docs", "cloud_brain.db")
import brain  # noqa: E402


def main():
    event = json.load(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8"))
    issue = event.get("issue", {})
    labels = [x.get("name") for x in issue.get("labels", [])]
    if "feedback" not in labels or "processed" in labels:
        print("skip: not a feedback issue")
        return
    body = (issue.get("body") or "").strip()
    title = issue.get("title") or ""
    text = (title + "\n" + body)[:1200]
    r = brain.submit_feedback(text)
    c = sqlite3.connect(os.environ["BRAIN_DB"])
    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    c.close()
    for suffix in ("-wal", "-shm"):
        try:
            os.remove(os.environ["BRAIN_DB"] + suffix)
        except FileNotFoundError:
            pass
    print("feedback", r)


if __name__ == "__main__":
    main()

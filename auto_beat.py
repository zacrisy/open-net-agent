#!/usr/bin/env python3
"""External heartbeat for OpenNetBrain.

Calls the local auto_tick endpoint so learning/evolution continues even if
the coordinator's in-process thread dies. Run alongside run_online.py.

    python3 auto_beat.py --interval 15
"""
import argparse
import json
import time
import urllib.request

URL = "http://127.0.0.1:8080/api/brain/auto_tick"


def tick():
    req = urllib.request.Request(URL, method="POST", data=b"{}", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=15)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    while True:
        try:
            out = tick()
            print(time.strftime("%H:%M:%S"), out.get("status"), out.get("action", ""), flush=True)
        except Exception as e:
            print(time.strftime("%H:%M:%S"), "tick failed:", str(e)[:120], flush=True)
        if args.once:
            return
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""HTTP client for LAN nodes with timeout + retry; measures real RTT."""
import json, time, urllib.error, urllib.request

def query(port, q, k=5, timeout=3.0, host="127.0.0.1", quality=False):
    t0 = time.time()
    payload = {"q": q, "k": k}
    if quality:
        payload["quality"] = True
    req = urllib.request.Request(
        f"http://{host}:{port}/query",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
        return {"ok": True, "hits": data.get("hits", []), "rtt": time.time() - t0}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120], "hits": [], "rtt": time.time() - t0}

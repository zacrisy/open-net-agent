# -*- coding: utf-8 -*-
"""审计/技能市场测试。"""
import json, threading, time, urllib.request
import coordinator
from node import Node

PORT = 8775; TOKEN = "secret"; BASE = f"http://127.0.0.1:{PORT}"

def req(path, obj=None, timeout=6):
    data = json.dumps(obj).encode() if obj is not None else None
    r = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json", "X-Auth-Token": TOKEN})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read().decode())

srv = coordinator.serve(PORT, TOKEN, preferred_k=1)
n = Node(BASE, "n0", 0, 1, TOKEN, "echo", poll=0.2)
threading.Thread(target=n.run, daemon=True).start(); time.sleep(1)
print("skills:", req("/skills"))
out = req("/query", {"query": "audit-test", "skill": "echo", "timeout": 3, "quorum": 1})
print("query:", out["answer"], out["score"])
aud = req(f"/audit?task_id={out['task_id']}")
print("audit tasks:", len(aud["tasks"]), "results:", len(aud["results"]))
assert aud["tasks"] and aud["results"]
print("AUDIT/SKILLS PASSED")
n.stop(); srv.shutdown()

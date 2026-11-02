# -*- coding: utf-8 -*-
"""信誉优先路由测试：高信誉节点先拿任务。"""
import json, subprocess, sys, time, urllib.request

PORT = 8772
TOKEN = "secret"
BASE = f"http://127.0.0.1:{PORT}"

def req(path, obj=None, timeout=6):
    data = json.dumps(obj).encode() if obj is not None else None
    r = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json", "X-Auth-Token": TOKEN})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read().decode())

def main():
    coord = subprocess.Popen([sys.executable, "coordinator.py", str(PORT), TOKEN])
    time.sleep(0.8)
    a = subprocess.Popen([sys.executable, "node.py", "--coordinator", BASE, "--node-id", "A", "--token", TOKEN, "--skill", "echo", "--ok", "20", "--fail", "0"])
    b = subprocess.Popen([sys.executable, "node.py", "--coordinator", BASE, "--node-id", "B", "--token", TOKEN, "--skill", "echo", "--ok", "0", "--fail", "5"])
    time.sleep(1.5)
    print("status:", req("/status"))
    out = req("/query", {"query": "hello", "skill": "echo", "timeout": 3, "quorum": 1, "preferred_k": 1})
    print("preferred:", out["preferred"], "results:", [(r["node_id"], r["score"]) for r in out["results"]])
    assert out["preferred"] == ["A"], out["preferred"]
    assert out["results"] and out["results"][0]["node_id"] == "A"
    print("REPUTATION ROUTING PASSED")
    for p in [a, b, coord]:
        try: p.terminate()
        except Exception: pass

if __name__ == "__main__":
    main()

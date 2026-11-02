# -*- coding: utf-8 -*-
"""20 节点负载测试：echo 技能，50 次查询，测 p50/p95。"""
import json, threading, time, urllib.request
import coordinator
from node import Node

PORT = 8774; TOKEN = "secret"; N = 20; Q = 50

def main():
    srv = coordinator.serve(PORT, TOKEN, preferred_k=N)
    nodes = [Node(f"http://127.0.0.1:{PORT}", f"n{i}", i, 1, TOKEN, "echo", poll=0.2, init_ok=1) for i in range(N)]
    ts = [threading.Thread(target=n.run, daemon=True) for n in nodes]
    for t in ts: t.start()
    time.sleep(1.5)
    lat, ok = [], 0
    for i in range(Q):
        body = json.dumps({"query": f"q{i}", "skill": "echo", "timeout": 5, "quorum": N, "preferred_k": N}).encode()
        r = urllib.request.Request(f"http://127.0.0.1:{PORT}/query", data=body, headers={"Content-Type": "application/json", "X-Auth-Token": TOKEN})
        t0 = time.time(); out = json.loads(urllib.request.urlopen(r, timeout=8).read().decode()); lat.append(time.time() - t0)
        if len(out["results"]) >= N: ok += 1
    lat.sort()
    print("nodes", N, "queries", Q, "success", ok / Q)
    print("p50", round(lat[len(lat)//2], 3), "p95", round(lat[int(len(lat)*0.95)], 3), "avg", round(sum(lat)/len(lat), 3))
    print("metrics", json.loads(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/metrics", headers={"X-Auth-Token": TOKEN})).read()))
    for n in nodes: n.stop()
    srv.shutdown()

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""WAN 模拟：5 节点，30ms 延迟、5% 丢包，20 次查询。"""
import json, threading, time, urllib.request
import coordinator
from node import Node

PORT = 8776; TOKEN = "secret"; N = 5; Q = 20

def main():
    srv = coordinator.serve(PORT, TOKEN, preferred_k=N)
    nodes = [Node(f"http://127.0.0.1:{PORT}", f"w{i}", i, 1, TOKEN, "echo", poll=0.2,
                  init_ok=1, latency_ms=30, drop_rate=0.05) for i in range(N)]
    for n in nodes: threading.Thread(target=n.run, daemon=True).start()
    time.sleep(1.5)
    lat, ok = [], 0
    for i in range(Q):
        body = json.dumps({"query": f"w{i}", "skill": "echo", "timeout": 8, "quorum": N, "preferred_k": N}).encode()
        r = urllib.request.Request(f"http://127.0.0.1:{PORT}/query", data=body, headers={"Content-Type": "application/json", "X-Auth-Token": TOKEN})
        t0 = time.time(); out = json.loads(urllib.request.urlopen(r, timeout=10).read().decode()); lat.append(time.time() - t0)
        if len(out["results"]) >= N: ok += 1
    lat.sort()
    print("nodes", N, "latency 30ms drop 5%", "success", ok / Q, "p50", round(lat[len(lat)//2], 3), "p95", round(lat[int(len(lat)*0.95)], 3))
    for n in nodes: n.stop()
    srv.shutdown()

if __name__ == "__main__":
    main()

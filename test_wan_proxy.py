# -*- coding: utf-8 -*-
"""传输层 WAN 模拟：节点经 TCP 代理连协调者。"""
import json, threading, time, urllib.request
import coordinator
from node import Node
from netproxy import serve as proxy_serve

COORD_PORT = 8781; PROXY_PORT = 8782; TOKEN = "secret"; N = 5; Q = 20

def main():
    srv = coordinator.serve(COORD_PORT, TOKEN, preferred_k=N)
    threading.Thread(target=proxy_serve, args=(PROXY_PORT, ("127.0.0.1", COORD_PORT), 30, 0.05), daemon=True).start()
    base = f"http://127.0.0.1:{PROXY_PORT}"
    nodes = [Node(base, f"p{i}", i, 1, TOKEN, "echo", poll=0.2, init_ok=1) for i in range(N)]
    for n in nodes: threading.Thread(target=n.run, daemon=True).start()
    time.sleep(2)
    for QUORUM in [5, 4, 3]:
      lat, ok = [], 0
      for i in range(10):
        body = json.dumps({"query": f"p{i}", "skill": "echo", "timeout": 10, "quorum": QUORUM, "preferred_k": N}).encode()
        r = urllib.request.Request(f"http://127.0.0.1:{COORD_PORT}/query", data=body, headers={"Content-Type": "application/json", "X-Auth-Token": TOKEN})
        t0 = time.time(); out = json.loads(urllib.request.urlopen(r, timeout=12).read().decode()); lat.append(time.time() - t0)
        if len(out["results"]) >= QUORUM: ok += 1
      lat.sort()
      print("proxy WAN 30ms/5% quorum", QUORUM, "success", ok / 10, "p50", round(lat[len(lat)//2], 2), "p95", round(lat[int(len(lat)*0.95)], 2))
    for n in nodes: n.stop()
    srv.shutdown()

if __name__ == "__main__":
    main()

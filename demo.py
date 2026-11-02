# -*- coding: utf-8 -*-
"""本机演示：1 个协调者 + 3 个节点。"""
import threading, time, json, urllib.request
import coordinator
from node import Node

def query(port, q, timeout=6):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/query", data=json.dumps({"query": q, "timeout": timeout}).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout + 2).read().decode())

if __name__ == "__main__":
    srv = coordinator.serve(8765)
    nodes = [Node("http://127.0.0.1:8765", f"node-{i}", i, 3) for i in range(3)]
    ths = [threading.Thread(target=n.run, daemon=True) for n in nodes]
    for t in ths: t.start()
    time.sleep(1.2)
    print("status:", json.loads(urllib.request.urlopen("http://127.0.0.1:8765/status").read()))
    for q in ["如何让多台电脑组成一个智能体？", "节点加入会不会影响正常工作？"]:
        out = query(8765, q)
        print("\nQ:", q)
        print("A:", out["answer"])
        print("score:", round(out["score"], 3), "nodes:", out["nodes"])
        for r in out["results"]: print("  -", r["node_id"], round(r["score"], 3))
    for n in nodes: n.stop()
    srv.shutdown()

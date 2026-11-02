# -*- coding: utf-8 -*-
"""节点：注册、心跳、轮询任务、本地技能、上报。"""
import argparse, json, os, random, time
import urllib.request
from corpus import shard

def post(url, obj, timeout=5):
    req = urllib.request.Request(url, data=json.dumps(obj).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())

def get(url, timeout=5):
    return json.loads(urllib.request.urlopen(url, timeout=timeout).read().decode())

def score(query, doc):
    q = set(query); d = set(doc)
    return len(q & d) / (len(q) + 1e-9)

class Node:
    def __init__(self, coord, node_id, index, total, pause_file=None):
        self.coord = coord.rstrip("/"); self.node_id = node_id
        self.docs = shard(index, total); self.pause_file = pause_file
        self.running = True
    def run(self):
        try: os.nice(10)
        except Exception: pass
        post(self.coord + "/register", {"node_id": self.node_id, "skills": ["retrieval"], "capacity": {"docs": len(self.docs)}})
        last_hb = 0
        while self.running:
            if self.pause_file and os.path.exists(self.pause_file):
                time.sleep(2); continue
            now = time.time()
            if now - last_hb > 10:
                try: post(self.coord + "/heartbeat", {"node_id": self.node_id})
                except Exception: pass
                last_hb = now
            try:
                t = get(f"{self.coord}/task?node_id={self.node_id}")
                if t and t.get("task_id"):
                    q = t["query"]; best = max(self.docs, key=lambda d: score(q, d))
                    post(self.coord + "/result", {"task_id": t["task_id"], "node_id": self.node_id,
                                                  "answer": best, "score": score(q, best), "latency": 0.01})
            except Exception:
                pass
            time.sleep(0.6 + random.random() * 0.4)
    def stop(self): self.running = False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--coordinator", required=True)
    ap.add_argument("--node-id", default=None)
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--total", type=int, default=1)
    ap.add_argument("--pause-file", default=None)
    a = ap.parse_args()
    nid = a.node_id or f"node-{os.getpid()}"
    Node(a.coordinator, nid, a.index, a.total, a.pause_file).run()

# -*- coding: utf-8 -*-
"""节点 v2：token、技能、暂停、限任务。"""
import argparse, json, os, random, time
import urllib.request
from corpus import shard
from skills import SKILLS


def _req(url, obj=None, token="", timeout=5):
    data = json.dumps(obj).encode() if obj is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "X-Auth-Token": token})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())


class Node:
    def __init__(self, coord, node_id, index, total, token="", skill="retrieval", pause_file=None, poll=0.8, max_tasks=None, init_ok=0, init_fail=0):
        self.coord = coord.rstrip("/"); self.node_id = node_id; self.token = token
        self.skill = skill; self.docs = shard(index, total); self.pause_file = pause_file
        self.poll = poll; self.max_tasks = max_tasks; self.running = True; self.done = 0
        self.init_ok = init_ok; self.init_fail = init_fail

    def run(self):
        try: os.nice(10)
        except Exception: pass
        for _ in range(3):
            try:
                _req(self.coord + "/register", {"node_id": self.node_id, "skills": [self.skill],
                                                "ok": self.init_ok, "fail": self.init_fail,
                                                "capacity": {"docs": len(self.docs)}}, self.token)
                break
            except urllib.error.HTTPError as e:
                if e.code == 401: print("unauthorized: check --token", flush=True); return
                time.sleep(1)
            except Exception: time.sleep(1)
        last_hb = 0
        while self.running and (self.max_tasks is None or self.done < self.max_tasks):
            if self.pause_file and os.path.exists(self.pause_file):
                time.sleep(1.5); continue
            now = time.time()
            if now - last_hb > 10:
                try: _req(self.coord + "/heartbeat", {"node_id": self.node_id}, self.token)
                except Exception: pass
                last_hb = now
            try:
                t = _req(f"{self.coord}/task?node_id={self.node_id}", token=self.token)
                if t and t.get("task_id"):
                    fn = SKILLS.get(t.get("skill", self.skill))
                    if fn:
                        out = fn(t["query"], {"docs": self.docs})
                        _req(self.coord + "/result", {"task_id": t["task_id"], "node_id": self.node_id,
                                                      "answer": out.get("answer"), "score": out.get("score", 0.0),
                                                      "evidence": out.get("evidence", []), "latency": 0.01}, self.token)
                        self.done += 1
            except Exception:
                pass
            time.sleep(self.poll + random.random() * 0.3)

    def stop(self): self.running = False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--coordinator", required=True)
    ap.add_argument("--node-id", default=None)
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--total", type=int, default=1)
    ap.add_argument("--token", default="")
    ap.add_argument("--skill", default="retrieval")
    ap.add_argument("--pause-file", default=None)
    ap.add_argument("--poll", type=float, default=0.8)
    ap.add_argument("--max-tasks", type=int, default=None)
    ap.add_argument("--ok", type=int, default=0)
    ap.add_argument("--fail", type=int, default=0)
    a = ap.parse_args()
    Node(a.coordinator, a.node_id or f"node-{os.getpid()}", a.index, a.total,
         a.token, a.skill, a.pause_file, a.poll, a.max_tasks, a.ok, a.fail).run()

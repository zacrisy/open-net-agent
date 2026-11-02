# -*- coding: utf-8 -*-
"""协调者 v2：token 鉴权、技能路由、quorum、信誉统计。"""
import json, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

TOKEN = ""
NODES, TASKS = {}, {}
LOCK = threading.Lock()
MIN_INTERVAL = 0.15


def aggregate(results):
    if not results: return {"answer": None, "score": 0.0, "results": []}
    best = max(results, key=lambda r: r.get("score", 0.0))
    return {"answer": best.get("answer"), "score": best.get("score", 0.0), "results": results}


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0)); return json.loads(self.rfile.read(n) or b"{}")

    def _auth(self):
        return (not TOKEN) or (self.headers.get("X-Auth-Token") == TOKEN)

    def do_POST(self):
        if not self._auth(): return self._send(401, {"error": "unauthorized"})
        p = urlparse(self.path).path
        try: d = self._body()
        except Exception: return self._send(400, {"error": "bad json"})
        if p == "/register":
            with LOCK:
                NODES[d["node_id"]] = {"skills": d.get("skills", []), "last_seen": time.time(),
                                       "ok": 0, "fail": 0, "score_sum": 0.0, "done": 0}
            return self._send(200, {"ok": True, "nodes": len(NODES)})
        if p == "/heartbeat":
            with LOCK:
                if d.get("node_id") in NODES: NODES[d["node_id"]]["last_seen"] = time.time()
            return self._send(200, {"ok": True})
        if p == "/result":
            with LOCK:
                t = TASKS.get(d.get("task_id"))
                if t:
                    t["results"].append({"node_id": d.get("node_id"), "answer": d.get("answer"),
                                         "score": float(d.get("score", 0)), "latency": d.get("latency")})
                    n = NODES.get(d.get("node_id"))
                    if n: n["ok"] += 1; n["done"] += 1; n["score_sum"] += float(d.get("score", 0))
                    t["event"].set()
            return self._send(200, {"ok": True})
        if p == "/query":
            tid = uuid.uuid4().hex[:12]
            t = {"id": tid, "query": d.get("query", ""), "skill": d.get("skill", "retrieval"),
                 "results": [], "assigned": set(), "event": threading.Event()}
            with LOCK: TASKS[tid] = t
            deadline = time.time() + float(d.get("timeout", 8))
            while time.time() < deadline:
                with LOCK:
                    capable = [n for n, v in NODES.items() if t["skill"] in v["skills"]]
                    need = min(int(d.get("quorum", 3)), max(1, len(capable)))
                    if len(t["results"]) >= need: break
                t["event"].clear(); t["event"].wait(timeout=0.2)
            with LOCK:
                for nid in t["assigned"]:
                    if not any(r["node_id"] == nid for r in t["results"]):
                        NODES[nid]["fail"] = NODES[nid].get("fail", 0) + 1
                out = aggregate(list(t["results"]))
            out.update({"task_id": tid, "skill": t["skill"], "nodes": len(NODES)})
            return self._send(200, out)
        return self._send(404, {"error": "not found"})

    def do_GET(self):
        if not self._auth(): return self._send(401, {"error": "unauthorized"})
        u = urlparse(self.path); p = u.path
        if p == "/task":
            nid = parse_qs(u.query).get("node_id", [""])[0]
            with LOCK:
                n = NODES.get(nid)
                if not n: return self._send(403, {"error": "unregistered"})
                if time.time() - n.get("last_assign", 0) < MIN_INTERVAL: return self._send(204, {})
                for t in TASKS.values():
                    if nid not in t["assigned"] and t["skill"] in n["skills"] and len(t["results"]) < 8:
                        t["assigned"].add(nid); n["last_assign"] = time.time()
                        return self._send(200, {"task_id": t["id"], "query": t["query"], "skill": t["skill"]})
            return self._send(204, {})
        if p == "/status":
            with LOCK:
                return self._send(200, {"nodes": {k: {"skills": v["skills"], "ok": v["ok"], "fail": v["fail"]} for k, v in NODES.items()}, "tasks": len(TASKS)})
        if p == "/metrics":
            with LOCK:
                done = sum(v["done"] for v in NODES.values()); ok = sum(v["ok"] for v in NODES.values())
                fail = sum(v["fail"] for v in NODES.values()); score = sum(v["score_sum"] for v in NODES.values())
                return self._send(200, {"nodes": len(NODES), "tasks": len(TASKS), "results": done,
                                        "ok": ok, "fail": fail, "avg_score": score / max(1, ok)})
        return self._send(404, {"error": "not found"})

    def log_message(self, *a): pass


def serve(port=8765, token=""):
    global TOKEN
    TOKEN = token
    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    token = sys.argv[2] if len(sys.argv) > 2 else ""
    srv = serve(port, token)
    print(f"coordinator on :{port} auth={'on' if token else 'off'}", flush=True)
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: srv.shutdown()

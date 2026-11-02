# -*- coding: utf-8 -*-
"""协调者：节点注册、任务分发、结果聚合。"""
import json, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

NODES = {}
TASKS = {}
LOCK = threading.Lock()


def aggregate(results):
    if not results:
        return {"answer": None, "score": 0.0, "results": []}
    best = max(results, key=lambda r: r.get("score", 0.0))
    return {"answer": best.get("answer"), "score": best.get("score", 0.0), "results": results}


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0)); return json.loads(self.rfile.read(n) or b"{}")

    def do_POST(self):
        p = urlparse(self.path).path
        try: data = self._body()
        except Exception: return self._send(400, {"error": "bad json"})
        if p == "/register":
            with LOCK:
                NODES[data["node_id"]] = {"skills": data.get("skills", []), "last_seen": time.time()}
            return self._send(200, {"ok": True, "nodes": len(NODES)})
        if p == "/heartbeat":
            with LOCK:
                if data.get("node_id") in NODES: NODES[data["node_id"]]["last_seen"] = time.time()
            return self._send(200, {"ok": True})
        if p == "/result":
            tid = data.get("task_id")
            with LOCK:
                t = TASKS.get(tid)
                if t:
                    t["results"].append({"node_id": data.get("node_id"), "answer": data.get("answer"),
                                         "score": float(data.get("score", 0)), "latency": data.get("latency")})
                    t["event"].set()
            return self._send(200, {"ok": True})
        if p == "/query":
            tid = uuid.uuid4().hex[:12]
            t = {"id": tid, "query": data.get("query", ""), "results": [], "assigned": set(), "event": threading.Event()}
            with LOCK: TASKS[tid] = t
            deadline = time.time() + float(data.get("timeout", 8))
            while time.time() < deadline:
                with LOCK:
                    need = min(len(NODES), 3)
                    if len(t["results"]) >= need: break
                t["event"].clear(); t["event"].wait(timeout=0.2)
            with LOCK: out = aggregate(list(t["results"]))
            out["task_id"] = tid; out["nodes"] = len(NODES)
            return self._send(200, out)
        return self._send(404, {"error": "not found"})

    def do_GET(self):
        u = urlparse(self.path); p = u.path
        if p == "/task":
            nid = parse_qs(u.query).get("node_id", [""])[0]
            with LOCK:
                for t in TASKS.values():
                    if nid not in t["assigned"] and len(t["results"]) < 8:
                        t["assigned"].add(nid)
                        return self._send(200, {"task_id": t["id"], "query": t["query"]})
            return self._send(204, {})
        if p == "/status":
            with LOCK:
                return self._send(200, {"nodes": list(NODES.keys()), "tasks": len(TASKS)})
        return self._send(404, {"error": "not found"})

    def log_message(self, *a): pass


def serve(port=8765):
    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    srv = serve(port)
    print(f"coordinator on :{port}", flush=True)
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        srv.shutdown()

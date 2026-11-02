# -*- coding: utf-8 -*-
"""协调者 v3：token 轮换、可选 TLS、技能路由、信誉优先、quorum。"""
import json, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

TOKENS = set()
NODES, TASKS = {}, {}
LOCK = threading.Lock()
PREFERRED_K = 2
GRACE = 0.4


def aggregate(results):
    if not results: return {"answer": None, "score": 0.0, "results": []}
    best = max(results, key=lambda r: r.get("score", 0.0))
    return {"answer": best.get("answer"), "score": best.get("score", 0.0), "results": results}


def rep(n):
    total = n["ok"] + n["fail"]
    acc = (n["ok"] + 1) / (total + 2)
    avg = n["score_sum"] / max(1, n["ok"])
    return 0.7 * acc + 0.3 * max(0.0, min(1.0, avg))


def preferred(skill, k):
    capable = [nid for nid, n in NODES.items() if skill in n["skills"]]
    capable.sort(key=lambda nid: rep(NODES[nid]), reverse=True)
    return set(capable[:k])


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0)); return json.loads(self.rfile.read(n) or b"{}")

    def _auth(self):
        return (not TOKENS) or (self.headers.get("X-Auth-Token") in TOKENS)

    def do_POST(self):
        if not self._auth(): return self._send(401, {"error": "unauthorized"})
        p = urlparse(self.path).path
        try: d = self._body()
        except Exception: return self._send(400, {"error": "bad json"})
        if p == "/register":
            with LOCK:
                NODES[d["node_id"]] = {"skills": d.get("skills", []), "last_seen": time.time(),
                                       "ok": int(d.get("ok", 0)), "fail": int(d.get("fail", 0)),
                                       "score_sum": float(d.get("score_sum", 0.0)), "done": 0, "last_assign": 0}
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
                 "results": [], "assigned": set(), "event": threading.Event(), "created": time.time(),
                 "quorum": int(d.get("quorum", 3))}
            with LOCK:
                t["preferred"] = preferred(t["skill"], int(d.get("preferred_k", PREFERRED_K)))
                TASKS[tid] = t
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
                out["nodes"] = len(NODES); out["preferred"] = sorted(t["preferred"])
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
                if time.time() - n.get("last_assign", 0) < 0.12: return self._send(204, {})
                for t in TASKS.values():
                    cap = max(8, t.get("quorum", 8))
                    if nid in t["assigned"] or t["skill"] not in n["skills"] or len(t["results"]) >= cap: continue
                    # 信誉优先：preferred 节点先拿；宽限后所有人可拿
                    if nid not in t["preferred"] and time.time() - t["created"] < GRACE: continue
                    t["assigned"].add(nid); n["last_assign"] = time.time()
                    return self._send(200, {"task_id": t["id"], "query": t["query"], "skill": t["skill"]})
            return self._send(204, {})
        if p == "/status":
            with LOCK:
                return self._send(200, {"nodes": {k: {"skills": v["skills"], "ok": v["ok"], "fail": v["fail"],
                                                       "rep": round(rep(v), 3)} for k, v in NODES.items()}, "tasks": len(TASKS)})
        if p == "/metrics":
            with LOCK:
                ok = sum(v["ok"] for v in NODES.values()); fail = sum(v["fail"] for v in NODES.values())
                score = sum(v["score_sum"] for v in NODES.values())
                return self._send(200, {"nodes": len(NODES), "tasks": len(TASKS), "ok": ok, "fail": fail,
                                        "avg_score": score / max(1, ok)})
        return self._send(404, {"error": "not found"})

    def log_message(self, *a): pass


def serve(port=8765, tokens="", certfile=None, keyfile=None, preferred_k=2):
    global TOKENS, PREFERRED_K
    TOKENS = set(t.strip() for t in tokens.split(",") if t.strip())
    PREFERRED_K = preferred_k
    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    if certfile and keyfile:
        import ssl
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile, keyfile)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    tokens = sys.argv[2] if len(sys.argv) > 2 else ""
    cert = sys.argv[3] if len(sys.argv) > 3 else None
    key = sys.argv[4] if len(sys.argv) > 4 else None
    srv = serve(port, tokens, cert, key)
    print(f"coordinator on :{port} auth={'on' if tokens else 'off'} tls={'on' if cert else 'off'}", flush=True)
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: srv.shutdown()

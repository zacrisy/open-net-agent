# -*- coding: utf-8 -*-
"""LAN service for nodes: POST /query {q, k} -> hits, with netproxy latency/loss.

This is the transport layer the plan asks for: real RTT, real packet loss, real
process boundaries. No shared memory between the client and the node.
"""
import argparse, json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from nbpw2.dense import recall  # noqa: E402

DOCS = []
VERIFIER = [None]
MISSES = [0]


def _load_verifier():
    """Load a verifier trained on the training split (offline, once)."""
    path = os.environ.get("LAN_VERIFIER")
    if not path:
        return None
    try:
        import pickle
        cache = os.path.join(ROOT, "nbpw2", "results", "lan", "verifier.pkl")
        if os.path.exists(cache):
            return pickle.load(open(cache, "rb"))
        from nbpw2.data import load as dmqa_load, build_pool
        from nbpw2.network import train_rows
        from nbpw2.verifier import train_verifier
        rows = dmqa_load(os.environ.get("LAN_TRAIN", os.path.join(ROOT, "nbpw2", "data", "dmqa_dev.jsonl")))
        pool = build_pool(rows)
        train = [r for r in rows if r["split"] == "train"]
        v = train_verifier(train_rows(train, pool, distractors=100, top_k=5), use_agreement=False)
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        pickle.dump(v, open(cache, "wb"))
        return v
    except Exception:
        return None

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/raw"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            q = (qs.get("q") or [""])[0]
            hits = recall(q, DOCS, 20)
            return self._send({"n": len(hits), "top": [(h["title"], round(h.get("local_score", 0), 4)) for h in hits[:5]],
                               "verifier": VERIFIER[0] is not None})
        if self.path.startswith("/stats"):
            return self._send({"misses": MISSES[0], "verifier": VERIFIER[0] is not None})
        if self.path.startswith("/health"):
            return self._send({"ok": True, "docs": len(DOCS), "verifier": VERIFIER[0] is not None})
        self._send({"error": "not found"}, 404)

    def do_POST(self):
        if not self.path.startswith("/query"):
            return self._send({"error": "not found"}, 404)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send({"error": "bad json"}, 400)
        q = str(req.get("q", ""))[:500]
        k = int(req.get("k", 5) or 5)
        quality = bool(req.get("quality", False)) or os.environ.get("LAN_VERIFIER") == "1"
        # fetch deeper, then rank with the project verifier (network-side readout)
        depth = int(req.get("depth", max(k * 4, 20)) or max(k * 4, 20))
        hits = recall(q, DOCS, depth)
        # de-duplicate identical paragraph texts, keep the best local score
        seen, uniq = set(), []
        for h in sorted(hits, key=lambda x: x.get("local_score", 0.0), reverse=True):
            key = (h.get("title"), (h.get("text") or "").strip()[:200])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(h)
        hits = uniq
        try:
            from nbpw2.network import score_candidates
            if VERIFIER[0] is None:
                VERIFIER[0] = _load_verifier()
            if VERIFIER[0] not in (None, "fail") and (quality or os.environ.get("LAN_VERIFIER") == "1"):
                ep = {"candidates": hits, "question": q, "gold": set(), "id": "lan"}
                cands = score_candidates(ep, VERIFIER[0], 1, use_agreement=False)
                # verifier already sees the absolute z-score of the local score;
                # keep a small retrieval prior so a single confident paragraph
                # cannot promote a gold-absent title over a strong hit.
                for h in cands:
                    h["final"] = 0.8 * float(h.get("verifier", 0.0)) + 0.2 * float(h.get("local_z", 0.0))
                best = {}
                for h in cands:
                    t = h["title"]
                    if t not in best or h["final"] > best[t]["final"]:
                        best[t] = h
                hits = sorted(best.values(), key=lambda h: h["final"], reverse=True)
                if os.environ.get("LAN_DEBUG"):
                    sys.stderr.write("DBG readout n=%d top=%s\n" % (len(hits), [(h["title"][:18], round(h["final"], 3)) for h in hits[:3]]))
                    sys.stderr.flush()
        except Exception:
            MISSES[0] += 1
        out = []
        for i, h in enumerate(hits[:k]):
            v = h.get("final")
            if v is None:
                v = h.get("verifier")
            if v is None:
                v = h.get("local_score", 0.0)
            out.append({"title": h["title"], "text": h["text"][:1200],
                        "local_score": h.get("local_score", 0.0),
                        "verifier": float(v) if v is not None else 0.0,
                        "rank": h.get("rank", i)})
        self._send({"hits": out, "docs": len(DOCS)})

    def log_message(self, *a):
        pass

def serve(port, docs_path, limit=200):
    global DOCS
    with open(docs_path, encoding="utf-8") as f:
        data = json.load(f)
    # docs_path may be a list of paragraphs (a shard)
    DOCS = data[:limit] if limit else data
    if os.environ.get("LAN_VERIFIER"):
        VERIFIER[0] = _load_verifier() or "fail"
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"node on :{port} docs {len(DOCS)}", flush=True)
    srv.serve_forever()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9001)
    ap.add_argument("--docs", required=True)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    serve(a.port, a.docs, a.limit)

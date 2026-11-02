# -*- coding: utf-8 -*-
"""异步协调者：aiohttp + WebSocket 推送 + Thompson 采样。"""
import asyncio, json, random, time, uuid
from collections import defaultdict
from aiohttp import web, WSMsgType
import db, db_async
from skills import SKILLS, SKILL_META
from starter_corpus import DOCS as STARTER_DOCS

JOIN_HTML = """<!doctype html><html lang=zh><meta charset=utf-8>
<title>加入 OpenNetAgent</title>
<style>body{background:#0e1116;color:#e6edf3;font:14px/1.7 -apple-system,sans-serif;max-width:760px;margin:6vh auto;padding:0 20px}
code,pre{background:#171c24;border:1px solid #2a3240;border-radius:8px}code{padding:2px 6px}pre{padding:14px;overflow:auto}
a{color:#4c8dff}h1{font-size:22px}</style>
<h1>加入 OpenNetAgent</h1>
<p>把你的电脑变成一个节点：出站连接、nice 19、可暂停/卸载，不影响正常工作。</p>
<pre>curl -fsSL __BASE__/install.sh | bash -s -- \
  --coordinator __BASE__ --token &lt;YOUR_TOKEN&gt;</pre>
<p>需要 token：向协调者申请，或使用演示 token（仅限试用）。</p>
<p>暂停：<code>bash install.sh --pause</code>；恢复：<code>--resume</code>；卸载：<code>--uninstall</code>。</p>
<p>查看状态：<a href="/">仪表盘</a></p>"""

TOKENS = set()
NODES, TASKS = {}, {}
PREFERRED_K = 3
NODE_TTL = 20
HITS = defaultdict(list)
PUBLIC_HITS = defaultdict(list)
db.init()


def auth(req):
    return (not TOKENS) or (req.headers.get("X-Auth-Token") in TOKENS) or (req.query.get("token") in TOKENS)


def theta(n):
    return random.betavariate(n["ok"] + 1, n["fail"] + 1)


def aggregate(results):
    if not results: return {"answer": None, "score": 0.0, "results": []}
    b = max(results, key=lambda r: r.get("score", 0))
    return {"answer": b.get("answer"), "score": b.get("score", 0), "results": results}


async def register(req):
    if not auth(req): return web.json_response({"error": "unauthorized"}, status=401)
    d = await req.json()
    NODES[d["node_id"]] = {"skills": d.get("skills", []), "ok": int(d.get("ok", 0)), "fail": int(d.get("fail", 0)),
                           "score_sum": 0.0, "pulls": 0, "ws": None}
    db_async.log_node(d["node_id"], d.get("skills", []))
    return web.json_response({"ok": True, "nodes": len(NODES)})


async def _run_query(d):
    skill = d.get("skill", "retrieval"); tid = uuid.uuid4().hex[:12]
    capable = [nid for nid, n in NODES.items() if skill in n["skills"] and n["ws"] and not n["ws"].closed]
    capable.sort(key=lambda nid: theta(NODES[nid]), reverse=True)
    preferred = capable[:int(d.get("preferred_k", PREFERRED_K))]
    t = {"id": tid, "query": d.get("query", ""), "skill": skill, "results": [], "assigned": set(preferred)}
    TASKS[tid] = t
    db_async.log_task(tid, t["query"], skill)
    for nid in preferred:
        n = NODES[nid]; n["pulls"] += 1
        try:
            await n["ws"].send_json({"type": "task", "task_id": tid, "query": t["query"], "skill": skill})
        except Exception:
            pass
    deadline = time.time() + float(d.get("timeout", 8)); need = min(int(d.get("quorum", 3)), max(1, len(preferred)))
    while time.time() < deadline and len(t["results"]) < need:
        await asyncio.sleep(0.02)
    out = aggregate(t["results"]); out.update({"task_id": tid, "preferred": sorted(preferred), "nodes": len(NODES)})
    return out


async def query(req):
    if not auth(req): return web.json_response({"error": "unauthorized"}, status=401)
    return web.json_response(await _run_query(await req.json()))


def public_limited(req):
    ip = req.headers.get("X-Forwarded-For", req.remote or "?").split(",")[0].strip()
    now = time.time(); PUBLIC_HITS[ip] = [t for t in PUBLIC_HITS[ip] if now - t < 60]
    if len(PUBLIC_HITS[ip]) >= 20: return True
    PUBLIC_HITS[ip].append(now); return False


async def public_query(req):
    if public_limited(req): return web.json_response({"error": "rate limit"}, status=429)
    d = await req.json()
    if d.get("skill", "retrieval") not in ("retrieval", "echo"):
        return web.json_response({"error": "public demo only supports retrieval/echo"}, status=403)
    if len(d.get("query", "")) > 200:
        return web.json_response({"error": "query too long"}, status=400)
    return web.json_response(await _run_query(d))


async def public_status(req):
    return web.json_response(_status_payload())


async def ws_handler(req):
    if not auth(req): return web.Response(status=401)
    nid = req.query.get("node_id", ""); ws = web.WebSocketResponse(); await ws.prepare(req)
    skills = [x for x in req.query.get("skills", "").split(",") if x]
    n = NODES.setdefault(nid, {"skills": [], "ok": 0, "fail": 0, "score_sum": 0.0, "pulls": 0, "ws": None})
    if skills: n["skills"] = skills
    n["ws"] = ws
    async for msg in ws:
        if msg.type != WSMsgType.TEXT: continue
        d = json.loads(msg.data)
        if d.get("type") == "result":
            t = TASKS.get(d.get("task_id"))
            if t:
                t["results"].append({"node_id": nid, "answer": d.get("answer"), "score": float(d.get("score", 0))})
                n["ok"] += 1; n["score_sum"] += float(d.get("score", 0))
                db_async.log_result(d.get("task_id"), nid, d.get("answer"), d.get("score", 0))
    n["ws"] = None; n["last_seen"] = time.time()
    return ws


def _status_payload():
    now = time.time()
    nodes = {k: {"skills": v["skills"], "ok": v["ok"], "fail": v["fail"], "theta": round(theta(v), 3),
                 "pulls": v["pulls"], "online": v.get("ws") is not None}
             for k, v in NODES.items() if active(v)}
    ok = sum(n["ok"] for n in nodes.values()); score = sum(max(0.0, n["score_sum"]) for n in NODES.values())
    return {"nodes": nodes, "tasks": len(TASKS), "ok": ok, "avg_conf": score / max(1, ok)}


def active(n):
    return n.get("ws") is not None or time.time() - n.get("last_seen", 0) < NODE_TTL


async def status(req):
    if not auth(req): return web.json_response({"error": "unauthorized"}, status=401)
    return web.json_response(_status_payload())


async def skills(req):
    return web.json_response({"skills": sorted(SKILLS.keys()), "meta": SKILL_META})


async def audit(req):
    db_async.flush(); return web.json_response(db.audit(req.query.get("task_id")))


async def metrics(req):
    ok = sum(n["ok"] for n in NODES.values()); fail = sum(n["fail"] for n in NODES.values())
    score = sum(max(0.0, n["score_sum"]) for n in NODES.values())
    return web.json_response({"nodes": sum(1 for n in NODES.values() if active(n)), "tasks": len(TASKS),
                              "ok": ok, "fail": fail, "avg_conf": score / max(1, ok)})


async def starter(req):
    return web.json_response(STARTER_DOCS)


async def health(req):
    return web.json_response({"ok": True, "nodes": sum(1 for n in NODES.values() if active(n)), "tasks": len(TASKS)})


async def index(req):
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
    return web.Response(text=open(p, encoding="utf-8").read(), content_type="text/html")


async def join_page(req):
    return web.Response(text=JOIN_HTML, content_type="text/html")


async def static_file(req):
    name = req.match_info["name"]
    allow = {"install.sh", "node.py", "corpus.py", "skills.py", "provision.py"}
    if name not in allow:
        return web.Response(status=404)
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    if not os.path.isfile(p):
        return web.Response(status=404)
    ct = "text/x-shellscript" if name.endswith(".sh") else "text/x-python"
    return web.Response(text=open(p, encoding="utf-8").read(), content_type=ct)


@web.middleware
async def rate_limit(request, handler):
    ip = request.headers.get("X-Forwarded-For", request.remote or "?").split(",")[0].strip()
    now = time.time(); HITS[ip] = [t for t in HITS[ip] if now - t < 60]
    if len(HITS[ip]) >= 120:
        return web.json_response({"error": "rate limit"}, status=429)
    HITS[ip].append(now)
    return await handler(request)


def app():
    a = web.Application(middlewares=[rate_limit])
    a.router.add_post("/register", register)
    a.router.add_post("/query", query)
    a.router.add_post("/public/query", public_query)
    a.router.add_get("/public/status", public_status)
    a.router.add_get("/ws", ws_handler)
    a.router.add_get("/status", status)
    a.router.add_get("/skills", skills)
    a.router.add_get("/audit", audit)
    a.router.add_get("/metrics", metrics)
    a.router.add_get("/health", health)
    a.router.add_get("/starter_corpus.json", starter)
    a.router.add_get("/", index)
    a.router.add_get("/join", join_page)
    a.router.add_get("/{name:install\.sh|node\.py|corpus\.py|skills\.py|provision\.py}", static_file)
    return a


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8790
    TOKENS.update(t for t in (sys.argv[2].split(",") if len(sys.argv) > 2 else []) if t)
    web.run_app(app(), port=port, print=None)

# -*- coding: utf-8 -*-
"""异步协调者：aiohttp + WebSocket 推送 + Thompson 采样。"""
import asyncio, json, random, time, uuid
from collections import defaultdict
from aiohttp import web, WSMsgType
import db, db_async
from skills import SKILLS, SKILL_META

TOKENS = set()
NODES, TASKS = {}, {}
PREFERRED_K = 3
HITS = defaultdict(list)
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


async def query(req):
    if not auth(req): return web.json_response({"error": "unauthorized"}, status=401)
    d = await req.json(); skill = d.get("skill", "retrieval"); tid = uuid.uuid4().hex[:12]
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
    return web.json_response(out)


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
    n["ws"] = None
    return ws


async def status(req):
    if not auth(req): return web.json_response({"error": "unauthorized"}, status=401)
    return web.json_response({"nodes": {k: {"skills": v["skills"], "ok": v["ok"], "fail": v["fail"],
                                            "theta": round(theta(v), 3), "pulls": v["pulls"]} for k, v in NODES.items()}, "tasks": len(TASKS)})


async def skills(req):
    return web.json_response({"skills": sorted(SKILLS.keys()), "meta": SKILL_META})


async def audit(req):
    db_async.flush(); return web.json_response(db.audit(req.query.get("task_id")))


async def metrics(req):
    ok = sum(n["ok"] for n in NODES.values()); fail = sum(n["fail"] for n in NODES.values())
    score = sum(max(0.0, n["score_sum"]) for n in NODES.values())
    return web.json_response({"nodes": len(NODES), "tasks": len(TASKS), "ok": ok, "fail": fail,
                              "avg_conf": score / max(1, ok)})


async def health(req):
    return web.json_response({"ok": True, "nodes": len(NODES), "tasks": len(TASKS)})


async def index(req):
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
    return web.Response(text=open(p, encoding="utf-8").read(), content_type="text/html")


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
    a.router.add_get("/ws", ws_handler)
    a.router.add_get("/status", status)
    a.router.add_get("/skills", skills)
    a.router.add_get("/audit", audit)
    a.router.add_get("/metrics", metrics)
    a.router.add_get("/health", health)
    a.router.add_get("/", index)
    return a


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8790
    TOKENS.update(t for t in (sys.argv[2].split(",") if len(sys.argv) > 2 else []) if t)
    web.run_app(app(), port=port, print=None)

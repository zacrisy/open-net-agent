# -*- coding: utf-8 -*-
"""异步协调者：aiohttp + WebSocket 推送 + Thompson 采样。"""
import asyncio, json, random, re, time, uuid
from collections import defaultdict
from aiohttp import web, WSMsgType
import db, db_async
import agent_core
import brain
import graph_retrieval
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
ASK_HITS = defaultdict(list)
ASK_JOBS = {}
LEARN_HITS = defaultdict(list)
FEEDBACK_HITS = defaultdict(list)
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


def ask_limited(req):
    ip = req.headers.get("X-Forwarded-For", req.remote or "?").split(",")[0].strip()
    now = time.time(); ASK_HITS[ip] = [t for t in ASK_HITS[ip] if now - t < 60]
    if len(ASK_HITS[ip]) >= 12: return True
    ASK_HITS[ip].append(now); return False


def _knowledge_pack():
    return STARTER_DOCS + db.top_experience_docs(30)


def _lexical_nli(claim, evidence):
    cw = set(re.findall(r"[a-zA-Z]{3,}", (claim or "").lower()))
    ew = set(re.findall(r"[a-zA-Z]{3,}", (evidence or "").lower()))
    if not cw or not ew:
        return "UNCERTAIN", 0.25, "no lexical overlap"
    overlap = len(cw & ew) / max(1, len(cw))
    neg = {"not", "no", "never", "without", "cannot", "isn't", "doesn't", "不", "无", "未", "没有", "不能"}
    cn = any(x in (claim or "").lower() for x in neg)
    en = any(x in (evidence or "").lower() for x in neg)
    if overlap >= 0.22:
        if cn != en:
            return "REFUTES", 0.68, f"overlap={overlap:.2f}, negation differs"
        return "SUPPORTS", 0.66, f"overlap={overlap:.2f}, no negation mismatch"
    return "UNCERTAIN", 0.35, f"overlap={overlap:.2f}"


def _self_intro():
    s = brain.status(); m = s.get("metrics", {}); a = s.get("auto", {})
    answer = (f"我是 OpenNetBrain，一个持续学习的网络大脑。\n\n"
              f"当前状态：{m.get('cards',0)} 张知识卡、{m.get('sources',0)} 个真实来源、{m.get('cycles',0)} 个学习/进化周期；"
              f"自动循环每 {a.get('interval',90)} 秒在 LEARN / EVOLVE 之间切换。\n\n"
              f"我能做：Research（多源研究 + 引用）、Docs（文档问答）、Compute（安全计算）、Verify（NLI 核查）、"
              f"Summarize（摘要）、Translate（翻译）、Extract（事实抽取）。\n\n"
              f"我的回答优先来自可追溯来源；没有来源时会说明，不会编造。学习发生在知识卡、信念图和课程层，不是改写权重。")
    return {"answer": answer,
            "sources": [{"title": "OpenNetBrain internal state", "snippet": f"cards={m.get('cards',0)}, sources={m.get('sources',0)}, cycles={m.get('cycles',0)}", "source": "brain", "url": "", "year": ""}],
            "trace": [{"step": "self", "detail": "state + capabilities"}, {"step": "cite", "detail": "internal"}],
            "confidence": 0.99, "engine": "self-model", "elapsed": 0.0}


async def _ask_core(d):
    mode = d.get("mode", "research")
    query = str(d.get("query", ""))[:500].strip()
    doc = str(d.get("doc", ""))[:8000]
    claim = str(d.get("claim", ""))[:400].strip()
    evidence = str(d.get("evidence", ""))[:1200].strip()
    SELF = ("介绍", "你是谁", "你能做什么", "你会什么", "介绍一下", "who are you", "what can you do", "about you")
    if mode == "research" and any(k in (query or "").lower() for k in SELF):
        res = _self_intro()
    elif mode == "verify":
        if not claim or not evidence:
            return {"error": "verify 需要 claim 和 evidence"}
        label, score, detail = _lexical_nli(claim, evidence)
        res = {"answer": label, "sources": [{"title": "Lexical/NLI check", "snippet": claim + " || " + evidence, "source": "NLI", "url": "", "year": ""}],
               "trace": [{"step": "verify", "detail": label}, {"step": "method", "detail": detail}],
               "confidence": round(min(1.0, abs(score)), 2), "engine": "lexical-nli", "elapsed": 0.0}
    elif mode == "compute":
        res = await asyncio.to_thread(agent_core.compute, query)
    elif mode == "docs":
        res = await asyncio.to_thread(agent_core.doc_answer, query, doc)
    elif mode == "summarize":
        res = await asyncio.to_thread(agent_core.summarize, doc or query)
    elif mode == "translate":
        res = await asyncio.to_thread(agent_core.translate_text, doc or query, str(d.get("target", "zh")))
    elif mode == "extract":
        res = await asyncio.to_thread(agent_core.extract_facts, doc or query)
    else:
        memory = db.search_experience(query, 3)
        res = await asyncio.to_thread(agent_core.research, query, mode, memory)
        try:
            g = await asyncio.to_thread(graph_retrieval.retrieve, query, 4)
            if g.get("cards"):
                seen = {str(s.get("url") or s.get("title") or "") for s in (res.get("sources") or [])}
                mem_sources = []
                for c in g["cards"]:
                    src = c.get("source") or {}
                    key = str(src.get("url") or src.get("title") or c.get("claim", ""))
                    if key in seen:
                        continue
                    seen.add(key)
                    mem_sources.append({"title": (c.get("claim") or "")[:140], "snippet": (c.get("evidence") or "")[:400],
                                        "url": src.get("url", ""), "source": c.get("source_type", "memory"), "year": src.get("year", "")})
                if mem_sources:
                    res["sources"] = mem_sources + (res.get("sources") or [])
                    extra = "\n\n关联知识卡（图谱扩散）：\n" + "\n".join(
                        f"- {(c.get('claim') or '')[:220]} [M{i+1}]" for i, c in enumerate(g["cards"]))
                    res["answer"] = (res.get("answer") or "") + extra
                res["trace"] = (res.get("trace") or []) + [{"step": "graph", "detail": f"PPR {len(g['cards'])} cards / {g.get('edges',0)} edges"}]
                res["graph"] = {"engine": g.get("engine"), "edges": g.get("edges", 0),
                                "seeds": g.get("seeds", []),
                                "cards": [{"id": c.get("id"), "claim": (c.get("claim") or "")[:220], "score": c.get("score", 0)} for c in g["cards"]]}
                res["engine"] = (res.get("engine") or "") + "+graph"
        except Exception as e:
            res.setdefault("trace", []).append({"step": "graph", "detail": "skipped: " + str(e)[:80]})
        try:
            check = agent_core.citation_report(res.get("answer", ""), res.get("sources", []))
            res["citation_check"] = check
            res.setdefault("trace", []).append({"step": "cite_check", "detail": f"{check['refs']} refs / {check['unsupported']} unsupported"})
        except Exception:
            pass
    res["id"] = uuid.uuid4().hex[:12]
    res["mode"] = mode
    res["query"] = query
    db_async.log_experience(res["id"], mode, query, res.get("answer", ""), res.get("sources", []),
                            res.get("confidence", 0), res.get("elapsed", 0))
    return res


async def ask(req):
    if not auth(req): return web.json_response({"error": "unauthorized"}, status=401)
    return web.json_response(await _ask_core(await req.json()))


async def _run_ask_job(jid, d):
    try:
        res = await _ask_core(d)
        ASK_JOBS[jid] = {"status": "done", "result": res, "ts": time.time()}
    except Exception as e:
        ASK_JOBS[jid] = {"status": "error", "error": str(e)[:300], "ts": time.time()}


async def public_ask_start(req):
    if ask_limited(req): return web.json_response({"error": "rate limit"}, status=429)
    try: d = await req.json()
    except Exception: d = {}
    jid = uuid.uuid4().hex[:12]
    now = time.time()
    for k, v in list(ASK_JOBS.items()):
        if now - v.get("ts", now) > 900: ASK_JOBS.pop(k, None)
    ASK_JOBS[jid] = {"status": "running", "ts": now}
    asyncio.create_task(_run_ask_job(jid, d))
    return web.json_response({"job_id": jid, "status": "running"})


async def public_ask_result(req):
    jid = req.query.get("job_id", "")
    job = ASK_JOBS.get(jid)
    if not job: return web.json_response({"error": "job not found"}, status=404)
    return web.json_response(job)


async def public_ask(req):
    if ask_limited(req): return web.json_response({"error": "rate limit"}, status=429)
    return web.json_response(await _ask_core(await req.json()))


async def feedback(req):
    d = await req.json(); eid = str(d.get("id", "")); vote = d.get("vote")
    if vote not in ("up", "down") or not eid:
        return web.json_response({"error": "bad vote"}, status=400)
    db_async.vote_experience(eid, vote)
    return web.json_response({"ok": True, "id": eid, "vote": vote})


async def evolution_stats(req):
    return web.json_response(db.evolution_stats())


async def knowledge_pack(req):
    return web.json_response(_knowledge_pack())


def learn_limited(req):
    ip = req.headers.get("X-Forwarded-For", req.remote or "?").split(",")[0].strip()
    now = time.time(); LEARN_HITS[ip] = [t for t in LEARN_HITS[ip] if now - t < 60]
    if len(LEARN_HITS[ip]) >= 3: return True
    LEARN_HITS[ip].append(now); return False


async def brain_learn(req):
    if learn_limited(req):
        return web.json_response({"error": "learning rate limit (3/min)"}, status=429)
    try:
        d = await req.json()
    except Exception:
        d = {}
    return web.json_response(brain.start(d.get("topic")))


async def brain_auto_tick(req):
    if req.remote not in ("127.0.0.1", "::1"):
        return web.json_response({"error": "local only"}, status=403)
    return web.json_response(brain.auto_tick())


async def brain_evolve(req):
    if learn_limited(req):
        return web.json_response({"error": "evolution rate limit (3/min)"}, status=429)
    return web.json_response(await asyncio.to_thread(brain.consolidate))


def feedback_limited(req):
    ip = req.headers.get("X-Forwarded-For", req.remote or "?").split(",")[0].strip()
    now = time.time(); FEEDBACK_HITS[ip] = [t for t in FEEDBACK_HITS[ip] if now - t < 60]
    if len(FEEDBACK_HITS[ip]) >= 5: return True
    FEEDBACK_HITS[ip].append(now); return False


async def feedback_submit(req):
    if feedback_limited(req):
        return web.json_response({"error": "feedback rate limit (5/min)"}, status=429)
    try: d = await req.json()
    except Exception: d = {}
    res = brain.submit_feedback(d.get("text", ""), d.get("kind", ""), d.get("contact", ""))
    return web.json_response(res, status=400 if res.get("error") else 200)


async def feedback_list(req):
    return web.json_response(brain.feedback_list(int(req.query.get("limit", 20))))


async def improvement_list(req):
    return web.json_response(brain.improvement_list(int(req.query.get("limit", 20))))


async def brain_status(req):
    return web.json_response(brain.status())


async def brain_retrieve(req):
    q = req.query.get("q", "")
    k = int(req.query.get("k", 5))
    return web.json_response(await asyncio.to_thread(graph_retrieval.retrieve, q, k))


async def brain_cards(req):
    return web.json_response(brain.cards(int(req.query.get("limit", 120))))


async def brain_graph(req):
    return web.json_response(brain.graph())


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
    return web.json_response(_knowledge_pack())


async def health(req):
    return web.json_response({"ok": True, "nodes": sum(1 for n in NODES.values() if active(n)), "tasks": len(TASKS)})


async def index(req):
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brain.html")
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


@web.middleware
async def cors(request, handler):
    if request.method == "OPTIONS":
        return web.Response(status=204, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Auth-Token",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Max-Age": "600",
        })
    resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,X-Auth-Token"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return resp


def app():
    a = web.Application(middlewares=[cors, rate_limit])
    a.router.add_post("/register", register)
    a.router.add_post("/query", query)
    a.router.add_post("/public/query", public_query)
    a.router.add_post("/ask", ask)
    a.router.add_post("/public/ask", public_ask)
    a.router.add_post("/public/ask/start", public_ask_start)
    a.router.add_get("/public/ask/result", public_ask_result)
    a.router.add_post("/api/brain/learn", brain_learn)
    a.router.add_post("/api/brain/evolve", brain_evolve)
    a.router.add_post("/api/brain/auto_tick", brain_auto_tick)
    a.router.add_post("/api/brain/feedback", feedback_submit)
    a.router.add_get("/api/brain/feedback", feedback_list)
    a.router.add_get("/api/brain/improvements", improvement_list)
    a.router.add_get("/api/brain/status", brain_status)
    a.router.add_get("/api/brain/cards", brain_cards)
    a.router.add_get("/api/brain/graph", brain_graph)
    a.router.add_get("/api/brain/retrieve", brain_retrieve)
    a.router.add_post("/feedback", feedback)
    a.router.add_get("/evolution/stats", evolution_stats)
    a.router.add_get("/knowledge_pack.json", knowledge_pack)
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

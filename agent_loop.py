# -*- coding: utf-8 -*-
"""Level-2 research agent: goal -> predict -> act -> observe -> reflect.

This is deliberately small and inspectable:
- world model: historical average outcome per action (v0)
- policy: uncertainty/coverage-driven action selection
- skills: search / graph / verify / synthesize / abstain
- episodes: every step with prediction, observation, surprise
"""
import json, re, threading, time, uuid
import agent_core
import brain
import graph_retrieval
import world_model
import bandit

LOCK = threading.Lock()
CURRENT = {"task_id": None, "status": "idle"}
SKILLS = {
    "search": "query real sources",
    "graph": "retrieve associated knowledge cards via PPR",
    "verify": "lexical claim/evidence check",
    "synthesize": "compose a cited answer",
    "abstain": "refuse when evidence is insufficient",
}


def _conn():
    return brain._conn()


def init():
    c = _conn()
    with c:
        c.execute("CREATE TABLE IF NOT EXISTS agent_tasks (id TEXT PRIMARY KEY, question TEXT, budget INTEGER, status TEXT, answer TEXT, confidence REAL, score REAL, reflection TEXT, created REAL, finished REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS agent_steps (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, step INTEGER, action TEXT, input TEXT, prediction TEXT, observation TEXT, surprise REAL, created REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS agent_skills (name TEXT PRIMARY KEY, description TEXT, uses INTEGER DEFAULT 0)")
        for k, v in SKILLS.items():
            c.execute("INSERT OR IGNORE INTO agent_skills VALUES (?,?,0)", (k, v))
    c.close()


def _tokens(s):
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}|[\u4e00-\u9fff]{2,}", (s or "").lower()))


def _coverage(question, evidence):
    q = _tokens(question)
    if not q:
        return 0.0
    text = " ".join((s.get("title", "") + " " + s.get("snippet", "")) for s in evidence)
    return len(q & _tokens(text)) / max(1, len(q))


def _lexical_nli(claim, evidence):
    cw = set(re.findall(r"[a-zA-Z]{3,}", (claim or "").lower()))
    ew = set(re.findall(r"[a-zA-Z]{3,}", (evidence or "").lower()))
    if not cw or not ew:
        return "UNCERTAIN", 0.25
    overlap = len(cw & ew) / max(1, len(cw))
    neg = {"not", "no", "never", "without", "cannot"}
    if overlap >= .22:
        return ("REFUTES" if (any(x in claim.lower() for x in neg) != any(x in evidence.lower() for x in neg)) else "SUPPORTS"), .66
    return "UNCERTAIN", .35


def predict(action, state=None):
    return world_model.predict(action, state or {})


def _store_step(tid, step, action, inp, pred, obs, surprise):
    c = _conn()
    with c:
        c.execute("INSERT INTO agent_steps(task_id,step,action,input,prediction,observation,surprise,created) VALUES (?,?,?,?,?,?,?,?)",
                  (tid, step, action, json.dumps(inp, ensure_ascii=False), json.dumps(pred, ensure_ascii=False), json.dumps(obs, ensure_ascii=False), surprise, time.time()))
        c.execute("UPDATE agent_skills SET uses=uses+1 WHERE name=?", (action,))
    c.close()


def _choose(state):
    if state.get("done"):
        return "done"
    if state["step"] >= state["budget"]:
        return "synthesize" if state["evidence"] else "abstain"
    allowed = []
    if state["queries"]:
        allowed.append("search")
    if not state["graph_done"]:
        allowed.append("graph")
    if state["evidence"]:
        if not state["verified"]:
            allowed.append("verify")
        allowed.append("synthesize")
    if not allowed:
        return "abstain"
    # force search on a cold start; bandit controls the rest
    if not state["evidence"] and "search" in allowed:
        return "search"
    return bandit.choose(allowed)


def _observe(state, action):
    if action == "search":
        q = state["queries"].pop(0) if state["queries"] else state["question"]
        sources, used = agent_core.collect(q)
        old = {(s.get("url") or s.get("title")) for s in state["evidence"]}
        new = [s for s in sources if (s.get("url") or s.get("title")) not in old]
        state["evidence"].extend(new[:6])
        state["coverage"] = _coverage(state["question"], state["evidence"])
        return {"query": q[:100], "sources": len(new), "used": used, "coverage": round(state["coverage"], 3), "total": len(state["evidence"])}
    if action == "graph":
        g = graph_retrieval.retrieve(state["question"], 4)
        state["graph"] = g.get("cards", [])
        state["graph_done"] = True
        return {"cards": len(state["graph"]), "edges": g.get("edges", 0), "workspace": len(g.get("workspace", []))}
    if action == "verify":
        if not state["evidence"]:
            return {"error": "no evidence"}
        src = state["evidence"][0]
        claim = state["question"]
        ev = (src.get("snippet") or src.get("title") or "")[:500]
        label, conf = _lexical_nli(claim, ev)
        state["verified"].append({"label": label, "confidence": conf})
        return {"label": label, "confidence": conf}
    return {}


def _synthesize(state):
    sources = list(state["evidence"])
    for c in state.get("graph", []):
        src = c.get("source") or {}
        sources.append({"title": c.get("claim", "")[:140], "snippet": c.get("evidence", ""), "url": src.get("url", ""),
                        "source": c.get("source_type", "memory"), "year": src.get("year", "")})
    if not sources:
        return "证据不足：没有检索到足够来源，无法给出可靠回答。", 0.15, 0.0
    picks = agent_core.best_sentences(sources, state["question"], 4)
    if picks:
        answer = agent_core.compose(state["question"], sources, picks)
    else:
        rows = []
        for i, src in enumerate(sources[:3]):
            text = (src.get("snippet") or src.get("title") or "").strip()
            if text:
                rows.append(f"- {text[:260]} [{i+1}]")
        answer = "结论：\n" + "\n".join(rows) if rows else "证据不足：来源没有可用摘要。"
    if state.get("graph"):
        answer += "\n\n关联知识卡（图谱扩散）：\n" + "\n".join(f"- {(c.get('claim') or '')[:200]} [M{i+1}]" for i, c in enumerate(state["graph"]))
    check = agent_core.citation_report(answer, sources)
    coverage = state.get("coverage", 0.0)
    verified = len(state.get("verified", []))
    conf = min(.9, .35 + .12 * len(sources) + .08 * verified + .2 * coverage)
    return answer, round(conf, 2), (1.0 if check.get("ok") else 0.0)


def run_task(question, budget=6, tid=None):
    init()
    tid = tid or ("task-" + uuid.uuid4().hex[:10])
    question = (question or "").strip()[:500]
    budget = max(3, min(12, int(budget or 6)))
    with LOCK:
        CURRENT.update({"task_id": tid, "status": "running", "question": question})
    c = _conn()
    with c:
        if not c.execute("SELECT id FROM agent_tasks WHERE id=?", (tid,)).fetchone():
            c.execute("INSERT INTO agent_tasks VALUES (?,?,?,?,?,?,?,?,?,?)", (tid, question, budget, "running", "", 0, 0, "", time.time(), None))
    c.close()
    state = {"question": question, "budget": budget, "step": 0, "queries": [agent_core.expand(question), question + " review"], "evidence": [], "graph": [], "graph_done": False, "verified": [], "coverage": 0.0, "done": False}
    try:
        for i in range(budget):
            action = _choose(state)
            if action == "done":
                break
            pred = predict(action, state)
            before_cov = state.get("coverage", 0.0)
            before_n = len(state.get("evidence", [])) + len(state.get("graph", []))
            obs = _observe(state, action)
            actual = obs.get("sources", obs.get("cards", obs.get("confidence", 1.0)))
            surprise = round(abs(float(actual) - float(pred["expected"])) / max(1.0, float(pred["expected"])), 3)
            after_n = len(state.get("evidence", [])) + len(state.get("graph", []))
            gain = max(0.0, state.get("coverage", 0.0) - before_cov) + 0.08 * max(0, after_n - before_n)
            bandit.update(action, gain - 0.02 if action != "synthesize" else 0.0)
            _store_step(tid, i, action, {"question": question}, pred, obs, surprise)
            state["step"] = i + 1
            if action in ("synthesize", "abstain"):
                state["done"] = True
                break
        answer, conf, cite_ok = _synthesize(state)
        total_sources = len(state["evidence"]) + len(state.get("graph", []))
        graph_as_sources = [{"title": c.get("claim", ""), "snippet": c.get("evidence", "")} for c in state.get("graph", [])]
        total_coverage = _coverage(state["question"], state["evidence"] + graph_as_sources)
        score = round(0.3 * cite_ok + 0.3 * min(1, total_sources / 4) + 0.2 * total_coverage + 0.2 * (1 if state["verified"] else 0), 3)
        bandit.update("synthesize", score)
        reflection = f"steps={state['step']} sources={total_sources} coverage={total_coverage:.2f} verify={len(state['verified'])} cite_ok={bool(cite_ok)}"
        c = _conn()
        with c:
            c.execute("UPDATE agent_tasks SET status='complete',answer=?,confidence=?,score=?,reflection=?,finished=? WHERE id=?", (answer, conf, score, reflection, time.time(), tid))
        c.close()
        with LOCK:
            CURRENT.update({"task_id": tid, "status": "complete"})
        return {"task_id": tid, "status": "complete", "score": score, "confidence": conf}
    except Exception as e:
        c = _conn()
        with c:
            c.execute("UPDATE agent_tasks SET status='error',reflection=?,finished=? WHERE id=?", (str(e)[:300], time.time(), tid))
        c.close()
        with LOCK:
            CURRENT.update({"task_id": tid, "status": "error"})
        return {"task_id": tid, "status": "error", "error": str(e)[:300]}


def start(question, budget=6):
    init()
    with LOCK:
        if CURRENT.get("status") == "running":
            return {"error": "agent busy", "task_id": CURRENT.get("task_id")}
        tid = "task-" + uuid.uuid4().hex[:10]
        CURRENT.update({"task_id": tid, "status": "running", "question": (question or "")[:500]})
    c = _conn()
    with c:
        c.execute("INSERT INTO agent_tasks VALUES (?,?,?,?,?,?,?,?,?,?)", (tid, (question or "")[:500], max(3, min(12, int(budget or 6))), "running", "", 0, 0, "", time.time(), None))
    c.close()
    threading.Thread(target=run_task, args=(question, budget, tid), daemon=True).start()
    return {"task_id": tid, "status": "started"}


def task_status(tid):
    c = _conn()
    row = c.execute("SELECT id,question,budget,status,answer,confidence,score,reflection,created,finished FROM agent_tasks WHERE id=?", (tid,)).fetchone()
    steps = c.execute("SELECT step,action,input,prediction,observation,surprise,created FROM agent_steps WHERE task_id=? ORDER BY step", (tid,)).fetchall()
    skills = c.execute("SELECT name,uses FROM agent_skills ORDER BY uses DESC").fetchall()
    c.close()
    if not row:
        return None
    return {"id": row[0], "question": row[1], "budget": row[2], "status": row[3], "answer": row[4], "confidence": row[5], "score": row[6],
            "reflection": row[7], "created": row[8], "finished": row[9],
            "steps": [{"step": r[0], "action": r[1], "input": json.loads(r[2] or "{}"), "prediction": json.loads(r[3] or "{}"),
                       "observation": json.loads(r[4] or "{}"), "surprise": r[5]} for r in steps],
            "skills": [{"name": r[0], "uses": r[1]} for r in skills]}


def list_tasks(limit=10):
    c = _conn()
    rows = c.execute("SELECT id,question,status,score,confidence,created FROM agent_tasks ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return [{"id": r[0], "question": r[1], "status": r[2], "score": r[3], "confidence": r[4], "created": r[5]} for r in rows]


init()

# -*- coding: utf-8 -*-
"""SQLite 审计：节点、任务、结果。"""
import json, os, sqlite3, threading, time

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "netagent.db")
LOCK = threading.Lock()
conn = sqlite3.connect(DB, check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL")


def init():
    with LOCK:
        conn.execute("CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY, skills TEXT, ts REAL)")
        conn.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, query TEXT, skill TEXT, ts REAL)")
        conn.execute("CREATE TABLE IF NOT EXISTS results (task_id TEXT, node_id TEXT, answer TEXT, score REAL, ts REAL)")
        conn.execute("""CREATE TABLE IF NOT EXISTS experience (
            id TEXT PRIMARY KEY, ts REAL, mode TEXT, query TEXT, answer TEXT,
            sources TEXT, confidence REAL, elapsed REAL, vote TEXT, client TEXT)""")
        conn.commit()


def log_node(nid, skills):
    with LOCK:
        conn.execute("INSERT OR REPLACE INTO nodes VALUES (?,?,?)", (nid, json.dumps(skills), time.time())); conn.commit()


def log_task(tid, query, skill):
    with LOCK:
        conn.execute("INSERT OR REPLACE INTO tasks VALUES (?,?,?,?)", (tid, query, skill, time.time())); conn.commit()


def log_result(tid, nid, answer, score):
    with LOCK:
        conn.execute("INSERT INTO results VALUES (?,?,?,?,?)", (tid, nid, str(answer)[:500], float(score), time.time())); conn.commit()


def audit(tid=None):
    with LOCK:
        if tid:
            tasks = conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchall()
            res = conn.execute("SELECT * FROM results WHERE task_id=?", (tid,)).fetchall()
        else:
            tasks = conn.execute("SELECT * FROM tasks ORDER BY ts DESC LIMIT 20").fetchall()
            res = conn.execute("SELECT * FROM results ORDER BY ts DESC LIMIT 50").fetchall()
    return {"tasks": tasks, "results": res}


def log_experience(eid, mode, query, answer, sources, confidence, elapsed, client=""):
    with LOCK:
        conn.execute("INSERT OR REPLACE INTO experience VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (eid, time.time(), mode, str(query)[:500], str(answer)[:4000],
                      json.dumps(sources, ensure_ascii=False), float(confidence), float(elapsed), None, client))
        conn.commit()


def vote_experience(eid, vote):
    with LOCK:
        conn.execute("UPDATE experience SET vote=? WHERE id=?", (vote, eid)); conn.commit()


def evolution_stats():
    with LOCK:
        total = conn.execute("SELECT COUNT(*) FROM experience").fetchone()[0]
        up = conn.execute("SELECT COUNT(*) FROM experience WHERE vote='up'").fetchone()[0]
        down = conn.execute("SELECT COUNT(*) FROM experience WHERE vote='down'").fetchone()[0]
        avg = conn.execute("SELECT AVG(confidence) FROM experience").fetchone()[0] or 0
        modes = conn.execute("SELECT mode, COUNT(*) c FROM experience GROUP BY mode ORDER BY c DESC LIMIT 5").fetchall()
        recent = conn.execute("SELECT COUNT(*) FROM experience WHERE ts > ?", (time.time() - 86400,)).fetchone()[0]
    return {"total": total, "up": up, "down": down, "avg_conf": round(avg, 2), "recent_24h": recent,
            "modes": [{"mode": m, "count": c} for m, c in modes], "learned": up}


def top_experience_docs(limit=30):
    with LOCK:
        rows = conn.execute("SELECT query, answer, sources FROM experience WHERE vote='up' ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for q, a, src in rows:
        out.append(f"用户问题：{q}\n网络回答：{a}")
    return out


def search_experience(query, limit=3):
    like = "%" + (query or "")[:40] + "%"
    with LOCK:
        rows = conn.execute("SELECT query, answer FROM experience WHERE vote='up' AND (query LIKE ? OR answer LIKE ?) ORDER BY ts DESC LIMIT ?", (like, like, limit)).fetchall()
    return [{"query": q, "answer": a} for q, a in rows]

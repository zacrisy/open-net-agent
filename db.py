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

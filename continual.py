# -*- coding: utf-8 -*-
"""NBCL brain service: live learning cycles, knowledge cards, belief graph."""
import json, os, sqlite3, threading, time, uuid
import agent_core
try:
    from continual import extract_cards, dedup, build_belief
except Exception:
    from nbpw.continual import extract_cards, dedup, build_belief

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brain.db")
LOCK = threading.Lock()
CURRENT = {"cycle_id": None, "topic": None, "stage": "idle", "started": None, "elapsed": 0}
DEFAULT_TOPIC = "GLP-1 weight loss mechanism"


def _conn():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init():
    c = _conn()
    with c:
        c.execute("CREATE TABLE IF NOT EXISTS cycles (id TEXT PRIMARY KEY, topic TEXT, started REAL, finished REAL, stage TEXT, sources INTEGER, cards INTEGER, new_cards INTEGER, conflicts INTEGER, status TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS cards (id TEXT PRIMARY KEY, topic TEXT, claim TEXT, evidence TEXT, source_json TEXT, source_type TEXT, confidence REAL, status TEXT, support INTEGER, cycle_id TEXT, ts REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS edges (src TEXT, dst TEXT, kind TEXT)")
    c.close()


def _set(cid, stage, **kw):
    now = time.time()
    with LOCK:
        CURRENT.update({"cycle_id": cid, "stage": stage, "elapsed": round(now - (CURRENT.get("started") or now), 1)})
        if "topic" in kw: CURRENT["topic"] = kw["topic"]
    c = _conn()
    with c:
        c.execute("UPDATE cycles SET stage=? WHERE id=?", (stage, cid))
        for k in ("sources", "cards", "new_cards", "conflicts", "status"):
            if k in kw: c.execute(f"UPDATE cycles SET {k}=? WHERE id=?", (kw[k], cid))
    c.close()


def upsert(cards, cid):
    c = _conn(); new = 0; conflicts = 0
    with c:
        for card in cards:
            old = c.execute("SELECT id FROM cards WHERE id=?", (card["id"],)).fetchone()
            if not old: new += 1
            c.execute("INSERT OR REPLACE INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (card["id"], card["topic"], card["claim"], card["evidence"],
                       json.dumps(card.get("source", {}), ensure_ascii=False), card.get("source_type", "web"),
                       float(card.get("confidence", 0.5)), card.get("status", "active"),
                       int(card.get("support", 1)), cid, time.time()))
            c.execute("DELETE FROM edges WHERE src=?", (card["id"],))
            for dst in card.get("supports", []) or []: c.execute("INSERT INTO edges VALUES (?,?,?)", (card["id"], dst, "supports"))
            for dst in card.get("contradicts", []) or []: c.execute("INSERT INTO edges VALUES (?,?,?)", (card["id"], dst, "contradicts"))
            if card.get("status") == "disputed": conflicts += 1
    c.close(); return new, conflicts


def _run(cid, topic):
    try:
        _set(cid, "retrieving", topic=topic)
        sources = []
        for q in (topic, topic + " review"):
            try:
                got, _ = agent_core.collect(q)
                sources.extend(got)
            except Exception:
                pass
        seen, uniq = set(), []
        for s in sources:
            k = (s.get("title") or "")[:80]
            if k and k not in seen:
                seen.add(k); uniq.append(s)
        _set(cid, "extracting", sources=len(uniq))
        cards = extract_cards(topic, uniq)
        cards = dedup(cards)
        _set(cid, "verifying", cards=len(cards))
        build_belief(cards)
        _set(cid, "consolidating", cards=len(cards))
        new, conflicts = upsert(cards, cid)
        _set(cid, "complete", cards=len(cards), new_cards=new, conflicts=conflicts, status="complete")
    except Exception as e:
        with LOCK: CURRENT["stage"] = "error"; CURRENT["error"] = str(e)[:200]
        c = _conn()
        with c: c.execute("UPDATE cycles SET status='error', finished=? WHERE id=?", (time.time(), cid))
        c.close()
    finally:
        with LOCK: CURRENT["elapsed"] = round(time.time() - (CURRENT.get("started") or time.time()), 1)
        c = _conn()
        with c:
            c.execute("UPDATE cycles SET finished=?, stage='complete' WHERE id=?", (time.time(), cid))
            c.execute("UPDATE cycles SET stage=? WHERE id=? AND status='error'", ("error", cid))
        c.close()


def start(topic=None):
    topic = (topic or DEFAULT_TOPIC).strip()[:120]
    with LOCK:
        if CURRENT.get("stage") in ("retrieving", "extracting", "verifying", "consolidating"):
            return {"cycle_id": CURRENT["cycle_id"], "status": "already_running", "topic": CURRENT["topic"]}
        cid = uuid.uuid4().hex[:12]
        CURRENT.update({"cycle_id": cid, "topic": topic, "stage": "queued", "started": time.time(), "elapsed": 0})
    c = _conn()
    with c: c.execute("INSERT INTO cycles VALUES (?,?,?,?,?,?,?,?,?,?)", (cid, topic, time.time(), None, "queued", 0, 0, 0, 0, "running"))
    c.close()
    threading.Thread(target=_run, args=(cid, topic), daemon=True).start()
    return {"cycle_id": cid, "status": "started", "topic": topic}


def status():
    c = _conn()
    cards = c.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    active = c.execute("SELECT COUNT(*) FROM cards WHERE status='active'").fetchone()[0]
    disputed = c.execute("SELECT COUNT(*) FROM cards WHERE status='disputed'").fetchone()[0]
    cycles = c.execute("SELECT COUNT(*) FROM cycles").fetchone()[0]
    topics = c.execute("SELECT topic, COUNT(*) FROM cards GROUP BY topic").fetchall()
    rows = c.execute("SELECT id,topic,started,finished,stage,sources,cards,new_cards,conflicts,status FROM cycles ORDER BY started DESC LIMIT 6").fetchall()
    feed = c.execute("SELECT id,topic,claim,source_type,confidence,status,ts FROM cards ORDER BY ts DESC LIMIT 12").fetchall()
    c.close()
    with LOCK:
        cur = dict(CURRENT)
        if cur.get("started"): cur["elapsed"] = round(time.time() - cur["started"], 1)
    return {"learning": cur,
            "metrics": {"cards": cards, "active": active, "disputed": disputed, "cycles": cycles,
                        "topics": [{"topic": t, "count": n} for t, n in topics],
                        "avg_confidence": round(sum(x[4] for x in feed) / max(1, len(feed)), 2)},
            "cycles": [{"id": r[0], "topic": r[1], "started": r[2], "finished": r[3], "stage": r[4],
                        "sources": r[5], "cards": r[6], "new_cards": r[7], "conflicts": r[8], "status": r[9]} for r in rows],
            "feed": [{"id": r[0], "topic": r[1], "claim": r[2][:260], "source_type": r[3], "confidence": r[4], "status": r[5]} for r in feed]}


def cards(limit=120):
    c = _conn()
    rows = c.execute("SELECT id,topic,claim,source_json,source_type,confidence,status,support FROM cards ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return [{"id": r[0], "topic": r[1], "claim": r[2], "source": json.loads(r[3] or "{}"), "source_type": r[4], "confidence": r[5], "status": r[6], "support": r[7]} for r in rows]


def graph():
    cs = cards(160)
    by_topic = {}
    for card in cs: by_topic.setdefault(card["topic"], []).append(card)
    nodes = []
    for topic, items in by_topic.items():
        for i, card in enumerate(items):
            import math
            ang = 2 * math.pi * i / max(1, len(items))
            rad = 100 + (hash(topic) % 50)
            nodes.append({"id": card["id"], "topic": topic, "label": card["claim"][:90],
                          "status": card["status"], "confidence": card["confidence"],
                          "source_type": card["source_type"], "x": math.cos(ang) * rad,
                          "y": math.sin(ang) * rad})
    edges = []
    c = _conn()
    for src, dst, kind in c.execute("SELECT src,dst,kind FROM edges").fetchall():
        edges.append({"source": src, "target": dst, "kind": kind})
    c.close()
    return {"nodes": nodes, "edges": edges, "topics": list(by_topic.keys())}


def maybe_bootstrap():
    c = _conn(); n = c.execute("SELECT COUNT(*) FROM cards").fetchone()[0]; c.close()
    if n == 0: start(DEFAULT_TOPIC)


init()

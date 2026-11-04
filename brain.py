# -*- coding: utf-8 -*-
"""NBCL brain service: live learning cycles, knowledge cards, belief graph."""
import json, os, random, re, sqlite3, threading, time, uuid
import agent_core
try:
    from continual import extract_cards, dedup, build_belief, conflict_type, score, make_questions, toks
except Exception:
    from nbpw.continual import extract_cards, dedup, build_belief, conflict_type, score, make_questions, toks

DB = os.environ.get("BRAIN_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "brain.db")
LOCK = threading.Lock()
CURRENT = {"cycle_id": None, "topic": None, "stage": "idle", "started": None, "elapsed": 0}
AUTO = {"enabled": False, "interval": 20, "next": None, "last": None, "last_kind": None}
AUTO_INTERVAL = 20
AUTO_STARTED = False
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
        c.execute("CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY, kind TEXT, text TEXT, contact TEXT, topic TEXT, status TEXT, created REAL, updated REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS improvements (id TEXT PRIMARY KEY, feedback_id TEXT, kind TEXT, title TEXT, detail TEXT, status TEXT, created REAL, updated REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS quiz (id TEXT PRIMARY KEY, card_id TEXT, question TEXT, answer TEXT, topic TEXT, correct INTEGER, ts REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS card_meta (id TEXT PRIMARY KEY, access_count INTEGER DEFAULT 0, last_access REAL DEFAULT 0, tier TEXT DEFAULT 'warm')")
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




def self_test(n=3):
    import graph_retrieval
    cs = cards(200)
    if not cs:
        return {"n": 0, "correct": 0}
    qs = make_questions(cs, per_topic=2)[:n]
    c = _conn(); correct = 0
    with c:
        for q in qs:
            r = graph_retrieval.retrieve(q["q"], 3)
            hit = any(x.get("id") == q["card"]["id"] for x in r.get("cards", []))
            correct += int(hit)
            c.execute("INSERT INTO quiz VALUES (?,?,?,?,?,?,?)",
                      ("q-" + uuid.uuid4().hex[:10], q["card"]["id"], q["q"], q.get("answer", ""), q.get("topic", ""), int(hit), time.time()))
    c.close()
    return {"n": len(qs), "correct": correct}


def retention():
    c = _conn()
    row = c.execute("SELECT COUNT(*), COALESCE(SUM(correct),0) FROM quiz").fetchone()
    recent = c.execute("SELECT correct FROM quiz ORDER BY ts DESC LIMIT 100").fetchall()
    c.close()
    total, good = row
    return {"n": total, "correct": good, "rate": round(good / total, 3) if total else 0.0,
            "recent": round(sum(x[0] for x in recent) / len(recent), 3) if recent else 0.0}



def touch(ids):
    if not ids:
        return
    c = _conn(); now = time.time()
    with c:
        for nid in ids:
            c.execute("INSERT INTO card_meta(id,access_count,last_access,tier) VALUES(?,?,?,'hot') ON CONFLICT(id) DO UPDATE SET access_count=access_count+1,last_access=excluded.last_access,tier='hot'",
                      (nid, 1, now))
    c.close()


def refresh_tiers():
    c = _conn(); now = time.time()
    rows = c.execute("SELECT id,ts FROM cards").fetchall()
    with c:
        for nid, ts in rows:
            tier = "hot" if ts and now - ts < 7 * 86400 else ("cold" if ts and now - ts > 30 * 86400 else "warm")
            c.execute("INSERT INTO card_meta(id,tier) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET tier=excluded.tier", (nid, tier))
    c.close()


def tier_counts():
    c = _conn()
    rows = c.execute("SELECT tier,COUNT(*) FROM card_meta GROUP BY tier").fetchall()
    c.close()
    return {t: n for t, n in rows}

def novelty_filter(cards):
    """Skip near-duplicate cards against history; merge support/confidence."""
    if not cards:
        return cards, 0
    c = _conn()
    rows = c.execute("SELECT id,topic,claim,evidence,source_json,source_type,confidence,status,support FROM cards").fetchall()
    existing = []
    for r in rows:
        existing.append({"id": r[0], "topic": r[1], "claim": r[2], "evidence": r[3],
                         "source": json.loads(r[4] or "{}"), "source_type": r[5],
                         "confidence": r[6], "status": r[7], "support": r[8]})
    keep, skipped = [], 0
    with c:
        for n in cards:
            hit = None
            for old in existing:
                if old.get("topic") != n.get("topic"):
                    continue
                if conflict_type(n, old):
                    continue
                a, b = toks(n.get("claim", "")), toks(old.get("claim", ""))
                if a and b and len(a & b) / len(a | b) > .82:
                    hit = old; break
            if hit:
                skipped += 1
                hit["support"] = int(hit.get("support", 1)) + 1
                hit["confidence"] = max(float(hit.get("confidence", 0)), float(n.get("confidence", 0)))
                c.execute("UPDATE cards SET support=?, confidence=? WHERE id=?", (hit["support"], hit["confidence"], hit["id"]))
            else:
                keep.append(n)
    c.close()
    return keep, skipped

def reconcile(new_cards):
    """Compare new cards against the existing library, mark conflicts with type."""
    if not new_cards:
        return 0
    c = _conn()
    rows = c.execute("SELECT id,topic,claim,evidence,source_json,source_type,confidence,status,support FROM cards").fetchall()
    existing = []
    for r in rows:
        existing.append({"id": r[0], "topic": r[1], "claim": r[2], "evidence": r[3],
                         "source": json.loads(r[4] or "{}"), "source_type": r[5],
                         "confidence": r[6], "status": r[7], "support": r[8]})
    by_topic = {}
    for old in existing:
        by_topic.setdefault(old.get("topic", ""), []).append(old)
    pairs = 0
    with c:
        for n in new_cards:
            n.setdefault("contradicts", [])
            for old in by_topic.get(n.get("topic", ""), []):
                typ = conflict_type(n, old)
                if not typ:
                    continue
                pairs += 1
                n["conflict_type"] = typ
                n["contradicts"].append(old["id"])
                if score(n) >= score(old):
                    old["status"] = "disputed"
                else:
                    n["status"] = "disputed"
                c.execute("UPDATE cards SET status=? WHERE id=?", (old["status"], old["id"]))
    c.close()
    return pairs

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
            for dst in card.get("contradicts", []) or []:
                c.execute("INSERT INTO edges VALUES (?,?,?)", (card["id"], dst, "contradicts:" + str(card.get("conflict_type", "unknown"))))
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
        cards, redundant = novelty_filter(cards)
        _set(cid, "verifying", cards=len(cards))
        build_belief(cards)
        reconciled = reconcile(cards)
        _set(cid, "consolidating", cards=len(cards))
        new, conflicts = upsert(cards, cid)
        mark_feedback_learned(topic)
        try:
            self_test(3)
        except Exception as e:
            print("SELF TEST ERROR:", e, flush=True)
        _set(cid, "complete", cards=len(cards), new_cards=new, conflicts=conflicts + reconciled, status="complete")
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


def consolidate():
    with LOCK:
        if CURRENT.get("stage") in ("retrieving", "extracting", "verifying", "consolidating"):
            return {"status": "busy"}
        cid = uuid.uuid4().hex[:12]
        CURRENT.update({"cycle_id": cid, "topic": "EVOLUTION", "stage": "consolidating", "started": time.time(), "elapsed": 0})
    c = _conn()
    with c:
        c.execute("INSERT INTO cycles VALUES (?,?,?,?,?,?,?,?,?,?)", (cid, "EVOLUTION", time.time(), None, "consolidating", 0, 0, 0, 0, "running"))
        rows = c.execute("SELECT id,topic,claim,evidence,source_json,source_type,confidence,status,support FROM cards").fetchall()
    c.close()
    cards = []
    for r in rows:
        cards.append({"id": r[0], "topic": r[1], "claim": r[2], "evidence": r[3], "source": json.loads(r[4] or "{}"),
                      "source_type": r[5], "confidence": r[6], "status": "active", "support": r[8]})
    cards = dedup(cards); build_belief(cards)
    new, conflicts = upsert(cards, cid)
    refresh_tiers()
    with LOCK:
        AUTO["last"] = time.time(); AUTO["last_kind"] = "evolve"
        CURRENT["stage"] = "complete"; CURRENT["topic"] = "EVOLUTION"; CURRENT["elapsed"] = round(time.time() - CURRENT["started"], 1)
    c = _conn()
    with c: c.execute("UPDATE cycles SET stage='complete', status='complete', finished=?, cards=?, conflicts=? WHERE id=?", (time.time(), len(cards), conflicts, cid))
    c.close()
    return {"cycle_id": cid, "status": "complete", "topic": "EVOLUTION", "cards": len(cards), "conflicts": conflicts}


def start(topic=None):
    topic = (topic or DEFAULT_TOPIC).strip()[:120]
    with LOCK:
        if CURRENT.get("stage") in ("retrieving", "extracting", "verifying", "consolidating"):
            return {"cycle_id": CURRENT["cycle_id"], "status": "already_running", "topic": CURRENT["topic"]}
        cid = uuid.uuid4().hex[:12]
        CURRENT.update({"cycle_id": cid, "topic": topic, "stage": "queued", "started": time.time(), "elapsed": 0})
        AUTO["last"] = time.time(); AUTO["last_kind"] = "learn"
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
    srcs = set()
    for (sj,) in c.execute("SELECT source_json FROM cards").fetchall():
        try: srcs.add(json.loads(sj or "{}").get("url") or "")
        except Exception: pass
    srcs.discard("")
    mix = c.execute("SELECT source_type, COUNT(*) FROM cards GROUP BY source_type ORDER BY COUNT(*) DESC").fetchall()
    fb_count = c.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    fb_open = c.execute("SELECT COUNT(*) FROM feedback WHERE status != 'learned'").fetchone()[0]
    imp_count = c.execute("SELECT COUNT(*) FROM improvements").fetchone()[0]
    c.close()
    with LOCK:
        cur = dict(CURRENT)
        if cur.get("started"): cur["elapsed"] = round(time.time() - cur["started"], 1)
    auto = dict(AUTO)
    if auto.get("next"): auto["next_in"] = max(0, round(auto["next"] - time.time()))
    return {"learning": cur, "auto": auto,
            "metrics": {"cards": cards, "active": active, "disputed": disputed, "cycles": cycles,
                        "topics": [{"topic": t, "count": n} for t, n in topics],
                        "avg_confidence": round(sum(x[4] for x in feed) / max(1, len(feed)), 2),
                        "sources": len(srcs), "source_mix": [{"type": t, "count": n} for t, n in mix],
                        "feedback": fb_count, "feedback_open": fb_open, "improvements": imp_count,
                        "quiz": retention()["n"], "retention": retention()["rate"],
                        "tiers": tier_counts()},
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
                          "claim": card["claim"], "status": card["status"], "confidence": card["confidence"],
                          "source_type": card["source_type"], "source_url": card.get("source", {}).get("url", ""),
                          "source_title": card.get("source", {}).get("title", ""),
                          "x": math.cos(ang) * rad, "y": math.sin(ang) * rad})
    edges = []
    c = _conn()
    for src, dst, kind in c.execute("SELECT src,dst,kind FROM edges").fetchall():
        edges.append({"source": src, "target": dst, "kind": kind})
    c.close()
    # add semantic support edges within each topic (belief graph is not only conflicts)
    import re
    def tok(s):
        return set(re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", (s or "").lower()))
    seen = {(e["source"], e["target"], e["kind"]) for e in edges}
    for topic, items in by_topic.items():
        added = 0
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = tok(items[i]["claim"]), tok(items[j]["claim"])
                if a and b and len(a & b) / len(a | b) > 0.10:
                    key = (items[i]["id"], items[j]["id"], "supports")
                    if key not in seen:
                        seen.add(key); edges.append({"source": key[0], "target": key[1], "kind": "supports"}); added += 1
        if added == 0:
            for i in range(len(items) - 1):
                key = (items[i]["id"], items[i+1]["id"], "supports")
                if key not in seen:
                    seen.add(key); edges.append({"source": key[0], "target": key[1], "kind": "supports"})
    return {"nodes": nodes, "edges": edges, "topics": list(by_topic.keys())}


AUTO_TOPICS = ["GLP-1 weight loss mechanism", "AI agent evaluation", "Python asyncio event loop",
               "LLM agent reliability evaluation", "retrieval augmented generation evaluation",
               "graph neural network advances", "knowledge graph construction",
               "continual learning catastrophic forgetting", "federated learning privacy",
               "semaglutide cardiovascular outcomes"]


def auto_start(interval=90):
    global AUTO_STARTED
    with LOCK:
        if AUTO_STARTED:
            return
        AUTO_STARTED = True
        AUTO.update({"enabled": True, "interval": interval, "next": time.time() + 4})
    def loop():
        time.sleep(4)
        while True:
            try:
                with LOCK:
                    busy = CURRENT.get("stage") in ("retrieving", "extracting", "verifying", "consolidating")
                if not busy:
                    if AUTO.get("last_kind") == "learn":
                        consolidate()
                    else:
                        fb = next_feedback_topic()
                        if fb:
                            r = start(fb["topic"])
                            if r.get("status") in ("started", "already_running"):
                                mark_feedback_learning(fb["id"])
                        else:
                            start(random.choice(AUTO_TOPICS))
            except Exception as e:
                print("AUTO LOOP ERROR:", e, flush=True)
            with LOCK:
                AUTO["next"] = time.time() + interval
            time.sleep(interval)
    threading.Thread(target=loop, daemon=True).start()


def _classify(text):
    low = (text or "").lower()
    if any(x in low for x in ("bug", "报错", "错误", "失效", "不能", "崩溃", "failed", "error", "卡住")):
        return "bug"
    if any(x in low for x in ("学习", "知识", "了解", "研究", "learn", "topic", "资料", "主题")):
        return "knowledge"
    if any(x in low for x in ("回答", "引用", "风格", "中文", "太长", "太短", "答案", "语气")):
        return "style"
    if any(x in low for x in ("功能", "增加", "支持", "feature", "add", "希望")):
        return "feature"
    return "other"


def _topic_from(text):
    m = re.search(r"(?:学习|了解|研究|learn|about|topic)\s*[:：]?\s*(.+)", text or "", re.I)
    topic = (m.group(1) if m else (text or "")).strip()
    topic = re.split(r"[。！？.!?\n]", topic)[0].strip()
    return (topic or "user suggested topic")[:90]


def submit_feedback(text, kind=None, contact=""):
    text = (text or "").strip()[:1200]
    if len(text) < 4:
        return {"error": "please write at least 4 characters"}
    kind = (kind or "").strip().lower()
    if kind not in ("bug", "feature", "knowledge", "style", "other"):
        kind = _classify(text)
    fid = "fb-" + uuid.uuid4().hex[:10]
    now = time.time()
    topic = _topic_from(text) if kind in ("knowledge", "feature") else ""
    status = "queued" if kind == "knowledge" else "open"
    c = _conn()
    with c:
        c.execute("INSERT INTO feedback VALUES (?,?,?,?,?,?,?,?)", (fid, kind, text, (contact or "")[:120], topic, status, now, now))
        title = (("Learn: " + topic) if kind == "knowledge" else ("Feature: " if kind == "feature" else ("Bug: " if kind == "bug" else ("Answer quality: " if kind == "style" else "Review: "))) + text[:80])
        c.execute("INSERT INTO improvements VALUES (?,?,?,?,?,?,?,?)",
                  ("imp-" + uuid.uuid4().hex[:10], fid, kind, title, text[:600], ("queued" if kind == "knowledge" else "open"), now, now))
    c.close()
    return {"id": fid, "kind": kind, "topic": topic, "status": status}


def feedback_list(limit=20):
    c = _conn()
    rows = c.execute("SELECT id,kind,text,contact,topic,status,created FROM feedback ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return [{"id": r[0], "kind": r[1], "text": r[2][:500], "topic": r[4], "status": r[5], "created": r[6]} for r in rows]


def improvement_list(limit=20):
    c = _conn()
    rows = c.execute("SELECT id,feedback_id,kind,title,status,created FROM improvements ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return [{"id": r[0], "feedback_id": r[1], "kind": r[2], "title": r[3], "status": r[4], "created": r[5]} for r in rows]


def next_feedback_topic():
    c = _conn()
    r = c.execute("SELECT id,topic FROM feedback WHERE status='queued' AND kind='knowledge' ORDER BY created LIMIT 1").fetchone()
    c.close()
    return {"id": r[0], "topic": r[1]} if r else None


def mark_feedback_learning(fid):
    c = _conn()
    with c:
        c.execute("UPDATE feedback SET status='learning', updated=? WHERE id=?", (time.time(), fid))
        c.execute("UPDATE improvements SET status='in_progress', updated=? WHERE feedback_id=?", (time.time(), fid))
    c.close()


def mark_feedback_learned(topic):
    c = _conn()
    with c:
        rows = c.execute("SELECT id FROM feedback WHERE status IN ('queued','learning') AND topic=?", (topic,)).fetchall()
        for (fid,) in rows:
            c.execute("UPDATE feedback SET status='learned', updated=? WHERE id=?", (time.time(), fid))
            c.execute("UPDATE improvements SET status='applied', updated=? WHERE feedback_id=?", (time.time(), fid))
    c.close()

def auto_tick():
    with LOCK:
        now = time.time()
        if AUTO.get("next") and now < AUTO["next"]:
            return {"status": "wait", "next_in": round(AUTO["next"] - now)}
        busy = CURRENT.get("stage") in ("retrieving", "extracting", "verifying", "consolidating")
    if busy:
        with LOCK: AUTO["next"] = time.time() + 5
        return {"status": "busy", "stage": CURRENT.get("stage")}
    fb = next_feedback_topic()
    if fb:
        r = start(fb["topic"])
        if r.get("status") in ("started", "already_running"):
            mark_feedback_learning(fb["id"])
        action = "feedback"
    elif AUTO.get("last_kind") == "learn":
        r = consolidate(); action = "evolve"
    else:
        r = start(random.choice(AUTO_TOPICS)); action = "learn"
    with LOCK:
        AUTO.update({"enabled": True, "interval": AUTO_INTERVAL, "next": time.time() + AUTO_INTERVAL, "last": time.time()})
    return {"status": "started", "action": action, "result": r, "next_in": AUTO_INTERVAL}


def maybe_bootstrap():
    c = _conn(); n = c.execute("SELECT COUNT(*) FROM cards").fetchone()[0]; c.close()
    if n == 0: start(DEFAULT_TOPIC)


init()

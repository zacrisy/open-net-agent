# -*- coding: utf-8 -*-
"""NBCL prototype: knowledge cards, belief graph, curriculum questions."""
import hashlib, math, re
from collections import Counter

STOP = set("the a an of and or to in for with on by from is are was were be been this that these those what how why which who whom whose does do did can could should would may might will".split())
NEG = re.compile(r"\b(not|no|never|without|does not|did not|is not|are not|cannot|can't|decrease|decreases|reduce|reduces|inhibit|inhibits)\b", re.I)


def toks(s):
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", (s or "").lower())) - STOP


def sents(text):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", text or "") if len(x.strip()) > 40]


def key_terms(topic):
    return [w for w in re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", topic.lower()) if w not in STOP]


def source_kind(source):
    s = source if isinstance(source, dict) else {}
    blob = ((s.get("url") or "") + " " + (s.get("title") or "") + " " + (s.get("source") or "")).lower()
    if "pubmed" in blob: return "PubMed"
    if "arxiv" in blob: return "arXiv"
    if "ycombinator" in blob or "hacker news" in blob: return "Hacker News"
    if "stackoverflow" in blob or "stack overflow" in blob: return "Stack Overflow"
    if "openalex" in blob: return "OpenAlex"
    if "doi.org" in blob or "crossref" in blob: return "Crossref"
    return (s.get("source") or "web")[:40]


def trust(source):
    s = source_kind(source).lower()
    if "pubmed" in s: return .92
    if "arxiv" in s: return .86
    if "openalex" in s: return .82
    if "crossref" in s: return .78
    if "stack overflow" in s: return .72
    if "hacker news" in s: return .62
    return .60


def extract_cards(topic, sources):
    terms = set(key_terms(topic)); cards = []
    for s in sources:
        text = (s.get("snippet") or "") or (s.get("title") or "")
        ranked = sorted(sents(text), key=lambda x: (len(terms & toks(x)), len(x)), reverse=True)[:2]
        if not ranked and s.get("title"):
            ranked = [s["title"]]
        for claim in ranked:
            if len(claim) < 40: continue
            overlap = len(terms & toks(claim))
            kind = source_kind(s)
            conf = trust(s) * (0.58 + min(.30, overlap * .08))
            cards.append({"id": "kc-" + hashlib.sha1(claim.encode()).hexdigest()[:10], "topic": topic,
                          "claim": claim[:600], "evidence": claim[:600], "source": s,
                          "source_type": kind, "confidence": round(min(.95, conf), 3),
                          "status": "active", "support": 1})
    return cards


def _norm(c):
    return " ".join(sorted(toks(c["claim"])))


def dedup(cards):
    out = []
    for c in cards:
        merged = False
        for o in out:
            a, b = toks(c["claim"]), toks(o["claim"])
            if a and b and len(a & b) / len(a | b) > .80:
                o["support"] += 1
                if c["confidence"] > o["confidence"]: o["confidence"] = c["confidence"]
                merged = True; break
        if not merged: out.append(c)
    return out


NUM = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|mg|kg|g|ml|mmhg|weeks?|months?|years?)?\b", re.I)
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
POP = re.compile(r"\b(adults?|children|elderly|mice|rats|patients?|pregnant|women|men)\b", re.I)
DEF = re.compile(r"\b(is defined as|refers to|means)\b", re.I)


def conflict_type(a, b):
    ta, tb = toks(a.get("claim", "")), toks(b.get("claim", ""))
    if not ta or not tb:
        return None
    overlap = len(ta & tb) / len(ta | tb)
    if overlap < .35:
        return None
    ca, cb = a.get("claim", ""), b.get("claim", "")
    na, nb = bool(NEG.search(ca)), bool(NEG.search(cb))
    if na != nb:
        return "negation"
    nums_a = set(NUM.findall(ca)); nums_b = set(NUM.findall(cb))
    if nums_a and nums_b and nums_a != nums_b:
        return "numeric"
    years_a = set(YEAR.findall(ca)); years_b = set(YEAR.findall(cb))
    if years_a and years_b and years_a != years_b:
        return "temporal"
    pops_a = set(x.lower() for x in POP.findall(ca)); pops_b = set(x.lower() for x in POP.findall(cb))
    if pops_a and pops_b and pops_a != pops_b:
        return "population"
    if DEF.search(ca) != DEF.search(cb):
        return "definition"
    return None


def conflict(a, b):
    return conflict_type(a, b) is not None


def score(card):
    try: year = int(str(card["source"].get("year") or "0")[:4])
    except Exception: year = 0
    rec = max(0, min(1, (year - 2015) / 11)) if year else .4
    return .55 * trust(card["source"]) + .25 * card["confidence"] + .10 * rec + .10 * min(3, card["support"]) / 3


def build_belief(cards):
    for i, a in enumerate(cards):
        for b in cards[i + 1:]:
            if a["topic"] != b["topic"]: continue
            if conflict(a, b):
                w, l = (a, b) if score(a) >= score(b) else (b, a)
                w.setdefault("supports", []); w.setdefault("contradicts", []).append(l["id"])
                l["status"] = "disputed"; l.setdefault("contradicts", []).append(w["id"])
    return cards


def mask_question(claim):
    m = re.search(r"\b\d+(?:\.\d+)?%?\b", claim)
    phrase = m.group(0) if m else None
    if not phrase:
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-]{5,}", claim) if w.lower() not in STOP]
        if words:
            phrase = max(words, key=len)
    if not phrase: return None
    return claim.replace(phrase, "____", 1), phrase


def retrieve(q, docs, doc_text):
    qt = toks(q)
    best, bs = None, -1
    for d in docs:
        text = doc_text(d)
        s = len(qt & toks(text)) / (math.sqrt(len(toks(text)) + 1))
        if s > bs: best, bs = d, s
    return best


def make_questions(cards, per_topic=4):
    out = []
    for topic in sorted({c["topic"] for c in cards}):
        active = [c for c in cards if c["topic"] == topic and c["status"] == "active"]
        for c in active[:per_topic]:
            mq = mask_question(c["claim"])
            if mq: out.append({"topic": topic, "q": mq[0], "answer": mq[1], "source": c["source"], "card": c})
    return out

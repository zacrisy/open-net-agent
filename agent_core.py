# -*- coding: utf-8 -*-
"""OpenNetAgent 的真实能力：多源研究、文档问答、计算、引用与经验。"""
import ast, html, json, math, os, re, time, urllib.parse, urllib.request
from xml.etree import ElementTree as ET

UA = {"User-Agent": "OpenNetAgent/0.7 (+https://github.com/zacrisy/open-net-agent)"}
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")
CACHE = {}


def _get(url, timeout=12):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _json(url, timeout=12):
    return json.loads(_get(url, timeout).decode("utf-8", "ignore"))


def _strip(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return html.unescape(re.sub(r"\s+", " ", s)).strip()


def _cache(key, fn, ttl=600):
    now = time.time()
    if key in CACHE and now - CACHE[key][0] < ttl:
        return CACHE[key][1]
    val = fn()
    CACHE[key] = (now, val)
    return val


def pubmed(q, n=3):
    def run():
        j = _json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&retmax=%d&term=%s" % (n, urllib.parse.quote(q)))
        ids = j.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        xml = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml&id=%s" % ",".join(ids))
        root = ET.fromstring(xml)
        out = []
        for art in root.findall(".//PubmedArticle"):
            title = "".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else ""
            abstract = " ".join("".join(a.itertext()) for a in art.findall(".//AbstractText"))
            pmid = art.findtext(".//PMID") or ""
            year = art.findtext(".//PubDate/Year") or ""
            journal = art.findtext(".//Journal/Title") or "PubMed"
            out.append({"title": _strip(title), "snippet": _strip(abstract)[:900], "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "source": journal, "year": year})
        return out
    return _cache(("pubmed", q, n), run)


def arxiv(q, n=3):
    def run():
        url = "https://export.arxiv.org/api/query?search_query=all:%s&max_results=%d" % (urllib.parse.quote(q), n)
        root = ET.fromstring(_get(url))
        ns = {"a": "http://www.w3.org/2005/Atom"}
        out = []
        for e in root.findall("a:entry", ns):
            out.append({"title": _strip(e.findtext("a:title", "", ns)), "snippet": _strip(e.findtext("a:summary", "", ns))[:900],
                        "url": e.findtext("a:id", "", ns), "source": "arXiv", "year": (e.findtext("a:published", "", ns) or "")[:4]})
        return out
    return _cache(("arxiv", q, n), run)


def hackernews(q, n=5):
    def run():
        j = _json("https://hn.algolia.com/api/v1/search?query=%s&tags=story&hitsPerPage=%d" % (urllib.parse.quote(q), n))
        out = []
        for h in j.get("hits", []):
            out.append({"title": h.get("title") or "", "snippet": (h.get("story_text") or h.get("comment_text") or "")[:500] or f"{h.get('points', 0)} points · {h.get('num_comments', 0)} comments",
                        "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}", "source": "Hacker News", "year": (h.get("created_at") or "")[:4]})
        return out
    return _cache(("hn", q, n), run)


def stackexchange(q, n=4):
    def run():
        j = _json("https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=relevance&q=%s&site=stackoverflow&pagesize=%d&filter=withbody" % (urllib.parse.quote(q), n))
        items = j.get("items", [])
        if not items:
            return []
        qids = ";".join(str(it["question_id"]) for it in items)
        best = {}
        try:
            ans = _json("https://api.stackexchange.com/2.3/questions/%s/answers?order=desc&sort=votes&site=stackoverflow&pagesize=20&filter=withbody" % qids)
            for a in ans.get("items", []):
                qid = a.get("question_id")
                if qid not in best or a.get("is_accepted") or a.get("score", 0) > best[qid].get("score", 0):
                    best[qid] = a
        except Exception:
            pass
        out = []
        for it in items:
            qid = it.get("question_id"); a = best.get(qid)
            body = a.get("body") if a else it.get("body", "")
            url = it.get("link", "")
            if a: url += "#answer-%s" % a.get("answer_id")
            out.append({"title": _strip(it.get("title", "")), "snippet": _strip(body)[:1000],
                        "url": url, "source": "Stack Overflow", "year": ""})
        return out
    return _cache(("se", q, n), run)


def openalex(q, n=4):
    def run():
        j = _json("https://api.openalex.org/works?search=%s&per-page=%d" % (urllib.parse.quote(q), n))
        out = []
        for w in j.get("results", []):
            inv = w.get("abstract_inverted_index")
            abstract = ""
            if inv:
                pos = {}
                for word, idxs in inv.items():
                    for i in idxs: pos[i] = word
                abstract = " ".join(pos[i] for i in sorted(pos))[:900]
            out.append({"title": w.get("display_name") or "", "snippet": abstract,
                        "url": w.get("doi") or w.get("id") or "", "source": (w.get("primary_location") or {}).get("source", {}).get("display_name") or "OpenAlex",
                        "year": str(w.get("publication_year") or "")})
        return out
    return _cache(("openalex", q, n), run)


def crossref(q, n=3):
    def run():
        j = _json("https://api.crossref.org/works?query=%s&rows=%d" % (urllib.parse.quote(q), n))
        out = []
        for w in j.get("message", {}).get("items", []):
            title = (w.get("title") or [""])[0]
            out.append({"title": _strip(title), "snippet": _strip(w.get("abstract", ""))[:800], "url": w.get("URL", ""), "source": "Crossref", "year": str((w.get("issued", {}).get("date-parts") or [[""]])[0][0])})
        return out
    return _cache(("crossref", q, n), run)


def _has(q, words):
    return any(w in q for w in words)


def route(query, mode="auto"):
    q = query.lower()
    if mode and mode not in ("auto", "research"):
        return [mode]
    if _has(q, ["药", "临床", "疾病", "医学", "患者", "drug", "clinical", "disease", "patient", "glp", "diabetes"]):
        return ["pubmed", "openalex"]
    if _has(q, ["论文", "paper", "研究", "arxiv", "模型", "算法", "transformer", "llm"]):
        return ["arxiv", "openalex"]
    if _has(q, ["新闻", "news", "最新", "发布", "融资", "startup", "launch"]):
        return ["hackernews", "openalex"]
    if _has(q, ["代码", "python", "javascript", "报错", "error", "api", "库", "bug"]):
        return ["stackexchange", "hackernews"]
    return ["openalex", "hackernews", "crossref"]


FETCH = {"pubmed": pubmed, "arxiv": arxiv, "hackernews": hackernews, "stackexchange": stackexchange, "openalex": openalex, "crossref": crossref}


def collect(query, mode="auto"):
    names = route(query, mode)
    sources, used = [], []
    for name in names:
        try:
            got = FETCH[name](query, 4 if name in ("hackernews", "openalex") else 3)
            if got:
                used.append(name); sources.extend(got[:4])
        except Exception:
            continue
    # dedupe by title
    seen, out = set(), []
    for s in sources:
        k = (s.get("title") or "")[:80]
        if k and k not in seen:
            seen.add(k); out.append(s)
    return out[:8], used


def _tokens(s):
    s = s.lower()
    en = re.findall(r"[a-z0-9]{2,}", s)
    zh = re.findall(r"[\u4e00-\u9fff]", s)
    bi = [zh[i] + zh[i + 1] for i in range(len(zh) - 1)]
    return set(en + zh + bi)


def _sentences(text):
    return [x.strip() for x in re.split(r"(?<=[。！？.!?])\s*|\n+", text or "") if len(x.strip()) > 20]


def extractive(query, sources):
    q = _tokens(query)
    scored = []
    for i, s in enumerate(sources):
        for sent in _sentences(s.get("snippet", "")):
            scored.append((len(q & _tokens(sent)), i, sent))
    scored.sort(reverse=True)
    picked, seen = [], set()
    for _, i, sent in scored:
        if sent in seen: continue
        seen.add(sent); picked.append(f"{sent} [{i+1}]")
        if len(picked) >= 4: break
    if not picked:
        picked = [f"{s.get('title','')} [{i+1}]" for i, s in enumerate(sources[:4])]
    return "结论：" + "；".join(picked[:2]) + "\n\n要点：\n" + "\n".join("- " + p for p in picked[2:]) if len(picked) > 1 else "结论：" + picked[0]


def llm(prompt, timeout=75, num_predict=140):
    payload = {"model": MODEL, "prompt": prompt, "stream": False,
               "options": {"num_predict": num_predict, "temperature": 0.25, "top_p": 0.9}}
    try:
        req = urllib.request.Request(OLLAMA + "/api/generate", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read()).get("response", "").strip()
    except Exception:
        return ""


def _research_prompt(query, sources):
    ctx = "\n".join(f"[{i+1}] {s.get('title','')} ({s.get('source','')} {s.get('year','')})\n{s.get('snippet','')[:700]}" for i, s in enumerate(sources[:6]))
    return f"""你是 OpenNetAgent 的研究助手。只根据来源回答，不要编造；来源不足就直说。
用中文输出：先给 2-3 句结论，再给 2-4 条要点，每条尽量带 [n] 引用。
问题：{query}
来源：
{ctx}
"""


STOP = set("the a an of and or to in for with on by from is are was were be been this that these those what how why which who whom whose does do did can could should would may might will".split())
MECH = set("mechanism receptor agonist insulin glucagon appetite gastric weight glucose secretion reduce increase inhibit stimulate receptor".split())


def is_zh(s):
    return bool(re.search(r"[\u4e00-\u9fff]", s or ""))


def translate(text, pair="zh-CN|en"):
    if not text:
        return ""
    def run():
        try:
            url = "https://api.mymemory.translated.net/get?q=%s&langpair=%s" % (urllib.parse.quote(text[:900]), urllib.parse.quote(pair))
            j = _json(url, timeout=12)
            return (j.get("responseData", {}) or {}).get("translatedText", "") or ""
        except Exception:
            return ""
    return _cache(("tr", pair, text[:200]), run, 86400)


def expand(query):
    if not is_zh(query):
        return query
    en = translate(query, "zh-CN|en")
    if not en:
        return query
    extra = []
    if "glp-1" in query.lower(): extra.append("GLP-1")
    if any(w in query for w in ("减肥", "肥胖", "体重")): extra += ["obesity", "weight loss"]
    if "机制" in query: extra.append("mechanism")
    if "药" in query: extra.append("drug")
    return " ".join([en] + extra)


def key_terms(q):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", (q or "").lower())
    return [w for w in words if w not in STOP][:12]


def rank_sources(sources, q):
    terms = key_terms(q)
    def score(s):
        text = ((s.get("title") or "") + " " + (s.get("snippet") or "")).lower()
        return sum(1 for t in terms if t in text) + (2 if s.get("source") in ("PubMed", "arXiv") else 0)
    return sorted(sources, key=score, reverse=True)


def best_sentences(sources, q, k=4):
    terms = set(key_terms(q))
    cand = []
    for i, s in enumerate(sources[:6]):
        for sent in _sentences(s.get("snippet", "")):
            low = sent.lower()
            if len(sent) < 45 or len(sent) > 520:
                continue
            score = len(terms & set(re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", low)))
            score += sum(1 for m in MECH if m in low)
            if "meta-analysis" in low or "systematic review" in low or "methods" in low:
                score -= 2
            cand.append((score, i, sent))
    cand.sort(key=lambda x: x[0], reverse=True)
    picked, seen = [], set()
    for _, i, sent in cand:
        if sent in seen: continue
        seen.add(sent); picked.append((i, sent))
        if len(picked) >= k: break
    return picked


def compose(query, sources, picks):
    rows = []
    for i, sent in picks:
        zh = translate(sent, "en|zh-CN") if is_zh(query) else sent
        rows.append(f"- {zh or sent} [{i+1}]")
    if not rows:
        return "没有检索到足够具体的证据。"
    return "结论：\n" + rows[0] + "\n\n关键证据：\n" + "\n".join(rows[1:] or rows[:1])


def research(query, mode="auto"):
    t0 = time.time()
    search_q = expand(query)
    sources, used = collect(search_q, mode)
    sources = rank_sources(sources, search_q)[:6]
    picks = best_sentences(sources, search_q, 4)
    trace = [{"step": "expand", "detail": search_q[:80]},
             {"step": "route", "detail": " + ".join(used) if used else "none"},
             {"step": "retrieve", "detail": f"{len(sources)} sources"}]
    if not sources:
        return {"answer": "没有检索到可用来源。可以换一个更具体的关键词，或在 DOCS 里粘贴资料。", "sources": [],
                "trace": trace, "confidence": 0.2, "engine": "none", "elapsed": round(time.time() - t0, 1),
                "search_query": search_q}
    qlow = query.lower()
    if "stackexchange" in used and any(k in qlow for k in ("python", "javascript", "asyncio", "error", "报错", "代码", "runtimeerror", "bug", "api")):
        src = sources[0]
        answer = "结论：Stack Overflow 高票/已采纳回答：\n\n" + src.get("snippet", "")[:1400] + "\n\n来源：[1] " + src.get("title", "") + " " + src.get("url", "")
        trace += [{"step": "answer", "detail": "stackoverflow top answer"}, {"step": "cite", "detail": "1 source"}]
        return {"answer": answer, "sources": sources[:3], "trace": trace, "confidence": 0.74,
                "engine": "stackoverflow", "elapsed": round(time.time() - t0, 1), "search_query": search_q}
    answer = compose(query, sources, picks)
    trace += [{"step": "extract", "detail": f"{len(picks)} evidence sentences"},
              {"step": "translate", "detail": "zh" if is_zh(query) else "en"},
              {"step": "cite", "detail": f"{len(sources)} sources"}]
    conf = 0.68 + min(0.12, 0.03 * len(sources))
    return {"answer": answer, "sources": sources, "trace": trace, "confidence": round(min(0.88, conf), 2),
            "engine": "evidence+translate", "elapsed": round(time.time() - t0, 1), "search_query": search_q}


def doc_answer(question, doc):
    t0 = time.time()
    doc = (doc or "")[:12000]
    if not doc.strip():
        return {"answer": "请先在 DOCS 里粘贴文档内容。", "sources": [], "trace": [{"step": "input", "detail": "empty"}], "confidence": 0.0, "engine": "none", "elapsed": 0.0}
    sents = _sentences(doc)
    q = _tokens(question)
    ranked = sorted(sents, key=lambda s: (len(q & _tokens(s)), len(s)), reverse=True)[:6]
    rows = [f"- {s} [D{i+1}]" for i, s in enumerate(ranked)]
    out = "根据文档，相关证据如下：\n" + "\n".join(rows)
    sources = [{"title": f"文档片段 D{i+1}", "snippet": s, "url": "", "source": "document", "year": ""} for i, s in enumerate(ranked)]
    return {"answer": out, "sources": sources, "trace": [{"step": "chunk", "detail": f"{len(sents)} sentences"},
            {"step": "rank", "detail": f"{len(ranked)} chunks"}, {"step": "extract", "detail": "document"}],
            "confidence": 0.62, "engine": "document", "elapsed": round(time.time() - t0, 1)}


_ALLOWED = {ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod,
            ast.USub, ast.UAdd, ast.Call, ast.Name, ast.Load}
_FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "log": math.log, "exp": math.exp,
          "abs": abs, "round": round, "min": min, "max": max, "pi": math.pi, "e": math.e}


def compute(query):
    expr = re.sub(r"^(请)?计算|等于多少|=\s*$", "", query).strip().strip("？?").strip()
    try:
        tree = ast.parse(expr, mode="eval")
        for node in ast.walk(tree):
            if type(node) not in _ALLOWED and not isinstance(node, ast.operator) and not isinstance(node, ast.unaryop) and not isinstance(node, ast.expr_context):
                raise ValueError("unsupported")
        val = eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}}, _FUNCS)
        return {"answer": f"{expr} = {val}", "sources": [], "trace": [{"step": "parse", "detail": expr}, {"step": "compute", "detail": "safe AST"}],
                "confidence": 0.99, "engine": "python", "elapsed": 0.0}
    except Exception as e:
        return {"answer": f"无法计算：{e}", "sources": [], "trace": [{"step": "parse", "detail": "failed"}], "confidence": 0.1, "engine": "python"}

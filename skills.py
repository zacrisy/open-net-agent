# -*- coding: utf-8 -*-
"""技能插件：节点声明自己会什么，协调者按 skill 路由。"""
import re

def _tokens(s):
    # 中英混合：英文词 + 中文二元组
    s = s.lower()
    words = re.findall(r"[a-z0-9]+", s)
    zh = re.findall(r"[\u4e00-\u9fff]", s)
    bigrams = ["".join(zh[i:i+2]) for i in range(len(zh) - 1)]
    return set(words + zh + bigrams)

def retrieval(query, ctx):
    docs = ctx.get("docs", [])
    q = _tokens(query)
    best, bs = None, 0.0
    for d in docs:
        s = len(q & _tokens(d)) / (len(q) + 1e-9)
        if s > bs: best, bs = d, s
    return {"answer": best, "score": bs, "evidence": [best] if best else []}

def echo(query, ctx):
    return {"answer": query, "score": 1.0, "evidence": []}

_NLI = None

def nli(query, ctx):
    """query 形如 'premise || hypothesis'；没有 || 时用 docs[0] 作 premise。"""
    global _NLI
    if _NLI is None:
        from transformers import pipeline
        _NLI = pipeline("text-classification", model="typeform/distilbert-base-uncased-mnli", device=-1)
    if "||" in query:
        prem, hyp = query.split("||", 1)
    else:
        prem = (ctx.get("docs") or [""])[0]; hyp = query
    r = _NLI({"text": prem.strip()[:800], "text_pair": hyp.strip()[:300]})
    lab = r["label"].upper(); sc = float(r["score"])
    score = sc if lab == "ENTAILMENT" else (-sc if lab == "CONTRADICTION" else 0.0)
    return {"answer": lab, "score": score, "evidence": [prem.strip()[:200]]}

SKILLS = {"retrieval": retrieval, "echo": echo, "nli": nli}
SKILL_META = {}


def load_plugins(base=None):
    import importlib.util, json, os
    base = base or os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")
    if not os.path.isdir(base): return SKILLS
    for name in os.listdir(base):
        d = os.path.join(base, name)
        mf = os.path.join(d, "manifest.json")
        if not os.path.isfile(mf): continue
        m = json.load(open(mf))
        hp = os.path.join(d, m.get("entry", "handler.py"))
        import hashlib
        h = hashlib.sha256(open(hp, "rb").read()).hexdigest()
        if m.get("sha256") and h != m["sha256"]:
            print(f"skip plugin {name}: sha256 mismatch", flush=True); continue
        spec = importlib.util.spec_from_file_location(f"plugin_{name}", hp)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        fn = getattr(mod, m.get("func", "handle"), None)
        if fn:
            if os.environ.get("SANDBOX") == "1":
                from sandbox import run_in_sandbox
                def wrapped(q, ctx, _hp=hp, _fn=m.get("func", "handle")):
                    return run_in_sandbox(_hp, _fn, q, ctx)
                SKILLS[m["name"]] = wrapped
            else:
                SKILLS[m["name"]] = fn
            SKILL_META[m["name"]] = {"version": m.get("version", "?"), "sha256": h[:12]}
    return SKILLS


load_plugins()

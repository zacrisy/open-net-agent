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

SKILLS = {"retrieval": retrieval, "echo": echo}

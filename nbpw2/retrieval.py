# -*- coding: utf-8 -*-
"""Small TF-IDF retriever (no sklearn)."""
import math
from collections import Counter
from .data import tokens

class Index:
    def __init__(self, docs):
        self.docs = docs
        self.N = len(docs)
        self.df = Counter()
        self.tfs = []
        for d in docs:
            ts = tokens(d["title"] + " " + d["text"])
            c = Counter(ts)
            self.tfs.append(c)
            for t in c:
                self.df[t] += 1
        self.idf = {t: math.log((self.N + 1) / (v + 1)) + 1.0 for t, v in self.df.items()}
        self.norms = []
        for c in self.tfs:
            s = sum((tf * self.idf.get(t, 1.0)) ** 2 for t, tf in c.items())
            self.norms.append(math.sqrt(s) or 1.0)

    def search(self, query, k=5):
        qt = set(tokens(query))
        if not qt:
            return []
        qnorm = math.sqrt(sum(self.idf.get(t, 1.0) ** 2 for t in qt)) or 1.0
        out = []
        for i, c in enumerate(self.tfs):
            s = sum((c.get(t, 0) * self.idf.get(t, 1.0)) for t in qt) / (self.norms[i] * qnorm)
            if s > 0:
                title_t = set(tokens(self.docs[i]["title"]))
                s += 0.35 * len(qt & title_t) / max(1, len(qt))
                out.append((s, i))
        out.sort(reverse=True)
        res = []
        for rank, (s, i) in enumerate(out[:k]):
            d = dict(self.docs[i])
            d["local_score"] = float(s)
            d["rank"] = rank
            res.append(d)
        return res

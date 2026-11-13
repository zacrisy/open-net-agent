# -*- coding: utf-8 -*-
"""Joint (pairwise / set-level) selector, fixed readout, A/B against workspace.

Rationale: second gold ranks median 3 and only 59.1% is in the shortlist, so a
per-candidate score cannot decide which two candidates belong together.  Here
candidate b is scored CONDITIONED on what is already selected:
  - bridge: does b's entity appear in a selected paragraph (HotpotQA 2nd hop)
  - coverage: query terms not yet covered
  - redundancy: overlap / duplicated extracted answer with selected items
A small logistic head is fitted on training episodes (anchor = best-ranked gold)
and used as the pairwise part of the greedy set-level score.
"""
import os, sys, json, math, random, statistics, re, types
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
NB = os.path.dirname(HERE)
if NB not in sys.path:
    sys.path.insert(0, NB)

from nbpw2.data import tokens, build_pool
from nbpw2.verifier import candidate_features, caps, Verifier, squash_rank
from nbpw2.workspace import select, _jacc

# ---------------- global idf ----------------
_IDF = None


def global_idf(pool):
    global _IDF
    if _IDF is not None:
        return _IDF
    df = {}
    for p in pool:
        for t in set(tokens(p["title"] + " " + p["text"])):
            df[t] = df.get(t, 0) + 1
    N = len(pool)
    _IDF = {t: math.log((N + 1) / (v + 1)) + 1.0 for t, v in df.items()}
    return _IDF


def _idf(t):
    return _IDF.get(t, 1.0)


def _norm_ans(a):
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", (a or "").lower()).split())


def dedupe(cands):
    best = {}
    for c in cands:
        k = c.get("title") or c.get("text", "")[:60]
        if k not in best or c.get("verifier", 0.0) > best[k].get("verifier", 0.0):
            best[k] = c
    return list(best.values())


# ---------------- pairwise features ----------------
def pair_features(anchor, c, query, selected, q_is_bridge):
    qt = set(tokens(query))
    qc = caps(query)
    a_all = caps(anchor.get("title", "") + " " + anchor.get("text", ""))
    c_all = caps(c.get("title", "") + " " + c.get("text", ""))
    a_ex, c_ex = a_all - qc, c_all - qc
    br_fwd = len(a_ex & c_ex) / max(1, len(c_ex))
    br_rev = len(a_ex & c_ex) / max(1, len(a_ex))
    br = max(br_fwd, br_rev)
    at = set(tokens(anchor.get("title", "")))
    ct = set(tokens(c.get("title", "")))
    atext = set(tokens(anchor.get("text", "")))
    ctext = set(tokens(c.get("text", "")))
    title_in_anchor = len(ct & atext) / max(1, len(ct))
    anchor_in_title = len(at & ctext) / max(1, len(at))
    nov = 1.0 - _jacc(ctext, atext)
    covered = set()
    for s in selected:
        covered |= (qt & set(tokens(s.get("text", ""))))
    cov_gain = len((qt & ctext) - covered) / max(1, len(qt))
    ca = c.get("_qa_ans") or c.get("_ans") or ""
    aa = anchor.get("_qa_ans") or anchor.get("_ans") or ""
    ans_dup = 1.0 if (ca and _norm_ans(ca) == _norm_ans(aa)) else 0.0
    # idf-weighted rare overlap (ignore query terms)
    ra = {t for t in atext if t not in qt}
    rc = {t for t in ctext if t not in qt}
    denom = sum(_idf(t) for t in rc) or 1.0
    rare = sum(_idf(t) for t in (ra & rc)) / denom
    return [
        float(c.get("verifier", 0.0)),
        float(anchor.get("verifier", 0.0)),
        br, title_in_anchor, anchor_in_title, rare,
        nov, cov_gain, ans_dup,
        1.0 if c.get("node") != anchor.get("node") else 0.0,
        squash_rank(c.get("rank", 4)) / 5.0,
        min(1.0, len(ctext) / 120.0),
        float(c.get("agreement", 0.0)),
    ], {"br": br, "rar": rare, "nov": nov, "cov": cov_gain, "dup": ans_dup}


N_BASE = 12


def _augment(phi, q_is_bridge):
    return phi + [phi[2] * q_is_bridge, phi[5] * q_is_bridge, phi[7] * q_is_bridge]


class PairHead:
    def __init__(self):
        self.v = None

    def fit(self, rows, y):
        self.v = Verifier(l2=2e-3, lr=0.1, epochs=800).fit(rows, y)
        return self

    def predict(self, rows):
        return self.v.predict(rows)


# ---------------- selection rules ----------------
def select_flat(cands, K=5):
    cs = dedupe(cands)
    out = sorted(cs, key=lambda c: c.get("verifier", 0.0), reverse=True)[:K]
    return out


def select_workspace(cands, query, K=5, n_nodes=5):
    return select(cands, query, K=K, mode="workspace", n_nodes=n_nodes)[0]


def select_pair(cands, query, K=5, head=None, q_is_bridge=0, w_pair=0.7, w_red=0.2):
    """Greedy, conditioned on the single best anchor (first hop)."""
    cs = dedupe(cands)
    if not cs:
        return []
    first = max(cs, key=lambda c: c.get("verifier", 0.0))
    selected = [first]
    pool = [c for c in cs if c is not first]
    while pool and len(selected) < K:
        anchor = selected[0]
        best, best_s = None, -1e9
        for c in pool:
            phi, _ = pair_features(anchor, c, query, selected, q_is_bridge)
            p = float(head.predict([_augment(phi, q_is_bridge)])[0]) if head else phi[2]
            red = max(_jacc(set(tokens(c.get("text", ""))), set(tokens(s.get("text", "")))) for s in selected)
            s = w_pair * p + 0.30 * phi[0] + 0.20 * phi[7] - w_red * red + 0.10 * phi[11]
            if s > best_s:
                best, best_s = c, s
        selected.append(best)
        pool.remove(best)
    return selected


def select_set(cands, query, K=5, head=None, q_is_bridge=0, w_pair=0.6, w_red=0.25):
    """Greedy set-level: bridge = max over ALL selected, plus coverage gain."""
    cs = dedupe(cands)
    if not cs:
        return []
    first = max(cs, key=lambda c: c.get("verifier", 0.0))
    selected = [first]
    pool = [c for c in cs if c is not first]
    while pool and len(selected) < K:
        best, best_s = None, -1e9
        for c in pool:
            ps = []
            for a in selected:
                phi, _ = pair_features(a, c, query, selected, q_is_bridge)
                ps.append(phi)
            # aggregate: max bridge-like signal over anchors, best pair probability
            phi_max = list(np.max(np.asarray(ps), axis=0))
            p = float(head.predict([_augment(phi_max, q_is_bridge)])[0]) if head else phi_max[2]
            red = max(_jacc(set(tokens(c.get("text", ""))), set(tokens(s.get("text", "")))) for s in selected)
            cov_gain = phi_max[7]
            s = w_pair * p + 0.30 * phi_max[0] + 0.25 * cov_gain - w_red * red + 0.10 * phi_max[11]
            if s > best_s:
                best, best_s = c, s
        selected.append(best)
        pool.remove(best)
    return selected


# ---------------- training ----------------
def fit_pair_head(episodes, n_nodes=5, sample_neg=24, seed=0):
    rng = random.Random(seed)
    X, y = [], []
    for ep in episodes:
        cands = [c for c in ep["candidates"] if c.get("verifier") is not None]
        if not cands:
            continue
        q = ep["question"]
        qbg = 1.0 if ep.get("type") == "bridge" else 0.0
        golds = [c for c in cands if c.get("is_gold")]
        if len(golds) < 2:
            continue
        golds = sorted(golds, key=lambda c: -c.get("verifier", 0.0))
        anchor = golds[0]
        pos = [g for g in golds[1:]]
        negs = [c for c in cands if not c.get("is_gold")]
        if len(negs) > sample_neg:
            negs = rng.sample(negs, sample_neg)
        for c in pos:
            phi, _ = pair_features(anchor, c, q, [anchor], qbg)
            X.append(_augment(phi, qbg)); y.append(1.0)
        for c in negs:
            phi, _ = pair_features(anchor, c, q, [anchor], qbg)
            X.append(_augment(phi, qbg)); y.append(0.0)
    return PairHead().fit(X, y), len(X), int(sum(y))


# ---------------- metrics ----------------
def metrics(selected, gold, k2=2, k5=5):
    titles = [c.get("title") for c in selected]
    s2, s5 = set(titles[:k2]), set(titles[:k5])
    rec5 = len(gold & s5) / max(1, len(gold))
    mrr = 0.0
    for i, t in enumerate(titles[:k5]):
        if t in gold:
            mrr = 1.0 / (i + 1)
            break
    return {"both@2": 1.0 if gold <= s2 else 0.0,
            "both@5": 1.0 if gold <= s5 else 0.0,
            "recall@5": rec5, "mrr": mrr,
            "second_rank": _second_rank(titles, gold)}


def _second_rank(titles, gold):
    """Rank (1-based) of the gold title that appears later; 99 if absent."""
    ranks = [i + 1 for i, t in enumerate(titles) if t in gold]
    if len(ranks) < 2:
        return 99
    return max(ranks)


def boot_ci(cluster_vals, n_boot=1000, seed=11):
    rng = random.Random(seed)
    ids = list(cluster_vals)
    vals = []
    for _ in range(n_boot):
        samp = [cluster_vals[rng.choice(ids)] for _ in ids]
        vals.append(statistics.mean(samp))
    vals.sort()
    return [round(vals[int(0.025 * n_boot)], 4), round(vals[int(0.975 * n_boot) - 1], 4)]

# -*- coding: utf-8 -*-
"""E15: multi-round active selection — query, look, decide again."""
import json, random, statistics, os
from .data import load, build_pool
from .network import train_rows, score_candidates, _metrics
from .verifier import train_verifier
from .workspace import select
from .active import ActiveEnv, gold_nodes_for

def bootstrap(diffs, n=4000, seed=7):
    rng = random.Random(seed)
    m = len(diffs)
    v = sorted(statistics.mean(diffs[rng.randrange(m)] for _ in range(m)) for _ in range(n))
    return [round(v[int(0.025 * n)], 4), round(v[int(0.975 * n)], 4)]

def next_node(env, scorer, policy, rng):
    un = [i for i in range(env.n_nodes) if i not in env.queried]
    if not un:
        return None
    if policy == "random":
        return rng.choice(un)
    if policy == "learned":
        from .node_scorer import node_features
        X = [node_features(env, i) for i in un]
        p = scorer.predict(X)
        return un[int(max(range(len(un)), key=lambda k: p[k]))]
    if policy == "greedy_stop":
        # stop as soon as we have a confident pair, else best profile gain
        from .node_scorer import node_features
        X = [node_features(env, i) for i in un]
        p = scorer.predict(X)
        return un[int(max(range(len(un)), key=lambda k: p[k]))]
    return un[0]

def satisfied(env, verifier, k=2, thresh=0.6):
    """Stop when the top-k distinct titles are confidently covered."""
    ep = {"candidates": env.candidates, "question": env.row["question"], "gold": set(), "id": env.row["id"]}
    cands = score_candidates(ep, verifier, env.n_nodes, use_agreement=False)
    best = {}
    for c in cands:
        t = c["title"]
        if t not in best or c["verifier"] > best[t]["verifier"]:
            best[t] = c
    top = sorted(best.values(), key=lambda c: c["verifier"], reverse=True)[:k]
    if len(top) < k:
        return False
    # second hop check: a confident pair is not enough if coverage is still low
    cov = 0.0
    if env.candidates:
        qt = set(__import__("nbpw2.data", fromlist=["tokens"]).tokens(env.row["question"]))
        seen = set()
        for c in top:
            seen |= (qt & set(__import__("nbpw2.data", fromlist=["tokens"]).tokens(c.get("text", ""))))
        cov = len(seen) / max(1, len(qt))
    return min(c["verifier"] for c in top) >= thresh and cov >= 0.45

def coverage(env):
    from .data import tokens
    qt = set(tokens(env.row["question"]))
    seen = set()
    for c in env.candidates:
        seen |= (qt & set(tokens(c.get("text", ""))))
    return len(seen) / max(1, len(qt))

def run(rows, pool, verifier, scorer, policy, max_budget=4, n_nodes=5, seed=0, early_stop=True,
        stop_mode="coverage", cov_target=0.6, min_queries=2, eps=0.02):
    rng = random.Random(seed)
    ms = []
    for row in rows:
        env = ActiveEnv(row, pool, n_nodes=n_nodes, gold_nodes=gold_nodes_for(row, n_nodes=n_nodes, seed=seed), scorer=scorer)
        prev_cov = 0.0
        while len(env.queried) < max_budget:
            if early_stop and len(env.queried) >= min_queries:
                if stop_mode == "coverage" and coverage(env) >= cov_target:
                    break
                if stop_mode == "marginal" and prev_cov and (coverage(env) - prev_cov) < eps:
                    break
                if stop_mode == "confident" and satisfied(env, verifier):
                    break
            nid = next_node(env, scorer, policy, rng)
            if nid is None:
                break
            prev_cov = coverage(env)
            hits = env.query(nid)
            gold_hit = any(h["title"] in env.gold for h in hits)
            env.ok[nid] = env.ok.get(nid, 1) + (1 if gold_hit else 0)
            env.fail[nid] = env.fail.get(nid, 0) + (0 if gold_hit else 1)
        m = env.finish(verifier)
        m["queries"] = len(env.queried)
        ms.append(m)
    return ms

def main():
    path = os.path.join(os.path.dirname(__file__), "data", "dmqa_1000.jsonl")
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(__file__), "data", "dmqa_dev.jsonl")
    rows = load(path); pool = build_pool(rows)
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    ver = train_verifier(train_rows(train, pool, distractors=100, top_k=5), use_agreement=False)
    from .node_scorer import collect_training
    scorer = collect_training(train[:400], pool)
    out = {}
    for policy in ["random", "learned"]:
        for stop, mode in [(False, "none"), (True, "coverage"), (True, "marginal"), (True, "confident")]:
            ms = run(test, pool, ver, scorer, policy, max_budget=4, early_stop=stop, stop_mode=mode)
            key = f"{policy},stop={mode}"
            out[key] = {k: round(statistics.mean(m[k] for m in ms), 4) for k in ("both@2", "both@5", "recall@5", "mrr", "queries")}
            out[key]["queries_p50"] = sorted(m["queries"] for m in ms)[len(ms) // 2]
            print(key, out[key])
    a = run(test, pool, ver, scorer, "learned", early_stop=True, stop_mode="coverage")
    b = run(test, pool, ver, scorer, "random", early_stop=True, stop_mode="coverage")
    d = [x["both@5"] - y["both@5"] for x, y in zip(a, b)]
    out["bootstrap_learned_minus_random"] = {"diff": round(statistics.mean(d), 4), "ci95": bootstrap(d), "n": len(d)}
    print(out["bootstrap_learned_minus_random"])
    dq = [x["queries"] - y["queries"] for x, y in zip(a, b)]
    out["queries_learned_minus_random"] = round(statistics.mean(dq), 3)
    print("queries diff", out["queries_learned_minus_random"])
    with open(os.path.join(os.path.dirname(__file__), "results", "e15_multiround.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

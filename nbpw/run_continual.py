# -*- coding: utf-8 -*-
"""NBCL experiments: acquisition, belief revision, retention/cost."""
import json, os, statistics, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import agent_core, starter_corpus
from continual import extract_cards, dedup, build_belief, make_questions, retrieve, conflict, score, trust, toks

plt.rcParams["font.sans-serif"] = ["Hiragino Sans GB", "PingFang SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
TOPICS = [("GLP-1 weight loss mechanism", ["GLP-1 obesity mechanism", "GLP-1 receptor agonist weight loss"]),
          ("AI agent evaluation", ["LLM agent evaluation benchmark", "AI agent reliability evaluation"]),
          ("Python asyncio event loop", ["asyncio event loop closed", "python asyncio runtime error"])]
QUIZ = {
    "GLP-1 weight loss mechanism": [
        ("What mechanisms explain GLP-1 weight loss?", ["appetite", "gastric", "insulin", "glucagon", "weight", "food intake"]),
        ("How does GLP-1 affect glucose and appetite?", ["glucose", "insulin", "appetite", "gastric"]),
    ],
    "AI agent evaluation": [
        ("How should AI agents be evaluated?", ["benchmark", "task", "success", "latency", "cost", "safety", "evaluation"]),
        ("What makes an agent reliable?", ["reliability", "failure", "robust", "test", "evaluation"]),
    ],
    "Python asyncio event loop": [
        ("Why does asyncio report event loop closed?", ["event loop", "closed", "run", "session", "cleanup"]),
        ("How to fix asyncio event loop errors?", ["run", "close", "session", "loop", "fix"]),
    ],
}


def load_sources():
    cache = os.path.join(HERE, "learning_sources.json")
    if os.path.exists(cache):
        return json.load(open(cache))
    out = {}
    for topic, queries in TOPICS:
        src = []
        for q in queries:
            try:
                got, used = agent_core.collect(q)
                src.extend(got)
            except Exception:
                pass
        seen, uniq = set(), []
        for s in src:
            k = (s.get("title") or "")[:80]
            if k and k not in seen:
                seen.add(k); uniq.append(s)
        out[topic] = uniq[:10]
    json.dump(out, open(cache, "w"), ensure_ascii=False, indent=1)
    return out


def static_docs():
    return [{"title": "starter", "snippet": d, "source": "starter", "url": "", "year": ""} for d in starter_corpus.DOCS]


def eval_questions(qs, docs, text_fn, cards_mode):
    ok = cite = 0
    for q in qs:
        best = retrieve(q["q"], docs, text_fn)
        if best is None: continue
        text = text_fn(best).lower()
        if q["answer"].lower() in text: ok += 1
        if cards_mode and best.get("source", {}).get("url") == q["source"].get("url"): cite += 1
    return {"success": ok / len(qs), "citation": cite / len(qs), "n": len(qs)}


def main():
    raw = load_sources()
    all_cards = []
    for topic, sources in raw.items():
        all_cards.extend(extract_cards(topic, sources))
    all_cards = dedup(all_cards)
    build_belief(all_cards)
    active = [c for c in all_cards if c["status"] == "active"]
    qs = make_questions(active, 4)
    starter = static_docs()
    res = {}
    res["static"] = eval_questions(qs, starter, lambda d: d["snippet"] + " " + d["title"], False)
    res["memory"] = eval_questions(qs, all_cards, lambda d: d["claim"] + " " + d["evidence"], True)
    res["nbcl"] = eval_questions(qs, active, lambda d: d["claim"] + " " + d["evidence"], True)
    # E2 synthetic belief revision
    pairs, naive_ok, nbcl_ok = [], 0, 0
    for i in range(12):
        a = {"id": f"a{i}", "topic": "synthetic", "claim": f"Drug X increases appetite in cohort {i}.", "evidence": "", "source": {"source": "Hacker News", "url": "a", "year": "2026"}, "confidence": .7, "status": "active", "support": 1}
        b = {"id": f"b{i}", "topic": "synthetic", "claim": f"Drug X does not increase appetite in cohort {i}.", "evidence": "", "source": {"source": "PubMed", "url": "b", "year": "2026"}, "confidence": .7, "status": "active", "support": 1}
        cards = build_belief([a, b]); active_b = [c for c in cards if c["status"] == "active"]
        nbcl_ok += int(len(active_b) == 1 and active_b[0]["id"] == b["id"])
        # append-only baseline: first write wins, no belief revision
        naive_ok += int(cards[0]["id"] == b["id"])
        pairs.append({"nbcl": active_b[0]["id"] if active_b else None})
    res["belief"] = {"nbcl": nbcl_ok / 12, "naive": naive_ok / 12}
    # concept quiz (not masked retrieval)
    def concept(docs, text_fn, k=3):
        total = ok = 0
        for topic, qs in QUIZ.items():
            for q, kws in qs:
                qt = toks(q)
                ranked = sorted(docs, key=lambda d: len(qt & toks(text_fn(d))) / (len(toks(text_fn(d))) ** .5 + 1), reverse=True)[:k]
                text = " ".join(text_fn(d) for d in ranked).lower()
                ok += int(sum(1 for x in kws if x in text) >= 2)
                total += 1
        return {"success": ok / max(1, total), "n": total}
    res["concept_static"] = concept(starter, lambda d: d["snippet"] + " " + d["title"])
    res["concept_memory"] = concept(all_cards, lambda d: d["claim"] + " " + d["evidence"])
    res["concept_nbcl"] = concept(active, lambda d: d["claim"] + " " + d["evidence"])
    # pruning / consolidation ablation
    res["prune"] = []
    for th in (0.0, 0.50, 0.55, 0.60, 0.65):
        sub = [c for c in active if c["confidence"] >= th]
        if not sub: continue
        cq = concept(sub, lambda d: d["claim"] + " " + d["evidence"])
        mq = eval_questions(qs, sub, lambda d: d["claim"] + " " + d["evidence"], True)
        res["prune"].append({"threshold": th, "cards": len(sub), "concept": cq["success"], "masked": mq["success"]})
    # save cards for inspection
    json.dump(all_cards, open(os.path.join(HERE, "continual_cards.json"), "w"), ensure_ascii=False, indent=1)
    # E3 retention: split topics, learn A, evaluate A, then add all
    first = [q for q in qs if q["topic"] == TOPICS[0][0]]
    first_cards = [c for c in active if c["topic"] == TOPICS[0][0]]
    res["retention"] = {"before": eval_questions(first, first_cards, lambda d: d["claim"] + " " + d["evidence"], True)}
    res["retention"]["after"] = eval_questions(first, active, lambda d: d["claim"] + " " + d["evidence"], True)
    # cost
    res["cost"] = {"cards": len(all_cards), "active": len(active), "disputed": len(all_cards) - len(active),
                   "questions": len(qs), "bytes_cards": sum(len(c["claim"]) for c in all_cards),
                   "sources": sum(len(v) for v in raw.values())}
    json.dump(res, open(os.path.join(HERE, "continual_results.json"), "w"), ensure_ascii=False, indent=1)
    # figures
    import numpy as np
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    names = ["static", "memory", "nbcl"]
    masked = [res[n]["success"] for n in names]
    concept = [res[n.replace("concept_", "")] if False else res["concept_" + n]["success"] for n in names]
    x = np.arange(len(names)); w = .36
    ax.bar(x - w/2, masked, w, label="masked evidence", color="#16a085")
    ax.bar(x + w/2, concept, w, label="concept question", color="#e67e22")
    ax.set_xticks(x); ax.set_xticklabels(names); ax.set_ylim(0, 1.08)
    ax.set_ylabel("success"); ax.set_title("Knowledge acquisition: evidence vs concept")
    for i, v in enumerate(masked): ax.text(i - w/2, v + .02, f"{v:.2f}", ha="center", fontsize=8)
    for i, v in enumerate(concept): ax.text(i + w/2, v + .02, f"{v:.2f}", ha="center", fontsize=8)
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(HERE, "figs", "learning_acquisition.png")); plt.close(fig)
    fig, ax = plt.subplots(figsize=(6, 4.5), dpi=150)
    ax.bar(["append-only", "NBCL"], [res["belief"]["naive"], res["belief"]["nbcl"]], color=["#e67e22", "#16a085"])
    ax.set_ylim(0, 1); ax.set_ylabel("correct active belief"); ax.set_title("Belief revision under contradiction")
    for i, v in enumerate([res["belief"]["naive"], res["belief"]["nbcl"]]): ax.text(i, v + .03, f"{v:.2f}", ha="center")
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "figs", "belief_revision.png")); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    ax.plot([p["cards"] for p in res["prune"]], [p["concept"] for p in res["prune"]], "o-", color="#16a085")
    for p in res["prune"]:
        ax.annotate(f"θ={p['threshold']}", (p["cards"], p["concept"]), textcoords="offset points", xytext=(5, 4), fontsize=8)
    ax.set_xlabel("cards kept"); ax.set_ylabel("concept question success")
    ax.set_title("Confidence pruning: fewer cards, better focus?")
    ax.grid(alpha=.25); fig.tight_layout()
    fig.savefig(os.path.join(HERE, "figs", "pruning.png")); plt.close(fig)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

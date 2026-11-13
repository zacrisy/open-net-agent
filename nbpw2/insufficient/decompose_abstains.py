#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Break the 49 abstained test questions into (a) out-of-coverage,
(b) retrieval/extraction failure, (c) gate false kill.

Uses the unmodified pool and the shipped D1 chain.  The gate is exactly the
one proposed for the default: empty span OR answer not grounded.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nbpw2.data import build_pool, load, tokens  # noqa: E402
from nbpw2.insufficient.analyze_abstain import _correct  # noqa: E402
from nbpw2.insufficient.run_cases import BASE_ASSET, BASE_DATA, _metrics  # noqa: E402


def _norm(s):
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).split())


def _classify(rec):
    gold = rec["gold"]
    sel_titles = {t.lower() for t in rec["selected_titles"]}
    recall_titles = {t.lower() for t in rec["recall_titles"]}
    support = {t.lower() for t in rec["support_titles"]}
    gold_norm = _norm(gold)
    selected_norm = _norm(rec["selected_full_text"])
    support_norm = _norm(rec["support_full_text"])
    yesno = gold_norm in ("yes", "no")

    if rec["correct"] and rec["gate"]:
        return "c_false_kill", "抽取正确但被 gate 拦下"
    if support & sel_titles:
        if yesno:
            return ("b3_yesno_not_extractive",
                    "答案是 yes/no，抽取式读出不支持该答案形式")
        if gold_norm and gold_norm in selected_norm:
            if rec["qtype"] not in ("number", "date", "person", "place", "entity"):
                return ("b1a_answer_present_reader_no_branch",
                        "gold 答案在选中段落全文里，但问句被判为 other，读出不产生 span")
            return ("b1b_answer_present_span_wrong",
                    "gold 答案在选中段落全文里，读出却给了空 span 或错误跨度")
        if gold_norm and gold_norm in support_norm:
            return ("b2_answer_in_support_not_selected",
                    "gold 答案在支撑段全文里，但没有进入读出候选文本")
        return ("b4_answer_not_literal_in_support",
                "支撑段已选中，但 gold 答案不是段内字面串（需要推断/改写）")
    if support & recall_titles:
        return ("b5_support_in_recall_not_selected",
                "gold 支撑段进了节点 recall top-10，但 selector/verifier 没选")
    if rec["support_in_pool"]:
        return ("b6_support_in_pool_not_retrieved",
                "gold 支撑段在 pool 中，但路由或节点内深度没召回")
    return "a_out_of_coverage", "gold 支撑段不在 pool（本题超出语料覆盖）"


def main():
    rows = load(str(BASE_DATA))
    test = [r for r in rows if r["split"] == "test" and len(r["question"]) <= 180]
    pool = build_pool(rows)
    pool_titles = {p["title"] for p in pool}
    title_text = {}
    for p in pool:
        title_text.setdefault(p["title"], []).append(p["text"])

    def _full(titles):
        return " ".join(" ".join(title_text.get(t, [])) for t in titles)

    from nbpw2 import online_ask
    online_ask.ASSET = str(BASE_ASSET)
    online_ask._E = None
    online_ask.STATE.update(
        {"ready": False, "loading": False, "error": None, "load_ms": None})
    online_ask.load()

    out = []
    for r in test:
        raw = online_ask.ask(r["question"])
        m = _metrics(raw, pool)
        support_titles = [s.get("title", "") for s in r.get("support") or []]
        # Use the production three-state verdict, not a re-implementation of
        # the gate: the shipped reader grounds on the full paragraph text.
        if m["status"] != "insufficient":
            continue
        grounded = bool((raw.get("answer") or {}).get("grounded"))
        old_span = m["rejected_span"] or m["answer_span"]
        has_span = bool(old_span)
        recall_titles = []
        for node in raw.get("recall") or []:
            for h in node.get("hits") or []:
                recall_titles.append(h.get("title", ""))
        rec = {
            "id": r["id"],
            "question": r["question"],
            "gold": r["answer"],
            "support_titles": support_titles,
            "support_in_pool": any(t in pool_titles for t in support_titles),
            "qtype": m["answer_qtype"],
            "status": m["status"],
            "span": old_span,
            "sentence": m["answer_sentence"] or (raw.get("answer") or {}).get("rejected", {}).get("sentence", ""),
            "source_title": m["answer_source_title"],
            "source_node": m["answer_source_node"],
            "correct": _correct(old_span, r["answer"]),
            "grounded": grounded,
            "gate": True,
            "selected_titles": m["selected_titles"],
            "selected_nodes": m["selected_nodes"],
            "recall_titles": recall_titles,
            "support_full_text": _full(support_titles),
            "selected_full_text": _full(m["selected_titles"]),
            "route_nodes": m["route_nodes"],
            "route_margin": m["route_hop1_margin"],
            "verifier_max": m["selected_verifier_max"],
            "coverage": m["answer_coverage"],
        }
        rec["class"], rec["class_reason"] = _classify(rec)
        rec["selected_excerpt"] = rec.pop("selected_full_text")[:600]
        rec["support_excerpt"] = rec.pop("support_full_text")[:400]
        out.append(rec)
        print("%-26s %-4s %-38s gold=%r span=%r" % (
            rec["id"][:26], rec["qtype"], rec["class"], rec["gold"],
            rec["span"]), flush=True)

    counts = {}
    for rec in out:
        counts[rec["class"]] = counts.get(rec["class"], 0) + 1
    report = {
        "gate": "production status == insufficient",
        "n_questions": len(test),
        "n_abstained": len(out),
        "counts": counts,
        "records": out,
    }
    path = ROOT / "nbpw2" / "results" / "abstain_decomposition.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(json.dumps({"n_abstained": len(out), "counts": counts},
                     ensure_ascii=False, indent=2))
    print("wrote", path)


if __name__ == "__main__":
    main()

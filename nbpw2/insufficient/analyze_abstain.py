#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure the shipped three-state chain on the dmqa_dev test questions.

Runs the deployed D1 chain locally over the unmodified pool and reports the
numbers the three-state default actually produces:

  * abstain rate (insufficient / total) and conflict rate
  * accuracy on the answered subset
  * accuracy over the whole test set
  * how many questions that used to emit a span were downgraded to
    insufficient

The single-threshold gates (coverage / focus / verifier / route top1) are kept
only as a rejected comparison: they throw away correct answers.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nbpw2.data import build_pool, load  # noqa: E402
from nbpw2.insufficient.run_cases import BASE_ASSET, BASE_DATA, _metrics  # noqa: E402


def _norm(s):
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).split())


def _correct(span, gold):
    if not span:
        return False
    s, g = _norm(span), _norm(gold)
    if not g:
        return False
    if g in s or s in g:
        return True
    ds, dg = re.sub(r"\D", "", s), re.sub(r"\D", "", g)
    return bool(dg) and ds == dg


def _gate_rows(records, cases):
    gates = {
        "span_only": lambda r: not r["has_span"],
        "span_or_ungrounded": lambda r: (not r["has_span"]) or (not r["grounded"]),
        "coverage<0.20": lambda r: (r["coverage"] or 0.0) < 0.20,
        "coverage<0.30": lambda r: (r["coverage"] or 0.0) < 0.30,
        "focus_coverage<0.30": lambda r: (r["focus_coverage"] or 0.0) < 0.30,
        "verifier_max<0.70": lambda r: (r["verifier_max"] or 0.0) < 0.70,
        "verifier_max<0.90": lambda r: (r["verifier_max"] or 0.0) < 0.90,
        "route_top1<0.60": lambda r: (r["route_top1"] or 0.0) < 0.60,
        "route_top1<0.65": lambda r: (r["route_top1"] or 0.0) < 0.65,
        "route_margin<0.02": lambda r: (r["route_margin"] if r["route_margin"] is not None else 1.0) < 0.02,
        "combined": lambda r: (
            (not r["has_span"]) or (not r["grounded"])
            or ((r["route_margin"] if r["route_margin"] is not None else 1.0) < 0.02)
        ),
    }
    n = len(records)
    correct_n = sum(1 for r in records if r["correct"])
    out = {}
    for name, fn in gates.items():
        abstained = [r for r in records if fn(r)]
        correct_abstained = [r for r in abstained if r["correct"]]
        kept = [r for r in records if not fn(r)]
        correct_kept = [r for r in kept if r["correct"]]
        out[name] = {
            "abstained": len(abstained),
            "abstain_rate": round(len(abstained) / n, 3) if n else None,
            "false_abstain_correct": len(correct_abstained),
            "false_abstain_rate_of_correct": round(
                len(correct_abstained) / correct_n, 3) if correct_n else None,
            "abstained_incorrect": len(abstained) - len(correct_abstained),
            "kept": len(kept),
            "accuracy_on_kept": round(
                len(correct_kept) / len(kept), 3) if kept else None,
        }

    # Apply the same gates to the insufficient-evidence cases.
    case_rows = {}
    for c in cases:
        m = c["metrics"]
        r = {
            "has_span": bool(m.get("answer_span")),
            "grounded": bool(m.get("grounded")),
            "coverage": m.get("answer_coverage"),
            "focus_coverage": m.get("answer_focus_coverage"),
            "verifier_max": m.get("selected_verifier_max"),
            "route_top1": m.get("route_hop1_top1_cos"),
            "route_margin": m.get("route_hop1_margin"),
        }
        case_rows[c["id"]] = {
            "verdict": c["verdict"],
            "gates": {name: bool(fn(r)) for name, fn in gates.items()},
        }
    return out, case_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "nbpw2" / "results" /
                                         "abstain_analysis.json"))
    args = ap.parse_args()

    rows = load(str(BASE_DATA))
    test_all = [r for r in rows if r["split"] == "test"]
    # The live endpoint rejects questions longer than 180 chars, so those are
    # outside the analyzed input domain.
    test = [r for r in test_all if len(r["question"]) <= 180]
    skipped_long = len(test_all) - len(test)
    pool = build_pool(rows)

    from nbpw2 import online_ask
    os.environ.pop("NBPW2_DATA", None)
    online_ask.ASSET = str(BASE_ASSET)
    online_ask._E = None
    online_ask.STATE.update(
        {"ready": False, "loading": False, "error": None, "load_ms": None})
    online_ask.load()

    records = []
    for i, r in enumerate(test, 1):
        raw = online_ask.ask(r["question"])
        m = _metrics(raw, pool)
        ans = raw.get("answer") or {}
        status = raw.get("status") or ans.get("status")
        rej = ans.get("rejected") or {}
        old_span = (rej.get("span") or "").strip() or m["answer_span"]
        records.append({
            "id": r["id"],
            "type": r.get("type"),
            "status": status,
            "has_span": bool(old_span),
            "old_span": old_span,
            "old_correct": _correct(old_span, r["answer"]),
            "grounded": bool(ans.get("grounded")),
            "correct": status == "answered" and _correct(
                m["answer_span"], r["answer"]),
            "gold": r["answer"],
            "span": m["answer_span"],
            "source": m["answer_source_title"],
            "coverage": m["answer_coverage"],
            "focus_coverage": m["answer_focus_coverage"],
            "verifier_max": m["selected_verifier_max"],
            "route_top1": m["route_hop1_top1_cos"],
            "route_margin": m["route_hop1_margin"],
        })
        if i % 20 == 0:
            print("ran", i, flush=True)

    cases = json.loads((ROOT / "nbpw2" / "results" /
                        "insufficient_cases.json").read_text(encoding="utf-8"))
    gates, case_rows = _gate_rows(records, cases["results"])
    n = len(records)

    statuses = {}
    for r in records:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1

    answered = [r for r in records if r["status"] == "answered"]
    correct_answered = [r for r in answered if r["correct"]]
    correct_all = [r for r in records if r["correct"]]

    # Questions that used to produce a span but are no longer answered.
    downgraded = [r for r in records
                  if r["has_span"] and r["status"] != "answered"
                  and r["status"] == "insufficient"]
    downgraded_correct = [r for r in downgraded if r["old_correct"]]

    out = {
        "n_test": n,
        "skipped_long_questions": skipped_long,
        "status_counts": statuses,
        "three_state": {
            "abstained": statuses.get("insufficient", 0),
            "abstain_rate": round(statuses.get("insufficient", 0) / n, 3),
            "conflict": statuses.get("conflict", 0),
            "conflict_rate": round(statuses.get("conflict", 0) / n, 3),
            "answered": len(answered),
            "correct_on_answered": len(correct_answered),
            "accuracy_on_answered": round(
                len(correct_answered) / len(answered), 3) if answered else None,
            "correct_overall": len(correct_all),
            "accuracy_overall": round(len(correct_all) / n, 3),
        },
        "old_chain": {
            "has_span": sum(r["has_span"] for r in records),
            "correct": sum(r["old_correct"] for r in records),
            "correct_rate": round(
                sum(r["old_correct"] for r in records) / n, 3),
        },
        "downgraded": {
            "count": len(downgraded),
            "of_span_questions": round(
                len(downgraded) / sum(r["has_span"] for r in records), 3)
            if sum(r["has_span"] for r in records) else None,
            "was_correct": len(downgraded_correct),
            "was_correct_ids": [r["id"] for r in downgraded_correct],
            "ids": [r["id"] for r in downgraded],
        },
        "rejected_gates": gates,
        "case_gate_matrix": case_rows,
        "records": records,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", args.out)
    print(json.dumps({"status_counts": statuses,
                      "three_state": out["three_state"],
                      "old_chain": out["old_chain"],
                      "downgraded": {k: v for k, v in out["downgraded"].items()
                                     if k != "ids"}},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

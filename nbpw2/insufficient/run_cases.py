#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the insufficient-evidence cases through the real D1 chain.

Two execution modes, both use the shipped chain unchanged (k=10, D1, B=2, K=5):

  vps      POST /public/brain/ask on the deployed backend.
  derived  rebuild the pool after the case's edit, then call online_ask.ask
           locally.  This is required because the deployed service only has
           the unmodified dmqa_dev pool; it cannot accept an arbitrary pool.

The derived data/asset files are written to a temp directory and deleted.
Only the case questions and the public corpus paragraphs are written to the
results file; no visitor question is involved.

Usage:
  python3 nbpw2/insufficient/run_cases.py
  python3 nbpw2/insufficient/run_cases.py --only cf_bratislava_population
"""
import argparse
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nbpw2.data import build_pool, load  # noqa: E402
from nbpw2 import dense as D  # noqa: E402
from nbpw2.insufficient.grounding import is_grounded  # noqa: E402

BASE_DATA = ROOT / "nbpw2" / "data" / "dmqa_dev.jsonl"
BASE_ASSET = ROOT / "nbpw2" / "results" / "bge_pool_nodes.npz"
VPS = "https://106-14-46-145.sslip.io"

REFUSAL = (
    "cannot", "can't", "not enough", "insufficient", "unable", "no evidence",
    "not supported", "unknown", "无法", "证据不足", "不足以", "没有足够",
    "不能确定", "无法确定", "缺乏",
)


def _key(p):
    return (p["title"], p["text"])


def _build_derived(case, outdir):
    """Return (data_path, asset_path, pool) for a modified pool."""
    rows = load(str(BASE_DATA))
    mod = case["source"]["modification"]
    overrides = {}
    if mod == "remove_paragraph":
        rem = case["source"]["removed"]
        for r in rows:
            r["paragraphs"] = [p for p in r["paragraphs"] if _key(p) != _key(rem)]
    elif mod == "inject_conflicting_paragraph":
        d = case["source"]["derived"]
        row = next(r for r in rows if r["id"] == case["source"]["question_id"])
        row["paragraphs"].append({"title": d["title"], "text": d["text"]})
        overrides[_key(d)] = int(d["node"])
    else:
        raise ValueError("unsupported modification: %s" % mod)

    data_path = outdir / "dmqa.jsonl"
    with open(data_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    base_pool = build_pool(load(str(BASE_DATA)))
    z = np.load(BASE_ASSET)
    base_e, base_assign = z["e"], z["assign"].tolist()
    base_idx = {_key(p): i for i, p in enumerate(base_pool)}
    new_pool = build_pool(rows)

    e_rows, assign = [], []
    for p in new_pool:
        k = _key(p)
        if k in base_idx:
            i = base_idx[k]
            e_rows.append(base_e[i])
            assign.append(base_assign[i])
        else:
            e_rows.append(D.encode([D._doc_text(p)])[0].astype(np.float32))
            assign.append(overrides[k])
    asset_path = outdir / "asset.npz"
    np.savez_compressed(
        asset_path, e=np.stack(e_rows).astype(np.float32),
        assign=np.array(assign, dtype=np.int8))
    return data_path, asset_path, new_pool


def _ask_local(data_path, asset_path, question):
    from nbpw2 import online_ask, selector_lib
    os.environ["NBPW2_DATA"] = str(data_path)
    online_ask.ASSET = str(asset_path)
    online_ask._E = None
    online_ask.STATE.update(
        {"ready": False, "loading": False, "error": None, "load_ms": None})
    # These caches are module-global; clear them so the next pool is clean.
    selector_lib._IDF = None
    return online_ask.ask(question)


def _ask_vps(question, timeout=45):
    body = json.dumps({"question": question}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        VPS + "/public/brain/ask", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _metrics(raw, pool):
    ans = raw.get("answer") or {}
    span = (ans.get("span") or "").strip()
    sent = (ans.get("sentence") or "").strip()
    selected = raw.get("selected") or []
    titles = [s.get("title", "") for s in selected]
    nodes = sorted({int(s.get("node", -1)) for s in selected})
    route = raw.get("route") or []

    hop1 = route[0] if route else {}
    scores = hop1.get("scores") or []
    top_cos = float(scores[0]["max_cos"]) if scores else None
    second_cos = float(scores[1]["max_cos"]) if len(scores) > 1 else None
    margin = round(top_cos - second_cos, 4) if (
        top_cos is not None and second_cos is not None) else None

    source_title, source_node, source_snippet = None, None, ""
    for s in selected:
        if span and span.lower() in (s.get("snippet") or "").lower():
            source_title, source_node = s.get("title"), s.get("node")
            source_snippet = s.get("snippet") or ""
            break
    if source_title is None and span:
        for s in selected:
            for p in pool:
                if p["title"] == s.get("title") and span.lower() in p["text"].lower():
                    source_title, source_node = s.get("title"), s.get("node")
                    source_snippet = s.get("snippet") or ""
                    break
            if source_title is not None:
                break

    selected_text = " ".join(s.get("snippet") or "" for s in selected)
    verifiers = [float(s["verifier"]) for s in selected if "verifier" in s]

    return {
        "route_nodes": [int(h.get("chosen", -1)) for h in route],
        "route_hop1_scores": [
            {"node": s.get("node"), "max_cos": s.get("max_cos"),
             "best_title": s.get("best_title")} for s in scores],
        "route_hop1_top1_cos": top_cos,
        "route_hop1_margin": margin,
        "candidate_count": sum(len(r.get("hits", [])) for r in raw.get("recall", [])),
        "selected_count": len(selected),
        "selected_titles": titles,
        "selected_nodes": nodes,
        "selected_verifier_max": round(max(verifiers), 4) if verifiers else None,
        "selected_verifier_mean": round(sum(verifiers) / len(verifiers), 4)
        if verifiers else None,
        "answer_span": span,
        "answer_sentence": sent,
        "answer_cite": ans.get("cite"),
        "answer_qtype": ans.get("qtype"),
        "answer_coverage": ans.get("coverage"),
        "answer_focus_coverage": ans.get("focus_coverage"),
        "answer_bridge_paragraph": ans.get("bridge_paragraph"),
        "answer_in_corpus": bool(span) and any(
            span.lower() in p["text"].lower() for p in pool),
        "answer_source_title": source_title,
        "answer_source_node": source_node,
        "answer_source_snippet": source_snippet,
        "selected_text": selected_text,
        "latency_ms": raw.get("latency", {}).get("total_ms"),
        "latency": raw.get("latency"),
    }


def _judge(case, m):
    exp = case["expected_behavior"]
    span = m["answer_span"]
    sent = m["answer_sentence"]
    text = (span + " " + sent).lower()
    refusal = any(k in text for k in REFUSAL)

    if exp == "answer":
        ok = case.get("expected_answer", "").lower() in span.lower()
        return "correct" if ok else "wrong"

    if exp == "expose_conflict":
        values = case["source"]["verification"]["conflict_values"]
        both_selected = all(m["selected_text_has_values"].get(v, False) for v in values)
        both_in_answer = all(v in (span + " " + sent) for v in values)
        if both_selected and both_in_answer:
            return "exposed_conflict"
        if both_selected:
            return "picked_one_side"
        return "missed_conflict"

    if refusal:
        return "honest_refusal"
    if not span:
        return "vague_no_answer"
    return "fabricated"


def _fabrication_note(case, m):
    if m["answer_span"] == "":
        return None
    return {
        "answer_span": m["answer_span"],
        "source_title": m["answer_source_title"],
        "source_node": m["answer_source_node"],
        "why": (
            "答案跨度来自《%s》（节点 %s）；该段并没有回答题目所问的关系。"
            % (m["answer_source_title"], m["answer_source_node"])
            if m["answer_source_title"] else
            "答案跨度在选中段落中找不到明确来源。"
        ),
        "answer_in_corpus": m["answer_in_corpus"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=str(Path(__file__).with_name("cases.json")))
    ap.add_argument("--out", default=str(ROOT / "nbpw2" / "results" /
                                        "insufficient_cases.json"))
    ap.add_argument("--only", default=None)
    ap.add_argument("--vps-timeout", type=int, default=45)
    args = ap.parse_args()

    spec = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    cases = spec["cases"]
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]
        if not cases:
            raise SystemExit("no such case: %s" % args.only)

    results = []
    with tempfile.TemporaryDirectory(prefix="nbpw2-insufficient-") as td:
        for case in cases:
            mode = case["run_mode"]
            t0 = time.time()
            pool = build_pool(load(str(BASE_DATA)))
            note = None
            if mode == "vps":
                raw = _ask_vps(case["question"], timeout=args.vps_timeout)
                time.sleep(0.6)
            elif mode == "derived":
                outdir = Path(td) / case["id"]
                outdir.mkdir(parents=True, exist_ok=True)
                data_path, asset_path, pool = _build_derived(case, outdir)
                raw = _ask_local(data_path, asset_path, case["question"])
            else:
                raise SystemExit("unknown run_mode: %s" % mode)

            m = _metrics(raw, pool)
            values = case.get("source", {}).get("verification", {}).get(
                "conflict_values", [])
            m["selected_text_has_values"] = {
                v: (v in m["selected_text"]) for v in values
            }
            m["grounded"] = is_grounded(
                case["question"], raw.get("selected") or [],
                m["answer_source_title"], m["answer_source_snippet"])
            verdict = _judge(case, m)
            results.append({
                "id": case["id"],
                "category": case["category"],
                "title": case["title"],
                "expected_behavior": case["expected_behavior"],
                "expected_behavior_text": case["expected_behavior_text"],
                "question": case["question"],
                "run_mode": mode,
                "verdict": verdict,
                "metrics": m,
                "fabrication": _fabrication_note(case, m)
                if verdict == "fabricated" else None,
                "raw": raw,
                "wall_ms": round((time.time() - t0) * 1000, 1),
            })
            print("%-28s %-22s %-18s total=%sms span=%r" % (
                case["id"], case["category"], verdict,
                m.get("latency_ms"), m.get("answer_span")), flush=True)

    summary = {
        "cases": len(results),
        "verdicts": {},
        "fabricated": [],
        "honest_refusals": [],
        "conflict_failures": [],
    }
    for r in results:
        summary["verdicts"][r["verdict"]] = summary["verdicts"].get(
            r["verdict"], 0) + 1
        if r["verdict"] == "fabricated":
            summary["fabricated"].append(r["id"])
        if r["verdict"] == "honest_refusal":
            summary["honest_refusals"].append(r["id"])
        if r["verdict"] in ("picked_one_side", "missed_conflict"):
            summary["conflict_failures"].append(r["id"])

    out = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": spec["dataset"],
        "backend": {"vps": VPS, "local": "nbpw2.online_ask.ask (derived pools)"},
        "defaults": {"recall_k": 10, "routing": "D1", "B": 2, "K": 5},
        "summary": summary,
        "results": results,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", args.out)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

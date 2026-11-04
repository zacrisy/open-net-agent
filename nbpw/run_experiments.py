# -*- coding: utf-8 -*-
"""Run NBPW preliminary experiments and write figures/results."""
import json, math, os, random, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from sim import run

HERE = os.path.dirname(os.path.abspath(__file__))
plt.rcParams["font.sans-serif"] = ["Hiragino Sans GB", "PingFang SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
POLICIES = ["random", "ucb", "moe", "nbpw"]
COLORS = {"random": "#95a5a6", "ucb": "#e67e22", "moe": "#8e44ad", "nbpw": "#16a085"}


def e1():
    seeds = range(5)
    agg = {p: [] for p in POLICIES}
    for s in seeds:
        for p in POLICIES:
            agg[p].append(run(p, seed=s))
    summary = {}
    for p in POLICIES:
        rows = agg[p]
        summary[p] = {
            "success": statistics.mean(r["success"] for r in rows),
            "p50": statistics.mean(r["p50"] for r in rows),
            "p95": statistics.mean(r["p95"] for r in rows),
            "p99": statistics.mean(r["p99"] for r in rows),
            "bytes": statistics.mean(r["bytes"] for r in rows),
            "windows": [statistics.mean(r["windows"][i] for r in rows) for i in range(len(rows[0]["windows"]))],
        }
    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    for p in POLICIES:
        ax.plot(summary[p]["windows"], label=p, color=COLORS[p], lw=2)
    ax.set_xlabel("query window (50 queries)")
    ax.set_ylabel("success rate")
    ax.set_title("Routing under heterogeneous nodes + 20% mid-run failure")
    ax.grid(alpha=.25); ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(HERE, "figs", "routing_learning.png")); plt.close(fig)
    return summary


def predictive(theta, rho=.92, dim=16, T=2000, seed=0):
    rng = random.Random(seed)
    x = [rng.gauss(0, 1) for _ in range(dim)]
    sent, err, n_sent = 0, 0.0, 0
    for t in range(T):
        prev = x[:]
        x = [rho * v + rng.gauss(0, .35) for v in prev]
        xhat = [rho * v for v in prev]  # one-step predictor from previous state
        res = [a - b for a, b in zip(x, xhat)]
        norm = math.sqrt(sum(v * v for v in res))
        if norm > theta:
            # send raw (4 bytes/value); receiver gets x
            sent += dim * 4; n_sent += 1
            rec = x
        else:
            rec = xhat
        err += sum((a - b) ** 2 for a, b in zip(x, rec)) / dim
    return {"theta": theta, "bytes_per_step": sent / T, "mse": err / T, "send_rate": n_sent / T}


def e1k():
    out = []
    for k in (1, 2, 3, 5):
        rows = [run("nbpw", seed=s, k=k) for s in range(5)]
        out.append({"k": k, "success": statistics.mean(r["success"] for r in rows),
                    "bytes": statistics.mean(r["bytes"] for r in rows),
                    "p95": statistics.mean(r["p95"] for r in rows)})
    fig, ax = plt.subplots(figsize=(7, 5), dpi=150)
    ax.plot([r["bytes"] for r in out], [r["success"] for r in out], "o-", color="#16a085")
    for r in out:
        ax.annotate(f"k={r['k']}", (r["bytes"], r["success"]), textcoords="offset points", xytext=(6, 5))
    ax.set_xlabel("bytes / query"); ax.set_ylabel("success rate")
    ax.set_title("Workspace size vs communication cost")
    ax.grid(alpha=.25); fig.tight_layout()
    fig.savefig(os.path.join(HERE, "figs", "workspace_tradeoff.png")); plt.close(fig)
    return out


def e2():
    rows = [predictive(th) for th in [0.01, 0.1, 0.25, 0.5, 0.8, 1.2, 1.8, 2.5]]
    fig, ax = plt.subplots(figsize=(7, 5), dpi=150)
    ax.plot([r["bytes_per_step"] for r in rows], [r["mse"] for r in rows], "o-", color="#16a085")
    for r in rows:
        if r["theta"] not in (2.5, 1.8, 1.2):
            continue
        off = (6, 5) if r["theta"] != 1.2 else (-44, 8)
        ax.annotate(f"θ={r['theta']}", (r["bytes_per_step"], r["mse"]), fontsize=8,
                    textcoords="offset points", xytext=off)
    ax.axhline(0.1225, color="#95a5a6", ls="--", lw=1, label="send none (MSE≈0.1225)")
    ax.legend(fontsize=7)
    ax.set_xlabel("bytes per step"); ax.set_ylabel("reconstruction MSE")
    ax.set_title("Predictive coding: send surprise, not raw signal")
    ax.grid(alpha=.25); fig.tight_layout()
    fig.savefig(os.path.join(HERE, "figs", "predictive_compression.png")); plt.close(fig)
    return rows


def workspace(k, corr, trials=3000, seed=0):
    rng = random.Random(seed)
    qs = [rng.uniform(.55, .90) for _ in range(20)]
    correct = 0
    for _ in range(trials):
        common = rng.random() < corr
        answers = []
        for q in qs[:k]:
            if common and rng.random() < .3:
                answers.append(False)
            else:
                answers.append(rng.random() < q)
        correct += sum(answers) > k / 2
    return {"k": k, "corr": corr, "accuracy": correct / trials}


def e3():
    rows = [workspace(k, c) for c in (.0, .2) for k in (1, 3, 5, 7, 9, 11)]
    fig, ax = plt.subplots(figsize=(7, 5), dpi=150)
    for c, color in [(.0, "#16a085"), (.2, "#c0392b")]:
        xs = [r["k"] for r in rows if r["corr"] == c]
        ys = [r["accuracy"] for r in rows if r["corr"] == c]
        ax.plot(xs, ys, "o-", label=f"error corr={c}", color=color)
    ax.set_xlabel("workspace size k"); ax.set_ylabel("majority accuracy")
    ax.set_title("Workspace size: gains vs communication")
    ax.grid(alpha=.25); ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(HERE, "figs", "workspace_accuracy.png")); plt.close(fig)
    return rows


if __name__ == "__main__":
    out = {"e1": e1(), "e1k": e1k(), "e2": e2(), "e3": e3()}
    json.dump(out, open(os.path.join(HERE, "results.json"), "w"), ensure_ascii=False, indent=1)
    for p, v in out["e1"].items():
        print(p, "success", round(v["success"], 3), "p95", round(v["p95"], 3), "bytes", round(v["bytes"], 2))
    print("e1k", [(r["k"], round(r["success"],3), round(r["bytes"],2)) for r in out["e1k"]])
    print("e2", [(r["theta"], round(r["mse"], 3), round(r["bytes_per_step"], 1)) for r in out["e2"]])
    print("e3", [(r["k"], r["corr"], round(r["accuracy"], 3)) for r in out["e3"]])

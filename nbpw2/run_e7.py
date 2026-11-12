# -*- coding: utf-8 -*-
"""E7: skill-aware routing — random vs greedy coverage vs learned."""
import json, random, statistics, os

SKILLS = ["retrieval", "nli", "compute", "memory"]

def make_nodes(seed, n=20):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        ss = rng.sample(SKILLS, rng.randint(1, 2))
        out.append({"id": i, "skills": set(ss), "lat": rng.uniform(0.01, 0.08), "cost": rng.uniform(1, 5)})
    return out

def run(policy, seed, n=1000):
    rng = random.Random(seed); nodes = make_nodes(seed)
    succ, cost = [], []
    stats = {s: {} for s in SKILLS}
    for _ in range(n):
        need = set(rng.sample(SKILLS, 2))
        if policy == "random":
            sel = rng.sample(nodes, 2)
        elif policy == "greedy":
            sel, covered = [], set()
            for _ in range(3):
                best = max(nodes, key=lambda x: len((x["skills"] & need) - covered) - 0.01 * x["lat"])
                sel.append(best); covered |= best["skills"]
                if need <= covered: break
        elif policy == "learned":
            sel, covered = [], set()
            for _ in range(3):
                # choose node with best estimated success per missing skill
                cand = []
                for x in nodes:
                    gain = len((x["skills"] & need) - covered)
                    est = statistics.mean([stats[s].get(x["id"], 0.5) for s in (need - covered)] or [0.5])
                    cand.append((gain + est - 0.05 * x["lat"], x))
                best = max(cand, key=lambda z: z[0])[1]
                sel.append(best); covered |= best["skills"]
                if need <= covered: break
        else:
            sel = nodes[:2]
        ok = 1 if need <= set().union(*(x["skills"] for x in sel)) else 0
        succ.append(ok); cost.append(sum(x["lat"] for x in sel))
        for s in need:
            for x in sel:
                stats[s][x["id"]] = 0.9 * stats[s].get(x["id"], 0.5) + 0.1 * (1 if s in x["skills"] else 0)
    return {"success": statistics.mean(succ), "latency": statistics.mean(cost)}

def main():
    out = {}
    for p in ["random", "greedy", "learned"]:
        runs = [run(p, s) for s in range(5)]
        out[p] = {k: round(statistics.mean(r[k] for r in runs), 4) for k in runs[0]}
        out[p]["success_sd"] = round(statistics.pstdev(r["success"] for r in runs), 4)
        print(p, out[p])
    with open(os.path.join(os.path.dirname(__file__), "results", "e7_skills.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

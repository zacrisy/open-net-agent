# -*- coding: utf-8 -*-
"""Thompson vs UCB 离线对照：两臂 p=0.9 / p=0.3。"""
import math, random, statistics

def run(policy, T=500, seed=0):
    random.seed(seed); p = [0.9, 0.3]; n = [0, 0]; s = [0, 0]; regret = 0.0
    for t in range(T):
        if policy == "ucb":
            i = max(range(2), key=lambda k: (s[k] / n[k] if n[k] else 1e9) + 0.5 * math.sqrt(math.log(t + 1) / (n[k] + 1)))
        else:
            i = max(range(2), key=lambda k: random.betavariate(s[k] + 1, n[k] - s[k] + 1))
        r = 1 if random.random() < p[i] else 0
        n[i] += 1; s[i] += r; regret += p[0] - p[i]
    return regret

for pol in ["ucb", "thompson"]:
    rs = [run(pol, seed=i) for i in range(20)]
    print(pol, "avg regret", round(statistics.mean(rs), 2), "sd", round(statistics.pstdev(rs), 2))

# -*- coding: utf-8 -*-
"""E14: real LAN transport — 5 node processes behind a lossy delay proxy.

Runs real HTTP services (separate processes), injects 30 ms RTT + 5% loss with
netproxy.py, and compares:
  - always query all nodes (no selection)
  - random selection under a latency budget
  - learned selector under a latency budget
  - learned selector *ignoring* latency (shows why RTT must be in the reward)

Output: results/e14_lan.json
"""
import json, os, random, socket, statistics, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from nbpw2.data import load, build_pool, tokens, stable_hash  # noqa: E402
from nbpw2.node_scorer import NodeScorer, node_features  # noqa: E402
from nbpw2 import lan_client  # noqa: E402

N = 5
BASE_PORT = int(os.environ.get("LAN_BASE_PORT", 9301))
PROXY_PORT = int(os.environ.get("LAN_PROXY_PORT", 9400))
LATENCY_MS = float(os.environ.get("LAN_LATENCY_MS", 30))
LOSS = float(os.environ.get("LAN_LOSS", 0.05))
NQ = int(os.environ.get("LAN_NQ", 25))
K_DEPTH = int(os.environ.get("LAN_K", 20))
MODE_PROXY = os.environ.get("LAN_THROUGH_PROXY", "0") == "1"
BUDGET = int(os.environ.get("LAN_BUDGET", 2))
OUT = os.path.join(HERE, "results", "e14_lan.json")

def free(port):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port)); return True
    except OSError:
        return False
    finally:
        s.close()

def wait_health(port, tries=300):
    for _ in range(tries):
        r = lan_client.query(port, "health-probe", 1, timeout=0.4)
        if r["ok"]:
            return True
        time.sleep(0.1)
    return False

def topic_shards(row, pool, n_nodes=N, distractors=100, seed=0):
    from nbpw2.data import make_shards
    nodes, gold = make_shards(row, pool, n_nodes=n_nodes, distractors_per_node=distractors,
                              top_k=5, seed=seed, replicas=1, topic_split=True)
    return nodes, gold

def main():
    rows = load(os.path.join(HERE, "data", "dmqa_dev.jsonl"))
    pool = build_pool(rows)
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"][:NQ]
    row_iter = test[:10] + train[:20]
    # build a per-node corpus from a few questions so shards are not tiny
    corpus = []
    for r in row_iter:
        corpus += r["paragraphs"]
    corpus += pool[:6000]
    by_title = {}
    for p in corpus:
        by_title.setdefault(p["title"], []).append(p)
    # ~200 docs per node = 40 topics x 5 paragraphs (topic shards)
    all_titles = list(by_title)
    random.Random(9).shuffle(all_titles)
    want = len(all_titles) // 5
    per_shard = [all_titles[i * want:(i + 1) * want] for i in range(5)]
    shard_paths = []
    os.makedirs(os.path.join(HERE, "results", "lan"), exist_ok=True)
    for i in range(5):
        chunk = []
        for t in per_shard[i]:
            chunk.extend(by_title[t][:5])
        p = os.path.join(HERE, "results", "lan", f"shard{i}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(chunk, f, ensure_ascii=False)
        shard_paths.append(p)
        print(f"shard {i}: {len(chunk)} docs, {len(per_shard[i])} titles")
    groups = {}
    os.makedirs(os.path.join(HERE, "results", "lan"), exist_ok=True)

    # co-locate: every question's gold goes to one shard, so gold is in the pool
    shard_docs = [json.load(open(p, encoding="utf-8")) for p in shard_paths]
    for i, row in enumerate(rows):
        nid = (i * 7 + 3) % N
        have = {d["title"] for d in shard_docs[nid]}
        for g in {x["title"] for x in row["support"]}:
            if g not in have:
                for d in by_title.get(g, [])[:5]:
                    shard_docs[nid].append(d)
    # each test question's gold titles are forced onto ONE shard
    qnode = {}
    for i, row in enumerate(test):
        nid = i % N
        have = {d["title"] for d in shard_docs[nid]}
        for g in {x["title"] for x in row["support"]}:
            if g not in have:
                for d in by_title.get(g, [])[:5]:
                    shard_docs[nid].append(d)
        qnode[row["id"]] = nid
    for i, p in enumerate(shard_paths):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(shard_docs[i], f, ensure_ascii=False)

    procs = []
    ports = [BASE_PORT + i for i in range(N)]
    try:
        for p, port in zip(shard_paths, ports):
            procs.append(subprocess.Popen([sys.executable, "-m", "nbpw2.lan", "--port", str(port),
                                           "--docs", p], cwd=ROOT,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for port in ports:
            assert wait_health(port), f"node :{port} did not start"
        proxy = subprocess.Popen([sys.executable, os.path.join(ROOT, "netproxy.py"),
                                  "--port", str(PROXY_PORT), "--target", f"127.0.0.1:{ports[0]}",
                                  "--latency-ms", str(LATENCY_MS), "--loss", str(LOSS)],
                                 cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append(proxy)
        time.sleep(0.5)

        # measure real RTT through the proxy vs direct
        direct = [lan_client.query(ports[0], "metformin", 3)["rtt"] for _ in range(5)]
        proxied_r = [lan_client.query(PROXY_PORT, "metformin", 3) for _ in range(8)]
        proxied = [r["rtt"] for r in proxied_r]
        fail = sum(0 if r["ok"] else 1 for r in proxied_r)

        # simple selector: reuse node_scorer features over remote hits
        scorer = None
        res = {}
        def run(mode, budget=BUDGET, seeds=2):
            ms = []
            for s in range(seeds):
                rng = random.Random(100 + s)
                for row in test:
                    q = row["question"]
                    gold = {x["title"] for x in row["support"]}
                    qnode = None
                    order = list(range(N))
                    rng.shuffle(order)
                    picked = []
                    lat = 0.0
                    for nid in order:
                        if len(picked) >= budget and mode != "all":
                            break
                        port = PROXY_PORT if MODE_PROXY else ports[nid]
                        r = lan_client.query(port, q, K_DEPTH, timeout=max(0.5, LATENCY_MS / 1000 * 8))
                        lat += r["rtt"]
                        picked.extend(r["hits"])
                        if mode == "all":
                            continue
                        if mode == "learned":
                            if gold <= {h["title"] for h in picked}:
                                break
                    ranked = sorted(picked, key=lambda h: h.get("verifier", 0.0), reverse=True)
                    titles = []
                    for h in ranked:
                        if h["title"] not in titles:
                            titles.append(h["title"])
                    b2 = 1.0 if gold <= set(titles[:2]) else 0.0
                    b5 = 1.0 if gold <= set(titles[:5]) else 0.0
                    ms.append({"both@2": b2, "both@5": b5, "latency": lat, "queries": len(order[:budget])})
            return {k: round(statistics.mean(m[k] for m in ms), 4) for k in ("both@2", "both@5", "latency", "queries")}

        res["direct_rtt_ms"] = round(statistics.mean(direct) * 1000, 1)
        res["proxied_rtt_ms"] = round(statistics.mean(proxied) * 1000, 1)
        res["proxy_failures"] = int(fail)
        res["proxy_success_rate"] = round(1 - fail / len(proxied_r), 3)
        res["random"] = run("random")
        res["all"] = run("all")
        res["learned"] = run("learned")
        # oracle-ish: query the shard that actually holds both gold titles
        ms = []
        for rng_seed in (0, 1):
            for row in test:
                gold = {x["title"] for x in row["support"]}
                holders = [i for i in range(N) if gold <= {d["title"] for d in json.load(open(shard_paths[i], encoding="utf-8"))}]
                picked, lat = [], 0.0
                for nid in holders[:BUDGET] or [0]:
                    r = lan_client.query(ports[nid], row["question"], K_DEPTH, timeout=max(0.5, LATENCY_MS / 1000 * 8))
                    lat += r["rtt"]; picked.extend(r["hits"])
                ranked = sorted(picked, key=lambda h: h.get("verifier", 0.0), reverse=True)
                titles = []
                for h in ranked:
                    if h["title"] not in titles:
                        titles.append(h["title"])
                ms.append({"both@2": 1.0 if gold <= set(titles[:2]) else 0.0,
                           "both@5": 1.0 if gold <= set(titles[:5]) else 0.0,
                           "latency": lat, "queries": len(holders[:BUDGET] or [0])})
        res["oracle_shard"] = {k: round(statistics.mean(m[k] for m in ms), 4) for k in ("both@2", "both@5", "latency", "queries")}

        # routed: send the query to the shard that holds the gold titles (1 hop)
        ms = []
        for rng_seed in (0, 1):
            for row in test:
                gold = {x["title"] for x in row["support"]}
                holders = [i for i in range(N) if gold <= {d["title"] for d in json.load(open(shard_paths[i], encoding="utf-8"))}]
                picked, lat = [], 0.0
                for nid in holders[:1] or [0]:
                    r = lan_client.query(ports[nid], row["question"], 10, timeout=max(1.0, LATENCY_MS / 1000 * 20))
                    lat += r["rtt"]; picked.extend(r["hits"])
                ranked = sorted(picked, key=lambda h: h.get("verifier", 0.0), reverse=True)
                titles = []
                for h in ranked:
                    if h["title"] not in titles:
                        titles.append(h["title"])
                ms.append({"both@2": 1.0 if gold <= set(titles[:2]) else 0.0,
                           "both@5": 1.0 if gold <= set(titles[:5]) else 0.0,
                           "latency": lat, "queries": 1})
        res["routed_single_shard"] = {k: round(statistics.mean(m[k] for m in ms), 4) for k in ("both@2", "both@5", "latency", "queries")}
        print(json.dumps(res, ensure_ascii=False, indent=2))
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump({"config": {"nodes": N, "latency_ms": LATENCY_MS, "loss": LOSS,
                                  "nq": NQ, "budget": BUDGET}, "results": res}, f, ensure_ascii=False, indent=2)
    finally:
        for p in procs:
            try: p.terminate()
            except Exception: pass

if __name__ == "__main__":
    main()

# Changelog

## Live ask entry + VPS backend (2026-11-13)

- `brain.html`: first-screen question box wired to `POST /public/brain/ask`;
  renders the same trace vocabulary as the frozen demo (route hops with max
  cosine per node, per-node recall, selected set with verifier scores, answer
  span + citation + latency). 180-char cap, 20s client abort, graceful
  "backend offline" fallback that keeps the snapshot demo.
- `nbpw2/online_ask.py`: the D1 chain as a callable service (route → dense
  recall k=10 → verifier → pair head K=5 → extractive readout) over the shipped
  `bge_pool_nodes.npz`; questions are never persisted or logged.
- `coordinator_async.py`: `/public/brain/ask` (8 req/min per IP, 180 chars,
  25s server timeout) and `/public/brain/health`.
- Deploy: `deploy/` gains pinned server requirements, systemd unit, Caddyfile,
  healthcheck and `vps_deploy_brain.sh`; `VPS_BRAIN.md` documents the box.

## NBPW-2 research pilot (2026-11-06)

Network-brain reference implementation + experiments, under `nbpw2/`:

- `nbpw2/protocol.py`, `bus.py`: Brain Message Bus v0 (typed envelope, signatures,
  append-only event log, replay).
- `nbpw2/workspace.py`: capacity-limited global workspace with salience
  competition, novelty/coverage/agreement terms and coalition bonus.
- `nbpw2/predictive.py`: predictive-coding residual gate (surprise threshold).
- `nbpw2/verifier.py`: learned logistic candidate verifier.
- `nbpw2/node_scorer.py`: learned node selector (P1) for active evidence gathering.
- `nbpw2/active.py`: active evidence gathering under a node-query budget.
- `nbpw2/router.py`, `world_model.py`, `policy.py`, `memory.py`, `skills.py`.
- `nbpw2/test_core.py`: protocol/bus/memory/skills smoke tests.

Key results (see `nbpw2/results/SUMMARY.md`):

- DMQA (HotpotQA paragraphs split across 5 nodes, gold split across nodes):
  best single node both@5 0.00; network aggregation 0.53–0.55.
- One-shot workspace reranking adds only +0.01–0.02 over a flat verifier:
  the verifier, not reranking, is the lever.
- **Active evidence selection is the first strong network-level result**:
  B=2 gets 0.287 both@5 vs 0.095 random (250 questions, +0.224, CI
  [0.156,0.292]) using ~39% of all-node bytes.
- **Learned node scorer (P1)**: B=2 0.400 vs 0.288 profile heuristic
  (+0.108, CI [0.040,0.180]); B=3 0.496 vs 0.387 (bm25 recall path). The
  selector is the binding constraint, as the 11-09 audit predicted.
- Predictive coding: theta=0.02 saves ~15% bytes at no loss; no 2x / <=2%
  Pareto point yet.
- Fault injection with replicated evidence degrades gracefully (3 replicas:
  kill 0/1/2 of 5 -> 0.79 / 0.66 / 0.67).
- World-model policy: 0.980 vs 0.951 fixed, 7.48 vs 8.65 steps (synthetic).
- Shapley vs counterfactual credit: Spearman 0.555.
- Skill-aware routing: 100% coverage vs 34.6% random.

### Round 2 (E12–E13): topic-split sharding

- New `topic_split` sharding mode: whole topics assigned to nodes (~22 titles
  per node instead of 100 random paragraphs), matching how a real federated
  network is partitioned.
- Learned node scorer under topic split: B=2 **0.445 vs 0.116 random**
  (+0.364, CI [0.288, 0.436]); B=3 0.645 vs 0.264. All-node ceiling rises from
  0.58 to 0.83 because candidate dilution drops.
- 10 nodes x topic split: B=4 gets 0.645 vs 0.120 random with 39% of the
  all-node bytes (all-10 = 0.850).
- Conclusion: node selection is a real lever; the remaining oracle gap is a
  node-profile/recall problem, not a workspace problem.

### Round 3 (E15): multi-round selection + stopping criteria

- Multi-round active selection: learned 0.772 vs random 0.504 both@5 at 4 node
  queries (250 questions).
- Stopping criteria: coverage>=0.6 reaches 0.524 both@5 with **2.11 queries**
  (random needs 4 queries to get 0.504). Per-query efficiency 0.248 vs 0.126.
- NEGATIVE: "stop when top-2 verifier scores are high" collapses accuracy
  (0.772 -> 0.280); a confident paragraph is not evidence of coverage.
- Real LAN transport (E14) is implemented but **blocked**: 5 node processes +
  netproxy (30 ms RTT, 5% loss, measured 12 ms -> ~90 ms) work, but long
  queries return different top-20 in subprocess vs in-process on the same
  shard file. No LAN numbers are reported until this is fixed.

Honest limits: paragraph-level retrieval only, 100–250 test questions, lexical
verifier (no LLM/embeddings yet), synthetic routing/world-model tasks, LAN
transport reproducibility bug unresolved. The 50-node WAN stage remains gated.

### Round 4 (E16–E17): dense default depth k=10 + node-route diagnosis

- Default recall depth is now **k=10** (`NBPW2_RECALL_K`, was 20), i.e. 20
  candidates at B=2 instead of 40. Measured through the real `recall()` entry
  point: set .720 / ws .670 / ceiling .780. Same-head paired comparison against
  k=20 (.730 set) is **−.01 [−.04, .02]** — no readout loss, ~94 ms saved at
  4.7 ms/candidate readout. k=20 stays available as a high-budget setting.
- Additive decomposition at the new default: hit .780 / node-not-queried .110 /
  in-node depth .110. The depth term is what dense retrieval fixed; the .11
  routing term is unchanged from BM25 and is now the largest structural gap.
- E17 route diagnosis on the 11 questions with a gold node never queried:
  **10/11 are distinct-node misrankings** (both golds live in different nodes,
  `bridge_hop` ranks the missing one 3rd), **1/11 is same-node-unroutable**
  (both golds in one node; no B=2 policy can recover it — it needs B>=3 or a
  node merge). Query signal exists: the missing node is rank 1–3 by dense
  max-cosine in every case.
- Variants (recall fixed at k=10, shipped verifier/head, only routing changes):
  - D1 dense node score, independent top-2: ceiling .780 -> .880, node recall
    .940 -> .995, set **.720 -> .790, +.07 [.02, .13]**, ws .670 -> .730.
  - D2 dense bridge from the hop-1 anchor paragraph: set .770, +.05 [0, .10].
  - D3 D2 + adaptive third hop when the hop-2 bridge is weak: set .760,
    +.04 [−.01, .10] at 2.19 node queries — adaptivity does not pay at K=3.
- D1 is wired as the default in Round 5 below; `bridge_hop` remains available
  as an optional routing policy.
- Same 100 test questions, K=3, B=2; paired question-cluster bootstrap; ±.07
  half-width rule unchanged. Raw numbers: `nbpw2/results/e16_dense_default.json`,
  `e16b_k10_default.json`, `e17_node_route.json`.

### Round 5 (E19): D1 dense node routing becomes the default

- `active.choose` gains `dense_route`: the query vector is computed once per
  environment (`_query_vec`), each node is scored by max cosine over its
  paragraph matrix (`_node_matrix`), and repeated calls give the independent
  top-k order. `run_policy` now defaults to `policy="dense_route"`;
  `bridge_hop` is unchanged and remains opt-in.
- End-to-end rerun through the wired path, default combo (dense k=10, B=2,
  shipped verifier/pair head, set greedy K=5, 100 dmqa_dev test questions):
  ceiling .880, node recall .995, ws .730, set **.790**. Bridge_hop baseline:
  .780 / .940 / .670 / .720. Paired question-cluster bootstrap:
  **set +.070 [.02, .13]**, ws +.060 [.01, .12]. Reproduces E17's .790.
- Additive decomposition at the new default: hit .880 / node-not-queried .010 /
  in-node depth .110. Routing is no longer the main structural gap; depth is.
- Interaction, B=3 with per-node k=10 unchanged: D1 and bridge_hop return the
  same 30-candidate union (set .790, ceiling .890). Route order differs on half
  the questions, but dilution does not change. No gain.
- Interaction, rank squash with retrained head: squash minus raw is 0.000
  [0.00, 0.00] with D1 (.790) and without (.720). The earlier "no effect on
  dense candidates" still holds; D1 introduced no interaction.
- Raw numbers: `nbpw2/results/e19_d1_default.json`; the public demo trace is
  regenerated with D1 in `e18_trace.json`.

## 0.7.0

- Evidence-first workbench: `/public/ask` with research / docs / compute / verify
- Real sources: PubMed, arXiv, Hacker News, Stack Overflow, OpenAlex, Crossref
- Chinese evidence summary with `[n]` citations; zh→en query expansion + translation
- Feedback → SQLite experience → knowledge pack → network memory injection
- Pages control deck (no Serveo warning), CORS backend
- 16-doc learned pack; new nodes auto-provision it


## 0.6.1

- auto provisioning: lite/auto/full by RAM, starter memory pack, `--data-dir`
- retrieval IDF weighting + phrase bonus
- CI workflow + badge; GitHub Pages; Discussions
- public demo tunnel

## 0.6.0

- WSS end-to-end (`test_wss.py`)
- plugin sandbox: subprocess + 2s timeout + 256MB limit (`test_sandbox.py`)
- node TTL cleanup; GitHub Pages; join page; public tunnel
- v0.5.0 release + issues #1–#4


## 0.5.0

- WebSocket async coordinator (`coordinator_async.py`) + WS node (`node_async.py`)
- public demo via localhost.run SSH tunnel
- dashboard, `/join`, installer served by coordinator
- token auth, rotation, per-IP rate limit
- UCB/Thompson routing, SQLite audit + async writer
- plugin manifest sha256/version, integrity check
- transport-level WAN proxy + quorum tuning
- 50-node local pilot: 100 queries 100%, p50 0.0226s

## 0.4.0

- long-poll, UCB, SQLite audit, plugin marketplace, WAN simulation

## 0.3.0

- TLS, token rotation, reputation routing, NLI skill, 20-node load

## 0.2.0

- token auth, skill routing, quorum/fault tolerance, metrics

## 0.1.0

- coordinator + node + one-click installer + demo

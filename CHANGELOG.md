# Changelog

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

Honest limits: paragraph-level retrieval only, 100–250 test questions, lexical
verifier (no LLM/embeddings yet), synthetic routing/world-model tasks, no real
LAN/WAN deployment. The 50-node WAN stage remains gated.

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

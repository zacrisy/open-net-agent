# NBPW-2: network brain reference implementation

This is the executable skeleton from `网络大脑实现方案.md`: a capacity-limited
global workspace, predictive-coding residual gate, learned verifier, routing,
world-model policy, versioned memory, skill registry, and credit assignment.

It is deliberately small and runnable on CPU, using real HotpotQA paragraphs
for the distributed multi-hop QA (DMQA) pilot.

## Data

`data/dmqa_dev.jsonl` (400 questions) and `data/dmqa_1000.jsonl` (1000
questions) are subset files built from HotpotQA validation; the 6 MB larger file
is not committed. Regenerate both with:

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 build_dmqa.py \
  ../../reasoning_lab/data/hotpot_validation.parquet data/dmqa_1000.jsonl 1000
```

`data/dmqa_dev.jsonl` contains 400 HotpotQA validation questions (300 train /
100 test), with 10 context paragraphs and two gold supporting paragraphs per
question. Built from `reasoning_lab/data/hotpot_validation.parquet`:

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 build_dmqa.py \
  ../../reasoning_lab/data/hotpot_validation.parquet data/dmqa_dev.jsonl 400
```

HotpotQA is CC BY-SA 4.0; this subset is for local research only.

## Run

Use a Python with numpy (tested: Python 3.12, numpy 2.2.6):

```bash
cd network_agent
PY=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
$PY -m nbpw2.test_core
$PY -m nbpw2.run_e1       # DMQA: workspace vs baselines
$PY -m nbpw2.run_e1b      # fair local-verifier workspace test
$PY -m nbpw2.analyze_e1   # paired bootstrap
$PY -m nbpw2.run_e2       # predictive-coding Pareto
$PY -m nbpw2.run_e3       # routing / active selection
$PY -m nbpw2.run_e4       # fault injection + replication
$PY -m nbpw2.run_e5       # world-model policy
$PY -m nbpw2.run_e6       # Shapley vs counterfactual credit
$PY -m nbpw2.run_e7       # skill-aware routing
$PY -m nbpw2.run_e8       # active evidence gathering (100 test)
$PY -m nbpw2.run_e9       # larger replication (1000 questions)
$PY -m nbpw2.run_e10      # 10-node simulation
$PY -m nbpw2.run_e11      # learned node scorer (P1)
$PY -m nbpw2.run_e12      # topic-split sharding (realistic network)
$PY -m nbpw2.run_e13      # 10 nodes x topic split
```

Or run everything:

```bash
$PY -m nbpw2.run_all
```

## Module map

| File | Role |
|---|---|
| `data.py` | DMQA loading + sharding (gold split across nodes) |
| `retrieval.py` | per-node TF-IDF retriever |
| `verifier.py` | learned logistic verifier over candidate features |
| `workspace.py` | capacity-limited salience competition + coalition |
| `predictive.py` | residual gate (surprise threshold) |
| `router.py` | UCB / context-UCB |
| `world_model.py` | linear world model for the synthetic research task |
| `policy.py` | world-model policy |
| `memory.py` | versioned memory + rollback |
| `skills.py` | executable skill registry with pre/post conditions |
| `protocol.py` | BMB v0 envelope + append-only event log |
| `bus.py` | in-process bus |
| `network.py` | episode runner + baselines |
| `node_scorer.py` | learned node selector (P1) |
| `run_e*.py` | experiments |

## Results (2026-11-06 pilot)

See `results/SUMMARY.md`. Headline:

- Network aggregation beats any single node on DMQA (0.55 vs 0.00 both@5),
  but a verifier-based flat ensemble is already 0.53. One-shot workspace adds
  only **+0.02** — not a proven network-specific gain.
- **Active evidence selection is the first strong result**: at B=2 it gets
  **0.287 both@5 vs 0.095 random** (250 test questions; +0.224, CI
  [0.156,0.292]), using ~39% of all-node bytes. At B=3: 0.381 vs 0.195.
  It also scales to 10 nodes: B=4 gets 0.303 vs 0.113 random, with 40% of
  all-node bytes.
- Predictive coding at theta=0.05 cuts bytes ~40% but loses ~6 points both@5;
  no 2x bandwidth / <=2% loss Pareto point in this pilot.
- Context-UCB/NBPW routing beats random and global UCB (0.816 vs 0.631/0.774;
  oracle 0.845).
- Replication (3 copies of gold evidence) makes 20–40% node loss graceful
  (both@5 0.79 -> 0.66/0.67), while no replication drops 0.55 -> 0.40/0.28.
- World-model policy beats fixed pipeline (0.980 vs 0.951 success, 7.48 vs
  8.65 steps).
- Skill-aware routing covers required skills 100% vs 34.6% random.
- Shapley and counterfactual credit agree at Spearman 0.555; exact Shapley
  is expensive (32 subsets for 5 nodes).

## Honest limitations

1. DMQA is **paragraph-level retrieval**, not full answer generation.
2. E1–E8 use 100 test questions (wide CIs); E9 replicates on 250 test questions.
3. The verifier is a small logistic model over lexical features; no LLM.
4. The workspace/coalition result is a **negative/weak** result: the verifier
   is the main lever, not the workspace.
5. E3/E5/E7 are synthetic; E4 uses replicated evidence, which is a
   fault-tolerance mechanism, not emergent cognition.
6. No real LAN/WAN, no 50-node deployment, no production integration yet.
7. M4 (multi-region, governance, public benchmark) is design-only.

## Next gate

Per the plan, do **not** jump to 50 nodes. The active-selection gate is now met
at equal budget: B=2 active 0.287 vs random 0.095 (250 questions, +0.224).
But it is still far from the all-node upper bound (0.580) and from oracle
(0.819), so the selector has room to improve. Next: **10-node LAN pilot** with
real latency, plus a **stronger dense retriever** (BGE/E5) and a better node
profile. Only then consider 50-node WAN.

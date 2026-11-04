# NBPW preliminary experiments

- Design: [DESIGN.md](DESIGN.md)
- Experiment report: [REPORT.md](REPORT.md)
- Continual learning report: [REPORT_CONTINUAL.md](REPORT_CONTINUAL.md)

Synthetic testbed for the Network Brain / Predictive Workspace design.

## Run

```bash
cd nbpw
python3 run_experiments.py
```

Outputs:
- `results.json`
- `figs/routing_learning.png`
- `figs/workspace_tradeoff.png`
- `figs/predictive_compression.png`
- `figs/workspace_accuracy.png`

## What is tested

1. **Heterogeneous routing** — random / UCB / MoE / NBPW top-k workspace, 30 nodes, 800 queries, 5 seeds, 20% mid-run failure.
2. **Predictive coding** — AR(1) signal, send residual only above θ; bytes vs reconstruction MSE.
3. **Workspace size** — independent vs correlated errors; accuracy vs k.

## Key findings

- NBPW k=3: success 0.947 vs UCB 0.805; p99 0.057s vs 1.0s; cost 2.7× bytes.
- k=2 is the budget sweet spot; k=3 for tail reliability; k=5 marginal.
- Predictive coding: θ=1.8 gives 22.9× fewer bytes but MSE 0.112; it is a budget knob, not lossless.
- **Correlated errors cap the workspace**: with corr=0.2, k=5 (0.825) is worse than k=3 (0.830). Diversity > quantity.

## Limits

Synthetic nodes/signals, no real WAN, no real model-error correlation, no async staleness. Next: 5–10 LAN nodes with netproxy latency/loss and real retrieval/NLI.

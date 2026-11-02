# Architecture

```
client ──HTTP──> coordinator ──WebSocket──> nodes
                    │
                    ├─ registry / skills
                    ├─ routing (UCB / Thompson)
                    ├─ quorum & timeout
                    ├─ verifier / aggregation
                    └─ audit (SQLite)
```

## Node

- outbound only; no inbound ports;
- declares `skills` (echo/retrieval/nli);
- executes locally, returns `{answer, score, evidence}`;
- pause file, `nice 19`, reconnect.

## Coordinator

- `POST /register`, `GET /task`, `POST /result`, `POST /query`;
- `GET /ws?node_id=&skills=` for push;
- `GET /status`, `/metrics`, `/skills`, `/audit`;
- token auth, per-IP rate limit, node TTL.

## Routing

- reputation `rep = 0.7*acc + 0.3*avg_score`;
- UCB: `rep + c*sqrt(log N / n)`;
- Thompson: `Beta(ok+1, fail+1)`;
- preferred nodes get a grace window.

## Quorum

- wait `min(quorum, capable)` results or timeout;
- quorum < N tolerates loss (5% loss: q=5 fails 30%, q=4 succeeds).

## Security

- token in `X-Auth-Token` (or `?token=` for WS);
- HTTPS/WSS via reverse proxy/tunnel;
- plugins sha256-pinned; no sandbox yet.

## Agent core (v0.7)

The current coordinator is not just a router; it runs an **evidence-first workbench**:

```
client → /public/ask
  ├─ research : expand query (zh→en) → PubMed / arXiv / HN / Stack Overflow / OpenAlex / Crossref
  │             → rank sources → extract mechanism sentences → translate → cite [n]
  ├─ docs     : split document → rank chunks → answer with [Dn]
  ├─ compute  : AST evaluator (no arbitrary eval)
  └─ verify   : route claim || evidence to an NLI node
```

### Why evidence-first

A 0.5B–1.5B local model is available, but it hallucinated in tests (e.g. invented
"orexin release" for GLP-1). Facts therefore come from retrieved sources; the model
is optional and not trusted for factual generation.

### Evolution loop

```
answer → user vote (up/down) → SQLite experience
      → top-voted experiences become a knowledge pack
      → new nodes pull the pack in provision.py
      → later answers cite "network memory"
```

This is **experience distillation**, not autonomous self-modifying code. Skill
versioning and automatic skill synthesis remain roadmap items.

### Limits

- Coordinator-side research means the work is not yet distributed across nodes;
  nodes currently provide retrieval, echo and NLI.
- Wikipedia / DuckDuckGo are unreachable in this network; the agent is strongest
  for medical, academic, technical and code questions.
- Sources can be wrong or stale; citations are shown so users can check.

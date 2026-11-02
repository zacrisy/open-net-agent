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

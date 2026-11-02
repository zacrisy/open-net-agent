# Changelog

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

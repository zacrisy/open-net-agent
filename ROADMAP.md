# Roadmap

## v0.5 (current)

- [x] coordinator + nodes + one-click install
- [x] token auth, TLS (optional), token rotation
- [x] skills: echo / retrieval / nli
- [x] quorum, fault injection, TTL cleanup
- [x] UCB / Thompson routing
- [x] SQLite audit + async writer
- [x] WebSocket push (p50 0.022s, 50-node local pilot)
- [x] public demo via SSH tunnel

## v0.6

- [ ] WSS end-to-end (aiohttp ssl_context)
- [ ] Postgres + queue
- [ ] plugin sandbox (subprocess, seccomp/limits)
- [ ] multi-coordinator + consistent hashing
- [ ] Prometheus metrics

## v0.7

- [ ] real LAN 3–5 machines
- [ ] public pilot 10–50 nodes
- [ ] reputation + verifier marketplace
- [ ] client SDKs (Go/Rust/Node)

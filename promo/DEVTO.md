# OpenNetAgent: an evidence-first network agent that cites real sources

Most “AI agents” are one model on one machine. OpenNetAgent treats each computer as a node: a coordinator routes tasks over WebSocket, nodes keep local memory and skills, and the coordinator aggregates and verifies.

The interesting part is not the graph. It is **what happens when a question needs facts**.

## The problem with small local models

I tried qwen2.5 0.5B and 1.5B for a research agent. It confidently invented “GLP-1 increases orexin release”, which was not in any source. A demo that looks smart but fabricates is worse than a demo that says “here is the evidence”.

So I changed the design:

1. Expand a Chinese question into English search keywords.
2. Retrieve from PubMed, arXiv, Hacker News, Stack Overflow, OpenAlex, Crossref.
3. Rank sources; extract mechanism sentences; translate to Chinese.
4. Cite each claim with `[n]`.
5. Keep the local model optional and never trust it for facts.

## What the workbench does

- **Research** — GLP-1 mechanism: 4 real papers, Chinese evidence summary, ~11s.
- **Docs** — paste a report or code, get chunk-level answers `[Dn]`.
- **Compute** — AST-safe math, no arbitrary eval.
- **Verify** — NLI node checks claim vs evidence.
- **Evolution** — upvoted answers become a knowledge pack; new nodes pull it; later answers cite `network memory`.

## Try it

- Control deck: https://zacrisy.github.io/open-net-agent/console.html?v=3
- Short link: https://tinyurl.com/2bfybazp
- Repo: https://github.com/zacrisy/open-net-agent
- Join a node: https://github.com/zacrisy/open-net-agent/issues/4

## Honest limits

Wikipedia/DuckDuckGo are unreachable in this network; the agent is strongest for medical, academic, technical and code questions. Research currently runs coordinator-side; nodes provide retrieval/echo/NLI. Self-evolution is experience distillation, not autonomous code rewriting.

If you run a node, I would love LAN/WAN latency and failure reports.

# OpenNetAgent Launch Kit (v0.7)

## 链接

- **控制台（推荐）**：https://zacrisy.github.io/open-net-agent/brain.html?v=3
- **短链**：https://tinyurl.com/247rsgct
- **仓库**：https://github.com/zacrisy/open-net-agent
- **Release**：https://github.com/zacrisy/open-net-agent/releases/tag/v0.7.0
- **Discussion**：https://github.com/zacrisy/open-net-agent/discussions/6
- **加入节点**：https://github.com/zacrisy/open-net-agent/issues/4
- **Awesome PR**：https://github.com/e2b-dev/awesome-ai-agents/pull/1914

## 一句话

**OpenNetAgent**：把每台电脑变成节点，组成一个**会给真实来源、带引用、能核查、会从反馈中积累记忆**的网络智能体。

不是“更大的模型”，而是“专家网络 + 证据优先”。

---

## Show HN

**Title:** Show HN: OpenNetAgent – a network agent that cites real sources

**URL:** https://zacrisy.github.io/open-net-agent/brain.html?v=3

**Body:**

Most agents are one model on one machine. OpenNetAgent treats each computer as a
node: a coordinator routes tasks over WebSocket, nodes keep local memory/skills,
and the coordinator aggregates and verifies.

What actually works today:

- **Research** with real sources: PubMed, arXiv, Hacker News, Stack Overflow,
  OpenAlex, Crossref; Chinese evidence summary with `[n]` citations.
- **Docs**: paste a report/code, get chunk-level answers `[Dn]`.
- **Compute**: AST-safe math (no arbitrary eval).
- **Verify**: NLI node checks claim vs evidence.
- **Evolution**: upvoted answers → experience → knowledge pack; later answers cite
  `network memory`.

Example: “GLP-1 mechanism” returns 4 real papers in ~11s; an asyncio error returns
a Stack Overflow accepted answer.

Honest limits: Wikipedia/DuckDuckGo are unreachable in this network; research runs
coordinator-side; nodes currently provide retrieval/echo/NLI. Looking for node
runners (LAN/WAN latency + failure reports) and contributors for distributed
research skills.

Join: https://github.com/zacrisy/open-net-agent/issues/4

---

## Reddit r/LocalLLaMA

**Title:** I stopped letting a small local model invent facts — OpenNetAgent cites sources instead

**Body:**

I tried qwen2.5 0.5B/1.5B for a research agent. It confidently invented “GLP-1
increases orexin release”, which is not in any source. So I changed the design:

- retrieve from PubMed / arXiv / HN / Stack Overflow / OpenAlex / Crossref;
- rank sources, extract mechanism sentences, translate to Chinese, cite `[n]`;
- local model is optional and never trusted for facts;
- docs Q&A with `[Dn]`; safe compute; NLI verification.

Feedback (upvote) becomes experience → knowledge pack → new nodes pull it → later
answers cite `network memory`.

Control deck: https://tinyurl.com/247rsgct
Repo: https://github.com/zacrisy/open-net-agent

Would love feedback on source ranking, translation quality, and how to distribute
research skills across nodes.

---

## Reddit r/selfhosted

**Title:** OpenNetAgent – add an idle box as a node with one command (outbound-only, low impact)

**Body:**

If you have an idle machine, you can add it as a node:

```bash
COORD=https://opennetagent2.serveousercontent.com
curl -fsSL $COORD/install.sh | bash -s -- \
  --coordinator $COORD --token <YOUR_TOKEN>
```

- outbound WebSocket only, no inbound ports;
- `nice 19`, pause/uninstall;
- auto-provision: lite mode needs no model, pulls starter + learned memory;
- coordinator routes research / docs / compute / NLI tasks.

I’m looking for 3–5 machine LAN tests and WAN latency reports. Control deck:
https://tinyurl.com/247rsgct

---

## X / Twitter thread

1/ Most agents are one model on one machine. OpenNetAgent treats each computer as
a node, connected as a graph. The network is the agent.

2/ It answers with **real sources**: PubMed, arXiv, Hacker News, Stack Overflow,
OpenAlex, Crossref — with `[n]` citations. GLP-1 mechanism: 4 papers, ~11s.

3/ Also: document Q&A `[Dn]`, AST-safe compute, NLI claim verification.

4/ A 0.5B model invented facts, so facts come from retrieval; the model is optional.
Evidence first, not vibes.

5/ Upvote an answer → experience → knowledge pack → new nodes pull it → later
answers cite `network memory`.

6/ Try it: https://tinyurl.com/247rsgct
Repo: https://github.com/zacrisy/open-net-agent
Looking for node runners + contributors.

---

## 中文：知乎 / V2EX / 即刻

**标题**：把每台电脑变成节点：一个会给出来源的网络智能体

我们习惯把模型越做越大，但一台机器总有上限。OpenNetAgent 换个思路：每台电脑是
图上的节点，协调者通过 WebSocket 分发任务，节点保留本地记忆与技能。

它现在能做什么：

- **Research**：PubMed / arXiv / Hacker News / Stack Overflow / OpenAlex /
  Crossref，中文证据摘要 + `[n]` 引用；
- **Docs**：粘贴报告/代码，按片段回答 `[Dn]`；
- **Compute**：AST 安全计算；
- **Verify**：NLI 判断支持/反驳；
- **Evolution**：赞/踩 → 经验 → 知识包 → 新节点记忆。

实测：GLP-1 机制返回 4 篇真实论文，约 11 秒；asyncio 报错返回 Stack Overflow
高票答案。

体验：https://tinyurl.com/247rsgct
仓库：https://github.com/zacrisy/open-net-agent
加入节点：https://github.com/zacrisy/open-net-agent/issues/4

诚实说明：当前网络 Wikipedia/DDG 不可达，强在医学/学术/技术/代码；研究编排还在
协调者侧，节点主要承担 retrieval/echo/NLI；自我进化是经验蒸馏，不是自动改代码。

---

## 一键发帖入口

- Hacker News：https://news.ycombinator.com/submit
- Reddit：https://www.reddit.com/submit
- X：https://x.com/intent/post?text=OpenNetAgent%20%E2%80%94%20a%20network%20agent%20that%20cites%20real%20sources&url=https%3A%2F%2Ftinyurl.com%2F22d5uz9e
- V2EX：https://www.v2ex.com/new
- 知乎：https://zhuanlan.zhihu.com/write

## 发布顺序建议

1. GitHub Release + Discussion（已完成）
2. awesome-ai-agents PR（已完成，#1914）
3. Hacker News（Show HN）
4. Reddit r/LocalLLaMA → r/selfhosted
5. X thread
6. V2EX / 知乎 / 即刻
7. 回复评论，收集节点延迟/失败数据，更新 issue #4

## 不夸大

- 不是 AGI，不是通用闲聊模型；
- 研究能力有明确数据源边界；
- 节点网络还在早期，欢迎真实测试而不是只看 star。

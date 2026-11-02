# Launch kit / 发布宣传材料

## 一句话

**OpenNetAgent**：把每台闲置电脑变成一个节点，用 WebSocket 组成一个可加入、可退出、低打扰、可验证的网络智能体。

- 出站连接，不开放入站端口
- `nice 19`，可暂停/卸载
- 协调者做路由、聚合、验证
- 50 节点本机试点：100 查询 100%，p50 0.023s

---

## Show HN

**Title:** Show HN: OpenNetAgent – turn idle computers into a network agent

**Body:**

Most "AI agents" are one process on one machine. We tried the opposite: treat each
computer as a node in a graph, connect them over WebSocket, and let a coordinator
route tasks, aggregate answers, and verify them.

- one-line join: `curl -fsSL <url>/install.sh | bash -s -- --coordinator <url> --token <token>`
- outbound-only, `nice 19`, pause/uninstall
- skills: echo / retrieval / NLI
- quorum, reputation/UCB/Thompson routing, SQLite audit
- 50-node local pilot: 100 queries 100%, p50 0.0226s

It's a prototype, not AGI: a graph of experts, not a giant neural net. Looking for
people to run nodes, add skills, and harden it.

Demo: <https://opennetagent.serveousercontent.com/> (temporary tunnel)
Repo: <https://github.com/zacrisy/open-net-agent>

---

## Reddit r/LocalLLaMA

**Title:** I built a network-native agent: each computer is a node, WebSocket + quorum

We keep scaling one box; I wanted to scale *across* boxes. OpenNetAgent treats each
machine as a node with local memory/skills; a coordinator pushes tasks over
WebSocket, nodes answer, coordinator aggregates/verifies.

What's in the prototype:
- one-line installer (launchd/systemd/nohup), outbound-only, `nice 19`, pause/uninstall
- echo / retrieval / NLI skills; plugin manifest with sha256
- quorum + fault injection; UCB/Thompson routing; SQLite audit
- 50-node local pilot 100%, p50 0.023s

Honest limits: demo corpus is tiny; tunnel is temporary; plugins are not sandboxed yet.
Would love feedback on routing, sandboxing, and real LAN/WAN tests.

---

## Reddit r/selfhosted

**Title:** OpenNetAgent – join a network agent with one command (outbound-only, low impact)

If you have an idle box, you can add it as a node:
`curl -fsSL <url>/install.sh | bash -s -- --coordinator <url> --token <token>`

- no inbound ports, outbound WebSocket
- `nice 19`, pause file, one-command uninstall
- coordinator can route by skill; audit log

Looking for self-hosters to test 3–5 machine LAN setups and report latency/failure modes.

---

## X / Twitter thread

1/ Most agents are one process on one machine. We tried the opposite: every computer
is a node, connected as a graph. Meet OpenNetAgent.

2/ One command turns a box into a node:
`curl -fsSL <url>/install.sh | bash -s -- --coordinator <url> --token <token>`
Outbound-only, `nice 19`, pause/uninstall.

3/ Coordinator routes tasks over WebSocket, aggregates answers, verifies with quorum.
Skills: echo / retrieval / NLI. 50-node local pilot: 100 queries 100%, p50 0.023s.

4/ It's a prototype: a graph of experts, not a giant neural net. Next: WSS, Postgres,
plugin sandbox, real LAN/WAN pilot.

5/ Want to run a node or add a skill? Repo: <https://github.com/zacrisy/open-net-agent>
Demo: <https://opennetagent.serveousercontent.com/>

---

## 中文：知乎 / V2EX / 即刻

**标题**：把每台闲置电脑变成神经元：一个可加入的网络智能体

我们习惯把模型越做越大，但一台机器的内存/算力总有上限。OpenNetAgent 换个思路：
把每台电脑当成图上的一个节点，节点各自持有本地记忆/技能，协调者通过 WebSocket
分发任务、聚合答案、做验证。

特点：
- 一条命令加入，出站连接，不开放入站端口；
- `nice 19`，可暂停/卸载，不影响正常工作；
- 技能插件：echo / retrieval / NLI；
- quorum、UCB/Thompson 路由、SQLite 审计；
- 50 节点本机试点：100 次查询 100%，p50 0.023s。

诚实说明：这是原型，不是 AGI；是“专家网络”，不是字面意义的大神经网络。演示语料很小，
隧道是临时的，插件还没沙箱。欢迎来跑节点、写技能、做 LAN/WAN 测试。

Demo：<https://opennetagent.serveousercontent.com/>
Repo：<https://github.com/zacrisy/open-net-agent>

---

## 发布 checklist

- [ ] GitHub 仓库公开（`gh repo create` 或网页导入）
- [ ] 替换 README/promo 里的 `zacrisy` 和 demo URL
- [ ] 打 tag `v0.5.0`，发 Release
- [ ] 开 3 个 issue：`good first issue`（Go 客户端、Prometheus、插件沙箱）
- [ ] HN / Reddit / X / 知乎 / V2EX 发帖
- [ ] 在 demo 页放“申请 token / 加入”说明
- [ ] 观察 `/metrics` 与节点留存，按反馈迭代

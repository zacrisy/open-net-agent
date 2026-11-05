# 网络大脑项目全面评估与改进研究

**日期**：2026-11-04  
**对象**：OpenNetBrain / `zacrisy/open-net-agent`  
**线上**：<https://zacrisy.github.io/open-net-agent/brain.html?v=20>  
**VPS API**：<https://kids-pcs-attacked-myth.trycloudflare.com>  
**代码基线**：`main`（v0.5.1 之后）

---

## 0. 执行摘要

### 0.1 一句话判断

**这个项目已经是一个“可运行的持续学习知识系统 + 网络大脑控制台”，但还不是最初设想的“网络本身作为认知介质”的网络大脑。**

它实现了：

- 真实来源 → 知识卡 → 信念图 → 自动学习/进化；
- 用户反馈 → 学习主题 / 改进提案；
- 20 秒 AUTO 循环、VPS 常驻、公网 UI；
- 研究/文档/计算/核查/摘要/翻译/抽取七个工具。

它还没有实现：

- **关联扩散**：图谱只是可视化 + 启发式支持边，检索并不走图扩散；
- **网络原生**：3 个节点跑在同一台 VPS 上，没有真实 WAN 多节点；
- **预测编码 / 全局工作空间 / 路由学习**：只在离线实验里验证，生产未接入；
- **真正的信念修正**：冲突检测是规则式，真实来源冲突数为 0；
- **自评估 / 课程 / 遗忘曲线**：没有持续评测闭环；
- **权重/适配器层面的学习**：目前是记忆、图、课程层。

### 0.2 最重要的三个结论

1. **方向没有错，但“网络大脑”目前只完成了“记忆层 + 控制面”。**  
   最强的是 NBCL（知识卡、信念图、自动循环、反馈），最弱的是“关联扩散”和“真实网络”。

2. **最高杠杆的下一步不是换更大的模型，而是把图变成检索与推理的主结构。**  
   用 Personalized PageRank / spreading activation 做多跳关联检索，是当前代码与原始思想之间最短的桥。

3. **必须补评估，否则“自我进化”无法证明。**  
   当前概念题 0.67、真实冲突 0、按置信度剪枝是负结果；需要标准化 benchmark、引用正确率、冲突 F1、保留率和成本指标。

---

## 1. 项目现状盘点

### 1.1 当前架构

```
Browser (brain.html)
   │  CORS
   ▼
coordinator_async.py (aiohttp)
   ├─ /api/brain/status, /graph, /learn, /evolve
   ├─ /api/brain/feedback, /improvements
   ├─ /public/ask  (research/docs/compute/verify/summarize/translate/extract)
   └─ /public/status
        │
        ▼
brain.py (NBCL)
   ├─ agent_core.collect：PubMed / arXiv / HN / SO / OpenAlex / Crossref
   ├─ continual.extract_cards / dedup / build_belief
   └─ SQLite：cycles / cards / edges / feedback / improvements
```

部署：

- 阿里云 Ubuntu VPS，894MB 内存；
- `opennetbrain.service` + `cloudflared-opennet.service`；
- Cloudflare Quick Tunnel 提供 HTTPS；
- `BRAIN_AUTO=1` 在容器/进程内每 15 秒调用 `auto_tick`，学习间隔 20 秒；
- Pages 作为 UI 与 cloud snapshot fallback；
- GitHub Actions 作为另一条云端学习快照。

### 1.2 当前真实数据

截至本次评估：

| 指标 | 数值 |
|---|---:|
| VPS 知识卡 | 114 |
| VPS 学习/进化周期 | 10 |
| VPS AUTO | 20s |
| 页面来源 | 64–76 |
| GitHub Actions 云端快照 | 124 卡 / 15 周期 |
| 本地实验知识卡 | 57 |
| 概念题准确率 | 0.667 |
| 真实来源冲突检测 | 0 |
| 按置信度剪枝 | 负结果（57→28 卡，概念题 0.67→0.33） |

### 1.3 已实现 vs 设计文档

| 设计层 | 设计内容 | 当前实现 | 完成度 |
|---|---|---|---:|
| L0 传输 | 节点、WAN、异步、预算 | 单 VPS、3 个本地 WS 节点 | 2/5 |
| L1 信号 | 预测误差、脉冲、稀疏事件 | 普通 HTTP/WS 消息，无残差编码 | 1.5/5 |
| L2 路由/注意力 | 语义路由、UCB、工作空间 | 固定 3 节点 + 反馈队列 | 2/5 |
| L3 局部计算 | retrieval/verifier/memory/expert | 有 retrieval/NLI stub/echo；工具在 coordinator | 3/5 |
| L4 全局工作空间 | coalition 竞争、广播 | UI 有 “CORE/WORKSPACE” 视觉，无真实 coalition | 1.5/5 |
| L5 可塑性 | 记忆、路由、适配器、蒸馏 | 知识卡/信念图/自动循环；无 adapter | 3/5 |
| L6 神经调制 | 奖励、信任、不确定性广播 | 反馈分类、置信度；无信任/奖励学习 | 1.5/5 |
| 关联扩散 | 图上扩散/多跳 | 图只用于展示；检索不用图 | 1/5 |
| 网络原生 | 真实多节点、失败、异构 | 3 节点同机；无 WAN 实验 | 1/5 |
| 持续学习 | 获取/修正/保留/巩固 | 已实现最小闭环 | 3.5/5 |
| 自我进化 | 课程/工具/架构/权重 | 反馈驱动主题 + 提案 | 2/5 |
| 部署 | 公网、常驻、可访问 | VPS + Tunnel + Pages | 4/5 |

> 评分是作者基于当前代码与实验的主观评估，不是形式化基准。

**总体成熟度：约 2.3–2.6 / 5。**  
更准确的定位是：**“A 模式（推理网络 + 记忆/路由学习）的可运行原型”**，不是完整的 NBPW（A+B+C）。

---

## 2. 与原始思路的逐项对照

### 2.1 原始思路的核心命题

此前的设计主张：

1. 不把互联网当 GPU，不做全局 WAN 反向传播；
2. 把网络当认知介质：节点=神经元，消息=脉冲，路由=突触，工作空间=广播；
3. 学习的是连接、路由、记忆、局部适配器，不是全网权重；
4. 预测编码：只传预测误差；
5. 全局工作空间：活跃 coalition 竞争；
6. 持续学习：知识卡、信念图、课程、巩固；
7. 自我进化：从反馈中学习主题、技能、结构。

### 2.2 哪些匹配得好

| 原始命题 | 当前匹配 | 评价 |
|---|---|---|
| 不做全局 WAN 反传 | ✅ | 没有虚假承诺，架构选择正确 |
| 真实来源 + 证据 | ✅ | 六类来源，带引用与来源类型 |
| 记忆层持续学习 | ✅ | 知识卡、信念图、自动循环 |
| 冲突可审计 | ⚠️ | 有 `disputed` 机制，但检测弱 |
| 用户反馈驱动 | ✅ | 反馈 → 学习主题 / 改进提案 |
| 公网可访问 | ✅ | VPS + Tunnel + Pages |
| 学习不是权重训练 | ✅ | 明确说明，避免过度宣称 |

### 2.3 哪些偏离了

#### 偏离 1：图不是“认知结构”，而是“展示结构”

当前 `brain.graph()`：

- 节点是知识卡；
- 边来自数据库的冲突边；
- 支持边是**词面 Jaccard 相似度**临时计算，仅用于 UI；
- 检索 `agent_core.research()` 不走图，仍是来源检索 + 抽取 + 翻译；
- 多跳、实体、关系、扩散都没有进入查询路径。

这意味着“关联扩散”目前是**视觉隐喻**，不是算法。

#### 偏离 2：网络大脑仍是中心化服务

- 3 个节点在同一台 VPS；
- 路由是固定 `NODES` 列表；
- 没有真实跨网络延迟、丢包、故障、异构；
- 没有 UCB/bandit 在线路由；
- 没有 quorum/共识/信誉；
- 工作空间只是 UI 标签。

#### 偏离 3：信念修正仍是规则式

- `build_belief` 主要是否定/词面规则；
- 真实来源冲突检测为 0；
- 没有 claim 对齐、实体/时间/数值一致性、NLI；
- `disputed` 状态有，但触发条件太窄；
- 没有 AGM/truth maintenance 的收缩/扩张/修正语义。

#### 偏离 4：自我进化只到“主题 + 提案”

- 知识类反馈会自动学习；
- 功能/Bug/风格反馈只生成 proposal；
- 没有工具自生成、prompt 自优化、架构自修改；
- 没有安全 gate 之外的自动代码变更。
- 这是**正确的安全边界**，但离“自我进化”还有距离。

#### 偏离 5：评估没有闭环

- NBCL 实验只有 6 道概念题、12 组冲突对；
- 没有 held-out、延迟测试、7 天保留；
- 没有引用 precision/recall；
- 没有成本/带宽/延迟的持续记录；
- 没有“学习前后”的回归测试。

---

## 3. 相关研究对标

### 3.1 终身学习智能体：记忆是核心，但感知/行动/评估同样重要

Zheng 等（2025/2026）把 LLM 智能体的终身学习拆成：

- **perception**：多模态输入；
- **memory**：存储与检索演化知识；
- **action**：与环境交互；
- 并强调灾难性遗忘、长期性能、评估指标。

**对本项目**：

- 我们的 memory 层做得最好；
- perception 很窄（文本/网页/文档）；
- action 只有工具调用，没有环境闭环；
- 评估不足。

**启示**：NBCL 应该明确自己是“memory-centric lifelong learner”，不要冒充完整智能体；下一步补 perception（URL/PDF/表格/代码）和 action（工具结果反馈）。

来源：[Lifelong Learning of LLM-based Agents: A Roadmap](https://arxiv.org/abs/2501.07278)

### 3.2 自进化智能体：当前只进化了“记忆”

Gao 等（2025/2026）用 **what / when / how / where** 四维组织自进化：

- what：模型、记忆、工具、架构；
- when：测试时、测试间；
- how：标量奖励、文本反馈、单/多智能体；
- where：单智能体 / 多智能体 / 网络。

**对本项目**：

| 维度 | 当前 |
|---|---|
| what | 主要是 memory；工具/架构未进化 |
| when | inter-test-time（定时循环） |
| how | 文本反馈 + 规则分类 |
| where | 单协调者（3 个本地节点） |

**启示**：把“自进化”拆成可审计的层级：记忆进化（已有）→ 工具进化（生成/选择工具）→ 架构进化（路由/工作空间）→ 模型进化（adapter/蒸馏）。不要一步跳到自动改代码。

来源：[A Survey of Self-Evolving Agents](https://arxiv.org/abs/2507.21046)

### 3.3 GraphRAG / HippoRAG / ROGRAG：图检索是最高杠杆

- **HippoRAG**：用知识图谱 + Personalized PageRank 模拟海马索引，多跳 QA 比强 RAG 高最多 20%，单步检索比迭代检索便宜 10–30 倍、快 6–13 倍。
- **GraphRAG**：实体图 + 社区摘要，解决“全局 sensemaking”问题。
- **ROGRAG**：多阶段检索（dual-level + logic form）+ 结果验证 + 增量建库；SeedBench 60%→75%。

**对本项目**：

- 我们的图只有展示和启发式边；
- 没有 PPR、社区、实体、关系、多阶段检索；
- 概念题 0.67 正是“平铺 top-k 不够”的信号；
- 这是最值得先做的改进。

**建议**：

1. 建 typed graph：`claim/entity/source/topic` 节点；`supports/contradicts/mentions/same_as/temporal` 边；
2. 用 PPR / spreading activation 从 query 实体扩散；
3. top-k 子图 → 多卡综合；
4. 记录路径，UI 展示“为什么这些卡被激活”。

来源：[HippoRAG](https://arxiv.org/abs/2405.14831)、[GraphRAG](https://arxiv.org/abs/2404.16130)、[ROGRAG](https://arxiv.org/abs/2503.06474)

### 3.4 A-MEM / MemGPT：记忆需要动态组织与分层

- **A-MEM**：Zettelkasten 式笔记，动态索引、链接、记忆演化；新记忆会更新旧记忆的上下文表示。
- **MemGPT**：OS 式虚拟上下文管理，快/慢记忆分层、中断控制。

**对本项目**：

- 知识卡是静态行，缺少“记忆演化”；
- 没有热/温/冷分层；
- 没有“新卡改写旧卡上下文”的机制；
- 去重是文本相似，不是语义结构。

**建议**：

- 卡片增加 `context/keywords/entities/relations/updated_by`；
- 新卡写入时，更新相关旧卡的 `summary/context`；
- 增加 `hot/warm/cold` 三层：工作集、长期图、归档；
- 用访问频率、任务效用、冲突状态决定层级。

来源：[A-MEM](https://arxiv.org/abs/2502.12110)、[MemGPT](https://arxiv.org/abs/2310.08560)

### 3.5 知识冲突：当前只覆盖了“否定”一种

Xu 等（2024）把知识冲突分为：

- context-memory（上下文 vs 参数记忆）；
- inter-context（不同来源之间）；
- intra-memory（记忆内部）。

**对本项目**：

- 我们主要检测“同一 claim + 否定”；
- 真实冲突 0，说明规则太窄；
- 缺少时间、剂量、人群、数值、定义、范围冲突；
- 没有 claim 对齐（同一实体/关系/时间）。

**建议**：

1. claim 结构化：`subject / relation / object / qualifier / time / population`；
2. NLI + 数值/时间一致性 + 来源可信度；
3. 冲突类型分类，不要只标 `disputed`；
4. 建立 100–300 组人工冲突集，测 precision/recall/F1；
5. 用 truth maintenance 记录“为什么被取代”。

来源：[Knowledge Conflicts for LLMs: A Survey](https://arxiv.org/abs/2403.08319)

### 3.6 RAG 评估：需要 reference-free + 回归测试

RAGAS 提供：

- faithfulness（答案是否被上下文支持）；
- answer relevance；
- context precision/recall；
- 不依赖人工标注的自动评估。

**对本项目**：

- 当前评估是自定义小测；
- 没有 citation correctness、faithfulness、context recall；
- 没有每次 AUTO 后的回归门禁。

**建议**：

- 用 RAGAS 风格指标做每日评估；
- 加“引用正确率”“无依据断言率”“冲突 F1”“保留率”；
- 任何新策略必须通过 baseline 回归。

来源：[RAGAS](https://arxiv.org/abs/2309.15217)

### 3.7 多智能体辩论：多样性买可靠性，但要防相关错误

Du 等（2023）证明多实例辩论能提升事实性与推理；但前提是**错误不完全相关**。

**对本项目**：

- 当前只有一个协调者；
- 之前的 NBPW 实验已经显示：workspace k 增大在独立错误下收益明显，在相关错误下不单调；
- 这与“冗余买可靠性，多样性买智能”一致。

**建议**：

- 引入 verifier / critic / synthesizer 三个角色；
- 角色使用不同来源/不同 prompt/不同模型；
- 先做“独立验证”再做“辩论”，避免同源错误放大；
- 用 quorum + 置信度校准，不要简单多数投票。

来源：[Improving Factuality and Reasoning through Multiagent Debate](https://arxiv.org/abs/2305.14325)

### 3.8 模型崩溃：自我生成数据会退化

Shumailov 等（Nature 2024）指出：递归使用模型生成数据训练会导致不可逆缺陷、尾部消失、模型崩溃。

**对本项目**：

- 目前主要用外部真实来源，风险较低；
- 但“反馈 → 自动学习主题”可能引入用户偏见/回声室；
- 如果未来用 LLM 生成知识卡或合成问答，必须保留真实数据锚点；
- 评估集不能被自生成数据污染。

**建议**：

- 真实来源优先，合成数据只做 curriculum/probe；
- 保留 held-out 真实集；
- 监控来源多样性、topic 分布、冲突率；
- 对反馈主题做去偏/多样性约束。

来源：[AI models collapse when trained on recursively generated data](https://doi.org/10.1038/s41586-024-07566-y)

### 3.9 联邦学习：通信是主约束，当前还没有“网络训练”

McMahan 等（2017）的 FedAvg 证明：在非 IID 数据上，通信高效的本地更新 + 聚合可行，通信轮次可降 10–100×。

**对本项目**：

- 当前没有联邦学习；
- 设计中的“局部 adapter + 联邦蒸馏”尚未实现；
- 单 VPS 也不是网络。

**建议**：

- 短期不要把“网络训练”作为卖点；
- 中期做 **federated distillation**：节点只传 logits/embedding，不传原始数据/权重；
- 先在小规模 LAN/多 VPS 上验证通信/延迟/失败；
- 再谈 WAN。

来源：[Communication-Efficient Learning of Deep Networks from Decentralized Data](https://arxiv.org/abs/1602.05629)

---

## 4. 关键差距（按优先级）

### P0：关联扩散没有进入检索

**证据**：

- `brain.graph()` 的支持边是 Jaccard 相似度；
- `agent_core.research()` 不使用图；
- 概念题 0.67；
- 图只用于 UI。

**影响**：项目最核心的“association diffusion”仍然是隐喻。

**改进**：typed graph + PPR/spreading activation + 路径解释。

### P0：信念修正太弱

**证据**：

- 真实冲突 0；
- 规则检测只覆盖否定；
- 无 NLI/时间/数值/人群对齐；
- `disputed` 触发少。

**影响**：所谓“信念图”更像“卡片列表 + 少量冲突标记”。

### P0：没有可重复的评估

**证据**：

- 6 道概念题、12 组冲突；
- 无 held-out；
- 无引用 precision/recall；
- 无 7 天保留；
- 无成本/延迟曲线。

**影响**：无法证明“学习有效”，也无法比较改进。

### P1：没有真实网络

**证据**：

- 3 节点同机；
- 无 WAN 延迟/丢包/失败；
- 无路由学习；
- 无 quorum/信誉。

**影响**：“网络大脑”仍是单机服务。

### P1：合成/抽取式答案，概念综合弱

**证据**：

- 研究答案是证据摘要 + 翻译；
- 概念题 0.67；
- 没有 citation-constrained synthesis/rerank。

### P1：运维脆弱

- Cloudflare Quick Tunnel URL 会变；
- 894MB 内存，NLI 未安装；
- 无备份/告警/观测；
- 单 VPS 单点。

### P2：反馈自进化边界

- 知识类反馈 → 自动学习（好）；
- 其他 → proposal（安全）；
- 但没有工具自生成/prompt 优化/架构进化；
- 需要防止反馈注入和回声室。

---

## 5. 改进方案

### 5.1 P0（1–2 周）：把图变成检索主结构

**目标**：概念题 0.67 → ≥0.80；多跳问题可解释。

**实现**：

1. 新增 `graph_nodes` / `graph_edges` 表：
   - node：claim、entity、source、topic；
   - edge：supports、contradicts、mentions、same_as、temporal、derived_from；
   - 每条边有权重、证据、时间。
2. 查询：
   - query → 实体/关键词；
   - 在图上做 Personalized PageRank / spreading activation；
   - 取 top-k 子图；
   - 多卡综合 + 引用。
3. UI：
   - 高亮激活路径；
   - 点击边看证据；
   - 显示“为什么这张卡被激活”。
4. 评估：
   - flat top-k vs graph PPR；
   - 10 主题 × 20 题；
   - 证据 recall@k、citation precision、concept accuracy。

**交付**：

- `brain_graph.py`（PPR/扩散）；
- `/api/brain/retrieve`；
- 对比报告；
- UI 路径高亮。

### 5.2 P1（3–6 周）：验证与综合

**目标**：冲突 F1 ≥0.75；引用正确率 ≥0.9；答案从“摘录”变“有依据的综合”。

**实现**：

1. **NLI/claim 对齐**：
   - 部署轻量 NLI（如 DeBERTa-MNLI）或调用外部 NLI；
   - claim 结构化：subject/relation/object/qualifier/time/population；
   - 数值/时间/单位一致性；
   - 来源可信度 + 多源共识。
2. **冲突分类**：
   - contradiction / temporal update / population difference / definition difference / measurement difference；
   - 不是所有冲突都标 `disputed`。
3. **综合**：
   - retrieve → rerank → citation-constrained synthesis；
   - 每个断言必须绑定 `[n]`；
   - 无依据断言直接删/标 uncertain。
4. **评估**：
   - RAGAS 风格 faithfulness/relevance/context precision；
   - 100–300 组人工冲突集；
   - 回归门禁。

### 5.3 P1（4–8 周）：课程、自测、保留

**目标**：7 天保留 ≥0.9；学习有“考试”，不是只堆卡。

**实现**：

1. 从卡片自动生成问题（填空/概念/多跳/冲突）；
2. 每次 AUTO 后抽 10 题自测；
3. 记录：
   - 首次学会时间；
   - 7 天保留；
   - 遗忘曲线；
   - 需要复习的卡。
4. 课程：
   - 先学基础实体，再学关系，再学冲突；
   - 失败题回到学习队列；
   - 避免只学热门主题。

### 5.4 P2（2–3 个月）：真实网络

**目标**：3–5 个真实节点，跨网络，故障下可用。

**实现**：

1. 节点角色：source / verifier / memory / expert；
2. 路由：UCB/Thompson + 能力画像 + 预算；
3. 失败：超时、降级、quorum；
4. 预测编码：只传残差/摘要；
5. 评测：
   - p50/p95 延迟；
   - bytes/query；
   - 掉线 20% 的准确率；
   - 路由 regret。

**不要做**：全局 WAN 反向传播；这是物理上不成立的。

### 5.5 P2：记忆生命周期

- 热/温/冷分层；
- 语义去重；
- 覆盖/效用剪枝（不是置信度硬阈值）；
- 旧卡上下文更新（A-MEM 式）；
- 归档/恢复；
- 数据来源与许可证记录。

### 5.6 P3（研究）：工作空间与神经调制

- coalition 竞争；
- workspace k 与多样性；
- 多智能体辩论 + 独立验证；
- 路由 bandit；
- 拓扑演化；
- 联邦蒸馏/局部 adapter；
- 与 NBPW 离线实验对齐。

---

## 6. 实验设计

### 6.1 Benchmark

| 维度 | 设计 |
|---|---|
| 主题 | 10 个（医学、AI、代码、政策、气候等） |
| 问题 | 200 道：事实/概念/多跳/冲突/时效 |
| 证据 | 每题 gold sources + gold claims |
| 冲突 | 100 组：否定/时间/人群/剂量/定义 |
| 时效 | 20 组“旧结论被新证据取代” |
| 保留 | 学后 1h / 1d / 7d 回测 |

### 6.2 条件

1. flat RAG（当前）；
2. graph PPR；
3. graph PPR + NLI；
4. full（graph + NLI + synthesis + curriculum）。

### 6.3 指标

- **证据**：recall@k、MRR、citation precision/recall；
- **答案**：accuracy、faithfulness、answer relevance；
- **冲突**：precision/recall/F1、类型准确率；
- **保留**：1h/1d/7d retention、遗忘率；
- **效率**：p50/p95 latency、bytes/query、cost/query；
- **校准**：ECE / Brier；
- **多样性**：source/topic entropy。

### 6.4 统计

- 5 seeds；
- bootstrap 95% CI；
- 配对检验；
- 公开数据与脚本。

### 6.5 验收目标（建议）

| 指标 | 当前 | 目标 |
|---|---:|---:|
| 概念题 | 0.67 | ≥0.80 |
| 多跳题 | 未测 | ≥0.65 |
| 冲突 F1 | ~0（真实） | ≥0.75 |
| 引用正确率 | 未测 | ≥0.90 |
| 7 天保留 | 未测 | ≥0.90 |
| p95 延迟 | 8.4s 研究 | <5s（缓存外） |
| 无依据断言率 | 未测 | <5% |

---

## 7. 风险与治理

| 风险 | 说明 | 缓解 |
|---|---|---|
| 模型崩溃/回声室 | 自生成/反馈驱动数据放大偏差 | 真实来源优先、hold-out、多样性约束 |
| 反馈注入 | 公开反馈文本可能含指令 | 只存文本、不直接进系统提示；分类/限长；人工审核 |
| 来源偏见 | 论文/社区/新闻偏差 | 来源多样性、可信度、冲突展示 |
| 许可证 | 论文/网页内容再分发 | 只存摘要/引用；遵守 ToS |
| 单点 | 单 VPS / Quick Tunnel | 命名隧道/域名、备份、健康检查 |
| 隐私 | 用户文档/反馈 | 不公开联系方式；最小化存储；保留期 |
| 过度宣称 | “网络大脑/自进化” | 明确边界：记忆/课程层，不是权重训练 |
| 评估污染 | 自测题来自同一卡 | 独立 gold set、人工抽检 |

---

## 8. 90 天路线图

| 阶段 | 时间 | 交付 | 成功标准 |
|---|---|---|---|
| P0 | 第 1–2 周 | typed graph + PPR 检索、评估 harness | 概念题 ≥0.80；路径可解释 |
| P1a | 第 3–4 周 | NLI/claim 对齐、冲突分类 | 冲突 F1 ≥0.75 |
| P1b | 第 5–6 周 | citation-constrained synthesis、RAGAS | 引用正确率 ≥0.90 |
| P1c | 第 6–8 周 | 课程/自测/7 天保留 | retention ≥0.90 |
| P2a | 第 9–10 周 | 3 节点真实网络、UCB 路由 | 掉线 20% 不崩；p95 可接受 |
| P2b | 第 11–12 周 | 记忆分层、覆盖剪枝、观测 | 存储/噪声下降，覆盖不降 |
| 研究 | 第 13 周+ | workspace/辩论/联邦蒸馏 | 论文级对比实验 |

---

## 9. 结论

### 9.1 与原始思路的关系

- **匹配**：物理边界判断、真实来源、记忆层持续学习、证据可追溯、不做虚假的全局训练。
- **不匹配**：关联扩散未实现、网络仍是单机、信念修正弱、工作空间/预测编码未生产化、自我进化边界窄。
- **总体**：项目走的是正确的“务实路线”，但当前是 **NBCL 记忆系统 + 网络大脑 UI**，不是完整的 NBPW。

### 9.2 最值得做的三件事

1. **把图变成检索结构**：typed graph + PPR/spreading activation；这是“association diffusion”的最小实现。
2. **把冲突检测做真**：claim 对齐 + NLI + 时间/数值/人群；这是“信念图”的可信度基础。
3. **把评估做成闭环**：RAGAS 风格指标 + 7 天保留 + 引用正确率；这是“自我进化”的证据。

### 9.3 一句话

**不要急着把“网络大脑”做得更像大脑；先把它做得更像一个可验证的图记忆系统。**  
当图能扩散、冲突能解释、学习能回测时，“网络大脑”才从隐喻变成工程。

---

## 10. 参考文献

1. Zheng et al. *Lifelong Learning of Large Language Model based Agents: A Roadmap.* arXiv:2501.07278. <https://arxiv.org/abs/2501.07278>
2. Gao et al. *A Survey of Self-Evolving Agents: What, When, How, and Where to Evolve on the Path to Artificial Super Intelligence.* arXiv:2507.21046. <https://arxiv.org/abs/2507.21046>
3. Gutiérrez et al. *HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models.* NeurIPS 2024. <https://arxiv.org/abs/2405.14831>
4. Edge et al. *From Local to Global: A Graph RAG Approach to Query-Focused Summarization.* arXiv:2404.16130. <https://arxiv.org/abs/2404.16130>
5. Wang et al. *ROGRAG: A Robustly Optimized GraphRAG Framework.* ACL 2025 Demo. <https://arxiv.org/abs/2503.06474>
6. Xu et al. *A-MEM: Agentic Memory for LLM Agents.* NeurIPS 2025. <https://arxiv.org/abs/2502.12110>
7. Packer et al. *MemGPT: Towards LLMs as Operating Systems.* arXiv:2310.08560. <https://arxiv.org/abs/2310.08560>
8. Xu et al. *Knowledge Conflicts for LLMs: A Survey.* arXiv:2403.08319. <https://arxiv.org/abs/2403.08319>
9. Es et al. *Ragas: Automated Evaluation of Retrieval Augmented Generation.* arXiv:2309.15217. <https://arxiv.org/abs/2309.15217>
10. Du et al. *Improving Factuality and Reasoning in Language Models through Multiagent Debate.* arXiv:2305.14325. <https://arxiv.org/abs/2305.14325>
11. McMahan et al. *Communication-Efficient Learning of Deep Networks from Decentralized Data.* AISTATS 2017. <https://arxiv.org/abs/1602.05629>
12. Shumailov et al. *AI models collapse when trained on recursively generated data.* Nature 631, 755–759 (2024). <https://doi.org/10.1038/s41586-024-07566-y>

# 从知识汇总到智能：网络大脑的智能工程路线

**日期**：2026-11-05  
**对象**：OpenNetBrain / `zacrisy/open-net-agent`  
**线上**：<https://zacrisy.github.io/open-net-agent/brain.html?v=17>  
**VPS**：<https://kids-pcs-attacked-myth.trycloudflare.com>

---

## 0. 结论先行

### 0.1 当前系统是什么

当前 OpenNetBrain 是一个：

> **可持续更新的语义记忆系统 + 关联检索 + 证据引用 + 信念图 + 工具集合**

它擅长：

- 找资料；
- 抽知识卡；
- 建关联；
- 检测部分冲突；
- 引用来源；
- 自动扩充主题。

它不擅长：

- 在**新任务**中自己定目标；
- 预测“下一步会发生什么”；
- 选择行动去改变世界/获取信息；
- 从少量经验中抽象出可复用规则；
- 判断自己“会不会”；
- 在网络中形成多主体的认知分工。

### 0.2 一句话

**知识卡是“记忆”，不是“智能”。智能是对记忆的控制：预测、行动、抽象、反思、评估。**

当前系统像一个**图书馆 + 索引 + 管理员**，还不是一个**会做研究的智能体**。

### 0.3 最关键的缺口

| 组件 | 当前 | 智能所需 |
|---|---|---|
| 目标 | 无（只有主题/反馈） | 任务目标、约束、预算 |
| 世界模型 | 无（只有静态卡） | 预测状态/证据/后果 |
| 行动 | 只有问答工具 | 查询、实验、追问、放弃 |
| 抽象 | 知识卡 | 概念、规则、可执行技能 |
| 元认知 | 启发式置信度 | 校准、何时求助/放弃 |
| 学习信号 | 新卡/反馈 | 预测误差、任务奖励、信息增益 |
| 评估 | 卡片/问答 | 泛化、样本效率、迁移 |
| 网络 | 单 VPS 多进程 | 多主体、分工、共识 |

---

## 1. 为什么“更多知识”不等于“更智能”

### 1.1 Chollet：智能是“技能获取效率”，不是技能本身

Chollet 在 *On the Measure of Intelligence* 中给出一个关键判断：

> 用无限先验/无限训练数据可以“买”到任意任务技能；这掩盖了系统自身的泛化能力。智能应衡量**在未知任务上获取技能的效率**。

他提出 ARC（Abstraction and Reasoning Corpus），用少量示例要求系统归纳规则并泛化。

**对本项目**：

- 当前“知识卡数量/周期数”不是智能指标；
- 当前概念题 0.67、掩码题 1.0，测的是记忆/检索；
- 真正该测的是：**给一个新领域、少量示例，系统能否自己形成规则并解决新问题**。

ARC Prize 2024 报告显示：SOTA 从 33% 提升到 55.5%，但仍远低于人类；这正说明“知识/技能”与“泛化”之间的差距。

参考：
- [Chollet, On the Measure of Intelligence](https://arxiv.org/abs/1911.01547)
- [ARC Prize 2024 Technical Report](https://arxiv.org/abs/2412.04604)

### 1.2 Legg & Hutter：智能是“在未知环境中的目标达成能力”

Legg & Hutter 把智能形式化为：

> 智能是 agent 在广泛未知环境中，最大化未来奖励/目标的能力。

关键词不是“知识”，而是：

- **agent**；
- **environment**；
- **observation**；
- **action**；
- **reward/goal**；
- **unknown environments**。

当前系统没有 environment/action/reward 闭环；它只响应 query。

参考：[Legg & Hutter, Universal Intelligence](https://arxiv.org/abs/0712.3329)

### 1.3 World Models：智能需要“在脑中预演”

Ha & Schmidhuber 的 World Models：

- 学习环境的压缩时空模型；
- 用世界模型训练 policy；
- 甚至可以在“梦”里训练，再迁移回真实环境。

当前系统没有“状态转移”：

- 知识卡是静态事实；
- 没有“如果我查 X，会发生什么/会获得什么证据”的预测；
- 没有“如果我改变剂量/人群/时间，结论会怎样”的反事实。

参考：[Ha & Schmidhuber, World Models](https://arxiv.org/abs/1803.10122)

### 1.4 Active Inference：智能是“通过行动减少预测误差”

主动推断（active inference）把感知、行动、学习统一为**最小化自由能/预测误差**：

- 预测下一步观察；
- 如果惊讶度高，选择行动获取信息；
- 行动不是被动响应，而是主动实验。

当前 AUTO 循环只是“按主题抓取”，不是“因为不确定而做实验”。

参考：
- Friston et al., *Active Inference: A Process Theory* (Neural Computation, 2017)  
  <https://doi.org/10.1162/neco_a_00912>

### 1.5 Global Workspace：智能需要“竞争与广播”

Global Workspace Theory 认为：

- 多个专门模块并行处理；
- 只有被选中的内容进入全局工作空间；
- 全局广播让其他模块协同。

当前 UI 有 “CORE / WORKSPACE” 的视觉，但没有真实的模块竞争、选择、广播。

参考：
- VanRullen & Kanai, *Deep learning and the Global Workspace Theory* (Trends in Cognitive Sciences, 2021)  
  <https://doi.org/10.1016/j.tics.2021.03.012>

### 1.6 Reflexion / Voyager：智能体通过“试错 + 反思 + 技能库”变强

- **Reflexion**：不更新权重，用语言反馈形成反思文本，存入 episodic memory，改进行动；HumanEval 91% pass@1。
- **Voyager**：自动课程 + 可执行技能库 + 自我验证；在 Minecraft 中 3.3× 独特物品、15.3× 更快解锁科技树；技能可迁移到新世界。

**对本项目**：

- 当前“学习”是学主题，不是学**技能**；
- 没有 episode（尝试→结果→反思→改进）；
- 没有可执行 skill library；
- 没有自动课程（由任务难度驱动）。

参考：
- [Reflexion](https://arxiv.org/abs/2303.11366)
- [Voyager](https://arxiv.org/abs/2305.16291)

### 1.7 JEPA / 世界模型：预测表征，而不是预测像素

LeCun 的 JEPA 路线主张：

- 在表征空间预测未来；
- 不生成每个像素；
- 用能量/预测误差驱动学习；
- 世界模型 + 规划器 + 代价模块。

这与“网络大脑”的预测编码思想一致：**传惊讶，不传原始数据**。  
参考：[A Path Towards Autonomous Machine Intelligence](https://openreview.net/forum?id=BZ5a1r-kVsf)

### 1.8 Thousand Brains：智能需要“参考系 + 感觉运动”

Thousand Brains 理论强调：

- 皮层柱学习感觉运动参考系；
- 通过运动/触摸识别物体；
- 智能来自大量“模型”的投票/共识。

当前系统没有传感器/运动，也没有参考系；它是文本世界的静态索引。

参考：<https://thousandbrains.org/papers/>

---

## 2. 智能的六个必要组件

> 不是“六个模块”就一定智能，而是缺一个都会退化成“知识库”。

### 2.1 目标 / 任务（Goal）

- 当前：用户 query，或 AUTO 主题；
- 智能：明确目标、约束、预算、成功标准；
- 例子：给定 30 分钟、20 次查询预算，写一份可引用的综述，并标出不确定处。

### 2.2 世界模型（World Model）

- 当前：静态知识卡 + 关联边；
- 智能：状态转移、因果图、反事实；
- 例子：预测“查询某个来源会降低哪条不确定性”；预测“剂量改变后结论方向”。

### 2.3 行动策略（Policy）

- 当前：固定 research 流程；
- 智能：选择 query/来源/工具/追问/实验/放弃；
- 学习信号：信息增益、任务奖励、成本。

### 2.4 抽象与技能（Abstraction / Skill）

- 当前：claim 卡；
- 智能：概念、规则、可执行程序、可复用技能；
- 例子：`compare_sources`、`design_experiment`、`verify_claim`、`synthesize_review`。

### 2.5 元认知（Metacognition）

- 当前：启发式 confidence；
- 智能：知道自己会不会、何时不确定、何时求助/放弃；
- 指标：校准误差（ECE）、拒答/求助的收益。

### 2.6 评估与课程（Evaluation / Curriculum）

- 当前：小样本概念题；
- 智能：held-out 任务、泛化、样本效率、迁移；
- 课程：从易到难，自动生成任务，失败驱动学习。

---

## 3. 当前项目的“智能度”评估

| 组件 | 当前评分（0–5） | 说明 |
|---|---:|---|
| 语义记忆 | 4 | 卡/图/来源/自动更新 |
| 关联检索 | 3 | PPR 已接入，但边是词面/规则 |
| 工具 | 3 | 研究/文档/计算/核查/摘要/翻译/抽取 |
| 目标 | 1 | 只有 query/主题，没有任务目标 |
| 世界模型 | 0.5 | 无状态转移/因果/反事实 |
| 行动策略 | 1 | 固定 pipeline，无选择/实验 |
| 抽象/技能 | 1 | 无技能库/程序合成 |
| 元认知 | 1.5 | confidence 未校准，无拒答策略 |
| 工作空间 | 1 | UI 隐喻，无模块竞争/广播 |
| 评估 | 1.5 | 小样本问答，不是泛化 |
| 网络 | 1 | 单 VPS 多进程，不是多主体 |

**综合：约 1.7–2.0 / 5，属于“记忆型知识系统”，不是“智能体”。**

---

## 4. 目标架构：从“知识库”到“研究智能体”

```
             ┌──────────────────────────────┐
             │        Task / Environment     │
             │  budget, success, constraints │
             └──────────────┬───────────────┘
                            │ observation
                            ▼
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │  Perception │───▶│ World Model │───▶│  Workspace  │
   │ sources/docs│    │ beliefs,    │    │ hypotheses, │
   │ tools       │    │ causal graph│    │ coalitions  │
   └─────────────┘    └──────┬──────┘    └──────┬──────┘
                             │ prediction       │ broadcast
                             ▼                  ▼
                      ┌─────────────┐    ┌─────────────┐
                      │   Policy    │───▶│   Action     │
                      │ query/exp/  │    │ tool/ask/   │
                      │ verify/abst │    │ abstain     │
                      └──────┬──────┘    └──────┬──────┘
                             │                  │
                             ▼                  ▼
                      ┌─────────────┐    ┌─────────────┐
                      │ Reflection  │◀───│  Outcome     │
                      │ critique    │    │ reward/surprise│
                      └──────┬──────┘    └─────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
       ┌─────────────┐              ┌─────────────┐
       │ Skill Library│              │   Memory     │
       │ executable  │              │ cards/graph  │
       └─────────────┘              └─────────────┘
```

核心闭环：

```
observe → predict → act → compare → reflect → consolidate
```

当前闭环是：

```
retrieve → extract → consolidate
```

**缺的是 predict / act / compare / reflect。**

---

## 5. 分阶段路线（Level 0–5）

### Level 0：知识汇总（当前）

- 知识卡、图、引用、AUTO；
- 指标：卡片/来源/覆盖；
- 局限：没有目标/行动/预测。

### Level 1：预测型记忆

目标：从“存事实”升级为“预测证据”。

- 输入：主题 + 当前信念；
- 预测：下一个来源/claim/冲突；
- 动作：只查询“惊讶度高”的方向；
- 指标：预测准确率、信息增益/查询成本。

**最小实验**：

- 给定前 3 条来源，预测第 4 条的主题/结论；
- 比较“随机查询”vs“按预测误差查询”。

### Level 2：目标导向的研究智能体

目标：给定任务，自己规划、执行、反思。

- 任务：`research(question, budget, citation_required)`；
- 动作：search / read / verify / compare / ask / abstain；
- 记忆：episode（尝试、结果、错误）；
- 反思：Reflexion 式文本；
- 指标：任务成功率、引用正确率、成本、样本效率。

**这是当前项目最应该先做的 Level。**

### Level 3：抽象与技能

目标：从“会查”到“会做”。

- 技能库：可执行函数/程序；
- 自动课程：难度递增；
- 组合：多技能组合解决新任务；
- 指标：新任务上的技能复用/迁移。

**实验**：

- 20 个研究任务，其中 10 个需要组合技能；
- 对比“每次重新规划”vs“复用技能库”。

### Level 4：元认知与自我改进

目标：知道自己不会，并主动学。

- 置信度校准；
- 拒答/求助策略；
- 失败驱动课程；
- 工具/技能自生成（人类 gate）；
- 指标：校准、求助收益、学习曲线。

### Level 5：网络智能

目标：多主体分工/共识/竞争。

- 不同节点有不同来源/模型/角色；
- 工作空间 coalition；
- 辩论/验证/quorum；
- 指标：多样性、相关性、共识质量、故障鲁棒。

**当前网络只是部署拓扑，不是认知网络。**

---

## 6. 具体实验设计

### 6.1 研究智能体任务集（20–50 题）

每题包含：

- 问题；
- 预算（查询次数/时间）；
- 成功标准（关键事实/引用/冲突说明）；
- gold sources；
- 评分 rubric。

对比：

1. 固定 pipeline（当前）；
2. ReAct 式 plan-act-observe；
3. + Reflexion；
4. + 世界模型/信息增益。

指标：

- task success；
- citation precision/recall；
- unsupported claims；
- queries/cost；
- p95 latency。

### 6.2 预测任务

- 从部分证据预测下一条证据；
- 预测冲突/时间更新；
- 用预测误差选择查询；
- 指标：top-k 预测准确率、信息增益/成本。

### 6.3 因果/反事实任务

- “如果剂量翻倍，结论会怎样？”
- “如果人群从成人换为儿童，结论是否仍成立？”
- 需要因果图/qualifier，不是知识卡；
- 指标：方向准确率、条件识别。

### 6.4 抽象任务（ARC 微基准）

- 20 个 ARC-AGI 风格网格任务；
- 当前检索系统预计接近 0；
- 加入程序合成/技能库后再测；
- 目的：区分“记忆”与“泛化”。

### 6.5 元认知任务

- 故意给不可回答问题；
- 测“拒答/求助”而不是胡编；
- 指标：ECE、拒答收益、错误成本。

### 6.6 技能迁移

- 训练任务：查文献、验证、比较；
- 测试任务：新领域但同结构；
- 指标：样本效率、成功率、技能复用率。

---

## 7. 对本项目代码的改造清单

### 7.1 数据层

新增：

- `tasks`：目标、预算、成功标准；
- `episodes`：观察、预测、行动、结果、反思；
- `skills`：可执行技能/程序；
- `world_model`：状态、转移、因果边；
- `evaluations`：任务评分。

保留：

- `cards` / `edges` / `feedback` 作为**语义记忆**，不丢弃。

### 7.2 模块

- `planner.py`：计划/重规划；
- `world_model.py`：预测/因果；
- `policy.py`：动作选择/信息增益；
- `skills/`：可执行技能库；
- `reflect.py`：Reflexion 式反思；
- `metacognition.py`：校准/拒答；
- `eval/`：任务与指标。

### 7.3 API/UI

- `/api/agent/run`：启动任务；
- `/api/agent/status`：计划/动作/预测/结果；
- UI 从 “Learning feed” 升级为 **Mission Control**：
  - 目标；
  - 计划；
  - 当前动作；
  - 预测 vs 实际；
  - 技能；
  - 评估。

### 7.4 不做什么

- 不承诺“全局 WAN 反向传播”；
- 不把“卡片数”当智能；
- 不做无人类 gate 的代码自修改；
- 不用自生成数据污染评估集。

---

## 8. 90 天路线

| 阶段 | 时间 | 交付 | 成功标准 |
|---|---|---|---|
| L1 | 2 周 | 预测任务 + 惊讶度查询 | 预测准确率 > baseline |
| L2 | 4 周 | 研究智能体 plan-act-reflect | 20 题任务成功率 > 固定 pipeline |
| L2+ | 6 周 | 技能库 + 自动课程 | 新任务样本效率提升 |
| L3 | 8 周 | 抽象/ARC 微基准 | 从 0 到非零泛化 |
| L3+ | 10 周 | 因果/反事实 | 方向准确率 > 随机 |
| L4 | 12 周 | 元认知/校准/拒答 | ECE 降低，错误成本降低 |
| L5 | 12 周+ | 多主体/workspace | 多样性/共识/故障鲁棒 |

---

## 9. 风险与治理

| 风险 | 说明 | 缓解 |
|---|---|---|
| 目标错配 | 自动课程追求“有趣”而非“有用” | 人类定义成功标准 |
| 反馈注入 | 公开反馈可被操纵 | 隔离、审核、限权 |
| 模型崩溃 | 自生成数据退化 | 真实数据锚点、hold-out |
| 评估污染 | 自测题来自同卡 | 独立 gold set |
| 过度宣称 | “智能”被滥用 | 用任务指标，不用卡片数 |
| 安全 | 自修改/工具滥用 | 人类 gate、沙箱、预算 |

---

## 10. 最终判断

### 10.1 当前项目的位置

- 它是一个**很好的语义记忆/知识基础设施**；
- 它的图检索、冲突检测、引用、自动学习，是智能系统的**记忆层**；
- 但它不是智能体：没有目标、世界模型、行动、抽象、元认知、评估。

### 10.2 如何实现智能

不是“再抓更多网页”，而是：

1. **选一个任务环境**（研究任务是当前最自然的）；
2. **定义目标/预算/成功标准**；
3. **建立预测-行动-比较-反思闭环**；
4. **把成功经验固化成可执行技能**；
5. **用 held-out 任务测泛化/样本效率**；
6. **让网络成为多主体分工，而不是多副本数据库**。

### 10.3 一句话

**知识卡让系统“知道”，世界模型让它“预判”，策略让它“行动”，技能让它“会做”，元认知让它“知道自己不会”，评估让它“真的变强”。**

当前项目已经完成了“知道”；下一步要做的，是让它**从知道走向会做**。

---

## 11. 参考文献

1. Legg & Hutter. *Universal Intelligence: A Definition of Machine Intelligence.* Minds & Machines, 2007. <https://arxiv.org/abs/0712.3329>
2. Chollet. *On the Measure of Intelligence.* arXiv:1911.01547. <https://arxiv.org/abs/1911.01547>
3. Chollet et al. *ARC Prize 2024: Technical Report.* arXiv:2412.04604. <https://arxiv.org/abs/2412.04604>
4. Ha & Schmidhuber. *World Models.* arXiv:1803.10122. <https://arxiv.org/abs/1803.10122>
5. LeCun. *A Path Towards Autonomous Machine Intelligence.* 2022. <https://openreview.net/forum?id=BZ5a1r-kVsf>
6. Friston et al. *Active Inference: A Process Theory.* Neural Computation, 2017. <https://doi.org/10.1162/neco_a_00912>
7. VanRullen & Kanai. *Deep learning and the Global Workspace Theory.* Trends in Cognitive Sciences, 2021. <https://doi.org/10.1016/j.tics.2021.03.012>
8. Shinn et al. *Reflexion: Language Agents with Verbal Reinforcement Learning.* arXiv:2303.11366. <https://arxiv.org/abs/2303.11366>
9. Wang et al. *Voyager: An Open-Ended Embodied Agent with Large Language Models.* arXiv:2305.16291. <https://arxiv.org/abs/2305.16291>
10. Hawkins et al. *Thousand Brains* research. <https://thousandbrains.org/papers/>

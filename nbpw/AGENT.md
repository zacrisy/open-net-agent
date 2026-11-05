# Mission Control：Level-2 研究智能体（v0.11）

## 1. 闭环

```
goal → predict → act → observe → compare → reflect → synthesize
```

不是“再抓一个主题”，而是：

- 目标：问题 + 预算；
- 预测：动作预期产出；
- 行动：search / graph / verify / synthesize / abstain；
- 观察：真实来源、图卡、验证结果；
- 比较：`surprise = |actual - predicted| / predicted`；
- 反思：来源数、覆盖率、验证数、引用完整性；
- 综合：带引用答案 + 图记忆。

## 2. 策略

`agent_loop._choose()`：

1. 无证据且还有 query → search；
2. 未做图检索 → graph；
3. 有证据但未验证 → verify；
4. 覆盖不足且还有预算 → search；
5. 否则 synthesize；
6. 无证据 → abstain。

## 3. 世界模型 v0（v0.12 升级）

- `world_model.py`：对历史 `agent_steps` 做 kNN（按 action + step 距离）；
- `bandit.py`：UCB 在允许动作中选择；
- reward = coverage 增益 + 新来源/卡数 - 成本；
- 这仍不是神经网络世界模型，但已经从“固定规则”变成“从 episode 学习”。

## 3.1 世界模型/策略评估

5 任务：agent 0.884 vs fixed 0.727（rubric 不完全对等，样本小）。

## 3.2 元认知与自动课程（v0.13）

- `metacognition.py`：ECE、abstain 阈值；
- `curriculum.py`：低保留卡生成下一题；
- API：`/api/agent/calibration`、`/api/agent/curriculum`；
- UI：NEXT TASK。

## 3.3 ARC 抽象测试

12 个玩具网格任务，程序合成 12/12；见 [`ARC.md`](ARC.md)。这是玩具 DSL，不是 ARC-AGI。

## 3.3 世界模型 v0（旧）

`predict(action)` 用历史 `agent_steps` 中该 action 的平均观察值：

- search → 平均新来源数；
- graph → 平均激活卡数；
- verify → 平均置信度；
- 无历史时用默认值。

这是**可检查的启发式预测器**，不是学习到的神经网络世界模型。它已经能产生 surprise 信号，但还没有用梯度更新。

## 4. 技能

- `search`：真实来源；
- `graph`：PPR 关联卡；
- `verify`：词面/否定核查；
- `synthesize`：引用约束综合；
- `abstain`：证据不足拒答。

`agent_skills` 记录使用次数；还不是“自动生成新技能”。

## 5. 评估（5 任务小样本）

| 任务 | Agent score | Fixed pipeline |
|---|---:|---:|
| semaglutide / gastric emptying | 0.933 | 0.746 |
| GLP-1 mechanism | 1.000 | 0.920 |
| AI agent evaluation | 1.000 | 0.920 |
| asyncio error | 0.971 | 0.671 |
| RAG metrics | 0.950 | 0.920 |
| **mean** | **0.971** | **0.835** |

**必须诚实**：

- 只有 5 个任务；
- Agent 的评分包含 coverage/verify，fixed 的评分更偏 confidence/sources，rubric 不完全对等；
- 不是人工 gold，也不是 ARC/泛化；
- 不能据此宣称“智能体已经更强”。

它证明的是：**闭环、预测、行动选择、反思、引用综合已经可运行**。

## 6. 限制

- 世界模型是历史均值，不是学习模型；
- 策略是规则，不是 RL/bandit；
- 没有任务环境（只有网页来源）；
- 没有自动技能生成；
- 没有元认知校准/拒答阈值学习；
- 没有多智能体/workspace 竞争。

## 7. 下一步

1. 50 题人工 gold + 统一 rubric；
2. 学习型世界模型（预测信息增益）；
3. 策略用 bandit/RL 选择动作；
4. 从成功 episode 固化技能；
5. ARC 微基准与因果任务。

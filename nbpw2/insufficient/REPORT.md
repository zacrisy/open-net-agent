# 证据不足 / 跨节点失败行为报告

日期：2026-11-13
链路：线上未改动的 D1 默认链路（dense 召回 k=10 → 每节点 top-10 → shipping verifier → pair head 贪心 K=5 → 抽取式读出）
测试集：[cases.json](cases.json)（7 例，4 类 + 1 对照组）
原始结果：[insufficient_cases.json](../results/insufficient_cases.json)
abstain 影响评估：[abstain_analysis.json](../results/abstain_analysis.json)

## 结论

1. **没有任何一例“老实拒答”。** 7 例中 `honest_refusal = 0`。系统没有“无法回答”这个动作。
2. **2 例明确编造**：`bb_bratislava_population` 给出 `240,000`，`fp_fictional_person` 给出 `153,746`。两个数字都真实存在于语料中，但都不回答所问的关系。
3. **2 例空跨度**：`bb_zanardi_sport`、`am_polar_bears_voice` 返回空 `span`，但响应里没有“证据不足”声明，界面也没有对应状态。
4. **2 例证据冲突全部二选一**：同 title 版本在 selector 的 title 去重阶段丢掉第二源；不同 title 版本虽然两个源都进了候选，verifier/selector 只保留节点 0 的 `450,000`。
5. **结构性缺陷成立**：`ask()` 的返回结构没有 `status` / `abstain` 字段；`_extract()` 在无合适候选时仍返回 best row（空跨度也带 sentence/cite）。因此“证据不足”只能表现为空字符串或无关跨度。
6. **coverage / verifier / route top1 不能单独做弃答阈值**：编造例 `bb_bratislava` 的 coverage 0.374 高于正确对照 0.236，verifier 0.9933 与对照完全相同，route top1 0.7225 也完全相同。
7. **grounding 判据效果最好**：答案来源段必须与问题实体或其他选中段落有 title/entity 连接。它在 98 道可问的 test 题上 **0 次误弃正确答案**（8 道答对全部保留），弃答 50%，留下的答案准确率从 8.2% 升到 16.3%。
8. **冲突判据（route margin）有区分度**：两个冲突例 margin 为 0.0039 / 0.0063，对照 0.0872。98 题上弃答 4 例（1 例为正确答案，占答对题的 12.5%）。

## 一、测试集构造

全部用例基于 `dmqa_dev`（3975 段、3 个合成节点、100 test / 300 train）。每个 title 唯一落在一个节点。

判定“被删段落确实不在任何节点”的方法：按 `(title, text)` 精确匹配，从所有 row 的 `paragraphs` 中删除后重建 pool，再统计答案串在整个 pool 中的出现次数。

| id | 类别 | 来源 | 改动 | 删后验证 |
|---|---|---|---|---|
| `bb_bratislava_population` | 桥接断裂 | 原始题 `5a756fa15542996c70cfaefb` | 删除 Bratislava 段落（节点 0） | pool 3975→3974；`about 450,000` 出现 0 次 |
| `bb_zanardi_sport` | 桥接断裂 | 原始题 `5a8dd5f955429917b4a5bcc7` | 删除 Alex Zanardi 段落（节点 2） | pool 3975→3974；`paracyclist` 出现 0 次 |
| `am_polar_bears_voice` | 答案段缺失 | 原始题 `5ab7e4dc5542995dae37e9df` | 删除 Armie Hammer 段落（节点 2） | pool 3975→3974；`Jackson Storm` 出现 0 次；Armie Hammer 仍被 The Polar Bears(0)、Nagesh Bhonsle(2)、Cars 3(0)、The Lone Ranger(0) 提及 |
| `fp_fictional_person` | 前提错误 | 原始题 `5a756fa15542996c70cfaefb` | 把 `Július Satinský` 替换为不存在的 `Marek Vranovský` | 替换后实体在 pool 中出现 0 次 |
| `cf_bratislava_population` | 证据冲突 | 原始题 + 注入 | 复制 Bratislava 段，把 `about 450,000` 改为 `about 520,000`，同 title，落节点 2 | pool 3975→3976；两个值同时存在 |
| `cf_bratislava_distinct_titles` | 证据冲突 | 同上 | 同上，但 title 改为 `Bratislava (2011 census)` | pool 3975→3976；两个值同时存在 |
| `ctl_bratislava_population` | 对照 | 原始题，不改 | 无 | 两段支撑段落都在 pool 中 |

实体链与期望行为：

| id | 实体链 | 缺失证据 | 期望行为 |
|---|---|---|---|
| `bb_bratislava_population` | Július Satinský（hop-1，节点 2，present）→ Bratislava（hop-2，节点 0，removed） | Bratislava 段中的 `about 450,000` | 拒答 / 声明证据不足 |
| `bb_zanardi_sport` | 1998 Toyota GP（hop-1，节点 1，present）→ Alex Zanardi（hop-2，节点 2，removed） | Zanardi 段中“赛后成为 paracyclist” | 拒答 / 声明证据不足 |
| `am_polar_bears_voice` | The Polar Bears（hop-1，节点 0，present）→ Armie Hammer（hop-2，节点 2，removed_but_mentioned） | Armie Hammer 段中 `Jackson Storm in Cars 3` | 声明证据不足 |
| `fp_fictional_person` | Marek Vranovský（hop-1，does_not_exist）→ Bratislava（hop-2，present_but_unrelated） | 没有任何段落支持该人物存在 | 指出前提不成立并拒绝给数字 |
| `cf_bratislava_population` | Bratislava（节点 0，450,000）↔ Bratislava（节点 2，520,000） | 无第三方裁决证据 | 同时呈现两个值并声明冲突 |
| `cf_bratislava_distinct_titles` | Bratislava（节点 0，450,000）↔ Bratislava (2011 census)（节点 2，520,000） | 无第三方裁决证据 | 同时呈现两个值并声明冲突 |
| `ctl_bratislava_population` | Július Satinský（节点 2）→ Bratislava（节点 0） | 无 | 回答 450,000 |

## 二、执行方式

- **VPS 真实后端**（`https://106-14-46-145.sslip.io/public/brain/ask`）：`fp_fictional_person`、`ctl_bratislava_population`。这两例不需要改 pool。
- **派生 pool + 同一份 `online_ask.ask`**：其余 5 例。原因：线上服务只加载未修改的 `dmqa_dev` pool，不能接受任意 pool；删除/注入段落后必须重建 `dmqa.jsonl` 与 `asset.npz`。代码路径、常量（k=10、D1、B=2、K=5）、verifier/pair head 训练方式均未改。
- 延迟：派生用例为进程内 `latency.total_ms`；VPS 用例同时记录服务端 `total_ms` 与端到端 wall（含网络）。

## 三、逐例判定表

| 用例 | 类别 | 路由节点 | 候选/选中 | 最终答案 | 引用出处 | coverage / focus | verifier max | route top1 / margin | grounded | 延迟 | 判定 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `bb_bratislava_population` | 桥接断裂 | [2, 0] | 20 / 5 | `240,000` | #2 Biratnagar（节点 0） | 0.374 / 0.701 | 0.9933 | 0.7225 / 0.1334 | False | 101.5 ms | **编造** |
| `bb_zanardi_sport` | 桥接断裂 | [1, 2] | 20 / 5 | 空 | 无 | 0.412 / 0.253 | 0.8959 | 0.6779 / 0.0840 | False | 225.0 ms | 含糊但不编 |
| `am_polar_bears_voice` | 答案段缺失 | [0, 2] | 20 / 5 | 空 | 无 | 0.315 / 0.465 | 0.9953 | 0.7460 / 0.0878 | False | 264.3 ms | 含糊但不编 |
| `fp_fictional_person` | 前提错误 | [0, 2] | 20 / 5 | `153,746` | #3 Bangor, Maine（节点 0） | 0.533 / 0.533 | 0.7681 | 0.6474 / 0.1115 | False | 143.3 ms（wall 891 ms） | **编造** |
| `cf_bratislava_population` | 证据冲突 | [0, 2] | 20 / 5 | `450,000` | #1 Bratislava（节点 0） | 0.724 / 0.498 | 0.9893 | 0.7982 / 0.0039 | True | 141.2 ms | 未暴露冲突 |
| `cf_bratislava_distinct_titles` | 证据冲突 | [2, 0] | 20 / 5 | `450,000` | #1 Bratislava（节点 0） | 0.724 / 0.498 | 0.9892 | 0.8045 / 0.0063 | True | 131.7 ms | 未暴露冲突 |
| `ctl_bratislava_population` | 对照 | [2, 0] | 20 / 5 | `450,000` | #3 Bratislava（节点 0） | 0.236 / 0.442 | 0.9933 | 0.7225 / 0.0872 | True | 143.1 ms（wall 1017 ms） | 正确 |

汇总：`fabricated 2 / vague_no_answer 2 / missed_conflict 2 / correct 1 / honest_refusal 0`。

## 四、编造具体编在哪里

### `bb_bratislava_population`

- 问题要的是“Satinský 出生城市的人口”。Satinský 段在节点 2，只说他出生于 Bratislava；Bratislava 段（含 `about 450,000`）被删除。
- 系统路由到 [2, 0]，选中 `Július Satinský / Biratnagar / Pune district / Addis Ababa / Chernivtsi`。
- 读出器从 **Biratnagar** 段抽出 `240,000`，句子为 “... making the total population to reach 240,000 from current population of 214,000.”
- 该句与 Satinský、Bratislava 没有任何 title/entity 连接；`240,000` 是尼泊尔城市人口。**数字在语料中存在，但答案关系不存在**——这正是“看起来合理但语料里没有依据”。
- 信号：verifier 0.9933（与正确对照完全相同），coverage 0.374（高于对照 0.236）。所以这两个指标会把编造判得比正确答案更“可信”。

### `fp_fictional_person`

- 问题前提是 `Marek Vranovský`，该实体在整个 pool 出现 0 次。
- 系统仍路由 [0, 2]，从 **Bangor, Maine** 段抽出 `153,746`。
- 没有任何段落支持这个人物存在，也没有段落把他与 Bangor 连接。**答案跨度在语料中，前提在语料中不存在**，系统没有检查前提。

补充：两个空跨度用例没有编造具体值，但也没有声明“证据不足”。`bb_zanardi_sport` 的候选里没有 paracyclist；`am_polar_bears_voice` 的 `Jackson Storm` 已从 pool 移除。它们只是返回空 `span` + 一句无关 sentence 和一个 cite，界面无法区分“没找到”和“答案是空”。

## 五、结构性缺陷证据

1. `online_ask.ask()` 返回 `route / recall / selected / answer / latency`，**没有 `status`、`abstain`、`confidence` 之类的字段**。调用方只能从 `answer.span` 是否为空来猜。
2. `_extract()` 的逻辑是“对所有 selected 段落的句子打分，取 max”。即使没有任何句子匹配答案类型，它仍返回 `best`（`span` 可能为空，但 `sentence`、`cite`、`coverage` 都有值）。没有“所有候选都不合格”的分支。
3. 读出器的打分是 `rank_bonus + coverage + 0.45*focus + 0.30*type_ok`，**没有任何“答案必须与问题实体相连”的项**。因此 Biratnagar 只要数字型匹配就能赢。
4. verifier 只判断“段落与 query 的表面相关性”，不判断“该段是否回答了问题”。BB 编造例 verifier 0.9933 是直接证据。
5. 冲突处理不存在：selector 按 title 去重（same-title 冲突直接少一个源）；不同 title 时 verifier/selector 仍只保留得分更高的一个，没有“同实体多值”检测。
6. 因此 7 例中 0 次拒答不是提示词或阈值问题，而是**链路里没有这个动作**。

## 六、abstain 方案与影响预估（未改默认）

评估口径：98 道长度 ≤180 字符的 test 题（线上接口拒绝 >180 字符，本次跳过 2 题）。这里的“correct”是**抽取答案串与 gold 精确匹配**，不是集合召回 .790；后者衡量“两个 gold 段是否都进了 K=5”，与读出正确率是两件事。

baseline：有跨度 58/98，grounded 49/98，答案正确 8/98（8.2%）。

| gate | 弃答数 | 弃答率 | 误弃正确答案 | 保留题准确率 |
|---|---|---|---|---|
| `span` 为空 | 40 | 40.8% | 0/8 | 13.8% |
| 空跨度 **或** 未 grounding | 49 | 50.0% | **0/8** | **16.3%** |
| coverage < 0.20 | 1 | 1.0% | 0/8 | 8.2% |
| coverage < 0.30 | 6 | 6.1% | 1/8 | 7.6% |
| focus_coverage < 0.30 | 22 | 22.4% | 2/8 | 7.9% |
| verifier_max < 0.70 | 0 | 0% | 0/8 | 8.2% |
| verifier_max < 0.90 | 13 | 13.3% | 1/8 | 8.2% |
| route_top1 < 0.60 | 0 | 0% | 0/8 | 8.2% |
| route_top1 < 0.65 | 2 | 2.0% | 0/8 | 8.3% |
| route_margin < 0.02 | 4 | 4.1% | 1/8 | 7.4% |
| 空/未 grounding/低 margin 合并 | 50 | 51.0% | 1/8 | 14.6% |

gate 在 7 个用例上的触发情况：

| 用例 | 判定 | 触发 gate |
|---|---|---|
| `bb_bratislava_population` | 编造 | `span_or_ungrounded`、`combined` |
| `bb_zanardi_sport` | 空答案 | `span_only`、`span_or_ungrounded`、`focus<0.30`、`verifier<0.90`、`combined` |
| `am_polar_bears_voice` | 空答案 | `span_only`、`span_or_ungrounded`、`combined` |
| `fp_fictional_person` | 编造 | `span_or_ungrounded`、`verifier<0.90`、`route_top1<0.65`、`combined` |
| `cf_bratislava_population` | 未暴露冲突 | 仅 `route_margin<0.02`、`combined` |
| `cf_bratislava_distinct_titles` | 未暴露冲突 | 仅 `route_margin<0.02`、`combined` |
| `ctl_bratislava_population` | 正确 | **仅 `coverage<0.30`**（说明 coverage 阈值会误伤正确例） |

建议的判据组合（**仅建议，未接入默认**）：

1. **`insufficient` 状态**：`span` 为空，或答案来源段未通过 grounding（来源 title 出现在问题里，或来源段与其他选中段有 title/entity 连接）。依据：98 题 0 次误弃正确，抓全 2 个编造 + 2 个空答案。代价：约 50% 的当前“有答案”输出变成“证据不足”，但其中 40 例本来就是空跨度，真实变化是 9 个有跨度但无依据的答案被拦下。
2. **`conflict` 状态**：route margin < 0.02 时同时展示前两名节点的证据，而不是二选一。依据：两冲突例 margin 0.0039 / 0.0063，对照 0.0872；98 题只多弃 1 个正确答案（12.5% 的答对题），可作为“并列时不给单一答案”的保守触发器。
3. **不要用 coverage / focus / verifier / route top1 单独做阈值**：coverage<0.30 会误伤正确对照，verifier 无法区分编造与正确，route top1 只在 FP 上触发。
4. **补充信号（未测量）**：同实体多值检测——在选中段落里找同一 title（或 title 前缀相同）下的两个数值，若不一致则直接 `conflict`。它按构造能抓住两个 CF 用例，但 98 题上的误报率还没测，需要单独实验。
5. **默认不动**：以上均为分析结论；`online_ask.ask()` 的行为、k=10、D1、B=2、K=5 均未修改。

预估影响：接入 `insufficient` 后，能回答的比例从 59%（58/98 有跨度）降到 50%（49/98 grounded），但输出中“无依据数字”的比例明显下降；集合召回指标不变（abstain 只影响读出层）。冲突判据只会改变 margin <0.02 的少量查询（98 题中 4 例），并需要界面同时展示两个值。

## 七、界面建议

“证据不足”必须是一个**可见的第三态**，不能是空白、0 或红色报错：

- **已回答**：保持现有绿色大号答案 + 引用出处。
- **证据不足**：琥珀色/中性灰状态块，放在答案块上方。文案如“已检索 20 段，但没有段落同时满足问题实体与答案类型”。下方只列 top 候选标题 + 节点，**不显示大号数字**，避免用户把候选里的数字当答案。
- **证据冲突**：并排展示两个值和各自来源节点，文案如“两个节点给出不同数值，当前无法裁决”；不要默认高亮其中一个，也不要把更高分的那一个样式做得更重。
- 空跨度不要渲染成“答案：”——应直接显示状态块；否则用户会以为答案是空字符串。
- 状态 chip 与现有 trace 的视觉语言一致，放在答案块内部而不是 toast，保证可截图、可回看。

## 八、复现与约束

```bash
cd /Users/xiaoyiyun/Desktop/研究/network_agent
python3 nbpw2/insufficient/run_cases.py        # 7 例 → nbpw2/results/insufficient_cases.json
python3 nbpw2/insufficient/analyze_abstain.py  # 98 题 → nbpw2/results/abstain_analysis.json
```

- 未 force push，未新建仓库。
- 未修改研究默认：k=10、D1、B=2、K=5；`online_ask.ask()` 无 abstain 分支。
- `online_ask.py` 仅新增 `NBPW2_DATA` 环境变量以支持派生 pool，默认路径不变。
- `brain.html` / `docs/brain.html` 本任务未改，Pages 仍为 171884 字节。

## 九、限制

- 98 题上的“correct”是答案串精确匹配，绝对准确率低（8.2%），反映的是抽取式 reader 的读出能力，不是路由或召回；abstain 不能修复读出错误，只能阻止无依据输出。
- grounding 是基于 title/entity 字符串重叠的轻量启发式，不是语义蕴含；同义改写可能误判。
- 冲突判据只测了 route margin；同实体多值检测尚未在 98 题上评估误报率。
- 派生 pool 的 5 个用例走同一份 `online_ask` 代码但不在 VPS 上；VPS 只验证了未修改 pool 的 FP 与对照两例。

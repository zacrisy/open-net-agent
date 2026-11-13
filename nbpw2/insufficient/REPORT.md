# 证据不足 / 跨节点失败行为报告

日期：2026-11-13
链路：线上未改动的 D1 默认链路（dense 召回 k=10 → 每节点 top-10 → shipping verifier → pair head 贪心 K=5 → 抽取式读出）
测试集：[cases.json](cases.json)（7 例，4 类 + 1 对照组）
原始结果：[insufficient_cases.json](../results/insufficient_cases.json)
三态影响评估：[abstain_analysis.json](../results/abstain_analysis.json)
弃答构成拆分：[abstain_decomposition.json](../results/abstain_decomposition.json)

## 结论

1. **弃答构成：(b) 占 100%。** 46 道 `insufficient` 中，(a) 语料没有答案 = 0，(c) 判据误杀 = 0，(b) 抽取/检索失败 = 46。用户担心的“把抽取弱点包装成诚实的不知道”成立。
2. **(b) 内部也不是检索问题。** 27/46（58.7%）的 gold 答案**字面就在选中的段落里**，只是读出不支持该答案形式（19 道 qtype 被判 `other` 无输出分支，8 道 yes/no）；再加 10 道 span 抽偏，共 37/46（80.4%）的答案已在选中全文里而读出失败。只有 9/46（19.6%）是支撑段没进 K=5（b2）。
3. **三态已进入默认链路。** `online_ask.ask()` 直接返回 `status`（`answered` / `insufficient` / `conflict`）、`route_margin`、`answer.rejected`、`answer.options`；不再是脚本分支。
4. **三组数（98 题）**：弃答 46（46.9%）+ 冲突 4（4.1%），answered 48；**answered 子集准确率 7/48 = 14.6%**；**98 题整体 7/98 = 7.1%**。旧链路是 8/98 = 8.2%。覆盖率减半、精确率翻倍，但绝对答对数 8→7，**整体准确率反而下降 1.1 个百分点**。
5. **降级规模**：原来 58 道有跨度的题里，9 道（15.5%）被降为 `insufficient`，其中原本答对 0 道；另有 1 道转 `conflict`（`Teen Titans`，旧口径按子串匹配算“对”）。所以 answered 从 58 变成 48。
6. **7 例重跑全部按预期**：4 例 `insufficient`（含 2 个原编造例）、2 例 `conflict` 双源、1 例对照 `answered`；`fabricated = 0`。
7. **conflict 不是免费的**：它把 1 道原本算对的题移出 answered。但 4 道 conflict 中没有一道能证明“并列值中哪个正确”，并列展示比默认选一个更诚实。
8. **单阈值 gate 仍不能用**：coverage / focus / verifier / route top1 在 98 题上要么误伤正确对照，要么区分不了编造（详见第七节）。
9. **界面三态已上线**：insufficient 琥珀块、不显示大号数字；conflict 两个值并排、中性色、不默认高亮；空跨度不渲染成“答案：”。

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

汇总（**上线前三态的历史判定**）：`fabricated 2 / vague_no_answer 2 / missed_conflict 2 / correct 1 / honest_refusal 0`。上线后同一批用例的重跑结果见第七节：4 例 `insufficient`、2 例 `conflict`、1 例 `answered`，`fabricated 0`。

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

## 六、弃答构成拆分（生产三态口径）

上线前的 49 是这个 gate 的估算值（240 字符 snippet grounding）。生产三态用整段文本做 grounding，并把低 margin 单列为 `conflict`，因此在同一批 98 题上得到：**`insufficient` 46 道 + `conflict` 4 道 = 50 道非 answered**。下面拆的是这 46 道 `insufficient`；4 道 `conflict` 见第七节。

| 类别 | 数量 | 占弃答 | 说明 |
|---|---|---|---|
| (a) 语料里确实没有答案 | **0** | 0% | 46 道的 gold 支撑段全部在 pool 中（`support_in_pool = True`） |
| (b) 有答案但抽取失败 | **46** | **100%** | |
| ├ b1a：qtype=`other`，读出不产生 span | 19 | 41.3% | gold 字面在选中段落全文里，但 `_extract` 没有 `other` 分支 |
| ├ b1b：有 span 分支但空/抽偏 | 10 | 21.7% | 3 道空 span，7 道抽到别的值 |
| ├ b2：支撑段没进 K=5 | 9 | 19.6% | gold 在支撑段全文里，但支撑段未被选中 |
| └ b3：yes/no 不可抽取 | 8 | 17.4% | 抽取式读出不支持 yes/no |
| (c) 判据误杀 | **0** | 0% | 46 道里 `correct = 0`，没有“抽对了却被拦” |

qtype 分布：`other` 33、`date` 5、`entity` 4、`number` 3、`person` 1。`other` 占 71.7%。

**关键结论：**

- **(b) 占比 100%，(a) 与 (c) 都是 0。** 这批弃答不是“语料里没有”，而是抽取/读出失败。
- **37/46（80.4%）的 gold 答案已经在选中的段落全文里**（b1a 19 + b1b 10 + b3 8），读出仍然没给出来。
- **27/46（58.7%）是“读出器没有这种答案形式的分支”**（b1a 19 + b3 8）。把这类标成“证据不足”，等于把读出的结构性缺陷包装成“诚实的不知道”。
- 真正属于检索/选择失败（b2）只有 9 道，19.6%。

### 抽样人工核对（12 例）

| id（前 10 位） | 类 | qtype | gold | 旧 span | 逐例判据与理由 |
|---|---|---|---|---|---|
| `5ab48c3255` | b1a | other | `Essex` | 空 | 问“Harold Godwinson 葬在哪个 county”。选中含 `Waltham Abbey Church`，其全文有 `Essex`；问句被判 `other`，读出直接返回空。答案在选中文本里，读出不取。 |
| `5ab3306a55` | b1a | other | `Walt Disney Productions` | 空 | 两部电影的共同制片公司。选中含 `The Boatniks`、`The Great Locomotive Chase`，两段全文都写了 `Walt Disney Productions`；`other` 无分支，返回空。 |
| `5a7b46e555` | b1a | other | `Ordos City` | 空 | 选中含 `Spaceware Sky Vision II` 与 `Ordos City`，答案字面在段内；问句是“which subsidiary…”，被判 `other`，不产生 span。 |
| `5a8eea4a55` | b1b | date | `between the 8th and 16th centuries` | 空 | qtype=date 有分支，但正则只认 4 位年份，`between the 8th and 16th centuries` 这种世纪区间抽不出来；gold 就在选中段 `Old Frisian` 里。属于**答案格式不匹配**。 |
| `5aba9e2455` | b1b | date | `1909` | 空 | 选中含 `Ann Wigmore`，段内有人物生年 1909，但 date 分支在打分时输给了别的句子，返回空；不是缺语料。 |
| `5a87ab9055` | b1b | number | `3,677 seated` | `1,400` | 选中含 `Androscoggin Bank Colisée`，也含 `Dwyer Arena`；读出从错误段落抽了 `1,400`。**典型 span 抽偏**，两种数字格式本身可归一化，不是格式问题。 |
| `5a77cb5e55` | b2 | other | `Kodos` | 空 | 支撑段 `Kang and Kodos` 没进 K=5（选中是 `Dan Castellaneta`、`Krusty the Clown` 等）；答案在支撑段全文里，但读出候选文本里没有。 |
| `5a8e3ea955` | b2 | other | `Greenwich Village, New York City` | 空 | 支撑段 `Adriana Trigiani` 未入选，选中只有 `Big Stone Gap (film)` 等；答案在未入选段落里。 |
| `5a7bae2055` | b2 | other | `Ryan Seacrest` | 空 | 支撑段 `American Idol (season 12)` 未入选，选中含 `Nicki Minaj` 等；答案在未入选段落里。 |
| `5a8c556955` | b3 | other | `yes` | 空 | 两段人物页都在选中里（`Gerry Marsden`、`Daryl Hall`），共享“音乐人”属性成立；读出没有 yes/no 分支。 |
| `5ae25ed155` | b3 | other | `no` | 空 | `Sorbaria` 与 `Goldenrod` 都在选中里，但一个是属、一个不是同一属；需要判断，读出没有 yes/no 分支。 |
| `5ab9812d55` | b3 | other | `no` | 空 | `Mauritz Stiller` 与 `Johannes Grenzfurthner` 都在选中里，国籍不同；同样卡在答案形式上。 |

关于 (c)=0：数字格式差异（如 `1,462` vs `1462`）在 `_correct` 里先做非数字剥离再比较，因此不会被误判为错；这批里也没有“抽对却被 gate 拦下”的样本。gate 的误杀代价不在这里，而在第七节的降级统计（9 道有跨度题被降级，原本答对 0 道）。

## 七、三态实现与验证数据

评估口径：98 道长度 ≤180 字符的 test 题（线上接口拒绝 >180 字符，本次跳过 2 题）。这里的“correct”是**抽取答案串与 gold 精确匹配**，不是集合召回 .790；后者衡量“两个 gold 段是否都进了 K=5”，与读出正确率是两件事。

### 三组数

| 指标 | 值 |
|---|---|
| `answered` | 48 |
| `insufficient` | 46（46.9%） |
| `conflict` | 4（4.1%） |
| 非 answered 合计 | 50（51.0%） |
| **answered 子集准确率** | **7/48 = 14.6%** |
| **98 题整体准确率** | **7/98 = 7.1%** |
| 旧链路（无三态）整体 | 8/98 = 8.2% |
| 58 道有跨度题 → `insufficient` | 9（15.5%），原本答对 0 |
| 58 道有跨度题 → `conflict` | 1（原按子串匹配算“对”） |

把三组数放在一起看：弃答率 46.9%，answered 子集 14.6%，整体 7.1%。**只报 14.6% 会掩盖覆盖率下降**；只报 7.1% 会掩盖“剩下的输出更干净”。两个都必须报。整体准确率比旧链路低 1.1 个百分点，原因是 conflict 把 `Teen Titans` 那道移出了 answered；如果只算 insufficient 的影响，整体仍是 8/98，因为 9 道降级题里没有一道原本答对。

同时必须承认：**三态没有提升绝对答对数**。48 道 answered 里仍有 41 道是错的，这些是读出能力问题（span 抽偏、问句类型判错），三态只是不再把 46 道无依据输出当成答案。

### 三态判据（已进 `online_ask.ask()` 默认返回）

1. **`answered`**：有 span，且通过 grounding。
2. **`insufficient`**：span 为空，**或**答案未 grounding。grounding 判据不是只看 span 是否为空，而是要求来源段与问题/其他选中段存在连接：
   - 来源 title 出现在问题里；或
   - 来源 title 出现在另一个选中段的正文里；或
   - 另一个选中的 title 出现在来源段正文里；或
   - 问题中的大写实体出现在来源段正文里。
3. **`conflict`**：route margin < 0.02，且能取到前两名节点的证据。对 top-2 路由节点，各取 recall 里 title 与答案来源 title 相交的最高排名段，用同一 `_extract` 抽值，两个值并列返回，不默认高亮其一。

返回结构：

```json
{
  "status": "answered | insufficient | conflict",
  "route_margin": 0.0868,
  "answer": {
    "status": "...", "span": "", "sentence": "", "cite": 0,
    "grounded": false,
    "rejected": {"span": "240,000", "source_title": "...", "source_node": 0},
    "options": [{"node": 0, "name": "节点 A", "title": "...", "value": "..."}]
  }
}
```

`insufficient` 与 `conflict` 时 `span` 一律为空，原抽取跨度放进 `rejected`，避免调用方误把被拦下的值当答案。

### 7 例重跑（已部署到 VPS 后）

| 用例 | 期望 | 实际 status | 输出 | 判定 |
|---|---|---|---|---|
| `bb_bratislava_population` | 拒答 | `insufficient` | 空；`rejected.span=240,000` 不展示为答案 | ✅ `declared_insufficient` |
| `bb_zanardi_sport` | 拒答 | `insufficient` | 空 | ✅ `declared_insufficient` |
| `am_polar_bears_voice` | 拒答 | `insufficient` | 空 | ✅ `declared_insufficient` |
| `fp_fictional_person` | 拒答 | `insufficient` | 空；`rejected.span=153,746` 不展示为答案 | ✅ `declared_insufficient` |
| `cf_bratislava_population` | 双源 | `conflict` | 节点 A `450,000` / 节点 C `520,000` | ✅ `exposed_conflict` |
| `cf_bratislava_distinct_titles` | 双源 | `conflict` | 节点 C `520,000` / 节点 A `450,000` | ✅ `exposed_conflict` |
| `ctl_bratislava_population` | 回答 | `answered` | `450,000` | ✅ `correct` |

汇总：`declared_insufficient 4 / exposed_conflict 2 / correct 1 / fabricated 0`。

### 单阈值 gate 的对照（仍不采用）

| gate | 弃答数 | 弃答率 | 误弃正确答案 | 保留题准确率 |
|---|---|---|---|---|
| `span` 为空 | 40 | 40.8% | 0/8 | 13.8% |
| 空跨度 **或** 未 grounding | 49 | 50.0% | **0/8** | 16.3% |
| coverage < 0.20 | 1 | 1.0% | 0/8 | 8.2% |
| coverage < 0.30 | 6 | 6.1% | 1/8 | 7.6% |
| focus_coverage < 0.30 | 22 | 22.4% | 2/8 | 7.9% |
| verifier_max < 0.90 | 13 | 13.3% | 1/8 | 8.2% |
| route_top1 < 0.65 | 2 | 2.0% | 0/8 | 8.3% |
| route_margin < 0.02 | 4 | 4.1% | 1/8 | 7.4% |

结论不变：coverage<0.30 会误伤正确对照（`ctl` 的 coverage 0.236），verifier 无法区分编造与正确（BB 编造例 0.9933，与对照相同），route top1 只在 FP 上触发。三态只采用 grounding + route margin，其余信号不参与弃答。


## 八、界面三态（已上线）

`brain.html`（同步 `docs/brain.html`）的 `renderLive()` 已按 `d.status` 分三支渲染，CSS 新增 `.aans-insufficient` / `.aans-conflict` / `.aans-tag`：

- **`answered`**：绿色左边框 + 大号答案数字 + 句子 + 出处（节点、title、覆盖率）。
- **`insufficient`**：琥珀色左边框块，顶部 `INSUFFICIENT · 证据不足` 标签，**不渲染大号数字**，只列本轮选中的候选标题与节点；若有被拦下的跨度，以 `已拦下未通过 grounding 的候选跨度：…` 的小字附在底部，不放进答案位。
- **`conflict`**：紫色左边框块，顶部 `CONFLICT · 证据不一致`，两个节点的值用等宽、同字号、同文字色并排卡片展示，标题里只写节点名与 title，不默认高亮其一；margin 写在上方说明里。
- 空跨度永远不会进入 `answered` 分支，因此不会渲染成“答案：”或空字符串。
- 若旧后端没有 `status` 字段，前端回退为 `a.span ? answered : insufficient`。

### 线上实测

部署后（见第九节）在第 98 题集合的真实问题上各触发一次，并抓取渲染 DOM：

| 状态 | 线上问题 | 后端返回 | 页面表现（抓 DOM） |
|---|---|---|---|
| `answered` | Satinský 出生城市人口题 | `status=answered`，span `450,000` | `.aans.aans-answered`；含 `ANSWERED`、大号 `450,000`、出处 `#2 · 节点 A · Bratislava` |
| `insufficient` | 虚构人物 Vranovský 出生城市人口题 | `status=insufficient`，`rejected.span=153,746` | `.aans.aans-insufficient`；无 `<b>` 大号值；候选 `#1 Chernivtsi / #2 Criss Angel / #3 Bangor, Maine / #4 Bratislava / #5 Strasbourg`；小字“已拦下未通过 grounding 的候选跨度：153,746（Bangor, Maine）” |
| `conflict` | Teen Titans 配音/播出地题 | `status=conflict`，两个 option | `.aans.aans-conflict`；两张卡并排：`节点 A · Teen Titans (season 4) / Cartoon Network`、`节点 C · The Voice Teens (Philippine TV series) / Philippine`；两值计算色均为 `#d9e8f4`，无高亮差异 |

原始返回可用以下命令复核：

```bash
curl -s -X POST https://106-14-46-145.sslip.io/public/brain/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Július Satinský was born in a city that has a current population of about how many people?"}'
```

## 九、复现与部署

```bash
cd /Users/xiaoyiyun/Desktop/研究/network_agent
python3 nbpw2/insufficient/decompose_abstains.py  # 46 题 → nbpw2/results/abstain_decomposition.json
python3 nbpw2/insufficient/run_cases.py           # 7 例 → nbpw2/results/insufficient_cases.json
python3 nbpw2/insufficient/analyze_abstain.py     # 98 题 → nbpw2/results/abstain_analysis.json
./deploy/vps_deploy_brain.sh 106.14.46.145        # 同步后端并重启
```

- 未 force push，未新建仓库。
- 研究默认保持不变：k=10、D1、B=2、K=5；三态只改变读出层的返回结构与展示，不改路由/召回/选择参数。
- `online_ask.py` 仅新增 `NBPW2_DATA` 环境变量以支持派生 pool，默认路径不变。
- 后端已部署到 VPS（`systemctl is-active opennetbrain` → active），`/public/brain/health` 返回 `ready: true`。
- Pages 推送 `docs/brain.html` 后记录 commit hash 与字节数（见提交回报）。

## 十、限制

- 98 题上的“correct”是答案串精确匹配，绝对准确率低（旧链路 8.2%，三态后整体 7.1%），反映的是抽取式 reader 的读出能力，不是路由或召回；三态不能修复读出错误，只能阻止无依据输出。
- 46 道 `insufficient` 里 37 道的 gold 就在选中段落中（b1a/b1b/b3），说明当前最大的短板是**读出没有覆盖答案形式**，不是检索；下一步应优先补 `other`/yes-no/区间型读出，而不是继续收紧 gate。
- grounding 是基于 title/entity 字符串重叠的轻量启发式，不是语义蕴含；同义改写可能误判。
- 冲突判据只测了 route margin；同实体多值检测尚未在 98 题上评估误报率。线上未修改 pool 里，部分 conflict 问题的两个 option 只有标题、没有可抽取的值，此时前端会显示“未抽出值”。
- 派生 pool 的 5 个用例走同一份 `online_ask` 代码但不在 VPS 上；VPS 上用未修改 pool 验证了 7 例中的 FP 与对照两例，其余 5 例在本地派生 pool 上验证。

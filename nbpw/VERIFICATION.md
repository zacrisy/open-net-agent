# P1 验证与保留（v0.9）

## 1. 新卡 vs 历史库对账

原来 `build_belief` 只在新批次内部比较，所以真实来源冲突长期为 0。

现在 `brain.reconcile(new_cards)`：

- 把新卡与历史卡库按 topic 对比；
- 区分冲突类型：
  - `negation`：否定/反义；
  - `numeric`：数字/剂量/比例不同；
  - `temporal`：年份/时间不同；
  - `population`：人群/物种不同；
  - `definition`：定义不同；
- 用 `score()`（来源信任 + 置信度 + 时间 + 支持度）选 active；
- 写入 `contradicts:<type>` 边，保留双方来源；
- 不删除旧卡，只标 `disputed`。

VPS 实测：**disputed = 1**，说明历史库对账开始工作。

## 2. 引用完整性

`agent_core.citation_report()` 检查：

- 引用数量 `[n]` / `[M#]`；
- 越界引用；
- 没有引用的 bullet。

VPS 实测（research）：

```json
{"refs": 8, "sources": 10, "bad_refs": [], "unsupported": 0, "ok": true}
```

说明当前答案的每个 bullet 都有引用，且没有越界引用。注意：这只检查“有没有引用”，不检查“引用是否真的支持该句”，后者需要 NLI/faithfulness。

## 3. 课程 / 自测 / 保留

`brain.self_test(n)`：

- 从知识卡生成掩码题；
- 用图检索回查；
- 记录是否正确到 `quiz` 表；
- `retention()` 返回总体/最近 100 题正确率。

VPS 实测：

```json
{"n": 5, "correct": 5}
{"n": 5, "correct": 5, "rate": 1.0, "recent": 1.0}
```

**必须诚实**：5 道题、同一批卡、掩码检索，难度很低；1.0 不能证明长期保留。它只证明“自测管线工作”。

## 4. 当前限制

- 冲突检测仍是规则式，不是 NLI；
- 数值/时间/人群需要更细的结构化 claim；
- 引用检查不验证语义支持；
- retention 样本太小，需要 1h/1d/7d 延迟测试；
- 没有独立人工 gold set。

## 5. 下一步

1. 100–300 组人工冲突/关联 gold；
2. NLI + 数值/时间一致性；
3. 7 天保留与遗忘曲线；
4. citation faithfulness（断言级）。

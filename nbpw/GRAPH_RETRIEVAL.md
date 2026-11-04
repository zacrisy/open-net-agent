# Graph Retrieval（v0.8）：typed graph + PPR 关联扩散

## 实现

- 节点：知识卡；
- 边：`supports`（语义支持）、`contradicts`（冲突）、`same_topic`（弱连接）；
- 查询：IDF 加权词面种子 → Personalized PageRank → 一跳邻居扩展；
- 输出：激活卡片、种子、边数、路径分数；
- API：`GET /api/brain/retrieve?q=...&k=5`；
- 问答：research 结果会追加“关联知识卡（图谱扩散）”，并写入 `trace.graph`。

## 合成诊断（57 卡）

| 测试 | Flat | PPR |
|---|---:|---:|
| Masked top-1 | 1.00 | **1.00** |
| Multi-hop cover@3 | 1.00 | **0.95** |
| Association top-3 | 0.20 | **0.20** |

说明：

- masked/multihop 中 flat 本身已接近满分，不能证明图扩散优势；
- association 是“查询 A，期望通过图边找到 B”，两者都是 0.20；这轮合成诊断没有证明 PPR 优势；
- 样本只有 20 对边，且为合成诊断，不是人工 gold benchmark。

## 限制

- 边仍以词面 Jaccard + 规则冲突为主，不是实体/关系抽取；
- 没有 NLI/时间/数值一致性；
- 57 卡规模太小，PPR 参数需要在大图上重调；
- 需要 100–300 组人工 gold 关联对才能下结论。

## 下一步

1. 实体/关系 typed graph；
2. 人工 gold benchmark；
3. PPR + rerank + citation-constrained synthesis；
4. 7 天保留与 citation precision。

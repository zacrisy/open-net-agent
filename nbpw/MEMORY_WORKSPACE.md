# P2 记忆生命周期与 Workspace（v0.10）

## 1. 跨批次冗余门控（预测残差式）

`brain.novelty_filter(cards)`：

- 新卡与历史卡库比较；
- 同 topic、无冲突、词面 Jaccard > 0.82 → 视为冗余；
- 不新增卡，只增加旧卡 `support`、提升 `confidence`；
- 返回保留卡与 `skipped` 数。

测试：重复 claim → `keep=[] skipped=1`。

这不是严格预测编码，但等价于“只传惊讶度足够大的事件”。

## 2. Workspace MMR

`graph_retrieval.ppr()` 返回 `workspace`：

- 对 top-k 激活卡做 MMR（λ=0.72）；
- 既保留相关性，又惩罚与已选卡高度重叠的卡；
- UI 显示 `WORKSPACE W1 ...`。

目的：避免“所有卡都在说同一句话”，对应设计中的 **全局工作空间 coalition**。

## 3. 记忆分层

新增 `card_meta`：

- `access_count` / `last_access` / `tier`；
- `retrieve()` 命中后 `touch()`；
- `refresh_tiers()`：7 天内 hot，30 天外 cold，其余 warm；
- 不删除卡；只分层/归档候选。

API/status 的 `metrics.tiers` 暴露 hot/warm/cold 数量。

## 4. 限制

- 冗余门控是词面 Jaccard，不是 embedding；
- MMR 也是词面多样性，不是语义多样性；
- tiers 只是元数据，尚未驱动淘汰/归档；
- 未做真实多节点网络。

## 5. 下一步

- embedding/实体去重；
- coverage-aware pruning（不是置信度剪枝）；
- workspace k 与错误相关性实验；
- 真实 3 节点 WAN。

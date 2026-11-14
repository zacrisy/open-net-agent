# 时间线：2026-11-06 ～ 2026-11-14

> 口径说明：本文只记录**研究阶段**的节点与结论；“当日 commit”指 `network_agent` 仓库里与该项研究直接相关的提交。  
> 2026-11-06 ～ 11-11 期间，仓库里只有 `cloud brain: auto learn/evolve [skip ci]` 自动提交；研究代码与结果在 2026-11-12 的 `ecab627` 一并入库。这不是遗漏，是当时的实际工作方式：研究在独立目录跑，结论先写报告，代码后归并。  
> 所有数字的口径与 CI 见 `RESEARCH_ARCHIVE.md` 与 `metrics_table.csv`。

---

## 2026-11-06（周四）· E1–E7 pilot + node-local BM25 hybrid

**做了什么**
- 在 5 节点 DMQA（300 train / 100 test，100 distractors/节点）上跑 E1/E1b：workspace vs flat verifier / 集中式检索 / 最佳单节点。
- E2 预测编码 Pareto；E3 routing；E4 故障注入/复制；E5 world-model policy；E6 Shapley vs counterfactual；E7 skill-aware routing。
- 同批 100 题 × 3 seeds 上比较 `active_orig` / `active_bm25` / `active_bm25strong` / `active_hybrid`，并试了 TF-IDF 余弦版 `active_dense`。

**结论**
- **workspace 不是杠杆**：NBPW 0.55 vs flat verifier 0.53；公平对照 E1b 只有 +0.01，95% CI [0.00, 0.03]。`no_novelty`/`no_coverage` 与完整版差在噪声内。
- **主动节点选择是强结果**：`active_hybrid` B=2 both@5 0.400 vs `active_orig` 0.247；B=3 0.487 vs 0.367。后续 n=300 复现 0.397 [0.323, 0.473]。
- **伪稠密画像失败**：`active_dense` 与 random 逐位相同（0.090 / 0.217），TF-IDF 余弦没有跨节点语义区分度。
- 预测编码没有 2× 带宽 / ≤2% 损失的工作点；theta=0.02 省 15% 带宽不降分，theta=0.05 省 40% 但掉 6pt。
- routing / world model / credit / skill 都是合成或小样本，只作方向，不作结论。

**当日 commit**
- 无研究 commit。当天仓库只有 `53fba51` / `144ae1f` / `688e591` 三条 cloud brain 自动提交。
- 研究代码与 `nbpw2/results/SUMMARY.md` 在 **2026-11-12 `ecab627`** 入库。

---

## 2026-11-09（周日）· 差距分解 + verifier 融合读出

**做了什么**
- 逐题记 `pool_has_both / node_queried / readout_ok`，把 `1 − both@5` 严格分解成池、选择器、读出三段（8 个策略×预算组合，残差 0）。
- 预计算 9,787 个问题×段落对的 NLI / 抽取式 QA 信号（126.8 ms/对，MPS），训练 A（NLI）、B（答案侧）、C（26 维融合）、RRF 四种读出。
- 在多节点复现集与 replica 集上重跑融合读出。

**结论**
- B=2 的误差构成：**选择器 75.7%、池 19.9%、读出 4.4%**；绝对天花板 0.787。
- 融合读出 all-nodes **0.517 → 0.677（+16pt）**，CI 不重叠；但端到端 hybrid B=2 只 **+1.3pt**，成本 **131×**；多节点复现衰减到 +2pt，replica 上崩到 0.09。**保留为 opt-in，不进默认。**
- NLI 直接把问句当 hypothesis 是结构性错误：AUC 0.444，单独排序 both@5 0.023。要做必须先做问句→陈述句改写。
- 当时把“选择器 75.7%”读成“节点选择是主瓶颈”；这条后来在 11-10 被主题切分数据修正（见下）。

**当日 commit**
- 无研究 commit。当天仓库只有 `63cbc42` / `1dc83f2` 两条 cloud brain 自动提交。
- 报告：`2026-11-09/network-brain-gap/outputs/gap_report.md`、`2026-11-09/network-brain-verifier/outputs/verifier_report.md`（在 `研究/` 下，未进 git）。

---

## 2026-11-10（周一）· 集合级选择器 + 检索深度/rerank

**做了什么**
- 实现 12 维 pairwise/set 特征（rel_c、rel_anchor、bridge_caps、title_in_anchor、rare_overlap、novelty、cov_gain、ans_dup、node_diff、rank、len），比较 workspace / pair / set 三种选择器。
- 深度实验：k=5/10/20/50；rerank@20；桥接二次查询；`title_in_query` 捷径消融。
- 重做“0.665 单段召回丢在哪”的逐事件归因（200 个 gold 事件）。

**结论**
- **集合选择器在候选完整时是大胜**：all-nodes 0.520 → 0.763（+24.3pt，CI 不重叠）；B=3 +11.3pt；**B=2 只有 +2.7pt（CI 完全重叠）**。
- 收益全部来自 bridge 题型（0.377 → 0.675）；comparison 已 100%，没有空间。
- **深度在 k=20 饱和**：单段召回 0.665 → 0.850（k=20）→ 0.940（k=50），但 set 0.550 → 0.560。
- **rerank@20 是性价比最高的一档**：set 0.610（+25pt，CI [0.17, 0.34]），40 候选，读出 82ms。
- 切分/同文档冗余丢失都是 **0%**；“同文档邻近段挤掉 gold”假设被直接证伪。
- 修正 11-09 的误读：在 3 个主题节点上，**只有 3pt 来自“gold 节点没被查”**，其余是节点内深度。5 节点随机切分的 75.7% 不能移植。

**当日 commit**
- 无研究 commit。当天仓库只有 `a2c8f99` / `530b145` / `e90416e` / `481f78f` 四条 cloud brain 自动提交。
- 报告：`2026-11-10/network-brain-selector/outputs/selector_report.md`、`2026-11-10/network-brain-retrieval-depth/outputs/retrieval_depth_report.md`。

---

## 2026-11-11（周二）· 稠密检索 + 默认链路诊断

**做了什么**
- 接入 `bge-small-en-v1.5`（CPU），在 3,975 段上建 384 维矩阵（5.8MB fp32），比较 bm25@5/20/50 与 dense@5/10/20/50。
- 试 linear hybrid（alpha 网格）与 RRF；在 dense 上再跑 rerank。
- 诊断默认链路为什么是 0.46 而不是 0.72：空候选、squash、dense-default、k=10、节点路由。
- 测空载延迟（`latency_clean.json`）。

**结论**
- **稠密同延迟碾压 BM25**：dense@5（75ms）0.690 vs bm25@50（350ms）0.550；dense@20 0.750 vs bm25@20 0.530（+0.220，CI [0.13, 0.32]）。
- **混合打不过纯稠密**：hybrid@20 0.710、RRF@20 0.670 < dense@20 0.750；alpha 最优落在网格边界 0.8（几乎纯稠密）。
- **rerank 在稠密上是负作用**：0.750 → 0.690（−6pt）。rerank 是给弱检索器补课，不是给强检索器加分。
- 稠密深度 k=10→20 只 +1pt，**k=20 已饱和**。
- 默认链路诊断：空候选不是主因；squash 在 BM25 上 +4~5pt、在 dense 上 −3pt；k=10 与 k=20 差 −0.01 [−0.04, 0.02]；节点路由损失 11pt（gold 节点没被查）。
- 空载延迟：编码 8.1ms；稠密扫描 0.04ms/节点；读出 4.7ms/候选；20 候选合计 ≈114ms。

**当日 commit**
- 无研究 commit。当天仓库只有 `28b0d2e` / `805e6a5` / `246830e` / `968ef8a` 四条 cloud brain 自动提交。
- 报告：`2026-11-11/network-brain-dense-retrieval/outputs/dense_retrieval_report.md`、`2026-11-11/network-brain-defaults/outputs/defaults_report.md`。
- 默认切换（dense k=10）在 **2026-11-12 `580c2f5`** 落地。

---

## 2026-11-12（周三）· 实现入库 + E12–E17 + LAN + k=10 默认

**做了什么**
- `ecab627`：`nbpw2` 参考实现入库（data/retrieval/verifier/workspace/router/network/node_scorer），补 E8–E11 的主动证据选择。
- `3adfe20`：主题切分（title 分组，~22 titles × ~5 docs/节点）+ 10 节点选择器（E12–E13）。
- `b1ef0c3`：真实 LAN transport + 每节点 readout；E14 先记为 blocked。
- `1de448e`：E15 多轮主动选择 + bootstrap 修复。
- `c2414f9`：E15b 停止准则（coverage / marginal / confident）。
- `33440fc`：CHANGELOG 记录 round 2/3 与 E14 blocking bug。
- `3cebfd8`：修 E14 的 `serve()` 默认 `--limit 200`（节点只读每 shard 前 200 段）；重跑并报告。
- `580c2f5`：**默认 dense recall depth k=10**；E16/E17 节点路由诊断。
- `2bf86e6` / `6dc92cf`：把 console 发布到 `docs/`，重建 `brain.html`。

**结论**
- 主题切分放大选择器收益：E12 active vs random B=2 **+0.364 [0.288, 0.436]**（n=250）；10 节点 B=4 0.645 vs 0.120（E13，n=100，2 seeds，无 CI）。
- E14 早期 LAN 数字全部作废；修复后 25 题只有方向性，不能下结论（`未成立`）。
- E15 多轮在 2.11 次查询/题下 coverage 0.524，低于一次查全节点 0.580；**多轮不是免费增益**。
- E16：dense@10 set 0.720、dense@20 0.730、k=10 vs k=20 −0.01 [−0.04, 0.02]；squash 在 dense 上 −3pt。
- E17：B=2 下 11 道 gold 节点未查，其中 10 道是路由排错、1 道同节点不可覆盖；信号存在，是打分函数没用上。D1（稠密 max 独立 top-2）ceiling .880 / node recall .995 / set .790 / ws .730。

**当日 commit**
- `ecab627` → `3adfe20` → `b1ef0c3` → `1de448e` → `c2414f9` → `33440fc` → `3cebfd8` → `580c2f5` → `2bf86e6` → `6dc92cf`（按时间顺序）。

---

## 2026-11-13（周四）· D1 默认 + 三态 + 界面/VPS

**做了什么**
- `db5b779`：**D1 稠密 max-cosine 节点路由成为默认**（B=2，每节点 k=10）。
- `1cec9da`：`brain.html` 接线上 ask box；VPS 后端上线（`https://106-14-46-145.sslip.io/public/brain/ask`、`/health`）。
- `2b92179`：7 例 insufficient-evidence 测试集，暴露“链路里没有弃答动作”。
- `4500bb1`：三态返回契约 `answered / insufficient / conflict`；grounding 校验；conflict 双源并列。
- `3629d4d`：记录线上三态 DOM/截图证据。

**结论**
- **D1 端到端**：ceiling .880 / node recall .995 / ws .730 / **set .790**；配对 bootstrap **set +.070 [.02, .13]**、ws +.060 [.01, .12]。三分解从 `hit .780 / node-not-queried .110 / depth .110` 变成 `hit .880 / node-not-queried .010 / depth .110`。路由不再是主结构缺口，深度是。
- D2 0.770、D3 0.760，均不如 D1；B=3 时 D1 与 bridge_hop 返回同一 30 候选并集，set 都是 0.790，**加预算没有额外收益**。
- **三态（98 题）**：answered 48（49.0%）、insufficient 46（46.9%）、conflict 4（4.1%）；answered 子集 exact-match **7/48 = 14.6%**；98 题整体 **7/98 = 7.1%**；旧链路 8/98 = 8.2%。
- **46 道弃答 100% 是抽取失败**：(a)=0、(c)=0；b1a 19 / b1b 10 / b2 9 / b3 8；**37/46（80.4%）gold 已在选中全文，27/46（58.7%）读出无对应答案形式**。
- 降级：58 道有旧跨度的题里 9 道（15.5%）变 insufficient，原本答对 0；另 1 道转 conflict（`Teen Titans`，旧按子串匹配算对），所以整体从 8 降到 7。
- 7 例重跑：`declared_insufficient 4 / exposed_conflict 2 / correct 1 / fabricated 0`。
- 单阈值 gate 全部不可用：coverage<0.30 误杀 1、focus<0.30 误杀 2、verifier<0.90 误杀 1、verifier<0.70 一道不拦；编造例 verifier 0.9933 与正确对照相同。
- 线上：VPS 894MB 内存上限，服务进程常驻约 294MB（整机约 500–600MB，另加 2G swap）；服务端 total 89–431ms；端到端 wall 891–1017ms；`docs/brain.html` 174,631 字节。

**当日 commit**
- `db5b779` → `1cec9da` → `2b92179` → `4500bb1` → `3629d4d`（另有 `055ef65` / `de54f02` 两条 cloud brain 自动提交）。

---

## 2026-11-14（周五）· 整理研究档案

**做了什么**
- 把 11-06 ～ 11-13 的全部实验整理成三份可长期查阅的文档：
  - `RESEARCH_ARCHIVE.md`：按“结论 → 证据 → 状态”组织，保留已推翻结论与旧数字被取代的记录。
  - `metrics_table.csv`：阶段 / 指标 / 口径 / 数值 / CI / 样本量 / 状态。
  - `timeline.md`：本文件。
- 只写文档，不改代码、不动默认。

**结论**
- 当前默认链路与最大缺口已固化：D1 top-2 → dense k=10 → fast verifier → set K=5 → 抽取 → 三态；最大缺口是读出（46 道弃答 100% 抽取失败，27 道无答案形式分支）。
- 下一步优先级按“能吃到多少”排序：P0 `other` 分支（19 题）、P1 yes/no（8 题）、P2 span 选择（10 题）、P3 支撑段选择（9 题）、P4 冲突（4 题）；fusion/rerank/k=20/50 节点不建议。

**当日 commit**
- 待提交：`docs(research): add consolidated research archive, metrics table, and timeline`。

---

## 附：阶段 ↔ 报告 ↔ commit 对照

| 阶段 | 主要报告 / 结果 | 关键 commit |
|---|---|---|
| E1–E7 pilot | `nbpw2/results/SUMMARY.md` | `ecab627`（11-12 入库） |
| 主动证据选择 E8–E11 | `SUMMARY.md`、`e8/e9/e11` | `ecab627` |
| node-local BM25 hybrid | `2026-11-06/outputs/bm25_variant_compare.json` | `ecab627` |
| 差距分解 | `2026-11-09/network-brain-gap/outputs/gap_report.md` | 无（11-12 入库） |
| verifier 融合读出 | `2026-11-09/network-brain-verifier/outputs/verifier_report.md`、`nbpw2/readout.py` | `ecab627` |
| 集合级选择器 | `2026-11-10/network-brain-selector/outputs/selector_report.md` | `ecab627` |
| 检索深度/rerank | `2026-11-10/network-brain-retrieval-depth/outputs/retrieval_depth_report.md` | `580c2f5` |
| 稠密检索 | `2026-11-11/network-brain-dense-retrieval/outputs/dense_retrieval_report.md` | `580c2f5` |
| D1 稠密路由 | `e17_node_route.json`、`e19_d1_default.json` | `db5b779` |
| 弃答三态 | `nbpw2/insufficient/REPORT.md`、`abstain_*.json` | `2b92179`、`4500bb1` |
| 界面与 VPS | `deploy/VPS_BRAIN.md`、`docs/brain.html` | `1cec9da`、`2bf86e6`、`6dc92cf` |
| 本档案 | 本目录三份文件 | 待提交 |

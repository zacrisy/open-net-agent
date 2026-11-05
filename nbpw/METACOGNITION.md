# 元认知与自动课程（v0.13）

## 校准

`metacognition.calibration()` 从完成的 `agent_tasks` 读取 confidence/score：

- 分桶计算 ECE；
- 搜索 abstain 阈值（保留高置信任务 vs 放弃低置信任务的效用）；
- 阈值下限 0.45，避免过度自信。

当前样本很小，实测 `n=2, ece=0.1, threshold=0.45, abstain_rate=0.0`。  
**不能据此证明校准良好**；需要 50+ 任务与人工 correctness。

## 自动课程

`curriculum.next_tasks(n)`：

- 从知识卡生成掩码题；
- 优先选择 `quiz` 中低正确率的卡；
- 返回 question / answer / priority；
- UI 的 **NEXT TASK** 会把它填入 Mission Control。

这是 Level-3 的“自动课程”雏形，不是完整的学习进度模型。

## 限制

- ECE 的“score”是任务 rubric，不是人工正确率；
- 课程只按 quiz 弱项，不考虑先修关系；
- 没有学习曲线/遗忘曲线；
- 没有真正多智能体。

# Coverage Protocol

`coverage/` 是全市场覆盖与筛选层。它不存放完整公司研究结论，也不替代
`research/companies/`。它的职责只有一个：在深度研究之前，把股票池分流成
“需要深研、只观察、跳过、人工复核”等状态，并留下可恢复的长程任务记录。

## 核心原则

- 筛选结果也是资产。跳过一家公司必须留下结构化理由，避免未来重复消耗研究资源。
- 筛选层只判断“是否值得投入深度研究火力”，不做完整估值报告。
- 完整研究报告只写入 `research/companies/{MARKET}/{TICKER}/reports/`。
- 长程任务必须能中断后恢复。每个批次用 run 文件记录状态、失败原因和下一步动作。
- 执行主体默认是 Codex、Claude 或其他 agent；不要假设用户会手动运行命令。

## 目录

```text
coverage/
  README.md
  cn-a/
    universe.schema.json
    screening.schema.json
    research-queue.schema.json
    universe.example.json
    screening.example.json
    research-queue.example.json
    runs/
      .gitkeep
```

## 分流结果

筛选结果使用固定枚举：

- `deep_research`：值得进入完整公司研究。
- `watch_only`：值得保留在观察池，但暂不写完整报告。
- `skip_risk`：风险、治理、财务质量或退市风险过高，跳过。
- `skip_too_small`：规模、流动性或覆盖价值过低，跳过。
- `skip_not_in_scope`：不在当前研究范围，如 ETF、基金、债券、B 股、优先股、壳资源等。
- `needs_manual_review`：信息冲突、业务复杂或数据不足，需要主 agent 决定。

## A 股第一轮筛选建议

第一轮只做低成本分流，目标是减少深研浪费：

1. 排除非普通 A 股、退市整理、长期停牌、明显壳化或不在能力圈的证券。
2. 排除 ST、高退市风险、重大违规、持续资不抵债或财报可信度过低的公司。
3. 排除市值和成交额过低、深研收益明显小于成本的公司。
4. 保留龙头、现金牛、长期复利资产、成长赛道核心公司、周期底部候选、困境反转和特殊资产。
5. 对数据冲突或业务复杂但可能重要的公司，标为 `needs_manual_review`，不要随手跳过。

## 长程执行

每次全市场筛选或深研批次都创建一个 run 文件，例如：

```text
coverage/cn-a/runs/2026-07-06-screening-pass-001.json
```

run 文件中的任务状态使用：

- `pending`
- `running`
- `completed`
- `failed`
- `skipped`
- `needs_review`

下一个 agent 接手时，读取最新 run 文件，优先处理 `pending`、`failed` 和
`needs_review`，不要重新开始整轮任务。

## 与研究资产的关系

- `coverage/cn-a/screening*.json` 决定哪些股票进入研究队列。
- `coverage/cn-a/research-queue*.json` 是深研任务队列。
- `research/companies/` 保存真正的研究报告和当前公司状态。
- `research/index.json`、`automation/review_schedule.json`、`automation/price_alerts.json`
  只从 `research/companies/` 生成，不从 coverage 生成。

# Coverage Protocol

`coverage/` 是全市场覆盖与任务编排层。它不保存完整公司研究结论，也不替代
`research/companies/`。它的职责是：在深度研究之前，把股票池整理成可恢复的研究队列，
记录优先级、风险标签、复核状态和跳过理由。

## 核心原则

- 默认应研尽研。普通 A 股公司原则上都应进入研究体系。
- 筛选不是为了大幅减少研究对象，而是为了安排顺序、识别硬风险、保证长程任务可恢复。
- 小市值、低流动性、亏损、PE 为负、行业冷门，都不能作为硬跳过理由。
- ST、*ST、重大异常公司进入 `needs_manual_review`，不要直接排除。
- `skip_*` 只用于硬排除项，例如退市整理、明显不在普通 A 股范围内、数据无法识别。
- 完整研究报告只写入 `research/companies/{MARKET}/{TICKER}/reports/`。

## 目录

```text
coverage/
  README.md
  cn-a/
    companies.jsonl
    screening.jsonl
    research_queue.jsonl
    runs.jsonl
    universe.schema.json
    screening.schema.json
    research-queue.schema.json
    universe.example.json
    screening.example.json
    research-queue.example.json
    runs/
      .gitkeep
```

`*.jsonl` 是全市场覆盖状态的工作真相。每一行是一家公司或一个任务，便于 Git diff，
也便于 agent 用工具安全查询和更新。`*.schema.json` 与 `*.example.json` 用来说明结构和约束。

## 分流结果

- `deep_research`：进入完整公司研究队列。
- `watch_only`：已有研究档案或等待既定复查，不重复创建初始研究任务。
- `skip_risk`：退市整理、明显无法作为普通股票研究的硬风险项。
- `skip_too_small`：原则上少用；不能因为普通小市值或低流动性而跳过。
- `skip_not_in_scope`：不在当前普通 A 股研究范围内，如 ETF、基金、债券、B 股、优先股等。
- `needs_manual_review`：ST、*ST、数据冲突、证券状态异常，需主 agent 先判断研究路径。

## A 股首筛建议

第一轮只做低成本分流：

1. 排除非普通 A 股和退市整理类硬排除项。
2. 将 ST、*ST、重大异常和数据冲突标为 `needs_manual_review`。
3. 其余普通 A 股默认标为 `deep_research`。
4. 用优先级控制执行顺序，而不是决定是否研究。
5. 已有初始研究报告的公司标为 `watch_only`，按 `meta.json` 的复查计划跟踪。

## Agent 辅助工具

agent 可以直接编辑 JSONL，但优先使用薄封装，避免破坏格式、重复 symbol 或打乱排序：

```bash
python -m trading_os coverage validate
python -m trading_os coverage status
python -m trading_os coverage get CN:600519
python -m trading_os coverage list --decision deep_research
python -m trading_os coverage set-screening CN:300750 --name 宁德时代 --decision deep_research --priority 1 --reason "动力电池龙头" --evidence "行业龙头" --next-action "加入研究队列"
python -m trading_os coverage enqueue CN:300750 --name 宁德时代 --priority 1 --reason "筛选结果为 deep_research"
```

这些命令是给 Codex、Claude 或其他 agent 用的安全编辑器，不要要求用户手动执行。

## 长程执行

每次全市场筛选或深研批次都向 `coverage/cn-a/runs.jsonl` 追加或更新 run 记录。
如果需要保留详细批次摘要，可以额外在 `coverage/cn-a/runs/` 下写 Markdown 或 JSON，
但不要把它当成唯一真相。

任务状态使用：

- `pending`
- `running`
- `completed`
- `requires_rebaseline`（已有历史材料，但旧结论不可执行；等待按当前协议重建）
- `failed`
- `skipped`
- `needs_review`

下一个 agent 接手时，读取 `coverage/cn-a/runs.jsonl` 和相关队列，优先处理
`pending`、`requires_rebaseline`、`failed` 和 `needs_review`，不要重新开始整轮任务。

## 与研究资产的关系

- `coverage/cn-a/screening.jsonl` 决定研究顺序和复核状态。
- `coverage/cn-a/research_queue.jsonl` 是深研任务队列。
- `research/companies/` 保存真正的研究报告和当前公司状态。
- `research/index.json`、`automation/review_schedule.json`、`automation/price_alerts.json`
  只从 `research/companies/` 生成，不从 coverage 生成。

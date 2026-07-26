# Coverage Protocol

`coverage/` 是全市场覆盖与任务编排层。它不保存完整公司研究结论，也不替代
`research/companies/`。它的职责是：在深度研究之前，把股票池整理成可恢复的研究队列，
记录优先级、风险标签、复核状态和跳过理由。

## 核心原则

- 默认全覆盖，但绝不平均投入。每家公司都可被找到、每次停止都可审计，只有最可能改变组合决策的少数公司获得完整深研。
- 筛选的任务是逐层购买信息：机器地图、快速画像、范围研究、完整深研、独立承保。
- 公开快照总分不能直接晋级完整深研；按综合赔率、现金价值、复利质量、金融、周期、危机、新信息和假阴性抽查多视角选样。
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

- `catalog`：已进入全市场可审计目录，但本周期未获得进一步研究预算。
- `quick_profile`：获得一小时级快速投资画像预算。
- `scoped_research`：只解决一至三个决定性未知数。
- `targeted_followup`：只补齐一个或少数决定性证据。
- `deep_research`：进入完整公司研究队列。
- `price_watch`：公司可能可投，但当前价格不支持继续购买研究预算。
- `reassign_or_stop`：超出当前 agent 能力圈，转派或暂停。
- `watch_only`：已有研究档案或等待既定复查，不重复创建初始研究任务。
- `conditional_stop`：继续研究的信息价值不足或存在经证据确认的阻断项；必须记录重新激活条件。
- `hard_exclusion`：非普通股、退市或法律上不能形成投资对象。
- `skip_risk`：退市整理、明显无法作为普通股票研究的硬风险项。
- `skip_too_small`：原则上少用；不能因为普通小市值或低流动性而跳过。
- `skip_not_in_scope`：不在当前普通 A 股研究范围内，如 ETF、基金、债券、B 股、优先股等。
- `needs_manual_review`：ST、*ST、数据冲突、证券状态异常，需主 agent 先判断研究路径。

## A 股首筛与研究资本配置

第一轮只做低成本分流：

1. 排除非普通 A 股和退市整理类硬排除项。
2. 将 ST、*ST、重大异常和数据冲突标为 `needs_manual_review`。
3. 其余普通 A 股进入机器画像，但不默认获得完整初研预算。
4. 使用 `policies/research-allocation.json` 的多视角容量选出快速画像名单。
5. 快速画像只能晋级范围研究；范围研究通过后才能进入完整初研。
6. 已有有效研究且价格远离买入区的公司转为 `watch_only`，仅跟踪价格与关键假设。
7. 所有非硬排除结果记录停止原因、研究预算和重启触发器。

## Agent 辅助工具

agent 可以直接编辑 JSONL，但优先使用薄封装，避免破坏格式、重复 symbol 或打乱排序：

```bash
python -m trading_os coverage validate
python -m trading_os coverage status
python -m trading_os coverage get CN:600519
python -m trading_os coverage rank-rebaseline
python -m trading_os coverage allocate-research
python -m trading_os coverage apply-allocation
python -m trading_os coverage evaluate-profile --input <quick-profile.json>
python -m trading_os coverage enqueue CN:300750 --name 宁德时代 --priority 1 --reason "多视角选样进入快速画像" --task-type quick_profile --effort-budget-hours 1 --preceding-stage machine_triage --stop-condition "不存在可信的10%回报路径"
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
- `coverage/cn-a/research_queue.jsonl` 是分层研究任务队列；任务必须带阶段、预算和停止条件。
- `research/companies/` 保存真正的研究报告和当前公司状态。
- `research/index.json`、`automation/review_schedule.json`、`automation/price_alerts.json`
  只从 `research/companies/` 生成，不从 coverage 生成。

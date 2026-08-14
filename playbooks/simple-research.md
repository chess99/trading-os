# 简化研究流程

## 目标

系统先完成一次全市场基线，此后只处理新增公司和足以影响研究的新事实。初筛负责选择研究对象；单公司研究负责形成完整、自足的当前报告。证券价格不是研究事实，不触发复核或任务。

核心原则：

1. 主 Agent 批量判断公司是否值得进行一次正式研究。
2. 所有候选使用同一份 `prompts/company/standard-deep-research.md`，一家公司由一个 Agent 端到端完成。
3. 正式报告是某个信息截止时点的完整研究快照，必须脱离历史报告独立可读。
4. 估值、正常化经营、核心逻辑、风险排序或正式结论变化，必须生成新的完整报告。
5. 研究由公司、财务、治理、资本结构和行业经营变量驱动，不由股票价格驱动。

## 三类状态

证券范围使用 `active / inactive`；公司研究状态使用：

- `unseen`：尚未完成首次初筛；
- `ignore`：当前不值得正式研究，或正式研究后不值得持续覆盖；
- `candidate`：已被选中，等待或正在正式研究；
- `covered`：已有当前有效正式报告，值得持续维护；
- `stale`：重大新事实已使当前报告失效，等待完整更新。

活动任务只使用 `queued / running`。同一公司最多一个活动任务，任务只绑定 `candidate / stale`。只有 active `covered` 进入 `research/watchlist.jsonl`。

## 一次性全市场基线

主 Agent 分批浏览 active unseen 公司的压缩事实，每家公司只做：

- `ignore`：当前不值得占用完整研究资源；
- `research_now`：商业质量、错价可能性、变化程度或关键问题的信息价值值得正式研究。

`research_now` 写入 `candidate` 并创建唯一任务。初筛不估值、不设置目标价或买点，也不生成公司 Markdown。不得按数量目标填队列，不得用单一财务指标机械决定。

## 单公司完整研究

结果只有 `covered / ignore`。两种结果都向以下目录追加报告：

```text
research/companies/CN/{ticker}/reports/YYYY-MM-DD.md
research/companies/CN/{ticker}/reports/YYYY-MM-DD-02.md
```

报告必须完整说明商业模式、竞争、行业、财务质量、普通股股东口径、治理、资本配置、市场隐含预期、估值、风险、结论和来源。不得写“详见前序报告”“历史分析继续有效”“沿时间线回看”来跳过正文。

`value_range` 是截至信息截止日、由已验证事实和正常化经营支持的普通股核心合理价值区间。它不是买入价，不包含具体投资决策人的安全边际、账户约束或仓位决定。无法可靠估值时填 `valuation_note` 说明原因。

定期财报默认需要新的完整报告。公告或其他事实即使不改变商业逻辑，只要改变正常化利润、估值参数、`value_range`、风险排序或 `covered / ignore`，也必须生成完整新报告，不能只写 update。

## 公司研究日志

不越过当前正式报告边界的事件，可以追加：

```text
research/companies/CN/{ticker}/updates/YYYY-MM-DD[-NN].md
```

update 只允许三种影响：

- `reaffirmed`：新事实确认当前报告；
- `monitor`：信息仍在原报告边界内，继续观察；
- `invalidated`：宣告当前报告失效，转 `stale` 并创建完整研究任务。

update 必须引用基础正式报告、事件 ID、事件摘要、分析、结论和来源。它不得修改：

- `value_range` 或正常化利润；
- 核心逻辑或风险排序；
- `covered / ignore`；
- 正式报告指针或信息截止时间。

每次 update 都必须在公司状态行推进 `updated_at`，并写入 `last_update`：日志路径、影响类型、审阅时间、该事件的信息截止点、事件 ID、摘要、来源和基础报告。这个字段是跨系统审计凭据，不会把 update 冒充为新的正式报告，也不会改写正式报告的 `information_cutoff`。

`invalidated` 只说明为什么旧报告已经不能使用；替代结论必须由后续完整正式报告给出。

已有正式报告的公司不得再通过全市场初筛的 `research_now` 路径直接失效。处理公告时必须先比较事件事实时间与当前报告的 `information_cutoff`：

- 事实时间不晚于报告截止点：视为已被当前报告吸收，不改变状态，也不重复排队；
- 事实时间晚于报告截止点、但没有越过报告边界：写 `reaffirmed` 或 `monitor` update；
- 事实时间晚于报告截止点、且足以改变正式报告：写带明确 `information_cutoff` 的 `invalidated` update，由协调器转 `stale` 并创建完整研究任务。

`stale` 的失效时间不得早于当前正式报告截止点，且必须引用实际存在的 `invalidated` update 文件。这样即使公告扫描回补旧窗口，也不能用历史公告推翻更新后的正式报告。

## 触发机制

公告扫描覆盖全部 active 公司，包括 `ignore`。典型触发包括：

- 年报、半年报、一季报和三季报；
- 业绩预告、重大合同、并购、融资、股本和控制权变化；
- 处罚、治理、关联交易和资本配置变化；
- 铜价、产品售价、运价、利率、汇率、产能利用率等经营或行业变量。

证券自身的收盘价、涨跌幅、估值区间穿越不触发研究。仓库不保存 `price_levels`、`price_monitor`、armed/hit/rearm 或每日收盘扫描结果。

公告扫描与完整研究是两条独立链路：扫描从最近一次成功检查点直接推进到当前时间，完成公告发现、裁决、研究日志和排队；独立的研究队列消费者再通过 `research next` 逐家公司完成完整研究。扫描不得顺带消费队列，也不应固定只清理一个很短的历史切片；只有在数据源故障恢复时才临时缩小窗口。

典型流转：

```text
ignore + material_event       -> candidate 或 ignore
covered + fact_in_range       -> reaffirmed / monitor update
covered + report_invalidated  -> invalidated update -> stale + full research
covered + valuation_change    -> stale + full research
stale + research_complete     -> covered 或 ignore
```

## 行情和网站边界

网站是附带的只读展示，不是仓库的主要产品。它可以现场获取行情，并机械展示：

```text
当前价格 / value_range.low
当前价格 / value_range 中枢
```

这些值不得写回研究状态，不得称为买入信号、关注价或“安全边际充分”。行情缺失时显示 `—`，不得从退役的价格运行状态回退。

## 状态维护

唯一事实源：

- `coverage/cn-a/research_state.jsonl`：证券范围与公司研究状态；
- `coverage/cn-a/research_queue.jsonl`：当前任务；
- `research/companies/CN/{ticker}/reports/`：完整正式报告；
- `research/companies/CN/{ticker}/updates/`：研究日志；
- `research/companies/CN/{ticker}/legacy/`：隔离旧稿；
- `research/watchlist.jsonl`：active covered 的确定性投影；
- `coverage/cn-a/event_scan_state.json`：公告扫描检查点。

共享 JSONL 只由协调器原子写入。worker 只返回最终结构化结果。状态变更后重建自选池并执行 `python -m trading_os validate`。

一次性迁移：

```bash
python -m trading_os state migrate-v3 --at <带时区时间>
```

v3 删除证券价格层、价格运行状态和证券价格型事件条件，保留财报、公司事件及经营变量触发。

## 验收

- active 范围没有遗留 `unseen`；
- 只有 `candidate / stale` 有活动任务；
- current 报告是最新、非空、自足的日期化完整报告；
- 状态和自选池不存在证券价格触发字段；
- update 没有修改正式估值或结论，invalidated 正确创建完整研究任务；
- 自选池与 active covered 完全一致；
- 公告扫描覆盖全部 active 公司；
- `python -m trading_os validate` 通过。

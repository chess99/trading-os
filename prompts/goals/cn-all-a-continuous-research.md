# 全 A 股持续研究 Goal

> 在新的 Codex 任务中引用本文件。状态与执行细节以根 `AGENTS.md`、`playbooks/simple-research.md` 和 `prompts/company/standard-deep-research.md` 为准。

持续维护全 A 股研究系统。只有没有有效基线时才跑全市场；基线完成后只处理新增公司及公司、财务、治理、资本结构和行业经营变量的新事实。股票价格不触发研究。

## 状态模型

证券范围使用 `active / inactive`。公司状态使用 `unseen / ignore / candidate / covered / stale`；任务使用 `queued / running`。

初筛只允许 `ignore / research_now`；`research_now` 写入 `candidate` 并创建任务。初筛不估值、不设置买点、不生成公司报告，也不按数量目标填队列。

## 单公司任务

一家公司由一个 Agent 使用 `prompts/company/standard-deep-research.md` 端到端完成。最终结果只有 `covered / ignore`，两者都追加完整、自足的日期化正式报告。报告不得把商业、财务、估值或风险正文委托给历史版本。

`value_range` 是公司研究结论，不是买入价。证券价格、涨跌幅和价格区间穿越不进入研究状态或队列。若展示层比较实时价格与价值区间，只能机械派生，不能写回仓库或解释为投资授权。

## 增量运行

公告扫描覆盖全部 active 公司。定期财报默认触发完整更新；任何正常化利润、估值、核心逻辑、风险排序或 `covered / ignore` 变化，也必须生成完整新报告。

财报更新必须重新生成整份报告，不得把财报摘录拼接到旧正文。累计与单季口径要分开，关键变量要说明“前次假设—实际—判断变化—估值影响”；全文只能有一套信息截止和结论，正文核心合理价值区间必须与结构化 `value_range` 一致。两种估值方法差异超过 25% 时解释主次，核心合理价值、悲观情景和决策安全边际不得混写。

未越过当前报告边界的事件可记录为 update：

- `reaffirmed`：确认当前报告；
- `monitor`：继续观察；
- `invalidated`：报告失效，转 `stale` 并创建完整研究任务。

update 不得修改正式估值或结论。铜价、产品售价、运价、利率、汇率等经营变量可以触发研究；公司股票的收盘价不能。

## 恢复与写入

启动时读取 Git 状态、`research_state.jsonl`、`research_queue.jsonl`、`research/watchlist.jsonl` 和 current 正式报告。保留用户及其他并行修改，不重做已完成公司。

单公司 Agent 不直接写共享 JSONL。协调器串行接收结果、原子写状态、重建自选池并运行 `python -m trading_os validate`。每个完整迭代只提交本轮修改。

## 每轮报告

向用户报告：运行模式、信息截止时间、active/inactive 数、各研究状态数、研究队列、完成公司、研究日志、重大事件、验证与提交。不要报告价格命中、armed/rearm 或多余流程层级。

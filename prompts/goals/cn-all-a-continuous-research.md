# 全 A 股持续研究 Goal

> 在新的 Codex 任务中引用本文件。状态与执行细节以根 `AGENTS.md`、`playbooks/simple-research.md` 和 `prompts/company/standard-deep-research.md` 为准。

持续维护全 A 股研究系统。只有没有有效基线时才跑全市场；基线完成后只处理新增公司及公司、财务、治理、资本结构和行业经营变量的新事实。股票价格不触发研究。

## 状态模型

证券范围使用 `active / inactive`。公司状态使用 `unseen / ignore / candidate / covered / stale`；任务使用 `queued / running`。

初筛只允许 `ignore / research_now`；`research_now` 写入 `candidate` 并创建任务。初筛不估值、不设置买点、不生成公司报告，也不按数量目标填队列。

## 单公司任务

一家公司由一个 Agent 使用 `prompts/company/standard-deep-research.md` 端到端完成。最终结果只有 `covered / ignore`，两者都追加完整、自足的日期化正式报告。报告不得把商业、财务、估值或风险正文委托给历史版本。

围绕少数决定性商业问题取证，按需参考并核验 `research/industries/` 中的产业专题。协调器依 `playbooks/simple-research.md` 的“商业判断验收”检查关键因果链、相反解释和重要模型假设；章节齐全、来源数量多或算术正确不能替代语义验收。

`value_range` 是截至信息截止时点的当前合理价值，不是买入价，也绝不能充当未来终值。每份新正式研究都必须提交非空 `return_model_note`；能够可靠建模时同时提交结构化 `return_model`，否则提交 `return_model: null`，并在 note 中说明原因。V1 使用统一的 `annual_common_equity_irr_v1` 接口：五年为主口径，提交未来第 1—5 年普通股每股现金分配和独立研究的第五年末普通股每股终值区间；三年终值区间可选，但不得从五年终值机械折算。行业经营预测和终值方法可以不同，最终接口必须一致。

正式报告正文增加“基准持有人回报模型输入”，说明年度分配、未来终值、普通股权益桥、完全稀释股数和关键口径，但不写入随现价变化的 IRR。证券价格、涨跌幅和价格区间穿越不进入研究状态或队列。展示层可以把实时价格与冻结的模型输入机械求解为 IRR，但不能写回仓库或解释为投资授权、收益率门槛或交易建议。

## 增量运行

公告扫描覆盖全部 active 公司。定期财报默认触发完整更新；任何正常化利润、估值、`return_model` 输入、核心逻辑、风险排序或 `covered / ignore` 变化，也必须生成完整新报告。

财报更新必须重新生成整份报告，不得把财报摘录拼接到旧正文。累计与单季口径要分开，关键变量要说明“前次假设—实际—判断变化—估值影响”；全文只能有一套信息截止和结论，正文核心合理价值区间必须与结构化 `value_range` 一致。两种估值方法差异超过 25% 时解释主次，核心合理价值、悲观情景和决策安全边际不得混写。

未越过当前报告边界的事件可记录为 update：

- `reaffirmed`：确认当前报告；
- `monitor`：继续观察；
- `invalidated`：报告失效，转 `stale` 并创建完整研究任务。

update 不得修改正式估值、`return_model`、`return_model_note` 或结论。铜价、产品售价、运价、利率、汇率等经营变量可以触发研究；公司股票的收盘价不能。任何模型输入变化都必须走完整研究，不得写补丁式 update。

## 恢复与写入

启动时读取 Git 状态、`research_state.jsonl`、`research_queue.jsonl`、`research/watchlist.jsonl` 和 current 正式报告。保留用户及其他并行修改，不重做已完成公司。

单公司 Agent 不直接写共享 JSONL。协调器串行接收结果、原子写状态、重建自选池并运行 `python -m trading_os validate`。每个完整迭代只提交本轮修改。

## 每轮报告

向用户报告：运行模式、信息截止时间、active/inactive 数、各研究状态数、研究队列、完成公司、研究日志、重大事件、验证与提交。不要报告价格命中、armed/rearm、收益率阈值、概率权重、仓位或多余流程层级。

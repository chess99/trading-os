# L1.5 快速甄别：{公司名称}（{MARKET:TICKER}）

本阶段只回答一个问题：在 Agent 已经看过这家公司以后，是否值得让它竞争下一层研究预算。默认预算为 15 分钟。不要计算机械综合分，不给 `buy_now`、仓位或正式投资评级。

## 输入绑定

- 必须使用 claim 返回的 `cycle_id`、`cohort_path` 与 `cohort_sha256`。
- `review_mode` 只能是 `baseline_recheck` 或 `triggered_update`。
- `prior_research_path` 没有可用旧研究时可为 `null`；不得伪造旧研究。
- `trigger_context` 要说明本次为何进入队列，而不是复述公司名称。

## 最低证据

- 至少两项来源，其中至少一项是最新年度、季度报告或交易所公告等 S1 来源。
- 价格必须来自最近七日内的独立来源；`price_source_id` 指向的来源，其 `supports` 必须显式包含 `current_price`。
- 来源只支持它真正证明的主张。明显的生存、治理或财务异常只记录足以分流的证据，不扩写成未经验证的完整调查。

## 必须写清的判断

1. `business_summary`：公司如何赚钱，主要客户、资产和资本需求是什么。
2. `change_summary`：相对旧研究或上次观察，事实与判断发生了什么变化；没有明显变化也要明确写出。
3. `normalized_earnings_view`：剔除周期、一次性项目、补贴、减值和资本化影响后，正常化盈利大致是什么状态。
4. `expectations_view`：当前价格大致隐含怎样的增长、利润率、资产价值或修复预期；不能只报 PE。
5. `counterevidence`：至少一项真正可能推翻乐观判断或停止判断的反方证据。
6. `decisive_question`：再投入下一小时最可能解决、并可能改变投资判断的问题。

## 重启触发器

每份 v2 package 至少写一个可执行的 `revisit_trigger`，即使当前值得继续研究也不能省略。可用类型：

- `price`：`condition={"operator":"price_lte|price_gte","threshold":正数}`；
- `date`：`condition={"date":"YYYY-MM-DD"}`；
- `ttl`：`condition={"days":正整数}` 或 `condition={"due_at":"带时区时间"}`；
- `filing`、`event`、`thesis`：`condition={"description":"可核验条件"}`。

每项还必须含唯一 `trigger_id` 和具体 `reason`。不要把“以后再看看”当作条件。

## 输出与晋级纪律

输出必须严格符合 `templates/rapid-triage.schema.json`。`triage-record` 会先封存 package，并成功追加到公司的不可变时间线，之后才把 coverage 队列标记为 completed。

单家公司完成后不得立即晋级。完整 cohort 全部完成后运行 `triage-compare`，由另一名未参与单公司甄别的 Agent 阅读 comparison packet，为其中每家公司逐一写出 `decision`、`reason`、`decisive_question` 和 `counterevidence_considered`。即使首轮 disposition 没有建议晋级，也必须复核并允许纠正假阴性。最后 `triage-finalize --decisions ...` 只验证显式决策和容量，不按因子、估值枚举、旧 priority 或 lens 自动排序。

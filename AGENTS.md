# Trading OS Agent Guide

除非用户主动要求切分支，否则直接在当前分支开发。文档默认使用中文。完成一个完整迭代后，只提交本次修改的文件；提交前检查暂存区，禁止带入用户或其他 Agent 的无关修改。

## 唯一事实源

- 全市场状态：`coverage/cn-a/research_state.jsonl`。
- 当前研究队列：`coverage/cn-a/research_queue.jsonl`。
- 自选池：`research/watchlist.jsonl`，必须可由全市场状态确定性重建。
- 单公司完整研究：`research/companies/CN/{ticker}/current.md`，每家公司最多一份，更新历史交给 Git。
- 收盘价触发的去重与重新武装状态直接保存在公司当前状态行中。
- 财报与重大公告扫描只用 `coverage/cn-a/event_scan_state.json` 保存最后成功时间和近期公告 ID；不得扩张为永久事件账本。

旧 manager-screen、quick/targeted/scoped/deep 阶段预算、claim/seal、calibration、独立承保、challenger、仲裁和组合审批均已退役，不得重新引入。

## 角色与并行

- 主 Agent 批量浏览全市场压缩事实，逐项判断 `ignore / research_now`。`research_now` 写入公司的 `candidate` 状态并创建唯一研究任务。
- 不设置必须深入研究的公司数量。是否值得派发，取决于主 Agent 对信息价值、业务质量、错价可能性和关键问题可解性的判断。
- 只有 `research_now` 派单公司 Agent；明显不值得研究的公司不得为了形式完整而派发。
- 不同公司允许并行，常见并行度为 3—6，具体由调用者配置；一家公司只允许一个 Agent 端到端完成。
- 单公司 Agent 收到一次完整任务，最终返回一次结构化结果。没有复核 Agent、经理审批或中间角色交流。
- 所有候选公司都使用 `prompts/company/standard-deep-research.md`。不设置研究强度等级或分钟数；报告长短可以随复杂度变化，但核心研究问题和输出契约必须一致。

## 结果要求

结果状态为 `ignore / covered`：

- 两种结果都必须完成统一提示词要求的商业、财务、治理、估值和风险研究，并写 `current.md`；
- `covered` 表示当前报告仍有效且值得持续监控，需给出价格或事件触发；
- `ignore` 表示正式研究后仍不值得持续监控，不得激活价格触发。初筛产生的 `ignore` 可以没有正式报告。

不要求仓位建议、`buy_now`、精确年化回报、独立承保结论或组合动作。数字应能在给出的来源中复核，但不建立 evidence ledger、SHA 权限链或多角色复核链。

## 初筛与日常触发

- 首轮全市场初筛只需要完整走一次。之后以价格、财报、公告、日期或人工事件驱动局部更新。
- 自选池只包含当前仍为 `covered` 的公司。未正式研究的 `candidate` 不得设置或扫描价格。
- 价格只做每日收盘扫描。首次越过触发价时生成复看提示；价格离开触发区后重新武装，避免每天重复提醒。价格命中本身不创建研究任务。
- 公告扫描必须覆盖全市场当前证券身份；任一目录、分页、URL 或判断结果不完整时不得推进检查点。
- `covered` 公司遇到足以使原报告失效的财报或重大事件时转为 `stale`，暂停价格信号并进入更新研究。
- 池外公司先进入批量变化筛选，主 Agent认为出现实质变化后才转为 `research_now`。
- 价格变化本身只触发估值和结论复核，不要求重做全部基本面研究。

## 写入纪律

- worker 不直接修改共享 JSONL；由协调器校验并原子写入。公司研究状态只使用 `unseen / ignore / candidate / covered / stale`；任务状态只使用 `queued / running`。
- `coverage/cn-a/research_state.jsonl` 是公司状态唯一事实源；`research/watchlist.jsonl` 只允许由其中的 active `covered` 公司确定性重建，禁止手改。
- `candidate` 没有有效正式报告和价格线；`covered` 必须绑定当前报告及价格或事件触发；`stale` 必须记录失效原因并暂停价格监控。
- 价格命中只更新触发器的 armed/hit 运行状态，不改变公司研究状态。持仓、仓位和账户信息也不进入公司研究状态。
- 同一公司、同一触发事件只能存在一个活动任务。
- 报告只保留公开来源的标题、URL 和日期；可重新下载的 PDF、网页、行情快照不进入 Git。
- 修改共享状态后重建自选池并运行 `python -m trading_os validate`。

## 开始工作

先读：

1. `playbooks/simple-research.md`
2. `prompts/goals/cn-all-a-continuous-research.md`

常用命令见 `README.md`。

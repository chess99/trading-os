# Trading OS Agent Guide

除非用户主动要求切分支，否则直接在当前分支开发。文档默认使用中文。完成一个完整迭代后，只提交本次修改的文件；提交前检查暂存区，禁止带入用户或其他 Agent 的无关修改。

## 唯一事实源

- 全市场状态：`coverage/cn-a/research_state.jsonl`。
- 当前研究队列：`coverage/cn-a/research_queue.jsonl`。
- 自选池：`research/watchlist.jsonl`，只能从全市场状态确定性重建。
- 正式报告：`research/companies/CN/{ticker}/reports/YYYY-MM-DD[-NN].md`。状态中的 `report_path` 指向最新正式报告，这个指针就是 current。
- 隔离旧稿：`research/companies/CN/{ticker}/legacy/YYYY-MM-DD.md`，每家公司最多一份，永远不参与当前状态、估值、队列或价格。
- 收盘价触发的去重与重新武装状态保存在公司当前状态行。
- 公告扫描只用 `coverage/cn-a/event_scan_state.json` 保存成功检查点和近期公告 ID。

正式报告和历史旧稿均为本机资料，由 Git 忽略，必须另行做文件备份。不得恢复会漂移的 `current.md` 副本，也不得用 `stale` 文件后缀表达公司状态。

旧 manager-screen、quick/targeted/scoped/deep 阶段预算、claim/seal、calibration、独立承保、challenger、仲裁和组合审批均已退役，不得重新引入。

## 角色与并行

- 主 Agent 批量浏览全市场压缩事实，逐项判断 `ignore / research_now`。
- `research_now` 写入 `candidate` 并创建唯一研究任务；明显不值得研究的公司不派 Agent。
- 不同公司可独立并行，常见并行度为 3—6；同一公司只允许一个 Agent 端到端完成。
- 单公司 Agent 接收一次完整任务，只返回一次结构化结果；没有复核 Agent、经理审批或中间角色交流。
- 所有候选统一使用 `prompts/company/standard-deep-research.md`。不设研究强度等级、固定分钟数或收益率硬门槛。

## 状态与结果

公司研究状态只使用 `unseen / ignore / candidate / covered / stale`；证券范围只使用 `active / inactive`；活动任务只使用 `queued / running`。

单公司正式结果只有 `ignore / covered`：

- 两种结果都必须完成统一提示词要求的商业、财务、治理、估值和风险研究，并向 `reports/` 追加日期化报告；
- `covered` 表示报告当前有效且值得持续监控，必须有价格或事件触发；
- `ignore` 表示正式研究后仍不值得持续监控，不得激活价格触发；
- `stale` 表示重大事实使当前报告失效，暂停价格监控并进入更新研究。

单公司层不输出仓位、`buy_now`、精确年化回报、承保意见或组合动作。数字应能在公开来源中复核，但不建立 evidence ledger、SHA 权限链或多角色复核链。

## 初筛与日常触发

- 全市场基线只完整执行一次；之后只处理新增公司、实质变化和每日收盘价格触发。
- 未正式研究的 `candidate` 不得设置或扫描价格。
- 价格只在每日收盘扫描。首次越过触发价时提示，离开触发区后重新武装；价格命中本身不创建完整研究任务。
- 公告扫描覆盖全部 active 公司，包括 `ignore`。池外公司出现实质变化后才能转为 `research_now`。
- `covered` 遇到足以使报告失效的财报或重大事件时转为 `stale`；普通价格变化只复核估值和结论，不重做全部基本面。

## 写入纪律

- worker 不直接修改共享 JSONL；协调器校验并原子写入。
- `research/watchlist.jsonl` 禁止手改。
- 同一公司、同一触发事件最多一个活动任务。
- 新正式研究只追加报告，不覆盖或删除历史报告；状态中的 `report_path` 必须是最新正式报告。
- `legacy/` 只允许通过旧研报归档工具写入，不得改变任何当前事实。
- 修改共享状态后重建自选池并执行 `python -m trading_os validate`。

## 开始工作

先读：

1. `playbooks/simple-research.md`
2. `prompts/goals/cn-all-a-continuous-research.md`

常用命令见 `README.md`。

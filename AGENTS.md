# Trading OS Agent Guide

除非用户主动要求切分支，否则直接在当前分支开发。文档默认使用中文。完成一个完整迭代后，只提交本次修改的文件；提交前检查暂存区，禁止带入用户或其他 Agent 的无关修改。

## 唯一事实源

- 全市场状态：`coverage/cn-a/research_state.jsonl`。
- 当前研究队列：`coverage/cn-a/research_queue.jsonl`。
- 自选池：`research/watchlist.jsonl`，只能从全市场状态确定性重建。
- 正式报告：`research/companies/CN/{ticker}/reports/YYYY-MM-DD[-NN].md`。`report_path` 指向最新正式报告，这个指针就是 current。
- 研究日志：`research/companies/CN/{ticker}/updates/YYYY-MM-DD[-NN].md`，只能确认、观察或宣告当前报告失效。
- 隔离旧稿：`research/companies/CN/{ticker}/legacy/YYYY-MM-DD.md`，每家公司最多一份，永远不参与当前状态、估值或队列。
- 公告扫描只用 `coverage/cn-a/event_scan_state.json` 保存成功检查点和近期公告 ID。

正式报告、研究日志和历史旧稿都进入 Git。不得恢复会漂移的 `current.md` 副本，也不得用 `stale` 文件后缀表达公司状态。

仓库不保存证券价格触发线、armed/hit/rearm 状态或每日收盘扫描结果。网站如展示实时价格相对 `value_range` 的位置，只能现场机械派生，不得写回研究状态或解释为买入信号。

旧 manager-screen、quick/targeted/scoped/deep 阶段预算、价格触发、claim/seal、calibration、独立承保、challenger、仲裁和组合审批均已退役，不得重新引入。

## 角色与结果

- 主 Agent 批量浏览全市场压缩事实，逐项判断 `ignore / research_now`。
- `research_now` 写入 `candidate` 并创建唯一研究任务；不同公司可并行，同一公司只允许一个 Agent 端到端完成。
- 所有候选统一使用 `prompts/company/standard-deep-research.md`；没有研究强度等级、固定分钟数、复核 Agent 或经理审批。
- 公司研究状态只使用 `unseen / ignore / candidate / covered / stale`；证券范围只使用 `active / inactive`；活动任务只使用 `queued / running`。
- 正式结果只有 `ignore / covered`，两种结果都必须完成商业、财务、治理、估值和风险研究，并追加完整、自足的正式报告。
- `covered` 表示当前报告有效且值得持续维护；`ignore` 表示正式研究后仍不值得持续覆盖；`stale` 表示新事实已使当前报告失效，必须进入完整更新研究。

正式报告必须脱离历史版本独立可读。不得用“参见前序报告”“历史分析继续有效”“沿时间线回看”等句子代替正文。任何正常化利润、`value_range`、核心逻辑、风险排序或 `covered / ignore` 结论变化，都必须生成一份新的完整正式报告。

单公司层不输出仓位、`buy_now`、精确年化回报、承保意见或组合动作。数字应能从公开来源复核，但不建立 evidence ledger、SHA 权限链或多角色复核链。

## 日常触发与研究日志

- 全市场基线只完整执行一次；之后只处理新增公司及公司、财务、治理、资本结构和行业经营变量的新事实。
- 公告扫描覆盖全部 active 公司，包括 `ignore`。股票价格变化不是研究触发器；铜价、产品售价、运价、利率、汇率等经营变量仍可触发研究。
- 定期财报默认触发完整更新研究。公告若改变估值、正常化经营、逻辑、风险或正式结论，也直接触发完整研究。
- 不越过当前报告边界的事件可写 `updates/`：`reaffirmed` 确认报告，`monitor` 保留观察，`invalidated` 宣告报告失效并转 `stale`、创建完整研究任务。所有 update 都在公司状态行写入 `last_update` 审阅凭据，供外部系统可靠识别“已检查但正式报告未改变”。
- update 不得修改价值区间、正常化利润、核心逻辑、风险排序或 `covered / ignore`。需要改其中任何一项时，不写补丁式 update，直接写新的完整报告。

## 写入纪律

- worker 不直接修改共享 JSONL；协调器校验并原子写入。
- `research/watchlist.jsonl` 禁止手改。同一公司最多一个活动任务。
- 新正式研究只追加报告，不覆盖或删除历史报告；`report_path` 必须指向最新正式报告。
- `legacy/` 只允许通过旧研报归档工具写入，不得改变任何当前事实。
- 修改共享状态后重建自选池并执行 `python -m trading_os validate`。

## 开始工作

先读：

1. `playbooks/simple-research.md`
2. `prompts/goals/cn-all-a-continuous-research.md`

常用命令见 `README.md`。

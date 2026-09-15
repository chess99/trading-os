# Trading OS Agent Guide

除非用户主动要求切分支，否则直接在当前分支开发。文档默认使用中文。完成一个完整迭代后，只提交本次修改的文件；提交前检查暂存区，禁止带入用户或其他 Agent 的无关修改。

## 唯一事实源

- 全市场状态：`coverage/cn-a/research_state.jsonl`。
- 当前研究队列：`coverage/cn-a/research_queue.jsonl`。
- 自选池：`research/watchlist.jsonl`，只能从全市场状态确定性重建。
- 正式报告：`research/companies/CN/{ticker}/reports/YYYY-MM-DD[-NN].md`。只有通过协调器验收并由 `research complete` 原子写入的结果才是正式报告；`report_path` 指向最新合格正式报告，这个指针就是 current。
- 研究日志：`research/companies/CN/{ticker}/updates/YYYY-MM-DD[-NN].md`，只能确认、观察或宣告当前报告失效。
- 隔离旧稿：`research/companies/CN/{ticker}/legacy/YYYY-MM-DD.md`，每家公司最多一份，永远不参与当前状态、估值或队列。
- 公告扫描只用 `coverage/cn-a/event_scan_state.json` 保存成功检查点和近期公告 ID。
- 独立价值质量池：`screening/cn-a/value-quality/pool.json`；筛选规范见 `prompts/screening/cn-a-value-quality.md`，可读投影 `current.md` 只能由池文件确定性生成。

正式报告、研究日志和历史旧稿都进入 Git。worker 返回的结构化 JSON 和 `report_markdown` 在验收前只是候选稿，不进入正式时间线；验收失败直接丢弃，不创建报告文件，也不占用 `-02/-03` 序号。已经通过验收的历史正式报告保持不可变；误入库且能够确认从未完成验收的坏稿按数据修复删除，并恢复到前一份合格报告和原研究任务。不得恢复会漂移的 `current.md` 副本，也不得用 `stale` 文件后缀表达公司状态。

仓库不保存证券价格触发线、armed/hit/rearm 状态或每日收盘扫描结果。正式研究可以冻结不含现价的 `return_model` 持有人回报模型输入；IRR 只允许由展示层使用实时价格现场机械求解，不得写回研究状态或解释为买入信号、收益率门槛或投资授权。

旧 manager-screen、quick/targeted/scoped/deep 阶段预算、价格触发、claim/seal、calibration、独立承保、challenger、仲裁和组合审批均已退役，不得重新引入。

## 独立价值质量筛选层

价值质量池与单公司研究完全隔离。筛选只维护 `screening/cn-a/value-quality/pool.json`，不得修改研究状态、队列、自选池、公司报告或研究日志；池内成员不会自动成为 `candidate / covered`。单公司研究也不得根据该池改变状态或结论。

筛选可以独立获取公开信息，也可以把正式报告当作普通参考，但公司研究状态不是入池条件。池中不得保存现价、估值、回报率、仓位、交易动作、任务 ID、报告路径或 `return_model`。结果只维护当前全量版本，历史通过 Git 查看；`current.md` 禁止手改。

处理价值质量池时必须完整阅读 `prompts/screening/cn-a-value-quality.md`，使用独立的 `quality-pool status / validate / list / replace / rebuild` 命令。v2 每家公司必须有竞争优势、普通股现金、反证、分层理由及公开来源；证券身份清单与实际复核范围嵌入池文件。JSON 是唯一提交点，投影失败用 rebuild 恢复，不能把机械校验当作商业认证。这里的价值质量筛选不要与下文决定 `ignore / research_now` 的研究队列初筛混淆。

## 角色与结果

- 主 Agent 批量浏览全市场压缩事实，逐项判断 `ignore / research_now`。
- `research_now` 写入 `candidate` 并创建唯一研究任务；不同公司可并行，同一公司只允许一个 Agent 端到端完成。
- 所有候选统一使用 `prompts/company/standard-deep-research.md`；没有研究强度等级、固定分钟数、复核 Agent 或经理审批。
- 公司研究状态只使用 `unseen / ignore / candidate / covered / stale`；证券范围只使用 `active / inactive`；活动任务只使用 `queued / running`。
- 正式结果只有 `ignore / covered`，两种结果都必须完成商业、财务、治理、估值和风险研究，并追加完整、自足的正式报告。
- `covered` 表示当前报告有效且值得持续维护；`ignore` 表示正式研究后仍不值得持续覆盖；`stale` 表示新事实已使当前报告失效，必须进入完整更新研究。

正式报告必须脱离历史版本独立可读。不得用“参见前序报告”“历史分析继续有效”“沿时间线回看”等句子代替正文。任何正常化利润、`value_range`、`return_model` 输入、核心逻辑、风险排序或 `covered / ignore` 结论变化，都必须生成一份新的完整正式报告。

每次新正式研究都必须提交非空 `return_model_note`；能够可靠建模时同时提交结构化 `return_model`，否则提交 `return_model: null`，并在 note 中说明原因。V1 统一使用五年主口径：五个年度的普通股每股现金分配和第五年末普通股每股终值区间；三年口径可选，但必须单独研究第三年末终值，不得从五年终值机械折算。当前 `value_range` 是当前合理价值，绝不能充当未来终值。行业和公司可以采用不同的经营预测与终值方法，最终都必须归一到这一接口。

单公司层不输出仓位、`buy_now`、随现价变化的 IRR、承保意见或组合动作，也不输出收益率阈值、概率权重、价格触发状态或交易建议。数字应能从公开来源复核，但不建立 evidence ledger、SHA 权限链或多角色复核链。

## 日常触发与研究日志

- 全市场基线只完整执行一次；之后只处理新增公司及公司、财务、治理、资本结构和行业经营变量的新事实。
- 公告扫描覆盖全部 active 公司，包括 `ignore`。股票价格变化不是研究触发器；铜价、产品售价、运价、利率、汇率等经营变量仍可触发研究。
- 定期财报默认触发完整更新研究。公告若改变估值、正常化经营、`return_model` 输入、逻辑、风险或正式结论，也直接触发完整研究。
- 不越过当前报告边界的事件可写 `updates/`：`reaffirmed` 确认报告，`monitor` 保留观察，`invalidated` 宣告报告失效并转 `stale`、创建完整研究任务。所有 update 都在公司状态行写入 `last_update` 审阅凭据，供外部系统可靠识别“已检查但正式报告未改变”。
- update 不得修改价值区间、正常化利润、`return_model`、`return_model_note`、核心逻辑、风险排序或 `covered / ignore`。需要改其中任何一项时，不写补丁式 update，直接写新的完整报告。

## 写入纪律

本轮用户明确授权的例外：依 `docs/reviews/2026-09-system-upgrade/report-scope.json` 审核已吸收2026中报的当前报告，可原路径修订并同步结构化研究字段；具体执行 `prompts/company/current-report-review.md`。此授权不延伸到清单外报告、legacy、历史版本或之后的常规研究，Git 保留原文。审核旧截止报告不能清除更晚事实造成的 stale 和任务。

- worker 不直接修改共享 JSONL；协调器校验并原子写入。
- `research/watchlist.jsonl` 禁止手改。同一公司最多一个活动任务。
- 新正式研究通过验收后只追加报告，不覆盖或删除已经合格的历史报告；`report_path` 必须指向最新合格正式报告。未通过验收的候选稿直接丢弃，不进入本规则所称的历史报告。
- `legacy/` 只允许通过旧研报归档工具写入，不得改变任何当前事实。
- 修改共享状态后重建自选池并执行 `python -m trading_os validate`。

## 开始工作

系统分层：研究队列初筛见 `prompts/screening/research-triage.md`；产业框架见 `research/industries/README.md`；单公司研究与验收沿用下列工作流；长期精选见 `selection/principles.md` 和 `prompts/selection/long-term-selection.md`。精选、产业知识与独立质量池均不产生公司研究状态或价格交易指令。

先读：

1. `playbooks/simple-research.md`
2. `prompts/goals/cn-all-a-continuous-research.md`

若任务涉及价值质量池，再读 `prompts/screening/cn-a-value-quality.md`。

常用命令见 `README.md`。

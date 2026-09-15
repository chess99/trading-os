# Trading OS

Trading OS 是一套面向 A 股、由新事实驱动的轻量研究工作流。仓库的主要产品是可审计的公司研究状态、完整正式报告和研究日志；网站只是这些资产的只读展示。系统不做自动交易，也不因股票价格变化启动研究。

仓库另有一层完全隔离的价值质量筛选：它从全市场维护一个当前商业质量池，不创建研究任务，也不改变公司研究状态。筛选规范与结果都随 Git 保存，但不保留重复的日期化筛选快照。

## 核心机制

1. 主 Agent 对全市场压缩事实只判断 `ignore / research_now`。
2. `research_now` 把公司标记为 `candidate` 并创建唯一研究任务；一家公司由一个 Agent 用统一提示词端到端完成。
3. 正式结果只有 `covered / ignore`；worker 先返回候选 JSON，协调器验收通过后才原子追加一份脱离历史版本也能独立阅读的完整报告。
4. 财报、公告、治理、资本结构及行业经营变量触发研究；定期财报以及任何估值或结论变化，都生成新的完整正式报告。
5. 不改变正式结论的事件可以写研究日志；日志只能 `reaffirmed / monitor / invalidated`，不能充当报告补丁。
6. 证券价格不进入研究触发、公司状态或队列。展示层可以把实时价格与 `value_range` 机械比较，但这不是买入信号或投资决策。
7. 正式研究冻结五年为主的 `return_model` 输入；展示层再把实时价格代入统一公式机械求解 IRR。研究仓库不保存随价格漂移的 IRR，也不设置收益率门槛、概率权重或价格触发状态。

没有研究强度分档、固定分钟数、复核 Agent、独立承保、经理审批、多 Agent 共识、收益率硬门槛或仓位审批。

研究围绕少数决定性商业问题取证，现有协调器同时检查关键原证、相反解释及经营假设怎样进入估值；具体见[商业判断验收](playbooks/simple-research.md#商业判断验收)。[产业专题](research/industries/README.md)按需积累跨公司知识，供研究者核验和反驳，不维护第二套公司状态。[星宇样本审查](docs/reviews/2026-09-15-xingyu-research-quality-review.md)展示了这套方法的依据和边界。

## 各层如何协作

| 层 | 回答的问题 | 入口与结果 |
|---|---|---|
| 研究队列初筛 | 哪些公司值得完整研究？ | [初筛方法](prompts/screening/research-triage.md)，`screen record` |
| 独立价值质量筛选 | 哪些已有优势与普通股现金证据？ | [质量池](prompts/screening/cn-a-value-quality.md)，独立维护 `pool.json` |
| 产业知识 | 利润由谁创造、谁取得，如何跨公司验证？ | [全行业框架](research/industries/README.md)，`industry list / validate` |
| 单公司研究 | 公司经济学、合理价值和条件现金回报如何？ | [完整深研](prompts/company/standard-deep-research.md)，正式报告及事件维护 |
| 协调验收 | 证据、推理与结构化结果是否一致？ | [验收规则](playbooks/simple-research.md#商业判断验收)，同一协调器串行落库 |
| 长期精选 | 哪些更值得长期拥有和等待？ | [原则](selection/principles.md)、[当前精选](selection/current.md)，文本取舍，不自动配置资金 |

网站提供研究台、研报库、产业研究和长期精选四个入口，均从仓库生成只读展示。研究覆盖池包含全部有效 covered，不等同长期精选。行情和机械IRR属于临时展示，不能代替商业判断。

[2026-09全层迭代](docs/reviews/2026-09-system-upgrade/README.md)包含用户授权的中报当前稿原路径修订例外。仅清单内报告可使用 `reports revise-current --scope <清单> --expected <审核前原文> --input <完整候选>`；正常研究继续追加正式报告，历史归档不参与本轮。

## 当前事实源

```text
coverage/cn-a/research_state.jsonl                       全市场当前状态，一家公司一行
coverage/cn-a/research_queue.jsonl                       当前 queued/running 任务
coverage/cn-a/screening_baseline.json                    全市场初筛基线
coverage/cn-a/event_scan_state.json                      公告扫描成功检查点
research/watchlist.jsonl                                 active covered 的确定性投影
research/companies/CN/{代码}/reports/YYYY-MM-DD[-NN].md 完整正式报告时间线
research/companies/CN/{代码}/updates/YYYY-MM-DD[-NN].md 研究日志
research/companies/CN/{代码}/legacy/YYYY-MM-DD.md        隔离旧稿
screening/cn-a/value-quality/pool.json                    独立价值质量池唯一结果源
screening/cn-a/value-quality/current.md                   由当前池生成的可读投影
```

`research_state.jsonl.report_path` 指向该公司最新合格正式报告，这个指针就是 current；同一天再次完成并通过验收的正式研究才依次写为 `-02`、`-03`。正式报告必须自足，禁止用“参见前序报告”替代商业、财务或估值正文。未通过验收的候选稿直接丢弃并重新排队，不创建报告文件、不推进指针，也不占序号；能够确认从未完成验收的历史误入稿可按数据修复删除，合格历史报告仍不可变。

财报更新不是给旧正文增加摘录：必须重写完整报告，区分累计与单季口径，逐项复核关键数字和截止日，并说明前次假设与本期实际如何改变判断和估值。新结果会拒绝已知拼接模板、财报原始片段、重复或冲突截止日、退役价格线，以及与结构化 `value_range` 不一致的正文核心合理价值区间；这些规则不追溯改写历史报告。

每份新正式结果都必须包含非空 `return_model_note`；能够可靠建模时同时包含结构化 `return_model`，否则包含 `return_model: null`，并在 note 中说明原因。V1 固定使用 `annual_common_equity_irr_v1`：

- 五年是主口径，提交未来第 1—5 年一股持续持有人实际收到的现金分配，以及独立研究的第五年末普通股每股终值区间；
- 三年口径可选，必须使用独立研究的第三年末终值，不得从第五年终值机械折现或插值；
- 公开市场回购不计入年度现金分配；回购注销、增发、可转债和期权稀释通过未来完全稀释股数与终值每股口径体现；
- 当前 `value_range` 是当前合理价值，不是第三年或第五年的未来终值；
- 行业经营预测、权益桥和终值方法可以不同，最终都归一为年度普通股每股现金分配和未来普通股每股终值区间。

正式报告正文保存“基准持有人回报模型输入”和口径说明，不保存由报告时点价格算出的 IRR。任何年度分配、终值、普通股权益桥或稀释口径变化，都必须生成新的完整正式报告。

`updates/` 记录事件处理过程：

- `reaffirmed`：新事实确认当前报告；
- `monitor`：信息尚未越过原报告边界，继续观察；
- `invalidated`：当前报告失效，状态转 `stale` 并创建完整研究任务。

update 不得调整 `value_range`、正常化利润、`return_model`、`return_model_note`、核心逻辑、风险排序或 `covered / ignore`。财报后即使商业逻辑未变，只要估值或持有人回报模型输入需要调整，也必须写一份新的完整正式报告。

已有正式报告的公司不能再通过初筛命令直接转为 `stale`。扫描到的新事实必须先与当前报告的 `information_cutoff` 比较：已被报告吸收的旧公告不触发任何状态变化；报告截止日之后、但仍在原报告边界内的事实写 `reaffirmed / monitor`；确实使报告失效时，必须用 `updates record` 写入带明确事实截止点的 `invalidated` 日志，再由系统转为 `stale` 并创建更新研究任务。

## 状态

- `unseen`：尚未完成首次初筛；
- `ignore`：当前不值得正式研究，或正式研究后不值得持续覆盖；
- `candidate`：已选中，等待或正在正式研究；
- `covered`：已有当前有效正式报告，值得持续维护；
- `stale`：重大新事实使当前报告失效，等待完整更新。

证券范围另用 `active / inactive`；任务另用 `queued / running`。只有 active `covered` 进入自选池。

## 可视化研究台

`dashboard/` 是只读附属展示。它从仓库状态和正式报告生成页面，不维护第二套研究事实。实时行情用于显示现价与合理价值区间的机械关系，例如 `当前价格 / value_range.low`；若存在 `return_model`，还可按 `现价 = Σ[D_t/(1+r)^t] + TV_H/(1+r)^H` 现场求解终值区间两端对应的 IRR。五年是主展示口径，只有模型含独立 `year_3` 时才补充三年结果。

行情缺失或公式无法求解时显示 `—`。IRR 只由当前行情和冻结的研究输入机械派生，不写回仓库，不触发研究，也不生成仓位、交易建议、收益率阈值、概率权重、价格提醒、“关注价”“安全边际充分”或 armed/hit/rearm 状态。

```bash
cd dashboard
npm install
npm run dev
```

## 独立价值质量池

价值质量池只回答“哪些公司值得长期研究”，不表达买入、仓位或当前估值。它不读写研究队列，单公司研究也不从该池派生状态。完整方法见 [价值质量筛选规范](prompts/screening/cn-a-value-quality.md)。

```bash
python -m trading_os quality-pool status
python -m trading_os quality-pool validate
python -m trading_os quality-pool list --tier core_moat
python -m trading_os quality-pool replace --input <完整池.json>
```

`pool.json` 是唯一结果源，`current.md` 只能由 `replace / rebuild` 确定性重建。成员增删和分层变化直接替换当前池；需要历史时查看 Git。v2 强制保存竞争优势、普通股现金、反证、分层理由及公开来源，并嵌入独立证券身份与实际复核范围。投影损坏时 `status/list` 仍读权威 JSON，运行 `python -m trading_os quality-pool rebuild` 恢复；`validate` 只做机械检查，不认证商业结论。

## 常用命令

```bash
# 查看与校验
python -m trading_os status
python -m trading_os validate

# 独立价值质量池（不会改变单公司研究）
python -m trading_os quality-pool status
python -m trading_os quality-pool validate

# 一次性从 schema v1/v2 迁移到无证券价格触发的 v3
python -m trading_os state migrate-v3 --at 2026-08-14T17:00:00+08:00

# 记录初筛、派发并完成完整研究
python -m trading_os screen record --input templates/screen-decisions.json
python -m trading_os research next --limit 4
python -m trading_os research complete --input templates/research-result.json

# 记录不改变正式结论的事件处理；invalidated 会自动进入完整研究
python -m trading_os updates record --input templates/research-update.json

# 重建或查看 active covered 投影
python -m trading_os watchlist build
python -m trading_os watchlist list

# 获取并完成全市场公告判断
python -m trading_os events fetch --since 2026-08-09T00:00:00+08:00 \
  --until 2026-08-09T07:30:00+08:00 --output tmp/event-packet.json
python -m trading_os events complete --packet tmp/event-packet.json \
  --input templates/event-judgments.json
```

`research complete` 使用 [研究结果模板](templates/research-result.json) 接收结果。机械校验负责结构化 `return_model` 合同、非空 `return_model_note` 和正文“基准持有人回报模型输入”章节是否存在；它不解析正文中的模型数字，正文与结构化输入是否一致由协调器验收时核对。CLI 不接收现价或 Agent 自报 IRR；动态 IRR 只在可视化研究台请求行情后现场计算。

公告扫描负责发现、判断、记录 update 和创建任务，不消费研究队列。`research next` 与后续完整研究由独立的队列消费者执行，避免一次扫描同时承担抓取、裁决和深度研究而超时。正常扫描应从成功检查点直接推进到当前时间；短时间窗仅用于故障恢复，不应成为长期积压机制。公告抓取失败时保持原检查点，不产生部分状态更新。完整约束见 [精简研究流程](playbooks/simple-research.md)。

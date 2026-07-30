# 研究资本配置 Playbook

## 核心原则

研究时间本身也是资本，但“节约研究时间”不能变成“先用机械指标决定哪些公司不值得被看”。冻结范围内每家公司先获得一次独立 Agent 的 rapid triage；只有 Agent 看过以后，才竞争更多研究预算。

下一小时优先投向：最可能改变组合决策、关键未知能够被公开证据解决、当前或近期可能形成赔率，而且相对其他候选更值得购买信息的公司。这个判断必须写成可读理由，不伪装成精确分数。

外部程序化选股可以提供线索和材料，但不得：

- 决定公司是否获得 rapid triage；
- 直接晋级正式画像、深研或承保；
- 成为买入、仓位或永久停止结论。

换句话说，它不能直接把公司晋级为深研，也不能让任何范围内公司失去被快速查看的资格。

## 自适应研究漏斗

| 层级 | 默认单周期容量 | 单家公司预算 | 只回答什么 |
|---|---:|---:|---|
| L0 范围冻结 | 冻结 universe 全量 | 批次级 | 哪些证券在范围内，哪些是硬排除或异常 |
| L1 快速甄别 | 全量；行政小批次 | 约 15 分钟 | 当前是否值得购买下一小时研究信息 |
| L2 正式投资画像 | 最多 40 | 约 1 小时 | 是否存在一条可信投资路径 |
| L3 范围研究 | 最多 15 | 约 4 小时 | 决定性未知能否由证据解决 |
| L4 完整深研 | 最多 6 | 约 24 小时 | 重建业务、会计、正常化盈利和估值 |
| L5 独立承保 | 最多 3 | 12 小时起 | 深研主张能否经半盲复核通过 |
| L6 组合决策 | 所有有效 passed 公司 | 组合层 | 最新价格下是否优于其他机会、如何配置 |

容量是上限，不是配额。L1 的“全量”不表示一次冻结约 5500 家；按 20—50 家稳定切批，保证每个 cohort 可完成、可封存、可恢复。

## L1 快速甄别

快速甄别读取最新定期报告、必要公告、旧研究和近期价格，但必须形成新的 Agent 判断，而不是复述旧评级。结构化 package 至少包含：

- `review_mode`、prior research 和触发上下文；
- 两三句话的业务简述与变化摘要；
- 生存、治理和资本结构判断；
- 正常化盈利粗判及其依据；
- 当前价格隐含预期；
- 最强反方证据与决定性问题；
- 结构化重启触发器；
- S1/价格来源和真实 provenance。

结果只能表示当前研究资本去向：等待横向比较、价格观察、条件停止、能力圈转派或返回目录。单家公司完成后不得立即晋级，也不得给组合操作。

## 横向分配正式画像预算

同一 cohort 全部简报封存且发布到公司时间线后，生成 comparison packet。独立 allocation Agent 必须逐项审阅并为每家公司提交：

- `select_quick_profile` 或 `defer`；
- 为什么下一小时值得或不值得购买；
- 最可能改变判断的决定性问题；
- 已考虑的反证；
- 风险簇与相对机会成本。

程序只执行形式和约束验证，不根据旧 priority、lens 数量、PE、完成顺序或固定加权公式代替 Agent 排序。多个视角仍可用于 Agent 检查盲区和分配风险簇容量，但不能变回 L1 前置筛选器。

## 风险簇与行业证据

不设必须填满的行业配额。正式画像以后按 policy 限制同一经济风险簇的集中度；没有合格替代者时容量留空。

在可信、可审计的经济风险簇分类机制建立以前，程序把所有待晋级公司保守视为同一个
`unclassified` 风险簇。因此 L1 横向配置即使总容量为 40，也最多只能选择 policy 中
`risk_cluster_caps.quick_profile` 允许的数量；当前默认是 10。要使用剩余容量，必须先封存
逐公司的风险簇分类、依据和校验结果，再由程序按簇执行上限。Agent 不得用未经证据支持的
`diversified` 标签绕过限制。

银行、保险、资源、周期制造等行业使用各自证据要求。银行不能仅凭低 PB、低 PE 或静态 ROE 晋级；必须核验最新 S1 财报、资产质量迁徙、资本充足、正常化信用成本与少数股东可得收益等 policy 要求。

## 停止、停放与重启

快速停止不是把公司永久贴成“垃圾”，而是当前停止购买低价值信息：

- `hard_exclusion`：证券身份不在范围、退市或法律上不能形成投资对象；
- `conditional_stop`：可靠证据显示少数股东权益不可承保、财务不可核验、无法生存、资本结构吞噬权益价值或核心论点已证伪；
- `price_watch`：业务可能可投，但当前价格隐含预期过高；
- `targeted_followup`：只补一项或少数决定性证据；
- `reassign_or_stop`：超出当前 Agent 能力圈，先转给对应行业 Agent；
- `catalog`：当前没有足够研究信息价值，等待明确变化。

除真正硬排除外，每次停止或停放都必须记录事实理由、反证、未知数以及至少一个可执行的 filing、price、date/TTL、event 或 thesis 重启条件。亏损、负 PE、小市值、低流动性或行业冷门不能单独构成停止理由。

## 假阴性控制

独立 allocation Agent 会二次阅读整个 cohort，而不是只读 selected symbols。除此之外，按长程 Goal 第一阶段新增并封存的质量审计 policy，对 `catalog`、`price_watch`、`conditional_stop` 和 `reassign_or_stop` 做确定性的分层假阴性抽查。该 policy 必须明确样本率、稳定选样种子、错误阈值和扩样规则；旧排名中的 `false_negative_audit` selection slot 不是质量审计 policy：

- 硬排除的证券身份 100% 复核；
- 抽查 Agent 尽量不读取原结论措辞，只读事实包与来源；
- 重大分歧直接重开公司；
- 某一分层错误率超阈值时扩样或重做该层；
- 抽查结果与 provenance 必须封存，不能只在对话里口头确认。

续审使用不可变轮次链：每一轮 plan 必须绑定上一轮 result 的路径与 SHA-256，并严格执行该 result 指定的扩样 symbol 或整层重做。finding 的 `severity` 表示发行人事实风险，不直接等同于原路由错误；错误率按 reviewer 建议路由与原路由的差异计算。

重大分歧不得直接改旧 package 或旧 result。先冻结仅包含全部 reopen symbols 的 correction cohort；每家公司换新的独立 Agent 形成新的不可变 package，再完成 correction cohort 自身质量门。最后封存 resolution，把原 package、触发分歧的 result、新 package 和 correction quality gate 串成 SHA-256 链；原 cohort 的 comparison 只可读取 resolution 指定的新 package。

## 后续升级纪律

完成顺序不是投资质量，任何同层结果都不能因为先完成而先晋级。

- L1 只有完整 cohort 封存、抽查和独立横向决策后，才能进入 L2。
- L2、L3 同样先完成同层 cohort，再由独立 Agent 统一竞争下一层容量。
- L3 只有在业务可理解、生存与治理基本通过、正常化盈利可建立且粗估值存在可信回报路径时，才能进入 L4。
- L4 只有证据、估值与反证完整，且相对其他机会仍有竞争力时，才购买独立承保预算。
- 单公司任何层级都不得给最终买入与仓位；只有组合层可以。

当前代码只在 rapid-triage → quick-profile 层实现了上述独立 decisions 契约；历史
`profile-finalize` 仍使用 score/priority 机械选择。它只可用于兼容旧资产，不符合新增长程
Goal 的晋级要求。长程执行在跨过 L2 或 L3 前，必须先把对应层迁移为 sealed comparison
packet、独立 Agent 全量 decisions 和可恢复物化，并完成故障注入试运行。

## 命令

```bash
python -m trading_os coverage scope-freeze <run-id> --mode auto --scope-cutoff <timestamp>
python -m trading_os coverage scope-status <run-id>
python -m trading_os coverage quality-scope-prepare <run-id>
python -m trading_os coverage quality-scope-record <run-id> --reviews <identity-reviews.json>
python -m trading_os coverage triage-freeze <cycle-id> --scope-run-id <run-id> --quality-policy-snapshot <policy-snapshot.json> --scope-identity-result <identity-result.json> --queue-status requires_rebaseline --symbols-file <scope-derived-symbols.json>
python -m trading_os coverage triage-claim <cycle-id> --agent <agent-id> [--symbol CN:000000]
python -m trading_os coverage triage-record --input <rapid-triage.json>
python -m trading_os coverage triage-status <cycle-id>
python -m trading_os coverage quality-triage-prepare <cycle-id>
python -m trading_os coverage quality-triage-record <cycle-id> --reviews <quality-reviews.json>
python -m trading_os coverage quality-triage-continue <cycle-id>
python -m trading_os coverage quality-triage-record-continuation <cycle-id> --reviews <quality-reviews.json>
python -m trading_os coverage quality-triage-correction-prepare <cycle-id> <correction-cycle-id>
python -m trading_os coverage quality-triage-correction-resolve <cycle-id> <correction-cycle-id>
python -m trading_os coverage triage-compare <cycle-id>
python -m trading_os coverage triage-finalize <cycle-id> --decisions <agent-decisions.json>
python -m trading_os coverage evaluate-profile --input <quick-profile.json>
python -m trading_os coverage record-profile --input <quick-profile-package.json>
python -m trading_os coverage profile-status <cycle-id>
python -m trading_os coverage profile-claim --agent <agent-id> [--symbol CN:000000]
python -m trading_os coverage profile-release --agent <agent-id> --symbol CN:000000 --failure-reason <reason>
```

历史 `allocate-research`、`apply-allocation` 和 `profile-finalize` 只为旧资产兼容保留，不得用于新增长程 Goal。

单公司 Agent 只提交自己的 package，不能手工编辑共享队列。`triage-record` 验证并封存 package，再幂等发布到公司时间线；`triage-finalize` 只应用独立 Agent 的显式全量决策，不生成机械投资排名。

所有会改写 `screening.jsonl` 或 `research_queue.jsonl` 的正式 workflow 共用 coverage 写锁。
根 Agent 仍是共享状态的唯一写入者；遇到 `coverage state is busy` 时应等待当前写入结束后重试，
不得绕过锁手工改 JSONL。`.coverage-write.lock` 是持久哨兵文件，真正的占用状态由操作系统锁
管理；进程退出后会自动释放，不要根据文件是否存在手工判断或删除活锁。

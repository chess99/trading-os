# 全 A 股 Goal 长程执行 Playbook

## 目标与边界

目标不是用机械指标挑出一小批公司供 Agent 阅读，而是让冻结范围内的每家普通 A 股都先被独立 Agent 快速看一眼，再把有限研究时间集中到最可能改变组合决策的少数公司。

一次 Goal 必须在启动时冻结：

- 普通 A 股 universe 及来源哈希；
- `scope_cutoff`；
- baseline 与 incremental 两条 lane 的输入；
- 纳入、硬排除、异常和延后项的完整分区。

截止时间后的上市、财报、公告和价格变化进入下一轮，不能令当前 Goal 无限增长。可直接引用 `prompts/goals/cn-all-a-continuous-research.md` 启动长期任务。

## 生产流程

```text
冻结全覆盖或已命中触发的范围
→ 按行政规则切成小 cohort
→ 每家公司一个独立 Agent 做 rapid triage
→ 封存并发布到公司不可变时间线
→ 独立质量抽查
→ 生成全量 comparison packet
→ 独立 allocation Agent 显式配置下一层预算
→ quick profile → scoped research → deep research
→ 半盲独立承保 / challenger
→ 最新行情下的组合综合
```

行政规则可以使用触发紧急度、逾期时间、等待时间和 symbol 稳定顺序，但不得使用因子、PE、市值、流动性、利润正负或旧投资评级决定谁有资格进入 rapid triage。

cohort 大小只是可恢复的执行边界，不是投资容量。建议使用 20—50 家的小批次；同一 cohort 的全部公司达到有效终态前，不得进行横向晋级。

## 两条研究 lane

### Baseline

处理冻结 universe 中缺少“当前 rapid-triage 协议有效终态”的全部公司。`requires_rebaseline` 只是一个 intake 提示，不是 baseline 的集合定义；legacy `completed`、watch 状态以及缺失 queue 的范围内公司，只要没有当前协议终态，也必须纳入 scope-to-queue 守恒。旧报告只能作为 prior research 和线索；Agent 必须核验足以支持本轮判断的最新 S1 信息与近期价格。有效快速甄别进入公司时间线后，才能清除已有的 `rebaseline_required`。

### Incremental

处理截止日前真实命中的增量事件：新财报、重大公告、价格阈值、论点失效、固定日期或证据 TTL 到期。触发器定义不是 trigger hit；filing、event、thesis 必须有可追溯观察记录，价格和日期必须由程序按结构化条件判断。

紧急增量 cohort 不必等待全市场 baseline backlog 清空，但两条 lane 只是逻辑上并行。每个 symbol 同时只能有一个可变任务所有者；启动生产执行前必须封存 arbitration 契约，规定新事件如何合并到活动任务、何时可抢占、何时延后，以及 hit 何时标记 consumed。容量政策需给 baseline 保留最低处理通道，避免长期被事件任务饿死。

## Rapid triage 的最低标准

每家公司最多投入轻量预算，但不是只看一个倍数。必须形成可审计简报，至少覆盖：

1. 业务如何赚钱；
2. 相对旧研究出现的变化；
3. 生存、强制稀释、资本结构和治理红旗；
4. 正常化盈利粗判及依据；
5. 当前价格隐含的要求；
6. 最强反方证据；
7. 再投入下一小时能解决的决定性问题；
8. 当前停止时的结构化重启条件；
9. 真实来源、工具、模型和信息截止时间。

快速简报也是公司不可变时间线的一部分。`meta.json` 只在简报、来源和 seal 全部验证后更新；coverage 队列不得先行声称完成。

## 横向预算配置与抽查

完整 cohort 封存后，程序生成包含全部条目的 comparison packet。未参与单公司甄别的独立 Agent 必须逐家公司给出 `select_quick_profile` 或 `defer`，并说明理由、决定性问题、已考虑的反证和相对研究成本。程序只校验全量覆盖、容量、风险簇、provenance 和禁止字段，不自动计算投资排名。

硬排除做 100% 身份复核。对 `catalog`、`price_watch`、`conditional_stop` 和 `reassign_or_stop`，按本 Goal 第一阶段新增并封存的质量审计 policy 做确定性分层抽查；该 policy 必须明确定义样本率、稳定选样种子、错误阈值和扩样规则，不得复用旧排名的 `false_negative_audit` selection slot。重大分歧重开该公司，某一分层错误率超限时扩大抽样或重做该层。续审轮次必须绑定上一轮封存结果；review finding 的严重度描述发行人事实风险，抽样错误率只按独立 reviewer 与原路由的差异计算，避免同为 `conditional_stop` 的重大风险事实造成无限重做。重大分歧通过专用 correction cohort 绑定原 package、触发 result 与新 package；correction cohort 自身质量门通过后才能封存 resolution，原 comparison 必须使用 resolution 指定的新 package。抽查完成前不得宣告整个 cycle 完成。

## 启动与恢复

1. 读取 `AGENTS.md`、本文件、`research-capital-allocation.md`、`screening.md`、`batch-dispatch.md`、`portfolio-synthesis.md` 和当前 policy。
2. 检查 Goal、Git、运行中 Agent、冻结 scope、coverage、公司时间线与已有 seal。保留用户和其他 Agent 的改动。
3. 同一 `run_id` 只冻结一次；续跑时以“冻结范围减去已验证的当前协议终态”重建工作清单，并先把 legacy 状态与缺失 queue 的范围成员守恒物化到 baseline intake。
4. 已有有效产物但状态未物化时做幂等发布或 reconcile，不重做公司。
5. 运行中任务只在租约失效后释放，并保留 `attempt_history`；失败后换独立 Agent。
6. 每个小批次完成即验证、封存、回写并只提交该批次自己的文件。

## 强制闸门

- 范围内每家公司必须有 rapid-triage 终态或结构化硬排除。
- 单家公司一个 Agent；跨公司预算配置必须由另一个 Agent 完成。
- 单公司完成顺序不得影响晋级。
- 非硬停止必须有 schedule/alerts 可消费的重启触发器。
- 单公司层不得给 `buy_now`、组合操作或仓位。
- 深研必须生成结构化主张和来源，封存后才能进入独立承保。
- 重大分歧、高风险或潜在核心仓位按 policy 触发 challenger；无可靠共识时不通过。
- 组合层必须以最新行情重新计算，不能复述旧报告价格。

## 关键命令

```bash
python -m trading_os coverage scope-freeze <run-id> --mode auto --scope-cutoff <timestamp>
python -m trading_os coverage scope-status <run-id>
python -m trading_os coverage trigger-checkpoint <run-id>
python -m trading_os coverage lane-freeze <run-id> --baseline-minimum-slots 1
python -m trading_os coverage quality-scope-prepare <run-id>
python -m trading_os coverage quality-scope-record <run-id> --reviews <identity-reviews.json>
python -m trading_os coverage triage-freeze <cycle-id> --scope-run-id <run-id> --quality-policy-snapshot <policy-snapshot.json> --scope-identity-result <identity-result.json> --queue-status requires_rebaseline --symbols-file <scope-derived-symbols.json>
python -m trading_os coverage triage-claim <cycle-id> --agent <agent-id>
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

python -m trading_os coverage profile-claim --agent <agent-id>
python -m trading_os coverage record-profile --input <profile-package.json>
python -m trading_os coverage profile-status <cycle-id>

python -m trading_os assets validate
python -m trading_os coverage validate
python -m trading_os coverage reconcile --check
python -m trading_os index rebuild
python -m trading_os schedule build
python -m trading_os alerts build
```

上面的 `triage-freeze` 只能在 scope-to-queue intake 已经把该小批次归一为兼容状态后使用。历史 `allocate-research`、`apply-allocation` 和 `profile-finalize` 不得用于新 Goal；L2/L3 的独立 decisions 新入口尚未建设，必须先完成迁移与试运行。

新 Goal 的生产 cohort 使用 schema v3：必须同时绑定已通过的 scope identity audit
result 和该审计的 policy snapshot。schema v1/v2 仍可读取历史，但不能作为新 Goal 的
横向晋级证明。`triage-compare` 与 `triage-finalize` 会验证 cycle quality result 已通过，
并验证 allocation Agent 不属于单公司研究 Agent 或质量 reviewer。

触发事件事实源是 `coverage/cn-a/trigger-hits/events.jsonl` 的全局哈希链；state 只是可重建
投影。每个 run 的 checkpoint 冻结账本前缀，随后才生成 incremental intake 与 lane
arbitration。price 采用 true edge / false rearm；date/TTL 只消费真正 due 的 schedule 行；
filing/event/thesis 必须通过 `coverage trigger-observe` 写入真实 occurrence evidence。结果发布
到公司时间线且 coverage 已物化后，`triage-record` 才消费 package 中显式绑定的 hit IDs。

## 完成定义与交付

完成不是“队列跑过一遍”，而是冻结范围数量守恒、所有公司有有效终态、公司时间线与 coverage 一致、抽查闭环、每层先完整封存再晋级、触发器能被调度消费、承保与组合产物有效、全部验证通过。

最终向用户列出 scope 与 cutoff、覆盖和各层数量、抽查及分歧、承保与组合结论、增量触发闭环、数据局限、验证和提交。持仓截图、个人成本和实际仓位等隐私只可用于本地判断，不得写入公开仓库。

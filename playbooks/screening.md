# 全市场初筛 Playbook

## 原则

初筛回答的是“现在是否值得购买下一小时研究信息”，不是完整估值，也不是买卖建议。

全市场初筛由同一投资经理 Agent 批量完成。程序可以压缩数据、冻结顺序和校验输出，但不能替 Agent 做业务理解和研究价值判断。

## 行政 intake

可以决定处理顺序的字段：

- 已观察事件的紧急度；
- 逾期和等待时间；
- 是否缺少当前 manager-screen terminal；
- scope intake ordinal 和 symbol 稳定顺序。

不得用于剥夺初筛资格：

- PE、PB、ROE 或任何机械因子；
- 小市值、低流动性、利润正负；
- 行业、风格或旧评级；
- 完成先后。

## 压缩 dossier

packet 对每家公司提供：

- 证券身份、行业、价格、市值和基础估值快照；
- 主营摘要、近三年收入/利润/扣非利润/经营现金流和最新中期数据；
- 现金、有息债务、应收、存货、商誉、合同资产与审计意见；
- 数据缺口；缺失不是静默排除理由，而是降低置信度或形成决定性问题；
- prior screening 与 queue 摘要；
- 已有公司时间线的最新指针、承保/估值摘要和触发器；
- 可引用的 evidence ID。

其中行情必须覆盖完整 universe、带来源与时间，并在 batch freeze 时重新校验实际年龄；不能相信自报的 `fresh` 字段。默认最大年龄 72 小时、未来容忍 5 分钟；日期型 A 股收盘价按当日 15:00，盘中价必须带时区。快照一旦封存不得覆盖，只能创建绑定原 snapshot 路径/SHA-256 的 sealed quote amendment；batch 必须显式绑定所采用 amendment。

投资经理可对少数信息不足项补查一手来源，并在 `additional_evidence` 中记录 URL、访问时间和 symbol。不要为了每家公司都查完整年报而把初筛变成深研。

## Manager-screen decision contract v3

以下 contract 只适用于未来新冻结的 v3 batch。旧 sealed v1/v2 batch、packet、result 和 quote-impact 资产保持原样，不回写、不迁移，也不为了采用 v3 重做历史决策。v3 继承 v2 的 canonical fact line、风险回应和 quote-impact 完整 replacement 规则。

- packet 为每家公司程序生成 `decision_support.canonical_fact_line` 对象；`one_line_reason` 必须以其中的 `.text` 作为逐字、逐字符的精确前缀，并紧接一个全角分号；前缀之后只能追加投资经理的定性判断。
- 定性后缀不得手抄、重算、四舍五入或“纠正”市值、价格、期间等数字。数字事实只认 packet 中绑定 snapshot 或 quote amendment 的 canonical fact line；若事实存疑，应把核验要求写入决定性问题，不在后缀另造一套数字。
- `decision_support.mandatory_risk_flags` 是必须逐项回应的风险候选，不是自动路由规则。flag 的存在本身不能把公司机械改成 `pass`、`watch` 或 `research_candidate`。
- 每个 mandatory flag 都必须在 `risk_acknowledgements` 中按 packet 顺序、用稳定 flag ID 标记为 `material` 或 `not_material` 并说明理由。被标记为 `material` 的理由必须同时进入 `one_line_reason` 的定性后缀或 `decisive_question`，不能只留在 acknowledgement 中。
- v2/v3 quote-impact 必须提交该公司的完整 replacement decision，而不是字段补丁；即使 route 不变，也必须用新 amendment 生成的 `canonical_fact_line.text` 刷新 reason 前缀，并重新提交决定性问题、trigger、置信度、证据和全部 risk acknowledgements。replacement 追加封存，不覆盖原 result，也不构成 correction 链。
- v3 的 `research_candidate` 只是未购预算提名。初筛记录不得把它物化为 `quick_profile,pending`；完整 scope 封存后，主 Agent 才对全部候选执行一次 sealed quick-profile allocation。

`send_to_analyst` 是 legacy decision contract v1/v2 的路由名：旧合同中它直接购买 quick-profile 预算，旧 sealed result 继续按原合同只读保留。新 v3 禁止生成或使用 `send_to_analyst`；v3 只能用未购预算的 `research_candidate`，再由后续 sealed allocation 决定是否购买研究预算。

从旧 v1/v2 存量切换到 v3 时，run 保持暂停并严格按以下顺序执行；每个 status 都必须通过后才能进入下一步或继续冻结 v3 batch：

```bash
python -m trading_os coverage manager-screen-allocation-v3-freeze <run-id> \
  --future-policy policies/manager-screening-allocation-v3.json \
  --manager-agent <agent> --manager-model <model> --manager-tool <tool> \
  --reason <reason> --at <timestamp>
python -m trading_os coverage manager-screen-allocation-v3-status <run-id>
python -m trading_os coverage manager-screen-allocation-v3-suspend <run-id> \
  --manager-agent <agent> --manager-model <model> --manager-tool <tool> \
  --reason <reason> --at <timestamp>
python -m trading_os coverage manager-screen-allocation-v3-suspension-status <run-id>
```

当前这一轮 manager-screen 仍为 `paused`。calibration 完成后也只允许受控续跑约 300 家（默认约两个 150 家 batch），随后再次停下审计；只有 calibration 与这批受控续跑中的身份错误、期间错误和强风险遗漏都为 0，才由主 Agent 考虑全面恢复。任一指标非 0 时保持暂停，修的是未来 contract 或后续正式研究，不对 sealed 决策生成 correction 套 correction。

run control 是 append-only sealed 时间线：`paused` 禁止新 freeze 和首次 record，`controlled` 绑定启用时的 completed baseline 与新增公司额度，`active` 才开放正常生产。新 policy 的 `run_control_required=true` 使 control 目录缺失也必须 fail closed；旧 policy 缺少该字段时才显示 `active_unmanaged`。已封存 result 的幂等 replay 在暂停期间仍可修复 coverage 物化。

## 统一 rubric

对每家公司快速回答：

1. 业务与普通股股东现金路径是否能大致理解；
2. 生存、治理、资本结构、会计或少数股东权益是否有明显阻断；
3. 正常化盈利与现金转换有没有可信轮廓；
4. 当前价格大致隐含什么；
5. 哪个问题最可能改变判断；
6. 下一小时研究的预期价值是否高于同批其他机会。

## 三条路由

### `pass`

当前研究信息价值低，停止继续花时间。必须写：

- 一句话理由；
- 决定性问题；
- 至少一个 filing/price/date/ttl/event/thesis 重启条件；
- 证据引用和置信度。

`pass` 不是永久垃圾标签。

### `watch`

业务可能可投，但需要等待价格、财报、事件或证据成熟。要求与 `pass` 相同，并明确等待什么。

### `research_candidate`

只有当下一小时研究很可能改变判断时使用。决定性问题必须足够具体，研究员能在有限预算内回答。该路由只进入未购预算候选池，不直接创建研究任务。

完整 scope 后，主 Agent 在同一 run 的全部候选中一次性比较并封存 allocation。已完成或 running 的旧 v2 预算锁定；尚未 claim 的旧 pending 可被显式撤回或替换。历史购买记录不删除，有效 quick-profile 数量与工时不得突破 run 上限。

allocation 选中的公司才物化为 `quick_profile,pending`，同时保留 manager-screen result 路径/SHA-256、决定性问题和证据 ID。研究员 package 的 `manager_screen_binding` 必须逐项匹配这些字段，并提交引用自身 source ID 的 `decisive_answer`；不能用一份泛化 profile 代替问题回答。

## 禁止字段

初筛不得输出：

- rank、score、priority；
- expected return 精确排名；
- `buy_now`、组合操作、仓位；
- 静默跳过。

## 质量控制

- 程序 100% 校验 schema、整批覆盖、顺序、route、trigger、证据引用、provenance 和禁止字段。
- 路由分歧不自动等于事实错误。
- calibration 由 policy 确定样本，独立 reviewer 必须按样本顺序完整覆盖并分别封存 packet/result。只把身份错误、可核验事实错误、重大风险遗漏和 contract 违规计为 material error；路由分歧只单列为 calibration signal，不阻塞 coverage，也不得触发 adjudication。只有记录 material error 时才必须且允许每家公司执行一次 adjudication，禁止 correction 链。
- 新 packet 在 `reviewer_contract.adjudication_trigger` 固化 `material_error_only`。已封存且缺少该字段的旧 calibration result 若按早期 contract 对纯路由分歧记录过 adjudication，validator 只读兼容并继续统计该历史；兼容分支不得用于生产新 result，也不得改写旧资产。
- status 区分 `planned`、`missing`、`complete`、`material_error`；旧 batch 没有 calibration policy 时显示 `not_configured`。需要复核旧 batch 时，只能用当前 policy 显式冻结新的 calibration packet，不修改旧 batch/result。
- 发现 material error 后由正式研究或一次裁决更正；禁止 correction 套 correction。
- 暂停恢复闸门是 run 级治理决定，不由单个 calibration result 自动打开；约 300 家受控续跑结束前不得恢复全速冻结新批次。
- control event 必须记录真实 manager provenance、原因和带时区时间；状态通过 `manager-screen-control-status` 核验，不以 prompt 内的口头声明代替资产。

## 批次 supersession

只有尚未封存 result 的批次可以 supersede。主 Agent 必须给出真实 provenance、原因和时间，workflow 封存 `supersession.json` 并绑定原 batch/packet seal。superseded 批次：

- 保留在历史批次数和审计轨迹中；
- 不占 active/open、重复 symbol 或 intake 守恒中的已批集合；
- 成员回到 remaining，使用新的 batch ID 重冻；
- 不适用 calibration，且之后不得 record。

## 守恒

```text
batch members = result decisions
scope screenable intake = completed + active open batch + remaining unbatched + deferred current state
```

superseded member 不重复计入等式；status 另列 superseded batch/company 数量。

每批完成后运行：

```bash
python -m trading_os coverage manager-screen-status <run-id>
python -m trading_os coverage validate
```

`manager-screen-status` 的 `analyst_budget` 同时保留兼容口径和最终资金口径：`purchased_*`、`historical_purchased_*` 与 `pre_full_market_purchased_*` 仅表示 singleton 全市场分配前的历史购买；`historical_total_purchased_*` 还包含 full-market v3 新购。`current_effective_send_*` 保持当前 sealed route 为 `send_to_analyst` 的旧语义，真正用于容量与执行监控的是 `current_effective_funded_*`；`current_backlog_*` 只统计其中处于 `pending` 或 `running` 的受保护研究任务，不把已完成、跳过或已 defer 的任务算作 backlog。

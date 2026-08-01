# 研究资本配置 Playbook

## 核心原则

研究时间本身是资本。主 Agent 负责决定“下一小时花在哪里”，研究员负责用证据回答具体问题。

初筛不使用机械分数，也不增加独立 allocation Agent。投资经理先用 `research_candidate` 提名，不购买预算；完整 scope 后仍由同一主 Agent 执行一次 sealed 横向配置。

## 漏斗

| 层级 | 默认范围/容量 | 单家公司预算 | 决策者 | 只回答什么 |
|---|---:|---:|---|---|
| L0 scope | universe 全量 | 批次级 | 程序 + 主 Agent | 身份、纳入、硬排除、异常 |
| L1 manager screen | 全量，默认每批 150 | 批次级 | 同一主 Agent | 是否值得购买下一小时 |
| L2 quick profile | sealed allocation 选中者 | 约 1.5 小时 | 单公司研究员 | 决定性问题能否解决 |
| L3 scoped research | 少数 | 约 4 小时 | 单公司研究员 | 投资路径能否由证据建立 |
| L4 deep research | 更少 | 约 24 小时 | 单公司研究员 | 重建业务、会计、盈利和估值 |
| L5 underwriting | 极少 | 12 小时起 | 独立 reviewer | 深研主张能否承保 |
| L6 portfolio | passed 公司 | 组合层 | 组合 Agent | 最新价格下如何配置 |

容量是上限，不是配额。没有合格公司时留空。

所有容量以同一个 `manager_screen_run_id` 为账本边界，而不是单个 batch、cycle 或 Agent。新开 cycle/batch 不能重置容量；批准前必须把同 run 已封存承诺与本次申请相加，超限则整项/整批拒绝，不允许机器靠改写路由、评分或降低门槛来“凑容量”。targeted/scoped/deep 的账本从现代 sealed approval/selection、已记录的 sealed legacy transition 和 allocation-v3 contract 的 irreversible sealed progress 重建，按 `(stage, symbol)` 去重，不使用 mutable queue 作为购买证据。targeted 必须有精确 targeted 证据，scoped 可由 scoped 或 deep 高水位证明，deep 必须有精确 deep 证据。

## L1：投资经理直接配置

`pass`、`watch`、`research_candidate` 必须基于可读理由、决定性问题、证据和相对研究价值。不得生成精确总分。

初筛同一批由同一个主 Agent 完成，避免不同单公司 Agent 的尺度漂移。`research_candidate` 只获得进入候选池的资格，不构成任何预算购买；只有最终 allocation 选中者才购买单公司上下文和工具调用。

完整 scope 后的 sealed allocation 是第一笔 analyst 预算，受 manager-screen policy 的 run 级上限。已完成或 running 的旧 v2 预算锁定；未 claim 的 pending 可在这一次 allocation 中显式 deselect/replace，历史记录继续保留。选中后 queue 保留原 manager-screen result 路径/SHA-256 作为历史来源，但决定性问题和证据 ID 以 full-market result 的最终 research brief 为准；quick profile 必须绑定这份最终授权并用自身来源形成 `decisive_answer`，否则不得进入同层比较。

旧 v1/v2 存量进入 v3 前，主 Agent 在暂停状态按以下顺序封存并核验治理资产；完成 suspension status 前不得继续领取旧 pending 或冻结新的 v3 batch：

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

### 完整 scope 后的 full-market allocation

run 必须继续保持 `paused`。先确保 scope 守恒完成且无 remaining/open work、已冻结的 legacy transition 已记录、calibration/QA 和 quote-impact review 均终态，并准备在 `prepare` 与 `record` 时都满足新鲜度要求的 sealed 全市场 quote amendment。随后执行：

```bash
python -m trading_os coverage manager-screen-allocation-v3-prepare <run-id> --at <timestamp>
python -m trading_os coverage manager-screen-allocation-v3-record <run-id> \
  --input <full-market-allocation.json> --at <timestamp>
python -m trading_os coverage manager-screen-allocation-v3-final-status <run-id>
```

其中 `prepare/record` 是不可回填的生产 singleton CLI：省略 `--at` 使用真实当前 aware time；显式时间与真实墙钟的绝对偏差最多 5 分钟，过去和未来超限都在调用 workflow 前拒绝。此限制只作用于这两个命令。

`prepare` 只封存 run 级 singleton packet，不购买预算也不改 coverage。packet 位于 `coverage/cn-a/manager-screen/{RUN_ID}/governance/allocation-v3/full-market/packet.json`，按候选所属 active batch 封存的 `(scope_ordinal, symbol)` 稳定顺序汇总全部可撤回的 suspended v2 候选、最终有效的 v3 `research_candidate` 和裁决为 `material_error_confirmed` 且尚无 irreversible commitment 的 calibration 公司；历史 ordinal 可以重复，不能改用 manifest 的全 universe ordinal。confirmed error 即使原 route 为 pass/watch 也进入池，已有 suspended/v3 候选只合并 context，不重复，`manager_upheld` 不新增候选。已锁定预算、superseded 和重复证券均被排除。每个候选都绑定有效决策路径/SHA、决策 SHA、route/reason/question/evidence/triggers/confidence/risk acknowledgements，以及 allocation 前 queue/screening 行与 SHA；confirmed error 还绑定 calibration result、review、adjudication 的内容和 SHA。

singleton packet 封存后即成为 terminal governance lock。此后禁止新增 control event、manager-screen batch/result、calibration、supersession、legacy transition、allocation-v3 contract/suspension、quote amendment 或 quote-impact 节点；只允许既有 artifact 的 exact replay/幂等投影修复，以及该 packet 自身的 `record/apply/final-status`。因此所有候选、裁决和行情演进都必须在 `prepare` 前终结。

confirmed error 若命中 irreversible commitment，不进入普通 `candidates`、不占 selection capacity，而进入独立 `locked_calibration_cases`；原任务和已购 quick-profile 保持原位，result 物化只追加 calibration/remediation binding，不改既有 running/completed 状态或预算。主 Agent 必须逐项选择 `resolved_by_existing_sealed_work`、`targeted_remediation_candidate` 或 `defer_remediation`：resolved 绑定晚于 calibration 的具体 sealed 正式进展及全部错误证据；targeted 只在已有 terminal targeted-followup candidate 可由原 manager 显式批准时允许，approval 自动消费修订问题和全部 material-error/adjudication 证据并绑定 allocation result/case SHA；defer 必须记录修订问题、证据与重启 triggers。

suspension 之后允许不同 batch 依次追加 sealed quote-impact replacement，同一 batch 也可随新的全市场 amendment 形成 append-only 链。每个新节点绑定唯一的前驱 result/行情 path+SHA，候选按相邻价格计算；重复 amendment、分叉、跳号、倒序时间和 prepared 前驱全部拒绝。0 个候选也由 prepare 自动封存 `automatic_noop` result。合法演进必须把 replacement path/SHA、完整决策与 history receipt 投影到 queue/screening，同时继续保留 suspension path/SHA 和 `candidate_unfunded`；不得直接恢复旧 quick-profile 购买。下一批 quote review 和最终 `prepare` 会逐公司重放累计有效 replacement；最终 amendment 若不同于 batch 自身 amendment，必须存在精确绑定最终 amendment 的 terminal 链节点，任一无 seal、身份不符或部分投影都会 fail closed。

提交文件字段必须精确如下，`decisions` 的数量、顺序、symbol 和 `candidate_sha256` 必须与 packet 完全一致；contract manager 也必须逐字段一致：

```json
{
  "schema_version": 1,
  "manager": {
    "agent": "<manager-agent>",
    "model": "<manager-model>",
    "tools": ["<manager-tool>"]
  },
  "decisions": [
    {
      "symbol": "CN:000000",
      "candidate_sha256": "<packet-candidate-sha256>",
      "decision": "fund_quick_profile",
      "reason": "相对完整候选池仍值得购买一次快速画像。",
      "decisive_question": "哪项可核验证据能决定该候选是否值得继续研究？",
      "evidence_ids": ["<sealed-evidence-id>"],
      "revisit_triggers": []
    },
    {
      "symbol": "CN:000001",
      "candidate_sha256": "<packet-candidate-sha256>",
      "decision": "defer_full_market",
      "reason": "本轮边际研究价值不足。",
      "decisive_question": "什么变化会推翻本轮暂缓结论？",
      "evidence_ids": ["<sealed-evidence-id>"],
      "revisit_triggers": [
        {
          "type": "filing",
          "condition": "下一份正式定期报告披露",
          "reason": "新证据可能改变相对研究价值。"
        }
      ]
    }
  ],
  "locked_calibration_remediations": []
}
```

`decisive_question` 与非空、去重的 `evidence_ids` 对两类决策都必填，且证据不能超出 sealed candidate/context。confirmed error 的问题必须不同于旧问题，并完整携带 material-error 与 adjudication evidence。`defer_full_market` 至少需要一个 `filing/price/date/ttl/event/thesis` trigger；`fund_quick_profile` 可留空。所有候选必须被显式二分，不设 rank/score，也不能携带组合动作。`locked_calibration_remediations` 必须与 packet 的 locked cases 等长、同序并绑定 case SHA；没有 locked case 时才是空数组。选中数量受 packet `selection_capacity` 约束，锁定和新购预算合计不得超过 200 家/300 小时；未使用容量在 result 封存后永久放弃。

`record` 先封存同目录的 `result.json`，生成共同的 `{run-id}-full-market-v3` profile cycle，再投影 queue/screening。选中者变为 `funded_quick_profile` 和 `quick_profile,pending`；未选者变为 `deferred_full_market` 并保留重启条件。两类都新增 allocation result/candidate SHA 绑定，并把最终 research brief 投影为新的 question/evidence；confirmed error 还投影 calibration result/review/adjudication SHA。若 result 已封存但投影未完成，运行以下恢复命令；不得手改 JSONL：

```bash
python -m trading_os coverage manager-screen-allocation-v3-apply <run-id>
python -m trading_os coverage manager-screen-allocation-v3-final-status <run-id>
```

`apply` 只把封存的 prior 行恢复为 expected projection，遇到无法识别的漂移会在任何写入前整批拒绝。`final-status` 是只读验证；首次 claim 前必须看到 `finalized=true` 并封存 activation gate，后续 claim 只能由同一 result/cycle 的逐公司 activation receipt 解释合法的 `pending → running` 变化。

activation receipt 只证明 full-market grant 已激活，不代替任务所有权。每个 manager-bound 阶段还必须先封存独立的 profile-stage claim attempt，再投影 `running`。claim receipt 绑定 run/cycle/symbol/stage、阶段授权 path/SHA、agent、真实领取时间和领取前 queue SHA；失败时先封存绑定该 attempt 的 release receipt，重试再创建连续的新 attempt。receipt-only 崩溃保留原 agent 和原 claim 时间，只允许原 agent 恢复投影；不得让另一 agent 直接接管。生产 CLI 的领取/释放时间必须使用真实墙钟或落在允许的窄容差内，不能用回填时间匹配旧结果。

quick/targeted/scoped 的 sealed evaluation 和 deep completion receipt 必须内嵌 claim attempt path/SHA。容量审计只在完成资产重新验证该绑定后，才把未 release attempt 视为成功关闭；mutable `stage_history`、`assigned_agent`、`started_at` 或展示性字段本身都不是完成证据。删除 manager provenance 字段不得绕过 claim 校验；授权身份、run/cycle/stage、allocation/selection path/SHA 和 claim path/SHA 的任何漂移必须 fail closed。

### 正式深研完成

`deep_research` 是正式公司研究，不再使用 profile package 记录，也不能由通用 `coverage reconcile` 根据旧 `latest_report` 代完成。研究员完成全新的 `initial_research` 报告、source manifest 与结构化 claims 后，提交绑定 selection/report/claims SHA 的 completion 文件，再运行：

```bash
python -m trading_os coverage deep-research-complete <CN:000000> \
  --input <completion.json> --at <timestamp>
python -m trading_os coverage deep-research-completion-status <CN:000000>
```

workflow 重验 scoped-research selection 的 `selected=true`、canonical path/SHA、manager-screen run policy 与 sealed deep ledger、active sealed claim attempt 的研究员和开始时间、full-market/manager predecessor、报告为晚于 selection/claim 的最新正式 `initial_research`、紧邻 predecessor、source manifest SHA 以及与报告绑定的 claims seal。completion receipt 先封存，再幂等投影 queue/screening 并追加唯一的 `deep_research/completed` history；receipt 同时绑定 claim attempt，并封存从 full-market allocation result 或合法 legacy predecessor 重验得到的 effective manager authority。崩溃重放只接受 receipt 内封存的原始行或确定性完成行，其他 drift fail closed。只有 completion status 通过后，主 Agent 才能购买 underwriting 预算；underwriting 必须绑定并重验 receipt path/SHA、claim、完整完成链和 effective manager authority，不能用裸报告、早期 batch manager 或 mutable queue 代替。

## L2/L3：研究员结果回到投资经理

研究员不自行决定深研或组合操作。主 Agent比较同层结果时关注：

- 问题是否被证据解决；
- 正常化所有者收益和现金转换是否可建立；
- 当前价格是否仍有可信回报路径；
- 最大反证与永久损失风险；
- 再投入时间相对其他公司是否更值。

可使用 `profile-compare/profile-select` 封存同层决策，但投资经理无需与最初 manager-screen 隔离；只需与提交单公司研究的研究员保持角色独立。targeted/scoped/deep 每次升级都必须是主 Agent 对同 run 可比 cohort 的显式决定，并占用对应 run 级容量。

研究员建议 `targeted_followup` 后，原 manager 只有两种正式动作：用 `profile-followup-approve` 封存购买决定，或用 `profile-followup-decline` 封存不购买决定。decline 必须绑定原 manager-screen result、已封存的画像/evaluation、研究员身份和至少一个结构化重启 trigger；manager 必须与研究员独立。其终态只允许 `price_watch`、`watch_only`、`conditional_stop`，追加预算固定为 0，不进入 targeted approval ledger。

修复前由 evaluator 自动生成、但没有 approval 的 `targeted_followup,status=pending`，只能在从未 claim、没有失败尝试且没有完成记录时由同一 decline 命令一次性收口为 `skipped`。原画像、evaluation 和 queue 历史全部保留；已 running、已 completed 或已经出现 sealed approval 的任务不得用 decline 回退。

## 停止与重启

- `pass/catalog`：当前不买更多研究信息；
- `watch/watch_only`：等待价格、财报、事件或关键证据；纯价格结论只在后续正式研究中使用 `price_watch`；
- `targeted_followup`：只补少数决定性证据；
- `conditional_stop`：存在结构性阻断；
- `deep_research`：证据和赔率都支持继续投入；
- `hard_exclusion`：证券身份不属于范围。

除硬排除外，停止必须有可执行重启条件。亏损、负 PE、小市值、低流动性或行业冷门不能单独构成停止理由。

`profile-followup-decline --triggers` 接受 JSON 数组，每项字段固定为 `type/condition/reason`；type 仅允许 `filing/price/date/ttl/event/thesis`。`price_watch` 至少包含一个 `price` trigger。命令先封存 decline，再物化 queue/screening；中途失败时用完全相同的 manager、outcome、reason 和 triggers 重放，禁止手改 JSONL。

## 承保预算

只有通过 sealed completion receipt 证明 deep research、结构化主张和来源均已完成的公司才能申请承保；裸 Markdown 报告或其 SHA 不是 completion。主 Agent 必须先封存独立的 underwriting approval，绑定并重验 deep selection、completion receipt、claims、live terminal projection、policy SHA、单家公司预算和同 run ledger；approver 还必须与 deep researcher 独立。以下情况构成 challenger 候选：

- 重大事实或估值分歧；
- 高治理、会计或永久损失风险；
- 可能进入组合前五大仓位；
- 第一 reviewer 证据不足。

没有可靠共识时不通过。

underwriting approval 只购买 underwriting，不授予 challenger 或 portfolio。challenger 与组合综合都必须由主 Agent 重新显式批准，并分别执行 manager-run 容量检查；相应批准 contract 尚未物化时不得提前 dispatch 或 synthesize。

## 旧机制

`rapid-triage → triage-compare/finalize`、`quality-triage-*`、`allocate-research`、`apply-allocation` 和 `profile-finalize` 仅验证历史资产。新 Goal 使用 manager-screen，不得启动递归 correction。

旧状态若要进入新协议，只能走一次性 sealed legacy transition：`adoption` 采用可验证正式研究，`rescreen` 释放回 manager-screen，`defer_active` 保持活动/更深阶段。旧 priority、price_watch 或 disposition 不得自动购买任何新预算。

## 共享状态

所有 coverage 写入走正式 workflow 和写锁。研究员只提交自己的 package；主 Agent 串行物化。遇到 `coverage state is busy` 时等待并重试，不手工改 JSONL。

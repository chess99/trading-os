# 全 A 股 Goal 长程执行 Playbook

## 目标

主 Agent 作为投资经理，用统一尺度快速看完全市场，再把有限研究时间集中到少数高信息价值公司。全覆盖不等于为 5500 家公司分别启动 Agent，也不等于制造 5500 份报告。

## 生产流程

```text
冻结普通 A 股 scope
→ 程序封存全市场事实快照
→ 程序生成每批 100—200 家压缩 dossier
→ 同一投资经理 Agent 完整浏览一批
→ pass / watch / research_candidate（未购预算）
→ 完整 scope 后 prepare 全市场候选 packet
→ 主 Agent 一次性完整二分并封存 quick-profile allocation result
→ 投影 queue/screening 并以 final-status 验收
→ 被选中的少数候选由单公司研究员解决决定性问题
→ scoped research → deep research
→ 独立承保 / challenger
→ 最新行情下的组合综合
```

默认批量 150 家。批量是上下文与恢复边界，不是投资容量。

## Baseline 与 Incremental

Baseline 处理冻结 universe 中缺少 manager-screen terminal 的公司。已验证的 legacy rapid-triage terminal 可作为兼容终态，但旧 rapid-triage workflow 不再生产新资产。

Incremental 只处理截止日前真实命中的财报、公告、价格、论点、date/TTL 或证据过期事件。触发器定义不是 hit。两条 lane 可交错，但同一 symbol 只能有一个活动写入者。

## 初筛事实源

每个 run 先创建：

```text
coverage/cn-a/snapshots/{RUN_ID}/companies.jsonl
```

它是该 run 的事实型压缩快照，包含主营摘要、三年财务与现金流、资产负债表风险字段、
审计意见、最新中期数据和数据缺口。它不包含 rank、score 或机器路由。scope manifest
绑定该文件的路径与 SHA-256，因此后续更新 `coverage/cn-a/companies.jsonl` 不会改变
已冻结 run。

行情是快照 contract 的一部分：必须完整覆盖 universe，记录来源、`quote_as_of` 和抓取时间，并在 cutoff 时通过新鲜度校验（默认最多 72 小时、未来容忍 5 分钟）。日期型 A 股报价按当日 15:00 解释，盘中报价必须带时区。已封存快照不得覆盖；刷新行情时追加 sealed quote amendment，绑定原快照路径与 SHA-256，batch 再绑定 amendment 路径与 SHA-256。

每批仅创建：

```text
coverage/cn-a/manager-screen/{RUN_ID}/{BATCH_ID}/
  batch.json + seal
  packet.json + seal
  result.json + seal，或 supersession.json + seal
  calibration/{CALIBRATION_ID}/packet.json + seal
  calibration/{CALIBRATION_ID}/result.json + seal
```

- `batch.json`：冻结成员、scope/policy 绑定和行政顺序。
- `packet.json`：全批压缩 dossier、证据目录和统一 rubric。
- `result.json`：一次主 Agent provenance 与逐公司决策。
- `supersession.json`：只作废未记录批次并释放成员；与 result 互斥。
- `calibration/`：确定性抽样的独立复核，不回写路由或 coverage。

`pass` 和 `watch` 不写单公司 Markdown；它们的不可变事实源是封存 result。只有研究员开始正式研究后才写公司时间线。

## Manager-screen decision contract v3

v3 只约束未来新冻结的 batch，不追溯改写任何 sealed v1/v2 batch、packet、result 或 quote-impact 资产。v3 继承 v2 的 canonical fact line、风险回应和完整 replacement 规则，并把候选提名与预算购买分离。

- packet 的 `decision_support.canonical_fact_line` 对象由程序根据所绑定的 snapshot 或 quote amendment 生成。主 Agent 的 `one_line_reason` 必须把其中的 `.text` 加全角分号作为逐字精确前缀；前缀后的定性后缀不得手抄、重算、舍入或修正数字。
- packet 的 `decision_support.mandatory_risk_flags` 只是必须回应的风险候选，不自动决定 route。每个 flag 必须在 decision 的 `risk_acknowledgements` 中明确标为 `material` 或 `not_material` 并说明理由；material 理由还必须进入 reason 的定性后缀或决定性问题。
- v2/v3 quote-impact 不是 delta patch。每个受影响 symbol 都必须提交完整 replacement decision，用新 amendment 对应的 canonical 市值事实刷新 reason 精确前缀，并完整重交 risk acknowledgements、决定性问题、trigger、证据与置信度；route 可以保持不变。replacement 只追加封存，不覆盖原决策，也不启动 correction 链。
- v3 的第三条路由是 `research_candidate`。它只表示“值得进入全市场候选池”，不得生成 `quick_profile,pending`、不得占用研究预算。完整 scope 结束后，主 Agent 对全部候选执行一次 sealed allocation；已完成或 running 的旧预算锁定，尚未 claim 的旧 v2 pending 可以显式撤回或被更高价值候选替换，但有效总预算不得超过原 run 上限。

## 全市场 sealed allocation v3

每个 run 的最终 allocation 是 singleton，资产固定在：

```text
coverage/cn-a/manager-screen/{RUN_ID}/governance/allocation-v3/full-market/
  packet.json + seal
  result.json + seal
```

只有 scope 守恒完成、run 为 `paused`、remaining/open 均为 0、旧预算 suspension 已完成基线投影或仅发生带 receipt 的 sealed quote-impact 合法演进、已冻结的 legacy transition 已记录、calibration/QA 与所有 quote-impact review 均终态，并且存在 sealed 全市场 quote amendment 时，才允许 `prepare`。suspension 之后，同一 batch 可随更新的全市场 amendment 形成 append-only quote-impact 链：新节点必须绑定唯一的前驱 result 和前驱行情 path/SHA，候选按相邻两次行情计算，禁止重复 amendment、分叉、跳号或跨过 prepared 前驱；0 个候选由 `prepare` 自动封存 `automatic_noop` terminal result，不产生任何 route 判断。演进后的公司仍是 `candidate_unfunded`，不能借 replacement 重新购买预算；无 seal 或只写一半的演进会阻断下一节点和最终 allocation。最终 amendment 若不同于某 active completed batch 自身冻结的 amendment，该 batch 必须有精确绑定最终 amendment 的 terminal 链节点，即使价格候选为 0 也不能缺席。已封存且按公司完成一次裁决的历史 material error 属于终态，不因汇总状态仍为 `material_error` 而永久阻断；缺失样本、未完成结果或未终结裁决仍会阻断。同一公司多条错误只需要一次终态裁决，不能拿错误条数与裁决公司数比较。该 amendment 在 `prepare` 与 `record` 时都必须仍处于新鲜度窗口内。

`prepare` 封存 singleton packet 的同时关闭该 run 的候选治理面。此后不得新增 control event、manager-screen batch/result、calibration、supersession、legacy transition、allocation-v3 contract/suspension、quote amendment 或 quote-impact 节点；已有 artifact 的 exact replay/幂等投影修复仍允许，且 packet 自身仍可按唯一流程执行 `record/apply/final-status`。任何新候选或新依赖都必须在 `prepare` 前完成。

packet 的 `terminal_governance_manifest` 逐项绑定 prepare 前全部 sealed 上游治理资产：control，batch 顶层的 batch/packet/result/supersession/freeze journal，calibration packet/result，quote-impact 与 quote-impact evolution 的 plan/packet/result，legacy transition plan/packet/result，以及 allocation-v3 contract/suspension。每项 seal 必须严格早于 `prepared_at`；封存后替换、删除或新增任一上游资产都会令 packet 重验失败。manifest 不扫描 downstream full-market/activation 子树，也排除 `research-policy*.json`，因为这些资产各自绑定并重验自己的 sealed authority，不属于候选治理的终态输入。

生产 CLI 的 `manager-screen-allocation-v3-prepare` 与 `manager-screen-allocation-v3-record` 禁止回填或预填时间：不传 `--at` 时直接使用真实当前 aware time；显式传入时必须处于真实墙钟前后 5 分钟以内（边界含 5 分钟），否则在进入 singleton workflow 前拒绝。该墙钟限制只适用于这两个不可逆命令，不改变其他命令的时间参数语义。

packet 先按各候选所属 active batch 中封存的 `(scope_ordinal, symbol)` 稳定排序；ordinal 可重复。若 sealed legacy transition adoption 中存在合法 suspended commitment，则严格绑定 transition plan/packet/result，并在 active batch 最大 ordinal 之后按 transition plan 原始顺序追加，不能从可变 queue 或全 universe manifest 猜顺序。候选全集包括未被锁定的 suspended v2/legacy commitment、最终有效路由为 `research_candidate` 的 v3 公司，以及 calibration 裁决为 `material_error_confirmed` 且尚无 irreversible commitment 的公司；后者即使原 route 是 pass/watch 也进入候选池。已存在的候选只合并 calibration context，不重复；`manager_upheld` 不新增候选。superseded 批次、已锁定 completed/running 预算和重复证券不得进入候选池。packet 同时绑定 contract、suspension、scope、policy、行情、每个有效决策及其来源 SHA、allocation 前的 queue/screening 行，以及 confirmed error 的 calibration result/review/adjudication 内容与 SHA。

若 confirmed error 命中 irreversible commitment，packet 将其放入独立 `locked_calibration_cases`，不占 candidate capacity，也不重复购买 quick-profile 或回退 live task；result 物化只追加校准/处置 binding，不改既有 running/completed 状态和预算。result 必须按 packet 顺序逐项选择：`resolved_by_existing_sealed_work` 绑定晚于 calibration 的具体 sealed 正式进展及全部错误证据；`targeted_remediation_candidate` 仅在已有 terminal targeted-followup candidate 可由原 manager 显式批准时允许，approval 自动消费修订问题和全部错误/裁决证据并绑定 result/case SHA；`defer_remediation` 则封存修订问题、证据和可执行重启条件。

主 Agent 必须按 packet 原顺序和 `candidate_sha256` 提交完整 partition；每项只能是 `fund_quick_profile` 或 `defer_full_market`。两者都要写可读理由、最终决定性问题和非空证据 ID，defer 还必须给出至少一个结构化 `revisit_trigger`。证据只能来自 sealed candidate/context；confirmed error 必须纳入 material-error 与 adjudication 的全部证据，并提交一个不同于原问题的修订问题。选中数不得超过 packet 的 `selection_capacity`，锁定预算与新选中预算之和不得突破 run 的绝对 200 家/300 小时上限；没有使用的容量随本次 singleton result 永久放弃，不能靠新 batch/cycle 再购买。

`record` 先封存 result，再把选中者投影为共享 `profile_cycle_id` 下的 `quick_profile,pending`，把未选者投影为 `deferred_full_market`。原 manager-screen result/path 继续作为历史来源，但 queue/screening 的决定性问题与证据改为本次 allocation result 中的最终 research brief；confirmed error 还显式投影 calibration result/review/adjudication SHA。若封存后投影中断，只能用 `apply` 恢复：它只接受 packet 中封存的 prior 行或 sealed result 的精确 expected 行，发现其他漂移则整批拒写。`final-status` 不写文件；仅当两个 seal 和 queue/screening 全部一致时才返回 `finalized=true`，首个 claim 以 sealed activation gate 锁存该完成证明，后续 claim 只接受已有合法 receipt 造成的投影变化。

本轮 manager-screen 保持 `paused`。calibration 结束后先只受控续跑约 300 家（默认约两个 batch），然后再次暂停审计；只有 calibration 与受控续跑样本中的身份错误、期间错误、强风险遗漏都为 0，主 Agent 才能考虑全面恢复。该门槛不是自动恢复开关；任何一项非 0 都继续暂停，并在未来 contract、正式研究或至多一次显式裁决中处理，不为旧决策制造递归 correction。

暂停、受控续跑和全面激活必须分别追加 sealed `paused`、`controlled`、`active` control event，事件包含 manager provenance、原因和时间。`controlled` 在事件中冻结当时的 completed baseline 与 `company_limit`；workflow 按 baseline 之后的 completed + open 原子扣减额度。新 policy 声明 `run_control_required=true` 后，control 目录缺失或无有效事件必须 fail closed；只有缺少该 policy 字段的 legacy run 才兼容为 `active_unmanaged`。

## 恢复与幂等

- 同 batch ID、同 scope/policy/容量可重放；不同内容必须失败。
- 新 batch 自动排除已冻结成员、已完成初筛、正在运行和已进入更深层的公司。
- superseded 批次保留审计历史但不占 active/open/重复证券集合，成员回到 remaining；使用新 batch ID 重冻，已记录批次不可 supersede。
- 同一 result 重放只修复 coverage 物化，不重写 seal，也不把已进入更深层的公司降级。
- full-market allocation 的 result 先于 coverage 投影封存；`apply` 只修复该 sealed result 的 queue/screening 投影，不重新决策。无法归类为 sealed prior 或 expected projection 的行会使整批 fail closed。
- `paused` 阻止新冻批和首次 result record，但允许同一已封存 batch/result 的幂等重放与 coverage 修复。
- `research_queue.jsonl` 是可恢复物化状态，不取代 scope、batch 或 result。
- v1 与 v2 按各自 sealed contract 重放；不得借恢复、quote-impact 或 calibration 把旧 v1 result 原地升级成 v2。

## 质量边界

Material error 只包括：

1. 证券身份错误；
2. 可核验事实错误；
3. 重大风险遗漏；
4. decision contract 违规。

投资经理与 reviewer 对 `pass/watch/research_candidate` 的观点差异不是自动错误。程序对 schema、整批覆盖、顺序、证据引用和禁止字段做 100% 校验。calibration 按 policy 生成确定性样本，由独立 reviewer 完整覆盖并封存 packet/result；路由分歧只单列为 calibration signal，不触发裁决。material error 只限上述四类，不阻塞 coverage；只有记录 material error 时才必须且允许每家公司执行一次裁决，也不生成递归 correction。

新 calibration packet 以 `reviewer_contract.adjudication_trigger=material_error_only` 固化触发规则。缺少该字段的早期 sealed result 若含纯路由分歧 adjudication，只做历史兼容读取和计数，不使结果失效；所有新 record 必须遵守新规则，兼容路径不能用于新增资产。

暂停期间不得继续批量冻结或记录生产 batch。完成 calibration 后的约 300 家属于受控续跑，不代表全量恢复；完成后必须再次审计身份、事实期间和强风险覆盖。

## 研究员与更深阶段

研究员一次只处理一家公司。package 必须绑定原 manager-screen result 的路径、SHA-256、决定性问题和证据 ID，并用自身 source ID 提交 `decisive_answer`；绑定不一致不得记录。研究员结果仍需真实来源、反证、正常化盈利/现金桥接和 provenance。

所有 manager-bound 的 `quick_profile/targeted_followup/scoped_research/deep_research` 领取都使用 append-only sealed attempt 链。workflow 先封存 claim receipt，再把同一 receipt 的 path/SHA、agent 和时间投影到 queue；receipt-only 崩溃只能由原 agent 幂等恢复，其他 agent 必须等待原 agent 先封存 release。失败释放同样先封存 release receipt，再恢复 pending；下一次领取必须创建严格晚于前一 release 的新 attempt。生产 `profile-claim/profile-release` 不允许任意回填时间。queue 的 `assigned_agent/started_at` 只是投影，不能作为所有权事实源；同一 agent 的活动任务必须从 claim/release 以及与 claim 精确绑定的 sealed completion 重建。

quick/targeted/scoped 的 profile evaluation 与 deep completion receipt 都必须内嵌当前 claim attempt path/SHA，并在提交、重放和容量审计时重验；删除 queue 中的 manager 来源字段不能把现代任务降级为 legacy 或绕过 claim。deep completion receipt 还要封存 effective manager authority：full-market 路径只认 sealed full-market allocation result 中的 manager，legacy 路径只认对应 sealed predecessor。underwriting 必须重新验证该 authority 的 source path/SHA/type、run identity 和 manager agent，不能回退到早期 batch manager 或 mutable queue。

quick-profile allocation 与 targeted/scoped/deep/underwriting 容量均按同一 manager-screen run 记账，不能靠新 cycle/batch 扩容；超限应原子拒绝，不机械改路由。targeted/scoped/deep 的已购预算只从现代 sealed approval/selection、已记录的 sealed legacy transition 和 allocation-v3 irreversible sealed progress 重建，按 `(stage, symbol)` 去重，不把 mutable queue 当账本；targeted 与 deep 必须有本阶段精确证据，scoped 可由 scoped 或 deep 高水位证明。只有 completion receipt 已封存并通过终态重验的 deep research 才能由主 Agent 显式购买独立承保，裸 Markdown 报告不能冒充 receipt。重大风险、重大分歧或潜在前五大仓位才考虑 challenger，但 challenger 与 portfolio 必须分别获得新的主 Agent 批准；上游 approval 不授权下游。研究层不给组合操作。

## Legacy transition 与 GC

旧 terminal 和正式研究不能凭旧 priority/disposition 自动晋级。一次性 legacy transition 先冻结完整人口，再由主 Agent 分类：

- `adoption`：采用可验证的正式研究，并绑定报告、claims、meta；
- `rescreen`：释放回普通 manager-screen；
- `defer_active`：保留当前活动或更深阶段，不降级。

plan、packet、result 全部封存并守恒。资产清理只先生成只读 reachability plan；formal report、sealed artifact、coverage、run state、policy 以及路径/SHA 引用都是保护根。候选清单不是删除授权，任何移动或删除必须另行逐项复核并显式确认。

## 命令

从旧 v1/v2 存量切换到 v3 时，run 必须保持暂停，并按
`allocation-v3-freeze → allocation-v3-status → allocation-v3-suspend → allocation-v3-suspension-status`
完成合同封存、核验和旧未领取预算暂停；四步通过后才继续冻结新的 v3 batch。

```bash
python -m trading_os coverage manager-screen-snapshot <run-id> \
  --information-cutoff <timestamp>
python -m trading_os coverage manager-screen-quote-amend <run-id> <amendment-id> \
  --tencent-previous-close-date <YYYY-MM-DD>
python -m trading_os coverage scope-freeze <run-id> --mode auto \
  --scope-cutoff <timestamp> \
  --universe-file coverage/cn-a/snapshots/<run-id>/companies.jsonl
python -m trading_os coverage scope-status <run-id>

python -m trading_os coverage manager-screen-allocation-v3-freeze <run-id> \
  --future-policy policies/manager-screening-allocation-v3.json \
  --manager-agent <agent> --manager-model <model> --manager-tool <tool> \
  --reason <reason> --at <timestamp>
python -m trading_os coverage manager-screen-allocation-v3-status <run-id>
python -m trading_os coverage manager-screen-allocation-v3-suspend <run-id> \
  --manager-agent <agent> --manager-model <model> --manager-tool <tool> \
  --reason <reason> --at <timestamp>
python -m trading_os coverage manager-screen-allocation-v3-suspension-status <run-id>

python -m trading_os coverage manager-screen-freeze <run-id> <batch-id> --batch-size 150
python -m trading_os coverage manager-screen-record <run-id> <batch-id> --input <decisions.json>
python -m trading_os coverage manager-screen-quote-impact-prepare \
  <run-id> <batch-id> <review-id> --quote-amendment <amendment.json>
python -m trading_os coverage manager-screen-quote-impact-record \
  <run-id> <batch-id> <review-id> --input <review.json>
python -m trading_os coverage manager-screen-quote-impact-status \
  <run-id> <batch-id> <review-id>
python -m trading_os coverage manager-screen-status <run-id>
python -m trading_os coverage manager-screen-supersede <run-id> <batch-id> --input <request.json>
python -m trading_os coverage manager-screen-calibration-prepare <run-id> <batch-id> <calibration-id>
python -m trading_os coverage manager-screen-calibration-record <run-id> <batch-id> <calibration-id> --input <review.json>
python -m trading_os coverage manager-screen-calibration-status <run-id>

python -m trading_os coverage manager-screen-transition-freeze <run-id> --input <classification.json>
python -m trading_os coverage manager-screen-transition-record <run-id> --input <decisions.json>
python -m trading_os coverage manager-screen-transition-status <run-id>

python -m trading_os coverage manager-screen-allocation-v3-prepare <run-id> --at <timestamp>
python -m trading_os coverage manager-screen-allocation-v3-record <run-id> \
  --input <full-market-allocation.json> --at <timestamp>
python -m trading_os coverage manager-screen-allocation-v3-apply <run-id>
python -m trading_os coverage manager-screen-allocation-v3-final-status <run-id>

python -m trading_os assets gc --plan \
  --output research/archives/gc-plans/<plan-id>.json

python -m trading_os coverage profile-status <cycle-id>
python -m trading_os coverage profile-compare <cycle-id> --stage quick_profile|scoped_research
python -m trading_os coverage profile-select <cycle-id> --stage quick_profile|scoped_research --decisions <decisions.json>
python -m trading_os coverage reconcile --check
```

以下命令只用于验证已封存旧资产，不得用于新 Goal：

```text
triage-freeze / triage-claim / triage-record / triage-compare / triage-finalize
quality-triage-* / allocate-research / apply-allocation / profile-finalize
```

## 进度与耗时

每个批次记录：

- dossier 生成耗时；
- 主 Agent 浏览与提交耗时；
- research_candidate 数量、最终购买 quick-profile 的数量和比例；
- 研究员、深研、承保各自耗时；
- 验证与修复耗时。

不要用文件数量冒充进度。全市场进度以 scope 守恒和 manager-screen terminal 数量计算。

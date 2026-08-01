# 批量研究与独立复核调度 Playbook

## 两种批次

### Manager screen

- 一批 100—200 家，默认 150。
- 同一个主 Agent完整浏览 packet，不派发单公司 Agent。
- 一次提交全批 `pass/watch/research_candidate`；候选在初筛时不购买预算。
- 批次创建 batch、packet、result 及各自 seal；未记录错误批次可改为与 result 互斥的 sealed supersession。
- 不设半盲路由 reviewer，不创建 correction cohort。

#### Decision contract v3

- v2 packet 的 `decision_support.canonical_fact_line` 对象由程序生成；decision 的 `one_line_reason` 必须以其中的 `.text` 加全角分号作为逐字精确前缀。后续定性判断不得手抄、重算、舍入或纠正任何数字。
- `decision_support.mandatory_risk_flags` 是必须回应的风险候选，不是 route 指令。每个 flag 都要在 `risk_acknowledgements` 中标记 `material` 或 `not_material` 并给出理由；material 理由必须同时进入 reason 定性后缀或决定性问题。
- v2 quote-impact 对每个受影响 symbol 调度完整 replacement decision，不调度局部 patch。replacement 必须采用新 quote amendment 的 canonical 市值事实并完整重交全部决策字段；route 可以不变。
- v3 继承上述 v2 事实与风险合同；`research_candidate` 只进入未购预算候选池。完整 scope 后由主 Agent 一次性 sealed allocation，才把选中者物化为 `quick_profile,pending`。
- 旧 sealed v1 batch/result 不重写、不升级。quote-impact replacement、calibration 和一次 adjudication 都是独立追加资产，不得串成 correction 链；路由分歧只作为 calibration signal，只有 material error 才必须且允许 adjudication。

本轮 manager-screen 调度仍为 `paused`，不得继续生产性冻批或 record。calibration 后只开放约 300 家受控续跑（默认约两个 batch），完成后立即再次暂停；身份错误、期间错误、强风险遗漏只有全部为 0 时，主 Agent 才考虑全面恢复，否则继续暂停并修未来机制。

### 单公司研究与承保

- 历史兼容说明：旧 v1/v2 的规则是“只有 `send_to_analyst` 后才一家公司一个研究员 Agent”；v3 禁止新用该路由，改由 sealed allocation 选中后再派研究员。
- 只有 sealed allocation 选中后才一家公司一个研究员 Agent。
- 公司之间可并行，公司内阶段串行。
- 研究员只解决决定性问题并提交自己的 package，不写共享 coverage；package 必须绑定原 manager-screen result 路径/SHA-256、问题和证据 ID，并提交有来源的 `decisive_answer`。
- 深研后的 blind review、reveal、challenger、仲裁和组合综合使用不同角色与最小可读范围。

## 调度顺序

1. 主 Agent冻结 scope 和 manager-screen batch。
   冻结 scope 前先生成该 run 的事实型 manager-screen snapshot，并用 `--universe-file`
   让 scope 绑定它。行情必须完整、带时间/来源并通过 freshness；快照封存后只用绑定原路径/SHA 的 sealed quote amendment 刷新。
2. 只有 run 级暂停闸门允许时，主 Agent 才亲自完成整批初筛并物化 coverage；受控续跑达到约 300 家后必须重新关闸审计。
3. 首次从旧 v1/v2 存量切换到 v3 时，先在暂停状态依次执行 `manager-screen-allocation-v3-freeze/status` 和 `manager-screen-allocation-v3-suspend/suspension-status`；全部核验通过后才继续冻结 v3 batch。manager-screen 的 `research_candidate` 不占预算。
   完整 scope 后继续保持 `paused`，确认 remaining/open 为 0、已冻结的 legacy transition 已记录、calibration/QA 与 quote-impact 均终态，且 sealed 全市场行情在 prepare/record 时仍新鲜，再按 `manager-screen-allocation-v3-prepare → record → final-status` 完成唯一一次全市场分配。`prepare` 按候选所属 active batch 封存的 `(scope_ordinal, symbol)` 稳定顺序封存 suspended v2、v3 `research_candidate` 和 calibration `material_error_confirmed` 候选全集；合法 legacy-transition suspended commitment 绑定 transition 三段 seal 后追加在 active batch ordinal 之后。已有候选只合并 calibration context。suspension 后不同 batch 可依次演进，同一 batch 也可随新 amendment 追加唯一前驱约束的 sealed quote-impact 链；0 候选节点仍自动封存 terminal no-op。所有演进都必须继续保持 `candidate_unfunded` 和完整 receipt，不能恢复直接购买；最终 allocation 前，每个未直接绑定最新 amendment 的 completed batch 都必须有绑定该 amendment 的 terminal 节点。主 Agent 按 packet 顺序将每项显式分为 `fund_quick_profile` 或带重启 trigger 的 `defer_full_market`，并为两类都提交最终决定性问题和证据；confirmed error 必须改写旧问题并携带全部错误/裁决证据。completed/running 的旧预算继续锁定，未 claim 的旧 pending 可撤回或替换，有效总量不得超过同一 run 的 200 家/300 小时上限。
   `record` 先封存 result，再投影 queue/screening；只有 `final-status` 返回 `finalized=true` 并在首次 claim 时形成 sealed activation gate 后，runner 才派发共同 profile cycle 中最终选中的 `quick_profile,status=pending`。研究员绑定 full-market result 的最终 question/evidence；confirmed error 还必须校验 calibration result/review/adjudication SHA。result 已封存但投影中断时使用 `manager-screen-allocation-v3-apply` 恢复，不重新决策；遇到非 sealed prior/expected 的 coverage 漂移必须整批拒写并停下审计。后续 claim 仅接受已有逐公司 activation receipt 造成的合法投影变化。
   packet 一经封存即成为 terminal governance lock：不得再新增 control、manager-screen batch/result、calibration、supersession、legacy transition、allocation-v3 contract/suspension 或 quote/quote-impact 演进；只可 exact replay/修复既有 artifact，并继续该 packet 的 `record/apply/final-status`。packet 同时封存全部 sealed 上游治理 manifest（control、batch/supersession/freeze journal、calibration、quote-impact/evolution、legacy transition、contract/suspension），且每个依赖 seal 必须严格早于 `prepared_at`；downstream full-market/activation 子树和具有独立 sealed authority 的 `research-policy*.json` 不进入该 manifest。若 material error 命中 irreversible commitment，该公司不占 candidate capacity，而进入 `locked_calibration_cases`；处置投影只追加 binding，不改既有任务或预算。主 Agent 必须选择 `resolved_by_existing_sealed_work`、`targeted_remediation_candidate` 或 `defer_remediation`。resolved 绑定晚于 calibration 的具体 sealed 正式进展及全部错误证据；targeted 只在已有 terminal targeted-followup candidate 可由原 manager 显式批准时允许，approval 自动消费修订问题/证据并绑定 result/case SHA；defer 必须有重启条件。
4. 研究员失败只重试该公司；已封存结果不得重写。
5. 主 Agent比较同层结果，决定停止、补证或深研。
   - 购买定向补证使用 sealed `profile-followup-approve`；不购买则使用 sealed `profile-followup-decline`，绑定可执行重启 triggers。decline 不占 targeted 容量，也不能撤销已批准、已开始或已完成的任务。
   - targeted/scoped/deep 的 run 级账本从现代 sealed approval/selection、sealed legacy transition 与 allocation-v3 irreversible progress 重建，按 `(stage, symbol)` 去重，不读取 mutable queue 计费；targeted/deep 只认精确阶段证据，scoped 可认 deep 高水位。
6. 深研完成后，由主 Agent 显式批准 underwriting 预算并占用 run 级 ledger；没有 sealed approval 不得冻结承保候选或派 reviewer。
   深研报告不能靠通用 `coverage reconcile` 完成任务。研究员先提交全新正式 `initial_research`、sources 和 claims，再由主 Agent运行 `deep-research-complete`：命令重验 scoped selection、running claim、run policy/ledger、报告时序、紧邻 predecessor 与 claims seal，先封存 completion receipt，再投影唯一的 deep completed history。underwriting 只接受并重验该 receipt 的 path/SHA 与完整完成链，裸报告不能替代；只有 completion status 完整通过，才能申请 underwriting。
7. 独立 reviewer 重建事实、会计、风险、估值和证据账本。
8. 重大分歧、高风险或潜在大仓位进入 challenger 候选；challenger 仍需主 Agent 新的显式批准，underwriting approval 不自动授权。无可靠共识不通过。
9. 公司承保终态后，主 Agent 另行显式批准 portfolio 综合，封存最新完整行情后才运行；任何上游预算都不自动授权组合动作。

## 租约与恢复

- 单公司任务使用 append-only sealed claim/release attempt 链；领取先封 claim 再投影 running，只有确实失败后才由原 agent 先封 release 再恢复 pending。receipt-only 崩溃由原 agent 幂等恢复，不能跨 agent 偷接。
- 同一 symbol 同时只能有一个 sealed 活动所有者；同一 agent 的单任务上限也从 sealed attempt 与精确绑定的 completion 重建，不信任 mutable queue。
- quick/targeted/scoped 的 profile evaluation 与 deep completion receipt 必须绑定当前 claim path/SHA；没有该绑定的 mutable stage history 不能关闭 claim。生产 claim/release 时间不得任意回填。
- result 已封存但 coverage 未写回时，主 Agent重放正式命令修复。
- full-market allocation result 已封存但 projection 未完成时，只运行 `manager-screen-allocation-v3-apply`；它只接受 packet 封存的 prior coverage 行或 sealed result 的 expected 行，其他漂移整批 fail closed。恢复后用只读 `manager-screen-allocation-v3-final-status` 验证 `finalized=true`。
- full-market packet 已封存后，恢复命令只能 exact replay 已有 artifact 或修复其投影；不得以“恢复”为名新增任何候选治理资产。
- 未记录批次若确需作废，主 Agent 封存 supersession 后用新 batch ID 重冻；superseded 成员回到 remaining，已记录批次不可作废。
- deep completion receipt 必须封存并重验 effective manager authority；full-market 公司只认最终 allocation result 的 manager，legacy 公司只认对应 sealed predecessor。underwriting 不得从 queue 或早期 batch manager 回退推断权限。
- runner 不拥有承保、晋级或组合结论权。
- 恢复只重放原 sealed contract；不得把 v1 decision 改写成 v2，也不得用 quote-impact 或 calibration 形成 correction 套 correction。

## 命令

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

python -m trading_os coverage manager-screen-allocation-v3-prepare <run-id> --at <timestamp>
python -m trading_os coverage manager-screen-allocation-v3-record <run-id> \
  --input <full-market-allocation.json> --at <timestamp>
python -m trading_os coverage manager-screen-allocation-v3-apply <run-id>
python -m trading_os coverage manager-screen-allocation-v3-final-status <run-id>

python -m trading_os coverage manager-screen-freeze <run-id> <batch-id>
python -m trading_os coverage manager-screen-record <run-id> <batch-id> --input <decisions.json>
python -m trading_os coverage manager-screen-quote-impact-prepare <run-id> <batch-id> <review-id> --quote-amendment <amendment.json>
python -m trading_os coverage manager-screen-quote-impact-record <run-id> <batch-id> <review-id> --input <review.json>
python -m trading_os coverage manager-screen-status <run-id>
python -m trading_os coverage manager-screen-supersede <run-id> <batch-id> --input <request.json>
python -m trading_os coverage manager-screen-calibration-prepare <run-id> <batch-id> <calibration-id>
python -m trading_os coverage manager-screen-calibration-record <run-id> <batch-id> <calibration-id> --input <review.json>

python -m trading_os coverage profile-claim --agent <agent-id> [--symbol CN:000000]
python -m trading_os coverage profile-release --agent <agent-id> --symbol CN:000000 --failure-reason <reason>
python -m trading_os coverage profile-followup-approve --symbol CN:000000 --manager <manager-agent> --reason <reason>
python -m trading_os coverage profile-followup-decline --symbol CN:000000 --manager <manager-agent> \
  --outcome <price_watch|watch_only|conditional_stop> --reason <reason> --triggers <triggers.json>
python -m trading_os coverage profile-status <cycle-id>
python -m trading_os coverage deep-research-complete <CN:000000> \
  --input <completion.json> --at <timestamp>
python -m trading_os coverage deep-research-completion-status <CN:000000>

python -m trading_os review create <review-id> --scope-type custom --market CN --description "批次" --candidates <candidates.json>
python -m trading_os review prepare <review-id>
python automation/scripts/review_dispatch.py <review-id> --runner <agent-runner> --concurrency 4
python -m trading_os review validate <review-id> --strict
python -m trading_os review synthesize <review-id> --quotes <quotes.json>
python -m trading_os review report <review-id>
```

旧 `triage-claim/record` 与 `quality-triage-*` 只读兼容，不用于新生产。

旧状态迁移使用一次性 manager-screen transition 的 freeze/record/status workflow，明确 adoption、rescreen、defer_active；禁止 runner 按旧标签自动映射。资产 GC 同样不属于 runner：它只生成只读可达性计划，任何实际删除都停在独立的逐项人工确认点。

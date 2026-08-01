# Trading OS Agent Guide

本仓库有两类事实源：

- 单公司正式研究从研究员阶段开始，写入 `research/companies/` 的不可变时间线；`meta.json` 是唯一可变公司状态。
- 全市场初筛写入 `coverage/cn-a/manager-screen/` 的不可变批次。初筛不为每家公司制造 Markdown 报告。

跨公司承保与组合事实源仍位于 `research/batches/` 和 `automation/runs/`。

## 角色模型

- 主 Agent 是投资经理：冻结范围、浏览整批压缩 dossier、统一判断研究价值、配置研究预算并维护共享状态。
- 初筛每批默认 150 家，由同一个主 Agent 完整判断；不得为初筛派发“一家公司一个 Agent”。
- decision contract v3 的 `research_candidate` 只提名候选，不购买预算。完整 scope 封存且 run 暂停、无 open work、已冻结的 legacy transition 已记录、calibration/QA 与 quote-impact 已终态，并且 sealed 全市场行情仍新鲜后，主 Agent 通过一次 full-market sealed allocation 在全市场候选中购买 quick-profile；只有被选中的公司才交给单公司研究员。研究员一次只处理一家公司；提交的 `manager_screen_binding` 必须匹配最终授权 result 的路径、SHA-256、决定性问题和证据 ID，并用自己的来源提交 `decisive_answer`。若 calibration 已确认原判断存在 material error，最终 allocation 必须重写决定性问题、纳入全部错误与裁决证据，并让研究员绑定这份新 research brief，禁止继续回答旧问题。
- 所有 manager-bound 的 quick/targeted/scoped/deep 领取都先封存 append-only claim attempt，再投影 `running`；失败释放也先封存 release receipt。正式提交必须绑定并重验当前未释放 claim，不能信任或手改 queue 的 `assigned_agent/started_at`。同一研究员的活动任务只能从 sealed claim/release/completion 链推导。
- quick-profile 有效预算受 manager-screen run 级容量约束；已完成或已领取的预算锁定，尚未领取的旧 v2 `send_to_analyst` 可在完整 scope 后的一次 sealed allocation 中显式撤回或替换。历史购买记录保留；有效预算不得超过 run 上限。targeted/scoped/deep/underwriting 等后续预算同样按 run 记账，不能靠新开 cycle 或 batch 扩容。targeted/scoped/deep 账本只从现代 sealed approval/selection、已记录的 sealed legacy transition 和 allocation-v3 contract 中的 irreversible sealed progress 重建，按 `(stage, symbol)` 去重，不信任可变 queue；targeted 与 deep 需要本阶段精确证据，scoped 可由 scoped 或 deep 高水位证明。
- 深研完成后，独立承保、challenger 和组合综合都必须由主 Agent 分阶段显式批准；上游批准不自动授予下游预算。承保 reviewer 不代写研究。
- 单公司层不得输出 `buy_now`、组合操作或仓位；只有组合层可以。

## 核心规则

- 每次正式研究新增报告，不覆盖历史判断；报告默认中文，并记录真实工具和模型。
- 初研必须同时生成结构化主张和来源清单，封存后才能进入独立承保。
- 半盲 reviewer 不能读取此前结论性答案；完全独立 challenger 用于重大风险、重大分歧或潜在前五大仓位。
- 验证通过后才更新公司状态和 coverage；批次末尾运行 reconcile。
- 不得因市值小、流动性低、暂时亏损、负 PE 或行业冷门静默丢弃公司。
- 程序化快照只能准备材料和确定行政顺序，不得直接决定 `pass`、`watch`、`research_candidate`、研究预算或组合操作。
- manager-screen 行情必须覆盖完整 universe、带来源和时间并通过新鲜度校验；默认最多 72 小时、未来容忍 5 分钟。已封存快照不可覆盖，只能追加绑定原快照路径与 SHA-256 的 sealed quote amendment。
- 新 manager-screen batch 使用 decision contract v3：程序生成并绑定 canonical fact line；投资经理只追加定性理由，不得手抄财务数字或报告期间。v3 继承 v2 的全部事实与风险合同，但把候选提名和预算购买分开；旧 sealed v1/v2 资产保持不可变。
- full-market allocation v3 是每个 run 唯一一次的 sealed 全候选分配：`prepare` 按各公司所属 active batch 封存的 `(scope_ordinal, symbol)` 稳定顺序封存全部 suspended v2 候选和 v3 `research_candidate`；历史 ordinal 可以重复，不得改用含 hard-excluded/legacy terminal 的 manifest 全 universe ordinal。singleton packet 一经封存即成为 terminal governance lock：不得再新增 control event、manager-screen batch/result、calibration、supersession、legacy transition、allocation-v3 contract/suspension 或 quote/quote-impact 演进；只允许既有 artifact 的 exact replay/幂等投影修复，以及该 packet 自身后续的 `record/apply/final-status`。packet 必须绑定 prepare 时全部 sealed 上游治理 manifest，包括 control、batch/result/supersession/freeze journal、calibration、quote-impact/evolution、legacy transition 与 allocation-v3 contract/suspension；每项 `sealed_at` 必须严格早于 `prepared_at`，后续替换、删除或新增任一上游项均使 packet 验证失败。manifest 明确排除 downstream full-market/activation 子树与 `research-policy*.json`；这些资产由各自 sealed authority 独立重验，不能反向改写候选治理快照。`manager-screen-allocation-v3-prepare/record` 两个不可逆 CLI 禁止回填：省略 `--at` 使用真实当前 aware time，显式 `--at` 与真实墙钟的绝对偏差不得超过 5 分钟；该限制不扩展到其他命令。`record` 必须由 contract 中同一 manager 按 packet 顺序把每家公司显式分为 `fund_quick_profile` 或 `defer_full_market`，后者必须带可执行重启条件。result 先封存，再整批检查并物化 queue/screening；崩溃恢复只可用 `apply` 重放 sealed result，最终必须以只读 `final-status` 的 `finalized=true` 验收。
- sealed suspension 是撤回资格与原始判断的基线，不把当时的 queue/screening 精确投影永久冻结。其后允许每个 batch 随新的全市场 quote amendment 形成 append-only quote-impact 链；每个新节点必须绑定唯一前驱 result 与前驱行情的路径/SHA，基于前驱有效决策和价格生成候选，禁止重复 amendment、分叉、跳号或越过未完成节点。0 个价格候选也必须自动封存无路由判断的 terminal no-op result。演进后的行必须继续保持 `candidate_unfunded`、保留 suspension path/SHA 和逐节点 quote-impact receipt，full-market prepare 会重放累计有效 replacement。无 seal、部分写入未恢复或不匹配 replacement 的漂移一律 fail closed。
- calibration 的 `material_error_confirmed` 公司即使原 route 为 pass/watch 也进入 full-market pool；已在 suspended/v3 pool 的只合并 context，不重复。若错误命中已形成 irreversible commitment 的公司，则改入独立 `locked_calibration_cases`，不占 full-market candidate capacity、不回退原任务、不重复购买 quick-profile；result 物化只追加校准/处置 binding，不改既有 running/completed 状态或预算。主 Agent 必须逐项选择 `resolved_by_existing_sealed_work`、`targeted_remediation_candidate` 或 `defer_remediation`。resolved 必须绑定晚于 calibration 的具体 sealed 正式进展和全部错误证据；targeted 只在已有 terminal targeted-followup candidate 可由原 manager 显式批准时允许，后续 approval 自动消费修订后的决定性问题和全部错误/裁决证据，并绑定 allocation result/case SHA；defer 必须给出重启条件。`manager_upheld` 不新增候选。候选与 locked case 都必须绑定 calibration result/review/adjudication 及各自 SHA；同一公司多条错误只要求一次终态裁决，不按错误条数重复计数。
- `deep_research` 不得由通用 coverage reconcile 根据任意旧报告自动标记完成。正式完成必须走 sealed deep-research completion workflow，绑定购买 deep 预算的 scoped selection、run 级 policy/ledger、active sealed claim attempt、晚于 selection/claim 的全新 `initial_research` 报告、结构化 claims 与紧邻 predecessor；receipt 先封存，再幂等投影 queue/screening 并追加唯一的 deep completed history。receipt 还必须封存从最终 full-market allocation result（legacy 则为相应 sealed predecessor）重验得到的 effective manager authority；underwriting 只能绑定并重验该 completion receipt、claim 与 authority，裸报告或 mutable queue 不构成深研完成/经理权限证明。
- `mandatory_risk_flags` 只是必须逐项回应的风险候选，不自动决定路由；每项都要明确判断 `material` 或 `not_material`，重大风险理由必须进入正式 reason 或决定性问题。
- 初筛的 `pass` / `watch` 必须记录理由、决定性问题、证据引用和可执行重启条件。
- 路由观点差异是校准信号，不自动视为错误。初筛 material error 仅包括证券身份错误、可核验事实错误、重大风险遗漏和 contract 违规。
- calibration 必须按确定性样本由独立 reviewer 完整复核并分别封存 packet/result；它不阻塞 coverage。路由分歧只作为 calibration signal 统计，不得触发裁决；只有记录 material error 时才必须且允许每家公司执行一次裁决，禁止 correction 链。
- 已封存旧 calibration result 中的纯路由分歧裁决只读兼容并保留统计，不得借兼容路径继续生产或改写资产。
- 初筛禁止 correction 套 correction。研究员发现 material error 时，由投资经理在后续正式研究或一次显式裁决中更正，不重启递归 reviewer 链。
- 未记录的错误批次只能用 sealed supersession 作废；superseded 批次保留审计历史，但不占 active/open/重复证券集合，其成员回到 remaining。已记录批次不可 supersede。
- 旧 rapid-triage、quality-triage、triage-compare/finalize 代码和 Cycle 001/002 资产仅为历史验证兼容保留；新 Goal 不得使用。旧状态只能通过一次性 sealed legacy transition 明确分类为 adoption、rescreen 或 defer_active，禁止从旧标签自动映射新路由。
- 资产 GC 只生成保守的只读可达性计划；正式报告、sealed artifact、coverage、run state 和 policy 都是根。计划不删除或移动文件，任何实际删除都需要另一次逐项人工复核和显式确认。
- 所有共享 coverage 写入必须走正式 workflow 和 coverage 写锁；单公司 Agent 不直接编辑 JSONL。

## 目录

```text
coverage/cn-a/manager-screen/{RUN_ID}/
  control/{EVENT_ID}.json
  governance/allocation-v3/full-market/
    packet.json
    result.json
  {BATCH_ID}/
    batch.json
    packet.json
    result.json 或 supersession.json
    calibration/{CALIBRATION_ID}/
      packet.json
      result.json

research/companies/{MARKET}/{TICKER}/
  meta.json
  reports/
  evidence/
  underwriting/{REVIEW_ID}/

research/archives/
research/batches/{RUN_ID}/
automation/runs/{RUN_ID}/
policies/
```

## 全 A 股长程工作

先读：

1. `playbooks/all-a-goal-execution.md`
2. `playbooks/screening.md`
3. `playbooks/research-capital-allocation.md`
4. `playbooks/batch-dispatch.md`
5. `playbooks/portfolio-synthesis.md`

可引用 `prompts/goals/cn-all-a-continuous-research.md` 启动长期 Goal。初筛命令：

```bash
python -m trading_os coverage manager-screen-snapshot <run-id> --information-cutoff <timestamp>
python -m trading_os coverage manager-screen-quote-amend <run-id> <amendment-id> \
  --tencent-previous-close-date <YYYY-MM-DD>
python -m trading_os coverage scope-freeze <run-id> --mode auto --scope-cutoff <timestamp> \
  --universe-file coverage/cn-a/snapshots/<run-id>/companies.jsonl
python -m trading_os coverage manager-screen-control-status <run-id>
python -m trading_os coverage manager-screen-control-record <run-id> <event-id> \
  --state paused --manager-agent <agent> --manager-model <model> \
  --manager-tool <tool> --reason <reason> --at <timestamp>
python -m trading_os coverage manager-screen-allocation-v3-freeze <run-id> \
  --future-policy policies/manager-screening-allocation-v3.json \
  --manager-agent <agent> --manager-model <model> --manager-tool <tool> \
  --reason <reason> --at <timestamp>
python -m trading_os coverage manager-screen-allocation-v3-status <run-id>
python -m trading_os coverage manager-screen-allocation-v3-suspend <run-id> \
  --manager-agent <agent> --manager-model <model> --manager-tool <tool> \
  --reason <reason> --at <timestamp>
python -m trading_os coverage manager-screen-allocation-v3-suspension-status <run-id>
python -m trading_os coverage manager-screen-freeze <run-id> <batch-id>
python -m trading_os coverage manager-screen-record <run-id> <batch-id> --input <decisions.json>
python -m trading_os coverage manager-screen-quote-impact-prepare <run-id> <batch-id> <review-id> \
  --quote-amendment <amendment.json>
python -m trading_os coverage manager-screen-quote-impact-record <run-id> <batch-id> <review-id> \
  --input <review.json>
python -m trading_os coverage manager-screen-supersede <run-id> <batch-id> --input <request.json>
python -m trading_os coverage manager-screen-calibration-status <run-id>
python -m trading_os coverage manager-screen-transition-status <run-id>
python -m trading_os coverage manager-screen-status <run-id>
python -m trading_os coverage manager-screen-allocation-v3-prepare <run-id> --at <timestamp>
python -m trading_os coverage manager-screen-allocation-v3-record <run-id> \
  --input <full-market-allocation.json> --at <timestamp>
python -m trading_os coverage manager-screen-allocation-v3-apply <run-id>
python -m trading_os coverage manager-screen-allocation-v3-final-status <run-id>
python -m trading_os coverage deep-research-complete <CN:000000> \
  --input <completion.json> --at <timestamp>
python -m trading_os coverage deep-research-completion-status <CN:000000>
python -m trading_os assets gc --plan --output research/archives/gc-plans/<plan-id>.json
```

## 验证命令

```bash
python -m trading_os assets validate
python -m trading_os review status <run-id>
python -m trading_os review validate <run-id> --strict
python -m trading_os coverage status
python -m trading_os coverage validate
python -m trading_os coverage reconcile --check
python -m trading_os index rebuild
python -m trading_os schedule build
python -m trading_os alerts build
```

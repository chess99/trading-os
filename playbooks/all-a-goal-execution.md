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
→ 完整 scope 后由主 Agent 一次性横向配置 quick-profile 预算
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

本轮 manager-screen 保持 `paused`。calibration 结束后先只受控续跑约 300 家（默认约两个 batch），然后再次暂停审计；只有 calibration 与受控续跑样本中的身份错误、期间错误、强风险遗漏都为 0，主 Agent 才能考虑全面恢复。该门槛不是自动恢复开关；任何一项非 0 都继续暂停，并在未来 contract、正式研究或至多一次显式裁决中处理，不为旧决策制造递归 correction。

暂停、受控续跑和全面激活必须分别追加 sealed `paused`、`controlled`、`active` control event，事件包含 manager provenance、原因和时间。`controlled` 在事件中冻结当时的 completed baseline 与 `company_limit`；workflow 按 baseline 之后的 completed + open 原子扣减额度。新 policy 声明 `run_control_required=true` 后，control 目录缺失或无有效事件必须 fail closed；只有缺少该 policy 字段的 legacy run 才兼容为 `active_unmanaged`。

## 恢复与幂等

- 同 batch ID、同 scope/policy/容量可重放；不同内容必须失败。
- 新 batch 自动排除已冻结成员、已完成初筛、正在运行和已进入更深层的公司。
- superseded 批次保留审计历史但不占 active/open/重复证券集合，成员回到 remaining；使用新 batch ID 重冻，已记录批次不可 supersede。
- 同一 result 重放只修复 coverage 物化，不重写 seal，也不把已进入更深层的公司降级。
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

quick-profile allocation 与 targeted/scoped/deep/underwriting 容量均按同一 manager-screen run 记账，不能靠新 cycle/batch 扩容；超限应原子拒绝，不机械改路由。只有完成 deep research、结构化主张和来源封存的公司才能由主 Agent 显式购买独立承保。重大风险、重大分歧或潜在前五大仓位才考虑 challenger，但 challenger 与 portfolio 必须分别获得新的主 Agent 批准；上游 approval 不授权下游。研究层不给组合操作。

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

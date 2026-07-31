# 批量研究与独立复核调度 Playbook

## 两种批次

### Manager screen

- 一批 100—200 家，默认 150。
- 同一个主 Agent完整浏览 packet，不派发单公司 Agent。
- 一次提交全批 `pass/watch/send_to_analyst`。
- 批次创建 batch、packet、result 及各自 seal；未记录错误批次可改为与 result 互斥的 sealed supersession。
- 不设半盲路由 reviewer，不创建 correction cohort。

#### 未来 decision contract v2

- v2 packet 的 `decision_support.canonical_fact_line` 对象由程序生成；decision 的 `one_line_reason` 必须以其中的 `.text` 加全角分号作为逐字精确前缀。后续定性判断不得手抄、重算、舍入或纠正任何数字。
- `decision_support.mandatory_risk_flags` 是必须回应的风险候选，不是 route 指令。每个 flag 都要在 `risk_acknowledgements` 中标记 `material` 或 `not_material` 并给出理由；material 理由必须同时进入 reason 定性后缀或决定性问题。
- v2 quote-impact 对每个受影响 symbol 调度完整 replacement decision，不调度局部 patch。replacement 必须采用新 quote amendment 的 canonical 市值事实并完整重交全部决策字段；route 可以不变。
- 旧 sealed v1 batch/result 不重写、不升级。quote-impact replacement、calibration 和一次 adjudication 都是独立追加资产，不得串成 correction 链；路由分歧只作为 calibration signal，只有 material error 才必须且允许 adjudication。

本轮 manager-screen 调度仍为 `paused`，不得继续生产性冻批或 record。calibration 后只开放约 300 家受控续跑（默认约两个 batch），完成后立即再次暂停；身份错误、期间错误、强风险遗漏只有全部为 0 时，主 Agent 才考虑全面恢复，否则继续暂停并修未来机制。

### 单公司研究与承保

- 只有 `send_to_analyst` 后才一家公司一个研究员 Agent。
- 公司之间可并行，公司内阶段串行。
- 研究员只解决决定性问题并提交自己的 package，不写共享 coverage；package 必须绑定原 manager-screen result 路径/SHA-256、问题和证据 ID，并提交有来源的 `decisive_answer`。
- 深研后的 blind review、reveal、challenger、仲裁和组合综合使用不同角色与最小可读范围。

## 调度顺序

1. 主 Agent冻结 scope 和 manager-screen batch。
   冻结 scope 前先生成该 run 的事实型 manager-screen snapshot，并用 `--universe-file`
   让 scope 绑定它。行情必须完整、带时间/来源并通过 freshness；快照封存后只用绑定原路径/SHA 的 sealed quote amendment 刷新。
2. 只有 run 级暂停闸门允许时，主 Agent 才亲自完成整批初筛并物化 coverage；受控续跑达到约 300 家后必须重新关闸审计。
3. `send_to_analyst` 按同一 manager-screen run 容量原子记账；超限整批拒绝，不改写路由。runner 只派发 `quick_profile,status=pending` 且决定性问题绑定完整的少数候选。
4. 研究员失败只重试该公司；已封存结果不得重写。
5. 主 Agent比较同层结果，决定停止、补证或深研。
6. 深研完成后，由主 Agent 显式批准 underwriting 预算并占用 run 级 ledger；没有 sealed approval 不得冻结承保候选或派 reviewer。
7. 独立 reviewer 重建事实、会计、风险、估值和证据账本。
8. 重大分歧、高风险或潜在大仓位进入 challenger 候选；challenger 仍需主 Agent 新的显式批准，underwriting approval 不自动授权。无可靠共识不通过。
9. 公司承保终态后，主 Agent 另行显式批准 portfolio 综合，封存最新完整行情后才运行；任何上游预算都不自动授权组合动作。

## 租约与恢复

- 单公司任务使用带超时租约；只有确实失效后才释放。
- 同一 symbol 同时只能有一个可变任务所有者。
- result 已封存但 coverage 未写回时，主 Agent重放正式命令修复。
- 未记录批次若确需作废，主 Agent 封存 supersession 后用新 batch ID 重冻；superseded 成员回到 remaining，已记录批次不可作废。
- runner 不拥有承保、晋级或组合结论权。
- 恢复只重放原 sealed contract；不得把 v1 decision 改写成 v2，也不得用 quote-impact 或 calibration 形成 correction 套 correction。

## 命令

```bash
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
python -m trading_os coverage profile-status <cycle-id>

python -m trading_os review create <review-id> --scope-type custom --market CN --description "批次" --candidates <candidates.json>
python -m trading_os review prepare <review-id>
python automation/scripts/review_dispatch.py <review-id> --runner <agent-runner> --concurrency 4
python -m trading_os review validate <review-id> --strict
python -m trading_os review synthesize <review-id> --quotes <quotes.json>
python -m trading_os review report <review-id>
```

旧 `triage-claim/record` 与 `quality-triage-*` 只读兼容，不用于新生产。

旧状态迁移使用一次性 manager-screen transition 的 freeze/record/status workflow，明确 adoption、rescreen、defer_active；禁止 runner 按旧标签自动映射。资产 GC 同样不属于 runner：它只生成只读可达性计划，任何实际删除都停在独立的逐项人工确认点。

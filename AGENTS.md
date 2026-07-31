# Trading OS Agent Guide

本仓库有两类事实源：

- 单公司正式研究从研究员阶段开始，写入 `research/companies/` 的不可变时间线；`meta.json` 是唯一可变公司状态。
- 全市场初筛写入 `coverage/cn-a/manager-screen/` 的不可变批次。初筛不为每家公司制造 Markdown 报告。

跨公司承保与组合事实源仍位于 `research/batches/` 和 `automation/runs/`。

## 角色模型

- 主 Agent 是投资经理：冻结范围、浏览整批压缩 dossier、统一判断研究价值、配置研究预算并维护共享状态。
- 初筛每批默认 150 家，由同一个主 Agent 完整判断；不得为初筛派发“一家公司一个 Agent”。
- 只有 `send_to_analyst` 才交给单公司研究员。研究员一次只处理一家公司；提交的 `manager_screen_binding` 必须匹配原 result 的路径、SHA-256、决定性问题和证据 ID，并用自己的来源提交 `decisive_answer`。
- `send_to_analyst` 受 manager-screen run 级容量约束；超限时整批拒绝，不允许程序机械改写路由。targeted/scoped/deep/underwriting 等后续预算同样按 run 记账，不能靠新开 cycle 或 batch 扩容。
- 深研完成后，独立承保、challenger 和组合综合都必须由主 Agent 分阶段显式批准；上游批准不自动授予下游预算。承保 reviewer 不代写研究。
- 单公司层不得输出 `buy_now`、组合操作或仓位；只有组合层可以。

## 核心规则

- 每次正式研究新增报告，不覆盖历史判断；报告默认中文，并记录真实工具和模型。
- 初研必须同时生成结构化主张和来源清单，封存后才能进入独立承保。
- 半盲 reviewer 不能读取此前结论性答案；完全独立 challenger 用于重大风险、重大分歧或潜在前五大仓位。
- 验证通过后才更新公司状态和 coverage；批次末尾运行 reconcile。
- 不得因市值小、流动性低、暂时亏损、负 PE 或行业冷门静默丢弃公司。
- 程序化快照只能准备材料和确定行政顺序，不得直接决定 `pass`、`watch`、`send_to_analyst` 或组合操作。
- manager-screen 行情必须覆盖完整 universe、带来源和时间并通过新鲜度校验；默认最多 72 小时、未来容忍 5 分钟。已封存快照不可覆盖，只能追加绑定原快照路径与 SHA-256 的 sealed quote amendment。
- 新 manager-screen batch 使用 decision contract v2：程序生成并绑定 canonical fact line；投资经理只追加定性理由，不得手抄财务数字或报告期间。
- `mandatory_risk_flags` 只是必须逐项回应的风险候选，不自动决定路由；每项都要明确判断 `material` 或 `not_material`，重大风险理由必须进入正式 reason 或决定性问题。
- 初筛的 `pass` / `watch` 必须记录理由、决定性问题、证据引用和可执行重启条件。
- 路由观点差异是校准信号，不自动视为错误。初筛 material error 仅包括证券身份错误、可核验事实错误、重大风险遗漏和 contract 违规。
- calibration 必须按确定性样本由独立 reviewer 完整复核并分别封存 packet/result；它不阻塞 coverage，不把路由分歧计为 material error，每家公司最多一次裁决，禁止 correction 链。
- 初筛禁止 correction 套 correction。研究员发现 material error 时，由投资经理在后续正式研究或一次显式裁决中更正，不重启递归 reviewer 链。
- 未记录的错误批次只能用 sealed supersession 作废；superseded 批次保留审计历史，但不占 active/open/重复证券集合，其成员回到 remaining。已记录批次不可 supersede。
- 旧 rapid-triage、quality-triage、triage-compare/finalize 代码和 Cycle 001/002 资产仅为历史验证兼容保留；新 Goal 不得使用。旧状态只能通过一次性 sealed legacy transition 明确分类为 adoption、rescreen 或 defer_active，禁止从旧标签自动映射新路由。
- 资产 GC 只生成保守的只读可达性计划；正式报告、sealed artifact、coverage、run state 和 policy 都是根。计划不删除或移动文件，任何实际删除都需要另一次逐项人工复核和显式确认。
- 所有共享 coverage 写入必须走正式 workflow 和 coverage 写锁；单公司 Agent 不直接编辑 JSONL。

## 目录

```text
coverage/cn-a/manager-screen/{RUN_ID}/
  control/{EVENT_ID}.json
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
python -m trading_os coverage manager-screen-freeze <run-id> <batch-id>
python -m trading_os coverage manager-screen-record <run-id> <batch-id> --input <decisions.json>
python -m trading_os coverage manager-screen-control-status <run-id>
python -m trading_os coverage manager-screen-control-record <run-id> <event-id> \
  --state paused --manager-agent <agent> --manager-model <model> \
  --manager-tool <tool> --reason <reason> --at <timestamp>
python -m trading_os coverage manager-screen-quote-impact-prepare <run-id> <batch-id> <review-id> \
  --quote-amendment <amendment.json>
python -m trading_os coverage manager-screen-quote-impact-record <run-id> <batch-id> <review-id> \
  --input <review.json>
python -m trading_os coverage manager-screen-supersede <run-id> <batch-id> --input <request.json>
python -m trading_os coverage manager-screen-calibration-status <run-id>
python -m trading_os coverage manager-screen-transition-status <run-id>
python -m trading_os coverage manager-screen-status <run-id>
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

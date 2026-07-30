# Trading OS Agent Guide

本仓库有两类事实源：

- 单公司正式研究从研究员阶段开始，写入 `research/companies/` 的不可变时间线；`meta.json` 是唯一可变公司状态。
- 全市场初筛写入 `coverage/cn-a/manager-screen/` 的不可变批次。初筛不为每家公司制造 Markdown 报告。

跨公司承保与组合事实源仍位于 `research/batches/` 和 `automation/runs/`。

## 角色模型

- 主 Agent 是投资经理：冻结范围、浏览整批压缩 dossier、统一判断研究价值、配置研究预算并维护共享状态。
- 初筛每批默认 150 家，由同一个主 Agent 完整判断；不得为初筛派发“一家公司一个 Agent”。
- 只有 `send_to_analyst` 才交给单公司研究员。研究员一次只处理一家公司，只回答投资经理列出的决定性问题。
- 深研完成后才购买独立承保、challenger 和组合综合预算。承保 reviewer 不代写研究。
- 单公司层不得输出 `buy_now`、组合操作或仓位；只有组合层可以。

## 核心规则

- 每次正式研究新增报告，不覆盖历史判断；报告默认中文，并记录真实工具和模型。
- 初研必须同时生成结构化主张和来源清单，封存后才能进入独立承保。
- 半盲 reviewer 不能读取此前结论性答案；完全独立 challenger 用于重大风险、重大分歧或潜在前五大仓位。
- 验证通过后才更新公司状态和 coverage；批次末尾运行 reconcile。
- 不得因市值小、流动性低、暂时亏损、负 PE 或行业冷门静默丢弃公司。
- 程序化快照只能准备材料和确定行政顺序，不得直接决定 `pass`、`watch`、`send_to_analyst` 或组合操作。
- 初筛的 `pass` / `watch` 必须记录理由、决定性问题、证据引用和可执行重启条件。
- 路由观点差异是校准信号，不自动视为错误。初筛 material error 仅包括证券身份错误、可核验事实错误、重大风险遗漏和 contract 违规。
- 初筛禁止 correction 套 correction。研究员发现 material error 时，由投资经理在后续正式研究或一次显式裁决中更正，不重启递归 reviewer 链。
- 旧 rapid-triage、quality-triage、triage-compare/finalize 代码和 Cycle 001/002 资产仅为历史验证兼容保留；新 Goal 不得使用。
- 所有共享 coverage 写入必须走正式 workflow 和 coverage 写锁；单公司 Agent 不直接编辑 JSONL。

## 目录

```text
coverage/cn-a/manager-screen/{RUN_ID}/{BATCH_ID}/
  batch.json
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
python -m trading_os coverage scope-freeze <run-id> --mode auto --scope-cutoff <timestamp>
python -m trading_os coverage manager-screen-freeze <run-id> <batch-id>
python -m trading_os coverage manager-screen-record <run-id> <batch-id> --input <decisions.json>
python -m trading_os coverage manager-screen-status <run-id>
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

# 动态重点池财报周期研究 Goal

> 在新的 Codex 任务中引用本文件。状态与执行细节以根 `AGENTS.md`、`playbooks/simple-research.md` 为准；单公司研究完整阅读[主提示词](../company/standard-deep-research.md)及[核验附录](../company/research-verification.md)。

## 目标

按财报周期维护动态重点跟踪池中的完整公司研究。重点池来自 `screening/cn-a/value-quality/pool.json`，成员和 A/B 分层可以变化；退出不删除历史报告，进入后从最新财报周期开始研究。

只允许两种任务：

- `periodic`：新的 `FY / Q1 / H1 / Q3` 周期槽位；
- `manual_rewrite`：用户明确要求的同周期完整重写。

不因政策、新闻、订单、治理、资本行动、行业变量或价格变化在周期中途创建报告。不维护 update、stale、公告扫描检查点或事件去重状态。

## 单公司任务

一家公司由一个 Agent 端到端完成。最终结果只有 `covered / ignore`，均须提交 `report_period` 和完整自足正文。先形成长期商业判断，再检验财务、必要资本、普通股归属、当前价值和持有人现金模型。

有前次周期报告时，复盘真正影响价值的旧假设；首次研究说明主要盲区。财报更新不是“新财报摘录＋旧正文”，必须重新形成整篇报告。

每份研究提交非空 `return_model_note`。能够可靠建模时同时提交五年 `return_model`；否则为 `null` 并说明决定性缺口。三年终值可选，但必须独立研究。

## 运行

财报季开始时：

```bash
python -m trading_os research enqueue-period --period <YYYY-FY|Q1|H1|Q3>
python -m trading_os research next --limit <N> --trigger-kind periodic
```

人工重写时：

```bash
python -m trading_os research enqueue-rewrite \
  --period <已有周期> --batch-id <批次> --input <公司及原因.json>
python -m trading_os research next --limit <N> --trigger-kind manual_rewrite
```

启动时读取 Git 状态、`research_state.jsonl`、`research_queue.jsonl`、动态重点池和 `basis_report_path` 所指报告。保留用户及并行修改，不重复已完成周期。

协调器串行接收结果、完成实质验收后用 `research complete` 原子写报告、状态及当时的现行标准，并运行校验。同周期正文变化必须重新走完整研究和验收，不另建 acceptance 文件。

## 每轮报告

向用户报告目标财报周期、当时重点池规模、已有槽位、创建任务、完成公司、验证和提交。不要报告新闻触发、stale、价格命中、仓位或交易指令。

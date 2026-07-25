# Trading OS Agent Guide

本仓库的事实源是 `research/companies/` 下的单公司不可变时间线；跨公司操作事实源是 `research/batches/` 下的封存模型组合。

## 核心规则

- 每次研究新增报告，不覆盖历史判断；`meta.json` 是唯一可变公司状态。
- 报告默认使用中文，并在头部记录真实工具和模型。
- 一个 agent 只研究或复核一家公司；跨公司综合由单独的组合 agent 完成。
- 初研必须同时生成结构化主张和来源清单；封存后才能进入独立承保。
- 半盲 agent 不能读取此前结论性答案；独立评估封存验证通过后才能揭示。
- 重大分歧、高风险或潜在前五大仓位触发完全独立的 challenger；没有可靠共识时不通过。
- 单公司结果只表示承保状态。只有组合层可给 `buy_now`、其他操作和仓位。
- 验证通过后才更新公司状态和 coverage 队列；批次末尾运行 reconcile 检查漂移。
- 跳过公司必须给结构化硬理由，不得因规模小、流动性低或暂时亏损静默丢弃。

## 目录

```text
research/companies/{MARKET}/{TICKER}/
  meta.json
  reports/
  evidence/
  underwriting/{REVIEW_ID}/

research/batches/{RUN_ID}/
automation/runs/{RUN_ID}/
coverage/
policies/
```

## 大批量研究

全 A 股工作先按 `playbooks/research-capital-allocation.md` 和 `playbooks/screening.md` 逐层配置研究预算；公开快照排名不能直接晋级深研或承保。行业或主题批次也必须冻结候选，然后一家公司一个 agent 独立承保。调度遵循 `playbooks/batch-dispatch.md`，组合综合遵循 `playbooks/portfolio-synthesis.md`。

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

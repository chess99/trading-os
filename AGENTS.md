# Trading OS Agent Guide

本仓库的事实源是 `research/companies/` 下的单公司不可变时间线；跨公司操作事实源是 `research/batches/` 下的封存模型组合。

## 核心规则

- 每次研究新增报告，不覆盖历史判断；`meta.json` 是唯一可变公司状态。
- 报告默认使用中文，并在头部记录真实工具和模型。
- 单公司研究或单公司复核 agent 一次只处理一家公司。跨公司 allocation、质量统计和组合综合是独立角色，只读取已封存的单公司产物，不代写单公司研究。
- 初研必须同时生成结构化主张和来源清单；封存后才能进入独立承保。
- 半盲 agent 不能读取此前结论性答案；独立评估封存验证通过后才能揭示。
- 重大分歧、高风险或潜在前五大仓位触发完全独立的 challenger；没有可靠共识时不通过。
- 单公司结果只表示承保状态。只有组合层可给 `buy_now`、其他操作和仓位。
- 验证通过后才更新公司状态和 coverage 队列；批次末尾运行 reconcile 检查漂移。
- 跳过公司必须给结构化硬理由，不得因规模小、流动性低或暂时亏损静默丢弃。
- 全覆盖工作必须让范围内每家公司先经独立 agent 快速甄别；机器排序只能决定行政处理顺序，不能决定谁有资格被看。
- 快速甄别也是公司不可变时间线的一部分。当前停止继续研究必须记录证据、反证和 schedule/alerts 可消费的重启触发器。
- 同一层完整封存后，才由未参与单公司研究的独立 agent 横向配置下一层预算；程序不得按旧 priority、完成顺序或机械分数自动晋级。
- 单公司 agent 只产出自己的封存 package，不直接改共享 coverage JSONL；根 agent 通过正式 workflow 串行回写，遇到 coverage 写锁占用时等待并重试。

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

全 A 股长程工作先读 `playbooks/all-a-goal-execution.md`，再按 `playbooks/research-capital-allocation.md` 和 `playbooks/screening.md` 逐层配置研究预算；可直接引用 `prompts/goals/cn-all-a-continuous-research.md` 启动长期 Goal。程序化快照只能准备材料，不能剥夺公司被 Agent 快速查看的资格，也不能直接晋级正式画像、深研或承保。行业或主题批次同样先冻结范围，再一家公司一个 Agent 独立研究。调度遵循 `playbooks/batch-dispatch.md`，组合综合遵循 `playbooks/portfolio-synthesis.md`。

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

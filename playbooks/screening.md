# A 股覆盖与筛选 Playbook

## 四层漏斗

全市场工作固定经过四层：

```text
约 5000 家普通 A 股覆盖
→ 数百家公司证据筛查
→ 数十家公司初始深研
→ 少数公司独立承保与组合比较
```

筛选只决定研究顺序，不是投资结论。默认尽可能覆盖普通 A 股；小市值、低流动性、暂时亏损或负倍数不能成为硬跳过理由。

## 事件性冲击与危机错杀

- 当期亏损、利润骤降或 PE 失真不能降低研究资格；这类公司应优先判断冲击是需求延后、周期波动还是永久损失。
- 估值使用 3—5 年正常化盈利和多情景现金流，不把危机期亏损机械外推，也不把危机前峰值直接当作常态。
- 必须核验现金消耗、债务到期、再融资能力、潜在稀释和维持经营所需资本，先回答公司能否活到需求恢复。
- 反推当前价格隐含的恢复时间、恢复幅度和长期回报，寻找“市场按永久受损定价、但资产负债表足以穿越周期”的错配。
- 不要求把研究流程改造成历史时点量化回测。历史案例和经验用于构造当前情景、基准率与反证，最终判断仍基于当下可得事实。

## 分流

- `deep_research`：进入初研队列。
- `watch_only`：已有资产或等待触发器。
- `needs_manual_review`：证券状态、数据或重大风险需人工判断。
- `skip_not_in_scope`：基金、债券、B 股等不在普通 A 股范围。
- 其他 `skip_*` 仅用于退市或确实无法形成研究对象的硬排除，必须写结构化理由。

## 可恢复文件

`coverage/cn-a/companies.jsonl`、`screening.jsonl`、`research_queue.jsonl` 和 `runs.jsonl` 都是可审计 JSONL，并使用稳定 symbol 排序。任务必须记录优先级、理由、证据、状态、目标公司目录、结果路径和下一步。

## 命令

```bash
python -m trading_os coverage validate
python -m trading_os coverage status
python -m trading_os coverage list --decision deep_research
python -m trading_os coverage reconcile --check
```

每个公司资产验证通过后立即更新对应队列项；批次末尾的 reconcile 只是漂移安全网。

# A 股覆盖与筛选 Playbook

## 自适应研究漏斗

全市场工作按研究的信息价值逐层购买更多证据：

```text
约 5000 家普通 A 股覆盖
→ 全市场多视角便宜地图
→ 数百家公司快速投资画像
→ 数十家公司范围研究
→ 少数公司完整深研、独立承保与组合比较
```

覆盖不等于每家公司都获得完整初研。筛选只决定是否值得购买下一阶段研究预算，不是投资结论；小市值、低流动性、暂时亏损或负倍数不能成为硬跳过理由。

公开数据排名只能作为便宜地图，不能直接晋级深研、承保或买入。必须经过 `playbooks/research-capital-allocation.md` 的快速画像和范围研究；不同类型机会分别选样，并为危机错杀与假阴性抽查保留容量。

## 事件性冲击与危机错杀

- 当期亏损、利润骤降或 PE 失真不能降低研究资格；这类公司应优先判断冲击是需求延后、周期波动还是永久损失。
- 估值使用 3—5 年正常化盈利和多情景现金流，不把危机期亏损机械外推，也不把危机前峰值直接当作常态。
- 必须核验现金消耗、债务到期、再融资能力、潜在稀释和维持经营所需资本，先回答公司能否活到需求恢复。
- 反推当前价格隐含的恢复时间、恢复幅度和长期回报，寻找“市场按永久受损定价、但资产负债表足以穿越周期”的错配。
- 不要求把研究流程改造成历史时点量化回测。历史案例和经验用于构造当前情景、基准率与反证，最终判断仍基于当下可得事实。

## 分流

- `catalog`：已完成全市场机器清洗，但本周期未获得快速画像预算；保留结构化重启触发器。
- `quick_profile`：一小时级快速投资画像。
- `scoped_research`：只解决决定性未知数的范围研究。
- `deep_research`：进入初研队列。
- `watch_only`：已有资产或等待触发器。
- `conditional_stop`：当前停止投入，但保留结构化重启条件。
- `hard_exclusion`：不构成可执行普通股票投资对象。
- `needs_manual_review`：证券状态、数据或重大风险需人工判断。
- `skip_not_in_scope`：基金、债券、B 股等不在普通 A 股范围。
- 其他 `skip_*` 仅用于退市或确实无法形成研究对象的硬排除，必须写结构化理由。

## 可恢复文件

`coverage/cn-a/companies.jsonl`、`screening.jsonl`、`research_queue.jsonl` 和 `runs.jsonl` 都是可审计 JSONL，并使用稳定 symbol 排序。任务必须记录优先级、理由、证据、状态、目标公司目录、结果路径和下一步。

## 命令

```bash
python -m trading_os coverage validate
python -m trading_os coverage status
python -m trading_os coverage rank-rebaseline
python -m trading_os coverage allocate-research
python -m trading_os coverage evaluate-profile --input <quick-profile.json>
python -m trading_os coverage record-profile --input <quick-profile-package.json>
python -m trading_os coverage reconcile --check
```

每个公司资产验证通过后立即更新对应队列项；批次末尾的 reconcile 只是漂移安全网。

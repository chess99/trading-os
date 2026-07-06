# A 股筛选 Playbook

使用本 playbook 时，目标不是写完整公司研究，而是在深度研究前完成低成本分流。

## 边界

- 一轮筛选可以覆盖很多公司，但每条记录必须独立给出理由。
- 不要在筛选阶段写完整估值报告。
- 不要因为暂时跳过就删除公司。跳过理由必须保存在筛选结果里。
- 执行主体是 agent；不要要求用户手动运行命令。

## 输入

- A 股 universe 快照，格式参考 `coverage/cn-a/universe.schema.json`。
- 已有研究资产索引 `research/index.json`。
- 用户指定的研究范围或排除范围。

## 分流结果

- `deep_research`：值得完整研究，进入研究队列。
- `watch_only`：值得保留观察，但暂不写完整报告。
- `skip_risk`：风险、治理、财务质量或退市风险过高。
- `skip_too_small`：规模、流动性或覆盖价值太低。
- `skip_not_in_scope`：不是当前范围内的普通 A 股公司。
- `needs_manual_review`：信息冲突、业务复杂或数据不足，需要主 agent 判断。

## 第一轮筛选顺序

1. 先排除非普通 A 股：ETF、基金、债券、B 股、优先股、退市整理、壳资源等。
2. 再排除明显风险：ST、高退市风险、重大违规、持续资不抵债、财报可信度过低。
3. 再排除低覆盖价值：市值太小、成交太弱、业务不可理解、深研收益明显不值得。
4. 保留值得深研的公司：行业龙头、现金牛、长期复利资产、成长赛道核心、周期底部、困境反转、特殊资产。
5. 对复杂但可能重要的公司，标记为 `needs_manual_review`，不要草率跳过。

## 输出

每轮筛选至少更新这些 Git 友好的 JSONL 文件：

```text
coverage/cn-a/companies.jsonl
coverage/cn-a/screening.jsonl
coverage/cn-a/research_queue.jsonl
coverage/cn-a/runs.jsonl
```

筛选结果必须包含：

- `symbol`
- `name`
- `decision`
- `priority`
- `reason`
- `evidence`
- `next_action`

研究队列只放 `deep_research` 和少量主 agent 认可的 `needs_manual_review`。

## Agent 辅助工具

优先用薄封装更新 JSONL，避免手写时破坏格式、重复 symbol 或打乱排序：

```bash
python -m trading_os coverage validate
python -m trading_os coverage status
python -m trading_os coverage get CN:600519
python -m trading_os coverage list --decision deep_research
python -m trading_os coverage set-screening CN:300750 --name 宁德时代 --decision deep_research --priority 1 --reason "动力电池龙头" --evidence "行业龙头" --next-action "加入研究队列"
python -m trading_os coverage enqueue CN:300750 --name 宁德时代 --priority 1 --reason "筛选结果为 deep_research"
```

这些命令是给 agent 用的安全编辑器，不要求用户手动执行。

## 长程恢复规则

下一个 agent 接手时：

1. 先读 `coverage/README.md`。
2. 再读本文件。
3. 再读 `coverage/cn-a/runs.jsonl` 和 `coverage/cn-a/research_queue.jsonl`。
4. 继续处理 `pending`、`failed`、`needs_review`，不要重跑已完成项目。
5. 每批完成后更新 JSONL 文件，并提交本批筛选资产。

## 质量标准

- `deep_research` 必须说明为什么值得花完整研究成本。
- `skip_*` 必须说明跳过原因，不能只写“不看”。
- `needs_manual_review` 必须说明卡点是什么。
- 不能把估值判断伪装成筛选结论；估值只在公司研究报告中完成。

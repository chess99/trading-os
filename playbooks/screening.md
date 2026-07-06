# A 股筛选 Playbook

使用本 playbook 时，目标不是节省研究算力，而是让全市场研究有序展开。
筛选层只做三件事：确认是否属于研究范围、标记硬风险、安排研究优先级。

## 核心口径

- 默认应研尽研。普通 A 股公司原则上都进入研究队列。
- 小市值、低成交、亏损、PE 为负、行业冷门，都不能作为硬跳过理由。
- 流动性只影响优先级，不影响是否研究；本仓库面向个人投资者，不按机构容量筛股票。
- ST、*ST、重大异常公司不直接跳过，先进入 `needs_manual_review`。
- 只有退市整理、明显非普通股票、数据不可识别等硬排除项，才使用 `skip_*`。
- 筛选结论不是投资结论，只决定研究顺序和任务状态。

## 输入

- A 股 universe 快照，格式参考 `coverage/cn-a/universe.schema.json`。
- 已有研究资产索引 `research/index.json`。
- 用户指定的研究范围或排除范围。

## 分流结果

- `deep_research`：进入完整公司研究队列。
- `watch_only`：已有研究档案或等待既定复查，不重复创建初始研究任务。
- `skip_risk`：退市整理、明显无法作为普通股票研究的硬风险项。
- `skip_too_small`：原则上少用；只用于极端微型、数据质量极差且无法形成研究任务的标的。
- `skip_not_in_scope`：不在当前普通 A 股研究范围内，如 ETF、基金、债券、B 股、优先股、壳资源等。
- `needs_manual_review`：ST、*ST、数据冲突、证券状态异常，需主 agent 决定是否按特殊情况研究。

## 第一轮筛选顺序

1. 排除非普通 A 股：ETF、基金、债券、B 股、优先股、退市整理、明显壳资源等。
2. 将 ST、*ST、重大异常、数据冲突标记为 `needs_manual_review`，不要直接删除。
3. 对所有其余普通 A 股标记为 `deep_research`。
4. 按优先级排序研究队列：
   - P1：超大市值核心资产。
   - P2：大市值或高成交关注度公司。
   - P3：具备一定规模的中优先级公司。
   - P4：规模较小、关注度一般或信息密度较低的公司。
   - P5：小市值、亏损、数据不充分或需要更多资料验证的公司。
5. 已有初始研究报告的公司不重复排队，标为 `watch_only` 并按 `meta.json` 的复查计划跟踪。

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

研究队列应包含 `deep_research`。`needs_manual_review` 可以进入队列，但状态应为
`needs_review`，由主 agent 先做特殊情况判断。

## Agent 辅助工具

优先使用薄封装更新 JSONL，避免手写时破坏格式、重复 symbol 或打乱排序：

```bash
python -m trading_os coverage validate
python -m trading_os coverage status
python -m trading_os coverage get CN:600519
python -m trading_os coverage list --decision deep_research
python -m trading_os coverage set-screening CN:300750 --name 宁德时代 --decision deep_research --priority 1 --reason "动力电池龙头" --evidence "行业龙头" --next-action "加入研究队列"
python -m trading_os coverage enqueue CN:300750 --name 宁德时代 --priority 1 --reason "筛选结果为 deep_research"
```

这些命令是给 agent 用的安全编辑器，不要要求用户手动执行。

## 长程恢复规则

下一个 agent 接手时：

1. 先读 `coverage/README.md`。
2. 再读本文档。
3. 再读 `coverage/cn-a/runs.jsonl` 和 `coverage/cn-a/research_queue.jsonl`。
4. 继续处理 `pending`、`failed`、`needs_review`，不要重新开始整轮任务。
5. 每批完成后更新 JSONL 文件，并提交本批筛选或研究资产。

## 质量标准

- `deep_research` 的理由只需说明为什么进入研究队列，不要伪装成估值结论。
- `skip_*` 必须说明硬跳过原因，不能因为小市值、低流动性或亏损而跳过。
- `needs_manual_review` 必须说明卡点是什么。
- 不能把估值判断伪装成筛选结论；估值只在公司研究报告中完成。

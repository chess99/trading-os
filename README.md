# Trading OS

Trading OS 是一套面向 A 股的轻量研究工作流。它不做自动交易，也不要求把每家公司都写成长篇研报；目标是让主 Agent 快速覆盖全市场，只把真正值得投入的公司交给单公司 Agent，并把研究结论转化为可持续维护的自选池和价格触发器。

## 核心流程

1. 主 Agent 批量浏览压缩后的公司事实，判断 `ignore`、`watch` 或 `research_now`。
2. `ignore` 和 `watch` 都不会派单公司 Agent；只有 `research_now` 入研究队列。
3. 不同公司可以并行研究，通常同时处理 3—6 家；并行数由运行方配置。一家公司始终由一个 Agent 从快速浏览到最终结论端到端完成。
4. Agent 自己决定研究深度。明显不值得看的公司可以很快结束；值得看的公司继续展开。没有按分钟计费的阶段，也没有 `quick / targeted / scoped / deep` 逐级审批。
5. 结果只保留有决策价值的内容：`discard` 只需一句非空结论；`watch` 至少写清观察理由和一个价格或事件触发条件；正式研究再保留关键逻辑、关键风险、合理价值区间、买入触发价、后续触发条件和来源 URL。
6. 研究结果形成自选池。价格只在每日收盘后扫描；命中触发价时进入一次简短复核和排序，不直接产生交易动作。
7. 池外公司遇到财报或重大公告时，先进入批量变化筛选；只有出现值得单独研究的变化才派 Agent。

这里没有独立承保、challenger、calibration、多 Agent 共识、收益率硬门槛、仓位审批或组合层闸门。Git 已经提供历史版本，因此仓库只保存每家公司当前仍有用的一份报告。

## 事实源

```text
coverage/cn-a/research_state.jsonl       全市场当前状态，一家公司一行
coverage/cn-a/research_queue.jsonl       当前待办与运行中的单公司任务
research/watchlist.jsonl                 由全市场状态派生的自选池
research/companies/CN/{代码}/current.md  真正完成过完整研究的公司当前报告
```

收盘价格触发的去重与重新武装状态直接保存在对应公司的当前状态行中，不另造一套账本。

状态只有四种：

- `unseen`：尚未完成本轮初筛；
- `ignore`：当前不值得持续占用注意力，等待重大变化；
- `watch`：值得跟踪，但暂时不需要完整研究或重做研究；
- `researched`：已有可用的完整研究，按价格、财报或事件复核。

`baseline` 只能写入当前仍为 `unseen` 且尚未做过 baseline 判断的公司；同一批中只要包含一家已经判断过的公司，整批拒绝且不产生部分更新。财报和事件使用 `event` 模式做局部更新。

## 日常使用

```bash
# 查看状态与待办
python -m trading_os status

# 首次登记或增量补充全市场证券清单
python -m trading_os universe register --input templates/universe.json

# 记录一批主 Agent 初筛判断；research_now 会自动入队
python -m trading_os screen record --input templates/screen-decisions.json

# 调用者决定本次并行公司数；每家公司仍只交给一个 Agent 端到端完成
python -m trading_os research next --limit 4
python -m trading_os research complete --input templates/research-result.json

# 重建自选池，并校验状态、队列、自选池与当前报告
python -m trading_os watchlist build
python -m trading_os validate

# 每日收盘后扫描一次价格；只返回命中项，交给主 Agent 简短复看和排序
python -m trading_os watchlist scan-close --input templates/close-quotes.json
```

输入输出契约和实际操作说明见 [精简研究流程](playbooks/simple-research.md)。迁移前的复杂机制仍可从 Git 标签 `pre-simplification-20260808` 或更早提交恢复；当前版本不再保留其运行资产。

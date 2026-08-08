# Trading OS

Trading OS 是一套面向 A 股的轻量研究工作流。它不做自动交易，也不要求把每家公司都写成长篇研报；目标是让主 Agent 快速覆盖全市场，只把真正值得投入的公司交给单公司 Agent，并把研究结论转化为可持续维护的自选池和价格触发器。

## 核心流程

1. 主 Agent 批量浏览压缩后的公司事实，只判断 `ignore` 或 `research_now`。
2. `research_now` 把公司标记为 `candidate` 并进入研究队列；未正式研究的公司没有价格触发。
3. 不同公司可以并行研究，通常同时处理 3—6 家；并行数由运行方配置。一家公司始终由一个 Agent 从快速浏览到最终结论端到端完成。
4. 所有公司统一使用 `prompts/company/standard-deep-research.md`。没有研究强度分档，也没有 `quick / targeted / scoped / deep` 逐级审批。
5. 正式研究结果为 `covered` 或 `ignore`，两者都保留当前报告；只有 `covered` 进入自选池并启用价格或事件触发。
6. 价格只在每日收盘后扫描 active `covered` 公司；命中触发价时进入一次简短复核和排序，不直接产生交易动作。
7. 池外公司遇到财报或重大公告时，先进入批量变化筛选；只有出现值得单独研究的变化才派 Agent。

这里没有独立承保、challenger、calibration、多 Agent 共识、收益率硬门槛、仓位审批或组合层闸门。Git 已经提供历史版本，因此仓库只保存每家公司当前仍有用的一份报告。

## 事实源

```text
coverage/cn-a/research_state.jsonl       全市场当前状态，一家公司一行
coverage/cn-a/research_queue.jsonl       当前待办与运行中的单公司任务
coverage/cn-a/screening_baseline.json    当前全市场初筛的数据截止时间、选择口径与结果计数
coverage/cn-a/event_scan_state.json      财报与重大公告扫描的可变成功检查点
research/watchlist.jsonl                 由全市场状态派生的自选池
research/companies/CN/{代码}/current.md  真正完成过完整研究的公司当前报告
```

收盘价格触发的去重与重新武装状态直接保存在对应公司的当前状态行中，不另造一套账本。公告检查点也只保存最后成功时间和近期稳定公告 ID；它不是公告历史账本。

研究状态只有五种：

- `unseen`：尚未完成本轮初筛；
- `ignore`：当前不值得持续占用注意力，等待重大变化；
- `candidate`：已经选中，等待或正在进行统一标准的正式研究；
- `covered`：已有当前有效正式报告，按价格、财报或事件监控；
- `stale`：重大新事实使原报告失效，暂停价格监控并等待更新。

`baseline` 只能写入当前仍为 `unseen` 且尚未做过 baseline 判断的公司；同一批中只要包含一家已经判断过的公司，整批拒绝且不产生部分更新。财报和事件使用 `event` 模式做局部更新。

## 日常使用

```bash
# 查看状态与待办
python -m trading_os status

# 一次性迁移旧 watch/researched 状态；全市场重筛前保留 covered、重置其余公司
python -m trading_os state migrate-v2 --at 2026-08-09T12:00:00+08:00
python -m trading_os state prepare-rebaseline --at 2026-08-09T12:05:00+08:00

# 首次登记或增量补充全市场证券清单
python -m trading_os universe register --input templates/universe.json

# 后续用完整上市证券快照同步 active/inactive；退出范围只停任务和监控，不删除研究历史
python -m trading_os universe sync --input templates/universe.json

# 记录一批主 Agent 初筛判断；research_now 会自动入队
python -m trading_os screen record --input templates/screen-decisions.json

# 每家公司仍只交给一个 Agent，使用统一提示词端到端完成
python -m trading_os research next --limit 4
python -m trading_os research complete --input templates/research-result.json

# 重建自选池，并校验状态、队列、自选池与当前报告
python -m trading_os watchlist build
python -m trading_os validate

# 查看完整报价但不改状态
python -m trading_os watchlist fetch-close --date 2026-08-07 --at 2026-08-07T16:30:00+08:00

# 每日收盘后完整取价并扫描；任一报价缺失时整批失败且不改状态
python -m trading_os watchlist run-close --date 2026-08-07 --at 2026-08-07T16:30:00+08:00

# 仍可用外部完整报价执行同一扫描
python -m trading_os watchlist scan-close --input templates/close-quotes.json

# 首次公告扫描显式给起点；以后从检查点继续，并自动回看上一自然日去重
python -m trading_os events fetch --since 2026-08-09T00:00:00+08:00 \
  --until 2026-08-09T07:30:00+08:00 --output tmp/event-packet.json

# 主 Agent 判断 packet 中全部公告、先写入必要的 event 筛选，再推进检查点
python -m trading_os events complete --packet tmp/event-packet.json \
  --input templates/event-judgments.json

# 查看公告检查点
python -m trading_os events status

# 从固定只读标签列出旧研报候选；只打捞核验后仍有决策价值的部分
python -m trading_os legacy-salvage candidates --limit 100 --min-score 40
python -m trading_os legacy-salvage apply --input templates/legacy-salvage-decisions.json
```

`events complete` 的成功 ID 必须与 packet 中待判断公告精确一致；遗漏、重复或额外 ID 都不会推进检查点。临时 packet 和判断文件放在已忽略的 `tmp/`，不要提交。

输入输出契约和实际操作说明见 [精简研究流程](playbooks/simple-research.md)。迁移前的复杂机制仍可从 Git 标签 `pre-simplification-20260808` 或更早提交恢复；当前版本不再保留其运行资产。`current.md` 表示“当前有效版本”，研究日期写在正文和状态里，历史版本由 Git 保存，避免日期文件与当前状态再次分叉。

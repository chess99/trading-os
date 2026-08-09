# Trading OS

Trading OS 是一套面向 A 股的轻量研究工作流。它不做自动交易，也不要求把每家公司都写成长篇研报；主 Agent 先快速覆盖全市场，只把真正值得投入的公司交给单公司 Agent，再把有效研究转成自选池和每日收盘价格触发。

## 核心流程

1. 主 Agent 批量浏览压缩事实，只判断 `ignore` 或 `research_now`。
2. `research_now` 把公司标记为 `candidate` 并放入研究队列；未正式研究的公司不能设置价格。
3. 不同公司可并行；一家公司始终由一个 Agent 用统一提示词端到端完成。
4. 正式结果只有 `covered` 或 `ignore`。只有 active `covered` 进入自选池和价格监控。
5. 每日收盘后扫描触发价格。池内外公司发生财报或重大事件时，只对受影响公司做局部更新。

没有研究强度分档、固定分钟数、复核 Agent、独立承保、经理审批、多 Agent 共识、收益率硬门槛或仓位审批。

## 当前事实源

```text
coverage/cn-a/research_state.jsonl              全市场当前状态，一家公司一行
coverage/cn-a/research_queue.jsonl              当前 queued/running 任务
coverage/cn-a/screening_baseline.json           全市场初筛基线
coverage/cn-a/event_scan_state.json             公告扫描成功检查点
research/watchlist.jsonl                        active covered 的确定性投影
research/companies/CN/{代码}/reports/{日期}.md  新机制正式研报时间线
research/companies/CN/{代码}/legacy/{日期}.md   隔离的旧研报档案
```

`research_state.jsonl.report_path` 指向该公司最新的正式日期报告，这个指针就是 current；不再维护会覆盖或漂移的 `current.md` 副本。同一天再次完成正式研究时依次写成 `YYYY-MM-DD-02.md`、`-03.md`。

`legacy/` 每家公司最多一份，只供偶尔翻阅。它不参与状态、队列、估值、触发价格、自选池或 current 判断。`stale` 是公司当前研究状态，不是历史文件后缀。

正式报告和历史档案都进入 Git，因此完整克隆仓库即可恢复报告正文。两类文件的区别只在研究语义：`reports/` 参与 current 判断，`legacy/` 永远只是历史参考。

## 状态

- `unseen`：尚未完成首次初筛；
- `ignore`：当前不值得投入正式研究或持续监控；
- `candidate`：已被主 Agent 选中，等待或正在正式研究；
- `covered`：已有当前有效正式报告，按价格或事件监控；
- `stale`：重大新事实使当前报告失效，暂停价格监控并等待更新。

证券范围另用 `active / inactive`；任务另用 `queued / running`。历史上是否写过报告不等于当前研究状态。

## 常用命令

```bash
# 查看状态、任务和自选池
python -m trading_os status
python -m trading_os validate

# 记录主 Agent 的 ignore / research_now 初筛结论
python -m trading_os screen record --input templates/screen-decisions.json

# 派发并完成单公司研究；报告自动追加到日期时间线
python -m trading_os research next --limit 4
python -m trading_os research complete --input templates/research-result.json

# 重建自选池；每日收盘后完整取价并扫描
python -m trading_os watchlist build
python -m trading_os watchlist run-close --date 2026-08-07 \
  --at 2026-08-07T16:30:00+08:00

# 获取并完成全市场公告判断
python -m trading_os events fetch --since 2026-08-09T00:00:00+08:00 \
  --until 2026-08-09T07:30:00+08:00 --output tmp/event-packet.json
python -m trading_os events complete --packet tmp/event-packet.json \
  --input templates/event-judgments.json

# 一次性旧格式迁移；以及从冻结标签恢复每家公司最佳历史旧稿
python -m trading_os reports migrate-current
python -m trading_os legacy-salvage candidates --limit 100
python -m trading_os legacy-salvage archive-best
```

完整状态约束和操作说明见 [精简研究流程](playbooks/simple-research.md)。迁移前的旧机制可从 Git 标签 `pre-simplification-20260808` 恢复，但旧资产不再参与当前运行。

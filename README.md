# Trading OS

Trading OS 是一套面向 A 股、由新事实驱动的轻量研究工作流。仓库的主要产品是可审计的公司研究状态、完整正式报告和研究日志；网站只是这些资产的只读展示。系统不做自动交易，也不因股票价格变化启动研究。

## 核心机制

1. 主 Agent 对全市场压缩事实只判断 `ignore / research_now`。
2. `research_now` 把公司标记为 `candidate` 并创建唯一研究任务；一家公司由一个 Agent 用统一提示词端到端完成。
3. 正式结果只有 `covered / ignore`，两者都追加一份脱离历史版本也能独立阅读的完整报告。
4. 财报、公告、治理、资本结构及行业经营变量触发研究；定期财报以及任何估值或结论变化，都生成新的完整正式报告。
5. 不改变正式结论的事件可以写研究日志；日志只能 `reaffirmed / monitor / invalidated`，不能充当报告补丁。
6. 证券价格不进入研究触发、公司状态或队列。展示层可以把实时价格与 `value_range` 机械比较，但这不是买入信号或投资决策。

没有研究强度分档、固定分钟数、复核 Agent、独立承保、经理审批、多 Agent 共识、收益率硬门槛或仓位审批。

## 当前事实源

```text
coverage/cn-a/research_state.jsonl                       全市场当前状态，一家公司一行
coverage/cn-a/research_queue.jsonl                       当前 queued/running 任务
coverage/cn-a/screening_baseline.json                    全市场初筛基线
coverage/cn-a/event_scan_state.json                      公告扫描成功检查点
research/watchlist.jsonl                                 active covered 的确定性投影
research/companies/CN/{代码}/reports/YYYY-MM-DD[-NN].md 完整正式报告时间线
research/companies/CN/{代码}/updates/YYYY-MM-DD[-NN].md 研究日志
research/companies/CN/{代码}/legacy/YYYY-MM-DD.md        隔离旧稿
```

`research_state.jsonl.report_path` 指向该公司最新正式报告，这个指针就是 current；同一天再次完成正式研究时依次写为 `-02`、`-03`。正式报告必须自足，禁止用“参见前序报告”替代商业、财务或估值正文。

财报更新不是给旧正文增加摘录：必须重写完整报告，区分累计与单季口径，逐项复核关键数字和截止日，并说明前次假设与本期实际如何改变判断和估值。新结果会拒绝已知拼接模板、财报原始片段、重复或冲突截止日、退役价格线，以及与结构化 `value_range` 不一致的正文核心合理价值区间；这些规则不追溯改写历史报告。

`updates/` 记录事件处理过程：

- `reaffirmed`：新事实确认当前报告；
- `monitor`：信息尚未越过原报告边界，继续观察；
- `invalidated`：当前报告失效，状态转 `stale` 并创建完整研究任务。

update 不得调整 `value_range`、正常化利润、核心逻辑、风险排序或 `covered / ignore`。财报后即使商业逻辑未变，只要估值需要调整，也必须写一份新的完整正式报告。

已有正式报告的公司不能再通过初筛命令直接转为 `stale`。扫描到的新事实必须先与当前报告的 `information_cutoff` 比较：已被报告吸收的旧公告不触发任何状态变化；报告截止日之后、但仍在原报告边界内的事实写 `reaffirmed / monitor`；确实使报告失效时，必须用 `updates record` 写入带明确事实截止点的 `invalidated` 日志，再由系统转为 `stale` 并创建更新研究任务。

## 状态

- `unseen`：尚未完成首次初筛；
- `ignore`：当前不值得正式研究，或正式研究后不值得持续覆盖；
- `candidate`：已选中，等待或正在正式研究；
- `covered`：已有当前有效正式报告，值得持续维护；
- `stale`：重大新事实使当前报告失效，等待完整更新。

证券范围另用 `active / inactive`；任务另用 `queued / running`。只有 active `covered` 进入自选池。

## 可视化研究台

`dashboard/` 是只读附属展示。它从仓库状态和正式报告生成页面，不维护第二套研究事实。实时行情仅用于显示现价与合理价值区间的机械关系，例如 `当前价格 / value_range.low`；行情缺失时显示 `—`，不回退到仓库中的价格状态，也不生成“关注价”“安全边际充分”或买入提示。

```bash
cd dashboard
npm install
npm run dev
```

## 常用命令

```bash
# 查看与校验
python -m trading_os status
python -m trading_os validate

# 一次性从 schema v1/v2 迁移到无证券价格触发的 v3
python -m trading_os state migrate-v3 --at 2026-08-14T17:00:00+08:00

# 记录初筛、派发并完成完整研究
python -m trading_os screen record --input templates/screen-decisions.json
python -m trading_os research next --limit 4
python -m trading_os research complete --input templates/research-result.json

# 记录不改变正式结论的事件处理；invalidated 会自动进入完整研究
python -m trading_os updates record --input templates/research-update.json

# 重建或查看 active covered 投影
python -m trading_os watchlist build
python -m trading_os watchlist list

# 获取并完成全市场公告判断
python -m trading_os events fetch --since 2026-08-09T00:00:00+08:00 \
  --until 2026-08-09T07:30:00+08:00 --output tmp/event-packet.json
python -m trading_os events complete --packet tmp/event-packet.json \
  --input templates/event-judgments.json
```

公告扫描负责发现、判断、记录 update 和创建任务，不消费研究队列。`research next` 与后续完整研究由独立的队列消费者执行，避免一次扫描同时承担抓取、裁决和深度研究而超时。正常扫描应从成功检查点直接推进到当前时间；短时间窗仅用于故障恢复，不应成为长期积压机制。公告抓取失败时保持原检查点，不产生部分状态更新。完整约束见 [精简研究流程](playbooks/simple-research.md)。

# 2026-07-29 Agent-first rapid triage 试运行

## 目的与边界

本次试运行只验证新流程从行政接入到正式画像预算物化的主链路，不包含尚未建立的生产质量抽查闭环：

```text
冻结 cohort
→ 一家公司一个独立 Agent 做 rapid triage
→ 封存并发布到公司不可变时间线
→ 生成无分数 comparison packet
→ 独立跨公司 Agent 全量复核
→ 写入 quick-profile / defer 队列
```

- `cycle_id`：`2026-07-29-agent-first-pilot-001`
- `information_cutoff`：`2026-07-29T17:50:00+08:00`
- 样本：按代码稳定顺序显式冻结 `CN:000042`、`CN:000045`、`CN:000048`
- 选择依据：行政试运行样本，不含因子、估值、风格或旧评级排序
- cohort：`coverage/cn-a/triage/2026-07-29-agent-first-pilot-001/cohort.json`
- cohort SHA-256：`0024fae9c22d919cda080fcce62b88393b9621d6d4b25d7f89e41148a8506e69`

本次不继续执行正式画像；`CN:000042` 进入 `quick_profile/pending` 是本试运行的预期交接结果，不是遗留失败。更深研究由后续长程 Goal 按预算继续。

## 单公司结果

| 公司 | rapid-triage 结果 | 独立 allocation | 关键判断 |
|---|---|---|---|
| `CN:000042` 中洲控股 | `triage_candidate` | `select_quick_profile` | 2026H1 预告利润显著改变旧基线，但利润是否转化为可支配现金、短债与存货风险是否同步改善仍可由下一小时研究收窄 |
| `CN:000045` 深纺织Ａ | `price_watch` | `defer` | S1 披露纠正了旧报告多项财务数据和“8 号线正在爬坡”的错误；项目仍在建设，当前价格已要求尚未证实的盈利修复，等待半年报或投产里程碑 |
| `CN:000048` 京基智农 | `price_watch` | `defer` | 2026H1 预亏且 6 月猪价低于可核验历史养殖成本；经营现金流尚为正，不作生存失败判断，等待成本、减值、周期或价格触发 |

对应封存资产：

- `CN:000042` package SHA-256：`63f758602e6ab32f09ac2d165602150c5e1e7a336630a2d650a6bc452779b094`
- `CN:000045` package SHA-256：`96fbd8f853c35da6961c759fc41c919bdd58656c5f8bfc84e6fae1fd16f04ac6`
- `CN:000048` package SHA-256：`a3f90ac402f6b65db0b333cd184b6ff98837adee77184b20ee92b09f16c3406c`

三份 package 均已发布到对应公司时间线，三家公司均清除 `rebaseline_required`，信息截止时间更新为本批次 cutoff。

## 横向预算配置

- comparison：`coverage/cn-a/triage/2026-07-29-agent-first-pilot-001/comparison.json`
- comparison SHA-256：`ea9ff2f79077aad512d8f4014c0a24a68e52bda9c75cc19072e2933d45929515`
- selection：`coverage/cn-a/triage/2026-07-29-agent-first-pilot-001/selection.json`
- selection SHA-256：`7f5ddf4f63868c1ab017fa1f23c8d9400e10c8e4647fd27fa1a01ad6c8276c6b`
- 独立 allocation Agent：`/root/pilot_allocator`
- 全量复核：`reviewed_count=3`，与 `cohort_count=3` 守恒
- 首轮候选：1 家；最终选择：1 家；defer：2 家
- 状态：`audit_status=completed_full_cross_company_review`

allocation Agent 必须对 comparison 的全部 rows 提交显式决策。首轮 `eligible_for_quick_profile=false` 的公司也能被救回；本次复核后没有发生救回，是独立判断结果，不是程序过滤结果。

## 试运行发现并修复的问题

首次成功发布 `CN:000042` 后，重放同一 package 曾因队列已为 `completed` 而失败。流程据此补上安全幂等发布：

- 首次发布返回 `idempotent=false`；
- 相同 package 重放返回 `idempotent=true`；
- 校验 package seal、内容、cohort 绑定、stage history、coverage 物化和公司时间线；
- 内容冲突、重复 history、缺失或损坏 seal 均拒绝；
- 公司已经晋级 `quick_profile` 后重放旧 package，不覆盖后续队列状态。

真实三家公司 package、comparison 和 selection 均完成了幂等重放验证。

收口审查又补了四类故障保护：

- 新生成且在 selection 内封存了 quick-profile 预算绑定的批次，如果 coverage 尚未写入或只写入 screening，重放会依据 seal 修复缺失物化；已进入 quick-profile running/completed 或更深阶段时不会回退。本 pilot 的 selection 早于预算绑定字段，只验证完整物化状态下的幂等重放；若其 queue 物化缺失会安全拒绝猜测预算。
- 同一家公司后续已有更新报告后，较早 rapid-triage package 仍可从完整历史按 source SHA 幂等返回，不会重复追加或改写当前状态。
- freeze 只接受明确的 intake 状态和任务类型；running、活动 assignment、正式画像及更深研究任务不能被清空或降级。
- 所有正式 screening/queue read-modify-write workflow 共用单写者锁；竞争写入会明确失败并可在锁释放后安全重试，不会覆盖其他 Agent 刚写入的行。`runs.jsonl` 的正式加锁写入入口仍属于长程基础设施边界。

当前尚无可信、可审计的逐公司经济风险簇分类。程序因此把 selected rows 保守视为同一 `unclassified` 簇，并执行 `risk_cluster_caps.quick_profile`；本次只选择 1 家，低于默认上限 10。

## 触发闭环

- 三家公司各自保留 3—4 个 filing、event、thesis、date 或 price 触发器。
- 价格触发器均进入 alerts 派生结果。
- `CN:000042` 的 `2026-09-01` 和 `CN:000048` 的 `2026-08-31` 日期触发器进入 schedule；以 `2026-09-02` 模拟构建时均变为 `due`。
- filing、event、thesis 当前只标为 `watching`。仓库尚未实现它们的 canonical observed-hit ledger，不会把触发器定义冒充已发生事件；这是后续增量研究机制仍需建设的边界。

价格提醒求值也已收紧为 fail-closed：行情 symbol 必须唯一，价格和带时区时间必须有效，快照相对显式检查时间最多陈旧 7 天、最多领先 5 分钟；承保结论的 10% 价格失效阈值从对应已封存 portfolio candidate 绑定参考价并独立重算，不再信任行情文件自报的相对涨跌字段。

## 尚未闭环的全市场基础设施

本次是显式冻结 3 家公司的机制试运行，不是全 A 范围守恒证明。仓库当前还缺少：

- 绑定普通 A 股 universe、`scope_cutoff`、来源哈希、纳入、硬排除和异常的全市场 manifest；
- 对停止分层执行半盲抽查并封存结果的正式质量审计契约；
- filing/event/thesis trigger hit 的 canonical 去重与消费账本。

因此不能从现有 companies、screening 和 queue 行数大致接近推断全 A 已闭环。长程 Goal 必须先建设并试运行以上机制，完成条件已写入 `prompts/goals/cn-all-a-continuous-research.md`。

## 验证

- `python -m trading_os assets validate`：5,530 家公司全部有效。
- `python -m trading_os coverage validate`：逐文件 schema 与唯一性验证通过；companies/screening 各 5,526 行，queue 5,521 行。该命令不证明全市场 scope 守恒。
- `python -m trading_os coverage reconcile --check`：`change_count=0`，`blocked_count=0`。
- `python -m trading_os coverage triage-status 2026-07-29-agent-first-pilot-001`：3/3 完成，comparison 与 selection seal 有效。
- schedule 与 alerts 使用 `tmp/` 输出验证，未覆盖工作区已有派生文件。
- `build_index("research")` 只读构建：5,530 家。
- `python -m pytest -q`：392 项全部通过。
- 本次涉及的 Python 文件 `ruff check` 全部通过，`git diff --check` 通过。
- 仓库级 `ruff check .` 仍报告 17 个本轮范围外的既存问题，位于未修改的研究抓取脚本和测试文件；本次不混入顺手格式化。

本次所有单公司与横向结果均为研究预算状态，不包含 `buy_now`、组合操作或仓位。

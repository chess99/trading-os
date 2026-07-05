# 2026-07-03 CANSLIM 全 A 筛选汇报

## 结论

今天的全 A CANSLIM 闭环筛选能用，但不能给高置信度交易结论。原因很简单：本次只有 AkShare 数据源，足够做研究队列和技术观察池，不足以支撑正式交易建议或回测证明。

结果上，系统从 4,981 个有效流动性样本里筛出 139 个候选，其中 28 个进入 strict CANSLIM 队列。真正需要今天盯盘的只有 1 个：绿的谐波（SSE:688017）。但它不是舒服的标准买点，而是“已经突破、但离 pivot 偏远且 base 偏深”的高波动观察对象。我的处理建议是：只放入 actionable watch，不追高下单，等待盘中是否回到合理买入区并确认量能。

其余 27 个 strict 标的全部先归为 wait_for_breakout。它们的共同问题是：基本面动量和相对强度强，但形态大多 base 过深，或者突破量能不够，今天不应被包装成买入清单。

## 今天该做什么

1. 绿的谐波（SSE:688017）列为唯一一级观察。
   - pivot：488.00
   - 买入区上沿：512.40
   - 风控止损：448.96
   - 量能倍数：1.86 倍，突破量能已确认
   - 风险：extended_from_pivot、base_too_deep
   - 我的判断：可以盯，不该追。若价格远高于 512.40，放弃本次买点；若回到买入区且不破坏量价结构，再进入风控评估。

2. 东杰智能（SZSE:300486）、超卓航科（SSE:688237）、新相微（SSE:688593）列为二级观察。
   - 它们在本次技术 flags 中没有 `base_too_deep`，形态相对干净。
   - 但当前决策仍是 wait_for_breakout，没有达到 actionable。
   - 触发条件：突破 pivot，并出现高于基准量能的确认。

3. 中际旭创、香农芯创、江波龙、精智达等高 RS 标的继续跟踪，但今天不追。
   - 这些票强度非常高，说明资金关注度在。
   - 但技术结构里普遍有 base_too_deep 或 extended 风险。
   - 处理方式是等待新的、较浅的整理结构，而不是在深 V 或过远位置追。

## 筛选结果

- 请求日期：2026-07-05
- 有效研究日：2026-07-03
- 全量候选：139
- strict 候选：28
- provisional 候选：111
- report 展示候选：30，仅是展示上限，不代表只筛了 30 个
- deep research run：28 个，机器状态均为 ok
- watchlist：28 个 strict 全部写入，其中 1 个 actionable、27 个 watching

过滤漏斗：

- ST 或非活跃：212
- 流动性不足：14
- 数据不足：88
- 无 CANSLIM 信号：4,754

## 观察池分层

| 层级 | 标的 | 处理 |
|---|---|---|
| 一级 | SSE:688017 绿的谐波 | actionable watch；只盯买入区和量能，不追高 |
| 二级 | SZSE:300486 东杰智能、SSE:688237 超卓航科、SSE:688593 新相微 | 形态相对干净，等待突破确认 |
| 三级 | 其余 24 个 strict | 基本面/RS 强，但 base 深或量能弱，只做观察池备选 |

## 我不满意的地方

这次机器生成的 company research report 不合格。它验证了 C/A/L/S 的确定性字段，但没有完成真正的深研：没有公告事件、没有主营结构、没有机构持仓、没有同业拥挤度，也没有把技术结构和基本面放在一起做取舍。所以这些 run 只能作为证据摘要，不能作为最终深度研究报告。

我已经把今天的人工复核写到：

- `artifacts/research/canslim-strict-review-20260703.md`

这份 strict review 才是今天 28 个 strict 标的的投研复核入口。

## 数据口径

本次只启用了 AkShare：

- universe snapshot：5,528 行，as_of=2026-07-03
- quote snapshot：5,203 行，as_of=2026-07-03
- fundamentals：4,981 行，as_of=2026-07-03
- bars：139 个候选懒补历史价格，时间范围 2025-05-09 至 2026-07-03

未启用 RQData、JQData、Tushare。缺少付费 PIT 财务、完整公告/新闻、机构持仓、主营构成和一致预期口径。因此今天的输出是研究队列和观察池，不是交易指令。

## 证据链

- Daily manifest：`data/research/runs/20260705T132519Z-daily_canslim_research-31971104/manifest.json`
- Screen manifest：`data/research/runs/20260705T132519Z-canslim_screen-8d1ca4a4/manifest.json`
- 全量候选表：`data/research/runs/20260705T132519Z-canslim_screen-8d1ca4a4/tables/all_candidates.csv`
- 决策表：`data/research/runs/20260705T132519Z-daily_canslim_research-31971104/tables/decisions.csv`
- 技术结构表：`data/research/runs/20260705T132519Z-daily_canslim_research-31971104/tables/technical_setups.csv`
- 观察池状态：`artifacts/watchlist/state.json`

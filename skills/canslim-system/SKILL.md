---
name: canslim-system
description: |
  CANSLIM 成长股体系入口。基于威廉·欧奈尔《笑傲股市》的成长股选股与交易系统。
  触发词："CANSLIM 分析 [标的]"、"成长股筛选"、"欧奈尔方法"、"基本面+技术面综合分析"、
  "这只股票值得长期关注吗"、"有没有真实业绩支撑"、"帮我做 CANSLIM 评分"。
  输出：通过 research recipe 生成快筛候选、深研报告和证据链。
---

# CANSLIM 成长股体系

CANSLIM 是 ResearchStore + DataHub + research recipe 驱动的成长股研究体系。

Agent 不直接拼接底层数据脚本，不直接读 parquet，不把快筛结果当作买入结论。

## 快筛入口

全 A 快筛使用：

```bash
python -m trading_os research run canslim_screen --as-of YYYY-MM-DD --top 30
```

该 recipe 会：

1. 读取或刷新全 A universe snapshot。
2. 读取或刷新 quote snapshot。
3. 读取财报缓存。
4. 对通过前置过滤的标的懒补齐相对强度所需历史价格。
5. 输出候选、评分拆解、过滤统计、manifest、trace 和 report。

快筛不应触发全市场逐标的历史 K 线刷新。

`--top` 只是展示上限：

- `report.md` 和 `tables/candidates.csv` 只展示前 N 个候选。
- 实际候选总数必须读 `manifest.json` 的 `candidates_total`。
- 严格候选总数必须读 `strict_candidates_total`。
- 全量候选明细必须读 `tables/all_candidates.csv`。

不要把 `Displayed Candidates` 当作全量扫描结果。

## 快筛后的默认动作

扫描完成后，agent 应按以下顺序推进：

1. 读取 manifest、report、`tables/all_candidates.csv`，解释全量候选数、展示数量、过滤统计和数据限制。
2. 对全部 `strict_canslim_candidate` 建立深研队列；不要任意只取 top 3。
3. 只在 strict 数量过多、用户要求压缩成本，或深研 recipe 明确受限时，才按分数/RS/流动性分批执行。
4. `provisional_research_queue` 不是正式候选；先补缺失字段或说明限制，再决定是否深研。
5. 深研完成后，必须在 `artifacts/research/` 写一份人类可读完整复核报告；不能只返回 `data/research/runs/...` 路径，也不能留下“后续再补”的维度后停止。
6. 完整复核报告必须包括：全量候选数、strict/provisional 数、全部 strict 标的、单标的报告路径、近 12 个月公告/事件、管理层指引/订单/产能/产品线索、机构持仓、主营构成、同业拥挤度、base/pivot/突破放量技术确认、数据限制、下一步队列。
7. 如果某个外部数据源真实失败，必须列明失败接口、失败原因、替代口径和对置信度的影响；不得把缺口写成待办后直接结束。
8. 完整复核报告完成后，再进入 watchlist、回测和风控。

## 单标的深研入口

对候选标的做完整研究：

```bash
python -m trading_os research company SSE:600660 --template quality_growth --as-of YYYY-MM-DD
```

深研报告必须说明：

- 核心财务数据和增长质量。
- 商业模式、护城河、竞争格局。
- 风险、机会、管理层指引或数据缺口。
- 估值口径和关键假设。
- 结论的置信水平和限制。

## 体系边界

CANSLIM 体系只做：

- 有真实业绩支撑的成长股。
- 相对强度领先、流动性足够的标的。
- 大盘环境不是明确熊市时的做多研究。

CANSLIM 体系不做：

- 纯技术面信号、没有基本面支撑的交易（用 Elder）。
- 低估值、低增长的价值股（用 Value）。
- 未经深研、风控和证据链支持的交易建议。

## 持仓管理

持仓监控仍使用 CANSLIM 双模式止损：

- 初期：7-8% 价格止损。
- 盈利后：逻辑止损，跟踪 EPS 增速、行业地位、机构持仓、重大风险事件。

任何交易动作都必须能通过 run manifest、研究报告、RiskManager 和 EventLog 追责。

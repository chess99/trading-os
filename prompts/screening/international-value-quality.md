# 港股商业质量筛选与 A/H 去重规范

> **市场范围调整说明**：投资者实际个股权限为 **A 股全板块 + 港股通**，原美股个股质量池（`screening/us/`）与覆盖队列已退役并归档至 `archive/retired-us-single-stocks/`；美股配置改由[美股宽基与国内 QDII 配置框架](../../research/macro/reference/us-broad-etf-qdii.md)与[全球产业龙头参照表](../../research/benchmarks/global-leaders.json)承载。本规范聚焦港股（港股通口径）双轨筛选与 A/H 同发行人合并。

## 一、研究目的与双轨筛选

沿用[双轨商业质量筛选规范](dual-track-screening.md)与[A 股规范](cn-a-value-quality.md)的 A/B 质量定义和普通股现金纪律，从港股全市场中识别值得持续跟踪的**纯港股核心企业**及**具备特定比价或治理研究意义的 A/H 双重上市标的**：

- **轨道一（`compounder`）**：互联网平台、港股通高现金消费品牌、公用基建、金融交易所及高质量制造；
- **轨道二（`inflection_growth`）**：由行业研究层触发的港股科技、生物医药、新能源车/智能驾驶及出海制造早期成长期或周期拐点企业。

## 二、A/H 同发行人去重与港股通实操约束

1. **`issuer` 合并与去重**：与 A 股双重上市的发行人，其 `issuer` 必须精确指向对应 `CN:` 主代码（例如 `HK:00300` 的 `issuer` 为 `"CN:000333"`）。全部市场视图按发行人合并计数，且在[港股通桥接配置](../../research/markets/ah-southbound-bridge.json)中登记股份比例与红利税结构。
2. **优先研究纯港股增量标的**：已有完整 A 股发行人报告的 A/H 重合股，不再消耗额外 Token 在港股侧重复写相同经营正文，只维护税后汇率比价桥；深研配额优先倾斜给仅在港股上市的核心标的（如腾讯、网易、农夫山泉、香港交易所、安踏体育、美团、申洲国际、创科实业等）。
3. **港股通可交易性与现金口径**：入池复核时标明是否属于港股通标的；金融/公用/平台企业严格核查注销式回购、股份支付稀释、跨境资金上划与权益法资产，不将账面回购缩股后的虚高 ROE 直接外推为增量资本回报。

## 三、v3 数据合同

港股池保存于 `screening/hk/value-quality/pool.json`，采用 v3 合同（完整覆盖 `universe.securities`、`review.exclusions`、`issuer`、`research_question`、带来源索引的 `metrics`），可选填充 `track`（`"compounder"` / `"inflection_growth"`）与 `industry_topic`。

```bash
python -m trading_os quality-pool --market hk status
python -m trading_os quality-pool --market hk validate
python -m trading_os quality-pool --market hk list --track inflection_growth
python -m trading_os quality-pool --market hk replace --input <完整池.json>
```

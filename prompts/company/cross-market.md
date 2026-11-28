# 港股与 A/H 发行人合一研究补充（港股通口径）

商业判断、价值定义、四情景与慢变量结构化要求沿用[统一深研提示词](standard-deep-research.md)与[核验附录](research-verification.md)。本补充规范港股普通股研究及 A/H 双重上市发行人的统一处理规则。

> **交易权限边界**：投资者通过 **A 股全板块 + 港股通** 交易个股。**美股个股研究与覆盖队列已退役**（见 [archive/README.md](../../archive/README.md)），美股资产统一通过国内场内美股宽基 QDII ETF 配置，仅保留 [global-leaders.json](../../research/benchmarks/global-leaders.json) 作为全球产业参照。

## 一、A/H 同发行人合一研究原则

对于同时在 A 股和港股上市的发行人（清单维护在 [ah-southbound-bridge.json](../../research/markets/ah-southbound-bridge.json)）：

1. **经营底稿合一，禁止重复造轮子**：同一发行人的商业模式、行业竞争、经营预测、母公司合并财务与长期现金流分析只维护一份核心发行人研究；**不分别为 A 股和 H 股重写两套内容雷同的 3 万字报告**。
2. **每股单位与汇率换算**：当以主上市地或主披露口径完成发行人模型后，另一市场证券只需通过股本换算比（当前 A/H 均为 `1:1`）和当期央行/外汇局港币中间价换算每股 `value_range`、`scenarios` 与 `return_model`，并在报告与 `security_basis` 中标明换算汇率及汇率敏感性。
3. **排期去重**：同一发行人同一时刻仅允许在一个市场队列中持有活动任务，A/H 同步入池时优先排期信息披露更完整、或代表主要上市口径的一侧并同步联动桥接映射。

## 二、港股通税务与股东权利边界

港股与 A/H 比价绝不能忽略交易通道带来的真实税后现金差异：

1. **红利税率规则（内地个人投资者通过港股通）**：
   - **H 股**（内地注册在港上市）：由 H 股公司按 **20%** 代扣个人所得税（`southbound_dividend_tax_rate = 0.20`）；
   - **中资红筹股**（境外注册但认定为中国居民企业，如中国移动、中国海油等）：若发行人先向香港结算预提 **10%** 企业所得税、再由中国结算按余额代扣 **20%** 个税，实际综合红利税可达 **28%**（`10% + 90%×20%`）。研究须核对发行人最近一期派息公告的实际代扣条款，在 `capital_return_profile.southbound_dividend_tax_rate` 如实填写（默认参考 [ah-southbound-bridge.json](../../research/markets/ah-southbound-bridge.json)）；
   - **其他港股通非 H 股**（如开曼/香港本地主体腾讯、网易、港交所、安踏等）：由中国结算代扣 **20%** 个人所得税（`0.20`）；
   - **A 股对比基准**：内地个人投资者持有 A 股满一年股息红利暂免个税（`0.0`），持股 1 个月至 1 年为 `10%`，1 个月以内为 `20%`。
2. **转让价差**：港股通个人投资者买卖港股取得的转让差价目前暂免个人所得税，因此**港股通税务折价只作用在现金股息（`base_case_distributions_per_share`），不扣减第 5 年终值资本利得部分**。
3. **回购型港股**：对以注销式回购为主要资本返还方式的港股标的（如腾讯、汇丰、友邦等），采用 `buyback_total_yield` 框架，在模型中扣减回购资金并同步缩小股数，同时在 `capital_return_profile.annual_net_buyback_per_share` 记录净增厚口径，避免税后股息率掩盖真实股东回报。

## 三、港股财报槽位与结构化依据

- **槽位沿用发行人财年**：`YYYY-FY / Q1 / H1 / Q3` 按发行人实际财年确定；港股主板若不强制季报且未发自愿季报，则只按 `H1` 与 `FY` 推进周期，不空造季度槽位。
- **必填字段**：任务与结果须完整提供 `financial_basis`（`period_end`、`published_on`、`source_url`）与 `security_basis`（`currency: "HKD"`、`unit`、`ordinary_shares_per_unit`、`source_url`），正文写明 `财务期末：YYYY-MM-DD` 与 `财报披露：YYYY-MM-DD`。
- 房地产投资信托按每基金单位计算分派与剩余权益，`security_basis.unit` 使用 `fund_unit`。交易所可买名单之外的独立港股注明核对日期，股息按税前金额列示，`southbound_dividend_tax_rate` 留空。
- **排期命令**：使用 `python -m trading_os research --market hk enqueue-latest --input disclosures.json [--apply]`，依据实际已披露财务期末预览和派发。

参考：[香港交易所上市规则与财务披露](https://www.hkex.com.hk/Listing/Explore-By-Role/Listed-Issuers/Equity-Securities?sc_lang=en)、[港股通桥接配置](../../research/markets/ah-southbound-bridge.json)。

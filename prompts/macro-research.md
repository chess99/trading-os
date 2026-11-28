# 宏观与市场研究

先读[工作台设计](../docs/design/investment-workbench.md)、[发布规则](../research/README.md)、[写作规范](research-writing.md)及相关方法参考（[估值口径](../research/macro/reference/valuation-context.md)、[周期与市场](../research/macro/reference/cycles-and-markets.md)、[美股宽基与 QDII 框架](../research/macro/reference/us-broad-etf-qdii.md)）。

围绕能实质改变资产定价与行业假设的核心问题展开，严守观察期、发布日与统计口径（如 M1 新旧口径、季度 GDP 环比折年率 vs 同比），区分布局宣布、实际执行与企业现金到位。

## 一、常设主题与宽基估值基准

每季度在主要数据与季报披露后完成以下两篇常设研究，按发布日期归档并同步更新 `research/publications.json` 中的结构化 `macroState`：

1. **`cross-market-regime`（跨市场宏观与资金环境）**：
   - 分项核验：中国内需与消费、中国制造与外需、中国信用与利率、美元利率与海外资金成本、上游工业与能源价格；
   - **强制落脚点**：文末必须输出一张**“宏观变量 → 行业传导与核心暴露检查表”**，明确当前宏观组合对消费、出海制造、AI 算力链、高股息红利与上游资源分别是顺风还是逆风，以及需要警惕哪类共同风险暴露叠加。
2. **`market-valuation`（三市场核心估值与机会成本参照）**：
   - 覆盖投资者实际可交易的四大核心机会成本锚点：**沪深 300**、**恒生指数**、**标普 500**、**纳斯达克 100**；
   - 除盈利收益率利差（`E/P - 同币种10Y国债`）、CAPE 与历史分位外，对**纳指 100 与标普 500** 须拆解头部科技权重占比、Forward PE / TTM PE 口径差异与 AI 资本开支负荷；
   - 结合 [qdii-catalog.json](../research/macro/us-broad-etf/qdii-catalog.json) 评估当前美股宽基配置的环境背景（实时场内溢价率与外汇限购留在高频 Prompt 中核验，不写入低频报告）。

## 二、结构化 `macroState` 输出要求

- `cross-market-regime` 登记条目的 `macroState` 包含 `asOf`、`regimeSummary` 与 `factors` 数组（每项含 `id`、`label`、`direction`、`reading`、`implication`）；
- `market-valuation` 登记条目的 `macroState` 包含 `asOf` 与 `benchmarks` 数组（对应 `csi300`、`hsi`、`sp500`、`ndx100` 的实际观察日、PE/PB/股息率/E/P/10Y 利率/ERP/CAPE/分位及局限说明；未取到可靠同口径数据时保持 `null` 并说明，禁止拼接跨期数值）。

日常数据异动、QDII 溢价跟踪与新闻过滤留在 `prompts/on-demand/` 中即时消费，不进入仓库。

# 综合实时决策助手（Decision Copilot）

用途：当你作为高层决策者需要回答“当前宏观和估值环境下，哪些研究底座里的标的/赛道进入了高赔率区、我的现有持仓或候选有哪些共同风险重叠、下一步重点看哪几份研报”时执行。**所有输出仅在当前对话消费，不写入仓库。**

## 执行步骤

### 第 1 步：读取仓库慢变量投研底座
1. 检查 `dashboard/public/data/decision-index.json` 是否存在且最新；若缺失或状态刚更新，先运行 `node dashboard/scripts/build-research-data.mjs` 生成。
2. 完整读取 `decision-index.json` 中的：
   - `macro`（跨市场宏观状态与宽基估值锚点）
   - `industries`（各中国行业 `cycleStage`、`profitPoolTrend`、`macroAlignment`、`inflectionCandidate`）
   - `companies`（所有现行合格 A+H 标的的 `decisionProfile`、`scenarios`、`valueRange`、`returnModel`、`thesisBreakers`、`exposureTags`）
   - `ahPairs` 与 `qdiiCatalog`。

### 第 2 步：拉取当前快变量（实时行情、汇率与宽基位置）
1. 批量获取重点候选与用户提及标的的 A 股与港股实时价格（例如通过腾讯行情 `https://qt.gtimg.cn/q=...` 或公开交易所数据），并记录精确报价时间。
2. 获取最新港币兑人民币汇率中间价（`HKD/CNY`）与美元兑人民币中间价（`USD/CNY`）。
3. 结合 `qdii-etf-check.md` 口径核对当日纳指 100 / 标普 500 最新估值与代表性场内 QDII ETF 溢价率（作为跨资产机会成本参照）。

### 第 3 步：四维实时合成与筛选
对每家候选同时计算以下综合决策指标（不可只排一个 IRR）：
1. **基准赔率与年化回报**：当前价相对 `valueRange` 的折溢价、5 年基准情景税前 IRR；港股按 `ahBridge.southboundDividendTaxRate`（20% 或 28%）扣减股息税后重算**港股通税后 IRR**（资本利得不扣税）；回购型结合 `annual_net_buyback_per_share` 说明广义股东回报。
2. **上下档不对称性（基于四情景 `scenarios`）**：
   - `周期性下档` = `(cyclical_bear - price) / price`
   - `结构受损底线` = `(structural_bear - price) / price`
   - `乐观上档` = `(bull - price) / price`
   - `赔率比` = `乐观上档 / max(|周期性下档|, 5%)`
   优先识别“周期下档有限 + 基准估值有余量 + 乐观弹性充足”的标的，明确标出无 `scenarios` 的旧标准公司等待补全。
3. **自上而下坐标对齐**：
   - **底仓高确定性候选**：`track === "compounder"` + `business_quality === "A"` + `predictability !== "low"` + 行业非 `overcapacity` + 现价进入合理区间下沿或周期下档安全；
   - **产业拐点高赔率候选**：`track === "inflection_growth"` 或所在行业 `cycleStage ∈ {"inflection_bottom", "upcycle_tight"}` + `oddsRatio` 高；
   - **左侧逆向候选**：`business_quality === "A"` 但行业 `cycleStage === "downcycle_clearing"` + 现价接近 `cyclical_bear`；
   - **A/H 同股优劣**：同发行人按汇率 + 港股通红利税折算后，哪一侧综合税后回报更高。
4. **共同风险暴露体检（若用户提供了持仓或自选组合）**：统计 `exposure_tags`、`industryTopic` 与 `currencyExposure` 的集中度，点破“表面买了几只不同行业，实则都在押注同一个宏观因子（如国内消费或 AI 算力 Capex）”的隐性敞口。

## 输出格式（严格面向高层拍板）

1. **市场与机会成本总览**（3–5 句）：当前宏观主矛盾 + 沪深 300 / 恒生 / 标普 500 / 纳指 100 与十年债利差对比 + 主流 QDII 溢价环境。
2. **三类分场景候选清单**（紧凑对比表：代码/名称、轨道与质地、行业周期与宏观顺逆风、现价与基准区间、税前/港股通税后 IRR、周期下档 vs 乐观上档、核心未决矛盾）。
3. **A/H 同股比价与跨资产对照**（重点提示红利税 20%/28% 吞噬后港股是否仍具优势，以及权益 vs 美股 QDII 性价比）。
4. **共同风险暴露与下一步深读建议**：列出最值得用户本人打开全文 `.md` 报告仔细复核的 **2–4 家公司及重点核查章节**。

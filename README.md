# Trading OS

Trading OS 是服务 **A 股（全板块）+ 港股（港股通口径）**，并以 **美股国内可投宽基 QDII ETF 与 25 家全球产业龙头参照** 补足全局视角的 AI 投研持久化工作台与高层决策平台。

仓库保存**低频、结构化、价格无关的慢变量研判底座**（供下游决策 AI 秒级调用与高层决策者按需阅览）；高频实时行情、四情景赔率对比与港股通税后 IRR 由决策台实时合成，日常观察与即需分析只提供提示词工具箱，不入库。

整体结构与慢快变量设计见[工作台设计](docs/design/investment-workbench.md)，报告更新与发布规则见[研究目录说明](research/README.md)。

## 核心定位与分工

| 层级 | 核心资产与频率 | 产出方式 |
|---|---|---|
| **慢变量底座（进 Git）** | 宏观状态（`macroState`）、34 个中国行业周期/顺逆风状态（`industryState`）、双轨公司质量池、FY/H1/Q1/Q3 完整公司研报、四情景锚点与改判条件（`decision_profile` / `scenarios` / `capital_return_profile`）、25 家全球龙头参照、A/H 港股通税桥 | AI 深度研究，低频提交，供其他 AI 快速调度决策 |
| **实时合成层（内存计算）** | 实时现价、5 年基准 IRR、港股通分红税后 IRR（H 股/一般港股 20%、红筹居民企业 28%）、四情景上下行空间与不对称赔率、决策视角筛选 | 研究台与 AI 决策索引按实时价格即时合成，不写回仓库 |
| **高频即需工具箱（不进 Git）** | 早晚市场观察、决策副驾、A/H 同发行人比价、国内美股 QDII 溢价核查、同行横评、新公司快筛 | 执行 [prompts/on-demand/](prompts/on-demand/README.md) 提示词，随用随清 |

## 公司研究与双轨机制

1. **双轨筛选（`track` 正交于 `tier`）**：
   - `compounder`（复利质量）：关注长期护城河、普通股自由现金与资本配置；
   - `inflection_growth`（产业拐点与早期成长）：由行业 `inflectionCandidate` 自上而下触发，核验供给出清/渗透拐点、客户验证与边际单位经济性改善，容忍重投期自由现金为负但严守稀释边界，兼顾早期复合或十倍潜质机会（规范见[双轨筛选规范](prompts/screening/dual-track-screening.md)）。
2. **统一全量周期更新**：FY / H1 / Q1 / Q3 统一产出完整自足报告，不拆分残缺简报。Q1/Q3 缺少完整附注时，正文显式声明**承接最近一份 H1/FY 已核实权益桥与资产结构**；正文设**经济重要性门槛**（<3%–5% 细项不做伪精确法医推演），按四类商业形态适配估值方法（`dividend_dcf_v1` / `buyback_total_yield` / `growth_terminal_matrix` / `cyclical_cost_curve`）。
3. **诚实淘汰与重写边界**：研究结论只有 `covered / ignore`；同周期重研覆盖原文件，用户明确要求更正时用 `research enqueue-rewrite`。
4. **高层与 AI 决策接口**：构建产物 `dashboard/public/data/decision-index.json` 把慢变量环境、行业状态、全球对标与已验收公司画像聚合为一份确定性索引，供任何下游决策 AI 与[决策副驾提示词](prompts/on-demand/decision-copilot.md)直接读取。

单公司研究使用[主提示词](prompts/company/standard-deep-research.md)和[核验附录](prompts/company/research-verification.md)。报告写作遵守[写作规范](prompts/research-writing.md)，归档边界见[研究文件与模型交付规范](docs/research-artifacts.md)。

## 研究板块与归档

| 板块 | 留存成果 | 入口 |
|---|---|---|
| 个股研究 | 双轨商业质量初筛、A+H 完整财报周期研报与慢变量画像 | [双轨筛选](prompts/screening/dual-track-screening.md)、[公司深研](prompts/company/standard-deep-research.md) |
| 行业研究 | 34 个中国行业完整报告、指标与 `industryState` 状态标签 | [行业研究规范](prompts/industry-research.md) |
| 宏观与宽基 | 跨市场环境、市场估值、国内美股 QDII 宽基名录及参照标准 | [宏观研究规范](prompts/macro-research.md)、[QDII 名录](research/macro/us-broad-etf/qdii-catalog.json) |
| 全球龙头参照 | 25 家海外/全球产业龙头经济天花板对比基准 | [全球龙头参照表](research/benchmarks/global-leaders.json) |
| 历史归档 | 已退役美股单股资产与 2026-Q1 未引用旧稿 | [归档说明](archive/README.md) |
| 高频即需工具 | 决策副驾、每日观察、A/H 对比、QDII 溢价核查 | [即需提示词目录](prompts/on-demand/README.md) |

## 唯一事实源

```text
coverage/{cn-a|hk}/research_state.jsonl                    A股与港股全市场证券及最新完成周期状态
coverage/{cn-a|hk}/research_queue.jsonl                    当前 periodic / manual_rewrite 任务
research/companies/{CN|HK}/{代码}/reports/YYYY-{FY|Q1|H1|Q3}.md 财报周期完整报告
screening/{cn-a|hk}/value-quality/pool.json                动态重点跟踪池（含可选 track / industry_topic）
research/industries/catalog.json & topic-routes.json       34 个行业主题与公司行业确定性映射
research/markets/ah-southbound-bridge.json                 15 对 A/H 发行人与港股通 20%/28% 红利税桥
research/macro/us-broad-etf/qdii-catalog.json              纳指100 / 标普500 国内 QDII ETF 目录
research/benchmarks/global-leaders.json                    25 家全球产业龙头对标（不入库、不建队列）
research/standards/registry.json                           公司研究展示标准
research/publications.json                                 行业、宏观报告（含状态标签）与方法发布目录
archive/                                                   退役美股单股资产与 2026-Q1 未引用旧稿归档
```

`basis_report_path` 和 `report_period` 只绑定结构化状态所依据的最新周期报告，不宣称报告在今天仍然“有效”。每份报告按自身财报周期、信息截止和研究标准阅读。`covered / ignore` 是该周期的研究结论，不是事件驱动状态。

公司状态只使用：

- `unseen`：尚无全市场基础判断；
- `ignore`：没有完成报告，或最近完成周期结论为不持续覆盖；
- `covered`：最近完成周期结论为持续覆盖。

证券范围另用 `active / inactive`；任务只用 `queued / running`，触发类型只用 `periodic / manual_rewrite`。

## 财报周期报告

研究结果必须显式提交 `report_period`：

- `YYYY-FY`：年度报告周期；
- `YYYY-Q1`：一季报周期；
- `YYYY-H1`：中报周期；
- `YYYY-Q3`：三季报周期。

同周期重写覆盖同一文件并重新验收，Git 保存自然修改历史，但产品不提供旧修订入口。跨周期报告并存，研报库默认打开最新周期并允许切换其他周期。

财报更新必须重新形成完整报告，区分累计、单季、同比和环比口径，复盘前次关键假设，并重新核验股本、普通股归属、正常化经营、估值和模型。不能把新财报摘录拼接到旧正文。

每份新结果都必须包含非空 `return_model_note`；能可靠建模时同时提交 `return_model`，否则为 `null` 并说明决定性缺口。五年模型包括未来五项每股实际现金分配和独立第五年终值；三年终值可选，但必须独立研究。

## 跨市场与港股通架构

研究台的活跃股票市场收束为 **A 股（主板/创业板/科创板/北交所）与港股（港股通口径）**：

- **A/H 同发行人统筹与港股通税桥**：公司池在全部市场按发行人合并 A/H 多地上市；[A/H 与港股通桥接表](research/markets/ah-southbound-bridge.json)记录已核对的 15 对 A/H 映射及港股通个人投资者红利税默认口径（H 股与一般非居民港股 20%，境内居民红筹 28%，转让差价 0%，A 股持股满一年 0%）。研究台对港股公司实时展示**港股通税后五年 IRR** 估算，同时不修改公司原生税前持有人回报模型。
- **美股投资接口重构**：不再维护美股单股筛选池与持仓队列（既有资产已归档至 `archive/retired-us-single-stocks/`），改为**美股国内可投宽基 QDII ETF 框架**（[纳指100 / 标普500 目录](research/macro/us-broad-etf/qdii-catalog.json)）配合 **25 家全球产业龙头参照表**（[global-leaders.json](research/benchmarks/global-leaders.json)）服务 A/H 行业和个股对比。

```bash
python -m trading_os quality-pool --market cn-a status
python -m trading_os quality-pool --market hk status
python -m trading_os industry validate
```

默认市场为 `cn-a`。A/H 双重上市发行人仍由两地证券分别按本地披露归档并独立建模，跨市场规则见[跨市场研究补充](prompts/company/cross-market.md)。

## 动态重点跟踪池（双轨）

价值质量池支持 `compounder`（复利质量）与 `inflection_growth`（产业拐点）双轨筛选，只回答哪些公司值得持续研究，不表达买入、仓位或当前估值。

```bash
python -m trading_os quality-pool status
python -m trading_os quality-pool validate
python -m trading_os quality-pool list --track inflection_growth
python -m trading_os quality-pool replace --input <完整池.json>
```

## 常用命令

```bash
# 校验
python -m trading_os status
python -m trading_os validate

# 全市场筛选完成后保存本轮名单，按实际披露派发
python -m trading_os quality-pool freeze-period --period 2026-Q3
python -m trading_os quality-pool list --period 2026-Q3
python -m trading_os research enqueue-period --period 2026-Q3

# 领取与完成
python -m trading_os research next --limit 4 --trigger-kind periodic
python -m trading_os research start <task_id>
python -m trading_os research complete --input <已验收完整候选.json>

# 用户明确要求同周期重写
python -m trading_os research enqueue-rewrite \
  --period 2026-H1 --batch-id manual-2026-10 \
  --input <公司及具体原因.json>
python -m trading_os research next --limit 4 --trigger-kind manual_rewrite
```

人工重写输入示例：

```json
{
  "at": "2026-10-15T12:00:00+08:00",
  "reason": "报告质量复核后需要完整重写",
  "companies": [
    {"symbol": "CN:000001"},
    {"symbol": "CN:000002", "reason": "关键普通股现金桥存在错误"}
  ]
}
```

[研究结果模板](templates/research-result.json)只演示字段合同，身份、数字、假设和来源均须替换并完成实际研究。

## 可视化研究与决策台

`dashboard/` 从仓库确定性生成，构建同时产出 `decision-index.json`（慢变量 AI 决策索引）和 `global-benchmarks.json`：

- 顶部折叠**宏观与宽基环境条**，展示跨市场状态、主要指数估值状态及国内美股 QDII ETF 名录；
- **最新周期模型**只展示按现行兼容标准完成的研究，按实时价格合成四年化 IRR、港股通税后 IRR、四情景不对称赔率，以及决策视角（核心防御 / 产业拐点 / 港股通与A-H）、轨道、行业周期和宏观顺逆风筛选；
- 这些实时计算值不写回仓库，不触发自动任务，也不直接替代人工终审与实际交易。

```bash
cd dashboard
npm install
npm run dev
```

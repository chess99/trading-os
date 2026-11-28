# 按需高频执行提示词工具箱（不入库）

本目录沉淀日常交易决策与动态监控所需的高频执行 Prompt。与 `research/` 中低频沉淀的深度研究严格分工：

- **只读消费仓库资产，结果不写回 Git**：不在仓库创建日报目录、实时价格记录或个人账户持仓文件；
- **复用 AI 投研底座**：优先读取由构建脚本确定性生成的 `dashboard/public/data/decision-index.json`（若文件缺失或仓库刚更新，先执行 `node dashboard/scripts/build-research-data.mjs`），不必每次重头分析全市场；
- **严格结合交易权限**：A 股全板块（主板/创业板/科创板/北交所）+ 港股通（计入 20%/28% 红利税）+ 国内美股宽基 QDII ETF（标普 500 / 纳指 100）。

## 场景索引

| 工具文件 | 适用场景 | 核心输入 |
|---|---|---|
| [decision-copilot.md](decision-copilot.md) | **综合实时投资决策简报**（核心入口） | `decision-index.json` + 实时 A/H 行情与汇率 + 用户临时关注/持仓 |
| [daily-brief.md](daily-brief.md) | **盘后/每日异动过滤** | `decision-index.json`（`thesis_breakers` 与宏观因子）+ 当日权威公告/数据 |
| [qdii-etf-check.md](qdii-etf-check.md) | **美股宽基与国内 QDII 实时体检** | `qdii-catalog.json` + 标普 500/纳指 100 估值 + 场内溢价与限额 |
| [ah-compare.md](ah-compare.md) | **A/H 同股实时比价与税后股息测算** | `ah-southbound-bridge.json` + 发行人最新报告 + 实时股价汇率 |
| [peer-comparison.md](peer-comparison.md) | **同行业 2–4 家公司横向 PK** | 仓库个股报告 + `global-leaders.json` + 实时行情 |
| [company-quick-screen.md](company-quick-screen.md) | **新线索 30 分钟快速排雷** | 公司最新年报/中报/季报 + 所属行业报告，决定是否入轨道一或轨道二 |

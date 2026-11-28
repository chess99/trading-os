# Trading OS 仓库协作

在当前分支开发，文档默认使用中文。开始前检查工作区和暂存区。一个完整任务通过验证后提交一次，跨日的同一批研究可合并提交。派发、领取、单家公司计数和临时返工留在工作目录。只暂存本次改动，提交前检查 `git diff --staged`。

## 研究入口

项目结构见[工作台设计](docs/design/investment-workbench.md)，命令见 [README](README.md)。开始公司研究前阅读[财报周期流程](playbooks/simple-research.md)和[重点池任务](prompts/goals/cn-all-a-continuous-research.md)。

| 工作 | 必读规范 |
|---|---|
| 价值质量筛选 | [双轨筛选](prompts/screening/dual-track-screening.md)、[A 股筛选](prompts/screening/cn-a-value-quality.md)，港股另读[跨市场筛选](prompts/screening/international-value-quality.md) |
| 单公司研究与验收 | 完整阅读[统一深研](prompts/company/standard-deep-research.md)、[核验附录](prompts/company/research-verification.md)和[报告写作](prompts/research-writing.md)。港股及 A/H 另读[跨市场补充](prompts/company/cross-market.md) |
| 公司研究派发 | [单公司任务简报](prompts/company/research-task-brief.md) |
| 登记研究结果或修改网页 | [现行研究展示标准](research/standards/README.md) |
| 模型、输入与复算 | [研究文件与模型交付](docs/research-artifacts.md) |
| 行业、宏观与即需分析 | 按主题阅读[行业研究](prompts/industry-research.md)或[宏观研究](prompts/macro-research.md)，遵守[写作规范](prompts/research-writing.md)和[发布规则](research/README.md)；日常与实时决策参考 [即需提示词工具箱](prompts/on-demand/README.md) |

## 数据与写入

- 活跃研究状态和队列位于 `coverage/{cn-a|hk}/research_state.jsonl` 和同目录的 `research_queue.jsonl`（美股单股已退役并归档至 `archive/retired-us-single-stocks/`；2026-Q1 未引用旧稿已归档至 `archive/legacy-2026-q1/`）。
- 质量筛选只更新活跃市场的 `screening/{cn-a|hk}/value-quality/pool.json`，支持 `track`（`compounder | inflection_growth`）与 `industry_topic`。用 `quality-pool` 维护成员及分层，`current.md` 由它确定性生成。池内严禁写入估值、现价、买点、任务或报告指针。
- 每轮先结合行业 `inflectionCandidate` 与全市场质量筛选更新入选名单，再按实际披露派发深研。同一发行人的 A/H 证券在同一时刻只领取一项任务。每家公司使用独立上下文，由一名研究者完成研究和必要返工。
- 协调器验收完整正文与结构化候选（含可选慢变量字段 `decision_profile`、`scenarios`、`capital_return_profile`）后，通过 `research complete` 一次写入报告、最新状态和当期标准。研究者不直接改共享 JSONL。
- 公司报告保存在 `research/companies/{CN|HK}/{ticker}/reports/YYYY-{FY|Q1|H1|Q3}.md`。所有四个报告期均保留完整自足报告；同周期覆盖，跨周期新增。`basis_report_path` 和 `report_period` 同步绑定最新完成周期。港股使用发行人财年，保留实际财务期末、披露日、来源、证券单位及港股通分红税率口径。
- 34 个中国行业主题及常设宏观主题逐季研究，并在 `research/publications.json` 维护 `industryState` / `macroState` 结构化慢变量。25 家全球行业龙头参照维护在 `research/benchmarks/global-leaders.json`，国内美股宽基 QDII 名录维护在 `research/macro/us-broad-etf/qdii-catalog.json`。日常观察与实时即需决策使用 `prompts/on-demand/` 与 `prompts/daily-market-observation.md`，结果**不提交进入 Git**。

## 研究与展示

公司研究先形成长期商业判断，再用财务、资本和普通股权益模型检验，并在正文保留重要性门槛与 Q1/Q3 附注继承说明。事实有公开出处，预测交代依据、范围及模型后果。价值含义以主提示词的[价值定义](prompts/company/standard-deep-research.md#价值定义)为准。区分慢变量经济判断、四情景锚点与实时价格带来的动态赔率/买点。

正式结论为 `covered` 或 `ignore`，均须有自足的完整报告。每次提交非空 `return_model_note` 与可选的 `decision_profile` / `scenarios` / `capital_return_profile`；现价、四情景不对称度及港股通税后 IRR 仅在展示层与 AI 实时分析中合成。公司慢变量研究严禁输出目标买价、仓位或交易指令。

网页默认展示动态重点池最新周期中符合兼容标准的结果，并在构建时生成供下游决策 AI 调用的 `dashboard/public/data/decision-index.json`。历史周期按各自资料截止阅读，不加载现价或最新摘要。

## 验证

- 修改共享状态后执行 `.venv/bin/python -m trading_os --market cn-a validate` 与 `--market hk validate`；修改质量池或行业映射后执行对应 `quality-pool validate` 与 `industry validate`。
- 模型复算使用当前源码和必要输入。报告、计算代码、必要数据及简明结果进入 Git。下载缓存、候选稿、全量轨迹、构建产物（`dashboard/public/data/`、`dashboard/dist/`）和即需提示词产出不提交进 Git。
- 网页与导出修改须验证研究状态，执行 `node dashboard/scripts/report-standards.mjs validate`，并在 `dashboard/` 运行 `npm run data`、`npm test`、`npx tsc --noEmit`、`npm run lint` 与 `node tests/standard-browser.mjs`。只报告实际执行的检查。

# Trading OS 仓库协作

在当前分支开发，文档默认使用中文。开始前检查工作区和暂存区。一个完整任务通过验证后提交一次，跨日的同一批研究可合并提交。派发、领取、单家公司计数和临时返工留在工作目录。只暂存本次改动，提交前检查 `git diff --staged`。

## 研究入口

项目结构见[工作台设计](docs/design/investment-workbench.md)，命令见 [README](README.md)。开始公司研究前阅读[财报周期流程](playbooks/simple-research.md)和[重点池任务](prompts/goals/cn-all-a-continuous-research.md)。

| 工作 | 必读规范 |
|---|---|
| 价值质量筛选 | [A 股筛选](prompts/screening/cn-a-value-quality.md)，港美股另读[跨市场筛选](prompts/screening/international-value-quality.md) |
| 单公司研究与验收 | 完整阅读[统一深研](prompts/company/standard-deep-research.md)、[核验附录](prompts/company/research-verification.md)和[报告写作](prompts/research-writing.md)。港美股另读[跨市场补充](prompts/company/cross-market.md) |
| 公司研究派发 | [单公司任务简报](prompts/company/research-task-brief.md) |
| 登记研究结果或修改网页 | [现行研究展示标准](research/standards/README.md) |
| 模型、输入与复算 | [研究文件与模型交付](docs/research-artifacts.md) |
| 行业、宏观与市场 | 按主题阅读[行业研究](prompts/industry-research.md)或[宏观研究](prompts/macro-research.md)，遵守[写作规范](prompts/research-writing.md)和[发布规则](research/README.md) |

## 数据与写入

- 分市场研究状态和队列分别在 `coverage/{cn-a|hk|us}/research_state.jsonl` 和同目录的 `research_queue.jsonl`。证券是否活跃、最近研究结论、当前任务分别记录。
- 质量筛选只更新本市场的 `screening/{cn-a|hk|us}/value-quality/pool.json`。用 `quality-pool` 维护成员及分层，`current.md` 由它生成。入池依据是竞争优势、普通股现金、反证与公开来源。池内不存估值、交易信息、任务或报告指针。
- 财报季按当时的动态池及实际披露排期。用户明确要求重写时才重开已有周期。公司与同一发行人的 A/H 证券在同一时刻只领取一项任务。每家公司使用独立上下文，由一名研究者完成研究和必要返工。
- 协调器验收完整正文与结构化候选后，通过 `research complete` 一次写入报告、最新状态和当期标准。研究者不直接改共享 JSONL。双方遵循同一研究规范。
- 公司报告保存在 `research/companies/{CN|HK|US}/{ticker}/reports/YYYY-{FY|Q1|H1|Q3}.md`。同周期覆盖，跨周期新增。`basis_report_path` 和 `report_period` 同步绑定最新完成周期。港美股使用发行人财年，保留实际财务期末、披露日、来源及证券币种和单位。
- 行业与宏观按主题和重要发布日期保存。发布入口是 `research/publications.json`，其中区分报告与方法参考。中国行业分类只维护 `research/industries/catalog.json`。日常观察遵循[执行规范](prompts/daily-market-observation.md)，结果在仓库外使用。

## 研究与展示

公司研究先形成长期商业判断，再用财务、资本和普通股权益模型检验。事实有公开出处，预测交代依据、范围及模型后果。价值含义以主提示词的[价值定义](prompts/company/standard-deep-research.md#价值定义)为准。区分长期拥有价值、价格吸引力与可论证的错价。

正式结论为 `covered` 或 `ignore`，均须有自足的完整报告。复盘前次关键假设，按本期资料重新形成判断。每次提交非空 `return_model_note`，可靠模型给出五年每股分配和独立终值，无法可靠建模时留空并说明原因。现价及派生 IRR 只在展示层计算。公司研究不输出仓位、买入线、价格触发或交易授权。

网页默认展示动态重点池最新周期中符合兼容标准的结果。历史周期按各自资料截止阅读，不加载现价或最新摘要。行业报告解释需求、供给、库存、利润和现金的传导，宏观指标注明公式、方向、单位、样本、窗口及修订版本。报告和界面直接面向独立读者，呈现判断、证据和必要的口径说明。

## 验证

- 修改共享状态后执行 `python -m trading_os --market <市场> validate`。修改质量池后执行对应市场的 `quality-pool validate`。
- 模型复算使用当前源码和必要输入。报告、计算代码、必要数据及简明结果进入 Git。下载缓存、候选稿、全量轨迹和批次进度保存在忽略的工作目录。纯研究修改按实际影响验证。
- 网页与导出修改须验证研究状态，执行 `node dashboard/scripts/report-standards.mjs validate`，并在 `dashboard/` 运行测试、类型检查和浏览器隔离测试。只报告实际执行的检查。

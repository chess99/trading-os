# 历史与退役资产归档说明

本目录保存已完成结构调整、退出活跃研究主线但仍需保留可追溯记录的历史文件。常规研究、质量池与展示构建不读取本目录内容。

## 目录结构

### 1. `legacy-2026-q1/`

- **内容**：2026 年 7 月第一轮全市场批量扫描产生的早期 `2026-Q1.md` 公司报告（共 5,097 份）。
- **移出原因**：该批早期全市场批量稿已在 `docs/reviews/2026-10-23-historical-reliability/报告正文.txt` 中复盘定位了大量口径与估值问题，且在 `coverage/cn-a/research_state.jsonl` 中已不再作为 `basis_report_path` 依据。将其移出活跃 `research/companies/` 目录，可避免低频精品研报库被海量历史批量草稿稀释。
- **保留边界**：仍在 `coverage/cn-a/research_state.jsonl` 中作为 `basis_report_path` 引用的 444 份 `2026-Q1.md` 保留在原位，确保状态校验与历史读取链路完整不断裂。

### 2. `retired-us-single-stocks/`

- **内容**：原 `screening/us/value-quality/` 美股个股质量池（106 家）及原 `coverage/us/` 美股个股覆盖队列与状态（101 条 `unseen`，0 篇报告）。
- **移出原因**：投资者的实际交易权限为 **A 股全板块 + 港股（港股通通道）**，不具备美股个股直接交易权限；美股投资通过国内场内可交易的美股宽基 QDII ETF（标普 500、纳斯达克 100）完成。
- **替代体系**：
  - 美股宽基与国内 QDII 配置框架见 [research/macro/reference/us-broad-etf-qdii.md](../research/macro/reference/us-broad-etf-qdii.md) 与 [research/macro/us-broad-etf/qdii-catalog.json](../research/macro/us-broad-etf/qdii-catalog.json)；
  - 原美股池沉淀出的全球产业链标杆企业见 [research/benchmarks/global-leaders.json](../research/benchmarks/global-leaders.json)，供 A 股与港股行业及成长天花板对标使用。

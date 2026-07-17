# 存储延伸行业 75 家公司复核实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 2026-07-17 收盘价和最新公开信息复核存储/HBM、锂资源、工业模拟/MCU、OLED、硅料相关 75 家 A 股公司，给出当前可买性、合理价、评级与理由。

**Architecture:** 每家公司由独立 agent 读取历史 `latest_report`，联网核验 2026-07-17 收盘价及历史报告后新增公告，生成不可变 follow-up 并更新 `meta.json`。主 agent 统一验证、对账、重建生成文件，并产出横向综合报告。

**Tech Stack:** Markdown、JSON、Trading OS CLI、web-access、Git。

## Global Constraints

- 公司研究报告主语言为中文。
- 每家公司一个独立 agent；agent 只修改自己的公司目录，不修改共享生成文件、不提交。
- 必须先读历史 `latest_report`，新建 `reports/2026-07-17-memory-cycle-followup.md`，不得覆盖历史报告。
- 当前价统一为 2026-07-17 收盘价；若来源时间不是收盘后，必须明确标注时间和局限。
- 股价下跌本身不改变合理价值；只有新增基本面、资本结构或公司行动证据才调整估值区间。
- 更新 `meta.json` 后执行 `python -m trading_os company validate <company-dir>`。
- 主 agent 只提交本批次文件，保留用户和其他任务的并行修改。

---

### Task 1: 建立范围与行情口径

**Files:**
- Create: `coverage/cn-a/runs/2026-07-17-memory-related-companies-review.md`

- [x] **Step 1: 锁定公司池**

公司池为 `2026-07-12-memory-cycle-next-opportunities.md` 的 51 家与 `2026-07-12-related-companies-completed-review.md` 的 24 家，合计 75 家，无重复。

- [x] **Step 2: 核验交易日**

2026-07-17 19:00 后执行，采用 2026-07-17 收盘价。

### Task 2: 每家公司独立复核

**Files:**
- Create: `research/companies/CN/{ticker}/reports/2026-07-17-memory-cycle-followup.md`
- Modify: `research/companies/CN/{ticker}/meta.json`

- [x] **Step 1: 读取旧报告和元数据**

读取 `meta.json.latest_report`、合理价值、买入区、仓位计划和待验证条件。

- [x] **Step 2: 联网核验**

核验 2026-07-17 收盘价，并检查旧报告研究日之后的公司公告、业绩预告、重大交易、回购减持、监管事项或行业数据；一手来源优先。

- [x] **Step 3: 形成新判断**

明确列出：现价、合理价值、买入区、当前评级、是否值得买、最大仓位、关键理由、失效条件。没有基本面新增证据时沿用旧估值，不因单日涨跌机械重估。

- [x] **Step 4: 写入并校验**

新建 follow-up、更新 `meta.json`，运行公司校验并返回结果。

### Task 3: 全量验收与综合报告

**Files:**
- Create: `research/themes/2026-07-17-memory-related-75-company-review.md`
- Modify: `coverage/cn-a/runs/2026-07-17-memory-related-companies-review.md`

- [x] **Step 1: 验证 75 家资产**

对 75 个目录逐一运行 `python -m trading_os company validate <company-dir>`，要求 75/75 通过。

- [x] **Step 2: 横向排序**

按“现价进入买入区 + 基本面确认度 + 资产负债表风险 + 估值上行空间”排序，区分可以买、接近可买、继续观察、不能买。

- [x] **Step 3: 输出综合报告**

综合报告必须覆盖 75 家的现价、合理价、买入区、评级和一句话理由，并单独解释评级变化公司。

### Task 4: 生成文件、coverage 与提交

- [x] **Step 1: coverage 对账**

运行 `python -m trading_os coverage validate` 和 `python -m trading_os coverage reconcile --check`；只有确认 drift 属于本批次才执行 `--apply`。

- [x] **Step 2: 重建**

运行 `python -m trading_os index rebuild`、`python -m trading_os schedule build`、`python -m trading_os alerts build`。

- [x] **Step 3: 提交**

只暂存 75 份 follow-up、75 个 `meta.json`、批次记录、综合报告及本批次可归因的生成文件；用 `git diff --staged` 审查后提交。

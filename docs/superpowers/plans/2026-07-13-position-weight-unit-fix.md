# 公司仓位单位修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复公司研究元数据中把百分数直接写入 `max_weight` 的单位错误，解除共享生成文件重建阻塞。

**Architecture:** 以各公司 `latest_report` 的明确仓位文字为唯一修正依据，将组合绝对仓位从百分数换算为 0—1 小数。对仅表达“目标仓位完成度”的公司不推断组合绝对仓位，只记录为后续研究口径问题。

**Tech Stack:** JSON、PowerShell、Trading OS CLI、Git。

## Global Constraints

- 不覆盖历史研究报告，只修改可变的 `meta.json`。
- 保留工作区中用户和其他任务的未提交内容。
- 生成文件可以重建验证，但提交时只暂存本次能够归因的文件。
- 当前分支直接执行，不切换分支。

---

### Task 1: 复现仓位单位错误

**Files:**
- Read: `research/companies/CN/{000599,001296,002188,002316,002342,301656}/meta.json`
- Read: 上述公司的 `latest_report`

- [x] **Step 1: 运行青岛双星严格校验**

Run: `python -m trading_os company validate research/companies/CN/000599 --strict`

Expected: FAIL，错误包含 `position_plan max_weight must be between 0 and 1`。

- [x] **Step 2: 运行语义单位断言**

检查 6 家目标公司的 `position_plan.max_weight` 是否存在 `>= 0.25` 的非零值。

Expected: FAIL，并列出与原报告中 `0.25%`—`3%` 不一致的数值。

### Task 2: 修正有报告证据的元数据

**Files:**
- Modify: `research/companies/CN/000599/meta.json`
- Modify: `research/companies/CN/001296/meta.json`
- Modify: `research/companies/CN/002188/meta.json`
- Modify: `research/companies/CN/002316/meta.json`
- Modify: `research/companies/CN/002342/meta.json`
- Modify: `research/companies/CN/301656/meta.json`

- [x] **Step 1: 换算百分数**

将报告中的 `0.25%`、`0.5%`、`1%`、`2%`、`3%` 分别写为 `0.0025`、`0.005`、`0.01`、`0.02`、`0.03`。

- [x] **Step 2: 检查差异**

Run: `git diff -- research/companies/CN/000599/meta.json research/companies/CN/001296/meta.json research/companies/CN/002188/meta.json research/companies/CN/002316/meta.json research/companies/CN/002342/meta.json research/companies/CN/301656/meta.json`

Expected: 只有 `max_weight` 数值变化。

### Task 3: 校验、重建和提交

**Files:**
- Verify: 6 家公司的 `meta.json` 与全库公司资产
- Modify: `research/companies/CN/600801/meta.json`
- Modify: `research/companies/CN/603228/meta.json`
- Modify: `research/companies/CN/600673/meta.json`
- Modify: `research/companies/CN/603268/meta.json`
- Rebuild: `research/index.json`、`automation/review_schedule.json`、`automation/price_alerts.json`

- [x] **Step 1: 校验 6 家公司**

Run: 对 6 个公司目录逐一执行 `python -m trading_os company validate <dir>`。

Expected: 6/6 返回 `ok: true`。旧版扩展字段和历史报告标题不在本次最小修复范围内。

- [x] **Step 2: 补齐已跟踪公司的规范论点字段**

若全局重建继续暴露已跟踪公司缺少 `current_thesis`，仅从其 `latest_report` 结论提炼并补入，不修改历史报告，不处理未提交的其他任务目录。

- [x] **Step 3: 运行仓位语义断言**

Expected: 6 家目标公司的非零 `max_weight` 均小于 `0.25`。

- [x] **Step 4: 重建生成文件**

Run: `python -m trading_os index rebuild`、`python -m trading_os schedule build`、`python -m trading_os alerts build`。

Expected: 三条命令均退出码 0。

若隔离重建暴露已跟踪 `report_history` 指向不存在的报告，先用目录实存文件和 Git 历史确认正确路径，再只修正引用，不覆盖报告。

若 `review_triggers` 混入 schema 不支持的无日期事件，保留已有日期复核项并删除不兼容事件项；事件逻辑仍保留在不可变报告正文中。

- [x] **Step 5: 只暂存本次文件并提交**

暂存本计划和 10 个 `meta.json`；用 `git diff --staged` 确认不含其他任务内容后提交。

# 研究进度收口实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 安全校准覆盖队列与实际公司资产，恢复生成文件一致性，并把严格校验调整为按研究类型区分的错误与警告。

**Architecture:** 在 `coverage_store.py` 中增加纯计算的对账函数与显式写入入口，CLI 仅负责参数互斥、输出和退出码；公司校验把严格发现拆成阻塞问题与审计警告，基础校验保持不变。最终以公司资产为研究结果事实来源，队列作为可对账的工作状态，生成文件继续由已通过基础校验的公司元数据派生。

**Tech Stack:** Python 3.11+、argparse、pytest、JSON/JSONL、现有 `trading_os.research_assets` 模块。

## Global Constraints

- 直接在当前需求分支开发，不切分支。
- 文档主语言使用中文。
- 不覆盖历史研究报告，只允许修复可变的 `meta.json`。
- 不暂存或提交其他 agent 的报告、来源文件或临时文件。
- 最终提交前运行验证和生成文件重建，并用隔离 Git 索引确认提交范围。

---

### Task 1: 覆盖队列对账核心

**Files:**
- Modify: `src/trading_os/research_assets/coverage_store.py`
- Test: `tests/test_coverage_store.py`

**Interfaces:**
- Consumes: `read_jsonl()`、`write_jsonl()`、`validate_company_dir()` 和队列记录中的 `target_company_dir`。
- Produces: `reconcile_research_queue(root: str | Path, research_root: str | Path, *, apply: bool = False) -> dict[str, Any]`，返回 `change_count`、`changes`、`blocked_count`、`blocked` 和 `applied`。

- [ ] **Step 1: 写出待完成资产、人工状态、无效资产和幂等性的失败测试**

  在临时目录创建有效公司资产与队列记录，断言 dry-run 只提出 `pending|running|failed -> completed`，保留 `needs_review`，并且无效资产进入 `blocked`。

- [ ] **Step 2: 运行核心测试并确认 RED**

  Run: `python -m pytest tests/test_coverage_store.py -q`

  Expected: FAIL，原因是 `reconcile_research_queue` 尚不存在。

- [ ] **Step 3: 实现最小纯计算和显式写入逻辑**

  对每个允许转换的队列项解析公司目录，调用基础 `validate_company_dir()`；成功时复制原记录并只更新 `status`、`result_path`、`failure_reason`、必要的 `finished_at` 和 `next_action`。只有 `apply=True` 且存在变化时调用一次 `write_jsonl()`。

- [ ] **Step 4: 运行核心测试并确认 GREEN**

  Run: `python -m pytest tests/test_coverage_store.py -q`

  Expected: PASS。

### Task 2: 对账 CLI 与退出码

**Files:**
- Modify: `src/trading_os/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `reconcile_research_queue()`。
- Produces: `trading_os coverage reconcile (--check|--apply) [--root PATH] [--research-root PATH]`。

- [ ] **Step 1: 写出 check、apply 和参数互斥的失败测试**

  `--check` 有漂移时输出 JSON 且返回 1，不写队列；无漂移时返回 0。`--apply` 写入并返回 0。未指定或同时指定两种模式时由 argparse 返回 2。

- [ ] **Step 2: 运行 CLI 测试并确认 RED**

  Run: `python -m pytest tests/test_cli.py -q`

  Expected: FAIL，原因是 `coverage reconcile` 子命令尚不存在。

- [ ] **Step 3: 实现 argparse 子命令和命令处理函数**

  使用 mutually exclusive group 且 `required=True`；`--research-root` 默认 `research`。输出核心函数返回的 JSON；check 模式用 `change_count > 0 or blocked_count > 0` 决定退出码。

- [ ] **Step 4: 运行 CLI 测试并确认 GREEN**

  Run: `python -m pytest tests/test_cli.py -q`

  Expected: PASS。

### Task 3: 严格校验错误与警告分层

**Files:**
- Modify: `src/trading_os/research_assets/company.py`
- Test: `tests/test_company_assets.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: 报告头部的日期、研究类型和二级标题。
- Produces: `_strict_company_findings(company_dir, meta) -> tuple[list[str], list[str]]`；`validate_company_dir(strict=True)` 只因第一组问题失败；`audit_research_assets()` 新增 `warning_count` 和 `warnings`。

- [ ] **Step 1: 把额外元数据、标题和分析师差异改写成预期警告的失败测试**

  断言这些差异不再使 `validate_company_dir(strict=True)` 失败，但在 audit 的 `warnings` 中可见。

- [ ] **Step 2: 写出按类型章节校验的失败测试**

  保留 initial 完整章节要求；构造 followup 报告，要求“上一轮判断复盘、新信息、判断变化、跟踪触发器、风险、来源”，并证明它不需要重复业务理解、行业格局和财务质量。缺少日期、类型或对应核心章节仍应严格失败。

- [ ] **Step 3: 运行公司校验测试并确认 RED**

  Run: `python -m pytest tests/test_company_assets.py tests/test_cli.py -q`

  Expected: FAIL，现有实现仍把警告当错误且不区分研究类型。

- [ ] **Step 4: 实现 findings 分层和类型化章节集合**

  将额外字段、标题和分析师问题放入 warnings；日期、可识别研究类型和对应章节放入 issues。审计对每家公司分别累计两组发现，同时保留现有额外字段与分析师统计。

- [ ] **Step 5: 运行公司校验与 CLI 测试并确认 GREEN**

  Run: `python -m pytest tests/test_company_assets.py tests/test_cli.py -q`

  Expected: PASS。

### Task 4: 工作流文档与阻塞资产修复

**Files:**
- Modify: `AGENTS.md`
- Modify: `playbooks/company-research.md`
- Modify only if audit still reports it: `research/companies/CN/002052/meta.json`

**Interfaces:**
- Consumes: 新增的 `coverage reconcile` CLI。
- Produces: 研究完成后同步队列、批次收尾对账的明确规则；所有公司通过基础校验。

- [ ] **Step 1: 在 agent 规则和公司研究 playbook 中加入队列同步与收尾命令**

  明确单家公司完成后应更新对应队列状态；并行批次结束运行 `coverage reconcile --check`，有预期漂移时审阅后执行 `--apply`。

- [ ] **Step 2: 重新运行资产审计并定位基础阻塞项**

  Run: `python -m trading_os company audit --research-root research`

  Expected: 输出 `validation_errors` 的当前真实列表。

- [ ] **Step 3: 只修复仍存在的可变元数据错误**

  若 `CN:002052` 仍缺少 `current_thesis`，从其最新不可变报告的结论提炼非空中文论点写入 `meta.json`；若并行 agent 已修复，则不改该文件。对其他新出现的基础错误采用同一原则，禁止修改报告。

- [ ] **Step 4: 验证基础资产全部有效**

  Run: `python -m pytest tests/test_asset_index.py::test_repository_company_assets_validate -q`

  Expected: PASS。

### Task 5: 最终对账、生成文件与完整验证

**Files:**
- Modify: `coverage/cn-a/research_queue.jsonl`
- Regenerate: `research/index.json`
- Regenerate: `automation/review_schedule.json`
- Regenerate: `automation/price_alerts.json`

**Interfaces:**
- Consumes: 所有已通过基础校验的公司资产和对账命令。
- Produces: 无队列漂移且与当前公司资产一致的四个状态/生成文件。

- [ ] **Step 1: 确认并行研究写入已经稳定**

  连续两次读取 HEAD、公司 `meta.json` 数量和队列文件哈希；若仍变化则等待当前批次完成，不覆盖中间态。

- [ ] **Step 2: 应用对账并验证幂等**

  Run: `python -m trading_os coverage reconcile --apply`

  Expected: 返回 0 并列出已应用变化。

  Run: `python -m trading_os coverage reconcile --check`

  Expected: 返回 0、`change_count` 为 0、`blocked_count` 为 0。

- [ ] **Step 3: 验证覆盖层并重建全部生成文件**

  Run: `python -m trading_os coverage validate`

  Run: `python -m trading_os index rebuild`

  Run: `python -m trading_os schedule build`

  Run: `python -m trading_os alerts build`

  Expected: 四个命令均返回 0。

- [ ] **Step 4: 运行完整测试与差异检查**

  Run: `python -m pytest -q`

  Run: `git diff --check`

  Expected: 全部测试通过，差异检查无输出。

- [ ] **Step 5: 用隔离索引暂存并审查本次文件**

  只暂存代码、测试、必要文档、明确修复的 meta、队列和三个生成文件。运行 `git diff --staged --name-status`、`git diff --staged --check` 和 `git diff --staged`，确认没有其他 agent 的报告、来源或临时文件。

- [ ] **Step 6: 提交完整收口迭代**

  Commit message: `fix: 校准研究进度与资产校验`

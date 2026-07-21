# 独立承保复核与模型组合决策系统实施计划

> 依据：`docs/superpowers/specs/2026-07-21-independent-underwriting-review-design.md`

**目标：** 用一套半盲、可封存、可复算、可恢复的承保复核流水线替换当前“初始报告直接给买入评级和仓位”的旧模型，并支持行业批次与全 A 股漏斗的最终模型组合决策。

**总体架构：** 公司研究资产、批次运行状态和组合决策彻底分层。公司目录保存不可变报告、证据和承保封存产物；`automation/runs/` 保存可恢复状态；`research/batches/` 保存不可变批次结果；`policies/` 保存带版本的承保和组合规则。CLI 只调用领域服务，不在命令处理函数中实现业务规则。

**技术约束：** Python 3.10+、标准库、pytest、ruff；原子文件替换；SHA-256；JSON/JSONL/Markdown。无需维护旧 CLI 或旧 Schema 的运行时兼容性。

## 实施原则

- 每个行为先写失败测试，再写最小实现，再重构。
- 每完成一个任务，运行该任务的定向测试并形成独立提交。
- 不覆盖历史 Markdown 报告。
- 迁移前保留旧元数据快照和文件哈希，不编造缺失事实。
- 迁移完成前不宣布新系统可用；迁移完成后不保留双轨入口。
- 当前工作区有大量其他任务改动。每次只暂存本任务文件，并用路径限定提交及提交树反查避免夹带。

---

## 任务 1：建立新版领域常量、策略文件和 Schema

**新增文件：**

- `src/trading_os/research_assets/models.py`
- `templates/company-meta-v2.schema.json`
- `templates/review-run.schema.json`
- `templates/claim-packet.schema.json`
- `templates/blind-assessment.schema.json`
- `templates/portfolio.schema.json`
- `policies/underwriting.json`
- `policies/portfolio.json`
- `policies/industries/memory.json`
- `policies/industries/manufacturing.json`
- `policies/industries/software.json`
- `policies/industries/banking.json`
- `policies/industries/insurance.json`
- `policies/industries/resources.json`
- `tests/test_research_models_v2.py`

### 步骤

1. 写失败测试，固定以下枚举和字段：
   - 报告类型：`initial_research`、`monitoring_update`、`underwriting_review`、`challenger_review`；
   - 承保状态：`passed`、`failed`、`insufficient_evidence`、`needs_challenger`、`stale`；
   - 组合操作：`buy_now`、`buy_on_weakness`、`hold`、`reduce`、`exit`、`watch`、`reject`；
   - 来源等级、主张复核状态和批次状态。
2. 测试策略文件必须带 `schema_version`、`policy_id`、`version`、`effective_at`，且不存在未知顶层字段。
3. 测试默认组合参数与设计一致：单股 5%、行业 20%、经济风险簇 25%、前五大 25%、中等置信度 3%。
4. 实现不可变 dataclass、枚举和通用 JSON 读取/类型检查辅助函数。
5. 编写六份 JSON Schema 和默认行业适配器；行业适配器必须声明适用范围、强制证据和估值方法。

### 验证

```bash
pytest tests/test_research_models_v2.py -q
ruff check src/trading_os/research_assets/models.py tests/test_research_models_v2.py
```

预期：全部通过，无 Ruff 问题。

---

## 任务 2：重写公司资产模型和严格验证器

**修改文件：**

- `src/trading_os/research_assets/company.py`
- `src/trading_os/research_assets/__init__.py`
- `tests/test_company_assets.py`

**删除文件：**

- `templates/meta.schema.json`

### 步骤

1. 用 v2 fixture 重写公司资产测试，先固定新版 `meta.json`：
   - `schema_version: 2`；
   - identity、research、reports、underwriting、valuation、triggers 分区；
   - 不允许 `current_rating`、`position_plan` 和最终组合操作字段；
   - 报告历史项必须含路径、类型、日期和 SHA-256；
   - 最新报告索引必须引用历史项；
   - `underwriting` 与估值快照允许为空或明确 `requires_rebaseline`。
2. 为四类报告分别定义必要章节和前置元数据验证。
3. 测试旧报告可以作为 `historical_artifacts` 保留，但运行时不解析其正文，也不能被设为新的 v2 承保报告。
4. 测试报告路径逃逸、哈希不一致、类型错配、时间倒序、非法价格区间和布尔数值全部失败。
5. 重写 `validate_company_dir`，删除旧评级、仓位和旧 report type 逻辑。
6. 将旧 `audit_research_assets` 拆为统一 `validate_research_assets`；只返回严格资产问题，不使用“audit”暗示投资审计。

### 验证

```bash
pytest tests/test_company_assets.py -q
ruff check src/trading_os/research_assets/company.py tests/test_company_assets.py
```

预期：v2 fixture 通过；旧 v1 fixture 明确失败并提示需要迁移。

---

## 任务 3：实现封存、哈希和不可变产物

**新增文件：**

- `src/trading_os/research_assets/sealing.py`
- `tests/test_sealing.py`

### 步骤

1. 写失败测试覆盖：
   - JSON 规范化序列化后哈希稳定；
   - 原子写入不会留下半文件；
   - 已封存文件禁止覆盖；
   - manifest 中的大小和哈希必须匹配；
   - 任意字节篡改都被发现；
   - 重复封存同一内容是幂等的；不同内容使用同一路径必须失败。
2. 实现 canonical JSON、SHA-256、原子写入、seal manifest 和验证函数。
3. 事件时间统一使用带时区 ISO 8601；运行时保存 UTC，报告显示时可转换为 Asia/Shanghai。

### 验证

```bash
pytest tests/test_sealing.py -q
ruff check src/trading_os/research_assets/sealing.py tests/test_sealing.py
```

---

## 任务 4：实现批次清单、任务租约和状态机

**新增文件：**

- `src/trading_os/research_assets/review_store.py`
- `tests/test_review_store.py`

### 步骤

1. 写状态转换参数化测试，允许：

```text
created
→ candidates_frozen
→ packets_ready
→ blind_reviewing
→ blind_sealed
→ revealing
→ challenging（按需）
→ company_reviews_complete
→ synthesizing
→ completed
```

2. 写非法转换测试：未冻结候选就准备主张包、未封存就揭示、未完成公司复核就综合、完成后回退状态都必须失败。
3. 写候选集合冻结测试：冻结后增删公司必须失败；显式修订产生新 `run_id` 和父批次引用。
4. 写租约测试：独占领取、到期重领、错误 owner 释放失败、重复完成幂等。
5. 写事件日志测试：只追加、严格序号、每条记录带前后状态和 actor。
6. 实现 `ReviewRunStore`，使用每任务独立原子租约文件，避免多个 agent 同时写一个大 JSON。

### 验证

```bash
pytest tests/test_review_store.py -q
ruff check src/trading_os/research_assets/review_store.py tests/test_review_store.py
```

---

## 任务 5：实现结构化主张、确定性脱敏和泄露检查

**新增文件：**

- `src/trading_os/research_assets/claims.py`
- `templates/research-claims.schema.json`
- `tests/test_claims.py`

### 步骤

1. 定义初始研究必须产出的结构化主张：事实、业务假设、行业假设、投资假设、验证指标、证伪条件、来源和决策字段。
2. 写脱敏失败测试，确保输出中没有：
   - 旧评级和操作；
   - 旧合理价值、目标价、买入区和减持区；
   - 旧仓位；
   - 直接泄露上述答案的自由文本。
3. 对金额、百分比和估值倍数采用字段级来源控制，不用不可靠的全文正则粗暴删除所有数字。
4. 实现 `build_claim_packet`：只允许白名单字段进入盲态包。
5. 实现独立 `scan_claim_packet_for_leaks`，在状态机进入 `packets_ready` 前强制执行。
6. 写回归测试，使用旧报告中把评级和目标价写进投资逻辑段落的恶意 fixture，验证泄露会阻断流程。

### 验证

```bash
pytest tests/test_claims.py -q
ruff check src/trading_os/research_assets/claims.py tests/test_claims.py
```

---

## 任务 6：实现证据账本和数据新鲜度验证

**新增文件：**

- `src/trading_os/research_assets/evidence.py`
- `tests/test_evidence.py`

### 步骤

1. 写证据项 Schema 测试：`claim_id`、值、期间、原始/调整口径、来源等级、定位、获取时间、交叉验证和复核结果。
2. 写来源等级测试：关键财务事实没有 S1 时失败；S4 单独支持购买理由时失败。
3. 写新鲜度测试：
   - 行情必须来自最近一个已完成交易日；
   - 强周期价格和库存默认 30 日；
   - 一般行业数据默认 90 日；
   - 新财报或重大公告使旧证据状态变为 `stale`。
4. 写股本口径测试：增发、回购、可转债和送转未处理时阻断每股估值。
5. 实现证据账本验证和结构化问题列表；不要把警告混成通过状态。

### 验证

```bash
pytest tests/test_evidence.py -q
ruff check src/trading_os/research_assets/evidence.py tests/test_evidence.py
```

---

## 任务 7：实现承保质量闸门和挑战升级

**新增文件：**

- `src/trading_os/research_assets/underwriting.py`
- `tests/test_underwriting.py`

### 步骤

1. 建立盲态评估 fixture，包含盈利质量桥、现金流桥、正常化盈利桥、三情景估值、两种估值方法、敏感性和三条反方证据。
2. 写自动阻断测试：
   - 单季利润乘四；
   - 周期峰值利润直接估值；
   - 非经常性收益、净债务、少数股东权益或稀释未处理；
   - 利润现金流背离未解释；
   - 估值不可复算；
   - 单点目标价；
   - 关键证据过期或缺失。
3. 写回报门槛和安全边际测试：

```text
max(12%，中国 10 年期国债收益率 + 8%，公司权益资本成本)
```

4. 写挑战升级测试：新旧价值中枢差异超过 30%、两种估值差异超过 40%、核心论点被推翻、治理疑点、周期位置不明或拟进入前五大。
5. 实现 `evaluate_underwriting`，输出结构化硬失败、挑战触发器、承保状态和可复算估值快照。
6. 实现揭示差异审计验证，确保每个旧主张都有 `confirmed/weakened/disproven/untested`。

### 验证

```bash
pytest tests/test_underwriting.py -q
ruff check src/trading_os/research_assets/underwriting.py tests/test_underwriting.py
```

---

## 任务 8：实现组合综合、风险簇和仓位约束

**新增文件：**

- `src/trading_os/research_assets/portfolio.py`
- `tests/test_portfolio.py`

### 步骤

1. 写 `buy_now` 五条件测试：承保通过、数据有效、价格进入买入区、横向入选、风险预算允许，缺一即失败。
2. 写操作状态测试，区分 `buy_on_weakness`、`watch`、`reject`、`hold`、`reduce` 和 `exit`。
3. 写经济风险簇测试：不同申万行业但相同存储周期暴露仍受同一 25% 上限约束。
4. 写仓位测试：单股 5%、行业 20%、前五大 25%、中等置信度 3%、低置信度 0%。
5. 写风险预算公式测试：建议仓位取单股、行业/风险簇余额、单笔允许损失和置信度四者最小值。
6. 写现金测试：候选不足或约束无法分配时保留现金，不能强行满仓。
7. 写同业择优和排除测试：每个落选公司必须有结构化原因，不能只输出赢家。
8. 实现确定性的组合构建器和结构化 `portfolio.json`；文字综合由 agent 根据该结果生成，不能反向修改机器约束结果。

### 验证

```bash
pytest tests/test_portfolio.py -q
ruff check src/trading_os/research_assets/portfolio.py tests/test_portfolio.py
```

---

## 任务 9：重构 CLI 为 `assets` 和 `review` 命名空间

**修改文件：**

- `src/trading_os/cli.py`
- `tests/test_cli.py`

### 步骤

1. 先写 CLI 解析和 JSON 输出测试：

```bash
python -m trading_os assets validate
python -m trading_os review create ...
python -m trading_os review prepare <run-id>
python -m trading_os review status <run-id>
python -m trading_os review validate <run-id> --strict
python -m trading_os review synthesize <run-id> --quotes <snapshot>
python -m trading_os review report <run-id>
```

2. 测试旧 `company audit` 和旧 `company validate` 不再出现在帮助中。
3. 将命令处理函数限制为参数解析、领域调用和 JSON 输出；业务规则留在领域模块。
4. `review run` 顺序调用各阶段，但状态机仍会阻止跳过封存、验证和挑战。
5. 所有失败写 stderr、返回非零码，并包含稳定错误代码供自动化脚本判断。

### 验证

```bash
pytest tests/test_cli.py -q
ruff check src/trading_os/cli.py tests/test_cli.py
python -m trading_os --help
python -m trading_os review --help
```

---

## 任务 10：替换批量调度器和 worker prompt

**新增文件：**

- `automation/scripts/review_dispatch.py`
- `automation/scripts/_underwriting_blind_prompt.md`
- `automation/scripts/_underwriting_reveal_prompt.md`
- `automation/scripts/_challenger_prompt.md`
- `automation/scripts/_portfolio_synthesis_prompt.md`
- `automation/scripts/build_review_prompt.py`
- `tests/test_review_dispatch.py`

**删除文件：**

- `automation/scripts/batch_research.py`
- `automation/scripts/build_worker_prompt.py`
- `automation/scripts/_worker_prompt.md`

### 步骤

1. 写 prompt 渲染测试，确保盲态 prompt 只读取主张包和允许来源，不出现旧报告路径、评级、估值或仓位。
2. 写一家公司一个任务、不同公司并行、同一公司阶段串行的调度测试。
3. 写 agent 租约、超时、失败隔离、幂等重领和断点恢复测试。
4. 写挑战 agent 权限测试：不得收到旧报告和第一份盲态评估。
5. 写综合 prompt 测试：只能在全部公司终态、严格验证通过且行情快照封存后生成。
6. 实现调度器；不要把特定供应商 CLI 写死在领域层，runner 通过适配器执行外部 agent。
7. 保留 Codex 子 agent 的纯 prompt 构建入口，使主 agent 可以按公司派发独立任务。

### 验证

```bash
pytest tests/test_review_dispatch.py -q
ruff check automation/scripts/review_dispatch.py automation/scripts/build_review_prompt.py tests/test_review_dispatch.py
```

---

## 任务 11：重写索引、计划和提醒生成件

**修改文件：**

- `src/trading_os/research_assets/index.py`
- `src/trading_os/research_assets/schedule.py`
- `src/trading_os/research_assets/alerts.py`
- `tests/test_asset_index.py`
- `tests/test_schedule_and_alerts.py`

### 步骤

1. 写失败测试，确保索引不再输出 `current_rating`、组合仓位或旧评级字段。
2. 索引输出研究覆盖、承保状态、证据截止、估值快照和失效状态。
3. 复核计划由公司触发器和结论失效条件生成。
4. 价格提醒区分：
   - 进入承保买入区，需要重新检查；
   - 价格变化超过 10%，结论自动过期；
   - 已持有公司的减持/退出观察事件来自模型组合，而非公司元数据。
5. 所有生成件使用原子写入和稳定排序。

### 验证

```bash
pytest tests/test_asset_index.py tests/test_schedule_and_alerts.py -q
ruff check src/trading_os/research_assets/index.py src/trading_os/research_assets/schedule.py src/trading_os/research_assets/alerts.py
```

---

## 任务 12：更新模板、playbook 和仓库操作说明

**新增文件：**

- `templates/initial-research-v2.md`
- `templates/underwriting-review.md`
- `templates/challenger-review.md`
- `templates/portfolio-synthesis.md`
- `playbooks/underwriting-review.md`
- `playbooks/portfolio-synthesis.md`

**修改文件：**

- `playbooks/company-research.md`
- `playbooks/followup-review.md`
- `playbooks/batch-dispatch.md`
- `playbooks/screening.md`
- `README.md`
- `AGENTS.md`
- `tests/test_templates_and_playbooks.py`
- `tests/test_coverage_protocol.py`

**删除文件：**

- `templates/company-report.md`

### 步骤

1. 写文档契约测试，固定四层漏斗、半盲两阶段、封存规则、一家公司一个 agent 和两级决策。
2. 初始研究模板必须同时产出结构化主张，不再把组合仓位写入公司元数据。
3. 承保模板必须包含证据账本、三张桥、三情景估值、反方证据、旧主张差异和自动阻断检查。
4. 综合模板必须列出当前价、悲观价值、合理价值、买入区、承保状态、最终操作、仓位以及全部落选理由。
5. README 和 AGENTS 只列新命令和新资产边界，不保留旧入口。

### 验证

```bash
pytest tests/test_templates_and_playbooks.py tests/test_coverage_protocol.py -q
```

---

## 任务 13：实现一次性迁移工具

**新增文件：**

- `src/trading_os/research_assets/migration.py`
- `tests/test_migration.py`
- `research/migrations/.gitkeep`

**修改文件：**

- `src/trading_os/cli.py`

### 步骤

1. 写 dry-run 测试：扫描所有旧公司资产，输出迁移计划，不修改文件。
2. 写旧元数据封存测试：迁移前把规范化旧 `meta.json` 和哈希写入不可变迁移快照。
3. 写转换测试：
   - 公司身份和触发器迁移；
   - 旧评级、仓位和组合字段不进入 v2 公司状态；
   - 旧 Markdown 只进入 `historical_artifacts`；
   - 缺少可靠结构化主张时状态为 `requires_rebaseline`；
   - 不伪造承保通过或有效合理价。
4. 写中断恢复测试：已迁移公司幂等跳过，失败公司记录原因，可再次运行。
5. 增加：

```bash
python -m trading_os assets migrate --dry-run
python -m trading_os assets migrate --apply --plan <migration-plan.json>
```

6. `--apply` 必须要求使用 dry-run 产生且哈希匹配的计划，防止扫描后资产发生变化仍盲目迁移。

### 验证

```bash
pytest tests/test_migration.py tests/test_cli.py -q
ruff check src/trading_os/research_assets/migration.py tests/test_migration.py
```

---

## 任务 14：端到端回归和七家公司冲突样本

**新增文件：**

- `tests/fixtures/underwriting/README.md`
- `tests/fixtures/underwriting/conflicting-seven/`
- `tests/test_underwriting_e2e.py`

### 步骤

1. 将本次七家公司涉及的“旧结论—独立复核—差异”抽象为去敏、最小化回归 fixture，不复制不必要的大型 PDF。
2. 写端到端测试：候选冻结、主张脱敏、盲态封存、揭示、挑战、仲裁、组合综合和排除记录。
3. 至少覆盖：
   - 旧报告把半年预告误当正式业绩；
   - 峰值利润年化；
   - 利润和现金流背离；
   - 新旧估值相差超过 30%；
   - 同一存储周期风险簇去重；
   - 公司承保通过但因价格或同业排序不能买。
4. 添加故障注入：一个 agent 超时、一个封存文件被篡改、行情过期，验证批次可恢复且不会错误进入 `buy_now`。

### 验证

```bash
pytest tests/test_underwriting_e2e.py -q
```

---

## 任务 15：执行迁移、删除旧轨道并全仓验收

**修改范围：**

- 由迁移计划列出的 `research/companies/**/meta.json`
- 新增 `research/migrations/{MIGRATION_ID}/**`
- 生成 `research/index.json`
- 生成 `automation/review_schedule.json`
- 生成 `automation/price_alerts.json`

### 步骤

1. 确认没有其他 agent 正在写公司资产；冻结旧调度器。
2. 运行迁移 dry-run，人工检查统计：总公司数、可迁移数、需要重新基线数、损坏资产数和计划哈希。
3. 在工作区无重叠写入的前提下执行迁移。
4. 删除所有旧运行代码、旧 Schema、旧模板和旧命令残留；用 `rg` 搜索：

```bash
rg "current_rating|position_plan|company audit|研究类型：initial|task_type.*followup_review" src tests templates playbooks automation README.md AGENTS.md
```

预期：除迁移测试和历史说明外无命中。

5. 严格验证全部公司、coverage、批次和政策。
6. 重建索引、复核计划和价格提醒。
7. 运行全套测试和静态检查。

### 最终验证

```bash
pytest -q
ruff check src automation/scripts tests
python -m trading_os assets validate
python -m trading_os coverage validate
python -m trading_os coverage reconcile --check
python -m trading_os index rebuild
python -m trading_os schedule build
python -m trading_os alerts build
git diff --check
```

完成条件：

- 全部命令成功；
- 全部公司要么通过 v2 验证，要么以结构化 `requires_rebaseline` 状态存在；
- 旧运行入口已删除；
- 生成件可重复构建且没有漂移；
- 工作区中本任务变更和其他并行变更可以清晰区分；
- 每个提交只包含对应任务文件。

## 实施提交序列

建议每个任务形成一个独立提交：

1. `feat: define underwriting v2 models and policies`
2. `refactor: replace company asset schema with v2`
3. `feat: add immutable artifact sealing`
4. `feat: add resumable review run state machine`
5. `feat: add deterministic blind claim packets`
6. `feat: validate underwriting evidence freshness`
7. `feat: enforce underwriting gates and challenges`
8. `feat: synthesize constrained model portfolios`
9. `refactor: replace research CLI with review workflow`
10. `refactor: replace batch research dispatcher`
11. `refactor: rebuild research generated assets for v2`
12. `docs: replace research templates and playbooks`
13. `feat: add one-shot research asset migration`
14. `test: add underwriting conflict end-to-end coverage`
15. `chore: migrate research assets to underwriting v2`

每次提交前必须运行对应验证、只暂存本任务文件，并检查提交树没有夹带其他任务或其他 agent 的修改。

# 全 A 股持续研究 Goal 启动提示词

> 用法：在新的 Codex 对话中引用本文件，并补充本次参数（如有）。本文件负责长期任务编排；研究口径、容量和闸门仍以仓库内 `AGENTS.md`、`playbooks/` 与 `policies/` 的当前版本为事实源。

请创建并持续执行一个 Goal，不设置 `token_budget`，除非我在本次调用中另有明确指定。目标是：以启动时冻结的普通 A 股范围和信息截止时间为边界，让范围内每家公司先经独立 Agent 快速甄别，再把有限研究预算分配给最值得继续看的公司；完成必要的正式画像、范围研究、深研、独立承保和组合综合，并使公司时间线、coverage、触发器和派生资产全部通过验证。

## 本次参数

- `mode`：`auto`（默认）、`baseline` 或 `incremental`。
- `run_id`：未指定时，以启动日期和用途生成稳定 ID。
- `scope_cutoff`：未指定时，使用 Goal 创建时的带时区时间；此后发生的新事件留给下一轮。
- `universe_ref`：未指定时，冻结当时仓库中可验证的普通 A 股 universe，并记录来源、哈希、纳入、排除和异常。
- `triage_batch_size`：未指定时读取当前 research-allocation policy 的 `triage_administrative_batch_size`；它只是行政分批上限，不是投资筛选容量。

`auto` 模式同时建立两条逻辑 lane：

1. `baseline`：处理冻结范围内缺少当前 rapid-triage 协议有效终态的全部公司，包括 legacy completed/watch 状态和缺失 queue 的范围成员；`requires_rebaseline` 只是一个 intake 提示；
2. `incremental`：处理 `scope_cutoff` 以前已经实际命中的财报、公告、价格、论点失效或证据过期事件。

两条 lane 可以交错推进，但同一 symbol 同时只能有一个可变任务所有者。第一阶段必须封存 lane arbitration 契约，定义新事件如何合并到活动研究、何时抢占、何时延后及何时消费 hit。不得把触发器定义本身冒充已经发生的事件。截止时间之后的新触发写入下一轮输入，不得令当前 Goal 无限扩张。

## 不可违背的原则

1. 全覆盖、先看后筛。每个纳入范围的普通 A 股都必须由 Agent 至少快速看一眼，或有经验证的证券身份硬排除；因子排名、PE、市值、流动性、当期亏损或行业偏好不得决定谁有资格被看。
2. 机器只做材料准备、触发检测、行政排序、冻结、调度、封存、校验和状态回写；业务理解、正常化盈利、价格隐含预期、反证与继续研究价值必须由 Agent 判断。
3. 一家公司一个独立单公司 Agent；不得让同一个子 Agent 同时研究多家公司。跨公司 allocation、质量统计和组合 Agent 是独立角色，只读取已封存的单公司产物，不代写单公司研究。
4. 同层完整后再晋级。rapid triage 结果全部封存后，必须由未参与单公司甄别的独立跨公司 Agent 显式分配下一层预算；程序不得按数值分数、旧 priority、完成先后或 lens 数量自动晋级。
5. 历史不可覆盖。每次有效快速甄别或更新都进入单公司不可变时间线；只有验证通过后才能原子更新 `meta.json` 和 coverage 队列。
6. 快速停止只是“当前不再购买更多研究信息”，不是永久贴标签。除真正硬排除外，必须记录事实理由、反方证据、未知数和可执行的重启触发器。
7. 单公司层不得输出 `buy_now`、组合操作或仓位。只有最新行情下的组合综合可以给操作与仓位。

## 启动与恢复

每次启动或续跑都执行：

1. 完整读取根 `AGENTS.md`、`playbooks/all-a-goal-execution.md`、`playbooks/research-capital-allocation.md`、`playbooks/screening.md`、`playbooks/batch-dispatch.md`、`playbooks/portfolio-synthesis.md` 和当前 policy。
2. 读取当前 Goal、Git 状态、运行中 Agent、冻结 scope、coverage、公司时间线和封存资产。保留用户及其他 Agent 的改动，不切分支，除非用户明确要求。
3. 若已有同一 `run_id`，不得重新冻结范围。验证已有 seal 后再复用，以“冻结范围减去已验证终态”重建工作清单，不能只相信队列状态。
4. 已有封存产物但队列或 `meta.json` 未回写时，使用幂等发布或 reconcile 修复；不得重做已经有效完成的公司。
5. `running` 任务只有在租约确实失效后才能释放；保留 `attempt_history`，失败后换独立 Agent 重试。
6. 机制缺陷可以先修代码、测试与文档，再恢复同一个 run；不能因此改动原始 scope 或 information cutoff。
7. 小批次完成即验证、封存、回写并提交本批自己修改的文件，确保任务可恢复。
8. 启动时先做基础设施就绪检查。若尚无全市场 scope 守恒 manifest、scope-to-queue baseline intake、正式质量抽查 policy 与封存、canonical trigger-hit ledger、lane arbitration，或 quick-profile/scoped-research 仍使用机械 score/priority 自动晋级，先建设并试运行对应的新契约；不得用现有 `companies.jsonl`、`screening.jsonl` 和队列行数大致接近来冒充范围或增量闭环已经成立，也不得让历史 `allocate-research`、`apply-allocation` 或 `profile-finalize` 替代独立 Agent 的同层全量 decisions。

## 执行阶段

### 1. 冻结范围与输入

- 冻结普通 A 股 universe、`scope_cutoff`、数据来源与哈希。
- 对冻结范围做数量守恒：`eligible + hard_excluded + exception = universe`，不得静默遗漏。
- baseline 以“缺少当前协议有效终态”计算，不按旧 queue status 计算；先把 legacy completed/watch 和缺失 queue 的 eligible 成员通过封存 intake 契约守恒物化，再调用 cohort freeze。当前 `triage-freeze` 不能单独证明这一步已经完成。
- baseline backlog 按等待时间和 symbol 等行政字段稳定分批；incremental 只按已观察触发的紧急程度、过期程度和稳定顺序分批。任何投资吸引力数据不得参与本阶段排序。
- 为每家公司准备最小差异包：旧状态、最新有效报告、截止日前新增 S1 财报/公告、近期价格、已观察触发和关键证据缺口。

### 2. 每家公司独立快速甄别

每个 Agent 在限定预算内至少回答：

- 公司靠什么赚钱，能否快速理解；
- 24—36 个月生存、强制稀释、资本结构或治理是否出现阻断项；
- 相对上一轮研究真正发生了什么变化；
- 正常化所有者收益能否粗判，依据和最大误差是什么；
- 当前价格要求市场相信什么，赔率是否至少可能成立；
- 最强反方证据是什么；
- 再投入下一小时最可能解决什么，是否足以改变组合决策；
- 若当前停止，什么财报、价格、事件、论点变化或 TTL 到期会重启研究。

快速甄别必须使用真实来源和真实 provenance。不得照抄旧结论，也不得把旧报告当作新的一手证据。完成后封存，并发布到公司不可变时间线。

### 3. 独立质量抽查

- 对硬排除和不在范围内的证券身份做 100% 校验。
- 对 `catalog`、`price_watch`、`conditional_stop`、`reassign_or_stop` 按第一阶段新增并封存的质量审计 policy 做确定性、分层、独立且尽量盲态的假阴性抽查；该 policy 必须定义样本率、稳定选样种子、错误阈值和扩样规则，不得复用旧排名 selection slot。
- 抽查 Agent 不读取原 Agent 的结论性措辞，只读取事实包和来源。重大分歧必须重开该公司；某一分层错误率超过阈值时扩大样本或重做该层。
- 抽查完成前不得封存整个 triage cycle。

### 4. 横向配置研究预算

- 同一个 cohort 的所有公司均有有效终态并完成抽查后，生成不含旧排名和机械分数的 comparison packet。
- 由未参与单公司研究的独立 allocation Agent 逐项给出 `select_quick_profile` 或 `defer`，写清预期信息价值、决定性问题、研究成本、相对机会成本和风险簇约束。
- 程序只验证全量覆盖、容量上限、风险簇约束、provenance 与禁止字段；不替 Agent 生成投资排序。
- 若还没有封存且可复核的逐公司经济风险簇，所有 selected rows 必须保守归入同一 `unclassified` 簇并受该簇上限约束；只有先建立可信分类契约和校验器，才能使用超过这一保守上限的正式画像容量。
- 未晋级公司保留快速简报和重启触发器，未来事件发生时重新竞争预算。

### 5. 更深研究与组合综合

按 playbook 继续执行：

```text
quick profile
→ scoped research
→ deep research + 结构化主张与来源
→ 半盲独立承保
→ 必要 challenger / 仲裁
→ 最新行情下的组合综合
```

每层都先封存完整 cohort，再由独立跨公司 Agent 配置下一层预算。没有合格公司时允许留空；不得为填配额降低标准。

### 6. 增量研究闭环

- 快速简报和后续研究留下的 `date/TTL` 触发器必须能进入 schedule；价格触发器必须能进入 alerts。
- `filing/event/thesis` 只有被可靠观察器或人工证据账本记录为 hit 后，才进入 incremental cohort。
- 同一 hit 必须可去重、可消费和可追溯；研究完成后不得反复入队。
- 重建索引、schedule 和 alerts，确认已完成 baseline 的 symbol 不再出现通用 `research-rebaseline`。

## 完成判定

只有同时满足以下条件，才可把 Goal 标为完成：

1. 冻结 scope 数量守恒，每个 symbol 都有有效 rapid-triage 终态或经验证的硬排除；
2. 没有本轮遗留的 pending、running、失效租约或未解释失败；
3. 每个 baseline 结果已进入公司不可变时间线，并正确清除 `requires_rebaseline`；
4. 每个非硬停止项都有 schedule/alerts 实际可消费的重启条件；
5. 独立抽查完成，重大分歧和 policy 要求的扩样全部处理；
6. 各层均满足“完整 cohort 先封存、后横向晋级”，没有完成顺序偏差；
7. 所有获得预算的候选完成相应深研、承保和必要 challenger；无合格候选时可为空；
8. 组合层使用最新行情重新计算，或明确封存“当前无可买机会”；
9. 截止时间后的事件已留给下一轮，不属于当前未完成项；
10. 全部验证通过，提交只含本 Goal 自己修改的文件。

其中 scope manifest、scope-to-queue baseline intake、质量抽查 policy 与封存、trigger-hit ledger 和 lane arbitration 是完成条件，不是可在最终报告中口头豁免的“后续优化”。若任一机制尚未建立或无法验证，只能继续执行或如实标记 Goal blocked，不能标记 complete。

至少执行当前仓库支持的以下验证；若 playbook 或 CLI 已更新，以更新后的命令为准：

```bash
python -m trading_os coverage status
python -m trading_os coverage triage-status <cycle-id>
python -m trading_os coverage profile-status <cycle-id>
python -m trading_os review status <run-id>
python -m trading_os review validate <run-id> --strict

python -m trading_os assets validate
python -m trading_os coverage validate
python -m trading_os coverage reconcile --check
python -m trading_os index rebuild
python -m trading_os schedule build
python -m trading_os alerts build

ruff check <本次涉及的 Python 文件>
python -m pytest -q
git diff --check
git diff --staged
```

## 最终交付

向用户报告冻结范围与截止时间、覆盖守恒、各层数量、抽查与分歧、承保和组合结果、未完成或证据不足事项、增量触发闭环、验证结果及提交。不得只说“跑完了”；必须给出能从封存资产和公司时间线复核的证据路径。

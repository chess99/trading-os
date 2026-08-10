# 简化研究流程

## 目标

系统先完成一次全市场基线，此后只处理新增公司、重大变化和每日收盘价格触发。初筛负责选择研究对象，不负责估值；单公司研究负责形成可持续维护的当前报告和触发条件。

核心原则：

1. 主 Agent 批量判断公司是否值得进行一次正式研究。
2. 未正式研究的公司不得设置价格触发。
3. 所有候选使用同一份 `prompts/company/standard-deep-research.md`，一家公司由一个 Agent 端到端完成。
4. 不设置研究强度等级、分钟预算、复核 Agent、承保、经理审批或跨 Agent 往返。

## 三类事实分开维护

### 证券范围

`universe_status`：

- `active`：当前属于研究范围；
- `inactive`：退市、终止上市、身份失效或移出范围。

证券身份不是投资判断。`inactive` 不得创建任务或价格监控，但历史研究保留。

首次或增量补录可使用 `universe register`。日后拿到完整上市证券快照时使用 `universe sync`：快照内证券设为 active，快照外证券设为 inactive；退出范围会取消活动任务和价格监控但不删除报告，重新进入范围时恢复 covered 监控，并重新排队此前未完成的 candidate/stale。

### 公司研究状态

`status`：

- `unseen`：尚未完成首次初筛；
- `ignore`：当前不值得投入正式研究或正式研究后不值得持续监控；
- `candidate`：已被主 Agent 选中，等待或正在正式研究；
- `covered`：已有当前有效正式报告，值得进行价格或事件监控；
- `stale`：重大新事实使旧报告或估值失效，暂停价格监控并等待更新。

“研究过”是报告历史，“当前是否可用”才是状态。只有 active `covered` 公司进入 `research/watchlist.jsonl`。

### 研究任务状态

活动队列只使用：

- `queued`：等待领取；
- `running`：一个 Agent 正在研究。

任务完成后从活动队列移除。失败或中断的 `running` 任务显式退回 `queued`。同一公司最多一个活动任务，任务只允许绑定 `candidate` 或 `stale`。

## 状态硬约束

- `unseen`：没有筛选结论、当前报告指针、任务或价格线；隔离历史档案不受影响。
- `ignore`：没有活动价格监控；正式研究后的 ignore 可以保留最新正式报告指针。
- `candidate`：有选入理由和时间，没有当前有效报告指针及价格线。
- `covered`：必须指向最新的非空日期化正式报告，并有信息截止时间、关键逻辑、风险、来源，以及价格或事件触发；无法可靠估值时必须解释原因。
- `stale`：必须保留旧报告和明确失效原因；价格监控关闭，只允许创建更新研究任务。
- 价格命中只改变触发器的 armed/hit 状态，不改变公司研究状态。
- 持仓、仓位和账户信息不进入公司研究状态。

## 一次性全市场基线

首次建立基线时，冻结证券范围和信息截止时间。主 Agent分批浏览压缩事实，对每家公司只做两个判断：

- `ignore`：当前不值得占用一次完整单公司研究资源；
- `research_now`：商业质量、错价可能性、变化程度或关键问题的信息价值值得完成正式研究。

`research_now` 是动作：写入 `candidate` 并创建唯一任务。初筛不输出价值区间、目标价、买点或价格触发，也不为每家公司生成 Markdown。

不得按数量目标填队列，也不得因市值、行业、亏损或单一指标机械决定。程序可以准备证券身份、业务、利润、现金流、债务、估值和风险摘要，但主 Agent 对整批作最终判断。

基线批次只接受 active `unseen` 公司；混入任何已判断公司时整批失败，不产生部分写入。基线完成后不再定期重跑全市场，只处理新增与变化。

## 单公司统一研究

只有 `candidate` 和 `stale` 可以派发。不同公司可以独立并行，同一公司始终只有一个 Agent。

Agent 必须使用统一提示词，完成商业模式、竞争、财务质量、治理、资本配置、市场预期、估值和风险检查。报告篇幅可以随复杂度变化，但不能自行选择研究等级或跳过核心问题。

结果只有：

- `covered`：报告当前有效且值得持续监控；
- `ignore`：完成正式研究后仍不值得持续监控。

两种结果都向 `research/companies/CN/{ticker}/reports/` 追加一份日期化报告。报告可以较短，但必须有来源、估值判断和证伪依据。不得覆盖以前的正式报告。

`covered` 若能可靠估值，给出合理价值区间和关注价；若无法可靠估值但事件具有持续研究价值，可以只做事件监控，并填写无法估值原因。`ignore` 不得激活价格触发。

## 报告存档

新机制正式报告使用：

```text
research/companies/CN/{ticker}/reports/YYYY-MM-DD.md
research/companies/CN/{ticker}/reports/YYYY-MM-DD-02.md  # 同一天第二份
```

`research_state.jsonl.report_path` 必须指向时间线上最新的正式报告，它就是 current；不生成 `current.md` 副本，也不使用 `stale` 文件后缀。公司转为 `stale` 时由状态说明旧报告已经失效。

迁移前旧稿放在 `research/companies/CN/{ticker}/legacy/YYYY-MM-DD.md`。每家公司最多一份，由固定 Git 标签中的候选按证券身份、报告类型、内容完整度和日期选优。`legacy/` 永远不修改公司状态，不参与 current、估值、任务、自选池和价格扫描；正文顶部必须显示历史资料警告。

`reports/` 和 `legacy/` 都进入 Git，完整克隆仓库即可恢复报告正文。是否参与当前研究状态只由目录语义和 `report_path` 决定，与 Git 跟踪状态无关。

## 自选池与每日收盘

`research/watchlist.jsonl` 是 active `covered` 的确定性投影，不是人工维护的第二套账本。

每日收盘：

1. 完整获取所有带价格线的 covered 公司收盘价；
2. 首次跌入触发区时提示，离开触发区后重新武装；
3. 主 Agent 简短检查原逻辑和最新信息；
4. 只有基本面或估值框架已经失效时，才把公司转为 `stale` 并更新研究。

缺少任意受监控公司报价时整批失败。价格命中不自动交易，也不自动创建完整研究任务。

## 财报与重大事件

公告扫描覆盖全部 active 公司，包括 `ignore`。程序找出新增财报、业绩预告、重大合同、处罚、控制权和资本结构变化，主 Agent 只记录确有状态影响的公司。

典型流转：

```text
ignore + material_event   -> candidate 或 ignore
candidate + new_context   -> candidate（更新任务理由）
covered + non_material    -> covered
covered + invalidation    -> stale
covered + decisive_failure -> ignore
stale + research_complete -> covered 或 ignore
```

全市场公告扫描负责让池外公司重新进入；公司特定事件触发帮助维护 covered 结论。无实质变化不写状态，不创建任务。

## 状态维护方式

唯一事实源：

- `coverage/cn-a/research_state.jsonl`：证券范围、公司研究状态、当前结论和触发器运行状态；
- `coverage/cn-a/research_queue.jsonl`：当前 queued/running 任务；
- `research/companies/CN/{ticker}/reports/`：新机制正式报告时间线，状态中的 `report_path` 指向最新一份；
- `research/companies/CN/{ticker}/legacy/`：每家公司最多一份的隔离历史旧稿；
- `research/watchlist.jsonl`：从 active covered 状态派生；
- `coverage/cn-a/event_scan_state.json`：公告扫描成功检查点。

所有共享 JSONL 只由协调器在锁内原子写入。单公司 Agent只返回最终结构化结果，不直接修改共享文件。每次状态变更后重建自选池并执行 `python -m trading_os validate`。

一次性旧状态迁移：

```bash
python -m trading_os state migrate-v2 --at <带时区时间>
```

迁移规则：旧 `researched` 变为 `covered`；旧 `watch` 若没有正式报告变为 `candidate` 并清除价格线。需要重新执行全市场基线时，先准备好筛选输入，再运行：

```bash
python -m trading_os state prepare-rebaseline --at <带时区时间>
```

该命令保留 active `covered`，把其余 active 公司重置为 `unseen`，然后用新的 `ignore / research_now` 批次完整覆盖。

## 验收

- active 范围内没有遗留 `unseen`；
- 只有 `candidate/stale` 有活动任务；
- candidate 没有价格线；
- covered 都有有效报告及价格或事件触发；
- stale 已暂停价格监控并记录失效原因；
- 自选池与 active covered 完全一致；
- 每日价格扫描只覆盖 covered；
- 公告扫描覆盖全部 active 公司；
- `python -m trading_os validate` 通过。

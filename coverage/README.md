# Coverage Protocol

`coverage/` 是全市场覆盖与任务编排层。它不保存完整公司研究结论，也不替代
`research/companies/`。它的职责是：冻结研究范围、按行政规则切分可恢复 cohort、
调度每家公司独立快速甄别，并记录后续预算、复核状态和停止理由。

## 核心原则

- 默认全覆盖，但绝不平均投入。每家公司都可被找到、每次停止都可审计，只有最可能改变组合决策的少数公司获得完整深研。
- 研究漏斗逐层购买信息：全覆盖接入、15 分钟快速甄别、正式画像、范围研究、完整深研、独立承保。
- 机器地图、因子排名和公开快照只可准备材料，不能决定哪些范围内公司有资格被 Agent 查看，也不能直接晋级正式画像或更深层级。
- 同一 rapid-triage cohort 全部封存后，由未参与单公司甄别的独立跨公司 allocation Agent 复核每一家公司并显式配置下一层预算；这是只读取封存包的跨公司角色，不代写任何单公司研究，程序也不生成投资分数。
- 小市值、低流动性、亏损、PE 为负、行业冷门，都不能作为硬跳过理由。
- ST、*ST、重大异常公司进入 `needs_manual_review`，不要直接排除。
- `skip_*` 只用于硬排除项，例如退市整理、明显不在普通 A 股范围内、数据无法识别。
- 完整研究报告只写入 `research/companies/{MARKET}/{TICKER}/reports/`。

## 目录

```text
coverage/
  README.md
  cn-a/
    companies.jsonl
    screening.jsonl
    research_queue.jsonl
    runs.jsonl
    universe.schema.json
    screening.schema.json
    research-queue.schema.json
    universe.example.json
    screening.example.json
    research-queue.example.json
    runs/
      .gitkeep
```

`*.jsonl` 是全市场覆盖状态的工作真相。每一行是一家公司或一个任务，便于 Git diff，
也便于 agent 用工具安全查询和更新。`*.schema.json` 与 `*.example.json` 用来说明结构和约束。

## 分流结果

- `catalog`：已进入全市场可审计目录，但本周期未获得进一步研究预算。
- `rapid_triage`：获得15分钟级快速甄别预算。
- `triage_candidate`：快速甄别通过，等待完整批次横向比较。
- `quick_profile`：获得一小时级正式投资画像预算。
- `profile_candidate`：正式画像通过，等待完整同层批次横向比较。
- `scoped_research`：只解决一至三个决定性未知数。
- `deep_candidate`：范围研究通过，等待完整同层批次横向比较。
- `targeted_followup`：只补齐一个或少数决定性证据。
- `deep_research`：进入完整公司研究队列。
- `price_watch`：公司可能可投，但当前价格不支持继续购买研究预算。
- `reassign_or_stop`：超出当前 agent 能力圈，转派或暂停。
- `watch_only`：已有研究档案或等待既定复查，不重复创建初始研究任务。
- `conditional_stop`：继续研究的信息价值不足或存在经证据确认的阻断项；必须记录重新激活条件。
- `hard_exclusion`：非普通股、退市或法律上不能形成投资对象。
- `skip_risk`：退市整理、明显无法作为普通股票研究的硬风险项。
- `skip_too_small`：原则上少用；不能因为普通小市值或低流动性而跳过。
- `skip_not_in_scope`：不在当前普通 A 股研究范围内，如 ETF、基金、债券、B 股、优先股等。
- `needs_manual_review`：ST、*ST、数据冲突、证券状态异常，需主 agent 先判断研究路径。

## A 股首筛与研究资本配置

第一轮只做低成本分流：

1. 排除非普通 A 股和退市整理类硬排除项。
2. 将 ST、*ST、重大异常和数据冲突标为 `needs_manual_review`。
3. 其余普通 A 股全部进入 rapid-triage backlog；按等待时间和 symbol 等行政字段切成 20—50 家的小 cohort，不按投资吸引力筛入。
4. 每家公司由一个独立 Agent 形成带 S1 证据、近期价格、反证、正常化盈利粗判和结构化重启触发器的快速简报。
5. 完整 cohort 封存并发布到公司时间线后，生成不含机械分数的 comparison packet。
6. 独立 allocation Agent 复核全部成员；即使首轮 disposition 不建议晋级，也允许在发现假阴性时救回。正式画像容量上限约 40 家，但在可信风险簇分类建立前，所有 selected rows 作为同一 `unclassified` 簇受更低的 policy 上限约束；完成顺序不能影响晋级。
7. 正式画像和范围研究同样必须先完成同层批次，再分别统一竞争范围研究和深研容量。
8. 所有未晋级公司保留停止原因、反证和可执行重启触发器；未来真实 trigger 命中后重新进入增量 cohort。

## 当前实现边界

- cohort seal 能证明一个小批次的成员与处理守恒，但当前还没有把普通 A 股 universe、`scope_cutoff`、纳入、硬排除和异常绑定在一起的全市场 scope manifest。启动全 A 长程 Goal 时必须先补这一层，不能从若干 JSONL 的近似行数推断全覆盖。
- baseline 不能等同于旧队列的 `requires_rebaseline`。scope 内缺少当前 rapid-triage 协议有效终态的 legacy `completed`、watch 状态或缺失 queue 的公司也必须进入 baseline；当前 `triage-freeze` 还不能独自完成这类 intake 归一化，长程 Goal 必须先建立 scope-to-queue 守恒物化与恢复契约。
- `date/TTL` 与 price trigger 已可派生到 schedule/alerts；`filing/event/thesis` 目前只有 watching 定义，还没有 canonical hit ledger、消费状态和去重闭环。
- baseline 与 incremental 是两条逻辑 lane，但每个 symbol 当前只有一个可变 queue row。长程 Goal 必须先定义事件与活动任务的合并、抢占、延后和消费规则，不能用“互不阻塞”掩盖同一公司的任务所有权冲突。
- rapid-triage 的独立 allocation 已封存；面向 catalog、price-watch、conditional-stop 等分层的正式半盲质量抽查仍需建立独立封存契约。
- 当前 `profile-finalize` 仍是历史的机械 score/priority 选择器，尚未迁移为“完整同层 comparison seal + 独立 Agent 全量 decisions”的新契约。长程 Goal 在执行任何 quick-profile → scoped-research 或 scoped-research → deep-research 晋级前，必须先完成这一迁移和试运行。
- `runs.jsonl` 目前还没有正式的加锁 upsert/事件账本入口；本 pilot 由根 Agent 串行追加。全 A 长程 Goal 应把 run ledger 与 scope manifest 一并纳入原子写入和恢复协议。

## Agent 辅助工具

单公司 Agent 不能直接编辑共享 JSONL；由根 Agent 串行调用正式 workflow。现有 screening/queue read-modify-write 入口共用 `.coverage-write.lock` 的操作系统文件锁，用于阻止 claim、record、finalize 或不同研究层级并发覆盖彼此的状态。锁文件是可长期存在的哨兵，进程退出会由操作系统释放实际锁；不得凭文件存在与否判断占用或手工删除活锁：

```bash
python -m trading_os coverage validate
python -m trading_os coverage status
python -m trading_os coverage get CN:600519
python -m trading_os coverage triage-freeze <cycle-id> --queue-status requires_rebaseline --symbols-file <scope-derived-symbols.json>
python -m trading_os coverage triage-claim <cycle-id> --agent <agent-id> [--symbol CN:000000]
python -m trading_os coverage triage-record --input <rapid-triage.json>
python -m trading_os coverage triage-status <cycle-id>
python -m trading_os coverage triage-compare <cycle-id>
python -m trading_os coverage triage-finalize <cycle-id> --decisions <agent-decisions.json>
python -m trading_os coverage evaluate-profile --input <quick-profile.json>
python -m trading_os coverage record-profile --input <quick-profile-package.json>
python -m trading_os coverage profile-status <cycle-id>
python -m trading_os coverage profile-claim --agent <agent-id> [--symbol CN:000000]
```

`allocate-research`、`apply-allocation` 与 `profile-finalize` 只为历史资产兼容保留，不是新增长程 Goal 的生产入口。L2/L3 横向晋级必须先迁移为独立 Agent 全量 decisions 契约。

这些命令是给 Codex、Claude 或其他 agent 用的安全编辑器，不要要求用户手动执行。

## 长程执行

每次全市场筛选或深研批次都向 `coverage/cn-a/runs.jsonl` 追加或更新 run 记录。
如果需要保留详细批次摘要，可以额外在 `coverage/cn-a/runs/` 下写 Markdown 或 JSON，
但不要把它当成唯一真相。

任务状态使用：

- `pending`
- `running`
- `completed`
- `requires_rebaseline`（已有历史材料，但旧结论不可执行；等待按当前协议重建）
- `failed`
- `skipped`
- `needs_review`

下一个 agent 接手时，读取 `coverage/cn-a/runs.jsonl` 和相关队列，优先处理
`pending`、`requires_rebaseline`、`failed` 和 `needs_review`，不要重新开始整轮任务。

## 与研究资产的关系

- `coverage/cn-a/screening.jsonl` 决定研究顺序和复核状态。
- `coverage/cn-a/research_queue.jsonl` 是分层研究任务队列；任务必须带阶段、预算和停止条件。
- `research/companies/` 保存真正的研究报告和当前公司状态。
- `research/index.json`、`automation/review_schedule.json`、`automation/price_alerts.json`
  只从 `research/companies/` 生成，不从 coverage 生成。

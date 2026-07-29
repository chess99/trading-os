# A 股覆盖、接入与分流 Playbook

文件名保留 `screening.md` 以兼容历史链接；当前机制不是用机器筛掉“不值得看”的公司，而是管理全覆盖接入、行政分批和 Agent 看过之后的研究分流。

## 全覆盖漏斗

```text
冻结普通 A 股 universe
→ 每家公司独立 rapid triage
→ 全批次封存与独立抽查
→ 跨公司 Agent 配置正式画像预算
→ 正式画像 → 范围研究 → 深研 → 独立承保 → 组合比较
```

覆盖不等于每家公司都获得完整初研，但等于每家范围内公司至少获得一次可审计的 Agent 快速查看。小市值、低流动性、暂时亏损、负倍数、冷门行业或不符合某种投资风格，都不能成为静默跳过理由。

程序化选股、人工提名和外部清单可以补充差异材料或形成紧急 trigger，但不能替代全覆盖，也不能直接晋级深研、承保或买入。

## Intake 只做行政排序

机器可以根据以下字段安排处理顺序：

- 已观察到的结论失效或重大事件；
- 已命中的财报、公告、价格和 date/TTL trigger；
- 逾期程度、等待时间；
- 缺少当前 rapid-triage 协议有效终态；`requires_rebaseline` 只是其中一个旧状态提示；
- symbol 稳定顺序。

机器不得使用市场估值、质量因子、利润正负、市值、流动性、行业偏好或旧评级决定是否纳入。容量不足时，`deferred_capacity` 只能作为 scope manifest 的调度分区字段并保留下一批次的稳定顺序，不能写成现有 screening decision 或 queue status。

baseline backlog 与 incremental trigger 使用独立逻辑 lane。critical trigger 可以提高行政紧急度，但同一 symbol 只能有一个活动任务；生产运行前必须定义事件合并、抢占、延后和 consumed 规则。policy 还应给 baseline 保留最低通道，防止存量公司永远排不到。

## 事件性冲击与危机错杀

- 当期亏损、利润骤降或 PE 失真不能降低 rapid-triage 资格；先判断冲击是需求延后、周期波动还是永久损失。
- 正常化盈利用 3—5 年中枢和多情景现金流粗判，不机械外推危机期亏损或历史峰值。
- 先核验现金消耗、债务到期、再融资、潜在稀释和维持经营资本，回答能否活到需求恢复。
- 反推当前价格要求的恢复时间、幅度和长期回报，寻找或否定“市场按永久受损定价”的错配。

## 分流状态

- `rapid_triage`：正在或等待 Agent 快速甄别；
- `triage_candidate`：快速甄别认为值得竞争正式画像预算；
- `quick_profile`：获得一小时级正式画像预算；
- `profile_candidate`：画像通过，等待同层比较；
- `scoped_research`：只解决决定性未知；
- `deep_candidate`：范围研究通过，等待深研预算；
- `deep_research`：进入完整初研；
- `price_watch`：等待价格触发后复核；
- `catalog`：当前停止购买更多信息，等待明确变化；
- `conditional_stop`：存在结构性风险，但保留证据化重启条件；
- `reassign_or_stop`：需要对应行业能力的独立 Agent；
- `hard_exclusion`：证券身份不构成范围内普通股投资对象；
- `needs_manual_review`：证券状态、数据或重大风险需要人工判断。

任何停止都不是永久投资标签。除 `hard_exclusion` 外必须有理由、反证和可执行重启条件。

## 可恢复与守恒

每个 intake cohort 在 `coverage/cn-a/triage/{cycle-id}/cohort.json` 冻结并封存。当前 cohort 记录完整成员、稳定顺序、纳入理由、行政请求和自身 seal，不含投资分数；它尚未绑定全市场 universe 来源。scope manifest 契约建立后，cohort 还必须保存 parent scope 的路径与 SHA-256，来源与范围哈希由 parent manifest 提供。`research_queue.jsonl` 是可恢复物化状态，不取代 cohort、scope manifest 或公司时间线事实源。

冻结必须幂等：同 ID、同内容可以修复半完成物化；同 ID、不同内容必须失败。正在运行或已进入更深研究的公司不得被新 cohort 静默覆盖。

批次守恒至少验证：

```text
冻结成员 = 有效终态 + pending + running + 明确失败
comparison decisions = cohort 全部成员
selected + deferred = cohort 全部成员
```

## 命令

```bash
python -m trading_os coverage validate
python -m trading_os coverage status
python -m trading_os coverage scope-freeze <run-id> --mode auto --scope-cutoff <timestamp>
python -m trading_os coverage scope-status <run-id>
python -m trading_os coverage trigger-checkpoint <run-id>
python -m trading_os coverage lane-freeze <run-id>
python -m trading_os coverage quality-scope-prepare <run-id>
python -m trading_os coverage quality-scope-record <run-id> --reviews <identity-reviews.json>
python -m trading_os coverage triage-freeze <cycle-id> --scope-run-id <run-id> --quality-policy-snapshot <policy-snapshot.json> --scope-identity-result <identity-result.json> --queue-status requires_rebaseline --symbols-file <scope-derived-symbols.json>
python -m trading_os coverage triage-status <cycle-id>
python -m trading_os coverage quality-triage-prepare <cycle-id>
python -m trading_os coverage quality-triage-record <cycle-id> --reviews <quality-reviews.json>
python -m trading_os coverage triage-compare <cycle-id>
python -m trading_os coverage triage-finalize <cycle-id> --decisions <agent-decisions.json>
python -m trading_os coverage evaluate-profile --input <quick-profile.json>
python -m trading_os coverage record-profile --input <quick-profile-package.json>
python -m trading_os coverage reconcile --check
```

历史 `allocate-research`、`apply-allocation` 和 `profile-finalize` 只用于兼容旧资产，禁止作为新 Goal 的生产晋级入口。

每个快速简报验证通过后立即发布到对应公司不可变时间线，再更新队列；批次末尾的 reconcile 是漂移安全网，不是正常状态传播机制。

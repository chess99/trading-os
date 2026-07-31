# 研究资本配置 Playbook

## 核心原则

研究时间本身是资本。主 Agent 负责决定“下一小时花在哪里”，研究员负责用证据回答具体问题。

初筛不使用机械分数，也不增加独立 allocation Agent：投资经理的 `send_to_analyst` 就是 L1 预算决策。

## 漏斗

| 层级 | 默认范围/容量 | 单家公司预算 | 决策者 | 只回答什么 |
|---|---:|---:|---|---|
| L0 scope | universe 全量 | 批次级 | 程序 + 主 Agent | 身份、纳入、硬排除、异常 |
| L1 manager screen | 全量，默认每批 150 | 批次级 | 同一主 Agent | 是否值得购买下一小时 |
| L2 quick profile | 仅 `send_to_analyst` | 约 1.5 小时 | 单公司研究员 | 决定性问题能否解决 |
| L3 scoped research | 少数 | 约 4 小时 | 单公司研究员 | 投资路径能否由证据建立 |
| L4 deep research | 更少 | 约 24 小时 | 单公司研究员 | 重建业务、会计、盈利和估值 |
| L5 underwriting | 极少 | 12 小时起 | 独立 reviewer | 深研主张能否承保 |
| L6 portfolio | passed 公司 | 组合层 | 组合 Agent | 最新价格下如何配置 |

容量是上限，不是配额。没有合格公司时留空。

所有容量以同一个 `manager_screen_run_id` 为账本边界，而不是单个 batch、cycle 或 Agent。新开 cycle/batch 不能重置容量；批准前必须把同 run 已封存承诺与本次申请相加，超限则整项/整批拒绝，不允许机器靠改写路由、评分或降低门槛来“凑容量”。

## L1：投资经理直接配置

`pass`、`watch`、`send_to_analyst` 必须基于可读理由、决定性问题、证据和相对研究价值。不得生成精确总分。

初筛同一批由同一个主 Agent完成，避免不同单公司 Agent 的尺度漂移。只有候选才购买单公司上下文和工具调用。

`send_to_analyst` 是第一笔 analyst 预算，但仍受 manager-screen policy 的 run 级上限。记录成功后，queue 保留原 result 路径/SHA-256、决定性问题和证据 ID；quick profile 必须绑定它们，并用自身来源形成 `decisive_answer`，否则不得进入同层比较。

## L2/L3：研究员结果回到投资经理

研究员不自行决定深研或组合操作。主 Agent比较同层结果时关注：

- 问题是否被证据解决；
- 正常化所有者收益和现金转换是否可建立；
- 当前价格是否仍有可信回报路径；
- 最大反证与永久损失风险；
- 再投入时间相对其他公司是否更值。

可使用 `profile-compare/profile-select` 封存同层决策，但投资经理无需与最初 manager-screen 隔离；只需与提交单公司研究的研究员保持角色独立。targeted/scoped/deep 每次升级都必须是主 Agent 对同 run 可比 cohort 的显式决定，并占用对应 run 级容量。

研究员建议 `targeted_followup` 后，原 manager 只有两种正式动作：用 `profile-followup-approve` 封存购买决定，或用 `profile-followup-decline` 封存不购买决定。decline 必须绑定原 manager-screen result、已封存的画像/evaluation、研究员身份和至少一个结构化重启 trigger；manager 必须与研究员独立。其终态只允许 `price_watch`、`watch_only`、`conditional_stop`，追加预算固定为 0，不进入 targeted approval ledger。

修复前由 evaluator 自动生成、但没有 approval 的 `targeted_followup,status=pending`，只能在从未 claim、没有失败尝试且没有完成记录时由同一 decline 命令一次性收口为 `skipped`。原画像、evaluation 和 queue 历史全部保留；已 running、已 completed 或已经出现 sealed approval 的任务不得用 decline 回退。

## 停止与重启

- `pass/catalog`：当前不买更多研究信息；
- `watch/watch_only`：等待价格、财报、事件或关键证据；纯价格结论只在后续正式研究中使用 `price_watch`；
- `targeted_followup`：只补少数决定性证据；
- `conditional_stop`：存在结构性阻断；
- `deep_research`：证据和赔率都支持继续投入；
- `hard_exclusion`：证券身份不属于范围。

除硬排除外，停止必须有可执行重启条件。亏损、负 PE、小市值、低流动性或行业冷门不能单独构成停止理由。

`profile-followup-decline --triggers` 接受 JSON 数组，每项字段固定为 `type/condition/reason`；type 仅允许 `filing/price/date/ttl/event/thesis`。`price_watch` 至少包含一个 `price` trigger。命令先封存 decline，再物化 queue/screening；中途失败时用完全相同的 manager、outcome、reason 和 triggers 重放，禁止手改 JSONL。

## 承保预算

只有完成 deep research、结构化主张和来源封存的公司才能申请承保。主 Agent 必须先封存独立的 underwriting approval，绑定 deep selection、deep completion、claims、policy SHA、单家公司预算和同 run ledger；approver 还必须与 deep researcher 独立。以下情况构成 challenger 候选：

- 重大事实或估值分歧；
- 高治理、会计或永久损失风险；
- 可能进入组合前五大仓位；
- 第一 reviewer 证据不足。

没有可靠共识时不通过。

underwriting approval 只购买 underwriting，不授予 challenger 或 portfolio。challenger 与组合综合都必须由主 Agent 重新显式批准，并分别执行 manager-run 容量检查；相应批准 contract 尚未物化时不得提前 dispatch 或 synthesize。

## 旧机制

`rapid-triage → triage-compare/finalize`、`quality-triage-*`、`allocate-research`、`apply-allocation` 和 `profile-finalize` 仅验证历史资产。新 Goal 使用 manager-screen，不得启动递归 correction。

旧状态若要进入新协议，只能走一次性 sealed legacy transition：`adoption` 采用可验证正式研究，`rescreen` 释放回 manager-screen，`defer_active` 保持活动/更深阶段。旧 priority、price_watch 或 disposition 不得自动购买任何新预算。

## 共享状态

所有 coverage 写入走正式 workflow 和写锁。研究员只提交自己的 package；主 Agent 串行物化。遇到 `coverage state is busy` 时等待并重试，不手工改 JSONL。

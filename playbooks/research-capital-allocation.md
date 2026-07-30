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

## L1：投资经理直接配置

`pass`、`watch`、`send_to_analyst` 必须基于可读理由、决定性问题、证据和相对研究价值。不得生成精确总分。

初筛同一批由同一个主 Agent完成，避免不同单公司 Agent 的尺度漂移。只有候选才购买单公司上下文和工具调用。

## L2/L3：研究员结果回到投资经理

研究员不自行决定深研或组合操作。主 Agent比较同层结果时关注：

- 问题是否被证据解决；
- 正常化所有者收益和现金转换是否可建立；
- 当前价格是否仍有可信回报路径；
- 最大反证与永久损失风险；
- 再投入时间相对其他公司是否更值。

可使用 `profile-compare/profile-select` 封存同层决策，但投资经理无需与最初 manager-screen 隔离；只需与提交单公司研究的研究员保持角色独立。

## 停止与重启

- `pass/catalog`：当前不买更多研究信息；
- `watch/watch_only`：等待价格、财报、事件或关键证据；纯价格结论只在后续正式研究中使用 `price_watch`；
- `targeted_followup`：只补少数决定性证据；
- `conditional_stop`：存在结构性阻断；
- `deep_research`：证据和赔率都支持继续投入；
- `hard_exclusion`：证券身份不属于范围。

除硬排除外，停止必须有可执行重启条件。亏损、负 PE、小市值、低流动性或行业冷门不能单独构成停止理由。

## 承保预算

只有完成 deep research、结构化主张和来源封存的公司才能承保。以下情况触发 challenger：

- 重大事实或估值分歧；
- 高治理、会计或永久损失风险；
- 可能进入组合前五大仓位；
- 第一 reviewer 证据不足。

没有可靠共识时不通过。

## 旧机制

`rapid-triage → triage-compare/finalize`、`quality-triage-*`、`allocate-research`、`apply-allocation` 和 `profile-finalize` 仅验证历史资产。新 Goal 使用 manager-screen，不得启动递归 correction。

## 共享状态

所有 coverage 写入走正式 workflow 和写锁。研究员只提交自己的 package；主 Agent 串行物化。遇到 `coverage state is busy` 时等待并重试，不手工改 JSONL。

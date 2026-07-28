# 研究资本配置 Playbook

## 核心原则

研究时间本身也是资本。下一小时应投向最可能改变组合决策、且关键不确定性能够被公开证据解决的公司，而不是平均分给全市场。

研究优先级使用方向性判断，不伪装成精确概率：

```text
承保通过可能性
× 当前或近期进入买入区的可能性
× 对组合的潜在贡献
× 新信息改变结论的可能性
× 不确定性的可解决程度
÷ 预计研究成本
```

公开快照总分只是购买更多信息的便宜地图，不能直接把公司晋级为深研、承保或 `buy_now`。

## 自适应漏斗

| 层级 | 默认单周期容量 | 单家公司预算 | 只回答什么 |
|---|---:|---:|---|
| L0 市场清洗 | 全市场 | 机器秒级 | 是否为可识别的普通上市股票 |
| L1 多视角便宜地图 | 全市场 | 机器分钟级 | 哪些公司值得进入动态候选池 |
| L1.5 快速甄别 | 200 | 15 分钟 | 是否值得竞争正式画像预算 |
| L2 正式投资画像 | 40 | 1 小时 | 是否存在一条可信投资路径 |
| L3 范围研究 | 15 | 4 小时 | 决定性未知数能否被证据解决 |
| L4 完整深研 | 6 | 24 小时 | 完整重建业务、会计、正常化盈利和估值 |
| L5 独立承保 | 3 | 12 小时起 | 深研主张能否经半盲复核通过 |
| L6 组合决策 | 所有有效 passed 公司 | 组合层 | 最新价格下是否优于其他机会、如何配置 |

容量是上限，不是配额。没有足够候选时保留研究预算和现金，不为填满队列降级标准。

## 多视角选样

不得用一张 PE、ROE、增长率加总榜包办全市场。每个周期分别为以下视角保留研究容量：

- 综合赔率；
- 现金回报与资产折价；
- 高质量复利；
- 非金融神奇公式：同时看 EBIT/EV 与 EBIT/有形经营资本；
- 银行、保险等专用模型；
- 周期成本曲线与中周期盈利；
- 危机错杀和负 PE 正常化；
- 新财报或重大信息变化；
- 从未入选公司的当前时点假阴性抽查。

神奇公式只是一条独立预算镜头，不替代公司研究。生产口径同时保留两套排名：经典版把
盈利收益率和资本回报率的全市场名次等权相加；A 股适配版用三年核心经营 EBIT 中位数、
当前市值和最近统一报告期资产负债表，并以 70% 全市场、30% 同行业分位降低行业会计
口径偏差。银行、保险、券商、地产、公用事业不适用；周期股转入中周期盈利专用镜头；
投入资本非正的轻资产公司转入质量镜头，不能获得无限资本回报率。全额扣除货币资金只
用于便宜地图，进入正式画像后必须核验受限资金与最低经营现金。

不同镜头的实际槽位来源记为 `selected_by`，进入多个镜头短名单的事实另记为
`matched_lenses`。多镜头共识只能读取后者，不能因去重而失效。

## 风险簇上限与行业证据闸门

不设必须填满的行业配额，但对单一明确经济风险簇设置上限：快速甄别 25、正式画像 10、
范围研究 5、完整深研 2、独立承保原则上 1。`diversified` 分类过粗，暂不应用同一硬上限。
达到上限后选择下一名不同风险簇公司；没有合格替代者时容量留空。

银行不得仅凭低 PB、低 PE 或静态 ROE 晋级。正式画像的 S1 来源 `supports` 至少覆盖
`bank_latest_s1_filing`、`bank_asset_quality_migration`、`bank_capital_adequacy`；范围研究
还必须覆盖 `bank_normalized_credit_cost_and_nim`、
`bank_common_equity_earnings_after_capital_instruments`、`bank_property_lgf_exposure`。
这些标签必须由法定定期报告等 S1 来源支持，缺任一项即不能竞争下一层预算。

危机错杀和假阴性抽查合计至少占快速甄别候选池的 15%。这不是历史回测，而是防止筛选形成风格盲区。

## L1.5 快速甄别

200 家是动态候选池，不是 200 份一小时报告。每家公司只获得最多 15 分钟，读取最新
定期报告、近期价格和必要风险信息，回答业务能否快速理解、是否存在生存/治理阻断、
正常化盈利是否可粗判、现价是否至少可能有赔率，以及再投入一小时能否改变决策。

输出必须符合 `templates/rapid-triage.schema.json` 并封存。结果只能是等待横向比较、
价格观察、结构化停止、能力圈转派或返回目录。单家公司完成后不得立即晋级。

## 正式画像的八个问题

1. 公司靠什么赚钱，是否处于当前能力圈？
2. 穿越周期的所有者收益大致是多少？
3. 悲观情况下能否在不被迫大幅稀释的前提下活过 24—36 个月？
4. 控股股东、管理层、审计和关联交易是否基本可信？
5. 当前利润是常态、峰值、谷底还是会计假象？
6. 宽区间估值下，现价是否存在达到 10%—12%回报的可信路径？
7. 市场可能错在哪里？
8. 下一阶段最关键的一至三个问题是什么，能否被证据解决？

## 停止、停放与重启

快速停止不是把公司永久贴成“垃圾”，而是停止购买低价值信息：

- `hard_exclusion`：非普通股、退市或法律上不可形成投资对象。
- `conditional_stop`：已由可靠证据确认少数股东权益不可承保、财务不可核验、无法生存、资本结构吞噬权益价值或核心论点已证伪。
- `price_watch`：公司可能可投，但当前价格没有达到深研回报门槛。
- `targeted_followup`：只补一个或少数决定性证据，不扩张成完整报告。
- `reassign_or_stop`：超出当前 agent 能力圈，先尝试交给具备相应行业能力的 agent。

除真正硬排除外，每次停止或停放必须记录证据、原因、重启条件和复查时间。亏损、负 PE、小市值、低流动性或行业冷门不能单独构成停止理由。

## 升级纪律

- L1 不能直接晋级正式画像、深研、承保或买入。
- L1.5 只有完整候选批次封存并横向比较后，最多 40 家进入 L2。
- L2 只能进入范围研究候选、定向补证、观察、转派或停止；范围研究候选必须等完整
  L2 同层批次封存后统一竞争容量。
- L3 只有在业务可理解、生存与治理基本通过、正常化盈利可建立、粗估值存在至少 10%基准回报路径时才能进入完整深研。
- L3 的深研候选也必须等完整同层批次封存后统一竞争容量。
- L4 只有证据和估值完整、基准回报达到 12%承保参考门槛、且相对全市场仍有竞争力时才购买独立承保预算。
- 单公司任何层级都不得给最终买入与仓位；只有组合层可以。

完成顺序不是投资质量。`triage-finalize` 和 `profile-finalize` 是生产强制闸门：
候选未全部终态时拒绝晋级，从机制上消除 first-in bias。

## 命令

```bash
python -m trading_os coverage rank-rebaseline --magic-formula automation/magic_formula_snapshot.json
python -m trading_os coverage allocate-research
python -m trading_os coverage apply-allocation
python -m trading_os coverage triage-claim --agent <agent-id> [--symbol CN:000000]
python -m trading_os coverage triage-record --input <rapid-triage.json>
python -m trading_os coverage triage-status <cycle-id>
python -m trading_os coverage triage-finalize <cycle-id>
python -m trading_os coverage evaluate-profile --input <quick-profile.json>
python -m trading_os coverage record-profile --input <quick-profile-package.json>
python -m trading_os coverage profile-status <cycle-id>
python -m trading_os coverage profile-claim --agent <agent-id> [--symbol CN:000000]
python -m trading_os coverage profile-release --agent <agent-id> --symbol CN:000000 --failure-reason <reason>
python -m trading_os coverage profile-finalize <cycle-id> --stage quick_profile
python -m trading_os coverage profile-finalize <cycle-id> --stage scoped_research
```

`triage-record` 和 `record-profile` 是生产入口：它们校验来源清单和 agent provenance，
封存单公司判断，但不按完成顺序自动晋级。快速甄别保存在 `coverage/cn-a/triage/`，
画像保存在
`coverage/cn-a/profiles/{CYCLE_ID}/{TICKER}/`；单公司 agent 只提交自己的 package，不能直接修改共享队列。

agent 因工具、来源或运行环境失败且尚未产出 package 时，必须先用 `profile-release` 释放认领。命令会把失败原因和原 agent 写入不可覆盖的 `attempt_history`，再允许其他 agent 重试；不得手工改写 `assigned_agent`。

# 全 A 股持续研究 Goal 启动提示词

> 用法：在新的 Codex 对话中引用本文件，并补充本次参数。本文件负责长期编排；仓库内 `AGENTS.md`、playbook 和 policy 是执行事实源。

请创建并持续执行一个 Goal。除非本次调用明确指定，不设置 `token_budget`。

目标是：冻结普通 A 股范围和信息截止时间，由主 Agent 作为投资经理快速浏览全市场；只有少数值得继续购买研究信息的公司才交给单公司研究员，之后按证据质量进入范围研究、深研、独立承保和组合综合。保持 coverage、公司时间线、触发器和仓库文件整洁可验证。

## 参数

- `mode`：`auto`（默认）、`baseline` 或 `incremental`。
- `run_id`：未指定时按启动日期与用途生成稳定 ID。
- `scope_cutoff`：未指定时使用 Goal 创建时的带时区时间。
- `universe_ref`：未指定时冻结仓库内可验证的普通 A 股 universe。
- `manager_batch_size`：未指定时读取 `policies/manager-screening.json`，默认 150；允许 50—250。

`auto` 同时维护 baseline 与 incremental 两条逻辑 lane。截止时间之后的新上市、新财报、新公告和价格变化留给下一轮，不让当前 Goal 无限扩张。

## 角色

把主 Agent 当作巴菲特式投资经理，而不是任务转发器：

- 主 Agent亲自读取每个 manager-screen packet，并对整批公司使用同一把尺子判断。
- 初筛不派发子 Agent，不生成每家公司一份 Markdown，不做半盲 reviewer 递归纠错。
- 主 Agent 可以用程序生成压缩 dossier，也可对少数信息不足项补查一手来源；新增来源在整批提交中统一记录 provenance。
- 只有 `send_to_analyst` 才派发研究员；研究员一次一家公司，必须绑定原 manager-screen result 与决定性问题并提交有来源的 `decisive_answer`。
- 主 Agent 阅读研究员结果后配置下一层预算；underwriting、challenger 和 portfolio 必须分别显式批准，上游批准不自动授权下游。

## 不可违背的原则

1. 全覆盖、先看后筛。范围内每家公司必须出现在一次 manager-screen 决策中，或有经验证的证券身份硬排除。
2. 初筛行政顺序只使用冻结 intake ordinal、等待时间和已命中事件，不使用估值、因子、市值、流动性、利润正负、行业偏好或旧评级。
3. 每批必须由同一个主 Agent 完整覆盖，并严格按 packet 顺序提交 `pass | watch | send_to_analyst`。
4. `pass` 表示当前不值得继续买研究时间；`watch` 表示等待价格、财报、事件或证据；两者都必须有重启触发器。
5. `send_to_analyst` 同时完成初筛预算配置，不再增加独立 L1 allocation 层。
6. 初筛只做 contract 的 100% 程序校验。路由观点差异不是 material error，不触发 correction；禁止 correction 套 correction。
7. 历史不可覆盖。manager-screen 批次和后续单公司研究均封存；旧 Cycle 001/002 只读保留。
8. 单公司层不得输出组合操作或仓位。
9. 所有研究容量按同一 manager-screen run 守恒。超限整批拒绝，不能改写 Agent 路由，也不能靠新开 batch/cycle 扩容。
10. sealed snapshot、batch、result 和历史研究不可原地修订；行情只用 sealed amendment 追加，未记录错误批次只用 sealed supersession 释放。
11. 旧状态只通过一次性 legacy transition 明确 adoption、rescreen、defer_active；GC 只做只读计划，删除必须另行逐项确认。

## 未来 manager-screen decision contract v2 与恢复闸门

未来新冻结的 v2 batch 必须遵守：

- packet 的 `decision_support.canonical_fact_line` 是程序根据所绑定 snapshot 或 quote amendment 生成的规范事实对象。`one_line_reason` 必须以其中的 `.text` 加全角分号作为逐字、逐字符的精确前缀；前缀后的定性后缀不得手抄、重算、四舍五入或纠正数字。
- `decision_support.mandatory_risk_flags` 只是必须回应的风险候选，不自动决定 `pass`、`watch` 或 `send_to_analyst`。每个 flag 必须在 `risk_acknowledgements` 中明确标记 `material` 或 `not_material` 并解释；material 理由还必须进入 reason 定性后缀或 `decisive_question`。
- v2 quote-impact 必须为每个受影响 symbol 提交完整 replacement decision，不能只交 route 或 reason patch。即使 route 不变，也要使用新 amendment 生成的 canonical 市值事实刷新 reason 精确前缀，并完整重交风险回应、决定性问题、trigger、置信度和证据。
- replacement、calibration 和 adjudication 都只追加封存，不覆盖原 result，不连接成 correction 链。旧 sealed v1 batch、packet、result 与 quote-impact 资产保持原样，不改写成 v2。

本轮 manager-screen 仍为 `paused`。先完成 calibration；之后也只开放约 300 家受控续跑（默认约两个 150 家 batch），完成后再次暂停审计。只有 calibration 和受控续跑中的身份错误、期间错误、强风险遗漏均为 0，主 Agent 才能考虑全面恢复；这不是程序自动开闸。任一项非 0 时继续暂停，修复未来 contract 或在后续正式研究/至多一次显式裁决中处理，不生成 correction 套 correction。

## 启动与恢复

每次启动或续跑：

1. 完整读取根 `AGENTS.md`、本 Goal、相关 playbook、`policies/manager-screening.json`、Git 状态、冻结 scope 和当前 manager-screen status。
2. 若同一 `run_id` 已存在，不重新冻结范围；验证 seal 后从“冻结 intake 减去已冻结批次和已验证终态”恢复。
3. 已封存 result 但 coverage 未完整物化时，重放同一 `manager-screen-record` 修复；不得重做整批。
4. 保留用户和其他工作的改动，不切分支，除非用户要求。
5. 机制缺陷可以先修代码、测试和文档，再继续同一 scope；不得改变原始 cutoff。
6. 每个完整迭代验证后提交本轮自己修改的文件。
7. 先运行 `manager-screen-control-status` 读取 sealed run control；`paused` 时不得因“继续 Goal”而自动冻结或首次记录新生产 batch。`controlled` 必须读取 baseline、limit 和 remaining，受控续跑额度归零后必须追加新的 `paused` event。policy 要求 control 时，目录缺失不得按 active 处理。

## 执行阶段

### 1. 冻结范围

```bash
python -m trading_os coverage manager-screen-snapshot <run-id> \
  --information-cutoff <timestamp>
python -m trading_os coverage scope-freeze <run-id> --mode <mode> \
  --scope-cutoff <timestamp> \
  --universe-file coverage/cn-a/snapshots/<run-id>/companies.jsonl
python -m trading_os coverage scope-status <run-id>
```

验证：

```text
eligible + hard_excluded + exception = universe
```

snapshot 只压缩事实，不输出评分或路由。至少提供主营摘要、近三年收入/归母与扣非利润/
经营现金流、现金与有息债务、应收/存货/商誉/合同资产、审计意见、最新可得中期数据
以及明确的数据缺口。scope 必须绑定该 run 自己的 snapshot，不能依赖以后会变化的
`companies.jsonl`。

行情必须完整覆盖 universe，并记录 `quote_as_of`、来源和抓取时间；默认在 cutoff 时最多 72 小时、未来容忍 5 分钟，日期型 A 股收盘价按当日 15:00 解释，盘中价必须带时区。快照封存后不得覆盖；需要刷新时生成绑定原 snapshot 路径与 SHA-256 的 sealed quote amendment，再让后续 batch 显式绑定它。

证券身份硬排除做 100% 程序或人工身份校验。baseline 是缺少 manager-screen 或兼容 legacy terminal 的公司集合，不按旧 priority 推断。

### 2. 投资经理批量初筛

只有恢复闸门开放后才循环执行；本轮当前仍暂停：

```bash
python -m trading_os coverage manager-screen-control-status <run-id>
python -m trading_os coverage manager-screen-freeze <run-id> <batch-id> \
  --batch-size <manager_batch_size>
```

状态变更必须显式追加事件，例如受控续跑：

```bash
python -m trading_os coverage manager-screen-control-record <run-id> <event-id> \
  --state controlled --company-limit 300 \
  --manager-agent <agent> --manager-model <model> --manager-tool <tool> \
  --reason <reason> --at <timestamp>
```

读取生成的 `packet.json`。同一个主 Agent 对每家公司回答：

- 公司大致靠什么赚钱，普通股股东现金路径是否可理解；
- 是否存在明显生存、治理、资本结构或会计阻断；
- 正常化盈利和现金转换有没有可验证轮廓；
- 当前价格大致隐含什么；
- 下一小时最决定性的问题是什么；
- 当前应该 `pass`、`watch` 还是 `send_to_analyst`；
- 若不送研究员，什么条件会重启。

未来 v2 packet 中每个 symbol 都包含程序生成的 decision support，例如：

```json
{
  "decision_support": {
    "schema_version": 1,
    "canonical_fact_line": {
      "schema_version": 1,
      "text": "程序生成且绑定 snapshot/amendment 的规范事实行",
      "source_evidence_id": "snapshot:CN:000001",
      "latest_annual_report_date": "2025-12-31",
      "latest_annual_report_type": "年报",
      "latest_interim_report_date": "2026-06-30",
      "latest_interim_report_type": "中报",
      "latest_annual_deducted_parent_net_profit_cny": 100000000,
      "latest_annual_operating_cash_flow_cny": 120000000,
      "latest_interim_deducted_parent_net_profit_cny": 60000000,
      "market_cap_cny": 2000000000,
      "year_end_net_debt_cny": 300000000,
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
    },
    "mandatory_risk_flags": [
      {
        "flag_id": "capital_structure",
        "category": "capital_structure",
        "summary": "必须由投资经理回应的风险候选",
        "evidence_ids": ["snapshot:CN:000001"],
        "signals": ["liabilities_to_assets:above_policy_threshold"]
      }
    ]
  }
}
```

对应的 v2 提交文件 contract：

```json
{
  "schema_version": 1,
  "manager": {
    "agent": "/root",
    "model": "真实模型",
    "tools": ["真实工具"]
  },
  "additional_evidence": [],
  "decisions": [
    {
      "symbol": "CN:000001",
      "route": "pass",
      "one_line_reason": "程序生成且绑定 snapshot/amendment 的规范事实行；定性后缀只写判断，不手抄数字",
      "decisive_question": "最可能改变判断的问题",
      "risk_acknowledgements": [
        {
          "flag_id": "capital_structure",
          "assessment": "material",
          "reason": "该风险为何实质重要；同一理由已进入 reason 或决定性问题"
        }
      ],
      "revisit_triggers": [
        {
          "type": "filing",
          "condition": "下一份定期报告",
          "reason": "核验盈利和现金转换"
        }
      ],
      "confidence": "medium",
      "evidence_ids": ["snapshot:CN:000001"]
    }
  ]
}
```

`one_line_reason` 的开头必须与 packet 中该 symbol 的 `canonical_fact_line.text` 加全角分号精确相等，不能人工改标点、数字或期间；其余文字只能做定性判断。顶层提交仍是 schema v1，nested decision contract 由 sealed policy 的 `decision_contract_version=2` 判定。`risk_acknowledgements` 必须逐项覆盖 packet 的 mandatory flags，但 flag 是否 material 与最终 route 仍由主 Agent 统一判断。

```bash
python -m trading_os coverage manager-screen-record <run-id> <batch-id> \
  --input <decisions.json>
python -m trading_os coverage manager-screen-status <run-id>
```

程序必须验证整批完整覆盖、顺序、合法路由、证据引用、provenance、禁止字段和 seal。不得包含 rank、score、priority、`buy_now` 或仓位。

`send_to_analyst` 按 sealed policy 的 run 级容量原子记账：既有 sealed result 加本批申请超限时，整批在任何 result/coverage 写入前失败，不得由程序把候选改成 pass/watch。

未记录批次若因身份、行情或 packet 问题失效，主 Agent 应说明原因并封存 supersession；成员回到 remaining 后使用新 batch ID 重冻。已记录批次不可 supersede。

对 v2 batch 做 quote-impact 时，必须提交完整 replacement decision 并刷新 canonical 市值事实；route 可保持原值。对旧 sealed v1 batch 不做 v2 replacement，不借行情复核重写历史。

### 3. 单公司研究员

只派发 coverage 中 `task_type=quick_profile,status=pending,preceding_stage=manager_screen` 的公司。

研究员一次只处理一家公司，在 policy 的 1.5 小时默认预算内：

- 在 package 中逐字绑定 manager-screen result 路径、SHA-256、决定性问题和证据 ID，并提交引用自身 source ID 的 `decisive_answer`；
- 优先核验 S1 财报、公告和价格；
- 建立业务、会计、正常化所有者收益与估值的最小桥接；
- 写明反证、剩余未知和停止条件；
- 只提交自己的封存 package，不编辑共享 coverage。

主 Agent 阅读同层研究员结果后决定停止、定向补证或进入 scoped/deep research。不要为了填满容量而晋级。

### 4. 深研、承保与组合

```text
quick profile
→ scoped research（只解决定性未知）
→ deep research + 结构化主张与来源
→ 半盲独立承保
→ 必要 challenger / 仲裁
→ 最新价格下的组合综合
```

独立承保只购买给已完成深研、结构化主张和来源封存的少数公司；购买前由主 Agent 显式批准并占用该 run 的 underwriting 容量。重大事实分歧、高风险或潜在前五大仓位才进入 challenger，但仍需新的主 Agent 批准。组合综合也必须另行批准，underwriting approval 不授予 challenger 或 portfolio 预算。

### 5. 增量闭环

- filing/event/thesis 必须先有真实 hit，不能把触发器定义冒充事件已经发生。
- 同一 hit 可去重、可消费、可追溯。
- pass/watch 的重启条件保存在 manager-screen result 与 coverage；正式研究触发器继续进入 schedule/alerts。
- 截止时间之后的 hit 进入下一轮。

## 初筛质量机制

- 证券身份、schema、全量覆盖、顺序、证据 ID 和禁止字段：100% 程序校验。
- calibration 使用 policy 的确定性样本，独立 reviewer 必须完整覆盖，并分别封存 packet/result。material error 仅限证券身份、可核验事实、重大风险遗漏和 contract 违规；路由分歧单列，不阻塞 coverage，每家公司最多一次裁决，禁止 correction 链。
- 研究员若发现 material error，在其正式研究中显式指出并由主 Agent 一次裁决；不创建 correction cohort。
- 同一公司初筛不得出现 correction 套 correction。
- calibration 结束不等于全面恢复；先受控续跑约 300 家并重新审计。身份错误、期间错误和强风险遗漏必须全部为 0，才可由主 Agent 考虑解除 run 级暂停。

## Legacy transition 与资产清理

- 对旧 rapid-triage/正式研究状态先冻结完整人口，再由主 Agent 逐项分类：可验证正式研究采用 `adoption`，需回到普通初筛用 `rescreen`，仍在活动或更深阶段用 `defer_active`。旧 `price_watch`、priority 或 disposition 不得自动映射新路由。
- transition 的 plan、packet、result 均封存并守恒；adoption 还必须绑定正式报告/claims/meta，rescreen 只释放回 manager-screen，defer_active 保持当前任务。
- 仓库清理先生成只读 reachability plan。formal report、seal、coverage、run state、policy 及路径/SHA 引用均受保护；plan 的候选不是删除授权，必须另行逐项确认后才能执行破坏性动作。

## 完成判定

只有同时满足以下条件，Goal 才可完成：

1. scope 数量守恒；
2. 每个范围内 symbol 有 manager-screen terminal、兼容 legacy terminal 或硬排除；
3. 没有未解释的 pending/running/failed manager-screen 批次；
4. 所有 `send_to_analyst` 都得到明确终态，或如实列为 blocked；
5. 获得更深预算的公司完成相应研究、承保和必要 challenger；
6. 组合层使用最新行情，或明确给出当前无可买机会；
7. 截止时间后的事件已留给下一轮；
8. 验证通过，提交只含本 Goal 自己修改的文件。

至少执行：

```bash
python -m trading_os coverage manager-screen-status <run-id>
python -m trading_os coverage status
python -m trading_os coverage validate
python -m trading_os assets validate
python -m trading_os coverage reconcile --check
python -m trading_os index rebuild
python -m trading_os schedule build
python -m trading_os alerts build
ruff check <本次涉及的 Python 文件>
python -m pytest -q
git diff --check
```

## 最终交付

向用户报告 scope/cutoff、全市场初筛完成数与三条路由数量、送研究员比例、各层产出、主要阻断、承保/组合结果、耗时分布、验证和提交。不要只说“跑完了”，必须给出封存路径。

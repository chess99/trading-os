# Coverage Protocol

`coverage/` 是全市场范围冻结、批量初筛和研究任务编排层。它不保存完整公司研究结论，也不替代 `research/companies/`。

当前协议有两类事实源：

- `coverage/cn-a/scopes/`：冻结的普通 A 股范围、截止时间和 baseline intake；
- `coverage/cn-a/snapshots/`：每个 run 一份事实型压缩公司快照；
- `coverage/cn-a/manager-screen/`：投资经理整批初筛的不可变 `batch / packet / result`。

`companies.jsonl` 是全市场快照；`screening.jsonl` 与 `research_queue.jsonl` 是可恢复的共享状态投影，不取代上述封存事实源。

## 角色与边界

- 主 Agent 是投资经理。它读取一整批压缩 dossier，用同一把尺子判断全部公司。
- manager screen 默认每批 150 家；批次是上下文和恢复边界，不是晋级配额。
- 初筛不派发“一家公司一个 Agent”，也不为每家公司创建 Markdown 报告。
- 只有 `send_to_analyst` 才创建单公司 `quick_profile` 任务；研究员一次只处理一家公司。
- 独立承保、challenger 和组合综合只购买给完成深研的少数公司。
- 程序只校验身份、范围守恒、完整覆盖、顺序、证据引用和 contract；不得替投资经理生成投资分数或路由。

## 目录

```text
coverage/cn-a/
  companies.jsonl
  screening.jsonl
  research_queue.jsonl
  runs.jsonl
  snapshots/{RUN_ID}/
    companies.jsonl
  scopes/{RUN_ID}/
    manifest.json + seal
    baseline-intake.json + seal
  manager-screen/{RUN_ID}/{BATCH_ID}/
    batch.json + seal
    packet.json + seal
    result.json + seal
  profiles/
  triage/                         # legacy，只读兼容
```

一个尚未提交判断的 manager-screen 批次只有 4 个文件：`batch`、`packet` 及两个 seal。完成后增加 `result` 及其 seal，共 6 个文件。`pass` 和 `watch` 不再制造单公司报告、source manifest、quality packet 或 correction cohort。

## Manager screen 路由

- `pass`：当前不值得继续购买研究时间；物化为 `screening.decision=catalog` 和已完成的 `manager_screen` queue 行。
- `watch`：等待价格、财报、事件或关键证据；物化为更通用的 `screening.decision=watch_only`，不冒充纯价格判断。
- `send_to_analyst`：下一小时很可能改变判断；物化为 `quick_profile,status=pending,preceding_stage=manager_screen`。

`pass` 和 `watch` 必须留下至少一个结构化重启条件。三种路由都必须记录一句话理由、决定性问题、证据 ID、置信度和真实 Agent provenance。

禁止在 manager-screen submission 中出现 `rank`、`score`、`priority`、`portfolio_action`、`buy_now` 或仓位。小市值、低流动性、暂时亏损、负 PE 或行业冷门也不能成为静默跳过理由。

## 生产流程

1. `manager-screen-snapshot` 生成只含事实、不含机器路由的压缩公司快照。
2. `scope-freeze --universe-file ...` 绑定该快照并冻结 `scope_cutoff`、身份分区和 baseline intake。
3. `manager-screen-freeze` 按 intake ordinal 生成一批压缩 dossier；行政顺序不使用投资吸引力字段。
4. 同一个主 Agent 完整读取 packet，一次提交整批 `pass/watch/send_to_analyst`。
5. `manager-screen-record` 校验、封存 result，并在 coverage 写锁内物化状态。
6. runner 只派发 `send_to_analyst` 产生的少数 quick profile。
7. 主 Agent 根据研究员结果决定停止、定向补证或继续 scoped/deep research。
8. 深研完成后才进入半盲独立承保、必要 challenger 和组合综合。

路由观点差异是校准信号，不自动算作 material error。只有证券身份错误、可核验事实错误、重大风险遗漏或 decision contract 违规才需要显式更正；同一公司最多一次裁决，禁止 correction 套 correction。

## 恢复与幂等

- 同 batch ID、同 scope/policy/容量可重放；内容冲突时失败。
- 新 batch 自动排除已冻结、已完成、正在运行或已进入更深层的公司。
- result 已封存但共享状态写回中断时，重放同一 `manager-screen-record` 修复物化。
- 重放不得覆盖已经 running/completed 的 quick profile、scoped research 或 deep research，也不得把后续 screening 结论降级。
- manager terminal 必须同时绑定真实 result 路径、seal SHA、run、batch、symbol 和 route；缺少任一绑定不计入未来 scope 的有效终态。
- 单公司 Agent 不直接编辑共享 JSONL；正式 workflow 共用 `.coverage-write.lock`。

批次的 `frozen_at` 与 result 的 `recorded_at` 可用于计算初筛墙钟时间。研究任务继续使用 queue 的 `started_at/finished_at`；耗时汇报必须区分初筛、研究员研究、承保和组合阶段，不能用文件数量冒充进度。

## 命令

```bash
python -m trading_os coverage validate
python -m trading_os coverage status
python -m trading_os coverage get CN:600519

python -m trading_os coverage manager-screen-snapshot <run-id> --information-cutoff <timestamp>
python -m trading_os coverage scope-freeze <run-id> --mode auto --scope-cutoff <timestamp> \
  --universe-file coverage/cn-a/snapshots/<run-id>/companies.jsonl
python -m trading_os coverage scope-status <run-id>
python -m trading_os coverage manager-screen-freeze <run-id> <batch-id> --batch-size 150
python -m trading_os coverage manager-screen-record <run-id> <batch-id> --input <decisions.json>
python -m trading_os coverage manager-screen-status <run-id>

python -m trading_os coverage profile-claim --agent <agent-id> [--symbol CN:000000]
python -m trading_os coverage profile-release --agent <agent-id> --symbol CN:000000 --failure-reason <reason>
python -m trading_os coverage profile-status <cycle-id>
```

旧 `triage-*`、`quality-triage-*`、`allocate-research`、`apply-allocation` 和旧 `profile-finalize` 仅用于验证已封存历史资产，不是新 Goal 的生产入口。相关代码、模板、policy 和 Cycle 001/002 资产不能随意修改，否则会破坏历史 seal/hash。

## 与研究资产的关系

- manager-screen 的 `pass/watch` 只保存在批次和 coverage 投影中，不写公司正式时间线。
- 研究员开始正式工作后，新增报告、来源和结构化主张写入 `research/companies/{MARKET}/{TICKER}/`，不覆盖历史判断。
- `research/index.json`、`automation/review_schedule.json` 和 `automation/price_alerts.json` 仍从正式公司研究资产生成。
- 跨公司承保与组合事实源位于 `research/batches/` 和 `automation/runs/`。

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
- 只有 `send_to_analyst` 才派发研究员；研究员一次一家公司，只解决决定性问题。
- 主 Agent 阅读研究员结果后配置下一层预算；深研以后再调用独立承保与 challenger。

## 不可违背的原则

1. 全覆盖、先看后筛。范围内每家公司必须出现在一次 manager-screen 决策中，或有经验证的证券身份硬排除。
2. 初筛行政顺序只使用冻结 intake ordinal、等待时间和已命中事件，不使用估值、因子、市值、流动性、利润正负、行业偏好或旧评级。
3. 每批必须由同一个主 Agent 完整覆盖，并严格按 packet 顺序提交 `pass | watch | send_to_analyst`。
4. `pass` 表示当前不值得继续买研究时间；`watch` 表示等待价格、财报、事件或证据；两者都必须有重启触发器。
5. `send_to_analyst` 同时完成初筛预算配置，不再增加独立 L1 allocation 层。
6. 初筛只做 contract 的 100% 程序校验。路由观点差异不是 material error，不触发 correction；禁止 correction 套 correction。
7. 历史不可覆盖。manager-screen 批次和后续单公司研究均封存；旧 Cycle 001/002 只读保留。
8. 单公司层不得输出组合操作或仓位。

## 启动与恢复

每次启动或续跑：

1. 完整读取根 `AGENTS.md`、本 Goal、相关 playbook、`policies/manager-screening.json`、Git 状态、冻结 scope 和当前 manager-screen status。
2. 若同一 `run_id` 已存在，不重新冻结范围；验证 seal 后从“冻结 intake 减去已冻结批次和已验证终态”恢复。
3. 已封存 result 但 coverage 未完整物化时，重放同一 `manager-screen-record` 修复；不得重做整批。
4. 保留用户和其他工作的改动，不切分支，除非用户要求。
5. 机制缺陷可以先修代码、测试和文档，再继续同一 scope；不得改变原始 cutoff。
6. 每个完整迭代验证后提交本轮自己修改的文件。

## 执行阶段

### 1. 冻结范围

```bash
python -m trading_os coverage scope-freeze <run-id> --mode <mode> --scope-cutoff <timestamp>
python -m trading_os coverage scope-status <run-id>
```

验证：

```text
eligible + hard_excluded + exception = universe
```

证券身份硬排除做 100% 程序或人工身份校验。baseline 是缺少 manager-screen 或兼容 legacy terminal 的公司集合，不按旧 priority 推断。

### 2. 投资经理批量初筛

循环执行：

```bash
python -m trading_os coverage manager-screen-freeze <run-id> <batch-id> \
  --batch-size <manager_batch_size>
```

读取生成的 `packet.json`。同一个主 Agent 对每家公司回答：

- 公司大致靠什么赚钱，普通股股东现金路径是否可理解；
- 是否存在明显生存、治理、资本结构或会计阻断；
- 正常化盈利和现金转换有没有可验证轮廓；
- 当前价格大致隐含什么；
- 下一小时最决定性的问题是什么；
- 当前应该 `pass`、`watch` 还是 `send_to_analyst`；
- 若不送研究员，什么条件会重启。

提交文件 contract：

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
      "one_line_reason": "一句话理由",
      "decisive_question": "最可能改变判断的问题",
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

```bash
python -m trading_os coverage manager-screen-record <run-id> <batch-id> \
  --input <decisions.json>
python -m trading_os coverage manager-screen-status <run-id>
```

程序必须验证整批完整覆盖、顺序、合法路由、证据引用、provenance、禁止字段和 seal。不得包含 rank、score、priority、`buy_now` 或仓位。

### 3. 单公司研究员

只派发 coverage 中 `task_type=quick_profile,status=pending,preceding_stage=manager_screen` 的公司。

研究员一次只处理一家公司，在 policy 的 1.5 小时默认预算内：

- 解决 manager-screen 的决定性问题；
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

独立承保只购买给已完成深研的少数公司。重大事实分歧、高风险或潜在前五大仓位才触发 challenger。

### 5. 增量闭环

- filing/event/thesis 必须先有真实 hit，不能把触发器定义冒充事件已经发生。
- 同一 hit 可去重、可消费、可追溯。
- pass/watch 的重启条件保存在 manager-screen result 与 coverage；正式研究触发器继续进入 schedule/alerts。
- 截止时间之后的 hit 进入下一轮。

## 初筛质量机制

- 证券身份、schema、全量覆盖、顺序、证据 ID 和禁止字段：100% 程序校验。
- 可选校准抽样只估计事实错误和重大遗漏，不阻塞正常批次，不按 reviewer 路由差异计算错误率。
- 研究员若发现 material error，在其正式研究中显式指出并由主 Agent 一次裁决；不创建 correction cohort。
- 同一公司初筛不得出现 correction 套 correction。

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

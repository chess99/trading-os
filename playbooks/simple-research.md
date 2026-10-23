# 财报周期研究流程

## 系统边界

Trading OS 只按财报周期维护完整公司研究。政策、新闻、订单、治理或资本事件不在周期中途生成报告、update 或 stale 状态；研究者在下一周期统一吸收信息截止前的重要事实。

唯一例外是用户明确认为某份报告有错误或质量不足，此时创建 `manual_rewrite`，完整覆盖同一周期并重新验收。

## 状态与任务

证券范围：`active / inactive`。

公司研究状态：

- `unseen`：尚无基础判断；
- `ignore`：没有完成报告，或最近周期结论为不持续覆盖；
- `covered`：最近周期结论为持续覆盖。

状态不表达“今天是否仍有效”。报告始终按财报周期和信息截止阅读。

任务状态只使用 `queued / running`，触发类型只使用：

- `periodic`：动态重点跟踪池的新财报周期；
- `manual_rewrite`：用户显式要求的同周期完整重写。

同一公司最多一个活动任务。

## 周期排期

财报季由协调器读取当时的 `screening/{cn-a|hk|us}/value-quality/pool.json`：

```bash
python -m trading_os research enqueue-period --period 2026-Q3
```

命令只为缺少目标槽位的池内公司创建任务；已有槽位自动跳过。池成员退出不会删除报告，进入后可以从最新可用周期开始。

周期名称只允许：

```text
YYYY-FY
YYYY-Q1
YYYY-H1
YYYY-Q3
```

## 人工同周期重写

报告事实错误、模型错误或表达质量不达标时，用户可以显式要求重写：

```bash
python -m trading_os research enqueue-rewrite \
  --period 2026-H1 --batch-id manual-2026-10 \
  --input <公司及具体原因.json>
```

人工重写只接受公司最新且已经存在的周期槽位，不用来补建新周期，也不由新闻自动触发。

## 单公司完整研究

研究者与协调器完整阅读[统一深研提示词](../prompts/company/standard-deep-research.md)和[核验附录](../prompts/company/research-verification.md)。先独立形成长期商业判断，再用财务、必要资本、普通股归属和估值检验，最后编辑成结论先行、自足可读的完整文章。

派发使用[单公司任务简报](../prompts/company/research-task-brief.md)：每家公司启动不继承协调对话的新上下文，研究者可以继续修订本公司候选，但完成后不接手下一家公司。任务中不携带目标估值或对话式示范文案；前次报告在独立判断与初步模型形成后用于复盘。协调器继续承担既有验收职责，不新增研究角色。

结果只有 `covered / ignore`。worker 返回结构化候选；协调器完成商业判断、事实、模型和表达验收后，才通过 `research complete` 写入：

```text
research/companies/{CN|HK|US}/{ticker}/reports/YYYY-{FY|Q1|H1|Q3}.md
```

同周期覆盖，跨周期新增。候选未通过验收时直接丢弃，不写文件、不推进 `basis_report_path`。

有前次周期报告时，正文保留简洁的“前次假设—本期实际—判断变化—估值影响”复盘。不得用“详见前序报告”跳过商业、财务、估值或风险正文。

## 事实与模型验收

协调器至少确认：

- 累计、报告期单季、上年同期和上一季度口径清楚；
- 关键旧假设与本期事实完成比较，并解释偏差原因；
- 全文只有一套信息截止和一致结论；
- 关键原始数字、普通股归属、股本和估值重新核验；
- 两种估值方法可复算并指定主次；
- 五年分配、未来终值、现金/权益桥和完全稀释股数一致；
- 正文核心价值区间与结构化 `value_range` 一致；
- 当前价值没有被复制成第五年终值；
- 已分配现金、金融资产、债务、少数权益和资本投入没有重复计价。

机械校验不替代商业判断。关键证据错误、普通股归属不清、重复计价或无法复算，不能靠流畅文字通过。

## 商业判断与表达验收

1. 找出决定性商业问题，抽查关键原表和上下文，区分公司自述与独立证据。
2. 检查“竞争机制 → 经营表现 → 必要资本 → 普通股现金”最薄弱的一环。
3. 检查最强相反解释和可比对象，不能以行业标签代替机制。
4. 确认关键前瞻判断进入了成长、利润、资本回报、现金归属或终值参数。
5. 对可估计的未知形成有依据的范围；决定性路径无法约束时允许 `null`。
6. 删除估值表后，读者仍应理解为什么值得或不值得长期拥有。

实质复核按核验附录的五项成品检查执行。关键假设应有可追溯的证据与替代解释，模型独立复算核心端点和支配性参数；正文删除聊天、任务、验收与内部接口旁白。普通股现金、资料边界和必要风险说明保留。返工反馈明确问题和通过条件，不指定估值方向。

## 标准写入

协调器完成上述实质验收后调用 `research complete`。该命令按[现行研究展示标准](../research/standards/README.md)自动把 active standard 写入最新周期状态，不再追加独立登记。同周期重写必须重新完成完整验收，随后一次覆盖报告、结构化结果和标准信息。

## 唯一事实源

- `coverage/cn-a/research_state.jsonl`：证券和最近完成周期的研究状态；
- `coverage/cn-a/research_queue.jsonl`：当前周期及人工重写任务；
- `research/companies/{CN|HK|US}/{ticker}/reports/`：财报周期完整报告；
- `screening/{cn-a|hk|us}/value-quality/pool.json`：动态重点跟踪池。

共享 JSONL 只由协调器原子写入。每轮写入后执行：

```bash
python -m trading_os validate
node dashboard/scripts/report-standards.mjs validate
```

港美股使用 `research --market hk|us enqueue-latest --input disclosures.json` 按已披露财务期末预览排期。财年、证券单位与币种要求见[跨市场补充](../prompts/company/cross-market.md)。

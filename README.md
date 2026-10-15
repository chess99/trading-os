# Trading OS

Trading OS 是一套按财报周期维护 A 股长期研究的轻量工作流。主要产品是动态重点跟踪池、完整公司报告及其结构化模型；网站只是只读展示。系统不做自动交易，也不因价格、政策、新闻或单项公告在周期中途启动研究。

## 核心机制

1. 价值质量筛选从全市场维护一个可增删、可调整 A/B 分层的重点跟踪池。
2. 财报季使用 `research enqueue-period`，只为当时池内公司创建缺失的 `FY / Q1 / H1 / Q3` 周期槽位。
3. 一家公司由一个研究者按统一规范端到端完成；正式结论只有 `covered / ignore`。
4. 同周期重新研究时覆盖原文件并重新验收；只有进入下一财报周期才新增文件。
5. 政策、新闻、订单、治理和资本事件不建立 update、不标记 stale，也不创建中途报告；下一周期研究统一吸收截止日前的重要事实。
6. 用户认为报告有错误或质量不足时，使用 `research enqueue-rewrite` 显式创建同周期人工重写任务。
7. 报告保存五年为主的持有人模型输入；网页把实时价格作为唯一动态输入机械求解 IRR，不写回仓库，也不形成交易信号。

单公司研究使用[主提示词](prompts/company/standard-deep-research.md)和[核验附录](prompts/company/research-verification.md)。先形成长期商业判断，再检验财务、必要资本、普通股归属、估值和持有人现金。报告结论先行、自足可读，不把核心推理委托给旧周期。

## 研究分层

| 层 | 回答的问题 | 入口与结果 |
|---|---|---|
| 动态重点跟踪池 | 哪些公司值得持续投入完整研究？ | [质量池规范](prompts/screening/cn-a-value-quality.md)，`pool.json` |
| 财报周期排期 | 本季哪些池内公司尚缺完整报告？ | `research enqueue-period --period ...` |
| 单公司研究 | 商业经济学、当前价值和条件现金回报如何？ | [完整深研](prompts/company/standard-deep-research.md)，周期报告 |
| 协调验收 | 正文、证据、模型和结构化结果是否一致？ | [验收流程](playbooks/simple-research.md)，acceptance |
| 产业知识 | 利润由谁创造、谁取得，如何跨公司验证？ | [产业框架](research/industries/README.md) |
| 长期精选 | 哪些更值得长期拥有和等待？ | [精选原则](selection/principles.md)、[当前精选](selection/current.md) |

## 唯一事实源

```text
coverage/cn-a/research_state.jsonl                         全市场证券与最近完成周期的研究状态
coverage/cn-a/research_queue.jsonl                         当前 periodic / manual_rewrite 任务
research/companies/CN/{代码}/reports/YYYY-{FY|Q1|H1|Q3}.md 财报周期完整报告
screening/cn-a/value-quality/pool.json                      动态重点跟踪池
screening/cn-a/value-quality/current.md                     由当前池确定性生成的可读投影
research/standards/registry.json                            现行研究标准
research/standards/acceptances/{代码}/{周期}.json           周期报告验收登记
```

`basis_report_path` 和 `report_period` 只绑定结构化状态所依据的最新周期报告，不宣称报告在今天仍然“有效”。每份报告按自身财报周期、信息截止和研究标准阅读。`covered / ignore` 是该周期的研究结论，不是事件驱动状态。

公司状态只使用：

- `unseen`：尚无全市场基础判断；
- `ignore`：没有完成报告，或最近完成周期结论为不持续覆盖；
- `covered`：最近完成周期结论为持续覆盖。

证券范围另用 `active / inactive`；任务只用 `queued / running`，触发类型只用 `periodic / manual_rewrite`。

## 财报周期报告

研究结果必须显式提交 `report_period`：

- `YYYY-FY`：年度报告周期；
- `YYYY-Q1`：一季报周期；
- `YYYY-H1`：中报周期；
- `YYYY-Q3`：三季报周期。

同周期重写覆盖同一文件并重新验收，Git 保存自然修改历史，但产品不提供旧修订入口。跨周期报告并存，研报库默认打开最新周期并允许切换其他周期。

财报更新必须重新形成完整报告，区分累计、单季、同比和环比口径，复盘前次关键假设，并重新核验股本、普通股归属、正常化经营、估值和模型。不能把新财报摘录拼接到旧正文。

每份新结果都必须包含非空 `return_model_note`；能可靠建模时同时提交 `return_model`，否则为 `null` 并说明决定性缺口。五年模型包括未来五项每股实际现金分配和独立第五年终值；三年终值可选，但必须独立研究。

## 动态重点跟踪池

价值质量池只回答哪些公司值得持续研究，不表达买入、仓位或当前估值。池成员和 A/B 分层可随筛选变化：退出不删除历史报告，进入后可从最新财报周期开始排期。

```bash
python -m trading_os quality-pool status
python -m trading_os quality-pool validate
python -m trading_os quality-pool list --tier core_moat
python -m trading_os quality-pool replace --input <完整池.json>
```

## 常用命令

```bash
# 校验
python -m trading_os status
python -m trading_os validate

# 为当前动态重点跟踪池创建下一财报周期任务；已有槽位自动跳过
python -m trading_os research enqueue-period --period 2026-Q3

# 领取与完成
python -m trading_os research next --limit 4 --trigger-kind periodic
python -m trading_os research start <task_id>
python -m trading_os research complete --input <已验收完整候选.json>

# 用户明确要求同周期重写
python -m trading_os research enqueue-rewrite \
  --period 2026-H1 --batch-id manual-2026-10 \
  --input <公司及具体原因.json>
python -m trading_os research next --limit 4 --trigger-kind manual_rewrite
```

人工重写输入示例：

```json
{
  "at": "2026-10-15T12:00:00+08:00",
  "reason": "报告质量复核后需要完整重写",
  "companies": [
    {"symbol": "CN:000001"},
    {"symbol": "CN:000002", "reason": "关键普通股现金桥存在错误"}
  ]
}
```

[研究结果模板](templates/research-result.json)只演示字段合同，身份、数字、假设和来源均须替换并完成实际研究。

## 可视化研究台

`dashboard/` 从仓库确定性生成。默认范围是动态重点跟踪池；“最新周期模型”只展示最新依据报告中通过现行兼容标准验收的结构化结果。非最新周期只阅读正文，不加载现价或参与排序。

实时行情仅用于把现价与报告冻结的 `value_range`、`return_model` 机械比较。行情缺失或公式无法求解时显示 `—`；这些派生值不触发研究，也不是交易建议。

```bash
cd dashboard
npm install
npm run dev
```

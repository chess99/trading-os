# Trading OS

Trading OS 是覆盖A股、港股与美股的价值投资研究工作台。个股研究关注长期股东现金、资本配置与价格；行业研究解释供需、竞争和利润归属；宏观与市场研究提供周期、资金条件及估值参照。研究成果低频积累，网页用于检索、比较和阅读。

整体结构与取舍见[工作台设计](docs/design/investment-workbench.md)，报告更新方式见[发布与阅读规则](research/README.md)。

## 公司研究核心机制

1. 价值质量筛选从全市场维护一个可增删、可调整 A/B 分层的重点跟踪池。
2. 财报季使用 `research enqueue-period`，只为当时池内公司创建缺失的 `FY / Q1 / H1 / Q3` 周期槽位。
3. 一家公司由一个研究者按统一规范端到端完成；正式结论只有 `covered / ignore`。
4. 同周期重新研究时覆盖原文件并重新验收；只有进入下一财报周期才新增文件。
5. 政策、新闻、订单、治理和资本事件不建立 update、不标记 stale，也不创建中途报告；下一周期研究统一吸收截止日前的重要事实。
6. 用户认为报告有错误或质量不足时，使用 `research enqueue-rewrite` 显式创建同周期人工重写任务。
7. 报告保存五年为主的持有人模型输入；网页把实时价格作为唯一动态输入机械求解 IRR，不写回仓库，也不形成交易信号。

单公司研究使用[主提示词](prompts/company/standard-deep-research.md)和[核验附录](prompts/company/research-verification.md)。先形成长期商业判断，再检验财务、必要资本、普通股归属、估值和持有人现金。报告结论先行、自足可读，不把核心推理委托给旧周期。

## 研究板块

| 板块 | 留存成果 | 入口 |
|---|---|---|
| 个股研究 | 商业质量初筛、完整财报周期研报与模型 | [初筛规范](prompts/screening/cn-a-value-quality.md)、[公司深研](prompts/company/standard-deep-research.md) |
| 行业研究 | 细分行业的历史、现状、竞争、前景与重要历史版本 | [行业研究规范](prompts/industry-research.md) |
| 宏观与市场 | 主题报告、必要的环境综述、指标与方法 | [宏观研究规范](prompts/macro-research.md) |

个股研究保留初筛和完整深研两个层次。行业与宏观采用主题及重要时点报告，季度复核不强制产出。日常市场观察仅保留[执行规范](prompts/daily-market-observation.md)，每日结果在仓库外使用。

## 唯一事实源

```text
coverage/cn-a/research_state.jsonl                         全市场证券与最近完成周期的研究状态
coverage/cn-a/research_queue.jsonl                         当前 periodic / manual_rewrite 任务
research/companies/CN/{代码}/reports/YYYY-{FY|Q1|H1|Q3}.md 财报周期完整报告
screening/cn-a/value-quality/pool.json                      动态重点跟踪池
screening/cn-a/value-quality/current.md                     由当前池确定性生成的可读投影
research/standards/registry.json                            公司研究展示标准
research/publications.json                                 行业、宏观报告与方法的发布目录
research/{industries|macro}/{主题}/reports/YYYY-MM-DD.md     重要时点的完整报告
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

## 跨市场公司池

研究台的「公司池」视图提供A股、港股、美股的商业质量池，可按市场、行业、层级和关键问题检索。列表用于横向比较，详情提供经营指标、年度资本回报、竞争优势、股东现金与反证。A/H等同一发行人的不同证券在全部市场视图合并计数。

港美股采用 [v3筛选合同](prompts/screening/international-value-quality.md)，保留完整的范围内取舍、每项指标的期间和公开来源。A股v2数据保持兼容。初筛结果用于确定研究对象，公司报告与估值由财报周期研究流程维护。

```bash
python -m trading_os quality-pool --market hk status
python -m trading_os quality-pool --market us validate
```

默认市场为 `cn-a`。各市场JSON保存于 `screening/{cn-a|hk|us}/value-quality/`，`current.md`由维护命令生成。研究状态、排期、研报和行情按市场隔离。港美股排期以已披露财报为依据，见[跨市场研究补充](prompts/company/cross-market.md)。

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

`dashboard/` 从仓库确定性生成。默认范围是动态重点跟踪池；“最新周期模型”只展示最新依据报告中按现行兼容标准完成的结构化结果。`research complete` 会把当时标准写入研究状态，不另建验收文件。非最新周期只阅读正文，不加载现价或参与排序。

实时行情仅用于把现价与报告冻结的 `value_range`、`return_model` 机械比较。行情缺失或公式无法求解时显示 `—`；这些派生值不触发研究，也不是交易建议。

```bash
cd dashboard
npm install
npm run dev
```

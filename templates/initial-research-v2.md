<!-- trading-os-report-meta
{
  "schema_version": 2,
  "report_id": "{REPORT_ID}",
  "report_type": "initial_research",
  "symbol": "{MARKET:TICKER}",
  "as_of": "YYYY-MM-DD",
  "information_cutoff": "ISO8601_WITH_OFFSET",
  "price_snapshot_id": null,
  "policy_versions": {
    "research-allocation.default": "1.0.0",
    "underwriting.default": "2.0.0"
  },
  "agent_id": "{TOOL_AND_MODEL}",
  "predecessor_reports": [],
  "sealed_artifacts": ["evidence/{REPORT_ID}-research-claims.json"],
  "source_manifest": "evidence/{REPORT_ID}-sources.json"
}
-->
# 公司研究：{名称}（{MARKET:TICKER}）

## 结论版

只给初步研究判断、关键不确定性和是否值得进入独立承保；不得给组合操作或仓位。

## 业务理解

解释客户、产品、收入和利润来源、资本强度及长期经济模型。

## 行业与竞争格局

说明行业结构、周期位置、供需、竞争者、替代风险和经济风险簇。

## 公司质量

分析护城河、治理、管理层、资本配置和可证伪的竞争优势。

## 财务质量

核对利润与现金流、资本回报与资本成本、杠杆、稀释和会计脆弱性。

## 结构化主张

同时生成并封存 `research-claims.json`：每条主张必须有 `claim_id`、类别、验证指标、证伪条件和来源 ID。结论字段只用于后续半盲脱敏，不写入公司状态。

## 估值

使用至少两种适合行业的方法，避免单点目标值和周期峰值利润直接外推。

## 市场隐含预期

反推当前价格隐含的增长、利润率、资本回报和持续期。

## 情景与赔率

列出悲观、基准、乐观三情景及永久资本损失风险。

## 关键假设

列出可跟踪、可证伪的关键假设。

## 跟踪触发器

使用 date、filing、event、thesis 或 price 的结构化触发器。

## 风险

主动寻找至少三条反方证据，不把风险章节写成免责声明。

## 来源

关键财务数字必须由 S1 一手来源支持。

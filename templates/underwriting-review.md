<!-- trading-os-report-meta
{"schema_version":2,"report_id":"{REPORT_ID}","report_type":"underwriting_review","symbol":"{MARKET:TICKER}","as_of":"YYYY-MM-DD","information_cutoff":"ISO8601_WITH_OFFSET","price_snapshot_id":"{SNAPSHOT_ID}","policy_versions":{"underwriting.default":"2.0.0"},"agent_id":"{TOOL_AND_MODEL}","predecessor_reports":["{REPORT_ID}"],"sealed_artifacts":["underwriting/{REVIEW_ID}/blind-assessment.json","underwriting/{REVIEW_ID}/reveal-assessment.json"],"source_manifest":"evidence/{REVIEW_ID}-sources.json"}
-->
# 公司研究：{名称}（{MARKET:TICKER}）

## 承保结论

只输出 passed、failed、insufficient_evidence、needs_challenger 或 stale；公司层不得输出组合操作和仓位。

## 证据账本

列出 claim、period、原始/调整口径、来源等级、定位、获取时间、交叉核验和复核结果。

## 盈利质量桥

## 现金流桥

## 正常化盈利

禁止单季利润乘四和周期峰值利润直接估值。

## 估值与敏感性

至少两种方法、悲观/基准/乐观三情景、可复算公式、必要回报率和安全边际。明确 `safety_margin_tier`，并说明风险进入正常化盈利、情景、折现率或风险覆层的具体位置，避免重复折价。

## 市场隐含预期

## 反方证据

至少三条主动寻找的反方证据。

## 旧主张差异审计

盲态结果封存后才揭示；逐条标为 confirmed、weakened、disproven 或 untested。

## 自动阻断检查

列出所有会计、现金流、正常化、证据新鲜度和估值硬闸门。

## 失效条件

明确财报、价格、行业驱动和论点失效条件。

## 来源

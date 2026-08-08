<!-- trading-os-report-meta
{
  "schema_version": 2,
  "report_id": "CN-000007-2026-07-30-rapid-triage-06ac6a733da8",
  "report_type": "rapid_triage",
  "symbol": "CN:000007",
  "as_of": "2026-07-30",
  "information_cutoff": "2026-07-30T03:03:20+08:00",
  "price_snapshot_id": "eastmoney-kline-000007-20260729",
  "policy_versions": {
    "rapid-triage-contract": "2.0.0"
  },
  "agent_id": "/root/triage_000007; gpt-5.6-sol; repository rg and sealed source locator extraction, PowerShell Invoke-RestMethod, Eastmoney public announcement API, Eastmoney public historical quote API, Chrome browser",
  "predecessor_reports": [],
  "sealed_artifacts": [
    "evidence/CN-000007-2026-07-30-rapid-triage-06ac6a733da8-sources.json"
  ],
  "source_manifest": "evidence/CN-000007-2026-07-30-rapid-triage-06ac6a733da8-sources.json"
}
-->
# 公司研究：全新好（CN:000007）

## 快速结论

本次为 `baseline_recheck`。研究价值粗判为 `low`，估值信号为 `unattractive`。本报告只分配后续研究预算，不构成买入、卖出或仓位结论。

## 业务速览

公司收入来自汽车销售与服务、物业租赁及管理、日用品贸易和医药医疗器械销售。2025年收入约3.96亿元，其中汽车销售与服务约3.29亿元且毛利率仅约3.49%；业务可理解但组合多变、协同弱，主要利润来源不稳定。

## 变化摘要

相对2026-07-10既有研究，7月14日半年度业绩预告新增确认2026H1归母净亏损225万至337万元、扣非净亏损164万至246万元，汽车竞争和物业盈利下滑并未改善；7月29日收盘9.16元，较7月10日10.85元回落约15.6%，但截至截止时点公告列表未出现可验证重大重组或资产注入，估值矛盾仍在。

## 正常化盈利粗判

2025年归母净利润仅约193万元、扣非约327万元；2026Q1归母亏损217万元，H1继续预亏。2025年和2026Q1经营现金流分别明显为正是重要反证，但现金流受业务周转和合并范围变化影响，不能把一次性营运资金释放等同于可持续所有者收益；正常化盈利目前更接近微利至小幅亏损。

## 市场隐含预期

9.16元乘以约3.4645亿股对应市值约31.7亿元，约为2026Q1末归母净资产1.791亿元的17.7倍；2025年微利和2026H1预亏无法提供常规盈利估值支撑。当前价格要求市场相信公司能通过新主业、资本运作或资产质量跃迁取得远高于现有经营资产的回报，但截至截止时点没有可验证方案。

## 反方证据

- 2025年经营活动现金流净额约3.60亿元、2026Q1约8318万元，显示短期现金流并非持续恶化。
- 大华会计师事务所对2025年财务报表出具标准无保留意见，内部控制审计认为财务报告内控在重大方面有效。
- 2026Q1营业收入同比增长29.72%，新增合并易联医疗扩大收入基础。
- 2025年归母及扣非利润均为正，公司一季末归母净资产仍为正，尚无退市或持续经营硬阻断。

## 重启触发器

- `filing` / `2026h1-report-filed`：核验经营现金流的形成、汽车和医药板块毛利、物业收入、应收存货短债以及实际担保余额，重算正常化所有者收益。；条件 `{"description": "公司披露2026年半年度报告"}`
- `event` / `verified-capital-transaction`：当前价格主要只能由经营外跃迁解释；仅有传闻不构成触发。；条件 `{"description": "公司正式披露重大资产重组、控制权变化或有审计财务数据的资产注入方案"}`
- `thesis` / `cash-earnings-conversion`：该组合证据才可能否定现有主营缺乏稳定所有者收益的判断。；条件 `{"description": "连续两个报告期扣非盈利且经营现金流为正，同时汽车和医药毛利改善、短债与实际担保余额不恶化"}`
- `price` / `price-lte-3`：价格较9.16元下降约67%后重新核验资产、现金流和治理；触发只代表重开研究，不代表买入。；条件 `{"operator": "price_lte", "threshold": 3.0}`
- `date` / `routine-90d-refresh`：若其他事件未先发生，90天后检查财报、担保、监管整改及公告变化。；条件 `{"due_at": "2026-10-28T03:03:20+08:00", "origin": "ttl"}`

## 来源

- [S1] 深圳市全新好股份有限公司2025年年度报告（issuer-annual-2025-000007）：https://np-cnotice-stock.eastmoney.com/api/content/ann?art_code=AN202604281821686638&client_source=web&page_index=1
- [S1] 深圳市全新好股份有限公司2026年第一季度报告（issuer-q1-2026-000007）：https://np-cnotice-stock.eastmoney.com/api/content/ann?art_code=AN202604281821686643&client_source=web&page_index=1
- [S1] 全新好2026年半年度业绩预告（issuer-h1-forecast-20260714-000007）：https://np-cnotice-stock.eastmoney.com/api/content/ann?art_code=AN202607141826955483&client_source=web&page_index=1
- [S1] 全新好关于公司及子公司2026年度对外担保预计额度的公告（issuer-guarantee-plan-20260611-000007）：https://np-cnotice-stock.eastmoney.com/api/content/ann?art_code=AN202606111823459238&client_source=web&page_index=1
- [S1] 全新好关于深圳证监局责令改正措施的整改报告（issuer-remediation-20260107-000007）：https://np-cnotice-stock.eastmoney.com/api/content/ann?art_code=AN202601071816760808&client_source=web&page_index=1
- [S2] 全新好公告列表（截止2026年7月30日03:03）（eastmoney-ann-list-000007-20260730）：https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=50&page_index=1&ann_type=A&client_source=web&stock_list=000007
- [S2] 东方财富全新好历史行情（2026年7月29日完整收盘）（eastmoney-kline-000007-20260729）：https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.000007&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&beg=20260720&end=20260730

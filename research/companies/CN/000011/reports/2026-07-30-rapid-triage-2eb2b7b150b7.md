<!-- trading-os-report-meta
{
  "schema_version": 2,
  "report_id": "CN-000011-2026-07-30-rapid-triage-2eb2b7b150b7",
  "report_type": "rapid_triage",
  "symbol": "CN:000011",
  "as_of": "2026-07-30",
  "information_cutoff": "2026-07-30T03:03:20+08:00",
  "price_snapshot_id": "eastmoney-daily-quote-20260729",
  "policy_versions": {
    "rapid-triage-contract": "2.0.0"
  },
  "agent_id": "/root/triage_000011; GPT-5; repository, PowerShell.Invoke-RestMethod, PowerShell.Invoke-WebRequest, pdfplumber, Poppler.pdftoppm, view_image",
  "predecessor_reports": [],
  "sealed_artifacts": [
    "evidence/CN-000011-2026-07-30-rapid-triage-2eb2b7b150b7-sources.json"
  ],
  "source_manifest": "evidence/CN-000011-2026-07-30-rapid-triage-2eb2b7b150b7-sources.json"
}
-->
# 公司研究：深物业A（CN:000011）

## 快速结论

本次为 `baseline_recheck`。研究价值粗判为 `high`，估值信号为 `unattractive`。本报告只分配后续研究预算，不构成买入、卖出或仓位结论。

## 业务速览

公司以产城空间开发、物业管理和产业生态运营为主。2025年物业管理收入16.37亿元、占营收68.70%，在管面积超过4800万平方米；房地产收入5.67亿元、占23.79%，产业生态运营收入1.79亿元、占7.52%。物业服务提供相对经常性收入，但资产负债表和利润仍显著受房地产项目结转、去化与存货可变现净值影响。

## 变化摘要

本次按新协议重建基线：2025年归母净利润3388.51万元但扣非归母净利润亏损1238.64万元，经营现金流净流出20.86亿元；2026年一季度归母净利润亏损2723.52万元、经营现金流净流出2.73亿元。公司随后预告2026年上半年归母净利润亏损6900万元、扣非亏损7340万元，原因是房地产结转项目毛利率下降。7月23日至24日A股连续异动，公司核查称经营环境未发生重大变化且无应披露未披露事项。

## 正常化盈利粗判

当前无法给出正的可靠正常化所有者收益。2025年扣非归母已为-1238.64万元，2026年一季度扣非归母为-2815.71万元，半年扣非预告扩大至-7340万元；同时开发投入、税款和项目结算令经营现金流持续为负。物业管理收入占比高可能形成底盘，但快速甄别无法从合并披露中分离其真实利润和现金转化，最大误差来自项目交付毛利、存货减值及土地增值税时点。

## 市场隐含预期

7.82元相当于2026年一季末归母净资产约5.65元/股的约1.38倍，且过去四个交易日曾因连续涨停出现异常波动；在核心盈利转负、存货占总资产约74%、公司明确无未披露重大事项的情况下，价格要求市场相信项目去化和毛利迅速修复、物业管理价值被重估，或同业竞争解决带来资产运作。现有一手证据不足以支持这些预期，赔率暂不成立。

## 反方证据

- 2025年物业管理收入16.37亿元、占总营收68.70%，在管面积超过4800万平方米；若分部利润和现金转化显著优于合并口径，稳定服务业务可能被低估。
- 2025年审计意见和内部控制审计均为标准无保留意见，审计报告未提示持续经营重大不确定性，且深圳市投资控股有限公司持股50.87%，融资可得性可能强于普通民营开发商。
- 2026年一季末合同负债由年初7.12亿元升至7.82亿元，房地产结转收入在上半年同比上升；后续交付和回款可能改善利润与经营现金流。
- 控股股东对城建集团、深深房同业竞争解决方案的承诺期限分别为2026年10月19日和11月9日，若按期形成对上市公司有利的资产注入、出售或划转方案，可能改变资产价值判断。

## 重启触发器

- `date` / `2026-h1-report-review`：公司公告预计在2026年8月29日披露半年报；届时核验业绩预告、分部毛利、存货减值、项目去化、经营现金流和一年内到期债务。；条件 `{"date": "2026-08-29"}`
- `price` / `price-at-or-below-q1-book`：A股价格回落至接近2026年一季末每股归母净资产约5.65元时，资产折价赔率可能重新成立，但仍需同步复核存货可变现净值和融资。；条件 `{"operator": "price_lte", "threshold": 5.7}`
- `event` / `controller-competition-resolution`：同业竞争解决方式会直接改变少数股东可归属资产、治理判断和潜在NAV。；条件 `{"description": "控股股东或公司披露城建集团、深深房同业竞争解决的资产注入、出售、托管、股权划转方案，或再次变更承诺期限。"}`

## 来源

- [S1] 深物业A：2025年年度报告（cninfo-2025-annual-report）：https://static.cninfo.com.cn/finalpage/2026-03-28/1225045283.PDF
- [S1] 深物业A：2026年第一季度报告（cninfo-2026-q1-report）：https://static.cninfo.com.cn/finalpage/2026-04-29/1225227130.PDF
- [S1] 深物业A：2026年半年度业绩预告（cninfo-2026-h1-forecast）：https://static.cninfo.com.cn/finalpage/2026-07-15/1225422736.PDF
- [S1] 深物业A：股票交易异常波动公告（cninfo-2026-abnormal-volatility）：https://static.cninfo.com.cn/finalpage/2026-07-25/1225440400.PDF
- [S2] 东方财富深物业A前复权日线行情（截至2026-07-29收盘）（eastmoney-daily-quote-20260729）：https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.000011&klt=101&fqt=1&lmt=10&end=20260730&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61

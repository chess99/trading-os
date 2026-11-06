# 跨市场公司研究补充

商业、估值和验证要求沿用统一深研提示词与核验附录。跨市场研究还需明确财报日历、证券权利和现金单位。

## 财报槽位

`YYYY-FY / Q1 / H1 / Q3`中的年份为发行人财年标签，第二季度累计资料使用H1。每个周期保留完整报告，同周期重研更新原文件，跨周期保留前期文件。

按实际已披露的财务期末选择最新资料。已经披露第三季度结果的采用Q3；尚无季度结果的采用最新半年或年度资料。非自然年公司不能按自然月猜槽位，例如6月结束的财年可以在7月已有当年FY资料。年度结果比旧季度新时，不能退回旧半年。

港股主板的年度、中期与自愿季度披露须按公司实际情况核验；美股也包含采用不同申报制度的外国发行人。公告摘要、完整财务结果和单项经营数字分别辨认，只有足够支撑完整研究的周期财务资料才作为依据。

## 结构化依据

港美股任务和结果必须含：

```json
{"financial_basis":{"period_end":"2026-06-30","published_on":"2026-07-29","source_url":"https://example.com/financial-results"}}
```

示例仅演示字段，不构成真实披露记录。正文同时写明`财务期末：YYYY-MM-DD`与`财报披露：YYYY-MM-DD`，并保留独立的信息截止。历史阅读因此能确认实际覆盖期间。

结果中的`security_basis`保存`currency`（CNY/HKD/USD）、`unit`（ordinary_share/ADS/share_class）、`ordinary_shares_per_unit`和公开`source_url`。每股估值、分配、未来终值和行情必须对应同一上市证券单位及币种。财务报告币种不同的，研究中说明换算依据和敏感性；展示层不默认为两种币种等价。

A/H、ADR与股份类别可以复用经过核验的经营事实。股本、权利、税费、跨境分配及单位桥须逐证券明确，不机械复制另一证券的每股估值。ADS比例必须有原始披露依据。

## 排期

披露输入为`{"disclosures":[{"symbol":"US:...","report_period":"2026-FY","financial_basis":{...}}]}`。先预览，再执行：

```bash
python -m trading_os research --market us enqueue-latest --input disclosures.json
python -m trading_os research --market us enqueue-latest --input disclosures.json --apply
python -m trading_os --market us validate
```

无披露依据的公司列入缺口，不按预计发布日期自动排队。已存在槽位与活动任务跳过；相近期末的冲突记录须先明确版本。下一周期报告使用“前次假设—本期实际—判断变化—估值影响”复盘，前期原文继续保留在原槽位。

参考：[香港交易所财务披露要求](https://www.hkex.com.hk/Listing/Explore-By-Role/Listed-Issuers/Equity-Securities?sc_lang=en)、[SEC EDGAR披露](https://www.sec.gov/edgar/search/)。

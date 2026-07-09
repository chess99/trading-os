# Follow-up Review Playbook

Use this playbook when a company has already been researched and a trigger asks for a new review.

## Boundary

Review exactly one company. Read the previous latest_report before doing new research.

## Process

1. Read `meta.json`.
2. Read the previous `latest_report`.
3. Extract the prior key assumptions, valuation range, buy zone, position plan, and follow-up triggers.
4. Gather new filings, announcements, earnings, industry data, price movement, and relevant news since the prior report.
5. Classify each prior key assumption as confirmed, weakened, disproven, or still untested.
6. Decide whether the rating, valuation range, buy zone, position plan, or triggers should change.
7. Write a new timestamped report under `reports/`.
8. Include a `Previous Thesis Review` section.
9. Update `meta.json` with the latest state and new report pointer.
10. Rebuild the repository index and automation files.

## Miller-Style Follow-up Discipline

- Re-read the prior thesis as a business-value claim, not just a price target.
- Classify each prior key assumption as confirmed, weakened, disproven, still untested, or only affected by short-term sentiment.
- Re-check whether the latest price changes the market implied expectations: is the market making a temporary problem permanent, or making growth too certain?
- Re-underwrite free cash flow, capital returns versus cost of capital, management capital allocation, and accounting quality before changing buy zones or adding exposure.
- Price weakness alone is not a reason to average down. Add only if core business value is intact and the probability/odds improved.
- Sell or reduce only when valuation is reached/exceeded, opportunity cost is better elsewhere, or the investment logic has changed.
- Keep short-term volatility separate from permanent capital loss risk.

## Output Rules

- Write the report in Chinese unless the user explicitly requests another language.
- Use the standard report header exactly:
  `# 公司研究：{name}（{MARKET:TICKER}）`, `日期：YYYY-MM-DD`,
  `研究类型：followup`, and `分析师：actual tool + model`.
- Never replace the previous report.
- The new report must explicitly name the previous latest_report.
- The new report must explain what changed.
- If nothing material changed, write that conclusion plainly and keep the metadata stable.
- New reports must include these H2 sections: `结论版`, `业务理解`,
  `行业与竞争格局`, `公司质量`, `财务质量`, `估值`, `市场隐含预期`,
  `情景与赔率`, `价格与仓位计划`, `关键假设`, `跟踪触发器`, `风险`,
  `上一轮判断复盘`, and `来源`.
- New `meta.json` updates should use only the fields defined in
  `templates/meta.schema.json`; keep current prices and source notes in the
  Markdown report, not extra metadata fields.
- Before handing off a new company asset, run
  `python -m trading_os company validate <company-dir> --strict`.

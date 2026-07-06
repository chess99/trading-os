# Company Research Playbook

Use this playbook when researching one company from scratch.

## Boundary

Research exactly one company. Do not edit another company directory. Do not overwrite existing reports.

## Inputs

- Company identifier in `MARKET:TICKER` format.
- Company directory under `research/companies/{MARKET}/{TICKER}/`.
- Optional user question or focus area.

## Process

1. Confirm whether the security is a listed common stock, private company exposure, fund, receipt, or synthetic exposure.
2. Gather primary sources first: exchange filings, annual reports, interim reports, company investor materials, official announcements, and prospectuses.
3. Gather credible secondary sources: industry reports, regulator data, reputable financial media, and analyst summaries.
4. Understand the business before valuation: products, customers, pricing, margins, sales channels, suppliers, and capital intensity.
5. Evaluate industry structure: market size, growth, concentration, substitution, regulation, and cycle position.
6. Evaluate company quality: moat, management, governance, capital allocation, competitive advantage, and failure modes.
7. Evaluate financial quality: growth, margin durability, cash conversion, leverage, dilution, and accounting quality.
8. Build a valuation range with explicit assumptions.
9. Define buy zone, reduce zone, maximum position size, and price-to-position rules.
10. Define follow-up triggers: earnings dates, filing dates, product milestones, regulatory events, price levels, and thesis validation points.
11. Write a new report under `reports/YYYY-MM-DD-slug.md`.
12. Update `meta.json` so `latest_report` points to the new report and `report_history` includes it.

## Output Rules

- Reports are immutable research snapshots.
- Do not overwrite existing reports.
- Do not edit a historical report to change the judgment.
- If a prior report was wrong, write a new report explaining the error.
- Keep `meta.json` concise and machine-readable.
- Keep the full reasoning in Markdown.

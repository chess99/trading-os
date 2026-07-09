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

## Miller-Style Value Discipline

Use low valuation multiples as clues, not conclusions. High PE/PB/PS is not an automatic exclusion either. First understand the long-term business model, then decide whether today's price is below intrinsic business value.

- Treat value as the present value of future free cash flow, not as a static accounting multiple.
- Explain whether growth creates value by earning capital returns above the cost of capital.
- Reverse-read the market price: state what revenue growth, margin, free cash flow, capital return, and duration the current price appears to imply.
- Use multi-factor valuation to find a central tendency: relative multiples, cash-flow methods, asset/private-market references, transaction references, and history where relevant.
- Frame scenarios as probability and odds: downside permanent capital loss risk, base case value, upside payoff, and whether the payoff compensates for uncertainty.
- Treat accounting data and models as fragile. Check one-off items, capitalized expenses, working capital, M&A accounting, leverage, cyclically inflated earnings, and management-adjusted numbers.
- Do not mechanically average down. Re-underwrite the thesis after a price drop; add only if business value is intact and the odds improved.
- Sell or reduce because valuation is reached/exceeded, a better risk-reward opportunity appears, or the original thesis changes, not because of price movement alone.

## Output Rules

- Write the report in Chinese unless the user explicitly requests another language.
- Reports are immutable research snapshots.
- Do not overwrite existing reports.
- Do not edit a historical report to change the judgment.
- If a prior report was wrong, write a new report explaining the error.
- Keep `meta.json` concise and machine-readable.
- Keep the full reasoning in Markdown.

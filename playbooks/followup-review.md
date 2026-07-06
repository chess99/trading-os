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

## Output Rules

- Write the report in Chinese unless the user explicitly requests another language.
- Never replace the previous report.
- The new report must explicitly name the previous latest_report.
- The new report must explain what changed.
- If nothing material changed, write that conclusion plainly and keep the metadata stable.

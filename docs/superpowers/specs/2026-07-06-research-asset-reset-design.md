# Research Asset Reset Design

Date: 2026-07-06

## Goal

Rebuild the repository around durable company research assets instead of the old
recipe-heavy research workflows.

The new system treats each research report as an immutable timestamped record.
Automation reads lightweight machine-readable metadata, while humans and agents
read the Markdown research timeline.

## Context

Before this reset, the repository was centered on `ResearchStore`, `DataHub`,
CANSLIM/Elder/Value skills, daily recipes, run manifests, watchlists, and historical
artifacts. That removed architecture was useful for deterministic screening and
evidence-chain recipes, but the new direction is different:

- The repository's main asset should be the research result itself.
- A company can be researched repeatedly over time.
- Each research run should remain reviewable as a historical judgment.
- A lightweight metadata layer should drive indexing, batch assignment, price alerts,
  and scheduled follow-up.
- Old workflows and old artifacts should be removed on the reset branch. Historical
  material remains available through git history, not through migrated archives.

## Recommended Approach

Use a Markdown plus index architecture.

Each company directory contains:

- Immutable Markdown reports under `reports/`.
- One mutable `meta.json` file containing current machine-readable state.
- Optional source attachments under `sources/` when a research run needs structured
  evidence capture.

Repository-level automation generates `research/index.json` from all company
`meta.json` files. Agents and scripts should not hand-edit the generated index.

This keeps the research reports expressive and readable while giving automation a
small, stable surface.

## Alternatives Considered

### Markdown-only

This keeps everything human-readable, but automation would need to parse prose to
find ratings, buy zones, review dates, and price triggers. That is brittle and makes
batch operations harder to audit.

### SQLite-first

This makes querying easy, but it turns research into database entry. It also makes
the most important asset less visible in git diffs. This project should optimize for
agent-readable research history, not for a normalized financial database.

### Markdown plus metadata index

This is the selected approach. Markdown remains the source of investment reasoning.
`meta.json` holds current state and trigger definitions. `research/index.json` is
derived from metadata for fast automation.

## Repository Shape

The reset branch should converge on this structure:

```text
research/
  companies/
    {MARKET}/{TICKER}/
      meta.json
      reports/
        2026-07-06-initial.md
        2026-08-31-h1-review.md
      sources/
        2026-07-06/
          sources.json
  index.json

playbooks/
  company-research.md
  followup-review.md
  batch-dispatch.md
  price-alert.md

automation/
  review_schedule.json
  price_alerts.json

templates/
  company-report.md
  meta.schema.json

src/trading_os/
  cli.py
  research_assets/
    __init__.py
    company.py
    index.py
    alerts.py
    schedule.py
```

Old `data/research/runs/`, old `artifacts/research/`, old `skills/`, old recipe
implementations, and old strategy/backtest/paper machinery are not part of the new
first version. They should be removed from the reset branch unless a small utility is
explicitly reintroduced for the new asset workflow.

## Company Asset Model

Each company is identified by a stable symbol in the form:

- `{MARKET}:{TICKER}`

The filesystem path uses market and raw ticker placeholders:

- `research/companies/{MARKET}/{TICKER}/`

### Immutable Reports

Every research run creates a new Markdown file:

```text
reports/YYYY-MM-DD-slug.md
```

Examples:

- `reports/2026-07-06-initial.md`
- `reports/2026-08-31-h1-review.md`
- `reports/2026-10-28-q3-review.md`
- `reports/2027-01-15-price-trigger-review.md`

Rules:

- Existing reports are not overwritten.
- Existing reports are not retroactively edited to change the investment judgment.
- Corrections are made by writing a new report that explicitly references the previous
  report and explains what changed.
- Each follow-up report includes a section named `Previous Thesis Review`.

### Mutable Metadata

Each company has exactly one `meta.json`. It represents the current machine-readable
state, not the full research argument.

Required fields:

```json
{
  "symbol": "TEST:000001",
  "market": "TEST",
  "ticker": "000001",
  "name": "Example Company",
  "currency": "USD",
  "status": "active",
  "current_rating": "watch",
  "current_thesis": "High-quality cash compounder, but buy only with sufficient margin of safety.",
  "fair_value_range": [1150, 1450],
  "buy_zone": [1000, 1100],
  "sell_or_reduce_zone": [1500, 1800],
  "position_plan": [
    {"condition": "price <= 1150", "max_weight": 0.05},
    {"condition": "price <= 1000", "max_weight": 0.12}
  ],
  "latest_report": "reports/2026-07-06-initial.md",
  "report_history": ["reports/2026-07-06-initial.md"],
  "review_triggers": [
    {
      "type": "date",
      "date": "2026-08-31",
      "reason": "Review after semiannual report."
    }
  ],
  "price_triggers": [
    {
      "type": "price_below",
      "price": 1100,
      "reason": "Enter initial buy zone."
    }
  ],
  "updated_at": "2026-07-06T00:00:00+08:00"
}
```

Allowed `current_rating` values:

- `buy`
- `watch`
- `hold`
- `avoid`
- `sell`
- `research_only`

Allowed `status` values:

- `active`
- `inactive`
- `archived`

`meta.json` is updated after every new report so that automation can read the latest
state without parsing Markdown.

## Report Template

Company reports should be written as investment memos, not as scraped data dumps.

Required sections:

```markdown
# Company Research: {Name} ({Symbol})

Date: YYYY-MM-DD
Research Type: initial | followup | earnings_review | price_trigger_review
Analyst: agent

## One-line Conclusion

## Decision

## Business Understanding

## Industry and Competitive Context

## Company Quality

## Financial Quality

## Valuation

## Price and Position Plan

## Key Assumptions

## Follow-up Triggers

## Risks

## Previous Thesis Review

## Sources
```

For an initial report, `Previous Thesis Review` states that no previous report exists.
For every later report, it names the prior `latest_report` and evaluates whether the
prior assumptions were confirmed, weakened, or disproven.

## Research Playbooks

Playbooks are prompts and operating procedures for future agents. They are not code.

### `playbooks/company-research.md`

Defines how a single-company research agent should work:

- Confirm the security identifier and whether it is public, private, fund-like, or a
  synthetic exposure.
- Gather primary sources first: filings, company investor materials, exchange filings,
  official announcements, and credible industry reports.
- Build a business model view before valuation.
- Identify industry structure, competitive position, management quality, unit economics,
  capital intensity, and key risks.
- Produce a valuation range, buy zone, sell/reduce zone, and position plan.
- Create one immutable Markdown report and update only `meta.json`.

### `playbooks/followup-review.md`

Defines how an agent reviews a prior thesis:

- Read `meta.json`.
- Read the previous `latest_report`.
- Check every previous key assumption.
- Gather new filings, news, earnings, price movement, and industry data since the prior
  report.
- Write a new report with `Previous Thesis Review`.
- Update current rating, valuation, triggers, and latest report pointer in `meta.json`.

### `playbooks/batch-dispatch.md`

Defines the batch model:

- One subagent researches exactly one company.
- A subagent writes only inside that company directory.
- The main agent assigns companies, reviews output quality, rebuilds the index, and
  commits completed batches.
- Failed research runs should create no partial company report unless the failure itself
  is a useful research artifact.

### `playbooks/price-alert.md`

Defines price monitoring semantics:

- Price triggers are alerts, not automatic trades.
- A price trigger creates a review task or notification.
- The follow-up agent must re-check the thesis before changing a rating or position plan.

## Automation

The first version should include lightweight deterministic scripts only.

### Index Generation

`research/index.json` is generated from all company `meta.json` files.

It includes:

- symbol
- name
- market
- rating
- fair value range
- buy zone
- latest report
- next date trigger
- active price triggers
- updated timestamp

Generation must fail if any `meta.json` is invalid.

### Review Schedule

`automation/review_schedule.json` is derived from company metadata. It lists upcoming
date-based review triggers.

### Price Alerts

`automation/price_alerts.json` is derived from company metadata. It lists active price
triggers. The CLI can read a supplied quote snapshot and report triggered symbols.

The first implementation may use manually supplied quote snapshots. Live quote provider
integration is not required for the reset foundation.

## CLI

Keep the CLI small.

Recommended commands:

```bash
python -m trading_os index rebuild
python -m trading_os company validate <company-dir>
python -m trading_os alerts build
python -m trading_os schedule build
python -m trading_os alerts check --quotes <quote-snapshot.json>
```

The CLI should not perform investment research itself. Research is done by agents using
playbooks; the CLI validates and indexes assets.

## Data Flow

Initial research:

1. Main agent selects a company.
2. Company research agent follows `playbooks/company-research.md`.
3. Agent creates `reports/YYYY-MM-DD-slug.md`.
4. Agent creates or updates `meta.json`.
5. Main agent validates the company directory.
6. Main agent rebuilds `research/index.json`.
7. Main agent commits the company asset.

Follow-up research:

1. Trigger is found from schedule, price alert, earnings date, filing date, or user request.
2. Agent reads `meta.json`.
3. Agent reads the previous `latest_report`.
4. Agent writes a new timestamped report.
5. Agent updates `meta.json` latest pointers, rating, valuation, and triggers.
6. Main agent rebuilds index and automation files.

Price alert:

1. Script reads generated price trigger list.
2. Script compares trigger definitions with quote input.
3. Script emits triggered alerts.
4. Human or agent starts a follow-up research run before any trade decision.

## Error Handling

Validation errors should be explicit:

- Missing `meta.json`.
- Invalid symbol format.
- `latest_report` path does not exist.
- `report_history` contains missing files.
- `fair_value_range`, `buy_zone`, or `sell_or_reduce_zone` has the wrong shape.
- `position_plan` has an unparseable condition.
- `review_triggers` contain invalid dates.
- `price_triggers` contain missing price fields.

Index generation should be all-or-nothing. If one company is invalid, the command exits
non-zero and does not replace the previous `research/index.json`.

Research quality errors are handled by review, not by schema:

- A report with weak sourcing should be rejected by the main agent before commit.
- A report that does not contain a valuation or position plan should not update
  `latest_report`.
- A follow-up report that does not review the previous thesis should be rejected.

## Testing Strategy

Core tests:

- Validate a correct company directory.
- Reject missing `latest_report`.
- Reject invalid rating values.
- Reject malformed price triggers.
- Rebuild an index from two valid companies.
- Keep previous index unchanged when one company is invalid.
- Build review schedule from date triggers.
- Build price alert list from price triggers.
- Detect triggered alerts from a supplied quote snapshot.

Documentation tests:

- Report template contains all required sections.
- Playbooks explain the immutable report rule.
- README states that old workflows were removed and research assets are the new source
  of truth.

No test should require real market data or network access.

## Migration and Deletion Policy

This reset branch intentionally does not migrate old artifacts.

Delete from the working tree during implementation:

- Old research run artifacts.
- Old human research artifacts.
- Old workflow skills.
- Old deterministic research recipes.
- Old data-provider machinery unless a small helper is explicitly reused.
- Old backtest, paper trading, and strategy modules.

Retain only what serves the new asset workflow:

- Project metadata such as `pyproject.toml`.
- Minimal package entry points.
- New research asset code.
- New tests.
- New playbooks and templates.
- New docs describing the reset model.

Historical material remains accessible through git history.

## Non-goals

- No live trading.
- No automatic order execution.
- No full-market intraday scanner in the first reset.
- No database as the primary research store.
- No migration of old artifacts into the new research tree.
- No attempt to fully automate research judgment inside deterministic scripts.

## First Implementation Scope

The first implementation should build the foundation only:

- Delete old workflow code and old artifacts from the reset branch.
- Add the new directory structure.
- Add `meta.schema.json`.
- Add report and playbook templates.
- Add validator and index builder.
- Add schedule and price alert builders.
- Add example company assets for the three already discussed companies only if the user
  approves seeding them into the new system.

Batch subagent orchestration can remain a playbook in the first implementation. Tooling for
automatic subagent dispatch can be added after the asset model proves useful.

## Seed Policy

The first implementation should not seed example company assets by default. This keeps the
reset focused on the asset model, validator, index, templates, and automation files.

The following real companies are not present in the baseline reset. If the user
explicitly asks to seed initial examples, use these three recent research cases:

- `HK:09660` Horizon Robotics
- `CN:600519` 贵州茅台
- `US:SPCX` SpaceX

Seeded reports must be rewritten into the new report template rather than copied from chat
transcripts verbatim.

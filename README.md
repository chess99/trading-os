# Trading OS

Trading OS is a research asset repository.

The primary asset is the company research timeline under `research/companies/`.
Each research run creates a new immutable Markdown report. Each company also has one
mutable `meta.json` file for current rating, valuation range, buy zone, position plan,
follow-up triggers, and price alerts.

## Structure

```text
research/
  companies/
    {MARKET}/{TICKER}/
      meta.json
      reports/
  index.json

coverage/
playbooks/
templates/
automation/
src/trading_os/research_assets/
```

## Rules

- Do not overwrite historical reports.
- Write company research reports in Chinese unless explicitly requested otherwise.
- For broad A-share work, use `coverage/` to screen first and record skipped-company reasons.
- Update `meta.json` after each accepted research report.
- Rebuild `research/index.json` from metadata.
- Use price alerts as review triggers, not automatic trades.
- Old recipe workflows, provider pipelines, backtests, and artifacts are not part of this reset.

## Commands

```bash
python -m trading_os company validate <company-dir>
python -m trading_os index rebuild
python -m trading_os schedule build
python -m trading_os alerts build
python -m trading_os alerts check --quotes <quote-snapshot.json>
python -m trading_os coverage status
python -m trading_os coverage validate
```

## Research Workflow

For a new company, follow `playbooks/company-research.md`.

For a follow-up review, follow `playbooks/followup-review.md`.

For batch research, follow `playbooks/batch-dispatch.md`.

For full-market screening before research, follow `playbooks/screening.md` and the
schemas under `coverage/cn-a/`.

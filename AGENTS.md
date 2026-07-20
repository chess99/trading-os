# Trading OS Agent Guide

This repository is a research asset repository. The source of truth is the company
research timeline under `research/companies/`.

## Core Model

- Every research run creates a new immutable Markdown report.
- Existing reports must not be overwritten to change a past judgment.
- `meta.json` is the only mutable company state file.
- `research/index.json`, `automation/review_schedule.json`, and `automation/price_alerts.json`
  are generated files.
- `coverage/` is the pre-research coverage layer. It records universe snapshots,
  screening decisions, research queues, skipped-company reasons, and long-running
  batch state before any company receives a full research report.

## Company Directory

```text
research/companies/{MARKET}/{TICKER}/
  meta.json
  reports/
    YYYY-MM-DD-slug.md
  sources/
```

## Agent Rules

- For broad A-share work, screen through `coverage/` first to assign priority,
  risk labels, and resumable queue state. The default policy is to research as
  many ordinary A-share companies as practical; do not use small size, low
  liquidity, or temporary losses as hard skip reasons.
- Follow `playbooks/screening.md` before creating large research queues.
- Research one company per agent unless the user explicitly asks for synthesis.
- Read the previous `latest_report` before writing a follow-up.
- Write a new report for every new research run.
- Write company research reports in Chinese unless the user explicitly asks for another language.
- Update `meta.json` only after the report is complete.
- After a company asset passes validation, update its matching coverage queue item
  to `completed` and set `result_path` to `meta.json.latest_report`.
- At the end of a parallel research batch, run `coverage reconcile --check`.
  Review any drift before using `coverage reconcile --apply`; reconciliation is a
  batch safety net, not a replacement for updating the queue in the worker.
- Run validation and rebuild generated files before committing.
- Record skipped companies with structured reasons instead of silently dropping them.
  Use `skip_*` sparingly for hard exclusions such as delisting or out-of-scope
  securities.
- Do not revive old recipe, DataHub, CANSLIM, Elder, Value, backtest, or paper-trading workflows.

## Commands

```bash
python -m trading_os company validate <company-dir>
python -m trading_os index rebuild
python -m trading_os schedule build
python -m trading_os alerts build
python -m trading_os alerts check --quotes <quote-snapshot.json>
python -m trading_os coverage status
python -m trading_os coverage validate
python -m trading_os coverage reconcile --check
python -m trading_os coverage reconcile --apply
```

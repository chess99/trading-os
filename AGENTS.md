# Trading OS Agent Guide

This repository is a research asset repository. The source of truth is the company
research timeline under `research/companies/`.

## Core Model

- Every research run creates a new immutable Markdown report.
- Existing reports must not be overwritten to change a past judgment.
- `meta.json` is the only mutable company state file.
- `research/index.json`, `automation/review_schedule.json`, and `automation/price_alerts.json`
  are generated files.

## Company Directory

```text
research/companies/{MARKET}/{TICKER}/
  meta.json
  reports/
    YYYY-MM-DD-slug.md
  sources/
```

## Agent Rules

- Research one company per agent unless the user explicitly asks for synthesis.
- Read the previous `latest_report` before writing a follow-up.
- Write a new report for every new research run.
- Write company research reports in Chinese unless the user explicitly asks for another language.
- Update `meta.json` only after the report is complete.
- Run validation and rebuild generated files before committing.
- Do not revive old recipe, DataHub, CANSLIM, Elder, Value, backtest, or paper-trading workflows.

## Commands

```bash
python -m trading_os company validate <company-dir>
python -m trading_os index rebuild
python -m trading_os schedule build
python -m trading_os alerts build
python -m trading_os alerts check --quotes <quote-snapshot.json>
```

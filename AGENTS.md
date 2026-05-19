# Trading OS Agent Guide

This repository is operated primarily by Claude Code / Codex agents. Read this file before running workflows or changing behavior.

## Daily Workflow

Daily research is scheduler-driven. Do not manually stitch together `fetch-ak-bulk`, `scan-elder`, `scan-canslim`, and `pool status` to produce a daily report.

Default commands:

```bash
python -m trading_os scheduler status
python -m trading_os scheduler jobs --limit 20
python -m trading_os daily
```

If `daily` produces `artifacts/daily/YYYYMMDD-blocked.md`, stop there. Report the blocker and do not make market, stock, entry, exit, or watchlist conclusions from incomplete data.

Manual scheduler triggers are for diagnosis or repair only:

```bash
python -m trading_os scheduler trigger market_data_probe
python -m trading_os scheduler trigger market_data_bulk_refresh --effective-date YYYY-MM-DD
python -m trading_os scheduler trigger full_scan_and_daily --effective-date YYYY-MM-DD
```

`python -m trading_os scheduler run` is a long-running service entrypoint. Check scheduler status before starting it.

## Date Semantics

`daily` uses the latest complete market data date as the effective date; it is not necessarily the wall-clock date.

Scanner `--date` means signal date. `DataPipeline` excludes same-day bars for lookahead protection, so scheduler handles the effective-date to signal-date conversion. Do not bypass that conversion when running the daily workflow.

## Data Access

Do not read parquet files directly for analysis or data correction. Use `LocalDataLake` APIs or `python -m trading_os` commands so compact/dedup layers and lookahead protections remain active.

## Claude Skills

Claude Code workflow instructions live under `.claude/skills/`. For daily work, the source of truth is:

- `.claude/skills/daily-workflow/SKILL.md`

Keep `AGENTS.md`, `.claude/CLAUDE.md`, `README.md`, and relevant skill files aligned when workflow semantics change.

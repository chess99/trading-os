# Claude Guide

Read `AGENTS.md` first. It is the source of truth for this repository.

Important routing:

- Use `coverage/` and `playbooks/screening.md` before broad A-share research.
  Screening is for priority, risk labels, and resumable queue state; the default
  A-share policy is research-as-much-as-practical, not aggressive exclusion.
- Prefer `python -m trading_os coverage ...` for JSONL coverage updates instead of
  hand-editing large files.
- Use `research/companies/` only for accepted company research assets.
- Write company research reports in Chinese unless the user explicitly asks otherwise.
- Do not revive legacy trading, backtest, recipe, CANSLIM, DataHub, or paper-trading workflows.

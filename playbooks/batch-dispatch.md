# Batch Dispatch Playbook

Use this playbook when a main agent assigns many companies to subagents.

## Operating Model

- One subagent researches exactly one company.
- A subagent writes only inside that company's directory.
- Company research reports should be written in Chinese unless the user explicitly asks otherwise.
- The main agent owns assignment, review, index rebuild, and commits.
- Failed runs should leave no partial report unless the failure analysis is itself useful.
- For large A-share batches, prefer `automation/scripts/batch_research.py`. It sends
  each Claude worker a self-contained prompt from `automation/scripts/_worker_prompt.md`,
  so the worker does not need to read repository instructions or playbooks.
- The batch script must run a Claude probe before dispatch unless the operator passes
  `--skip-claude-probe`. The probe verifies that Claude can both write a file and emit
  a machine-readable result.
- If a worker times out after writing a valid company asset, the dispatcher may salvage
  the result by validating the company directory and marking the queue item completed.

## Main Agent Steps

1. Prepare a company list with market, ticker, name, and research reason.
2. For broad A-share work, require the list to come from `coverage/` screening results.
3. Dispatch one company per subagent.
4. Require each subagent to follow `playbooks/company-research.md` or `playbooks/followup-review.md`.
5. Review every generated report for sourcing, valuation, position plan, and trigger quality.
6. Reject reports that read like data dumps or lack a decision.
7. Run `python -m trading_os company validate <company-dir>` for each company.
8. Run `python -m trading_os index rebuild`.
9. Run `python -m trading_os schedule build`.
10. Run `python -m trading_os alerts build`.
11. Commit only reviewed company assets, generated indexes, and generated automation files.

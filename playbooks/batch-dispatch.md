# Batch Dispatch Playbook

Use this playbook when a main agent assigns many companies to subagents.

## Operating Model

- One subagent researches exactly one company.
- A subagent writes only inside that company's directory.
- The main agent owns assignment, review, index rebuild, and commits.
- Failed runs should leave no partial report unless the failure analysis is itself useful.

## Main Agent Steps

1. Prepare a company list with market, ticker, name, and research reason.
2. Dispatch one company per subagent.
3. Require each subagent to follow `playbooks/company-research.md` or `playbooks/followup-review.md`.
4. Review every generated report for sourcing, valuation, position plan, and trigger quality.
5. Reject reports that read like data dumps or lack a decision.
6. Run `python -m trading_os company validate <company-dir>` for each company.
7. Run `python -m trading_os index rebuild`.
8. Run `python -m trading_os schedule build`.
9. Run `python -m trading_os alerts build`.
10. Commit only reviewed company assets, generated indexes, and generated automation files.

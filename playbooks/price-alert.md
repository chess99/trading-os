# Price Alert Playbook

Use this playbook when price reaches a level defined in company metadata.

## Rule

Price alerts are review triggers, not trade instructions.

## Process

1. Read the triggered alert.
2. Read the company's `meta.json`.
3. Read the previous `latest_report`.
4. Verify the current price from a reliable market source.
5. Check whether the business thesis changed since the prior report.
6. Write a new price-trigger review report when the trigger is material.
7. Update `meta.json` only after the new research judgment is complete.

## Output

The output is a new Chinese research report and updated metadata. It is not an automatic order.

import assert from "node:assert/strict";
import test from "node:test";
import { compareOpportunityRanks } from "../app/lib/opportunity-sort.mjs";

function row(ticker, midpointIrr, lowRatio, updatedAt) {
  return { ticker, midpointIrr, lowRatio, updatedAt };
}

test("opportunity sorting prioritizes IRR, then falls back to cheaper low-ratio rows", () => {
  const rows = [
    row("000001", null, 0.80, "2026-08-20T09:00:00+08:00"),
    row("000002", 0.12, 0.50, "2026-08-18T09:00:00+08:00"),
    row("000003", null, 0.60, "2026-08-19T09:00:00+08:00"),
    row("000004", 0.18, 2.00, "2026-08-17T09:00:00+08:00"),
    row("000005", null, null, "2026-08-21T09:00:00+08:00"),
    row("000006", null, 0.60, "2026-08-20T09:00:00+08:00"),
  ];

  rows.sort(compareOpportunityRanks);

  assert.deepEqual(
    rows.map(({ ticker }) => ticker),
    ["000004", "000002", "000006", "000003", "000001", "000005"],
  );
});

import assert from "node:assert/strict";
import test from "node:test";
import { compareOpportunityRanks, compareResearchMapRows } from "../app/lib/opportunity-sort.mjs";

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

test("research map defaults stay stable when prices or estimated returns change", () => {
  const rows = [row("000003", 0.99, 0.1, "2026-09-15"), row("000001", null, null, "2026-08-01"),
    row("000002", 0.04, 1.2, "2026-09-16")];
  assert.deepEqual([...rows].sort(compareResearchMapRows).map((item) => item.ticker), ["000001", "000002", "000003"]);
  assert.deepEqual([...rows].sort((a,b) => compareResearchMapRows(a,b,"irr")).map((item) => item.ticker), ["000003", "000002", "000001"]);
  assert.deepEqual([...rows].sort((a,b) => compareResearchMapRows(a,b,"updated")).map((item) => item.ticker), ["000002", "000003", "000001"]);
  rows[0].midpointIrr = -0.6;
  rows[2].lowRatio = 0.01;
  assert.deepEqual([...rows].sort(compareResearchMapRows).map((item) => item.ticker), ["000001", "000002", "000003"]);
});

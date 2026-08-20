import assert from "node:assert/strict";
import test from "node:test";
import { calculateAnnualIrr, calculateIrrRange } from "../app/lib/irr.mjs";

function closeTo(actual, expected, tolerance = 1e-10) {
  assert.notEqual(actual, null);
  assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} is not close to ${expected}`);
}

function model(overrides = {}) {
  return {
    schema_version: 1,
    method: "annual_common_equity_irr_v1",
    currency: "CNY",
    model_as_of: "2026-08-20T12:00:00+08:00",
    base_case_distributions_per_share: [0, 0, 0, 0, 0],
    base_case_terminal_equity_value_range_per_share: {
      year_5: { low: 100, high: 161.051 },
      year_3: { low: 133.1, high: 133.1 },
    },
    ...overrides,
  };
}

test("annual IRR handles negative, zero, and high finite returns", () => {
  closeTo(calculateAnnualIrr(100, [0], 50), -0.5);
  closeTo(calculateAnnualIrr(100, [0], 100), 0);
  closeTo(calculateAnnualIrr(100, [0], 10_100), 100);
});

test("annual IRR includes each per-share distribution before terminal value", () => {
  closeTo(calculateAnnualIrr(100, [10, 10, 10, 10, 10], 100), 0.1);
});

test("3-year and 5-year IRRs use their independent terminal value ranges", () => {
  const returnModel = model();
  const year3 = calculateIrrRange(100, returnModel, 3);
  const year5 = calculateIrrRange(100, returnModel, 5);

  assert.ok(year3);
  assert.ok(year5);
  closeTo(year3.midpoint, 0.1);
  closeTo(year5.low, 0);
  closeTo(year5.high, 0.1);
  closeTo(year5.midpoint, 1.305255 ** (1 / 5) - 1);
});

test("3-year IRR is absent unless the research model provides year_3", () => {
  const withoutYear3 = model({
    base_case_terminal_equity_value_range_per_share: {
      year_5: { low: 100, high: 161.051 },
    },
  });
  assert.equal(calculateIrrRange(100, withoutYear3, 3), null);
  assert.ok(calculateIrrRange(100, withoutYear3, 5));
});

test("missing quotes and malformed model numbers fail closed", () => {
  assert.equal(calculateIrrRange(undefined, model(), 5), null);
  assert.equal(calculateIrrRange(0, model(), 5), null);
  assert.equal(calculateIrrRange(Number.POSITIVE_INFINITY, model(), 5), null);
  assert.equal(
    calculateIrrRange(100, model({ base_case_distributions_per_share: [0, 0, 0, 0, Number.NaN] }), 5),
    null,
  );
  assert.equal(
    calculateIrrRange(100, model({
      base_case_terminal_equity_value_range_per_share: {
        year_5: { low: 120, high: 100 },
      },
    }), 5),
    null,
  );
  assert.equal(
    calculateIrrRange(100, model({
      base_case_terminal_equity_value_range_per_share: {
        year_5: { low: 100, high: 120 },
        year_4: { low: 90, high: 110 },
      },
    }), 5),
    null,
  );
  assert.equal(
    calculateIrrRange(100, model({
      base_case_terminal_equity_value_range_per_share: {
        year_5: { low: 100, high: 120, midpoint: 110 },
      },
    }), 5),
    null,
  );
});

test("an endpoint with no future cash flow has no IRR without hiding solvable endpoints", () => {
  const result = calculateIrrRange(100, model({
    base_case_terminal_equity_value_range_per_share: {
      year_5: { low: 0, high: 100 },
    },
  }), 5);
  assert.ok(result);
  assert.equal(result.low, null);
  closeTo(result.midpoint, 0.5 ** (1 / 5) - 1);
  closeTo(result.high, 0);
});

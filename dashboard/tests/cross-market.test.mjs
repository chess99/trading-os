import assert from "node:assert/strict";
import test from "node:test";
import { normalizeQuoteKey, quoteCode, parseForeignTencent, exchangeTimestamp } from "../app/lib/market-quotes.mjs";
import { reportReferenceLink } from "../app/lib/report-reference.mjs";
import { calculateIrrRange } from "../app/lib/irr.mjs";

test("market identity preserves share classes and rejects path or URL input", () => {
  assert.equal(normalizeQuoteKey("HK:00700"), "HK-00700");
  assert.equal(normalizeQuoteKey("US:BRK.B"), "US-BRK.B");
  assert.equal(quoteCode("US-BRK.B"), "usBRK.B");
  assert.equal(quoteCode("920001"), "bj920001");
  assert.equal(normalizeQuoteKey("https://evil.example"), null);
  assert.equal(normalizeQuoteKey("US:../A"), null);
  assert.equal(reportReferenceLink("/research/companies/US/BRK.B/reports/2026-FY.md"), "/reports/US-BRK.B?version=2026-FY");
  assert.equal(reportReferenceLink("/research/companies/HK/00700/reports/2026-H1.md"), "/reports/HK-00700?version=2026-H1");
});
test("foreign quotes verify currency and convert New York summer/winter timestamps", () => {
  const f=Array(78).fill(""); f[1]="Apple"; f[3]="100"; f[4]="99"; f[30]="2026-10-23 12:00:00"; f[35]="USD";
  const text = `v_usAAPL="${f.join("~")}";`;
  const quotes = parseForeignTencent(text,["US-AAPL"]);
  assert.equal(quotes[0].currency, "USD");
  assert.equal(quotes[0].quoteAt,"2026-10-23T16:00:00.000Z");
  assert.equal(exchangeTimestamp("2026-12-23 12:00:00","America/New_York"),"2026-12-23T17:00:00.000Z");
  assert.equal(parseForeignTencent(text, ["HK-00700"]).length,0);
  f[35]="HKD"; assert.equal(parseForeignTencent(`v_usAAPL="${f.join("~")}";`,["US-AAPL"]).length,0);
  f[75]="HKD"; f[30]="2026/10/23 16:08:14";
  assert.equal(parseForeignTencent(`v_hk00700="${f.join("~")}";`,["HK-00700"])[0].quoteAt,"2026-10-23T08:08:14.000Z");
});
test("holder arithmetic works in each supported currency without FX conversion", () => {
  for (const currency of ["CNY","HKD","USD"]) {
    const model={schema_version:1,method:"annual_common_equity_irr_v1",currency,model_as_of:"2026-10-23T08:00:00Z",base_case_distributions_per_share:[10,10,10,10,10],base_case_terminal_equity_value_range_per_share:{year_5:{low:100,high:100}}};
    assert.ok(Math.abs(calculateIrrRange(100,model,5).midpoint-.1)<1e-9);
  }
});

test("display comparisons reject mixed currencies", async () => {
  const { matchingQuoteCurrency } = await import("../app/lib/market-quotes.mjs");
  assert.equal(matchingQuoteCurrency({price:100,currency:"USD"},"HKD"),false);
  assert.equal(matchingQuoteCurrency({price:100,currency:"HKD"},"HKD"),true);
  assert.equal(matchingQuoteCurrency({price:100},"USD"),false);
  assert.equal(matchingQuoteCurrency(null,"CNY"),false);
});

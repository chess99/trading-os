import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { projectScreeningPool, screeningMarkets } from "../scripts/lib/screening-data.mjs";
const root = new URL("../../", import.meta.url);
async function pool(market) { return JSON.parse(await readFile(new URL(`screening/${market}/value-quality/pool.json`, root), "utf8")); }
test("three market projection retains judgment and sources without mixing research", async () => {
  const output = JSON.parse(await readFile(new URL("dashboard/public/data/screening-pools.json", root), "utf8"));
  for (const market of screeningMarkets) {
    const original = await pool(market.id);
    const projected = output.pools.find((item) => item.market === market.id);
    assert.deepEqual(projected, projectScreeningPool(original, market));
    assert.deepEqual(projected.companies, original.companies);
  }
});
test("foreign identity, duplicate symbol and valuation contamination stop export", async () => {
  const original = await pool("hk");
  assert.throws(() => projectScreeningPool(original, screeningMarkets[0]), /市场代码/);
  const duplicate = structuredClone(original); duplicate.companies.push(duplicate.companies[0]);
  assert.throws(() => projectScreeningPool(duplicate, screeningMarkets[1]), /身份/);
  const price = structuredClone(original); price.companies[0].valueRange = { low: 1, high: 2 };
  assert.throws(() => projectScreeningPool(price, screeningMarkets[1]), /非合同/);
});

test("v3 covers every reviewed identity and retains source-indexed operating metrics", async () => {
  for (const id of ["hk", "us"]) {
    const original = await pool(id);
    assert.equal(original.schema_version, 3);
    const included = new Set(original.companies.map((c) => c.symbol));
    const excluded = new Set(original.review.exclusions.map((c) => c.symbol));
    assert.deepEqual(new Set([...included, ...excluded]), new Set(original.review.reviewed_symbols));
    assert.ok([...included].every((symbol) => !excluded.has(symbol)));
    for (const c of original.companies) {
      assert.ok(c.research_question && c.issuer && c.metrics.items.length);
      for (const item of c.metrics.items) assert.ok(item.period && c.sources[item.source]);
      if (c.metrics.history.length) assert.ok(c.sources[c.metrics.history_source]);
    }
    const broken = structuredClone(original);
    broken.companies[0].metrics.items[0].source = 99;
    assert.throws(() => projectScreeningPool(broken, screeningMarkets.find((m) => m.id === id)), /来源/);
  }
});

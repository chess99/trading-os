import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { currentResults } from "../app/lib/display-policy.mjs";

async function render(pathname = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}-${pathname}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(new Request(`http://localhost${pathname}`, { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} });
}
test("server-renders the Trading OS workspace with fail-closed data loading", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>研究决策台 · Trading OS<\/title>/i);
  assert.match(html, /Trading OS/); assert.match(html, /研究决策台/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape|react-loading-skeleton/i);
});
test("current table uses a common eligible set for prices, ranking, stats and export", async () => {
  const [dashboard, research] = await Promise.all([
    readFile(new URL("../app/components/dashboard-client.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/research.ts", import.meta.url), "utf8"),
  ]);
  for (const title of ["现价", "5年基准情景年化回报", "合理价值", "相对下沿", "相对中枢"]) assert.ok(dashboard.includes(title));
  assert.match(dashboard, /currentResults/); assert.match(dashboard, /progressCounts/);
  assert.match(dashboard, /accepted\.map\(\(company\) => company\.ticker\)/);
  assert.match(dashboard, /exportName/); assert.match(dashboard, /pricePosition/); assert.match(dashboard, /returnIrr/);
  assert.match(research, /schemaVersion !== 2/); assert.match(research, /isCurrentResult/);
  assert.match(research, /company\.returnModel\.model_as_of !== company\.informationCutoff/);
  assert.doesNotMatch(dashboard, /filter\(isActiveCovered\)/);
});
test("quote refresh keeps the existing timing policy without historical requests", async () => {
  const dashboard = await readFile(new URL("../app/components/dashboard-client.tsx", import.meta.url), "utf8");
  assert.match(dashboard, /QUOTE_REFRESH_INTERVAL_MS = 5 \* 60 \* 1000/);
  assert.match(dashboard, /timeZone: "Asia\/Shanghai"/);
  assert.match(dashboard, /setInterval\(refreshIfDue, 60_000\)/);
  assert.match(dashboard, /view !== "current"/);
  assert.match(dashboard, /generation !== quoteGeneration\.current/);
  assert.match(dashboard, /clearQuoteSnapshot/);
});
test("report library and detail route render", async () => {
  const [library, detail] = await Promise.all([render("/reports"), render("/reports/000001")]);
  assert.equal(library.status, 200); assert.equal(detail.status, 200);
  assert.match(await library.text(), /研报库/); assert.match(await detail.text(), /研报详情/);
});
test("historical reader binds selected metadata, never current summary or live prices", async () => {
  const reader = await readFile(new URL("../app/components/report-workspace.tsx", import.meta.url), "utf8");
  assert.match(reader, /readingContext/); assert.match(reader, /context\.report\.informationCutoff/);
  assert.match(reader, /!context\.live/); assert.match(reader, /context\.live &&/);
  assert.doesNotMatch(reader, /当前研究摘要|上方状态、行情与右侧摘要来自当前研究/);
});
test("industry and selection routes retain original exported research documents", async () => {
  const [industry, selection] = await Promise.all([render("/industries"), render("/selection")]);
  assert.equal(industry.status, 200); assert.equal(selection.status, 200);
  assert.match(await industry.text(), /产业研究/); assert.match(await selection.text(), /长期精选/);
  const { documents } = JSON.parse(await readFile(new URL("../public/data/documents.json", import.meta.url), "utf8"));
  assert.ok(documents.some((doc) => doc.id === "selection-current"));
  assert.ok(documents.some((doc) => doc.id === "industry-guide"));
  for (const doc of documents) {
    const original = await readFile(new URL(`../../${doc.sourcePath}`, import.meta.url), "utf8");
    const projection = await readFile(new URL(`../public${doc.path}`, import.meta.url), "utf8");
    assert.equal(projection, original);
  }
});
test("production projection matches qualified state rows and redacts all unqualified values", async () => {
  const catalog = JSON.parse(await readFile(new URL("../public/data/research-catalog.json", import.meta.url), "utf8"));
  const rows = (await readFile(new URL("../../coverage/cn-a/research_state.jsonl", import.meta.url), "utf8"))
    .split(/\r?\n/u).filter(Boolean).map((line) => JSON.parse(line));
  const sources = new Map(rows.map((row) => [row.symbol, row]));
  const pool = JSON.parse(await readFile(new URL("../../screening/cn-a/value-quality/pool.json", import.meta.url), "utf8"));
  assert.equal(catalog.stats.researchStateRows, rows.length);
  assert.equal(catalog.scope.count, pool.companies.length);
  for (const company of catalog.companies) {
    assert.ok(!JSON.stringify(company).includes("legacy/"));
    assert.ok(!("currentIrr" in company) && !("lastClose" in company));
    const source = sources.get(company.symbol);
    if (company.display.eligible) {
      assert.ok(source); assert.equal(company.reportPath, source.report_path);
      assert.deepEqual(company.valueRange, source.value_range ?? null);
      assert.deepEqual(company.returnModel, source.return_model ?? null);
      assert.equal(company.returnModelNote, source.return_model_note ?? null);
      assert.equal(company.summary, source.summary);
      assert.ok(company.reports.some((report) => report.sourcePath === company.reportPath && report.compatible));
    } else {
      assert.equal(company.valueRange, null); assert.equal(company.returnModel, null); assert.equal(company.returnModelNote, null); assert.equal(company.summary, "");
    }
    if (!source) assert.equal(company.hasResearchState, false);
  }
  const current = currentResults(catalog.companies);
  assert.equal(catalog.stats.current.completed, current.length);
  const exported = JSON.parse(await readFile(new URL("../public/data/current-research.json", import.meta.url), "utf8"));
  assert.deepEqual(exported.companies.map((item) => item.symbol), current.map((item) => item.symbol));
  const all = JSON.parse(await readFile(new URL("../public/data/all-current-research.json", import.meta.url), "utf8"));
  assert.equal(all.count, currentResults(catalog.companies, "all_standard").length);
});

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render(pathname = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}-${pathname}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request(`http://localhost${pathname}`, { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the Trading OS decision workspace", async () => {
  const response = await render("/");
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>研究决策台 · Trading OS<\/title>/i);
  assert.match(html, /Trading OS/);
  assert.match(html, /研究决策台/);
  assert.match(html, /从全市场状态里，先找到今天值得看的公司/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape|react-loading-skeleton/i);
});

test("server-renders the report library and detail route", async () => {
  const [library, detail] = await Promise.all([render("/reports"), render("/reports/000001")]);
  assert.equal(library.status, 200);
  assert.equal(detail.status, 200);
  assert.match(await library.text(), /研报库/);
  assert.match(await detail.text(), /研报详情/);
});

test("generated research catalog remains a faithful compact projection", async () => {
  const [catalogText, sourceText] = await Promise.all([
    readFile(new URL("../public/data/research-catalog.json", import.meta.url), "utf8"),
    readFile(new URL("../../coverage/cn-a/research_state.jsonl", import.meta.url), "utf8"),
  ]);
  const catalog = JSON.parse(catalogText);
  const sourceRows = sourceText.split(/\r?\n/u).filter((line) => line.trim());
  assert.equal(catalog.stats.total, sourceRows.length);
  assert.equal(catalog.companies.length, sourceRows.length);
  assert.ok(catalog.companies.some((company) => company.status === "covered" && company.reports.length));
  assert.ok(catalog.companies.every((company) => !JSON.stringify(company).includes("legacy/")));

  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  const layout = await readFile(new URL("../app/layout.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(page, /_sites-preview|codex-preview/);
  assert.match(layout, /lang="zh-CN"/);
});

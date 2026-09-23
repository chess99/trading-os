import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { setTimeout as delay } from "node:timers/promises";
import { chromium } from "playwright";
import { currentResults } from "../app/lib/display-policy.mjs";

const catalog = JSON.parse(await readFile(new URL("../public/data/research-catalog.json", import.meta.url), "utf8"));
const qualified = currentResults(catalog.companies);
const history = catalog.companies.find((company) => company.inQualityPool && !company.display.eligible && company.reports.length);
const output = new URL("../outputs/standard-checks/", import.meta.url);
await mkdir(output, { recursive: true });
const server = spawn("npm", ["run", "dev", "--", "--host", "127.0.0.1", "--port", "4173"],
  { cwd: new URL("..", import.meta.url), detached: process.platform !== "win32", stdio: ["ignore", "pipe", "pipe"] });
let log = "";
server.stdout.on("data", (chunk) => { log += chunk; });
server.stderr.on("data", (chunk) => { log += chunk; });
let browser;
const passed = [];
try {
  let ready = false;
  for (let attempt = 0; attempt < 90; attempt++) {
    if (server.exitCode !== null) throw new Error(`Dev server exited: ${log}`);
    try { const response = await fetch("http://127.0.0.1:4173/"); ready = response.ok; } catch { /* starting */ }
    if (ready) break;
    await delay(1000);
  }
  assert.ok(ready, `Dev server not ready: ${log}`);
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const quoteRequests = [];
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/quotes?*", async (route) => {
    quoteRequests.push(new URL(route.request().url()).searchParams.get("symbols").split(","));
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ quotes: [] }) });
  });
  await page.goto("http://127.0.0.1:4173/");
  await page.getByRole("tab", { name: /^当前研究/ }).waitFor();
  assert.equal(await page.locator("tbody tr[data-symbol]").count(), Math.min(80, qualified.length));
  for (const row of await page.locator("tbody tr[data-symbol]").evaluateAll((rows) => rows.map((item) => item.dataset.symbol))) {
    assert.ok(qualified.some((company) => company.symbol === row));
  }
  for (const request of quoteRequests) for (const ticker of request) assert.ok(qualified.some((company) => company.ticker === ticker));
  await page.screenshot({ path: new URL("current-desktop.png", output).pathname, fullPage: true });
  passed.push("默认核心池、当前列表、行情集合与资格一致");
  await page.getByRole("tab", { name: /^研究进度/ }).click();
  assert.equal(await page.getByRole("columnheader", { name: "合理价值", exact: true }).count(), 0);
  assert.equal(await page.locator("tbody tr[data-symbol]").count(), Math.min(80, catalog.scope.count));
  passed.push("进度页包含未完成公司，不展示旧估值");
  if (history) {
    quoteRequests.length = 0;
    await page.goto(`http://127.0.0.1:4173/reports/${history.ticker}`);
    await page.getByText("尚无可展示的现行标准报告", { exact: true }).waitFor();
    assert.equal(await page.locator(".markdown-document").count(), 0);
    await page.getByRole("button", { name: "主动查看历史研报", exact: true }).click();
    await page.locator(".markdown-document").waitFor();
    assert.equal(await page.getByTestId("live-research-panel").count(), 0);
    assert.equal(quoteRequests.length, 0);
    await page.getByTestId("historical-notice").waitFor();
    await page.screenshot({ path: new URL("history-desktop.png", output).pathname, fullPage: true });
    passed.push("旧报告需主动进入，历史正文不加载现价或当前摘要");
  }
  const sample = qualified[0] ?? history;
  if (sample) {
    quoteRequests.length = 0;
    const report = sample.reports.find((item) => item.sourcePath === sample.reportPath) ?? sample.reports[0];
    await page.goto(`http://127.0.0.1:4173/reports/${sample.ticker}?version=${report.date}`);
    await page.locator(".markdown-document").waitFor();
    assert.equal(await page.getByTestId("live-research-panel").count(), 0);
    assert.equal(quoteRequests.length, 0);
    await page.goto(`http://127.0.0.1:4173/reports/${sample.ticker}?version=1900-01-01`);
    await page.getByText("所引用的报告版本不存在", { exact: true }).waitFor();
    assert.equal(await page.locator(".markdown-document").count(), 0);
    passed.push("日期化引用保持历史身份；不存在的版本不自动回退");
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("http://127.0.0.1:4173/");
  await page.getByRole("tab", { name: /^当前研究/ }).waitFor();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
  assert.equal(overflow, false, "移动端不应产生全页横向溢出；表格内部可以滚动");
  await page.screenshot({ path: new URL("current-mobile.png", output).pathname, fullPage: true });
  passed.push("移动端布局无全页横向溢出");
  assert.deepEqual(errors, [], "页面运行时错误");
  const summary = { ok: true, standard: catalog.standard.id, pool: catalog.scope.count,
    currentResults: qualified.length, checks: passed };
  await writeFile(new URL("summary.json", output), JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary, null, 2));
} finally {
  await writeFile(new URL("dev-server.log", output), log);
  await browser?.close();
  try { if (process.platform === "win32") server.kill("SIGTERM"); else process.kill(-server.pid, "SIGTERM"); } catch { /* already exited */ }
}

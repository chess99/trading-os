import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { setTimeout as delay } from "node:timers/promises";
import { chromium } from "playwright";
import { currentResults } from "../app/lib/display-policy.mjs";

const catalog = JSON.parse(await readFile(new URL("../public/data/research-catalog.json", import.meta.url), "utf8"));
const qualified = currentResults(catalog.companies);
const history = catalog.companies.find((company) => !company.display.eligible && company.reports.length);
const output = new URL("../outputs/standard-checks/", import.meta.url);
await mkdir(output, { recursive: true });
const baseURL = process.env.TRADING_OS_TEST_URL ?? "http://127.0.0.1:4173";
const server = process.env.TRADING_OS_TEST_URL ? null : spawn("npm", ["run", "dev", "--", "--host", "127.0.0.1", "--port", "4173"],
  { cwd: new URL("..", import.meta.url), detached: process.platform !== "win32", stdio: ["ignore", "pipe", "pipe"] });
let log = "";
server?.stdout.on("data", (chunk) => { log += chunk; });
server?.stderr.on("data", (chunk) => { log += chunk; });
let browser;
const passed = [];
try {
  let ready = false;
  for (let attempt = 0; attempt < 90; attempt++) {
    if (server && server.exitCode !== null) throw new Error(`Dev server exited: ${log}`);
    try { const response = await fetch(`${baseURL}/`); ready = response.ok; } catch { /* starting */ }
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
  await page.goto(`${baseURL}/`);
  await page.getByRole("tab", { name: /^最新周期模型/ }).waitFor();
  assert.equal(await page.locator("tbody tr[data-symbol]").count(), Math.min(80, qualified.length));
  for (const row of await page.locator("tbody tr[data-symbol]").evaluateAll((rows) => rows.map((item) => item.dataset.symbol))) {
    assert.ok(qualified.some((company) => company.symbol === row));
  }
  for (const request of quoteRequests) for (const ticker of request) assert.ok(qualified.some((company) => company.ticker === ticker));
  await page.screenshot({ path: new URL("current-desktop.png", output).pathname, fullPage: true });
  passed.push("默认核心池、当前列表、行情集合与资格一致");
  await page.getByRole("tab", { name: /^跟踪进度/ }).click();
  assert.equal(await page.getByRole("columnheader", { name: "合理价值", exact: true }).count(), 0);
  assert.equal(await page.locator("tbody tr[data-symbol]").count(), Math.min(80, catalog.scope.count));
  passed.push("进度页包含未完成公司，不展示旧估值");
  if (history) {
    quoteRequests.length = 0;
    await page.goto(`${baseURL}/reports/${history.ticker}`);
    await page.locator(".markdown-document").waitFor();
    assert.equal(await page.getByTestId("live-research-panel").count(), 0);
    assert.equal(quoteRequests.length, 0);
    await page.getByTestId("historical-notice").waitFor();
    await page.screenshot({ path: new URL("history-desktop.png", output).pathname, fullPage: true });
    passed.push("全市场历史报告可直接阅读，且不加载现价或当前摘要");
  }
  const sample = catalog.companies.find((company) => company.reports.some((item) => item.sourcePath !== company.basisReportPath));
  if (sample) {
    quoteRequests.length = 0;
    const report = sample.reports.find((item) => item.sourcePath !== sample.basisReportPath);
    await page.goto(`${baseURL}/reports/${sample.ticker}?version=${report.period}`);
    await page.locator(".markdown-document").waitFor();
    assert.equal(await page.getByTestId("live-research-panel").count(), 0);
    assert.equal(quoteRequests.length, 0);
    await page.goto(`${baseURL}/reports/${sample.ticker}?version=1900-Q1`);
    await page.getByText("所选研究周期不存在", { exact: true }).waitFor();
    assert.equal(await page.locator(".markdown-document").count(), 0);
    passed.push("周期引用保持历史身份；不存在的周期不自动回退");
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${baseURL}/`);
  await page.getByRole("tab", { name: /^最新周期模型/ }).waitFor();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
  assert.equal(overflow, false, "移动端不应产生全页横向溢出；表格内部可以滚动");
  await page.screenshot({ path: new URL("current-mobile.png", output).pathname, fullPage: true });
  passed.push("移动端布局无全页横向溢出");
  await page.setViewportSize({ width: 1440, height: 1000 });
  quoteRequests.length = 0;
  await page.goto(`${baseURL}/screening`);
  await page.getByRole("heading", { name: "商业质量池" }).waitFor();
  const screening = JSON.parse(await readFile(new URL("../public/data/screening-pools.json", import.meta.url), "utf8"));
  await page.locator(".pool-market-bar").waitFor();
  for (const [market, label] of [["hk", "港股"], ["us", "美股"]]) {
    await page.getByRole("button", { name: new RegExp(`^${label}`) }).click();
    const expected = screening.pools.find((pool) => pool.market === market).companies;
    assert.equal(await page.locator("tbody tr[data-symbol]").count(), Math.min(30, expected.length));
    await page.getByLabel("质量层级").selectOption("core_moat");
    assert.equal(await page.locator("tbody tr[data-symbol]").count(), Math.min(30, expected.filter((c) => c.tier === "core_moat").length));
    await page.getByLabel("质量层级").selectOption("all");
    await page.getByRole("button", { name: "下一页", exact: true }).click();
    assert.equal(await page.locator("tbody tr[data-symbol]").count(), Math.min(30, expected.length-30));
    await page.getByRole("button", { name: "上一页", exact: true }).click();
  }
  await page.getByRole("button", { name: /^查看 / }).first().click();
  await page.getByRole("heading", { name: "关键研究问题" }).waitFor();
  await page.locator(".pool-sources summary").click();
  assert.ok(await page.locator("aside.pool-detail a[target=_blank]").count() > 0);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.locator("aside.pool-detail").evaluate((element) => { element.scrollTop = 0; });
  await page.screenshot({ path: new URL("screening-desktop.png", output).pathname, fullPage: true });
  await page.getByRole("button", { name: "全部市场", exact: true }).click();
  await page.getByLabel("搜索公司或关键问题").fill("美的");
  assert.equal(await page.locator("tbody tr[data-symbol]").count(), 1, "A/H同发行人合并");
  await page.getByRole("button", { name: /^查看 美的/ }).click();
  assert.match(await page.locator("aside.pool-detail").innerText(), /CN:000333/);
  assert.match(await page.locator("aside.pool-detail").innerText(), /HK:00300/);
  assert.match(await page.locator("aside.pool-detail").innerText(), /FY2025/);
  await page.reload();
  await page.getByRole("heading", { name: "关键研究问题" }).waitFor();
  assert.equal(await page.getByLabel("搜索公司或关键问题").inputValue(), "美的");
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: /导出当前列表/ }).click();
  assert.equal((await downloaded).suggestedFilename(), "company-screening.csv");
  await page.getByLabel("搜索公司或关键问题").fill("not-a-company-xyz");
  await page.getByRole("heading", { name: "没有符合条件的公司" }).waitFor();
  await page.getByRole("button", { name: "清除筛选条件" }).click();
  await page.getByRole("button", { name: /^美股/ }).click();
  await page.getByRole("tab", { name: "未纳入", exact: true }).click();
  await page.getByLabel("搜索公司或关键问题").fill("TSLA");
  assert.equal(await page.locator("tbody tr[data-symbol]").count(), 1);
  assert.match(await page.locator(".pool-reason").innerText(), /自动驾驶/);
  await page.getByRole("tab", { name: "入选公司", exact: true }).click();
  await page.getByLabel("搜索公司或关键问题").fill("");
  await page.getByRole("button", { name: /^港股/ }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByLabel("搜索公司或关键问题").fill("腾讯");
  await page.getByRole("button", { name: /^查看 腾讯/ }).click();
  await page.locator("dialog[open]").waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2), false);
  await page.screenshot({ path: new URL("screening-mobile-detail.png", output).pathname });
  await page.keyboard.press("Escape");
  assert.equal(await page.locator("dialog[open]").count(), 0);
  await page.getByLabel("搜索公司或关键问题").fill("");
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: new URL("screening-mobile.png", output).pathname, fullPage: true });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2), false);
  assert.equal(quoteRequests.length, 0, "公司池不得请求行情");
  assert.doesNotMatch(await page.locator("body").innerText(), /本轮完成筛选|暂不开展公司深研|首批采用精选样本/);
  passed.push("跨市场筛选、分页、A/H合并、指标来源、链接恢复、CSV导出及取舍理由通过");
  passed.push("手机详情弹层、键盘关闭与布局通过，公司池无行情请求");
  assert.deepEqual(errors, [], "页面运行时错误");
  const summary = { ok: true, standard: catalog.standard.id, pool: catalog.scope.count,
    currentResults: qualified.length, checks: passed };
  await writeFile(new URL("summary.json", output), JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary, null, 2));
} finally {
  await writeFile(new URL("dev-server.log", output), log);
  await browser?.close();
  try { if (server) { if (process.platform === "win32") server.kill("SIGTERM"); else process.kill(-server.pid, "SIGTERM"); } } catch { /* already exited */ }
}

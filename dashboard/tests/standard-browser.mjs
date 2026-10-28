import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { setTimeout as delay } from "node:timers/promises";
import { chromium } from "playwright";
import { currentResults } from "../app/lib/display-policy.mjs";

const catalog = JSON.parse(await readFile(new URL("../public/data/research-catalog.json", import.meta.url), "utf8"));
const qualified = currentResults(catalog.companies);
const publications = JSON.parse(await readFile(new URL("../public/data/documents.json", import.meta.url), "utf8")).documents;
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
  await page.goto(`${baseURL}/`);
  await page.getByRole("tab", { name: "跟踪进度", exact: true }).click();
  await page.getByLabel("研究市场").selectOption("HK");
  await page.getByRole("cell", { name: "尚无公司研究", exact: true }).first().waitFor();
  assert.equal(await page.locator("tbody tr[data-symbol]").count(),catalog.companies.filter((c) => c.market === "HK" && c.inQualityPool).length);
  await page.getByRole("tab", { name: "最新周期模型", exact: true }).click();
  await page.getByText("暂无符合条件的现行研究", { exact:true }).waitFor();
  assert.equal(await page.locator("tbody tr[data-symbol]").count(),0);
  await page.goto(`${baseURL}/reports`);
  await page.getByLabel("研报市场").selectOption("US");
  await page.getByText("该范围尚无已完成研报。", { exact:true }).waitFor();
  await page.goto(`${baseURL}/industries`);
  await page.getByLabel("适用市场").selectOption("HK");
  if (publications.some((d) => d.kind === "industry" && d.type === "report" && d.markets.includes("HK"))) await page.locator(".research-document-body h1").waitFor();
  else { await page.getByRole("heading", { name: "暂无行业研究报告", exact: true }).waitFor(); assert.equal(await page.locator(".markdown-document").count(),0); }
  if (await page.locator(".publication-outline").count()) {
    await page.locator(".publication-outline summary").click();
    const outlineLinks = page.getByRole("navigation", { name: "本文目录", exact:true }).locator("a");
    assert.ok(await outlineLinks.count() > 3);
    const anchor = await outlineLinks.first().getAttribute("href");
    assert.equal(await page.locator(anchor).count(),1);
    await outlineLinks.first().click();
    assert.equal(new URL(page.url()).hash,anchor);
    await page.evaluate(() => window.scrollTo({top:0,behavior:"instant"}));
  }
  await page.screenshot({ path: new URL("industry-library.png", output).pathname });
  await page.goto(`${baseURL}/macro`);
  await page.getByLabel("适用市场").selectOption("US");
  await page.locator(".research-document-body .markdown-document h1").waitFor();
  await page.getByRole("button", { name: /^指标与方法/ }).click();
  await page.getByRole("button", { name: /^研究报告/ }).click();
  if (publications.some((d) => d.kind === "macro" && d.type === "report" && d.markets.includes("US"))) await page.locator(".research-document-body h1").waitFor();
  else await page.getByRole("heading", { name: "暂无宏观研究报告", exact:true }).waitFor();
  await page.getByRole("button", { name: /^指标与方法/ }).click();
  await page.locator(".research-document-body .markdown-document h1").waitFor();
  await page.getByRole("navigation", { name: "研究主题" }).locator("button").first().click();
  const documentTitle=await page.locator(".research-document-body h1").innerText();
  await page.reload();
  await page.locator(".research-document-body .markdown-document h1").waitFor();
  assert.equal(await page.locator(".research-document-body h1").innerText(),documentTitle);
  await page.screenshot({ path: new URL("macro-reference.png", output).pathname });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2),false);
  await page.screenshot({ path: new URL("macro-mobile.png", output).pathname });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`${baseURL}/selection`);
  await page.getByRole("heading", { name: "商业质量池", exact: true }).waitFor();
  assert.equal(new URL(page.url()).searchParams.get("view"),"pool");
  passed.push("行业与宏观区分正式报告和方法；空状态、市场范围、深链及旧精选入口通过");
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
  for (const width of [360, 390, 820, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto(`${baseURL}/?view=pool`);
    await page.locator(".pool-market-bar").waitFor();
    assert.equal(await page.locator(".primary-nav").evaluate((nav) => nav.scrollWidth > nav.clientWidth + 1), false, "主导航完整可见");
    const navigation = page.getByRole("tablist", { name: "研究视图", exact: true });
    const baseline = await navigation.boundingBox();
    for (const name of ["跟踪进度", "最新周期模型", "全部档案", "公司池"]) {
      await page.getByRole("tab", { name, exact: true }).click();
      await page.locator("tbody tr[data-symbol]").first().waitFor();
      const box = await navigation.boundingBox();
      assert.ok(Math.abs(box.y - baseline.y) <= 1, `${width}px ${name}: 视图切换不移动导航`);
      assert.equal(await page.evaluate(() => scrollY), 0, "视图切换不滚动页面");
      const row = await page.locator("tbody tr[data-symbol]").first().boundingBox();
      assert.ok(row.y < 510, `${width}px ${name}: 首屏应直接看到公司`);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2), false);
      if (width === 390 || width === 1440) await page.screenshot({ path: new URL(`compact-${width}-${name}.png`, output).pathname });
    }
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("tab", { name: "最新周期模型", exact: true }).click();
  assert.equal(await page.getByLabel("行业筛选").isVisible(), false);
  await page.getByRole("button", { name: "筛选", exact: true }).click();
  await page.getByLabel("行业筛选").selectOption("白色家电");
  const filteredRows = await page.locator("tbody tr[data-symbol]").count();
  assert.ok(filteredRows > 0 && filteredRows < qualified.length);
  await page.getByRole("button", { name: "筛选 ·", exact: true }).click();
  assert.equal(await page.getByLabel("行业筛选").isVisible(), false);
  assert.equal(await page.locator("tbody tr[data-symbol]").count(), filteredRows, "折叠筛选保留条件");
  const firstReportLink = page.locator("tbody tr[data-symbol] .research-company-link").first();
  assert.match(await firstReportLink.getAttribute("href"), /^\/reports\//);
  await page.getByRole("button", { name: "研究口径", exact: true }).click();
  await page.getByRole("dialog", { name: "研究口径", exact: true }).waitFor();
  await page.keyboard.press("Escape");
  assert.equal(await page.locator("dialog[open]").count(), 0);
  assert.equal(await page.evaluate(() => document.activeElement.textContent), "研究口径");
  await page.locator(".standards-table-scroll").evaluate((node) => { node.scrollLeft = 200; });
  await page.getByRole("tab", { name: "跟踪进度", exact: true }).click();
  assert.equal(await page.locator(".standards-table-scroll").evaluate((node) => node.scrollLeft), 0);
  await page.keyboard.press("ArrowRight");
  assert.equal(await page.getByRole("tab", { name: "最新周期模型", exact: true }).getAttribute("aria-selected"), "true");
  await page.keyboard.press("Home");
  assert.equal(await page.getByRole("tab", { name: "公司池", exact: true }).getAttribute("aria-selected"), "true");
  passed.push("360–1440px视图切换导航稳定、首屏可见公司；手机筛选、研报入口、弹层与键盘操作通过");
  const reportPage = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const snapshots=["2026-09-30","2026-10-28"].map((date,index)=>({id:`test-${date}`,kind:"industry",type:"report",topic:"test",title:`测试判断 ${index}`,summary:"测试数据",publishedOn:date,revision:1,version:date,informationCutoff:date,markets:["CN"],regions:["中国"],status:index?"withdrawn":"published",withdrawalReason:index?"测试更正":null,sourcePath:`research/industries/test/reports/${date}.md`,path:`/data/documents/test-${date}.md`}));
  await reportPage.route("**/data/documents.json",r=>r.fulfill({json:{schemaVersion:1,documents:snapshots}}));
  await reportPage.route("**/data/documents/test-*.md",r=>r.fulfill({contentType:"text/plain",body:`# ${r.request().url().includes("09-30")?"前期判断":"后期判断"}\n\n测试正文。`}));
  await reportPage.goto(`${baseURL}/industries`);
  await reportPage.getByText("本报告已撤回：测试更正").waitFor();
  await reportPage.getByLabel("报告版本").selectOption("2026-09-30");
  await reportPage.getByRole("heading",{name:"前期判断",exact:true}).waitFor();
  assert.equal(await reportPage.getByRole("alert").count(),0);
  await reportPage.reload();await reportPage.getByRole("heading",{name:"前期判断",exact:true}).waitFor();
  await reportPage.goto(`${baseURL}/industries?topic=test&version=2020-01-01&view=report`);
  await reportPage.getByRole("heading",{name:"未找到所选主题或版本",exact:true}).waitFor();
  assert.equal(await reportPage.locator(".markdown-document").count(),0);
  await reportPage.close();
  passed.push("独立夹具验证报告版本、历史链接恢复、撤回提示及不存在版本不回退");
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

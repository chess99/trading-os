import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { currentResults } from "../app/lib/display-policy.mjs";
import { fragmentId, researchHeadings } from "../app/lib/research-headings.mjs";

const catalog = JSON.parse(await readFile(new URL("../public/data/research-catalog.json", import.meta.url), "utf8"));
const qualified = currentResults(catalog.companies);
const publicationDirectory = JSON.parse(await readFile(new URL("../public/data/documents.json", import.meta.url), "utf8"));
const publications = publicationDirectory.documents;
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
  browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {}) });
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
  await page.screenshot({ path: fileURLToPath(new URL("current-desktop.png", output)), fullPage: true });
  const contextToggle = page.locator(".decision-context-bar > summary");
  await contextToggle.waitFor();
  await contextToggle.click();
  await page.getByText(/国内可投美股宽基 QDII ETF 名录/).waitFor();
  await contextToggle.click();
  passed.push("默认核心池、当前列表、行情集合、宏观/QDII上下文条与资格一致");
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
    await page.screenshot({ path: fileURLToPath(new URL("history-desktop.png", output)), fullPage: true });
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
  // Former oversized deliveries must remain small, real file downloads.
  for (const ticker of ["300015", "600018"]) {
    const period = "2026-Q3";
    await page.goto(`${baseURL}/reports/${ticker}?version=${period}`);
    await page.locator(".markdown-document").waitFor();
    for (const suffix of [".py", "-output.json"]) {
      const filename = `${period}${suffix}`;
      const original = await readFile(new URL(`../../research/companies/CN/${ticker}/models/${filename}`, import.meta.url));
      assert.ok(original.length <= 1024 ** 2, `${ticker} ${filename} exceeds the file budget`);
      const path = `/data/models/${ticker}/${filename}`;
      const link = page.locator(`.markdown-document a[href="${path}"]`).first();
      await link.waitFor();
      assert.equal(await link.getAttribute("download"), "");
      const pendingDownload = page.waitForEvent("download");
      await link.click();
      const download = await pendingDownload;
      assert.equal(download.suggestedFilename(), filename);
      assert.equal(download.url(), `${baseURL}${path}`);
      assert.deepEqual(await readFile(await download.path()), original, `${ticker} ${filename} download bytes`);
    }
  }
  passed.push("原大体积模型的源码和简明结果可下载，内容与仓库一致且符合文件预算");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${baseURL}/`);
  await page.getByRole("tab", { name: /^最新周期模型/ }).waitFor();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
  assert.equal(overflow, false, "移动端不应产生全页横向溢出；表格内部可以滚动");
  await page.screenshot({ path: fileURLToPath(new URL("current-mobile.png", output)), fullPage: true });
  passed.push("移动端布局无全页横向溢出");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`${baseURL}/`);
  await page.getByRole("tab", { name: "跟踪进度", exact: true }).click();
  await page.getByLabel("研究市场").selectOption("HK");
  const hkProgressCount = Math.min(80, catalog.companies.filter((c) => c.market === "HK" && c.inQualityPool).length);
  await page.waitForFunction((expected) => document.querySelectorAll("tbody tr[data-symbol]").length === expected, hkProgressCount);
  await page.getByRole("tab", { name: "最新周期模型", exact: true }).click();
  const hkCurrent = qualified.filter((company) => company.market === "HK");
  if (!hkCurrent.length) await page.getByText("暂无符合条件的现行研究", { exact:true }).waitFor();
  else await page.locator("tbody tr[data-symbol]").first().waitFor();
  assert.equal(await page.locator("tbody tr[data-symbol]").count(), Math.min(80, hkCurrent.length));
  for (const symbol of await page.locator("tbody tr[data-symbol]").evaluateAll((rows) => rows.map((row) => row.dataset.symbol))) {
    assert.ok(hkCurrent.some((company) => company.symbol === symbol));
  }
  await page.goto(`${baseURL}/reports`);
  await page.getByLabel("研报市场").selectOption("HK");
  const hkReports = catalog.companies.filter((company) => company.market === "HK" && company.inQualityPool && company.reports.length);
  if (!hkReports.length) await page.getByText("该范围尚无已完成研报。", { exact:true }).waitFor();
  else {
    await page.locator(".standards-library-list button").first().waitFor();
    assert.equal(await page.locator(".standards-library-list button").count(), hkReports.length);
    await page.locator(".standards-library-list button").first().click();
    await page.locator(".markdown-document").waitFor();
  }
  await page.goto(`${baseURL}/industries?region=archive`);
  await page.getByLabel("适用市场").selectOption("HK");
  if (publications.some((d) => d.kind === "industry" && d.type === "report" && d.regionId !== "cn" && d.markets.includes("HK"))) await page.locator(".research-document-body h1").waitFor();
  else { await page.getByRole("heading", { name: "暂无行业研究报告", exact: true }).waitFor(); assert.equal(await page.locator(".markdown-document").count(),0); }
  if (await page.locator(".publication-outline").count()) {
    await page.locator(".publication-outline summary").click();
    const outlineLinks = page.getByRole("navigation", { name: "本文目录", exact:true }).locator("a");
    assert.ok(await outlineLinks.count() > 3);
    const anchor = await outlineLinks.first().getAttribute("href");
    assert.equal(await page.evaluate((hash) => Boolean(document.getElementById(decodeURIComponent(hash.slice(1)))), anchor), true);
    await outlineLinks.first().click();
    assert.equal(fragmentId(new URL(page.url()).hash), fragmentId(anchor));
    await page.evaluate(() => window.scrollTo({top:0,behavior:"instant"}));
  }
  await page.screenshot({ path: fileURLToPath(new URL("industry-library.png", output)) });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${baseURL}/industries?region=archive`);
  const mobileTopics = page.getByLabel("选择研究主题", { exact: true });
  if (new Set(publications.filter((d) => d.kind === "industry" && d.type === "report" && d.regionId !== "cn").map((d) => d.topic)).size > 1) {
    await mobileTopics.waitFor();
    const lastTopic = mobileTopics.locator("option").last();
    const topicId = await lastTopic.getAttribute("value");
    const topicLabel = await lastTopic.innerText();
    await mobileTopics.selectOption(topicId);
    const heading = page.locator(".research-document-body h1");
    await heading.filter({ hasText: topicLabel }).waitFor();
    assert.ok((await heading.boundingBox()).y < 700, "移动端应在首屏进入报告标题，无需翻过行业卡片");
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2), false);
    await page.getByLabel("搜索研究主题").fill(topicLabel);
    await heading.filter({ hasText: topicLabel }).waitFor();
    assert.equal(await page.locator(".publication-list button").count(), 1);
    await page.getByLabel("搜索研究主题").fill("");
    await mobileTopics.waitFor();
    await page.screenshot({ path: fileURLToPath(new URL("industry-mobile.png", output)) });
    passed.push("多主题行业目录支持移动选择与搜索，首屏可见正文标题且无横向溢出");
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  const withIndicators = publications.find((d) => d.indicatorPath && d.regionId === "cn");
  if (withIndicators) {
    await page.goto(`${baseURL}/industries?topic=${withIndicators.topic}&region=cn&view=report&panel=indicators`);
    const indicatorPanel = page.getByRole("region", {name:"行业运行指标"});
    await indicatorPanel.waitFor();
    assert.ok(await page.locator(".indicator-release-links a").count() >= 2);
    await page.getByLabel("趋势指标", {exact:true}).selectOption("retail-yoy");
    await page.getByRole("img", {name:/新能源零售同比趋势/}).waitFor();
    await page.screenshot({path:fileURLToPath(new URL("ev-indicators-desktop.png",output))});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth > innerWidth + 2),false);
    assert.ok((await page.locator(".indicator-headlines strong").first().boundingBox()).y < 650, "手机首屏应能看到核心行业数字");
    await page.getByLabel("选择份额统计",{exact:true}).selectOption("global-ytd");
    await page.getByRole("heading",{name:"全球重点电池企业份额",exact:true}).waitFor();
    assert.equal(await page.locator(".indicator-rankings > section").count(),1);
    assert.ok(await page.locator(".indicator-rankings > section").evaluate((e)=>e.getBoundingClientRect().right <= innerWidth));
    await page.screenshot({path:fileURLToPath(new URL("ev-indicators-mobile.png",output)),fullPage:true});
    await page.reload();
    await indicatorPanel.waitFor();
    const older = publications.find((d)=>d.topic===withIndicators.topic && d.publishedOn < withIndicators.publishedOn);
    if (older) {
      await page.goto(`${baseURL}/industries?topic=${older.topic}&version=${older.version}&view=report&panel=indicators`);
      await page.locator(".research-document-body h1").waitFor();
      assert.equal(await page.getByRole("region",{name:"行业运行指标"}).count(),0);
      await page.goto(`${baseURL}/industries?topic=${withIndicators.topic}&region=cn&version=${withIndicators.version}&view=report`);
      await page.getByRole("button",{name:"行业指标",exact:true}).waitFor();
      await page.getByRole("button",{name:"行业指标",exact:true}).click();
      await page.getByRole("region",{name:"行业运行指标"}).waitFor();
    }
    await page.setViewportSize({width:1440,height:1000});
    passed.push("新能源指标月报入口、负增长图表、移动端、深链和历史报告隔离通过");
  }
  const archiveIndicators = publications.find((d) => d.indicatorPath && d.regionId !== "cn");
  if (archiveIndicators) {
    await page.goto(`${baseURL}/industries?topic=${archiveIndicators.topic}&version=${archiveIndicators.version}&region=archive&view=report&panel=indicators`);
    await page.locator(".research-document-body h1").waitFor();
    assert.equal(await page.getByRole("region", { name: "行业运行指标" }).count(), 0);
    passed.push("历史与海外档案保留原报告，不加载独立更新的当前指标");
  }
  const industryCatalog = publicationDirectory.industryCatalog;
  if (industryCatalog) {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(`${baseURL}/industries`);
    const groups = page.getByRole("navigation", { name: "行业大类", exact: true });
    await groups.waitFor();
    assert.equal(await groups.locator("button").count(), industryCatalog.groups.length + 1);
    assert.equal(await page.getByRole("navigation", { name: "研究主题", exact: true }).locator("button").count(), industryCatalog.topics.length);
    for (const group of industryCatalog.groups) {
      await groups.getByRole("button", { name: group.label, exact: true }).click();
      assert.equal(await page.getByRole("navigation", { name: "研究主题", exact: true }).locator("button").count(), industryCatalog.topics.filter((topic) => topic.group === group.id).length);
    }
    await groups.getByRole("button", { name: "全部", exact: true }).click();
    assert.equal(await page.getByLabel("适用市场").count(), 0, "中国行业范围不由上市市场筛选");
    await page.screenshot({ path: fileURLToPath(new URL("china-industry-desktop.png", output)) });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole("combobox", { name: "行业大类", exact: true }).selectOption(industryCatalog.groups.at(-1).id);
    const lastGroupTopics = industryCatalog.topics.filter((topic) => topic.group === industryCatalog.groups.at(-1).id);
    await page.getByLabel("选择研究主题", { exact: true }).selectOption(lastGroupTopics.at(-1).id);
    await page.reload();
    await page.getByRole("combobox", { name: "行业大类", exact: true }).waitFor();
    assert.equal(await page.getByLabel("选择研究主题", { exact: true }).inputValue(), lastGroupTopics.at(-1).id);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2), false);
    await page.screenshot({ path: fileURLToPath(new URL("china-industry-mobile.png", output)) });
    passed.push("中国行业目录按来源大类与主题动态导航，移动选择与深链恢复；上市市场不改变经营地域");
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
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
  await page.screenshot({ path: fileURLToPath(new URL("macro-reference.png", output)) });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2),false);
  await page.screenshot({ path: fileURLToPath(new URL("macro-mobile.png", output)) });
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
  for (const [market, label] of [["cn-a", "A股"], ["hk", "港股"]]) {
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
  await page.screenshot({ path: fileURLToPath(new URL("screening-desktop.png", output)), fullPage: true });
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
  await page.getByRole("button", { name: /^港股/ }).click();
  await page.getByRole("tab", { name: "未纳入", exact: true }).click();
  await page.getByLabel("搜索公司或关键问题").fill("00001");
  assert.equal(await page.locator("tbody tr[data-symbol]").count(), 1);
  assert.match(await page.locator(".pool-reason").innerText(), /复杂集团/);
  await page.getByRole("tab", { name: "入选公司", exact: true }).click();
  await page.getByLabel("搜索公司或关键问题").fill("");
  await page.getByRole("button", { name: /^港股/ }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByLabel("搜索公司或关键问题").fill("腾讯");
  await page.getByRole("button", { name: /^查看 腾讯/ }).click();
  await page.locator("dialog[open]").waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2), false);
  await page.screenshot({ path: fileURLToPath(new URL("screening-mobile-detail.png", output)) });
  await page.keyboard.press("Escape");
  assert.equal(await page.locator("dialog[open]").count(), 0);
  await page.getByLabel("搜索公司或关键问题").fill("");
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: fileURLToPath(new URL("screening-mobile.png", output)), fullPage: true });
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
      if (width === 390 || width === 1440) await page.screenshot({ path: fileURLToPath(new URL(`compact-${width}-${name}.png`, output)) });
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
  const taxonomyPage = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  taxonomyPage.on("pageerror", (error) => errors.push(error.message));
  const taxonomy = { schemaVersion: 1, groups: [{ id: "consumer", label: "消费" }, { id: "finance", label: "金融" }], topics: [
    { id: "retail", label: "零售", group: "consumer", scope: "中国商品零售与线上渠道。" },
    { id: "restaurants", label: "餐饮", group: "consumer", scope: "中国门店与加盟经营。" },
    { id: "banking", label: "银行", group: "finance", scope: "中国存款、借贷与资本。" },
  ] };
  const taxonomyDocuments = [
    { ...snapshots[0], id: "catalog-retail-cn", topic: "retail", regionId: "cn", version: "2026-11-16", publishedOn: "2026-11-16", title: "中国零售当前研究", sourcePath: "research/industries/retail/reports/2026-11-16.md", path: "/data/documents/catalog-retail-cn.md" },
    { ...snapshots[0], id: "catalog-retail-old", topic: "retail", title: "海外零售旧文", sourcePath: "research/industries/retail/reports/2026-09-30.md", path: "/data/documents/catalog-retail-old.md" },
    { ...snapshots[0], id: "catalog-restaurants-old", topic: "restaurants", title: "海外餐饮旧文", sourcePath: "research/industries/restaurants/reports/2026-09-30.md", path: "/data/documents/catalog-restaurants-old.md" },
  ];
  const taxonomyRequests = [];
  await taxonomyPage.route("**/data/documents.json", (route) => route.fulfill({ json: { schemaVersion: 1, documents: taxonomyDocuments, industryCatalog: taxonomy } }));
  await taxonomyPage.route("**/data/documents/catalog-*.md", (route) => {
    taxonomyRequests.push(route.request().url());
    const document = taxonomyDocuments.find((item) => route.request().url().endsWith(item.path));
    return route.fulfill({ contentType: "text/plain", body: `# ${document.title}\n\n## 需求\n\n独立研究正文。\n\n[中国零售](../${document.topic === "retail" ? "reports" : "../retail/reports"}/2026-11-16.md#需求)\n` });
  });
  await taxonomyPage.goto(`${baseURL}/industries`);
  await taxonomyPage.getByRole("heading", { name: "中国零售当前研究", exact: true }).waitFor();
  assert.equal(await taxonomyPage.getByRole("navigation", { name: "研究主题", exact: true }).locator("button").count(), taxonomy.topics.length);
  await taxonomyPage.getByRole("navigation", { name: "研究主题", exact: true }).getByRole("button", { name: "餐饮", exact: true }).click();
  await taxonomyPage.getByText("暂无已发布研究。", { exact: true }).waitFor();
  assert.equal(await taxonomyPage.locator(".markdown-document").count(), 0);
  assert.ok(!taxonomyRequests.some((url) => url.endsWith("catalog-restaurants-old.md")), "中国空主题不能借用海外旧文");
  await taxonomyPage.getByRole("navigation", { name: "行业大类", exact: true }).getByRole("button", { name: "金融", exact: true }).click();
  await taxonomyPage.getByText("中国存款、借贷与资本。", { exact: true }).waitFor();
  assert.equal(await taxonomyPage.getByRole("navigation", { name: "研究主题", exact: true }).locator("button").count(), 1);
  await taxonomyPage.goto(`${baseURL}/industries?topic=retail&version=2026-09-30&view=report`);
  await taxonomyPage.getByRole("heading", { name: "海外零售旧文", exact: true }).waitFor();
  assert.equal(await taxonomyPage.getByRole("button", { name: /^历史与海外/ }).getAttribute("aria-pressed"), "true");
  await taxonomyPage.getByRole("link", { name: "中国零售", exact: true }).click();
  await taxonomyPage.getByRole("heading", { name: "中国零售当前研究", exact: true }).waitFor();
  assert.equal(new URL(taxonomyPage.url()).searchParams.get("region"), "cn");
  assert.equal(new URL(taxonomyPage.url()).searchParams.get("version"), "2026-11-16");
  await taxonomyPage.setViewportSize({ width: 390, height: 844 });
  await taxonomyPage.getByRole("combobox", { name: "行业大类", exact: true }).selectOption("finance");
  await taxonomyPage.reload();
  await taxonomyPage.getByText("暂无已发布研究。", { exact: true }).waitFor();
  assert.equal(await taxonomyPage.getByRole("combobox", { name: "行业大类", exact: true }).inputValue(), "finance");
  assert.equal(await taxonomyPage.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2), false);
  await taxonomyPage.close();
  passed.push("独立目录夹具验证中国/海外隔离、未发布主题、动态分类、跨区版本链接与移动深链恢复");
  const linkedCompany = catalog.companies.find((company) => company.ticker === "000002"
    && company.reports.some((report) => report.sourcePath !== company.basisReportPath)) ?? sample;
  if (linkedCompany) {
    const companyReport = linkedCompany.reports.find((report) => report.sourcePath !== linkedCompany.basisReportPath);
    const companyBody = await readFile(new URL(`../../${companyReport.sourcePath}`, import.meta.url), "utf8");
    const companyChapter = researchHeadings(companyBody).find((heading) => heading.depth === 2);
    assert.ok(companyChapter, "跨层阅读测试需要可定位的历史公司章节");
    const linkedPage = await browser.newPage({ viewport: { width: 390, height: 844 } });
    const linkedQuoteRequests = [];
    const linkedIndicatorRequests = [];
    linkedPage.on("pageerror", (error) => errors.push(error.message));
    await linkedPage.route("**/api/quotes?*", (route) => {
      linkedQuoteRequests.push(route.request().url());
      return route.fulfill({ json: { quotes: [] } });
    });
    await linkedPage.route("**/data/indicators/**", (route) => {
      linkedIndicatorRequests.push(route.request().url());
      return route.fulfill({ json: {} });
    });
    const industryFixture = {
      ...snapshots[0], indicatorPath: "/data/indicators/test-current.json",
    };
    const macroFixture = {
      ...snapshots[0], id: "test-credit", kind: "macro", topic: "test-credit", title: "信用与地产链",
      sourcePath: "research/macro/test-credit/reports/2026-09-30.md", path: "/data/documents/test-credit.md",
    };
    await linkedPage.route("**/data/documents.json", (route) => route.fulfill({ json: {
      schemaVersion: 1, documents: [industryFixture, snapshots[1], macroFixture],
      companyReportPaths: [companyReport.sourcePath],
    } }));
    const padding = "这一段只用于检验章节在正文加载后的位置。\n\n".repeat(30);
    // Leave room below the target so native scrolling is not clamped at the
    // document bottom before the heading can reach the requested top margin.
    await linkedPage.route("**/data/documents/test-2026-09-30.md", (route) => route.fulfill({ contentType: "text/plain", body:
      `# 前期地产判断\n\n${padding}## 需求与回款\n\n[信用传导](../../../macro/test-credit/reports/2026-09-30.md#信用传导)\n\n[内部说明](../../../industries/sectors/private.md)\n\n${padding}` }));
    await linkedPage.route("**/data/documents/test-credit.md", (route) => route.fulfill({ contentType: "text/plain", body:
      `# 信用与地产链\n\n${padding}## 信用传导\n\n[公司现金流](../../../${companyReport.sourcePath.slice("research/".length)}#${companyChapter.id})\n\n${padding}` }));
    await linkedPage.route(`**${companyReport.path}`, (route) => route.fulfill({ contentType: "text/plain", body:
      `${companyBody}\n\n[回到行业需求](../../../../industries/test/reports/2026-09-30.md#需求与回款)\n` }));
    async function expectChapter(id) {
      await linkedPage.waitForFunction((chapter) => {
        const node = document.getElementById(chapter);
        return Boolean(node && node.getBoundingClientRect().top >= 0 && node.getBoundingClientRect().top < 200);
      }, id);
      assert.equal(fragmentId(new URL(linkedPage.url()).hash), id);
    }
    await linkedPage.goto(`${baseURL}/industries?topic=test&version=2026-09-30&view=report&panel=indicators#${encodeURIComponent("需求与回款")}`);
    await expectChapter("需求与回款");
    assert.equal(await linkedPage.getByRole("link", { name: "内部说明", exact: true }).count(), 0);
    assert.equal(await linkedPage.getByRole("region", { name: "行业运行指标" }).count(), 0);
    await linkedPage.getByRole("link", { name: "信用传导", exact: true }).click();
    await expectChapter("信用传导");
    assert.equal(new URL(linkedPage.url()).searchParams.get("version"), "2026-09-30");
    await linkedPage.getByRole("link", { name: "公司现金流", exact: true }).click();
    await expectChapter(companyChapter.id);
    assert.equal(new URL(linkedPage.url()).searchParams.get("version"), companyReport.period);
    await linkedPage.getByTestId("historical-notice").waitFor();
    assert.equal(await linkedPage.getByTestId("live-research-panel").count(), 0);
    await linkedPage.reload();
    await expectChapter(companyChapter.id);
    await linkedPage.getByRole("link", { name: "回到行业需求", exact: true }).click();
    await expectChapter("需求与回款");
    assert.equal(new URL(linkedPage.url()).searchParams.get("version"), "2026-09-30");
    assert.deepEqual(linkedQuoteRequests, []);
    assert.deepEqual(linkedIndicatorRequests, []);
    assert.equal(await linkedPage.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2), false);
    await linkedPage.screenshot({ path: fileURLToPath(new URL("linked-research-mobile.png", output)) });
    await linkedPage.close();
    passed.push("行业、宏观、公司跨层相对链接保留版本与章节；异步定位和刷新恢复，历史隔离与未登记路径保护通过");
  }
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

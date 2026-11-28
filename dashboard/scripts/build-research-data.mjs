import { copyFile, lstat, mkdir, readFile, readdir, realpath, rm, writeFile } from "node:fs/promises";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { loadStandards, reportMetadata, displayEligibility } from "./lib/research-standards.mjs";
import { loadPublications } from "./lib/publications.mjs";
import { loadIndustryCatalog } from "./lib/industry-catalog.mjs";
import { loadScreeningData } from "./lib/screening-data.mjs";
import { currentResults, progressCounts } from "../app/lib/display-policy.mjs";
import { modelArtifactName, researchResourceLink } from "../app/lib/report-reference.mjs";

const dashboardRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(dashboardRoot, "..");
function assertInside(parent, child) {
  const path = relative(parent, child);
  if (!path || path.startsWith(`..${sep}`) || path === "..") throw new Error(`Refusing to write outside ${parent}: ${child}`);
}
function parseJsonLines(text, label) {
  return text.split(/\r?\n/u).filter((line) => line.trim()).map((line, index) => {
    try { return JSON.parse(line); }
    catch (error) { throw new Error(`${label}:${index + 1} is not valid JSON`, { cause: error }); }
  });
}
// Downloads contain readable, bounded research inputs and results only.
export async function exportModelArtifacts(root, output, market, ticker, period, markdown, sourcePath) {
  const route = market === "CN" ? ticker : `${market}-${ticker}`;
  const directory = join(root, "research/companies", market, ticker, "models");
  let canonical;
  try { canonical = await realpath(directory); }
  catch (error) { if (error.code === "ENOENT") return; throw error; }
  const directDirectory = join(await realpath(root), "research/companies", market, ticker, "models");
  if (canonical !== directDirectory) throw new Error("Model directory must not traverse symbolic links");
  const names = new Map([[`${period}.py`, false], [`${period}-engine.py`, false], [`${period}-input.json`, false], [`${period}-output.json`, false]]);
  const hrefs = [...markdown.matchAll(/\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)/gu)].map((match) => match[1]);
  for (const href of hrefs) {
    const link = researchResourceLink(href, sourcePath);
    const prefix = `/data/models/${route}/`;
    if (!link?.startsWith(prefix)) continue;
    const name = link.slice(prefix.length).split(/[?#]/u, 1)[0];
    if (modelArtifactName(name, period)) names.set(name, true);
  }
  async function modules(folder) {
    let entries;
    try { entries = await readdir(join(directory, folder), { withFileTypes: true }); }
    catch (error) { if (error.code === "ENOENT") return; throw error; }
    for (const entry of entries) {
      if (entry.isSymbolicLink()) throw new Error("Model source modules cannot be symbolic links");
      const name = `${folder}/${entry.name}`;
      if (entry.isDirectory()) await modules(name);
      else if (entry.isFile() && modelArtifactName(name, period)) names.set(name, true);
    }
  }
  await modules(period);
  const destination = join(output, "models", route);
  assertInside(output, destination);
  let total = 0;
  for (const [name, required] of [...names].sort(([a], [b]) => a.localeCompare(b))) {
    if (!modelArtifactName(name, period)) throw new Error(`Unsafe model artifact: ${name}`);
    const path = join(directory, name);
    let stat;
    try { stat = await lstat(path); }
    catch (error) { if (error.code === "ENOENT" && !required) continue; throw error; }
    if (!stat.isFile() || stat.isSymbolicLink() || await realpath(path) !== resolve(canonical, name)) {
      throw new Error(`Model artifact must be a direct regular file: ${name}`);
    }
    total += stat.size;
    if (stat.size > 1024 ** 2 || total > 2 * 1024 ** 2) throw new Error(`Research artifact budget exceeded: ${market}:${ticker}/${period}`);
    const bytes = await readFile(path);
    if (name.endsWith(".json")) {
      const data = JSON.parse(bytes);
      if (/lossless|payload|complete_case_manifest/u.test(data?.schema ?? "") || /base64|gzip|xz/u.test(data?.encoding ?? "")) {
        throw new Error(`Archived model output cannot be published: ${name}`);
      }
    }
    await mkdir(destination, { recursive: true });
    await mkdir(dirname(join(destination, name)), { recursive: true });
    await writeFile(join(destination, name), bytes);
  }
}

async function collectReports(root, output, symbol, policy, state) {
  const [market, ticker] = symbol.split(":");
  const route = market === "CN" ? ticker : `${market}-${ticker}`;
  const directory = join(root, "research/companies", market, ticker, "reports");
  let files;
  const periodKey = (name) => {
    const match = /^(20\d{2})-(FY|Q1|H1|Q3)\.md$/u.exec(name);
    const order = { Q1: 1, H1: 2, Q3: 3, FY: 4 };
    return match ? Number(match[1]) * 10 + order[match[2]] : -1;
  };
  try { files = (await readdir(directory)).filter((name) => /^(?:20\d{2})-(?:FY|Q1|H1|Q3)\.md$/u.test(name)).sort((a, b) => periodKey(b) - periodKey(a)); }
  catch (error) { if (error.code === "ENOENT") return []; throw error; }
  const destination = join(output, "reports", route);
  assertInside(output, destination);
  await mkdir(destination, { recursive: true });
  return Promise.all(files.map(async (filename) => {
    const sourcePath = `research/companies/${market}/${ticker}/reports/${filename}`;
    const body = await readFile(join(root, sourcePath));
    await copyFile(join(root, sourcePath), join(destination, filename));
    await exportModelArtifacts(root, output, market, ticker, filename.replace(/\.md$/u, ""), body.toString("utf8"), sourcePath);
    const title = /^#\s+(.+)$/mu.exec(body.toString("utf8"))?.[1] ?? ticker;
    return { period: filename.replace(/\.md$/u, ""), path: `/data/reports/${route}/${filename}`, title,
      ...reportMetadata(sourcePath, body, policy, state) };
  }));
}
async function readOptionalJson(root, relativePath) {
  try { return JSON.parse(await readFile(join(root, relativePath), "utf8")); }
  catch (error) { if (error.code === "ENOENT") return null; throw error; }
}
function resolveAhBridge(symbol, bridgeData) {
  if (!bridgeData) return null;
  const pair = (bridgeData.ahPairs ?? []).find((item) => item.aSymbol === symbol || item.hSymbol === symbol);
  if (pair) {
    const isA = pair.aSymbol === symbol;
    return { role: isA ? "A" : "H", pairSymbol: isA ? pair.hSymbol : pair.aSymbol, pairName: pair.name, issuer: pair.issuer,
      sharesRatio: pair.sharesRatio, hShareStructure: pair.hShareStructure,
      aDividendTaxRateOver1Y: pair.aDividendTaxRateOver1Y, southboundDividendTaxRate: pair.southboundDividendTaxRate,
      taxNote: pair.taxNote };
  }
  if (symbol.startsWith("HK:") && bridgeData.pureHkDefaults) {
    const override = bridgeData.pureHkDefaults.overrides?.[symbol];
    const researchOnly = bridgeData.researchOnly?.symbols.includes(symbol);
    return { role: "HK_ONLY", pairSymbol: null, pairName: null, issuer: symbol, sharesRatio: null,
      hShareStructure: override?.hShareStructure ?? "hk_general", aDividendTaxRateOver1Y: null,
      ...(researchOnly && { southboundUnavailableOn: bridgeData.researchOnly.checkedOn }),
      southboundDividendTaxRate: researchOnly ? null : override?.southboundDividendTaxRate ?? bridgeData.pureHkDefaults.defaultSouthboundDividendTaxRate,
      taxNote: researchOnly ? "沪深港股通可买名单均未收录，股息按税前金额研究。" : override?.taxNote ?? bridgeData.pureHkDefaults.defaultNote };
  }
  return null;
}
export function projectCompany(row, reports, member, policy, task = null, context = {}) {
  const metadata = reports.find((report) => report.sourcePath === row.basis_report_path);
  const display = displayEligibility(row, metadata);
  const issue = row.last_revision?.display_issue;
  const industry = row.industry || member?.industry || "未分类";
  const track = member?.track ?? (display.eligible ? row.decision_profile?.track : null) ?? "compounder";
  const industryTopic = (display.eligible ? row.decision_profile?.industry_topic : null)
    ?? member?.industry_topic ?? context.topicRoutes?.industryToTopic?.[industry] ?? null;
  const industryState = industryTopic ? (context.industryStates?.get(industryTopic) ?? null) : null;
  const ahBridge = resolveAhBridge(row.symbol, context.ahBridge);
  return {
    symbol: row.symbol, ticker: row.symbol.startsWith("CN:") ? row.symbol.slice(3) : row.symbol.replace(":", "-"),
    code: row.symbol.slice(3), market: row.symbol.slice(0, 2),
    quoteCurrency: ({ CN: "CNY", HK: "HKD" })[row.symbol.slice(0, 2)] ?? "CNY",
    issuer: member?.issuer ?? row.symbol, financialBasis: row.financial_basis ?? null,
    securityBasis: row.security_basis ?? null, name: row.name || reports[0]?.title || row.symbol,
    exchange: row.exchange ?? "—", industry,
    track, industryTopic, industryState, ahBridge,
    status: row.status, universeStatus: row.universe_status ?? "unregistered",
    hasResearchState: row.hasResearchState !== false,
    inQualityPool: Boolean(member), qualityTier: member?.tier ?? null,
    updatedAt: row.updated_at ?? null, informationCutoff: row.information_cutoff ?? null,
    display, standardId: metadata?.standardId ?? null, standardLabel: metadata?.standardLabel ?? "未验收",
    acceptedAt: metadata?.acceptedAt ?? null,
    // No old number or conclusion enters the current machine-readable catalog.
    // Historical text remains available only via the explicit report reader.
    summary: display.eligible ? row.summary || "暂无结论摘要。" : "",
    valueRange: display.eligible ? row.value_range ?? null : null,
    valuationNote: display.eligible ? row.valuation_note ?? null : null,
    returnModel: display.eligible ? row.return_model ?? null : null,
    returnModelNote: display.eligible ? row.return_model_note ?? null : null,
    returnModelDisplayIssue: display.eligible && issue?.base_report === row.basis_report_path
      && issue?.model_as_of === row.information_cutoff ? issue : null,
    decisionProfile: display.eligible ? row.decision_profile ?? null : null,
    scenarios: display.eligible ? row.scenarios ?? null : null,
    capitalReturnProfile: display.eligible ? row.capital_return_profile ?? null : null,
    basisReportPath: row.basis_report_path ?? null,
    reportPeriod: row.report_period ?? null,
    reportUpdatedAt: row.last_research_at ?? null,
    latestReportPeriod: reports[0]?.period ?? null,
    pendingReportPeriod: task?.report_period ?? null,
    pendingTaskKind: task?.trigger_kind ?? null,
    reports,
  };
}
async function collectResearchDocuments(output, publications, companies, industryCatalog) {
  await mkdir(join(output, "documents"), { recursive: true });
  for (const doc of publications) await writeFile(join(output, "documents", `${doc.id}.md`), doc.markdown, "utf8");
  await mkdir(join(output, "indicators"), { recursive: true });
  for (const doc of publications) if (doc.indicatorData) await writeFile(join(output, "indicators", `${doc.topic}.json`), JSON.stringify(doc.indicatorData, null, 2), "utf8");
  const documents = publications.map((doc) => { const metadata = { ...doc }; delete metadata.markdown; delete metadata.indicatorData; return metadata; });
  const companyReportPaths = companies.flatMap((company) => company.reports.map((report) => report.sourcePath)).sort();
  await writeFile(join(output, "documents.json"), JSON.stringify({ schemaVersion: 1, documents, companyReportPaths, industryCatalog }, null, 2), "utf8");
}
export function makeExports(catalog, scope) {
  const companies = currentResults(catalog.companies, scope);
  return { generatedAt: catalog.generatedAt, scope, activeStandard: catalog.standard,
    count: companies.length, companies };
}
function csvCell(value) {
  let text = value == null ? "" : String(value);
  if (/^[=+@-]/u.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}
async function exportCurrent(output, catalog, scope, basename) {
  const data = makeExports(catalog, scope);
  await writeFile(join(output, `${basename}.json`), `${JSON.stringify(data)}\n`, "utf8");
  const lines = [["公司", "代码", "研究标准", "资料截止", "完成入库", "价值低端", "价值高端", "币种", "研究结论", "当前摘要"]];
  for (const company of data.companies) lines.push([company.name, company.symbol, company.standardId,
    company.informationCutoff, company.acceptedAt, company.valueRange?.low, company.valueRange?.high,
    company.valueRange?.currency, company.status, company.summary]);
  await writeFile(join(output, `${basename}.csv`), `\uFEFF${lines.map((line) => line.map(csvCell).join(",")).join("\r\n")}\r\n`, "utf8");
}
export async function buildResearchData(root = repositoryRoot) {
  const output = join(root, "dashboard/public/data");
  assertInside(join(root, "dashboard"), output);
  // Validate policy before deleting the prior generated projection. Missing or
  // malformed policy is an error, never a reason to show the old full catalog.
  const policy = await loadStandards(root);
  const pool = JSON.parse(await readFile(join(root, policy.registry.scope_source), "utf8"));
  if (![2, 3].includes(pool.schema_version) || !Array.isArray(pool.companies)) throw new Error("质量池缺失或格式不正确");
  const screening = await loadScreeningData(root);
  const poolCompanies = screening.pools.flatMap((item) => item.companies);
  const members = new Map(poolCompanies.map((company) => [company.symbol, company]));
  if (members.size !== poolCompanies.length) throw new Error("质量池存在重复代码");
  async function rowsFor(market, filename) {
    try { return parseJsonLines(await readFile(join(root, `coverage/${market}/${filename}.jsonl`), "utf8"), filename); }
    catch (error) { if (error.code === "ENOENT" && market !== "cn-a") return []; throw error; }
  }
  const activeStateMarkets = ["cn-a", "hk"];
  const activeCompanyMarkets = ["CN", "HK"];
  const states = (await Promise.all(activeStateMarkets.map((m) => rowsFor(m, "research_state")))).flat();
  const queue = (await Promise.all(activeStateMarkets.map((m) => rowsFor(m, "research_queue")))).flat();
  const stateSymbols = new Set(states.map((row) => row.symbol));
  if (stateSymbols.size !== states.length) throw new Error("研究状态代码重复");
  const sourceStateCount = states.length;
  const archiveSymbols = [];
  for (const market of activeCompanyMarkets) {
    let directories;
    try { directories = await readdir(join(root, "research/companies", market), { withFileTypes: true }); }
    catch (error) { if (error.code === "ENOENT") continue; throw error; }
    for (const entry of directories) {
      const symbol = `${market}:${entry.name}`;
      if (entry.isDirectory() && /^(?:CN:[0-9]{6}|HK:[0-9]{5})$/u.test(symbol)
        && !stateSymbols.has(symbol) && !members.has(symbol)) archiveSymbols.push(symbol);
    }
  }
  // Pool-only identities are progress placeholders; archive-only identities
  // make every retained report readable without creating research state.
  const rows = [...states, ...poolCompanies.filter((member) => !stateSymbols.has(member.symbol))
    .map((member) => ({ symbol: member.symbol, name: member.name, industry: member.industry,
      status: "unregistered", hasResearchState: false, report_period: null,
      basis_report_path: null })), ...archiveSymbols.map((symbol) => ({ symbol, name: null,
      industry: "历史档案", status: "unregistered", universe_status: "inactive",
      hasResearchState: false, report_period: null, basis_report_path: null }))];
  const [publications, industryCatalog, topicRoutes, ahBridge, qdiiCatalog, globalLeaders] = await Promise.all([
    loadPublications(root),
    loadIndustryCatalog(root),
    readOptionalJson(root, "research/industries/topic-routes.json"),
    readOptionalJson(root, "research/markets/ah-southbound-bridge.json"),
    readOptionalJson(root, "research/macro/us-broad-etf/qdii-catalog.json"),
    readOptionalJson(root, "research/benchmarks/global-leaders.json"),
  ]);
  const industryTopicLabels = new Map((industryCatalog?.topics ?? []).map((item) => [item.id, item.label]));
  const industryStates = new Map();
  let macroRegime = null;
  let marketBenchmarks = null;
  for (const doc of publications) {
    if (doc.status !== "published" || doc.type !== "report") continue;
    if (doc.kind === "industry" && doc.regionId === "cn" && doc.industryState && !industryStates.has(doc.topic)) {
      industryStates.set(doc.topic, {
        ...doc.industryState,
        topic: doc.topic,
        label: industryTopicLabels.get(doc.topic) ?? doc.topic,
        documentId: doc.id,
        publishedOn: doc.publishedOn,
        informationCutoff: doc.informationCutoff,
      });
    } else if (doc.kind === "macro" && doc.macroState) {
      if (doc.topic === "cross-market-regime" && !macroRegime) {
        macroRegime = { documentId: doc.id, publishedOn: doc.publishedOn, informationCutoff: doc.informationCutoff, ...doc.macroState };
      } else if (doc.topic === "market-valuation" && !marketBenchmarks) {
        marketBenchmarks = { documentId: doc.id, publishedOn: doc.publishedOn, informationCutoff: doc.informationCutoff, ...doc.macroState };
      }
    }
  }
  const projectContext = { topicRoutes, industryStates, ahBridge };
  await rm(output, { recursive: true, force: true });
  await mkdir(output, { recursive: true });
  await writeFile(join(output, "screening-pools.json"), JSON.stringify(screening, null, 2) + "\n", "utf8");
  const tasksBySymbol = new Map(queue.map((item) => [item.symbol, item]));
  const companies = [];
  for (const row of rows) {
    if (!/^(?:CN:[0-9]{6}|HK:[0-9]{5})$/u.test(row.symbol)) throw new Error(`无效证券代码: ${row.symbol}`);
    const reports = await collectReports(root, output, row.symbol, policy, row);
    companies.push(projectCompany(row, reports, members.get(row.symbol), policy,
      tasksBySymbol.get(row.symbol) ?? null, projectContext));
  }
  await collectResearchDocuments(output, publications, companies, industryCatalog);
  const status = Object.fromEntries(["unseen", "ignore", "covered", "unregistered"]
    .map((name) => [name, companies.filter((company) => company.status === name).length]));
  const queued = queue.filter((item) => item.status === "queued").length;
  const running = queue.filter((item) => item.status === "running").length;
  const catalog = {
    schemaVersion: 2, generatedAt: new Date().toISOString(), standard: policy.active,
    standards: policy.registry.standards,
    scope: { id: "quality_pool", label: "重点跟踪池", asOf: screening.pools.map((p) => p.asOf).sort().at(-1), count: members.size },
    environment: { macroRegime, marketBenchmarks, qdiiCatalog, globalBenchmarksCount: globalLeaders?.leaders?.length ?? 0 },
    stats: { total: companies.length, researchStateRows: sourceStateCount,
      active: states.filter((row) => row.universe_status === "active").length,
      reports: companies.filter((company) => company.reports.length).length,
      status, queue: { queued, running, total: queue.length },
      current: progressCounts(companies), allStandard: progressCounts(companies, "all_standard") },
    companies,
  };
  await writeFile(join(output, "research-catalog.json"), `${JSON.stringify(catalog)}\n`, "utf8");
  await writeFile(join(output, "global-benchmarks.json"), JSON.stringify({
    schemaVersion: 1,
    asOf: globalLeaders?.asOf ?? null,
    purpose: globalLeaders?.purpose ?? null,
    leaders: globalLeaders?.leaders ?? [],
  }, null, 2) + "\n", "utf8");
  const decisionCompanies = currentResults(companies, "all_standard").map((company) => ({
    symbol: company.symbol,
    ticker: company.ticker,
    name: company.name,
    market: company.market,
    issuer: company.issuer,
    quoteCurrency: company.quoteCurrency,
    industry: company.industry,
    inQualityPool: company.inQualityPool,
    qualityTier: company.qualityTier,
    track: company.track,
    industryTopic: company.industryTopic,
    industryState: company.industryState,
    status: company.status,
    reportPeriod: company.reportPeriod,
    informationCutoff: company.informationCutoff,
    acceptedAt: company.acceptedAt,
    basisReportPath: company.basisReportPath,
    summary: company.summary,
    valueRange: company.valueRange,
    valuationNote: company.valuationNote,
    returnModel: company.returnModel,
    returnModelNote: company.returnModelNote,
    decisionProfile: company.decisionProfile,
    scenarios: company.scenarios,
    capitalReturnProfile: company.capitalReturnProfile,
    ahBridge: company.ahBridge,
  }));
  await writeFile(join(output, "decision-index.json"), JSON.stringify({
    schemaVersion: 1,
    generatedAt: catalog.generatedAt,
    activeStandard: policy.active.id,
    tradingProfile: {
      activeMarkets: activeCompanyMarkets,
      hkChannel: ahBridge?.channel ?? "southbound_stock_connect",
      usChannel: "domestic_qdii_etf",
      taxRules: ahBridge?.taxRules ?? null,
    },
    macro: {
      regime: macroRegime,
      marketBenchmarks,
      qdiiCatalog,
    },
    industries: [...industryStates.values()].sort((a, b) => a.topic.localeCompare(b.topic)),
    globalBenchmarks: globalLeaders?.leaders ?? [],
    ahPairs: ahBridge?.ahPairs ?? [],
    companies: decisionCompanies,
  }, null, 2) + "\n", "utf8");
  await exportCurrent(output, catalog, "quality_pool", "current-research");
  await exportCurrent(output, catalog, "all_standard", "all-current-research");
  for (const market of activeCompanyMarkets) {
    const subset = { ...catalog, companies: companies.filter((c) => c.market === market) };
    await exportCurrent(output, subset, "quality_pool", `current-research-${market}`);
    await exportCurrent(output, subset, "all_standard", `all-current-research-${market}`);
  }
  const progress = companies.filter((company) => company.inQualityPool).map((company) => ({
    symbol: company.symbol, name: company.name, qualityTier: company.qualityTier,
    hasResearchState: company.hasResearchState, display: company.display,
    informationCutoff: company.informationCutoff, reportPeriod: company.reportPeriod,
    basisReportPath: company.basisReportPath, pendingReportPeriod: company.pendingReportPeriod,
  }));
  await writeFile(join(output, "research-progress.json"), JSON.stringify({ scope: catalog.scope,
    standard: catalog.standard, stats: catalog.stats.current, companies: progress }), "utf8");
  process.stdout.write(`Research catalog: ${sourceStateCount} state rows; ${members.size} pool companies; ${catalog.stats.current.completed} current-standard results\n`);
  return catalog;
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await buildResearchData();

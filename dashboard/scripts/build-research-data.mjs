import { copyFile, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { loadStandards, reportMetadata, displayEligibility } from "./lib/research-standards.mjs";
import { currentResults, progressCounts } from "../app/lib/display-policy.mjs";

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
async function collectReports(root, output, ticker, policy) {
  const directory = join(root, "research/companies/CN", ticker, "reports");
  let files;
  try { files = (await readdir(directory)).filter((name) => /^\d{4}-\d{2}-\d{2}(?:-\d{2})?\.md$/u.test(name)).sort().reverse(); }
  catch (error) { if (error.code === "ENOENT") return []; throw error; }
  const destination = join(output, "reports", ticker);
  assertInside(output, destination);
  await mkdir(destination, { recursive: true });
  return Promise.all(files.map(async (filename) => {
    const sourcePath = `research/companies/CN/${ticker}/reports/${filename}`;
    const body = await readFile(join(root, sourcePath));
    await copyFile(join(root, sourcePath), join(destination, filename));
    return { date: filename.replace(/\.md$/u, ""), path: `/data/reports/${ticker}/${filename}`,
      ...reportMetadata(sourcePath, body, policy) };
  }));
}
export function projectCompany(row, reports, member, policy) {
  const metadata = reports.find((report) => report.sourcePath === row.report_path);
  const display = displayEligibility(row, metadata, policy);
  const issue = row.last_revision?.display_issue;
  return {
    symbol: row.symbol, ticker: row.symbol.replace(/^CN:/u, ""), name: row.name,
    exchange: row.exchange ?? "—", industry: row.industry || member?.industry || "未分类",
    status: row.status, universeStatus: row.universe_status ?? "unregistered",
    hasResearchState: row.hasResearchState !== false,
    inQualityPool: Boolean(member), qualityTier: member?.tier ?? null,
    updatedAt: row.updated_at ?? null, informationCutoff: row.information_cutoff ?? null,
    invalidation: row.invalidation ?? null, candidateSince: row.candidate_since ?? null,
    display, standardId: metadata?.standardId ?? null, standardLabel: metadata?.standardLabel ?? "未验收",
    acceptedAt: metadata?.acceptedAt ?? null,
    // No old number or conclusion enters the current machine-readable catalog.
    // Historical text remains available only via the explicit report reader.
    summary: display.eligible ? row.summary || "暂无结论摘要。" : "",
    valueRange: display.eligible ? row.value_range ?? null : null,
    valuationNote: display.eligible ? row.valuation_note ?? null : null,
    returnModel: display.eligible ? row.return_model ?? null : null,
    returnModelNote: display.eligible ? row.return_model_note ?? null : null,
    returnModelDisplayIssue: display.eligible && issue?.base_report === row.report_path
      && issue?.model_as_of === row.information_cutoff ? issue : null,
    reportPath: row.report_path ?? null, reportDate: metadata?.date ?? null, reports,
    eventTriggerCount: (row.event_triggers ?? []).length,
  };
}
async function collectResearchDocuments(root, output) {
  let sectors;
  try { sectors = (await readdir(join(root, "research/industries/sectors"))).filter((file) => file.endsWith(".md")).sort(); }
  catch (error) { if (error.code !== "ENOENT") throw error; sectors = []; }
  const sources = [
    ...sectors.map((file) => ({ id: file.slice(0, -3), kind: "industry", path: `research/industries/sectors/${file}` })),
    { id: "automotive-lighting", kind: "industry", path: "research/industries/automotive-lighting.md" },
    { id: "industry-guide", kind: "industry", path: "research/industries/README.md" },
    { id: "selection-current", kind: "selection", path: "selection/current.md" },
    { id: "selection-principles", kind: "selection", path: "selection/principles.md" },
    { id: "selection-process", kind: "selection", path: "prompts/selection/long-term-selection.md" },
  ];
  const documents = [];
  const destination = join(output, "documents");
  await mkdir(destination, { recursive: true });
  for (const source of sources) {
    let markdown;
    try { markdown = await readFile(join(root, source.path), "utf8"); }
    catch (error) { if (error.code === "ENOENT") continue; throw error; }
    const title = /^#\s+(.+)$/mu.exec(markdown)?.[1] ?? source.id;
    const industries = /^适用二级行业：\s*(.+)$/mu.exec(markdown)?.[1].split("、").map((name) => name.trim().replace(/。$/u, "")) ?? [];
    const path = `/data/documents/${source.id}.md`;
    await writeFile(join(output, path.replace("/data/", "")), markdown, "utf8");
    documents.push({ ...source, sourcePath: source.path, path, title, industries });
  }
  await writeFile(join(output, "documents.json"), JSON.stringify({ documents }, null, 2), "utf8");
}
export function makeExports(catalog, scope) {
  const companies = currentResults(catalog.companies, scope);
  return { generatedAt: catalog.generatedAt, scope, activeStandard: catalog.standard,
    count: companies.length, companies };
}
function csvCell(value) {
  let text = value == null ? "" : String(value);
  if (/^[=+@\-]/u.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}
async function exportCurrent(output, catalog, scope, basename) {
  const data = makeExports(catalog, scope);
  await writeFile(join(output, `${basename}.json`), `${JSON.stringify(data)}\n`, "utf8");
  const lines = [["公司", "代码", "研究标准", "资料截止", "验收时间", "价值低端", "价值高端", "币种", "研究结论", "当前摘要"]];
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
  if (pool.schema_version !== 2 || !Array.isArray(pool.companies)) throw new Error("质量池缺失或格式不正确");
  const members = new Map(pool.companies.map((company) => [company.symbol, company]));
  if (members.size !== pool.companies.length) throw new Error("质量池存在重复代码");
  const states = parseJsonLines(await readFile(join(root, "coverage/cn-a/research_state.jsonl"), "utf8"), "research_state");
  const queue = parseJsonLines(await readFile(join(root, "coverage/cn-a/research_queue.jsonl"), "utf8"), "research_queue");
  const stateSymbols = new Set(states.map((row) => row.symbol));
  if (stateSymbols.size !== states.length) throw new Error("研究状态代码重复");
  const sourceStateCount = states.length;
  // Pool-only identities are progress placeholders, not new research-state rows.
  const rows = [...states, ...pool.companies.filter((member) => !stateSymbols.has(member.symbol))
    .map((member) => ({ symbol: member.symbol, name: member.name, industry: member.industry,
      status: "unregistered", hasResearchState: false, report_path: null }))];
  await rm(output, { recursive: true, force: true });
  await mkdir(output, { recursive: true });
  await collectResearchDocuments(root, output);
  const companies = [];
  for (const row of rows) {
    const ticker = row.symbol.replace(/^CN:/u, "");
    if (!/^\d{6}$/u.test(ticker)) throw new Error(`无效证券代码: ${row.symbol}`);
    const reports = row.report_path ? await collectReports(root, output, ticker, policy) : [];
    companies.push(projectCompany(row, reports, members.get(row.symbol), policy));
  }
  const status = Object.fromEntries(["unseen", "ignore", "candidate", "covered", "stale", "unregistered"]
    .map((name) => [name, companies.filter((company) => company.status === name).length]));
  const queued = queue.filter((item) => item.status === "queued").length;
  const running = queue.filter((item) => item.status === "running").length;
  const catalog = {
    schemaVersion: 2, generatedAt: new Date().toISOString(), standard: policy.active,
    standards: policy.registry.standards,
    scope: { id: "quality_pool", label: "核心研究池", asOf: pool.as_of, count: members.size },
    stats: { total: companies.length, researchStateRows: sourceStateCount,
      active: states.filter((row) => row.universe_status === "active").length,
      reports: companies.filter((company) => company.reports.length).length,
      status, queue: { queued, running, total: queue.length },
      current: progressCounts(companies), allStandard: progressCounts(companies, "all_standard") },
    companies,
  };
  await writeFile(join(output, "research-catalog.json"), `${JSON.stringify(catalog)}\n`, "utf8");
  await exportCurrent(output, catalog, "quality_pool", "current-research");
  await exportCurrent(output, catalog, "all_standard", "all-current-research");
  const progress = companies.filter((company) => company.inQualityPool).map((company) => ({
    symbol: company.symbol, name: company.name, qualityTier: company.qualityTier,
    hasResearchState: company.hasResearchState, display: company.display,
    informationCutoff: company.informationCutoff, reportPath: company.reportPath,
  }));
  await writeFile(join(output, "research-progress.json"), JSON.stringify({ scope: catalog.scope,
    standard: catalog.standard, stats: catalog.stats.current, companies: progress }), "utf8");
  process.stdout.write(`Research catalog: ${sourceStateCount} state rows; ${members.size} pool companies; ${catalog.stats.current.completed} current-standard results\n`);
  return catalog;
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await buildResearchData();

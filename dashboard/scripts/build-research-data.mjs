import { createHash } from "node:crypto";
import { copyFile, lstat, mkdir, readFile, readdir, realpath, rm, writeFile } from "node:fs/promises";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { loadStandards, reportMetadata, displayEligibility } from "./lib/research-standards.mjs";
import { currentResults, progressCounts } from "../app/lib/display-policy.mjs";

import { xzManifestEntry, verifyXzBytes } from "./lib/model-xz.mjs";
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
async function collectReports(root, output, ticker, policy, state) {
  const directory = join(root, "research/companies/CN", ticker, "reports");
  let files;
  const periodKey = (name) => {
    const match = /^(20\d{2})-(FY|Q1|H1|Q3)\.md$/u.exec(name);
    const order = { Q1: 1, H1: 2, Q3: 3, FY: 4 };
    return match ? Number(match[1]) * 10 + order[match[2]] : -1;
  };
  try { files = (await readdir(directory)).filter((name) => /^(?:20\d{2})-(?:FY|Q1|H1|Q3)\.md$/u.test(name)).sort((a, b) => periodKey(b) - periodKey(a)); }
  catch (error) { if (error.code === "ENOENT") return []; throw error; }
  const destination = join(output, "reports", ticker);
  assertInside(output, destination);
  await mkdir(destination, { recursive: true });
  return Promise.all(files.map(async (filename) => {
    const sourcePath = `research/companies/CN/${ticker}/reports/${filename}`;
    const body = await readFile(join(root, sourcePath));
    await copyFile(join(root, sourcePath), join(destination, filename));
    // Keep the legacy source/output pair, then close over reader-linked allowed
    // auxiliaries and the explicit split-output manifest. Never execute artifacts.
    const period = filename.replace(/\.md$/u, "");
    const names = new Map([[`${period}.py`, false], [`${period}-output.json`, false]]);
    const markdown = body.toString("utf8");
    const hrefs = [
      ...[...markdown.matchAll(/\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)/gu)].map((m) => m[1]),
      ...[...markdown.matchAll(/^\s*\[[^\]]+\]:\s*(\S+)/gmu)].map((m) => m[1]),
    ];
    for (const href of hrefs) {
      const link = researchResourceLink(href, sourcePath);
      const prefix = `/data/models/${ticker}/`;
      if (!link?.startsWith(prefix)) continue;
      const name = link.slice(prefix.length).split(/[?#]/u, 1)[0];
      if (modelArtifactName(name, period)) names.set(name, true);
    }
    const artifactOrder = (a, b) => Number(b === `${period}-output.json`) - Number(a === `${period}-output.json`) || (a < b ? -1 : a > b ? 1 : 0);
    const pending = [...names.keys()].sort(artifactOrder);
    const exported = new Set();
    const expectedFiles = new Map();
    const xzManifests = new Map();
    const canonicalModelDirectory = join(await realpath(root), "research/companies/CN", ticker, "models");
    const modelDestination = join(output, "models", ticker);
    assertInside(output, modelDestination);
    while (pending.length) {
      const modelName = pending.shift();
      if (exported.has(modelName)) continue;
      if (!modelArtifactName(modelName, period)) throw new Error(`Unsafe model artifact: ${modelName}`);
      if (modelName.startsWith(`${period}-case-`) && !expectedFiles.has(modelName)) throw new Error(`Case artifact is absent from its split manifest: ${modelName}`);
      if (modelName.endsWith("-output.json.xz") && !xzManifests.has(modelName)) throw new Error(`XZ artifact is absent from its transport manifest: ${modelName}`);
      const modelSource = join(root, "research/companies/CN", ticker, "models", modelName);
      let modelBody;
      try {
        const stat = await lstat(modelSource);
        if (!stat.isFile() || stat.isSymbolicLink()) throw new Error(`Model artifact must be a regular file: ${modelName}`);
        if (await realpath(modelSource) !== join(canonicalModelDirectory, modelName)) throw new Error(`Model artifact escapes its company directory: ${modelName}`);
        modelBody = await readFile(modelSource);
      } catch (error) {
        if (error.code === "ENOENT" && !names.get(modelName)) continue;
        throw error;
      }
      const expected = expectedFiles.get(modelName);
      if (expected && (modelBody.length !== expected.bytes
          || createHash("sha256").update(modelBody).digest("hex") !== expected.file_sha256)) {
        throw new Error(`Split model artifact does not match manifest: ${modelName}`);
      }
      if (xzManifests.has(modelName)) verifyXzBytes(modelBody, xzManifests.get(modelName));
      await mkdir(modelDestination, { recursive: true });
      await writeFile(join(modelDestination, modelName), modelBody);
      exported.add(modelName);
      if (modelName === `${period}-output.json`) {
        let manifest;
        try { manifest = JSON.parse(modelBody); } catch { /* Legacy bytes remain downloadable. */ }
        if (manifest?.schema === "trading_os_lossless_json_xz_v1") {
          const entry = xzManifestEntry(manifest, period);
          names.set(entry.file, true);
          xzManifests.set(entry.file, manifest);
          expectedFiles.set(entry.file, { bytes: entry.compressed_bytes, file_sha256: entry.compressed_sha256 });
          pending.push(entry.file);
          pending.sort(artifactOrder);
        }
        if (manifest?.schema === "cn300033_complete_case_manifest_v1") {
          if (!manifest.case_files || typeof manifest.case_files !== "object" || Array.isArray(manifest.case_files)) {
            throw new Error("Invalid split model manifest");
          }
          const seen = new Set();
          for (const [caseName, entry] of Object.entries(manifest.case_files).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)) {
            const name = entry?.file;
            if (!/^[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*$/u.test(caseName)
                || name !== `${period}-case-${caseName}.json` || !modelArtifactName(name, period)
                || seen.has(name) || !Number.isSafeInteger(entry.bytes) || entry.bytes < 0
                || !/^[a-f0-9]{64}$/u.test(entry.file_sha256 ?? "")) {
              throw new Error(`Unsafe split model manifest entry: ${caseName}`);
            }
            seen.add(name); names.set(name, true); expectedFiles.set(name, entry);
            // Manifest is processed before its dependencies; a reader-linked case
            // already copied is also rechecked rather than bypassing its digest.
            if (exported.has(name)) {
              const bytes = await readFile(join(modelDestination, name));
              if (bytes.length !== entry.bytes || createHash("sha256").update(bytes).digest("hex") !== entry.file_sha256) {
                throw new Error(`Split model artifact does not match manifest: ${name}`);
              }
            } else pending.push(name);
          }
          pending.sort(artifactOrder);
        }
      }
    }
    const title = /^#\s+(.+)$/mu.exec(body.toString("utf8"))?.[1] ?? ticker;
    return { period: filename.replace(/\.md$/u, ""), path: `/data/reports/${ticker}/${filename}`, title,
      ...reportMetadata(sourcePath, body, policy, state) };
  }));
}
export function projectCompany(row, reports, member, policy, task = null) {
  const metadata = reports.find((report) => report.sourcePath === row.basis_report_path);
  const display = displayEligibility(row, metadata);
  const issue = row.last_revision?.display_issue;
  return {
    symbol: row.symbol, ticker: row.symbol.replace(/^CN:/u, ""), name: row.name || reports[0]?.title || row.symbol,
    exchange: row.exchange ?? "—", industry: row.industry || member?.industry || "未分类",
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
    basisReportPath: row.basis_report_path ?? null,
    reportPeriod: row.report_period ?? null,
    reportUpdatedAt: row.last_research_at ?? null,
    latestReportPeriod: reports[0]?.period ?? null,
    pendingReportPeriod: task?.report_period ?? null,
    pendingTaskKind: task?.trigger_kind ?? null,
    reports,
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
  if (pool.schema_version !== 2 || !Array.isArray(pool.companies)) throw new Error("质量池缺失或格式不正确");
  const members = new Map(pool.companies.map((company) => [company.symbol, company]));
  if (members.size !== pool.companies.length) throw new Error("质量池存在重复代码");
  const states = parseJsonLines(await readFile(join(root, "coverage/cn-a/research_state.jsonl"), "utf8"), "research_state");
  const queue = parseJsonLines(await readFile(join(root, "coverage/cn-a/research_queue.jsonl"), "utf8"), "research_queue");
  const stateSymbols = new Set(states.map((row) => row.symbol));
  if (stateSymbols.size !== states.length) throw new Error("研究状态代码重复");
  const sourceStateCount = states.length;
  const companyDirectories = await readdir(join(root, "research/companies/CN"), { withFileTypes: true });
  const archiveSymbols = companyDirectories.filter((entry) => entry.isDirectory() && /^\d{6}$/u.test(entry.name))
    .map((entry) => `CN:${entry.name}`).filter((symbol) => !stateSymbols.has(symbol) && !members.has(symbol));
  // Pool-only identities are progress placeholders; archive-only identities
  // make every retained report readable without creating research state.
  const rows = [...states, ...pool.companies.filter((member) => !stateSymbols.has(member.symbol))
    .map((member) => ({ symbol: member.symbol, name: member.name, industry: member.industry,
      status: "unregistered", hasResearchState: false, report_period: null,
      basis_report_path: null })), ...archiveSymbols.map((symbol) => ({ symbol, name: null,
      industry: "历史档案", status: "unregistered", universe_status: "inactive",
      hasResearchState: false, report_period: null, basis_report_path: null }))];
  await rm(output, { recursive: true, force: true });
  await mkdir(output, { recursive: true });
  await collectResearchDocuments(root, output);
  const tasksBySymbol = new Map(queue.map((item) => [item.symbol, item]));
  const companies = [];
  for (const row of rows) {
    const ticker = row.symbol.replace(/^CN:/u, "");
    if (!/^\d{6}$/u.test(ticker)) throw new Error(`无效证券代码: ${row.symbol}`);
    const reports = await collectReports(root, output, ticker, policy, row);
    companies.push(projectCompany(row, reports, members.get(row.symbol), policy,
      tasksBySymbol.get(row.symbol) ?? null));
  }
  const status = Object.fromEntries(["unseen", "ignore", "covered", "unregistered"]
    .map((name) => [name, companies.filter((company) => company.status === name).length]));
  const queued = queue.filter((item) => item.status === "queued").length;
  const running = queue.filter((item) => item.status === "running").length;
  const catalog = {
    schemaVersion: 2, generatedAt: new Date().toISOString(), standard: policy.active,
    standards: policy.registry.standards,
    scope: { id: "quality_pool", label: "重点跟踪池", asOf: pool.as_of, count: members.size },
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
    informationCutoff: company.informationCutoff, reportPeriod: company.reportPeriod,
    basisReportPath: company.basisReportPath, pendingReportPeriod: company.pendingReportPeriod,
  }));
  await writeFile(join(output, "research-progress.json"), JSON.stringify({ scope: catalog.scope,
    standard: catalog.standard, stats: catalog.stats.current, companies: progress }), "utf8");
  process.stdout.write(`Research catalog: ${sourceStateCount} state rows; ${members.size} pool companies; ${catalog.stats.current.completed} current-standard results\n`);
  return catalog;
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await buildResearchData();

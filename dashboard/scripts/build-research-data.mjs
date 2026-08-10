import { copyFile, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const dashboardRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(dashboardRoot, "..");
const statePath = join(repositoryRoot, "coverage", "cn-a", "research_state.jsonl");
const queuePath = join(repositoryRoot, "coverage", "cn-a", "research_queue.jsonl");
const reportsRoot = join(repositoryRoot, "research", "companies", "CN");
const outputRoot = join(dashboardRoot, "public", "data");

function assertInside(parent, child) {
  const path = relative(parent, child);
  if (!path || path.startsWith(`..${sep}`) || path === "..") {
    throw new Error(`Refusing to write outside ${parent}: ${child}`);
  }
}

function parseJsonLines(text, label) {
  return text
    .split(/\r?\n/u)
    .filter((line) => line.trim())
    .map((line, index) => {
      try {
        return JSON.parse(line);
      } catch (error) {
        throw new Error(`${label}:${index + 1} is not valid JSON`, { cause: error });
      }
    });
}

function reportDate(filename) {
  return filename.replace(/\.md$/u, "");
}

function compactPriceLevels(row) {
  const runtime = row.price_monitor?.levels ?? {};
  return (row.price_levels ?? []).map((level) => {
    const monitored = runtime[level.id] ?? {};
    return {
      id: level.id,
      label: level.label,
      threshold: level.threshold,
      rearmAbove: level.rearm_above ?? level.threshold,
      armed: monitored.armed ?? true,
      lastClose: monitored.last_close ?? null,
      lastScanDate: monitored.last_scan_date ?? null,
      lastHitDate: monitored.last_hit_date ?? null,
    };
  });
}

async function collectReports(ticker) {
  const sourceDirectory = join(reportsRoot, ticker, "reports");
  let files = [];
  try {
    files = (await readdir(sourceDirectory))
      .filter((filename) => /^\d{4}-\d{2}-\d{2}(?:-\d{2})?\.md$/u.test(filename))
      .sort()
      .reverse();
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }

  if (!files.length) return [];
  const destinationDirectory = join(outputRoot, "reports", ticker);
  assertInside(outputRoot, destinationDirectory);
  await mkdir(destinationDirectory, { recursive: true });
  await Promise.all(
    files.map((filename) =>
      copyFile(join(sourceDirectory, filename), join(destinationDirectory, filename)),
    ),
  );
  return files.map((filename) => ({
    date: reportDate(filename),
    path: `/data/reports/${ticker}/${filename}`,
  }));
}

async function main() {
  assertInside(dashboardRoot, outputRoot);
  const [stateText, queueText] = await Promise.all([
    readFile(statePath, "utf8"),
    readFile(queuePath, "utf8"),
  ]);
  const states = parseJsonLines(stateText, statePath);
  const queue = parseJsonLines(queueText, queuePath);

  await rm(outputRoot, { recursive: true, force: true });
  await mkdir(outputRoot, { recursive: true });

  const companies = [];
  for (const row of states) {
    const ticker = String(row.symbol ?? "").replace(/^CN:/u, "");
    const reports = /^\d{6}$/u.test(ticker) && row.report_path ? await collectReports(ticker) : [];
    const priceLevels = compactPriceLevels(row);
    const latestReport = reports[0] ?? null;
    const monitoredClose = priceLevels.find((level) => level.lastClose !== null) ?? null;
    companies.push({
      symbol: row.symbol,
      ticker,
      name: row.name,
      exchange: row.exchange,
      industry: row.industry || "未分类",
      status: row.status,
      universeStatus: row.universe_status,
      updatedAt: row.updated_at,
      summary: row.summary || "暂无结论摘要。",
      informationCutoff: row.information_cutoff,
      invalidation: row.invalidation,
      candidateSince: row.candidate_since,
      valueRange: row.value_range
        ? {
            currency: row.value_range.currency,
            low: row.value_range.low,
            high: row.value_range.high,
          }
        : null,
      priceLevels,
      lastClose: monitoredClose?.lastClose ?? null,
      lastCloseDate: monitoredClose?.lastScanDate ?? null,
      reportPath: row.report_path,
      reportDate: latestReport?.date ?? null,
      reports,
      eventTriggerCount: (row.event_triggers ?? []).length,
    });
  }

  const statusCounts = Object.fromEntries(
    ["unseen", "ignore", "candidate", "covered", "stale"].map((status) => [
      status,
      companies.filter((company) => company.status === status).length,
    ]),
  );
  const queueCounts = Object.fromEntries(
    ["queued", "running"].map((status) => [
      status,
      queue.filter((task) => task.status === status).length,
    ]),
  );

  const catalog = {
    generatedAt: new Date().toISOString(),
    stats: {
      total: companies.length,
      active: companies.filter((company) => company.universeStatus === "active").length,
      reports: companies.filter((company) => company.reports.length > 0).length,
      status: statusCounts,
      queue: { ...queueCounts, total: queue.length },
    },
    companies,
  };

  await writeFile(
    join(outputRoot, "research-catalog.json"),
    `${JSON.stringify(catalog)}\n`,
    "utf8",
  );
  process.stdout.write(
    `Research catalog: ${companies.length} companies, ${catalog.stats.reports} report companies\n`,
  );
}

await main();

import { readFile, realpath } from "node:fs/promises";
import { resolve } from "node:path";
import { loadIndustryIndicators } from "./industry-indicators.mjs";
import { loadIndustryCatalog } from "./industry-catalog.mjs";

function validDate(value) {
  return typeof value === "string" && /^20\d{2}-\d{2}-\d{2}$/u.test(value)
    && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
}
function nonblank(value) { return typeof value === "string" && value.trim().length > 0; }
const CYCLE_STAGES = new Set(["upcycle_tight", "inflection_bottom", "mature_stable", "downcycle_clearing", "overcapacity"]);
const PROFIT_TRENDS = new Set(["expanding", "stable", "contracting"]);
const MACRO_ALIGNMENTS = new Set(["tailwind", "neutral", "headwind"]);
function validateIndustryState(state) {
  if (!state || typeof state !== "object" || Array.isArray(state)) throw new Error("行业状态格式错误");
  if (!CYCLE_STAGES.has(state.cycleStage)) throw new Error("行业状态 cycleStage 无效");
  if (!PROFIT_TRENDS.has(state.profitPoolTrend)) throw new Error("行业状态 profitPoolTrend 无效");
  if (!MACRO_ALIGNMENTS.has(state.macroAlignment)) throw new Error("行业状态 macroAlignment 无效");
  if (typeof state.inflectionCandidate !== "boolean") throw new Error("行业状态 inflectionCandidate 必须为布尔值");
  if (!nonblank(state.macroTransmission)) throw new Error("行业状态 macroTransmission 不能为空");
  if (!Array.isArray(state.keyDrivers) || !state.keyDrivers.length || !state.keyDrivers.every(nonblank)) {
    throw new Error("行业状态 keyDrivers 必须为非空字符串数组");
  }
}
function validateMacroState(state) {
  if (!state || typeof state !== "object" || Array.isArray(state)) throw new Error("宏观状态格式错误");
  if (!validDate(state.asOf)) throw new Error("宏观状态 asOf 日期无效");
  if (state.regimeSummary !== undefined && !nonblank(state.regimeSummary)) throw new Error("宏观状态 regimeSummary 不能为空");
  const hasFactors = Array.isArray(state.factors) && state.factors.length > 0;
  const hasBenchmarks = Array.isArray(state.benchmarks) && state.benchmarks.length > 0;
  if (!hasFactors && !hasBenchmarks) throw new Error("宏观状态至少需包含 factors 或 benchmarks");
  if (state.factors !== undefined) {
    if (!hasFactors) throw new Error("宏观状态 factors 必须为非空数组");
    for (const f of state.factors) {
      if (!f || typeof f !== "object" || !nonblank(f.id) || !nonblank(f.label) || !nonblank(f.direction) || !nonblank(f.reading) || !nonblank(f.implication)) {
        throw new Error("宏观状态 factor 字段不完整");
      }
    }
  }
  if (state.benchmarks !== undefined) {
    if (!hasBenchmarks) throw new Error("宏观状态 benchmarks 必须为非空数组");
    for (const b of state.benchmarks) {
      if (!b || typeof b !== "object" || !nonblank(b.id) || !nonblank(b.name) || !["CN", "HK", "US"].includes(b.market) || !nonblank(b.note)) {
        throw new Error("宏观状态 benchmark 字段不完整");
      }
    }
  }
}

// Only explicitly published reader-facing documents enter the website.
export async function loadPublications(root) {
  let manifest;
  try { manifest = JSON.parse(await readFile(resolve(root, "research/publications.json"), "utf8")); }
  catch (error) { if (error.code === "ENOENT") return []; throw error; }
  if (manifest.schemaVersion !== 1 || !Array.isArray(manifest.documents)) throw new Error("研究发布目录格式错误");
  const industryCatalog = await loadIndustryCatalog(root);
  const ids = new Set(), paths = new Set(), versions = new Set(), topics = new Map();
  const documents = [];
  for (const entry of manifest.documents) {
    if (!entry || !["industry", "macro"].includes(entry.kind) || !["report", "reference"].includes(entry.type)
      || ![entry.id, entry.topic].every((s) => typeof s === "string" && /^[a-z0-9]+(?:-[a-z0-9]+)*$/u.test(s))
      || !["published", "withdrawn"].includes(entry.status) || !validDate(entry.publishedOn) || !nonblank(entry.summary)) throw new Error("研究发布条目字段错误");
    if (entry.regionId != null && (entry.regionId !== "cn" || entry.kind !== "industry" || entry.type !== "report"
      || !industryCatalog?.topics.some((topic) => topic.id === entry.topic))) throw new Error("中国行业报告必须属于行业目录中的主题");
    if (!Array.isArray(entry.markets) || !entry.markets.length || new Set(entry.markets).size !== entry.markets.length
      || entry.markets.some((m) => !["CN", "HK", "US"].includes(m))
      || !Array.isArray(entry.regions) || !entry.regions.length || !entry.regions.every(nonblank)) throw new Error("研究市场或地域范围错误");
    if (entry.type === "report" ? !validDate(entry.informationCutoff) || entry.informationCutoff > entry.publishedOn : entry.informationCutoff !== null) throw new Error("研究资料截止错误");
    if (entry.status === "withdrawn" && !nonblank(entry.withdrawalReason)) throw new Error("撤回报告必须说明原因");
    const revision = entry.revision ?? 1;
    if (!Number.isInteger(revision) || revision < 1 || (entry.type === "reference" && revision !== 1)) throw new Error("研究修订编号错误");
    const versionKey = entry.publishedOn + (revision > 1 ? `-r${revision}` : "");
    const directory = entry.kind === "industry" ? "industries" : "macro";
    const expected = entry.type === "report" ? `research/${directory}/${entry.topic}/reports/${versionKey}.md`
      : `research/${directory}/reference/${entry.topic}.md`;
    if (entry.sourcePath !== expected) throw new Error("发布路径必须对应主题、类型和日期");
    const topic = `${entry.kind}:${entry.topic}`;
    const version = `${topic}:${versionKey}`;
    if (ids.has(entry.id) || paths.has(expected) || versions.has(version)) throw new Error("研究发布条目重复");
    if (topics.has(topic) && topics.get(topic) !== entry.type) throw new Error("同一主题不能混用报告与方法");
    ids.add(entry.id); paths.add(expected); versions.add(version); topics.set(topic, entry.type);
    const local = resolve(root, expected);
    if (await realpath(local) !== resolve(await realpath(root), expected)) throw new Error("发布正文不能通过符号链接替换");
    const markdown = await readFile(local, "utf8");
    const title = /^#\s+(.+)$/mu.exec(markdown)?.[1];
    if (!title || !markdown.trim()) throw new Error("发布正文缺少标题");
    if (entry.indicatorSourcePath && (entry.kind !== "industry" || entry.type !== "report" || entry.status !== "published")) throw new Error("只有正式行业报告可连接运行指标");
    const indicatorData = entry.indicatorSourcePath ? await loadIndustryIndicators(root, entry.topic, entry.indicatorSourcePath) : null;
    if (entry.industryState !== undefined) {
      if (entry.kind !== "industry") throw new Error("只有行业文档可包含行业状态");
      validateIndustryState(entry.industryState);
    }
    if (entry.macroState !== undefined) {
      if (entry.kind !== "macro") throw new Error("只有宏观文档可包含宏观状态");
      validateMacroState(entry.macroState);
    }
    documents.push({ indicatorData, indicatorPath: indicatorData ? `/data/indicators/${entry.topic}.json` : null, id: entry.id, kind: entry.kind, type: entry.type, topic: entry.topic, publishedOn: entry.publishedOn, revision, version: versionKey,
      informationCutoff: entry.informationCutoff, markets: entry.markets, regions: entry.regions, regionId: entry.regionId ?? null, summary: entry.summary,
      industryState: entry.industryState ?? null, macroState: entry.macroState ?? null,
      sourcePath: expected, status: entry.status, withdrawalReason: entry.withdrawalReason ?? null,
      title, path: `/data/documents/${entry.id}.md`, markdown });
  }
  return documents.sort((a, b) => b.publishedOn.localeCompare(a.publishedOn) || b.revision - a.revision || a.id.localeCompare(b.id));
}

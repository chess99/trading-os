import assert from "node:assert/strict";
import test from "node:test";
import { readFile, mkdir, writeFile, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { validateRegistry, reportMetadata, displayEligibility } from "../scripts/lib/research-standards.mjs";
import { currentResults, progressCounts, readingContext } from "../app/lib/display-policy.mjs";
import { buildResearchData, projectCompany, makeExports } from "../scripts/build-research-data.mjs";

const registry = JSON.parse(await readFile(new URL("../../research/standards/registry.json", import.meta.url), "utf8"));
const standard = registry.standards[0];
const body = Buffer.from("# 示例\n信息截止：2026-09-18\n## 一句话结论\n判断成立。\n核心合理价值区间：10—20 元。\n");
const sourcePath = "research/companies/CN/000001/reports/2026-H1.md";
function state(overrides = {}) {
  return { schema_version: 6, symbol: "CN:000001", name: "测试公司", report_period: "2026-H1",
    basis_report_path: sourcePath, last_research_at: "2026-09-23T10:00:00+08:00",
    information_cutoff: "2026-09-18T20:00:00+08:00", status: "covered", universe_status: "active",
    summary: "基准判断", key_logic: ["长期能力"], risks: ["资本回报"], value_range: { low: 10, high: 20, currency: "CNY" },
    return_model: null, return_model_note: "模型缺口说明", standard_id: standard.id,
    spec_revision: standard.spec_revision, accepted_at: "2026-09-23T10:00:00+08:00", ...overrides };
}
function policy(config = registry) { return validateRegistry(structuredClone(config)); }
function metadata(row, rules, path = row.basis_report_path, content = body) {
  return { period: /([^/]+)\.md$/u.exec(path)?.[1], path: `/data/reports/${row.symbol.slice(3)}/${path.split("/").at(-1)}`,
    ...reportMetadata(path, content, rules, row) };
}
function projected(row = state(), rules = policy(), member = true) {
  return projectCompany(row, [metadata(row, rules)], member ? { tier: "core_moat" } : null, rules);
}

test("missing and malformed registry never imply legacy compatibility", () => {
  assert.throws(() => validateRegistry(null));
  assert.throws(() => validateRegistry({ ...registry, active_standard: "missing" }));
  const draft = structuredClone(registry);
  draft.standards.find((item) => item.id === draft.active_standard).status = "draft";
  assert.throws(() => validateRegistry(draft), /草案/);
  const duplicate = structuredClone(registry); duplicate.standards.push(duplicate.standards[0]);
  assert.throws(() => validateRegistry(duplicate), /重复/);
});

test("explicit compatible minor release preserves the completed standard label", () => {
  const config = structuredClone(registry);
  config.standards.push({ ...standard, id: "test-compatible-minor", change_kind: "minor",
    compatible_with: ["test-compatible-minor", standard.id] });
  config.active_standard = "test-compatible-minor";
  const row = state(); const rules = policy(config); const meta = metadata(row, rules);
  assert.equal(meta.standardId, standard.id);
  assert.equal(displayEligibility(row, meta).eligible, true);
});

test("major incompatible release hides older results without deleting reports", () => {
  const config = structuredClone(registry);
  config.standards.push({ ...config.standards[0], id: "owner-value-2.0", compatible_with: ["owner-value-2.0"] });
  config.active_standard = "owner-value-2.0";
  const row = state(); const rules = policy(config);
  assert.equal(displayEligibility(row, metadata(row, rules)).state, "pending_standard");
});

test("different value meanings cannot be declared directly compatible", () => {
  const config = structuredClone(registry);
  config.standards.push({ ...config.standards[0], id: "new-meaning", value_definition: "buying-price",
    compatible_with: ["new-meaning", "owner-value-1.0"] });
  assert.throws(() => validateRegistry(config), /不同价值语义/);
});

test("a completed state without a standard stamp remains historical", () => {
  const row = state({ standard_id: null, spec_revision: null, accepted_at: null });
  const output = projected(row);
  assert.equal(output.display.state, "pending_standard");
  assert.equal(output.valueRange, null); assert.equal(output.returnModelNote, null); assert.equal(output.summary, "");
});

test("only the basis period receives the state standard metadata", () => {
  const row = state(); const rules = policy();
  const historicalPath = sourcePath.replace("H1.md", "Q1.md");
  const current = metadata(row, rules);
  const historical = metadata(row, rules, historicalPath);
  assert.equal(current.compatible, true);
  assert.equal(historical.compatible, false);
  assert.equal(historical.standardLabel, "历史标准未确认");
});

test("inactivity and incomplete standard state fail closed", () => {
  assert.equal(projected(state({ universe_status: "inactive" })).display.state, "inactive");
  assert.equal(projected(state({ accepted_at: null })).display.state, "needs_review");
});

test("qualified negative conclusions and null valuations remain visible", () => {
  const negative = projected(state({ status: "ignore" }));
  const unpriced = projected(state({ value_range: null, valuation_note: "cannot bound the path" }));
  const rows = currentResults([negative, unpriced]);
  assert.equal(rows.length, 2); assert.equal(unpriced.display.state, "unpriced");
  assert.deepEqual(progressCounts(rows), { total: 2, completed: 2, valued: 1, unpriced: 1, pending: 0, review: 0, inactive: 0 });
});

test("same selection drives current count and JSON/CSV export input", () => {
  const valid = projected(); const outside = projected(state({ symbol: "CN:000002" }), undefined, false);
  const historical = projected(state({ standard_id: null, spec_revision: null, accepted_at: null }));
  const catalog = { generatedAt: "now", standard, companies: [valid, outside, historical] };
  assert.deepEqual(makeExports(catalog, "quality_pool").companies, currentResults(catalog.companies));
  assert.equal(makeExports(catalog, "all_standard").count, 2);
});

test("the basis period stays live while other periods are historical", () => {
  const company = projected();
  assert.equal(readingContext(company).live, true);
  assert.equal(readingContext(company, "2026-H1").live, true);
  assert.equal(readingContext(company, "1999-Q1").report, null);
  assert.equal(readingContext({ ...company, display: { eligible: false } }).live, false);
});

async function fixture() {
  const root = await mkdtemp(join(tmpdir(), "research-standard-test-"));
  const row = state();
  async function save(path, content) {
    await mkdir(join(root, path, ".."), { recursive: true });
    await writeFile(join(root, path), typeof content === "string" || Buffer.isBuffer(content) ? content : JSON.stringify(content));
  }
  await save("research/standards/registry.json", registry);
  await save(sourcePath, body);
  await save("coverage/cn-a/research_state.jsonl", `${JSON.stringify(row)}\n`);
  await save("coverage/cn-a/research_queue.jsonl", "");
  for (const [market, identities] of [["cn-a", { [row.symbol]: row.name, "CN:000003": "待研究公司" }],
    ["hk", { "HK:00700": "港股样本" }], ["us", { "US:V": "美股样本" }]]) {
    await save(`screening/${market}/value-quality/pool.json`, { schema_version: 2, as_of: "2026-09-18",
      universe: { securities: identities }, review: { reviewed_symbols: Object.keys(identities), scope_note: "测试样本" },
      companies: Object.entries(identities).map(([symbol, name]) => ({ symbol, name, tier: "core_moat",
        industry: "服务", group: "consumer_brand_network", moat: "网络", owner_cash: "现金", risks: "竞争",
        tier_reason: "持续复核", sources: [{ title: "披露", url: "https://example.com/report" }] })) });
  }
  return { root, row, save };
}

test("catalog build redacts historical fields, retains reports, and includes pool-only progress", async () => {
  const { root, row, save } = await fixture();
  try {
    const historical = state({ symbol: "CN:000002", name: "历史公司",
      basis_report_path: sourcePath.replace("000001", "000002"), standard_id: null,
      spec_revision: null, accepted_at: null, summary: "旧结论不应泄露",
      value_range: { low: 991237, high: 991238, currency: "CNY" } });
    await save(historical.basis_report_path, body);
    await save("coverage/cn-a/research_state.jsonl", [row, historical].map(JSON.stringify).join("\n") + "\n");
    const catalog = await buildResearchData(root);
    const screening = JSON.parse(await readFile(join(root, "dashboard/public/data/screening-pools.json"), "utf8"));
    assert.equal(screening.pools.length, 3);
    assert.ok(catalog.companies.every((company) => company.symbol.startsWith("CN:")));
    assert.equal(catalog.stats.current.completed, 1); assert.equal(catalog.stats.current.total, 2);
    assert.equal(catalog.stats.researchStateRows, 2); assert.equal(catalog.companies.length, 3);
    assert.equal(catalog.companies.find((item) => item.symbol === "CN:000003").hasResearchState, false);
    assert.ok(!JSON.stringify(catalog).includes("991237")); assert.ok(!JSON.stringify(catalog).includes("旧结论不应泄露"));
    assert.deepEqual(await readFile(join(root, "dashboard/public/data/reports/000002/2026-H1.md")), body);
    const exported = JSON.parse(await readFile(join(root, "dashboard/public/data/current-research.json"), "utf8"));
    assert.equal(exported.count, 1); assert.equal(exported.companies[0].symbol, row.symbol);
    assert.ok(!(await readFile(join(root, "dashboard/public/data/current-research.csv"), "utf8")).includes("历史公司"));
    const progress = JSON.parse(await readFile(join(root, "dashboard/public/data/research-progress.json"), "utf8"));
    assert.equal(progress.companies.length, 2); assert.ok(progress.companies.every((item) => !("valueRange" in item)));
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("standard CLI validates state stamps without creating sidecar files", async () => {
  const { root, row, save } = await fixture();
  const script = fileURLToPath(new URL("../scripts/report-standards.mjs", import.meta.url));
  const run = () => execFileSync(process.execPath, [script, "validate", "--root", root],
    { encoding: "utf8", stdio: ["pipe", "pipe", "pipe"] });
  try {
    const valid = JSON.parse(run());
    assert.equal(valid.stamped_results, 1); assert.equal(valid.compatible_results, 1);
    await save("coverage/cn-a/research_state.jsonl", `${JSON.stringify({ ...row, accepted_at: null })}\n`);
    assert.throws(run);
    await assert.rejects(readFile(join(root, "research/standards/acceptances/000001/2026-H1.json")));
  } finally { await rm(root, { recursive: true, force: true }); }
});

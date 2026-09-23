import assert from "node:assert/strict";
import test from "node:test";
import { readFile, mkdir, writeFile, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { validateRegistry, validateAcceptance, sha256, researchDigest, reportMetadata,
  displayEligibility, acceptancePath, loadStandards } from "../scripts/lib/research-standards.mjs";
import { currentResults, progressCounts, readingContext } from "../app/lib/display-policy.mjs";
import { buildResearchData, projectCompany, makeExports } from "../scripts/build-research-data.mjs";

const registry = JSON.parse(await readFile(new URL("../../research/standards/registry.json", import.meta.url), "utf8"));
const body = Buffer.from("# 示例\n信息截止：2026-09-18\n## 一句话结论\n判断成立。\n核心合理价值区间：10—20 元。\n");
const sourcePath = "research/companies/CN/000001/reports/2026-09-18.md";
function state(overrides = {}) {
  return { symbol: "CN:000001", name: "测试公司", report_path: sourcePath,
    information_cutoff: "2026-09-18T20:00:00+08:00", status: "covered", universe_status: "active",
    summary: "基准判断", key_logic: ["长期能力"], risks: ["资本回报"], value_range: { low: 10, high: 20, currency: "CNY" },
    return_model: null, return_model_note: "模型缺口说明", ...overrides };
}
function receipt(row, overrides = {}) {
  return { schema_version: 1, symbol: row.symbol, outcome: row.status, report_path: row.report_path,
    report_sha256: sha256(body), research_sha256: researchDigest(row), information_cutoff: row.information_cutoff,
    standard_id: "owner-value-1.0", spec_revision: registry.standards[0].spec_revision,
    value_definition: registry.standards[0].value_definition, accepted_at: "2026-09-23T10:00:00+08:00",
    source_revision: "a".repeat(40), reviewer: "test", review_note: "仅测试验收结构", revoked_at: null, ...overrides };
}
function policy(row = state(), overrides = {}) {
  return { ...validateRegistry(structuredClone(registry)), receipts: new Map([[row.report_path, receipt(row, overrides)]]) };
}
function metadata(row, rules, content = body) { return { date: "2026-09-18", path: "/data/reports/000001/2026-09-18.md", ...reportMetadata(row.report_path, content, rules) }; }
function projected(row = state(), rules = policy(row), member = true) {
  return projectCompany(row, [metadata(row, rules)], member ? { tier: "core_moat" } : null, rules);
}

test("missing and malformed registry never imply legacy compatibility", () => {
  assert.throws(() => validateRegistry(null));
  assert.throws(() => validateRegistry({ ...registry, active_standard: "missing" }));
  const draft = structuredClone(registry); draft.standards[0].status = "draft";
  assert.throws(() => validateRegistry(draft), /草案/);
  const duplicate = structuredClone(registry); duplicate.standards.push(duplicate.standards[0]);
  assert.throws(() => validateRegistry(duplicate), /重复/);
});
test("explicit compatible minor release preserves authentic old version labels", () => {
  const config = structuredClone(registry);
  config.standards.push({ ...config.standards[0], id: "owner-value-1.1", change_kind: "minor", compatible_with: ["owner-value-1.1", "owner-value-1.0"] });
  config.active_standard = "owner-value-1.1";
  const row = state(); const rules = { ...validateRegistry(config), receipts: policy(row).receipts };
  const meta = metadata(row, rules);
  assert.equal(meta.standardId, "owner-value-1.0");
  assert.equal(displayEligibility(row, meta, rules).eligible, true);
});
test("major incompatible release hides older results without deleting files", () => {
  const config = structuredClone(registry);
  config.standards.push({ ...config.standards[0], id: "owner-value-2.0", compatible_with: ["owner-value-2.0"] });
  config.active_standard = "owner-value-2.0";
  const row = state(); const rules = { ...validateRegistry(config), receipts: policy(row).receipts };
  assert.equal(displayEligibility(row, metadata(row, rules), rules).eligible, false);
});
test("different value meanings cannot be declared directly compatible", () => {
  const config = structuredClone(registry);
  config.standards.push({ ...config.standards[0], id: "new-meaning", value_definition: "buying-price", compatible_with: ["new-meaning", "owner-value-1.0"] });
  assert.throws(() => validateRegistry(config), /不同价值语义/);
});
test("new date and covered state do not automatically certify a report", () => {
  const row = state(); const rules = { ...policy(row), receipts: new Map() };
  const output = projected(row, rules);
  assert.equal(output.display.state, "pending_standard");
  assert.equal(output.valueRange, null); assert.equal(output.returnModelNote, null); assert.equal(output.summary, "");
});
test("body and every economically relevant structured field are bound independently", () => {
  const row = state(); const rules = policy(row);
  assert.equal(displayEligibility(row, metadata(row, rules, Buffer.from("rewritten")), rules).state, "needs_review");
  for (const key of ["summary", "key_logic", "risks", "value_range", "valuation_note", "return_model", "return_model_note", "source_urls", "event_triggers"]) {
    const changed = { ...row, [key]: "changed" };
    assert.equal(displayEligibility(changed, metadata(row, rules), rules).state, "needs_review", key);
  }
  assert.equal(researchDigest({ ...row, updated_at: "later", last_update: { impact: "monitor" } }), researchDigest(row));
});
test("material invalidation hides estimates and never revives an older report", () => {
  const row = state(); const rules = policy(row);
  for (const changed of [{ ...row, status: "stale" }, { ...row, invalidation: { reason: "material" } }]) {
    const output = projected(changed, rules);
    assert.equal(output.display.state, "needs_update"); assert.equal(output.valueRange, null);
  }
  const newer = { ...row, report_path: sourcePath.replace("18.md", "23.md") };
  assert.equal(projectCompany(newer, [metadata(row, rules)], {}, rules).display.state, "needs_review");
});
test("revocation, inactivity and changed outcome are distinct from normal completion", () => {
  const row = state();
  assert.equal(projected(row, policy(row, { revoked_at: "2026-09-23T12:00:00+08:00", revocation_reason: "bad source" })).display.state, "needs_review");
  assert.equal(projected({ ...row, universe_status: "inactive" }, policy(row)).display.state, "inactive");
  assert.equal(projected({ ...row, status: "ignore" }, policy(row)).display.state, "needs_review");
});
test("qualified negative conclusions and null valuations remain visible", () => {
  const negative = projected(state({ status: "ignore" }));
  const unpriced = projected(state({ value_range: null, valuation_note: "cannot bound the path" }));
  const rows = currentResults([negative, unpriced]);
  assert.equal(rows.length, 2); assert.equal(unpriced.display.state, "unpriced");
  assert.deepEqual(progressCounts(rows), { total: 2, completed: 2, valued: 1, unpriced: 1, pending: 0, updating: 0, review: 0, inactive: 0 });
});
test("same selection drives current count and JSON/CSV export input", () => {
  const valid = projected(); const outside = projected(state({ symbol: "CN:000002" }), undefined, false);
  const legacy = projected(state(), { ...policy(), receipts: new Map() });
  const catalog = { generatedAt: "now", standard: registry.standards[0], companies: [valid, outside, legacy] };
  assert.deepEqual(makeExports(catalog, "quality_pool").companies, currentResults(catalog.companies));
  assert.equal(makeExports(catalog, "all_standard").count, 2);
});
test("all explicit dated reads suppress live panels, even for the current file", () => {
  const company = projected();
  assert.equal(readingContext(company).live, true);
  assert.equal(readingContext(company, "2026-09-18").live, false);
  assert.equal(readingContext(company, null, "history").live, false);
  assert.equal(readingContext(company, "1999-01-01").report, null);
  assert.equal(readingContext({ ...company, display: { eligible: false } }).report, null);
});
test("acceptance validates identity, standard definition, timezone and audit explanation", () => {
  const row = state(); const rules = policy(row); const record = receipt(row);
  assert.equal(validateAcceptance(record, rules), record);
  for (const overrides of [{ symbol: "CN:999999" }, { report_path: "../../secret" }, { accepted_at: "2026-09-23" }, { review_note: "" }, { spec_revision: "b".repeat(40) }, { research_sha256: "bad" }]) {
    assert.throws(() => validateAcceptance({ ...record, ...overrides }, rules));
  }
});
async function fixture() {
  const root = await mkdtemp(join(tmpdir(), "research-standard-test-"));
  const row = state();
  async function save(path, content) { await mkdir(join(root, path, ".."), { recursive: true }); await writeFile(join(root, path), typeof content === "string" || Buffer.isBuffer(content) ? content : JSON.stringify(content)); }
  await save("research/standards/registry.json", registry);
  await save(sourcePath, body);
  await save("coverage/cn-a/research_state.jsonl", `${JSON.stringify(row)}\n`);
  await save("coverage/cn-a/research_queue.jsonl", "");
  await save("screening/cn-a/value-quality/pool.json", { schema_version: 2, as_of: "2026-09-18", companies: [{ symbol: row.symbol, name: row.name, tier: "core_moat" }, { symbol: "CN:000003", name: "待登记公司", tier: "quality_research" }] });
  return { root, row, save };
}
test("catalog build redacts legacy fields, retains exact history, and includes pool-only progress", async () => {
  const { root, row, save } = await fixture();
  try {
    const legacy = state({ symbol: "CN:000002", name: "历史公司", report_path: sourcePath.replace("000001", "000002"), summary: "旧结论不应泄露", value_range: { low: 991237, high: 991238, currency: "CNY" } });
    await save(legacy.report_path, body);
    await save("coverage/cn-a/research_state.jsonl", [row, legacy].map(JSON.stringify).join("\n") + "\n");
    await save(acceptancePath(sourcePath), receipt(row));
    const catalog = await buildResearchData(root);
    assert.equal(catalog.stats.current.completed, 1); assert.equal(catalog.stats.current.total, 2);
    assert.equal(catalog.stats.researchStateRows, 2); assert.equal(catalog.companies.length, 3);
    assert.equal(catalog.companies.find((item) => item.symbol === "CN:000003").hasResearchState, false);
    assert.ok(!JSON.stringify(catalog).includes("991237")); assert.ok(!JSON.stringify(catalog).includes("旧结论不应泄露"));
    assert.deepEqual(await readFile(join(root, "dashboard/public/data/reports/000002/2026-09-18.md")), body);
    const exported = JSON.parse(await readFile(join(root, "dashboard/public/data/current-research.json"), "utf8"));
    assert.equal(exported.count, 1); assert.equal(exported.companies[0].symbol, row.symbol);
    assert.ok(!(await readFile(join(root, "dashboard/public/data/current-research.csv"), "utf8")).includes("历史公司"));
    const progress = JSON.parse(await readFile(join(root, "dashboard/public/data/research-progress.json"), "utf8"));
    assert.equal(progress.companies.length, 2); assert.ok(progress.companies.every((item) => !("valueRange" in item)));
  } finally { await rm(root, { recursive: true, force: true }); }
});
test("CLI requires explicit semantic review and snapshot hashes; writes only metadata", async () => {
  const { root, row } = await fixture();
  const script = fileURLToPath(new URL("../scripts/report-standards.mjs", import.meta.url));
  const run = (...args) => execFileSync(process.execPath, [script, ...args, "--root", root], { encoding: "utf8", stdio: ["pipe", "pipe", "pipe"] });
  try {
    const info = JSON.parse(run("inspect", "--symbol", row.symbol));
    assert.equal(info.report_sha256, sha256(body));
    const args = ["--symbol", row.symbol, "--standard", "owner-value-1.0", "--report-sha", info.report_sha256,
      "--research-sha", info.research_sha256, "--source-revision", "a".repeat(40), "--at", "2026-09-23T12:00:00+08:00", "--reviewer", "test", "--note", "actual review in test fixture"];
    assert.throws(() => run("accept", ...args));
    assert.throws(() => run("accept", ...args, "--confirm-review", "--report-sha", "bad"));
    run("accept", ...args, "--confirm-review");
    assert.throws(() => run("accept", ...args, "--confirm-review"));
    assert.equal(JSON.parse(run("validate")).acceptances, 1);
    const accepted = JSON.parse(run("inspect", "--symbol", row.symbol));
    run("revoke", ...args, "--confirm-review", "--expected-receipt", accepted.receipt_sha256);
    const rules = await loadStandards(root);
    assert.equal(displayEligibility(row, metadata(row, rules), rules).eligible, false);
    assert.deepEqual(await readFile(join(root, sourcePath)), body);
    assert.equal((await readFile(join(root, "coverage/cn-a/research_state.jsonl"), "utf8")).trim(), JSON.stringify(row));
  } finally { await rm(root, { recursive: true, force: true }); }
});

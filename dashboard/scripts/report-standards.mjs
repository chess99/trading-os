import { readFile } from "node:fs/promises";
import { dirname, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { loadStandards } from "./lib/research-standards.mjs";

const { values, positionals } = parseArgs({ allowPositionals: true, options: {
  root: { type: "string" },
} });
const root = resolve(values.root ?? join(dirname(fileURLToPath(import.meta.url)), "../.."));
const command = positionals[0];
const assert = (ok, message) => { if (!ok) throw new Error(message); };
const nonblank = (value) => typeof value === "string" && value.trim().length > 0;
const timestamp = (value) => nonblank(value) && /(?:Z|[+-]\d{2}:\d{2})$/u.test(value) && Number.isFinite(Date.parse(value));
const reportPath = /^research\/companies\/(CN|HK|US)\/([A-Z0-9.-]+)\/reports\/(20\d{2}-(?:FY|Q1|H1|Q3))\.md$/u;

async function main() {
  assert(command === "validate" && positionals.length === 1,
    "用法: node dashboard/scripts/report-standards.mjs validate");
  const policy = await loadStandards(root);
  const states = (await Promise.all(["cn-a", "hk", "us"].map(async (market) => {
    try { return (await readFile(join(root, `coverage/${market}/research_state.jsonl`), "utf8")).split(/\r?\n/u).filter(Boolean).map(JSON.parse); }
    catch (error) { if (market !== "cn-a" && error.code === "ENOENT") return []; throw error; }
  }))).flat();
  let stampedResults = 0;
  let compatibleResults = 0;
  for (const state of states) {
    const stamp = [state.standard_id, state.spec_revision, state.accepted_at];
    if (stamp.every((value) => value == null)) continue;
    assert(stamp.every(nonblank), `研究标准信息不完整: ${state.symbol}`);
    const match = reportPath.exec(state.basis_report_path ?? "");
    assert(match && state.symbol === `${match[1]}:${match[2]}` && state.report_period === match[3],
      `研究标准对应报告路径不正确: ${state.symbol}`);
    assert(["covered", "ignore"].includes(state.status), `标准标记只适用于已完成研究: ${state.symbol}`);
    const standard = policy.standards.get(state.standard_id);
    assert(standard && standard.status !== "draft", `研究标准不存在或仍是草案: ${state.symbol}`);
    assert(state.spec_revision === standard.spec_revision, `研究标准版本不匹配: ${state.symbol}`);
    assert(timestamp(state.accepted_at), `研究完成时间必须有时区: ${state.symbol}`);
    assert(timestamp(state.information_cutoff)
      && Date.parse(state.accepted_at) >= Date.parse(state.information_cutoff), `研究完成时间/资料截止不合法: ${state.symbol}`);
    const report = await readFile(join(root, state.basis_report_path), "utf8");
    assert(report.trim(), `研究依据报告为空: ${state.symbol}`);
    stampedResults += 1;
    if (policy.active.compatible_with.includes(state.standard_id)) compatibleResults += 1;
  }
  process.stdout.write(`${JSON.stringify({ ok: true, active_standard: policy.active.id,
    stamped_results: stampedResults, compatible_results: compatibleResults }, null, 2)}\n`);
}

main().catch((error) => { console.error(error.message); process.exitCode = 1; });

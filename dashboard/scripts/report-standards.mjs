import { readFile, mkdir, open, rename, rm } from "node:fs/promises";
import { dirname, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { acceptancePath, loadStandards, reportMetadata, researchDigest, sha256,
  validateAcceptance } from "./lib/research-standards.mjs";

const { values, positionals } = parseArgs({ allowPositionals: true, options: {
  root: { type: "string" }, symbol: { type: "string" }, standard: { type: "string" },
  "report-sha": { type: "string" }, "research-sha": { type: "string" },
  "expected-receipt": { type: "string" }, "source-revision": { type: "string" },
  reviewer: { type: "string" }, note: { type: "string" }, at: { type: "string" },
  "confirm-review": { type: "boolean", default: false },
} });
const root = resolve(values.root ?? join(dirname(fileURLToPath(import.meta.url)), "../.."));
const command = positionals[0];
const assert = (ok, message) => { if (!ok) throw new Error(message); };
const emit = (payload) => process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);

async function main() {
  assert(["inspect", "accept", "revoke", "validate"].includes(command),
    "用法: node dashboard/scripts/report-standards.mjs inspect|accept|revoke|validate [--symbol CN:xxxxxx]");
  const policy = await loadStandards(root);
  const states = (await readFile(join(root, "coverage/cn-a/research_state.jsonl"), "utf8"))
    .split(/\r?\n/u).filter(Boolean).map((line) => JSON.parse(line));
  if (command === "validate") {
    for (const receipt of policy.receipts.values()) {
      const body = await readFile(join(root, receipt.report_path));
      assert(receipt.revoked_at || sha256(body) === receipt.report_sha256, `报告内容已变化: ${receipt.report_path}`);
      const state = states.find((row) => row.report_path === receipt.report_path);
      assert(receipt.revoked_at || !state || researchDigest(state) === receipt.research_sha256,
        `当前结构化研究与验收不一致: ${receipt.report_path}`);
      assert(receipt.revoked_at || !state || !["covered", "ignore"].includes(state.status)
        || state.status === receipt.outcome, `当前结论状态与验收不一致: ${receipt.report_path}`);
    }
    emit({ ok: true, active_standard: policy.active.id, acceptances: policy.receipts.size });
    return;
  }
  assert(/^CN:\d{6}$/u.test(values.symbol ?? ""), "必须指定单家公司 --symbol CN:xxxxxx");
  const state = states.find((row) => row.symbol === values.symbol);
  assert(state?.report_path, "该公司没有当前正式报告，不可根据历史文件猜测当前指针");
  const target = join(root, acceptancePath(state.report_path));
  const body = await readFile(join(root, state.report_path));
  const reportSha = sha256(body);
  const stateSha = researchDigest(state);
  let previous;
  try { previous = await readFile(target, "utf8"); }
  catch (error) { if (error.code !== "ENOENT") throw error; }
  if (command === "inspect") {
    emit({ symbol: state.symbol, report_path: state.report_path, report_sha256: reportSha,
      research_sha256: stateSha, information_cutoff: state.information_cutoff,
      receipt_sha256: previous ? sha256(previous) : null,
      report: reportMetadata(state.report_path, body, policy) });
    return;
  }
  assert(values["confirm-review"] && values.note?.trim() && values.reviewer?.trim(),
    "写入必须确认已实质验收，并给出 --confirm-review --reviewer --note；哈希校验不代替研究验收");
  assert(values["report-sha"] === reportSha && values["research-sha"] === stateSha,
    "正文或研究结果与已检查快照不同，请重新读取后验收");
  assert(!previous || values["expected-receipt"] === sha256(previous), "已有验收记录，替换须提供 --expected-receipt");
  const at = values.at ?? new Date().toISOString();
  let receipt;
  if (command === "revoke") {
    assert(previous, "没有可撤销的验收记录");
    receipt = { ...JSON.parse(previous), revoked_at: at, revocation_reason: values.note,
      revoked_by: values.reviewer };
  } else {
    const standard = policy.standards.get(values.standard);
    assert(standard?.status === "released", "只可按已发布标准验收");
    assert(state.universe_status === "active" && ["covered", "ignore"].includes(state.status)
      && !state.invalidation, "当前报告失效、未完成或不在市，不能登记为现行结果");
    receipt = { schema_version: 1, symbol: state.symbol, outcome: state.status, report_path: state.report_path,
      report_sha256: reportSha, research_sha256: stateSha, information_cutoff: state.information_cutoff,
      standard_id: standard.id, spec_revision: standard.spec_revision, value_definition: standard.value_definition,
      accepted_at: at, reviewer: values.reviewer, review_note: values.note,
      source_revision: values["source-revision"], revoked_at: null };
  }
  validateAcceptance(receipt, policy);
  await mkdir(dirname(target), { recursive: true });
  // Per-report lock and compare-and-swap protect local concurrent coordinators.
  // Normal git conflict checks are still required when committing from other hosts.
  const lock = await open(`${target}.lock`, "wx");
  const temporary = `${target}.${process.pid}.tmp`;
  try {
    let current;
    try { current = await readFile(target, "utf8"); } catch (error) { if (error.code !== "ENOENT") throw error; }
    assert(current === previous, "验收记录并发变化，拒绝覆盖");
    const latest = (await readFile(join(root, "coverage/cn-a/research_state.jsonl"), "utf8"))
      .split(/\r?\n/u).filter(Boolean).map((line) => JSON.parse(line)).find((row) => row.symbol === state.symbol);
    assert(latest?.report_path === state.report_path && researchDigest(latest) === stateSha
      && sha256(await readFile(join(root, state.report_path))) === reportSha, "研究快照并发变化，拒绝登记");
    if (command === "accept") assert(latest.universe_status === "active"
      && latest.status === receipt.outcome && !latest.invalidation, "研究有效性并发变化，拒绝登记");
    const file = await open(temporary, "wx");
    try { await file.writeFile(`${JSON.stringify(receipt, null, 2)}\n`); await file.sync(); }
    finally { await file.close(); }
    await rename(temporary, target);
  } finally {
    await rm(temporary, { force: true }); await lock.close(); await rm(`${target}.lock`, { force: true });
  }
  emit({ ok: true, path: acceptancePath(state.report_path), receipt });
}
main().catch((error) => { console.error(error.message); process.exitCode = 1; });

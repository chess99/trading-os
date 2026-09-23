import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import { resolve, join } from "node:path";

export const REGISTRY_PATH = "research/standards/registry.json";
export const ACCEPTANCES_PATH = "research/standards/acceptances";
const REPORT_PATH = /^research\/companies\/CN\/(\d{6})\/reports\/(\d{4}-\d{2}-\d{2}(?:-\d{2})?)\.md$/u;
const SHA = /^[a-f0-9]{64}$/u;
const ID = /^[a-z0-9][a-z0-9._-]*$/u;
const nonblank = (value) => typeof value === "string" && value.trim().length > 0;
const timestamp = (value) => nonblank(value) && /(?:Z|[+-]\d{2}:\d{2})$/u.test(value) && Number.isFinite(Date.parse(value));
function ensure(condition, message) { if (!condition) throw new Error(message); }
export function sha256(value) { return createHash("sha256").update(value).digest("hex"); }
export function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value ?? null);
}
// Identity binding, not a second valuation database. Review timestamps and
// dynamic status are excluded; material invalidation is checked separately.
export function researchDigest(state) {
  const fields = ["symbol", "report_path", "information_cutoff", "summary", "key_logic", "risks",
    "value_range", "valuation_note", "return_model", "return_model_note", "source_urls", "event_triggers"];
  return sha256(canonical(Object.fromEntries(fields.map((field) => [field, state[field] ?? null]))));
}
export function acceptancePath(reportPath) {
  const match = REPORT_PATH.exec(reportPath ?? "");
  ensure(match, `不是正式报告路径: ${reportPath}`);
  return `${ACCEPTANCES_PATH}/${match[1]}/${match[2]}.json`;
}
export function validateRegistry(registry) {
  ensure(registry?.schema_version === 1, "未知展示标准schema，停止生成目录");
  ensure(registry.default_scope === "quality_pool", "默认范围必须为质量池");
  ensure(registry.scope_source === "screening/cn-a/value-quality/pool.json", "质量池入口不正确");
  ensure(Array.isArray(registry.standards) && registry.standards.length > 0, "缺少标准声明");
  const standards = new Map();
  for (const item of registry.standards) {
    ensure(ID.test(item.id) && !standards.has(item.id), "标准ID缺失或重复");
    ensure(["draft", "released", "retired"].includes(item.status), `标准状态错误: ${item.id}`);
    ensure(nonblank(item.label) && nonblank(item.value_definition) && nonblank(item.value_label), `缺少标准含义: ${item.id}`);
    ensure(/^[a-f0-9]{40}$/u.test(item.spec_revision ?? ""), `须绑定完整规范提交: ${item.id}`);
    ensure(timestamp(item.published_at), `标准发布时间必须有时区: ${item.id}`);
    ensure(nonblank(item.spec_path) && nonblank(item.verification_path), `缺少规范入口: ${item.id}`);
    ensure(["major", "minor", "patch"].includes(item.change_kind) && nonblank(item.change_note), `缺少变更说明: ${item.id}`);
    ensure(Array.isArray(item.compatible_with) && item.compatible_with.includes(item.id)
      && new Set(item.compatible_with).size === item.compatible_with.length && nonblank(item.compatibility_note), `缺少显式兼容声明: ${item.id}`);
    standards.set(item.id, item);
  }
  const active = standards.get(registry.active_standard);
  ensure(active?.status === "released", "现行标准必须已正式发布，草案不改变展示资格");
  for (const item of standards.values()) for (const compatible of item.compatible_with) {
    const target = standards.get(compatible);
    ensure(target && (target.status !== "draft" || target.id === item.id), `兼容目标未发布或不存在: ${compatible}`);
    ensure(target.value_definition === item.value_definition, "不同价值语义不可直接声明兼容");
  }
  return { registry, standards, active };
}
export function validateAcceptance(receipt, policy) {
  ensure(receipt?.schema_version === 1, "未知报告验收schema");
  const match = REPORT_PATH.exec(receipt.report_path ?? "");
  ensure(match && receipt.symbol === `CN:${match[1]}`, "验收记录公司与路径不一致");
  ensure(SHA.test(receipt.report_sha256 ?? "") && SHA.test(receipt.research_sha256 ?? ""), "验收必须绑定正文及结构化结果摘要");
  ensure(timestamp(receipt.information_cutoff) && timestamp(receipt.accepted_at)
    && Date.parse(receipt.accepted_at) >= Date.parse(receipt.information_cutoff), "验收时间/资料截止不合法");
  const standard = policy.standards.get(receipt.standard_id);
  ensure(standard && standard.status !== "draft", "验收标准不存在或仍是草案");
  ensure(receipt.value_definition === standard.value_definition && receipt.spec_revision === standard.spec_revision, "验收标准与冻结口径不一致");
  ensure(["covered", "ignore"].includes(receipt.outcome), "缺少验收时的研究结论状态");
  ensure(nonblank(receipt.reviewer) && nonblank(receipt.review_note), "缺少实质验收说明");
  ensure(/^[a-f0-9]{40}$/u.test(receipt.source_revision ?? ""), "缺少来源提交");
  ensure(receipt.revoked_at == null || (timestamp(receipt.revoked_at)
    && Date.parse(receipt.revoked_at) >= Date.parse(receipt.accepted_at) && nonblank(receipt.revocation_reason)), "撤销必须注明时间和原因");
  return receipt;
}
export async function loadStandards(root) {
  const registry = JSON.parse(await readFile(join(root, REGISTRY_PATH), "utf8"));
  const policy = validateRegistry(registry);
  const receipts = new Map();
  async function walk(directory) {
    let entries;
    try { entries = await readdir(directory, { withFileTypes: true }); }
    catch (error) { if (error.code === "ENOENT") return; throw error; }
    for (const entry of entries) {
      const path = join(directory, entry.name);
      ensure(!entry.isSymbolicLink(), "验收目录不允许符号链接");
      if (entry.isDirectory()) { await walk(path); continue; }
      if (!entry.name.endsWith(".json")) continue;
      const receipt = validateAcceptance(JSON.parse(await readFile(path, "utf8")), policy);
      ensure(resolve(root, acceptancePath(receipt.report_path)) === resolve(path), "验收记录存储路径不匹配");
      ensure(!receipts.has(receipt.report_path), "重复报告验收记录");
      receipts.set(receipt.report_path, receipt);
    }
  }
  await walk(join(root, ACCEPTANCES_PATH));
  return { ...policy, receipts };
}
export function reportMetadata(sourcePath, body, policy) {
  const receipt = policy.receipts.get(sourcePath);
  const standard = receipt && policy.standards.get(receipt.standard_id);
  const intact = Boolean(receipt && receipt.report_sha256 === sha256(body));
  const compatible = Boolean(intact && !receipt.revoked_at && policy.active.compatible_with.includes(receipt.standard_id));
  const cutoff = /信息截止(?:时间|时点|日)?\s*[：:=]?\s*(20\d{2}[-年/]\d{1,2}[-月/]\d{1,2}日?)/u.exec(body.toString("utf8"));
  return {
    sourcePath,
    informationCutoff: intact ? receipt.information_cutoff : cutoff?.[1] ?? null,
    standardId: receipt?.standard_id ?? null,
    standardLabel: standard?.label ?? "历史标准未确认",
    valueDefinition: receipt?.value_definition ?? null,
    acceptedAt: receipt?.accepted_at ?? null,
    compatible,
    acceptanceStatus: !receipt ? "unconfirmed" : receipt.revoked_at ? "revoked" : !intact ? "content_changed" : compatible ? "compatible" : "incompatible",
  };
}
export function displayEligibility(state, metadata, policy) {
  const fail = (stateCode, reason) => ({ eligible: false, state: stateCode, reason });
  if (!state?.report_path) return fail("pending_research", "尚无当前正式报告");
  if (!metadata || metadata.sourcePath !== state.report_path) return fail("needs_review", "当前指针对应的报告缺失，未回退到旧稿");
  const receipt = policy.receipts.get(state.report_path);
  if (!receipt) return fail("pending_standard", "历史标准未确认，待按现行标准研究");
  if (receipt.revoked_at) return fail("needs_review", `验收已撤销：${receipt.revocation_reason}`);
  if (state.status === "stale" || state.invalidation || !["covered", "ignore"].includes(state.status)) {
    return fail("needs_update", "该报告已失效或正在更新，不回退到更早估值");
  }
  if (receipt.outcome !== state.status) return fail("needs_review", "研究结论状态已变化，需要重新验收");
  if (metadata.acceptanceStatus === "content_changed" || researchDigest(state) !== receipt.research_sha256) {
    return fail("needs_review", "正文或结构化研究已改变，需要重新验收");
  }
  if (!metadata.compatible) return fail("pending_standard", "原验收标准不兼容现行标准");
  if (state.universe_status !== "active") return fail("inactive", "证券不在当前在市范围");
  return { eligible: true, state: state.value_range ? "current" : "unpriced",
    reason: state.value_range ? "现行兼容标准已验收" : "研究已验收，暂无法形成可靠价值区间" };
}

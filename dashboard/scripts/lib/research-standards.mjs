import { readFile } from "node:fs/promises";
import { join } from "node:path";

export const REGISTRY_PATH = "research/standards/registry.json";
const ID = /^[a-z0-9][a-z0-9._-]*$/u;
const nonblank = (value) => typeof value === "string" && value.trim().length > 0;
const timestamp = (value) => nonblank(value) && /(?:Z|[+-]\d{2}:\d{2})$/u.test(value) && Number.isFinite(Date.parse(value));
function ensure(condition, message) { if (!condition) throw new Error(message); }

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

export async function loadStandards(root) {
  const registry = JSON.parse(await readFile(join(root, REGISTRY_PATH), "utf8"));
  return validateRegistry(registry);
}

export function reportMetadata(sourcePath, body, policy, state) {
  const isBasis = sourcePath === state?.basis_report_path;
  const stamp = isBasis ? [state?.standard_id, state?.spec_revision, state?.accepted_at] : [];
  const completeStamp = stamp.length === 3 && stamp.every(nonblank);
  const standard = completeStamp ? policy.standards.get(state.standard_id) : null;
  const revisionMatches = Boolean(standard && standard.spec_revision === state.spec_revision);
  const compatible = Boolean(revisionMatches && policy.active.compatible_with.includes(state.standard_id));
  const cutoff = /信息截止(?:时间|时点|日)?\s*[：:=]?\s*(20\d{2}[-年/]\d{1,2}[-月/]\d{1,2}日?)/u.exec(body.toString("utf8"));
  return {
    sourcePath,
    periodEnd: isBasis ? state?.financial_basis?.period_end ?? null
      : /财务期末[:：]\s*(\d{4}-\d{2}-\d{2})/u.exec(body.toString("utf8"))?.[1] ?? null,
    informationCutoff: isBasis && state?.information_cutoff ? state.information_cutoff : cutoff?.[1] ?? null,
    standardId: revisionMatches ? state.standard_id : null,
    standardLabel: revisionMatches ? standard.label : "历史标准未确认",
    valueDefinition: revisionMatches ? standard.value_definition : null,
    acceptedAt: revisionMatches ? state.accepted_at : null,
    compatible,
  };
}

export function displayEligibility(state, metadata) {
  const fail = (stateCode, reason) => ({ eligible: false, state: stateCode, reason });
  if (state?.universe_status === "inactive") return fail("inactive", "证券不在当前在市范围，仅保留历史研究");
  if (!state?.basis_report_path) return fail("pending_research", "尚无研究依据报告");
  if (!metadata || metadata.sourcePath !== state.basis_report_path) return fail("needs_review", "研究依据报告缺失，未回退到其他周期");
  if (!["covered", "ignore"].includes(state.status)) return fail("pending_research", "尚无完成的周期研究");
  const stamp = [state.standard_id, state.spec_revision, state.accepted_at];
  if (stamp.every((value) => value == null)) return fail("pending_standard", "历史标准未确认，待按现行标准研究");
  if (!stamp.every(nonblank)) return fail("needs_review", "研究标准信息不完整，需要修复状态");
  if (state.symbol && !state.symbol.startsWith("CN:")) {
    const currency = state.symbol.startsWith("HK:") ? "HKD" : "USD";
    if (!state.financial_basis?.period_end || !state.security_basis?.unit
      || state.security_basis.currency !== currency || !(state.security_basis.ordinary_shares_per_unit > 0)
      || (state.value_range && state.value_range.currency !== currency)
      || (state.return_model && state.return_model.currency !== currency)) {
      return fail("needs_review", "财务期末或证券币种/单位未明确");
    }
  }
  if (!metadata.compatible) return fail("pending_standard", "原研究标准不兼容现行标准");
  if (state.universe_status !== "active") return fail("inactive", "证券不在当前在市范围");
  return { eligible: true, state: state.value_range ? "current" : "unpriced",
    reason: state.value_range ? "符合现行兼容标准" : "研究完成，暂无法形成可靠价值区间" };
}

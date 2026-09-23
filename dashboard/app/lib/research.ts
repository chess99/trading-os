import { calculateIrrRange } from "./irr.mjs";
import { isCurrentResult } from "./display-policy.mjs";

export type ResearchStatus = "unseen" | "ignore" | "candidate" | "covered" | "stale" | "unregistered";
export type DisplayState = "current" | "unpriced" | "pending_research" | "pending_standard" | "needs_update" | "needs_review" | "inactive";
export interface ReportVersion {
  date: string; path: string; sourcePath: string; informationCutoff: string | null;
  standardId: string | null; standardLabel: string; valueDefinition: string | null;
  acceptedAt: string | null; compatible: boolean; acceptanceStatus: string;
}
export interface TerminalEquityValueRange { low: number; high: number }
export interface ReturnModel {
  schema_version: 1; method: "annual_common_equity_irr_v1"; currency: "CNY"; model_as_of: string;
  base_case_distributions_per_share: number[];
  base_case_terminal_equity_value_range_per_share: { year_5: TerminalEquityValueRange; year_3?: TerminalEquityValueRange };
}
export interface IrrRange { low: number | null; midpoint: number | null; high: number | null }
export interface Company {
  symbol: string; ticker: string; name: string; exchange: string; industry: string;
  status: ResearchStatus; universeStatus: "active" | "inactive" | "unregistered";
  hasResearchState: boolean; inQualityPool: boolean; qualityTier: string | null;
  updatedAt: string | null; informationCutoff: string | null;
  invalidation: { at?: string; reason?: string; update_path?: string } | null; candidateSince: string | null;
  display: { eligible: boolean; state: DisplayState; reason: string };
  standardId: string | null; standardLabel: string; acceptedAt: string | null;
  summary: string; valueRange: { currency: string; low: number; high: number } | null; valuationNote: string | null;
  returnModel: ReturnModel | null; returnModelNote: string | null;
  returnModelDisplayIssue?: { event_date: string; reason: string; source_url: string } | null;
  reportPath: string | null; reportDate: string | null; reports: ReportVersion[]; eventTriggerCount: number;
}
export interface ResearchStandard {
  id: string; label: string; status: string; published_at: string; spec_revision: string;
  value_definition: string; value_label: string; compatible_with: string[];
  compatibility_note: string; change_note: string;
}
export interface ProgressCounts {
  total: number; completed: number; valued: number; unpriced: number;
  pending: number; updating: number; review: number; inactive: number;
}
export interface Catalog {
  schemaVersion: 2; generatedAt: string; standard: ResearchStandard; standards: ResearchStandard[];
  scope: { id: string; label: string; asOf: string; count: number };
  stats: { total: number; researchStateRows: number; active: number; reports: number;
    status: Record<ResearchStatus, number>; queue: { queued: number; running: number; total: number };
    current: ProgressCounts; allStandard: ProgressCounts };
  companies: Company[];
}
export interface Quote {
  symbol: string; ticker: string; name: string; price: number; previousClose: number | null;
  change: number | null; changePercent: number | null; quoteAt: string | null; source: "tencent" | "eastmoney";
}
export const STATUS_META: Record<ResearchStatus, { label: string; shortLabel: string; description: string }> = {
  covered: { label: "持续覆盖", shortLabel: "已覆盖", description: "研究有效且值得持续维护，不代表买入建议。" },
  ignore: { label: "暂不持续覆盖", shortLabel: "暂不覆盖", description: "可以是完成研究后的否定结论，不等于未研究。" },
  stale: { label: "等待更新", shortLabel: "待更新", description: "新事实已使当前报告失效。" },
  candidate: { label: "候选研究", shortLabel: "候选", description: "等待或正在完成研究。" },
  unseen: { label: "尚未筛选", shortLabel: "未筛选", description: "尚未完成首次研究初筛。" },
  unregistered: { label: "待衔接研究状态", shortLabel: "待登记", description: "已在质量池，尚无研究状态记录；此占位不修改状态。" },
};
export async function loadCatalog(signal?: AbortSignal): Promise<Catalog> {
  const response = await fetch("/data/research-catalog.json", { signal, cache: "no-store" });
  if (!response.ok) throw new Error("研究目录暂时无法读取");
  const catalog = (await response.json()) as Catalog;
  if (catalog.schemaVersion !== 2 || !catalog.standard || !catalog.scope || !Array.isArray(catalog.companies)) {
    throw new Error("目录尚未按现行展示标准构建，已停止混用旧估值。请重新生成并发布研究目录。");
  }
  return { ...catalog, companies: catalog.companies.map((company) => {
    const eligible = isCurrentResult(company, "all_standard");
    return { ...company, summary: eligible ? company.summary : "",
      valueRange: eligible ? company.valueRange ?? null : null,
      returnModel: eligible ? company.returnModel ?? null : null,
      returnModelNote: eligible ? company.returnModelNote ?? null : null };
  }) };
}
export async function loadQuotes(tickers: string[], signal?: AbortSignal): Promise<Quote[]> {
  if (!tickers.length) return [];
  const chunks: string[][] = [];
  for (let offset = 0; offset < tickers.length; offset += 80) chunks.push(tickers.slice(offset, offset + 80));
  const payloads = await Promise.all(chunks.map(async (chunk) => {
    const response = await fetch(`/api/quotes?${new URLSearchParams({ symbols: chunk.join(",") })}`, { signal });
    if (!response.ok) return { quotes: [] as Quote[] };
    return (await response.json()) as { quotes: Quote[] };
  }));
  return payloads.flatMap((payload) => payload.quotes);
}
export function pricePosition(company: Company, quote?: Quote) {
  const price = quote?.price ?? null;
  const range = isCurrentResult(company, "all_standard") ? company.valueRange : null;
  if (price === null || !range || range.low <= 0 || range.high < range.low) {
    return { price, lowRatio: null, midpointRatio: null, label: "—" };
  }
  return { price, lowRatio: price / range.low, midpointRatio: price / ((range.low + range.high) / 2),
    label: price < range.low ? "低于区间下沿" : price <= range.high ? "区间内" : "高于区间上沿" };
}
export function returnIrr(company: Company, quote: Quote | undefined, horizonYears: 3 | 5): IrrRange | null {
  if (!isCurrentResult(company, "all_standard") || company.returnModelDisplayIssue) return null;
  if (!company.returnModel || company.returnModel.model_as_of !== company.informationCutoff) return null;
  return calculateIrrRange(quote?.price, company.returnModel, horizonYears);
}
export function formatPrice(value: number | null | undefined) {
  return value == null || !Number.isFinite(value) ? "—" : new Intl.NumberFormat("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
}
export function formatIrr(value: number | null | undefined) {
  return value == null || !Number.isFinite(value) ? "—" : `${new Intl.NumberFormat("zh-CN", { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Math.abs(value) < 0.0005 ? 0 : value * 100)}%`;
}
export function formatDate(value: string | null | undefined, withTime = false) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit",
    ...(withTime ? { hour: "2-digit", minute: "2-digit", hour12: false } : {}) }).format(date);
}
export function cleanCompanyName(name: string) { return name.replace(/\s+/gu, " ").trim(); }

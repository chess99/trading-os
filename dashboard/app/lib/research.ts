import { matchingQuoteCurrency } from "./market-quotes.mjs";
import { calculateIrrRange } from "./irr.mjs";
import { isCurrentResult } from "./display-policy.mjs";

export type ResearchStatus = "unseen" | "ignore" | "covered" | "unregistered";
export type DisplayState = "current" | "unpriced" | "pending_research" | "pending_standard" | "needs_review" | "inactive";
export interface ReportVersion {
  period: string; periodEnd?: string | null; path: string; sourcePath: string; informationCutoff: string | null;
  standardId: string | null; standardLabel: string; valueDefinition: string | null;
  acceptedAt: string | null; compatible: boolean;
}
export interface TerminalEquityValueRange { low: number; high: number }
export interface ReturnModel {
  schema_version: 1; method: "annual_common_equity_irr_v1"; currency: "CNY" | "HKD" | "USD"; model_as_of: string;
  base_case_distributions_per_share: number[];
  base_case_terminal_equity_value_range_per_share: { year_5: TerminalEquityValueRange; year_3?: TerminalEquityValueRange };
}
export interface IrrRange { low: number | null; midpoint: number | null; high: number | null }
export type ResearchTrack = "compounder" | "inflection_growth";
export type CycleStage = "upcycle_tight" | "inflection_bottom" | "mature_stable" | "downcycle_clearing" | "overcapacity";
export type ProfitPoolTrend = "expanding" | "stable" | "contracting";
export type MacroAlignment = "tailwind" | "neutral" | "headwind";
export interface IndustryState {
  cycleStage: CycleStage;
  profitPoolTrend: ProfitPoolTrend;
  macroAlignment: MacroAlignment;
  macroTransmission: string;
  inflectionCandidate: boolean;
  keyDrivers: string[];
  topic?: string;
  label?: string;
  documentId?: string;
  publishedOn?: string;
  informationCutoff?: string | null;
}
export interface DecisionProfile {
  track: ResearchTrack;
  valuation_framework: "dividend_dcf_v1" | "buyback_total_yield" | "growth_terminal_matrix" | "cyclical_cost_curve";
  industry_topic: string;
  business_quality: "A" | "B" | "C";
  capital_allocation: "high" | "medium" | "low";
  predictability: "high" | "medium" | "low";
  downside_risk: "low" | "medium" | "high";
  exposure_tags: string[];
  thesis_breakers: string[];
}
export interface Scenarios {
  currency: "CNY" | "HKD";
  structural_bear: number;
  cyclical_bear: number;
  base_low: number;
  base_high: number;
  bull: number;
  horizon_note: string;
}
export interface CapitalReturnProfile {
  annual_net_buyback_per_share: number | null;
  southbound_dividend_tax_rate: number | null;
  note: string;
}
export interface AhBridge {
  role: "A" | "H" | "HK_ONLY";
  pairSymbol: string | null;
  pairName: string | null;
  issuer: string;
  sharesRatio: number | null;
  hShareStructure: string;
  aDividendTaxRateOver1Y: number | null;
  southboundDividendTaxRate: number | null;
  southboundUnavailableOn?: string;
  taxNote: string;
}
export interface MacroFactor {
  id: string;
  label: string;
  direction: string;
  reading: string;
  implication: string;
}
export interface MacroBenchmark {
  id: string;
  name: string;
  market: "CN" | "HK" | "US";
  observedOn: string | null;
  pe: number | null;
  pb: number | null;
  dividendYieldPct: number | null;
  earningsYieldPct: number | null;
  bondYield10yPct: number | null;
  erpPct: number | null;
  cape: number | null;
  percentile5y: number | null;
  percentile10y: number | null;
  note: string;
}
export interface QdiiCatalog {
  schemaVersion: number;
  updatedOn: string;
  trackedIndices: { id: string; name: string; englishName: string; currency: string; focusMetrics: string[] }[];
  etfs: { symbol: string; name: string; manager: string; trackedIndex: string; currencyExposure: string; checkItems: string[] }[];
}
export interface MacroEnvironment {
  macroRegime: { asOf: string; regimeSummary?: string; factors?: MacroFactor[]; documentId?: string; publishedOn?: string; informationCutoff?: string | null } | null;
  marketBenchmarks: { asOf: string; benchmarks?: MacroBenchmark[]; documentId?: string; publishedOn?: string; informationCutoff?: string | null } | null;
  qdiiCatalog: QdiiCatalog | null;
  globalBenchmarksCount: number;
}
export interface Company {
  symbol: string; ticker: string; code: string; market: "CN" | "HK"; issuer: string;
  quoteCurrency: string; financialBasis: { period_end: string; published_on: string; source_url: string } | null;
  securityBasis: { currency: string; unit: string; ordinary_shares_per_unit: number; source_url: string } | null;
  name: string; exchange: string; industry: string;
  track?: ResearchTrack;
  industryTopic?: string | null;
  industryState?: IndustryState | null;
  ahBridge?: AhBridge | null;
  status: ResearchStatus; universeStatus: "active" | "inactive" | "unregistered";
  hasResearchState: boolean; inQualityPool: boolean; qualityTier: string | null;
  updatedAt: string | null; informationCutoff: string | null;
  display: { eligible: boolean; state: DisplayState; reason: string };
  standardId: string | null; standardLabel: string; acceptedAt: string | null;
  summary: string; valueRange: { currency: string; low: number; high: number } | null; valuationNote: string | null;
  returnModel: ReturnModel | null; returnModelNote: string | null;
  returnModelDisplayIssue?: { event_date: string; reason: string; source_url: string } | null;
  decisionProfile?: DecisionProfile | null;
  scenarios?: Scenarios | null;
  capitalReturnProfile?: CapitalReturnProfile | null;
  reportPeriod: string | null; basisReportPath: string | null; reportUpdatedAt: string | null;
  latestReportPeriod: string | null; pendingReportPeriod: string | null;
  pendingTaskKind: "periodic" | "manual_rewrite" | null; reports: ReportVersion[];
}
export interface ResearchStandard {
  id: string; label: string; status: string; published_at: string; spec_revision: string;
  value_definition: string; value_label: string; compatible_with: string[];
  compatibility_note: string; change_note: string;
}
export interface ProgressCounts {
  total: number; completed: number; valued: number; unpriced: number;
  pending: number; review: number; inactive: number;
}
export interface Catalog {
  schemaVersion: 2; generatedAt: string; standard: ResearchStandard; standards: ResearchStandard[];
  scope: { id: string; label: string; asOf: string; count: number };
  environment?: MacroEnvironment;
  stats: { total: number; researchStateRows: number; active: number; reports: number;
    status: Record<ResearchStatus, number>; queue: { queued: number; running: number; total: number };
    current: ProgressCounts; allStandard: ProgressCounts };
  companies: Company[];
}
export interface Quote {
  symbol: string; ticker: string; name: string; price: number; previousClose: number | null;
  currency?: string;
  change: number | null; changePercent: number | null; quoteAt: string | null; source: "tencent" | "eastmoney" | "yahoo";
}
export const STATUS_META: Record<ResearchStatus, { label: string; shortLabel: string; description: string }> = {
  covered: { label: "本周期：持续覆盖", shortLabel: "持续覆盖", description: "最近完成周期的研究结论，不代表今日推荐。" },
  ignore: { label: "本周期：不持续覆盖", shortLabel: "不持续覆盖", description: "可以是完成研究后的否定结论，不等于未研究。" },
  unseen: { label: "尚无公司研究", shortLabel: "待研究", description: "尚未完成首次完整公司研究。" },
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
      returnModelNote: eligible ? company.returnModelNote ?? null : null,
      decisionProfile: eligible ? company.decisionProfile ?? null : null,
      scenarios: eligible ? company.scenarios ?? null : null,
      capitalReturnProfile: eligible ? company.capitalReturnProfile ?? null : null };
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
  const matching = matchingQuoteCurrency(quote, company.quoteCurrency ?? company.valueRange?.currency ?? "CNY");
  const price = matching && quote ? quote.price : null;
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
  if (!matchingQuoteCurrency(quote, company.returnModel.currency)) return null;
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

export const EQUITY_MARKET_LABELS = { all: "全部市场", CN: "A股", HK: "港股" };
export const MARKET_LABELS = { all: "全部市场", CN: "A股", HK: "港股", US: "美股/宽基" };
export function currencyLabel(currency?: string) { return ({ CNY: "¥", HKD: "HK$", USD: "US$" } as Record<string,string>)[currency ?? "CNY"] ?? currency ?? ""; }

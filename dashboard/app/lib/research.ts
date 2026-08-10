export type ResearchStatus = "unseen" | "ignore" | "candidate" | "covered" | "stale";

export interface PriceLevel {
  id: string;
  label: string;
  threshold: number;
  rearmAbove: number;
  armed: boolean;
  lastClose: number | null;
  lastScanDate: string | null;
  lastHitDate: string | null;
}

export interface ReportVersion {
  date: string;
  path: string;
}

export interface Company {
  symbol: string;
  ticker: string;
  name: string;
  exchange: string;
  industry: string;
  status: ResearchStatus;
  universeStatus: "active" | "inactive";
  updatedAt: string;
  summary: string;
  informationCutoff: string | null;
  invalidation: string | null;
  candidateSince: string | null;
  valueRange: { currency: string; low: number; high: number } | null;
  priceLevels: PriceLevel[];
  lastClose: number | null;
  lastCloseDate: string | null;
  reportPath: string | null;
  reportDate: string | null;
  reports: ReportVersion[];
  eventTriggerCount: number;
}

export interface Catalog {
  generatedAt: string;
  stats: {
    total: number;
    active: number;
    reports: number;
    status: Record<ResearchStatus, number>;
    queue: { queued: number; running: number; total: number };
  };
  companies: Company[];
}

export interface Quote {
  symbol: string;
  ticker: string;
  name: string;
  price: number;
  previousClose: number | null;
  change: number | null;
  changePercent: number | null;
  quoteAt: string | null;
  source: "tencent" | "eastmoney";
}

export const STATUS_META: Record<
  ResearchStatus,
  { label: string; shortLabel: string; description: string }
> = {
  covered: {
    label: "持续覆盖",
    shortLabel: "已覆盖",
    description: "正式研报当前有效，正在进行价格或事件监控。",
  },
  candidate: {
    label: "候选研究",
    shortLabel: "候选",
    description: "已通过初筛，等待或正在完成正式研究。",
  },
  stale: {
    label: "等待更新",
    shortLabel: "待更新",
    description: "重大事实已使当前研报失效，价格监控暂停。",
  },
  ignore: {
    label: "暂不关注",
    shortLabel: "忽略",
    description: "当前不值得投入正式研究或持续监控。",
  },
  unseen: {
    label: "尚未筛选",
    shortLabel: "未筛选",
    description: "尚未完成首次市场初筛。",
  },
};

export async function loadCatalog(signal?: AbortSignal): Promise<Catalog> {
  const response = await fetch("/data/research-catalog.json", { signal });
  if (!response.ok) throw new Error("研究目录暂时无法读取");
  return (await response.json()) as Catalog;
}

export async function loadQuotes(tickers: string[], signal?: AbortSignal): Promise<Quote[]> {
  if (!tickers.length) return [];
  const chunks: string[][] = [];
  for (let offset = 0; offset < tickers.length; offset += 80) {
    chunks.push(tickers.slice(offset, offset + 80));
  }
  const payloads = await Promise.all(
    chunks.map(async (chunk) => {
      const params = new URLSearchParams({ symbols: chunk.join(",") });
      const response = await fetch(`/api/quotes?${params.toString()}`, { signal });
      if (!response.ok) return { quotes: [] as Quote[] };
      return (await response.json()) as { quotes: Quote[] };
    }),
  );
  return payloads.flatMap((payload) => payload.quotes);
}

export function primaryPriceLevel(company: Company): PriceLevel | null {
  if (!company.priceLevels.length) return null;
  return [...company.priceLevels].sort((a, b) => b.threshold - a.threshold)[0];
}

export function effectivePrice(company: Company, quote?: Quote): number | null {
  return quote?.price ?? company.lastClose;
}

function clamp(value: number, low = 0, high = 100) {
  return Math.min(high, Math.max(low, value));
}

export function opportunityPriority(company: Company, quote?: Quote) {
  const price = effectivePrice(company, quote);
  const level = primaryPriceLevel(company);
  if (price === null) {
    return { score: 0, label: "等待行情", distance: null, price: null, level };
  }

  let triggerScore = 25;
  let distance: number | null = null;
  if (level) {
    distance = (price - level.threshold) / level.threshold;
    triggerScore = distance <= 0 ? 100 : clamp(100 - distance * 180, 12, 100);
  }

  let valueScore = 35;
  const range = company.valueRange;
  if (range) {
    if (price <= range.low) valueScore = 100;
    else if (price <= range.high) {
      valueScore = 100 - ((price - range.low) / Math.max(range.high - range.low, 0.01)) * 35;
    } else {
      valueScore = clamp(65 - ((price - range.high) / range.high) * 120);
    }
  }

  const cutoff = company.informationCutoff ? new Date(company.informationCutoff).getTime() : 0;
  const ageDays = cutoff ? Math.max(0, (Date.now() - cutoff) / 86_400_000) : 365;
  const freshnessScore = clamp(100 - ageDays * 0.45, 20, 100);
  const score = Math.round(triggerScore * 0.55 + valueScore * 0.35 + freshnessScore * 0.1);
  const label =
    level && distance !== null && distance <= 0
      ? "已到复核区"
      : score >= 78
        ? "接近关注"
        : score >= 58
          ? "估值可读"
          : "继续观察";
  return { score, label, distance, price, level };
}

export function formatPrice(value: number | null | undefined) {
  return value === null || value === undefined
    ? "—"
    : new Intl.NumberFormat("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(
        value,
      );
}

export function formatDate(value: string | null | undefined, withTime = false) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(withTime ? { hour: "2-digit", minute: "2-digit", hour12: false } : {}),
  }).format(date);
}

export function cleanCompanyName(name: string) {
  return name.replace(/\s+/gu, " ").trim();
}

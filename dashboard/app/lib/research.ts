export type ResearchStatus = "unseen" | "ignore" | "candidate" | "covered" | "stale";

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
  invalidation: { at?: string; reason?: string; update_path?: string } | null;
  candidateSince: string | null;
  valueRange: { currency: string; low: number; high: number } | null;
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
    description: "正式研报当前有效，等待公司、财务、治理或行业新事实。",
  },
  candidate: {
    label: "候选研究",
    shortLabel: "候选",
    description: "已通过初筛，等待或正在完成正式研究。",
  },
  stale: {
    label: "等待更新",
    shortLabel: "待更新",
    description: "重大事实已使当前研报失效，等待完整更新研究。",
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

export function pricePosition(company: Company, quote?: Quote) {
  const price = quote?.price ?? null;
  const range = company.valueRange;
  if (price === null || !range) {
    return { price, lowRatio: null, midpointRatio: null, label: "—" };
  }
  const lowRatio = price / range.low;
  const midpointRatio = price / ((range.low + range.high) / 2);
  const label = price < range.low ? "低于区间下沿" : price <= range.high ? "区间内" : "高于区间上沿";
  return { price, lowRatio, midpointRatio, label };
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

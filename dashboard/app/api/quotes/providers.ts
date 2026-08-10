import type { Quote } from "../../lib/research";

const TENCENT_ENDPOINT = "https://qt.gtimg.cn/q=";
const EASTMONEY_ENDPOINT = "https://push2.eastmoney.com/api/qt/ulist.np/get";
const TICKER_PATTERN = /^\d{6}$/u;

export function normalizeTickers(values: string[]) {
  return [...new Set(values.map((value) => value.trim()).filter((value) => TICKER_PATTERN.test(value)))];
}

function exchangePrefix(ticker: string) {
  if (/^(?:5|6|9)/u.test(ticker)) return "sh";
  if (/^(?:4|8)/u.test(ticker) || ticker.startsWith("920")) return "bj";
  return "sz";
}

function eastmoneySecurityId(ticker: string) {
  return `${exchangePrefix(ticker) === "sh" ? "1" : "0"}.${ticker}`;
}

function finiteNumber(value: unknown): number | null {
  const parsed = typeof value === "number" ? value : Number.parseFloat(String(value ?? ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function isoFromTencent(value: string) {
  if (!/^\d{14}$/u.test(value)) return null;
  const parts = value.match(/^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})$/u);
  if (!parts) return null;
  return `${parts[1]}-${parts[2]}-${parts[3]}T${parts[4]}:${parts[5]}:${parts[6]}+08:00`;
}

export async function fetchTencentQuotes(tickers: string[]): Promise<Quote[]> {
  if (!tickers.length) return [];
  const codes = tickers.map((ticker) => `${exchangePrefix(ticker)}${ticker}`);
  const response = await fetch(`${TENCENT_ENDPOINT}${codes.join(",")}`, {
    headers: {
      Accept: "text/plain,*/*",
      Referer: "https://gu.qq.com/",
      "User-Agent": "Trading-OS dashboard/1.0",
    },
  });
  if (!response.ok) throw new Error(`Tencent quote request failed: ${response.status}`);
  const bytes = await response.arrayBuffer();
  const text = new TextDecoder("gbk").decode(bytes);
  const rows = [...text.matchAll(/v_(?:sh|sz|bj)(\d{6})="([^"\r\n]*)";/gu)];
  const quotes: Quote[] = [];
  for (const match of rows) {
    const fields = match[2].split("~");
    const price = finiteNumber(fields[3]);
    if (price === null || price <= 0) continue;
    const previousClose = finiteNumber(fields[4]);
    const explicitChange = finiteNumber(fields[31]);
    const explicitPercent = finiteNumber(fields[32]);
    const change = explicitChange ?? (previousClose ? price - previousClose : null);
    const changePercent =
      explicitPercent ?? (previousClose && change !== null ? (change / previousClose) * 100 : null);
    quotes.push({
      symbol: `CN:${match[1]}`,
      ticker: match[1],
      name: fields[1] || match[1],
      price,
      previousClose,
      change,
      changePercent,
      quoteAt: isoFromTencent(fields[30] ?? ""),
      source: "tencent",
    });
  }
  return quotes;
}

interface EastmoneyRow {
  f2?: number | string;
  f3?: number | string;
  f4?: number | string;
  f12?: string;
  f14?: string;
  f18?: number | string;
  f124?: number | string;
}

export async function fetchEastmoneyQuotes(tickers: string[]): Promise<Quote[]> {
  if (!tickers.length) return [];
  const params = new URLSearchParams({
    secids: tickers.map(eastmoneySecurityId).join(","),
    fields: "f2,f3,f4,f12,f14,f18,f124",
    fltt: "2",
  });
  const response = await fetch(`${EASTMONEY_ENDPOINT}?${params.toString()}`, {
    headers: {
      Accept: "application/json",
      Referer: "https://quote.eastmoney.com/",
      "User-Agent": "Trading-OS dashboard/1.0",
    },
  });
  if (!response.ok) throw new Error(`Eastmoney quote request failed: ${response.status}`);
  const payload = (await response.json()) as { data?: { diff?: EastmoneyRow[] } };
  return (payload.data?.diff ?? []).flatMap((row) => {
    const ticker = String(row.f12 ?? "");
    const price = finiteNumber(row.f2);
    if (!TICKER_PATTERN.test(ticker) || price === null || price <= 0) return [];
    const timestamp = finiteNumber(row.f124);
    return [
      {
        symbol: `CN:${ticker}`,
        ticker,
        name: String(row.f14 ?? ticker),
        price,
        previousClose: finiteNumber(row.f18),
        change: finiteNumber(row.f4),
        changePercent: finiteNumber(row.f3),
        quoteAt: timestamp ? new Date(timestamp * 1000).toISOString() : null,
        source: "eastmoney" as const,
      },
    ];
  });
}

export async function fetchQuotesWithFallback(tickers: string[]) {
  const normalized = normalizeTickers(tickers);
  if (!normalized.length) return { quotes: [], missing: [], providers: [] as string[] };
  const byTicker = new Map<string, Quote>();
  const providers: string[] = [];

  try {
    const quotes = await fetchTencentQuotes(normalized);
    quotes.forEach((quote) => byTicker.set(quote.ticker, quote));
    if (quotes.length) providers.push("tencent");
  } catch {
    // The secondary provider below keeps the dashboard usable when Tencent is unavailable.
  }

  const missingAfterTencent = normalized.filter((ticker) => !byTicker.has(ticker));
  if (missingAfterTencent.length) {
    try {
      const quotes = await fetchEastmoneyQuotes(missingAfterTencent);
      quotes.forEach((quote) => byTicker.set(quote.ticker, quote));
      if (quotes.length) providers.push("eastmoney");
    } catch {
      // The client will use the last validated closing price for any remaining symbols.
    }
  }

  return {
    quotes: normalized.flatMap((ticker) => (byTicker.has(ticker) ? [byTicker.get(ticker)!] : [])),
    missing: normalized.filter((ticker) => !byTicker.has(ticker)),
    providers,
  };
}

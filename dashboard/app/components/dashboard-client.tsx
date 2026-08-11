"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  cleanCompanyName,
  effectivePrice,
  formatDate,
  formatPrice,
  loadCatalog,
  loadQuotes,
  opportunityPriority,
  STATUS_META,
  type Catalog,
  type Company,
  type PriceLevel,
  type Quote,
  type ResearchStatus,
} from "../lib/research";

type ExplorerView = "opportunities" | "market";
type MarketSort = "updated" | "name" | "status";

const STATUS_ORDER: ResearchStatus[] = ["covered", "candidate", "stale", "ignore", "unseen"];
const QUOTE_REFRESH_INTERVAL_MS = 5 * 60 * 1000;

function isChinaMarketOpen(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Shanghai",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value ?? "";
  const weekday = part("weekday");
  if (weekday === "Sat" || weekday === "Sun") return false;

  const minutes = Number(part("hour")) * 60 + Number(part("minute"));
  return (minutes >= 9 * 60 + 30 && minutes <= 11 * 60 + 30) || (minutes >= 13 * 60 && minutes <= 15 * 60);
}

function latestQuoteTimestamp(quotes: Quote[]) {
  return quotes.reduce<string | null>((latest, quote) => {
    if (!quote.quoteAt || Number.isNaN(Date.parse(quote.quoteAt))) return latest;
    if (!latest || Date.parse(quote.quoteAt) > Date.parse(latest)) return quote.quoteAt;
    return latest;
  }, null);
}

function formatQuoteTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function statusCount(catalog: Catalog, status: ResearchStatus) {
  return catalog.stats.status[status] ?? 0;
}

function quoteChangeClass(quote?: Quote) {
  if (!quote?.change) return "price-flat";
  return quote.change > 0 ? "price-up" : "price-down";
}

function quoteSourceLabel(quote?: Quote, fallbackDate?: string | null) {
  if (quote?.source === "tencent") return "腾讯行情";
  if (quote?.source === "eastmoney") return "东方财富行情";
  return fallbackDate ? `${fallbackDate} 收盘` : "行情待同步";
}

function isHighAttractionLevel(level: PriceLevel) {
  return /高吸引力|安全边际/u.test(level.label);
}

function groupPriceLevels(company: Company) {
  const sorted = [...company.priceLevels].sort((a, b) => b.threshold - a.threshold);
  return {
    attention: sorted.filter((level) => !isHighAttractionLevel(level)),
    highAttraction: sorted.filter(isHighAttractionLevel),
  };
}

function PriceLevelCell({ levels }: { levels: PriceLevel[] }) {
  if (!levels.length) return <td className="level-cell empty-price">—</td>;

  const thresholds = levels.map((level) => level.threshold).sort((a, b) => a - b);
  const value =
    thresholds.length === 1
      ? formatPrice(thresholds[0])
      : `${formatPrice(thresholds[0])}–${formatPrice(thresholds.at(-1))}`;
  const labels = [...new Set(levels.map((level) => level.label))].join(" / ");

  return (
    <td className="level-cell" title={levels.map((level) => `${level.label} ¥${formatPrice(level.threshold)}`).join("；")}>
      <strong>¥{value}</strong>
      <span>{labels}</span>
    </td>
  );
}

function StatusBadge({ status }: { status: ResearchStatus }) {
  return (
    <span className={`status-badge status-${status}`} title={STATUS_META[status].description}>
      {STATUS_META[status].label}
    </span>
  );
}

export function DashboardClient() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [quotes, setQuotes] = useState<Map<string, Quote>>(new Map());
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [quoteState, setQuoteState] = useState<"loading" | "live" | "fallback">("loading");
  const [quoteRefreshing, setQuoteRefreshing] = useState(false);
  const [quoteUpdatedAt, setQuoteUpdatedAt] = useState<string | null>(null);
  const [view, setView] = useState<ExplorerView>("opportunities");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ResearchStatus | "all">("all");
  const [industry, setIndustry] = useState("all");
  const [marketSort, setMarketSort] = useState<MarketSort>("updated");
  const [visibleRows, setVisibleRows] = useState(80);
  const searchRef = useRef<HTMLInputElement>(null);
  const quoteRefreshRunningRef = useRef(false);
  const lastQuoteRequestAtRef = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    loadCatalog(controller.signal)
      .then(setCatalog)
      .catch((error: Error) => {
        if (error.name !== "AbortError") setCatalogError(error.message);
      });
    return () => controller.abort();
  }, []);

  const refreshQuotes = useCallback(async (signal?: AbortSignal) => {
    if (!catalog || quoteRefreshRunningRef.current) return;
    quoteRefreshRunningRef.current = true;
    lastQuoteRequestAtRef.current = Date.now();
    setQuoteRefreshing(true);

    const coveredTickers = catalog.companies
      .filter((company) => company.status === "covered")
      .map((company) => company.ticker);
    try {
      const nextQuotes = await loadQuotes(coveredTickers, signal);
      if (signal?.aborted) return;
      if (nextQuotes.length) {
        setQuotes(new Map(nextQuotes.map((quote) => [quote.ticker, quote])));
        setQuoteUpdatedAt(latestQuoteTimestamp(nextQuotes) ?? new Date().toISOString());
        setQuoteState("live");
      } else {
        setQuoteState((current) => current === "live" ? current : "fallback");
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") return;
      setQuoteState((current) => current === "live" ? current : "fallback");
    } finally {
      quoteRefreshRunningRef.current = false;
      if (!signal?.aborted) setQuoteRefreshing(false);
    }
  }, [catalog]);

  useEffect(() => {
    if (!catalog) return;
    const controller = new AbortController();
    const initialRefresh = window.setTimeout(() => void refreshQuotes(controller.signal), 0);

    function refreshIfDue() {
      if (document.visibilityState !== "visible" || !isChinaMarketOpen()) return;
      if (Date.now() - lastQuoteRequestAtRef.current < QUOTE_REFRESH_INTERVAL_MS) return;
      void refreshQuotes(controller.signal);
    }

    const interval = window.setInterval(refreshIfDue, 60_000);
    document.addEventListener("visibilitychange", refreshIfDue);
    return () => {
      controller.abort();
      window.clearTimeout(initialRefresh);
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", refreshIfDue);
    };
  }, [catalog, refreshQuotes]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "/" && document.activeElement?.tagName !== "INPUT") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const opportunities = useMemo(() => {
    if (!catalog) return [];
    return catalog.companies
      .filter((company) => company.status === "covered")
      .sort((a, b) => {
        const priorityDifference =
          opportunityPriority(b, quotes.get(b.ticker)).score -
          opportunityPriority(a, quotes.get(a.ticker)).score;
        if (priorityDifference) return priorityDifference;
        return b.updatedAt.localeCompare(a.updatedAt) || a.ticker.localeCompare(b.ticker);
      });
  }, [catalog, quotes]);

  const industries = useMemo(() => {
    if (!catalog) return [];
    const counts = new Map<string, number>();
    catalog.companies.forEach((company) => counts.set(company.industry, (counts.get(company.industry) ?? 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh-CN"));
  }, [catalog]);

  const triggerCount = useMemo(
    () =>
      opportunities.filter((company) => {
        const priority = opportunityPriority(company, quotes.get(company.ticker));
        return priority.distance !== null && priority.distance <= 0;
      }).length,
    [opportunities, quotes],
  );

  const filtered = useMemo(() => {
    if (!catalog) return [];
    const normalizedQuery = query.trim().toLocaleLowerCase("zh-CN");
    let rows = view === "opportunities" ? opportunities : [...catalog.companies];
    if (status !== "all") rows = rows.filter((company) => company.status === status);
    if (industry !== "all") rows = rows.filter((company) => company.industry === industry);
    if (normalizedQuery) {
      rows = rows.filter((company) =>
        [company.name, company.ticker, company.symbol, company.industry, company.summary]
          .join(" ")
          .toLocaleLowerCase("zh-CN")
          .includes(normalizedQuery),
      );
    }
    if (view === "market") {
      rows.sort((a, b) => {
        if (marketSort === "name") return a.name.localeCompare(b.name, "zh-CN");
        if (marketSort === "status") {
          return STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status) || a.ticker.localeCompare(b.ticker);
        }
        return b.updatedAt.localeCompare(a.updatedAt) || a.ticker.localeCompare(b.ticker);
      });
    }
    return rows;
  }, [catalog, industry, marketSort, opportunities, query, status, view]);

  function switchView(nextView: ExplorerView) {
    setView(nextView);
    setStatus("all");
    setVisibleRows(80);
  }

  function showStatus(nextStatus: ResearchStatus) {
    setView("market");
    setStatus(nextStatus);
    setVisibleRows(80);
    document.getElementById("company-explorer")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (catalogError) {
    return (
      <main className="load-state error-state">
        <span>研究目录读取失败</span>
        <h1>页面暂时没有拿到仓库数据</h1>
        <p>{catalogError}</p>
        <button onClick={() => window.location.reload()}>重新载入</button>
      </main>
    );
  }

  if (!catalog) {
    return (
      <main className="dashboard-shell dashboard-loading" aria-busy="true">
        <div className="loading-state-strip" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
        </div>
        <div className="loading-table" aria-hidden="true" />
      </main>
    );
  }

  return (
    <main className="dashboard-shell">
      <section className="state-strip" aria-label="研究状态概览">
        <button onClick={() => switchView("opportunities")}>
          <span className="state-number">{statusCount(catalog, "covered")}</span>
          <span className="state-copy"><strong>持续覆盖</strong></span>
        </button>
        <button className={triggerCount ? "attention" : ""} onClick={() => switchView("opportunities")}>
          <span className="state-number">{triggerCount}</span>
          <span className="state-copy"><strong>进入复核区</strong></span>
        </button>
        <button onClick={() => showStatus("candidate")}>
          <span className="state-number">{statusCount(catalog, "candidate")}</span>
          <span className="state-copy"><strong>候选研究</strong></span>
        </button>
        <button className={statusCount(catalog, "stale") ? "attention" : ""} onClick={() => showStatus("stale")}>
          <span className="state-number">{statusCount(catalog, "stale")}</span>
          <span className="state-copy"><strong>等待更新</strong></span>
        </button>
      </section>

      <section className="company-explorer" id="company-explorer" aria-label="公司研究列表">
        <div className="explorer-toolbar">
          <div className="view-switch" role="tablist" aria-label="公司列表视图">
            <button
              aria-selected={view === "opportunities"}
              className={view === "opportunities" ? "is-active" : ""}
              onClick={() => switchView("opportunities")}
              role="tab"
            >
              机会池 <span>{statusCount(catalog, "covered")}</span>
            </button>
            <button
              aria-selected={view === "market"}
              className={view === "market" ? "is-active" : ""}
              onClick={() => switchView("market")}
              role="tab"
            >
              全市场 <span>{catalog.stats.active}</span>
            </button>
          </div>
          <label className="search-field">
            <span aria-hidden="true">⌕</span>
            <input
              onChange={(event) => {
                setQuery(event.target.value);
                setVisibleRows(80);
              }}
              placeholder="搜索公司、代码、行业或结论  /"
              ref={searchRef}
              type="search"
              value={query}
            />
          </label>
          <label className="select-field">
            <span>行业</span>
            <select value={industry} onChange={(event) => setIndustry(event.target.value)}>
              <option value="all">全部行业</option>
              {industries.map(([name, count]) => (
                <option key={name} value={name}>
                  {name} · {count}
                </option>
              ))}
            </select>
          </label>
          {view === "market" ? (
            <label className="select-field sort-field">
              <span>排序</span>
              <select value={marketSort} onChange={(event) => setMarketSort(event.target.value as MarketSort)}>
                <option value="updated">最近更新</option>
                <option value="status">研究状态</option>
                <option value="name">公司名称</option>
              </select>
            </label>
          ) : null}
        </div>

        {view === "market" ? (
          <div className="status-filters" aria-label="研究状态筛选">
            <button className={status === "all" ? "is-active" : ""} onClick={() => setStatus("all")}>
              全部 <span>{catalog.stats.active}</span>
            </button>
            {STATUS_ORDER.map((value) => (
              <button
                className={status === value ? `is-active status-filter-${value}` : ""}
                key={value}
                onClick={() => setStatus(value)}
                title={STATUS_META[value].description}
              >
                {STATUS_META[value].shortLabel} <span>{statusCount(catalog, value)}</span>
              </button>
            ))}
          </div>
        ) : null}

        <div className="table-caption">
          <span>
            显示 {Math.min(visibleRows, filtered.length).toLocaleString("zh-CN")} / {filtered.length.toLocaleString("zh-CN")} 家
          </span>
          {view === "opportunities" ? (
            <div className="quote-controls" aria-live="polite">
              <span className={`quote-status quote-status-${quoteRefreshing ? "loading" : quoteState}`}>
                <i aria-hidden="true" />
                {quoteRefreshing
                  ? "现价更新中"
                  : quoteState === "live"
                    ? "现价已更新"
                    : quoteState === "loading"
                      ? "现价更新中"
                      : "显示最近收盘价"}
              </span>
              {quoteUpdatedAt ? <time dateTime={quoteUpdatedAt}>行情时间 {formatQuoteTime(quoteUpdatedAt)}</time> : null}
              <button
                className="quote-refresh"
                disabled={quoteRefreshing}
                onClick={() => void refreshQuotes()}
                type="button"
              >
                {quoteRefreshing ? "刷新中" : "刷新"}
              </button>
            </div>
          ) : (
            <span>更新于 {formatDate(catalog.generatedAt, true)}</span>
          )}
        </div>

        <div className="company-table-wrap">
          <table className={`company-table company-table-${view}`}>
            <thead>
              {view === "opportunities" ? (
                <tr>
                  <th className="rank-column">顺序</th>
                  <th className="company-column">公司</th>
                  <th className="industry-column">行业</th>
                  <th className="current-price-column">现价</th>
                  <th className="value-column">合理价值</th>
                  <th className="level-column">关注价</th>
                  <th className="level-column attraction-column">高吸引力价</th>
                  <th className="summary-column">当前结论</th>
                  <th className="action-column" aria-label="操作" />
                </tr>
              ) : (
                <tr>
                  <th className="company-column">公司</th>
                  <th className="status-column">研究状态</th>
                  <th className="industry-column">行业</th>
                  <th className="updated-column">最近更新</th>
                  <th className="summary-column">当前结论</th>
                  <th className="action-column" aria-label="操作" />
                </tr>
              )}
            </thead>
            <tbody>
              {filtered.slice(0, visibleRows).map((company, index) => {
                const quote = quotes.get(company.ticker);
                const groupedLevels = groupPriceLevels(company);
                const price = effectivePrice(company, quote);
                return view === "opportunities" ? (
                  <tr key={company.symbol}>
                    <td className="rank-cell">{String(index + 1).padStart(2, "0")}</td>
                    <td className="company-cell">
                      <strong>{cleanCompanyName(company.name)}</strong>
                      <span>{company.ticker} · {company.exchange}</span>
                    </td>
                    <td className="industry-cell">{company.industry}</td>
                    <td className="current-price-cell" title={quoteSourceLabel(quote, company.lastCloseDate)}>
                      <strong>¥{formatPrice(price)}</strong>
                      {quote?.changePercent === null || quote?.changePercent === undefined ? (
                        <span>{company.lastCloseDate ? `${company.lastCloseDate} 收盘` : "待同步"}</span>
                      ) : (
                        <span className={quoteChangeClass(quote)}>
                          {quote.changePercent > 0 ? "+" : ""}{quote.changePercent.toFixed(2)}%
                        </span>
                      )}
                    </td>
                    <td className="value-cell">
                      {company.valueRange ? (
                        <strong>¥{formatPrice(company.valueRange.low)}–{formatPrice(company.valueRange.high)}</strong>
                      ) : (
                        <span className="empty-price">—</span>
                      )}
                    </td>
                    <PriceLevelCell levels={groupedLevels.attention} />
                    <PriceLevelCell levels={groupedLevels.highAttraction} />
                    <td className="summary-cell"><p>{company.summary}</p></td>
                    <td className="row-action">
                      {company.reports.length ? (
                        <a href={`/reports/${company.ticker}`} aria-label={`阅读${cleanCompanyName(company.name)}研报`}>
                          阅读
                        </a>
                      ) : (
                        <span>—</span>
                      )}
                    </td>
                  </tr>
                ) : (
                  <tr key={company.symbol}>
                    <td className="company-cell">
                      <strong>{cleanCompanyName(company.name)}</strong>
                      <span>{company.ticker} · {company.exchange}</span>
                    </td>
                    <td><StatusBadge status={company.status} /></td>
                    <td className="industry-cell">{company.industry}</td>
                    <td className="updated-cell">
                      <strong>{formatDate(company.updatedAt)}</strong>
                      <span>{company.reportDate ? `研报 ${company.reportDate}` : "无正式研报"}</span>
                    </td>
                    <td className="summary-cell"><p>{company.summary}</p></td>
                    <td className="row-action">
                      {company.reports.length ? (
                        <a href={`/reports/${company.ticker}`} aria-label={`阅读${cleanCompanyName(company.name)}研报`}>
                          阅读
                        </a>
                      ) : (
                        <span>—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!filtered.length ? (
            <div className="empty-table">
              <strong>没有符合当前条件的公司</strong>
              <span>试试清空关键词或切换状态、行业筛选。</span>
            </div>
          ) : null}
        </div>
        {visibleRows < filtered.length ? (
          <button className="load-more" onClick={() => setVisibleRows((current) => current + 100)}>
            再显示 {Math.min(100, filtered.length - visibleRows)} 家
          </button>
        ) : null}
      </section>
    </main>
  );
}

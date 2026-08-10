"use client";
/* eslint-disable @next/next/no-html-link-for-pages */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  cleanCompanyName,
  effectivePrice,
  formatDate,
  formatPrice,
  loadCatalog,
  loadQuotes,
  opportunityPriority,
  primaryPriceLevel,
  STATUS_META,
  type Catalog,
  type Company,
  type Quote,
  type ResearchStatus,
} from "../lib/research";

type ExplorerView = "opportunities" | "market";
type MarketSort = "updated" | "name" | "status";

const STATUS_ORDER: ResearchStatus[] = ["covered", "candidate", "stale", "ignore", "unseen"];

function percent(value: number | null, signed = false) {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${signed && value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}

function quoteChangeClass(quote?: Quote) {
  if (!quote?.change) return "price-flat";
  return quote.change > 0 ? "price-up" : "price-down";
}

function sourceLabel(quote?: Quote, fallbackDate?: string | null) {
  if (quote?.source === "tencent") return "腾讯行情";
  if (quote?.source === "eastmoney") return "东方财富备援";
  return fallbackDate ? `${fallbackDate} 收盘` : "行情待同步";
}

function statusCount(catalog: Catalog, status: ResearchStatus) {
  return catalog.stats.status[status] ?? 0;
}

function valuationMarker(company: Company, price: number | null) {
  if (!company.valueRange || price === null) return 50;
  const { low, high } = company.valueRange;
  const start = Math.max(0.01, low * 0.72);
  const end = high * 1.28;
  return Math.min(100, Math.max(0, ((price - start) / (end - start)) * 100));
}

function PriorityPill({ company, quote }: { company: Company; quote?: Quote }) {
  const priority = opportunityPriority(company, quote);
  const tone = priority.score >= 78 ? "hot" : priority.score >= 58 ? "warm" : "cool";
  return (
    <span className={`priority-pill ${tone}`} title={`复核优先级 ${priority.score}/100`}>
      <span>{priority.score || "—"}</span>
      {priority.label}
    </span>
  );
}

function StatusBadge({ status }: { status: ResearchStatus }) {
  return (
    <span className={`status-badge status-${status}`} title={STATUS_META[status].description}>
      {STATUS_META[status].label}
    </span>
  );
}

function TopOpportunity({ company, quote }: { company: Company; quote?: Quote }) {
  const priority = opportunityPriority(company, quote);
  const price = effectivePrice(company, quote);
  const level = primaryPriceLevel(company);
  const marker = valuationMarker(company, price);
  return (
    <article className="top-opportunity-card">
      <div className="top-card-head">
        <div>
          <div className="rank-kicker">NO. 01 · 今日优先复核</div>
          <div className="company-title-line">
            <h2>{cleanCompanyName(company.name)}</h2>
            <span>{company.ticker}</span>
          </div>
          <p className="company-industry">{company.industry}</p>
        </div>
        <PriorityPill company={company} quote={quote} />
      </div>

      <div className="quote-and-thesis">
        <div className="hero-quote">
          <span>现价</span>
          <strong>¥{formatPrice(price)}</strong>
          <span className={quoteChangeClass(quote)}>
            {quote?.changePercent === null || quote?.changePercent === undefined
              ? ""
              : `${quote.changePercent > 0 ? "+" : ""}${quote.changePercent.toFixed(2)}%`}
          </span>
          <small>{sourceLabel(quote, company.lastCloseDate)}</small>
        </div>
        <p className="top-summary">{company.summary}</p>
      </div>

      <div className="valuation-band-block">
        <div className="valuation-labels">
          <span>
            合理价值 <strong>{company.valueRange ? `¥${company.valueRange.low}—${company.valueRange.high}` : "待定"}</strong>
          </span>
          <span>
            {level?.label ?? "事件触发"} <strong>{level ? `¥${formatPrice(level.threshold)}` : `${company.eventTriggerCount} 项`}</strong>
          </span>
        </div>
        <div className="valuation-track" aria-label="现价相对合理价值区间的位置">
          <span className="fair-zone" />
          <span className="price-marker" style={{ left: `${marker}%` }}>
            <i />
          </span>
        </div>
        <div className="valuation-axis">
          <span>更有安全边际</span>
          <span>合理价值区间</span>
          <span>估值偏高</span>
        </div>
      </div>

      <div className="card-footer">
        <div className="distance-note">
          {priority.distance === null
            ? "该公司以事件触发为主"
            : priority.distance <= 0
              ? `现价已进入“${level?.label}”复核区`
              : `距“${level?.label}”还有 ${percent(priority.distance)}`}
        </div>
        {company.reportPath ? (
          <a className="primary-button" href={`/reports/${company.ticker}`}>
            阅读最新研报 <span aria-hidden="true">↗</span>
          </a>
        ) : null}
      </div>
    </article>
  );
}

function OpportunityQueue({ companies, quotes }: { companies: Company[]; quotes: Map<string, Quote> }) {
  return (
    <aside className="opportunity-queue" aria-label="下一步复核队列">
      <div className="queue-header">
        <div>
          <span className="section-eyebrow">NEXT UP</span>
          <h3>接下来值得看</h3>
        </div>
        <span>{companies.length} 家</span>
      </div>
      <div className="queue-list">
        {companies.slice(0, 5).map((company, index) => {
          const quote = quotes.get(company.ticker);
          const priority = opportunityPriority(company, quote);
          const level = primaryPriceLevel(company);
          return (
            <a className="queue-item" href={`/reports/${company.ticker}`} key={company.symbol}>
              <span className="queue-rank">{String(index + 2).padStart(2, "0")}</span>
              <span className="queue-company">
                <strong>{cleanCompanyName(company.name)}</strong>
                <small>
                  {company.ticker} · {company.industry}
                </small>
              </span>
              <span className="queue-numbers">
                <strong>¥{formatPrice(priority.price)}</strong>
                <small>
                  {level && priority.distance !== null
                    ? priority.distance <= 0
                      ? "已触发"
                      : `距线 ${percent(priority.distance)}`
                    : "事件监控"}
                </small>
              </span>
              <span className={`score-dot score-${priority.score >= 78 ? "hot" : priority.score >= 58 ? "warm" : "cool"}`}>
                {priority.score || "—"}
              </span>
            </a>
          );
        })}
      </div>
    </aside>
  );
}

export function DashboardClient() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [quotes, setQuotes] = useState<Map<string, Quote>>(new Map());
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [quoteState, setQuoteState] = useState<"loading" | "live" | "fallback">("loading");
  const [view, setView] = useState<ExplorerView>("opportunities");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ResearchStatus | "all">("all");
  const [industry, setIndustry] = useState("all");
  const [marketSort, setMarketSort] = useState<MarketSort>("updated");
  const [visibleRows, setVisibleRows] = useState(80);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    loadCatalog(controller.signal)
      .then(async (nextCatalog) => {
        setCatalog(nextCatalog);
        const coveredTickers = nextCatalog.companies
          .filter((company) => company.status === "covered")
          .map((company) => company.ticker);
        try {
          const nextQuotes = await loadQuotes(coveredTickers, controller.signal);
          setQuotes(new Map(nextQuotes.map((quote) => [quote.ticker, quote])));
          setQuoteState(nextQuotes.length ? "live" : "fallback");
        } catch {
          setQuoteState("fallback");
        }
      })
      .catch((error: Error) => {
        if (error.name !== "AbortError") setCatalogError(error.message);
      });
    return () => controller.abort();
  }, []);

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
        <section className="hero-copy">
          <span className="section-eyebrow">RESEARCH NAVIGATOR</span>
          <h1>从全市场状态里，先找到今天值得看的公司。</h1>
          <p>正在整理机会、研究状态和最新研报…</p>
        </section>
        <div className="loading-card-grid" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </main>
    );
  }

  const top = opportunities[0];
  return (
    <main className="dashboard-shell">
      <section className="dashboard-hero" aria-labelledby="dashboard-title">
        <div className="hero-copy">
          <span className="section-eyebrow">RESEARCH NAVIGATOR · {formatDate(catalog.generatedAt, true)}</span>
          <h1 id="dashboard-title">先看最接近研究边界的公司。</h1>
          <p>
            这里排序的是<strong>研报复核优先级</strong>，不是买入评级。价格、价值区间和研究新鲜度只负责告诉你先读谁。
          </p>
        </div>
        <div className="hero-status">
          <span className={`sync-light sync-${quoteState}`} />
          <div>
            <strong>{quoteState === "live" ? "现价已连接" : quoteState === "loading" ? "行情连接中" : "使用最近收盘价"}</strong>
            <span>腾讯行情主源 · 东方财富自动备援</span>
          </div>
        </div>
      </section>

      <section className="state-strip" aria-label="研究状态概览">
        <button onClick={() => switchView("opportunities")}>
          <span className="state-number">{statusCount(catalog, "covered")}</span>
          <span className="state-copy">
            <strong>持续覆盖</strong>
            <small>机会池中的有效研报</small>
          </span>
        </button>
        <button className={triggerCount ? "attention" : ""} onClick={() => switchView("opportunities")}>
          <span className="state-number">{triggerCount}</span>
          <span className="state-copy">
            <strong>进入复核区</strong>
            <small>现价已到关注线</small>
          </span>
        </button>
        <button onClick={() => showStatus("candidate")}>
          <span className="state-number">{statusCount(catalog, "candidate")}</span>
          <span className="state-copy">
            <strong>候选研究</strong>
            <small>{catalog.stats.queue.running} 运行中 · {catalog.stats.queue.queued} 排队</small>
          </span>
        </button>
        <button className={statusCount(catalog, "stale") ? "attention" : ""} onClick={() => showStatus("stale")}>
          <span className="state-number">{statusCount(catalog, "stale")}</span>
          <span className="state-copy">
            <strong>等待更新</strong>
            <small>报告失效，监控暂停</small>
          </span>
        </button>
      </section>

      {top ? (
        <section className="opportunity-stage" aria-label="最高优先级机会">
          <TopOpportunity company={top} quote={quotes.get(top.ticker)} />
          <OpportunityQueue companies={opportunities.slice(1)} quotes={quotes} />
        </section>
      ) : null}

      <details className="ranking-note">
        <summary>排序为什么把这些公司放在前面？</summary>
        <div>
          <p>
            复核优先级 = 55% 关注价距离 + 35% 合理价值区间位置 + 10% 报告新鲜度。价格进入关注区时优先级最高；没有可靠估值的事件型公司不会被硬算成低估。
          </p>
          <p>算法只安排阅读顺序，不输出仓位、买入动作或预期收益率。</p>
        </div>
      </details>

      <section className="company-explorer" id="company-explorer" aria-labelledby="explorer-title">
        <div className="explorer-heading">
          <div>
            <span className="section-eyebrow">UNIVERSE EXPLORER</span>
            <h2 id="explorer-title">从机会池切到全市场，只需要一次点击。</h2>
          </div>
          <a className="text-link" href="/reports">
            在研报库中搜索 <span aria-hidden="true">↗</span>
          </a>
        </div>

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
          <span>显示 {Math.min(visibleRows, filtered.length).toLocaleString("zh-CN")} / {filtered.length.toLocaleString("zh-CN")} 家</span>
          <span>{view === "opportunities" ? "按复核优先级排序" : "状态来自唯一事实源"}</span>
        </div>
        <div className="company-table-wrap">
          <table className="company-table">
            <thead>
              <tr>
                {view === "opportunities" ? <th className="rank-column">优先级</th> : null}
                <th>公司</th>
                <th>研究状态</th>
                <th>行业</th>
                <th className="price-column">{view === "opportunities" ? "现价 / 关注价" : "最近更新"}</th>
                <th className="summary-column">当前结论</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, visibleRows).map((company, index) => {
                const quote = quotes.get(company.ticker);
                const priority = opportunityPriority(company, quote);
                const level = primaryPriceLevel(company);
                return (
                  <tr key={company.symbol}>
                    {view === "opportunities" ? (
                      <td className="rank-cell">
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <i style={{ width: `${priority.score}%` }} />
                      </td>
                    ) : null}
                    <td className="company-cell">
                      <strong>{cleanCompanyName(company.name)}</strong>
                      <span>
                        {company.ticker} · {company.exchange}
                      </span>
                    </td>
                    <td>
                      <StatusBadge status={company.status} />
                    </td>
                    <td className="industry-cell">{company.industry}</td>
                    <td className="price-cell">
                      {view === "opportunities" ? (
                        <>
                          <strong>¥{formatPrice(priority.price)}</strong>
                          <span>{level ? `${level.label} ¥${formatPrice(level.threshold)}` : `${company.eventTriggerCount} 项事件`}</span>
                        </>
                      ) : (
                        <>
                          <strong>{formatDate(company.updatedAt)}</strong>
                          <span>{company.reportDate ? `研报 ${company.reportDate}` : "无正式研报"}</span>
                        </>
                      )}
                    </td>
                    <td className="summary-cell">
                      <p>{company.summary}</p>
                    </td>
                    <td className="row-action">
                      {company.reports.length ? (
                        <a href={`/reports/${company.ticker}`} aria-label={`阅读${cleanCompanyName(company.name)}研报`}>
                          ↗
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

      <footer className="dashboard-footer">
        <span>Trading OS · 研究状态与正式报告只读投影</span>
        <span>行情仅用于复核排序，不构成投资建议</span>
      </footer>
    </main>
  );
}

"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cleanCompanyName, formatDate, formatIrr, formatPrice, loadCatalog, loadQuotes,
  pricePosition, returnIrr, STATUS_META, type Catalog, type Company, type Quote } from "../lib/research";
import { currentResults, scopedCompanies, progressCounts, DISPLAY_LABELS } from "../lib/display-policy.mjs";
import { compareResearchMapRows } from "../lib/opportunity-sort.mjs";
import "../standards.css";
import { ScreeningClient } from "./screening-client";
import { MARKET_LABELS, currencyLabel } from "../lib/research";

type View = "current" | "progress" | "market" | "pool";
type Scope = "quality_pool" | "all_standard";
type Sort = "ticker" | "updated" | "irr" | "value";
const QUOTE_REFRESH_INTERVAL_MS = 5 * 60 * 1000;
function isChinaMarketOpen(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Shanghai", weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(date);
  const part = (name: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === name)?.value ?? "";
  const minutes = Number(part("hour")) * 60 + Number(part("minute"));
  return !["Sat", "Sun"].includes(part("weekday")) && ((minutes >= 570 && minutes <= 690) || (minutes >= 780 && minutes <= 900));
}
function returnModelTitle(company: Company) {
  return [company.returnModel?.model_as_of, company.returnModelNote, company.returnModelDisplayIssue?.reason].filter(Boolean).join("\n");
}
export function DashboardClient() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("current");
  const [market, setMarket] = useState("all");
  const [scope, setScope] = useState<Scope>("quality_pool");
  const [query, setQuery] = useState("");
  const [industry, setIndustry] = useState("all");
  const [progress, setProgress] = useState("all");
  const [sort, setSort] = useState<Sort>("ticker");
  const [limit, setLimit] = useState(80);
  const [quotes, setQuotes] = useState<Map<string, Quote>>(new Map());
  const [quoteRefreshing, setQuoteRefreshing] = useState(false);
  const [quoteAt, setQuoteAt] = useState<string | null>(null);
  const search = useRef<HTMLInputElement>(null);
  const methodology = useRef<HTMLDialogElement>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const quoteGeneration = useRef(0);
  const lastRequest = useRef(0);
  useEffect(() => {
    const controller = new AbortController();
    loadCatalog(controller.signal).then((data) => {
      setCatalog(data);
      const params = new URLSearchParams(window.location.search);
      const requestedMarket = ({ "cn-a": "CN", hk: "HK", us: "US" } as Record<string,string>)[params.get("market") ?? ""] ?? params.get("market");
      if (requestedMarket && requestedMarket in MARKET_LABELS) setMarket(requestedMarket);
      if (["pool", "current", "progress", "market"].includes(params.get("view") ?? "")) setView(params.get("view") as View);
    }).catch((e: Error) => { if (e.name !== "AbortError") setError(e.message); });
    return () => controller.abort();
  }, []);
  const marketCompanies = useMemo(() => (catalog?.companies ?? []).filter((c) => market === "all" || c.market === market), [catalog, market]);
  const accepted: Company[] = useMemo(() => currentResults(marketCompanies, scope), [marketCompanies, scope]);
  const scoped: Company[] = useMemo(() => scopedCompanies(marketCompanies, scope), [marketCompanies, scope]);
  const counts = useMemo(() => progressCounts(marketCompanies, scope), [marketCompanies, scope]);
  const refreshQuotes = useCallback(async (signal?: AbortSignal) => {
    if (!catalog || view !== "current") return;
    const generation = ++quoteGeneration.current; lastRequest.current = Date.now(); setQuoteRefreshing(true);
    const clearQuoteSnapshot = () => { setQuotes(new Map()); setQuoteAt(null); };
    try {
      // Exactly the same eligible set as the current table; never fetch the old covered universe.
      const rows = await loadQuotes(accepted.map((company) => company.ticker), signal);
      if (signal?.aborted || generation !== quoteGeneration.current) return;
      if (rows.length) {
        setQuotes(new Map(rows.map((quote) => [quote.ticker, quote])));
        setQuoteAt(rows.map((quote) => quote.quoteAt).filter((date): date is string => Boolean(date)).sort().at(-1) ?? null);
      } else clearQuoteSnapshot();
    } catch (e) { if (generation === quoteGeneration.current && !(e instanceof Error && e.name === "AbortError")) clearQuoteSnapshot(); }
    finally { if (generation === quoteGeneration.current) setQuoteRefreshing(false); }
  }, [catalog, view, accepted]);
  useEffect(() => {
    if (!catalog || view !== "current") return;
    const controller = new AbortController();
    const initial = window.setTimeout(() => void refreshQuotes(controller.signal), 0);
    const refreshIfDue = () => {
      if (document.visibilityState === "visible" && (market !== "CN" || isChinaMarketOpen())
        && Date.now() - lastRequest.current >= QUOTE_REFRESH_INTERVAL_MS) void refreshQuotes(controller.signal);
    };
    const interval = window.setInterval(refreshIfDue, 60_000);
    document.addEventListener("visibilitychange", refreshIfDue);
    return () => { controller.abort(); window.clearTimeout(initial); window.clearInterval(interval); document.removeEventListener("visibilitychange", refreshIfDue); };
  }, [catalog, view, refreshQuotes, market]);
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => { if (event.key === "/" && document.activeElement?.tagName !== "INPUT") { event.preventDefault(); search.current?.focus(); } };
    window.addEventListener("keydown", keydown); return () => window.removeEventListener("keydown", keydown);
  }, []);
  const candidates: Company[] = view === "current" ? accepted : view === "progress" ? scoped : marketCompanies;
  const industries = [...new Set(candidates.map((company) => company.industry))].sort((a, b) => a.localeCompare(b, "zh-CN"));
  const filtered = candidates.filter((company) => (industry === "all" || company.industry === industry)
    && (progress === "all" || view !== "progress" || company.display.state === progress)
    && [company.name, company.ticker, company.industry, view === "current" ? company.summary : ""]
      .join(" ").toLowerCase().includes(query.trim().toLowerCase()));
  const ordered = filtered.map((company) => ({ company, ticker: company.ticker, updatedAt: company.updatedAt,
    midpointIrr: view === "current" ? returnIrr(company, quotes.get(company.ticker), 5)?.midpoint ?? null : null,
    lowRatio: view === "current" ? pricePosition(company, quotes.get(company.ticker)).lowRatio : null }))
    .sort((a, b) => compareResearchMapRows(a, b, view === "current" ? sort : "ticker")).map(({ company }) => company);
  const compared = view === "current" ? filtered.filter((company) => pricePosition(company, quotes.get(company.ticker)).lowRatio !== null) : [];
  function changeView(next: View) {
    setView(next); setIndustry("all"); setProgress("all"); setLimit(80);
    const params = new URLSearchParams({ view: next });
    if (market !== "all") params.set("market", market);
    window.history.replaceState(null, "", `/?${params}`);
  }
  if (error) return <main className="standards-workspace"><h1>研究决策台</h1><p role="alert">{error}</p></main>;
  if (!catalog) return <main className="standards-workspace"><h1>研究决策台</h1><p>正在读取现行标准及验收结果…</p></main>;
  const exportName = (scope === "quality_pool" ? "current-research" : "all-current-research") + (market === "all" ? "" : `-${market}`);
  return <main className="standards-workspace research-console">
    <h1 className="sr-only">研究决策台</h1>
    <div className="research-viewbar"><div className="standards-tabs" role="tablist" aria-label="研究视图">
      {([["pool", "公司池"], ["progress", "跟踪进度"], ["current", "最新周期模型"], ["market", "全部档案"]] as const).map(([id, label], index, tabs) =>
        <button key={id} id={`view-${id}`} role="tab" aria-selected={view === id} aria-controls="company-research-panel" tabIndex={view === id ? 0 : -1}
          onClick={() => changeView(id)} onKeyDown={(event) => {
            const target = event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length
              : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : null;
            if (target !== null) { event.preventDefault(); changeView(tabs[target][0]); document.getElementById(`view-${tabs[target][0]}`)?.focus(); }
          }}>{label}</button>)}</div></div>
    <section id="company-research-panel" role="tabpanel" aria-labelledby={`view-${view}`}>
      {view !== "pool" && <div className="research-toolbar">
        <input ref={search} type="search" aria-label="搜索公司" placeholder="搜索公司、代码" value={query} onChange={(event) => { setQuery(event.target.value); setLimit(80); }} />
        <select aria-label="研究市场" value={market} onChange={(e) => { setMarket(e.target.value); setIndustry("all"); setLimit(80); }}>{Object.entries(MARKET_LABELS).map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select>
        <button className="research-filter-toggle" aria-expanded={filtersOpen} aria-controls="research-filters" onClick={() => setFiltersOpen(!filtersOpen)}>筛选{industry !== "all" || progress !== "all" || scope !== "quality_pool" || sort !== "ticker" ? " ·" : ""}</button>
        <div id="research-filters" className={`research-filters${filtersOpen ? " is-open" : ""}`}>
          {view !== "market" && <select aria-label="研究范围" value={scope} onChange={(event) => { setScope(event.target.value as Scope); setIndustry("all"); setLimit(80); }}>
            <option value="quality_pool">重点跟踪池</option><option value="all_standard">全部研究</option></select>}
          <select aria-label="行业筛选" value={industry} onChange={(event) => setIndustry(event.target.value)}><option value="all">全部行业</option>{industries.map((name) => <option key={name}>{name}</option>)}</select>
          {view === "current" && <select aria-label="周期模型排序" value={sort} onChange={(event) => setSort(event.target.value as Sort)}><option value="ticker">代码顺序</option><option value="updated">最近研究</option><option value="irr">模型年化回报</option><option value="value">相对价值下沿</option></select>}
          {view === "progress" && <select aria-label="周期进度筛选" value={progress} onChange={(event) => setProgress(event.target.value)}><option value="all">全部进度</option>{Object.entries(DISPLAY_LABELS).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>}
        </div>
      </div>}
      {view === "pool" ? <ScreeningClient embedded initialMarket={({ CN: "cn-a", HK: "hk", US: "us" } as Record<string,string>)[market] ?? "all"} onMarketChange={(value) => setMarket(({ "cn-a": "CN", hk: "HK", us: "US" } as Record<string,string>)[value] ?? "all")} /> : <>
      {view === "progress" && <div className="research-progress-summary" aria-label="选定范围研究进度">
        <span>跟踪 <strong>{counts.total}</strong></span><span>已研究 <strong>{counts.completed}</strong></span><span>待研究 <strong>{counts.pending}</strong></span>
        {counts.unpriced > 0 && <span>暂无法估值 <strong>{counts.unpriced}</strong></span>}{counts.review > 0 && <span>需复核 <strong>{counts.review}</strong></span>}
      </div>}
      <div className="standards-caption"><span>显示 {Math.min(limit, ordered.length)} / {ordered.length} 家</span>
        <div className="research-list-actions">
          {view === "current" && <><button disabled={quoteRefreshing} onClick={() => void refreshQuotes()}>{quoteRefreshing ? "刷新中" : "刷新"}</button>
            <details className="research-data-menu"><summary>导出</summary><div><p>行情时间 {formatDate(quoteAt, true)}</p><p>可比较行情 {compared.length} 家</p><a href={`/data/${exportName}.json`} download>本范围 JSON</a><a href={`/data/${exportName}.csv`} download>本范围 CSV</a></div></details></>}
          <button onClick={() => methodology.current?.showModal()}>研究口径</button>
        </div>
      </div>
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- Keyboard users need a focusable region to scroll the wide data table. */}
      <div key={view} className="standards-table-scroll" role="region" aria-label="公司研究数据" tabIndex={0}><table className="standards-table"><thead><tr><th>公司</th><th className="research-secondary-column">行业</th>
        {view === "current" ? <><th className="research-secondary-column">现价</th><th>合理价值</th><th>5年基准情景年化回报</th><th>相对下沿</th><th>相对中枢</th><th>当前结论</th><th>资料截止</th></>
          : <><th>周期进度</th><th>最近结论</th><th>说明</th><th>报告周期</th></>}<th>阅读</th></tr></thead><tbody>
        {ordered.slice(0, limit).map((company) => {
          const quote = quotes.get(company.ticker); const position = pricePosition(company, quote); const irr = returnIrr(company, quote, 5);
          return <tr key={company.symbol} data-symbol={company.symbol}><td>{company.reports.length ? <a className="research-company-link" href={`/reports/${company.ticker}`}><strong>{cleanCompanyName(company.name)}</strong></a> : <strong>{cleanCompanyName(company.name)}</strong>}<small className="research-company-sector">{company.industry}</small><small>{company.ticker}{company.inQualityPool ? ` · ${company.qualityTier === "core_moat" ? "A" : "B"}` : ""}</small></td><td className="research-secondary-column">{company.industry}</td>
            {view === "current" ? <><td className="research-secondary-column">{currencyLabel(company.quoteCurrency)}{formatPrice(position.price)}</td><td>{company.valueRange ? <strong>{currencyLabel(company.valueRange.currency)}{formatPrice(company.valueRange.low)}–{formatPrice(company.valueRange.high)}</strong> : <span>暂无法估值</span>}<small className="research-mobile-price">现价 {position.price == null ? "—" : `${currencyLabel(company.quoteCurrency)}${formatPrice(position.price)}`}</small></td>
              <td title={returnModelTitle(company)}><strong>{formatIrr(irr?.midpoint)}</strong><small>{irr?.midpoint != null ? `低 ${formatIrr(irr.low)} · 高 ${formatIrr(irr.high)}` : company.returnModelDisplayIssue ? "现金路径待更新" : company.returnModel ? "行情暂缺或模型暂不可用" : company.returnModelNote ? "暂无法可靠建模" : "待后续完整研究补充"}</small></td>
              <td>{position.lowRatio == null ? "—" : `${position.lowRatio.toFixed(2)}×`}<small>{position.label}</small></td><td>{position.midpointRatio == null ? "—" : `${position.midpointRatio.toFixed(2)}×`}</td>
              <td className="summary-cell"><p>{company.summary}</p>{company.status === "ignore" && <small>研究后暂不持续覆盖</small>}</td><td>{formatDate(company.informationCutoff)}<small>验收 {formatDate(company.acceptedAt)}</small></td></>
              : <><td>{company.pendingReportPeriod ? `${company.pendingReportPeriod} · 待研究` : DISPLAY_LABELS[company.display.state]}</td><td>{company.status === "unseen" ? "尚无公司研究" : STATUS_META[company.status].label}</td><td className="summary-cell">{company.pendingReportPeriod ? `${company.pendingTaskKind === "manual_rewrite" ? "人工重写" : "财报周期"}任务已排队` : company.hasResearchState ? company.display.reason : "等待已披露财报的首次完整研究。"}</td><td>{company.latestReportPeriod ? `${company.latestReportPeriod}${company.reportUpdatedAt ? ` · ${formatDate(company.reportUpdatedAt)}` : ""}` : "尚无报告"}</td></>}
            <td>{company.reports.length ? <a href={`/reports/${company.ticker}`}>阅读最新</a> : "—"}</td></tr>;
        })}</tbody></table></div>
      {!ordered.length && <div className="standards-empty"><strong>{view === "current" ? "暂无符合条件的现行研究" : "没有符合条件的公司"}</strong><p>调整筛选条件，或到研报库阅读已有周期。</p></div>}
      {ordered.length > limit && <button className="load-more" onClick={() => setLimit((value) => value + 100)}>继续显示</button>}</>}
    </section>
    <dialog ref={methodology} className="research-method-dialog" aria-labelledby="research-method-title">
      <div className="research-method-body"><header><h2 id="research-method-title">研究口径</h2><button aria-label="关闭研究口径" onClick={() => methodology.current?.close()}>关闭</button></header>
        <h3>{catalog.standard.label}</h3><p>{catalog.standard.value_label}。</p>
        <p>最新周期模型展示按现行兼容标准完成的研究。资料截止与研究完成日期分别标明；其他周期可在研报库阅读。</p>
        <h3>价值与回报</h3><p>五年基准情景年化回报由研究中的现金分配、终值与现价计算，随价格和假设变化。比较时请同时阅读各公司的资料日期、关键假设及风险。</p>
        <p>研究判断与证券交易币种、每股或 ADS 单位对应。市场之间不直接换算或合并每股数值。</p>
        <details><summary>标准与兼容版本</summary><p>发布于 {formatDate(catalog.standard.published_at)}。{catalog.standard.compatibility_note}</p><p>兼容版本：{catalog.standard.compatible_with.join("、")}。{catalog.standard.change_note}</p></details>
      </div>
    </dialog>
  </main>;
}

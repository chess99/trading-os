"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cleanCompanyName, formatDate, formatIrr, formatPrice, loadCatalog, loadQuotes,
  pricePosition, returnIrr, STATUS_META, EQUITY_MARKET_LABELS, currencyLabel,
  type Catalog, type Company, type Quote } from "../lib/research";
import { currentResults, scopedCompanies, progressCounts, DISPLAY_LABELS } from "../lib/display-policy.mjs";
import { compareResearchMapRows } from "../lib/opportunity-sort.mjs";
import { CYCLE_STAGE_LABELS, MACRO_ALIGN_LABELS, QUALITY_LABELS, TRACK_LABELS,
  matchesDecisionLens, scenarioAsymmetry, southboundAfterTaxIrr } from "../lib/decision-metrics.mjs";
import "../standards.css";
import { ScreeningClient } from "./screening-client";

type View = "current" | "progress" | "market" | "pool";
type Scope = "quality_pool" | "all_standard";
type Sort = "ticker" | "updated" | "irr" | "value" | "odds" | "cycle";
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
  const [track, setTrack] = useState("all");
  const [cycle, setCycle] = useState("all");
  const [macroAlign, setMacroAlign] = useState("all");
  const [lens, setLens] = useState("all");
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
      const requestedMarket = ({ "cn-a": "CN", hk: "HK" } as Record<string,string>)[params.get("market") ?? ""] ?? params.get("market");
      if (requestedMarket && requestedMarket in EQUITY_MARKET_LABELS) setMarket(requestedMarket);
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
  const filtered = candidates.filter((company) => {
    const quote = quotes.get(company.ticker);
    if (industry !== "all" && company.industry !== industry) return false;
    if (progress !== "all" && view === "progress" && company.display.state !== progress) return false;
    if (view === "current") {
      if (track !== "all" && (company.track ?? "compounder") !== track) return false;
      if (cycle !== "all" && company.industryState?.cycleStage !== cycle) return false;
      if (macroAlign !== "all" && company.industryState?.macroAlignment !== macroAlign) return false;
      if (!matchesDecisionLens(company, quote, lens)) return false;
    }
    return [company.name, company.ticker, company.industry, view === "current" ? company.summary : "",
      ...(view === "current" ? (company.decisionProfile?.exposure_tags ?? []) : [])]
      .join(" ").toLowerCase().includes(query.trim().toLowerCase());
  });
  const ordered = filtered.map((company) => {
    const quote = quotes.get(company.ticker);
    const asym = view === "current" ? scenarioAsymmetry(company, quote) : null;
    return {
      company,
      ticker: company.ticker,
      updatedAt: company.updatedAt,
      midpointIrr: view === "current" ? returnIrr(company, quote, 5)?.midpoint ?? null : null,
      lowRatio: view === "current" ? pricePosition(company, quote).lowRatio : null,
      oddsRatio: asym?.oddsRatio ?? null,
      cycleStage: company.industryState?.cycleStage ?? null,
    };
  }).sort((a, b) => compareResearchMapRows(a, b, view === "current" ? sort : "ticker")).map(({ company }) => company);
  const compared = view === "current" ? filtered.filter((company) => pricePosition(company, quotes.get(company.ticker)).lowRatio !== null) : [];
  function changeView(next: View) {
    setView(next); setIndustry("all"); setProgress("all"); setTrack("all"); setCycle("all"); setMacroAlign("all"); setLens("all"); setLimit(80);
    const params = new URLSearchParams({ view: next });
    if (market !== "all") params.set("market", market);
    window.history.replaceState(null, "", `/?${params}`);
  }
  const hasActiveFilters = industry !== "all" || progress !== "all" || scope !== "quality_pool" || sort !== "ticker"
    || track !== "all" || cycle !== "all" || macroAlign !== "all" || lens !== "all";
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
        <input ref={search} type="search" aria-label="搜索公司" placeholder="搜索公司、代码或标签" value={query} onChange={(event) => { setQuery(event.target.value); setLimit(80); }} />
        <select aria-label="研究市场" value={market} onChange={(e) => { setMarket(e.target.value); setIndustry("all"); setLimit(80); }}>{Object.entries(EQUITY_MARKET_LABELS).map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select>
        <button className="research-filter-toggle" aria-expanded={filtersOpen} aria-controls="research-filters" onClick={() => setFiltersOpen(!filtersOpen)}>筛选{hasActiveFilters ? " ·" : ""}</button>
        <div id="research-filters" className={`research-filters${filtersOpen ? " is-open" : ""}`}>
          {view !== "market" && <select aria-label="研究范围" value={scope} onChange={(event) => { setScope(event.target.value as Scope); setIndustry("all"); setLimit(80); }}>
            <option value="quality_pool">重点跟踪池</option><option value="all_standard">全部研究</option></select>}
          <select aria-label="行业筛选" value={industry} onChange={(event) => setIndustry(event.target.value)}><option value="all">全部行业</option>{industries.map((name) => <option key={name}>{name}</option>)}</select>
          {view === "current" && <>
            <select aria-label="决策视角" value={lens} onChange={(event) => setLens(event.target.value)}>
              <option value="all">全部视角</option>
              <option value="core_defense">核心防御</option>
              <option value="inflection_odds">产业拐点</option>
              <option value="ah_southbound">港股通/A-H</option>
            </select>
            <select aria-label="筛选轨道" value={track} onChange={(event) => setTrack(event.target.value)}>
              <option value="all">全部轨道</option>
              {Object.entries(TRACK_LABELS).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </select>
            <select aria-label="行业周期" value={cycle} onChange={(event) => setCycle(event.target.value)}>
              <option value="all">全部周期</option>
              {Object.entries(CYCLE_STAGE_LABELS).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </select>
            <select aria-label="宏观顺逆风" value={macroAlign} onChange={(event) => setMacroAlign(event.target.value)}>
              <option value="all">全部顺逆风</option>
              {Object.entries(MACRO_ALIGN_LABELS).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </select>
            <select aria-label="周期模型排序" value={sort} onChange={(event) => setSort(event.target.value as Sort)}>
              <option value="ticker">代码顺序</option><option value="updated">最近研究</option>
              <option value="irr">模型年化回报</option><option value="odds">赔率不对称</option>
              <option value="value">相对价值下沿</option><option value="cycle">行业周期</option>
            </select>
          </>}
          {view === "progress" && <select aria-label="周期进度筛选" value={progress} onChange={(event) => setProgress(event.target.value)}><option value="all">全部进度</option>{Object.entries(DISPLAY_LABELS).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>}
        </div>
      </div>}
      {view === "current" && (catalog.environment?.macroRegime || catalog.environment?.qdiiCatalog) && <details className="decision-context-bar">
        <summary>宏观与宽基 · {catalog.environment?.macroRegime?.regimeSummary ?? "跨市场环境与指数基准"}（指数 {catalog.environment?.marketBenchmarks?.benchmarks?.length ?? 0} · 美股宽基 QDII {catalog.environment?.qdiiCatalog?.etfs?.length ?? 0}）</summary>
        <div className="decision-context-body">
          {catalog.environment?.macroRegime?.factors && <section className="decision-context-section">
            <h3>跨市场宏观因子 · {catalog.environment.macroRegime.asOf}</h3>
            <div className="decision-context-grid">{catalog.environment.macroRegime.factors.map((factor) => <div key={factor.id} className="decision-context-card">
              <strong>{factor.label}</strong><span>{factor.reading}</span><small>{factor.implication}</small>
            </div>)}</div>
          </section>}
          {catalog.environment?.marketBenchmarks?.benchmarks && <section className="decision-context-section">
            <h3>指数估值与股债利差 · {catalog.environment.marketBenchmarks.asOf}</h3>
            <div className="decision-context-grid">{catalog.environment.marketBenchmarks.benchmarks.map((bm) => <div key={bm.id} className="decision-context-card">
              <strong>{bm.name} ({bm.market})</strong>
              <span>{bm.pe != null ? `PE ${bm.pe.toFixed(1)}×` : "待补序列"}{bm.erpPct != null ? ` · ERP ${bm.erpPct >= 0 ? "+" : ""}${bm.erpPct.toFixed(2)}%` : ""}{bm.cape != null ? ` · CAPE ${bm.cape.toFixed(1)}` : ""}</span>
              <small>{bm.note}</small>
            </div>)}</div>
          </section>}
          {catalog.environment?.qdiiCatalog && <section className="decision-context-section">
            <h3>国内可投美股宽基 QDII ETF 名录（实盘前请核查场内实时溢价率与限购）</h3>
            <div className="decision-qdii-list">{catalog.environment.qdiiCatalog.etfs.map((etf) => <div key={etf.symbol} className="decision-qdii-item">
              <code>{etf.symbol}</code><span>{etf.name}</span><small>{etf.trackedIndex === "ndx100" ? "纳指100" : "标普500"}</small>
            </div>)}</div>
          </section>}
          <div className="decision-context-links">
            <a href="/macro">完整宏观与宽基报告 →</a>
            <a href="/data/decision-index.json" download>下载 AI 决策索引 (JSON) ↓</a>
            <a href="/data/global-benchmarks.json" download>全球 {catalog.environment?.globalBenchmarksCount ?? 25} 家龙头参照 ↓</a>
          </div>
        </div>
      </details>}
      {view === "pool" ? <ScreeningClient embedded initialMarket={({ CN: "cn-a", HK: "hk" } as Record<string,string>)[market] ?? "all"} onMarketChange={(value) => setMarket(({ "cn-a": "CN", hk: "HK" } as Record<string,string>)[value] ?? "all")} /> : <>
      {view === "progress" && <div className="research-progress-summary" aria-label="选定范围研究进度">
        <span>跟踪 <strong>{counts.total}</strong></span><span>已研究 <strong>{counts.completed}</strong></span><span>待研究 <strong>{counts.pending}</strong></span>
        {counts.unpriced > 0 && <span>暂无法估值 <strong>{counts.unpriced}</strong></span>}{counts.review > 0 && <span>需复核 <strong>{counts.review}</strong></span>}
      </div>}
      <div className="standards-caption"><span>显示 {Math.min(limit, ordered.length)} / {ordered.length} 家</span>
        <div className="research-list-actions">
          {view === "current" && <><button disabled={quoteRefreshing} onClick={() => void refreshQuotes()}>{quoteRefreshing ? "刷新中" : "刷新"}</button>
            <details className="research-data-menu"><summary>导出</summary><div><p>行情时间 {formatDate(quoteAt, true)}</p><p>可比较行情 {compared.length} 家</p><a href={`/data/${exportName}.json`} download>本范围 JSON</a><a href={`/data/${exportName}.csv`} download>本范围 CSV</a><a href="/data/decision-index.json" download>AI 决策索引 JSON</a><a href="/data/global-benchmarks.json" download>全球龙头参照 JSON</a></div></details></>}
          <button onClick={() => methodology.current?.showModal()}>研究口径</button>
        </div>
      </div>
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- Keyboard users need a focusable region to scroll the wide data table. */}
      <div key={view} className="standards-table-scroll" role="region" aria-label="公司研究数据" tabIndex={0}><table className="standards-table"><thead><tr><th>公司</th><th className="research-secondary-column">行业</th>
        {view === "current" ? <><th className="research-secondary-column">现价</th><th>合理价值</th><th>5年基准情景年化回报</th><th>相对下沿</th><th>相对中枢</th><th className="research-secondary-column">质地与赔率</th><th>当前结论</th><th>资料截止</th></>
          : <><th>周期进度</th><th>最近结论</th><th>说明</th><th>报告周期</th></>}<th>阅读</th></tr></thead><tbody>
        {ordered.slice(0, limit).map((company) => {
          const quote = quotes.get(company.ticker); const position = pricePosition(company, quote); const irr = returnIrr(company, quote, 5);
          const afterTax = southboundAfterTaxIrr(company, quote, 5);
          const asym = scenarioAsymmetry(company, quote);
          return <tr key={company.symbol} data-symbol={company.symbol}><td>{company.reports.length ? <a className="research-company-link" href={`/reports/${company.ticker}`}><strong>{cleanCompanyName(company.name)}</strong></a> : <strong>{cleanCompanyName(company.name)}</strong>}<small className="research-company-sector">{company.industry}{company.industryState ? ` · ${CYCLE_STAGE_LABELS[company.industryState.cycleStage]}` : ""}</small><small>{company.ticker}{company.inQualityPool ? ` · ${company.qualityTier === "core_moat" ? "A" : "B"}` : ""}{company.track === "inflection_growth" ? " · 拐点" : ""}{company.ahBridge?.pairSymbol ? ` · A/H` : ""}{company.ahBridge?.southboundUnavailableOn && <span title={`沪深交易所名单核对日 ${company.ahBridge.southboundUnavailableOn}`}> · 港股通不可买</span>}</small></td><td className="research-secondary-column">{company.industry}{company.industryState && <small className={`decision-pill align-${company.industryState.macroAlignment}`}>{CYCLE_STAGE_LABELS[company.industryState.cycleStage]} · {MACRO_ALIGN_LABELS[company.industryState.macroAlignment]}{company.industryState.inflectionCandidate ? " · 拐点" : ""}</small>}</td>
            {view === "current" ? <><td className="research-secondary-column">{currencyLabel(company.quoteCurrency)}{formatPrice(position.price)}</td><td>{company.valueRange ? <strong>{currencyLabel(company.valueRange.currency)}{formatPrice(company.valueRange.low)}–{formatPrice(company.valueRange.high)}</strong> : <span>暂无法估值</span>}<small className="research-mobile-price">现价 {position.price == null ? "—" : `${currencyLabel(company.quoteCurrency)}${formatPrice(position.price)}`}</small></td>
              <td title={returnModelTitle(company)}><strong>{formatIrr(irr?.midpoint)}</strong><small>{irr?.midpoint != null ? `低 ${formatIrr(irr.low)} · 高 ${formatIrr(irr.high)}` : company.returnModelDisplayIssue ? "现金路径待更新" : company.returnModel ? "行情暂缺或模型暂不可用" : company.returnModelNote ? "暂无法可靠建模" : "待后续完整研究补充"}</small>{afterTax?.irr?.midpoint != null && <small className="decision-aftertax-note">港股通税后({Math.round(afterTax.taxRate * 100)}%) ≈ {formatIrr(afterTax.irr.midpoint)}</small>}</td>
              <td>{position.lowRatio == null ? "—" : `${position.lowRatio.toFixed(2)}×`}<small>{position.label}</small></td><td>{position.midpointRatio == null ? "—" : `${position.midpointRatio.toFixed(2)}×`}</td>
              <td className="research-secondary-column">{asym ? <><strong>{asym.downsideCovered ? "周期底已覆盖" : `赔率 ${asym.oddsRatio.toFixed(1)}×`}</strong><small>乐观 {asym.bullUpside >= 0 ? "+" : ""}{(asym.bullUpside * 100).toFixed(0)}% · 周期底 {asym.cyclicalDownside >= 0 ? "+" : ""}{(asym.cyclicalDownside * 100).toFixed(0)}%</small></> : company.decisionProfile ? <><strong>{QUALITY_LABELS[company.decisionProfile.business_quality]}</strong><small>{TRACK_LABELS[company.decisionProfile.track]} · 四情景已建锚</small></> : <><span>{TRACK_LABELS[company.track ?? "compounder"]}</span><small>四情景待下期补全</small></>}</td>
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
        <p>活跃研究覆盖 A 股、港股通及单列的港股独立研究标的；美股通过国内可投纳指 100 / 标普 500 宽基 QDII ETF 与 25 家全球产业龙头参照衔接。</p>
        <h3>慢变量底座与实时合成</h3><p>公司研报固定商业判断、四情景每股锚点（<code>scenarios</code>）与基准五年模型；实时现价、四情景不对称赔率与港股通红利税后 IRR（按证券适用口径扣减股息，终值按港股通资本利得税规则处理）仅在展示层实时合成，不写回仓库。</p>
        <p>双轨筛选并行维护复利质量（<code>compounder</code>）与产业拐点（<code>inflection_growth</code>）；AI 决策可直接消费导出的 <code>decision-index.json</code>。</p>
        <details><summary>标准与兼容版本</summary><p>发布于 {formatDate(catalog.standard.published_at)}。{catalog.standard.compatibility_note}</p><p>兼容版本：{catalog.standard.compatible_with.join("、")}。{catalog.standard.change_note}</p></details>
      </div>
    </dialog>
  </main>;
}

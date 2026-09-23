"use client";
/* eslint-disable @next/next/no-html-link-for-pages */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cleanCompanyName, formatDate, formatIrr, formatPrice, loadCatalog, loadQuotes,
  pricePosition, returnIrr, STATUS_META, type Catalog, type Company, type Quote } from "../lib/research";
import { currentResults, scopedCompanies, progressCounts, DISPLAY_LABELS } from "../lib/display-policy.mjs";
import { compareResearchMapRows } from "../lib/opportunity-sort.mjs";
import "../standards.css";

type View = "current" | "progress" | "market";
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
  const quoteGeneration = useRef(0);
  const lastRequest = useRef(0);
  useEffect(() => {
    const controller = new AbortController();
    loadCatalog(controller.signal).then(setCatalog).catch((e: Error) => { if (e.name !== "AbortError") setError(e.message); });
    return () => controller.abort();
  }, []);
  const accepted: Company[] = useMemo(() => currentResults(catalog?.companies ?? [], scope), [catalog, scope]);
  const scoped: Company[] = useMemo(() => scopedCompanies(catalog?.companies ?? [], scope), [catalog, scope]);
  const counts = useMemo(() => progressCounts(catalog?.companies ?? [], scope), [catalog, scope]);
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
      if (document.visibilityState === "visible" && isChinaMarketOpen()
        && Date.now() - lastRequest.current >= QUOTE_REFRESH_INTERVAL_MS) void refreshQuotes(controller.signal);
    };
    const interval = window.setInterval(refreshIfDue, 60_000);
    document.addEventListener("visibilitychange", refreshIfDue);
    return () => { controller.abort(); window.clearTimeout(initial); window.clearInterval(interval); document.removeEventListener("visibilitychange", refreshIfDue); };
  }, [catalog, view, refreshQuotes]);
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => { if (event.key === "/" && document.activeElement?.tagName !== "INPUT") { event.preventDefault(); search.current?.focus(); } };
    window.addEventListener("keydown", keydown); return () => window.removeEventListener("keydown", keydown);
  }, []);
  const candidates: Company[] = view === "current" ? accepted : view === "progress" ? scoped : catalog?.companies ?? [];
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
  const below = compared.filter((company) => (pricePosition(company, quotes.get(company.ticker)).lowRatio ?? Infinity) < 1).length;
  function changeView(next: View) { setView(next); setIndustry("all"); setProgress("all"); setLimit(80); }
  if (error) return <main className="standards-workspace"><h1>研究决策台</h1><p role="alert">{error}</p></main>;
  if (!catalog) return <main className="standards-workspace"><h1>研究决策台</h1><p>正在读取现行标准及验收结果…</p></main>;
  const exportName = scope === "quality_pool" ? "current-research" : "all-current-research";
  return <main className="standards-workspace">
    <header className="standards-heading"><div><span className="section-eyebrow">CURRENT RESEARCH</span><h1>当前研究</h1>
      <p>少而清楚：仅展示现行兼容标准下已验收、仍有效的结果。旧估值留在历史研报，不填补新版空缺。</p></div>
      <a className="standards-link" href="/reports?view=history">查看历史研报 ↗</a></header>
    <details className="standards-banner"><summary>现行标准：{catalog.standard.label} · {catalog.standard.value_label}</summary>
      <p>发布于 {formatDate(catalog.standard.published_at)}；规范提交 {catalog.standard.spec_revision.slice(0, 7)}。资料截止与验收日期分别标明。</p>
      <p>{catalog.standard.compatibility_note}</p><p>兼容版本：{catalog.standard.compatible_with.join("、")}。{catalog.standard.change_note}</p>
      <p>统一的是价值含义和验收标准，不是要求不同行业使用同一公式或相同资本成本。</p></details>
    <section className="standards-stats" aria-label="选定范围研究进度">
      <button onClick={() => changeView("progress")}><strong>{counts.total}</strong><span>{scope === "quality_pool" ? "核心池公司" : "研究档案"}</span></button>
      <button onClick={() => changeView("current")}><strong>{counts.completed}</strong><span>新版有效结果</span></button>
      <button onClick={() => { changeView("progress"); setProgress("unpriced"); }}><strong>{counts.unpriced}</strong><span>已研究 · 暂无法估值</span></button>
      <button onClick={() => changeView("progress")}><strong>{counts.pending}</strong><span>待首次研究 / 待升级</span></button>
      <button onClick={() => changeView("progress")}><strong>{counts.updating + counts.review}</strong><span>新版待更新 / 待复核</span></button>
    </section>
    <section aria-label="公司研究列表">
      <div className="standards-toolbar"><div className="standards-tabs" role="tablist" aria-label="研究视图">
        {([["current", "当前研究"], ["progress", "研究进度"], ["market", "全部档案"]] as const).map(([id, label]) =>
          <button key={id} role="tab" aria-selected={view === id} onClick={() => changeView(id)}>{label}</button>)}</div>
        {view !== "market" && <label>范围 <select aria-label="研究范围" value={scope} onChange={(event) => { setScope(event.target.value as Scope); setIndustry("all"); setLimit(80); }}>
          <option value="quality_pool">核心研究池 · {catalog.scope.count}家</option><option value="all_standard">全部研究档案（当前页仍仅现行标准）</option></select></label>}
        <input ref={search} aria-label="搜索公司" placeholder="搜索公司、代码、行业 /" value={query} onChange={(event) => { setQuery(event.target.value); setLimit(80); }} />
        <select aria-label="行业筛选" value={industry} onChange={(event) => setIndustry(event.target.value)}><option value="all">全部行业</option>{industries.map((name) => <option key={name}>{name}</option>)}</select>
        {view === "current" && <select aria-label="当前研究排序" value={sort} onChange={(event) => setSort(event.target.value as Sort)}><option value="ticker">代码顺序</option><option value="updated">最近研究</option><option value="irr">模型年化回报</option><option value="value">相对价值下沿</option></select>}
        {view === "progress" && <select aria-label="新版进度筛选" value={progress} onChange={(event) => setProgress(event.target.value)}><option value="all">全部进度</option>{Object.entries(DISPLAY_LABELS).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>}
      </div>
      <div className="standards-caption"><span>显示 {Math.min(limit, ordered.length)} / {ordered.length} 家{view === "current" ? ` · 已取得可比较行情 ${compared.length} 家，其中低于区间下沿 ${below} 家` : " · 不展示旧估值"}</span>
        {view === "current" ? <div><span>行情时间 {formatDate(quoteAt, true)}</span> <button disabled={quoteRefreshing} onClick={() => void refreshQuotes()}>{quoteRefreshing ? "刷新中" : "刷新"}</button>
          <a href={`/data/${exportName}.json`} download>导出本范围 JSON</a><a href={`/data/${exportName}.csv`} download>CSV</a></div> : <span>质量池版本 {catalog.scope.asOf}</span>}</div>
      {view === "current" && <p className="standards-hint">5年基准情景回报按现价机械派生，不是收益承诺或交易信号。只对本页现行结果计算；不同公司的资料日期与关键假设仍需分别阅读。</p>}
      <div className="standards-table-scroll"><table className="standards-table"><thead><tr><th>公司</th><th>行业</th>
        {view === "current" ? <><th>现价</th><th>合理价值</th><th>5年基准情景年化回报</th><th>相对下沿</th><th>相对中枢</th><th>当前结论</th><th>资料截止</th></>
          : <><th>新版进度</th><th>研究状态</th><th>说明</th><th>报告版本</th></>}<th>阅读</th></tr></thead><tbody>
        {ordered.slice(0, limit).map((company) => {
          const quote = quotes.get(company.ticker); const position = pricePosition(company, quote); const irr = returnIrr(company, quote, 5);
          return <tr key={company.symbol} data-symbol={company.symbol}><td><strong>{cleanCompanyName(company.name)}</strong><small>{company.ticker}{company.inQualityPool ? ` · ${company.qualityTier === "core_moat" ? "A" : "B"}` : ""}</small></td><td>{company.industry}</td>
            {view === "current" ? <><td>¥{formatPrice(position.price)}</td><td>{company.valueRange ? <strong>¥{formatPrice(company.valueRange.low)}–{formatPrice(company.valueRange.high)}</strong> : <span>暂无法估值</span>}</td>
              <td title={returnModelTitle(company)}><strong>{formatIrr(irr?.midpoint)}</strong><small>{irr?.midpoint != null ? `低 ${formatIrr(irr.low)} · 高 ${formatIrr(irr.high)}` : company.returnModelDisplayIssue ? "现金路径待更新" : company.returnModel ? "行情暂缺或模型暂不可用" : company.returnModelNote ? "暂无法可靠建模" : "待后续完整研究补充"}</small></td>
              <td>{position.lowRatio == null ? "—" : `${position.lowRatio.toFixed(2)}×`}<small>{position.label}</small></td><td>{position.midpointRatio == null ? "—" : `${position.midpointRatio.toFixed(2)}×`}</td>
              <td className="summary-cell"><p>{company.summary}</p>{company.status === "ignore" && <small>研究后暂不持续覆盖</small>}</td><td>{formatDate(company.informationCutoff)}<small>验收 {formatDate(company.acceptedAt)}</small></td></>
              : <><td>{DISPLAY_LABELS[company.display.state]}</td><td>{STATUS_META[company.status].label}</td><td className="summary-cell">{company.hasResearchState ? company.display.reason : "已在质量池，待与研究状态衔接；未自动创建研究任务。"}</td><td>{company.reportDate ?? "尚无报告"}</td></>}
            <td>{company.reports.length ? <a href={`/reports/${company.ticker}${company.display.eligible ? "" : "?view=history"}`}>{company.display.eligible ? "阅读新版" : "查看历史"}</a> : "—"}</td></tr>;
        })}</tbody></table></div>
      {!ordered.length && <div className="standards-empty"><strong>{view === "current" ? "暂无符合条件的现行研究" : "没有符合条件的公司"}</strong><p>不会使用旧估值补位。可以切换研究进度或主动查看历史研报。</p></div>}
      {ordered.length > limit && <button className="load-more" onClick={() => setLimit((value) => value + 100)}>继续显示</button>}
    </section>
  </main>;
}

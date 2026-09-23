"use client";
/* eslint-disable @next/next/no-html-link-for-pages */
import { useEffect, useMemo, useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { loadCatalog, loadQuotes, formatDate, formatPrice, STATUS_META,
  type Catalog, type Company, type Quote, type ReportVersion } from "../lib/research";
import { currentResults, isCurrentResult, readingContext } from "../lib/display-policy.mjs";
import "../standards.css";

function nodeText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join("");
  if (node && typeof node === "object" && "props" in node) return nodeText((node as { props: { children?: ReactNode } }).props.children);
  return "";
}
function slug(value: string) { return value.trim().replace(/[*_`]/gu, "").replace(/[^\p{Letter}\p{Number}]+/gu, "-"); }
type Mode = "current" | "history";
type Scope = "quality_pool" | "all_standard";
export function ReportWorkspace({ initialTicker }: { initialTicker?: string }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("current");
  const [scope, setScope] = useState<Scope>("quality_pool");
  const [selectedTicker, setSelectedTicker] = useState(initialTicker ?? "");
  const [version, setVersion] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [standardFilter, setStandardFilter] = useState("all");
  const [content, setContent] = useState<{ path: string; body: string } | null>(null);
  const [bodyError, setBodyError] = useState<{ path: string; message: string } | null>(null);
  const [quoteSnapshot, setQuoteSnapshot] = useState<{ ticker: string; quote: Quote } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    loadCatalog(controller.signal).then((data) => {
      const params = new URLSearchParams(window.location.search);
      const requestedVersion = params.get("version");
      const historical = Boolean(requestedVersion || params.get("view") === "history");
      setCatalog(data); setVersion(requestedVersion); setMode(historical ? "history" : "current");
      if (historical || initialTicker) setScope("all_standard");
      if (!initialTicker) {
        const rows: Company[] = historical ? data.companies.filter((company) => company.reports.length) : currentResults(data.companies);
        setSelectedTicker(rows.sort((a, b) => historical ? (b.reportDate ?? "").localeCompare(a.reportDate ?? "") : a.ticker.localeCompare(b.ticker))[0]?.ticker ?? "");
      }
    }).catch((e: Error) => { if (e.name !== "AbortError") setError(e.message); });
    return () => controller.abort();
  }, [initialTicker]);
  const selected = useMemo(() => catalog?.companies.find((company) => company.ticker === selectedTicker) ?? null, [catalog, selectedTicker]);
  const context = readingContext(selected, version, mode) as { report: ReportVersion | null; live: boolean; historical: boolean };
  const path = context.report?.path ?? "";
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    fetch(path, { signal: controller.signal }).then((response) => {
      if (!response.ok) throw new Error("所选研报暂时不可用；没有回退到其他版本。");
      return response.text();
    }).then((body) => { setContent({ path, body }); setBodyError(null); })
      .catch((e: Error) => { if (e.name !== "AbortError") setBodyError({ path, message: e.message }); });
    return () => controller.abort();
  }, [path]);
  useEffect(() => {
    if (!selected || !context.live) return;
    const controller = new AbortController();
    const ticker = selected.ticker;
    loadQuotes([ticker], controller.signal).then((quotes) => setQuoteSnapshot(quotes[0] ? { ticker, quote: quotes[0] } : null))
      .catch((e: Error) => { if (e.name !== "AbortError") setQuoteSnapshot(null); });
    return () => controller.abort();
  }, [selected, context.live]);
  const markdown = content?.path === path ? content.body : "";
  const quote = context.live && quoteSnapshot?.ticker === selectedTicker ? quoteSnapshot.quote : undefined;
  const toc = markdown.split(/\r?\n/u).flatMap((line) => {
    const match = /^(#{2,3})\s+(.+)$/u.exec(line);
    return match ? [{ depth: match[1].length, label: match[2].replace(/[*_`]/gu, ""), id: slug(match[2]) }] : [];
  });
  const rows = (catalog?.companies ?? []).filter((company) => mode === "current"
    ? isCurrentResult(company, scope) : company.reports.length && (scope === "all_standard" || company.inQualityPool))
    .filter((company) => mode !== "history" || standardFilter === "all" || company.reports.some((report) => (report.standardId ?? "unconfirmed") === standardFilter))
    .filter((company) => [company.name, company.ticker, company.industry].join(" ").toLowerCase().includes(query.trim().toLowerCase()))
    .sort((a, b) => a.ticker.localeCompare(b.ticker));
  function choose(company: Company, nextMode = mode) {
    const matchingVersion = nextMode === "history" && standardFilter !== "all"
      ? company.reports.find((report) => (report.standardId ?? "unconfirmed") === standardFilter)?.date ?? null : null;
    setSelectedTicker(company.ticker); setVersion(matchingVersion); setMode(nextMode); setQuoteSnapshot(null);
    const suffix = matchingVersion ? `?version=${matchingVersion}` : nextMode === "history" ? "?view=history" : "";
    window.history.replaceState({}, "", `/reports/${company.ticker}${suffix}`);
  }
  function switchMode(nextMode: Mode) {
    setMode(nextMode); setVersion(null); setStandardFilter("all"); setQuoteSnapshot(null);
    if (nextMode === "history") setScope("all_standard");
    window.history.replaceState({}, "", selectedTicker ? `/reports/${selectedTicker}${nextMode === "history" ? "?view=history" : ""}` : `/reports${nextMode === "history" ? "?view=history" : ""}`);
  }
  if (error) return <main className="standards-workspace"><h1>研报库</h1><p role="alert">{error}</p></main>;
  return <main className="standards-workspace standards-reader">
    <aside className="standards-library"><h1>研报库</h1><p>当前结果与历史档案分开阅读。</p>
      <div className="standards-tabs" role="tablist" aria-label="研报库范围">
        <button role="tab" aria-selected={mode === "current"} onClick={() => switchMode("current")}>当前标准</button>
        <button role="tab" aria-selected={mode === "history"} onClick={() => switchMode("history")}>历史研报</button></div>
      <label>公司范围<select aria-label="研报公司范围" value={scope} onChange={(event) => setScope(event.target.value as Scope)}><option value="quality_pool">核心研究池</option><option value="all_standard">全部公司</option></select></label>
      <input aria-label="搜索研报" placeholder="公司、代码、行业" value={query} onChange={(event) => setQuery(event.target.value)} />
      {mode === "history" && <label>历史标准<select aria-label="历史标准筛选" value={standardFilter} onChange={(event) => setStandardFilter(event.target.value)}><option value="all">所有历史标准（不进行估值混排）</option><option value="unconfirmed">历史标准未确认</option>{catalog?.standards.map((standard) => <option key={standard.id} value={standard.id}>{standard.label}</option>)}</select></label>}
      <p>{rows.length} 家{mode === "current" ? "现行标准结果" : "历史档案"}</p>
      <div className="standards-library-list">{rows.map((company) => <button key={company.symbol} aria-pressed={selectedTicker === company.ticker} onClick={() => choose(company)}><strong>{company.name}</strong><small>{company.ticker} · {company.industry}</small><span>{mode === "current" ? company.standardLabel : `${company.reports.length} 个版本`}</span></button>)}</div>
    </aside>
    <section className="standards-reading" aria-label="所选报告">
      {selected ? <><header><span className="section-eyebrow">{context.historical ? "HISTORICAL SNAPSHOT" : "CURRENT STANDARD"}</span><h2>{selected.name}</h2>
        {context.report ? <><p className="standards-meta">阅读版本 {context.report.date} · 资料截止 {formatDate(context.report.informationCutoff)} · {context.report.standardLabel}</p>
          <p className="standards-meta">验收时间 {formatDate(context.report.acceptedAt, true)}{context.report.valueDefinition ? ` · ${context.report.valueDefinition}` : " · 本版价值含义以历史正文为准"}</p></> : <p>尚无可展示的现行标准报告</p>}
        {context.live && <div className="standards-reader-price" data-testid="live-research-panel"><span>{STATUS_META[selected.status].label}</span><strong>现价 ¥{formatPrice(quote?.price)}</strong><span>行情 {formatDate(quote?.quoteAt, true)}</span><p>{selected.summary}</p></div>}
        {selected.reports.length > 0 && <label>报告版本<select aria-label="报告版本" value={context.report?.date ?? ""} onChange={(event) => { setVersion(event.target.value); setMode("history"); setQuoteSnapshot(null); window.history.replaceState({}, "", `/reports/${selected.ticker}?version=${event.target.value}`); }}>
          {!context.report && <option value="" disabled>选择历史版本</option>}{selected.reports.map((report) => <option key={report.sourcePath} value={report.date}>{report.date} · {report.standardLabel}{report.sourcePath === selected.reportPath ? " · 当前文件指针" : ""}</option>)}</select></label>}
      </header>
      {context.historical && <div className="standards-history-note" data-testid="historical-notice"><strong>历史快照</strong><p>正文保留本版的判断与估值，不加载现价、不附上其他版本摘要，也不参与当前估值排序。</p>
        {context.report?.acceptanceStatus === "content_changed" && <p>该正文与原验收记录不一致，原验收不适用于当前内容。</p>}
        {context.report?.acceptanceStatus === "revoked" && <p>该版本验收已撤销。</p>}
        {selected.display.eligible && <a href={`/reports/${selected.ticker}`}>转到现行有效研究 →</a>}</div>}
      {!context.report ? <div className="standards-empty"><strong>{context.historical ? "所引用的报告版本不存在" : selected.display.reason}</strong><p>不会自动用更早或其他口径的估值补位。</p>
        {selected.reports.length > 0 && <button onClick={() => choose(selected, "history")}>主动查看历史研报</button>}</div>
        : bodyError?.path === path ? <p role="alert">{bodyError.message}</p>
          : !markdown ? <p aria-busy="true">正在读取所选版本…</p>
            : <article className="markdown-document"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{
              h1: ({ children }) => <h1 id={slug(nodeText(children))}>{children}</h1>,
              h2: ({ children }) => <h2 id={slug(nodeText(children))}>{children}</h2>,
              h3: ({ children }) => <h3 id={slug(nodeText(children))}>{children}</h3>,
              a: ({ href, children }) => <a href={href} rel="noreferrer" target={href?.startsWith("http") ? "_blank" : undefined}>{children}</a>,
              table: ({ children }) => <div className="standards-table-scroll"><table>{children}</table></div>,
            }}>{markdown}</ReactMarkdown></article>}
      </> : <div className="standards-empty"><h2>{catalog ? "从左侧选择报告" : "正在读取研报库…"}</h2><p>现行结果为空时可以主动进入历史研报；不会自动补入旧估值。</p></div>}
    </section>
    <aside className="standards-toc"><h3>本版目录</h3><nav aria-label="本版目录">{toc.map((item, index) => <a key={`${item.id}-${index}`} href={`#${item.id}`} style={{ paddingLeft: item.depth === 3 ? 12 : 0 }}>{item.label}</a>)}</nav></aside>
  </main>;
}

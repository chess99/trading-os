"use client";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { loadCatalog, loadQuotes, formatDate, formatPrice, STATUS_META,
  type Catalog, type Company, type Quote, type ReportVersion } from "../lib/research";
import { readingContext } from "../lib/display-policy.mjs";
import "../standards.css";

function nodeText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join("");
  if (node && typeof node === "object" && "props" in node) return nodeText((node as { props: { children?: ReactNode } }).props.children);
  return "";
}
function slug(value: string) { return value.trim().replace(/[*_`]/gu, "").replace(/[^\p{Letter}\p{Number}]+/gu, "-"); }
type Scope = "quality_pool" | "all_standard";
export function ReportWorkspace({ initialTicker }: { initialTicker?: string }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scope, setScope] = useState<Scope>(initialTicker ? "all_standard" : "quality_pool");
  const [selectedTicker, setSelectedTicker] = useState(initialTicker ?? "");
  const [version, setVersion] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [content, setContent] = useState<{ path: string; body: string } | null>(null);
  const [bodyError, setBodyError] = useState<{ path: string; message: string } | null>(null);
  const [quoteSnapshot, setQuoteSnapshot] = useState<{ ticker: string; quote: Quote } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    loadCatalog(controller.signal).then((data) => {
      const requestedVersion = new URLSearchParams(window.location.search).get("version");
      setCatalog(data); setVersion(requestedVersion);
      if (!initialTicker) {
        const rows = data.companies.filter((company) => company.inQualityPool && company.reports.length);
        setSelectedTicker(rows.sort((a, b) => a.ticker.localeCompare(b.ticker))[0]?.ticker ?? "");
      }
    }).catch((e: Error) => { if (e.name !== "AbortError") setError(e.message); });
    return () => controller.abort();
  }, [initialTicker]);
  const selected = useMemo(() => catalog?.companies.find((company) => company.ticker === selectedTicker) ?? null, [catalog, selectedTicker]);
  const context = readingContext(selected, version) as { report: ReportVersion | null; live: boolean; historical: boolean };
  const path = context.report?.path ?? "";
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    fetch(path, { signal: controller.signal }).then((response) => {
      if (!response.ok) throw new Error("所选研报暂时不可用；没有回退到其他周期。");
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
  const rows = (catalog?.companies ?? []).filter((company) => company.reports.length
    && (scope === "all_standard" || company.inQualityPool))
    .filter((company) => [company.name, company.ticker, company.industry].join(" ").toLowerCase().includes(query.trim().toLowerCase()))
    .sort((a, b) => a.ticker.localeCompare(b.ticker));
  function choose(company: Company) {
    setSelectedTicker(company.ticker); setVersion(null); setQuoteSnapshot(null);
    window.history.replaceState({}, "", `/reports/${company.ticker}`);
  }
  if (error) return <main className="standards-workspace"><h1>研报库</h1><p role="alert">{error}</p></main>;
  return <main className="standards-workspace standards-reader">
    <aside className="standards-library"><h1>研报库</h1><p>每个财报周期保留一份完整研究，同周期重写直接更新原文件。</p>
      <label>公司范围<select aria-label="研报公司范围" value={scope} onChange={(event) => setScope(event.target.value as Scope)}><option value="quality_pool">重点跟踪池 · {catalog?.scope.count ?? "—"}家</option><option value="all_standard">全市场</option></select></label>
      <input aria-label="搜索研报" placeholder="公司、代码、行业" value={query} onChange={(event) => setQuery(event.target.value)} />
      <p>{rows.length} 家有研究报告</p>
      <div className="standards-library-list">{rows.map((company) => <button key={company.symbol} aria-pressed={selectedTicker === company.ticker} onClick={() => choose(company)}><strong>{company.name}</strong><small>{company.ticker} · {company.industry}</small><span>最新 {company.latestReportPeriod}{company.reportUpdatedAt ? ` · 更新 ${formatDate(company.reportUpdatedAt)}` : ""} · 共 {company.reports.length} 个周期</span></button>)}</div>
    </aside>
    <section className="standards-reading" aria-label="所选报告">
      {selected ? <><header><span className="section-eyebrow">{context.live ? "CURRENT STANDARD" : "RESEARCH ARCHIVE"}</span><h2>{selected.name}</h2>
        {context.report ? <><p className="standards-meta">研究周期 {context.report.period} · 资料截止 {formatDate(context.report.informationCutoff)} · {context.report.standardLabel}</p>
          {context.report.sourcePath === selected.basisReportPath && <p className="standards-meta">报告更新 {formatDate(selected.reportUpdatedAt, true)} · 完成入库 {formatDate(context.report.acceptedAt, true)}</p>}</> : <p>该研究周期不存在</p>}
        {context.live && <div className="standards-reader-price" data-testid="live-research-panel"><span>{STATUS_META[selected.status].label}</span><strong>现价 ¥{formatPrice(quote?.price)}</strong><span>行情 {formatDate(quote?.quoteAt, true)}</span><p>{selected.summary}</p></div>}
        {selected.reports.length > 0 && <label>研究周期<select aria-label="研究周期" value={context.report?.period ?? ""} onChange={(event) => { setVersion(event.target.value); setQuoteSnapshot(null); window.history.replaceState({}, "", `/reports/${selected.ticker}?version=${event.target.value}`); }}>
          {!context.report && <option value="" disabled>选择研究周期</option>}{selected.reports.map((report) => <option key={report.sourcePath} value={report.period}>{report.period} · {report.standardLabel}{report.sourcePath === selected.basisReportPath ? " · 状态依据" : ""}</option>)}</select></label>}
      </header>
      {context.historical && <div className="standards-history-note" data-testid="historical-notice"><strong>历史研究周期</strong><p>本报告保留该周期最后一次完整研究，不加载现价、不参与现行结果排序。</p></div>}
      {!context.report ? <div className="standards-empty"><strong>所选研究周期不存在</strong></div>
        : bodyError?.path === path ? <p role="alert">{bodyError.message}</p>
          : !markdown ? <p aria-busy="true">正在读取所选报告…</p>
            : <article className="markdown-document"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{
              h1: ({ children }) => <h1 id={slug(nodeText(children))}>{children}</h1>,
              h2: ({ children }) => <h2 id={slug(nodeText(children))}>{children}</h2>,
              h3: ({ children }) => <h3 id={slug(nodeText(children))}>{children}</h3>,
              a: ({ href, children }) => <a href={href} rel="noreferrer" target={href?.startsWith("http") ? "_blank" : undefined}>{children}</a>,
              table: ({ children }) => <div className="standards-table-scroll"><table>{children}</table></div>,
            }}>{markdown}</ReactMarkdown></article>}
      </> : <div className="standards-empty"><h2>{catalog ? "从左侧选择报告" : "正在读取研报库…"}</h2></div>}
    </section>
    <aside className="standards-toc"><h3>本期目录</h3><nav aria-label="本期目录">{toc.map((item, index) => <a key={`${item.id}-${index}`} href={`#${item.id}`} style={{ paddingLeft: item.depth === 3 ? 12 : 0 }}>{item.label}</a>)}</nav></aside>
  </main>;
}

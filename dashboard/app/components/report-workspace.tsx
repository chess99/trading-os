"use client";
/* eslint-disable @next/next/no-html-link-for-pages */

import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  cleanCompanyName,
  formatDate,
  formatPrice,
  loadCatalog,
  loadQuotes,
  STATUS_META,
  type Catalog,
  type Company,
  type Quote,
  type ResearchStatus,
} from "../lib/research";

interface ReportWorkspaceProps {
  initialTicker?: string;
}

interface TocItem {
  depth: number;
  label: string;
  id: string;
}

function slugify(value: string) {
  return value
    .trim()
    .toLocaleLowerCase("zh-CN")
    .replace(/[\s/]+/gu, "-")
    .replace(/[^\p{Letter}\p{Number}-]/gu, "")
    .replace(/-+/gu, "-");
}

function nodeText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join("");
  if (node && typeof node === "object" && "props" in node) {
    return nodeText((node as { props: { children?: ReactNode } }).props.children);
  }
  return "";
}

function parseToc(markdown: string): TocItem[] {
  return markdown
    .split(/\r?\n/u)
    .flatMap((line) => {
      const match = /^(#{2,3})\s+(.+)$/u.exec(line.trim());
      if (!match) return [];
      const label = match[2].replace(/[*_`]/gu, "").trim();
      return [{ depth: match[1].length, label, id: slugify(label) }];
    })
    .slice(0, 32);
}

function ReportStatus({ status }: { status: ResearchStatus }) {
  return <span className={`status-badge status-${status}`}>{STATUS_META[status].label}</span>;
}

function reportSourceLabel(quote?: Quote) {
  if (!quote) return "行情暂缺";
  return quote.source === "tencent" ? "腾讯行情" : "东方财富备援";
}

export function ReportWorkspace({ initialTicker }: ReportWorkspaceProps) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [selectedTicker, setSelectedTicker] = useState(initialTicker ?? "");
  const [selectedReportPath, setSelectedReportPath] = useState("");
  const [markdown, setMarkdown] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ResearchStatus | "all">("all");
  const [industry, setIndustry] = useState("all");
  const [quote, setQuote] = useState<Quote | undefined>();
  const [loadingReport, setLoadingReport] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    loadCatalog(controller.signal)
      .then((nextCatalog) => {
        setCatalog(nextCatalog);
        const withReports = nextCatalog.companies
          .filter((company) => company.reports.length)
          .sort((a, b) => (b.reportDate ?? "").localeCompare(a.reportDate ?? ""));
        const requested = withReports.find((company) => company.ticker === initialTicker);
        const next = requested ?? withReports[0];
        if (next) {
          setSelectedTicker(next.ticker);
          setSelectedReportPath(next.reports[0].path);
        }
      })
      .catch((loadError: Error) => {
        if (loadError.name !== "AbortError") setError(loadError.message);
      });
    return () => controller.abort();
  }, [initialTicker]);

  useEffect(() => {
    if (!selectedReportPath) return;
    const controller = new AbortController();
    fetch(selectedReportPath, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("研报正文暂时无法读取");
        return response.text();
      })
      .then((body) => {
        setMarkdown(body);
        setLoadingReport(false);
        window.scrollTo({ top: 0, behavior: "smooth" });
      })
      .catch((loadError: Error) => {
        if (loadError.name !== "AbortError") {
          setError(loadError.message);
          setLoadingReport(false);
        }
      });
    return () => controller.abort();
  }, [selectedReportPath]);

  useEffect(() => {
    if (!selectedTicker) return;
    const controller = new AbortController();
    loadQuotes([selectedTicker], controller.signal)
      .then((quotes) => setQuote(quotes[0]))
      .catch(() => setQuote(undefined));
    return () => controller.abort();
  }, [selectedTicker]);

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

  const reportCompanies = useMemo(() => {
    if (!catalog) return [];
    const normalized = query.trim().toLocaleLowerCase("zh-CN");
    return catalog.companies
      .filter((company) => company.reports.length)
      .filter((company) => status === "all" || company.status === status)
      .filter((company) => industry === "all" || company.industry === industry)
      .filter(
        (company) =>
          !normalized ||
          [company.name, company.ticker, company.industry, company.summary]
            .join(" ")
            .toLocaleLowerCase("zh-CN")
            .includes(normalized),
      )
      .sort((a, b) => (b.reportDate ?? "").localeCompare(a.reportDate ?? "") || a.ticker.localeCompare(b.ticker));
  }, [catalog, industry, query, status]);

  const industries = useMemo(() => {
    if (!catalog) return [];
    return [...new Set(catalog.companies.filter((company) => company.reports.length).map((company) => company.industry))].sort(
      (a, b) => a.localeCompare(b, "zh-CN"),
    );
  }, [catalog]);

  const selected = useMemo(
    () => catalog?.companies.find((company) => company.ticker === selectedTicker) ?? null,
    [catalog, selectedTicker],
  );
  const toc = useMemo(() => parseToc(markdown), [markdown]);

  function chooseCompany(company: Company) {
    setLoadingReport(true);
    setQuote(undefined);
    setSelectedTicker(company.ticker);
    setSelectedReportPath(company.reports[0].path);
    window.history.replaceState({}, "", `/reports/${company.ticker}`);
  }

  return (
    <main className="report-shell">
      <aside className="report-library-panel">
        <div className="library-intro">
          <span className="section-eyebrow">REPORT LIBRARY</span>
          <h1>研报库</h1>
          <p>{catalog ? `${catalog.stats.reports} 家公司有正式研报` : "正在整理正式研报"}</p>
        </div>
        <label className="search-field report-search">
          <span aria-hidden="true">⌕</span>
          <input
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索公司、代码、行业  /"
            ref={searchRef}
            type="search"
            value={query}
          />
        </label>
        <div className="report-filters">
          <select aria-label="按研究状态筛选" value={status} onChange={(event) => setStatus(event.target.value as ResearchStatus | "all")}>
            <option value="all">全部状态</option>
            <option value="covered">持续覆盖</option>
            <option value="ignore">暂不关注</option>
            <option value="stale">等待更新</option>
          </select>
          <select aria-label="按行业筛选" value={industry} onChange={(event) => setIndustry(event.target.value)}>
            <option value="all">全部行业</option>
            {industries.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
        <div className="report-result-count">
          <span>{reportCompanies.length} 份当前公司档案</span>
          {(query || status !== "all" || industry !== "all") && (
            <button
              onClick={() => {
                setQuery("");
                setStatus("all");
                setIndustry("all");
              }}
            >
              清除筛选
            </button>
          )}
        </div>
        <div className="report-company-list">
          {reportCompanies.map((company) => (
            <button
              className={company.ticker === selectedTicker ? "is-active" : ""}
              key={company.symbol}
              onClick={() => chooseCompany(company)}
            >
              <span className="report-list-title">
                <strong>{cleanCompanyName(company.name)}</strong>
                <small>{company.ticker}</small>
              </span>
              <span className="report-list-meta">
                <span>{company.industry}</span>
                <time>{company.reportDate}</time>
              </span>
              <span className={`report-status-dot report-status-${company.status}`} aria-label={STATUS_META[company.status].label} />
            </button>
          ))}
          {!reportCompanies.length ? <div className="report-list-empty">没有符合条件的正式研报。</div> : null}
        </div>
        <div className="legacy-note">隔离旧稿不参与当前结论，也不会混入这里的搜索结果。</div>
      </aside>

      <section className="report-reader">
        {error ? (
          <div className="reader-empty">
            <strong>研报暂时无法显示</strong>
            <span>{error}</span>
          </div>
        ) : selected ? (
          <>
            <header className="report-document-header">
              <div className="report-breadcrumbs">
                <a href="/">研究决策台</a>
                <span>/</span>
                <span>研报库</span>
                <span>/</span>
                <strong>{selected.ticker}</strong>
              </div>
              <div className="report-title-row">
                <div>
                  <span className="report-ticker">{selected.ticker} · {selected.exchange} · {selected.industry}</span>
                  <h2>{cleanCompanyName(selected.name)}</h2>
                  <div className="report-meta-line">
                    <ReportStatus status={selected.status} />
                    <span>信息截止 {formatDate(selected.informationCutoff)}</span>
                    <span>当前版本 {selectedReportPath.split("/").pop()?.replace(".md", "")}</span>
                  </div>
                </div>
                <div className="reader-quote">
                  <span>现价</span>
                  <strong>¥{formatPrice(quote?.price)}</strong>
                  {quote?.changePercent !== null && quote?.changePercent !== undefined ? (
                    <small className={quote.changePercent > 0 ? "price-up" : quote.changePercent < 0 ? "price-down" : "price-flat"}>
                      {quote.changePercent > 0 ? "+" : ""}{quote.changePercent.toFixed(2)}%
                    </small>
                  ) : null}
                  <em>{reportSourceLabel(quote)}</em>
                </div>
              </div>
              {selected.reports.length > 1 ? (
                <label className="version-select">
                  <span>报告版本</span>
                  <select
                    value={selectedReportPath}
                    onChange={(event) => {
                      setLoadingReport(true);
                      setSelectedReportPath(event.target.value);
                    }}
                  >
                    {selected.reports.map((report, index) => (
                      <option key={report.path} value={report.path}>
                        {report.date}{index === 0 ? " · 当前" : ""}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
            </header>

            {loadingReport ? (
              <div className="report-loading" aria-busy="true">
                <span />
                <span />
                <span />
                <p>正在展开研报正文…</p>
              </div>
            ) : (
              <article className="markdown-document">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h1: ({ children }) => <h1 id={slugify(nodeText(children))}>{children}</h1>,
                    h2: ({ children }) => <h2 id={slugify(nodeText(children))}>{children}</h2>,
                    h3: ({ children }) => <h3 id={slugify(nodeText(children))}>{children}</h3>,
                    a: ({ href, children }) => (
                      <a href={href} rel="noreferrer" target={href?.startsWith("http") ? "_blank" : undefined}>
                        {children}
                      </a>
                    ),
                    table: ({ children }) => (
                      <div className="markdown-table-wrap">
                        <table>{children}</table>
                      </div>
                    ),
                  }}
                >
                  {markdown}
                </ReactMarkdown>
              </article>
            )}
          </>
        ) : (
          <div className="reader-empty">
            <strong>从左侧选择一份研报</strong>
            <span>可以按公司、代码、行业或研究状态筛选。</span>
          </div>
        )}
      </section>

      <aside className="report-toc-panel">
        <div className="toc-sticky">
          <span className="section-eyebrow">ON THIS PAGE</span>
          <h3>本页目录</h3>
          <nav aria-label="研报目录">
            {toc.map((item, index) => (
              <a className={item.depth === 3 ? "toc-depth-three" : ""} href={`#${item.id}`} key={`${item.id}-${index}`}>
                {item.label}
              </a>
            ))}
          </nav>
          {selected ? (
            <div className="toc-summary">
              <span>一句话结论</span>
              <p>{selected.summary}</p>
            </div>
          ) : null}
        </div>
      </aside>
    </main>
  );
}

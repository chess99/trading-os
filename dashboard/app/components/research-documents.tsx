"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { MARKET_LABELS, loadCatalog, type Catalog } from "../lib/research";
import { currentResults } from "../lib/display-policy.mjs";
import { reportReferenceLink } from "../lib/report-reference.mjs";

interface Document {
  id: string;
  kind: "industry" | "selection";
  title: string;
  path: string;
  sourcePath: string;
  industries: string[];
  markets: string[];
  companyReferences: {symbol: string; name: string; industry: string; market: string; reportHref: string}[];
}

export function ResearchDocuments({ kind }: { kind: Document["kind"] }) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [market, setMarket] = useState("all");
  const [catalogError, setCatalogError] = useState("");
  const [bodyPath, setBodyPath] = useState("");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [selected, setSelected] = useState("");
  const [query, setQuery] = useState("");
  const [markdown, setMarkdown] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    loadCatalog(controller.signal).then(setCatalog).catch((reason: Error) => { if (reason.name !== "AbortError") setCatalogError("研究基础暂时无法读取。"); });
    fetch("/data/documents.json", { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("研究目录暂时无法读取"); return response.json(); })
      .then((data: { documents: Document[] }) => {
        setDocuments(data.documents);
        const requested = new URLSearchParams(window.location.search).get("topic");
        const initial = data.documents.find((doc) => doc.kind === kind && doc.id === requested)
          ?? data.documents.find((doc) => doc.id === (kind === "industry" ? "cross-market-guide" : "selection-current"))
          ?? data.documents.find((doc) => doc.kind === kind);
        setSelected(initial?.id ?? "");
      }).catch((reason: Error) => { if (reason.name !== "AbortError") setError(reason.message); });
    return () => controller.abort();
  }, [kind]);

  const current = documents.find((doc) => doc.id === selected && (market === "all" || doc.markets.includes(market)))
    ?? documents.find((doc) => doc.kind === kind && (market === "all" || doc.markets.includes(market)));
  const path = current?.path;
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    fetch(path, { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("研究正文暂时无法读取"); return response.text(); })
      .then((text) => { setMarkdown(text); setBodyPath(path); setError(""); })
      .catch((reason: Error) => { if (reason.name !== "AbortError") setError(reason.message); });
    return () => controller.abort();
  }, [path]);

  const filtered = documents.filter((doc) => doc.kind === kind
    && (market === "all" || doc.markets.includes(market))
    && `${doc.title} ${doc.industries.join(" ")}`.includes(query.trim()));
  function documentLink(href: string | undefined) {
    if (!href || /^(https?:|mailto:|#)/u.test(href)) return href;
    const resolved = new URL(href, `https://research.local/${current?.sourcePath ?? ""}`);
    const reportLink = reportReferenceLink(resolved.pathname);
    if (reportLink) return reportLink;
    const target = documents.find((doc) => `/${doc.sourcePath}` === resolved.pathname);
    return target ? `/${target.kind === "industry" ? "industries" : "selection"}?topic=${encodeURIComponent(target.id)}` : undefined;
  }

  return (
    <main className="research-documents">
      <aside className="research-documents-nav">
        <h1>{kind === "industry" ? "产业研究" : "长期精选"}</h1>
        <label>市场<select aria-label={kind === "industry" ? "产业市场" : "精选市场"} disabled={!documents.length} value={market} onChange={(event) => { setMarket(event.target.value); }}>{Object.entries(MARKET_LABELS).map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select></label>
        <label htmlFor="document-search">查找主题或细分行业</label>
        <input id="document-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="输入关键词" />
        <nav aria-label="研究文档">
          {filtered.map((doc) => <button key={doc.id} className={current?.id === doc.id ? "is-active" : ""}
            onClick={() => { setSelected(doc.id); window.scrollTo({ top: 0 }); }}>
            {doc.title.replace(/：.*$/u, "")}
          </button>)}
          {!filtered.length && <p>没有匹配的主题。</p>}
        </nav>
      </aside>
      <article className="markdown-document research-document-body" aria-live="polite">
        <section className="document-coverage" aria-label={kind === "industry" ? "关联公司" : "精选研究基础"}>
          <h2>{kind === "industry" ? "关联公司" : "研究基础"}</h2>
          {kind === "industry" ? <div>{current?.companyReferences.filter((c) => market === "all" || c.market === market).slice(0,18).map((c) => <a key={c.symbol} href={`/?view=pool&q=${encodeURIComponent(c.symbol)}`}>{c.name} <small>{c.symbol}</small></a>)}</div>
          : !catalog ? <p>{catalogError || "正在读取研究基础…"}</p> : <><p>已完成可比较研究：{currentResults((catalog?.companies ?? []).filter((c) => market === "all" || c.market === market)).length} 个标的</p>
            <p>公司池：{(catalog?.companies ?? []).filter((c) => c.inQualityPool && (market === "all" || c.market === market)).length} 个标的</p>
            {catalog && currentResults(catalog.companies.filter((c) => market === "all" || c.market === market)).length === 0 && <p>该市场尚无可供精选比较的完整研究。</p>}</>}
        </section>
        {error ? <p role="alert">{error}</p> : !markdown || bodyPath !== path ? <p>正在读取研究正文…</p> :
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
            a: ({ href, children }) => { const link = documentLink(href); return link ? <a href={link}>{children}</a> : <span>{children}</span>; },
          }}>{markdown}</ReactMarkdown>}
      </article>
    </main>
  );
}

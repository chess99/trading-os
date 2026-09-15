"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Document {
  id: string;
  kind: "industry" | "selection";
  title: string;
  path: string;
  sourcePath: string;
  industries: string[];
}

export function ResearchDocuments({ kind }: { kind: Document["kind"] }) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selected, setSelected] = useState("");
  const [query, setQuery] = useState("");
  const [markdown, setMarkdown] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/data/documents.json", { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("研究目录暂时无法读取"); return response.json(); })
      .then((data: { documents: Document[] }) => {
        setDocuments(data.documents);
        const requested = new URLSearchParams(window.location.search).get("topic");
        const initial = data.documents.find((doc) => doc.kind === kind && doc.id === requested)
          ?? data.documents.find((doc) => doc.id === (kind === "industry" ? "industry-guide" : "selection-current"))
          ?? data.documents.find((doc) => doc.kind === kind);
        setSelected(initial?.id ?? "");
      }).catch((reason: Error) => { if (reason.name !== "AbortError") setError(reason.message); });
    return () => controller.abort();
  }, [kind]);

  const current = documents.find((doc) => doc.id === selected);
  const path = current?.path;
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    fetch(path, { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("研究正文暂时无法读取"); return response.text(); })
      .then((text) => { setMarkdown(text); setError(""); })
      .catch((reason: Error) => { if (reason.name !== "AbortError") setError(reason.message); });
    return () => controller.abort();
  }, [path]);

  const filtered = documents.filter((doc) => doc.kind === kind
    && `${doc.title} ${doc.industries.join(" ")}`.includes(query.trim()));
  function documentLink(href: string | undefined) {
    if (!href || /^(https?:|mailto:|#)/u.test(href)) return href;
    const resolved = new URL(href, `https://research.local/${current?.sourcePath ?? ""}`);
    const ticker = /research\/companies\/CN\/(\d{6})\/reports\//u.exec(resolved.pathname)?.[1];
    if (ticker) return `/reports/${ticker}`;
    const target = documents.find((doc) => `/${doc.sourcePath}` === resolved.pathname);
    return target ? `/${target.kind === "industry" ? "industries" : "selection"}?topic=${encodeURIComponent(target.id)}` : undefined;
  }

  return (
    <main className="research-documents">
      <aside className="research-documents-nav">
        <h1>{kind === "industry" ? "产业研究" : "长期精选"}</h1>
        <label htmlFor="document-search">查找主题或细分行业</label>
        <input id="document-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="输入关键词" />
        <nav aria-label="研究文档">
          {filtered.map((doc) => <button key={doc.id} className={selected === doc.id ? "is-active" : ""}
            onClick={() => { setSelected(doc.id); setMarkdown(""); window.scrollTo({ top: 0 }); }}>
            {doc.title.replace(/：.*$/u, "")}
          </button>)}
          {!filtered.length && <p>没有匹配的主题。</p>}
        </nav>
      </aside>
      <article className="markdown-document research-document-body" aria-live="polite">
        {error ? <p role="alert">{error}</p> : !markdown ? <p>正在读取研究正文…</p> :
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
            a: ({ href, children }) => { const link = documentLink(href); return link ? <a href={link}>{children}</a> : <span>{children}</span>; },
          }}>{markdown}</ReactMarkdown>}
      </article>
    </main>
  );
}

"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { MARKET_LABELS } from "../lib/research";
import { reportReferenceLink } from "../lib/report-reference.mjs";
import { IndustryIndicators } from "./industry-indicators";

interface Document {
  id: string;
  kind: "industry" | "macro";
  type: "report" | "reference";
  topic: string;
  title: string;
  summary: string;
  path: string;
  sourcePath: string;
  publishedOn: string;
  revision: number;
  version: string;
  informationCutoff: string | null;
  markets: string[];
  regions: string[];
  status: "published" | "withdrawn";
  withdrawalReason: string | null;
  indicatorPath: string | null;
}

export function ResearchDocuments({ kind }: { kind: Document["kind"] }) {
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [market, setMarket] = useState("all");
  const [type, setType] = useState<Document["type"]>("report");
  const [topic, setTopic] = useState("");
  const [version, setVersion] = useState("");
  const [panel, setPanel] = useState("report");
  const [query, setQuery] = useState("");
  const [body, setBody] = useState({ path: "", text: "", error: "" });
  const [error, setError] = useState("");
  const label = kind === "industry" ? "行业研究" : "宏观与市场";

  useEffect(() => {
    const controller = new AbortController();
    fetch("/data/documents.json", { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("研究目录暂时无法读取"); return response.json(); })
      .then((data: { schemaVersion: number; documents: Document[] }) => {
        if (data.schemaVersion !== 1 || !Array.isArray(data.documents)) throw new Error("研究目录格式不正确");
        setDocuments(data.documents);
        const params = new URLSearchParams(window.location.search);
        setTopic(params.get("topic") ?? ""); setVersion(params.get("version") ?? "");
        if ((params.get("market") ?? "") in MARKET_LABELS) setMarket(params.get("market")!);
        setPanel(params.get("panel") === "indicators" ? "indicators" : "report");
        const wanted = params.get("view");
        if (wanted === "report" || wanted === "reference") setType(wanted);
        else if (!data.documents.some((d) => d.kind === kind && d.type === "report")
          && data.documents.some((d) => d.kind === kind && d.type === "reference")) setType("reference");
      }).catch((reason: Error) => { if (reason.name !== "AbortError") setError(reason.message); });
    return () => controller.abort();
  }, [kind]);

  const available = (documents ?? []).filter((d) => d.kind === kind);
  const scoped = available.filter((d) => d.type === type && (market === "all" || d.markets.includes(market)))
    .sort((a, b) => b.publishedOn.localeCompare(a.publishedOn) || b.revision - a.revision);
  const topics = [...new Map([...scoped].reverse().map((d) => [d.topic, d])).values()]
    .sort((a,b) => b.publishedOn.localeCompare(a.publishedOn) || b.revision - a.revision)
    .filter((d) => `${d.title} ${d.summary} ${d.regions.join(" ")}`.toLowerCase().includes(query.trim().toLowerCase()));
  const selectedTopic = topic || topics[0]?.topic;
  const versions = scoped.filter((d) => d.topic === selectedTopic);
  const current = version ? versions.find((d) => d.version === version) : versions[0];
  const path = current?.path;
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    fetch(path, { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("研究正文暂时无法读取"); return response.text(); })
      .then((text) => setBody({ path, text, error: "" }))
      .catch((reason: Error) => { if (reason.name !== "AbortError") setBody({ path, text: "", error: reason.message }); });
    return () => controller.abort();
  }, [path]);

  function update(nextTopic: string, nextVersion = "", nextType = type, nextMarket = market) {
    setTopic(nextTopic); setVersion(nextVersion); setType(nextType); setMarket(nextMarket); setPanel("report");
    const params = new URLSearchParams({ view: nextType });
    if (nextTopic) params.set("topic", nextTopic);
    if (nextVersion) params.set("version", nextVersion);
    if (nextMarket !== "all") params.set("market", nextMarket);
    window.history.replaceState(null, "", `${kind === "industry" ? "/industries" : "/macro"}?${params}`);
  }
  function showPanel(next: string) {
    setPanel(next);
    const params = new URLSearchParams(window.location.search);
    params.set("topic", current!.topic); params.set("view", type);
    if (next === "indicators") params.set("panel", next); else params.delete("panel");
    window.history.replaceState(null, "", `${kind === "industry" ? "/industries" : "/macro"}?${params}`);
  }
  function documentLink(href: string | undefined) {
    if (!href || /^(https?:|mailto:|#)/u.test(href)) return href;
    const resolved = new URL(href, `https://research.local/${current?.sourcePath ?? ""}`);
    if (["/industries", "/macro"].includes(resolved.pathname)) return `${resolved.pathname}${resolved.search}${resolved.hash}`;
    const companyReport = reportReferenceLink(resolved.pathname);
    if (companyReport) return companyReport;
    const target = documents?.find((d) => `/${d.sourcePath}` === resolved.pathname);
    return target ? `${target.kind === "industry" ? "/industries" : "/macro"}?topic=${target.topic}&version=${target.version}&view=${target.type}` : undefined;
  }
  const outline = body.path === path && !body.error ? body.text.split("\n").flatMap((line, index) => {
    const match = /^##\s+(.+)$/u.exec(line);
    return match ? [{ id: `section-${index + 1}`, title: match[1] }] : [];
  }) : [];
  const reportCount = new Set(available.filter((d) => d.type === "report" && d.status === "published").map((d) => d.topic)).size;
  const referenceCount = available.filter((d) => d.type === "reference" && d.status === "published").length;

  return <main className="publication-workspace">
    <header className="publication-heading"><h1>{label}</h1><p>{kind === "industry" ? "行业历史、供需与竞争，及其未来的利润归属。" : "周期、资金条件与估值，及其对长期投资的影响。"}</p></header>
    <div className="publication-toolbar">
      <div className="publication-types" aria-label="内容类型">
        <button aria-pressed={type === "report"} onClick={() => update("", "", "report")}>研究报告 {reportCount}</button>
        {(referenceCount > 0 || type === "reference") && <button aria-pressed={type === "reference"} onClick={() => update("", "", "reference")}>指标与方法 {referenceCount}</button>}
      </div>
      <select aria-label="适用市场" disabled={!documents} value={market} onChange={(e) => update("", "", type, e.target.value)}>{Object.entries(MARKET_LABELS).map(([id,name]) => <option key={id} value={id}>{name}</option>)}</select>
      <input type="search" aria-label="搜索研究主题" placeholder="搜索主题、地域或判断" value={query} onChange={(e) => { setQuery(e.target.value); update(""); }} />
    </div>
    {error ? <p role="alert">{error}</p> : !documents ? <p role="status">正在读取研究目录…</p> : !current ? <section className="publication-empty">
      <h2>{topic || version ? "未找到所选主题或版本" : type === "report" ? `暂无${kind === "industry" ? "行业" : "宏观"}研究报告` : "没有符合条件的参考文章"}</h2>
      <p>{topic || version ? "可清除筛选后查看现有主题。" : "调整市场或关键词，查看已发布内容。"}</p>
      {(topic || version || query || market !== "all") && <button onClick={() => { setQuery(""); update("", "", type, "all"); }}>查看全部主题</button>}
    </section> : <div className="publication-layout">
      <aside className="publication-sidebar">
        {topics.length > 1 && <select className="publication-mobile-topics" aria-label="选择研究主题" value={current.topic} onChange={(e) => update(e.target.value)}>{topics.map((d) => <option key={d.topic} value={d.topic}>{d.title.split("：")[0]}</option>)}</select>}
        {!(panel === "indicators" && current.indicatorPath) && outline.length > 3 && <details key={current.id} className="publication-outline"><summary>本文目录</summary><nav aria-label="本文目录">{outline.map((item) => <a key={item.id} href={`#${item.id}`}>{item.title}</a>)}</nav></details>}
        <nav aria-label="研究主题" className="publication-list">{topics.map((d) => <button key={d.topic} title={d.title} aria-label={d.title} aria-current={d.topic === current.topic ? "true" : undefined} onClick={() => update(d.topic)}><strong>{d.title.split("：")[0]}</strong><span>{d.publishedOn}{d.status === "withdrawn" ? " · 已撤回" : ""}</span></button>)}</nav>
      </aside>
      <article className="research-document-body" aria-live="polite">
        {current.indicatorPath && <div className="publication-panel-switch" role="group" aria-label="主题内容"><button aria-pressed={panel !== "indicators"} onClick={() => showPanel("report")}>完整研究</button><button aria-pressed={panel === "indicators"} onClick={() => showPanel("indicators")}>行业指标</button></div>}
        {panel === "indicators" && current.indicatorPath ? <IndustryIndicators key={current.indicatorPath} path={current.indicatorPath}/> : <>
        <header className="publication-meta"><details><summary>{current.type === "report" ? `资料截止 ${current.informationCutoff}` : `指标与方法 · ${current.publishedOn}`} · 范围</summary>
          <p>版本：{current.version} · 适用市场：{current.markets.map((m) => MARKET_LABELS[m as keyof typeof MARKET_LABELS]).join("、")} · 覆盖地域：{current.regions.join("、")}</p></details>
          {versions.length > 1 && <label>报告版本<select aria-label="报告版本" value={current.version} onChange={(e) => update(current.topic, e.target.value)}>{versions.map((d) => <option key={d.id} value={d.version}>{d.version}{d.status === "withdrawn" ? " · 已撤回" : ""}</option>)}</select></label>}
        </header>
        {current.status === "withdrawn" && <p role="alert" className="publication-withdrawn">本报告已撤回：{current.withdrawalReason}</p>}
        {body.path !== path ? <p>正在读取正文…</p> : body.error ? <p role="alert">{body.error}</p> : <div className="markdown-document"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{h2: ({node, children}) => <h2 id={`section-${node?.position?.start.line}`}>{children}</h2>, a: ({href, children}) => { const link = documentLink(href); return link ? <a href={link}>{children}</a> : <span>{children}</span>; }}}>{body.text}</ReactMarkdown></div>}
        </>}
      </article>
    </div>}
  </main>;
}

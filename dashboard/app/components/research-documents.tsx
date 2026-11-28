"use client";

import { useEffect, useMemo, useState } from "react";
import { MARKET_LABELS } from "../lib/research";
import { CYCLE_STAGE_LABELS, MACRO_ALIGN_LABELS } from "../lib/decision-metrics.mjs";
import { loadPublicationDirectory, type PublishedDocument, type PublicationDirectory } from "../lib/publications";
import { initialIndustryRegion, industryRegion, industryTopicChoices } from "../lib/industry-view.mjs";
import { researchHeadings } from "../lib/research-headings.mjs";
import { IndustryIndicators } from "./industry-indicators";
import { ResearchMarkdown } from "./research-markdown";

type Region = "cn" | "archive";
type TopicChoice = { topic: string; label: string; publishedOn?: string; status?: PublishedDocument["status"] };

export function ResearchDocuments({ kind }: { kind: PublishedDocument["kind"] }) {
  const [directory, setDirectory] = useState<PublicationDirectory | null>(null);
  const documents = directory?.documents;
  const catalog = kind === "industry" ? directory?.industryCatalog : null;
  const [region, setRegion] = useState<Region>("cn");
  const [group, setGroup] = useState("");
  const [market, setMarket] = useState("all");
  const [type, setType] = useState<PublishedDocument["type"]>("report");
  const [topic, setTopic] = useState("");
  const [version, setVersion] = useState("");
  const [panel, setPanel] = useState("report");
  const [query, setQuery] = useState("");
  const [body, setBody] = useState({ path: "", text: "", error: "" });
  const [error, setError] = useState("");
  const label = kind === "industry" ? "行业研究" : "宏观与市场";
  const catalogMode = Boolean(catalog && region === "cn" && type === "report");

  useEffect(() => {
    const controller = new AbortController();
    loadPublicationDirectory(controller.signal).then((data) => {
      setDirectory(data);
      const params = new URLSearchParams(window.location.search);
      setTopic(params.get("topic") ?? ""); setVersion(params.get("version") ?? "");
      if ((params.get("market") ?? "") in MARKET_LABELS) setMarket(params.get("market")!);
      setPanel(params.get("panel") === "indicators" ? "indicators" : "report");
      if (kind === "industry") {
        setRegion(initialIndustryRegion(data, params));
        const requestedGroup = params.get("group");
        const selectedGroup = data.industryCatalog?.groups.some((item) => item.id === requestedGroup) ? requestedGroup
          : data.industryCatalog?.topics.find((item) => item.id === params.get("topic"))?.group;
        setGroup(selectedGroup ?? "");
      }
      const wanted = params.get("view");
      if (wanted === "report" || wanted === "reference") setType(wanted);
      else if (!data.documents.some((d) => d.kind === kind && d.type === "report")
        && data.documents.some((d) => d.kind === kind && d.type === "reference")) setType("reference");
    }).catch((reason: Error) => { if (reason.name !== "AbortError") setError(reason.message); });
    return () => controller.abort();
  }, [kind]);

  const available = (documents ?? []).filter((d) => d.kind === kind);
  const scoped = available.filter((d) => d.type === type
    && (kind !== "industry" || industryRegion(d) === region)
    && (catalogMode || market === "all" || d.markets.includes(market)))
    .sort((a, b) => b.publishedOn.localeCompare(a.publishedOn) || b.revision - a.revision);
  const latestTopics = [...new Map([...scoped].reverse().map((d) => [d.topic, d])).values()]
    .sort((a, b) => b.publishedOn.localeCompare(a.publishedOn) || b.revision - a.revision);
  const topics: TopicChoice[] = catalogMode && catalog
    ? industryTopicChoices(catalog, scoped, group, query).map((item: { id: string; label: string }) => {
      const latest = latestTopics.find((document) => document.topic === item.id);
      return { topic: item.id, label: item.label, publishedOn: latest?.publishedOn, status: latest?.status };
    })
    : latestTopics.filter((d) => `${d.title} ${d.summary} ${d.regions.join(" ")}`.toLowerCase().includes(query.trim().toLowerCase()))
      .map((d) => ({ topic: d.topic, label: d.title.split("：")[0], publishedOn: d.publishedOn, status: d.status }));
  const selectedTopic = topic || topics[0]?.topic;
  const selectedCatalogTopic = catalogMode ? catalog?.topics.find((item) => item.id === selectedTopic) : undefined;
  const versions = scoped.filter((d) => d.topic === selectedTopic);
  const current = version ? versions.find((d) => d.version === version) : versions[0];
  const path = current?.path;
  const indicatorPath = region === "cn" && current?.id === versions[0]?.id && current?.status === "published" ? current.indicatorPath : null;
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    fetch(path, { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("研究正文暂时无法读取"); return response.text(); })
      .then((text) => setBody({ path, text, error: "" }))
      .catch((reason: Error) => { if (reason.name !== "AbortError") setBody({ path, text: "", error: reason.message }); });
    return () => controller.abort();
  }, [path]);

  function update(nextTopic: string, nextVersion = "", nextType = type, nextMarket = market, nextRegion = region, nextGroup = group) {
    setTopic(nextTopic); setVersion(nextVersion); setType(nextType); setMarket(nextMarket); setRegion(nextRegion); setGroup(nextGroup); setPanel("report");
    const params = new URLSearchParams({ view: nextType });
    if (nextTopic) params.set("topic", nextTopic);
    if (nextVersion) params.set("version", nextVersion);
    if (kind === "industry") {
      params.set("region", nextRegion);
      if (nextRegion === "cn" && nextGroup) params.set("group", nextGroup);
    }
    if (nextMarket !== "all" && !(kind === "industry" && nextRegion === "cn")) params.set("market", nextMarket);
    window.history.replaceState(null, "", `${kind === "industry" ? "/industries" : "/macro"}?${params}`);
  }
  function showPanel(next: string) {
    setPanel(next);
    const params = new URLSearchParams(window.location.search);
    params.set("topic", current!.topic); params.set("view", type);
    if (kind === "industry") params.set("region", region);
    if (next === "indicators") params.set("panel", next); else params.delete("panel");
    window.history.replaceState(null, "", `${kind === "industry" ? "/industries" : "/macro"}?${params}`);
  }
  const markdown = body.path === path && !body.error ? body.text : "";
  const headings = useMemo(() => researchHeadings(markdown), [markdown]);
  const outline = headings.filter((heading) => heading.depth === 2);
  const reportCount = new Set(available.filter((d) => d.type === "report" && d.status === "published").map((d) => d.topic)).size;
  const archiveCount = new Set(available.filter((d) => d.type === "report" && industryRegion(d) === "archive").map((d) => d.topic)).size;
  const referenceCount = available.filter((d) => d.type === "reference" && d.status === "published").length;
  const showReader = Boolean(current || selectedCatalogTopic);
  const selectGroup = (id: string) => update("", "", "report", "all", "cn", id);

  return <main className="publication-workspace">
    <header className="publication-heading"><h1>{label}</h1><p>{kind === "industry" ? "中国行业的需求、供给、竞争与利润分配。" : "周期、资金条件与估值，及其对长期投资的影响。"}</p></header>
    <div className="publication-toolbar">
      <div className="publication-types" aria-label="内容类型">
        {kind === "industry" && catalog ? <>
          <button aria-pressed={region === "cn" && type === "report"} onClick={() => update("", "", "report", "all", "cn", "")}>中国行业 {catalog.topics.length}</button>
          <button aria-pressed={region === "archive" && type === "report"} onClick={() => update("", "", "report", "all", "archive", "")}>历史与海外 {archiveCount}</button>
        </> : <button aria-pressed={type === "report"} onClick={() => update("", "", "report")}>研究报告 {reportCount}</button>}
        {(referenceCount > 0 || type === "reference") && <button aria-pressed={type === "reference"} onClick={() => update("", "", "reference", "all", "archive", "")}>指标与方法 {referenceCount}</button>}
      </div>
      {!catalogMode && <select aria-label="适用市场" disabled={!documents} value={market} onChange={(e) => update("", "", type, e.target.value)}>{Object.entries(MARKET_LABELS).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select>}
      <input type="search" aria-label="搜索研究主题" placeholder="搜索主题、范围或判断" value={query} onChange={(e) => { setQuery(e.target.value); update(""); }} />
    </div>
    {catalogMode && catalog && <>
      <nav className="industry-group-nav" aria-label="行业大类"><button aria-pressed={!group} onClick={() => selectGroup("")}>全部</button>{catalog.groups.map((item) => <button key={item.id} aria-pressed={group === item.id} onClick={() => selectGroup(item.id)}>{item.label}</button>)}</nav>
      <select className="industry-mobile-groups" aria-label="行业大类" value={group} onChange={(e) => selectGroup(e.target.value)}><option value="">全部行业</option>{catalog.groups.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select>
    </>}
    {error ? <p role="alert">{error}</p> : !documents ? <p role="status">正在读取研究目录…</p> : !showReader ? <section className="publication-empty">
      <h2>{topic || version ? "未找到所选主题或版本" : type === "report" ? `暂无${kind === "industry" ? "行业" : "宏观"}研究报告` : "没有符合条件的参考文章"}</h2>
      <p>{topic || version ? "可清除筛选后查看现有主题。" : "调整分类或关键词，查看现有主题。"}</p>
      {(topic || version || query || market !== "all" || group) && <button onClick={() => { setQuery(""); update("", "", type, "all", region, ""); }}>查看全部主题</button>}
    </section> : <div className="publication-layout">
      <aside className="publication-sidebar">
        {topics.length > 1 && <select className="publication-mobile-topics" aria-label="选择研究主题" value={selectedTopic} onChange={(e) => update(e.target.value)}>{topics.map((d) => <option key={d.topic} value={d.topic}>{d.label}</option>)}</select>}
        {!(panel === "indicators" && indicatorPath) && outline.length > 3 && <details key={current?.id} className="publication-outline"><summary>本文目录</summary><nav aria-label="本文目录">{outline.map((item) => <a key={item.id} href={`#${item.id}`}>{item.label}</a>)}</nav></details>}
        <nav aria-label="研究主题" className="publication-list">{topics.map((d) => <button key={d.topic} title={d.label} aria-label={d.label} aria-current={d.topic === selectedTopic ? "true" : undefined} onClick={() => update(d.topic)}><strong>{d.label}</strong>{d.publishedOn && <span>{d.publishedOn}{d.status === "withdrawn" ? " · 已撤回" : ""}</span>}</button>)}</nav>
      </aside>
      <article className="research-document-body" aria-live="polite">
        {!current ? <section className="publication-topic-empty"><h2>{version ? "未找到所选主题或版本" : selectedCatalogTopic?.label}</h2><p>{selectedCatalogTopic?.scope}</p>{!version && <p>暂无已发布研究。</p>}</section> : <>
          {indicatorPath && <div className="publication-panel-switch" role="group" aria-label="主题内容"><button aria-pressed={panel !== "indicators"} onClick={() => showPanel("report")}>完整研究</button><button aria-pressed={panel === "indicators"} onClick={() => showPanel("indicators")}>行业指标</button></div>}
          {panel === "indicators" && indicatorPath ? <IndustryIndicators key={indicatorPath} path={indicatorPath}/> : <>
            <header className="publication-meta"><details><summary>{current.type === "report" ? `资料截止 ${current.informationCutoff}` : `指标与方法 · ${current.publishedOn}`} · 范围</summary>
              <p>版本：{current.version} · 适用市场：{current.markets.map((m) => MARKET_LABELS[m as keyof typeof MARKET_LABELS]).join("、")} · 覆盖地域：{current.regions.join("、")}</p>{selectedCatalogTopic && <p>{selectedCatalogTopic.scope}</p>}</details>
              {kind === "industry" && <span className="publication-reading-area">{region === "cn" ? "中国行业研究" : "历史与海外研究"}</span>}
              {kind === "industry" && current.industryState && <span className={`decision-pill align-${current.industryState.macroAlignment}`}>{CYCLE_STAGE_LABELS[current.industryState.cycleStage]} · {MACRO_ALIGN_LABELS[current.industryState.macroAlignment]}{current.industryState.inflectionCandidate ? " · 拐点雷达" : ""}</span>}
              {versions.length > 1 && <label>报告版本<select aria-label="报告版本" value={current.version} onChange={(e) => update(current.topic, e.target.value)}>{versions.map((d) => <option key={d.id} value={d.version}>{d.version}{d.status === "withdrawn" ? " · 已撤回" : ""}</option>)}</select></label>}
            </header>
            {current.status === "withdrawn" && <p role="alert" className="publication-withdrawn">本报告已撤回：{current.withdrawalReason}</p>}
            {body.path !== path ? <p>正在读取正文…</p> : body.error ? <p role="alert">{body.error}</p> : <div className="markdown-document"><ResearchMarkdown markdown={markdown} sourcePath={current.sourcePath} headings={headings} links={directory ?? {}} /></div>}
          </>}
        </>}
      </article>
    </div>}
  </main>;
}

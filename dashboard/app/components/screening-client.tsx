"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import "../screening.css";

type Source = { title: string; url: string };
type Metrics = { as_of: string; basis: string; items: { label: string; value: string; period: string; source: number }[];
  history: { period: string; value: string }[]; history_metric: string | null; history_source: number | null; note: string };
type Card = { symbol: string; name: string; industry: string; tier: string; group: string; issuer?: string;
  moat: string; owner_cash: string; risks: string; tier_reason: string; research_question?: string; metrics?: Metrics; sources: Source[] };
type Exclusion = { symbol: string; name: string; reason: string };
type Pool = { market: string; label: string; asOf: string; universeCount: number; companies: Card[]; exclusions: Exclusion[]; hasExclusions: boolean;
  review: { scope_note: string; omission_check: string; admission_check: string; reviewed_symbols: string[] } };
type Data = { schemaVersion: number; pools: Pool[] };
type Row = Card & { marketLabel: string; market: string; asOf: string; listings: string[] };
const tiers: Record<string, string> = { core_moat: "A · 核心护城河", quality_research: "B · 质量研究" };
const groupNames: Record<string, string> = { consumer_brand_network: "消费与服务", technology_industrial: "科技与工业",
  healthcare_platform: "医疗与健康", infrastructure_finance_resource: "金融与基础资产" };
function readerText(value: string) { return value.replace(/^(?:保留[AB]|由[AB]转[AB])[:：]\s*/u, ""); }
function csvCell(value: string) { return `"${(/^[=+@-]/u.test(value) ? "'" + value : value).replaceAll('"', '""')}"`; }

export function ScreeningClient() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const [market, setMarket] = useState("all");
  const [tier, setTier] = useState("all");
  const [group, setGroup] = useState("all");
  const [industry, setIndustry] = useState("all");
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("selected");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [mobile, setMobile] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const detailPanel = useRef<HTMLElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/data/screening-pools.json", { signal: controller.signal }).then(async (response) => {
      if (!response.ok) throw new Error("公司资料暂时无法读取，请刷新重试。");
      const result: Data = await response.json();
      if (result.schemaVersion !== 1 || !Array.isArray(result.pools)) throw new Error("公司资料格式不正确。");
      setData(result);
      const params = new URLSearchParams(window.location.search);
      if (["cn-a", "hk", "us"].includes(params.get("market") ?? "")) setMarket(params.get("market")!);
      if (Object.keys(tiers).includes(params.get("tier") ?? "")) setTier(params.get("tier")!);
      setQuery(params.get("q") ?? "");
      if (Object.keys(groupNames).includes(params.get("group") ?? "")) setGroup(params.get("group")!);
      if (params.get("industry")) setIndustry(params.get("industry")!);
      if (params.get("view") === "excluded" && result.pools.some((pool) => pool.hasExclusions
        && (!params.get("market") || params.get("market") === "all" || pool.market === params.get("market")))) setMode("excluded");
      setSelected(params.get("company"));
    }).catch((reason: Error) => { if (reason.name !== "AbortError") setError(reason.message); });
    const media = window.matchMedia("(max-width: 900px)");
    const update = () => setMobile(media.matches);
    update(); media.addEventListener("change", update);
    return () => { controller.abort(); media.removeEventListener("change", update); };
  }, []);
  useEffect(() => {
    if (!data) return;
    const params = new URLSearchParams();
    if (market !== "all") params.set("market", market);
    if (tier !== "all") params.set("tier", tier);
    if (query) params.set("q", query);
    if (group !== "all") params.set("group", group);
    if (industry !== "all") params.set("industry", industry);
    if (mode === "excluded") params.set("view", mode);
    if (selected) params.set("company", selected);
    window.history.replaceState(null, "", `/screening${params.size ? "?" + params.toString() : ""}`);
  }, [data, market, tier, query, selected, group, industry, mode]);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key === "/" && !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName ?? "") && !dialog.current?.open) {
        event.preventDefault(); searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", key); return () => window.removeEventListener("keydown", key);
  }, []);
  const pools = useMemo(() => data?.pools.filter((pool) => market === "all" || pool.market === market) ?? [], [data, market]);
  const supportsExclusions = pools.some((pool) => pool.hasExclusions);
  const allRows = useMemo(() => {
    const rows = new Map<string, Row>();
    for (const pool of pools) for (const company of pool.companies) {
      const key = market === "all" ? company.issuer ?? company.symbol : company.symbol;
      const existing = rows.get(key);
      if (existing) {
        const listings = [...existing.listings, `${pool.label} ${company.symbol}`];
        if (!existing.metrics && company.metrics) rows.set(key, { ...company, market: pool.market, marketLabel: pool.label, asOf: pool.asOf, listings });
        else existing.listings = listings;
      }
      else rows.set(key, { ...company, market: pool.market, marketLabel: pool.label, asOf: pool.asOf, listings: [`${pool.label} ${company.symbol}`] });
    }
    return [...rows.values()].sort((a,b) => a.tier.localeCompare(b.tier) || a.symbol.localeCompare(b.symbol));
  }, [pools, market]);
  const matchingGroup = allRows.filter((row) => group === "all" || row.group === group);
  const industries = [...new Set(matchingGroup.map((row) => row.industry))].sort((a,b) => a.localeCompare(b,"zh-CN"));
  const filtered = matchingGroup.filter((row) => (tier === "all" || row.tier === tier) && (industry === "all" || row.industry === industry)
    && [row.symbol, row.name, row.industry, row.moat, row.risks, row.research_question, ...row.listings].join(" ").toLowerCase().includes(query.trim().toLowerCase()));
  const excluded = pools.flatMap((pool) => pool.exclusions.map((item) => ({ ...item, marketLabel: pool.label })))
    .filter((row) => [row.symbol,row.name,row.reason].join(" ").toLowerCase().includes(query.trim().toLowerCase()));
  const active = allRows.find((row) => row.symbol === selected || row.issuer === selected || row.listings.some((listing) => listing.endsWith(selected ?? "!")));
  const activeExcluded = excluded.find((row) => row.symbol === selected);
  const hasDetail = mode === "selected" ? Boolean(active) : Boolean(activeExcluded);
  useEffect(() => {
    if (mobile && hasDetail) { if (!dialog.current?.open) dialog.current?.showModal(); }
    else dialog.current?.close();
  }, [mobile, hasDetail, selected]);
  useEffect(() => {
    detailPanel.current?.scrollTo({ top: 0, behavior: "instant" });
    dialog.current?.scrollTo({ top: 0, behavior: "instant" });
  }, [selected]);
  function resetResults() { setPage(0); setSelected(null); }
  function clear() { setTier("all"); setGroup("all"); setIndustry("all"); setQuery(""); resetResults(); }
  function changeMarket(next: string) {
    setMarket(next); setIndustry("all"); resetResults();
    if (next !== "all" && !data?.pools.find((pool) => pool.market === next)?.hasExclusions) setMode("selected");
  }
  const total = mode === "selected" ? filtered.length : excluded.length;
  const pages = Math.max(1, Math.ceil(total / 30));
  function download() {
    const rows = mode === "selected" ? [["公司", "证券", "行业", "层级", "初筛理由", "关键问题", "反证"],
      ...filtered.map((c) => [c.name,c.listings.join("；"),c.industry,tiers[c.tier],readerText(c.tier_reason),c.research_question ?? "",c.risks])]
      : [["公司", "证券", "未纳入理由"], ...excluded.map((c) => [c.name,c.symbol,c.reason])];
    const url = URL.createObjectURL(new Blob(["\uFEFF" + rows.map((row) => row.map(csvCell).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = "company-screening.csv"; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const detail = active && mode === "selected" ? <>
    <div className="pool-detail-heading"><span className={`pool-tier ${active.tier}`}>{tiers[active.tier]}</span><button type="button" onClick={() => setSelected(null)} aria-label="关闭公司详情">×</button></div>
    <h2>{active.name}</h2><p className="pool-detail-meta">{active.industry} · {active.listings.join(" / ")}</p>
    <p className="pool-detail-thesis">{readerText(active.tier_reason)}</p>
    {active.research_question && <section className="pool-question"><h3>关键研究问题</h3><p>{active.research_question}</p></section>}
    {active.metrics && <section className="pool-metrics"><h3>经营与资本</h3><div className="pool-metric-grid">{active.metrics.items.map((item) => <div key={item.label}><span>{item.label}</span><strong>{item.value}</strong><small>{item.period}</small></div>)}</div>
      {active.metrics.history.length > 0 && <details className="pool-history"><summary>{active.metrics.history_metric} · 年度记录</summary><div>{[...active.metrics.history].reverse().map((item) => <span key={item.period}><small>{item.period}</small><strong>{item.value}</strong></span>)}</div></details>}
      <details className="pool-metric-note"><summary>指标口径</summary><p>{active.metrics.note}</p><p>{active.metrics.basis} · 核对 {active.metrics.as_of}</p>
        <ul>{[...new Set(active.metrics.items.map((item) => item.source))].map((index) => <li key={index}><a href={active.sources[index].url} target="_blank" rel="noreferrer">{active.sources[index].title} ↗</a></li>)}</ul></details></section>}
    <section className="pool-judgment"><h3>竞争优势</h3><p>{active.moat}</p><h3>股东现金</h3><p>{active.owner_cash}</p><h3>主要反证</h3><p>{active.risks}</p></section>
    <details className="pool-sources"><summary>资料来源 · {active.sources.length}</summary><ul>{active.sources.map((source) => <li key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a></li>)}</ul></details>
    <p className="pool-detail-meta">判断更新 {active.asOf}</p>
  </> : activeExcluded ? <><div className="pool-detail-heading"><span>未纳入</span><button type="button" onClick={() => setSelected(null)} aria-label="关闭公司详情">×</button></div><h2>{activeExcluded.name}</h2><p className="pool-detail-meta">{activeExcluded.marketLabel} · {activeExcluded.symbol}</p><h3>筛选判断</h3><p>{activeExcluded.reason}</p></> : <div className="pool-detail-empty"><span>研究笔记</span><h2>选择一家公司</h2><p>查看经营指标、竞争优势与需要进一步回答的问题。</p></div>;
  if (error) return <main className="company-pool"><h1>商业质量池</h1><p role="alert">{error}</p></main>;
  if (!data) return <main className="company-pool"><h1>商业质量池</h1><p>正在读取公司资料…</p></main>;
  const uniqueCount = new Set(data.pools.flatMap((pool) => pool.companies.map((c) => c.issuer ?? c.symbol))).size;
  return <main className="company-pool">
    <header className="pool-heading"><div><p className="pool-eyebrow">COMPANY RESEARCH</p><h1>商业质量池</h1><p>寻找竞争优势能够持续转化为股东现金的企业。</p></div><div className="pool-heading-actions"><span><strong>{uniqueCount}</strong> 家公司</span><button type="button" onClick={download}>导出当前列表 ↓</button></div></header>
    <div className="pool-market-bar"><nav aria-label="市场筛选"><button type="button" aria-pressed={market === "all"} onClick={() => changeMarket("all")}>全部市场</button>{data.pools.map((pool) => <button type="button" key={pool.market} aria-pressed={market === pool.market} onClick={() => changeMarket(pool.market)}>{pool.label}<span>{pool.companies.length}</span></button>)}</nav>
      <details className="pool-method"><summary>筛选方法与范围</summary><div><h2>长期商业质量</h2><p>A · 核心护城河：优势与普通股现金有多年兑现。B · 质量研究：优势已商业化，仍有决定性问题需要验证。</p><p>结合客户选择、资本效率、必要投入、现金归属和治理判断。价格吸引力在公司估值中另行讨论。</p>
        {pools.map((pool) => <section key={pool.market}><h3>{pool.label} · 更新 {pool.asOf}</h3><p>{pool.review.scope_note}</p><p>复核 {pool.review.reviewed_symbols.length} 个证券条目 · 入选 {pool.companies.length}</p></section>)}
        <p>全部市场按发行人合并A/H等多地上市记录；单一市场保留该市场证券。财务期间见各项指标，访问日与财务期末分别阅读。</p></div></details></div>
    <div className="pool-toolbar"><label className="pool-search"><span className="sr-only">搜索公司或关键问题</span><input ref={searchRef} type="search" value={query} placeholder="搜索公司、代码或关键问题" onChange={(e) => { setQuery(e.target.value); resetResults(); }}/><kbd>/</kbd></label>
      <label><span className="sr-only">质量层级</span><select disabled={mode !== "selected"} value={tier} onChange={(e) => { setTier(e.target.value); resetResults(); }}><option value="all">全部层级</option>{Object.entries(tiers).map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      <label><span className="sr-only">业务领域</span><select disabled={mode !== "selected"} value={group} onChange={(e) => { setGroup(e.target.value); setIndustry("all"); resetResults(); }}><option value="all">全部领域</option>{Object.entries(groupNames).map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      <label><span className="sr-only">行业</span><select disabled={mode !== "selected"} value={industry} onChange={(e) => { setIndustry(e.target.value); resetResults(); }}><option value="all">全部行业</option>{industries.map((name) => <option key={name}>{name}</option>)}</select></label>
      <button type="button" className="pool-reset" onClick={clear}>重置</button></div>
    <div className="pool-list-bar"><div role="tablist" aria-label="筛选结果"><button role="tab" aria-selected={mode === "selected"} onClick={() => { setMode("selected"); resetResults(); }}>入选公司</button>{supportsExclusions && <button role="tab" aria-selected={mode === "excluded"} onClick={() => { setMode("excluded"); resetResults(); }}>未纳入</button>}</div><p role="status">{total} 家{mode === "selected" ? ` · A ${filtered.filter((c) => c.tier === "core_moat").length} / B ${filtered.filter((c) => c.tier === "quality_research").length}` : ` · ${pools.filter((pool) => pool.hasExclusions).map((pool) => pool.label).join(" / ")}`}</p></div>
    <div className="pool-workbench"><section className="pool-list" aria-label="公司筛选结果"><div className="pool-table-scroll"><table><thead><tr><th>公司</th>{mode === "selected" && <th className="pool-col-tier">层级</th>}<th>{mode === "selected" ? "初筛理由" : "未纳入理由"}</th>{mode === "selected" && <th className="pool-col-metric">经营指标</th>}</tr></thead><tbody>
      {mode === "selected" ? filtered.slice(page*30,(page+1)*30).map((row) => <tr key={row.symbol} data-symbol={row.symbol} className={active?.symbol === row.symbol ? "is-selected" : ""}><td><button type="button" aria-label={`查看 ${row.name}`} aria-pressed={active?.symbol === row.symbol} onClick={() => setSelected(row.symbol)}><strong>{row.name}</strong><span>{row.symbol} · {row.industry}</span>{row.listings.length > 1 && <small>{row.listings.map((l) => l.split(" ")[0]).join(" / ")}</small>}</button></td><td className="pool-col-tier"><span className={`pool-tier ${row.tier}`}>{row.tier === "core_moat" ? "A" : "B"}</span></td><td className="pool-reason">{readerText(row.tier_reason)}</td><td className="pool-col-metric">{row.metrics ? <>{row.metrics.items.slice(0,2).map((item) => <div key={item.label}><span>{item.label}</span><strong>{item.value}</strong></div>)}<small className="pool-period">{[...new Set(row.metrics.items.slice(0,2).map((item) => item.period))].join(" · ")}</small></> : <span className="pool-muted">见判断详情</span>}</td></tr>)
      : excluded.slice(page*30,(page+1)*30).map((row) => <tr key={row.symbol} data-symbol={row.symbol} className={row.symbol === selected ? "is-selected" : ""}><td><button type="button" aria-label={`查看 ${row.name}`} onClick={() => setSelected(row.symbol)}><strong>{row.name}</strong><span>{row.symbol}</span></button></td><td className="pool-reason">{row.reason}</td></tr>)}
    </tbody></table>{!total && <div className="pool-empty"><h2>没有符合条件的公司</h2><p>调整市场、行业或关键词继续查找。</p><button type="button" onClick={clear}>清除筛选条件</button></div>}</div>
      <footer className="pool-pagination"><span>{total ? page*30+1 : 0}–{Math.min((page+1)*30,total)} / {total}</span><div><button disabled={page === 0} type="button" onClick={() => setPage(page-1)}>上一页</button><span>{page+1} / {pages}</span><button disabled={page+1 >= pages} type="button" onClick={() => setPage(page+1)}>下一页</button></div></footer></section>
      {!mobile && <aside ref={detailPanel} className="pool-detail" aria-label="公司判断详情">{detail}</aside>}</div>
    {mobile && <dialog ref={dialog} className="pool-detail pool-dialog" onCancel={() => setSelected(null)} onClose={() => setSelected(null)}>{detail}</dialog>}
  </main>;
}

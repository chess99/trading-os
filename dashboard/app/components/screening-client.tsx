"use client";
import { useEffect, useState } from "react";
import "../screening.css";

type Card = { symbol: string; name: string; industry: string; tier: string; group: string;
  moat: string; owner_cash: string; risks: string; tier_reason: string; sources: { title: string; url: string }[] };
type Pool = { market: string; label: string; scope: string; asOf: string; philosophy: string;
  universeCount: number; companies: Card[]; review: { scope_note: string; omission_check: string; admission_check: string; reviewed_symbols: string[] } };
type Data = { schemaVersion: number; pools: Pool[] };
const tiers: Record<string, string> = { core_moat: "A · 核心护城河", quality_research: "B · 质量研究" };
export function ScreeningClient() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const [market, setMarket] = useState("all");
  const [tier, setTier] = useState("all");
  const [industry, setIndustry] = useState("all");
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(24);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/data/screening-pools.json", { signal: controller.signal }).then(async (response) => {
      if (!response.ok) throw new Error("筛选资料暂时无法读取，请刷新重试。");
      const result: Data = await response.json();
      if (result.schemaVersion !== 1 || !Array.isArray(result.pools)) throw new Error("筛选资料格式不正确。");
      setData(result);
    }).catch((reason: Error) => { if (reason.name !== "AbortError") setError(reason.message); });
    return () => controller.abort();
  }, []);
  if (error) return <main className="screening-workspace"><h1>第一层筛选</h1><p role="alert">{error}</p></main>;
  if (!data) return <main className="screening-workspace"><h1>第一层筛选</h1><p>正在读取各市场判断卡…</p></main>;
  const pools = data.pools.filter((pool) => market === "all" || pool.market === market);
  const all = pools.flatMap((pool) => pool.companies.map((company) => ({ ...company, market: pool.market, marketLabel: pool.label, asOf: pool.asOf })));
  const industries = [...new Set(all.map((company) => company.industry))].sort((a,b) => a.localeCompare(b,"zh-CN"));
  const filtered = all.filter((company) => (tier === "all" || company.tier === tier) && (industry === "all" || company.industry === industry)
    && [company.symbol, company.name, company.industry, company.moat, company.risks, company.tier_reason].join(" ").toLowerCase().includes(query.trim().toLowerCase()));
  function clear() { setMarket("all"); setTier("all"); setIndustry("all"); setQuery(""); setLimit(24); }
  return <main className="screening-workspace">
    <header className="screening-hero"><div><span className="screening-eyebrow">01 / LONG-TERM BUSINESS QUALITY</span>
      <h1>把视野放到五至十年</h1><p>先理解竞争优势如何变成普通股现金，再决定哪些公司值得继续研究。</p>
      <div className="screening-stage"><strong>第一层 · 商业质量筛选</strong><span>第二层 · 公司深研</span><span>第三层 · 长期精选</span></div>
    </div><aside><strong>A股 / 港股 / 美股</strong><p>港美股采用小范围精选样本。<br />本轮完成筛选，暂不开展公司深研。</p><a href="/data/screening-pools.json" download>下载完整判断卡 JSON ↗</a></aside></header>
    <section className="screening-markets" aria-label="市场范围">
      <button type="button" aria-pressed={market === "all"} onClick={() => { setMarket("all"); setIndustry("all"); setLimit(24); }}><span>全部市场</span><strong>{data.pools.reduce((sum,pool) => sum + pool.companies.length,0)}</strong><small>已入选证券 · 各池分别复核</small></button>
      {data.pools.map((pool) => <button type="button" key={pool.market} aria-pressed={market === pool.market} onClick={() => { setMarket(pool.market); setIndustry("all"); setLimit(24); }}>
        <span>{pool.label}</span><strong>{pool.companies.length}</strong><small>{pool.scope} · {pool.asOf}</small></button>)}
    </section>
    <section className="screening-method"><h2>用同一标准，尊重不同商业模式</h2><p>A 层：优势与现金已有多年支持，仍须持续检验反证。B 层：优势已商业化，但有明确未决问题。分层不表达价格吸引力。</p>
      <p>筛选复核日期与财务资料期间分别阅读；来源标题注明已读材料。港美股不会因入池自动进入公司研究队列。</p></section>
    <div className="screening-filters"><label>搜索公司或关键问题<input type="search" value={query} placeholder="名称、代码、AI、现金…" onChange={(event) => { setQuery(event.target.value); setLimit(24); }} /></label>
      <label>质量层级<select value={tier} onChange={(event) => { setTier(event.target.value); setLimit(24); }}><option value="all">全部层级</option>{Object.entries(tiers).map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      <label>行业<select value={industry} onChange={(event) => { setIndustry(event.target.value); setLimit(24); }}><option value="all">全部行业</option>{industries.map((name) => <option key={name}>{name}</option>)}</select></label><button type="button" onClick={clear}>重置筛选</button>
    </div>
    <p className="screening-result-count" role="status">当前 {filtered.length} 家 · A {filtered.filter((c) => c.tier === "core_moat").length} / B {filtered.filter((c) => c.tier === "quality_research").length} · 展开阅读判断与来源</p>
    <section className="screening-cards" aria-label="公司筛选判断">
      {filtered.slice(0,limit).map((company) => <article className="screening-card" key={company.symbol} data-symbol={company.symbol}>
        <div className="screening-card-top"><span>{company.marketLabel} · {company.symbol}</span><span className={company.tier === "core_moat" ? "tier-a" : "tier-b"}>{tiers[company.tier]}</span></div>
        <h2>{company.name}</h2><p className="screening-meta">{company.industry} · 筛选复核 {company.asOf}</p>
        <p className="screening-thesis">{company.tier_reason}</p>
        <details><summary>竞争优势、现金与反证</summary><dl>
          <dt>竞争优势</dt><dd>{company.moat}</dd><dt>普通股现金</dt><dd>{company.owner_cash}</dd><dt>主要反证</dt><dd>{company.risks}</dd>
        </dl><h3>已读材料与公开来源</h3><ul>{company.sources.map((source) => <li key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a></li>)}</ul>
        <p className="screening-meta">本卡是第一层商业质量判断，不代表已完成公司深研。</p></details>
      </article>)}
    </section>
    {!filtered.length && <div className="screening-empty"><h2>没有符合条件的公司</h2><p>试试其他市场、行业或关键词。</p><button type="button" onClick={clear}>清除筛选条件</button></div>}
    {filtered.length > limit && <button className="screening-more" type="button" onClick={() => setLimit(limit + 24)}>再显示 24 家（尚余 {filtered.length - limit} 家）</button>}
    <section className="screening-scope"><h2>本轮覆盖到哪里</h2><p>以下为各市场池的原始范围说明。未覆盖公司不等同于被否决；A股本轮沿用原池。</p>
      {pools.map((pool) => <details key={pool.market}><summary>{pool.label} · 入选 {pool.companies.length} / 身份范围 {pool.universeCount} · 复核 {pool.asOf}</summary>
        <p>{pool.review.scope_note}</p><p><strong>遗漏检查：</strong>{pool.review.omission_check}</p><p><strong>误入检查：</strong>{pool.review.admission_check}</p></details>)}
    </section>
  </main>;
}

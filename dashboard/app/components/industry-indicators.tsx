"use client";

import { useEffect, useId, useState } from "react";

type Point = { period: string; value: number | null; sourceId: string; note?: string };
type Series = { id: string; label: string; unit: string; frequency: string; definition: string; interpretation: string; points: Point[] };
type Source = { id: string; title: string; publisher: string; url: string; publishedOn: string; shortTitle?: string };
type Ranking = { id: string; label: string; period: string; frequency: string; definition: string; note?: string; sourceId: string; items: { name: string; share: number; volumeGWh?: number }[] };
type Indicators = { schemaVersion: number; topic: string; title: string; checkedOn: string; reviewAfter: string; scopeNote: string; releaseLinks: string[]; headlines: string[]; monthlyReports?: { period: string; analysisId: string; deepId?: string; nevDeepId?: string }[]; series: Series[]; sources: Source[]; rankings: Ranking[] };
const format = (v: number | null) => v === null ? "未取得" : v.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
const periodLabel = (period: string, frequency: string) => frequency === "ytd" ? `${period.slice(0,4)}年1—${Number(period.slice(5))}月累计` : frequency === "annual" ? `${period}年` : `${period.slice(0,4)}年${Number(period.slice(5))}月`;

function Trend({ series }: { series: Series }) {
  const titleId = useId();
  const values = series.points.flatMap((p) => p.value === null ? [] : [p.value]);
  const min = Math.min(...values, 0) * 1.12;
  const max = Math.max(...values, 1) * 1.12;
  const x = (i: number) => 80 + i * 532 / Math.max(series.points.length - 1, 1);
  const y = (v: number) => 204 - (v-min) / (max-min) * 170;
  const last = series.points.at(-1);
  return <figure className="indicator-chart">
    <figcaption>{series.label} <span>单位：{series.unit} · {series.frequency === "ytd" ? "年初至当月累计" : series.frequency === "annual" ? "全年" : "单月"}</span></figcaption>
    <svg viewBox="0 0 640 245" role="img" aria-labelledby={titleId}>
      <title id={titleId}>{series.label}趋势，{series.points[0]?.period}至{last?.period}，最新值{format(last?.value ?? null)}{series.unit}。精确值与来源见下方表格。</title>
      {[0, .5, 1].map((t) => <g key={t}><line x1="80" x2="616" y1={y(min+(max-min)*t)} y2={y(min+(max-min)*t)} stroke="currentColor" opacity="0.15"/><text x="70" y={y(min+(max-min)*t)+4} textAnchor="end">{format(Math.round(min+(max-min)*t))}</text></g>)}
      {series.points.map((p,i) => {
        const before = series.points[i-1];
        return <g key={p.period}>
          {p.value !== null && before?.value != null && <line x1={x(i-1)} x2={x(i)} y1={y(before.value)} y2={y(p.value)} className="indicator-trend-line"/>}
          {p.value !== null && <circle cx={x(i)} cy={y(p.value)} r="4" className="indicator-trend-point"><title>{p.period}：{format(p.value)}{series.unit}</title></circle>}
          {(i === 0 || i === series.points.length-1 || i === Math.floor((series.points.length-1)/2)) && <text x={x(i)} y="229" textAnchor={i === 0 ? "start" : i === series.points.length-1 ? "end" : "middle"}>{p.period}</text>}
        </g>;
      })}
    </svg>
  </figure>;
}

export function IndustryIndicators({ path }: { path: string }) {
  const [result, setResult] = useState<{ path: string; data?: Indicators; error?: string }>({ path: "" });
  const [selected, setSelected] = useState("");
  const [rankingId, setRankingId] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetch(path, { signal: controller.signal }).then((r) => { if (!r.ok) throw new Error("行业指标暂时无法读取"); return r.json(); })
      .then((data: Indicators) => { if (data.schemaVersion !== 1 || !Array.isArray(data.series)) throw new Error("行业指标格式错误"); setResult({path, data}); })
      .catch((e: Error) => { if (e.name !== "AbortError") setResult({path, error:e.message}); });
    return () => controller.abort();
  }, [path]);
  if (result.path !== path) return <p role="status">正在读取行业指标…</p>;
  if (result.error || !result.data) return <p role="alert">{result.error ?? "行业指标暂时无法读取"}</p>;
  const data = result.data;
  const series = data.series.find((s) => s.id === selected) ?? data.series[0];
  const ranking = data.rankings.find((r) => r.id === rankingId) ?? data.rankings[0];
  const sources = new Map(data.sources.map((s) => [s.id, s]));
  const today = new Intl.DateTimeFormat("en-CA", {timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
  const due = today >= data.reviewAfter;
  return <section className="industry-indicators" aria-label="行业运行指标">
    <header><h2>{data.title}</h2><p>资料核验 {data.checkedOn}{due ? " · 已到复核期" : ""}</p></header>
    {due && <p className="indicator-update-notice">当前显示已核验资料。建议复核日期 {data.reviewAfter} 已到，请以各发布机构的新月报确认最新状态。</p>}
    <div className="indicator-headlines">{data.headlines.map((id) => {
      const s = data.series.find((v) => v.id === id)!; const p = s.points.at(-1)!;
      return <button key={id} aria-pressed={series.id === id} onClick={() => setSelected(id)}><span>{s.label}</span><strong>{format(p.value)}<small>{p.value === null ? "" : s.unit}</small></strong><span>{periodLabel(p.period,s.frequency)}</span></button>;
    })}</div>
    <div className="indicator-release-links" aria-label="正式月报入口">{data.releaseLinks.map((id)=>{const source=sources.get(id)!;return <a key={id} href={source.url} target="_blank" rel="noreferrer">{source.shortTitle ?? source.title}<small>{source.publishedOn} · {source.publisher.replace("中国汽车流通协会乘用车市场信息联席分会", "乘联分会")}</small></a>;})}</div>
    <details className="indicator-evidence"><summary>统计范围与口径</summary><p className="indicator-scope">{data.scopeNote}</p></details>
    <label className="indicator-selector">趋势指标<select aria-label="趋势指标" value={series.id} onChange={(e)=>setSelected(e.target.value)}>{data.series.map((s)=><option key={s.id} value={s.id}>{s.label} · {s.frequency === "annual" ? "年度" : s.frequency === "ytd" ? "累计" : "月度"}</option>)}</select></label>
    <p className="indicator-definition">{series.definition}</p>
    <Trend series={series}/>
    <p>{series.interpretation}</p>
    <details className="indicator-evidence"><summary>查看数据与来源</summary><div className="indicator-table"><table><thead><tr><th>观察期</th><th>{series.label}（{series.unit}）</th><th>发布日与来源</th></tr></thead><tbody>{[...series.points].reverse().map((p)=>{const source=sources.get(p.sourceId)!;return <tr key={p.period}><td>{periodLabel(p.period,series.frequency)}</td><td>{format(p.value)}{p.note && <small>{p.note}</small>}</td><td><a href={source.url} target="_blank" rel="noreferrer">{source.publisher} · {source.publishedOn}</a></td></tr>;})}</tbody></table></div></details>
    {ranking && <label className="indicator-selector indicator-ranking-selector">电池企业份额<select aria-label="选择份额统计" value={ranking.id} onChange={(e)=>setRankingId(e.target.value)}>{data.rankings.map((r)=><option key={r.id} value={r.id}>{r.label} · {periodLabel(r.period,r.frequency)}</option>)}</select></label>}
    <div className="indicator-rankings">{(ranking ? [ranking] : []).map((r)=>{const source=sources.get(r.sourceId)!;return <section key={r.id}><h3>{r.label}</h3><p>{periodLabel(r.period,r.frequency)} · {r.definition}</p><div className="indicator-table"><table><thead><tr><th>企业</th><th>份额</th><th>装车电量</th></tr></thead><tbody>{r.items.map((row)=><tr key={row.name}><td>{row.name}</td><td><span className="share-track"><span style={{width:`${row.share}%`}}/></span>{format(row.share)}%</td><td>{row.volumeGWh === undefined ? "—" : `${format(row.volumeGWh)} GWh`}</td></tr>)}</tbody></table></div>{r.note && <p>{r.note}</p>}<a href={source.url} target="_blank" rel="noreferrer">{source.publisher} · {source.publishedOn}</a></section>;})}</div>
    {!!data.monthlyReports?.length && <details className="indicator-evidence"><summary>历月正式报告</summary><div className="indicator-table"><table><thead><tr><th>月份</th><th>市场分析</th><th>深度分析</th><th>新能源专题</th></tr></thead><tbody>{[...data.monthlyReports].reverse().map((r)=><tr key={r.period}><td>{r.period}</td>{[r.analysisId,r.deepId,r.nevDeepId].map((id,i)=><td key={i}>{id ? <a href={sources.get(id)!.url} target="_blank" rel="noreferrer">{sources.get(id)!.publishedOn}</a> : "—"}</td>)}</tr>)}</tbody></table></div></details>}
    <details className="indicator-evidence"><summary>数据来源与更新范围</summary><p>月度指标与完整行业研究分别更新。图表显示已核验数据；没有公布的月份不填入估算值。建议下次复核：{data.reviewAfter}。</p><ul>{data.sources.map((s)=><li key={s.id}><a href={s.url} target="_blank" rel="noreferrer">{s.title}</a> · {s.publisher} · {s.publishedOn}</li>)}</ul></details>
  </section>;
}

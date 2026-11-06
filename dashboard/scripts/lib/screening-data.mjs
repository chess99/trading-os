import { readFile } from "node:fs/promises";
import { join } from "node:path";

export const screeningMarkets = [
  { id: "cn-a", label: "A股", prefix: /^CN:[0-9]{6}$/u, scope: "A股" },
  { id: "hk", label: "港股", prefix: /^HK:[0-9]{5}$/u, scope: "港股" },
  { id: "us", label: "美股", prefix: /^US:[A-Z]{1,5}(?:[.-][A-Z])?$/u, scope: "美股" },
];
export function projectScreeningPool(pool, market) {
  if (![2, 3].includes(pool.schema_version) || !Array.isArray(pool.companies) || !pool.universe?.securities
    || !Array.isArray(pool.review?.reviewed_symbols) || !pool.review.scope_note || !pool.as_of) {
    throw new Error(`${market.id}筛选池格式不正确`);
  }
  const identities = pool.universe.securities;
  for (const symbol of Object.keys(identities)) if (!market.prefix.test(symbol)) throw new Error(`市场代码不匹配: ${symbol}`);
  const seen = new Set();
  const keys = ["symbol", "name", "industry", "tier", "group", "moat", "owner_cash", "risks", "tier_reason", "sources", ...(pool.schema_version === 3 ? ["issuer", "research_question", "metrics"] : [])];
  for (const company of pool.companies) {
    if (Object.keys(company).length !== keys.length || keys.some((key) => !(key in company))) throw new Error("筛选卡含非合同字段");
    if (seen.has(company.symbol) || identities[company.symbol] !== company.name || !market.prefix.test(company.symbol)
      || !pool.review.reviewed_symbols.includes(company.symbol)) throw new Error(`无效筛选身份: ${company.symbol}`);
    if (!["core_moat", "quality_research"].includes(company.tier)) throw new Error("无效筛选分层");
    for (const field of keys.filter((key) => !["sources", "metrics"].includes(key))) if (typeof company[field] !== "string" || !company[field].trim()) throw new Error(`缺少筛选判断: ${field}`);
    if (!Array.isArray(company.sources) || !company.sources.length || company.sources.length > 3
      || company.sources.some((source) => !source.title || !/^https?:\/\//u.test(source.url))) throw new Error("无效筛选来源");
    if (pool.schema_version === 3) {
      const metrics = company.metrics;
      if (!metrics || !Array.isArray(metrics.items) || !metrics.items.length || !Array.isArray(metrics.history)) throw new Error("缺少经营指标");
      for (const item of metrics.items) if (!item.label || !item.value || !item.period
        || !Number.isInteger(item.source) || !company.sources[item.source]) throw new Error("经营指标来源无效");
      if (metrics.history.length && (!metrics.history_metric || !Number.isInteger(metrics.history_source)
        || !company.sources[metrics.history_source])) throw new Error("历史指标来源无效");
      if (!/^(?:CN:[0-9]{6}|HK:[0-9]{5}|US:[A-Z]{1,5}(?:[.-][A-Z])?)$/u.test(company.issuer)) throw new Error("发行人身份无效");
    }
    seen.add(company.symbol);
  }
  const exclusions = pool.review.exclusions ?? [];
  if (pool.schema_version === 3) {
    const excluded = new Set(exclusions.map((item) => item.symbol));
    if (excluded.size !== exclusions.length || exclusions.some((item) => seen.has(item.symbol)
      || !identities[item.symbol] || !item.reason || !pool.review.reviewed_symbols.includes(item.symbol))
      || new Set([...seen, ...excluded]).size !== pool.review.reviewed_symbols.length) throw new Error("复核范围不完整或结论冲突");
  }
  return { market: market.id, label: market.label, scope: market.scope, asOf: pool.as_of,
    philosophy: pool.philosophy, review: pool.review, universeCount: Object.keys(identities).length,
    companies: pool.companies, hasExclusions: pool.schema_version === 3, exclusions: exclusions.map((item) => ({ ...item, name: identities[item.symbol] })) };
}
export async function loadScreeningData(root) {
  const pools = await Promise.all(screeningMarkets.map(async (market) => {
    const pool = JSON.parse(await readFile(join(root, `screening/${market.id}/value-quality/pool.json`), "utf8"));
    return projectScreeningPool(pool, market);
  }));
  return { schemaVersion: 1, pools };
}

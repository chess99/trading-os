import { readFile } from "node:fs/promises";
import { join } from "node:path";

export const screeningMarkets = [
  { id: "cn-a", label: "A股", prefix: /^CN:[0-9]{6}$/u, scope: "A股原有范围" },
  { id: "hk", label: "港股", prefix: /^HK:[0-9]{5}$/u, scope: "精选样本 · 非全市场" },
  { id: "us", label: "美股", prefix: /^US:[A-Z]{1,5}(?:[.-][A-Z])?$/u, scope: "精选样本 · 非全市场" },
];
export function projectScreeningPool(pool, market) {
  if (pool.schema_version !== 2 || !Array.isArray(pool.companies) || !pool.universe?.securities
    || !Array.isArray(pool.review?.reviewed_symbols) || !pool.review.scope_note || !pool.as_of) {
    throw new Error(`${market.id}筛选池格式不正确`);
  }
  const identities = pool.universe.securities;
  for (const symbol of Object.keys(identities)) if (!market.prefix.test(symbol)) throw new Error(`市场代码不匹配: ${symbol}`);
  const seen = new Set();
  const keys = ["symbol", "name", "industry", "tier", "group", "moat", "owner_cash", "risks", "tier_reason", "sources"];
  for (const company of pool.companies) {
    if (Object.keys(company).length !== keys.length || keys.some((key) => !(key in company))) throw new Error("筛选卡含非合同字段");
    if (seen.has(company.symbol) || identities[company.symbol] !== company.name || !market.prefix.test(company.symbol)
      || !pool.review.reviewed_symbols.includes(company.symbol)) throw new Error(`无效筛选身份: ${company.symbol}`);
    if (!["core_moat", "quality_research"].includes(company.tier)) throw new Error("无效筛选分层");
    for (const field of keys.filter((key) => key !== "sources")) if (typeof company[field] !== "string" || !company[field].trim()) throw new Error(`缺少筛选判断: ${field}`);
    if (!Array.isArray(company.sources) || !company.sources.length || company.sources.length > 3
      || company.sources.some((source) => !source.title || !/^https?:\/\//u.test(source.url))) throw new Error("无效筛选来源");
    seen.add(company.symbol);
  }
  return { market: market.id, label: market.label, scope: market.scope, asOf: pool.as_of,
    philosophy: pool.philosophy, review: pool.review, universeCount: Object.keys(identities).length,
    companies: pool.companies };
}
export async function loadScreeningData(root) {
  const pools = await Promise.all(screeningMarkets.map(async (market) => {
    const pool = JSON.parse(await readFile(join(root, `screening/${market.id}/value-quality/pool.json`), "utf8"));
    return projectScreeningPool(pool, market);
  }));
  return { schemaVersion: 1, pools };
}

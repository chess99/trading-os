import { readFile, realpath } from "node:fs/promises";
import { resolve } from "node:path";

const date = (v) => typeof v === "string" && /^20\d{2}-\d{2}-\d{2}$/u.test(v) && Number.isFinite(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v;
const text = (v) => typeof v === "string" && v.trim().length > 0;
const id = (v) => typeof v === "string" && /^[a-z0-9]+(?:-[a-z0-9]+)*$/u.test(v);
const url = (v) => { try { return ["http:", "https:"].includes(new URL(v).protocol); } catch { return false; } };
const finite = (v) => typeof v === "number" && Number.isFinite(v);
const frequency = (v) => ["monthly", "annual", "ytd"].includes(v);
const period = (v, f) => typeof v === "string" && (f === "annual" ? /^20\d{2}$/u : /^20\d{2}-(0[1-9]|1[0-2])$/u).test(v);
const periodEnd = (v, f) => f === "annual" ? `${v}-12-31` : new Date(Date.UTC(Number(v.slice(0,4)), Number(v.slice(5,7)), 0)).toISOString().slice(0,10);

export function validateIndustryIndicators(data, topic) {
  function require(ok, message) { if (!ok) throw new Error(`行业指标：${message}`); }
  require(data?.schemaVersion === 1 && id(data.topic) && data.topic === topic, "主题或版本错误");
  require(text(data.title) && text(data.scopeNote) && date(data.checkedOn) && date(data.reviewAfter) && data.reviewAfter > data.checkedOn, "缺少资料日期或范围");
  require(Array.isArray(data.sources) && data.sources.length > 0, "缺少原始来源");
  const sourceMap = new Map();
  for (const s of data.sources) {
    require(id(s.id) && !sourceMap.has(s.id) && text(s.title) && text(s.publisher) && url(s.url) && date(s.publishedOn) && s.publishedOn <= data.checkedOn, "来源重复、地址或发布日期错误");
    sourceMap.set(s.id, s);
  }
  function evidence(sourceId, p, f) {
    const s = sourceMap.get(sourceId);
    require(s && periodEnd(p, f) <= s.publishedOn, "观察期晚于发布日期或来源缺失");
  }
  require(Array.isArray(data.releaseLinks) && data.releaseLinks.length <= 5 && data.releaseLinks.every((x) => sourceMap.has(x)), "月报入口引用错误");
  require(Array.isArray(data.series) && data.series.length > 0 && Array.isArray(data.headlines), "缺少指标序列");
  const seriesIds = new Set();
  for (const s of data.series) {
    require(id(s.id) && !seriesIds.has(s.id) && text(s.label) && text(s.unit) && text(s.definition) && text(s.interpretation) && frequency(s.frequency) && ["level", "share", "change"].includes(s.valueType), "序列定义不完整或重复");
    require(s.valueType !== "share" || s.unit === "%", "份额单位必须为百分数");
    seriesIds.add(s.id);
    require(Array.isArray(s.points) && s.points.length > 0, "序列没有观察值");
    let previous = "";
    for (const p of s.points) {
      require(period(p.period, s.frequency) && p.period > previous, "观察期重复、乱序或格式错误");
      require(p.value === null || (finite(p.value) && (s.valueType === "change" || p.value >= 0) && (s.valueType !== "share" || p.value <= 100)), "观察值无效");
      require(p.value !== null || text(p.note), "缺值必须说明原因");
      evidence(p.sourceId, p.period, s.frequency);
      if (p.numerator !== undefined || p.denominator !== undefined) {
        require(finite(p.numerator) && finite(p.denominator) && p.numerator >= 0 && p.denominator > 0 && s.valueType === "share" && s.unit === "%" && p.value !== null, "比例输入无效");
        require(Math.abs(100 * p.numerator / p.denominator - p.value) <= 0.15, "比例与原始输入不一致");
      }
      previous = p.period;
    }
  }
  require(data.headlines.length <= 4 && new Set(data.headlines).size === data.headlines.length && data.headlines.every((x) => seriesIds.has(x)), "摘要指标引用错误");
  require(Array.isArray(data.rankings), "缺少份额表数组");
  const rankingIds = new Set();
  for (const t of data.rankings) {
    require(id(t.id) && !rankingIds.has(t.id) && text(t.label) && text(t.definition) && frequency(t.frequency) && period(t.period, t.frequency), "份额表定义错误");
    rankingIds.add(t.id); evidence(t.sourceId, t.period, t.frequency);
    require(Array.isArray(t.items) && t.items.length > 0, "份额表为空");
    const names = new Set();
    for (const row of t.items) {
      require(text(row.name) && !names.has(row.name) && finite(row.share) && row.share >= 0 && row.share <= 100, "企业份额无效");
      names.add(row.name);
      if (row.volumeGWh !== undefined) require(finite(row.volumeGWh) && row.volumeGWh >= 0, "装车量无效");
    }
    require(t.items.reduce((sum, row) => sum + row.share, 0) <= 100.2, "份额总和超过100%");
  }
  if (data.monthlyReports !== undefined) {
    require(Array.isArray(data.monthlyReports), "月报目录格式错误");
    const months = new Set();
    for (const report of data.monthlyReports) {
      require(period(report.period, "monthly") && !months.has(report.period), "月报观察期错误或重复"); months.add(report.period);
      evidence(report.analysisId, report.period, "monthly");
      if (report.deepId) evidence(report.deepId, report.period, "monthly");
      if (report.nevDeepId) evidence(report.nevDeepId, report.period, "monthly");
    }
  }
  return data;
}

export async function loadIndustryIndicators(root, topic, sourcePath) {
  const expected = `research/industries/${topic}/indicators.json`;
  if (sourcePath !== expected) throw new Error("行业指标路径必须对应主题");
  const file = resolve(root, expected);
  if (await realpath(file) !== resolve(await realpath(root), expected)) throw new Error("行业指标不能通过符号链接替换");
  return validateIndustryIndicators(JSON.parse(await readFile(file, "utf8")), topic);
}

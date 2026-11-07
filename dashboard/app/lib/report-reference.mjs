const periodPattern = "(?:20\\d{2})-(?:FY|Q1|H1|Q3)";
const tickerPattern = "[A-Za-z0-9][A-Za-z0-9.-]{0,19}";
const reportPattern = new RegExp(`^/research/companies/(CN|HK|US)/(${tickerPattern})/reports/(${periodPattern})\\.md$`, "u");
const modelPattern = new RegExp(`^/research/companies/(CN|HK|US)/(${tickerPattern})/models/(.+)$`, "u");
const artifactPattern = new RegExp(`^(${periodPattern})(\\.py|-engine\\.py|-input\\.json|-output\\.json|-assumptions\\.md|-sources-assumptions\\.md|-independent-recompute\\.py)$`, "u");
const modulePattern = new RegExp(`^(${periodPattern})/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*\\.(?:py|json|md|csv)$`, "u");
const processMaterial = /(?:^|[-_/])(?:candidate|snapshot|payload|stdout|stderr|cache|history|historical|evidence|trace|checkpoint)(?:[-_./]|$)/iu;
function route(market, ticker) { return market === "CN" ? ticker : `${market}-${ticker}`; }
export function reportReferenceLink(pathname) {
  const match = reportPattern.exec(pathname);
  return match ? `/reports/${route(match[1], match[2])}?version=${match[3]}` : null;
}
export function referencedReport(reports, version) {
  return version ? reports.find((report) => report.period === version) ?? null : reports[0] ?? null;
}
export function modelArtifactName(filename, period) {
  if (processMaterial.test(filename)) return false;
  const match = artifactPattern.exec(filename) ?? modulePattern.exec(filename);
  return Boolean(match && (!period || match[1] === period));
}
// Repository-relative references retain their company and reporting period.
// Downloads expose only small, readable research files.
export function researchResourceLink(href, sourcePath) {
  if (!href) return undefined;
  if (/^(?:https?:|mailto:|#|\/\/)/iu.test(href)) return href;
  const rawPath = href.split(/[?#]/u, 1)[0];
  if (rawPath.includes("\\") || /(?:^|\/)\.(?:\/|$)/u.test(rawPath)) return undefined;
  let resolved;
  try { resolved = new URL(href, `https://research.local/${sourcePath ?? ""}`); }
  catch { return undefined; }
  if (resolved.origin !== "https://research.local") return undefined;
  const report = reportReferenceLink(resolved.pathname);
  if (report) return `${report}${resolved.hash}`;
  const model = modelPattern.exec(resolved.pathname);
  if (!model || !modelArtifactName(model[3])) return undefined;
  const ordinary = `../models/${model[3]}`;
  const absolute = `/research/companies/${model[1]}/${model[2]}/models/${model[3]}`;
  if (rawPath !== ordinary && rawPath !== absolute) return undefined;
  return `/data/models/${route(model[1], model[2])}/${model[3]}${resolved.search}${resolved.hash}`;
}

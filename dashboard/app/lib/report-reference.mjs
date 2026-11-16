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
/** @typedef {{kind: string, type: string, topic: string, version: string, sourcePath: string, indicatorPath?: string | null, status?: string, regionId?: string | null}} PublishedDocument */
/** @typedef {{documents?: PublishedDocument[], companyReportPaths?: string[]}} ResearchLinkContext */

function publicationLink(document, hash, indicators = false) {
  const params = new URLSearchParams({ topic: document.topic, version: document.version, view: document.type });
  if (document.kind === "industry") params.set("region", document.regionId === "cn" ? "cn" : "archive");
  if (indicators) params.set("panel", "indicators");
  return `${document.kind === "industry" ? "/industries" : "/macro"}?${params}${hash}`;
}

// Links use the published catalog, never arbitrary repository files. Company
// periods and publication versions remain explicit when moving between readers.
/** @param {string | undefined} href
 * @param {string | undefined} sourcePath
 * @param {ResearchLinkContext} context
 */
export function researchResourceLink(href, sourcePath, context = {}) {
  if (!href || [...href].some((character) => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127 || character === "\\")) return undefined;
  if (href.startsWith("#")) return href;
  const { documents = [], companyReportPaths = [] } = context;
  if (/^(?:https?:|mailto:|\/\/)/iu.test(href)) {
    try {
      const external = new URL(href, "https://research.local");
      return ["http:", "https:", "mailto:"].includes(external.protocol) ? href : undefined;
    } catch { return undefined; }
  }
  const rawPath = href.split(/[?#]/u, 1)[0];
  let resolved;
  try { resolved = new URL(href, `https://research.local/${sourcePath ?? ""}`); }
  catch { return undefined; }
  if (resolved.origin !== "https://research.local") return undefined;
  const report = reportReferenceLink(resolved.pathname);
  if (report) return companyReportPaths.includes(resolved.pathname.slice(1)) ? `${report}${resolved.hash}` : undefined;
  const publication = documents.find((document) => `/${document.sourcePath}` === resolved.pathname);
  if (publication) return publicationLink(publication, resolved.hash);
  if (["/industries", "/macro"].includes(resolved.pathname)) {
    const kind = resolved.pathname === "/industries" ? "industry" : "macro";
    const type = resolved.searchParams.get("view") ?? "report";
    const topic = resolved.searchParams.get("topic");
    const version = resolved.searchParams.get("version");
    const region = resolved.searchParams.get("region");
    const versions = documents.filter((document) => document.kind === kind && document.type === type && document.topic === topic)
      .filter((document) => kind !== "industry" || !region || (document.regionId === "cn" ? "cn" : "archive") === region)
      .sort((a, b) => b.version.localeCompare(a.version, "en", { numeric: true }));
    const target = version ? versions.find((document) => document.version === version) : versions[0];
    if (!target) return undefined;
    return publicationLink(target, resolved.hash, resolved.searchParams.get("panel") === "indicators"
      && target === versions[0] && target.status === "published" && target.regionId === "cn" && Boolean(target.indicatorPath));
  }
  if (/^\/reports\/[^/]+$/u.test(resolved.pathname)) {
    const version = resolved.searchParams.get("version");
    const exists = companyReportPaths.some((path) => {
      const link = reportReferenceLink(`/${path}`);
      if (!link) return false;
      const target = new URL(link, "https://research.local");
      return target.pathname === resolved.pathname && (!version || target.searchParams.get("version") === version);
    });
    return exists ? `${resolved.pathname}${version ? `?${new URLSearchParams({ version })}` : ""}${resolved.hash}` : undefined;
  }
  const model = modelPattern.exec(resolved.pathname);
  if (!model || !modelArtifactName(model[3])) return undefined;
  const ordinary = `../models/${model[3]}`;
  const absolute = `/research/companies/${model[1]}/${model[2]}/models/${model[3]}`;
  if (rawPath !== ordinary && rawPath !== absolute) return undefined;
  return `/data/models/${route(model[1], model[2])}/${model[3]}${resolved.search}${resolved.hash}`;
}

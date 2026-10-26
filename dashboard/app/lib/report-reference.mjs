export function reportReferenceLink(pathname) {
  const match = /^\/research\/companies\/CN\/(\d{6})\/reports\/((?:20\d{2})-(?:FY|Q1|H1|Q3))\.md$/u.exec(pathname);
  return match ? `/reports/${match[1]}?version=${match[2]}` : null;
}

export function referencedReport(reports, version) {
  return version ? reports.find((report) => report.period === version) ?? null : reports[0] ?? null;
}

// Resolve against the repository source, not /reports/{ticker} in the browser.
export function researchResourceLink(href, sourcePath) {
  if (!href) return undefined;
  if (/^(?:https?:|mailto:|#|\/\/)/iu.test(href)) return href;
  let resolved;
  try { resolved = new URL(href, `https://research.local/${sourcePath ?? ""}`); }
  catch { return undefined; }
  if (resolved.origin !== "https://research.local") return undefined;
  const report = reportReferenceLink(resolved.pathname);
  if (report) return `${report}${resolved.hash}`;
  const model = /^\/research\/companies\/CN\/(\d{6})\/models\/((?:20\d{2})-(?:FY|Q1|H1|Q3)(?:\.py|-output\.json))$/u.exec(resolved.pathname);
  return model ? `/data/models/${model[1]}/${model[2]}${resolved.search}${resolved.hash}` : undefined;
}

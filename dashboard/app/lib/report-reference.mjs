export function reportReferenceLink(pathname) {
  const match = /^\/research\/companies\/CN\/(\d{6})\/reports\/((?:20\d{2})-(?:FY|Q1|H1|Q3))\.md$/u.exec(pathname);
  return match ? `/reports/${match[1]}?version=${match[2]}` : null;
}

export function referencedReport(reports, version) {
  return version ? reports.find((report) => report.period === version) ?? null : reports[0] ?? null;
}

// A closed artifact vocabulary, not a general repository-file endpoint.
export function modelArtifactName(filename, period) {
  const match = /^((?:20\d{2})-(?:FY|Q1|H1|Q3))(\.py|-output\.json|-output\.json\.xz|-case-[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*\.json|-sources-assumptions\.md|-independent-recompute\.py)$/u.exec(filename);
  return Boolean(match && (!period || match[1] === period));
}

// Resolve against the repository source, not /reports/{ticker} in the browser.
export function researchResourceLink(href, sourcePath) {
  if (!href) return undefined;
  if (/^(?:https?:|mailto:|#|\/\/)/iu.test(href)) {
    // Ordinary external citations/anchors retain their old behavior. A URL that
    // claims one of the new model-auxiliary names is not a local model download.
    if (/^(?:https?:|\/\/)/iu.test(href)) {
      const name = href.split(/[?#]/u, 1)[0].split("/").at(-1);
      if (modelArtifactName(name) && !/^(?:20\d{2})-(?:FY|Q1|H1|Q3)(?:\.py|-output\.json)$/u.test(name)) return undefined;
    }
    return href;
  }
  let resolved;
  try { resolved = new URL(href, `https://research.local/${sourcePath ?? ""}`); }
  catch { return undefined; }
  if (resolved.origin !== "https://research.local") return undefined;
  const report = reportReferenceLink(resolved.pathname);
  if (report) return `${report}${resolved.hash}`;
  const model = /^\/research\/companies\/CN\/(\d{6})\/models\/([^/]+)$/u.exec(resolved.pathname);
  if (!model || !modelArtifactName(model[2])) return undefined;
  const primary = /^(?:20\d{2})-(?:FY|Q1|H1|Q3)(?:\.py|-output\.json)$/u.test(model[2]);
  if (!primary) {
    const source = /^research\/companies\/CN\/(\d{6})\/reports\/((?:20\d{2})-(?:FY|Q1|H1|Q3))\.md$/u.exec(sourcePath ?? "");
    // New auxiliary artifacts stay with the originating report company/period.
    // Permit only the ordinary ../models/ or exact repository-absolute form;
    // URL normalization must not silently turn traversal into an allowed file.
    const rawPath = href.split(/[?#]/u, 1)[0];
    const relative = `../models/${model[2]}`;
    const absolute = `/research/companies/CN/${model[1]}/models/${model[2]}`;
    if (!source || source[1] !== model[1] || !modelArtifactName(model[2], source[2])
        || (rawPath !== relative && rawPath !== absolute)) return undefined;
  }
  return `/data/models/${model[1]}/${model[2]}${resolved.search}${resolved.hash}`;
}

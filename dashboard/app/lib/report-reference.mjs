export function reportReferenceLink(pathname) {
  const match = /^\/research\/companies\/CN\/(\d{6})\/reports\/((?:20\d{2})-(?:FY|Q1|H1|Q3))\.md$/u.exec(pathname);
  return match ? `/reports/${match[1]}?version=${match[2]}` : null;
}

export function referencedReport(reports, version) {
  return version ? reports.find((report) => report.period === version) ?? null : reports[0] ?? null;
}

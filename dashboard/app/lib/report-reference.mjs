export function reportReferenceLink(pathname) {
  const match = /^\/research\/companies\/(CN|HK|US)\/([A-Z0-9.-]+)\/reports\/((?:20\d{2})-(?:FY|Q1|H1|Q3))\.md$/u.exec(pathname);
  return match ? `/reports/${match[1] === "CN" ? match[2] : `${match[1]}-${match[2]}`}?version=${match[3]}` : null;
}

export function referencedReport(reports, version) {
  return version ? reports.find((report) => report.period === version) ?? null : reports[0] ?? null;
}

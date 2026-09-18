// A dated research reference must keep its basis when newer reports arrive.
export function reportReferenceLink(pathname) {
  const match = /^\/research\/companies\/CN\/(\d{6})\/reports\/(\d{4}-\d{2}-\d{2}(?:-\d{2})?)\.md$/u.exec(pathname);
  return match ? `/reports/${match[1]}?version=${match[2]}` : null;
}

export function referencedReport(reports, version) {
  return version ? reports.find((report) => report.date === version) ?? null : reports[0] ?? null;
}

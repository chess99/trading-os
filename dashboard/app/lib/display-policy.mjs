// One selection rule for lists, counts, quotes, numeric ranking and exports.
// Absence of an explicit eligibility result always means "not current".
export function isCurrentResult(company, scope = "quality_pool") {
  return company?.display?.eligible === true
    && company.universeStatus === "active" && ["covered", "ignore"].includes(company.status)
    && (scope === "all_standard" || company.inQualityPool === true);
}
export function scopedCompanies(companies, scope = "quality_pool") {
  return companies.filter((company) => scope === "all_standard" || company.inQualityPool === true);
}
export function currentResults(companies, scope = "quality_pool") {
  return companies.filter((company) => isCurrentResult(company, scope));
}
export function progressCounts(companies, scope = "quality_pool") {
  const rows = scopedCompanies(companies, scope);
  const count = (states) => rows.filter((company) => states.includes(company.display?.state)).length;
  return {
    total: rows.length,
    completed: currentResults(rows, "all_standard").length,
    valued: currentResults(rows, "all_standard").filter((company) => company.display.state === "current").length,
    unpriced: currentResults(rows, "all_standard").filter((company) => company.display.state === "unpriced").length,
    pending: rows.filter((company) => company.pendingReportPeriod
      || ["pending_research", "pending_standard"].includes(company.display?.state)).length,
    review: count(["needs_review"]),
    inactive: count(["inactive"]),
  };
}
/** @param {string | null} [version] */
export function readingContext(company, version = null) {
  if (!company) return { report: null, live: false, historical: false };
  const report = version
    ? company.reports.find((item) => item.period === version)
    : company.reports[0];
  const live = Boolean(report && isCurrentResult(company, "all_standard")
    && report.sourcePath === company.basisReportPath);
  return { report: report ?? null, live, historical: Boolean(report && !live) };
}
export const DISPLAY_LABELS = {
  current: "现行标准 · 已估值",
  unpriced: "研究完成 · 暂无法估值",
  pending_research: "待首次研究",
  pending_standard: "待按现行标准研究",
  needs_review: "验收待复核",
  inactive: "不在当前在市范围",
};

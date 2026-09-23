// One selection rule for lists, counts, quotes, numeric ranking and exports.
// Absence of an explicit eligibility result always means "not current".
export function isCurrentResult(company, scope = "quality_pool") {
  return company?.display?.eligible === true
    && company.universeStatus === "active" && ["covered", "ignore"].includes(company.status) && !company.invalidation
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
    pending: count(["pending_research", "pending_standard"]),
    updating: count(["needs_update"]),
    review: count(["needs_review"]),
    inactive: count(["inactive"]),
  };
}
export function readingContext(company, version = null, mode = "current") {
  if (!company) return { report: null, live: false, historical: false };
  if (version || mode === "history") {
    const report = version ? company.reports.find((item) => item.date === version) : company.reports[0];
    // Explicit dated reading is a snapshot even when its path is current.
    return { report: report ?? null, live: false, historical: true };
  }
  const report = isCurrentResult(company, "all_standard")
    ? company.reports.find((item) => item.sourcePath === company.reportPath) : null;
  return { report: report ?? null, live: Boolean(report), historical: false };
}
export const DISPLAY_LABELS = {
  current: "现行标准 · 已估值",
  unpriced: "研究完成 · 暂无法估值",
  pending_research: "待首次研究",
  pending_standard: "待按现行标准研究",
  needs_update: "新版已失效 · 待更新",
  needs_review: "验收待复核",
  inactive: "不在当前在市范围",
};

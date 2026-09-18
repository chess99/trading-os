function finiteNumberOrNull(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function compareRecencyAndTicker(a, b) {
  return String(b.updatedAt ?? "").localeCompare(String(a.updatedAt ?? ""))
    || String(a.ticker ?? "").localeCompare(String(b.ticker ?? ""));
}

export function compareOpportunityRanks(a, b) {
  const aIrr = finiteNumberOrNull(a.midpointIrr);
  const bIrr = finiteNumberOrNull(b.midpointIrr);
  if (aIrr !== null && bIrr !== null) {
    return bIrr - aIrr || compareRecencyAndTicker(a, b);
  }
  if (aIrr !== null) return -1;
  if (bIrr !== null) return 1;

  const aLowRatio = finiteNumberOrNull(a.lowRatio);
  const bLowRatio = finiteNumberOrNull(b.lowRatio);
  if (aLowRatio !== null && bLowRatio !== null) {
    return aLowRatio - bLowRatio || compareRecencyAndTicker(a, b);
  }
  if (aLowRatio !== null) return -1;
  if (bLowRatio !== null) return 1;
  return compareRecencyAndTicker(a, b);
}

// Numeric ordering is an explicit exploration choice, never the default shortlist.
export function compareResearchMapRows(a, b, mode = "ticker") {
  if (mode === "irr") return compareOpportunityRanks(a, b);
  if (mode === "updated") return compareRecencyAndTicker(a, b);
  if (mode === "value") {
    const aValue = finiteNumberOrNull(a.lowRatio);
    const bValue = finiteNumberOrNull(b.lowRatio);
    if (aValue !== null && bValue !== null) return aValue - bValue || compareRecencyAndTicker(a, b);
    if (aValue !== null) return -1;
    if (bValue !== null) return 1;
  }
  return String(a.ticker ?? "").localeCompare(String(b.ticker ?? ""));
}

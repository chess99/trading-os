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

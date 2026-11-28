import { matchingQuoteCurrency } from "./market-quotes.mjs";
import { calculateIrrRange } from "./irr.mjs";
import { isCurrentResult } from "./display-policy.mjs";

/** @type {Record<string, string>} */
export const TRACK_LABELS = {
  compounder: "复利质量",
  inflection_growth: "产业拐点",
};

/** @type {Record<string, string>} */
export const CYCLE_STAGE_LABELS = {
  upcycle_tight: "上行景气",
  inflection_bottom: "底部拐点",
  mature_stable: "成熟稳定",
  downcycle_clearing: "下行出清",
  overcapacity: "产能过剩",
};

/** @type {Record<string, string>} */
export const PROFIT_TREND_LABELS = {
  expanding: "利润扩张",
  stable: "利润平稳",
  contracting: "利润承压",
};

/** @type {Record<string, string>} */
export const MACRO_ALIGN_LABELS = {
  tailwind: "宏观顺风",
  neutral: "宏观中性",
  headwind: "宏观逆风",
};

/** @type {Record<string, string>} */
export const QUALITY_LABELS = {
  A: "A · 卓越",
  B: "B · 良好",
  C: "C · 一般",
};

/** @type {Record<string, string>} */
export const PREDICTABILITY_LABELS = {
  high: "高可预见",
  medium: "中可预见",
  low: "低可预见",
};

/** @type {Record<string, number>} */
export const CYCLE_ORDER = {
  inflection_bottom: 0,
  upcycle_tight: 1,
  mature_stable: 2,
  downcycle_clearing: 3,
  overcapacity: 4,
};

/**
 * Compute dynamic four-scenario upside/downside asymmetry from slow scenario anchors and live price.
 * @param {any} company
 * @param {any} [quote]
 * @returns {{ cyclicalDownside: number, structuralDownside: number, bullUpside: number, oddsRatio: number, downsideCovered: boolean } | null}
 */
export function scenarioAsymmetry(company, quote) {
  if (!isCurrentResult(company, "all_standard") || !company?.scenarios) return null;
  if (!matchingQuoteCurrency(quote, company.scenarios.currency)) return null;
  const price = quote?.price;
  if (typeof price !== "number" || !Number.isFinite(price) || price <= 0) return null;
  const { structural_bear: structuralBear, cyclical_bear: cyclicalBear, bull } = company.scenarios;
  if (![structuralBear, cyclicalBear, bull].every((v) => typeof v === "number" && Number.isFinite(v) && v >= 0)) {
    return null;
  }
  const cyclicalDownside = (cyclicalBear - price) / price;
  const structuralDownside = (structuralBear - price) / price;
  const bullUpside = (bull - price) / price;
  const downsideCovered = price <= cyclicalBear;
  const oddsRatio = bullUpside <= 0
    ? 0
    : downsideCovered
      ? Infinity
      : bullUpside / Math.abs(cyclicalDownside);
  return {
    cyclicalDownside,
    structuralDownside,
    bullUpside,
    oddsRatio,
    downsideCovered,
  };
}

/**
 * Estimate Southbound Stock Connect dividend-tax-adjusted IRR for HK stocks without mutating capital gains (0% tax).
 * @param {any} company
 * @param {any} [quote]
 * @param {3 | 5} [horizonYears]
 * @returns {{ taxRate: number, irr: { low: number | null, midpoint: number | null, high: number | null } } | null}
 */
export function southboundAfterTaxIrr(company, quote, horizonYears = 5) {
  if (!company || company.market !== "HK" || company.ahBridge?.southboundUnavailableOn) return null;
  if (!isCurrentResult(company, "all_standard") || company.returnModelDisplayIssue) return null;
  if (!company.returnModel || company.returnModel.model_as_of !== company.informationCutoff) return null;
  if (!matchingQuoteCurrency(quote, company.returnModel.currency)) return null;
  const taxRate = company.capitalReturnProfile?.southbound_dividend_tax_rate ?? company.ahBridge?.southboundDividendTaxRate ?? null;
  if (typeof taxRate !== "number" || !Number.isFinite(taxRate) || taxRate <= 0 || taxRate >= 1) return null;
  const afterTaxModel = {
    schema_version: company.returnModel.schema_version,
    method: company.returnModel.method,
    currency: company.returnModel.currency,
    model_as_of: company.returnModel.model_as_of,
    base_case_distributions_per_share: company.returnModel.base_case_distributions_per_share.map((/** @type {number} */ d) => d * (1 - taxRate)),
    base_case_terminal_equity_value_range_per_share: company.returnModel.base_case_terminal_equity_value_range_per_share,
  };
  const irr = calculateIrrRange(quote?.price, afterTaxModel, horizonYears);
  if (!irr) return null;
  return { taxRate, irr };
}

/**
 * Filter companies by executive decision lens without inventing hidden scores.
 * @param {any} company
 * @param {any} [quote]
 * @param {string} [lens]
 * @returns {boolean}
 */
export function matchesDecisionLens(company, quote, lens = "all") {
  if (!lens || lens === "all") return true;
  if (lens === "core_defense") {
    const qualityOk = company.decisionProfile
      ? company.decisionProfile.business_quality === "A"
      : company.qualityTier === "core_moat";
    const riskOk = company.decisionProfile ? company.decisionProfile.downside_risk !== "high" : true;
    const macroOk = company.industryState?.macroAlignment !== "headwind";
    const asym = scenarioAsymmetry(company, quote);
    const priceNotOverstretched = asym ? asym.bullUpside > -0.1 : true;
    return qualityOk && riskOk && macroOk && priceNotOverstretched;
  }
  if (lens === "inflection_odds") {
    return company.track === "inflection_growth"
      || company.industryState?.inflectionCandidate === true
      || company.industryState?.cycleStage === "inflection_bottom"
      || company.industryState?.cycleStage === "upcycle_tight";
  }
  if (lens === "ah_southbound") {
    return !company.ahBridge?.southboundUnavailableOn && (company.market === "HK" || Boolean(company.ahBridge?.pairSymbol));
  }
  return true;
}

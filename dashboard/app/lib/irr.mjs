const RETURN_MODEL_SCHEMA_VERSION = 1;
const RETURN_MODEL_METHOD = "annual_common_equity_irr_v1";
const MAX_BRACKET_EXPANSIONS = 1024;
const BISECTION_STEPS = 256;

/**
 * @typedef {{ low: number, high: number }} TerminalValueRange
 * @typedef {{
 *   schema_version: number,
 *   method: string,
 *   currency: string,
 *   model_as_of: string,
 *   base_case_distributions_per_share: number[],
 *   base_case_terminal_equity_value_range_per_share: {
 *     year_5: TerminalValueRange,
 *     year_3?: TerminalValueRange,
 *   },
 * }} ReturnModel
 * @typedef {{ low: number | null, midpoint: number | null, high: number | null }} IrrRange
 */

function isNonNegativeFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

function isTerminalValueRange(value) {
  if (value === null || typeof value !== "object") return false;
  const keys = Object.keys(value).sort();
  return (
    keys.length === 2
    && keys[0] === "high"
    && keys[1] === "low"
    && isNonNegativeFiniteNumber(value.low)
    && isNonNegativeFiniteNumber(value.high)
    && value.low <= value.high
  );
}

function isSupportedReturnModel(value) {
  if (value === null || typeof value !== "object") return false;
  const modelKeys = Object.keys(value).sort();
  const expectedModelKeys = [
    "base_case_distributions_per_share",
    "base_case_terminal_equity_value_range_per_share",
    "currency",
    "method",
    "model_as_of",
    "schema_version",
  ];
  if (
    modelKeys.length !== expectedModelKeys.length
    || modelKeys.some((key, index) => key !== expectedModelKeys[index])
  ) {
    return false;
  }
  if (value.schema_version !== RETURN_MODEL_SCHEMA_VERSION) return false;
  if (value.method !== RETURN_MODEL_METHOD || value.currency !== "CNY") return false;
  if (
    typeof value.model_as_of !== "string"
    || !/(?:Z|[+-]\d{2}:\d{2})$/u.test(value.model_as_of)
    || Number.isNaN(Date.parse(value.model_as_of))
  ) {
    return false;
  }
  const distributions = value.base_case_distributions_per_share;
  if (
    !Array.isArray(distributions)
    || distributions.length !== 5
    || !distributions.every(isNonNegativeFiniteNumber)
  ) {
    return false;
  }
  const terminalValues = value.base_case_terminal_equity_value_range_per_share;
  if (terminalValues === null || typeof terminalValues !== "object") return false;
  const terminalKeys = Object.keys(terminalValues).sort();
  const keysAreExact = (
    (terminalKeys.length === 1 && terminalKeys[0] === "year_5")
    || (terminalKeys.length === 2 && terminalKeys[0] === "year_3" && terminalKeys[1] === "year_5")
  );
  if (
    !keysAreExact
    || !isTerminalValueRange(terminalValues.year_5)
    || (terminalValues.year_3 !== undefined && !isTerminalValueRange(terminalValues.year_3))
  ) {
    return false;
  }
  if (distributions.reduce((sum, value) => sum + value, 0) + terminalValues.year_5.high <= 0) {
    return false;
  }
  return terminalValues.year_3 === undefined
    || distributions.slice(0, 3).reduce((sum, value) => sum + value, 0) + terminalValues.year_3.high > 0;
}

function presentValue(distributions, terminalValue, growthFactor) {
  let value = 0;
  for (let index = 0; index < distributions.length; index += 1) {
    const distribution = distributions[index];
    if (distribution > 0) {
      value += distribution / growthFactor ** (index + 1);
    }
  }
  if (terminalValue > 0) {
    value += terminalValue / growthFactor ** distributions.length;
  }
  return value;
}

/**
 * Solve the periodic annual IRR for one current outflow and non-negative future
 * common-equity cash flows. Returns a decimal rate (0.10 means 10%).
 *
 * @param {number} currentPrice
 * @param {number[]} annualDistributions
 * @param {number} terminalValue
 * @returns {number | null}
 */
export function calculateAnnualIrr(currentPrice, annualDistributions, terminalValue) {
  if (typeof currentPrice !== "number" || !Number.isFinite(currentPrice) || currentPrice <= 0) {
    return null;
  }
  if (
    !Array.isArray(annualDistributions)
    || annualDistributions.length === 0
    || !annualDistributions.every(isNonNegativeFiniteNumber)
    || !isNonNegativeFiniteNumber(terminalValue)
  ) {
    return null;
  }
  if (terminalValue === 0 && annualDistributions.every((value) => value === 0)) return null;

  let lowerGrowthFactor = Number.EPSILON;
  if (presentValue(annualDistributions, terminalValue, lowerGrowthFactor) <= currentPrice) {
    return null;
  }

  let upperGrowthFactor = 1;
  let upperPresentValue = presentValue(annualDistributions, terminalValue, upperGrowthFactor);
  for (
    let expansion = 0;
    upperPresentValue > currentPrice && expansion < MAX_BRACKET_EXPANSIONS;
    expansion += 1
  ) {
    if (upperGrowthFactor > Number.MAX_VALUE / 2) return null;
    lowerGrowthFactor = upperGrowthFactor;
    upperGrowthFactor *= 2;
    upperPresentValue = presentValue(annualDistributions, terminalValue, upperGrowthFactor);
  }
  if (upperPresentValue > currentPrice) return null;
  if (upperPresentValue === currentPrice) return upperGrowthFactor - 1;

  for (let step = 0; step < BISECTION_STEPS; step += 1) {
    const midpoint = lowerGrowthFactor + (upperGrowthFactor - lowerGrowthFactor) / 2;
    if (midpoint === lowerGrowthFactor || midpoint === upperGrowthFactor) break;
    const midpointPresentValue = presentValue(annualDistributions, terminalValue, midpoint);
    if (midpointPresentValue > currentPrice) {
      lowerGrowthFactor = midpoint;
    } else {
      upperGrowthFactor = midpoint;
    }
  }

  const rate = (lowerGrowthFactor + (upperGrowthFactor - lowerGrowthFactor) / 2) - 1;
  return Number.isFinite(rate) && rate > -1 ? rate : null;
}

/**
 * Calculate low/midpoint/high IRRs from the independently researched terminal
 * equity-value range for the requested horizon.
 *
 * @param {number | null | undefined} currentPrice
 * @param {ReturnModel | null | undefined} returnModel
 * @param {3 | 5} horizonYears
 * @returns {IrrRange | null}
 */
export function calculateIrrRange(currentPrice, returnModel, horizonYears) {
  if (
    typeof currentPrice !== "number"
    || !Number.isFinite(currentPrice)
    || currentPrice <= 0
    || !isSupportedReturnModel(returnModel)
  ) {
    return null;
  }

  const terminalValues = returnModel.base_case_terminal_equity_value_range_per_share;
  const terminalRange = horizonYears === 5
    ? terminalValues.year_5
    : horizonYears === 3
      ? terminalValues.year_3
      : undefined;
  if (!terminalRange) return null;

  const distributions = returnModel.base_case_distributions_per_share.slice(0, horizonYears);
  const midpointTerminalValue = terminalRange.low + (terminalRange.high - terminalRange.low) / 2;
  return {
    low: calculateAnnualIrr(currentPrice, distributions, terminalRange.low),
    midpoint: calculateAnnualIrr(currentPrice, distributions, midpointTerminalValue),
    high: calculateAnnualIrr(currentPrice, distributions, terminalRange.high),
  };
}

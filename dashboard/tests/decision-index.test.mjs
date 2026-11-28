import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { currentResults } from "../app/lib/display-policy.mjs";
import { calculateIrrRange } from "../app/lib/irr.mjs";
import {
  matchesDecisionLens,
  scenarioAsymmetry,
  southboundAfterTaxIrr,
} from "../app/lib/decision-metrics.mjs";
import { compareResearchMapRows } from "../app/lib/opportunity-sort.mjs";
import { buildResearchData, projectCompany } from "../scripts/build-research-data.mjs";
import { validateRegistry } from "../scripts/lib/research-standards.mjs";
import { loadPublications } from "../scripts/lib/publications.mjs";

function makeQualifiedCompany(overrides = {}) {
  return {
    symbol: "HK:00700",
    ticker: "HK-00700",
    market: "HK",
    quoteCurrency: "HKD",
    status: "covered",
    universeStatus: "active",
    inQualityPool: true,
    qualityTier: "core_moat",
    track: "compounder",
    updatedAt: "2026-11-20T10:00:00+08:00",
    informationCutoff: "2026-11-20T10:00:00+08:00",
    display: { eligible: true, state: "current", reason: "已核验" },
    valueRange: { low: 400, high: 500, currency: "HKD" },
    returnModel: {
      schema_version: 1,
      method: "annual_common_equity_irr_v1",
      currency: "HKD",
      model_as_of: "2026-11-20T10:00:00+08:00",
      base_case_distributions_per_share: [10, 10, 10, 10, 10],
      base_case_terminal_equity_value_range_per_share: {
        year_5: { low: 500, high: 600 },
      },
    },
    scenarios: {
      currency: "HKD",
      structural_bear: 260,
      cyclical_bear: 320,
      base_low: 400,
      base_high: 500,
      bull: 640,
      horizon_note: "五年基准与周期对比",
    },
    decisionProfile: {
      track: "compounder",
      valuation_framework: "buyback_total_yield",
      industry_topic: "internet-content-platforms",
      business_quality: "A",
      capital_allocation: "high",
      predictability: "high",
      downside_risk: "low",
      exposure_tags: ["平台经济"],
      thesis_breakers: ["现金流恶化"],
    },
    ahBridge: {
      role: "HK_ONLY",
      pairSymbol: null,
      hShareStructure: "hk_general",
      southboundDividendTaxRate: 0.2,
    },
    ...overrides,
  };
}

test("decision-index.json follows schema v1, covers active A+H only, and stays decoupled from live prices", async () => {
  const [index, catalog] = await Promise.all([
    readFile(new URL("../public/data/decision-index.json", import.meta.url), "utf8").then(JSON.parse),
    readFile(new URL("../public/data/research-catalog.json", import.meta.url), "utf8").then(JSON.parse),
  ]);
  assert.equal(index.schemaVersion, 1);
  assert.deepEqual(index.tradingProfile.activeMarkets, ["CN", "HK"]);
  assert.equal(index.tradingProfile.hkChannel, "southbound_stock_connect");
  assert.equal(index.industries.length, 34);
  assert.equal(index.globalBenchmarks.length, 25);
  assert.equal(index.ahPairs.length, 15);
  assert.equal(index.macro.qdiiCatalog.etfs.length, 6);
  const expected = currentResults(catalog.companies, "all_standard");
  assert.equal(index.companies.length, expected.length);
  for (const company of index.companies) {
    assert.ok(["CN", "HK"].includes(company.market));
    assert.ok(!("currentIrr" in company) && !("lastClose" in company) && !("price" in company));
    assert.ok(!JSON.stringify(company).includes("legacy/"));
  }
});

test("scenarioAsymmetry computes normal odds, downside coverage, and fail-closed nulls", () => {
  const company = makeQualifiedCompany();
  const quote = { ticker: "HK-00700", currency: "HKD", price: 400 };
  const normal = scenarioAsymmetry(company, quote);
  assert.ok(normal);
  assert.equal(normal.downsideCovered, false);
  assert.ok(Math.abs(normal.bullUpside - 0.6) < 1e-9);
  assert.ok(Math.abs(normal.cyclicalDownside - (-0.2)) < 1e-9);
  assert.ok(Math.abs(normal.oddsRatio - 3.0) < 1e-9);

  const covered = scenarioAsymmetry(company, { ...quote, price: 300 });
  assert.equal(covered.downsideCovered, true);
  assert.equal(covered.oddsRatio, Infinity);

  assert.equal(scenarioAsymmetry(company, { ticker: "HK-00700", currency: "CNY", price: 400 }), null);
  assert.equal(scenarioAsymmetry(makeQualifiedCompany({ display: { eligible: false, state: "pending_standard", reason: "旧标准" } }), quote), null);
});

test("southboundAfterTaxIrr applies 20% and 28% dividend tax to distributions only", () => {
  const hk20 = makeQualifiedCompany();
  const quote = { ticker: "HK-00700", currency: "HKD", price: 400 };
  const preTax = calculateIrrRange(quote.price, hk20.returnModel, 5);
  const post20 = southboundAfterTaxIrr(hk20, quote, 5);
  assert.ok(preTax && post20);
  assert.equal(post20.taxRate, 0.2);
  assert.ok(post20.irr.midpoint < preTax.midpoint);
  // Check exact terminal invariance at 0 dividend baseline: scaling distributions only leaves pure terminal IRR unchanged
  const pureTerminal = makeQualifiedCompany({
    returnModel: {
      ...hk20.returnModel,
      base_case_distributions_per_share: [0, 0, 0, 0, 0],
    },
  });
  const purePre = calculateIrrRange(quote.price, pureTerminal.returnModel, 5);
  const purePost = southboundAfterTaxIrr(pureTerminal, quote, 5);
  assert.ok(Math.abs(purePost.irr.midpoint - purePre.midpoint) < 1e-9);

  const redChip28 = makeQualifiedCompany({
    symbol: "HK:00941",
    ticker: "HK-00941",
    capitalReturnProfile: { annual_net_buyback_per_share: null, southbound_dividend_tax_rate: 0.28, note: "红筹28%" },
  });
  const post28 = southboundAfterTaxIrr(redChip28, { ticker: "HK-00941", currency: "HKD", price: 400 }, 5);
  assert.equal(post28.taxRate, 0.28);
  assert.ok(post28.irr.midpoint < post20.irr.midpoint);

  const cnStock = makeQualifiedCompany({ symbol: "CN:600519", ticker: "600519", market: "CN", quoteCurrency: "CNY" });
  assert.equal(southboundAfterTaxIrr(cnStock, { ticker: "600519", currency: "CNY", price: 400 }, 5), null);

  const researchOnly = makeQualifiedCompany({
    ahBridge: { southboundUnavailableOn: "2026-11-27", southboundDividendTaxRate: null },
    capitalReturnProfile: { southbound_dividend_tax_rate: 0.2 },
  });
  assert.equal(southboundAfterTaxIrr(researchOnly, quote), null);
  assert.equal(matchesDecisionLens(researchOnly, quote, "ah_southbound"), false);
});

test("matchesDecisionLens and extended sorts rank odds and cycle stages cleanly", () => {
  const coreA = makeQualifiedCompany({
    industryState: { cycleStage: "mature_stable", profitPoolTrend: "stable", macroAlignment: "neutral", inflectionCandidate: false, macroTransmission: "稳健", keyDrivers: ["用户"] },
  });
  const inflection = makeQualifiedCompany({
    symbol: "CN:002594",
    ticker: "002594",
    market: "CN",
    track: "inflection_growth",
    qualityTier: "quality_research",
    decisionProfile: { ...coreA.decisionProfile, track: "inflection_growth", business_quality: "B", downside_risk: "medium" },
    industryState: { cycleStage: "inflection_bottom", profitPoolTrend: "expanding", macroAlignment: "tailwind", inflectionCandidate: true, macroTransmission: "渗出拐点", keyDrivers: ["渗透率"] },
    ahBridge: { role: "A", pairSymbol: "HK:01211", southboundDividendTaxRate: 0.2 },
  });
  assert.equal(matchesDecisionLens(coreA, undefined, "core_defense"), true);
  assert.equal(matchesDecisionLens(coreA, undefined, "inflection_odds"), false);
  assert.equal(matchesDecisionLens(inflection, undefined, "inflection_odds"), true);
  assert.equal(matchesDecisionLens(inflection, undefined, "ah_southbound"), true);

  const byOdds = [
    { ticker: "A", midpointIrr: 0.1, lowRatio: 1, oddsRatio: 2.5 },
    { ticker: "B", midpointIrr: 0.08, lowRatio: 0.9, oddsRatio: Infinity },
    { ticker: "C", midpointIrr: 0.2, lowRatio: 0.8, oddsRatio: null },
  ].sort((a, b) => compareResearchMapRows(a, b, "odds"));
  assert.deepEqual(byOdds.map((x) => x.ticker), ["B", "A", "C"]);

  const byCycle = [
    { ticker: "A", cycleStage: "downcycle_clearing", midpointIrr: 0.15 },
    { ticker: "B", cycleStage: "inflection_bottom", midpointIrr: 0.1 },
    { ticker: "C", cycleStage: null, midpointIrr: 0.2 },
  ].sort((a, b) => compareResearchMapRows(a, b, "cycle"));
  assert.deepEqual(byCycle.map((x) => x.ticker), ["B", "A", "C"]);
});

test("loadPublications validates and exposes industryState and macroState", async () => {
  const root = await mkdtemp(join(tmpdir(), "pub-state-test-"));
  async function save(rel, content) {
    await mkdir(dirname(join(root, rel)), { recursive: true });
    await writeFile(join(root, rel), content);
  }
  try {
    await save("research/industries/catalog.json", JSON.stringify({
      schemaVersion: 1,
      groups: [{ id: "tech", label: "科技" }],
      topics: [{ id: "semiconductors", label: "半导体", group: "tech", scope: "芯片与设备" }],
    }));
    await save("research/industries/semiconductors/reports/2026-10-28.md", "# 半导体\n\n正文。\n");
    await save("research/macro/cross-market-regime/reports/2026-10-28.md", "# 宏观环境\n\n正文。\n");
    const validDocs = [
      {
        id: "semi-2026-10-28",
        kind: "industry",
        type: "report",
        topic: "semiconductors",
        publishedOn: "2026-10-28",
        informationCutoff: "2026-10-28",
        markets: ["CN", "HK"],
        regions: ["中国"],
        regionId: "cn",
        summary: "AI 算力与存储拉动景气上行。",
        sourcePath: "research/industries/semiconductors/reports/2026-10-28.md",
        status: "published",
        industryState: {
          cycleStage: "upcycle_tight",
          profitPoolTrend: "expanding",
          macroAlignment: "tailwind",
          macroTransmission: "下游资本开支与国产替代驱动订单扩张。",
          inflectionCandidate: true,
          keyDrivers: ["国产替代", "HBM需求"],
        },
      },
      {
        id: "regime-2026-10-28",
        kind: "macro",
        type: "report",
        topic: "cross-market-regime",
        publishedOn: "2026-10-28",
        informationCutoff: "2026-10-28",
        markets: ["CN", "HK", "US"],
        regions: ["全球"],
        summary: "宽流动性弱私企信用。",
        sourcePath: "research/macro/cross-market-regime/reports/2026-10-28.md",
        status: "published",
        macroState: {
          asOf: "2026-10-28",
          regimeSummary: "流动性宽松但美债利率偏高。",
          factors: [{ id: "rates", label: "美债利率", direction: "tight", reading: "5.0%", implication: "压制远期估值" }],
        },
      },
    ];
    await save("research/publications.json", JSON.stringify({ schemaVersion: 1, documents: validDocs }));
    const loaded = await loadPublications(root);
    assert.equal(loaded.find((d) => d.kind === "industry").industryState.cycleStage, "upcycle_tight");
    assert.equal(loaded.find((d) => d.kind === "macro").macroState.factors.length, 1);

    const invalid = structuredClone(validDocs);
    invalid[0].industryState.cycleStage = "invalid_stage";
    await save("research/publications.json", JSON.stringify({ schemaVersion: 1, documents: invalid }));
    await assert.rejects(loadPublications(root), /cycleStage/);

    const badMacro = structuredClone(validDocs);
    delete badMacro[1].macroState.factors;
    await save("research/publications.json", JSON.stringify({ schemaVersion: 1, documents: badMacro }));
    await assert.rejects(loadPublications(root), /factors|benchmarks/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("projectCompany prioritizes current pool track over historical report decision_profile track while keeping report judgment intact", async () => {
  const registry = JSON.parse(await readFile(new URL("../../research/standards/registry.json", import.meta.url), "utf8"));
  const rules = validateRegistry(registry);
  const std = rules.active;
  const sourcePath = "research/companies/CN/002371/reports/2026-Q3.md";
  const row = {
    schema_version: 6,
    symbol: "CN:002371",
    name: "测试半导体设备",
    report_period: "2026-Q3",
    basis_report_path: sourcePath,
    last_research_at: "2026-11-20T10:00:00+08:00",
    information_cutoff: "2026-11-20T10:00:00+08:00",
    status: "covered",
    universe_status: "active",
    summary: "判断成立",
    value_range: { low: 100, high: 140, currency: "CNY" },
    standard_id: std.id,
    spec_revision: std.spec_revision,
    accepted_at: "2026-11-20T10:00:00+08:00",
    decision_profile: {
      track: "inflection_growth",
      valuation_framework: "dividend_dcf_v1",
      industry_topic: "semiconductors",
      business_quality: "A",
      capital_allocation: "high",
      predictability: "medium",
      downside_risk: "medium",
      exposure_tags: ["半导体设备"],
      thesis_breakers: ["订单连续两季下滑"],
    },
  };
  const reports = [{
    period: "2026-Q3",
    path: "/data/reports/002371/2026-Q3.md",
    sourcePath,
    informationCutoff: row.information_cutoff,
    standardId: std.id,
    standardLabel: std.label,
    valueDefinition: std.value_definition,
    acceptedAt: row.accepted_at,
    compatible: true,
  }];
  const inPool = projectCompany(row, reports, { tier: "core_moat", track: "compounder", industry_topic: "semiconductors" }, rules);
  assert.equal(inPool.track, "compounder");
  assert.equal(inPool.decisionProfile.track, "inflection_growth");

  const outsidePool = projectCompany(row, reports, null, rules);
  assert.equal(outsidePool.track, "inflection_growth");
  assert.equal(outsidePool.decisionProfile.track, "inflection_growth");
  assert.equal(typeof buildResearchData, "function");
});

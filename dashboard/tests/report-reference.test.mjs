import assert from "node:assert/strict";
import test from "node:test";
import { reportReferenceLink, referencedReport } from "../app/lib/report-reference.mjs";

test("a period reference opens that financial reporting period", () => {
  const link = reportReferenceLink("/research/companies/CN/601799/reports/2026-H1.md");
  const reports = [
    { period: "2026-Q3", path: "/data/reports/601799/2026-Q3.md" },
    { period: "2026-H1", path: "/data/reports/601799/2026-H1.md" },
  ];
  const version = new URL(link, "https://research.local").searchParams.get("version");
  assert.equal(referencedReport(reports, version), reports[1]);
  assert.equal(referencedReport(reports, null), reports[0]);
  assert.equal(referencedReport(reports, "2025-FY"), null);
  assert.equal(reportReferenceLink("/research/companies/CN/601799/reports/draft.md"), null);
});

test("model links retain company and period when resolved from repository reports", async () => {
  const { researchResourceLink } = await import("../app/lib/report-reference.mjs");
  const source = "research/companies/CN/300750/reports/2026-Q3.md";
  const context = { companyReportPaths: ["research/companies/CN/300750/reports/2026-H1.md"] };
  assert.equal(researchResourceLink("../models/2026-Q3.py", source), "/data/models/300750/2026-Q3.py");
  assert.equal(researchResourceLink("../models/2026-H1-output.json?download=1#result", source),
    "/data/models/300750/2026-H1-output.json?download=1#result");
  assert.equal(researchResourceLink("/research/companies/CN/600674/models/2026-Q3.py", source),
    "/data/models/600674/2026-Q3.py");
  assert.equal(researchResourceLink("2026-H1.md#结论", source, context), "/reports/300750?version=2026-H1#%E7%BB%93%E8%AE%BA");
  for (const href of ["https://example.com/a", "//example.com/a", "mailto:reader@example.com", "#结论"]) {
    assert.equal(researchResourceLink(href, source), href);
  }
  for (const href of ["javascript:alert(1)", "data:text/html,hello", "../models/secret.txt", "../models/2026-Q3-output.json/../../secret", "../models/2026-Q3.py.exe"]) {
    assert.equal(researchResourceLink(href, source), undefined);
  }
});

const industryPath = "research/industries/property-chain/reports/2026-11-16.md";
const macroPath = "research/macro/property-credit/reports/2026-11-16.md";
const companyPath = "research/companies/CN/000002/reports/2026-H1.md";
const directory = {
  companyReportPaths: [companyPath, "research/companies/HK/00688/reports/2026-H1.md"],
  documents: [
    { kind: "industry", type: "report", topic: "property-chain", sourcePath: industryPath, version: "2026-11-16", status: "published", indicatorPath: "/data/indicators/property-chain.json" },
    { kind: "industry", type: "report", topic: "property-chain", sourcePath: industryPath.replace("11-16", "10-28"), version: "2026-10-28", status: "published", indicatorPath: "/data/indicators/property-chain.json" },
    { kind: "macro", type: "report", topic: "property-credit", sourcePath: macroPath, version: "2026-11-16", status: "published" },
    { kind: "macro", type: "reference", topic: "valuation", sourcePath: "research/macro/reference/valuation.md", version: "2026-10-28", status: "published" },
  ],
};

test("company, industry and macro links retain the registered version and chapter", async () => {
  const { researchResourceLink } = await import("../app/lib/report-reference.mjs");
  assert.equal(researchResourceLink("../../../../industries/property-chain/reports/2026-11-16.md#需求与回款", companyPath, directory),
    "/industries?topic=property-chain&version=2026-11-16&view=report#%E9%9C%80%E6%B1%82%E4%B8%8E%E5%9B%9E%E6%AC%BE");
  assert.equal(researchResourceLink("../../../macro/property-credit/reports/2026-11-16.md#信用传导", industryPath, directory),
    "/macro?topic=property-credit&version=2026-11-16&view=report#%E4%BF%A1%E7%94%A8%E4%BC%A0%E5%AF%BC");
  assert.equal(researchResourceLink("../../../companies/CN/000002/reports/2026-H1.md#财务质量", macroPath, directory),
    "/reports/000002?version=2026-H1#%E8%B4%A2%E5%8A%A1%E8%B4%A8%E9%87%8F");
  assert.equal(researchResourceLink("/research/companies/HK/00688/reports/2026-H1.md#现金", industryPath, directory),
    "/reports/HK-00688?version=2026-H1#%E7%8E%B0%E9%87%91");
  assert.equal(researchResourceLink("../../../macro/reference/valuation.md#定义", industryPath, directory),
    "/macro?topic=valuation&version=2026-10-28&view=reference#%E5%AE%9A%E4%B9%89");
  assert.equal(researchResourceLink("./2026-10-28.md", industryPath, directory), "/industries?topic=property-chain&version=2026-10-28&view=report");
  assert.equal(researchResourceLink("/reports/000002?version=2026-H1#财务质量", industryPath, directory),
    "/reports/000002?version=2026-H1#%E8%B4%A2%E5%8A%A1%E8%B4%A8%E9%87%8F");
});

test("unregistered research and unsafe URLs remain non-links", async () => {
  const { researchResourceLink } = await import("../app/lib/report-reference.mjs");
  for (const href of ["../../../macro/private/reports/2026-11-16.md", "../../../companies/CN/000002/reports/2026-Q3.md",
    "../../../sectors/real-estate.md", "/industries?topic=unknown", "/reports/000002?version=2025-FY",
    "javascript:alert(1)", "data:text/html,test", "file:///etc/passwd", "https://", "https:\\example.com", "java\nscript:alert(1)"]) {
    assert.equal(researchResourceLink(href, industryPath, directory), undefined, href);
  }
  assert.equal(researchResourceLink(companyPath, undefined), undefined);
  assert.equal(researchResourceLink(`/${companyPath}`, undefined), undefined);
});

test("topic routes keep explicit historical versions and never attach current indicators", async () => {
  const { researchResourceLink } = await import("../app/lib/report-reference.mjs");
  assert.equal(researchResourceLink("/industries?topic=property-chain&view=report&panel=indicators", macroPath, directory),
    "/industries?topic=property-chain&version=2026-11-16&view=report&panel=indicators");
  assert.equal(researchResourceLink("/industries?topic=property-chain&version=2026-10-28&view=report&panel=indicators#需求", macroPath, directory),
    "/industries?topic=property-chain&version=2026-10-28&view=report#%E9%9C%80%E6%B1%82");
  assert.equal(researchResourceLink("/industries?topic=property-chain&version=2020-01-01&view=report", macroPath, directory), undefined);
  const revisions = { documents: [2, 10].map((revision) => ({ ...directory.documents[0], version: `2026-11-16-r${revision}` })) };
  assert.equal(researchResourceLink("/industries?topic=property-chain", macroPath, revisions), "/industries?topic=property-chain&version=2026-11-16-r10&view=report");
});

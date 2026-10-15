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

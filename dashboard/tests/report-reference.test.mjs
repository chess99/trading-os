import assert from "node:assert/strict";
import test from "node:test";
import { reportReferenceLink, referencedReport } from "../app/lib/report-reference.mjs";

test("a dated reference still opens its original report after a new current report arrives", () => {
  const link = reportReferenceLink("/research/companies/CN/601799/reports/2026-09-08-02.md");
  const reports = [
    { date: "2026-10-30", path: "/data/reports/601799/2026-10-30.md" },
    { date: "2026-09-08-02", path: "/data/reports/601799/2026-09-08-02.md" },
  ];
  const version = new URL(link, "https://research.local").searchParams.get("version");
  assert.equal(referencedReport(reports, version), reports[1]);
  assert.equal(referencedReport(reports, null), reports[0]);
  assert.equal(referencedReport(reports, "2026-01-01"), null);
  assert.equal(reportReferenceLink("/research/companies/CN/601799/legacy/2026-01-01.md"), null);
});

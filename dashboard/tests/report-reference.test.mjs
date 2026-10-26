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
  assert.equal(researchResourceLink("../models/2026-Q3.py", source), "/data/models/300750/2026-Q3.py");
  assert.equal(researchResourceLink("../models/2026-H1-output.json?download=1#result", source),
    "/data/models/300750/2026-H1-output.json?download=1#result");
  assert.equal(researchResourceLink("/research/companies/CN/600674/models/2026-Q3.py", source),
    "/data/models/600674/2026-Q3.py");
  assert.equal(researchResourceLink("2026-H1.md#结论", source), "/reports/300750?version=2026-H1#%E7%BB%93%E8%AE%BA");
  for (const href of ["https://example.com/a", "//example.com/a", "mailto:reader@example.com", "#结论"]) {
    assert.equal(researchResourceLink(href, source), href);
  }
  for (const href of ["javascript:alert(1)", "data:text/html,hello", "../models/secret.txt", "../models/2026-Q3-output.json/../../secret", "../models/2026-Q3.py.exe"]) {
    assert.equal(researchResourceLink(href, source), undefined);
  }
});

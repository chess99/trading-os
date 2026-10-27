import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { researchResourceLink } from "../app/lib/report-reference.mjs";

// Discover completed reports, not a frozen pool or a list of expected future reports.
test("every completed 2026 Q3 report exposes its own reproducible model artifacts", async () => {
  const catalog = JSON.parse(await readFile(new URL("../public/data/research-catalog.json", import.meta.url), "utf8"));
  const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");
  let checked = 0;
  for (const company of catalog.companies) {
    const report = company.reports.find((item) => item.period === "2026-Q3");
    if (!report) continue;
    const expectedSource = `research/companies/CN/${company.ticker}/reports/2026-Q3.md`;
    assert.equal(report.sourcePath, expectedSource);
    const markdown = await readFile(new URL(`../../${expectedSource}`, import.meta.url), "utf8");
    const links = [...markdown.matchAll(/\[[^\]]+\]\(([^)]+)\)/gu)]
      .map((match) => researchResourceLink(match[1], expectedSource));
    // Validate every declared local model attachment, including auxiliary files.
    for (const match of markdown.matchAll(/\[[^\]]+\]\(([^)]+)\)/gu)) {
      const href = match[1];
      if (!href.startsWith("../models/")) continue;
      const resolved = researchResourceLink(href, expectedSource);
      assert.ok(resolved, `${company.ticker}: invalid declared model link ${href}`);
      const path = resolved.split(/[?#]/u, 1)[0];
      assert.ok(path.startsWith(`/data/models/${company.ticker}/`),
        `${company.ticker}: cross-company attachment ${href}`);
      const filename = path.split("/").at(-1);
      const source = await readFile(new URL(
        `../../research/companies/CN/${company.ticker}/models/${filename}`, import.meta.url));
      const exported = await readFile(new URL(`../public${path}`, import.meta.url));
      assert.equal(digest(exported), digest(source), `${company.ticker}: attachment mismatch ${href}`);
    }
    // A genuinely unmodellable result may have no model; any existing model must ship
    // as a complete, linked source/output pair. This does not require a false valuation.
    let model;
    try { model = await readFile(new URL(`../../research/companies/CN/${company.ticker}/models/2026-Q3.py`, import.meta.url)); }
    catch (error) { if (error.code === "ENOENT") continue; throw error; }
    for (const suffix of [".py", "-output.json"]) {
      const filename = `2026-Q3${suffix}`;
      const path = `/data/models/${company.ticker}/${filename}`;
      assert.ok(links.includes(path), `${company.ticker}: missing reader link ${filename}`);
      const original = suffix === ".py" ? model : await readFile(new URL(`../../research/companies/CN/${company.ticker}/models/${filename}`, import.meta.url));
      const exported = await readFile(new URL(`../public${path}`, import.meta.url));
      assert.equal(digest(exported), digest(original), `${company.ticker}: wrong company/period/content at ${path}`);
      if (suffix === "-output.json") assert.doesNotThrow(() => JSON.parse(exported));
      checked++;
    }
  }
  assert.ok(checked >= 10, "published pilot fixtures must remain covered alongside additional reports");
});

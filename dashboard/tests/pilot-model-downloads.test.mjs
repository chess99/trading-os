import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { researchResourceLink } from "../app/lib/report-reference.mjs";

// This is a bounded regression fixture for the Q3 pilot, not the dashboard's pool.
const pilotTickers = ["300012", "300750", "600066", "600674", "600941"];
const period = "2026-Q3";
const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");
test("all ten Q3 pilot model links resolve to the correct exported source bytes", async () => {
  const catalog = JSON.parse(await readFile(new URL("../public/data/research-catalog.json", import.meta.url), "utf8"));
  let checked = 0;
  for (const ticker of pilotTickers) {
    const report = catalog.companies.find((company) => company.ticker === ticker)?.reports.find((item) => item.period === period);
    assert.ok(report, `${ticker} ${period} report must exist`);
    assert.equal(report.sourcePath, `research/companies/CN/${ticker}/reports/${period}.md`);
    const markdown = await readFile(new URL(`../../${report.sourcePath}`, import.meta.url), "utf8");
    const links = [...markdown.matchAll(/\[[^\]]+\]\(([^)]+)\)/gu)].map((match) => researchResourceLink(match[1], report.sourcePath));
    for (const extension of [".py", "-output.json"]) {
      const filename = `${period}${extension}`;
      const path = `/data/models/${ticker}/${filename}`;
      assert.ok(links.includes(path), `${ticker} ${period} must link ${filename}`);
      const source = await readFile(new URL(`../../research/companies/CN/${ticker}/models/${filename}`, import.meta.url));
      const exported = await readFile(new URL(`../public${path}`, import.meta.url));
      assert.equal(digest(exported), digest(source), `${ticker} ${period} ${filename} SHA-256`);
      if (extension === "-output.json") assert.doesNotThrow(() => JSON.parse(exported));
      else assert.match(exported.toString(), /(?:import |def )/u);
      checked++;
    }
  }
  assert.equal(checked, 10);
});

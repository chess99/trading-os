import assert from "node:assert/strict";
import test from "node:test";
import { mkdtemp, mkdir, writeFile, rm, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { validateIndustryCatalog, loadIndustryCatalog } from "../scripts/lib/industry-catalog.mjs";
import { initialIndustryRegion, industryTopicChoices } from "../app/lib/industry-view.mjs";

const sample = () => ({ schemaVersion: 1,
  groups: [{ id: "consumer", label: "消费" }, { id: "finance", label: "金融" }],
  topics: [{ id: "retail", label: "零售", group: "consumer", scope: "中国实体与线上渠道。" },
    { id: "restaurants", label: "餐饮", group: "consumer", scope: "中国门店与加盟体系。" },
    { id: "banking", label: "银行", group: "finance", scope: "中国负债、信用和资本。" }] });

test("industry taxonomy keeps source order and remains independent of report dates and counts", () => {
  const catalog = sample();
  assert.equal(validateIndustryCatalog(catalog), catalog);
  assert.deepEqual(industryTopicChoices(catalog, [], "consumer").map((topic) => topic.id), ["retail", "restaurants"]);
  assert.equal(industryTopicChoices(catalog, [], "", "资本")[0].id, "banking");
  assert.equal(industryTopicChoices(catalog, [{ topic: "retail", title: "渠道库存", summary: "周转" }], "", "库存")[0].id, "retail");
});

test("taxonomy rejects duplicate identities, unknown groups and duplicated publication metadata", () => {
  for (const change of [
    (catalog) => catalog.topics.push({ ...catalog.topics[0] }),
    (catalog) => catalog.groups.push({ ...catalog.groups[0] }),
    (catalog) => catalog.topics[0].group = "unknown",
    (catalog) => catalog.topics[0].scope = "",
    (catalog) => catalog.topics[0].currentReportPath = "current.md",
    (catalog) => catalog.groups.push({ id: "empty", label: "空类" }),
  ]) { const catalog = sample(); change(catalog); assert.throws(() => validateIndustryCatalog(catalog)); }
});

test("reading-area selection preserves old deep links without filling China topics from overseas reports", () => {
  const directory = { industryCatalog: sample(), documents: [
    { kind: "industry", topic: "banking", version: "2026-10-28", regionId: null },
    { kind: "industry", topic: "banking", version: "2026-11-16", regionId: "cn" },
    { kind: "industry", topic: "global-energy", version: "2026-10-28", regionId: null },
  ] };
  for (const [query, region] of [["", "cn"], ["topic=restaurants", "cn"], ["topic=global-energy", "archive"],
    ["topic=banking&version=2026-10-28", "archive"], ["topic=banking&version=2026-11-16", "cn"],
    ["topic=banking&version=2026-10-28&region=cn", "cn"]]) {
    assert.equal(initialIndustryRegion(directory, new URLSearchParams(query)), region);
  }
  assert.equal(initialIndustryRegion({ documents: [] }, new URLSearchParams()), "archive");
});

test("industry catalog imports reject symlink substitution", async () => {
  const root = await mkdtemp(join(tmpdir(), "industry-catalog-"));
  try {
    assert.equal(await loadIndustryCatalog(root), null);
    await mkdir(join(root, "research/industries"), { recursive: true });
    await writeFile(join(root, "research/industries/catalog.json"), JSON.stringify(sample()));
    assert.deepEqual(await loadIndustryCatalog(root), sample());
    await writeFile(join(root, "outside.json"), JSON.stringify(sample()));
    await rm(join(root, "research/industries/catalog.json"));
    await symlink(join(root, "outside.json"), join(root, "research/industries/catalog.json"));
    await assert.rejects(loadIndustryCatalog(root), /符号链接/u);
  } finally { await rm(root, { recursive: true, force: true }); }
});

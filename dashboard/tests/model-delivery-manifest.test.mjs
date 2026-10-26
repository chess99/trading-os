import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cp, mkdir, mkdtemp, readFile, readdir, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { modelArtifactName, researchResourceLink } from "../app/lib/report-reference.mjs";
import { buildResearchData } from "../scripts/build-research-data.mjs";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const period = "2026-Q3", source = "research/companies/CN/300033/reports/2026-Q3.md";

async function fixture(t, report = "[model](../models/2026-Q3.py) [output](../models/2026-Q3-output.json)") {
  const dir = await mkdtemp(join(tmpdir(), "model-delivery-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  for (const name of ["research/standards", "coverage/cn-a", "screening/cn-a/value-quality", "research/companies/CN/300033/reports", "research/companies/CN/300033/models"]) await mkdir(join(dir, name), { recursive: true });
  await cp(join(root, "research/standards/registry.json"), join(dir, "research/standards/registry.json"));
  await writeFile(join(dir, "coverage/cn-a/research_state.jsonl"), "");
  await writeFile(join(dir, "coverage/cn-a/research_queue.jsonl"), "");
  await writeFile(join(dir, "screening/cn-a/value-quality/pool.json"), JSON.stringify({ schema_version: 2, companies: [] }));
  await writeFile(join(dir, source), `# Fixture\n信息截止：2026-10-26\n${report}\n`);
  const models = join(dir, "research/companies/CN/300033/models");
  await writeFile(join(models, `${period}.py`), "raise RuntimeError('must never execute at export time')\n");
  await writeFile(join(models, `${period}-output.json`), "{}\n");
  return { dir, models };
}

test("closed artifact grammar and new auxiliary reader company/period boundaries", () => {
  for (const name of ["2026-Q3.py", "2026-Q3-output.json", "2026-Q3-case-base.json", "2026-Q3-case-margin_minus5pp_fromY1.json", "2026-Q3-sources-assumptions.md", "2026-Q3-independent-recompute.py"]) {
    assert.equal(modelArtifactName(name, period), true, name);
    assert.equal(researchResourceLink(`../models/${name}`, source), `/data/models/300033/${name}`);
  }
  for (const name of ["../2026-Q3-case-base.json", "2026-Q3-case-a/b.json", "2026-Q3-case-%2e.json", "2026-Q3-secret.md", "2026-Q3-case-a.json.exe", "2026-Q3-case-a-b.json", "2025-FY-case-base.json"]) assert.equal(modelArtifactName(name, period), false, name);
  for (const href of ["https://example.com/models/2026-Q3-case-base.json", "//example.com/models/2026-Q3-sources-assumptions.md", "../models/2025-FY-case-base.json", "/research/companies/CN/002270/models/2026-Q3-case-base.json", "../models/x/../2026-Q3-case-base.json", "../models/%2e%2e/models/2026-Q3-case-base.json", "../models/2026-Q3-case-base.json/../2026-Q3-case-base.json", "../models/2026-Q3-sources-assumptions.md.exe", "file:///research/companies/CN/300033/models/2026-Q3-case-base.json", "javascript:alert(1)"]) assert.equal(researchResourceLink(href, source), undefined, href);
  // Legacy explicit cross-company primary model and report-version links stay unchanged.
  assert.equal(researchResourceLink("/research/companies/CN/600674/models/2026-Q3.py", source), "/data/models/600674/2026-Q3.py");
  assert.equal(researchResourceLink("2026-H1.md#x", source), "/reports/300033?version=2026-H1#x");
});

test("legacy two-file export plus only reader-linked closed auxiliaries", async (t) => {
  const { dir, models } = await fixture(t, "[model](../models/2026-Q3.py) [output](../models/2026-Q3-output.json) [sources](../models/2026-Q3-sources-assumptions.md)\n[recompute]: ../models/2026-Q3-independent-recompute.py\n[other](/research/companies/CN/002270/models/2026-Q3-sources-assumptions.md)\n[external](https://example.com/2026-Q3-secret.md)");
  for (const name of ["2026-Q3-sources-assumptions.md", "2026-Q3-independent-recompute.py", "2026-Q3-secret.md", "2026-Q3-case-unused.json"]) await writeFile(join(models, name), name);
  await buildResearchData(dir);
  const exported = join(dir, "dashboard/public/data/models/300033");
  assert.deepEqual((await readdir(exported)).sort(), ["2026-Q3-independent-recompute.py", "2026-Q3-output.json", "2026-Q3-sources-assumptions.md", "2026-Q3.py"].sort());
  for (const name of await readdir(exported)) assert.equal(sha(await readFile(join(exported, name))), sha(await readFile(join(models, name))));
});

test("exact manifest closes complete case export and is deterministic", async (t) => {
  const { dir, models } = await fixture(t);
  const caseName = "margin_minus5pp_fromY1", name = `${period}-case-${caseName}.json`, bytes = Buffer.from('{"complete":"all annual rows"}\n');
  await writeFile(join(models, name), bytes);
  await writeFile(join(models, `${period}-output.json`), JSON.stringify({ schema: "cn300033_complete_case_manifest_v1", case_files: { [caseName]: { file: name, bytes: bytes.length, file_sha256: sha(bytes) } } }));
  await buildResearchData(dir);
  const out = join(dir, "dashboard/public/data/models/300033");
  const first = new Map(await Promise.all((await readdir(out)).map(async (file) => [file, sha(await readFile(join(out, file)))])));
  assert.equal(first.size, 3);assert.equal(first.get(name), sha(bytes));
  await buildResearchData(dir);
  for (const [file, digest] of first) assert.equal(sha(await readFile(join(out, file))), digest);
});

test("manifest rejects traversal external cross-period aliases and bad digests", async (t) => {
  for (const filename of ["../2026-Q3-case-base.json", "https://example.com/x.json", "/tmp/2026-Q3-case-base.json", "2025-FY-case-base.json", "../../002270/models/2026-Q3-case-base.json", "2026-Q3-sources-assumptions.md", "2026-Q3-case-other.json"]) {
    const { dir, models } = await fixture(t);
    await writeFile(join(models, `${period}-output.json`), JSON.stringify({ schema: "cn300033_complete_case_manifest_v1", case_files: { base: { file: filename, bytes: 2, file_sha256: "0".repeat(64) } } }));
    await assert.rejects(buildResearchData(dir), /Unsafe split model manifest entry/u);
  }
  const { dir, models } = await fixture(t);
  await writeFile(join(models, `${period}-case-base.json`), "{}");
  await writeFile(join(models, `${period}-output.json`), JSON.stringify({ schema: "cn300033_complete_case_manifest_v1", case_files: { base: { file: `${period}-case-base.json`, bytes: 2, file_sha256: "0".repeat(64) } } }));
  await assert.rejects(buildResearchData(dir), /does not match manifest/u);
});

test("missing required links and nonmanifest cases fail rather than publishing partial closure", async (t) => {
  const absent = await fixture(t, "[missing](../models/2026-Q3-sources-assumptions.md)");
  await assert.rejects(buildResearchData(absent.dir), { code: "ENOENT" });
  const orphan = await fixture(t, "[case](../models/2026-Q3-case-base.json)");
  await writeFile(join(orphan.models, `${period}-case-base.json`), "{}");
  await assert.rejects(buildResearchData(orphan.dir), /absent from its split manifest/u);
  const linked = await fixture(t, "[sources](../models/2026-Q3-sources-assumptions.md)");
  await writeFile(join(linked.dir,"private.md"), "private");
  await symlink(join(linked.dir,"private.md"), join(linked.models,"2026-Q3-sources-assumptions.md"));
  await assert.rejects(buildResearchData(linked.dir), /regular file/u);
});

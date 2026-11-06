import assert from "node:assert/strict";
import test from "node:test";
import { mkdtemp, mkdir, readFile, readdir, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { exportModelArtifacts } from "../scripts/build-research-data.mjs";
import { modelArtifactName, researchResourceLink } from "../app/lib/report-reference.mjs";

async function fixture(run) {
  const root = await mkdtemp(join(tmpdir(), "model-artifacts-"));
  try {
    const directory = join(root, "research/companies/HK/00700/models");
    const output = join(root, "dashboard/public/data");
    await mkdir(directory, { recursive: true });
    await mkdir(output, { recursive: true });
    await run({ root, directory, output });
  } finally { await rm(root, { recursive: true, force: true }); }
}

test("only readable period files are recognized across markets", () => {
  for (const suffix of [".py", "-input.json", "-output.json", "-sources-assumptions.md", "-independent-recompute.py"]) {
    assert.equal(modelArtifactName(`2026-Q3${suffix}`, "2026-Q3"), true);
    assert.equal(modelArtifactName(`2026-Q3${suffix}`, "2026-H1"), false);
  }
  for (const suffix of ["-output.json.xz", "-verification-part-000.bin", "-output-production-part-000.xzpart", "-verification-payload.json", "-case-base.json"]) {
    assert.equal(modelArtifactName(`2026-Q3${suffix}`), false);
  }
  const report = "research/companies/HK/00700/reports/2026-Q3.md";
  assert.equal(modelArtifactName("2026-Q3/calculation.py", "2026-Q3"), true);
  assert.equal(modelArtifactName("2026-Q3/candidate.json", "2026-Q3"), false);
  assert.equal(researchResourceLink("../models/2026-Q3-input.json", report), "/data/models/HK-00700/2026-Q3-input.json");
  assert.equal(researchResourceLink("../models/2026-Q3/calculation.py", report), "/data/models/HK-00700/2026-Q3/calculation.py");
  assert.equal(researchResourceLink("../models/secret/../2026-Q3.py", report), undefined);
});

test("small inputs and results export without code execution or archive traversal", async () => {
  await fixture(async ({ root, directory, output }) => {
    await writeFile(join(directory, "2026-Q3.py"), "raise RuntimeError('do not execute during build')\n");
    await mkdir(join(directory, "2026-Q3"));
    await writeFile(join(directory, "2026-Q3/calculation.py"), "def value(): return 6\n");
    await writeFile(join(directory, "2026-Q3-input.json"), '{"growth":0.02}');
    await writeFile(join(directory, "2026-Q3-output.json"), '{"symbol":"HK:00700","value_range":null}');
    await writeFile(join(directory, "2026-Q3-output.json.xz"), "old archive");
    await writeFile(join(directory, "secret.txt"), "private working note");
    await exportModelArtifacts(root, output, "HK", "00700", "2026-Q3", "", "research/companies/HK/00700/reports/2026-Q3.md");
    const target = join(output, "models/HK-00700");
    assert.deepEqual((await readdir(target)).sort(), ["2026-Q3", "2026-Q3-input.json", "2026-Q3-output.json", "2026-Q3.py"]);
    assert.equal(await readFile(join(target, "2026-Q3-input.json"), "utf8"), '{"growth":0.02}');
    assert.equal(await readFile(join(target, "2026-Q3/calculation.py"), "utf8"), "def value(): return 6\n");
  });
});

test("oversized files and disguised archives fail the ordinary build", async () => {
  await fixture(async ({ root, directory, output }) => {
    const run = () => exportModelArtifacts(root, output, "HK", "00700", "2026-Q3", "", "research/companies/HK/00700/reports/2026-Q3.md");
    await writeFile(join(directory, "2026-Q3-output.json"), '{"schema":"trading_os_lossless_json_xz_v1"}');
    await assert.rejects(run, /Archived model output/u);
    await writeFile(join(directory, "2026-Q3-output.json"), " ".repeat(1024 ** 2 + 1));
    await assert.rejects(run, /budget exceeded/u);
  });
});

test("a linked model directory cannot publish files from another location", async () => {
  await fixture(async ({ root, directory, output }) => {
    const other = join(root, "another-location");
    await mkdir(other);
    await writeFile(join(other, "2026-Q3-output.json"), '{"private":"not a research artifact"}');
    await rm(directory, { recursive: true });
    await symlink(other, directory, process.platform === "win32" ? "junction" : "dir");
    await assert.rejects(
      () => exportModelArtifacts(root, output, "HK", "00700", "2026-Q3", "", "research/companies/HK/00700/reports/2026-Q3.md"),
      /must not traverse symbolic links/u,
    );
  });
});

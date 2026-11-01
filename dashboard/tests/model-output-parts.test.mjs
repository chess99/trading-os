import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { createServer } from 'node:http';
import { cp, mkdir, mkdtemp, readFile, readdir, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { buildResearchData } from '../scripts/build-research-data.mjs';
import { parseOutputParts, verifyOutputParts, EIGHT_NAMES } from '../scripts/lib/model-output-parts.mjs';
import { modelArtifactName, researchResourceLink } from '../app/lib/report-reference.mjs';
import { xzManifestEntry } from '../scripts/lib/model-xz.mjs';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const sha = (b) => createHash('sha256').update(b).digest('hex');
const canonical = (m) => Buffer.from(JSON.stringify(m) + '\n');
const period = '2026-Q3', symbol = '300661';
const producer = Buffer.from("raise RuntimeError('codec/build must never execute research')\n");
const producerSha = sha(producer);
const raw = Buffer.from('{"all_years":[1,2,3],"complete":true}\n');
const encoded = spawnSync('python3', ['-I', '-c', 'import lzma,sys;sys.stdout.buffer.write(lzma.compress(sys.stdin.buffer.read(),preset=0))'], { input: raw });
assert.equal(encoded.status, 0);
const xz = encoded.stdout;
function manifest(code = symbol) {
  const names = code === '300015' ? EIGHT_NAMES : ['main'];
  return { schema: 'trading_os_lossless_json_xz_parts_v1', artifact_kind: 'transport_manifest_not_model_result', period, symbol: code, producer_sha256: producerSha, layout: code === '300015' ? 'cn300015_complete_eight_json' : 'single_complete_json', outputs: names.map((name) => ({ name, compression: 'xz', compressed_bytes: xz.length, compressed_sha256: sha(xz), expanded_bytes: raw.length, expanded_sha256: sha(raw), expanded_media_type: 'application/json', parts: [{ file: `${period}-output-${name}-part-000.xzpart`, bytes: xz.length, sha256: sha(xz) }] })) };
}
async function fixture(t, code = symbol) {
  const dir = await mkdtemp(join(tmpdir(), 'actual-output-parts-')); t.after(() => rm(dir, { recursive: true, force: true }));
  for (const name of ['research/standards', 'coverage/cn-a', 'screening/cn-a/value-quality', `research/companies/CN/${code}/reports`, `research/companies/CN/${code}/models`]) await mkdir(join(dir, name), { recursive: true });
  await cp(join(root, 'research/standards/registry.json'), join(dir, 'research/standards/registry.json'));
  for (const name of ['research_state.jsonl', 'research_queue.jsonl']) await writeFile(join(dir, 'coverage/cn-a', name), '');
  await writeFile(join(dir, 'screening/cn-a/value-quality/pool.json'), JSON.stringify({ schema_version: 2, companies: [] }));
  await writeFile(join(dir, `research/companies/CN/${code}/reports/${period}.md`), `# Test\n[complete outputs](../models/${period}-output.json)\n`);
  const models = join(dir, `research/companies/CN/${code}/models`), m = manifest(code);
  await writeFile(join(models, `${period}.py`), producer);
  await writeFile(join(models, `${period}-output.json`), canonical(m));
  for (const entry of m.outputs) await writeFile(join(models, entry.parts[0].file), xz);
  return { dir, models, m, code };
}
test('closed output names cannot impersonate verification or arbitrary paths', () => {
  const file = manifest().outputs[0].parts[0].file;
  assert.equal(modelArtifactName(file, period), true);
  assert.equal(researchResourceLink(`../models/${file}`, `research/companies/CN/300661/reports/${period}.md`), `/data/models/300661/${file}`);
  for (const name of ['2026-Q3-output-unknown-part-000.xzpart', '2026-Q3-output-main-part-0.xzpart', '2026-Q3-output-main-part-000.bin', '../' + file]) assert.equal(modelArtifactName(name, period), false);
});
test('canonical identity, duplicate keys, coverage and original single-XZ cap remain strict', () => {
  const m = manifest(); parseOutputParts(canonical(m), period, symbol, producerSha);
  const edits = [x => x.extra = true, x => x.producer_sha256 = '0'.repeat(64), x => x.outputs[0].expanded_bytes = 513 * 1024 ** 2, x => x.outputs[0].parts[0].file = '../secret', x => x.outputs[0].parts[0].bytes = true, x => x.outputs[0].parts.push(x.outputs[0].parts[0])];
  for (const edit of edits) { const bad = structuredClone(m); edit(bad); assert.throws(() => parseOutputParts(canonical(bad), period, symbol, producerSha)); }
  assert.throws(() => parseOutputParts(Buffer.from(canonical(m).toString().replace('"schema":', '"schema":"duplicate","schema":')), period, symbol, producerSha));
  const eight = manifest('300015'); parseOutputParts(canonical(eight), period, '300015', producerSha); eight.outputs.pop(); assert.throws(() => parseOutputParts(canonical(eight), period, '300015', producerSha));
  assert.throws(() => xzManifestEntry({ schema: 'trading_os_lossless_json_xz_v1', artifact_kind: 'transport_manifest_not_model_result', compression: 'xz', file: `${period}-output.json.xz`, compressed_bytes: 101 * 1024 ** 2, compressed_sha256: sha(xz), expanded_bytes: raw.length, expanded_sha256: sha(raw), expanded_media_type: 'application/json' }, period), /Unsafe XZ/);
});
test('actual build exports every full document without executing producer', async (t) => {
  for (const code of [symbol, '300015']) {
    const f = await fixture(t, code); verifyOutputParts(f.models, canonical(f.m), period, code, producerSha); await buildResearchData(f.dir);
    const output = join(f.dir, `dashboard/public/data/models/${code}`);
    const expected = [`${period}.py`, `${period}-output.json`, ...f.m.outputs.flatMap(e => e.parts.map(p => p.file))].sort();
    assert.deepEqual((await readdir(output)).sort(), expected);
    verifyOutputParts(output, await readFile(join(output, `${period}-output.json`)), period, code, producerSha);
  }
});
test('build rejects missing/tampered parts, symlink escapes and unknown linked parts', async (t) => {
  const a = await fixture(t); await rm(join(a.models, a.m.outputs[0].parts[0].file)); await assert.rejects(buildResearchData(a.dir), /Output parts integrity/);
  const b = await fixture(t); await writeFile(join(b.models, b.m.outputs[0].parts[0].file), Buffer.alloc(xz.length)); await assert.rejects(buildResearchData(b.dir), /Output parts integrity/);
  const c = await fixture(t); const file = c.m.outputs[0].parts[0].file; await rm(join(c.models, file)); await writeFile(join(c.dir, 'outside.xz'), xz); await symlink(join(c.dir, 'outside.xz'), join(c.models, file)); await assert.rejects(buildResearchData(c.dir), /Output parts integrity/);
  const d = await fixture(t); await writeFile(join(d.models, `${period}-output.json`), '{}'); await writeFile(join(d.dir, `research/companies/CN/${symbol}/reports/${period}.md`), `# Test\n[orphan](../models/${file})\n`); await assert.rejects(buildResearchData(d.dir), /absent from its complete manifest/);
});
test('real HTTP download reconstructs all eight JSONs; missing/reordered/wrong-hash downloads fail', async (t) => {
  const f = await fixture(t, '300015'); await buildResearchData(f.dir); const output = join(f.dir, 'dashboard/public/data/models/300015');
  const allowed = new Set(await readdir(output));
  const server = createServer(async (req, res) => { const name = req.url.slice(1); if (!allowed.has(name)) { res.writeHead(404); res.end(); return; } res.end(await readFile(join(output, name))); });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  t.after(() => new Promise(resolve => server.close(resolve)));
  const url = `http://127.0.0.1:${server.address().port}`; const download = join(f.dir, 'real-http-download'); await mkdir(download);
  for (const name of allowed) { const response = await fetch(`${url}/${name}`); assert.equal(response.status, 200); await writeFile(join(download, name), Buffer.from(await response.arrayBuffer())); }
  const desc = await readFile(join(download, `${period}-output.json`)); verifyOutputParts(download, desc, period, '300015', sha(await readFile(join(download, `${period}.py`))));
  const bad = structuredClone(f.m); bad.outputs.reverse(); assert.throws(() => verifyOutputParts(download, canonical(bad), period, '300015', producerSha));
  bad.outputs.reverse(); bad.outputs[0].compressed_sha256 = '0'.repeat(64); assert.throws(() => verifyOutputParts(download, canonical(bad), period, '300015', producerSha));
  await rm(join(download, f.m.outputs[0].parts[0].file)); assert.throws(() => verifyOutputParts(download, desc, period, '300015', producerSha));
});

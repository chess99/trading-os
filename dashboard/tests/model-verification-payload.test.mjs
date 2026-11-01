import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { cp, link, mkdir, mkdtemp, readFile, readdir, rename, symlink, writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { buildResearchData } from '../scripts/build-research-data.mjs';
import { modelArtifactName, researchResourceLink } from '../app/lib/report-reference.mjs';
import { parseVerificationManifest } from '../scripts/lib/model-verification-payload.mjs';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const period = '2026-Q3', part = `${period}-verification-part-000.bin`, file = `${period}-verification-payload.json`;
const raw = Buffer.from('whole original opaque verification ZIP fixture'), sha = createHash('sha256').update(raw).digest('hex');
const manifest = { schema: 'trading_os_verification_payload_v1', period, payload_bytes: raw.length, payload_sha256: sha, parts: [{ file: part, bytes: raw.length, sha256: sha }] };
const encode = (m) => Buffer.from(JSON.stringify(m) + '\n');
async function fixture(m = manifest, options = {}) {
  const dir = await mkdtemp(join(tmpdir(), 'verification-sidecar-regression-'));
  for (const name of ['research/standards', 'coverage/cn-a', 'screening/cn-a/value-quality', 'research/companies/CN/000001/reports', 'research/companies/CN/000001/models']) await mkdir(join(dir, name), { recursive: true });
  await cp(join(root, 'research/standards/registry.json'), join(dir, 'research/standards/registry.json'));
  for (const name of ['research_state.jsonl', 'research_queue.jsonl']) await writeFile(join(dir, 'coverage/cn-a', name), '');
  await writeFile(join(dir, 'screening/cn-a/value-quality/pool.json'), JSON.stringify({ schema_version: 2, companies: [] }));
  await writeFile(join(dir, 'research/companies/CN/000001/reports/2026-Q3.md'), `# Fixture\n[transport](../models/${options.orphan ? part : file})\n`);
  const models = join(dir, 'research/companies/CN/000001/models');
  await writeFile(join(models, `${period}.py`), "raise RuntimeError('build must not execute producer')\n");
  await writeFile(join(models, `${period}-output.json`), '{"fixture":true}\n');
  const reader = await readFile(join(root, 'src/trading_os/model_verification_payload.py'), 'utf8');
  const checker = reader + `\nassert verification_payload(Path(__file__).resolve().parent, '${period}', ${raw.length}, '${sha}') == ${JSON.stringify(raw.toString()).replace(/^"|"$/g, "'")} .encode()\n`;
  await writeFile(join(models, `${period}-independent-recompute.py`), checker);
  if (!options.orphan) await writeFile(join(models, file), options.manifestBytes ?? encode(m));
  await writeFile(join(models, part), raw);
  return { dir, models };
}
test('verification vocabulary and canonical metadata reject alternate paths and duplicate keys', () => {
  for (const name of [file, part]) assert(modelArtifactName(name, period));
  for (const name of ['2026-Q3-verification-part-1.bin', '2026-Q3-verification-part-000.bin.exe']) assert(!modelArtifactName(name, period));
  for (const href of [`../models/x/../${part}`, `../models/2025-FY-verification-payload.json`, `/research/companies/CN/999999/models/${part}`, `https://example.invalid/${part}`]) assert.equal(researchResourceLink(href, 'research/companies/CN/000001/reports/2026-Q3.md'), undefined);
  assert.deepEqual(parseVerificationManifest(encode(manifest), period), manifest);
  const duplicate = Buffer.from(encode(manifest).toString().trimEnd().slice(0, -1) + ',"period":"2026-Q3"}\n');
  assert.throws(() => parseVerificationManifest(duplicate, period));
  for (const change of [m => m.parts[0].file = '../x', m => m.parts[0].file = '2026-Q3-verification-part-001.bin', m => m.parts.push({ ...m.parts[0] }), m => m.payload_bytes = 192 * 1024**2 + 1, m => m.parts[0].bytes = true, m => m.parts[0].sha256 = [sha], m => m.payload_sha256 = [sha], m => m.extra = 1]) { const m = structuredClone(manifest); change(m); assert.throws(() => parseVerificationManifest(encode(m), period)); }
});
test('build closes complete verification siblings and rejects missing, wrong bytes, symlinks and orphan parts', async () => {
  const valid = await fixture(); await buildResearchData(valid.dir);
  const output = join(valid.dir, 'dashboard/public/data/models/000001');
  assert.deepEqual((await readdir(output)).sort(), (await readdir(valid.models)).sort());
  for (const name of await readdir(valid.models)) assert.deepEqual(await readFile(join(output, name)), await readFile(join(valid.models, name)));
  const missing = await fixture(); await rename(join(missing.models, part), join(missing.models, 'retained.bin')); await assert.rejects(buildResearchData(missing.dir));
  const tampered = await fixture(); await writeFile(join(tampered.models, part), Buffer.alloc(raw.length)); await assert.rejects(buildResearchData(tampered.dir));
  const linked = await fixture(); await rename(join(linked.models, part), join(linked.models, 'retained.bin')); await symlink('retained.bin', join(linked.models, part)); await assert.rejects(buildResearchData(linked.dir));
  const hard = await fixture(); await link(join(hard.models, part), join(hard.models, 'retained.bin')); await assert.rejects(buildResearchData(hard.dir));
  const orphan = await fixture(manifest, { orphan: true }); await assert.rejects(buildResearchData(orphan.dir));
  for (const change of [m => m.parts[0].file = '../outside.bin', m => m.parts[0].file = '2026-Q3-verification-part-001.bin', m => m.parts.push({ ...m.parts[0] }), m => m.payload_sha256 = '0'.repeat(64), m => m.payload_bytes = 192 * 1024**2 + 1]) { const m = structuredClone(manifest); change(m); const bad = await fixture(m); await assert.rejects(buildResearchData(bad.dir)); }
  const duplicate = Buffer.from(encode(manifest).toString().trimEnd().slice(0, -1) + ',"period":"2026-Q3"}\n'); const dup = await fixture(manifest, { manifestBytes: duplicate }); await assert.rejects(buildResearchData(dup.dir));
});
test('real HTTP downloaded standalone synthetic checker accepts exact payload and rejects missing/order/hash', async () => {
  const valid = await fixture(); await buildResearchData(valid.dir);
  const source = join(valid.dir, 'dashboard/public/data/models/000001'), names = await readdir(source);
  const bytes = new Map(await Promise.all(names.map(async n => [n, await readFile(join(source, n))]))); let mode = 'valid';
  const server = createServer((req, res) => { const name = req.url?.startsWith('/data/models/000001/') ? req.url.slice('/data/models/000001/'.length) : ''; let data = bytes.get(name); if (!data || (mode === 'missing' && name === part)) { res.writeHead(404); res.end(); return; } if (mode === 'tampered' && name === part) data = Buffer.alloc(raw.length); if (mode === 'order' && name === file) { const m = structuredClone(manifest); m.parts[0].file = '2026-Q3-verification-part-001.bin'; data = encode(m); } res.writeHead(200); res.end(data); });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); }); const port = server.address().port;
  try { for (const variant of ['valid', 'missing', 'tampered', 'order']) { mode = variant; const dest = join(valid.dir, `downloaded-${variant}`); await mkdir(dest); for (const name of names) { const response = await fetch(`http://127.0.0.1:${port}/data/models/000001/${name}`); if (response.status === 200) await writeFile(join(dest, name), Buffer.from(await response.arrayBuffer())); else assert.equal(variant, 'missing'); } const run = spawnSync('python3', ['-I', '-S', join(dest, `${period}-independent-recompute.py`)], { cwd: valid.dir, encoding: 'utf8', timeout: 30000, maxBuffer: 65536 }); await writeFile(join(dest, 'checker.stdout'), run.stdout ?? ''); await writeFile(join(dest, 'checker.stderr'), run.stderr ?? ''); assert.equal(run.status === 0, variant === 'valid', `${variant}: ${run.stderr}`); } }
  finally { await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve())); }
});

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { cp, mkdir, mkdtemp, readFile, readdir, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { modelArtifactName, researchResourceLink } from "../app/lib/report-reference.mjs";
import { buildResearchData } from "../scripts/build-research-data.mjs";
import { xzManifestEntry, verifyXzBytes } from "../scripts/lib/model-xz.mjs";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const sha = (b) => createHash("sha256").update(b).digest("hex");
const period = "2026-Q3", file = `${period}-output.json.xz`, source = "research/companies/CN/300896/reports/2026-Q3.md";
const raw = Buffer.from('{"all_years":[1,2,3],"not_a_summary":true}\n');
const compressed = spawnSync("python3", ["-I", "-c", "import lzma,sys;sys.stdout.buffer.write(lzma.compress(sys.stdin.buffer.read()))"], {input:raw});
assert.equal(compressed.status, 0);
const xz = compressed.stdout;
const manifest = {schema:"trading_os_lossless_json_xz_v1",artifact_kind:"transport_manifest_not_model_result",compression:"xz",file,compressed_bytes:xz.length,compressed_sha256:sha(xz),expanded_bytes:raw.length,expanded_sha256:sha(raw),expanded_media_type:"application/json"};
async function fixture(t, desc=manifest, bytes=xz, report=`[model](../models/${period}.py) [transport only](../models/${period}-output.json) [complete lossless JSON](../models/${file})`) {
  const dir=await mkdtemp(join(tmpdir(),"xz-delivery-")); t.after(()=>rm(dir,{recursive:true,force:true}));
  for(const name of ["research/standards","coverage/cn-a","screening/cn-a/value-quality","research/companies/CN/300896/reports","research/companies/CN/300896/models"]) await mkdir(join(dir,name),{recursive:true});
  await cp(join(root,"research/standards/registry.json"),join(dir,"research/standards/registry.json"));
  for(const name of ["research_state.jsonl","research_queue.jsonl"])await writeFile(join(dir,"coverage/cn-a",name),"");
  await writeFile(join(dir,"screening/cn-a/value-quality/pool.json"),JSON.stringify({schema_version:2,companies:[]}));
  await writeFile(join(dir,source),`# Test\n${report}\n`);const models=join(dir,"research/companies/CN/300896/models");
  await writeFile(join(models,`${period}.py`),"raise RuntimeError('export must not execute model')\n");
  await writeFile(join(models,`${period}-output.json`),JSON.stringify(desc));await writeFile(join(models,file),bytes);return {dir,models};
}
test("XZ exact filename retains company, period and local-link boundaries",()=>{
  assert.equal(modelArtifactName(file,period),true);assert.equal(researchResourceLink(`../models/${file}`,source),`/data/models/300896/${file}`);
  for(const name of ["2026-Q3-output.xz","2026-Q3.py.xz","2026-Q3-output.json.xz.exe","2026-Q3-case-base.json.xz"])assert.equal(modelArtifactName(name,period),false);
  for(const href of [`https://example.com/${file}`,`../models/x/../${file}`,`../models/2025-FY-output.json.xz`,`/research/companies/CN/300033/models/${file}`,`../models/%2e%2e/models/${file}`])assert.equal(researchResourceLink(href,source),undefined,href);
});
test("XZ descriptor is explicit metadata and rejects aliases, size/hash and unknown fields",()=>{
  assert.deepEqual(xzManifestEntry(manifest,period),manifest);
  for(const bad of [{file:"../"+file},{file:"https://example.com/"+file},{file:"2025-FY-output.json.xz"},{expanded_bytes:-1},{expanded_bytes:513*1024**2},{expanded_bytes:1.5},{compressed_bytes:101*1024**2},{expanded_sha256:"0"},{compressed_sha256:"G".repeat(64)},{artifact_kind:"model_result"},{value_range:{low:1,high:2}},{compression:"gzip"}])assert.throws(()=>xzManifestEntry({...manifest,...bad},period),/Unsafe XZ/);
});
test("bounded verifier checks BOTH hashes, complete stream, expansion bounds and trailing bytes",()=>{
  verifyXzBytes(xz,manifest);
  for(const bad of [{expanded_sha256:"0".repeat(64)},{compressed_sha256:"0".repeat(64)},{expanded_bytes:raw.length-1},{expanded_bytes:raw.length+1}])assert.throws(()=>verifyXzBytes(xz,{...manifest,...bad}),/XZ integrity/);
  for(const bytes of [xz.subarray(0,-1),Buffer.concat([xz,Buffer.from("extra")]),Buffer.concat([xz,xz])])assert.throws(()=>verifyXzBytes(bytes,{...manifest,compressed_bytes:bytes.length,compressed_sha256:sha(bytes)}),/XZ integrity/);
});
test("build closes XZ transport manifest, preserves every byte and never runs producer",async(t)=>{
  const {dir}=await fixture(t,manifest,xz,"[transport](../models/2026-Q3-output.json)");await buildResearchData(dir);const output=join(dir,"dashboard/public/data/models/300896");
  assert.deepEqual((await readdir(output)).sort(),[`${period}.py`,`${period}-output.json`,file].sort());assert.deepEqual(await readFile(join(output,file)),xz);
  const decode=spawnSync("python3",["-I","-c","import lzma,sys;sys.stdout.buffer.write(lzma.decompress(sys.stdin.buffer.read()))"],{input:await readFile(join(output,file))});assert.equal(decode.status,0);assert.deepEqual(decode.stdout,raw);
});
test("build rejects absent manifest, missing stream, tampering and symlink escape",async(t)=>{
  const orphan=await fixture(t,{});await assert.rejects(buildResearchData(orphan.dir),/absent from its transport manifest/);
  const missing=await fixture(t);await rm(join(missing.models,file));await assert.rejects(buildResearchData(missing.dir),{code:"ENOENT"});
  const tampered=await fixture(t,{...manifest,expanded_sha256:"0".repeat(64)});await assert.rejects(buildResearchData(tampered.dir),/XZ integrity/);
  const linked=await fixture(t);await rm(join(linked.models,file));await writeFile(join(linked.dir,"private.xz"),xz);await symlink(join(linked.dir,"private.xz"),join(linked.models,file));await assert.rejects(buildResearchData(linked.dir),/regular file/);
  const escaped=await fixture(t);const away=join(escaped.dir,"outside-models");await cp(escaped.models,away,{recursive:true});await rm(escaped.models,{recursive:true});await symlink(away,escaped.models);await assert.rejects(buildResearchData(escaped.dir),/escapes its company directory/);
});

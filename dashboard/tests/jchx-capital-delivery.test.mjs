import assert from 'node:assert/strict';
import { cp, mkdir, mkdtemp, readFile, readdir, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { modelArtifactName, researchResourceLink } from '../app/lib/report-reference.mjs';
import { buildResearchData } from '../scripts/build-research-data.mjs';
const root=resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const files=['2026-Q3-capital-20261102.py','2026-Q3-capital-20261102-output.json','2026-Q3-capital-20261102-check.py'];
const source='research/companies/CN/603979/reports/2026-Q3.md';
async function fixture(t){
 const dir=await mkdtemp(join(tmpdir(),'jchx-capital-'));t.after(()=>rm(dir,{recursive:true,force:true}));
 for(const n of ['research/standards','coverage/cn-a','screening/cn-a/value-quality','research/companies/CN/603979/reports','research/companies/CN/603979/models']) await mkdir(join(dir,n),{recursive:true});
 await cp(join(root,'research/standards/registry.json'),join(dir,'research/standards/registry.json'));
 for(const n of ['research_state.jsonl','research_queue.jsonl'])await writeFile(join(dir,'coverage/cn-a',n),'');
 await writeFile(join(dir,'screening/cn-a/value-quality/pool.json'),JSON.stringify({schema_version:2,companies:[]}));
 await writeFile(join(dir,source),'# Fixed fixture\n信息截止：2026-10-26\n'+files.map(n=>`[${n}](../models/${n})`).join('\n'));
 const models=join(dir,'research/companies/CN/603979/models');
 for(const n of files) await writeFile(join(models,n),n.endsWith('.py')?"raise RuntimeError('never execute during export')\n":'{}\n');
 return{dir,models};
}
test('Nov2 cash attachments allow only three exact names within603979 Q3',()=>{
 for(const n of files){
  assert(modelArtifactName(n,'2026-Q3','603979'));
  assert(!modelArtifactName(n,'2026-Q3','603195'));
  assert(!modelArtifactName(n,'2025-FY','603979'));
  assert(!modelArtifactName(n));
  assert.equal(researchResourceLink('../models/'+n,source),'/data/models/603979/'+n);
  for(const h of ['https://example.com/'+n,'../models/x/../'+n,'../models/'+n+'.exe','../models/%2e%2e/models/'+n,'/research/companies/CN/603195/models/'+n])assert.equal(researchResourceLink(h,source),undefined);
  assert.equal(researchResourceLink('../models/'+n,'research/companies/CN/603195/reports/2026-Q3.md'),undefined);
 }
 for(const n of ['2026-Q3-capital-20261103.py','2026-Q3-capital-20261102-secret.json','2025-FY-capital-20261102.py','../'+files[0]])assert(!modelArtifactName(n,'2026-Q3','603979'));
});
test('three exact linked cash attachments export full bytes, never execute',async(t)=>{
 const{dir,models}=await fixture(t);await writeFile(join(models,'2026-Q3-capital-20261102-private.json'),'private');
 await buildResearchData(dir);const out=join(dir,'dashboard/public/data/models/603979');assert.deepEqual((await readdir(out)).sort(),[...files].sort());
 for(const n of files)assert.deepEqual(await readFile(join(out,n)),await readFile(join(models,n)));
});
test('missing or symlink cash attachments fail closed',async(t)=>{
 const one=await fixture(t);await rm(join(one.models,files[0]));await assert.rejects(buildResearchData(one.dir),{code:'ENOENT'});
 const two=await fixture(t);await rm(join(two.models,files[1]));await writeFile(join(two.dir,'private.json'),'{}');await symlink(join(two.dir,'private.json'),join(two.models,files[1]));await assert.rejects(buildResearchData(two.dir),/regular file/u);
});

import assert from 'node:assert/strict';
import { cp, mkdir, mkdtemp, readFile, readdir, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { modelArtifactName, researchResourceLink } from '../app/lib/report-reference.mjs';
import { buildResearchData } from '../scripts/build-research-data.mjs';
const root=resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const specs=[['000651','20261103'],['000921','20261103'],['003816','20261103']];
const names=(date)=>['.py','-output.json','-check.py'].map(s=>`2026-Q3-capital-${date}${s}`);
async function fixture(t,code,date){
 const dir=await mkdtemp(join(tmpdir(),'three-capital-'));t.after(()=>rm(dir,{recursive:true,force:true}));
 for(const n of ['research/standards','coverage/cn-a','screening/cn-a/value-quality',`research/companies/CN/${code}/reports`,`research/companies/CN/${code}/models`])await mkdir(join(dir,n),{recursive:true});
 await cp(join(root,'research/standards/registry.json'),join(dir,'research/standards/registry.json'));
 for(const n of ['research_state.jsonl','research_queue.jsonl'])await writeFile(join(dir,'coverage/cn-a',n),'');
 await writeFile(join(dir,'screening/cn-a/value-quality/pool.json'),JSON.stringify({schema_version:2,companies:[]}));
 await writeFile(join(dir,`research/companies/CN/${code}/reports/2026-Q3.md`),'# Fixture\n信息截止：2026-10-26\n'+names(date).map(n=>`[${n}](../models/${n})`).join('\n'));
 const models=join(dir,`research/companies/CN/${code}/models`);
 for(const n of names(date))await writeFile(join(models,n),n.endsWith('.py')?"raise RuntimeError('export must not execute')\n":'{}\n');
 return{dir,models};
}
test('three current revisions admit only exact ticker, Q3 and dated cash filenames',()=>{
 for(const[code,date]of specs){const src=`research/companies/CN/${code}/reports/2026-Q3.md`;
  for(const n of names(date)){
   assert(modelArtifactName(n,'2026-Q3',code));assert(!modelArtifactName(n,'2025-FY',code));assert(!modelArtifactName(n,'2026-Q3','600000'));assert(!modelArtifactName(n));
   assert.equal(researchResourceLink('../models/'+n,src),`/data/models/${code}/${n}`);
   for(const h of ['https://example.com/'+n,'../models/x/../'+n,'../models/'+n+'.exe','../models/%2e%2e/models/'+n,`/research/companies/CN/600000/models/${n}`])assert.equal(researchResourceLink(h,src),undefined);
  }
  for(const n of ['2026-Q3-capital-20261104.py',`2026-Q3-capital-${date}-private.json`,`2025-FY-capital-${date}.py`])assert(!modelArtifactName(n,'2026-Q3',code));
 }
});
test('each of three exact cash attachments exports complete bytes without execution',async(t)=>{
 for(const[code,date]of specs){const{dir,models}=await fixture(t,code,date);await writeFile(join(models,`2026-Q3-capital-${date}-private.json`),'private');await buildResearchData(dir);const out=join(dir,'dashboard/public/data/models',code);assert.deepEqual((await readdir(out)).sort(),names(date).sort());for(const n of names(date))assert.deepEqual(await readFile(join(out,n)),await readFile(join(models,n)));}
});
test('each revision rejects missing and symbolic-link attachments',async(t)=>{
 for(const[code,date]of specs){const a=await fixture(t,code,date);await rm(join(a.models,names(date)[0]));await assert.rejects(buildResearchData(a.dir),{code:'ENOENT'});const b=await fixture(t,code,date);await rm(join(b.models,names(date)[1]));await writeFile(join(b.dir,'private.json'),'{}');await symlink(join(b.dir,'private.json'),join(b.models,names(date)[1]));await assert.rejects(buildResearchData(b.dir),/regular file/u);}
});
test('three current states bind complete new cash output and same-base holder paths',async()=>{
 const states=(await readFile(join(root,'coverage/cn-a/research_state.jsonl'),'utf8')).trim().split('\n').map(JSON.parse);
 for(const[code,date]of specs){
  const s=states.find(x=>x.symbol===`CN:${code}`),r=JSON.parse(await readFile(join(root,`research/companies/CN/${code}/models/2026-Q3-capital-${date}-output.json`),'utf8'));
  assert.deepEqual(s.return_model,r.return_model);assert.deepEqual(s.value_range,r.value_range);
  assert.equal(r.holder_source_path,'base only; core endpoints never feed Y5');
  const b=r.paths.base,rows=b.annual??b.rows,d=rows.slice(0,5).map(x=>x.dps??x.dividend_per_share);
  assert.deepEqual(r.return_model.base_case_distributions_per_share,d);
  for(const[side,rate]of Object.entries(r.same_base_rates)){
   const tv=rows.slice(5).reduce((a,x,i)=>a+(x.dps??x.dividend_per_share)/(1+rate)**(i+1),0);
   assert(Math.abs(tv-r.return_model.base_case_terminal_equity_value_range_per_share.year_5[side])<1e-9);
  }
  const report=await readFile(join(root,s.basis_report_path),'utf8');assert.match(report,/历史/u);
  for(const n of names(date))assert(report.includes(`../models/${n}`));assert(report.includes('../models/2026-Q3-output.json'));
 }
});

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { xzManifestEntry,verifyXzBytes } from '../scripts/lib/model-xz.mjs';
import { cp, mkdir, mkdtemp, readFile, readdir, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { modelArtifactName, researchResourceLink } from '../app/lib/report-reference.mjs';
import { buildResearchData } from '../scripts/build-research-data.mjs';
const root=resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const specs=[['300750','20261103'],['688100','20261103'],['600887','20261103'],['600690','20261103'],['688008','20261103']];
const names=(date)=>['.py','-output.json','-check.py'].map(s=>`2026-Q3-capital-${date}${s}`);
async function fixture(t,code,date){
 const dir=await mkdtemp(join(tmpdir(),'five-capital-'));t.after(()=>rm(dir,{recursive:true,force:true}));
 for(const n of ['research/standards','coverage/cn-a','screening/cn-a/value-quality',`research/companies/CN/${code}/reports`,`research/companies/CN/${code}/models`])await mkdir(join(dir,n),{recursive:true});
 await cp(join(root,'research/standards/registry.json'),join(dir,'research/standards/registry.json'));
 for(const n of ['research_state.jsonl','research_queue.jsonl'])await writeFile(join(dir,'coverage/cn-a',n),'');
 await writeFile(join(dir,'screening/cn-a/value-quality/pool.json'),JSON.stringify({schema_version:2,companies:[]}));
 await writeFile(join(dir,`research/companies/CN/${code}/reports/2026-Q3.md`),'# Fixture\n信息截止：2026-10-26\n'+names(date).map(n=>`[${n}](../models/${n})`).join('\n'));
 const models=join(dir,`research/companies/CN/${code}/models`);
 for(const n of names(date))await writeFile(join(models,n),n.endsWith('.py')?"raise RuntimeError('export must not execute')\n":'{}\n');
 return{dir,models};
}
test('five revisions admit only exact ticker, Q3 and dated cash filenames',()=>{
 for(const[code,date]of specs){const src=`research/companies/CN/${code}/reports/2026-Q3.md`;
  for(const n of names(date)){
   assert(modelArtifactName(n,'2026-Q3',code));assert(!modelArtifactName(n,'2025-FY',code));assert(!modelArtifactName(n,'2026-Q3','600000'));assert(!modelArtifactName(n));
   assert.equal(researchResourceLink('../models/'+n,src),`/data/models/${code}/${n}`);
   for(const h of ['https://example.com/'+n,'../models/x/../'+n,'../models/'+n+'.exe','../models/%2e%2e/models/'+n,`/research/companies/CN/600000/models/${n}`])assert.equal(researchResourceLink(h,src),undefined);
  }
  for(const n of ['2026-Q3-capital-20261104.py',`2026-Q3-capital-${date}-private.json`,`2025-FY-capital-${date}.py`])assert(!modelArtifactName(n,'2026-Q3',code));
 }
});
test('each of five exact cash attachments exports complete bytes without execution',async(t)=>{
 for(const[code,date]of specs){const{dir,models}=await fixture(t,code,date);await writeFile(join(models,`2026-Q3-capital-${date}-private.json`),'private');await buildResearchData(dir);const out=join(dir,'dashboard/public/data/models',code);assert.deepEqual((await readdir(out)).sort(),names(date).sort());for(const n of names(date))assert.deepEqual(await readFile(join(out,n)),await readFile(join(models,n)));}
});
test('each revision rejects missing and symbolic-link attachments',async(t)=>{
 for(const[code,date]of specs){const a=await fixture(t,code,date);await rm(join(a.models,names(date)[0]));await assert.rejects(buildResearchData(a.dir),{code:'ENOENT'});const b=await fixture(t,code,date);await rm(join(b.models,names(date)[1]));await writeFile(join(b.dir,'private.json'),'{}');await symlink(join(b.dir,'private.json'),join(b.models,names(date)[1]));await assert.rejects(buildResearchData(b.dir),/regular file/u);}
});
test('current front-five state binds actual complete current cash, same-base endpoints and information version',async()=>{
 const states=(await readFile(join(root,'coverage/cn-a/research_state.jsonl'),'utf8')).trim().split('\n').map(JSON.parse);
 const map={
 '300750':{base:'models/volume/base',core:['models/volume/core_low','models/volume/core_high'],holder:['models/volume/core_low','models/volume/core_high'],value:'PV',tv:'TV5',d:'D'},
 '688100':{base:'cases/0',core:['cases/0','cases/4'],value:'current_equity_value_per_share'},
 '600887':{base:'cases/base',core:['cases/low','cases/high'],holder:['cases/holder_low','cases/holder_high'],value:'value',tv:'terminal5',d:'first5'},
 '600690':{base:'base',core:['low','high'],holder:['low','high'],value:'value',tv:'year5',d:'dividends'},
 '688008':{base:'results/base',core:['results/core_low','results/core_high'],holder:['continuations/core_low','continuations/core_high'],value:'value',tv:'year5_value',d:'first5'}};
 for(const[code,date]of specs){
  const state=states.find(x=>x.symbol===`CN:${code}`),dir=join(root,`research/companies/CN/${code}/models`);let r=JSON.parse(await readFile(join(dir,`2026-Q3-capital-${date}-output.json`),'utf8'));
  if(code==='600887'){
   const desc=xzManifestEntry(r,'2026-Q3',code,`2026-Q3-capital-${date}-output.json`),bytes=await readFile(join(dir,desc.file));verifyXzBytes(bytes,desc,code);
   const out=spawnSync('python3',['-I','-c','import lzma,sys;sys.stdout.buffer.write(lzma.decompress(sys.stdin.buffer.read()))'],{input:bytes,maxBuffer:64*1024**2});assert.equal(out.status,0);r=JSON.parse(out.stdout);
  }
  assert.equal(r.company,code);assert.equal(r.information_asof,state.information_cutoff);assert.equal(state.return_model.model_as_of,state.information_cutoff);
  const x=map[code],raw=r.complete_cash_results,b=raw[x.base];const d=code==='688100'?b.holder.map(y=>y.distribution_per_share):b[x.d];
  const tv=code==='688100'?[r.same_base_holder['0.1'].year5_per_share,r.same_base_holder['0.085'].year5_per_share]:x.holder.map(k=>raw[k][x.tv]);
  assert.deepEqual(state.return_model.base_case_distributions_per_share,d);assert.deepEqual(state.return_model.base_case_terminal_equity_value_range_per_share.year_5,{low:tv[0],high:tv[1]});
  assert.deepEqual(state.value_range,{currency:'CNY',low:raw[x.core[0]][x.value],high:raw[x.core[1]][x.value]});
  const report=await readFile(join(root,state.basis_report_path),'utf8');assert.match(report,/历史/u);assert.match(state.return_model_note,/原金融预算锚/u);
  for(const n of names(date))assert(report.includes(`../models/${n}`));assert(report.includes('../models/2026-Q3-output.json'));
 }
});
test('only Yili exact current dated output receives existing bounded XZ transport',async()=>{
 const file='2026-Q3-capital-20261103-output.json.xz',name=file.slice(0,-3),source='research/companies/CN/600887/reports/2026-Q3.md';
 assert(modelArtifactName(file,'2026-Q3','600887'));assert.equal(researchResourceLink('../models/'+file,source),'/data/models/600887/'+file);
 const m=JSON.parse(await readFile(join(root,'research/companies/CN/600887/models',name),'utf8'));assert.deepEqual(xzManifestEntry(m,'2026-Q3','600887',name),m);
 for(const code of ['300750','688100','600690','688008','600000']){assert(!modelArtifactName(file,'2026-Q3',code));assert.throws(()=>xzManifestEntry(m,'2026-Q3',code,name),/Unsafe XZ/u);}
 for(const bad of ['2026-Q3-capital-20261104-output.json.xz','2026-Q3-capital-20261103-private.json.xz','../'+file])assert(!modelArtifactName(bad,'2026-Q3','600887'));
 for(const href of ['https://example.com/'+file,'../models/x/../'+file,'../models/%2e%2e/models/'+file,'/research/companies/CN/600690/models/'+file])assert.equal(researchResourceLink(href,source),undefined);
});

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
const specs=[['002714','20261103']];
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
test('Muyuan current primary and auxiliary retain exact separate complete sources and dual dates',async()=>{
 const dir=join(root,'research/companies/CN/002714/models'),name='2026-Q3-capital-20261103-output.json';
 const m=JSON.parse(await readFile(join(dir,name),'utf8'));xzManifestEntry(m,'2026-Q3','002714',name);
 const bytes=await readFile(join(dir,m.file));verifyXzBytes(bytes,m,'002714');
 const decoded=spawnSync('python3',['-I','-c','import lzma,sys;sys.stdout.buffer.write(lzma.decompress(sys.stdin.buffer.read()))'],{input:bytes,maxBuffer:64*1024**2});assert.equal(decoded.status,0);const r=JSON.parse(decoded.stdout);
 assert.equal(r.company,'CN:002714');assert.equal(r.valuation_anchor,'2026-10-29T20:00:00+00:00');assert.equal(Object.keys(r.complete_raw_objects).length,24);
 const states=(await readFile(join(root,'coverage/cn-a/research_state.jsonl'),'utf8')).trim().split('\n').map(JSON.parse),state=states.find(x=>x.symbol==='CN:002714');
 assert.equal(state.information_cutoff,r.information_cutoff);assert.equal(state.return_model.model_as_of,r.information_cutoff);
 const raw=r.complete_raw_objects,base=raw['results/main/A0/base.json'],lo=raw['results/main/A0/core_low.json'],hi=raw['results/main/A0/core_high.json'],aux=raw['results/aux/A0/capital.json'];
 assert.deepEqual(state.value_range,{currency:'CNY',low:Number(lo.current_value.toFixed(1)),high:Number(hi.current_value.toFixed(1))});
 assert.deepEqual(state.return_model.base_case_distributions_per_share,base.dps5.map(x=>Number(x.toFixed(6))));
 const tails=['low','high'].map(side=>raw[`results/main/A0/same-base-Y5-${side}.json`]);for(const t of tails){assert.deepEqual(t.rows,base.rows);assert.deepEqual(t.final_state,base.final_state);}
 assert.deepEqual(state.return_model.base_case_terminal_equity_value_range_per_share.year_5,{low:Number(tails[0].terminal_y5.toFixed(2)),high:Number(tails[1].terminal_y5.toFixed(2))});
 assert.notDeepEqual(base.dps5,aux.dps5);assert.equal(aux.current_value,12.638420050968715);assert.equal(aux.rows[0].new_finance,1.1663067064032635);
 const report=await readFile(join(root,state.basis_report_path),'utf8');for(const n of [...names('20261103'),name+'.xz','2026-Q3-sources-assumptions.md'])assert(report.includes('../models/'+n));
 assert.match(report,/2026-10-29T20:00:00/u);assert.match(report,/不是已经取得的银行承诺/u);assert.match(report,/历史/u);
});
test('Muyuan bounded dated XZ route rejects other dates, companies and traversal',async()=>{
 const name='2026-Q3-capital-20261103-output.json',file=name+'.xz';const m=JSON.parse(await readFile(join(root,'research/companies/CN/002714/models',name),'utf8'));const source='research/companies/CN/002714/reports/2026-Q3.md';
 assert(modelArtifactName(file,'2026-Q3','002714'));assert.equal(researchResourceLink('../models/'+file,source),'/data/models/002714/'+file);
 for(const code of ['300750','688100','600690','688008','600000']){assert(!modelArtifactName(file,'2026-Q3',code));assert.throws(()=>xzManifestEntry(m,'2026-Q3',code,name),/Unsafe XZ/u);}
 for(const bad of [file.replace('20261103','20261104'),'../'+file,file+'.bak'])assert(!modelArtifactName(bad,'2026-Q3','002714'));
 for(const href of ['https://example.com/'+file,'../models/x/../'+file,'../models/%2e%2e/models/'+file,'/research/companies/CN/600887/models/'+file])assert.equal(researchResourceLink(href,source),undefined);
});

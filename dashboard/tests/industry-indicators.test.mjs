import assert from "node:assert/strict";
import test from "node:test";
import { mkdtemp, mkdir, writeFile, rm, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { validateIndustryIndicators, loadIndustryIndicators } from "../scripts/lib/industry-indicators.mjs";

function sample() {
  return { schemaVersion:1, topic:"autos-batteries", title:"行业运行", checkedOn:"2026-11-04", reviewAfter:"2026-11-15", scopeNote:"国内乘用车单月零售。", sources:[{id:"cpca",title:"九月报告",publisher:"乘联分会",url:"https://www.cada.cn/report",publishedOn:"2026-10-12"}], releaseLinks:["cpca"], headlines:["share"], series:[{id:"share",label:"渗透率",unit:"%",valueType:"share",frequency:"monthly",definition:"新能源零售/全部乘用车零售",interpretation:"销量与占比同时看",points:[{period:"2026-09",value:67,numerator:108.4,denominator:161.8,sourceId:"cpca"}]}], rankings:[] };
}
test("indicator ratios are reproducible and negative growth is allowed separately from shares",()=>{
  const d=sample(); validateIndustryIndicators(d,d.topic);
  d.series.push({...d.series[0],id:"yoy",valueType:"change",points:[{period:"2026-09",value:-16.7,sourceId:"cpca"}]});
  assert.doesNotThrow(()=>validateIndustryIndicators(d,d.topic));
  d.series[0].points[0].value=40; assert.throws(()=>validateIndustryIndicators(d,d.topic),/比例/);
});
test("unpublished complete periods, future sources, duplicate points and unsafe links fail closed",()=>{
  for (const change of [
    d=>d.series[0].points[0].period="2026-11",
    d=>d.sources[0].publishedOn="2026-11-20",
    d=>d.series[0].points.push({...d.series[0].points[0]}),
    d=>d.sources[0].url="javascript:alert(1)",
    d=>d.series[0].points[0].value=-2,
    d=>d.releaseLinks.push("missing")
  ]) { const d=sample();change(d);assert.throws(()=>validateIndustryIndicators(d,d.topic)); }
});
test("missing data needs a reason and never becomes zero",()=>{
  const d=sample();d.series[0].points=[{period:"2026-09",value:null,sourceId:"cpca"}];
  assert.throws(()=>validateIndustryIndicators(d,d.topic),/缺值/);
  d.series[0].points[0].note="原表暂缺此项";
  assert.equal(validateIndustryIndicators(d,d.topic).series[0].points[0].value,null);
});
test("rankings keep published shares without forcing the all-chemistry GWh denominator",()=>{
  const d=sample();d.rankings=[{id:"battery",label:"锂电榜",period:"2026-09",frequency:"ytd",definition:"不含其他体系，榜单分母单列",sourceId:"cpca",items:[{name:"企业甲",share:44.16,volumeGWh:253.68},{name:"企业乙",share:18.53,volumeGWh:106.44}]}];
  assert.doesNotThrow(()=>validateIndustryIndicators(d,d.topic));
  d.rankings[0].items.push({name:"企业丙",share:80}); assert.throws(()=>validateIndustryIndicators(d,d.topic),/100/);
});
test("indicator imports reject mismatched topics and symlink sources",async()=>{
  const root=await mkdtemp(join(tmpdir(),"industry-indicators-"));
  const dir=join(root,"research/industries/autos-batteries");
  try {
    await mkdir(dir,{recursive:true});await writeFile(join(dir,"indicators.json"),JSON.stringify(sample()));
    assert.equal((await loadIndustryIndicators(root,"autos-batteries","research/industries/autos-batteries/indicators.json")).topic,"autos-batteries");
    await assert.rejects(loadIndustryIndicators(root,"autos-batteries","research/industries/other/indicators.json"),/路径/);
    await writeFile(join(root,"outside.json"),JSON.stringify(sample()));await rm(join(dir,"indicators.json"));await symlink(join(root,"outside.json"),join(dir,"indicators.json"));
    await assert.rejects(loadIndustryIndicators(root,"autos-batteries","research/industries/autos-batteries/indicators.json"),/符号链接/);
  } finally { await rm(root,{recursive:true,force:true}); }
});

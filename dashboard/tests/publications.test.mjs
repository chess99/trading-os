import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, rm, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import test from "node:test";
import { loadPublications } from "../scripts/lib/publications.mjs";

function report(date = "2026-09-30", extra = {}) {
  return { id: `demand-${date}`, kind: "industry", type: "report", topic: "demand", publishedOn: date,
    informationCutoff: date, markets: ["CN", "HK"], regions: ["中国"], summary: "测试行业判断",
    sourcePath: `research/industries/demand/reports/${date}.md`, status: "published", ...extra };
}
async function fixture(fn) {
  const root = await mkdtemp(join(tmpdir(), "research-publication-"));
  async function save(path, text) { await mkdir(dirname(join(root,path)),{recursive:true}); await writeFile(join(root,path),text); }
  async function publish(entries) {
    for (const d of entries) if (d.sourcePath.startsWith("research/") && !d.sourcePath.includes("..")) await save(d.sourcePath, `# ${d.id}\n\n独立研究正文。\n`);
    await save("research/publications.json", JSON.stringify({schemaVersion:1,documents:entries}));
  }
  try { await fn({root,save,publish}); } finally { await rm(root,{recursive:true,force:true}); }
}
test("publication directory keeps important historical reports and excludes internal frameworks", async () => fixture(async ({root,save,publish}) => {
  await save("research/industries/sectors/legacy.md", "# 内部框架\n请执行工作流。");
  await publish([report(),report("2026-10-28")]);
  const docs = await loadPublications(root);
  assert.equal(docs.length,2); assert.equal(docs[0].publishedOn,"2026-10-28");
  assert.notEqual(docs[0].path,docs[1].path); assert.ok(docs.every((d)=>d.type === "report"));
  assert.ok(docs.every((d)=>!d.markdown.includes("内部框架")));
}));
test("publications reject wrong paths, dates, duplicate versions and missing scope", async () => fixture(async ({root,publish}) => {
  for (const entries of [[report("2026-02-30")],[report(undefined,{informationCutoff:"2026-10-01"})],
    [report(undefined,{sourcePath:"research/industries/sectors/legacy.md"})], [report(), report(undefined,{id:"another"})],
    [report(undefined,{markets:[]})], [report(undefined,{regions:[]})], [report(undefined,{status:"draft"})]]) {
    await publish(entries); await assert.rejects(loadPublications(root));
  }
}));
test("reference articles are separate from time-specific reports; withdrawal keeps reason and history", async () => fixture(async ({root,publish}) => {
  await publish([report(undefined,{status:"withdrawn",withdrawalReason:"关键数据口径错误"}),
    report("2026-10-28",{id:"reference",kind:"macro",type:"reference",topic:"valuation",informationCutoff:null,sourcePath:"research/macro/reference/valuation.md"})]);
  const docs=await loadPublications(root);
  assert.equal(docs[0].type,"reference"); assert.equal(docs[0].informationCutoff,null);
  assert.equal(docs[1].withdrawalReason,"关键数据口径错误");
  await publish([report(undefined,{status:"withdrawn"})]); await assert.rejects(loadPublications(root),/原因/);
}));
test("published source cannot resolve to another file through a symbolic link", async () => fixture(async ({root,save,publish}) => {
  await publish([report()]); await save("internal.md","# 内部记录");
  await rm(join(root,report().sourcePath)); await symlink(join(root,"internal.md"),join(root,report().sourcePath));
  await assert.rejects(loadPublications(root),/符号链接/);
}));

test("same-day substantive corrections retain the first version with a separate revision", async () => fixture(async ({root,publish}) => {
  await publish([report(),report(undefined,{id:"demand-corrected",revision:2,sourcePath:"research/industries/demand/reports/2026-09-30-r2.md"})]);
  const docs=await loadPublications(root);
  assert.deepEqual(docs.map((d)=>d.version),["2026-09-30-r2","2026-09-30"]);
  assert.notEqual(docs[0].sourcePath,docs[1].sourcePath);
}));

test("current industry indicators remain separate from a report's historical cutoff", async () => fixture(async ({root,save,publish}) => {
  const newer = report("2026-10-28", {indicatorSourcePath:"research/industries/demand/indicators.json"});
  await publish([report(), newer]);
  const indicators={schemaVersion:1,topic:"demand",title:"需求",checkedOn:"2026-11-04",reviewAfter:"2026-11-15",scopeNote:"月度实际",sources:[{id:"source",title:"月报",publisher:"协会",url:"https://example.org/report",publishedOn:"2026-10-12"}],releaseLinks:["source"],headlines:["units"],series:[{id:"units",label:"销量",unit:"万辆",valueType:"level",frequency:"monthly",definition:"国内零售",interpretation:"与份额同看",points:[{period:"2026-09",value:10,sourceId:"source"}]}],rankings:[]};
  await save(newer.indicatorSourcePath,JSON.stringify(indicators));
  const docs=await loadPublications(root);
  assert.equal(docs[0].informationCutoff,"2026-10-28");
  assert.equal(docs[0].indicatorData.checkedOn,"2026-11-04");
  assert.equal(docs[0].indicatorPath,"/data/indicators/demand.json");
  assert.equal(docs[1].indicatorPath,null);
  await publish([report(undefined,{indicatorSourcePath:"../../private.json"})]);
  await assert.rejects(loadPublications(root),/路径/);
}));

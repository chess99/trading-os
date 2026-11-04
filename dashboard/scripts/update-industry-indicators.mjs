import { readFile, writeFile, rename, unlink, realpath } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { loadIndustryIndicators, validateIndustryIndicators } from "./lib/industry-indicators.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const args = process.argv.slice(2);
const inputIndex = args.indexOf("--input");
if (inputIndex < 0 || !args[inputIndex + 1] || args.some((v,i) => !["--input","--apply"].includes(v) && i !== inputIndex + 1)) throw new Error("用法：node dashboard/scripts/update-industry-indicators.mjs --input <已核验JSON> [--apply]");
const next = JSON.parse(await readFile(resolve(args[inputIndex+1]), "utf8"));
validateIndustryIndicators(next, next.topic);
const target = `research/industries/${next.topic}/indicators.json`;
let previous;
try { previous = await loadIndustryIndicators(root, next.topic, target); }
catch (e) { if (e.code !== "ENOENT") throw e; }
if (previous) {
  if (next.checkedOn < previous.checkedOn) throw new Error("资料核验日期不能倒退");
  const revision = typeof next.revisionNote === "string" && next.revisionNote.trim();
  for (const old of previous.series) {
    const series = next.series.find((s) => s.id === old.id);
    if (!series) throw new Error(`不能静默删除历史序列：${old.id}`);
    if (["unit","valueType","frequency","definition"].some((k) => series[k] !== old[k]) && !revision) throw new Error(`指标口径变化需说明revisionNote：${old.id}`);
    for (const point of old.points) {
      const replacement = series.points.find((p) => p.period === point.period);
      if (!replacement) throw new Error(`不能静默删除历史观察：${old.id}/${point.period}`);
      if (replacement.value !== point.value && !revision) throw new Error(`历史值修订需说明revisionNote：${old.id}/${point.period}`);
    }
  }
}
const output = resolve(root, target);
if (await realpath(dirname(output)) !== resolve(await realpath(root), dirname(target))) throw new Error("目标目录不能通过符号链接替换");
if (args.includes("--apply")) {
  const temporary = `${output}.tmp-${process.pid}`;
  try { await writeFile(temporary, `${JSON.stringify(next,null,2)}\n`, { flag:"wx" }); await rename(temporary,output); }
  finally { await unlink(temporary).catch((e) => { if (e.code !== "ENOENT") throw e; }); }
}
console.log(JSON.stringify({ok:true,applied:args.includes("--apply"),topic:next.topic,checkedOn:next.checkedOn,series:next.series.length,path:target}));

import { readFile, realpath } from "node:fs/promises";
import { resolve } from "node:path";

const identifier = (value) => typeof value === "string" && /^[a-z0-9]+(?:-[a-z0-9]+)*$/u.test(value);
const text = (value) => typeof value === "string" && value.trim().length > 0;

export function validateIndustryCatalog(data) {
  function require(ok, message) { if (!ok) throw new Error(`行业目录：${message}`); }
  require(data?.schemaVersion === 1 && Array.isArray(data.groups) && data.groups.length > 0
    && Array.isArray(data.topics) && data.topics.length > 0, "版本或目录结构错误");
  require(Object.keys(data).every((key) => ["schemaVersion", "groups", "topics"].includes(key)), "包含目录以外的字段");
  const groups = new Set(), topics = new Set();
  for (const group of data.groups) {
    require(identifier(group.id) && !groups.has(group.id) && text(group.label)
      && Object.keys(group).every((key) => ["id", "label"].includes(key)), "大类定义错误或重复");
    groups.add(group.id);
  }
  for (const topic of data.topics) {
    require(identifier(topic.id) && !topics.has(topic.id) && text(topic.label) && groups.has(topic.group) && text(topic.scope)
      && Object.keys(topic).every((key) => ["id", "label", "group", "scope"].includes(key)), "主题定义错误、重复或大类不存在");
    topics.add(topic.id);
  }
  require(data.groups.every((group) => data.topics.some((topic) => topic.group === group.id)), "大类没有主题");
  return data;
}

export async function loadIndustryCatalog(root) {
  const path = "research/industries/catalog.json";
  const file = resolve(root, path);
  let body;
  try { body = await readFile(file, "utf8"); }
  catch (error) { if (error.code === "ENOENT") return null; throw error; }
  if (await realpath(file) !== resolve(await realpath(root), path)) throw new Error("行业目录不能通过符号链接替换");
  return validateIndustryCatalog(JSON.parse(body));
}

import assert from "node:assert/strict";
import test from "node:test";
import { fragmentId, researchHeadings } from "../app/lib/research-headings.mjs";

test("heading IDs use parsed text, support duplicate titles and ignore code blocks", () => {
  const markdown = "# 地产链研究\n\n## **需求**、[信用](https://example.com)与 `现金`\n\n```md\n## 假标题\n```\n\n## 需求\n\n### 需求\n\n需求-1\n---\n\n## 需求\n";
  const headings = researchHeadings(markdown);
  assert.deepEqual(headings.map(({ id, label, depth }) => ({ id, label, depth })), [
    { id: "地产链研究", label: "地产链研究", depth: 1 },
    { id: "需求信用与-现金", label: "需求、信用与 现金", depth: 2 },
    { id: "需求", label: "需求", depth: 2 },
    { id: "需求-1", label: "需求", depth: 3 },
    { id: "需求-1-1", label: "需求-1", depth: 2 },
    { id: "需求-2", label: "需求", depth: 2 },
  ]);
  assert.ok(!headings.some((heading) => heading.label === "假标题"));
  const allIds = headings.flatMap((heading) => [heading.id, ...heading.aliases]);
  assert.equal(new Set(allIds).size, allIds.length);
});

test("old company and publication chapter aliases remain available", () => {
  const headings = researchHeadings("# Report\n\n## 一、经营与现金？\n\n### ROE / ROIC\n");
  assert.equal(headings[1].id, "一经营与现金");
  assert.ok(headings[1].aliases.includes("一-经营与现金-"));
  assert.ok(headings[1].aliases.includes("section-3"));
  assert.equal(headings[2].id, "roe-roic");
  assert.ok(headings[2].aliases.includes("ROE-ROIC"));
});

test("encoded fragments resolve safely after asynchronous Markdown loading", () => {
  assert.equal(fragmentId("#%E9%9C%80%E6%B1%82"), "需求");
  assert.equal(fragmentId("#需求-1"), "需求-1");
  assert.equal(fragmentId("#%E9%9C"), "");
  assert.equal(fragmentId(""), "");
});

import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";

const parser = unified().use(remarkParse).use(remarkGfm);
/** @typedef {{id: string, label: string, depth: number, line: number, aliases: string[]}} ResearchHeading */

function textContent(node) {
  if (node.children) return node.children.map(textContent).join("");
  return node.type === "image" || node.type === "imageReference" ? node.alt ?? "" : node.value ?? "";
}

export function headingSlug(text) {
  return text.trim().toLowerCase().replace(/[^\p{Letter}\p{Number}\p{Mark}\s_-]/gu, "").replace(/\s+/gu, "-") || "section";
}

// The same Markdown parser drives the rendered text and the outline. Fenced
// code, inline formatting, setext headings and repeated titles keep correct IDs.
export function researchHeadings(markdown) {
  /** @type {ResearchHeading[]} */
  const headings = [];
  const ids = new Set();
  function visit(node) {
    if (node.type === "heading") {
      const label = textContent(node);
      const base = headingSlug(label);
      let id = base;
      for (let suffix = 1; ids.has(id); suffix++) id = `${base}-${suffix}`;
      ids.add(id);
      headings.push({ id, label, depth: node.depth, line: node.position.start.line, aliases: [] });
    }
    for (const child of node.children ?? []) visit(child);
  }
  visit(parser.parse(markdown));
  const used = new Set(ids);
  for (const heading of headings) {
    const oldCompanyId = heading.label.trim().replace(/[*_`]/gu, "").replace(/[^\p{Letter}\p{Number}]+/gu, "-");
    for (const alias of [oldCompanyId, `section-${heading.line}`]) {
      if (alias && !used.has(alias)) { heading.aliases.push(alias); used.add(alias); }
    }
  }
  return headings;
}

export function fragmentId(hash) {
  try { return decodeURIComponent(hash.replace(/^#/u, "")); }
  catch { return ""; }
}

"use client";

import { createElement, useEffect, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { fragmentId, researchHeadings } from "../lib/research-headings.mjs";
import { researchResourceLink } from "../lib/report-reference.mjs";

export function ResearchMarkdown({ markdown, sourcePath, headings, links }: {
  markdown: string;
  sourcePath: string;
  headings: ReturnType<typeof researchHeadings>;
  links: NonNullable<Parameters<typeof researchResourceLink>[2]>;
}) {
  useEffect(() => {
    function scrollToFragment() {
      const id = fragmentId(window.location.hash);
      if (id) document.getElementById(id)?.scrollIntoView({ block: "start" });
    }
    const frame = window.requestAnimationFrame(scrollToFragment);
    window.addEventListener("hashchange", scrollToFragment);
    return () => { window.cancelAnimationFrame(frame); window.removeEventListener("hashchange", scrollToFragment); };
  }, [markdown, sourcePath]);

  function heading(depth: number, node: { position?: { start: { line: number } } } | undefined, children: ReactNode) {
    const entry = headings.find((item) => item.line === node?.position?.start.line);
    return createElement(`h${depth}`, { id: entry?.id },
      entry?.aliases.map((id) => <span key={id} id={id} aria-hidden="true" />), children);
  }
  return <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
    h1: ({ node, children }) => heading(1, node, children),
    h2: ({ node, children }) => heading(2, node, children),
    h3: ({ node, children }) => heading(3, node, children),
    h4: ({ node, children }) => heading(4, node, children),
    h5: ({ node, children }) => heading(5, node, children),
    h6: ({ node, children }) => heading(6, node, children),
    a: ({ href, children }) => {
      const link = researchResourceLink(href, sourcePath, links);
      return link ? <a href={link} download={link.startsWith("/data/models/") || undefined}
        rel="noreferrer" target={/^(https?:|\/\/)/iu.test(link) ? "_blank" : undefined}>{children}</a> : <span>{children}</span>;
    },
    table: ({ children }) => <div className="standards-table-scroll research-table-scroll"><table>{children}</table></div>,
  }}>{markdown}</ReactMarkdown>;
}

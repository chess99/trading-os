/** @returns {"cn" | "archive"} */
export function industryRegion(document) {
  return document.regionId === "cn" ? "cn" : "archive";
}

// Old exact-version links retain their reading area. A topic-only link uses
// the China catalog when that topic exists there, including an unpublished one.
/** @returns {"cn" | "archive"} */
export function initialIndustryRegion(directory, params) {
  const requested = params.get("region");
  if (requested === "cn" || requested === "archive") return requested;
  const topic = params.get("topic");
  const version = params.get("version");
  if (topic && version) {
    const exact = directory.documents.find((document) => document.kind === "industry"
      && document.topic === topic && document.version === version);
    if (exact) return industryRegion(exact);
  }
  if (!directory.industryCatalog) return "archive";
  return !topic || directory.industryCatalog.topics.some((item) => item.id === topic) ? "cn" : "archive";
}

export function industryTopicChoices(catalog, documents, group = "", query = "") {
  const search = query.trim().toLowerCase();
  return catalog.topics.filter((topic) => (!group || topic.group === group) && (!search
    || `${topic.label} ${topic.scope} ${documents.filter((document) => document.topic === topic.id)
      .map((document) => `${document.title} ${document.summary}`).join(" ")}`.toLowerCase().includes(search)));
}

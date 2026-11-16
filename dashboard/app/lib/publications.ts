export interface PublishedDocument {
  id: string;
  kind: "industry" | "macro";
  type: "report" | "reference";
  topic: string;
  title: string;
  summary: string;
  path: string;
  sourcePath: string;
  publishedOn: string;
  revision: number;
  version: string;
  informationCutoff: string | null;
  markets: string[];
  regions: string[];
  regionId: "cn" | null;
  status: "published" | "withdrawn";
  withdrawalReason: string | null;
  indicatorPath: string | null;
}

export interface PublicationDirectory {
  documents: PublishedDocument[];
  companyReportPaths: string[];
  industryCatalog?: {
    schemaVersion: 1;
    groups: { id: string; label: string }[];
    topics: { id: string; label: string; group: string; scope: string }[];
  } | null;
}

export async function loadPublicationDirectory(signal?: AbortSignal): Promise<PublicationDirectory> {
  const response = await fetch("/data/documents.json", { signal });
  if (!response.ok) throw new Error("研究目录暂时无法读取");
  const data = await response.json();
  if (data.schemaVersion !== 1 || !Array.isArray(data.documents)) throw new Error("研究目录格式不正确");
  return { documents: data.documents, companyReportPaths: Array.isArray(data.companyReportPaths) ? data.companyReportPaths : [], industryCatalog: data.industryCatalog ?? null };
}

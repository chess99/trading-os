import { AppHeader } from "../components/app-header";
import { ResearchDocuments } from "../components/research-documents";
import "../standards.css";

export default function SelectionPage() {
  return <><AppHeader active="selection" />
    <aside className="standards-workspace standards-history-note" aria-label="精选资料的时点与口径">
      <strong>精选是独立的商业取舍，不授予当前估值展示资格。</strong>
      <p>下面保留原文及其引用时点；其中的日期化报告链接打开历史快照。现行已验收估值以研究决策台为准，未按现行标准研究的公司不会自动补入。</p>
      <a href="/">查看现行标准研究 →</a>
    </aside>
    <ResearchDocuments kind="selection" /></>;
}

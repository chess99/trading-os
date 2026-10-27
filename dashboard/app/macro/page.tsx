import { AppHeader } from "../components/app-header";
import { ResearchDocuments } from "../components/research-documents";

export const metadata = { title: "宏观与市场" };
export default function MacroPage() {
  return <><AppHeader active="macro" /><ResearchDocuments kind="macro" /></>;
}

import { AppHeader } from "../components/app-header";
import { ResearchDocuments } from "../components/research-documents";

export default function SelectionPage() {
  return <><AppHeader active="selection" /><ResearchDocuments kind="selection" /></>;
}

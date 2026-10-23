import { AppHeader } from "../components/app-header";
import { ResearchDocuments } from "../components/research-documents";
import "../standards.css";

export default function SelectionPage() {
  return <><AppHeader active="selection" /><ResearchDocuments kind="selection" /></>;
}

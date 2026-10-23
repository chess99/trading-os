import type { Metadata } from "next";
import { AppHeader } from "../components/app-header";
import { ScreeningClient } from "../components/screening-client";
export const metadata: Metadata = { title: "第一层筛选", description: "A股、港股与美股长期商业质量判断，阅读竞争优势、普通股现金及反证。" };
export default function ScreeningPage() {
  return <><AppHeader active="screening" /><ScreeningClient /></>;
}

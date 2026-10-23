import type { Metadata } from "next";
import { AppHeader } from "../components/app-header";
import { ScreeningClient } from "../components/screening-client";
export const metadata: Metadata = { title: "公司池", description: "跨市场比较企业的竞争优势、资本效率、现金质量与长期风险。" };
export default function ScreeningPage() {
  return <><AppHeader active="screening" /><ScreeningClient /></>;
}

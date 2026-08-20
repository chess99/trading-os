import type { Metadata } from "next";
import { AppHeader } from "./components/app-header";
import { DashboardClient } from "./components/dashboard-client";

export const metadata: Metadata = {
  title: "研究决策台",
  description: "浏览全市场研究状态、五年基准情景年化回报、合理价值位置及完整正式研报。",
};

export default function Home() {
  return (
    <>
      <AppHeader active="dashboard" />
      <DashboardClient />
    </>
  );
}

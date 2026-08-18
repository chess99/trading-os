import type { Metadata } from "next";
import { AppHeader } from "./components/app-header";
import { DashboardClient } from "./components/dashboard-client";

export const metadata: Metadata = {
  title: "研究决策台",
  description: "浏览全市场研究状态、完整正式研报及实时价格相对价值区间的机械位置。",
};

export default function Home() {
  return (
    <>
      <AppHeader active="dashboard" />
      <DashboardClient />
    </>
  );
}

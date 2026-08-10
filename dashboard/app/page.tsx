import type { Metadata } from "next";
import { AppHeader } from "./components/app-header";
import { DashboardClient } from "./components/dashboard-client";

export const metadata: Metadata = {
  title: "研究决策台",
  description: "从全市场研究状态中发现优先复核机会，并浏览全部公司与正式研报。",
};

export default function Home() {
  return (
    <>
      <AppHeader active="dashboard" />
      <DashboardClient />
    </>
  );
}

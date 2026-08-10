import type { Metadata } from "next";
import { AppHeader } from "../components/app-header";
import { ReportWorkspace } from "../components/report-workspace";

export const metadata: Metadata = {
  title: "研报库",
  description: "搜索、筛选并阅读 Trading OS 的正式公司研报。",
};

export default function ReportsPage() {
  return (
    <>
      <AppHeader active="reports" />
      <ReportWorkspace />
    </>
  );
}

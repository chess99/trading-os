import type { Metadata } from "next";
import { AppHeader } from "../../components/app-header";
import { ReportWorkspace } from "../../components/report-workspace";

export const metadata: Metadata = {
  title: "研报详情",
  description: "阅读公司正式研报，并在同一页面搜索或筛选其他研报。",
};

export default async function ReportDetailPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  return (
    <>
      <AppHeader active="reports" />
      <ReportWorkspace initialTicker={ticker} />
    </>
  );
}

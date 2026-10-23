import { redirect } from "next/navigation";
export default async function ScreeningPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = new URLSearchParams({ view: "pool" });
  for (const [key, value] of Object.entries(await searchParams)) if (typeof value === "string" && key !== "view") params.set(key, value);
  redirect(`/?${params.toString()}`);
}

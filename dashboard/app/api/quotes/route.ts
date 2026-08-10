import { fetchQuotesWithFallback, normalizeTickers } from "./providers";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const requested = (url.searchParams.get("symbols") ?? "").split(",");
  const tickers = normalizeTickers(requested);
  if (!tickers.length) {
    return Response.json({ error: "symbols must contain at least one A-share ticker" }, { status: 400 });
  }
  if (tickers.length > 100) {
    return Response.json({ error: "a quote request supports at most 100 tickers" }, { status: 400 });
  }

  const result = await fetchQuotesWithFallback(tickers);
  return Response.json(
    { ...result, fetchedAt: new Date().toISOString() },
    {
      headers: {
        "Cache-Control": "public, max-age=15, stale-while-revalidate=45",
      },
    },
  );
}

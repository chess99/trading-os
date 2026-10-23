export function normalizeQuoteKey(value) {
  const raw = String(value).trim().toUpperCase();
  if (/^(?:CN:)?[0-9]{6}$/u.test(raw)) return raw.replace(/^CN:/u, "");
  if (/^HK[:-][0-9]{5}$/u.test(raw)) return raw.replace(":", "-");
  if (/^US[:-][A-Z]{1,5}(?:[.-][A-Z])?$/u.test(raw)) return raw.replace(":", "-");
  return null;
}
export function quoteCode(key) {
  if (key.startsWith("HK-")) return `hk${key.slice(3)}`;
  if (key.startsWith("US-")) return `us${key.slice(3)}`;
  if (/^(?:4|8|920)/u.test(key)) return `bj${key}`;
  return `${/^(?:5|6|9)/u.test(key) ? "sh" : "sz"}${key}`;
}
export function exchangeTimestamp(value, zone) {
  const match = /^(\d{4})[-/](\d{2})[-/](\d{2}) (\d{2}):(\d{2}):(\d{2})$/u.exec(value);
  if (!match) return null;
  const [,y,m,d,h,min,sec] = match.map(Number);
  const wall = Date.UTC(y,m-1,d,h,min,sec);
  const fmt = new Intl.DateTimeFormat("en-GB", { timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
  let utc = wall;
  for (let i=0;i<2;i++) {
    const parts = Object.fromEntries(fmt.formatToParts(new Date(utc)).map((p) => [p.type,p.value]));
    const represented = Date.UTC(+parts.year,+parts.month-1,+parts.day,+parts.hour,+parts.minute,+parts.second);
    utc += wall-represented;
  }
  return new Date(utc).toISOString();
}
export function parseForeignTencent(text, requested) {
  const allowed = new Set(requested);
  return [...text.matchAll(/v_(hk[0-9]{5}|us[A-Z]{1,5}(?:[.-][A-Z])?)="([^"\r\n]*)";/gu)].flatMap((match) => {
    const hk = match[1].startsWith("hk");
    const ticker = `${hk ? "HK" : "US"}-${match[1].slice(2)}`;
    if (!allowed.has(ticker)) return [];
    const f=match[2].split("~");
    const currency = hk ? f[75] : f[35];
    if (currency !== (hk ? "HKD" : "USD")) return [];
    const price=Number(f[3]);
    if (!Number.isFinite(price) || price<=0) return [];
    const num = (v) => v !== "" && Number.isFinite(Number(v)) ? Number(v) : null;
    return [{symbol:ticker.replace("-",":"),ticker,name:f[1],price,currency,
      previousClose:num(f[4]),change:num(f[31]),changePercent:num(f[32]),
      quoteAt:exchangeTimestamp(f[30],hk ? "Asia/Hong_Kong" : "America/New_York"),source:"tencent"}];
  });
}

export function matchingQuoteCurrency(quote, currency) { return Boolean(quote && (quote.currency ?? "CNY") === currency); }

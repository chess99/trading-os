from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(slots=True)
class TushareResearchProvider:
    """Tushare Pro adapter for A-share research datasets.

    The adapter is intentionally optional. Production code can enable it with
    `TUSHARE_TOKEN`; tests inject a fake `pro_client` and never call the network.
    """

    token: str | None = None
    pro_client: Any | None = None

    name = "tushare"
    capabilities = {"universe", "quote_snapshot_eod", "bars_daily", "fundamentals"}

    def _client(self) -> Any:
        if self.pro_client is not None:
            return self.pro_client
        try:
            import tushare as ts
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("tushare is not installed; install trading-os[data_ashare]") from exc
        if not self.token:
            raise RuntimeError("TUSHARE_TOKEN is required for TushareResearchProvider")
        return ts.pro_api(self.token)

    def fetch_universe(self, as_of: date) -> Any:  # noqa: ARG002
        import pandas as pd

        raw = self._client().stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,symbol,name,area,industry,market,list_date,list_status",
        )
        if raw is None or raw.empty:
            return pd.DataFrame()
        out = raw.copy()
        out["symbol"] = out["ts_code"].map(_canonical_from_ts_code)
        out["exchange"] = out["ts_code"].map(lambda value: str(value).split(".")[-1])
        out["is_st"] = out["name"].astype(str).str.contains("ST|退市", na=False)
        out["is_active"] = out.get("list_status", "L").astype(str).eq("L") & ~out["is_st"]
        columns = [
            "symbol",
            "name",
            "exchange",
            "market",
            "area",
            "industry",
            "list_date",
            "is_st",
            "is_active",
        ]
        return out[[column for column in columns if column in out.columns]].dropna(
            subset=["symbol"]
        )

    def fetch_quote_snapshot(self, as_of: date) -> Any:
        import pandas as pd

        trade_date = _yyyymmdd(as_of)
        daily = self._client().daily(trade_date=trade_date)
        if daily is None or daily.empty:
            return pd.DataFrame()
        daily_basic = _safe_client_call(
            self._client(),
            "daily_basic",
            trade_date=trade_date,
            fields="ts_code,total_mv,circ_mv,pe_ttm,pb,turnover_rate,volume_ratio",
        )
        out = daily.copy()
        if daily_basic is not None and not daily_basic.empty:
            out = out.merge(daily_basic, on="ts_code", how="left")
        return _normalize_tushare_bars(out, include_quote_fields=True)

    def fetch_bars(self, symbols: list[str], start: date, end: date, adjustment: str) -> Any:
        import pandas as pd

        parts = []
        for symbol in symbols:
            ts_code = _ts_code_from_canonical(symbol)
            raw = self._client().daily(
                ts_code=ts_code,
                start_date=_yyyymmdd(start),
                end_date=_yyyymmdd(end),
            )
            if raw is None or raw.empty:
                continue
            bars = raw.copy()
            if adjustment in {"qfq", "hfq"}:
                bars = _apply_forward_adjustment(self._client(), bars, adjustment=adjustment)
            parts.append(_normalize_tushare_bars(bars, include_quote_fields=False))
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    def fetch_fundamentals(
        self, symbols: list[str], as_of: date, periods: int | None = None
    ) -> Any:
        import pandas as pd

        rows = []
        for symbol in symbols:
            raw = self._client().fina_indicator(
                ts_code=_ts_code_from_canonical(symbol),
                end_date="",
                start_date="",
            )
            row = _latest_fina_indicator(symbol, raw, as_of=as_of, periods=periods)
            if row:
                rows.append(row)
        return pd.DataFrame(rows)


def _normalize_tushare_bars(raw: Any, *, include_quote_fields: bool) -> Any:
    import pandas as pd

    out = pd.DataFrame(
        {
            "symbol": raw["ts_code"].map(_canonical_from_ts_code),
            "ts": pd.to_datetime(raw["trade_date"], format="%Y%m%d", errors="coerce"),
            "open": pd.to_numeric(raw.get("open"), errors="coerce"),
            "high": pd.to_numeric(raw.get("high"), errors="coerce"),
            "low": pd.to_numeric(raw.get("low"), errors="coerce"),
            "close": pd.to_numeric(raw.get("close"), errors="coerce"),
            "pre_close": pd.to_numeric(raw.get("pre_close"), errors="coerce"),
            "pct_chg": pd.to_numeric(raw.get("pct_chg"), errors="coerce"),
            "volume": pd.to_numeric(raw.get("vol"), errors="coerce") * 100.0,
            "amount": pd.to_numeric(raw.get("amount"), errors="coerce") * 1000.0,
        }
    )
    if include_quote_fields:
        for target, source in [
            ("market_cap", "total_mv"),
            ("float_market_cap", "circ_mv"),
            ("pe_ttm", "pe_ttm"),
            ("pb", "pb"),
            ("turnover_rate", "turnover_rate"),
            ("volume_ratio", "volume_ratio"),
        ]:
            if source in raw.columns:
                out[target] = pd.to_numeric(raw[source], errors="coerce")
        if "market_cap" in out.columns:
            out["market_cap"] = out["market_cap"] * 10_000.0
        if "float_market_cap" in out.columns:
            out["float_market_cap"] = out["float_market_cap"] * 10_000.0
    return out.dropna(subset=["symbol", "ts"]).sort_values(["symbol", "ts"]).reset_index(drop=True)


def _apply_forward_adjustment(client: Any, bars: Any, *, adjustment: str) -> Any:
    import pandas as pd

    factors = _safe_client_call(
        client,
        "adj_factor",
        ts_code=str(bars.iloc[0]["ts_code"]),
        start_date=str(bars["trade_date"].min()),
        end_date=str(bars["trade_date"].max()),
    )
    if factors is None or factors.empty or "adj_factor" not in factors.columns:
        return bars
    merged = bars.merge(
        factors[["ts_code", "trade_date", "adj_factor"]],
        on=["ts_code", "trade_date"],
    ).sort_values("trade_date")
    if merged.empty:
        return bars
    factor = pd.to_numeric(merged["adj_factor"], errors="coerce")
    if adjustment == "qfq":
        base = factor.iloc[-1]
    else:
        base = factor.iloc[0]
    if not base:
        return bars
    multiplier = factor / float(base)
    for column in ("open", "high", "low", "close", "pre_close"):
        if column in merged.columns:
            merged[column] = pd.to_numeric(merged[column], errors="coerce") * multiplier
    return merged


def _latest_fina_indicator(
    symbol: str, raw: Any, *, as_of: date, periods: int | None
) -> dict[str, Any] | None:
    import pandas as pd

    if raw is None or raw.empty:
        return None
    df = raw.copy()
    if "end_date" not in df.columns:
        return None
    df["end_date"] = pd.to_datetime(df["end_date"], format="%Y%m%d", errors="coerce")
    if "ann_date" in df.columns:
        df["ann_date"] = pd.to_datetime(df["ann_date"], format="%Y%m%d", errors="coerce")
        df = df[(df["ann_date"].dt.date <= as_of) | df["ann_date"].isna()]
    else:
        df = df[df["end_date"].dt.date <= as_of]
    df = df.dropna(subset=["end_date"]).sort_values("end_date", ascending=False)
    if df.empty:
        return None
    history = df.head(periods or 8)
    latest = history.iloc[0]
    return {
        "symbol": symbol,
        "period": latest["end_date"].date().isoformat(),
        "pub_date": _date_or_none(latest.get("ann_date")),
        "eps_growth_yoy": _ratio(latest, "q_netprofit_yoy", "netprofit_yoy"),
        "revenue_growth_yoy": _ratio(latest, "tr_yoy", "or_yoy"),
        "roe": _ratio(latest, "roe", "roe_waa"),
        "gross_margin": _ratio(latest, "grossprofit_margin"),
        "net_margin": _ratio(latest, "netprofit_margin"),
        "debt_to_assets": _ratio(latest, "debt_to_assets"),
        "positive_quarters": _positive_quarters(history),
    }


def _positive_quarters(history: Any) -> int | None:
    import pandas as pd

    for column in ("q_netprofit", "n_income_attr_p", "netprofit"):
        if column not in history.columns:
            continue
        count = 0
        for value in pd.to_numeric(history[column], errors="coerce"):
            if pd.isna(value) or float(value) <= 0:
                break
            count += 1
        return count
    return None


def _ratio(row: Any, *columns: str) -> float | None:
    import pandas as pd

    for column in columns:
        if column not in row:
            continue
        value = pd.to_numeric(row.get(column), errors="coerce")
        if pd.isna(value):
            continue
        return float(value) / 100.0
    return None


def _date_or_none(value: Any) -> str | None:
    import pandas as pd

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def _canonical_from_ts_code(value: Any) -> str | None:
    text = str(value)
    if "." not in text:
        return None
    ticker, suffix = text.split(".", 1)
    exchange = {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}.get(suffix.upper())
    if exchange is None:
        return None
    return f"{exchange}:{ticker.zfill(6)}"


def _ts_code_from_canonical(symbol: str) -> str:
    exchange, ticker = symbol.split(":", 1)
    suffix = {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}[exchange]
    return f"{ticker}.{suffix}"


def _yyyymmdd(value: date) -> str:
    return value.strftime("%Y%m%d")


def _safe_client_call(client: Any, method_name: str, **kwargs: Any) -> Any:
    method = getattr(client, method_name, None)
    if method is None:
        return None
    try:
        return method(**kwargs)
    except Exception:
        return None

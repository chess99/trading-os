from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .paid_provider_utils import (
    canonical_from_vendor_code,
    normalize_fundamentals,
    normalize_price_frame,
    vendor_code_from_canonical,
    ymd,
)


@dataclass(slots=True)
class JqdataResearchProvider:
    """JoinQuant JQData adapter with optional runtime dependency."""

    client: Any | None = None
    username: str | None = None
    password: str | None = None

    name = "jqdata"
    capabilities = {"universe", "quote_snapshot_eod", "bars_daily", "fundamentals"}

    def _client(self) -> Any:
        if self.client is not None:
            return self.client
        try:
            import jqdatasdk
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("jqdatasdk is not installed") from exc
        if self.username and self.password:
            jqdatasdk.auth(self.username, self.password)
        return jqdatasdk

    def fetch_universe(self, as_of: date) -> Any:
        import pandas as pd

        raw = self._client().get_all_securities(types=["stock"], date=ymd(as_of))
        if raw is None or raw.empty:
            return pd.DataFrame()
        df = raw.reset_index()
        if "code" not in df.columns:
            df = df.rename(columns={"index": "code"})
        if "code" in df.columns and hasattr(df["code"], "ndim") and df["code"].ndim != 1:
            df = df.loc[:, ~df.columns.duplicated()]
        out = pd.DataFrame(
            {
                "symbol": df["code"].map(canonical_from_vendor_code),
                "name": df.get("display_name", df.get("name")),
                "exchange": df["code"].astype(str).str.split(".").str[-1],
                "list_date": df.get("start_date"),
                "is_st": False,
                "is_active": True,
            }
        )
        out["is_active"] = out["is_active"].map(bool).astype(object)
        return out.dropna(subset=["symbol"]).reset_index(drop=True)

    def fetch_quote_snapshot(self, as_of: date) -> Any:
        universe = self.fetch_universe(as_of)
        symbols = universe["symbol"].astype(str).tolist() if not universe.empty else []
        return self.fetch_bars(symbols, start=as_of, end=as_of, adjustment="qfq")

    def fetch_bars(self, symbols: list[str], start: date, end: date, adjustment: str) -> Any:
        import pandas as pd

        securities = [vendor_code_from_canonical(symbol, style="jqdata") for symbol in symbols]
        if not securities:
            return pd.DataFrame()
        raw = self._client().get_price(
            securities,
            start_date=ymd(start),
            end_date=ymd(end),
            frequency="daily",
            fq="pre" if adjustment == "qfq" else None,
        )
        if raw is None or raw.empty:
            return pd.DataFrame()
        return normalize_price_frame(raw, symbol_column="code", date_column="time")

    def fetch_fundamentals(
        self,
        symbols: list[str],
        as_of: date,
        periods: int | None = None,
    ) -> Any:
        import pandas as pd

        securities = [vendor_code_from_canonical(symbol, style="jqdata") for symbol in symbols]
        raw = self._client().get_fundamentals(securities, as_of, periods)
        if raw is None or raw.empty:
            return pd.DataFrame()
        return normalize_fundamentals(raw, symbol_column="code")

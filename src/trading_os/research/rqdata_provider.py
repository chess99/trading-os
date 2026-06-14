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
class RqdataResearchProvider:
    """RiceQuant RQData adapter.

    The real `rqdatac` package is optional; tests inject a fake client. This adapter keeps
    the production boundary capability-based so DataHub can swap it in without recipes
    knowing the vendor.
    """

    client: Any | None = None
    username: str | None = None
    password: str | None = None

    name = "rqdata"
    capabilities = {"universe", "quote_snapshot_eod", "bars_daily", "fundamentals"}

    def _client(self) -> Any:
        if self.client is not None:
            return self.client
        try:
            import rqdatac
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("rqdatac is not installed") from exc
        if self.username and self.password:
            rqdatac.init(self.username, self.password)
        return rqdatac

    def fetch_universe(self, as_of: date) -> Any:
        import pandas as pd

        raw = self._client().all_instruments(type="CS", date=ymd(as_of))
        if raw is None or raw.empty:
            return pd.DataFrame()
        out = pd.DataFrame(
            {
                "symbol": raw["order_book_id"].map(canonical_from_vendor_code),
                "name": raw.get("symbol"),
                "exchange": raw.get("exchange"),
                "list_date": raw.get("listed_date"),
                "is_st": False,
                "is_active": raw.get("status", "Active").astype(str).str.lower().eq("active"),
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

        order_book_ids = [vendor_code_from_canonical(symbol, style="rqdata") for symbol in symbols]
        if not order_book_ids:
            return pd.DataFrame()
        raw = self._client().get_price(
            order_book_ids,
            start_date=ymd(start),
            end_date=ymd(end),
            frequency="1d",
            adjust_type="pre" if adjustment == "qfq" else "none",
        )
        if raw is None or raw.empty:
            return pd.DataFrame()
        return normalize_price_frame(raw, symbol_column="order_book_id", date_column="date")

    def fetch_fundamentals(
        self,
        symbols: list[str],
        as_of: date,
        periods: int | None = None,
    ) -> Any:
        import pandas as pd

        order_book_ids = [vendor_code_from_canonical(symbol, style="rqdata") for symbol in symbols]
        raw = self._client().get_fundamentals(order_book_ids, as_of, periods)
        if raw is None or raw.empty:
            return pd.DataFrame()
        return normalize_fundamentals(raw, symbol_column="order_book_id")

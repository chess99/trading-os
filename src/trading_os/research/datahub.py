from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from .store import ResearchStore


class MissingDataError(RuntimeError):
    pass


class ResearchDataProvider(Protocol):
    def fetch_universe(self, as_of: date) -> Any: ...
    def fetch_quote_snapshot(self, as_of: date) -> Any: ...


@dataclass
class DataHub:
    store: ResearchStore
    provider: Any | None = None

    def get_universe(self, as_of: date, *, policy: str = "cache_first") -> Any:
        cached = self.store.get_universe(as_of=as_of)
        if policy in {"cache_first", "offline", "lazy_fill"} and not cached.empty:
            return cached
        if policy == "offline":
            raise MissingDataError(f"universe_snapshot missing for as_of={as_of}")
        provider = self._provider()
        source = self._provider_name(provider)
        df = provider.fetch_universe(as_of)
        self.store.write_universe(df, as_of=as_of, source=source, provenance={"provider": source})
        return self.store.get_universe(as_of=as_of)

    def get_quote_snapshot(self, as_of: date, *, policy: str = "cache_first") -> Any:
        cached = self.store.get_quote_snapshot(as_of=as_of)
        if policy in {"cache_first", "offline", "lazy_fill"} and not cached.empty:
            return cached
        if policy == "offline":
            raise MissingDataError(f"quote_snapshot missing for as_of={as_of}")
        provider = self._provider()
        source = self._provider_name(provider)
        df = provider.fetch_quote_snapshot(as_of)
        self.store.write_quote_snapshot(
            df, as_of=as_of, source=source, provenance={"provider": source}
        )
        return self.store.get_quote_snapshot(as_of=as_of)

    def get_bars(
        self,
        symbols: list[str],
        *,
        start: date,
        end: date,
        adjustment: str = "qfq",
        policy: str = "lazy_fill",
    ) -> Any:
        cached = self.store.get_bars(symbols, start=start, end=end)
        cached_symbols = set(cached["symbol"].unique()) if not cached.empty else set()
        missing = [sym for sym in symbols if sym not in cached_symbols]
        if missing and policy == "offline":
            raise MissingDataError(f"bars missing for {','.join(missing)}")
        if missing and policy in {"lazy_fill", "refresh", "cache_first"}:
            provider = self._provider()
            source = self._provider_name(provider)
            df = provider.fetch_bars(missing, start, end, adjustment)
            if df is not None and not df.empty:
                self.store.write_bars(df, source=source, provenance={"provider": source})
        return self.store.get_bars(symbols, start=start, end=end)

    def get_fundamentals(
        self,
        symbols: list[str],
        *,
        as_of: date,
        periods: int | None = None,
        policy: str = "cache_first",
    ) -> Any:
        cached = self.store.get_fundamentals(symbols, as_of=as_of)
        if policy in {"cache_first", "offline", "lazy_fill"} and not cached.empty:
            return cached
        if policy == "offline":
            raise MissingDataError(f"fundamentals missing for as_of={as_of}")
        provider = self._provider()
        if not hasattr(provider, "fetch_fundamentals"):
            return cached
        source = self._provider_name(provider)
        df = provider.fetch_fundamentals(symbols, as_of, periods)
        if df is not None and not df.empty:
            self.store.write_fundamentals(
                df, as_of=as_of, source=source, provenance={"provider": source}
            )
        return self.store.get_fundamentals(symbols, as_of=as_of)

    def get_estimates(self, symbols: list[str], *, as_of: date, policy: str = "cache_first") -> Any:
        cached = self.store.get_estimates(symbols, as_of=as_of)
        if policy in {"cache_first", "offline", "lazy_fill"} and not cached.empty:
            return cached
        if policy == "offline":
            raise MissingDataError(f"estimates missing for as_of={as_of}")
        return cached

    def get_news(
        self,
        symbols: list[str],
        *,
        as_of: date,
        lookback_months: int = 12,
        policy: str = "cache_first",
    ) -> Any:
        cached = self.store.get_news(symbols, as_of=as_of)
        if policy in {"cache_first", "offline", "lazy_fill"} and not cached.empty:
            return cached
        if policy == "offline":
            raise MissingDataError(f"news missing for as_of={as_of}")
        return cached

    def _provider(self) -> Any:
        if self.provider is None:
            self.provider = AkshareResearchProvider()
        return self.provider

    @staticmethod
    def _provider_name(provider: Any) -> str:
        return str(getattr(provider, "name", provider.__class__.__name__))


class AkshareResearchProvider:
    name = "akshare"

    def fetch_universe(self, as_of: date) -> Any:  # noqa: ARG002
        from ..data.sources.akshare_factors import AkshareFactorSource

        df = AkshareFactorSource().get_a_stock_list()
        df["is_st"] = df["name"].astype(str).str.contains("ST|退市", na=False)
        df["is_active"] = ~df["name"].astype(str).str.contains("退市", na=False)
        return df[["symbol", "name", "exchange", "market", "is_st", "is_active"]].assign(
            symbol=lambda x: x["exchange"].astype(str) + ":" + x["symbol"].astype(str)
        )

    def fetch_quote_snapshot(self, as_of: date) -> Any:  # noqa: ARG002
        import akshare as ak
        import pandas as pd

        raw = ak.stock_zh_a_spot_em()
        if raw is None or raw.empty:
            return pd.DataFrame()
        out = pd.DataFrame(
            {
                "symbol": raw["代码"].map(_canonical_from_code),
                "name": raw.get("名称", ""),
                "close": pd.to_numeric(raw.get("最新价"), errors="coerce"),
                "volume": pd.to_numeric(raw.get("成交量"), errors="coerce") * 100.0,
                "amount": pd.to_numeric(raw.get("成交额"), errors="coerce"),
                "market_cap": pd.to_numeric(raw.get("总市值"), errors="coerce"),
                "pe_ttm": pd.to_numeric(raw.get("市盈率-动态"), errors="coerce"),
                "pb": pd.to_numeric(raw.get("市净率"), errors="coerce"),
            }
        )
        return out.dropna(subset=["symbol"])

    def fetch_bars(self, symbols: list[str], start: date, end: date, adjustment: str) -> Any:
        import pandas as pd

        from ..data.schema import Adjustment, Exchange
        from ..data.sources.akshare_source import fetch_daily_bars

        adj = {"qfq": Adjustment.QFQ, "hfq": Adjustment.HFQ}.get(adjustment, Adjustment.NONE)
        parts = []
        for symbol in symbols:
            exchange, ticker = symbol.split(":", 1)
            df, _source = fetch_daily_bars(
                ticker,
                exchange=Exchange(exchange),
                start=start.isoformat(),
                end=end.isoformat(),
                adjustment=adj,
            )
            if not df.empty:
                parts.append(df)
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _canonical_from_code(code: str) -> str:
    code = str(code).zfill(6)
    exchange = "SSE" if code.startswith("6") else "SZSE"
    return f"{exchange}:{code}"

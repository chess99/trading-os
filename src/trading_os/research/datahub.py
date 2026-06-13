from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from .providers import ProviderFetchError, ProviderResult, ProviderRouter
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
        if (
            policy in {"cache_first", "offline", "lazy_fill"}
            and not cached.empty
            and _snapshot_matches_as_of(cached, as_of)
        ):
            return cached
        if policy == "offline":
            raise MissingDataError(f"universe_snapshot missing for as_of={as_of}")
        provider = self._provider()
        if isinstance(provider, ProviderRouter):
            result = self._router_fetch(provider, "universe", "fetch_universe", as_of)
            source = result.provider_name
            df = result.data
        else:
            source = self._provider_name(provider)
            df = provider.fetch_universe(as_of)
            self._ensure_non_empty(df, "universe", source)
        self.store.write_universe(df, as_of=as_of, source=source, provenance={"provider": source})
        return self.store.get_universe(as_of=as_of)

    def get_quote_snapshot(self, as_of: date, *, policy: str = "cache_first") -> Any:
        cached = self.store.get_quote_snapshot(as_of=as_of)
        if (
            policy in {"cache_first", "offline", "lazy_fill"}
            and not cached.empty
            and _snapshot_matches_as_of(cached, as_of)
        ):
            return cached
        if policy == "offline":
            raise MissingDataError(f"quote_snapshot missing for as_of={as_of}")
        provider = self._provider()
        if isinstance(provider, ProviderRouter):
            result = self._router_fetch(
                provider, "quote_snapshot_eod", "fetch_quote_snapshot", as_of
            )
            source = result.provider_name
            df = result.data
        else:
            source = self._provider_name(provider)
            df = provider.fetch_quote_snapshot(as_of)
            self._ensure_non_empty(df, "quote_snapshot_eod", source)
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
        missing = _symbols_with_missing_bar_coverage(cached, symbols, start=start, end=end)
        if missing and policy == "offline":
            raise MissingDataError(f"bars missing for {','.join(missing)}")
        symbols_to_fetch = list(symbols) if policy == "refresh" else missing
        if symbols_to_fetch and policy in {"lazy_fill", "refresh", "cache_first"}:
            provider = self._provider()
            if isinstance(provider, ProviderRouter):
                result = self._router_fetch(
                    provider, "bars_daily", "fetch_bars", symbols_to_fetch, start, end, adjustment
                )
                source = result.provider_name
                df = result.data
            else:
                source = self._provider_name(provider)
                df = provider.fetch_bars(symbols_to_fetch, start, end, adjustment)
                self._ensure_non_empty(df, "bars_daily", source)
            if df is not None and not df.empty:
                self.store.write_bars(df, source=source, provenance={"provider": source})
        final = self.store.get_bars(symbols, start=start, end=end)
        remaining = _symbols_with_missing_bar_coverage(final, symbols, start=start, end=end)
        if remaining and policy in {"lazy_fill", "refresh"}:
            raise MissingDataError(f"bars missing for {','.join(remaining)}")
        return final

    def get_fundamentals(
        self,
        symbols: list[str],
        *,
        as_of: date,
        periods: int | None = None,
        policy: str = "cache_first",
    ) -> Any:
        cached = self.store.get_fundamentals(symbols, as_of=as_of)
        cached_symbols = _cached_symbols(cached)
        missing = [symbol for symbol in symbols if symbol not in cached_symbols]
        if policy in {"cache_first", "lazy_fill"} and not missing:
            return cached
        if policy == "offline":
            if missing:
                raise MissingDataError(
                    f"fundamentals missing for {','.join(missing)} as_of={as_of}"
                )
            return cached
        symbols_to_fetch = list(symbols) if policy == "refresh" else missing
        if not symbols_to_fetch:
            return cached
        provider = self._provider()
        if isinstance(provider, ProviderRouter):
            result = self._router_fetch(
                provider, "fundamentals", "fetch_fundamentals", symbols_to_fetch, as_of, periods
            )
            source = result.provider_name
            df = result.data
        else:
            if not hasattr(provider, "fetch_fundamentals"):
                return cached
            source = self._provider_name(provider)
            df = provider.fetch_fundamentals(symbols_to_fetch, as_of, periods)
            if policy == "refresh":
                self._ensure_non_empty(df, "fundamentals", source)
        if df is not None and not df.empty:
            if policy != "refresh" and not cached.empty:
                df = _merge_fundamentals(cached, df)
            self.store.write_fundamentals(
                df, as_of=as_of, source=source, provenance={"provider": source}
            )
        final = self.store.get_fundamentals(symbols, as_of=as_of)
        remaining = [symbol for symbol in symbols_to_fetch if symbol not in _cached_symbols(final)]
        if remaining and policy == "refresh":
            raise MissingDataError(f"fundamentals missing for {','.join(remaining)} as_of={as_of}")
        return final

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

    def _router_fetch(
        self, provider: ProviderRouter, capability: str, method_name: str, *args: Any
    ) -> ProviderResult:
        try:
            result = provider.fetch(capability, method_name, *args)
        except ProviderFetchError as exc:
            self.store.write_provider_health(exc.failures)
            raise
        self.store.write_provider_health(result.failures)
        return result

    @staticmethod
    def _ensure_non_empty(data: Any, capability: str, source: str) -> None:
        if data is None or getattr(data, "empty", False) is True:
            raise MissingDataError(f"{capability} provider {source} returned no data")

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

    def fetch_fundamentals(
        self, symbols: list[str], as_of: date, periods: int | None = None
    ) -> Any:
        import akshare as ak
        import pandas as pd

        rows = []
        for symbol in symbols:
            _exchange, ticker = symbol.split(":", 1)
            try:
                raw = ak.stock_financial_abstract_new_ths(symbol=ticker)
            except Exception:
                continue
            row = _quarter_history_from_ths(symbol, raw, as_of=as_of, periods=periods)
            if row:
                rows.append(row)
        return pd.DataFrame(rows)


def _canonical_from_code(code: str) -> str:
    code = str(code).zfill(6)
    exchange = "SSE" if code.startswith("6") else "SZSE"
    return f"{exchange}:{code}"


def _snapshot_matches_as_of(cached: Any, as_of: date) -> bool:
    if cached is None or cached.empty or "as_of" not in cached.columns:
        return False
    return cached["as_of"].astype(str).eq(as_of.isoformat()).all()


def _symbols_with_missing_bar_coverage(
    cached: Any, symbols: list[str], *, start: date, end: date
) -> list[str]:
    if cached is None or cached.empty:
        return list(symbols)
    if "symbol" not in cached.columns or "ts" not in cached.columns:
        return list(symbols)

    import pandas as pd

    expected_dates = set(pd.bdate_range(start=start, end=end, inclusive="left").date)
    result: list[str] = []
    for symbol in symbols:
        rows = cached[cached["symbol"] == symbol]
        if rows.empty:
            result.append(symbol)
            continue
        if not expected_dates:
            continue
        cached_dates = set(pd.to_datetime(rows["ts"], utc=True).dt.date)
        if not expected_dates.issubset(cached_dates):
            result.append(symbol)
    return result


def _cached_symbols(cached: Any) -> set[str]:
    if cached is None or cached.empty or "symbol" not in cached.columns:
        return set()
    return set(cached["symbol"].astype(str))


def _merge_fundamentals(cached: Any, fetched: Any) -> Any:
    import pandas as pd

    if cached is None or cached.empty:
        return fetched
    if fetched is None or fetched.empty:
        return cached
    cached_idx = cached.copy().set_index("symbol", drop=False)
    fetched_idx = fetched.copy().set_index("symbol", drop=False)
    merged = fetched_idx.combine_first(cached_idx)
    return pd.DataFrame(merged).reset_index(drop=True)


def _quarter_history_from_ths(
    symbol: str, raw: Any, *, as_of: date, periods: int | None = None
) -> dict[str, Any] | None:
    import pandas as pd

    if raw is None or raw.empty:
        return None
    df = raw.copy()
    if "report_date" not in df.columns or "metric_name" not in df.columns:
        return None
    df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
    df = df[df["report_date"].dt.date <= as_of]
    profit = df[df["metric_name"] == "parent_holder_net_profit"].sort_values(
        "report_date", ascending=False
    )
    if profit.empty:
        return None
    if periods is not None:
        profit = profit.head(periods)

    positive_quarters = 0
    for value in pd.to_numeric(profit.get("single"), errors="coerce"):
        if pd.isna(value) or float(value) <= 0:
            break
        positive_quarters += 1

    latest = profit.iloc[0]
    return {
        "symbol": symbol,
        "period": latest["report_date"].date().isoformat(),
        "pub_date": latest["report_date"].date().isoformat(),
        "positive_quarters": positive_quarters,
    }

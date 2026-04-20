"""DataPipeline look-ahead bias protection tests.

The most important invariant in the system: get_bars(trading_date=T)
must NEVER return a bar with ts >= T.
"""
import pathlib
import tempfile
from datetime import date, datetime, timezone

import pytest

pd = pytest.importorskip("pandas")


def _make_lake_with_bars(tmp_path: pathlib.Path):
    """Create a LocalDataLake with synthetic bars spanning 2024-01-01 to 2024-06-30."""
    from trading_os.data.lake import LocalDataLake
    from trading_os.data.schema import Adjustment, Exchange, Timeframe

    lake = LocalDataLake(tmp_path)

    dates = pd.date_range("2024-01-01", "2024-06-30", freq="B", tz="UTC")
    prices = [100.0 + i * 0.1 for i in range(len(dates))]
    bars = pd.DataFrame({
        "symbol": "SSE:600000",
        "ts": dates,
        "open": prices,
        "high": [p * 1.01 for p in prices],
        "low": [p * 0.99 for p in prices],
        "close": prices,
        "volume": [1_000_000.0] * len(dates),
        "source": "synthetic",
    })
    lake.write_bars_parquet(
        bars,
        exchange=Exchange.SSE,
        timeframe=Timeframe.D1,
        adjustment=Adjustment.QFQ,
        source="synthetic",
    )
    lake.init()
    return lake


def test_get_bars_excludes_trading_date():
    """No bar with ts >= trading_date should be returned."""
    from trading_os.data.pipeline import DataPipeline

    with tempfile.TemporaryDirectory() as tmp:
        lake = _make_lake_with_bars(pathlib.Path(tmp))
        pipeline = DataPipeline(lake)

        trading_date = date(2024, 3, 15)
        bars = pipeline.get_bars(
            symbols=["SSE:600000"],
            trading_date=trading_date,
            lookback_days=120,
        )

        assert not bars.empty, "Should return historical bars"
        cutoff = pd.Timestamp(trading_date, tz="UTC")
        assert (bars["ts"] < cutoff).all(), (
            f"All bars must be strictly before {trading_date}, "
            f"but found bars on or after: {bars[bars['ts'] >= cutoff]['ts'].tolist()}"
        )


def test_get_bars_cutoff_is_strict():
    """The bar on trading_date itself must be excluded (strict <, not <=)."""
    from trading_os.data.pipeline import DataPipeline

    with tempfile.TemporaryDirectory() as tmp:
        lake = _make_lake_with_bars(pathlib.Path(tmp))
        pipeline = DataPipeline(lake)

        # 2024-03-15 is a Friday — there's a bar on that date in the synthetic data
        trading_date = date(2024, 3, 15)
        bars = pipeline.get_bars(
            symbols=["SSE:600000"],
            trading_date=trading_date,
            lookback_days=365,
        )

        # The bar for 2024-03-15 must NOT be in the result
        trading_date_ts = pd.Timestamp(trading_date, tz="UTC")
        same_day_bars = bars[bars["ts"] == trading_date_ts]
        assert same_day_bars.empty, (
            f"Bar for trading_date {trading_date} must be excluded, but was returned"
        )


def test_get_bars_includes_day_before_trading_date():
    """The bar for trading_date - 1 business day should be included."""
    from trading_os.data.pipeline import DataPipeline

    with tempfile.TemporaryDirectory() as tmp:
        lake = _make_lake_with_bars(pathlib.Path(tmp))
        pipeline = DataPipeline(lake)

        trading_date = date(2024, 3, 15)  # Friday
        bars = pipeline.get_bars(
            symbols=["SSE:600000"],
            trading_date=trading_date,
            lookback_days=365,
        )

        # 2024-03-14 (Thursday) should be the latest bar
        prev_day = pd.Timestamp("2024-03-14", tz="UTC")
        assert not bars.empty
        latest = bars["ts"].max()
        assert latest == prev_day, (
            f"Latest bar should be 2024-03-14, got {latest}"
        )


def test_get_bars_empty_when_no_data_before_trading_date():
    """Returns empty DataFrame when trading_date is before all available data."""
    from trading_os.data.pipeline import DataPipeline

    with tempfile.TemporaryDirectory() as tmp:
        lake = _make_lake_with_bars(pathlib.Path(tmp))
        pipeline = DataPipeline(lake)

        # Data starts 2024-01-01, so trading_date=2024-01-01 means no prior data
        bars = pipeline.get_bars(
            symbols=["SSE:600000"],
            trading_date=date(2024, 1, 1),
            lookback_days=30,
        )
        assert bars.empty


def test_available_symbols_returns_correct_list():
    """available_symbols() returns the symbols present in the lake."""
    from trading_os.data.pipeline import DataPipeline

    with tempfile.TemporaryDirectory() as tmp:
        lake = _make_lake_with_bars(pathlib.Path(tmp))
        pipeline = DataPipeline(lake)

        symbols = pipeline.available_symbols()
        assert "SSE:600000" in symbols

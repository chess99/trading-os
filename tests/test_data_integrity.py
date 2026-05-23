import pytest
import pandas as pd


def test_data_integrity_error_is_value_error():
    """DataIntegrityError must be catchable as ValueError."""
    from trading_os.data.exceptions import DataIntegrityError

    with pytest.raises(ValueError):
        raise DataIntegrityError(
            symbol="SSE:000001",
            expected_range=(3000.0, 4500.0),
            actual_value=11.0,
        )


def test_data_integrity_error_message_contains_symbol():
    from trading_os.data.exceptions import DataIntegrityError

    err = DataIntegrityError(
        symbol="SSE:000001",
        expected_range=(3000.0, 4500.0),
        actual_value=11.0,
    )
    assert "SSE:000001" in str(err)
    assert "11.0" in str(err)


def _make_lake(tmp_path):
    from trading_os.data.lake import LocalDataLake
    lake = LocalDataLake(tmp_path / "data")
    lake.init()
    return lake


def _make_bar_df(symbol: str, closes: list, source: str = "akshare"):
    """Create a minimal normalized bar DataFrame for writing to the lake."""
    from trading_os.data.schema import Timeframe, Adjustment

    n = len(closes)
    return pd.DataFrame({
        "symbol": [symbol] * n,
        "exchange": [symbol.split(":")[0]] * n,
        "timeframe": [Timeframe.D1.value] * n,
        "adjustment": [Adjustment.NONE.value] * n,
        "ts": pd.date_range("2026-01-02", periods=n, freq="B", tz="UTC"),
        "open":   closes,
        "high":   [c * 1.02 for c in closes],
        "low":    [c * 0.98 for c in closes],
        "close":  closes,
        "volume": [1_000_000.0] * n,
        "vwap":   closes,
        "trades": [10000] * n,
        "source": [source] * n,
    })


def test_price_continuity_passes_on_empty_lake(tmp_path):
    """First write to a new symbol must not raise (empty lake = no history)."""
    from trading_os.data.schema import Timeframe, Adjustment

    lake = _make_lake(tmp_path)
    df = _make_bar_df("SSE:000001", [3200.0, 3210.0], source="akshare_index")

    # Should not raise
    lake.write_bars_parquet(
        df,
        timeframe=Timeframe.D1,
        adjustment=Adjustment.NONE,
        source="akshare_index",
    )


def test_price_continuity_passes_for_normal_equity_update(tmp_path):
    """Writing stock prices consistent with existing history must not raise."""
    from trading_os.data.schema import Timeframe, Adjustment

    lake = _make_lake(tmp_path)
    existing = _make_bar_df("SSE:600000", [10.0, 10.1, 10.2, 10.3, 10.4])
    lake.write_bars_parquet(
        existing,
        timeframe=Timeframe.D1,
        adjustment=Adjustment.NONE,
        source="akshare",
    )
    lake.init()

    new_data = _make_bar_df("SSE:600000", [10.5, 10.6])
    # Should not raise
    lake.write_bars_parquet(
        new_data,
        timeframe=Timeframe.D1,
        adjustment=Adjustment.NONE,
        source="akshare",
    )


def test_price_continuity_rejects_magnitude_jump(tmp_path):
    """Writing 平安银行 prices (~11) after 上证指数 history (~3800) must raise."""
    from trading_os.data.schema import Timeframe, Adjustment
    from trading_os.data.exceptions import DataIntegrityError

    lake = _make_lake(tmp_path)
    # Write correct index history
    good_data = _make_bar_df("SSE:000001", [3800.0, 3850.0, 3900.0, 3920.0, 3880.0],
                             source="baostock")
    lake.write_bars_parquet(
        good_data,
        timeframe=Timeframe.D1,
        adjustment=Adjustment.NONE,
        source="baostock",
    )
    lake.init()

    # Try to write 平安银行 price as if it were 000001
    bad_data = _make_bar_df("SSE:000001", [11.09, 11.01, 11.37], source="akshare")
    with pytest.raises(DataIntegrityError):
        lake.write_bars_parquet(
            bad_data,
            timeframe=Timeframe.D1,
            adjustment=Adjustment.NONE,
            source="akshare",
        )

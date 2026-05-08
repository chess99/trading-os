"""Tests for akshare_source.py — specifically the BaoStock fallback path."""
import pytest
from unittest.mock import MagicMock, patch

pd = pytest.importorskip("pandas")


def _make_akshare_df():
    """Minimal DataFrame in akshare (eastmoney) column format."""
    return pd.DataFrame({
        "日期": pd.date_range("2024-01-01", periods=5, freq="B"),
        "开盘": [10.0, 10.1, 10.2, 10.3, 10.4],
        "最高": [10.5, 10.6, 10.7, 10.8, 10.9],
        "最低": [9.5, 9.6, 9.7, 9.8, 9.9],
        "收盘": [10.2, 10.3, 10.4, 10.5, 10.6],
        "成交量": [1_000_000] * 5,
        "成交额": [10_000_000.0] * 5,
    })


def _make_baostock_df():
    """Minimal DataFrame in baostock_source standard output format."""
    return pd.DataFrame({
        "symbol": ["SSE:600000"] * 5,
        "ts": pd.date_range("2024-01-01", periods=5, freq="B", tz="UTC"),
        "open": [10.0, 10.1, 10.2, 10.3, 10.4],
        "high": [10.5, 10.6, 10.7, 10.8, 10.9],
        "low": [9.5, 9.6, 9.7, 9.8, 9.9],
        "close": [10.2, 10.3, 10.4, 10.5, 10.6],
        "volume": [1_000_000.0] * 5,
        "source": ["baostock"] * 5,
    })


def test_fetch_returns_akshare_source_when_eastmoney_succeeds():
    """When eastmoney succeeds, source should be 'akshare'."""
    from trading_os.data.schema import Exchange
    from trading_os.data.sources.akshare_source import _fetch_with_fallback

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_hist.return_value = _make_akshare_df()

    df, source = _fetch_with_fallback(
        mock_ak, "600000", Exchange.SSE, "20240101", "20240110", "qfq"
    )

    assert source == "akshare"
    assert not df.empty
    assert "收盘" in df.columns


def test_fetch_falls_back_to_baostock_when_akshare_fails():
    """When both eastmoney and sina fail, source should be 'baostock'."""
    from trading_os.data.schema import Exchange
    from trading_os.data.sources.akshare_source import _fetch_with_fallback

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_hist.side_effect = ConnectionError("proxy error")
    mock_ak.stock_zh_a_daily.side_effect = ValueError("No value to decode")

    bs_df = _make_baostock_df()
    with patch(
        "trading_os.data.sources.akshare_source._BAOSTOCK_LOCK"
    ):
        with patch(
            "trading_os.data.sources.baostock_source.fetch_daily_bars",
            return_value=bs_df,
        ):
            df, source = _fetch_with_fallback(
                mock_ak, "600000", Exchange.SSE, "20240101", "20240110", "qfq"
            )

    assert source == "baostock"
    assert not df.empty


def test_fetch_returns_none_source_when_all_fail():
    """When all three sources fail, returns (empty DataFrame, 'none')."""
    from trading_os.data.schema import Exchange
    from trading_os.data.sources.akshare_source import _fetch_with_fallback

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_hist.side_effect = ConnectionError("proxy error")
    mock_ak.stock_zh_a_daily.side_effect = ValueError("No value to decode")

    with patch(
        "trading_os.data.sources.baostock_source.fetch_daily_bars",
        side_effect=RuntimeError("BaoStock failed"),
    ):
        df, source = _fetch_with_fallback(
            mock_ak, "600000", Exchange.SSE, "20240101", "20240110", "qfq"
        )

    assert source == "none"
    assert df.empty


def test_fetch_daily_bars_accepts_asset_type_index():
    """fetch_daily_bars with asset_type=AssetType.INDEX dispatches to IndexHandler."""
    from unittest.mock import patch
    import pandas as pd
    from trading_os.data.schema import Exchange, Adjustment, AssetType
    from trading_os.data.sources.akshare_source import fetch_daily_bars

    mock_df = pd.DataFrame({
        "date": pd.date_range("2026-04-08", periods=3, freq="B"),
        "open": [3200.0, 3210.0, 3220.0],
        "high": [3250.0, 3260.0, 3270.0],
        "low":  [3180.0, 3190.0, 3200.0],
        "close": [3220.0, 3230.0, 3240.0],
        "volume": [30_000_000.0] * 3,
        "amount": [3.5e11] * 3,
    })

    with patch("trading_os.data.sources.asset_type_handler.ak") as mock_ak:
        mock_ak.stock_zh_index_daily.return_value = mock_df
        df, source = fetch_daily_bars(
            "000001",
            exchange=Exchange.SSE,
            adjustment=Adjustment.QFQ,
            asset_type=AssetType.INDEX,
        )

    assert source == "akshare_index"
    assert not df.empty
    assert df["source"].iloc[0] == "akshare_index"
    assert df["adjustment"].iloc[0] == "none"  # forced to NONE for indices


def test_fetch_daily_bars_default_asset_type_is_equity():
    """Calling without asset_type defaults to equity (backward compatible)."""
    from unittest.mock import MagicMock, patch
    from trading_os.data.schema import Exchange, Adjustment
    from trading_os.data.sources.akshare_source import fetch_daily_bars, _make_akshare_df_for_test

    with patch("trading_os.data.sources.akshare_source._fetch_with_fallback") as mock_fb:
        mock_fb.return_value = (_make_akshare_df_for_test(), "akshare")
        df, source = fetch_daily_bars("600000", exchange=Exchange.SSE, adjustment=Adjustment.QFQ)

    assert source == "akshare"

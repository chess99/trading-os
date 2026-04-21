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

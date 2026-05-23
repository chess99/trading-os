"""测试 ETF 代码在 _fetch_with_fallback 中不会走 BaoStock fallback。"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from trading_os.data.sources.akshare_source import _fetch_with_fallback, _SOURCE_AVAILABILITY
from trading_os.data.schema import Exchange


def _make_empty_df():
    return pd.DataFrame()


def _make_valid_df():
    return pd.DataFrame({
        "日期": ["2026-01-02"],
        "开盘": [1.0], "收盘": [1.0], "最高": [1.0], "最低": [1.0], "成交量": [100],
    })


def test_etf_skips_baostock_when_sina_fails():
    """ETF 代码（51xxxx）在新浪失败后，不应尝试 BaoStock——因为 BaoStock 不通时会超时卡死。"""
    import trading_os.data.sources.akshare_source as mod
    # 重置会话缓存
    mod._SOURCE_AVAILABILITY.update({"eastmoney": False, "sina": False, "baostock": None})

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_hist.side_effect = Exception("eastmoney fail")
    mock_ak.stock_zh_a_daily.side_effect = Exception("sina fail: No value to decode")

    baostock_called = []
    def fake_bs_fetch(*args, **kwargs):
        baostock_called.append(True)
        return _make_valid_df()

    with patch("trading_os.data.sources.akshare_source._BAOSTOCK_LOCK"):
        with patch("trading_os.data.sources.baostock_source.fetch_daily_bars", fake_bs_fetch):
            df, src = _fetch_with_fallback(
                mock_ak, "515880", Exchange.SSE, "20260101", "20260401", "qfq"
            )

    assert not baostock_called, "ETF 代码不应触发 BaoStock fallback"
    assert df.empty


def test_normal_stock_still_uses_baostock_fallback():
    """普通股票（600000）在新浪失败后，仍应尝试 BaoStock。"""
    import trading_os.data.sources.akshare_source as mod
    mod._SOURCE_AVAILABILITY.update({"eastmoney": False, "sina": False, "baostock": None})

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_hist.side_effect = Exception("eastmoney fail")
    mock_ak.stock_zh_a_daily.side_effect = Exception("sina fail")

    baostock_called = []
    def fake_bs_fetch(*args, **kwargs):
        baostock_called.append(True)
        return _make_valid_df()

    with patch("trading_os.data.sources.akshare_source._BAOSTOCK_LOCK"):
        with patch("trading_os.data.sources.baostock_source.fetch_daily_bars", fake_bs_fetch):
            df, src = _fetch_with_fallback(
                mock_ak, "600000", Exchange.SSE, "20260101", "20260401", "qfq"
            )

    assert baostock_called, "普通股票应尝试 BaoStock fallback"


def test_kechuang_etf_skips_baostock():
    """科创板 ETF（58xxxx，如588000科创50ETF）也应跳过 BaoStock fallback。"""
    import trading_os.data.sources.akshare_source as mod
    mod._SOURCE_AVAILABILITY.update({"eastmoney": False, "sina": False, "baostock": None})

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_hist.side_effect = Exception("eastmoney fail")
    mock_ak.stock_zh_a_daily.side_effect = Exception("sina fail: No value to decode")

    baostock_called = []
    def fake_bs_fetch(*args, **kwargs):
        baostock_called.append(True)
        return _make_valid_df()

    with patch("trading_os.data.sources.akshare_source._BAOSTOCK_LOCK"):
        with patch("trading_os.data.sources.baostock_source.fetch_daily_bars", fake_bs_fetch):
            df, src = _fetch_with_fallback(
                mock_ak, "588000", Exchange.SSE, "20260101", "20260401", "qfq"
            )

    assert not baostock_called, "科创板ETF（588000）不应触发 BaoStock fallback"
    assert df.empty

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd


def _make_index_df():
    """Minimal DataFrame in ak.stock_zh_index_daily format (English columns)."""
    return pd.DataFrame({
        "date": pd.date_range("2026-04-08", periods=5, freq="B"),
        "open": [3200.0, 3210.0, 3220.0, 3230.0, 3240.0],
        "high": [3250.0, 3260.0, 3270.0, 3280.0, 3290.0],
        "low":  [3180.0, 3190.0, 3200.0, 3210.0, 3220.0],
        "close": [3220.0, 3230.0, 3240.0, 3250.0, 3260.0],
        "volume": [30_000_000.0] * 5,  # 3000万手，正常
        "amount": [3.5e11] * 5,        # 3500亿元
    })


def _make_equity_df():
    """Minimal DataFrame in akshare eastmoney format (Chinese columns)."""
    return pd.DataFrame({
        "日期": pd.date_range("2026-04-08", periods=5, freq="B"),
        "开盘": [10.0, 10.1, 10.2, 10.3, 10.4],
        "最高": [10.5, 10.6, 10.7, 10.8, 10.9],
        "最低": [9.5, 9.6, 9.7, 9.8, 9.9],
        "收盘": [10.2, 10.3, 10.4, 10.5, 10.6],
        "成交量": [1_000_000] * 5,
        "成交额": [10_000_000.0] * 5,
    })


# ── IndexHandler ──────────────────────────────────────────────────────────────

def test_index_handler_fetch_uses_sh_prefix_for_sse():
    """SSE index fetches with 'sh' prefix."""
    from trading_os.data.schema import Exchange, Adjustment
    from trading_os.data.sources.asset_type_handler import IndexHandler

    mock_ak = MagicMock()
    mock_ak.stock_zh_index_daily.return_value = _make_index_df()

    handler = IndexHandler()
    with patch("trading_os.data.sources.asset_type_handler.ak", mock_ak):
        df, source = handler.fetch(
            "000001", Exchange.SSE,
            start="2026-04-08", end="2026-04-12",
            adjustment=Adjustment.QFQ,
        )

    mock_ak.stock_zh_index_daily.assert_called_once_with(symbol="sh000001")
    assert source == "akshare_index"
    assert not df.empty


def test_index_handler_fetch_uses_sz_prefix_for_szse():
    """SZSE index fetches with 'sz' prefix."""
    from trading_os.data.schema import Exchange, Adjustment
    from trading_os.data.sources.asset_type_handler import IndexHandler

    mock_ak = MagicMock()
    mock_ak.stock_zh_index_daily.return_value = _make_index_df()

    handler = IndexHandler()
    with patch("trading_os.data.sources.asset_type_handler.ak", mock_ak):
        df, source = handler.fetch(
            "399001", Exchange.SZSE,
            start="2026-04-08", end="2026-04-12",
            adjustment=Adjustment.QFQ,
        )

    mock_ak.stock_zh_index_daily.assert_called_once_with(symbol="sz399001")
    assert source == "akshare_index"


def test_index_handler_normalized_df_has_standard_columns():
    """fetch() result must have symbol, ts, open, high, low, close, volume, source."""
    from trading_os.data.schema import Exchange, Adjustment
    from trading_os.data.sources.asset_type_handler import IndexHandler

    mock_ak = MagicMock()
    mock_ak.stock_zh_index_daily.return_value = _make_index_df()

    handler = IndexHandler()
    with patch("trading_os.data.sources.asset_type_handler.ak", mock_ak):
        df, _ = handler.fetch(
            "000001", Exchange.SSE,
            start="2026-04-08", end="2026-04-12",
            adjustment=Adjustment.NONE,
        )

    for col in ["symbol", "ts", "open", "high", "low", "close", "volume", "source"]:
        assert col in df.columns, f"Missing column: {col}"
    assert df["source"].iloc[0] == "akshare_index"
    assert df["symbol"].iloc[0] == "SSE:000001"


def test_index_handler_adjustment_forced_to_none():
    """adjustment stored in df must be 'none' regardless of what caller passed."""
    from trading_os.data.schema import Exchange, Adjustment
    from trading_os.data.sources.asset_type_handler import IndexHandler

    mock_ak = MagicMock()
    mock_ak.stock_zh_index_daily.return_value = _make_index_df()

    handler = IndexHandler()
    with patch("trading_os.data.sources.asset_type_handler.ak", mock_ak):
        df, _ = handler.fetch(
            "000001", Exchange.SSE,
            start=None, end=None,
            adjustment=Adjustment.QFQ,   # caller asked for QFQ
        )

    assert df["adjustment"].iloc[0] == "none"  # must be overridden


def test_index_handler_validate_passes_for_valid_index_price():
    """Prices in 100-20000 range and volume > 1e6 should pass."""
    from trading_os.data.schema import Exchange
    from trading_os.data.sources.asset_type_handler import IndexHandler

    handler = IndexHandler()
    df = pd.DataFrame({
        "close": [3200.0, 3250.0],
        "volume": [30_000_000.0, 25_000_000.0],
    })
    handler.validate(df, "000001", Exchange.SSE)  # should not raise


def test_index_handler_validate_rejects_zero_price():
    """Zero or negative close must fail index validation."""
    from trading_os.data.schema import Exchange
    from trading_os.data.sources.asset_type_handler import IndexHandler
    from trading_os.data.exceptions import DataIntegrityError

    handler = IndexHandler()
    df = pd.DataFrame({
        "close": [0.0, 3200.0],
        "volume": [30_000_000.0, 30_000_000.0],
    })
    with pytest.raises(DataIntegrityError):
        handler.validate(df, "000001", Exchange.SSE)


def test_index_handler_validate_passes_for_low_historical_price():
    """Early 1990s index price (~100) must pass — lower bound is 0, not 100."""
    from trading_os.data.schema import Exchange
    from trading_os.data.sources.asset_type_handler import IndexHandler

    handler = IndexHandler()
    df = pd.DataFrame({
        "close": [99.98, 104.5],
        "volume": [126_000.0, 200_000.0],
    })
    handler.validate(df, "000001", Exchange.SSE)  # should not raise


# ── EquityHandler ─────────────────────────────────────────────────────────────

def test_equity_handler_validate_passes_for_normal_stock():
    from trading_os.data.schema import Exchange
    from trading_os.data.sources.asset_type_handler import EquityHandler

    handler = EquityHandler()
    df = pd.DataFrame({
        "close": [10.2, 10.3, 10.4],
        "volume": [1_000_000.0] * 3,
    })
    handler.validate(df, "600000", Exchange.SSE)  # should not raise


def test_equity_handler_validate_rejects_absurd_price():
    from trading_os.data.schema import Exchange
    from trading_os.data.sources.asset_type_handler import EquityHandler
    from trading_os.data.exceptions import DataIntegrityError

    handler = EquityHandler()
    df = pd.DataFrame({
        "close": [999999.0],  # 超出 10000 上限
        "volume": [1_000_000.0],
    })
    with pytest.raises(DataIntegrityError):
        handler.validate(df, "600000", Exchange.SSE)


# ── EtfHandler stub ───────────────────────────────────────────────────────────

def test_etf_handler_raises_not_implemented():
    from trading_os.data.schema import Exchange, Adjustment
    from trading_os.data.sources.asset_type_handler import EtfHandler

    handler = EtfHandler()
    with pytest.raises(NotImplementedError):
        handler.fetch("510300", Exchange.SSE, start=None, end=None, adjustment=Adjustment.QFQ)

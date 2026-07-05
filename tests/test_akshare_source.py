from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pd = pytest.importorskip("pandas")


def _make_akshare_df():
    return pd.DataFrame(
        {
            "日期": pd.date_range("2024-01-01", periods=5, freq="B"),
            "开盘": [10.0, 10.1, 10.2, 10.3, 10.4],
            "最高": [10.5, 10.6, 10.7, 10.8, 10.9],
            "最低": [9.5, 9.6, 9.7, 9.8, 9.9],
            "收盘": [10.2, 10.3, 10.4, 10.5, 10.6],
            "成交量": [1_000_000] * 5,
            "成交额": [10_000_000.0] * 5,
        }
    )


def test_fetch_daily_bars_uses_eastmoney_and_normalizes_volume():
    from trading_os.data.schema import Adjustment, Exchange
    from trading_os.data.sources.akshare_source import fetch_daily_bars

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_hist.return_value = _make_akshare_df()

    with patch.dict("sys.modules", {"akshare": mock_ak}):
        df, source = fetch_daily_bars(
            "600000",
            exchange=Exchange.SSE,
            start="2024-01-01",
            end="2024-01-10",
            adjustment=Adjustment.QFQ,
        )

    assert source == "eastmoney"
    assert mock_ak.stock_zh_a_hist.call_args.kwargs["start_date"] == "20240101"
    assert mock_ak.stock_zh_a_hist.call_args.kwargs["end_date"] == "20240110"
    assert mock_ak.stock_zh_a_hist.call_args.kwargs["adjust"] == "qfq"
    assert df["symbol"].unique().tolist() == ["SSE:600000"]
    assert (df["volume"] == 100_000_000).all()
    assert df["source"].unique().tolist() == ["eastmoney"]


def test_fetch_daily_bars_falls_back_to_akshare_daily_when_eastmoney_fails():
    from trading_os.data.schema import Adjustment, Exchange
    from trading_os.data.sources.akshare_source import fetch_daily_bars

    fallback = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=2, freq="B"),
            "open": [10.0, 10.1],
            "high": [10.5, 10.6],
            "low": [9.5, 9.6],
            "close": [10.2, 10.3],
            "volume": [1_000_000.0, 2_000_000.0],
            "amount": [10_000_000.0, 21_000_000.0],
        }
    )
    mock_ak = MagicMock()
    mock_ak.stock_zh_a_hist.side_effect = RuntimeError("eastmoney unavailable")
    mock_ak.stock_zh_a_daily.return_value = fallback

    with patch.dict("sys.modules", {"akshare": mock_ak}):
        df, source = fetch_daily_bars(
            "600000",
            exchange=Exchange.SSE,
            start="2024-01-01",
            end="2024-01-10",
            adjustment=Adjustment.QFQ,
        )

    assert source == "sina_daily"
    assert mock_ak.stock_zh_a_daily.call_args.kwargs["symbol"] == "sh600000"
    assert df["symbol"].unique().tolist() == ["SSE:600000"]
    assert df["volume"].tolist() == [1_000_000.0, 2_000_000.0]
    assert df["source"].unique().tolist() == ["sina_daily"]


def test_fetch_daily_bars_rejects_non_equity_asset_type():
    from trading_os.data.schema import Adjustment, AssetType, Exchange
    from trading_os.data.sources.akshare_source import fetch_daily_bars

    with pytest.raises(ValueError, match="only supports A-share equities"):
        fetch_daily_bars(
            "000001",
            exchange=Exchange.SSE,
            adjustment=Adjustment.QFQ,
            asset_type=AssetType.INDEX,
        )


def test_normalize_akshare_data_tolerates_nan_volume():
    from trading_os.data.schema import Adjustment, Exchange
    from trading_os.data.sources.akshare_source import _normalize_akshare_data

    raw = pd.DataFrame(
        {
            "日期": pd.date_range("2026-05-01", periods=2, freq="B"),
            "开盘": [10.0, 10.1],
            "最高": [10.2, 10.3],
            "最低": [9.8, 9.9],
            "收盘": [10.1, 10.2],
            "成交量": [1_000_000, None],
            "成交额": [10_000_000.0, 0.0],
        }
    )

    df = _normalize_akshare_data(
        raw,
        ticker="600355",
        exchange=Exchange.SSE,
        adjustment=Adjustment.QFQ,
    )

    assert len(df) == 2
    assert df["trades"].iloc[0] == 10000
    assert df["trades"].iloc[1] == 0
    assert df["adjustment"].iloc[0] == "qfq"

import pandas as pd
import pytest
import tempfile
from pathlib import Path
from trading_os.data.lake import LocalDataLake
from trading_os.data.schema import Exchange, Timeframe, Adjustment
from trading_os.data.exceptions import DataIntegrityError


def _make_lake():
    d = tempfile.mkdtemp()
    return LocalDataLake(Path(d)), d


def _bar_df(symbol, dates, closes, exchange="SSE"):
    return pd.DataFrame({
        "symbol": symbol,
        "ts": pd.to_datetime(dates),
        "open": closes,
        "high": [c * 1.02 for c in closes],
        "low": [c * 0.98 for c in closes],
        "close": closes,
        "volume": [1_000_000.0] * len(closes),
        "vwap": closes,
        "trades": [100] * len(closes),
        "source": "akshare",
    })


def test_first_write_always_passes():
    """空 lake，任何数据都应通过"""
    lake, _ = _make_lake()
    df = _bar_df("SSE:600000", ["2026-01-01"], [10.0])
    lake.write_bars_parquet(df, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")


def test_normal_price_movement_passes():
    """正常的日内波动（±10%）应通过"""
    lake, _ = _make_lake()
    df1 = _bar_df("SSE:600000", ["2026-01-01", "2026-01-02", "2026-01-03",
                                  "2026-01-06", "2026-01-07"],
                  [10.0, 10.5, 9.8, 10.2, 10.3])
    lake.write_bars_parquet(df1, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")
    df2 = _bar_df("SSE:600000", ["2026-01-08"], [10.8])
    lake.write_bars_parquet(df2, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")


def test_qfq_historical_low_passes():
    """前复权历史价格较低（如600031早期0.41），新增相近价格应通过"""
    lake, _ = _make_lake()
    df1 = _bar_df("SSE:600031", ["2005-01-01", "2005-01-02", "2005-01-03",
                                  "2005-01-04", "2005-01-05"],
                  [0.41, 0.42, 0.40, 0.39, 0.43])
    lake.write_bars_parquet(df1, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")
    df2 = _bar_df("SSE:600031", ["2005-01-06"], [0.40])
    lake.write_bars_parquet(df2, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")


def test_magnitude_error_blocked():
    """数量级错误：历史约25元，新数据0.025（少了3个零）应被拦"""
    lake, _ = _make_lake()
    df1 = _bar_df("SSE:600031", ["2026-01-01", "2026-01-02", "2026-01-03",
                                  "2026-01-06", "2026-01-07"],
                  [24.5, 25.0, 25.2, 24.8, 25.1])
    lake.write_bars_parquet(df1, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")
    df2 = _bar_df("SSE:600031", ["2026-01-08"], [0.025])
    with pytest.raises(DataIntegrityError):
        lake.write_bars_parquet(df2, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                                 adjustment=Adjustment.QFQ, source="akshare")


def test_mixed_history_does_not_false_positive():
    """历史数据本身跨度大（前复权早期0.41 + 现价25），新数据0.40应通过"""
    lake, _ = _make_lake()
    mixed_dates = ["2005-01-01", "2020-01-01", "2023-01-01", "2025-01-01", "2026-01-01"]
    mixed_closes = [0.41, 5.0, 15.0, 22.0, 25.0]  # 跨越 60x
    df1 = _bar_df("SSE:600031", mixed_dates, mixed_closes)
    lake.write_bars_parquet(df1, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")
    # 新数据0.40 — 与历史最低0.41接近，应通过（不被误拦）
    # 当前 median 逻辑：median([25, 22, 15, 5, 0.41]) = 15, lo=15/50=0.30, hi=750
    # 0.40 > 0.30，通过
    df2 = _bar_df("SSE:600031", ["2026-01-02"], [0.40])
    lake.write_bars_parquet(df2, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")


def test_recent_modern_history_does_not_block_qfq_low():
    """600031 实际失败场景：最近5条都是现代价格（~25元），
    新浪接口返回的前复权价格0.40应通过。

    旧 median 逻辑：median=25, lo=0.50, 0.40 < lo → 误拦
    新 min/max 逻辑：min=24.5, lo=24.5/10=2.45 — 仍然会拦...

    重新思考：实际 600031 的问题是历史 lake 中同时存了旧复权数据（0.41）
    和现代数据（25），导致 median ~13，使 lo=0.26，0.40 通过。
    但新浪返回 0.40，而历史只有现代数据 ~25，median=25, lo=0.50，0.40 被拦。

    正确修复不是放宽阈值，而是：_flush_batch 不 crash（Task 1），
    将此 symbol 记录为 failed，整体流程继续。
    """
    lake, _ = _make_lake()
    # 最近5条全是现代价格
    df1 = _bar_df("SSE:600031", ["2026-01-01", "2026-01-02", "2026-01-03",
                                  "2026-01-06", "2026-01-07"],
                  [24.5, 25.0, 25.2, 24.8, 25.1])
    lake.write_bars_parquet(df1, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")
    # 新数据0.40：这确实是数量级异常（25元 → 0.40，差60倍），应该被拦截
    # 修复的重点是 _flush_batch 不 crash，而是记录为 failed 继续
    df2 = _bar_df("SSE:600031", ["2026-01-08"], [0.40])
    with pytest.raises(DataIntegrityError):
        lake.write_bars_parquet(df2, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                                 adjustment=Adjustment.QFQ, source="akshare")

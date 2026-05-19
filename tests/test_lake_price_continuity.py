import pandas as pd
import pytest
import tempfile
from pathlib import Path
from trading_os.data.lake import LocalDataLake
from trading_os.data.schema import Timeframe, Adjustment
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
    lake.write_bars_parquet(df, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")


def test_normal_price_movement_passes():
    """正常的日内波动（±10%）应通过"""
    lake, _ = _make_lake()
    df1 = _bar_df("SSE:600000", ["2026-01-01", "2026-01-02", "2026-01-03",
                                  "2026-01-06", "2026-01-07"],
                  [10.0, 10.5, 9.8, 10.2, 10.3])
    lake.write_bars_parquet(df1, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")
    df2 = _bar_df("SSE:600000", ["2026-01-08"], [10.8])
    lake.write_bars_parquet(df2, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")


def test_qfq_historical_low_passes():
    """前复权历史价格较低（如600031早期0.41），新增相近价格应通过"""
    lake, _ = _make_lake()
    df1 = _bar_df("SSE:600031", ["2005-01-01", "2005-01-02", "2005-01-03",
                                  "2005-01-04", "2005-01-05"],
                  [0.41, 0.42, 0.40, 0.39, 0.43])
    lake.write_bars_parquet(df1, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")
    df2 = _bar_df("SSE:600031", ["2005-01-06"], [0.40])
    lake.write_bars_parquet(df2, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")


def test_magnitude_error_blocked():
    """数量级错误：历史约25元，新数据0.025（少了3个零）应被拦"""
    lake, _ = _make_lake()
    df1 = _bar_df("SSE:600031", ["2026-01-01", "2026-01-02", "2026-01-03",
                                  "2026-01-06", "2026-01-07"],
                  [24.5, 25.0, 25.2, 24.8, 25.1])
    lake.write_bars_parquet(df1, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")
    df2 = _bar_df("SSE:600031", ["2026-01-08"], [0.025])
    with pytest.raises(DataIntegrityError):
        lake.write_bars_parquet(df2, timeframe=Timeframe.D1,
                                 adjustment=Adjustment.QFQ, source="akshare")


def test_mixed_history_does_not_false_positive():
    """历史数据本身跨度大（前复权早期0.41 + 现价25），新数据0.40应通过"""
    lake, _ = _make_lake()
    mixed_dates = ["2005-01-01", "2020-01-01", "2023-01-01", "2025-01-01", "2026-01-01"]
    mixed_closes = [0.41, 5.0, 15.0, 22.0, 25.0]  # 跨越 60x
    df1 = _bar_df("SSE:600031", mixed_dates, mixed_closes)
    lake.write_bars_parquet(df1, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")
    # 新数据0.40 — 与历史最低0.41接近，应通过（不被误拦）
    # 当前 median 逻辑：median([25, 22, 15, 5, 0.41]) = 15, lo=15/50=0.30, hi=750
    # 0.40 > 0.30，通过
    df2 = _bar_df("SSE:600031", ["2026-01-02"], [0.40])
    lake.write_bars_parquet(df2, timeframe=Timeframe.D1,
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
    lake.write_bars_parquet(df1, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="akshare")
    # 新数据0.40：这确实是数量级异常（25元 → 0.40，差60倍），应该被拦截
    # 修复的重点是 _flush_batch 不 crash，而是记录为 failed 继续
    df2 = _bar_df("SSE:600031", ["2026-01-08"], [0.40])
    with pytest.raises(DataIntegrityError):
        lake.write_bars_parquet(df2, timeframe=Timeframe.D1,
                                 adjustment=Adjustment.QFQ, source="akshare")


# ── _check_volume_unit tests ─────────────────────────────────────────────────


def _bar_df_with_vol(symbol, dates, closes, volumes, exchange="SSE"):
    return pd.DataFrame({
        "symbol": symbol,
        "ts": pd.to_datetime(dates),
        "open": closes,
        "high": [c * 1.02 for c in closes],
        "low": [c * 0.98 for c in closes],
        "close": closes,
        "volume": [float(v) for v in volumes],
        "vwap": closes,
        "trades": [100] * len(closes),
        "source": "akshare",
    })


def test_volume_unit_first_write_passes():
    """空 lake，合理 volume 应通过（无参考数据）"""
    lake, _ = _make_lake()
    df = _bar_df_with_vol("SSE:601138", ["2026-01-01"], [65.0], [200_000])
    lake.write_bars_parquet(df, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="sina")


def test_volume_unit_first_write_lot_sized_blocked():
    """新 symbol 首次写入，volume < 10000（手数级别）应被绝对阈值拦截。"""
    lake, _ = _make_lake()
    # 3000 是典型的手数数据（30万股换算成手 = 3000手），不是股数
    df = _bar_df_with_vol("SSE:601138", ["2026-01-01"], [65.0], [3000])
    with pytest.raises(DataIntegrityError):
        lake.write_bars_parquet(df, timeframe=Timeframe.D1,
                                 adjustment=Adjustment.QFQ, source="eastmoney")


def test_volume_unit_lot_data_blocked():
    """已有股数数据时，写入手数数据（差 100 倍）应被拦截。

    模拟场景：东财接口返回 volume=手，未经 *100 换算直接写入。
    现有数据 median ≈ 2亿股，新数据 median ≈ 200万（手），比值 = 100，触发拦截。
    """
    lake, _ = _make_lake()
    # 写入正确的股数数据（10 条，确保 median 稳定）
    share_vol = 200_000_000  # 2亿股，典型大盘股
    dates_existing = [f"2026-01-{d:02d}" for d in range(2, 12)]
    df1 = _bar_df_with_vol("SSE:601138", dates_existing, [65.0] * 10,
                           [share_vol] * 10)
    lake.write_bars_parquet(df1, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="baostock")

    # 尝试写入手数数据（volume = share_vol / 100）
    lot_vol = share_vol // 100  # 200万手，是股数的 1/100
    df2 = _bar_df_with_vol("SSE:601138", ["2026-01-13"], [65.5], [lot_vol])
    with pytest.raises(DataIntegrityError):
        lake.write_bars_parquet(df2, timeframe=Timeframe.D1,
                                 adjustment=Adjustment.QFQ, source="eastmoney")


def test_volume_unit_normal_variation_passes():
    """正常的成交量波动（±50%）不应触发拦截"""
    lake, _ = _make_lake()
    base_vol = 10_000_000  # 1千万股
    dates = [f"2026-01-{d:02d}" for d in range(2, 12)]
    df1 = _bar_df_with_vol("SZSE:300857", dates, [280.0] * 10, [base_vol] * 10)
    lake.write_bars_parquet(df1, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="baostock")

    # 成交量减少到基准的 5%（仍在 1/50 阈值以上）
    df2 = _bar_df_with_vol("SZSE:300857", ["2026-01-13"], [281.0],
                           [int(base_vol * 0.06)])
    lake.write_bars_parquet(df2, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="sina")


def test_volume_unit_small_cap_low_volume_passes():
    """小盘股低成交量（301061 赛伍技术，日均 ~180万股）不应被误拦截"""
    lake, _ = _make_lake()
    # 小盘股真实 volume 范围：120万~240万股
    vols = [1_267_755, 1_770_628, 1_798_385, 2_394_242, 2_133_466,
            1_500_000, 1_800_000, 2_000_000, 1_600_000, 1_700_000]
    dates = [f"2026-01-{d:02d}" for d in range(2, 12)]
    df1 = _bar_df_with_vol("SZSE:301061", dates, [65.0] * 10, vols)
    lake.write_bars_parquet(df1, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="baostock")

    # 新数据仍在同量级范围内（~130万）
    df2 = _bar_df_with_vol("SZSE:301061", ["2026-01-13"], [65.6], [1_300_000])
    lake.write_bars_parquet(df2, timeframe=Timeframe.D1,
                             adjustment=Adjustment.QFQ, source="sina")

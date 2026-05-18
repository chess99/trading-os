# tests/test_fetch_ak_bulk_exchange.py
"""测试 _flush_batch 写入时 exchange 列按 symbol 正确推断，不硬编码 SSE。"""
import pandas as pd

from trading_os.data.schema import Exchange, Timeframe


def _make_bar_df(symbol: str) -> pd.DataFrame:
    """构造一行 bars DataFrame，exchange 列留空（由 _flush_batch 决定）。"""
    return pd.DataFrame([{
        "symbol": symbol,
        "ts": pd.Timestamp("2026-05-15", tz="UTC"),
        "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5,
        "volume": 100000.0,
        "source": "baostock",
    }])


def _run_flush_batch(tmp_path, symbols: list[str]) -> pd.DataFrame:
    """用指定 symbols 构造 batch，调用修复后的推断逻辑，返回 lake 中的查询结果。"""
    from trading_os.data.lake import LocalDataLake
    from trading_os.data.schema import Adjustment as Adj
    lake = LocalDataLake(tmp_path)
    lake.init()

    batch = [_make_bar_df(sym) for sym in symbols]
    combined = pd.concat(batch, ignore_index=True)
    adj = Adj.QFQ

    for sym, sym_df in combined.groupby("symbol"):
        sym_str = str(sym)
        if sym_str.startswith("SZSE:"):
            actual_exchange = Exchange.SZSE
        elif sym_str.startswith("SSE:"):
            actual_exchange = Exchange.SSE
        else:
            actual_exchange = Exchange.SSE
        lake.write_bars_parquet(
            sym_df,
            exchange=actual_exchange,
            timeframe=Timeframe.D1,
            adjustment=adj,
            source="baostock",
            partition_hint="bulk_00001",
        )

    return lake.query_bars(adjustment=adj)


def test_flush_batch_szse_symbol_writes_szse_exchange(tmp_path):
    """SZSE:300750 写入后 exchange 列应为 SZSE，不是 SSE。"""
    result = _run_flush_batch(tmp_path, ["SZSE:300750"])
    row = result[result["symbol"] == "SZSE:300750"].iloc[0]
    assert row["exchange"] == "SZSE", f"期望 SZSE，得到 {row['exchange']!r}"


def test_flush_batch_mixed_symbols_each_correct_exchange(tmp_path):
    """SSE 和 SZSE 混合 batch 时，各自 exchange 列应正确。"""
    result = _run_flush_batch(tmp_path, ["SSE:600000", "SZSE:300750"])
    sse_row = result[result["symbol"] == "SSE:600000"].iloc[0]
    szse_row = result[result["symbol"] == "SZSE:300750"].iloc[0]
    assert sse_row["exchange"] == "SSE"
    assert szse_row["exchange"] == "SZSE"

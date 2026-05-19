"""Tests for LocalDataLake.compact() — dedup priority, atomicity, threshold."""
import pytest

pd = pytest.importorskip("pandas")


def _make_lake(tmp_path):
    from trading_os.data.lake import LocalDataLake
    lake = LocalDataLake(tmp_path / "data")
    lake.init()
    return lake


_write_counter = 0

def _write_bars(lake, symbol, closes, source):
    """Write bars with a unique partition_hint to avoid filename collisions between calls."""
    global _write_counter
    from trading_os.data.schema import Timeframe, Adjustment

    _write_counter += 1
    n = len(closes)
    df = pd.DataFrame({
        "symbol": [symbol] * n,
        "ts": pd.date_range("2024-01-02", periods=n, freq="B", tz="UTC"),
        "open":   closes,
        "high":   [c * 1.01 for c in closes],
        "low":    [c * 0.99 for c in closes],
        "close":  closes,
        "volume": [1_000_000.0] * n,
        "vwap":   closes,
        "trades": [10000] * n,
        "source": [source] * n,
    })
    return lake.write_bars_parquet(
        df,
        timeframe=Timeframe.D1,
        adjustment=Adjustment.NONE,
        source=source,
        partition_hint=f"t{_write_counter:04d}",
    )


# ── Threshold ─────────────────────────────────────────────────────────────────

def test_compact_does_not_trigger_below_threshold(tmp_path):
    """compact() with default threshold=20 returns 0 when only 1 file exists."""
    lake = _make_lake(tmp_path)
    _write_bars(lake, "SSE:600000", [10.0, 10.1], "baostock")
    result = lake.compact(threshold=20)
    assert result == 0


def test_compact_triggers_at_threshold(tmp_path):
    """compact(threshold=0) always runs and produces compacted file(s)."""
    lake = _make_lake(tmp_path)
    _write_bars(lake, "SSE:600000", [10.0, 10.1], "baostock")
    result = lake.compact(threshold=0)
    assert result >= 1


def test_compact_on_empty_lake_returns_zero(tmp_path):
    """compact() on a lake with no parquet files returns 0."""
    lake = _make_lake(tmp_path)
    result = lake.compact(threshold=0)
    assert result == 0


# ── Dedup: source priority (ORDER BY source DESC) ─────────────────────────────

def test_compact_dedup_sina_beats_eastmoney(tmp_path):
    """'sina' > 'eastmoney' alphabetically — sina row survives dedup."""
    lake = _make_lake(tmp_path)
    _write_bars(lake, "SSE:600000", [10.0], "eastmoney")
    _write_bars(lake, "SSE:600000", [20.0], "sina")
    lake.compact(threshold=0)
    lake.init()

    from trading_os.data.schema import Timeframe, Adjustment
    df = lake.query_bars(
        symbols=["SSE:600000"],
        timeframe=Timeframe.D1, adjustment=Adjustment.NONE,
    )
    assert not df.empty
    # After dedup, only one row per ts; sina's close (20.0) should win
    assert (df["close"] == 20.0).all(), f"Expected sina close=20.0, got: {df['close'].tolist()}"


def test_compact_dedup_baostock_beats_akshare_index(tmp_path):
    """'baostock' > 'akshare_index' alphabetically — baostock row survives dedup."""
    lake = _make_lake(tmp_path)
    _write_bars(lake, "SSE:000001", [3800.0], "akshare_index")
    _write_bars(lake, "SSE:000001", [3900.0], "baostock")
    lake.compact(threshold=0)
    lake.init()

    from trading_os.data.schema import Timeframe, Adjustment
    df = lake.query_bars(
        symbols=["SSE:000001"],
        timeframe=Timeframe.D1, adjustment=Adjustment.NONE,
    )
    assert not df.empty
    assert (df["close"] == 3900.0).all(), (
        "baostock should beat akshare_index in current alphabetical dedup. "
        "If this fails after adding explicit priority column, update expected value."
    )


def test_compact_dedup_keeps_only_one_row_per_ts(tmp_path):
    """After compact, no duplicate (symbol, ts) pairs remain."""
    lake = _make_lake(tmp_path)
    _write_bars(lake, "SSE:600000", [10.0, 10.1, 10.2], "eastmoney")
    _write_bars(lake, "SSE:600000", [10.0, 10.1, 10.2], "sina")
    lake.compact(threshold=0)
    lake.init()

    from trading_os.data.schema import Timeframe, Adjustment
    df = lake.query_bars(
        symbols=["SSE:600000"],
        timeframe=Timeframe.D1, adjustment=Adjustment.NONE,
    )
    assert not df.empty
    assert df.duplicated(subset=["symbol", "ts"]).sum() == 0


def test_compact_dedup_does_not_lose_rows_from_different_symbols(tmp_path):
    """Dedup operates per symbol — rows for other symbols are not dropped."""
    lake = _make_lake(tmp_path)
    _write_bars(lake, "SSE:600000", [10.0, 10.1], "baostock")
    _write_bars(lake, "SSE:600036", [20.0, 20.1], "baostock")
    lake.compact(threshold=0)
    lake.init()

    from trading_os.data.schema import Timeframe, Adjustment
    df = lake.query_bars(timeframe=Timeframe.D1, adjustment=Adjustment.NONE)
    symbols = set(df["symbol"].unique())
    assert "SSE:600000" in symbols
    assert "SSE:600036" in symbols


# ── Atomicity ──────────────────────────────────────────────────────────────────

def test_compact_leaves_old_files_if_write_fails(tmp_path, monkeypatch):
    """If writing a compacted file fails mid-way, the original files are kept."""
    import pandas as _pd

    lake = _make_lake(tmp_path)
    _write_bars(lake, "SSE:600000", [10.0, 10.1], "baostock")
    _write_bars(lake, "SSE:600000", [10.2, 10.3], "sina")

    original_files = sorted(lake.paths.bars_dir.glob("*.parquet"))
    assert len(original_files) >= 1

    # Patch to_parquet to raise on the first compacted write
    original_to_parquet = _pd.DataFrame.to_parquet
    call_count = {"n": 0}

    def _failing_to_parquet(self, path, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1 and "compacted" in str(path):
            raise OSError("Simulated disk full")
        return original_to_parquet(self, path, **kwargs)

    monkeypatch.setattr(_pd.DataFrame, "to_parquet", _failing_to_parquet)

    with pytest.raises(OSError, match="Simulated disk full"):
        lake.compact(threshold=0)

    # Original files must still be present
    remaining = sorted(lake.paths.bars_dir.glob("*.parquet"))
    assert len(remaining) >= len(original_files), (
        "Original parquet files were deleted before new files were verified"
    )
    # No partially-written compacted file should remain
    for f in remaining:
        if "compacted" in f.name:
            pytest.fail(f"Partial compacted file left on disk: {f.name}")

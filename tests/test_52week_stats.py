"""Tests for get_52week_stats — data freshness fields added in fix(workflow)."""
import pathlib
import pytest

pd = pytest.importorskip("pandas")


def _make_lake_with_bars(data_path: pathlib.Path, symbol: str, closes: list, adj: str = "qfq"):
    from trading_os.data.lake import LocalDataLake
    from trading_os.data.schema import Adjustment, Exchange, Timeframe

    lake = LocalDataLake(data_path)
    n = len(closes)
    df = pd.DataFrame({
        "symbol": [symbol] * n,
        "exchange": [symbol.split(":")[0]] * n,
        "timeframe": [Timeframe.D1.value] * n,
        "adjustment": [adj] * n,
        "ts": pd.date_range("2025-01-02", periods=n, freq="B", tz="UTC"),
        "open": closes, "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes], "close": closes,
        "volume": [1_000_000.0] * n, "vwap": closes,
        "trades": [1000] * n, "source": ["synthetic"] * n,
    })
    lake.write_bars_parquet(
        df,
        exchange=Exchange(symbol.split(":")[0]),
        timeframe=Timeframe.D1,
        adjustment=Adjustment(adj),
        source="synthetic",
    )
    lake.init()
    return lake


def test_52week_stats_result_dict_has_latest_date_on_normal_path(tmp_path, monkeypatch):
    """latest_date should be present and non-None when data exists."""
    import trading_os.data.sources.fundamental_source as fs_mod

    data_path = tmp_path / "data"
    lake = _make_lake_with_bars(data_path, "SSE:600000", [10.0, 10.5, 11.0])

    # Patch repo_root inside the module's own namespace (lazy import path)
    monkeypatch.setattr(fs_mod, "get_52week_stats",
                        fs_mod.get_52week_stats, raising=False)
    # The function does LocalDataLake(repo_root() / "data") internally,
    # so patch repo_root at the source module level.
    import trading_os.paths as _paths_mod
    monkeypatch.setattr(_paths_mod, "repo_root", lambda: tmp_path)

    result = fs_mod.get_52week_stats("SSE:600000")

    assert result["error"] is None, f"Unexpected error: {result['error']}"
    assert "latest_date" in result, "latest_date key must always be present"
    assert result["latest_date"] is not None
    # Must be a valid ISO date string
    from datetime import date
    date.fromisoformat(result["latest_date"])


def test_52week_stats_result_dict_has_latest_date_on_error_path():
    """latest_date must be in the result dict even when no data is found (error path)."""
    from trading_os.data.sources.fundamental_source import get_52week_stats

    result = get_52week_stats("SSE:000000_nonexistent")

    assert "latest_date" in result, "latest_date key must be present on error path"
    assert result["latest_date"] is None, "latest_date should be None when no data"


def test_52week_stats_summary_text_starts_with_data_cutoff(tmp_path, monkeypatch):
    """summary_text line 2 must be '  数据截止: YYYY-MM-DD'."""
    import trading_os.data.sources.fundamental_source as fs_mod
    import trading_os.paths as _paths_mod

    data_path = tmp_path / "data"
    _make_lake_with_bars(data_path, "SSE:600000", [10.0, 10.5, 11.0])
    monkeypatch.setattr(_paths_mod, "repo_root", lambda: tmp_path)

    result = fs_mod.get_52week_stats("SSE:600000")

    assert result["error"] is None, f"Unexpected error: {result['error']}"
    lines = result["summary_text"].splitlines()
    # Line 0: 【52周统计】SSE:600000
    # Line 1: 数据截止: YYYY-MM-DD
    assert len(lines) >= 2
    assert lines[1].strip().startswith("数据截止:"), (
        f"Expected '数据截止:' on line 2, got: {lines[1]!r}"
    )

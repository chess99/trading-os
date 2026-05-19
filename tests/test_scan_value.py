"""Tests for scan/value_scanner.py."""
from datetime import date
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from trading_os.scan.value_scanner import _price_percentile, scan_value


# ── _price_percentile ─────────────────────────────────────────────────────

def test_price_percentile_at_historical_low():
    import pandas as pd
    close = pd.Series([100.0, 110.0, 120.0, 130.0, 140.0])
    pct, _ = _price_percentile(close, current_price=95.0)
    assert pct == 0.0  # 低于所有历史价格


def test_price_percentile_at_historical_high():
    import pandas as pd
    close = pd.Series([100.0, 110.0, 120.0, 130.0, 140.0])
    pct, _ = _price_percentile(close, current_price=150.0)
    assert pct == 1.0  # 高于所有历史价格


def test_price_percentile_middle():
    import pandas as pd
    close = pd.Series([100.0, 110.0, 120.0, 130.0, 140.0])
    pct, _ = _price_percentile(close, current_price=115.0)
    # 2 out of 5 values < 115 → 0.4
    assert pct == pytest.approx(0.4)


def test_price_percentile_empty_series():
    import pandas as pd
    pct, limited = _price_percentile(pd.Series([], dtype=float), current_price=100.0)
    assert pct == 1.0  # 空序列返回最高分位（不通过筛选）
    assert limited is True


def test_price_percentile_limited_data_flag():
    import pandas as pd
    # 少于 3 年数据（252 * 3 = 756 天）
    close = pd.Series([100.0] * 200)
    _, limited = _price_percentile(close, current_price=100.0)
    assert limited is True


def test_price_percentile_full_data_flag():
    import pandas as pd
    # 超过 3 年数据
    close = pd.Series([100.0] * 800)
    _, limited = _price_percentile(close, current_price=100.0)
    assert limited is False


def _make_value_bars() -> "pd.DataFrame":
    return pd.DataFrame(
        {
            "symbol": ["SSE:600000"] * 800,
            "ts": pd.date_range("2021-01-01", periods=800, freq="B", tz="UTC"),
            "close": [100.0] * 799 + [90.0],
        }
    )


def test_scan_value_live_marks_result_non_replayable(monkeypatch, tmp_path):
    snapshot = pd.DataFrame([{"代码": "600000", "总市值": 80e8, "市净率": 1.5}])
    monkeypatch.setitem(__import__("sys").modules, "akshare", type("Ak", (), {
        "stock_zh_a_spot_em": staticmethod(lambda: snapshot)
    }))
    monkeypatch.setattr(
        "trading_os.scan.common.load_fundamental",
        lambda data_root, sym: {"profitability": [{"roe": 0.2}]},
    )

    result = scan_value(
        ["SSE:600000"],
        _make_value_bars(),
        scan_date=date(2024, 3, 15),
        data_root=tmp_path,
        mode="live",
    )

    assert result["metadata"]["mode"] == "live"
    assert result["metadata"]["replayable"] is False
    assert result["candidates"][0]["pe_pb_source"] == "realtime_snapshot"


def test_scan_value_historical_without_snapshot_degrades_to_insufficient_data(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "trading_os.scan.common.load_fundamental",
        lambda data_root, sym: {"profitability": [{"roe": 0.2}]},
    )

    result = scan_value(
        ["SSE:600000"],
        _make_value_bars(),
        scan_date=date(2024, 3, 15),
        data_root=tmp_path,
        mode="historical",
    )

    assert result["candidates"] == []
    assert result["_stats"]["insufficient_data"] == 1
    assert result["metadata"]["mode"] == "historical"
    assert result["metadata"]["replayable"] is True


def test_scan_value_historical_uses_snapshot_file(monkeypatch, tmp_path):
    snapshot_dir = tmp_path / "valuation_snapshots"
    snapshot_dir.mkdir()
    snapshot_path = snapshot_dir / "2024-03-15.json"
    snapshot_path.write_text(
        '[{"代码":"600000","总市值":8000000000.0,"市净率":1.5}]',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "trading_os.scan.common.load_fundamental",
        lambda data_root, sym: {"profitability": [{"roe": 0.2}]},
    )

    result = scan_value(
        ["SSE:600000"],
        _make_value_bars(),
        scan_date=date(2024, 3, 15),
        data_root=tmp_path,
        mode="historical",
    )

    assert len(result["candidates"]) == 1
    assert result["metadata"]["valuation_data_as_of"] == "2024-03-15"
    assert result["candidates"][0]["pe_pb_source"] == "historical_snapshot"

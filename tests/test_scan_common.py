"""Tests for scan/common.py."""
import json
import tempfile
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from trading_os.scan.common import (
    filter_by_turnover,
    fundamental_path,
    load_fundamental,
    to_canonical,
    write_scan_output,
)


# ── to_canonical ──────────────────────────────────────────────────────────

def test_to_canonical_sse():
    assert to_canonical("SSE", "600000") == "SSE:600000"


def test_to_canonical_szse():
    assert to_canonical("SZSE", "000001") == "SZSE:000001"


def test_to_canonical_lowercase_exchange():
    assert to_canonical("sse", "600519") == "SSE:600519"


# ── fundamental_path ──────────────────────────────────────────────────────

def test_fundamental_path_no_colon():
    root = Path("/tmp/fake")
    p = fundamental_path(root, "SSE:600000")
    assert ":" not in p.name
    assert p.name == "SSE_600000.json"


# ── load_fundamental ──────────────────────────────────────────────────────

def test_load_fundamental_exists():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "fundamental").mkdir()
        path = fundamental_path(root, "SSE:600519")
        path.write_text(json.dumps({"symbol": "SSE:600519", "roe": 0.28}), encoding="utf-8")

        result = load_fundamental(root, "SSE:600519")
        assert result is not None
        assert result["roe"] == 0.28


def test_load_fundamental_missing_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        result = load_fundamental(Path(tmp), "SSE:999999")
        assert result is None  # 不抛异常


# ── filter_by_turnover ────────────────────────────────────────────────────

def _make_bars(symbols_prices_volumes: list[tuple]) -> "pd.DataFrame":
    """Helper: build a minimal bars DataFrame."""
    import pandas as pd
    rows = []
    for sym, price, volume in symbols_prices_volumes:
        for i in range(25):  # 25 days
            rows.append({"symbol": sym, "ts": f"2024-01-{i+1:02d}", "close": price, "volume": volume})
    return pd.DataFrame(rows)


def test_filter_by_turnover_all_pass():
    bars = _make_bars([("SSE:A", 10.0, 2_000_000), ("SSE:B", 20.0, 1_000_000)])
    passed, filtered = filter_by_turnover(["SSE:A", "SSE:B"], bars, min_amount=1e7)
    assert set(passed) == {"SSE:A", "SSE:B"}
    assert filtered == 0


def test_filter_by_turnover_all_fail():
    bars = _make_bars([("SSE:A", 1.0, 100), ("SSE:B", 1.0, 100)])
    passed, filtered = filter_by_turnover(["SSE:A", "SSE:B"], bars, min_amount=1e7)
    assert passed == []
    assert filtered == 2


def test_filter_by_turnover_partial():
    bars = _make_bars([("SSE:A", 10.0, 2_000_000), ("SSE:B", 1.0, 100)])
    passed, filtered = filter_by_turnover(["SSE:A", "SSE:B"], bars, min_amount=1e7)
    assert passed == ["SSE:A"]
    assert filtered == 1


def test_filter_by_turnover_empty_bars():
    import pandas as pd
    passed, filtered = filter_by_turnover(["SSE:A"], pd.DataFrame(), min_amount=1e7)
    assert passed == []
    assert filtered == 1


# ── write_scan_output ─────────────────────────────────────────────────────

def test_write_scan_output_empty_candidates():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scan" / "elder-20240315.json"
        write_scan_output({"candidates": [], "system": "elder"}, path)
        data = json.loads(path.read_text())
        assert data["candidates"] == []
        assert data["system"] == "elder"


def test_write_scan_output_creates_parent_dirs():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "deep" / "nested" / "output.json"
        write_scan_output({"candidates": []}, path)
        assert path.exists()

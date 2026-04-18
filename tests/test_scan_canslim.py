"""Tests for scan/canslim_scanner.py."""
import json
import tempfile
from datetime import date
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from trading_os.scan.canslim_scanner import (
    _annual_eps_continuous_growth,
    _eps_yoy_growth,
    scan_canslim,
)


# ── _eps_yoy_growth ───────────────────────────────────────────────────────

def test_eps_growth_normal():
    growth = _eps_yoy_growth(current_eps=1.5, prior_eps=1.0)
    assert growth == pytest.approx(0.5)


def test_eps_growth_prior_zero_returns_none():
    result = _eps_yoy_growth(current_eps=1.5, prior_eps=0.0)
    assert result is None


def test_eps_growth_prior_negative_returns_none():
    result = _eps_yoy_growth(current_eps=1.5, prior_eps=-0.5)
    assert result is None


def test_eps_growth_negative_growth():
    growth = _eps_yoy_growth(current_eps=0.5, prior_eps=1.0)
    assert growth == pytest.approx(-0.5)


# ── _annual_eps_continuous_growth ─────────────────────────────────────────

def test_annual_eps_continuous_3yr_pass():
    assert _annual_eps_continuous_growth([1.0, 1.5, 2.0, 2.5], years=3) is True


def test_annual_eps_continuous_3yr_fail_decline():
    assert _annual_eps_continuous_growth([1.0, 1.5, 1.2, 2.0], years=3) is False


def test_annual_eps_continuous_3yr_fail_loss():
    assert _annual_eps_continuous_growth([1.0, -0.5, 1.0, 1.5], years=3) is False


def test_annual_eps_continuous_insufficient_data():
    assert _annual_eps_continuous_growth([1.0, 1.5], years=3) is False


# ── scan_canslim integration ──────────────────────────────────────────────

def _make_fundamental(symbol: str, eps_growth: float = 0.30, roe: float = 0.20) -> dict:
    """Build a minimal fundamental JSON dict.

    quarterly_eps has 5 entries: indices [-5].eps = prior_year, [-1].eps = current.
    eps_growth = (current - prior) / prior
    """
    prior_eps = 1.0
    current_eps = prior_eps * (1 + eps_growth)
    return {
        "symbol": symbol,
        "per_share": {
            "quarterly_eps": [
                # 4 filler quarters before the "prior year same quarter"
                {"quarter": "2021Q1", "eps": 0.8},
                {"quarter": "2021Q2", "eps": 0.85},
                {"quarter": "2021Q3", "eps": 0.9},
                {"quarter": "2021Q4", "eps": 0.95},
                {"quarter": "2022Q1", "eps": prior_eps},   # index [-5]: prior year
                {"quarter": "2022Q2", "eps": 1.05},
                {"quarter": "2022Q3", "eps": 1.10},
                {"quarter": "2022Q4", "eps": 1.15},
                {"quarter": "2023Q1", "eps": current_eps}, # index [-1]: current
            ],
            "annual_eps": [
                {"year": "2020", "eps": 0.8},
                {"year": "2021", "eps": 1.0},
                {"year": "2022", "eps": 1.3},
                {"year": "2023", "eps": 1.7},
            ],
        },
        "profitability": {
            "roe": [{"year": "2023", "value": roe}],
        },
    }


def _write_fundamental(data_root: Path, symbol: str, data: dict) -> None:
    from trading_os.scan.common import fundamental_path
    path = fundamental_path(data_root, symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _make_bars(symbol: str, days: int = 260) -> "pd.DataFrame":
    import pandas as pd
    import numpy as np
    np.random.seed(0)
    prices = 100 * (1 + np.random.normal(0.001, 0.01, days)).cumprod()
    return pd.DataFrame({
        "symbol": symbol,
        "ts": pd.date_range("2023-01-01", periods=days, freq="B", tz="UTC"),
        "close": prices,
        "volume": [1_000_000.0] * days,
        "open": prices,
        "high": prices * 1.01,
        "low": prices * 0.99,
    })


def test_scan_canslim_no_fundamental_counted_as_insufficient():
    import pandas as pd
    with tempfile.TemporaryDirectory() as tmp:
        data_root = Path(tmp)
        bars = _make_bars("SSE:600000")
        result = scan_canslim(
            ["SSE:600000"], bars,
            scan_date=date(2024, 3, 15),
            data_root=data_root,
            top_n=30,
        )
        assert result["_stats"]["insufficient_data"] == 1
        assert result["candidates"] == []


def test_scan_canslim_passing_stock():
    import pandas as pd
    with tempfile.TemporaryDirectory() as tmp:
        data_root = Path(tmp)
        sym = "SSE:600000"
        _write_fundamental(data_root, sym, _make_fundamental(sym, eps_growth=0.35, roe=0.25))
        bars = _make_bars(sym, days=300)
        result = scan_canslim(
            [sym], bars,
            scan_date=date(2024, 3, 15),
            data_root=data_root,
            top_n=30,
        )
        # Should produce 1 candidate (all conditions pass)
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["signals"]["eps_growth_yoy"] > 0


def test_scan_canslim_low_eps_growth_filtered():
    import pandas as pd
    with tempfile.TemporaryDirectory() as tmp:
        data_root = Path(tmp)
        sym = "SSE:600000"
        # EPS growth of 5% < 18% threshold
        fund = _make_fundamental(sym, eps_growth=0.05, roe=0.25)
        _write_fundamental(data_root, sym, fund)
        bars = _make_bars(sym)
        result = scan_canslim(
            [sym], bars,
            scan_date=date(2024, 3, 15),
            data_root=data_root,
            top_n=30,
        )
        assert result["candidates"] == []
        assert result["_stats"]["no_signal"] == 1

"""Tests for scan/value_scanner.py."""
import pytest

pd = pytest.importorskip("pandas")

from trading_os.scan.value_scanner import _price_percentile


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

# AssetType 分派器体系 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 `schema.py` 中已有但从未使用的 `AssetType` 抽象，使每种资产类型（股票/指数/ETF）走各自独立的数据获取和校验逻辑，从根本上防止上证指数被当成平安银行股票拉取的问题。

**Architecture:** 新增 `AssetTypeHandler` ABC 基类，每个 handler 封装 fetch+normalize+validate 三合一逻辑。`fetch_daily_bars` 函数接收新增的 `asset_type` 参数并分派到对应 handler。`write_bars_parquet` 增加写入前价格连续性检查。新增 `lake-fix-index` CLI 命令清洗现有脏数据并补充正确的指数历史。

**Tech Stack:** Python 3.13, akshare, pandas, DuckDB, argparse

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/trading_os/data/exceptions.py` | Create | `DataIntegrityError` 异常类 |
| `src/trading_os/data/sources/asset_type_handler.py` | Create | `AssetTypeHandler` ABC + `EquityHandler` + `IndexHandler` + `EtfHandler` stub |
| `src/trading_os/data/sources/akshare_source.py` | Modify | `fetch_daily_bars` 增加 `asset_type` 参数，分派到 handler |
| `src/trading_os/data/lake.py` | Modify | `write_bars_parquet` 增加 `_check_price_continuity` |
| `src/trading_os/cli.py` | Modify | `fetch-bars` 增加 `--asset-type`；新增 `lake-fix-index` 子命令 |
| `.claude/skills/daily-workflow/SKILL.md` | Modify | 更新 `fetch-bars` 命令加 `--asset-type index` |
| `tests/test_asset_type_handler.py` | Create | Handler 单元测试 |
| `tests/test_data_integrity.py` | Create | `_check_price_continuity` 测试 |

---

## Task 1: DataIntegrityError 异常类

**Files:**
- Create: `src/trading_os/data/exceptions.py`
- Test: `tests/test_data_integrity.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_data_integrity.py
import pytest


def test_data_integrity_error_is_value_error():
    """DataIntegrityError must be catchable as ValueError."""
    from trading_os.data.exceptions import DataIntegrityError

    with pytest.raises(ValueError):
        raise DataIntegrityError(
            symbol="SSE:000001",
            expected_range=(3000.0, 4500.0),
            actual_value=11.0,
        )


def test_data_integrity_error_message_contains_symbol():
    from trading_os.data.exceptions import DataIntegrityError

    err = DataIntegrityError(
        symbol="SSE:000001",
        expected_range=(3000.0, 4500.0),
        actual_value=11.0,
    )
    assert "SSE:000001" in str(err)
    assert "11.0" in str(err)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/zcs/code2/trading-os
python -m pytest tests/test_data_integrity.py -v
```

Expected: `ImportError: cannot import name 'DataIntegrityError'`

- [ ] **Step 3: Create the exceptions module**

```python
# src/trading_os/data/exceptions.py
"""Data integrity exceptions for the trading_os data pipeline."""


class DataIntegrityError(ValueError):
    """Raised when incoming data would corrupt an existing symbol's price series.

    Inherits from ValueError so callers can ``except ValueError`` to catch both
    this and ordinary validation errors without needing to import this class.
    """

    def __init__(self, *, symbol: str, expected_range: tuple[float, float], actual_value: float) -> None:
        self.symbol = symbol
        self.expected_range = expected_range
        self.actual_value = actual_value
        lo, hi = expected_range
        super().__init__(
            f"Price continuity check failed for {symbol}: "
            f"existing data median implies range [{lo:.2f}, {hi:.2f}], "
            f"but new data contains {actual_value:.4f}. "
            "This likely means data from a different asset is being written to this symbol. "
            "Use --asset-type to specify the correct asset type."
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_data_integrity.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/data/exceptions.py tests/test_data_integrity.py
git commit -m "feat: add DataIntegrityError for price continuity violations"
```

---

## Task 2: AssetTypeHandler ABC + EquityHandler + IndexHandler

**Files:**
- Create: `src/trading_os/data/sources/asset_type_handler.py`
- Test: `tests/test_asset_type_handler.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_asset_type_handler.py
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd


def _make_index_df():
    """Minimal DataFrame in ak.stock_zh_index_daily format (English columns)."""
    return pd.DataFrame({
        "date": pd.date_range("2026-04-08", periods=5, freq="B"),
        "open": [3200.0, 3210.0, 3220.0, 3230.0, 3240.0],
        "high": [3250.0, 3260.0, 3270.0, 3280.0, 3290.0],
        "low":  [3180.0, 3190.0, 3200.0, 3210.0, 3220.0],
        "close": [3220.0, 3230.0, 3240.0, 3250.0, 3260.0],
        "volume": [30_000_000.0] * 5,  # 3000万手，正常
        "amount": [3.5e11] * 5,        # 3500亿元
    })


def _make_equity_df():
    """Minimal DataFrame in akshare eastmoney format (Chinese columns)."""
    return pd.DataFrame({
        "日期": pd.date_range("2026-04-08", periods=5, freq="B"),
        "开盘": [10.0, 10.1, 10.2, 10.3, 10.4],
        "最高": [10.5, 10.6, 10.7, 10.8, 10.9],
        "最低": [9.5, 9.6, 9.7, 9.8, 9.9],
        "收盘": [10.2, 10.3, 10.4, 10.5, 10.6],
        "成交量": [1_000_000] * 5,
        "成交额": [10_000_000.0] * 5,
    })


# ── IndexHandler ──────────────────────────────────────────────────────────────

def test_index_handler_fetch_uses_sh_prefix_for_sse():
    """SSE index fetches with 'sh' prefix."""
    from trading_os.data.schema import Exchange, Adjustment
    from trading_os.data.sources.asset_type_handler import IndexHandler

    mock_ak = MagicMock()
    mock_ak.stock_zh_index_daily.return_value = _make_index_df()

    handler = IndexHandler()
    with patch("trading_os.data.sources.asset_type_handler.ak", mock_ak):
        df, source = handler.fetch(
            "000001", Exchange.SSE,
            start="2026-04-08", end="2026-04-12",
            adjustment=Adjustment.QFQ,
        )

    mock_ak.stock_zh_index_daily.assert_called_once_with(symbol="sh000001")
    assert source == "akshare_index"
    assert not df.empty


def test_index_handler_fetch_uses_sz_prefix_for_szse():
    """SZSE index fetches with 'sz' prefix."""
    from trading_os.data.schema import Exchange, Adjustment
    from trading_os.data.sources.asset_type_handler import IndexHandler

    mock_ak = MagicMock()
    mock_ak.stock_zh_index_daily.return_value = _make_index_df()

    handler = IndexHandler()
    with patch("trading_os.data.sources.asset_type_handler.ak", mock_ak):
        df, source = handler.fetch(
            "399001", Exchange.SZSE,
            start="2026-04-08", end="2026-04-12",
            adjustment=Adjustment.QFQ,
        )

    mock_ak.stock_zh_index_daily.assert_called_once_with(symbol="sz399001")
    assert source == "akshare_index"


def test_index_handler_normalized_df_has_standard_columns():
    """fetch() result must have symbol, ts, open, high, low, close, volume, source."""
    from trading_os.data.schema import Exchange, Adjustment
    from trading_os.data.sources.asset_type_handler import IndexHandler

    mock_ak = MagicMock()
    mock_ak.stock_zh_index_daily.return_value = _make_index_df()

    handler = IndexHandler()
    with patch("trading_os.data.sources.asset_type_handler.ak", mock_ak):
        df, _ = handler.fetch(
            "000001", Exchange.SSE,
            start="2026-04-08", end="2026-04-12",
            adjustment=Adjustment.NONE,
        )

    for col in ["symbol", "ts", "open", "high", "low", "close", "volume", "source"]:
        assert col in df.columns, f"Missing column: {col}"
    assert df["source"].iloc[0] == "akshare_index"
    assert df["symbol"].iloc[0] == "SSE:000001"


def test_index_handler_adjustment_forced_to_none():
    """adjustment stored in df must be 'none' regardless of what caller passed."""
    from trading_os.data.schema import Exchange, Adjustment
    from trading_os.data.sources.asset_type_handler import IndexHandler

    mock_ak = MagicMock()
    mock_ak.stock_zh_index_daily.return_value = _make_index_df()

    handler = IndexHandler()
    with patch("trading_os.data.sources.asset_type_handler.ak", mock_ak):
        df, _ = handler.fetch(
            "000001", Exchange.SSE,
            start=None, end=None,
            adjustment=Adjustment.QFQ,   # caller asked for QFQ
        )

    assert df["adjustment"].iloc[0] == "none"  # must be overridden


def test_index_handler_validate_passes_for_valid_index_price():
    """Prices in 100-20000 range and volume > 1e6 should pass."""
    from trading_os.data.schema import Exchange
    from trading_os.data.sources.asset_type_handler import IndexHandler

    handler = IndexHandler()
    df = pd.DataFrame({
        "close": [3200.0, 3250.0],
        "volume": [30_000_000.0, 25_000_000.0],
    })
    handler.validate(df, "000001", Exchange.SSE)  # should not raise


def test_index_handler_validate_rejects_equity_price():
    """Price of ~11 (平安银行 range) must fail index validation."""
    from trading_os.data.schema import Exchange
    from trading_os.data.sources.asset_type_handler import IndexHandler
    from trading_os.data.exceptions import DataIntegrityError

    handler = IndexHandler()
    df = pd.DataFrame({
        "close": [11.09, 11.01, 11.37],
        "volume": [680_915.0, 722_530.0, 936_958.0],
    })
    with pytest.raises(DataIntegrityError):
        handler.validate(df, "000001", Exchange.SSE)


# ── EquityHandler ─────────────────────────────────────────────────────────────

def test_equity_handler_validate_passes_for_normal_stock():
    from trading_os.data.schema import Exchange
    from trading_os.data.sources.asset_type_handler import EquityHandler

    handler = EquityHandler()
    df = pd.DataFrame({
        "close": [10.2, 10.3, 10.4],
        "volume": [1_000_000.0] * 3,
    })
    handler.validate(df, "600000", Exchange.SSE)  # should not raise


def test_equity_handler_validate_rejects_absurd_price():
    from trading_os.data.schema import Exchange
    from trading_os.data.sources.asset_type_handler import EquityHandler
    from trading_os.data.exceptions import DataIntegrityError

    handler = EquityHandler()
    df = pd.DataFrame({
        "close": [999999.0],  # 超出 10000 上限
        "volume": [1_000_000.0],
    })
    with pytest.raises(DataIntegrityError):
        handler.validate(df, "600000", Exchange.SSE)


# ── EtfHandler stub ───────────────────────────────────────────────────────────

def test_etf_handler_raises_not_implemented():
    from trading_os.data.schema import Exchange, Adjustment
    from trading_os.data.sources.asset_type_handler import EtfHandler

    handler = EtfHandler()
    with pytest.raises(NotImplementedError):
        handler.fetch("510300", Exchange.SSE, start=None, end=None, adjustment=Adjustment.QFQ)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_asset_type_handler.py -v
```

Expected: `ImportError: cannot import name 'IndexHandler'`

- [ ] **Step 3: Create the asset_type_handler module**

```python
# src/trading_os/data/sources/asset_type_handler.py
"""Asset-type-aware data handlers.

Each AssetType gets its own handler that encapsulates:
  - fetch: pull data from the right API endpoint
  - normalize: map raw columns to the standard bar schema
  - validate: sanity-check prices before writing to the lake

The dispatcher in akshare_source.fetch_daily_bars selects the handler
based on the caller-supplied asset_type argument.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

import pandas as pd

try:
    import akshare as ak
except ImportError:
    ak = None  # type: ignore[assignment]

from ..schema import Adjustment, Exchange, Symbol, Timeframe
from ..exceptions import DataIntegrityError


class AssetTypeHandler(ABC):
    """Base class for all asset-type handlers."""

    @abstractmethod
    def fetch(
        self,
        ticker: str,
        exchange: Exchange,
        *,
        start: str | None,
        end: str | None,
        adjustment: Adjustment,
    ) -> tuple[pd.DataFrame, str]:
        """Fetch, normalize, and return (df, source_name).

        The returned df already has all standard bar columns:
        symbol, exchange, timeframe, adjustment, ts, open, high, low,
        close, volume, vwap, trades, source.
        """
        ...

    @abstractmethod
    def validate(self, df: pd.DataFrame, ticker: str, exchange: Exchange) -> None:
        """Sanity-check prices/volume before writing.

        Raises DataIntegrityError if the data looks wrong for this asset type.
        """
        ...


# ── Equity ────────────────────────────────────────────────────────────────────

class EquityHandler(AssetTypeHandler):
    """A-share equity (普通股票). Uses the existing _fetch_with_fallback path."""

    def fetch(
        self,
        ticker: str,
        exchange: Exchange,
        *,
        start: str | None,
        end: str | None,
        adjustment: Adjustment,
    ) -> tuple[pd.DataFrame, str]:
        # Delegate to the existing equity logic in akshare_source
        from .akshare_source import (
            _fetch_with_fallback,
            _normalize_akshare_data,
            _build_akshare_symbol,
        )
        from datetime import timedelta

        symbol_str = _build_akshare_symbol(ticker, exchange)

        end_str = (end or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
        start_str = (
            start
            or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        ).replace("-", "")

        adjust_map = {Adjustment.QFQ: "qfq", Adjustment.HFQ: "hfq", Adjustment.NONE: ""}
        adjust_str = adjust_map.get(adjustment, "")

        df, source = _fetch_with_fallback(ak, symbol_str, exchange, start_str, end_str, adjust_str)
        if df is None or df.empty:
            return pd.DataFrame(), "none"

        df = _normalize_akshare_data(df, ticker, exchange, adjustment)
        return df, source

    def validate(self, df: pd.DataFrame, ticker: str, exchange: Exchange) -> None:
        if df.empty:
            return
        bad = df[df["close"] < 0.01]
        if not bad.empty:
            raise DataIntegrityError(
                symbol=f"{exchange.value}:{ticker}",
                expected_range=(0.01, 10_000.0),
                actual_value=float(bad["close"].iloc[0]),
            )
        bad = df[df["close"] > 10_000]
        if not bad.empty:
            raise DataIntegrityError(
                symbol=f"{exchange.value}:{ticker}",
                expected_range=(0.01, 10_000.0),
                actual_value=float(bad["close"].iloc[0]),
            )


# ── Index ─────────────────────────────────────────────────────────────────────

class IndexHandler(AssetTypeHandler):
    """A-share market index (指数). Uses ak.stock_zh_index_daily — the correct index API."""

    def fetch(
        self,
        ticker: str,
        exchange: Exchange,
        *,
        start: str | None,
        end: str | None,
        adjustment: Adjustment,  # ignored for indices — always stored as NONE
    ) -> tuple[pd.DataFrame, str]:
        if ak is None:
            raise RuntimeError("akshare is required. Install with: pip install akshare")

        prefix = "sh" if exchange == Exchange.SSE else "sz"
        symbol_str = f"{prefix}{ticker}"

        raw = ak.stock_zh_index_daily(symbol=symbol_str)
        if raw is None or raw.empty:
            return pd.DataFrame(), "none"

        # Filter by date range if provided
        raw["date"] = pd.to_datetime(raw["date"])
        if start:
            raw = raw[raw["date"] >= pd.Timestamp(start)]
        if end:
            raw = raw[raw["date"] <= pd.Timestamp(end)]
        if raw.empty:
            return pd.DataFrame(), "none"

        # Normalize to standard bar schema
        df = raw.rename(columns={"date": "ts"}).copy()
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        df["symbol"] = str(Symbol(exchange=exchange, ticker=ticker))
        df["exchange"] = exchange.value
        df["timeframe"] = Timeframe.D1.value
        df["adjustment"] = Adjustment.NONE.value   # always NONE for indices
        df["source"] = "akshare_index"

        # vwap: amount (元) / volume (手*100股) ≈ average price per share
        if "amount" in df.columns and df["amount"].notna().all() and (df["volume"] > 0).all():
            df["vwap"] = df["amount"] / (df["volume"] * 100)
        else:
            df["vwap"] = (df["high"] + df["low"] + df["close"]) / 3

        df["trades"] = 0  # not available from index API

        for col in ["open", "high", "low", "close", "volume", "vwap"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.sort_values("ts").reset_index(drop=True)

        keep = ["symbol", "exchange", "timeframe", "adjustment", "ts",
                "open", "high", "low", "close", "volume", "vwap", "trades", "source"]
        return df[[c for c in keep if c in df.columns]], "akshare_index"

    def validate(self, df: pd.DataFrame, ticker: str, exchange: Exchange) -> None:
        if df.empty:
            return
        symbol_id = f"{exchange.value}:{ticker}"
        # Price range: A-share indices have never been below 100 or above 20000
        bad_price = df[(df["close"] < 100) | (df["close"] > 20_000)]
        if not bad_price.empty:
            raise DataIntegrityError(
                symbol=symbol_id,
                expected_range=(100.0, 20_000.0),
                actual_value=float(bad_price["close"].iloc[0]),
            )
        # Volume: index volume is in 手 (lots); normal trading day > 1M lots
        bad_vol = df[df["volume"] < 1_000_000]
        if not bad_vol.empty:
            raise DataIntegrityError(
                symbol=symbol_id,
                expected_range=(1_000_000.0, float("inf")),
                actual_value=float(bad_vol["volume"].iloc[0]),
            )


# ── ETF (stub) ────────────────────────────────────────────────────────────────

class EtfHandler(AssetTypeHandler):
    """ETF handler — not yet implemented."""

    def fetch(
        self,
        ticker: str,
        exchange: Exchange,
        *,
        start: str | None,
        end: str | None,
        adjustment: Adjustment,
    ) -> tuple[pd.DataFrame, str]:
        raise NotImplementedError(
            "EtfHandler is not yet implemented. "
            "Use --asset-type equity for now and handle ETF codes manually."
        )

    def validate(self, df: pd.DataFrame, ticker: str, exchange: Exchange) -> None:
        raise NotImplementedError("EtfHandler is not yet implemented.")


# ── Dispatcher ────────────────────────────────────────────────────────────────

from ..schema import AssetType  # noqa: E402 — import after class defs to avoid circularity

_HANDLERS: dict[AssetType, AssetTypeHandler] = {
    AssetType.EQUITY: EquityHandler(),
    AssetType.INDEX: IndexHandler(),
    AssetType.ETF: EtfHandler(),
}


def get_handler(asset_type: AssetType) -> AssetTypeHandler:
    """Return the handler for the given asset type.

    Raises ValueError for unsupported types.
    """
    handler = _HANDLERS.get(asset_type)
    if handler is None:
        supported = ", ".join(k.value for k in _HANDLERS)
        raise ValueError(
            f"No handler registered for AssetType.{asset_type.value}. "
            f"Supported: {supported}"
        )
    return handler
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_asset_type_handler.py -v
```

Expected: All tests pass. If `akshare` is not importable in the test environment, the `IndexHandler.fetch` tests will skip via the `ak = None` guard — that is acceptable.

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/data/sources/asset_type_handler.py tests/test_asset_type_handler.py
git commit -m "feat: add AssetTypeHandler ABC with EquityHandler, IndexHandler, EtfHandler stub"
```

---

## Task 3: Wire `fetch_daily_bars` to the dispatcher

**Files:**
- Modify: `src/trading_os/data/sources/akshare_source.py` (lines 109–117, signature only)
- Test: `tests/test_akshare_source.py` (add two new tests at the bottom)

- [ ] **Step 1: Write the failing tests**

Append to the bottom of `tests/test_akshare_source.py`:

```python
def test_fetch_daily_bars_accepts_asset_type_index():
    """fetch_daily_bars with asset_type=AssetType.INDEX dispatches to IndexHandler."""
    from unittest.mock import patch, MagicMock
    import pandas as pd
    from trading_os.data.schema import Exchange, Adjustment, AssetType
    from trading_os.data.sources.akshare_source import fetch_daily_bars

    mock_df = pd.DataFrame({
        "date": pd.date_range("2026-04-08", periods=3, freq="B"),
        "open": [3200.0, 3210.0, 3220.0],
        "high": [3250.0, 3260.0, 3270.0],
        "low":  [3180.0, 3190.0, 3200.0],
        "close": [3220.0, 3230.0, 3240.0],
        "volume": [30_000_000.0] * 3,
        "amount": [3.5e11] * 3,
    })

    with patch("trading_os.data.sources.asset_type_handler.ak") as mock_ak:
        mock_ak.stock_zh_index_daily.return_value = mock_df
        df, source = fetch_daily_bars(
            "000001",
            exchange=Exchange.SSE,
            adjustment=Adjustment.QFQ,
            asset_type=AssetType.INDEX,
        )

    assert source == "akshare_index"
    assert not df.empty
    assert df["source"].iloc[0] == "akshare_index"
    assert df["adjustment"].iloc[0] == "none"  # forced to NONE for indices


def test_fetch_daily_bars_default_asset_type_is_equity():
    """Calling without asset_type defaults to equity (backward compatible)."""
    from unittest.mock import MagicMock, patch
    from trading_os.data.schema import Exchange, Adjustment
    from trading_os.data.sources.akshare_source import fetch_daily_bars, _make_akshare_df

    mock_ak = MagicMock()
    mock_ak.stock_zh_a_hist.return_value = _make_akshare_df()

    with patch("trading_os.data.sources.akshare_source._fetch_with_fallback") as mock_fb:
        mock_fb.return_value = (_make_akshare_df(), "akshare")
        df, source = fetch_daily_bars("600000", exchange=Exchange.SSE, adjustment=Adjustment.QFQ)

    assert source == "akshare"
```

Note: `_make_akshare_df` needs to be importable from `akshare_source`. We'll expose it in the next step.

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_akshare_source.py::test_fetch_daily_bars_accepts_asset_type_index -v
```

Expected: `TypeError: fetch_daily_bars() got an unexpected keyword argument 'asset_type'`

- [ ] **Step 3: Modify `fetch_daily_bars` in `akshare_source.py`**

Change the function signature and body (lines 109–181). Replace the entire `fetch_daily_bars` function:

```python
def fetch_daily_bars(
    ticker: str,
    *,
    exchange: Exchange,
    start: str | None = None,
    end: str | None = None,
    adjustment: Adjustment = Adjustment.NONE,
    config: AkshareConfig | None = None,
    asset_type: "AssetType | None" = None,
) -> tuple[pd.DataFrame, str]:
    """
    从akshare获取A股日线数据（自动选择最佳数据源）

    Args:
        ticker: 股票代码 (如 "600000", "000001")
        exchange: 交易所 (SSE/SZSE)
        start: 开始日期 "YYYY-MM-DD"
        end: 结束日期 "YYYY-MM-DD"
        adjustment: 复权类型（对指数无效，会被强制覆盖为 NONE）
        config: 配置参数（仅 EquityHandler 使用）
        asset_type: 资产类型。None 或不传时默认 AssetType.EQUITY（向后兼容）。
                    指数请显式传 AssetType.INDEX。

    Returns:
        (标准化的DataFrame，实际使用的数据源名称)
    """
    from ..schema import AssetType as AT
    from .asset_type_handler import get_handler

    if asset_type is None:
        asset_type = AT.EQUITY

    try:
        import akshare  # noqa: F401 — ensure akshare is installed
    except ImportError as e:
        raise RuntimeError(
            "akshare is required for A-share data. Install with: pip install akshare"
        ) from e

    if exchange not in [Exchange.SSE, Exchange.SZSE]:
        raise ValueError(f"akshare仅支持SSE和SZSE交易所，得到: {exchange}")

    handler = get_handler(asset_type)
    df, source = handler.fetch(ticker, exchange, start=start, end=end, adjustment=adjustment)
    if df is not None and not df.empty:
        handler.validate(df, ticker, exchange)
    return df if df is not None else pd.DataFrame(), source
```

Also expose `_make_akshare_df` as a module-level helper for tests by adding this at the bottom of `akshare_source.py` (after existing functions):

```python
def _make_akshare_df_for_test() -> "pd.DataFrame":
    """Test helper: minimal DataFrame in akshare (eastmoney) column format."""
    import pandas as _pd
    return _pd.DataFrame({
        "日期": _pd.date_range("2024-01-01", periods=5, freq="B"),
        "开盘": [10.0, 10.1, 10.2, 10.3, 10.4],
        "最高": [10.5, 10.6, 10.7, 10.8, 10.9],
        "最低": [9.5, 9.6, 9.7, 9.8, 9.9],
        "收盘": [10.2, 10.3, 10.4, 10.5, 10.6],
        "成交量": [1_000_000] * 5,
        "成交额": [10_000_000.0] * 5,
    })
```

Update the new test in `tests/test_akshare_source.py` to import this helper instead of `_make_akshare_df`:

```python
# In test_fetch_daily_bars_default_asset_type_is_equity:
from trading_os.data.sources.akshare_source import fetch_daily_bars, _make_akshare_df_for_test

# ...
mock_fb.return_value = (_make_akshare_df_for_test(), "akshare")
df, source = fetch_daily_bars("600000", exchange=Exchange.SSE, adjustment=Adjustment.QFQ)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_akshare_source.py -v
python -m pytest tests/test_asset_type_handler.py -v
```

Expected: All pass (existing tests still pass because default `asset_type=None` → `EQUITY`).

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/data/sources/akshare_source.py tests/test_akshare_source.py
git commit -m "feat: wire fetch_daily_bars to AssetType dispatcher"
```

---

## Task 4: `_check_price_continuity` in `write_bars_parquet`

**Files:**
- Modify: `src/trading_os/data/lake.py`
- Test: `tests/test_data_integrity.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_data_integrity.py`:

```python
def _make_lake(tmp_path):
    from pathlib import Path
    from trading_os.data.lake import LocalDataLake
    lake = LocalDataLake(tmp_path / "data")
    lake.init()
    return lake


def _make_bar_df(symbol: str, closes: list[float], source: str = "akshare"):
    """Create a minimal normalized bar DataFrame for writing to the lake."""
    import pandas as pd
    from trading_os.data.schema import Exchange, Timeframe, Adjustment

    exch = symbol.split(":")[0]
    ticker = symbol.split(":")[1]
    n = len(closes)
    return pd.DataFrame({
        "symbol": [symbol] * n,
        "exchange": [exch] * n,
        "timeframe": [Timeframe.D1.value] * n,
        "adjustment": [Adjustment.NONE.value] * n,
        "ts": pd.date_range("2026-01-02", periods=n, freq="B", tz="UTC"),
        "open":   closes,
        "high":   [c * 1.02 for c in closes],
        "low":    [c * 0.98 for c in closes],
        "close":  closes,
        "volume": [1_000_000.0] * n,
        "vwap":   closes,
        "trades": [10000] * n,
        "source": [source] * n,
    })


def test_price_continuity_passes_on_empty_lake(tmp_path):
    """First write to a new symbol must not raise (empty lake = no history)."""
    from trading_os.data.schema import Exchange, Timeframe, Adjustment

    lake = _make_lake(tmp_path)
    df = _make_bar_df("SSE:000001", [3200.0, 3210.0], source="akshare_index")

    # Should not raise
    lake.write_bars_parquet(
        df,
        exchange=Exchange.SSE,
        timeframe=Timeframe.D1,
        adjustment=Adjustment.NONE,
        source="akshare_index",
    )


def test_price_continuity_passes_for_normal_equity_update(tmp_path):
    """Writing stock prices consistent with existing history must not raise."""
    from trading_os.data.schema import Exchange, Timeframe, Adjustment

    lake = _make_lake(tmp_path)
    existing = _make_bar_df("SSE:600000", [10.0, 10.1, 10.2, 10.3, 10.4])
    lake.write_bars_parquet(
        existing,
        exchange=Exchange.SSE,
        timeframe=Timeframe.D1,
        adjustment=Adjustment.NONE,
        source="akshare",
    )
    lake.init()

    new_data = _make_bar_df("SSE:600000", [10.5, 10.6])
    # Should not raise
    lake.write_bars_parquet(
        new_data,
        exchange=Exchange.SSE,
        timeframe=Timeframe.D1,
        adjustment=Adjustment.NONE,
        source="akshare",
    )


def test_price_continuity_rejects_magnitude_jump(tmp_path):
    """Writing 平安银行 prices (~11) after 上证指数 history (~3800) must raise."""
    from trading_os.data.schema import Exchange, Timeframe, Adjustment
    from trading_os.data.exceptions import DataIntegrityError

    lake = _make_lake(tmp_path)
    # Write correct index history
    good_data = _make_bar_df("SSE:000001", [3800.0, 3850.0, 3900.0, 3920.0, 3880.0],
                             source="baostock")
    lake.write_bars_parquet(
        good_data,
        exchange=Exchange.SSE,
        timeframe=Timeframe.D1,
        adjustment=Adjustment.NONE,
        source="baostock",
    )
    lake.init()

    # Try to write 平安银行 price as if it were 000001
    bad_data = _make_bar_df("SSE:000001", [11.09, 11.01, 11.37], source="akshare")
    with pytest.raises(DataIntegrityError):
        lake.write_bars_parquet(
            bad_data,
            exchange=Exchange.SSE,
            timeframe=Timeframe.D1,
            adjustment=Adjustment.NONE,
            source="akshare",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_data_integrity.py -v
```

Expected: `test_price_continuity_rejects_magnitude_jump` FAILS because `write_bars_parquet` has no continuity check yet.

- [ ] **Step 3: Add `_check_price_continuity` to `lake.py`**

Add this function just before `write_bars_parquet` in `src/trading_os/data/lake.py`:

```python
def _check_price_continuity(self, df: "Any", symbol: str) -> None:
    """Reject writes that would create a magnitude discontinuity in close prices.

    Compares the median of the 5 most-recent existing close values for *symbol*
    against every close in the incoming *df*.  If any new close is more than 50x
    or less than 1/50th of that median, raises DataIntegrityError.

    Empty lake (no existing history for symbol): passes silently — first write is
    always allowed.
    """
    from .exceptions import DataIntegrityError

    bars_glob = self.paths.bars_dir.as_posix() + "/*.parquet"
    files = list(self.paths.bars_dir.glob("*.parquet"))
    if not files:
        return  # empty lake — first write

    try:
        with self.connect() as con:
            result = con.execute(
                f"""
                SELECT close FROM read_parquet('{bars_glob}', union_by_name=true)
                WHERE symbol = ?
                ORDER BY ts DESC
                LIMIT 5
                """,
                [symbol],
            ).df()
    except Exception:
        return  # if query fails, don't block the write

    if result.empty:
        return  # no existing data for this symbol — first write

    median_close = float(result["close"].median())
    if median_close <= 0:
        return  # guard against bad existing data

    lo = median_close / 50.0
    hi = median_close * 50.0

    new_closes = df["close"] if hasattr(df, "__iter__") else []
    try:
        import pandas as _pd
        new_closes = _pd.to_numeric(df["close"], errors="coerce").dropna()
    except (KeyError, TypeError):
        return

    bad = new_closes[(new_closes < lo) | (new_closes > hi)]
    if not bad.empty:
        raise DataIntegrityError(
            symbol=symbol,
            expected_range=(lo, hi),
            actual_value=float(bad.iloc[0]),
        )
```

Then modify `write_bars_parquet` to call it. After the existing `missing` columns check (around line 208), add:

```python
        # Price continuity guard: reject writes that would corrupt existing series
        if BarColumns.symbol in df.columns:
            for sym in df[BarColumns.symbol].unique():
                self._check_price_continuity(df[df[BarColumns.symbol] == sym], sym)
        elif BarColumns.symbol not in df.columns:
            pass  # no symbol column — skip check
```

Place this block right after:
```python
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"bars df missing columns: {missing}")
```

The full insertion point in `write_bars_parquet` (after line 208, before `out = df.copy()`):

```python
        # ── price continuity guard ──────────────────────────────────────────
        # Reject writes that would create a magnitude discontinuity.
        # Only checks symbols present in df; skips silently if lake is empty.
        if BarColumns.symbol in df.columns:
            for sym in df[BarColumns.symbol].unique():
                self._check_price_continuity(df[df[BarColumns.symbol] == sym], sym)
        # ───────────────────────────────────────────────────────────────────
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_data_integrity.py -v
```

Expected: All 5 tests pass.

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/trading_os/data/lake.py tests/test_data_integrity.py
git commit -m "feat: add _check_price_continuity to write_bars_parquet"
```

---

## Task 5: CLI — `--asset-type` for `fetch-bars` + `lake-fix-index` command

**Files:**
- Modify: `src/trading_os/cli.py`

- [ ] **Step 1: Add `--asset-type` to `fetch-bars`**

In `src/trading_os/cli.py`, find the argparse block for `fetch-bars` (around line 1408):

```python
    p = sub.add_parser("fetch-bars", help="获取A股日线数据（自动选择最佳数据源）")
    p.add_argument("--exchange", required=True, choices=["SSE", "SZSE"])
    p.add_argument("--ticker", required=True, help="股票代码，如 600000")
    p.add_argument("--start", default=None, help="开始日期 YYYY-MM-DD")
    p.add_argument("--end", default=None, help="结束日期 YYYY-MM-DD")
    p.add_argument("--adjustment", choices=["none", "qfq", "hfq"], default="qfq", help="复权方式")
    p.set_defaults(func=_cmd_fetch_bars)
```

Replace with:

```python
    p = sub.add_parser("fetch-bars", help="获取A股日线数据（自动选择最佳数据源）")
    p.add_argument("--exchange", required=True, choices=["SSE", "SZSE"])
    p.add_argument("--ticker", required=True, help="股票代码，如 600000")
    p.add_argument("--start", default=None, help="开始日期 YYYY-MM-DD")
    p.add_argument("--end", default=None, help="结束日期 YYYY-MM-DD")
    p.add_argument("--adjustment", choices=["none", "qfq", "hfq"], default="qfq", help="复权方式")
    p.add_argument(
        "--asset-type",
        choices=["equity", "index", "etf"],
        default="equity",
        dest="asset_type",
        help="资产类型 (默认: equity)。指数请用 index，如: --asset-type index",
    )
    p.set_defaults(func=_cmd_fetch_bars)
```

- [ ] **Step 2: Update `_cmd_fetch_bars` to pass `asset_type`**

Find `_cmd_fetch_bars` (line 67) and replace:

```python
def _cmd_fetch_bars(ns: argparse.Namespace) -> int:
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, AssetType, Exchange, Timeframe
    from .data.sources.akshare_source import fetch_daily_bars

    root = repo_root()
    lake = LocalDataLake(root / "data")
    exch = Exchange(ns.exchange)
    adj = {"qfq": Adjustment.QFQ, "hfq": Adjustment.HFQ}.get(ns.adjustment, Adjustment.NONE)
    asset_type_map = {
        "equity": AssetType.EQUITY,
        "index": AssetType.INDEX,
        "etf": AssetType.ETF,
    }
    asset_type = asset_type_map.get(getattr(ns, "asset_type", "equity"), AssetType.EQUITY)

    # For index, adjustment is always NONE (IndexHandler enforces this internally,
    # but we also set it here so the write_bars_parquet call uses the right value)
    if asset_type == AssetType.INDEX:
        adj = Adjustment.NONE

    try:
        print(f"获取A股数据: {exch.value}:{ns.ticker} (复权: {adj.value}, 类型: {asset_type.value})")
        df, actual_source = fetch_daily_bars(
            ns.ticker,
            exchange=exch,
            start=ns.start,
            end=ns.end,
            adjustment=adj,
            asset_type=asset_type,
        )
        if df.empty:
            print("未获取到数据")
            return 1
        lake.write_bars_parquet(
            df, exchange=exch, timeframe=Timeframe.D1, adjustment=adj,
            source=actual_source, partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        )
        lake.init()
        source_note = f" (via {actual_source})" if actual_source != "akshare" else ""
        print(f"写入 {len(df)} 条: {exch.value}:{ns.ticker}{source_note}")
        print(f"数据范围: {df['ts'].min().date()} 至 {df['ts'].max().date()}")
        return 0
    except Exception as e:
        print(f"获取A股数据失败: {e}", file=sys.stderr)
        return 1
```

- [ ] **Step 3: Add `_cmd_lake_fix_index` function**

Add this function after `_cmd_lake_compact` (around line 65):

```python
def _cmd_lake_fix_index(ns: argparse.Namespace) -> int:
    """Clean up index data polluted by equity API calls, then re-fetch correct data.

    Idempotent: if correct akshare_index data already exists for the target period,
    skips the re-fetch.
    """
    import duckdb
    from .data.lake import LocalDataLake
    from .data.schema import Adjustment, AssetType, Exchange, Timeframe
    from .data.sources.akshare_source import fetch_daily_bars

    root = repo_root()
    lake = LocalDataLake(root / "data")

    symbol = ns.symbol  # e.g. "SSE:000001"
    exch_str, ticker = symbol.split(":", 1)
    exch = Exchange(exch_str)

    bars_glob = lake.paths.bars_dir.as_posix() + "/*.parquet"
    files = list(lake.paths.bars_dir.glob("*.parquet"))

    if not files:
        print(f"No parquet files found in {lake.paths.bars_dir}. Nothing to fix.")
        return 0

    # Step 1: Count dirty records
    with lake.connect() as con:
        try:
            dirty = con.execute(
                f"""
                SELECT COUNT(*) AS n FROM read_parquet('{bars_glob}', union_by_name=true)
                WHERE symbol = ? AND source = 'akshare'
                """,
                [symbol],
            ).fetchone()[0]
        except Exception:
            dirty = 0

    print(f"[lake-fix-index] {symbol}: found {dirty} dirty records (source=akshare)")

    # Step 2: Determine earliest dirty date for re-fetch range
    if dirty > 0:
        with lake.connect() as con:
            try:
                first_dirty = con.execute(
                    f"""
                    SELECT MIN(ts)::DATE AS d FROM read_parquet('{bars_glob}', union_by_name=true)
                    WHERE symbol = ? AND source = 'akshare'
                    """,
                    [symbol],
                ).fetchone()[0]
            except Exception:
                first_dirty = None
        refetch_start = str(first_dirty) if first_dirty else "2026-04-08"
    else:
        # No dirty data, but check for gap (2026-04-08 to 2026-04-15)
        refetch_start = "2026-04-08"

    # Step 3: Check if already have akshare_index data for the target range
    with lake.connect() as con:
        try:
            existing_clean = con.execute(
                f"""
                SELECT COUNT(*) AS n FROM read_parquet('{bars_glob}', union_by_name=true)
                WHERE symbol = ? AND source = 'akshare_index'
                  AND ts::DATE >= ?
                """,
                [symbol, refetch_start],
            ).fetchone()[0]
        except Exception:
            existing_clean = 0

    if existing_clean > 0 and dirty == 0:
        print(f"[lake-fix-index] Already clean: {existing_clean} akshare_index records, 0 dirty. Nothing to do.")
        return 0

    # Step 4: Remove all dirty parquet files that contain the polluted symbol rows.
    # Strategy: compact first, then delete the bad rows by rewriting all parquet files.
    # Simpler approach: write a cleaned parquet that excludes source=akshare for this symbol.
    print(f"[lake-fix-index] Removing dirty records for {symbol} (source=akshare)...")
    try:
        with lake.connect() as con:
            clean_df = con.execute(
                f"""
                SELECT * FROM read_parquet('{bars_glob}', union_by_name=true)
                WHERE NOT (symbol = ? AND source = 'akshare')
                ORDER BY symbol, ts
                """,
                [symbol],
            ).df()
        # Overwrite all bars with the cleaned data
        clean_path = lake.paths.bars_dir / "bars_cleaned_after_fix_index.parquet"
        clean_df.to_parquet(clean_path, index=False)
        # Remove all other parquet files
        for f in lake.paths.bars_dir.glob("*.parquet"):
            if f != clean_path:
                f.unlink()
        print(f"[lake-fix-index] Dirty records removed. {len(clean_df)} rows retained.")
    except Exception as e:
        print(f"[lake-fix-index] ERROR during cleanup: {e}", file=sys.stderr)
        return 1

    # Step 5: Re-fetch correct index data
    print(f"[lake-fix-index] Re-fetching {symbol} as INDEX from {refetch_start} to today...")
    try:
        df, source = fetch_daily_bars(
            ticker,
            exchange=exch,
            start=refetch_start,
            end=None,
            adjustment=Adjustment.NONE,
            asset_type=AssetType.INDEX,
        )
        if df.empty:
            print(f"[lake-fix-index] WARNING: no data returned for {symbol} from {refetch_start}. "
                  "Check network connectivity.")
            return 1

        lake.write_bars_parquet(
            df, exchange=exch, timeframe=Timeframe.D1, adjustment=Adjustment.NONE,
            source=source,
            partition_hint=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        )
        lake.init()
        print(f"[lake-fix-index] Written {len(df)} clean records for {symbol} (source={source})")
        print(f"[lake-fix-index] Data range: {df['ts'].min().date()} to {df['ts'].max().date()}")
        print(f"[lake-fix-index] DONE. {symbol} is now clean.")
        return 0
    except Exception as e:
        print(f"[lake-fix-index] ERROR during re-fetch: {e}", file=sys.stderr)
        return 1
```

- [ ] **Step 4: Register `lake-fix-index` in `main()`**

In the `main()` function's argparse setup, add after the `lake-compact` block (around line 1352):

```python
    p = sub.add_parser(
        "lake-fix-index",
        help="清洗被股票 API 污染的指数数据并重新拉取正确数据（幂等）",
    )
    p.add_argument(
        "--symbol",
        required=True,
        help="要修复的指数 symbol，如 SSE:000001",
    )
    p.set_defaults(func=_cmd_lake_fix_index)
```

- [ ] **Step 5: Smoke test the CLI changes**

```bash
cd /Users/zcs/code2/trading-os
python -m trading_os fetch-bars --help | grep asset-type
```

Expected output contains: `--asset-type {equity,index,etf}`

```bash
python -m trading_os lake-fix-index --help
```

Expected output contains: `--symbol SYMBOL`

- [ ] **Step 6: Commit**

```bash
git add src/trading_os/cli.py
git commit -m "feat: add --asset-type to fetch-bars; add lake-fix-index command"
```

---

## Task 6: Run `lake-fix-index` to clean existing dirty data

This task runs the one-time data migration. **Requires network access** to re-fetch index data.

- [ ] **Step 1: Check current dirty records**

```bash
python -c "
import duckdb
from pathlib import Path
bars_glob = str(Path('data/bars') / '*.parquet')
con = duckdb.connect('data/lake.duckdb')
print(con.execute(\"\"\"
    SELECT symbol, source, COUNT(*) as n, MIN(ts::DATE) as first, MAX(ts::DATE) as last
    FROM read_parquet('{glob}', union_by_name=true)
    WHERE symbol = 'SSE:000001'
    GROUP BY symbol, source
    ORDER BY source
\"\"\".format(glob=bars_glob)).df().to_string())
con.close()
"
```

Expected: Shows rows with `source=akshare` (dirty) and `source=baostock` (clean history).

- [ ] **Step 2: Run the fix**

```bash
python -m trading_os lake-fix-index --symbol SSE:000001
```

Expected output:
```
[lake-fix-index] SSE:000001: found N dirty records (source=akshare)
[lake-fix-index] Removing dirty records for SSE:000001 (source=akshare)...
[lake-fix-index] Dirty records removed. XXXX rows retained.
[lake-fix-index] Re-fetching SSE:000001 as INDEX from 2026-04-08 to today...
[lake-fix-index] Written NN clean records for SSE:000001 (source=akshare_index)
[lake-fix-index] Data range: 2026-04-08 to 2026-05-08
[lake-fix-index] DONE. SSE:000001 is now clean.
```

- [ ] **Step 3: Verify clean state**

```bash
python -c "
import duckdb
from pathlib import Path
bars_glob = str(Path('data/bars') / '*.parquet')
con = duckdb.connect('data/lake.duckdb')
print(con.execute(\"\"\"
    SELECT symbol, source, COUNT(*) as n, MIN(ts::DATE) as first, MAX(ts::DATE) as last
    FROM read_parquet('{glob}', union_by_name=true)
    WHERE symbol = 'SSE:000001'
    GROUP BY symbol, source
    ORDER BY source
\"\"\".format(glob=bars_glob)).df().to_string())
con.close()
"
```

Expected: No rows with `source=akshare`. Rows with `source=baostock` and `source=akshare_index`.

- [ ] **Step 4: Verify market-breadth returns sensible results**

```bash
python -m trading_os market-breadth --index SSE:000001
```

Expected:換筹日数量合理（不应全为 0 或全为 30），价格范围应在 3000~4500 点，not ~11.

- [ ] **Step 5: Commit data state note**

```bash
git add -A  # pool.json or tracking files may have changed
git commit -m "fix: clean SSE:000001 index data polluted by equity API; re-fetch correct points via IndexHandler"
```

---

## Task 7: Update `daily-workflow` skill

**Files:**
- Modify: `.claude/skills/daily-workflow/SKILL.md` (line 27)

- [ ] **Step 1: Update the fetch-bars command**

In `.claude/skills/daily-workflow/SKILL.md`, find (line 25-28):

```markdown
```bash
# 全量更新（等完成后再继续）
python -m trading_os fetch-ak-bulk --start {LAST_TRADING_DAY} --end {TODAY} --adjustment qfq
# 同时更新上证指数（market-breadth 需要）
python -m trading_os fetch-bars --exchange SSE --ticker 000001 --start {LAST_TRADING_DAY}
```
```

Replace with:

```markdown
```bash
# 全量更新（等完成后再继续）
python -m trading_os fetch-ak-bulk --start {LAST_TRADING_DAY} --end {TODAY} --adjustment qfq
# 同时更新上证指数（market-breadth 需要；必须加 --asset-type index 才能拉到真实点位）
python -m trading_os fetch-bars --exchange SSE --ticker 000001 --asset-type index --start {LAST_TRADING_DAY}
```
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/daily-workflow/SKILL.md
git commit -m "fix: update daily-workflow to use --asset-type index for SSE:000001"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by task |
|-----------------|----------------|
| AssetTypeHandler ABC | Task 2 |
| EquityHandler (wraps existing logic) | Task 2 |
| IndexHandler with `sh`/`sz` prefix + `stock_zh_index_daily` | Task 2 |
| EtfHandler stub with `NotImplementedError` | Task 2 |
| `fetch_daily_bars` receives `asset_type`, dispatches to handler | Task 3 |
| `validate()` called before returning from `fetch_daily_bars` | Task 3 |
| `DataIntegrityError` inherits `ValueError` | Task 1 |
| `_check_price_continuity` with empty-lake bypass | Task 4 |
| `_check_price_continuity` raises `DataIntegrityError` on 50x magnitude jump | Task 4 |
| `--asset-type` CLI flag for `fetch-bars` | Task 5 |
| `lake-fix-index` command (idempotent, deletes source=akshare only) | Task 5+6 |
| `daily-workflow` skill updated | Task 7 |
| `adjustment=NONE` for index, `source=akshare_index` | Task 2 + Task 5 |
| Backward compatible (default asset_type=equity) | Task 3 |

**No placeholders found.**

**Type consistency:**
- `get_handler(asset_type)` defined in Task 2, called in Task 3 ✓
- `DataIntegrityError(symbol=, expected_range=, actual_value=)` defined in Task 1, raised in Tasks 2 and 4 ✓
- `source="akshare_index"` set in `IndexHandler.fetch()` (Task 2), checked in `lake-fix-index` (Task 6) ✓
- `_check_price_continuity` defined in Task 4 as method `self._check_price_continuity`, called in `write_bars_parquet` ✓

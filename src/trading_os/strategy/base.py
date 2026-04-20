"""Core strategy abstractions.

The three-environment contract:
  - Strategy.generate_signals() is called once per trading day.
  - The `bars` DataFrame passed in contains only data up to (but NOT including)
    the trading_date. This is enforced by the DataPipeline, not the strategy.
  - The same Strategy subclass runs unchanged in backtest, paper, and live modes.
    Only the data source and broker differ.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import pandas as pd


SignalAction = Literal["BUY", "SELL", "HOLD"]


@dataclass
class Signal:
    """A trading signal produced by a strategy for one symbol.

    Attributes:
        symbol:      Canonical symbol id, e.g. "SSE:600000".
        action:      BUY | SELL | HOLD.
        size:        Target portfolio allocation as a fraction of NAV (0.0–1.0).
                     For BUY: target weight after the trade.
                     For SELL: target weight after the trade (0.0 = full liquidation).
                     For HOLD: ignored.
        reason:      Human-readable justification.
        confidence:  0.0–1.0, optional (used by AI strategies).
        valid_until: Signal expires after this date. EventBus drops stale signals.
    """

    symbol: str
    action: SignalAction
    size: float = 0.0
    reason: str = ""
    confidence: float = 1.0
    valid_until: date | None = None
    metadata: dict = field(default_factory=dict)
    # metadata 用于策略内部传递额外信息，BacktestRunner 不读取此字段。
    # 示例（Elder 策略）：{"stop_price": 5.70, "atr": 0.33}

    def __post_init__(self) -> None:
        if not 0.0 <= self.size <= 1.0:
            raise ValueError(f"Signal.size must be in [0, 1], got {self.size}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Signal.confidence must be in [0, 1], got {self.confidence}")
        if self.action not in ("BUY", "SELL", "HOLD"):
            raise ValueError(f"Signal.action must be BUY/SELL/HOLD, got {self.action!r}")


@dataclass
class StrategyContext:
    """Runtime context injected into the strategy at startup."""

    trading_date: date
    symbols: list[str]
    initial_cash: float = 1_000_000.0
    # Additional metadata can be added here (e.g., universe filters, risk limits)
    extra: dict = field(default_factory=dict)


class Strategy(ABC):
    """Abstract base class for all trading strategies.

    Subclass this and implement `generate_signals`. The same subclass is used
    in BacktestRunner, PaperRunner, and LiveRunner without modification.

    Example::

        class MACrossStrategy(Strategy):
            def generate_signals(self, bars, trading_date):
                ma5  = bars.groupby("symbol")["close"].transform(lambda s: s.rolling(5).mean())
                ma20 = bars.groupby("symbol")["close"].transform(lambda s: s.rolling(20).mean())
                signals = {}
                for sym in bars["symbol"].unique():
                    sym_bars = bars[bars["symbol"] == sym]
                    if sym_bars.empty:
                        continue
                    last_ma5  = sym_bars["close"].rolling(5).mean().iloc[-1]
                    last_ma20 = sym_bars["close"].rolling(20).mean().iloc[-1]
                    if last_ma5 > last_ma20:
                        signals[sym] = Signal(sym, "BUY", size=0.95)
                    else:
                        signals[sym] = Signal(sym, "SELL", size=0.0)
                return signals
    """

    def on_start(self, context: StrategyContext) -> None:
        """Called once before the first bar. Override to initialize state."""

    def on_fill(self, fill: object) -> None:
        """Called after each order fill. Override to track position state."""

    @abstractmethod
    def generate_signals(
        self,
        bars: "pd.DataFrame",
        trading_date: date,
    ) -> dict[str, Signal]:
        """Generate trading signals for the given trading date.

        Args:
            bars:         Historical OHLCV bars up to (NOT including) trading_date.
                          Columns: symbol, ts, open, high, low, close, volume, ...
            trading_date: The date for which signals are being generated.
                          Orders will execute at the OPEN of trading_date.

        Returns:
            Dict mapping symbol → Signal. Symbols not in the dict are treated as HOLD.
        """

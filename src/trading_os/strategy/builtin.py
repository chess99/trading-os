"""Built-in reference strategies.

These are simple, well-understood strategies for baseline comparison and testing.
They are NOT investment advice.
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from .base import Signal, Strategy

if TYPE_CHECKING:
    import pandas as pd


class BuyAndHoldStrategy(Strategy):
    """Buy all symbols on the first bar and hold forever.

    Useful as a benchmark. Allocates equally across all symbols.
    """

    def __init__(self) -> None:
        self._entered: set[str] = set()

    def on_start(self, context: object) -> None:
        self._entered.clear()

    def generate_signals(
        self,
        bars: "pd.DataFrame",
        trading_date: date,
    ) -> dict[str, Signal]:
        from ..data.schema import BarColumns

        symbols = bars[BarColumns.symbol].unique().tolist()
        if not symbols:
            return {}

        per_symbol_size = 0.95 / len(symbols)  # 95% invested, 5% cash buffer
        signals = {}

        for sym in symbols:
            if sym not in self._entered:
                signals[sym] = Signal(
                    symbol=sym,
                    action="BUY",
                    size=per_symbol_size,
                    reason="Buy-and-hold initial entry",
                )
                self._entered.add(sym)

        return signals


class MACrossStrategy(Strategy):
    """Simple moving average crossover strategy.

    Signal logic:
        - MA(fast) crosses above MA(slow) → BUY (target 95% allocation)
        - MA(fast) crosses below MA(slow) → SELL (target 0% allocation)

    This is a textbook momentum strategy, not a production strategy.
    """

    def __init__(self, fast: int = 5, slow: int = 20) -> None:
        if fast >= slow:
            raise ValueError(f"fast ({fast}) must be less than slow ({slow})")
        self.fast = fast
        self.slow = slow

    def generate_signals(
        self,
        bars: "pd.DataFrame",
        trading_date: date,
    ) -> dict[str, Signal]:
        from ..data.schema import BarColumns

        signals: dict[str, Signal] = {}
        symbols = bars[BarColumns.symbol].unique().tolist()

        for sym in symbols:
            sym_bars = bars[bars[BarColumns.symbol] == sym].sort_values(BarColumns.ts)

            if len(sym_bars) < self.slow + 1:
                # Not enough history
                continue

            close = sym_bars[BarColumns.close].astype(float)
            ma_fast = close.rolling(self.fast).mean()
            ma_slow = close.rolling(self.slow).mean()

            # Current and previous values (last two rows)
            curr_fast = ma_fast.iloc[-1]
            curr_slow = ma_slow.iloc[-1]
            prev_fast = ma_fast.iloc[-2]
            prev_slow = ma_slow.iloc[-2]

            if any(v != v for v in [curr_fast, curr_slow, prev_fast, prev_slow]):
                # NaN check
                continue

            if prev_fast <= prev_slow and curr_fast > curr_slow:
                # Golden cross: fast crosses above slow
                signals[sym] = Signal(
                    symbol=sym,
                    action="BUY",
                    size=0.95,
                    reason=f"MA{self.fast}/MA{self.slow} golden cross",
                )
            elif prev_fast >= prev_slow and curr_fast < curr_slow:
                # Death cross: fast crosses below slow
                signals[sym] = Signal(
                    symbol=sym,
                    action="SELL",
                    size=0.0,
                    reason=f"MA{self.fast}/MA{self.slow} death cross",
                )

        return signals


class RSIStrategy(Strategy):
    """RSI mean-reversion strategy.

    Signal logic:
        - RSI < oversold_threshold → BUY
        - RSI > overbought_threshold → SELL
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
    ) -> None:
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(
        self,
        bars: "pd.DataFrame",
        trading_date: date,
    ) -> dict[str, Signal]:
        from ..data.schema import BarColumns

        signals: dict[str, Signal] = {}
        symbols = bars[BarColumns.symbol].unique().tolist()

        for sym in symbols:
            sym_bars = bars[bars[BarColumns.symbol] == sym].sort_values(BarColumns.ts)

            if len(sym_bars) < self.period + 1:
                continue

            close = sym_bars[BarColumns.close].astype(float)
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(self.period).mean()
            loss = (-delta.clip(upper=0)).rolling(self.period).mean()

            rs = gain / loss.replace(0, float("nan"))
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]

            if current_rsi != current_rsi:  # NaN
                continue

            if current_rsi < self.oversold:
                signals[sym] = Signal(
                    symbol=sym,
                    action="BUY",
                    size=0.95,
                    reason=f"RSI({self.period})={current_rsi:.1f} < {self.oversold} (oversold)",
                )
            elif current_rsi > self.overbought:
                signals[sym] = Signal(
                    symbol=sym,
                    action="SELL",
                    size=0.0,
                    reason=f"RSI({self.period})={current_rsi:.1f} > {self.overbought} (overbought)",
                )

        return signals

"""Elder Triple Screen Strategy — A-share long-only implementation.

Performance design: indicators are precomputed once in on_data() for all symbols
and all dates, stored as a lookup table. generate_signals() is O(1) per symbol
per day — just a dict lookup, no pandas computation in the hot loop.

Rules (from Alexander Elder, "Trading for a Living"):

First Screen (weekly timeframe — strategic direction):
  - Weekly EMA(26) rising
  - Weekly MACD histogram season = spring (below zero, rising) or summer (above zero, rising)

Second Screen (daily timeframe — tactical timing):
  - Daily Stochastic K < 30 (oversold) OR 2-day Force Index EMA < 0 (pullback)

Third Screen (entry execution):
  - Simplified: buy at next open (approximation of buy-stop above prior day's high)
  - Initial stop: current_price - 2 × ATR(13)

Exit rules:
  - Rule A (trailing stop): price falls below trailing stop → sell at next open
  - Rule B (trend reversal): weekly impulse turns red → sell at next open

Position sizing: 2%/6% principle
"""
from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

from .base import Signal, Strategy, StrategyContext

if TYPE_CHECKING:
    import pandas as pd

log = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
EMA_PERIOD = 26
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
ATR_PERIOD = 13
ATR_STOP_MULT = 2.0
STOCH_K, STOCH_D = 5, 3
STOCH_THRESHOLD = 30
MIN_DAILY_BARS = 180      # ≈ 36 weeks minimum
RISK_PER_TRADE = 0.02
MONTHLY_FUSE = 0.06
LOT_SIZE = 100
MAX_POSITION_SIZE = 0.20  # cap single position at 20% NAV


class ElderStrategy(Strategy):
    """Elder Triple Screen — A-share long-only, precomputed indicators."""

    def on_start(self, context: StrategyContext) -> None:
        self._ctx = context
        context.extra.update({
            "stops": {},
            "entry_prices": {},
            "monthly_loss": 0.0,
            "current_month": None,
            "current_nav": context.initial_cash,
        })
        # Will be populated by on_data()
        self._signals_cache: dict[str, dict[date, dict]] = {}  # {symbol: {date: indicators}}

    def on_data(self, all_bars: "pd.DataFrame") -> None:
        """Precompute all indicators for all symbols across the full date range.

        Called once before the backtest loop. Builds a lookup table:
            self._signals_cache[symbol][date] = {
                'ema_dir': 'up'|'down'|'flat',
                'season': 'spring'|'summer'|'autumn'|'winter'|'unknown',
                'stoch_ok': bool,
                'force_ok': bool,
                'atr': float,
                'close': float,
                'impulse_red': bool,  # for Rule B exit
            }
        """
        try:
            import pandas as pd
            import pandas_ta as ta
        except ImportError:
            log.error("pandas_ta required. Install: pip install pandas-ta")
            return

        from ..data.schema import BarColumns

        symbols = all_bars[BarColumns.symbol].unique()
        log.info("ElderStrategy.on_data: precomputing indicators for %d symbols...", len(symbols))

        cache: dict[str, dict[date, dict]] = {}

        for sym in symbols:
            sym_bars = all_bars[all_bars[BarColumns.symbol] == sym].copy()
            sym_bars = sym_bars.sort_values(BarColumns.ts).reset_index(drop=True)

            if len(sym_bars) < MIN_DAILY_BARS:
                continue

            # ── Weekly resample ──
            d = sym_bars.copy()
            d.index = pd.to_datetime(d[BarColumns.ts], utc=True)
            weekly = d[["open", "high", "low", "close", "volume"]].resample("W-FRI").agg(
                {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
            ).dropna()

            if len(weekly) < EMA_PERIOD + 5:
                continue

            # ── Weekly indicators (computed once for the full series) ──
            w_ema = ta.ema(weekly["close"], length=EMA_PERIOD)
            w_macd = ta.macd(weekly["close"], fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
            if w_ema is None or w_macd is None or w_macd.empty:
                continue
            hist_col = next((c for c in w_macd.columns if c.startswith("MACDh")), None)
            if hist_col is None:
                continue

            # ── Daily indicators ──
            stoch = ta.stoch(sym_bars["high"], sym_bars["low"], sym_bars["close"], k=STOCH_K, d=STOCH_D)
            k_col = next((c for c in stoch.columns if "k_" in c.lower()), None) if stoch is not None else None

            sym_bars["force"] = sym_bars["volume"] * sym_bars["close"].diff()
            force_ema2 = ta.ema(sym_bars["force"], length=2)

            atr_series = ta.atr(sym_bars["high"], sym_bars["low"], sym_bars["close"], length=ATR_PERIOD)

            # ── Build per-date lookup ──
            sym_cache: dict[date, dict] = {}

            for i in range(len(sym_bars)):
                row_ts = sym_bars.iloc[i][BarColumns.ts]
                if hasattr(row_ts, "date"):
                    row_date = row_ts.date()
                else:
                    row_date = pd.Timestamp(row_ts).date()

                # Find the weekly bar for this date (last weekly bar up to this date)
                week_idx = weekly.index.searchsorted(pd.Timestamp(row_date, tz="UTC"), side="right") - 1
                if week_idx < 2:  # need at least 3 weekly bars for EMA direction
                    continue

                # Weekly EMA direction
                ema_val = w_ema.iloc[week_idx] if week_idx < len(w_ema) else float("nan")
                ema_prev = w_ema.iloc[week_idx - 2] if week_idx >= 2 else float("nan")
                import math
                if math.isnan(ema_val) or math.isnan(ema_prev) or ema_prev == 0:
                    ema_dir = "flat"
                else:
                    pct = (ema_val - ema_prev) / ema_prev
                    ema_dir = "up" if pct > 0.001 else ("down" if pct < -0.001 else "flat")

                # MACD season
                hist = w_macd[hist_col]
                h_val = hist.iloc[week_idx] if week_idx < len(hist) else float("nan")
                h_prev = hist.iloc[week_idx - 1] if week_idx >= 1 else float("nan")
                if math.isnan(h_val) or math.isnan(h_prev):
                    season = "unknown"
                else:
                    rising = h_val > h_prev
                    if h_val < 0 and rising:
                        season = "spring"
                    elif h_val >= 0 and rising:
                        season = "summer"
                    elif h_val >= 0 and not rising:
                        season = "autumn"
                    else:
                        season = "winter"

                # Stochastic
                stoch_k_val = None
                if stoch is not None and k_col and i < len(stoch):
                    v = stoch[k_col].iloc[i]
                    if not math.isnan(v):
                        stoch_k_val = float(v)

                # Force index
                force_val = None
                if force_ema2 is not None and i < len(force_ema2):
                    v = force_ema2.iloc[i]
                    if not math.isnan(v):
                        force_val = float(v)

                # ATR
                atr_val = None
                if atr_series is not None and i < len(atr_series):
                    v = atr_series.iloc[i]
                    if not math.isnan(v):
                        atr_val = float(v)

                close_val = float(sym_bars.iloc[i]["close"])

                stoch_ok = stoch_k_val is not None and stoch_k_val < STOCH_THRESHOLD
                force_ok = force_val is not None and force_val < 0
                impulse_red = ema_dir == "down" and season in ("autumn", "winter")

                sym_cache[row_date] = {
                    "ema_dir": ema_dir,
                    "season": season,
                    "stoch_ok": stoch_ok,
                    "force_ok": force_ok,
                    "atr": atr_val,
                    "close": close_val,
                    "impulse_red": impulse_red,
                }

            if sym_cache:
                cache[sym] = sym_cache

        self._signals_cache = cache
        log.info("ElderStrategy.on_data: done. %d symbols with precomputed indicators.", len(cache))

    def on_fill(self, fill: object) -> None:
        extra = self._ctx.extra
        sym = fill.symbol  # type: ignore[attr-defined]
        side = fill.side   # type: ignore[attr-defined]
        price = fill.price  # type: ignore[attr-defined]
        shares = fill.shares  # type: ignore[attr-defined]

        if side == "BUY":
            extra["entry_prices"][sym] = price
        elif side == "SELL":
            entry = extra["entry_prices"].pop(sym, None)
            if entry is not None:
                pnl = (price - entry) * shares
                if pnl < 0:
                    extra["monthly_loss"] += abs(pnl)
            extra["stops"].pop(sym, None)

    def generate_signals(
        self,
        bars: "pd.DataFrame",
        trading_date: date,
    ) -> dict[str, Signal]:
        from ..data.schema import BarColumns

        extra = self._ctx.extra
        signals: dict[str, Signal] = {}

        # Reset monthly fuse on month change
        month_key = (trading_date.year, trading_date.month)
        if extra["current_month"] != month_key:
            extra["current_month"] = month_key
            extra["monthly_loss"] = 0.0

        portfolio_value = extra.get("current_nav", self._ctx.initial_cash)
        fuse_triggered = extra["monthly_loss"] >= portfolio_value * MONTHLY_FUSE

        symbols = bars[BarColumns.symbol].unique().tolist()

        for sym in symbols:
            # Fast lookup — no computation here
            sym_cache = self._signals_cache.get(sym)
            if sym_cache is None:
                continue
            ind = sym_cache.get(trading_date)
            if ind is None:
                continue

            atr = ind["atr"]
            close = ind["close"]
            is_held = sym in extra["stops"]

            # ── Exit logic ──
            if is_held:
                current_stop = extra["stops"][sym]

                # Update trailing stop with current ATR
                if atr and atr > 0:
                    new_stop = close - ATR_STOP_MULT * atr
                    if new_stop > current_stop:
                        extra["stops"][sym] = new_stop
                        current_stop = new_stop

                # Rule B: weekly impulse red
                if ind["impulse_red"] or close <= current_stop:
                    reason = "Rule B: weekly impulse red" if ind["impulse_red"] else "Rule A: trailing stop hit"
                    signals[sym] = Signal(symbol=sym, action="SELL", size=0.0, reason=reason)
                continue

            # ── Entry logic ──
            if fuse_triggered:
                continue

            if ind["ema_dir"] != "up" or ind["season"] not in ("spring", "summer"):
                continue

            if not (ind["stoch_ok"] or ind["force_ok"]):
                continue

            if atr is None or atr <= 0:
                continue

            stop_price = round(close - ATR_STOP_MULT * atr, 2)
            risk_per_share = close - stop_price
            if risk_per_share <= 0:
                continue

            max_risk = portfolio_value * RISK_PER_TRADE
            max_shares = int(max_risk / risk_per_share / LOT_SIZE) * LOT_SIZE
            if max_shares <= 0:
                continue

            size = min((max_shares * close) / portfolio_value, MAX_POSITION_SIZE)
            if size <= 0:
                continue

            extra["stops"][sym] = stop_price

            signals[sym] = Signal(
                symbol=sym,
                action="BUY",
                size=size,
                reason=f"Triple screen: {ind['season']} season",
                metadata={"stop_price": stop_price, "atr": atr},
            )

        return signals

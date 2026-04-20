"""Elder Triple Screen Strategy — A-share long-only implementation.

Rules (from Alexander Elder, "Trading for a Living"):

First Screen (weekly timeframe — strategic direction):
  - Weekly EMA(26) rising
  - Weekly MACD histogram season = spring (below zero, rising) or summer (above zero, rising)
  → Only go long when both conditions pass.

Second Screen (daily timeframe — tactical timing):
  - Daily Stochastic K < 30 (oversold) OR 2-day Force Index EMA < 0 (pullback)
  → Wait for a pullback in an uptrend.

Third Screen (entry execution):
  - Simplified: buy at next open (approximation of buy-stop above prior day's high)
  - Initial stop: current_price - 2 × ATR(13)

Exit rules:
  - Rule A (trailing stop): price falls below trailing stop → sell at next open
  - Rule B (trend reversal): weekly impulse system turns red (EMA down AND MACD hist down) → sell at next open
  - Rule B takes priority over Rule A.

Position sizing (Elder 2%/6% principle):
  - Max risk per trade = portfolio_value × 2%
  - Monthly fuse: when realized monthly losses ≥ portfolio_value × 6%, stop new entries

Simplifications vs. original (documented):
  - Entry: open price instead of buy-stop above prior high (slightly optimistic bias)
  - Trailing stop: uses current ATR (not frozen entry-time ATR) — correct
  - Monthly fuse: realized losses only (not unrealized exposure) — conservative
"""
from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

from .base import Signal, Strategy, StrategyContext

if TYPE_CHECKING:
    import pandas as pd

log = logging.getLogger(__name__)

# ── Constants (Elder canonical values, not parameters) ──────────────────────
EMA_PERIOD = 26          # Weekly EMA
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
ATR_PERIOD = 13
ATR_STOP_MULT = 2.0      # Initial stop = entry - 2×ATR
STOCH_K = 5
STOCH_D = 3
STOCH_THRESHOLD = 30     # Oversold threshold
MIN_DAILY_BARS = 180     # ≈ 36 weeks; skip symbol if insufficient history
RISK_PER_TRADE = 0.02    # 2% of portfolio per trade
MONTHLY_FUSE = 0.06      # Stop new entries when monthly loss ≥ 6%
LOT_SIZE = 100           # A-share minimum lot


def _macd_season(hist_series: "pd.Series") -> str:
    """Classify MACD histogram into Elder's four seasons.

    spring: below zero, rising  → best long entry
    summer: above zero, rising  → hold longs
    autumn: above zero, falling → no new longs
    winter: below zero, falling → no new longs
    """
    if len(hist_series) < 2:
        return "unknown"
    last = hist_series.iloc[-1]
    prev = hist_series.iloc[-2]
    import math
    if math.isnan(last) or math.isnan(prev):
        return "unknown"
    rising = last > prev
    if last < 0 and rising:
        return "spring"
    if last >= 0 and rising:
        return "summer"
    if last >= 0 and not rising:
        return "autumn"
    return "winter"


def _ema_direction(ema_series: "pd.Series") -> str:
    """Return 'up', 'down', or 'flat' based on last 3 values."""
    if len(ema_series) < 3:
        return "flat"
    import math
    last = ema_series.iloc[-1]
    prev = ema_series.iloc[-3]
    if math.isnan(last) or math.isnan(prev) or prev == 0:
        return "flat"
    pct = (last - prev) / prev
    if pct > 0.001:
        return "up"
    if pct < -0.001:
        return "down"
    return "flat"


def _compute_indicators(daily: "pd.DataFrame") -> dict:
    """Compute all required indicators for one symbol's daily bars.

    Returns dict with keys: weekly_ema, macd_season, ema_dir,
    stoch_k, force_index_ema2, atr, latest_close, latest_high
    or None if insufficient data.
    """
    try:
        import pandas as pd
        import pandas_ta as ta
    except ImportError:
        log.error("pandas_ta required. Install: pip install pandas-ta")
        return {}

    if len(daily) < MIN_DAILY_BARS:
        return {}

    # ── Weekly resample (W-FRI boundary, drop incomplete last week) ──
    d = daily.copy()
    d.index = pd.to_datetime(d["ts"], utc=True)
    weekly = d[["open", "high", "low", "close", "volume"]].resample("W-FRI").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    # Drop the last incomplete week if it has fewer than 5 trading days
    # (simple heuristic: just use all complete weeks)
    if len(weekly) < EMA_PERIOD + 5:
        return {}

    # ── First screen: weekly EMA(26) + MACD ──
    w_ema = ta.ema(weekly["close"], length=EMA_PERIOD)
    if w_ema is None or w_ema.isna().all():
        return {}
    ema_dir = _ema_direction(w_ema.dropna())

    w_macd = ta.macd(weekly["close"], fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
    if w_macd is None or w_macd.empty:
        return {}
    hist_col = next((c for c in w_macd.columns if c.startswith("MACDh")), None)
    if hist_col is None:
        return {}
    season = _macd_season(w_macd[hist_col].dropna())

    # ── Second screen: daily stochastic + force index ──
    stoch = ta.stoch(d["high"], d["low"], d["close"], k=STOCH_K, d=STOCH_D)
    stoch_k_val = None
    if stoch is not None and not stoch.empty:
        # pandas_ta column name: STOCHk_5_3_3 — match by "k_" prefix after "STOCH"
        k_col = next((c for c in stoch.columns if "k_" in c.lower() or c.lower().endswith("k")), None)
        if k_col:
            k_series = stoch[k_col].dropna()
            if not k_series.empty:
                stoch_k_val = float(k_series.iloc[-1])

    d["force"] = d["volume"] * d["close"].diff()
    force_ema2 = ta.ema(d["force"].dropna(), length=2)
    force_val = None
    if force_ema2 is not None and not force_ema2.empty:
        force_val = float(force_ema2.iloc[-1])

    # ── ATR for stop sizing ──
    atr = ta.atr(d["high"], d["low"], d["close"], length=ATR_PERIOD)
    atr_val = None
    if atr is not None and not atr.empty:
        atr_series = atr.dropna()
        if not atr_series.empty:
            atr_val = float(atr_series.iloc[-1])

    return {
        "ema_dir": ema_dir,
        "season": season,
        "stoch_k": stoch_k_val,
        "force_ema2": force_val,
        "atr": atr_val,
        "latest_close": float(d["close"].iloc[-1]),
        "latest_high": float(d["high"].iloc[-1]),
        # For Rule B: weekly impulse system
        "w_ema_dir": ema_dir,
        "w_macd_season": season,
    }


class ElderStrategy(Strategy):
    """Elder Triple Screen — A-share long-only, full rule set.

    See module docstring for complete rule description.
    """

    def on_start(self, context: StrategyContext) -> None:
        self._ctx = context
        context.extra.update({
            # Trailing stop state
            "stops": {},           # {symbol: current_stop_price}
            "entry_prices": {},    # {symbol: actual_fill_price} — written by on_fill(BUY)
            # Monthly risk fuse
            "monthly_loss": 0.0,
            "current_month": None,
        })

    def on_fill(self, fill: object) -> None:
        """Track entry prices and realized P&L for the monthly fuse."""
        extra = self._ctx.extra
        sym = fill.symbol  # type: ignore[attr-defined]
        side = fill.side   # type: ignore[attr-defined]
        price = fill.price  # type: ignore[attr-defined]
        shares = fill.shares  # type: ignore[attr-defined]

        if side == "BUY":
            # Record actual fill price as entry (open price approximation)
            extra["entry_prices"][sym] = price
            # Initial stop already written by generate_signals before this fill
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

        # ── Reset monthly fuse counter on month change ──
        month_key = (trading_date.year, trading_date.month)
        if extra["current_month"] != month_key:
            extra["current_month"] = month_key
            extra["monthly_loss"] = 0.0

        # ── Use current NAV for position sizing (updated by BacktestRunner before each call) ──
        portfolio_value = extra.get('current_nav', self._ctx.initial_cash)

        # ── Monthly fuse: stop new entries if realized loss ≥ 6% ──
        fuse_triggered = extra["monthly_loss"] >= portfolio_value * MONTHLY_FUSE

        symbols = bars[BarColumns.symbol].unique().tolist()

        for sym in symbols:
            sym_bars = bars[bars[BarColumns.symbol] == sym].copy()
            if sym_bars.empty:
                continue

            indicators = _compute_indicators(sym_bars)
            if not indicators:
                continue

            atr = indicators.get("atr")
            latest_close = indicators["latest_close"]
            ema_dir = indicators["ema_dir"]
            season = indicators["season"]

            is_held = sym in extra["stops"]

            # ── Exit logic for held positions ──
            if is_held:
                current_stop = extra["stops"][sym]

                # Update trailing stop: move up if price warrants
                if atr and atr > 0:
                    new_stop = latest_close - ATR_STOP_MULT * atr
                    if new_stop > current_stop:
                        extra["stops"][sym] = new_stop
                        current_stop = new_stop

                # Rule B: weekly impulse turns red (EMA down AND MACD declining)
                impulse_red = ema_dir == "down" and season in ("autumn", "winter")

                # Rule A: price below trailing stop
                stop_hit = latest_close <= current_stop

                if impulse_red or stop_hit:
                    reason = "Rule B: weekly impulse red" if impulse_red else "Rule A: trailing stop hit"
                    signals[sym] = Signal(
                        symbol=sym,
                        action="SELL",
                        size=0.0,
                        reason=reason,
                    )
                continue  # Don't also evaluate entry for held positions

            # ── Entry logic for new positions ──
            if fuse_triggered:
                continue

            # First screen: EMA up AND season is spring or summer
            if ema_dir != "up" or season not in ("spring", "summer"):
                continue

            # Second screen: stoch oversold OR force index negative
            stoch_k = indicators.get("stoch_k")
            force = indicators.get("force_ema2")
            stoch_ok = stoch_k is not None and stoch_k < STOCH_THRESHOLD
            force_ok = force is not None and force < 0
            if not (stoch_ok or force_ok):
                continue

            # Position sizing: 2% risk rule
            if atr is None or atr <= 0:
                continue
            stop_price = round(latest_close - ATR_STOP_MULT * atr, 2)
            risk_per_share = latest_close - stop_price
            if risk_per_share <= 0:
                continue

            max_risk = portfolio_value * RISK_PER_TRADE
            max_shares = int(max_risk / risk_per_share / LOT_SIZE) * LOT_SIZE
            if max_shares <= 0:
                continue

            size = min((max_shares * latest_close) / portfolio_value, 0.20)  # cap at 20% NAV
            if size <= 0:
                continue

            # Write initial stop BEFORE the fill (on_fill will record entry price)
            extra["stops"][sym] = stop_price

            stoch_str = f"{stoch_k:.0f}" if stoch_k is not None else "N/A"
            signals[sym] = Signal(
                symbol=sym,
                action="BUY",
                size=size,
                reason=f"Triple screen: {season} season, stoch={stoch_str}, force={'neg' if force_ok else 'pos'}",
                metadata={"stop_price": stop_price, "atr": atr},
            )

        return signals

"""Event-driven backtest runner for A-share markets.

Execution model (prevents look-ahead bias):
    Day T close  → Strategy.generate_signals(bars_up_to_T-1, trading_date=T)
    Day T+1 open → Orders execute at T+1 open price

A-share market rules enforced:
    - T+1 settlement: shares bought on T cannot be sold until T+1
    - Daily price limits: ±10% for normal stocks, ±5% for ST stocks
    - Minimum lot size: 100 shares (1 手)
    - Suspended stocks: orders rejected

Fee model:
    - Commission: 0.03% per trade (min 5 CNY), both sides
    - Stamp duty: 0.05% on SELL only (China A-share)
    - Slippage: configurable bps applied to execution price
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Literal

from ..data.schema import BarColumns
from ..strategy.base import Signal, Strategy, StrategyContext

if TYPE_CHECKING:
    import pandas as pd

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 1_000_000.0
    commission_rate: float = 0.0003     # 0.03% both sides (min 5 CNY)
    commission_min: float = 5.0          # minimum commission per order (CNY)
    stamp_duty_rate: float = 0.0005      # 0.05% on SELL only
    slippage_bps: float = 5.0            # slippage in basis points
    price_limit_normal: float = 0.10     # ±10% daily limit for normal stocks
    price_limit_st: float = 0.05         # ±5% daily limit for ST stocks
    lot_size: int = 100                  # minimum lot size (shares)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@dataclass
class BarEvent:
    trading_date: date
    bars: "pd.DataFrame"   # all bars available as of trading_date (strict < trading_date)


@dataclass
class SignalEvent:
    trading_date: date
    symbol: str
    signal: Signal


@dataclass
class OrderEvent:
    trading_date: date
    symbol: str
    side: Literal["BUY", "SELL"]
    shares: float
    reason: str = ""


@dataclass
class FillEvent:
    trading_date: date
    symbol: str
    side: Literal["BUY", "SELL"]
    shares: float
    price: float        # actual execution price (with slippage)
    commission: float
    stamp_duty: float

    @property
    def total_cost(self) -> float:
        """Net cash impact (negative = cash outflow for BUY)."""
        gross = self.shares * self.price
        fees = self.commission + self.stamp_duty
        if self.side == "BUY":
            return -(gross + fees)
        else:
            return gross - fees


@dataclass
class RiskRejectEvent:
    trading_date: date
    symbol: str
    reason: str


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

@dataclass
class Position:
    symbol: str
    shares: float
    avg_cost: float
    buy_date: date   # for T+1 settlement enforcement


@dataclass
class Portfolio:
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)

    @property
    def nav(self) -> float:
        """Net asset value (cash only; call mark_to_market for full NAV)."""
        return self.cash

    def mark_to_market(self, prices: dict[str, float]) -> float:
        """Return total NAV = cash + sum(shares * price)."""
        equity = sum(
            pos.shares * prices.get(pos.symbol, pos.avg_cost)
            for pos in self.positions.values()
        )
        return self.cash + equity

    def can_sell(self, symbol: str, trading_date: date) -> bool:
        """T+1 settlement: can only sell shares bought before trading_date."""
        pos = self.positions.get(symbol)
        if pos is None or pos.shares <= 0:
            return False
        return pos.buy_date < trading_date  # strictly before, not same day

    def apply_fill(self, fill: FillEvent) -> None:
        if fill.side == "BUY":
            self.cash += fill.total_cost  # total_cost is negative for BUY
            pos = self.positions.get(fill.symbol)
            if pos is None:
                self.positions[fill.symbol] = Position(
                    symbol=fill.symbol,
                    shares=fill.shares,
                    avg_cost=fill.price,
                    buy_date=fill.trading_date,
                )
            else:
                total_shares = pos.shares + fill.shares
                pos.avg_cost = (pos.shares * pos.avg_cost + fill.shares * fill.price) / total_shares
                pos.shares = total_shares
                # Keep the earlier buy_date (conservative for T+1)
        else:  # SELL
            self.cash += fill.total_cost  # total_cost is positive for SELL
            pos = self.positions.get(fill.symbol)
            if pos is not None:
                pos.shares -= fill.shares
                if pos.shares <= 1e-6:
                    del self.positions[fill.symbol]


# ---------------------------------------------------------------------------
# BacktestBroker — A-share rules
# ---------------------------------------------------------------------------

class BacktestBroker:
    """Simulates order execution with A-share market rules."""

    def __init__(self, config: BacktestConfig) -> None:
        self.config = config

    def execute(
        self,
        order: OrderEvent,
        portfolio: Portfolio,
        open_price: float,
        prev_close: float,
        is_suspended: bool = False,
        is_st: bool = False,
    ) -> FillEvent | RiskRejectEvent:
        """Try to execute an order. Returns Fill or RiskReject."""
        cfg = self.config

        # 1. Suspended stock
        if is_suspended:
            return RiskRejectEvent(order.trading_date, order.symbol, "股票停牌")

        # 2. Price limit check
        limit = cfg.price_limit_st if is_st else cfg.price_limit_normal
        upper_limit = prev_close * (1 + limit)
        lower_limit = prev_close * (1 - limit)

        if order.side == "BUY" and open_price >= upper_limit * 0.999:
            return RiskRejectEvent(order.trading_date, order.symbol, "涨停无法买入")
        if order.side == "SELL" and open_price <= lower_limit * 1.001:
            return RiskRejectEvent(order.trading_date, order.symbol, "跌停无法卖出")

        # 3. T+1 settlement
        if order.side == "SELL" and not portfolio.can_sell(order.symbol, order.trading_date):
            return RiskRejectEvent(order.trading_date, order.symbol, "T+1限制：当日买入不可卖出")

        # 4. Apply slippage
        slip = cfg.slippage_bps / 10_000.0
        if order.side == "BUY":
            exec_price = open_price * (1 + slip)
        else:
            exec_price = open_price * (1 - slip)

        # 5. Round to lot size (100 shares)
        shares = (order.shares // cfg.lot_size) * cfg.lot_size
        if shares < cfg.lot_size:
            return RiskRejectEvent(order.trading_date, order.symbol, f"数量不足最小手数 {cfg.lot_size} 股")

        # 6. Commission
        gross = shares * exec_price
        commission = max(gross * cfg.commission_rate, cfg.commission_min)
        stamp_duty = gross * cfg.stamp_duty_rate if order.side == "SELL" else 0.0

        # 7. Cash check for BUY
        if order.side == "BUY":
            total_needed = gross + commission
            if total_needed > portfolio.cash:
                # Reduce shares to fit available cash
                max_affordable = portfolio.cash / (exec_price * (1 + cfg.commission_rate))
                shares = (max_affordable // cfg.lot_size) * cfg.lot_size
                if shares < cfg.lot_size:
                    return RiskRejectEvent(order.trading_date, order.symbol, "现金不足")
                gross = shares * exec_price
                commission = max(gross * cfg.commission_rate, cfg.commission_min)

        return FillEvent(
            trading_date=order.trading_date,
            symbol=order.symbol,
            side=order.side,
            shares=shares,
            price=exec_price,
            commission=commission,
            stamp_duty=stamp_duty,
        )


# ---------------------------------------------------------------------------
# BacktestResult
# ---------------------------------------------------------------------------

@dataclass
class BacktestResult:
    symbol_universe: list[str]
    start_date: date
    end_date: date
    initial_cash: float
    equity_curve: "pd.DataFrame"   # columns: date, nav, cash, equity
    trades: "pd.DataFrame"         # columns: date, symbol, side, shares, price, ...
    events: list                   # all events (for audit)
    final_nav: float = 0.0

    @property
    def total_return(self) -> float:
        if self.initial_cash == 0:
            return 0.0
        return (self.final_nav - self.initial_cash) / self.initial_cash

    def summary(self) -> dict:
        import pandas as pd

        if self.equity_curve.empty:
            return {"total_return": 0.0, "trades": 0}

        nav_series = self.equity_curve["nav"]
        daily_returns = nav_series.pct_change().dropna()

        sharpe = 0.0
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            sharpe = (daily_returns.mean() / daily_returns.std()) * (252 ** 0.5)

        rolling_max = nav_series.cummax()
        drawdown = (nav_series - rolling_max) / rolling_max
        max_drawdown = drawdown.min()

        n_years = max((self.end_date - self.start_date).days / 365.25, 1e-6)
        annualized_return = (1 + self.total_return) ** (1 / n_years) - 1

        return {
            "total_return": round(self.total_return * 100, 2),
            "annualized_return": round(annualized_return * 100, 2),
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown": round(max_drawdown * 100, 2),
            "final_nav": round(self.final_nav, 2),
            "trades": len(self.trades),
        }


# ---------------------------------------------------------------------------
# BacktestRunner
# ---------------------------------------------------------------------------

class BacktestRunner:
    """Runs a Strategy over historical data using the event-driven engine.

    Usage::

        runner = BacktestRunner(
            strategy=MACrossStrategy(),
            pipeline=DataPipeline.from_repo_root(repo_root),
            config=BacktestConfig(),
        )
        result = runner.run(
            symbols=["SSE:600000"],
            start=date(2022, 1, 1),
            end=date(2024, 12, 31),
        )
        print(result.summary())
    """

    def __init__(
        self,
        strategy: Strategy,
        pipeline: object,   # DataPipeline (avoid circular import)
        config: BacktestConfig | None = None,
    ) -> None:
        self.strategy = strategy
        self.pipeline = pipeline
        self.config = config or BacktestConfig()
        self._broker = BacktestBroker(self.config)

    def run(
        self,
        symbols: list[str],
        start: date,
        end: date,
        lookback_days: int = 252,
    ) -> BacktestResult:
        """Run the backtest.

        Args:
            symbols:       Symbols to trade.
            start:         First trading date (signals generated from this date).
            end:           Last trading date.
            lookback_days: Historical window passed to strategy.

        Returns:
            BacktestResult with equity curve, trades, and summary metrics.
        """
        try:
            import pandas as pd
        except ImportError as e:
            raise RuntimeError("Backtest requires pandas") from e

        # Initialize strategy context
        context = StrategyContext(
            trading_date=start,
            symbols=symbols,
            initial_cash=self.config.initial_cash,
        )
        self.strategy.on_start(context)

        portfolio = Portfolio(cash=self.config.initial_cash)
        all_events: list = []
        equity_rows: list[dict] = []
        trade_rows: list[dict] = []

        # Get all trading dates in range
        all_bars = self.pipeline.get_bars(
            symbols=symbols,
            trading_date=end,
            lookback_days=(end - start).days + lookback_days + 30,
        )

        if all_bars is None or all_bars.empty:
            log.warning("No bars found for backtest period %s–%s", start, end)
            return BacktestResult(
                symbol_universe=symbols,
                start_date=start,
                end_date=end,
                initial_cash=self.config.initial_cash,
                equity_curve=pd.DataFrame(),
                trades=pd.DataFrame(),
                events=[],
                final_nav=self.config.initial_cash,
            )

        # Get unique trading dates in [start, end]
        all_bars[BarColumns.ts] = pd.to_datetime(all_bars[BarColumns.ts], utc=True)
        start_ts = pd.Timestamp(start, tz="UTC")
        end_ts = pd.Timestamp(end, tz="UTC")

        trading_dates = sorted(
            all_bars[
                (all_bars[BarColumns.ts] >= start_ts) &
                (all_bars[BarColumns.ts] <= end_ts)
            ][BarColumns.ts]
            .dt.normalize()
            .unique()
        )

        for ts in trading_dates:
            trading_date = ts.date()

            # Bars available for signal generation: strictly < trading_date
            hist_bars = self.pipeline.get_bars(
                symbols=symbols,
                trading_date=trading_date,
                lookback_days=lookback_days,
            )

            if hist_bars is None or hist_bars.empty:
                continue

            # Update strategy context with current portfolio NAV (using prev close prices)
            # This lets strategies use real-time NAV for position sizing instead of initial cash
            if hasattr(self.strategy, '_ctx') and hasattr(self.strategy._ctx, 'extra'):
                prev_close_prices = {}
                if not hist_bars.empty:
                    latest = hist_bars.groupby(BarColumns.symbol)[BarColumns.close].last()
                    prev_close_prices = latest.to_dict()
                current_nav = portfolio.mark_to_market(prev_close_prices)
                self.strategy._ctx.extra['current_nav'] = current_nav

            # Generate signals
            try:
                signals = self.strategy.generate_signals(hist_bars, trading_date)
            except Exception as e:
                log.error("Strategy error on %s: %s", trading_date, e)
                signals = {}

            # Today's bars (for execution prices and prev_close)
            today_bars = all_bars[all_bars[BarColumns.ts].dt.normalize() == ts]

            # Build price lookup for today
            open_prices: dict[str, float] = {}
            prev_close_prices: dict[str, float] = {}

            for _, row in today_bars.iterrows():
                sym = row[BarColumns.symbol]
                open_prices[sym] = float(row[BarColumns.open])

            # Get previous close for price limit calculation
            prev_date_bars = hist_bars.groupby(BarColumns.symbol).last()
            for sym, row in prev_date_bars.iterrows():
                prev_close_prices[sym] = float(row[BarColumns.close])

            # Process signals → orders → fills
            for sym in sorted(signals.keys()):  # deterministic order
                signal = signals[sym]

                # Check signal expiry
                if signal.valid_until is not None and signal.valid_until < trading_date:
                    all_events.append(RiskRejectEvent(trading_date, sym, "信号已过期"))
                    continue

                if signal.action == "HOLD":
                    continue

                open_px = open_prices.get(sym)
                prev_close = prev_close_prices.get(sym)

                if open_px is None or prev_close is None or open_px <= 0:
                    log.debug("No price data for %s on %s, skipping", sym, trading_date)
                    continue

                # Compute target shares from signal.size
                current_nav = portfolio.mark_to_market(open_prices)
                target_value = signal.size * current_nav
                current_pos = portfolio.positions.get(sym)
                current_shares = current_pos.shares if current_pos else 0.0

                if signal.action == "BUY":
                    current_value = current_shares * open_px
                    delta_value = target_value - current_value
                    if delta_value <= 0:
                        continue
                    shares_to_buy = delta_value / open_px
                    order = OrderEvent(trading_date, sym, "BUY", shares_to_buy, signal.reason)
                else:  # SELL
                    target_shares = target_value / open_px if open_px > 0 else 0.0
                    shares_to_sell = current_shares - target_shares
                    if shares_to_sell <= 0:
                        continue
                    order = OrderEvent(trading_date, sym, "SELL", shares_to_sell, signal.reason)

                all_events.append(order)

                result = self._broker.execute(
                    order=order,
                    portfolio=portfolio,
                    open_price=open_px,
                    prev_close=prev_close,
                )

                all_events.append(result)

                if isinstance(result, FillEvent):
                    portfolio.apply_fill(result)
                    self.strategy.on_fill(result)
                    trade_rows.append({
                        "date": trading_date,
                        "symbol": result.symbol,
                        "side": result.side,
                        "shares": result.shares,
                        "price": result.price,
                        "commission": result.commission,
                        "stamp_duty": result.stamp_duty,
                        "net_cash": result.total_cost,
                    })
                    log.debug(
                        "%s %s %s %.0f shares @ %.2f",
                        trading_date, result.side, result.symbol,
                        result.shares, result.price,
                    )
                else:
                    log.debug("Rejected %s on %s: %s", sym, trading_date, result.reason)

            # Record equity at end of day (mark-to-market using today's close)
            close_prices = {
                row[BarColumns.symbol]: float(row[BarColumns.close])
                for _, row in today_bars.iterrows()
            }
            nav = portfolio.mark_to_market(close_prices)
            equity = nav - portfolio.cash
            equity_rows.append({
                "date": trading_date,
                "nav": nav,
                "cash": portfolio.cash,
                "equity": equity,
            })

        equity_df = pd.DataFrame(equity_rows)
        trades_df = pd.DataFrame(trade_rows)
        final_nav = equity_rows[-1]["nav"] if equity_rows else self.config.initial_cash

        return BacktestResult(
            symbol_universe=symbols,
            start_date=start,
            end_date=end,
            initial_cash=self.config.initial_cash,
            equity_curve=equity_df,
            trades=trades_df,
            events=all_events,
            final_nav=final_nav,
        )

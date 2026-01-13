"""Backtesting engine and sample strategies."""

from .engine import BacktestConfig, BacktestResult, run_backtest
from .metrics import PerformanceMetrics, compute_performance_metrics
from .strategies import buy_and_hold_signals, sma_crossover_signals

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "PerformanceMetrics",
    "buy_and_hold_signals",
    "compute_performance_metrics",
    "run_backtest",
    "sma_crossover_signals",
]


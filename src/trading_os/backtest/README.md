# Backtest building blocks for strategies and analytics.
# Input: market bars and strategy signals; output: equity curves, trades, and metrics.
# Update rule: when files change here, update this README; update parent index if scope changes.

- `__init__.py`: package exports for backtest utilities.
- `dca.py`: dollar-cost averaging backtest and metrics helpers.
- `engine.py`: minimal long-only backtest engine (signal-driven).
- `metrics.py`: performance metrics for backtests.
- `multi_factor_strategy.py`: multi-factor strategy helpers.
- `strategies.py`: sample signal generators (SMA, buy-and-hold).

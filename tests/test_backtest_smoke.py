import pytest


pd = pytest.importorskip("pandas")


def test_backtest_sma_smoke():
    from trading_os.backtest.engine import BacktestConfig, run_backtest
    from trading_os.backtest.strategies import sma_crossover_signals
    from trading_os.data.schema import BarColumns, Exchange
    from trading_os.data.sources.synthetic_source import make_daily_bars

    bars = make_daily_bars("TEST", exchange=Exchange.NASDAQ).head(50)
    res = run_backtest(
        bars,
        signals_fn=lambda b: sma_crossover_signals(b, fast=5, slow=20),
        config=BacktestConfig(initial_cash=10_000.0),
    )

    assert len(res.equity_curve) == len(bars)
    assert BarColumns.ts in res.equity_curve.columns
    assert "equity" in res.equity_curve.columns


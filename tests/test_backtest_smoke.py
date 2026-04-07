"""Smoke tests for the new event-driven backtest runner."""
import pytest
from datetime import date

pd = pytest.importorskip("pandas")


def test_backtest_ma_smoke():
    """MA crossover strategy runs end-to-end with synthetic data."""
    from trading_os.backtest.runner import BacktestConfig, BacktestRunner
    from trading_os.data.lake import LocalDataLake
    from trading_os.data.pipeline import DataPipeline
    from trading_os.data.schema import Adjustment, Exchange, Timeframe
    from trading_os.data.sources.synthetic_source import make_daily_bars
    from trading_os.strategy.builtin import MACrossStrategy
    import tempfile, pathlib

    # Build in-memory lake with synthetic data
    with tempfile.TemporaryDirectory() as tmp:
        lake = LocalDataLake(pathlib.Path(tmp))
        bars = make_daily_bars("600000", exchange=Exchange.SSE)
        lake.write_bars_parquet(
            bars, exchange=Exchange.SSE, timeframe=Timeframe.D1,
            adjustment=Adjustment.QFQ, source="synthetic",
        )
        lake.init()
        pipeline = DataPipeline(lake)

        strategy = MACrossStrategy(fast=5, slow=20)
        runner = BacktestRunner(
            strategy=strategy,
            pipeline=pipeline,
            config=BacktestConfig(initial_cash=1_000_000.0),
        )

        # Synthetic data starts 2020-01-01; use a window within that range
        result = runner.run(
            symbols=["SSE:600000"],
            start=date(2020, 1, 20),
            end=date(2020, 2, 20),
        )

        assert result.final_nav > 0
        assert isinstance(result.trades, pd.DataFrame)
        assert isinstance(result.equity_curve, pd.DataFrame)
        summary = result.summary()
        assert "total_return" in summary


def test_backtest_bh_smoke():
    """Buy-and-hold strategy runs without errors."""
    from trading_os.backtest.runner import BacktestRunner
    from trading_os.data.lake import LocalDataLake
    from trading_os.data.pipeline import DataPipeline
    from trading_os.data.schema import Adjustment, Exchange, Timeframe
    from trading_os.data.sources.synthetic_source import make_daily_bars
    from trading_os.strategy.builtin import BuyAndHoldStrategy
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as tmp:
        lake = LocalDataLake(pathlib.Path(tmp))
        bars = make_daily_bars("000001", exchange=Exchange.SZSE)
        lake.write_bars_parquet(
            bars, exchange=Exchange.SZSE, timeframe=Timeframe.D1,
            adjustment=Adjustment.QFQ, source="synthetic",
        )
        lake.init()
        pipeline = DataPipeline(lake)

        runner = BacktestRunner(strategy=BuyAndHoldStrategy(), pipeline=pipeline)
        result = runner.run(
            symbols=["SZSE:000001"],
            start=date(2020, 1, 15),
            end=date(2020, 2, 15),
        )
        assert result.final_nav > 0


def test_risk_manager_rejects_oversized_position():
    """RiskManager rejects signals that exceed position limits."""
    from datetime import date
    from trading_os.backtest.runner import Portfolio
    from trading_os.risk.manager import RiskConfig, RiskManager
    from trading_os.strategy.base import Signal

    risk = RiskManager(RiskConfig(max_position_pct=0.10))
    portfolio = Portfolio(cash=1_000_000.0)
    prices = {"SSE:600000": 15.0}

    # 5% — should approve
    sig_ok = Signal("SSE:600000", "BUY", size=0.05)
    assert risk.check_signal(sig_ok, portfolio, prices).approved

    # 15% — should reject
    sig_big = Signal("SSE:600000", "BUY", size=0.15)
    decision = risk.check_signal(sig_big, portfolio, prices)
    assert not decision.approved
    assert "position_limit" in decision.check_name


def test_event_log_append_only():
    """EventLog writes and reads events correctly."""
    import tempfile, pathlib
    from trading_os.journal.event_log import EventLog

    with tempfile.TemporaryDirectory() as tmp:
        log = EventLog(pathlib.Path(tmp) / "test.db")
        log.write("FILL", {"symbol": "SSE:600000", "shares": 100})
        log.write("RISK_REJECT", {"symbol": "SSE:000001", "reason": "涨停"})

        rows = log.query()
        assert len(rows) == 2
        assert rows[0]["event_type"] == "FILL"
        assert rows[1]["event_type"] == "RISK_REJECT"

        fills = log.query(event_type="FILL")
        assert len(fills) == 1
        assert fills[0]["payload"]["symbol"] == "SSE:600000"

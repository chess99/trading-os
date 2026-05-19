"""Smoke tests for the new event-driven backtest runner."""
from datetime import date

import pytest

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
            bars, timeframe=Timeframe.D1,
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
            bars, timeframe=Timeframe.D1,
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


def test_backtest_includes_end_date_trading_session():
    """The final trading date in [start, end] must still execute."""
    import pathlib
    import tempfile

    from trading_os.backtest.runner import BacktestConfig, BacktestRunner
    from trading_os.data.lake import LocalDataLake
    from trading_os.data.pipeline import DataPipeline
    from trading_os.data.schema import Adjustment, Exchange, Timeframe
    from trading_os.risk.manager import RiskConfig
    from trading_os.strategy.builtin import BuyAndHoldStrategy

    with tempfile.TemporaryDirectory() as tmp:
        lake = LocalDataLake(pathlib.Path(tmp))
        bars = pd.DataFrame(
            {
                "symbol": ["SSE:600000"] * 3,
                "ts": pd.date_range("2024-01-02", periods=3, freq="B", tz="UTC"),
                "open": [10.0, 10.2, 10.4],
                "high": [10.1, 10.3, 10.5],
                "low": [9.9, 10.1, 10.3],
                "close": [10.0, 10.2, 10.4],
                "volume": [1_000_000.0] * 3,
            }
        )
        lake.write_bars_parquet(
            bars,
            timeframe=Timeframe.D1,
            adjustment=Adjustment.QFQ,
            source="synthetic",
        )
        lake.init()

        result = BacktestRunner(
            strategy=BuyAndHoldStrategy(),
            pipeline=DataPipeline(lake),
            config=BacktestConfig(
                risk=RiskConfig(max_position_pct=1.0, max_sector_pct=1.0),
            ),
        ).run(
            symbols=["SSE:600000"],
            start=date(2024, 1, 4),
            end=date(2024, 1, 4),
        )

        assert len(result.trades) == 1
        assert result.trades.iloc[0]["date"] == date(2024, 1, 4)


def test_backtest_applies_risk_manager_before_execution():
    """Backtest should reject oversized positions just like paper trading."""
    import pathlib
    import tempfile

    from trading_os.backtest.runner import BacktestConfig, BacktestRunner
    from trading_os.data.lake import LocalDataLake
    from trading_os.data.pipeline import DataPipeline
    from trading_os.data.schema import Adjustment, Exchange, Timeframe
    from trading_os.data.sources.synthetic_source import make_daily_bars
    from trading_os.risk.manager import RiskConfig
    from trading_os.strategy.builtin import BuyAndHoldStrategy

    with tempfile.TemporaryDirectory() as tmp:
        lake = LocalDataLake(pathlib.Path(tmp))
        bars = make_daily_bars("600000", exchange=Exchange.SSE)
        lake.write_bars_parquet(
            bars,
            timeframe=Timeframe.D1,
            adjustment=Adjustment.QFQ,
            source="synthetic",
        )
        lake.init()

        result = BacktestRunner(
            strategy=BuyAndHoldStrategy(),
            pipeline=DataPipeline(lake),
            config=BacktestConfig(
                initial_cash=1_000_000.0,
                risk=RiskConfig(max_position_pct=0.10),
            ),
        ).run(
            symbols=["SSE:600000"],
            start=date(2020, 1, 2),
            end=date(2020, 1, 10),
        )

        assert result.trades.empty
        assert result.summary()["risk_rejects"] >= 1

"""Smoke tests for ResearchStore-backed backtest and paper runners."""

from __future__ import annotations

from datetime import date

import pytest

pd = pytest.importorskip("pandas")


def _bars(symbol: str, start: str = "2024-01-02", periods: int = 40):
    ts = pd.date_range(start, periods=periods, freq="B", tz="UTC")
    base = pd.Series(range(periods), dtype="float64")
    return pd.DataFrame(
        {
            "symbol": [symbol] * periods,
            "ts": ts,
            "open": 10.0 + base * 0.1,
            "high": 10.2 + base * 0.1,
            "low": 9.8 + base * 0.1,
            "close": 10.1 + base * 0.1,
            "volume": [1_000_000.0] * periods,
        }
    )


def _bar_provider(tmp_path, *symbols: str):
    from trading_os.backtest.data import ResearchStoreBarProvider
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    for symbol in symbols:
        store.write_bars(_bars(symbol), source="synthetic_fixture")
    return ResearchStoreBarProvider(store)


def test_backtest_ma_smoke_uses_research_store_bars(tmp_path):
    from trading_os.backtest.runner import BacktestConfig, BacktestRunner
    from trading_os.strategy.builtin import MACrossStrategy

    provider = _bar_provider(tmp_path, "SSE:600000")
    result = BacktestRunner(
        strategy=MACrossStrategy(fast=5, slow=20),
        bar_provider=provider,
        config=BacktestConfig(initial_cash=1_000_000.0),
    ).run(
        symbols=["SSE:600000"],
        start=date(2024, 1, 22),
        end=date(2024, 2, 20),
    )

    assert result.final_nav > 0
    assert isinstance(result.trades, pd.DataFrame)
    assert isinstance(result.equity_curve, pd.DataFrame)
    assert "total_return" in result.summary()


def test_backtest_signal_history_excludes_trading_date(tmp_path):
    from trading_os.backtest.data import ResearchStoreBarProvider
    from trading_os.backtest.runner import BacktestConfig, BacktestRunner
    from trading_os.risk.manager import RiskConfig
    from trading_os.strategy.base import Signal, Strategy

    class CapturingStrategy(Strategy):
        def __init__(self) -> None:
            self.observed: list[tuple[date, date]] = []

        def generate_signals(self, bars, trading_date):
            self.observed.append((trading_date, bars["ts"].dt.date.max()))
            return {"SSE:600000": Signal("SSE:600000", "BUY", size=0.1)}

    provider: ResearchStoreBarProvider = _bar_provider(tmp_path, "SSE:600000")
    strategy = CapturingStrategy()
    BacktestRunner(
        strategy=strategy,
        bar_provider=provider,
        config=BacktestConfig(risk=RiskConfig(max_position_pct=1.0, max_sector_pct=1.0)),
    ).run(
        symbols=["SSE:600000"],
        start=date(2024, 1, 5),
        end=date(2024, 1, 8),
        lookback_days=10,
    )

    assert strategy.observed
    assert all(seen < trading_date for trading_date, seen in strategy.observed)


def test_backtest_includes_end_date_trading_session(tmp_path):
    from trading_os.backtest.runner import BacktestConfig, BacktestRunner
    from trading_os.risk.manager import RiskConfig
    from trading_os.strategy.builtin import BuyAndHoldStrategy

    provider = _bar_provider(tmp_path, "SSE:600000")
    result = BacktestRunner(
        strategy=BuyAndHoldStrategy(),
        bar_provider=provider,
        config=BacktestConfig(risk=RiskConfig(max_position_pct=1.0, max_sector_pct=1.0)),
    ).run(
        symbols=["SSE:600000"],
        start=date(2024, 1, 4),
        end=date(2024, 1, 4),
    )

    assert len(result.trades) == 1
    assert result.trades.iloc[0]["date"] == date(2024, 1, 4)


def test_backtest_applies_risk_manager_before_execution(tmp_path):
    from trading_os.backtest.runner import BacktestConfig, BacktestRunner
    from trading_os.risk.manager import RiskConfig
    from trading_os.strategy.builtin import BuyAndHoldStrategy

    provider = _bar_provider(tmp_path, "SSE:600000")
    result = BacktestRunner(
        strategy=BuyAndHoldStrategy(),
        bar_provider=provider,
        config=BacktestConfig(
            initial_cash=1_000_000.0,
            risk=RiskConfig(max_position_pct=0.10),
        ),
    ).run(
        symbols=["SSE:600000"],
        start=date(2024, 1, 4),
        end=date(2024, 1, 10),
    )

    assert result.trades.empty
    assert result.summary()["risk_rejects"] >= 1


def test_risk_manager_rejects_oversized_position():
    from trading_os.backtest.runner import Portfolio
    from trading_os.risk.manager import RiskConfig, RiskManager
    from trading_os.strategy.base import Signal

    risk = RiskManager(RiskConfig(max_position_pct=0.10))
    portfolio = Portfolio(cash=1_000_000.0)
    prices = {"SSE:600000": 15.0}

    assert risk.check_signal(Signal("SSE:600000", "BUY", size=0.05), portfolio, prices).approved
    decision = risk.check_signal(Signal("SSE:600000", "BUY", size=0.15), portfolio, prices)
    assert not decision.approved
    assert "position_limit" in decision.check_name


def test_paper_runner_writes_event_log_with_research_store_bars(tmp_path):
    from trading_os.journal.event_log import EventLog
    from trading_os.paper.runner import PaperConfig, PaperRunner
    from trading_os.risk.manager import RiskConfig
    from trading_os.strategy.builtin import BuyAndHoldStrategy

    event_log = EventLog(tmp_path / "paper.db")
    session = PaperRunner(
        strategy=BuyAndHoldStrategy(),
        bar_provider=_bar_provider(tmp_path, "SSE:600000"),
        config=PaperConfig(
            confirm_mode="auto",
            risk=RiskConfig(max_position_pct=1.0, max_sector_pct=1.0),
        ),
        event_log=event_log,
    ).run(
        symbols=["SSE:600000"],
        start=date(2024, 1, 4),
        end=date(2024, 1, 8),
    )

    assert session.total_fills >= 1
    assert event_log.query(event_type="SESSION_START")
    assert event_log.query(event_type="FILL")


def test_event_log_append_only(tmp_path):
    from trading_os.journal.event_log import EventLog

    log = EventLog(tmp_path / "test.db")
    log.write("FILL", {"symbol": "SSE:600000", "shares": 100})
    log.write("RISK_REJECT", {"symbol": "SSE:000001", "reason": "涨停"})

    rows = log.query()
    assert len(rows) == 2
    assert rows[0]["event_type"] == "FILL"
    assert rows[1]["event_type"] == "RISK_REJECT"
    assert log.query(event_type="FILL")[0]["payload"]["symbol"] == "SSE:600000"

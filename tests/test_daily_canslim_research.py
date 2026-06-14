from __future__ import annotations

import json
from datetime import date

import pytest

pd = pytest.importorskip("pandas")


def test_detects_simple_pivot_and_buy_zone():
    from trading_os.research.technical import detect_technical_setup

    bars = pd.DataFrame(
        [
            {"symbol": "SSE:600000", "ts": f"2026-05-{day:02d}", "close": close, "volume": 1000}
            for day, close in enumerate(
                [10.0, 10.5, 11.0, 10.8, 10.6, 11.2, 11.5, 11.3, 11.8, 12.0],
                start=1,
            )
        ]
    )

    setup = detect_technical_setup("SSE:600000", bars)

    assert setup["symbol"] == "SSE:600000"
    assert setup["pivot_price"] == 12.0
    assert setup["buy_zone_high"] == 12.6
    assert setup["stop_loss"] == 11.04
    assert setup["volume_baseline"] == 1000.0
    assert setup["status"] == "wait_for_breakout"


@pytest.mark.parametrize(
    "symbol,bars",
    [
        ("SSE:600000", None),
        ("", pd.DataFrame([{"symbol": "SSE:600000", "ts": "2026-05-01", "close": 10.0}])),
        ("SSE:600000", pd.DataFrame()),
        ("SSE:600000", pd.DataFrame([{"ts": "2026-05-01", "close": 10.0}])),
        ("SSE:600000", pd.DataFrame([{"symbol": "SSE:600000", "ts": "2026-05-01"}])),
        ("SSE:600000", pd.DataFrame([{"symbol": "SSE:600001", "ts": "2026-05-01", "close": 10.0}])),
    ],
)
def test_detects_insufficient_bars_for_missing_inputs(symbol, bars):
    from trading_os.research.technical import detect_technical_setup

    setup = detect_technical_setup(symbol, bars)

    assert setup == {
        "symbol": symbol,
        "status": "insufficient_bars",
        "pivot_price": None,
        "buy_zone_high": None,
        "stop_loss": None,
        "volume_baseline": None,
    }


def test_detects_setup_without_volume_column_uses_zero_baseline():
    from trading_os.research.technical import detect_technical_setup

    bars = pd.DataFrame(
        [
            {"symbol": "SSE:600000", "ts": "2026-05-02", "close": 10.12345},
            {"symbol": "SSE:600000", "ts": "2026-05-01", "close": 11.56789},
        ]
    )

    setup = detect_technical_setup("SSE:600000", bars)

    assert setup["pivot_price"] == 11.5679
    assert setup["buy_zone_high"] == 12.1463
    assert setup["stop_loss"] == 10.6425
    assert setup["volume_baseline"] == 0.0


def test_detects_insufficient_bars_when_ts_column_missing():
    from trading_os.research.technical import detect_technical_setup

    bars = pd.DataFrame([{"symbol": "SSE:600000", "close": 10.0, "volume": 1000}])

    setup = detect_technical_setup("SSE:600000", bars)

    assert setup == {
        "symbol": "SSE:600000",
        "status": "insufficient_bars",
        "pivot_price": None,
        "buy_zone_high": None,
        "stop_loss": None,
        "volume_baseline": None,
    }


def test_detects_insufficient_bars_when_no_valid_close_remains():
    from trading_os.research.technical import detect_technical_setup

    bars = pd.DataFrame(
        [
            {"symbol": "SSE:600000", "ts": "2026-05-01", "close": "bad", "volume": 1000},
            {"symbol": "SSE:600000", "ts": "2026-05-02", "close": None, "volume": 2000},
        ]
    )

    setup = detect_technical_setup("SSE:600000", bars)

    assert setup == {
        "symbol": "SSE:600000",
        "status": "insufficient_bars",
        "pivot_price": None,
        "buy_zone_high": None,
        "stop_loss": None,
        "volume_baseline": None,
    }


def test_detects_setup_with_bad_volume_values_uses_valid_volume_baseline():
    from trading_os.research.technical import detect_technical_setup

    bars = pd.DataFrame(
        [
            {"symbol": "SSE:600000", "ts": "2026-05-01", "close": 10.0, "volume": "bad"},
            {"symbol": "SSE:600000", "ts": "2026-05-02", "close": 12.0, "volume": 2000},
            {"symbol": "SSE:600000", "ts": "2026-05-03", "close": 11.0, "volume": None},
            {"symbol": "SSE:600000", "ts": "2026-05-04", "close": 11.5, "volume": 3000},
        ]
    )

    setup = detect_technical_setup("SSE:600000", bars)

    assert setup["status"] == "wait_for_breakout"
    assert setup["pivot_price"] == 12.0
    assert setup["volume_baseline"] == 2500.0


def test_detects_setup_with_no_valid_volume_values_uses_zero_baseline():
    from trading_os.research.technical import detect_technical_setup

    bars = pd.DataFrame(
        [
            {"symbol": "SSE:600000", "ts": "2026-05-01", "close": 10.0, "volume": "bad"},
            {"symbol": "SSE:600000", "ts": "2026-05-02", "close": 12.0, "volume": None},
        ]
    )

    setup = detect_technical_setup("SSE:600000", bars)

    assert setup["status"] == "wait_for_breakout"
    assert setup["pivot_price"] == 12.0
    assert setup["volume_baseline"] == 0.0


def test_detects_flat_base_candidate_and_breakout_volume_confirmation():
    from trading_os.research.technical import detect_technical_setup

    closes = [10.0, 10.2, 10.4, 10.1, 10.5, 10.3, 10.6, 10.4, 10.7, 10.5] * 4
    closes[-1] = 10.95
    rows = []
    for index, close in enumerate(closes, start=1):
        rows.append(
            {
                "symbol": "SSE:600000",
                "ts": f"2026-05-{index:02d}",
                "close": close,
                "volume": 1000 if index < len(closes) else 1800,
            }
        )
    bars = pd.DataFrame(rows)

    setup = detect_technical_setup("SSE:600000", bars)

    assert setup["status"] == "actionable_watch"
    assert setup["setup_type"] == "flat_base_candidate"
    assert setup["base_length_days"] == 40
    assert setup["base_depth_pct"] < 0.1
    assert setup["breakout_volume_confirmed"] is True
    assert setup["volume_multiple"] >= 1.4


def test_decision_board_emits_one_decision_per_strict_candidate():
    from trading_os.research.decisions import build_canslim_decisions

    candidates = [
        {
            "symbol": "SSE:600000",
            "classification": "strict_canslim_candidate",
            "score": 9.0,
            "signals": {"relative_strength_top20pct": True},
        },
        {
            "symbol": "SSE:600001",
            "classification": "provisional_research_queue",
            "score": 8.0,
            "signals": {},
        },
    ]
    setups = {
        "SSE:600000": {
            "status": "wait_for_breakout",
            "pivot_price": 12.0,
            "buy_zone_high": 12.6,
            "stop_loss": 11.04,
        }
    }

    decisions = build_canslim_decisions(
        candidates, setups, as_of="2026-06-12", source_run_id="screen-1"
    )

    assert [d["symbol"] for d in decisions] == ["SSE:600000"]
    assert decisions[0]["decision"] == "wait_for_breakout"
    assert decisions[0]["pivot_price"] == 12.0
    assert decisions[0]["source_run_id"] == "screen-1"


def test_decision_board_marks_incomplete_setup_research_only_and_ignores_non_strict():
    from trading_os.research.decisions import build_canslim_decisions

    candidates = [
        {
            "symbol": "SSE:600000",
            "classification": "strict_canslim_candidate",
            "score": 9.0,
        },
        {
            "symbol": "SSE:600001",
            "classification": "provisional_research_queue",
            "score": 8.0,
        },
    ]
    setups = {
        "SSE:600000": {
            "status": "wait_for_breakout",
            "pivot_price": 12.0,
            "buy_zone_high": 12.6,
            "stop_loss": None,
        },
        "SSE:600001": {
            "status": "wait_for_breakout",
            "pivot_price": 20.0,
            "buy_zone_high": 21.0,
            "stop_loss": 18.4,
        },
    }

    decisions = build_canslim_decisions(
        candidates, setups, as_of="2026-06-12", source_run_id="screen-1"
    )

    assert decisions == [
        {
            "symbol": "SSE:600000",
            "as_of": "2026-06-12",
            "decision": "research_only",
            "confidence": 0.45,
            "reason": "strict CANSLIM evidence but technical setup is incomplete",
            "score": 9.0,
            "pivot_price": 12.0,
            "buy_zone_high": 12.6,
            "stop_loss": None,
            "source_run_id": "screen-1",
        }
    ]


@pytest.mark.parametrize(
    "pivot_price,stop_loss",
    [
        ("bad", 11.04),
        (float("nan"), 11.04),
        (12.0, "bad"),
        (12.0, float("nan")),
    ],
)
def test_decision_board_marks_nonnumeric_or_nan_setup_research_only(
    pivot_price, stop_loss
):
    from trading_os.research.decisions import build_canslim_decisions

    candidates = [
        {
            "symbol": "SSE:600000",
            "classification": "strict_canslim_candidate",
            "score": 9.0,
        }
    ]
    setups = {
        "SSE:600000": {
            "status": "wait_for_breakout",
            "pivot_price": pivot_price,
            "buy_zone_high": 12.6,
            "stop_loss": stop_loss,
        }
    }

    decisions = build_canslim_decisions(
        candidates, setups, as_of="2026-06-12", source_run_id="screen-1"
    )

    assert decisions[0]["decision"] == "research_only"
    assert decisions[0]["confidence"] == 0.45
    assert (
        decisions[0]["reason"]
        == "strict CANSLIM evidence but technical setup is incomplete"
    )


def test_decision_board_skips_missing_or_blank_symbol_without_exception():
    from trading_os.research.decisions import build_canslim_decisions

    candidates = [
        {"classification": "strict_canslim_candidate", "score": 9.0},
        {
            "symbol": "   ",
            "classification": "strict_canslim_candidate",
            "score": 8.0,
        },
        {
            "symbol": "SSE:600000",
            "classification": "strict_canslim_candidate",
            "score": 7.0,
        },
    ]
    setups = {
        "SSE:600000": {
            "status": "wait_for_breakout",
            "pivot_price": 12.0,
            "buy_zone_high": 12.6,
            "stop_loss": 11.04,
        }
    }

    decisions = build_canslim_decisions(
        candidates, setups, as_of="2026-06-12", source_run_id="screen-1"
    )

    assert [decision["symbol"] for decision in decisions] == ["SSE:600000"]


def test_decision_board_duplicate_strict_candidates_emit_one_decision():
    from trading_os.research.decisions import build_canslim_decisions

    candidates = [
        {
            "symbol": "SSE:600000",
            "classification": "strict_canslim_candidate",
            "score": 9.0,
        },
        {
            "symbol": "SSE:600000",
            "classification": "strict_canslim_candidate",
            "score": 7.5,
        },
    ]
    setups = {
        "SSE:600000": {
            "status": "wait_for_breakout",
            "pivot_price": 12.0,
            "buy_zone_high": 12.6,
            "stop_loss": 11.04,
        }
    }

    decisions = build_canslim_decisions(
        candidates, setups, as_of="2026-06-12", source_run_id="screen-1"
    )

    assert len(decisions) == 1
    assert decisions[0]["symbol"] == "SSE:600000"
    assert decisions[0]["score"] == 9.0


class DailyProvider:
    name = "daily-fixture"
    capabilities = {"universe", "quote_snapshot_eod", "bars_daily"}

    def __init__(self) -> None:
        self.bars_calls: list[list[str]] = []

    def fetch_universe(self, as_of):
        return pd.DataFrame(
            [
                {"symbol": "SSE:600000", "name": "A", "is_st": False, "is_active": True},
                {"symbol": "SSE:600001", "name": "B", "is_st": False, "is_active": True},
                {"symbol": "SSE:600002", "name": "C", "is_st": False, "is_active": True},
            ]
        )

    def fetch_quote_snapshot(self, as_of):
        return pd.DataFrame(
            [
                {"symbol": "SSE:600000", "name": "A", "close": 12.0, "amount": 30_000_000.0},
                {"symbol": "SSE:600001", "name": "B", "close": 10.0, "amount": 30_000_000.0},
                {"symbol": "SSE:600002", "name": "C", "close": 9.0, "amount": 30_000_000.0},
            ]
        )

    def fetch_bars(self, symbols, start, end, adjustment):
        self.bars_calls.append(list(symbols))
        rows = []
        multipliers = {"SSE:600000": 0.02, "SSE:600001": 0.02, "SSE:600002": 0.001}
        for symbol in symbols:
            for idx, ts in enumerate(pd.bdate_range(start=start, end=end, inclusive="left")):
                rows.append(
                    {
                        "symbol": symbol,
                        "ts": ts,
                        "close": 10.0 + idx * multipliers.get(symbol, 0.01),
                        "volume": 1_000_000.0,
                    }
                )
        return pd.DataFrame(rows)


class DailyProviderWithHolidayGap(DailyProvider):
    def fetch_bars(self, symbols, start, end, adjustment):
        full = super().fetch_bars(symbols, start, end, adjustment)
        gap = pd.Timestamp("2026-01-01")
        return full[pd.to_datetime(full["ts"]).dt.normalize() != gap].reset_index(drop=True)


def test_daily_canslim_research_processes_all_strict_candidates(tmp_path, monkeypatch):
    import trading_os.research.recipes as recipes
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_daily_canslim_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.35,
                    "roe": 0.22,
                    "positive_quarters": 8,
                },
                {
                    "symbol": "SSE:600001",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.40,
                    "roe": 0.24,
                    "positive_quarters": 8,
                },
                {
                    "symbol": "SSE:600002",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.05,
                    "roe": 0.21,
                    "positive_quarters": 8,
                },
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    monkeypatch.setattr(recipes, "repo_root", lambda: tmp_path)
    provider = DailyProvider()
    hub = DataHub(store, provider=provider)

    result = run_daily_canslim_research(hub, requested_as_of=date(2026, 6, 13))

    assert result.recipe == "daily_canslim_research"
    assert result.manifest["requested_as_of"] == "2026-06-13"
    assert result.manifest["effective_as_of"] == "2026-06-12"
    assert result.manifest["strict_candidates_processed"] == 2
    assert result.manifest["decisions_total"] == 2
    assert (result.run.path / "report.md").exists()
    assert (result.run.path / "tables" / "decisions.csv").exists()
    assert (result.run.path / "tables" / "watchlist_state.csv").exists()
    assert (result.run.path / "tables" / "technical_setups.csv").exists()
    assert provider.bars_calls[-1] == ["SSE:600000", "SSE:600001"]
    assert not store.get_decisions(as_of=date(2026, 6, 12)).empty
    assert not store.get_watchlist_state(as_of=date(2026, 6, 12)).empty
    assert not store.get_technical_setups(as_of=date(2026, 6, 12)).empty


def test_daily_canslim_research_refreshes_existing_watchlist_symbols(tmp_path, monkeypatch):
    import trading_os.research.recipes as recipes
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_daily_canslim_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.35,
                    "roe": 0.22,
                    "positive_quarters": 8,
                }
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    store.write_watchlist_state(
        [
            {
                "symbol": "SSE:600099",
                "as_of": "2026-06-11",
                "status": "watching",
                "pivot_price": 9.0,
                "buy_zone_high": 9.45,
                "stop_loss": 8.28,
            }
        ]
    )
    monkeypatch.setattr(recipes, "repo_root", lambda: tmp_path)
    provider = DailyProvider()
    hub = DataHub(store, provider=provider)

    result = run_daily_canslim_research(hub, requested_as_of=date(2026, 6, 13))

    assert result.manifest["active_watchlist_symbols_processed"] == 1
    assert "SSE:600099" in provider.bars_calls[-1]
    assert {decision["symbol"] for decision in result.candidates} == {
        "SSE:600000",
        "SSE:600099",
    }
    watchlist_decision = next(
        decision for decision in result.candidates if decision["symbol"] == "SSE:600099"
    )
    assert watchlist_decision["decision"] == "wait_for_breakout"
    setups = store.get_technical_setups(as_of=date(2026, 6, 12))
    assert "SSE:600099" in set(setups["symbol"])


def test_daily_canslim_research_uses_latest_watchlist_status_by_as_of(
    tmp_path, monkeypatch
):
    import trading_os.research.recipes as recipes
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_daily_canslim_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.35,
                    "roe": 0.22,
                    "positive_quarters": 8,
                }
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    store.write_watchlist_state(
        [
            {
                "symbol": "SSE:600099",
                "as_of": "2026-06-12",
                "status": "invalidated",
            }
        ]
    )
    store.write_watchlist_state(
        [
            {
                "symbol": "SSE:600099",
                "as_of": "2026-06-11",
                "status": "watching",
                "pivot_price": 9.0,
                "buy_zone_high": 9.45,
                "stop_loss": 8.28,
            }
        ]
    )
    monkeypatch.setattr(recipes, "repo_root", lambda: tmp_path)
    provider = DailyProvider()
    hub = DataHub(store, provider=provider)

    result = run_daily_canslim_research(hub, requested_as_of=date(2026, 6, 13))

    assert result.manifest["active_watchlist_symbols_processed"] == 0
    assert "SSE:600099" not in provider.bars_calls[-1]
    assert "SSE:600099" not in {decision["symbol"] for decision in result.candidates}


def test_daily_canslim_research_does_not_promote_existing_candidate_without_deep_research(
    tmp_path, monkeypatch
):
    import trading_os.research.recipes as recipes
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_daily_canslim_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.35,
                    "roe": 0.22,
                    "positive_quarters": 8,
                }
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    store.write_watchlist_state(
        [
            {
                "symbol": "SSE:600099",
                "as_of": "2026-06-11",
                "status": "candidate",
                "last_decision": "research_only",
            }
        ]
    )
    monkeypatch.setattr(recipes, "repo_root", lambda: tmp_path)
    provider = DailyProvider()
    hub = DataHub(store, provider=provider)

    result = run_daily_canslim_research(hub, requested_as_of=date(2026, 6, 13))

    assert result.manifest["active_watchlist_symbols_processed"] == 0
    assert "SSE:600099" not in provider.bars_calls[-1]
    decision = next(row for row in result.candidates if row["symbol"] == "SSE:600099")
    assert decision["decision"] == "research_only"
    assert (
        decision["reason"]
        == "existing candidate requires fresh strict screen and complete deep research"
    )
    state = {
        row["symbol"]: row
        for row in store.get_watchlist_state(as_of=date(2026, 6, 12)).to_dict("records")
    }
    assert state["SSE:600099"]["status"] == "candidate"
    assert state["SSE:600099"]["last_decision"] == "research_only"
    assert pd.isna(state["SSE:600099"]["pivot_price"])


def test_daily_canslim_research_continues_when_strict_bars_have_partial_gap(tmp_path, monkeypatch):
    import trading_os.research.recipes as recipes
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_daily_canslim_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.35,
                    "roe": 0.22,
                    "positive_quarters": 8,
                },
                {
                    "symbol": "SSE:600001",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.40,
                    "roe": 0.24,
                    "positive_quarters": 8,
                },
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    monkeypatch.setattr(recipes, "repo_root", lambda: tmp_path)
    provider = DailyProviderWithHolidayGap()
    hub = DataHub(store, provider=provider)

    result = run_daily_canslim_research(hub, requested_as_of=date(2026, 6, 13))

    assert result.manifest["strict_candidates_processed"] == 2
    assert result.manifest["decisions_total"] == 2
    assert {decision["symbol"] for decision in result.candidates} == {
        "SSE:600000",
        "SSE:600001",
    }
    assert (result.run.path / "report.md").exists()
    assert (result.run.path / "tables" / "technical_setups.csv").exists()
    assert not store.get_decisions(as_of=date(2026, 6, 12)).empty
    assert not store.get_watchlist_state(as_of=date(2026, 6, 12)).empty
    assert not store.get_technical_setups(as_of=date(2026, 6, 12)).empty


def test_daily_canslim_research_writes_human_report(tmp_path, monkeypatch):
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_daily_canslim_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.35,
                    "roe": 0.22,
                    "positive_quarters": 8,
                }
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    import trading_os.research.recipes as recipes

    monkeypatch.setattr(recipes, "repo_root", lambda: tmp_path)
    hub = DataHub(store, provider=DailyProvider())

    result = run_daily_canslim_research(hub, requested_as_of=date(2026, 6, 13))

    report_path = tmp_path / "artifacts" / "research" / "daily-canslim-20260612.md"
    assert report_path.exists()
    assert str(report_path) == result.manifest["human_report"]


def test_daily_canslim_research_exports_watchlist_state_json(tmp_path, monkeypatch):
    import trading_os.research.recipes as recipes
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_daily_canslim_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.35,
                    "roe": 0.22,
                    "positive_quarters": 8,
                }
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    monkeypatch.setattr(recipes, "repo_root", lambda: tmp_path)
    hub = DataHub(store, provider=DailyProvider())

    result = run_daily_canslim_research(hub, requested_as_of=date(2026, 6, 13))

    state_path = tmp_path / "artifacts" / "watchlist" / "state.json"
    assert state_path.exists()
    payload = json.loads(state_path.read_text(encoding="utf-8"))

    assert payload["as_of"] == "2026-06-12"
    assert payload["generated_from_run_id"] == result.run.run_id
    assert result.manifest["watchlist_state_json"] == str(state_path)
    assert payload["watchlist_state"][0]["symbol"] == "SSE:600000"
    assert payload["watchlist_state"][0]["status"] == "watching"


def test_daily_canslim_research_runs_company_research_for_every_strict(
    tmp_path, monkeypatch
):
    import trading_os.research.recipes as recipes
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_daily_canslim_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.35,
                    "roe": 0.22,
                    "positive_quarters": 8,
                },
                {
                    "symbol": "SSE:600001",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.40,
                    "roe": 0.24,
                    "positive_quarters": 8,
                },
                {
                    "symbol": "SSE:600002",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.05,
                    "roe": 0.21,
                    "positive_quarters": 8,
                },
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    monkeypatch.setattr(recipes, "repo_root", lambda: tmp_path)
    hub = DataHub(store, provider=DailyProvider())

    result = run_daily_canslim_research(hub, requested_as_of=date(2026, 6, 13))

    deep_research_runs = result.manifest["deep_research_runs"]
    assert len(deep_research_runs) == 2
    assert all(item["status"] == "ok" for item in deep_research_runs)
    assert all(item["template"] == "canslim" for item in deep_research_runs)
    assert {item["symbol"] for item in deep_research_runs} == {
        "SSE:600000",
        "SSE:600001",
    }
    assert all((tmp_path / item["report"]).exists() for item in deep_research_runs)
    assert "## Deep Research Runs" in result.report
    assert all(item["report"] in result.report for item in deep_research_runs)


def test_daily_canslim_research_records_failed_company_research_and_continues(
    tmp_path, monkeypatch
):
    import trading_os.research.recipes as recipes
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_daily_canslim_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.35,
                    "roe": 0.22,
                    "positive_quarters": 8,
                },
                {
                    "symbol": "SSE:600001",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.40,
                    "roe": 0.24,
                    "positive_quarters": 8,
                },
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    monkeypatch.setattr(recipes, "repo_root", lambda: tmp_path)
    original_run_company_research = recipes.run_company_research

    def flaky_run_company_research(hub, symbol, *, as_of, template):
        if symbol == "SSE:600001":
            raise RuntimeError("company research unavailable")
        return original_run_company_research(
            hub,
            symbol,
            as_of=as_of,
            template=template,
        )

    monkeypatch.setattr(recipes, "run_company_research", flaky_run_company_research)
    hub = DataHub(store, provider=DailyProvider())

    result = run_daily_canslim_research(hub, requested_as_of=date(2026, 6, 13))

    assert (result.run.path / "manifest.json").exists()
    assert (result.run.path / "report.md").exists()
    deep_research_runs = result.manifest["deep_research_runs"]
    assert {item["symbol"]: item["status"] for item in deep_research_runs} == {
        "SSE:600000": "ok",
        "SSE:600001": "failed",
    }
    failed = next(item for item in deep_research_runs if item["status"] == "failed")
    assert failed == {
        "symbol": "SSE:600001",
        "template": "canslim",
        "status": "failed",
        "error_type": "RuntimeError",
        "error": "company research unavailable",
    }
    assert "SSE:600001 status=failed error_type=RuntimeError" in result.report
    assert result.manifest["strict_candidates_processed"] == 2
    assert result.manifest["decisions_total"] == 2
    decisions = {decision["symbol"]: decision for decision in result.candidates}
    assert decisions["SSE:600001"]["decision"] == "research_only"
    assert decisions["SSE:600001"]["confidence"] == 0.35
    assert decisions["SSE:600001"]["reason"] == "strict CANSLIM evidence but deep research failed"
    watchlist = store.get_watchlist_state(as_of=date(2026, 6, 12)).to_dict("records")
    state = {row["symbol"]: row for row in watchlist}
    assert state["SSE:600001"]["status"] == "candidate"
    assert state["SSE:600001"]["last_decision"] == "research_only"
    assert pd.isna(state["SSE:600001"]["pivot_price"])


def test_daily_canslim_research_downgrades_incomplete_company_research(
    tmp_path, monkeypatch
):
    import trading_os.research.recipes as recipes
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_daily_canslim_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.35,
                    "roe": 0.22,
                    "positive_quarters": 8,
                },
                {
                    "symbol": "SSE:600001",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.40,
                    "roe": 0.24,
                    "positive_quarters": 8,
                },
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    monkeypatch.setattr(recipes, "repo_root", lambda: tmp_path)
    original_run_company_research = recipes.run_company_research

    def incomplete_run_company_research(hub, symbol, *, as_of, template):
        result = original_run_company_research(
            hub,
            symbol,
            as_of=as_of,
            template=template,
        )
        if symbol == "SSE:600001":
            result.manifest["complete"] = False
        return result

    monkeypatch.setattr(recipes, "run_company_research", incomplete_run_company_research)
    hub = DataHub(store, provider=DailyProvider())

    result = run_daily_canslim_research(hub, requested_as_of=date(2026, 6, 13))

    runs = {item["symbol"]: item for item in result.manifest["deep_research_runs"]}
    assert runs["SSE:600001"]["status"] == "incomplete"
    assert runs["SSE:600001"]["reason"] == "company research marked incomplete"
    assert runs["SSE:600001"]["run_id"] in result.manifest["child_runs"]
    decisions = {decision["symbol"]: decision for decision in result.candidates}
    assert decisions["SSE:600001"]["decision"] == "research_only"
    assert (
        decisions["SSE:600001"]["reason"]
        == "strict CANSLIM evidence but deep research incomplete"
    )
    state = {
        row["symbol"]: row
        for row in store.get_watchlist_state(as_of=date(2026, 6, 12)).to_dict("records")
    }
    assert state["SSE:600001"]["status"] == "candidate"


def test_daily_canslim_research_deduplicates_strict_symbols_for_deep_research(
    tmp_path, monkeypatch
):
    import trading_os.research.recipes as recipes
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_daily_canslim_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_fundamentals(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.35,
                    "roe": 0.22,
                    "positive_quarters": 8,
                },
                {
                    "symbol": "SSE:600001",
                    "period": "2026Q1",
                    "eps_growth_yoy": 0.40,
                    "roe": 0.24,
                    "positive_quarters": 8,
                },
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    monkeypatch.setattr(recipes, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        recipes,
        "_read_screen_all_candidates",
        lambda screen: [
            {
                "symbol": "SSE:600000",
                "classification": "strict_canslim_candidate",
                "score": 9.0,
            },
            {
                "symbol": "SSE:600000",
                "classification": "strict_canslim_candidate",
                "score": 8.5,
            },
            {
                "symbol": "SSE:600001",
                "classification": "strict_canslim_candidate",
                "score": 8.0,
            },
        ],
    )
    provider = DailyProvider()
    hub = DataHub(store, provider=provider)

    result = run_daily_canslim_research(hub, requested_as_of=date(2026, 6, 13))

    deep_research_runs = result.manifest["deep_research_runs"]
    assert result.manifest["strict_candidates_processed"] == 3
    assert [item["symbol"] for item in deep_research_runs] == ["SSE:600000", "SSE:600001"]
    assert provider.bars_calls[-1] == ["SSE:600000", "SSE:600001"]

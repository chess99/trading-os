from __future__ import annotations

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

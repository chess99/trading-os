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

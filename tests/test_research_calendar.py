from __future__ import annotations

from datetime import date, time


def test_resolves_weekend_to_previous_trading_day():
    from trading_os.research.calendar import TradingCalendar

    cal = TradingCalendar(extra_holidays={date(2026, 6, 19)})

    assert cal.resolve_effective_as_of(date(2026, 6, 13)) == date(2026, 6, 12)


def test_resolves_holiday_to_previous_trading_day():
    from trading_os.research.calendar import TradingCalendar

    cal = TradingCalendar(extra_holidays={date(2026, 6, 19)})

    assert cal.resolve_effective_as_of(date(2026, 6, 19)) == date(2026, 6, 18)


def test_trading_day_before_eod_cutoff_uses_previous_trading_day():
    from trading_os.research.calendar import TradingCalendar

    cal = TradingCalendar(eod_ready_time=time(18, 0))

    assert cal.resolve_effective_as_of(date(2026, 6, 12), now_time=time(15, 30)) == date(
        2026, 6, 11
    )


def test_trading_day_after_eod_cutoff_uses_same_day():
    from trading_os.research.calendar import TradingCalendar

    cal = TradingCalendar(eod_ready_time=time(18, 0))

    assert cal.resolve_effective_as_of(date(2026, 6, 12), now_time=time(18, 30)) == date(
        2026, 6, 12
    )

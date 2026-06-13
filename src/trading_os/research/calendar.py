from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, timedelta


@dataclass(frozen=True, slots=True)
class TradingCalendar:
    """Simple A-share trading calendar with injectable holidays.

    This starts with weekend and configured holiday handling. A provider-backed
    calendar can replace the holiday set without changing recipe code.
    """

    extra_holidays: set[date] = field(default_factory=set)
    eod_ready_time: time = time(18, 0)

    def is_trading_day(self, value: date) -> bool:
        return value.weekday() < 5 and value not in self.extra_holidays

    def previous_trading_day(self, value: date) -> date:
        current = value - timedelta(days=1)
        while not self.is_trading_day(current):
            current -= timedelta(days=1)
        return current

    def resolve_effective_as_of(
        self,
        requested: date,
        *,
        now_date: date | None = None,
        now_time: time | None = None,
    ) -> date:
        if not self.is_trading_day(requested):
            current = requested
            while not self.is_trading_day(current):
                current -= timedelta(days=1)
            return current
        if now_date is not None and requested != now_date:
            return requested
        if now_time is not None and now_time < self.eod_ready_time:
            return self.previous_trading_day(requested)
        return requested

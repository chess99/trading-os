from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone


@dataclass(frozen=True, slots=True)
class Session:
    """A trading session definition for a given calendar day.

    All datetimes are UTC.
    """

    session_date: date
    open_utc: datetime
    close_utc: datetime


class TradingCalendar:
    """Minimal trading calendar interface.

    For MVP we keep it intentionally small. We can later plug in exchange-specific calendars
    (holidays, half-days, etc.) without changing downstream components.
    """

    name: str = "generic"

    def is_trading_day(self, d: date) -> bool:
        raise NotImplementedError

    def session(self, d: date) -> Session:
        """Return session open/close in UTC for date d.

        Raises ValueError if d is not a trading day.
        """

        raise NotImplementedError

    def next_trading_day(self, d: date) -> date:
        cur = d
        while True:
            cur = date.fromordinal(cur.toordinal() + 1)
            if self.is_trading_day(cur):
                return cur

    def prev_trading_day(self, d: date) -> date:
        cur = d
        while True:
            cur = date.fromordinal(cur.toordinal() - 1)
            if self.is_trading_day(cur):
                return cur


class AlwaysOpenCalendar(TradingCalendar):
    """Every day is a trading day; session is full day UTC."""

    name = "always_open"

    def is_trading_day(self, d: date) -> bool:  # noqa: ARG002
        return True

    def session(self, d: date) -> Session:
        open_utc = datetime.combine(d, time(0, 0), tzinfo=timezone.utc)
        close_utc = datetime.combine(d, time(23, 59, 59), tzinfo=timezone.utc)
        return Session(session_date=d, open_utc=open_utc, close_utc=close_utc)


class WeekdayCalendar(TradingCalendar):
    """Mon-Fri trading days; session is full day UTC.

    This is a pragmatic default for backtests and paper trading until exchange-specific
    calendars are wired in.
    """

    name = "weekday"

    def is_trading_day(self, d: date) -> bool:
        return d.weekday() < 5

    def session(self, d: date) -> Session:
        if not self.is_trading_day(d):
            raise ValueError(f"Not a trading day: {d}")
        open_utc = datetime.combine(d, time(0, 0), tzinfo=timezone.utc)
        close_utc = datetime.combine(d, time(23, 59, 59), tzinfo=timezone.utc)
        return Session(session_date=d, open_utc=open_utc, close_utc=close_utc)


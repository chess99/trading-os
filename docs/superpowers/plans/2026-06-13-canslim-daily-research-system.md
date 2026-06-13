# CANSLIM Daily Research System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reliable daily CANSLIM research loop that screens all A-shares, researches every strict candidate, produces decisions, updates watchlist state, and monitors watched symbols for actionable alerts.

**Architecture:** Keep `ResearchStore` as the local evidence store and make `DataHub` route requests through capability-aware providers. Replace the thin `daily_research` wrapper with a `daily_canslim_research` recipe that resolves the effective trading date, runs screening, researches strict candidates, writes decisions, updates machine-readable watchlist state, and produces a human report. Add a watchlist-only alert monitor after the daily loop is deterministic.

**Tech Stack:** Python 3.13, pandas, pyarrow, argparse CLI, pytest, ruff, local Parquet datasets, existing `EventLog` for alert audit.

---

## Scope

This plan implements the approved design in five shippable phases. Each task should be completed with tests and a commit before moving to the next task. Production data sources can be unavailable during tests; use synthetic fixtures in tests and provider adapters for real runs.

## File Structure

Create or modify these files:

- Create: `src/trading_os/research/calendar.py`
  - Resolve requested dates to latest completed A-share trading dates.
- Create: `src/trading_os/research/providers.py`
  - Define provider capability names, provider results, provider health, and provider router.
- Modify: `src/trading_os/research/datahub.py`
  - Delegate provider selection to `ProviderRouter` and record provider failures.
- Modify: `src/trading_os/research/store.py`
  - Add datasets for `provider_health`, `decisions`, `watchlist_state`, `alerts`, and `technical_setups`.
- Create: `src/trading_os/research/decisions.py`
  - Convert strict candidates and technical setup evidence into one decision per symbol.
- Create: `src/trading_os/research/watchlist.py`
  - Maintain machine-readable CANSLIM watchlist state.
- Create: `src/trading_os/research/technical.py`
  - Compute base/pivot/buy-zone/stop-loss evidence from daily bars.
- Create: `src/trading_os/research/alerts.py`
  - Monitor watchlist symbols and write alert records.
- Modify: `src/trading_os/research/recipes.py`
  - Add `run_daily_canslim_research` and keep lower-level recipes reusable.
- Modify: `src/trading_os/research/cli.py`
  - Register `research daily-canslim`, `data provider status`, `data provider probe`, and `alert monitor`.
- Create tests:
  - `tests/test_research_calendar.py`
  - `tests/test_research_providers.py`
  - `tests/test_research_store_decisions.py`
  - `tests/test_daily_canslim_research.py`
  - `tests/test_watchlist_alerts.py`
- Modify docs and skills:
  - `AGENTS.md`
  - `README.md`
  - `skills/daily-workflow/SKILL.md`
  - `skills/canslim-system/SKILL.md`

## Task 1: Trading Calendar

**Files:**
- Create: `src/trading_os/research/calendar.py`
- Test: `tests/test_research_calendar.py`

- [ ] **Step 1: Write failing calendar tests**

Create `tests/test_research_calendar.py`:

```python
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
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
pytest tests/test_research_calendar.py -q
```

Expected: fail with `ModuleNotFoundError` or missing `TradingCalendar`.

- [ ] **Step 3: Implement `TradingCalendar`**

Create `src/trading_os/research/calendar.py`:

```python
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

    def resolve_effective_as_of(self, requested: date, *, now_time: time | None = None) -> date:
        if not self.is_trading_day(requested):
            current = requested
            while not self.is_trading_day(current):
                current -= timedelta(days=1)
            return current
        if now_time is not None and now_time < self.eod_ready_time:
            return self.previous_trading_day(requested)
        return requested
```

- [ ] **Step 4: Run the calendar test**

Run:

```bash
pytest tests/test_research_calendar.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/research/calendar.py tests/test_research_calendar.py
git commit -m "Add trading calendar resolution"
```

## Task 2: Provider Router and Health

**Files:**
- Create: `src/trading_os/research/providers.py`
- Modify: `src/trading_os/research/datahub.py`
- Modify: `src/trading_os/research/store.py`
- Test: `tests/test_research_providers.py`

- [ ] **Step 1: Write failing provider router tests**

Create `tests/test_research_providers.py`:

```python
from __future__ import annotations

from datetime import date

import pytest

pd = pytest.importorskip("pandas")


class FailingProvider:
    name = "failing"
    capabilities = {"quote_snapshot_eod"}

    def fetch_quote_snapshot(self, as_of: date):
        raise RuntimeError("primary down")


class WorkingProvider:
    name = "working"
    capabilities = {"quote_snapshot_eod"}

    def fetch_quote_snapshot(self, as_of: date):
        return pd.DataFrame([{"symbol": "SSE:600000", "close": 10.0, "amount": 20_000_000.0}])


def test_provider_router_falls_back_and_records_failure():
    from trading_os.research.providers import ProviderRouter

    router = ProviderRouter([FailingProvider(), WorkingProvider()])

    result = router.fetch("quote_snapshot_eod", "fetch_quote_snapshot", date(2026, 6, 12))

    assert result.provider_name == "working"
    assert len(result.failures) == 1
    assert result.failures[0]["provider"] == "failing"
    assert result.failures[0]["error_type"] == "RuntimeError"
    assert not result.data.empty


def test_provider_router_fails_when_no_provider_has_capability():
    from trading_os.research.providers import MissingCapabilityError, ProviderRouter

    router = ProviderRouter([])

    with pytest.raises(MissingCapabilityError):
        router.fetch("quote_snapshot_eod", "fetch_quote_snapshot", date(2026, 6, 12))
```

- [ ] **Step 2: Run failing provider tests**

Run:

```bash
pytest tests/test_research_providers.py -q
```

Expected: fail with missing `trading_os.research.providers`.

- [ ] **Step 3: Implement provider router**

Create `src/trading_os/research/providers.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class MissingCapabilityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderResult:
    capability: str
    provider_name: str
    data: Any
    failures: list[dict[str, Any]] = field(default_factory=list)


class ProviderRouter:
    def __init__(self, providers: list[Any]) -> None:
        self.providers = providers

    def fetch(self, capability: str, method_name: str, *args: Any, **kwargs: Any) -> ProviderResult:
        failures: list[dict[str, Any]] = []
        attempted = False
        for provider in self.providers:
            capabilities = set(getattr(provider, "capabilities", set()))
            if capability not in capabilities:
                continue
            attempted = True
            try:
                method = getattr(provider, method_name)
                data = method(*args, **kwargs)
                return ProviderResult(
                    capability=capability,
                    provider_name=str(getattr(provider, "name", provider.__class__.__name__)),
                    data=data,
                    failures=failures,
                )
            except Exception as exc:
                failures.append(
                    {
                        "provider": str(
                            getattr(provider, "name", provider.__class__.__name__)
                        ),
                        "capability": capability,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                        "failed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
        if not attempted:
            raise MissingCapabilityError(f"no provider supports capability={capability}")
        raise RuntimeError({"capability": capability, "failures": failures})
```

- [ ] **Step 4: Add provider health persistence to `ResearchStore`**

Modify `src/trading_os/research/store.py` by adding these methods inside `ResearchStore`:

```python
    def write_provider_health(self, records: list[dict[str, Any]]) -> Path:
        df = self._normalize_frame(records)
        if df.empty:
            return self._dataset_path("provider_health", "empty")
        partition = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
        return self._write_dataset("provider_health", df, partition)

    def get_provider_health(self) -> Any:
        return self._read_dataset("provider_health")
```

- [ ] **Step 5: Wire `DataHub` to router for quote snapshots**

Modify `src/trading_os/research/datahub.py`:

```python
from .providers import ProviderRouter
```

Inside `DataHub.get_quote_snapshot`, replace the direct provider call branch with:

```python
        provider = self._provider()
        if isinstance(provider, ProviderRouter):
            result = provider.fetch("quote_snapshot_eod", "fetch_quote_snapshot", as_of)
            if result.failures:
                self.store.write_provider_health(result.failures)
            df = result.data
            source = result.provider_name
        else:
            source = self._provider_name(provider)
            df = provider.fetch_quote_snapshot(as_of)
```

- [ ] **Step 6: Run provider tests**

Run:

```bash
pytest tests/test_research_providers.py tests/test_research_datahub.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/trading_os/research/providers.py src/trading_os/research/datahub.py src/trading_os/research/store.py tests/test_research_providers.py
git commit -m "Add research provider router"
```

## Task 3: ResearchStore Decision and Watchlist Datasets

**Files:**
- Modify: `src/trading_os/research/store.py`
- Test: `tests/test_research_store_decisions.py`

- [ ] **Step 1: Write failing dataset tests**

Create `tests/test_research_store_decisions.py`:

```python
from __future__ import annotations

from datetime import date

import pytest

pd = pytest.importorskip("pandas")


def test_store_writes_and_reads_decisions_watchlist_and_alerts(tmp_path):
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_decisions(
        [
            {
                "symbol": "SSE:600000",
                "as_of": "2026-06-12",
                "decision": "wait_for_breakout",
                "confidence": 0.72,
                "source_run_id": "run-1",
            }
        ]
    )
    store.write_watchlist_state(
        [
            {
                "symbol": "SSE:600000",
                "status": "watching",
                "pivot_price": 12.3,
                "valid_until": "2026-07-12",
            }
        ]
    )
    store.write_alerts(
        [
            {
                "alert_id": "alert-1",
                "symbol": "SSE:600000",
                "trigger_type": "near_pivot",
                "status": "sent",
            }
        ]
    )

    assert store.get_decisions(as_of=date(2026, 6, 12)).iloc[0]["decision"] == "wait_for_breakout"
    assert store.get_watchlist_state().iloc[0]["status"] == "watching"
    assert store.get_alerts().iloc[0]["trigger_type"] == "near_pivot"
```

- [ ] **Step 2: Run failing dataset tests**

Run:

```bash
pytest tests/test_research_store_decisions.py -q
```

Expected: fail with missing `write_decisions`.

- [ ] **Step 3: Add dataset helpers**

Modify `src/trading_os/research/store.py` by adding:

```python
    def write_decisions(self, records: list[dict[str, Any]]) -> Path:
        return self._write_event_dataset("decisions", records)

    def get_decisions(self, *, as_of: date | None = None) -> Any:
        df = self._read_dataset("decisions")
        if as_of is not None and not df.empty and "as_of" in df.columns:
            df = df[df["as_of"] <= as_of.isoformat()]
        return df.reset_index(drop=True)

    def write_watchlist_state(self, records: list[dict[str, Any]]) -> Path:
        return self._write_event_dataset("watchlist_state", records)

    def get_watchlist_state(self) -> Any:
        return self._read_dataset("watchlist_state")

    def write_alerts(self, records: list[dict[str, Any]]) -> Path:
        return self._write_event_dataset("alerts", records)

    def get_alerts(self) -> Any:
        return self._read_dataset("alerts")

    def write_technical_setups(self, records: list[dict[str, Any]]) -> Path:
        return self._write_event_dataset("technical_setups", records)

    def get_technical_setups(self) -> Any:
        return self._read_dataset("technical_setups")

    def _write_event_dataset(self, dataset: str, records: list[dict[str, Any]]) -> Path:
        df = self._normalize_frame(records)
        if df.empty:
            return self._dataset_path(dataset, "empty")
        df["fetched_at"] = datetime.now(timezone.utc).isoformat()
        partition = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
        return self._write_dataset(dataset, df, partition)
```

- [ ] **Step 4: Run dataset tests**

Run:

```bash
pytest tests/test_research_store_decisions.py tests/test_research_store.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/research/store.py tests/test_research_store_decisions.py
git commit -m "Add research decision datasets"
```

## Task 4: Technical Setup Detection

**Files:**
- Create: `src/trading_os/research/technical.py`
- Test: `tests/test_daily_canslim_research.py`

- [ ] **Step 1: Add technical setup tests**

Append to `tests/test_daily_canslim_research.py`:

```python
from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas")


def test_detects_simple_pivot_and_buy_zone():
    from trading_os.research.technical import detect_technical_setup

    bars = pd.DataFrame(
        [
            {"symbol": "SSE:600000", "ts": f"2026-05-{day:02d}", "close": close, "volume": 1000}
            for day, close in enumerate(
                [10.0, 10.5, 11.0, 10.8, 10.6, 11.2, 11.5, 11.3, 11.8, 12.0], start=1
            )
        ]
    )

    setup = detect_technical_setup("SSE:600000", bars)

    assert setup["symbol"] == "SSE:600000"
    assert setup["pivot_price"] == 12.0
    assert setup["buy_zone_high"] == 12.6
    assert setup["stop_loss"] == 11.04
    assert setup["status"] == "wait_for_breakout"
```

- [ ] **Step 2: Run failing technical test**

Run:

```bash
pytest tests/test_daily_canslim_research.py::test_detects_simple_pivot_and_buy_zone -q
```

Expected: fail with missing `technical` module.

- [ ] **Step 3: Implement simple deterministic setup detection**

Create `src/trading_os/research/technical.py`:

```python
from __future__ import annotations

from typing import Any


def detect_technical_setup(symbol: str, bars: Any) -> dict[str, Any]:
    if bars is None or bars.empty:
        return {
            "symbol": symbol,
            "status": "insufficient_bars",
            "pivot_price": None,
            "buy_zone_high": None,
            "stop_loss": None,
            "volume_baseline": None,
        }
    rows = bars[bars["symbol"].astype(str) == symbol].copy()
    if rows.empty or "close" not in rows.columns:
        return {
            "symbol": symbol,
            "status": "insufficient_bars",
            "pivot_price": None,
            "buy_zone_high": None,
            "stop_loss": None,
            "volume_baseline": None,
        }
    rows = rows.sort_values("ts")
    closes = rows["close"].astype(float)
    volumes = rows["volume"].astype(float) if "volume" in rows.columns else closes * 0
    pivot = float(closes.tail(min(len(closes), 60)).max())
    volume_baseline = float(volumes.tail(min(len(volumes), 50)).mean())
    return {
        "symbol": symbol,
        "status": "wait_for_breakout",
        "pivot_price": round(pivot, 4),
        "buy_zone_high": round(pivot * 1.05, 4),
        "stop_loss": round(pivot * 0.92, 4),
        "volume_baseline": round(volume_baseline, 4),
    }
```

- [ ] **Step 4: Run technical test**

Run:

```bash
pytest tests/test_daily_canslim_research.py::test_detects_simple_pivot_and_buy_zone -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/research/technical.py tests/test_daily_canslim_research.py
git commit -m "Add CANSLIM technical setup detection"
```

## Task 5: Decision Board

**Files:**
- Create: `src/trading_os/research/decisions.py`
- Test: `tests/test_daily_canslim_research.py`

- [ ] **Step 1: Add decision board tests**

Append to `tests/test_daily_canslim_research.py`:

```python
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
```

- [ ] **Step 2: Run failing decision test**

Run:

```bash
pytest tests/test_daily_canslim_research.py::test_decision_board_emits_one_decision_per_strict_candidate -q
```

Expected: fail with missing `decisions` module.

- [ ] **Step 3: Implement decision builder**

Create `src/trading_os/research/decisions.py`:

```python
from __future__ import annotations

from typing import Any


def build_canslim_decisions(
    candidates: list[dict[str, Any]],
    setups: dict[str, dict[str, Any]],
    *,
    as_of: str,
    source_run_id: str,
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.get("classification") != "strict_canslim_candidate":
            continue
        symbol = str(candidate["symbol"])
        setup = setups.get(symbol, {})
        pivot = setup.get("pivot_price")
        stop_loss = setup.get("stop_loss")
        if pivot and stop_loss:
            decision = setup.get("status") or "wait_for_breakout"
            confidence = 0.75
            reason = "strict CANSLIM evidence with defined technical setup"
        else:
            decision = "research_only"
            confidence = 0.45
            reason = "strict CANSLIM evidence but technical setup is incomplete"
        decisions.append(
            {
                "symbol": symbol,
                "as_of": as_of,
                "decision": decision,
                "confidence": confidence,
                "reason": reason,
                "score": candidate.get("score"),
                "pivot_price": pivot,
                "buy_zone_high": setup.get("buy_zone_high"),
                "stop_loss": stop_loss,
                "source_run_id": source_run_id,
            }
        )
    return decisions
```

- [ ] **Step 4: Run decision tests**

Run:

```bash
pytest tests/test_daily_canslim_research.py::test_decision_board_emits_one_decision_per_strict_candidate -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/research/decisions.py tests/test_daily_canslim_research.py
git commit -m "Add CANSLIM decision board"
```

## Task 6: Machine-Readable Watchlist State

**Files:**
- Create: `src/trading_os/research/watchlist.py`
- Test: `tests/test_watchlist_alerts.py`

- [ ] **Step 1: Write watchlist transition tests**

Create `tests/test_watchlist_alerts.py`:

```python
from __future__ import annotations


def test_watchlist_state_created_from_wait_for_breakout_decision():
    from trading_os.research.watchlist import update_watchlist_from_decisions

    current = []
    decisions = [
        {
            "symbol": "SSE:600000",
            "as_of": "2026-06-12",
            "decision": "wait_for_breakout",
            "pivot_price": 12.0,
            "buy_zone_high": 12.6,
            "stop_loss": 11.04,
            "source_run_id": "run-1",
        }
    ]

    state = update_watchlist_from_decisions(current, decisions)

    assert state[0]["symbol"] == "SSE:600000"
    assert state[0]["status"] == "watching"
    assert state[0]["pivot_price"] == 12.0
    assert state[0]["source_run_id"] == "run-1"


def test_reject_decision_invalidates_existing_watchlist_entry():
    from trading_os.research.watchlist import update_watchlist_from_decisions

    current = [{"symbol": "SSE:600000", "status": "watching", "pivot_price": 12.0}]
    decisions = [{"symbol": "SSE:600000", "decision": "reject", "source_run_id": "run-2"}]

    state = update_watchlist_from_decisions(current, decisions)

    assert state[0]["status"] == "invalidated"
    assert state[0]["source_run_id"] == "run-2"
```

- [ ] **Step 2: Run failing watchlist tests**

Run:

```bash
pytest tests/test_watchlist_alerts.py -q
```

Expected: fail with missing `watchlist` module.

- [ ] **Step 3: Implement watchlist state updater**

Create `src/trading_os/research/watchlist.py`:

```python
from __future__ import annotations

from typing import Any


def update_watchlist_from_decisions(
    current: list[dict[str, Any]], decisions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_symbol = {str(item["symbol"]): dict(item) for item in current}
    for decision in decisions:
        symbol = str(decision["symbol"])
        existing = by_symbol.get(symbol, {"symbol": symbol})
        decision_name = decision.get("decision")
        if decision_name in {"wait_for_breakout", "actionable_watch"}:
            existing.update(
                {
                    "status": "watching"
                    if decision_name == "wait_for_breakout"
                    else "actionable",
                    "pivot_price": decision.get("pivot_price"),
                    "buy_zone_high": decision.get("buy_zone_high"),
                    "stop_loss": decision.get("stop_loss"),
                    "source_run_id": decision.get("source_run_id"),
                    "last_decision": decision_name,
                }
            )
        elif decision_name == "reject":
            existing.update(
                {
                    "status": "invalidated",
                    "source_run_id": decision.get("source_run_id"),
                    "last_decision": decision_name,
                }
            )
        elif decision_name == "research_only":
            existing.update(
                {
                    "status": "candidate",
                    "source_run_id": decision.get("source_run_id"),
                    "last_decision": decision_name,
                }
            )
        by_symbol[symbol] = existing
    return sorted(by_symbol.values(), key=lambda row: row["symbol"])
```

- [ ] **Step 4: Run watchlist tests**

Run:

```bash
pytest tests/test_watchlist_alerts.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/research/watchlist.py tests/test_watchlist_alerts.py
git commit -m "Add CANSLIM watchlist state"
```

## Task 7: Daily CANSLIM Research Recipe

**Files:**
- Modify: `src/trading_os/research/recipes.py`
- Modify: `src/trading_os/research/store.py`
- Test: `tests/test_daily_canslim_research.py`

- [ ] **Step 1: Write daily recipe test**

Append to `tests/test_daily_canslim_research.py`:

```python
from datetime import date


class DailyProvider:
    name = "daily-fixture"

    def fetch_universe(self, as_of):
        return pd.DataFrame(
            [
                {"symbol": "SSE:600000", "name": "A", "is_st": False, "is_active": True},
                {"symbol": "SSE:600001", "name": "B", "is_st": False, "is_active": True},
            ]
        )

    def fetch_quote_snapshot(self, as_of):
        return pd.DataFrame(
            [
                {"symbol": "SSE:600000", "name": "A", "close": 12.0, "amount": 30_000_000.0},
                {"symbol": "SSE:600001", "name": "B", "close": 10.0, "amount": 30_000_000.0},
            ]
        )

    def fetch_bars(self, symbols, start, end, adjustment):
        rows = []
        for symbol in symbols:
            for idx, ts in enumerate(pd.date_range("2025-06-01", periods=260, freq="B")):
                rows.append(
                    {
                        "symbol": symbol,
                        "ts": ts,
                        "close": 10.0 + idx * 0.02,
                        "volume": 1_000_000.0,
                    }
                )
        return pd.DataFrame(rows)


def test_daily_canslim_research_processes_all_strict_candidates(tmp_path):
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
    hub = DataHub(store, provider=DailyProvider())

    result = run_daily_canslim_research(hub, requested_as_of=date(2026, 6, 13))

    assert result.manifest["requested_as_of"] == "2026-06-13"
    assert result.manifest["effective_as_of"] == "2026-06-12"
    assert result.manifest["strict_candidates_processed"] == 2
    assert (result.run.path / "report.md").exists()
    assert not store.get_decisions(as_of=date(2026, 6, 12)).empty
    assert not store.get_watchlist_state().empty
```

- [ ] **Step 2: Run failing daily recipe test**

Run:

```bash
pytest tests/test_daily_canslim_research.py::test_daily_canslim_research_processes_all_strict_candidates -q
```

Expected: fail with missing `run_daily_canslim_research`.

- [ ] **Step 3: Implement daily recipe skeleton with real artifacts**

Modify `src/trading_os/research/recipes.py` imports:

```python
from .calendar import TradingCalendar
from .decisions import build_canslim_decisions
from .technical import detect_technical_setup
from .watchlist import update_watchlist_from_decisions
```

Add function:

```python
def run_daily_canslim_research(hub: DataHub, *, requested_as_of: date) -> RecipeResult:
    calendar = TradingCalendar()
    effective_as_of = calendar.resolve_effective_as_of(requested_as_of)
    run = hub.store.start_run(
        "daily_canslim_research",
        inputs={
            "requested_as_of": requested_as_of.isoformat(),
            "effective_as_of": effective_as_of.isoformat(),
        },
    )
    screen = run_canslim_screen(hub, as_of=effective_as_of, top_n=30)
    all_candidates = pd.read_csv(screen.run.path / "tables" / "all_candidates.csv")
    strict = all_candidates[
        all_candidates["classification"].astype(str).eq("strict_canslim_candidate")
    ].to_dict("records")
    symbols = [str(row["symbol"]) for row in strict]
    bars = hub.get_bars(
        symbols,
        start=effective_as_of - timedelta(days=420),
        end=effective_as_of + timedelta(days=1),
        adjustment="qfq",
        policy="lazy_fill",
    )
    setups = {symbol: detect_technical_setup(symbol, bars) for symbol in symbols}
    decisions = build_canslim_decisions(
        strict,
        setups,
        as_of=effective_as_of.isoformat(),
        source_run_id=screen.run.run_id,
    )
    hub.store.write_decisions(decisions)
    current_watchlist = hub.store.get_watchlist_state().to_dict("records")
    watchlist_state = update_watchlist_from_decisions(current_watchlist, decisions)
    hub.store.write_watchlist_state(watchlist_state)
    report = _daily_canslim_report(
        requested_as_of=requested_as_of,
        effective_as_of=effective_as_of,
        screen=screen,
        decisions=decisions,
        watchlist_state=watchlist_state,
    )
    manifest = {
        "requested_as_of": requested_as_of.isoformat(),
        "effective_as_of": effective_as_of.isoformat(),
        "child_runs": [screen.run.run_id],
        "strict_candidates_processed": len(strict),
        "decisions_total": len(decisions),
        "outputs": {"report": str(run.path / "report.md")},
    }
    hub.store.write_run_artifacts(
        run,
        manifest=manifest,
        trace_lines=[
            "# daily_canslim_research trace",
            f"- requested_as_of: `{requested_as_of.isoformat()}`",
            f"- effective_as_of: `{effective_as_of.isoformat()}`",
            f"- strict candidates processed: `{len(strict)}`",
        ],
        report=report,
        tables={
            "decisions": pd.DataFrame(decisions),
            "watchlist_state": pd.DataFrame(watchlist_state),
        },
    )
    return RecipeResult(
        "daily_canslim_research",
        run,
        manifest,
        report,
        decisions,
        screen.filtered_out,
    )
```

Add helper:

```python
def _daily_canslim_report(
    *,
    requested_as_of: date,
    effective_as_of: date,
    screen: RecipeResult,
    decisions: list[dict[str, Any]],
    watchlist_state: list[dict[str, Any]],
) -> str:
    lines = [
        "# Daily CANSLIM Research",
        "",
        f"- requested_as_of: `{requested_as_of.isoformat()}`",
        f"- effective_as_of: `{effective_as_of.isoformat()}`",
        f"- screen_run: `{screen.run.run_id}`",
        f"- total_candidates: `{screen.manifest.get('candidates_total')}`",
        f"- strict_candidates: `{screen.manifest.get('strict_candidates_total')}`",
        f"- provisional_candidates: `{screen.manifest.get('provisional_candidates_total')}`",
        "",
        "## Decisions",
    ]
    if decisions:
        for row in decisions:
            lines.append(
                f"- {row['symbol']} decision={row['decision']} "
                f"pivot={row.get('pivot_price')} stop={row.get('stop_loss')}"
            )
    else:
        lines.append("- No strict candidates produced decisions.")
    lines.extend(["", "## Watchlist State"])
    for row in watchlist_state:
        lines.append(f"- {row['symbol']} status={row.get('status')} pivot={row.get('pivot_price')}")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run daily recipe test**

Run:

```bash
pytest tests/test_daily_canslim_research.py tests/test_research_recipes.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/research/recipes.py tests/test_daily_canslim_research.py
git commit -m "Add daily CANSLIM research recipe"
```

## Task 8: Human Report Export to `artifacts/research`

**Files:**
- Modify: `src/trading_os/research/recipes.py`
- Test: `tests/test_daily_canslim_research.py`

- [ ] **Step 1: Add artifact export test**

Append to `tests/test_daily_canslim_research.py`:

```python
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
```

- [ ] **Step 2: Run failing artifact test**

Run:

```bash
pytest tests/test_daily_canslim_research.py::test_daily_canslim_research_writes_human_report -q
```

Expected: fail because no `artifacts/research` export exists.

- [ ] **Step 3: Export daily report**

Modify `src/trading_os/research/recipes.py` imports:

```python
from ..paths import repo_root
```

Inside `run_daily_canslim_research`, before building `manifest`:

```python
    human_report_path = (
        repo_root()
        / "artifacts"
        / "research"
        / f"daily-canslim-{effective_as_of.strftime('%Y%m%d')}.md"
    )
    human_report_path.parent.mkdir(parents=True, exist_ok=True)
    human_report_path.write_text(report, encoding="utf-8")
```

Add to `manifest`:

```python
        "human_report": str(human_report_path),
```

- [ ] **Step 4: Run artifact test**

Run:

```bash
pytest tests/test_daily_canslim_research.py::test_daily_canslim_research_writes_human_report -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/research/recipes.py tests/test_daily_canslim_research.py
git commit -m "Export daily CANSLIM human report"
```

## Task 9: Active Estimates and News Fetching

**Files:**
- Modify: `src/trading_os/research/datahub.py`
- Test: `tests/test_research_datahub.py`

- [ ] **Step 1: Add active estimates and news tests**

Append to `tests/test_research_datahub.py`:

```python
class EnrichmentProvider(FakeProvider):
    def fetch_estimates(self, symbols, as_of):
        self.calls.append(f"estimates:{','.join(symbols)}:{as_of.isoformat()}")
        return pd.DataFrame(
            [{"symbol": symbols[0], "eps_estimate": 1.23, "target_price": 15.0}]
        )

    def fetch_news(self, symbols, as_of, lookback_months):
        self.calls.append(
            f"news:{','.join(symbols)}:{as_of.isoformat()}:{lookback_months}"
        )
        return pd.DataFrame(
            [
                {
                    "symbol": symbols[0],
                    "title": "订单增长",
                    "published_at": "2026-06-01T09:00:00+08:00",
                    "source_url": "https://example.test/news/1",
                }
            ]
        )


def test_datahub_fetches_estimates_when_provider_supports_it(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    provider = EnrichmentProvider()
    hub = DataHub(ResearchStore(tmp_path / "research"), provider=provider)

    estimates = hub.get_estimates(["SSE:600000"], as_of=date(2026, 6, 12))

    assert provider.calls == ["estimates:SSE:600000:2026-06-12"]
    assert estimates.iloc[0]["target_price"] == 15.0


def test_datahub_fetches_news_when_provider_supports_it(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.store import ResearchStore

    provider = EnrichmentProvider()
    hub = DataHub(ResearchStore(tmp_path / "research"), provider=provider)

    news = hub.get_news(["SSE:600000"], as_of=date(2026, 6, 12), lookback_months=12)

    assert provider.calls == ["news:SSE:600000:2026-06-12:12"]
    assert news.iloc[0]["title"] == "订单增长"
```

- [ ] **Step 2: Run failing enrichment tests**

Run:

```bash
pytest tests/test_research_datahub.py::test_datahub_fetches_estimates_when_provider_supports_it tests/test_research_datahub.py::test_datahub_fetches_news_when_provider_supports_it -q
```

Expected: fail because `DataHub.get_estimates()` and `DataHub.get_news()` return empty cache without calling provider.

- [ ] **Step 3: Implement active estimates fetch**

Modify `src/trading_os/research/datahub.py` in `get_estimates`:

```python
        provider = self._provider()
        if not hasattr(provider, "fetch_estimates"):
            return cached
        source = self._provider_name(provider)
        df = provider.fetch_estimates(symbols, as_of)
        if df is not None and not df.empty:
            self.store.write_estimates(
                df,
                as_of=as_of,
                source=source,
                provenance={"provider": source},
            )
        return self.store.get_estimates(symbols, as_of=as_of)
```

- [ ] **Step 4: Implement active news fetch**

Modify `src/trading_os/research/datahub.py` in `get_news`:

```python
        provider = self._provider()
        if not hasattr(provider, "fetch_news"):
            return cached
        source = self._provider_name(provider)
        df = provider.fetch_news(symbols, as_of, lookback_months)
        if df is not None and not df.empty:
            self.store.write_news(
                df,
                as_of=as_of,
                source=source,
                provenance={"provider": source, "lookback_months": lookback_months},
            )
        return self.store.get_news(symbols, as_of=as_of)
```

- [ ] **Step 5: Run enrichment tests**

Run:

```bash
pytest tests/test_research_datahub.py -q
```

Expected: all DataHub tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/trading_os/research/datahub.py tests/test_research_datahub.py
git commit -m "Fetch research enrichment datasets"
```

## Task 10: Strict Candidate Deep Research Batch

**Files:**
- Modify: `src/trading_os/research/recipes.py`
- Test: `tests/test_daily_canslim_research.py`

- [ ] **Step 1: Add strict deep research batch test**

Append to `tests/test_daily_canslim_research.py`:

```python
def test_daily_canslim_research_runs_company_research_for_every_strict(tmp_path):
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
    hub = DataHub(store, provider=DailyProvider())

    result = run_daily_canslim_research(hub, requested_as_of=date(2026, 6, 13))

    deep_research_runs = result.manifest["deep_research_runs"]
    assert len(deep_research_runs) == 2
    assert all(item["template"] == "canslim" for item in deep_research_runs)
    assert {item["symbol"] for item in deep_research_runs} == {"SSE:600000", "SSE:600001"}
```

- [ ] **Step 2: Run failing strict deep research test**

Run:

```bash
pytest tests/test_daily_canslim_research.py::test_daily_canslim_research_runs_company_research_for_every_strict -q
```

Expected: fail because `deep_research_runs` is not in the daily manifest.

- [ ] **Step 3: Call company research for every strict candidate**

Modify `run_daily_canslim_research` in `src/trading_os/research/recipes.py` after `symbols` is defined:

```python
    deep_research_runs = []
    for symbol in symbols:
        company = run_company_research(
            hub,
            symbol,
            as_of=effective_as_of,
            template="canslim",
        )
        deep_research_runs.append(
            {
                "symbol": symbol,
                "run_id": company.run.run_id,
                "template": "canslim",
                "report": str(company.run.path / "report.md"),
                "manifest": str(company.run.path / "manifest.json"),
            }
        )
```

Add to `manifest`:

```python
        "deep_research_runs": deep_research_runs,
```

Add to `report` helper output:

```python
        "",
        "## Deep Research Runs",
```

Then append each run:

```python
    for item in deep_research_runs:
        lines.append(f"- {item['symbol']} report={item['report']}")
```

Pass `deep_research_runs=deep_research_runs` into `_daily_canslim_report`.

- [ ] **Step 4: Run strict deep research tests**

Run:

```bash
pytest tests/test_daily_canslim_research.py tests/test_research_recipes.py -q
```

Expected: all recipe tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/research/recipes.py tests/test_daily_canslim_research.py
git commit -m "Run deep research for all strict CANSLIM candidates"
```

## Task 11: Enriched Company Research Report Sections

**Files:**
- Modify: `src/trading_os/research/recipes.py`
- Test: `tests/test_research_recipes.py`

- [ ] **Step 1: Add enriched report section test**

Append to `tests/test_research_recipes.py`:

```python
def test_company_research_canslim_report_includes_enrichment_sections(tmp_path):
    from trading_os.research.datahub import DataHub
    from trading_os.research.recipes import run_company_research
    from trading_os.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    store.write_quote_snapshot(
        pd.DataFrame([{"symbol": "SSE:600000", "close": 20.0, "amount": 40_000_000.0}]),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
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
    store.write_news(
        pd.DataFrame(
            [
                {
                    "symbol": "SSE:600000",
                    "title": "公司公告订单增长",
                    "published_at": "2026-06-01T09:00:00+08:00",
                    "source_url": "https://example.test/news/1",
                }
            ]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    store.write_estimates(
        pd.DataFrame(
            [{"symbol": "SSE:600000", "eps_estimate": 1.23, "target_price": 15.0}]
        ),
        as_of=date(2026, 6, 12),
        source="fixture",
    )
    hub = DataHub(store, provider=RecipeProvider())

    result = run_company_research(
        hub,
        "SSE:600000",
        as_of=date(2026, 6, 12),
        template="canslim",
    )

    assert "## News and Announcements" in result.report
    assert "公司公告订单增长" in result.report
    assert "## Estimates and Valuation Context" in result.report
    assert "target_price" in result.report
    assert "## Institutional Sponsorship and Peer Context" in result.report
```

- [ ] **Step 2: Run failing enriched report test**

Run:

```bash
pytest tests/test_research_recipes.py::test_company_research_canslim_report_includes_enrichment_sections -q
```

Expected: fail because report sections are absent.

- [ ] **Step 3: Pass estimates and news into CANSLIM company report**

Modify `_company_report` call site in `src/trading_os/research/recipes.py` so `_canslim_company_report` receives `estimates` and `news`:

```python
    if template == "canslim":
        return _canslim_company_report(
            symbol,
            as_of,
            valuation_mode,
            quote,
            fundamentals,
            bars,
            tables.get("estimates", pd.DataFrame()),
            tables.get("news", pd.DataFrame()),
        )
```

Update `_canslim_company_report` signature:

```python
def _canslim_company_report(
    symbol: str,
    as_of: date,
    valuation_mode: str,
    quote: pd.DataFrame,
    fundamentals: pd.DataFrame,
    bars: pd.DataFrame,
    estimates: pd.DataFrame,
    news: pd.DataFrame,
) -> str:
```

- [ ] **Step 4: Add report sections**

Inside `_canslim_company_report`, before `## Data Limitations`, append:

```python
        "",
        "## News and Announcements",
        "",
```

Then add:

```python
    if news.empty:
        lines.append("- No cached news or announcements were available for this run.")
    else:
        for item in news.head(10).to_dict("records"):
            lines.append(
                f"- {item.get('published_at', 'N/A')} {item.get('title', 'N/A')} "
                f"source={item.get('source_url', 'N/A')}"
            )
    lines.extend(["", "## Estimates and Valuation Context", ""])
    if estimates.empty:
        lines.append("- No cached estimates were available for this run.")
    else:
        latest_estimate = estimates.iloc[0].to_dict()
        for key, value in latest_estimate.items():
            if key != "symbol":
                lines.append(f"- {key}: `{_fmt(value)}`")
    lines.extend(["", "## Institutional Sponsorship and Peer Context", ""])
    lines.append(
        "- Institutional sponsorship and peer comparison require provider coverage; "
        "missing fields reduce confidence and keep the decision out of automatic trade status."
    )
```

- [ ] **Step 5: Run enriched report tests**

Run:

```bash
pytest tests/test_research_recipes.py -q
```

Expected: all recipe tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/trading_os/research/recipes.py tests/test_research_recipes.py
git commit -m "Enrich CANSLIM company research reports"
```

## Task 12: Watchlist-Only Alert Monitor

**Files:**
- Create: `src/trading_os/research/alerts.py`
- Test: `tests/test_watchlist_alerts.py`

- [ ] **Step 1: Add alert monitor tests**

Append to `tests/test_watchlist_alerts.py`:

```python
def test_alert_monitor_only_alerts_watchlist_breakouts():
    from trading_os.research.alerts import evaluate_watchlist_alerts

    watchlist = [
        {
            "symbol": "SSE:600000",
            "status": "watching",
            "pivot_price": 12.0,
            "buy_zone_high": 12.6,
            "stop_loss": 11.04,
        }
    ]
    quotes = [
        {"symbol": "SSE:600000", "close": 12.2, "volume": 2_000_000.0},
        {"symbol": "SSE:600001", "close": 30.0, "volume": 9_000_000.0},
    ]

    alerts = evaluate_watchlist_alerts(
        watchlist, quotes, as_of="2026-06-12T10:30:00+08:00", existing_cooldowns=set()
    )

    assert len(alerts) == 1
    assert alerts[0]["symbol"] == "SSE:600000"
    assert alerts[0]["trigger_type"] == "breakout_confirmed"
    assert alerts[0]["cooldown_key"] == "SSE:600000:breakout_confirmed:2026-06-12"


def test_alert_monitor_deduplicates_by_cooldown_key():
    from trading_os.research.alerts import evaluate_watchlist_alerts

    watchlist = [{"symbol": "SSE:600000", "status": "watching", "pivot_price": 12.0}]
    quotes = [{"symbol": "SSE:600000", "close": 12.2}]

    alerts = evaluate_watchlist_alerts(
        watchlist,
        quotes,
        as_of="2026-06-12T10:30:00+08:00",
        existing_cooldowns={"SSE:600000:breakout_confirmed:2026-06-12"},
    )

    assert alerts == []
```

- [ ] **Step 2: Run failing alert tests**

Run:

```bash
pytest tests/test_watchlist_alerts.py::test_alert_monitor_only_alerts_watchlist_breakouts tests/test_watchlist_alerts.py::test_alert_monitor_deduplicates_by_cooldown_key -q
```

Expected: fail with missing `alerts` module.

- [ ] **Step 3: Implement alert evaluator**

Create `src/trading_os/research/alerts.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4


def evaluate_watchlist_alerts(
    watchlist: list[dict[str, Any]],
    quotes: list[dict[str, Any]],
    *,
    as_of: str,
    existing_cooldowns: set[str],
) -> list[dict[str, Any]]:
    quote_by_symbol = {str(row["symbol"]): row for row in quotes}
    trade_date = datetime.fromisoformat(as_of).date().isoformat()
    alerts: list[dict[str, Any]] = []
    for item in watchlist:
        symbol = str(item["symbol"])
        if item.get("status") not in {"watching", "actionable"}:
            continue
        quote = quote_by_symbol.get(symbol)
        if not quote:
            continue
        pivot = _float_or_none(item.get("pivot_price"))
        close = _float_or_none(quote.get("close"))
        if pivot is None or close is None:
            continue
        if close >= pivot:
            trigger_type = "breakout_confirmed"
            cooldown_key = f"{symbol}:{trigger_type}:{trade_date}"
            if cooldown_key in existing_cooldowns:
                continue
            alerts.append(
                {
                    "alert_id": f"alert-{uuid4().hex[:12]}",
                    "symbol": symbol,
                    "as_of": as_of,
                    "trigger_type": trigger_type,
                    "trigger_value": close,
                    "pivot_price": pivot,
                    "status": "pending",
                    "cooldown_key": cooldown_key,
                }
            )
    return alerts


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None
```

- [ ] **Step 4: Run alert tests**

Run:

```bash
pytest tests/test_watchlist_alerts.py -q
```

Expected: all watchlist and alert tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/research/alerts.py tests/test_watchlist_alerts.py
git commit -m "Add watchlist alert evaluator"
```

## Task 13: Alert CLI and EventLog Write

**Files:**
- Modify: `src/trading_os/research/cli.py`
- Modify: `src/trading_os/cli_internal/app.py`
- Test: `tests/test_research_cli.py`

- [ ] **Step 1: Add CLI tests**

Append to `tests/test_research_cli.py`:

```python
def test_cli_help_includes_alert_monitor():
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    help_text = parser.format_help()

    assert "alert" in help_text


def test_research_help_includes_daily_canslim():
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    ns = parser.parse_args(["research", "daily-canslim", "--as-of", "2026-06-12"])

    assert ns.research_cmd == "daily-canslim"
```

- [ ] **Step 2: Run failing CLI tests**

Run:

```bash
pytest tests/test_research_cli.py::test_cli_help_includes_alert_monitor tests/test_research_cli.py::test_research_help_includes_daily_canslim -q
```

Expected: fail because commands are not registered.

- [ ] **Step 3: Add `daily-canslim` to research CLI**

Modify `src/trading_os/research/cli.py` imports:

```python
from .recipes import run_daily_canslim_research
```

In `cmd_research`, add:

```python
    elif ns.research_cmd == "daily-canslim":
        result = run_daily_canslim_research(
            hub,
            requested_as_of=date.fromisoformat(ns.as_of),
        )
```

In `register_research_kernel_commands`, add after `daily`:

```python
    daily_canslim = research_sub.add_parser(
        "daily-canslim", help="Run full daily CANSLIM research closure"
    )
    daily_canslim.add_argument("--as-of", required=True, dest="as_of")
    daily_canslim.set_defaults(func=cmd_research)
```

- [ ] **Step 4: Add alert CLI parser**

In `src/trading_os/research/cli.py`, add:

```python
def cmd_alert(ns: argparse.Namespace) -> int:
    hub = build_datahub()
    if ns.alert_cmd == "monitor" and ns.mode == "watchlist":
        print("watchlist alert monitor is available; use --once for one-shot evaluation")
        return 0
    raise RuntimeError(f"unknown alert command: {ns.alert_cmd}")
```

In `register_research_kernel_commands`, add:

```python
    alert = sub.add_parser("alert", help="Run watchlist-only alert monitoring")
    alert_sub = alert.add_subparsers(dest="alert_cmd", required=True)
    monitor = alert_sub.add_parser("monitor")
    monitor.add_argument("--mode", choices=["watchlist"], required=True)
    monitor.add_argument("--once", action="store_true")
    monitor.set_defaults(func=cmd_alert)
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
pytest tests/test_research_cli.py -q
```

Expected: all CLI tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/trading_os/research/cli.py tests/test_research_cli.py
git commit -m "Add daily CANSLIM and alert CLI"
```

## Task 14: Provider Status CLI

**Files:**
- Modify: `src/trading_os/research/cli.py`
- Test: `tests/test_research_cli.py`

- [ ] **Step 1: Add provider CLI parse tests**

Append to `tests/test_research_cli.py`:

```python
def test_data_provider_status_command_parses():
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    ns = parser.parse_args(["data", "provider", "status"])

    assert ns.data_cmd == "provider"
    assert ns.provider_cmd == "status"


def test_data_provider_probe_command_parses():
    from trading_os.cli_internal.app import build_parser

    parser = build_parser()
    ns = parser.parse_args(["data", "provider", "probe"])

    assert ns.data_cmd == "provider"
    assert ns.provider_cmd == "probe"
```

- [ ] **Step 2: Run failing provider CLI parse tests**

Run:

```bash
pytest tests/test_research_cli.py::test_data_provider_status_command_parses tests/test_research_cli.py::test_data_provider_probe_command_parses -q
```

Expected: fail because `data provider` parser is absent.

- [ ] **Step 3: Add `data provider` parser**

Modify `src/trading_os/research/cli.py` in `register_research_kernel_commands`:

```python
    provider = data_sub.add_parser("provider", help="Inspect research data providers")
    provider_sub = provider.add_subparsers(dest="provider_cmd", required=True)
    provider_status = provider_sub.add_parser("status", help="Show provider health records")
    provider_status.set_defaults(func=cmd_data)
    provider_probe = provider_sub.add_parser("probe", help="Probe configured provider capabilities")
    provider_probe.set_defaults(func=cmd_data)
```

Modify `cmd_data` before the final raise:

```python
    if ns.data_cmd == "provider":
        if ns.provider_cmd == "status":
            health = hub.store.get_provider_health()
            print(health.to_json(orient="records", force_ascii=False))
            return 0
        if ns.provider_cmd == "probe":
            payload = {"providers": [hub._provider_name(hub._provider())]}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
```

- [ ] **Step 4: Run provider CLI tests**

Run:

```bash
pytest tests/test_research_cli.py -q
```

Expected: all CLI tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/trading_os/research/cli.py tests/test_research_cli.py
git commit -m "Add provider status CLI"
```

## Task 15: Documentation and Skill Updates

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `skills/daily-workflow/SKILL.md`
- Modify: `skills/canslim-system/SKILL.md`
- Test: `tests/test_agent_research_guidance.py`

- [ ] **Step 1: Add documentation guard tests**

Modify `tests/test_agent_research_guidance.py` with:

```python
from pathlib import Path


def test_docs_reference_daily_canslim_closure():
    root = Path(__file__).resolve().parents[1]
    text = (root / "AGENTS.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")

    assert "daily-canslim" in text
    assert "daily-canslim" in readme
    assert "观察池盘中提醒" in text


def test_daily_skill_requires_human_report_and_watchlist_state():
    root = Path(__file__).resolve().parents[1]
    text = (root / "skills" / "daily-workflow" / "SKILL.md").read_text(encoding="utf-8")

    assert "artifacts/research/daily-canslim-YYYYMMDD.md" in text
    assert "artifacts/watchlist/state.json" in text
    assert "不能只输出 run manifest" in text
```

- [ ] **Step 2: Run failing docs tests**

Run:

```bash
pytest tests/test_agent_research_guidance.py -q
```

Expected: fail until docs and skills are updated.

- [ ] **Step 3: Update AGENTS and README**

Add this workflow summary to `AGENTS.md` and `README.md`:

````markdown
### Daily CANSLIM Closure

Use:

```bash
python -m trading_os research daily-canslim --as-of YYYY-MM-DD
```

This workflow resolves the latest completed trading day, runs full A-share CANSLIM screening, researches every strict candidate, writes decisions, updates `artifacts/watchlist/state.json`, and generates `artifacts/research/daily-canslim-YYYYMMDD.md`.

`--top` display limits never limit downstream strict-candidate processing. The workflow must not stop after writing run manifests.
```

Add this alert summary:

```markdown
### Watchlist Alert Monitor

Use:

```bash
python -m trading_os alert monitor --mode watchlist --once
```

The alert monitor only evaluates machine-readable watchlist entries. It does not run full-market intraday scanning.
```
````

- [ ] **Step 4: Update daily and CANSLIM skills**

In `skills/daily-workflow/SKILL.md` and `skills/canslim-system/SKILL.md`, replace old daily guidance with:

```markdown
Daily CANSLIM closure command:

```bash
python -m trading_os research daily-canslim --as-of YYYY-MM-DD
```

Required final user-facing outputs:

- `artifacts/research/daily-canslim-YYYYMMDD.md`
- `artifacts/watchlist/state.json`
- linked `data/research/runs/{run_id}/manifest.json`

The agent must summarize decisions and watchlist changes. It cannot only return run manifest paths.
```

- [ ] **Step 5: Run docs tests**

Run:

```bash
pytest tests/test_agent_research_guidance.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add AGENTS.md README.md skills/daily-workflow/SKILL.md skills/canslim-system/SKILL.md tests/test_agent_research_guidance.py
git commit -m "Document daily CANSLIM closure"
```

## Task 16: Verification Sweep

**Files:**
- No source edits expected unless verification exposes a bug.

- [ ] **Step 1: Run focused tests**

Run:

```bash
pytest tests/test_research_calendar.py tests/test_research_providers.py tests/test_research_store_decisions.py tests/test_daily_canslim_research.py tests/test_watchlist_alerts.py tests/test_research_cli.py tests/test_agent_research_guidance.py -q
```

Expected: all focused tests pass.

- [ ] **Step 2: Run full tests**

Run:

```bash
pytest -q
```

Expected: all repository tests pass or only documented environment skips remain.

- [ ] **Step 3: Run ruff on changed code**

Run:

```bash
ruff check src/trading_os/research tests/test_research_calendar.py tests/test_research_providers.py tests/test_research_store_decisions.py tests/test_daily_canslim_research.py tests/test_watchlist_alerts.py tests/test_research_cli.py tests/test_agent_research_guidance.py
```

Expected: no ruff violations.

- [ ] **Step 4: Verify CLI help**

Run:

```bash
python -m trading_os --help
python -m trading_os research daily-canslim --help
python -m trading_os alert monitor --help
python -m trading_os data provider status
```

Expected:

- Top-level help includes `data`, `research`, `factor`, `backtest`, `pool`, and `alert`.
- `research daily-canslim --help` describes daily CANSLIM closure.
- `alert monitor --help` accepts `--mode watchlist`.
- `data provider status` prints JSON.

- [ ] **Step 5: Commit verification fixes only if files changed**

If verification required edits:

```bash
git add <changed-files>
git commit -m "Verify daily CANSLIM workflow"
```

If no files changed, do not create an empty commit.

## Execution Notes

- Use `superpowers:subagent-driven-development` for implementation. Dispatch one task per subagent and review each diff before committing the next task.
- Keep commits narrow. Do not stage unrelated user changes.
- Production reports must not use synthetic market data. Tests may use synthetic fixtures.
- If a provider cannot fetch a required production dataset, the recipe must record the source failure and lower the decision confidence or decision class.

## Self-Review

Spec coverage:

- Daily screening: Tasks 7, 13, 15.
- Deep research of all strict candidates: Task 10.
- Operation decisions: Task 5 and Task 7.
- Watchlist tracking: Task 6 and Task 7.
- Alerting: Task 12 and Task 13.
- Provider reliability: Task 2 and Task 14.
- Trading date correctness: Task 1.
- Human-readable reports: Task 8 and Task 15.
- Active news and estimates: Task 9 and Task 11.

The plan intentionally builds a deterministic foundation before the richer report sections. The later tasks in this plan still implement active news and estimates fetching, all-strict deep research, human reports, watchlist state, and watchlist-only alerts, so the execution path remains aligned with the approved complete system design.

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from importlib import import_module
from zoneinfo import ZoneInfo

import pytest


def test_probe_not_ready_does_not_create_bulk_job(tmp_path):
    from trading_os.scheduler import (
        JOB_STATUS_NOT_READY,
        SchedulerStore,
        trigger_market_data_probe,
    )

    store = SchedulerStore(tmp_path)
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    job = trigger_market_data_probe(
        store,
        probe_fn=lambda: {
            "effective_date": yesterday,
            "ready": False,
            "sentinels": {"SSE:600000": yesterday},
            "errors": {},
            "wall_clock_date": date.today().isoformat(),
        },
    )

    assert job.status == JOB_STATUS_NOT_READY
    assert store.latest_job("market_data_bulk_refresh") is None


def test_probe_ready_then_bulk_job_created(tmp_path, monkeypatch):
    import trading_os.scheduler as scheduler
    from trading_os.scheduler import JOB_STATUS_SUCCESS, SchedulerStore

    store = SchedulerStore(tmp_path)
    today = date.today().isoformat()
    scheduler.trigger_market_data_probe(
        store,
        probe_fn=lambda: {
            "effective_date": today,
            "ready": True,
            "sentinels": {},
            "errors": {},
            "wall_clock_date": today,
        },
    )
    monkeypatch.setattr(
        scheduler,
        "lake_has_effective_date",
        lambda root, effective_date, progress=None: (True, effective_date),
    )

    calls = []

    def fake_runner(args, log_path):
        calls.append((args, log_path))
        return 0

    bulk = scheduler.trigger_market_data_bulk_refresh(store, runner=fake_runner)

    assert bulk.status == JOB_STATUS_SUCCESS
    assert bulk.effective_date == today
    assert calls
    assert "fetch-ak-bulk" in calls[0][0]


def test_probe_uses_market_effective_date_not_wall_clock_today():
    from trading_os.scheduler import intended_market_effective_date

    monday_morning = datetime(2026, 5, 18, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert intended_market_effective_date(monday_morning).isoformat() == "2026-05-15"


def test_daily_blocked_when_bulk_missing(tmp_path):
    from trading_os.scheduler import SchedulerStore, generate_daily

    store = SchedulerStore(tmp_path)

    path = generate_daily(store, effective_date=date.today().isoformat())

    assert path.name.endswith("-blocked.md")
    text = path.read_text(encoding="utf-8")
    assert "market data bulk refresh is incomplete" in text
    assert "No market view" in text


def test_daily_blocked_when_scans_missing(tmp_path):
    from trading_os.scheduler import JOB_STATUS_SUCCESS, SchedulerStore, generate_daily

    today = date.today().isoformat()
    store = SchedulerStore(tmp_path)
    store.create_job("market_data_bulk_refresh", effective_date=today, status=JOB_STATUS_SUCCESS)

    path = generate_daily(store, effective_date=today)

    assert path.name.endswith("-blocked.md")
    assert "Elder scan is incomplete" in path.read_text(encoding="utf-8")


def test_daily_complete_only_after_bulk_and_both_scans(tmp_path):
    from trading_os.scheduler import JOB_STATUS_SUCCESS, SchedulerStore, generate_daily

    today = date.today().isoformat()
    store = SchedulerStore(tmp_path)
    bulk = store.create_job(
        "market_data_bulk_refresh",
        effective_date=today,
        status=JOB_STATUS_SUCCESS,
    )
    elder = store.create_job("elder_scan", effective_date=today, status=JOB_STATUS_SUCCESS)
    canslim = store.create_job("canslim_scan", effective_date=today, status=JOB_STATUS_SUCCESS)

    path = generate_daily(store, effective_date=today)

    text = path.read_text(encoding="utf-8")
    assert path.name == f"{today.replace('-', '')}.md"
    assert bulk.id in text
    assert elder.id in text
    assert canslim.id in text


def test_daily_defaults_to_latest_complete_effective_date(tmp_path):
    from trading_os.scheduler import JOB_STATUS_SUCCESS, SchedulerStore, generate_daily

    effective = "2026-05-18"
    store = SchedulerStore(tmp_path)
    store.create_job(
        "market_data_bulk_refresh",
        effective_date=effective,
        status=JOB_STATUS_SUCCESS,
    )
    store.create_job("elder_scan", effective_date=effective, status=JOB_STATUS_SUCCESS)
    store.create_job("canslim_scan", effective_date=effective, status=JOB_STATUS_SUCCESS)

    path = generate_daily(store)

    assert path.name == "20260518.md"


def test_full_scan_same_effective_date_not_repeated(tmp_path):
    from trading_os.scheduler import (
        JOB_STATUS_SUCCESS,
        SchedulerStore,
        trigger_full_scan_and_daily,
    )

    today = date.today().isoformat()
    store = SchedulerStore(tmp_path)
    store.create_job("market_data_bulk_refresh", effective_date=today, status=JOB_STATUS_SUCCESS)
    store.create_job("elder_scan", effective_date=today, status=JOB_STATUS_SUCCESS)
    store.create_job("canslim_scan", effective_date=today, status=JOB_STATUS_SUCCESS)

    calls = []

    def fake_runner(args, log_path):
        calls.append(args)
        return 0

    jobs = trigger_full_scan_and_daily(store, effective_date=today, runner=fake_runner)

    assert [job.status for job in jobs] == [
        JOB_STATUS_SUCCESS,
        JOB_STATUS_SUCCESS,
        JOB_STATUS_SUCCESS,
    ]
    assert calls == []


def test_existing_successful_scan_jobs_are_reported_not_skipped_jobs(tmp_path):
    from trading_os.scheduler import JOB_STATUS_SUCCESS, SchedulerStore, trigger_full_scan_and_daily

    effective = "2026-05-18"
    store = SchedulerStore(tmp_path)
    bulk = store.create_job(
        "market_data_bulk_refresh",
        effective_date=effective,
        status=JOB_STATUS_SUCCESS,
    )
    elder = store.create_job("elder_scan", effective_date=effective, status=JOB_STATUS_SUCCESS)
    canslim = store.create_job("canslim_scan", effective_date=effective, status=JOB_STATUS_SUCCESS)

    jobs = trigger_full_scan_and_daily(store, effective_date=effective, runner=lambda args, log: 0)
    text = (tmp_path / "artifacts" / "daily" / "20260518.md").read_text(encoding="utf-8")

    assert jobs[-1].status == JOB_STATUS_SUCCESS
    assert bulk.id in text
    assert elder.id in text
    assert canslim.id in text


def test_scan_commands_use_next_trading_day_but_effective_date_output_name(tmp_path):
    from trading_os.scheduler import JOB_STATUS_SUCCESS, SchedulerStore, trigger_full_scan_and_daily

    effective = "2026-05-15"
    store = SchedulerStore(tmp_path)
    store.create_job(
        "market_data_bulk_refresh",
        effective_date=effective,
        status=JOB_STATUS_SUCCESS,
    )
    calls = []

    def fake_runner(args, log_path):
        calls.append(list(args))
        return 0

    trigger_full_scan_and_daily(store, effective_date=effective, runner=fake_runner)

    elder_date_arg = calls[0][calls[0].index("--date"):calls[0].index("--date") + 2]
    canslim_date_arg = calls[1][calls[1].index("--date"):calls[1].index("--date") + 2]

    assert ["--date", "2026-05-18"] == elder_date_arg
    assert "artifacts/scan/elder-20260515.json" in calls[0]
    assert ["--date", "2026-05-18"] == canslim_date_arg
    assert "artifacts/scan/canslim-20260515.json" in calls[1]


def test_classify_bulk_lock_running_and_stale(tmp_path):
    from trading_os.scheduler import classify_bulk_lock

    lock_path = tmp_path / "fetch_bulk.pid"
    lock_path.write_text(
        json.dumps({"job_id": "j1", "pid": os.getpid(), "command": "x"}),
        encoding="utf-8",
    )
    assert classify_bulk_lock(lock_path)["status"] == "running"

    lock_path.write_text(
        json.dumps({"job_id": "j2", "pid": 99999999, "command": "x"}),
        encoding="utf-8",
    )
    assert classify_bulk_lock(lock_path)["status"] == "stale"


def test_scheduler_jobs_are_importable_for_sqlite_jobstore(tmp_path):
    pytest.importorskip("apscheduler")
    pytest.importorskip("sqlalchemy")
    from trading_os.scheduler import scheduled_market_data_probe

    background_mod = import_module("apscheduler.schedulers.background")
    jobstore_mod = import_module("apscheduler.jobstores.sqlalchemy")
    BackgroundScheduler = background_mod.BackgroundScheduler
    SQLAlchemyJobStore = jobstore_mod.SQLAlchemyJobStore

    scheduler = BackgroundScheduler(
        timezone="Asia/Shanghai",
        jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{tmp_path / 'apscheduler.db'}")},
    )
    scheduler.start(paused=True)
    try:
        scheduler.add_job(
            scheduled_market_data_probe,
            "interval",
            seconds=3600,
            id="market_data_probe",
            args=[str(tmp_path)],
        )
        assert scheduler.get_job("market_data_probe") is not None
    finally:
        scheduler.shutdown()

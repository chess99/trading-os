from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from importlib import import_module
from pathlib import Path
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


def test_bulk_nonzero_can_still_succeed_when_only_inactive_laggards_remain(tmp_path, monkeypatch):
    import trading_os.scheduler as scheduler
    from trading_os.scheduler import JOB_STATUS_SUCCESS, SchedulerStore

    store = SchedulerStore(tmp_path)
    effective = "2026-05-19"
    scheduler.trigger_market_data_probe(
        store,
        probe_fn=lambda: {
            "effective_date": effective,
            "ready": True,
            "sentinels": {},
            "errors": {},
            "wall_clock_date": "2026-05-20",
        },
    )
    monkeypatch.setattr(
        scheduler,
        "lake_has_effective_date",
        lambda root, effective_date, progress=None: (True, effective_date),
    )
    monkeypatch.setattr(
        scheduler,
        "bulk_coverage_exception",
        lambda root, effective_date: (
            True,
            [{"symbol": "SSE:600355", "out_date": "2026-04-27", "status": "0"}],
        ),
    )

    job = scheduler.trigger_market_data_bulk_refresh(store, runner=lambda args, log_path: 1)

    assert job.status == JOB_STATUS_SUCCESS
    assert job.metadata["coverage_exception"][0]["symbol"] == "SSE:600355"


def test_probe_uses_market_effective_date_not_wall_clock_today():
    from trading_os.scheduler import intended_market_effective_date

    monday_morning = datetime(2026, 5, 18, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert intended_market_effective_date(monday_morning).isoformat() == "2026-05-15"


def test_daily_blocked_when_bulk_missing(tmp_path, monkeypatch):
    import trading_os.scheduler as scheduler
    from trading_os.scheduler import SchedulerStore, generate_daily

    store = SchedulerStore(tmp_path)
    today = date.today().isoformat()
    monkeypatch.setattr(
        scheduler,
        "intended_market_effective_date",
        lambda now=None: date.fromisoformat(today),
    )

    path = generate_daily(store, effective_date=today)

    assert path.name.endswith("-blocked.md")
    text = path.read_text(encoding="utf-8")
    assert "market data bulk refresh is incomplete" in text
    assert "No market view" in text


def test_daily_blocked_when_scans_missing(tmp_path, monkeypatch):
    import trading_os.scheduler as scheduler
    from trading_os.scheduler import JOB_STATUS_SUCCESS, SchedulerStore, generate_daily

    today = date.today().isoformat()
    store = SchedulerStore(tmp_path)
    store.create_job("market_data_bulk_refresh", effective_date=today, status=JOB_STATUS_SUCCESS)
    monkeypatch.setattr(
        scheduler,
        "intended_market_effective_date",
        lambda now=None: date.fromisoformat(today),
    )

    path = generate_daily(store, effective_date=today)

    assert path.name.endswith("-blocked.md")
    assert "CANSLIM scan is incomplete" in path.read_text(encoding="utf-8")


def test_daily_complete_only_after_bulk_and_canslim_scan(tmp_path, monkeypatch):
    import trading_os.scheduler as scheduler
    from trading_os.scheduler import JOB_STATUS_SUCCESS, SchedulerStore, generate_daily

    today = date.today().isoformat()
    store = SchedulerStore(tmp_path)
    bulk = store.create_job(
        "market_data_bulk_refresh",
        effective_date=today,
        status=JOB_STATUS_SUCCESS,
    )
    canslim = store.create_job("canslim_scan", effective_date=today, status=JOB_STATUS_SUCCESS)
    store.create_job("daily_report", effective_date=today, status=JOB_STATUS_SUCCESS)
    monkeypatch.setattr(
        scheduler,
        "intended_market_effective_date",
        lambda now=None: date.fromisoformat(today),
    )

    daily_dir = tmp_path / "artifacts" / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts" / "scan").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts" / "watchlist").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts" / "watchlist" / "pool.json").write_text(
        json.dumps(
            {
                "last_updated": "",
                "pools": {
                    "canslim": {"candidates": [], "watchlist": [], "ready": []},
                    "elder": {"candidates": [], "watchlist": [], "ready": []},
                    "value": {"candidates": [], "watchlist": [], "ready": []},
                },
                "exited": [],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "artifacts" / "scan" / f"canslim-{today.replace('-', '')}.json").write_text(
        json.dumps(
            {
                "effective_date": today,
                "signal_date": today,
                "scan_date": today,
                "system": "canslim",
                "total_scanned": 7,
                "candidates_total": 4,
                "candidates_output_count": 3,
                "candidates": [{"symbol": "SSE:600001", "rank": 1, "score": 9.0, "name": "A"}],
                "filtered_out": {"no_data": 0, "low_turnover": 0, "insufficient_data": 1, "no_signal": 3},
            }
        ),
        encoding="utf-8",
    )

    path = generate_daily(store, effective_date=today)

    text = path.read_text(encoding="utf-8")
    assert path.name == f"{today.replace('-', '')}-summary.md"
    assert bulk.id in text
    assert canslim.id in text
    assert "elder_scan" not in text
    assert "## Scan Summary" in text
    assert "matched `4` / output `3`" in text


def test_status_snapshot_reports_latest_completed_daily(tmp_path, monkeypatch):
    import trading_os.scheduler as scheduler
    from trading_os.scheduler import JOB_STATUS_SUCCESS, SchedulerStore

    completed = "2026-05-19"
    intended = "2026-05-20"
    store = SchedulerStore(tmp_path)
    store.create_job("market_data_bulk_refresh", effective_date=completed, status=JOB_STATUS_SUCCESS)
    store.create_job("elder_scan", effective_date=completed, status=JOB_STATUS_SUCCESS)
    store.create_job("canslim_scan", effective_date=completed, status=JOB_STATUS_SUCCESS)
    store.create_job("daily_report", effective_date=completed, status=JOB_STATUS_SUCCESS)
    monkeypatch.setattr(
        scheduler,
        "intended_market_effective_date",
        lambda now=None: date.fromisoformat(intended),
    )

    snapshot = store.status_snapshot()

    assert snapshot["daily_effective_date"] == intended
    assert snapshot["latest_completed_daily_effective_date"] == completed
    assert snapshot["latest_completed_daily_report"].endswith("20260519-summary.md")


def test_daily_defaults_to_intended_effective_date_and_does_not_fallback(tmp_path, monkeypatch):
    import trading_os.scheduler as scheduler
    from trading_os.scheduler import JOB_STATUS_SUCCESS, SchedulerStore, generate_daily

    intended = "2026-05-19"
    completed = "2026-05-18"
    store = SchedulerStore(tmp_path)
    store.create_job(
        "market_data_bulk_refresh",
        effective_date=completed,
        status=JOB_STATUS_SUCCESS,
    )
    store.create_job("elder_scan", effective_date=completed, status=JOB_STATUS_SUCCESS)
    store.create_job("canslim_scan", effective_date=completed, status=JOB_STATUS_SUCCESS)
    store.create_job("daily_report", effective_date=completed, status=JOB_STATUS_SUCCESS)
    monkeypatch.setattr(
        scheduler,
        "intended_market_effective_date",
        lambda now=None: date.fromisoformat(intended),
    )

    path = generate_daily(store)

    assert path.name == "20260519-blocked.md"
    assert "market data bulk refresh is incomplete" in path.read_text(encoding="utf-8")


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
    store.create_job("daily_report", effective_date=today, status=JOB_STATUS_SUCCESS)

    calls = []

    def fake_runner(args, log_path):
        calls.append(args)
        return 0

    jobs = trigger_full_scan_and_daily(store, effective_date=today, runner=fake_runner)

    assert [job.status for job in jobs] == ["skipped"]
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
    store.create_job("daily_report", effective_date=effective, status=JOB_STATUS_SUCCESS)

    jobs = trigger_full_scan_and_daily(store, effective_date=effective, runner=lambda args, log: 0)
    assert jobs[0].status == "skipped"
    assert jobs[0].metadata["existing_job_id"]


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

    canslim_call = next(call for call in calls if "scan-canslim" in call)
    canslim_date_arg = canslim_call[canslim_call.index("--date"):canslim_call.index("--date") + 2]

    assert not any("scan-elder" in call for call in calls)
    assert ["--date", "2026-05-18"] == canslim_date_arg
    assert ["--effective-date", "2026-05-15"] == canslim_call[canslim_call.index("--effective-date"):canslim_call.index("--effective-date") + 2]
    assert "artifacts/scan/canslim-20260515.json" in canslim_call


def test_daily_blocked_when_daily_report_missing(tmp_path, monkeypatch):
    import trading_os.scheduler as scheduler
    from trading_os.scheduler import JOB_STATUS_SUCCESS, SchedulerStore, generate_daily

    effective = "2026-05-18"
    store = SchedulerStore(tmp_path)
    store.create_job("market_data_bulk_refresh", effective_date=effective, status=JOB_STATUS_SUCCESS)
    store.create_job("elder_scan", effective_date=effective, status=JOB_STATUS_SUCCESS)
    store.create_job("canslim_scan", effective_date=effective, status=JOB_STATUS_SUCCESS)
    monkeypatch.setattr(
        scheduler,
        "intended_market_effective_date",
        lambda now=None: date.fromisoformat(effective),
    )

    path = generate_daily(store, effective_date=effective)

    assert path.name == "20260518-blocked.md"
    assert "daily report is incomplete" in path.read_text(encoding="utf-8")


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


def test_trigger_full_scan_and_daily_runs_canslim_only(tmp_path: Path) -> None:
    """Daily 默认只跑 CANSLIM，不再跑宽口径 Elder 扫描。"""
    from trading_os.scheduler import SchedulerStore, trigger_full_scan_and_daily
    from trading_os.scheduler import JOB_STATUS_SUCCESS

    store = SchedulerStore(tmp_path)

    bulk = store.create_job("market_data_bulk_refresh", effective_date="2026-05-19")
    store.update_job(bulk.id, status=JOB_STATUS_SUCCESS, ended=True)

    commands: list[str] = []

    def slow_runner(args: list, log_path) -> int:
        cmd = " ".join(args)
        commands.append(cmd)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok")
        return 0

    trigger_full_scan_and_daily(store, effective_date="2026-05-19", runner=slow_runner)

    assert len(commands) == 1
    assert "scan-canslim" in commands[0]
    assert "scan-elder" not in commands[0]


def test_two_scan_processes_can_open_lake_simultaneously(tmp_path: Path) -> None:
    """两个 DataPipeline（read_only=True）可同时存在，不会互相阻塞。"""
    from concurrent.futures import ThreadPoolExecutor
    from trading_os.data.lake import LocalDataLake
    from trading_os.data.pipeline import DataPipeline

    lake_path = tmp_path / "data"
    lake_path.mkdir()
    (lake_path / "parquet" / "bars").mkdir(parents=True)

    def make_pipeline_and_list(i: int) -> list:
        lake = LocalDataLake(lake_path, read_only=True)
        pipe = DataPipeline(lake)
        return pipe.available_symbols()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(make_pipeline_and_list, range(2)))

    assert results[0] == results[1]

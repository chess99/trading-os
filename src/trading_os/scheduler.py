from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Sequence
from zoneinfo import ZoneInfo

from .paths import repo_root

JobRunner = Callable[[Sequence[str], Path], int]

JOB_STATUS_PENDING = "pending"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_SUCCESS = "success"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_NOT_READY = "not_ready"
JOB_STATUS_SKIPPED = "skipped"

PROBE_SENTINELS = (
    ("SSE", "600000", "equity"),
    ("SZSE", "000001", "equity"),
    ("SSE", "000001", "index"),
)
MARKET_TZ = ZoneInfo("Asia/Shanghai")
PROBE_WINDOW_TEXT = "18:30-22:30 every 30 minutes"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def scheduler_db_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "data" / "scheduler.db"


def jobs_dir(root: Path | None = None, day: date | None = None) -> Path:
    day_str = (day or date.today()).strftime("%Y%m%d")
    return (root or repo_root()) / "artifacts" / "jobs" / day_str


def status_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "artifacts" / "jobs" / "status.json"


def current_fetch_bulk_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "artifacts" / "jobs" / "current_fetch_bulk.json"


def daily_summary_path(
    effective_date: str,
    *,
    root: Path | None = None,
    historical: bool = False,
) -> Path:
    suffix = "-historical-summary" if historical else "-summary"
    return (root or repo_root()) / "artifacts" / "daily" / f"{effective_date.replace('-', '')}{suffix}.md"


def research_daily_path(
    effective_date: str,
    *,
    root: Path | None = None,
) -> Path:
    return (root or repo_root()) / "artifacts" / "daily" / f"{effective_date.replace('-', '')}.md"


@dataclass(slots=True)
class JobRecord:
    id: str
    name: str
    status: str = JOB_STATUS_PENDING
    effective_date: str | None = None
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    ended_at: str | None = None
    updated_at: str = field(default_factory=utc_now)
    metadata: dict = field(default_factory=dict)
    error: str | None = None
    log_path: str | None = None


class SchedulerStore:
    def __init__(self, root: Path | None = None):
        self.root = root or repo_root()
        self.db_path = scheduler_db_path(self.root)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._status_lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    effective_date TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    ended_at TEXT,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    error TEXT,
                    log_path TEXT
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_name_date ON jobs(name, effective_date)"
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_updated ON jobs(updated_at)")

    def create_job(
        self,
        name: str,
        *,
        effective_date: str | None = None,
        metadata: dict | None = None,
        status: str = JOB_STATUS_PENDING,
        log_path: Path | None = None,
    ) -> JobRecord:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        job = JobRecord(
            id=f"{name}-{stamp}",
            name=name,
            status=status,
            effective_date=effective_date,
            metadata=metadata or {},
            log_path=str(log_path) if log_path else None,
        )
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO jobs (
                    id, name, status, effective_date, created_at, started_at,
                    ended_at, updated_at, metadata_json, error, log_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.name,
                    job.status,
                    job.effective_date,
                    job.created_at,
                    job.started_at,
                    job.ended_at,
                    job.updated_at,
                    json.dumps(job.metadata, ensure_ascii=False, sort_keys=True),
                    job.error,
                    job.log_path,
                ),
            )
        self.write_status()
        return job

    def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        metadata: dict | None = None,
        error: str | None = None,
        started: bool = False,
        ended: bool = False,
    ) -> JobRecord:
        job = self.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        now = utc_now()
        if status is not None:
            job.status = status
        if metadata:
            job.metadata.update(metadata)
        if error is not None:
            job.error = error
        if started and job.started_at is None:
            job.started_at = now
        if ended:
            job.ended_at = now
        job.updated_at = now
        with self._connect() as con:
            con.execute(
                """
                UPDATE jobs
                SET status=?, started_at=?, ended_at=?, updated_at=?,
                    metadata_json=?, error=?
                WHERE id=?
                """,
                (
                    job.status,
                    job.started_at,
                    job.ended_at,
                    job.updated_at,
                    json.dumps(job.metadata, ensure_ascii=False, sort_keys=True),
                    job.error,
                    job.id,
                ),
            )
        self.write_status()
        return job

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._connect() as con:
            row = con.execute("SELECT * FROM jobs WHERE id=?", [job_id]).fetchone()
        return _row_to_job(row) if row else None

    def latest_job(
        self,
        name: str,
        *,
        effective_date: str | None = None,
        statuses: set[str] | None = None,
    ) -> JobRecord | None:
        query = "SELECT * FROM jobs WHERE name=?"
        params: list[str] = [name]
        if effective_date is not None:
            query += " AND effective_date=?"
            params.append(effective_date)
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            query += f" AND status IN ({placeholders})"
            params.extend(sorted(statuses))
        query += " ORDER BY updated_at DESC LIMIT 1"
        with self._connect() as con:
            row = con.execute(query, params).fetchone()
        return _row_to_job(row) if row else None

    def list_jobs(self, limit: int = 50) -> list[JobRecord]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM jobs ORDER BY updated_at DESC LIMIT ?",
                [int(limit)],
            ).fetchall()
        return [_row_to_job(row) for row in rows]

    def status_snapshot(self) -> dict:
        jobs = self.list_jobs(limit=20)
        latest_by_name: dict[str, dict] = {}
        for job in jobs:
            latest_by_name.setdefault(job.name, _job_to_dict(job))
        fetch_progress = load_json(current_fetch_bulk_path(self.root))
        effective_date = default_daily_effective_date(self)
        blocked_reason = compute_daily_blocker(self, effective_date)
        latest_completed_daily = latest_complete_daily_effective_date(self)
        return {
            "updated_at": utc_now(),
            "scheduler_db": str(self.db_path),
            "latest_jobs": latest_by_name,
            "fetch_bulk": fetch_progress,
            "daily_effective_date": effective_date,
            "daily_blocked_reason": blocked_reason,
            "latest_completed_daily_effective_date": latest_completed_daily,
            "latest_completed_daily_report": (
                str(daily_summary_path(latest_completed_daily, root=self.root))
                if latest_completed_daily
                else None
            ),
            "next_probe_window": PROBE_WINDOW_TEXT,
        }

    def write_status(self) -> None:
        path = status_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._status_lock:
            payload = json.dumps(self.status_snapshot(), ensure_ascii=False, indent=2)
            path.write_text(payload, encoding="utf-8")


def _row_to_job(row: sqlite3.Row) -> JobRecord:
    return JobRecord(
        id=row["id"],
        name=row["name"],
        status=row["status"],
        effective_date=row["effective_date"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        updated_at=row["updated_at"],
        metadata=json.loads(row["metadata_json"] or "{}"),
        error=row["error"],
        log_path=row["log_path"],
    )


def _job_to_dict(job: JobRecord) -> dict:
    data = asdict(job)
    data["metadata"] = job.metadata
    return data


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"error": f"invalid json: {path}"}


def default_runner(args: Sequence[str], log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"$ {' '.join(args)}\n")
        log.flush()
        proc = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, text=True, check=False)
        log.write(f"\nexit_code={proc.returncode}\n")
        return int(proc.returncode)


def intended_market_effective_date(now: datetime | None = None) -> date:
    from .data.calendar import WeekdayCalendar

    local_now = (now or datetime.now(MARKET_TZ)).astimezone(MARKET_TZ)
    cal = WeekdayCalendar()
    today = local_now.date()
    if not cal.is_trading_day(today):
        return cal.prev_trading_day(today)
    market_close_buffer = local_now.replace(hour=15, minute=30, second=0, microsecond=0)
    if local_now >= market_close_buffer:
        return today
    return cal.prev_trading_day(today)


def signal_date_for_effective_date(effective_date: str) -> str:
    from .data.calendar import WeekdayCalendar

    return WeekdayCalendar().next_trading_day(date.fromisoformat(effective_date)).isoformat()


def probe_market_data(today: date | None = None) -> dict:
    from .data.schema import Adjustment, AssetType, Exchange
    from .data.sources.akshare_source import fetch_daily_bars

    target_date = today or intended_market_effective_date()
    wall_clock_date = datetime.now(MARKET_TZ).date()
    sentinels: dict[str, str | None] = {}
    errors: dict[str, str] = {}
    latest_dates: list[date] = []
    for exchange, ticker, asset_kind in PROBE_SENTINELS:
        symbol = f"{exchange}:{ticker}"
        try:
            asset_type = AssetType.INDEX if asset_kind == "index" else AssetType.EQUITY
            adjustment = Adjustment.NONE if asset_type == AssetType.INDEX else Adjustment.QFQ
            df, source = fetch_daily_bars(
                ticker,
                exchange=Exchange(exchange),
                start=(target_date - timedelta(days=10)).isoformat(),
                end=target_date.isoformat(),
                adjustment=adjustment,
                asset_type=asset_type,
            )
            if df.empty:
                sentinels[symbol] = None
                errors[symbol] = f"empty response from {source}"
                continue
            latest = df["ts"].max().date()
            sentinels[symbol] = latest.isoformat()
            latest_dates.append(latest)
        except Exception as exc:
            sentinels[symbol] = None
            errors[symbol] = str(exc)[:200]

    effective = min(latest_dates).isoformat() if len(latest_dates) == len(PROBE_SENTINELS) else None
    ready = effective is not None and effective >= target_date.isoformat()
    return {
        "effective_date": effective,
        "target_effective_date": target_date.isoformat(),
        "ready": ready,
        "sentinels": sentinels,
        "errors": errors,
        "wall_clock_date": wall_clock_date.isoformat(),
    }


def trigger_market_data_probe(
    store: SchedulerStore,
    *,
    probe_fn: Callable[[], dict] = probe_market_data,
) -> JobRecord:
    job = store.create_job("market_data_probe")
    store.update_job(job.id, status=JOB_STATUS_RUNNING, started=True)
    result = probe_fn()
    status = JOB_STATUS_SUCCESS if result.get("ready") else JOB_STATUS_NOT_READY
    return store.update_job(
        job.id,
        status=status,
        metadata=result,
        ended=True,
        error=None if status == JOB_STATUS_SUCCESS else "market data not ready",
    )


def trigger_market_data_bulk_refresh(
    store: SchedulerStore,
    *,
    effective_date: str | None = None,
    runner: JobRunner = default_runner,
) -> JobRecord:
    effective_date = effective_date or _latest_ready_probe_date(store)
    if not effective_date:
        job = store.create_job("market_data_bulk_refresh", status=JOB_STATUS_NOT_READY)
        return store.update_job(job.id, error="no successful probe effective_date", ended=True)
    existing = store.latest_job(
        "market_data_bulk_refresh",
        effective_date=effective_date,
        statuses={JOB_STATUS_SUCCESS, JOB_STATUS_RUNNING},
    )
    if existing:
        return store.create_job(
            "market_data_bulk_refresh",
            effective_date=effective_date,
            status=JOB_STATUS_SKIPPED,
            metadata={"reason": f"existing {existing.status} job", "existing_job_id": existing.id},
        )

    log_path = jobs_dir(store.root) / f"bulk-{effective_date}.log"
    job = store.create_job(
        "market_data_bulk_refresh",
        effective_date=effective_date,
        log_path=log_path,
    )
    store.update_job(job.id, status=JOB_STATUS_RUNNING, started=True)
    cmd = [
        sys.executable,
        "-m",
        "trading_os",
        "fetch-ak-bulk",
        "--start",
        effective_date,
        "--end",
        effective_date,
        "--adjustment",
        "qfq",
    ]
    code = runner(cmd, log_path)
    progress = load_json(current_fetch_bulk_path(store.root))
    ok, latest = lake_has_effective_date(store.root, effective_date, progress=progress)
    if code != 0:
        exception_ok, inactive = bulk_coverage_exception(store.root, effective_date)
        if ok and exception_ok:
            return store.update_job(
                job.id,
                status=JOB_STATUS_SUCCESS,
                metadata={
                    "lake_latest_qfq": latest,
                    "coverage_exception": inactive,
                    "warning": "inactive laggards excluded from blocking bulk success",
                },
                ended=True,
            )
        return store.update_job(
            job.id,
            status=JOB_STATUS_FAILED,
            error=f"exit code {code}",
            ended=True,
        )
    if not ok:
        return store.update_job(
            job.id,
            status=JOB_STATUS_FAILED,
            error=f"bulk coverage incomplete; lake qfq latest {latest or 'unknown'}",
            ended=True,
        )
    return store.update_job(
        job.id,
        status=JOB_STATUS_SUCCESS,
        metadata={"lake_latest_qfq": latest},
        ended=True,
    )


def trigger_full_scan_and_daily(
    store: SchedulerStore,
    *,
    effective_date: str | None = None,
    runner: JobRunner = default_runner,
    force: bool = False,
) -> list[JobRecord]:
    effective_date = effective_date or _latest_success_date(store, "market_data_bulk_refresh")
    if not effective_date:
        job = store.create_job("full_scan_and_daily", status=JOB_STATUS_NOT_READY)
        return [store.update_job(job.id, error="no successful bulk refresh", ended=True)]
    existing_orchestrator = store.latest_job(
        "full_scan_and_daily",
        effective_date=effective_date,
        statuses={JOB_STATUS_RUNNING},
    )
    if existing_orchestrator:
        return [
            store.create_job(
                "full_scan_and_daily",
                effective_date=effective_date,
                status=JOB_STATUS_SKIPPED,
                metadata={
                    "reason": "full_scan_and_daily already running",
                    "existing_job_id": existing_orchestrator.id,
                },
            )
        ]
    bulk = store.latest_job(
        "market_data_bulk_refresh",
        effective_date=effective_date,
        statuses={JOB_STATUS_SUCCESS},
    )
    if not bulk:
        job = store.create_job(
            "full_scan_and_daily",
            effective_date=effective_date,
            status=JOB_STATUS_NOT_READY,
        )
        return [store.update_job(job.id, error="bulk refresh incomplete", ended=True)]
    existing_daily = store.latest_job(
        "daily_report",
        effective_date=effective_date,
        statuses={JOB_STATUS_SUCCESS},
    )
    if existing_daily and not force:
        return [
            store.create_job(
                "full_scan_and_daily",
                effective_date=effective_date,
                status=JOB_STATUS_SKIPPED,
                metadata={
                    "reason": "daily already completed",
                    "existing_job_id": existing_daily.id,
                },
            )
        ]

    orchestrator = store.create_job("full_scan_and_daily", effective_date=effective_date)
    orchestrator = store.update_job(orchestrator.id, status=JOB_STATUS_RUNNING, started=True)
    results: list[JobRecord] = [orchestrator]
    signal_date = signal_date_for_effective_date(effective_date)
    effective_compact = effective_date.replace("-", "")
    with ThreadPoolExecutor(max_workers=2) as _scan_pool:
        elder_future = _scan_pool.submit(
            _ensure_scan_job,
            store,
            name="elder_scan",
            effective_date=effective_date,
            command=[
                sys.executable,
                "-m",
                "trading_os",
                "scan-elder",
                "--date",
                signal_date,
                "--effective-date",
                effective_date,
                "--output",
                f"artifacts/scan/elder-{effective_compact}.json",
            ],
            runner=runner,
            force=force,
        )
        canslim_future = _scan_pool.submit(
            _ensure_scan_job,
            store,
            name="canslim_scan",
            effective_date=effective_date,
            command=[
                sys.executable,
                "-m",
                "trading_os",
                "scan-canslim",
                "--date",
                signal_date,
                "--effective-date",
                effective_date,
                "--output",
                f"artifacts/scan/canslim-{effective_compact}.json",
            ],
            runner=runner,
            force=force,
        )
    elder = elder_future.result()
    canslim = canslim_future.result()
    results.append(elder)
    results.append(canslim)
    if elder.status != JOB_STATUS_SUCCESS or canslim.status != JOB_STATUS_SUCCESS:
        daily = store.create_job(
            "daily_report",
            effective_date=effective_date,
            status=JOB_STATUS_NOT_READY,
        )
        results.append(store.update_job(daily.id, error="scan incomplete", ended=True))
        write_blocked_daily(store, effective_date, "scan incomplete")
        store.update_job(orchestrator.id, status=JOB_STATUS_FAILED, error="scan incomplete", ended=True)
        return results

    daily = store.create_job(
        "daily_report",
        effective_date=effective_date,
        metadata={
            "bulk_job_id": bulk.id,
            "elder_scan_job_id": elder.id,
            "canslim_scan_job_id": canslim.id,
            "scan_signal_date": signal_date,
        },
    )
    store.update_job(daily.id, status=JOB_STATUS_RUNNING, started=True)
    try:
        write_complete_daily(store, effective_date, bulk, elder, canslim)
    except Exception as exc:
        results.append(
            store.update_job(
                daily.id,
                status=JOB_STATUS_FAILED,
                error=str(exc)[:300],
                ended=True,
            )
        )
        store.update_job(
            orchestrator.id,
            status=JOB_STATUS_FAILED,
            error=f"daily report failed: {str(exc)[:260]}",
            ended=True,
        )
        raise
    results.append(store.update_job(daily.id, status=JOB_STATUS_SUCCESS, ended=True))
    store.update_job(orchestrator.id, status=JOB_STATUS_SUCCESS, ended=True)
    return results


def _ensure_scan_job(
    store: SchedulerStore,
    *,
    name: str,
    effective_date: str,
    command: Sequence[str],
    runner: JobRunner,
    force: bool,
) -> JobRecord:
    existing = store.latest_job(name, effective_date=effective_date, statuses={JOB_STATUS_SUCCESS})
    if existing and not force:
        return existing
    log_path = jobs_dir(store.root) / f"{name}-{effective_date}.log"
    job = store.create_job(name, effective_date=effective_date, log_path=log_path)
    store.update_job(job.id, status=JOB_STATUS_RUNNING, started=True)
    code = runner(command, log_path)
    if code != 0:
        return store.update_job(
            job.id,
            status=JOB_STATUS_FAILED,
            error=f"exit code {code}",
            ended=True,
        )
    return store.update_job(job.id, status=JOB_STATUS_SUCCESS, ended=True)


def compute_daily_blocker(
    store: SchedulerStore,
    effective_date: str,
    *,
    allow_historical: bool = False,
) -> str | None:
    if allow_historical:
        pass
    bulk = store.latest_job(
        "market_data_bulk_refresh",
        effective_date=effective_date,
        statuses={JOB_STATUS_SUCCESS},
    )
    if not bulk:
        progress = load_json(current_fetch_bulk_path(store.root))
        if progress and progress.get("status") == JOB_STATUS_RUNNING:
            return "market data bulk refresh is running"
        return "market data bulk refresh is incomplete"
    elder = store.latest_job(
        "elder_scan",
        effective_date=effective_date,
        statuses={JOB_STATUS_SUCCESS},
    )
    if not elder:
        return "Elder scan is incomplete"
    canslim = store.latest_job(
        "canslim_scan",
        effective_date=effective_date,
        statuses={JOB_STATUS_SUCCESS},
    )
    if not canslim:
        return "CANSLIM scan is incomplete"
    daily = store.latest_job(
        "daily_report",
        effective_date=effective_date,
        statuses={JOB_STATUS_SUCCESS},
    )
    if not daily:
        return "daily report is incomplete"
    return None


def write_blocked_daily(store: SchedulerStore, effective_date: str, reason: str) -> Path:
    out = (
        store.root
        / "artifacts"
        / "daily"
        / "tmp"
        / f"{effective_date.replace('-', '')}-blocked.md"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    snapshot = store.status_snapshot()
    progress = snapshot.get("fetch_bulk") or {}
    lines = [
        f"# Daily blocked - {effective_date}",
        "",
        f"- intended_effective_date: `{default_daily_effective_date(store)}`",
        f"- effective_date: `{effective_date}`",
        f"- reason: {reason}",
        f"- updated_at: `{snapshot['updated_at']}`",
        f"- next_probe_window: {snapshot['next_probe_window']}",
        "",
        "## Current Progress",
        "",
        f"- fetch_bulk: `{progress.get('done', 0)}/{progress.get('total', 0)}`",
        f"- eta_sec: `{progress.get('eta_sec')}`",
        f"- running_job_id: `{progress.get('job_id')}`",
        "",
        "## Diagnostics",
        "",
        "- `python -m trading_os scheduler status`",
        "- `python -m trading_os scheduler jobs`",
        "- `tail -f artifacts/fetch_bulk_progress.log`",
        "",
        "No market view, scan changes, symbol conclusion, or trading action is emitted "
        "while upstream jobs are incomplete.",
        "Pool state is not updated in blocked mode.",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def write_complete_daily(
    store: SchedulerStore,
    effective_date: str,
    bulk: JobRecord,
    elder: JobRecord,
    canslim: JobRecord,
    *,
    historical: bool = False,
) -> Path:
    import json
    from .cli_internal.commands.pool import _load_pool, sync_candidates_from_scan

    out = daily_summary_path(effective_date, root=store.root, historical=historical)
    out.parent.mkdir(parents=True, exist_ok=True)
    pool_path = store.root / "artifacts" / "watchlist" / "pool.json"
    title = "Historical Daily Summary" if historical else "Daily Workflow Summary"
    effective_compact = effective_date.replace("-", "")
    elder_scan_path = store.root / "artifacts" / "scan" / f"elder-{effective_compact}.json"
    canslim_scan_path = store.root / "artifacts" / "scan" / f"canslim-{effective_compact}.json"
    elder_scan = json.loads(elder_scan_path.read_text(encoding="utf-8")) if elder_scan_path.exists() else {}
    canslim_scan = json.loads(canslim_scan_path.read_text(encoding="utf-8")) if canslim_scan_path.exists() else {}
    signal_date = (
        canslim_scan.get("signal_date")
        or elder_scan.get("signal_date")
        or signal_date_for_effective_date(effective_date)
    )
    canslim_sync = sync_candidates_from_scan(
        system="canslim",
        scan_data=canslim_scan or {"candidates": []},
        apply=not historical and canslim_scan_path.exists(),
        scan_file=str(canslim_scan_path),
        scan_job_id=canslim.id,
        pool_path=pool_path,
    )
    pool_data = _load_pool(pool_path)
    research_path = research_daily_path(effective_date, root=store.root)
    ready_items = []
    for sys_name in ["canslim", "elder", "value"]:
        ready_items.extend(
            [(sys_name, item) for item in pool_data["pools"].get(sys_name, {}).get("ready", [])]
        )
    canslim_pool = pool_data["pools"].get("canslim", {})
    lines = [
        f"# {title} - {effective_date}",
        "",
        f"- effective_date: `{effective_date}`",
        f"- signal_date: `{signal_date}`",
        f"- market_data_bulk_refresh: `{bulk.id}` ({bulk.status})",
        f"- elder_scan: `{elder.id}` ({elder.status})",
        f"- canslim_scan: `{canslim.id}` ({canslim.status})",
        (
            f"- research_report: `{research_path}`"
            if research_path.exists()
            else "- research_report: `not generated`"
        ),
        "",
        "## Scan Summary",
        "",
        (
            f"- Elder: scanned `{elder_scan.get('total_scanned', 0)}` / "
            f"matched `{elder_scan.get('candidates_total', len(elder_scan.get('candidates', [])))}` / "
            f"output `{elder_scan.get('candidates_output_count', len(elder_scan.get('candidates', [])))}`"
        ),
        (
            f"- CANSLIM: scanned `{canslim_scan.get('total_scanned', 0)}` / "
            f"matched `{canslim_scan.get('candidates_total', len(canslim_scan.get('candidates', [])))}` / "
            f"output `{canslim_scan.get('candidates_output_count', len(canslim_scan.get('candidates', [])))}`"
        ),
        "",
        "## Pool Update",
        "",
        f"- CANSLIM scan matched total: `{canslim_sync['scan_candidates_total']}`",
        f"- CANSLIM scan output considered: `{canslim_sync['scan_candidates']}`",
        f"- Eligible after policy filter: `{canslim_sync['eligible_after_policy_filter']}`",
        f"- Actually written to candidates: `{canslim_sync['actually_written']}`",
        f"- CANSLIM candidates rebuilt: `{canslim_sync['previous_candidates']}` -> `{canslim_sync['next_candidates']}`",
        f"- Added: `{', '.join(canslim_sync['added']) if canslim_sync['added'] else 'none'}`",
        f"- Dropped: `{', '.join(canslim_sync['dropped']) if canslim_sync['dropped'] else 'none'}`",
        f"- Already active in watchlist/ready: `{', '.join(canslim_sync['already_active']) if canslim_sync['already_active'] else 'none'}`",
        f"- Blocked re-entry: `{', '.join(canslim_sync['blocked_reentry']) if canslim_sync['blocked_reentry'] else 'none'}`",
        f"- Current CANSLIM watchlist/ready: watchlist `{len(canslim_pool.get('watchlist', []))}` / ready `{len(canslim_pool.get('ready', []))}`",
        "",
        "## Immediate Actions",
        "",
    ]
    if ready_items:
        for sys_name, item in ready_items:
            lines.append(
                f"- [{sys_name.upper()}] `{item['symbol']}` {item.get('name', '')} "
                f"trigger={item.get('trigger_price')} stop={item.get('stop_loss')}"
            )
    else:
        lines.append("- none")
    lines.extend([
        "",
        "## Notes",
        "",
        "- This file is a scheduler-generated workflow summary, not the research daily.",
        "- Value pool is carried forward from existing manual tracking; it is not rebuilt by scheduler daily.",
        "- This report is generated only after all upstream jobs for the same effective_date completed.",
    ])
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def generate_daily(
    store: SchedulerStore,
    *,
    effective_date: str | None = None,
    allow_historical: bool = False,
) -> Path:
    default_effective = default_daily_effective_date(store)
    if effective_date is not None and not allow_historical and effective_date != default_effective:
        return write_blocked_daily(
            store,
            effective_date,
            f"historical effective_date requires --allow-historical; latest is {default_effective}",
        )
    effective_date = effective_date or default_effective
    reason = compute_daily_blocker(store, effective_date, allow_historical=allow_historical)
    if reason:
        return write_blocked_daily(store, effective_date, reason)
    bulk = store.latest_job(
        "market_data_bulk_refresh",
        effective_date=effective_date,
        statuses={JOB_STATUS_SUCCESS},
    )
    elder = store.latest_job(
        "elder_scan",
        effective_date=effective_date,
        statuses={JOB_STATUS_SUCCESS},
    )
    canslim = store.latest_job(
        "canslim_scan",
        effective_date=effective_date,
        statuses={JOB_STATUS_SUCCESS},
    )
    daily = store.latest_job(
        "daily_report",
        effective_date=effective_date,
        statuses={JOB_STATUS_SUCCESS},
    )
    if bulk is None or elder is None or canslim is None or daily is None:
        return write_blocked_daily(
            store,
            effective_date,
            "upstream state changed during generation",
        )
    return write_complete_daily(
        store,
        effective_date,
        bulk,
        elder,
        canslim,
        historical=allow_historical and effective_date != date.today().isoformat(),
    )


def lake_has_effective_date(
    root: Path,
    effective_date: str,
    *,
    progress: dict | None = None,
) -> tuple[bool, str | None]:
    if progress is not None:
        if (
            progress.get("effective_date") != effective_date
            or progress.get("status") != JOB_STATUS_SUCCESS
        ):
            return False, None
        done = int(progress.get("done") or 0)
        total = int(progress.get("total") or 0)
        success = int(progress.get("success") or 0)
        failed = int(progress.get("failed") or 0)
        if total <= 0 or done < total or success + failed < total or failed > 0:
            return False, None
    try:
        from .data.lake import LocalDataLake

        lake = LocalDataLake(root / "data")
        con = lake.connect()
        if not lake.has_bar_files():
            con.close()
            return False, None
        row = con.execute(
            "SELECT MAX(ts)::DATE AS latest "
            f"FROM {lake._bars_glob_sql()} "
            "WHERE timeframe='1d' AND adjustment='qfq'"
        ).fetchone()
        con.close()
    except Exception:
        return False, None
    if not row or row[0] is None:
        return False, None
    latest = row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0])
    return latest >= effective_date, latest


def lagging_qfq_symbols(root: Path, effective_date: str) -> list[tuple[str, str]]:
    try:
        import duckdb

        con = duckdb.connect(str(root / "data" / "lake.duckdb"), read_only=False)
        rows = con.execute(
            """
            SELECT symbol, CAST(MAX(ts) AS DATE)::VARCHAR AS latest
            FROM read_parquet(?, union_by_name=true)
            WHERE timeframe='1d' AND adjustment='qfq'
            GROUP BY symbol
            HAVING CAST(MAX(ts) AS DATE) < CAST(? AS DATE)
            ORDER BY latest DESC, symbol
            """,
            [str(root / "data" / "parquet" / "bars" / "*.parquet"), effective_date],
        ).fetchall()
        con.close()
        return [(str(symbol), str(latest)) for symbol, latest in rows]
    except Exception:
        return []


def inactive_laggards_as_of(effective_date: str, laggards: list[tuple[str, str]]) -> list[dict]:
    if not laggards:
        return []
    try:
        import baostock as bs

        lg = bs.login()
        if lg.error_code != "0":
            return []
        try:
            import baostock.common.context as _bs_ctx

            sock = getattr(_bs_ctx, "default_socket", None)
            if sock is not None:
                sock.settimeout(30)
        except Exception:
            pass
        inactive = []
        for symbol, latest in laggards:
            exch, ticker = symbol.split(":", 1)
            code = f"{'sh' if exch == 'SSE' else 'sz'}.{ticker}"
            rs = bs.query_stock_basic(code=code)
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
            if not rows:
                continue
            row = rows[0]
            out_date = row[3]
            status = row[5]
            if status != "1" and out_date and out_date <= effective_date:
                inactive.append(
                    {
                        "symbol": symbol,
                        "latest": latest,
                        "name": row[1],
                        "out_date": out_date,
                        "status": status,
                    }
                )
        bs.logout()
        return inactive
    except Exception:
        return []


def bulk_coverage_exception(root: Path, effective_date: str) -> tuple[bool, list[dict]]:
    laggards = lagging_qfq_symbols(root, effective_date)
    if not laggards:
        return False, []
    inactive = inactive_laggards_as_of(effective_date, laggards)
    if inactive and len(inactive) == len(laggards):
        return True, inactive
    return False, inactive


def classify_bulk_lock(lock_path: Path) -> dict:
    if not lock_path.exists():
        return {"status": "absent"}
    try:
        raw = lock_path.read_text(encoding="utf-8").strip()
        data = json.loads(raw) if raw.startswith("{") else {"pid": int(raw)}
        pid = int(data["pid"])
        os.kill(pid, 0)
        return {"status": "running", **data}
    except ProcessLookupError:
        return {"status": "stale", "raw": lock_path.read_text(encoding="utf-8", errors="replace")}
    except PermissionError:
        return {"status": "unknown", "raw": lock_path.read_text(encoding="utf-8", errors="replace")}
    except Exception as exc:
        return {"status": "invalid", "error": str(exc)}


def _latest_ready_probe_date(store: SchedulerStore) -> str | None:
    job = store.latest_job("market_data_probe", statuses={JOB_STATUS_SUCCESS})
    if not job:
        return None
    return job.metadata.get("effective_date")


def _latest_success_date(store: SchedulerStore, name: str) -> str | None:
    job = store.latest_job(name, statuses={JOB_STATUS_SUCCESS})
    return job.effective_date if job else None


def latest_complete_daily_effective_date(store: SchedulerStore) -> str | None:
    query = """
        SELECT b.effective_date
        FROM jobs b
        WHERE b.name='market_data_bulk_refresh'
          AND b.status=?
          AND EXISTS (
            SELECT 1 FROM jobs e
            WHERE e.name='elder_scan'
              AND e.status=?
              AND e.effective_date=b.effective_date
          )
          AND EXISTS (
            SELECT 1 FROM jobs c
            WHERE c.name='canslim_scan'
              AND c.status=?
              AND c.effective_date=b.effective_date
          )
          AND EXISTS (
            SELECT 1 FROM jobs d
            WHERE d.name='daily_report'
              AND d.status=?
              AND d.effective_date=b.effective_date
          )
        ORDER BY b.effective_date DESC, b.updated_at DESC
        LIMIT 1
    """
    with store._connect() as con:
        row = con.execute(
            query,
            [JOB_STATUS_SUCCESS, JOB_STATUS_SUCCESS, JOB_STATUS_SUCCESS, JOB_STATUS_SUCCESS],
        ).fetchone()
    return row[0] if row else None


def default_daily_effective_date(store: SchedulerStore) -> str:
    return intended_market_effective_date().isoformat()


def scheduled_market_data_probe(root: str | None = None) -> None:
    trigger_market_data_probe(SchedulerStore(Path(root) if root else None))


def scheduled_market_data_bulk_refresh(root: str | None = None) -> None:
    trigger_market_data_bulk_refresh(SchedulerStore(Path(root) if root else None))


def scheduled_full_scan_and_daily(root: str | None = None) -> None:
    trigger_full_scan_and_daily(SchedulerStore(Path(root) if root else None))


def cmd_scheduler(ns: argparse.Namespace) -> int:
    store = SchedulerStore()
    action = ns.scheduler_cmd
    if action == "status":
        store.write_status()
        snapshot = load_json(status_path(store.root)) or {}
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0
    if action == "jobs":
        for job in store.list_jobs(limit=ns.limit):
            print(
                f"{job.updated_at}  {job.status:<10}  {job.name:<26}  "
                f"{job.effective_date or '-':<10}  {job.id}"
            )
        return 0
    if action == "trigger":
        if ns.job_name == "market_data_probe":
            job = trigger_market_data_probe(store)
            print(f"{job.id}: {job.status}")
            return 0 if job.status in {JOB_STATUS_SUCCESS, JOB_STATUS_NOT_READY} else 1
        if ns.job_name == "market_data_bulk_refresh":
            job = trigger_market_data_bulk_refresh(store, effective_date=ns.effective_date)
            print(f"{job.id}: {job.status}")
            return 0 if job.status in {JOB_STATUS_SUCCESS, JOB_STATUS_SKIPPED} else 1
        if ns.job_name == "full_scan_and_daily":
            jobs = trigger_full_scan_and_daily(
                store,
                effective_date=ns.effective_date,
                force=ns.force,
            )
            for job in jobs:
                print(f"{job.id}: {job.status}")
            return 0 if jobs and jobs[-1].status == JOB_STATUS_SUCCESS else 1
        print(f"unknown job: {ns.job_name}", file=sys.stderr)
        return 2
    if action == "run":
        return run_scheduler_service(store)
    print(f"unknown scheduler command: {action}", file=sys.stderr)
    return 2


def cmd_daily(ns: argparse.Namespace) -> int:
    store = SchedulerStore()
    path = generate_daily(
        store,
        effective_date=getattr(ns, "effective_date", None),
        allow_historical=getattr(ns, "allow_historical", False),
    )
    print(f"daily report written: {path}")
    return 0


def run_scheduler_service(store: SchedulerStore) -> int:
    try:
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
        from apscheduler.schedulers.blocking import BlockingScheduler
    except ModuleNotFoundError:
        print(
            "APScheduler/SQLAlchemy is not installed. Install with `pip install -e .`.",
            file=sys.stderr,
        )
        return 1

    scheduler = BlockingScheduler(
        timezone="Asia/Shanghai",
        jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{store.db_path}")},
    )

    scheduler.add_job(
        scheduled_market_data_probe,
        "cron",
        hour="18-22",
        minute="0,30",
        id="market_data_probe",
        args=[str(store.root)],
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_market_data_bulk_refresh,
        "cron",
        hour="18-22",
        minute="10,40",
        id="market_data_bulk_refresh",
        args=[str(store.root)],
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_full_scan_and_daily,
        "cron",
        hour="18-23",
        minute="20,50",
        id="full_scan_and_daily",
        args=[str(store.root)],
        replace_existing=True,
    )
    print(f"scheduler running; db={store.db_path}")
    scheduler.start()
    return 0

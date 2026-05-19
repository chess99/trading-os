from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Sequence

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
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
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
        blocked_reason = compute_daily_blocker(self, date.today().isoformat())
        return {
            "updated_at": utc_now(),
            "scheduler_db": str(self.db_path),
            "latest_jobs": latest_by_name,
            "fetch_bulk": fetch_progress,
            "daily_blocked_reason": blocked_reason,
            "next_probe_window": "18:30-22:30 every 30 minutes",
        }

    def write_status(self) -> None:
        path = status_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
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


def probe_market_data(today: date | None = None) -> dict:
    from .data.schema import Adjustment, AssetType, Exchange
    from .data.sources.akshare_source import fetch_daily_bars

    today = today or date.today()
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
                start=(today - timedelta(days=10)).isoformat(),
                end=today.isoformat(),
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
    ready = effective == today.isoformat()
    return {
        "effective_date": effective,
        "ready": ready,
        "sentinels": sentinels,
        "errors": errors,
        "wall_clock_date": today.isoformat(),
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
    if code != 0:
        return store.update_job(
            job.id,
            status=JOB_STATUS_FAILED,
            error=f"exit code {code}",
            ended=True,
        )
    ok, latest = lake_has_effective_date(store.root, effective_date)
    if not ok:
        return store.update_job(
            job.id,
            status=JOB_STATUS_FAILED,
            error=f"lake qfq latest {latest or 'unknown'} < {effective_date}",
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

    results: list[JobRecord] = []
    elder = _ensure_scan_job(
        store,
        name="elder_scan",
        effective_date=effective_date,
        command=[sys.executable, "-m", "trading_os", "scan-elder", "--date", effective_date],
        runner=runner,
        force=force,
    )
    results.append(elder)
    canslim = _ensure_scan_job(
        store,
        name="canslim_scan",
        effective_date=effective_date,
        command=[
            sys.executable,
            "-m",
            "trading_os",
            "scan-canslim",
            "--date",
            effective_date,
            "--live",
        ],
        runner=runner,
        force=force,
    )
    results.append(canslim)
    scan_complete_statuses = {JOB_STATUS_SUCCESS, JOB_STATUS_SKIPPED}
    if elder.status not in scan_complete_statuses or canslim.status not in scan_complete_statuses:
        daily = store.create_job(
            "daily_report",
            effective_date=effective_date,
            status=JOB_STATUS_NOT_READY,
        )
        results.append(store.update_job(daily.id, error="scan incomplete", ended=True))
        write_blocked_daily(store, effective_date, "scan incomplete")
        return results

    daily = store.create_job(
        "daily_report",
        effective_date=effective_date,
        metadata={
            "bulk_job_id": bulk.id,
            "elder_scan_job_id": elder.id,
            "canslim_scan_job_id": canslim.id,
        },
    )
    store.update_job(daily.id, status=JOB_STATUS_RUNNING, started=True)
    write_complete_daily(store, effective_date, bulk, elder, canslim)
    results.append(store.update_job(daily.id, status=JOB_STATUS_SUCCESS, ended=True))
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
        return store.create_job(
            name,
            effective_date=effective_date,
            status=JOB_STATUS_SKIPPED,
            metadata={"reason": "already completed", "existing_job_id": existing.id},
        )
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
    if effective_date != date.today().isoformat() and not allow_historical:
        return "historical effective_date requires --allow-historical"
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
    scan_done = {JOB_STATUS_SUCCESS, JOB_STATUS_SKIPPED}
    elder = store.latest_job(
        "elder_scan",
        effective_date=effective_date,
        statuses=scan_done,
    )
    if not elder:
        return "Elder scan is incomplete"
    canslim = store.latest_job(
        "canslim_scan",
        effective_date=effective_date,
        statuses=scan_done,
    )
    if not canslim:
        return "CANSLIM scan is incomplete"
    return None


def write_blocked_daily(store: SchedulerStore, effective_date: str, reason: str) -> Path:
    out = store.root / "artifacts" / "daily" / f"{effective_date.replace('-', '')}-blocked.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    snapshot = store.status_snapshot()
    progress = snapshot.get("fetch_bulk") or {}
    lines = [
        f"# Daily blocked - {effective_date}",
        "",
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
    suffix = "-historical" if historical else ""
    out = store.root / "artifacts" / "daily" / f"{effective_date.replace('-', '')}{suffix}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    title = "Historical Daily Review" if historical else "Daily Workflow"
    lines = [
        f"# {title} - {effective_date}",
        "",
        f"- effective_date: `{effective_date}`",
        f"- market_data_bulk_refresh: `{bulk.id}` ({bulk.status})",
        f"- elder_scan: `{elder.id}` ({elder.status})",
        f"- canslim_scan: `{canslim.id}` ({canslim.status})",
        "",
        "This report is generated only after all upstream jobs for the same "
        "effective_date completed.",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def generate_daily(
    store: SchedulerStore,
    *,
    effective_date: str | None = None,
    allow_historical: bool = False,
) -> Path:
    effective_date = effective_date or date.today().isoformat()
    reason = compute_daily_blocker(store, effective_date, allow_historical=allow_historical)
    if reason:
        return write_blocked_daily(store, effective_date, reason)
    scan_done = {JOB_STATUS_SUCCESS, JOB_STATUS_SKIPPED}
    bulk = store.latest_job(
        "market_data_bulk_refresh",
        effective_date=effective_date,
        statuses={JOB_STATUS_SUCCESS},
    )
    elder = store.latest_job(
        "elder_scan",
        effective_date=effective_date,
        statuses=scan_done,
    )
    canslim = store.latest_job(
        "canslim_scan",
        effective_date=effective_date,
        statuses=scan_done,
    )
    if bulk is None or elder is None or canslim is None:
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


def lake_has_effective_date(root: Path, effective_date: str) -> tuple[bool, str | None]:
    try:
        from .data.lake import LocalDataLake

        lake = LocalDataLake(root / "data")
        lake.init()
        con = lake.connect()
        row = con.execute(
            "SELECT MAX(ts)::DATE AS latest FROM bars WHERE timeframe='1d' AND adjustment='qfq'"
        ).fetchone()
        con.close()
    except Exception:
        return False, None
    if not row or row[0] is None:
        return False, None
    latest = row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0])
    return latest >= effective_date, latest


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

    def probe_and_continue() -> None:
        probe = trigger_market_data_probe(store)
        if probe.status == JOB_STATUS_SUCCESS:
            effective_date = probe.metadata.get("effective_date")
            bulk = trigger_market_data_bulk_refresh(
                store,
                effective_date=effective_date,
            )
            if bulk.status in {JOB_STATUS_SUCCESS, JOB_STATUS_SKIPPED}:
                trigger_full_scan_and_daily(store, effective_date=effective_date)

    scheduler.add_job(
        probe_and_continue,
        "cron",
        hour="18-22",
        minute="0,30",
        id="market_data_probe",
    )
    print(f"scheduler running; db={store.db_path}")
    scheduler.start()
    return 0

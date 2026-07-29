from __future__ import annotations

import json
import os
import re
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from functools import wraps
from inspect import signature
from pathlib import Path
from typing import Any

from .company import AssetValidationError, validate_company_dir
from .sealing import atomic_write_bytes

DECISIONS = {
    "catalog",
    "rapid_triage",
    "triage_candidate",
    "quick_profile",
    "profile_candidate",
    "scoped_research",
    "deep_candidate",
    "targeted_followup",
    "deep_research",
    "price_watch",
    "reassign_or_stop",
    "watch_only",
    "conditional_stop",
    "hard_exclusion",
    "skip_risk",
    "skip_too_small",
    "skip_not_in_scope",
    "needs_manual_review",
}
QUEUE_STATUSES = {
    "pending",
    "running",
    "completed",
    "requires_rebaseline",
    "failed",
    "skipped",
    "needs_review",
}
TASK_TYPES = {
    "rapid_triage",
    "quick_profile",
    "targeted_followup",
    "scoped_research",
    "deep_research",
    "monitoring_update",
    "initial_research",
    "followup_review",
}
BUDGETED_TASK_TYPES = {
    "rapid_triage",
    "quick_profile",
    "targeted_followup",
    "scoped_research",
    "deep_research",
}
PRE_REPORT_TASK_TYPES = {
    "rapid_triage",
    "quick_profile",
    "targeted_followup",
    "scoped_research",
}
SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")

COMPANIES_FILE = "companies.jsonl"
SCREENING_FILE = "screening.jsonl"
RESEARCH_QUEUE_FILE = "research_queue.jsonl"
RUNS_FILE = "runs.jsonl"


class CoverageValidationError(ValueError):
    """Raised when coverage JSONL files are invalid."""


@contextmanager
def coverage_write_lock(root: str | Path) -> Iterator[None]:
    """Serialize read-modify-write operations across the shared coverage files."""

    lock_path = Path(root) / ".coverage-write.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
        os.fsync(handle.fileno())
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise CoverageValidationError(f"coverage state is busy: {lock_path}") from exc
    try:
        yield
    finally:
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def serialized_coverage_write(function: Any) -> Any:
    """Run a coverage read-modify-write function under the repository lock."""

    function_signature = signature(function)

    @wraps(function)
    def locked(*args: Any, **kwargs: Any) -> Any:
        root = function_signature.bind(*args, **kwargs).arguments.get("root")
        if root is None:
            raise TypeError("serialized coverage writes require a root argument")
        with coverage_write_lock(root):
            return function(*args, **kwargs)

    return locked


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(file_path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CoverageValidationError(f"invalid JSONL in {file_path}:{line_no}: {exc}") from exc
        if not isinstance(item, dict):
            raise CoverageValidationError(f"JSONL row must be an object: {file_path}:{line_no}")
        records.append(item)
    return records


def write_jsonl(path: str | Path, records: list[dict[str, Any]], sort_key: str = "symbol") -> Path:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    sorted_records = sorted(records, key=lambda item: str(item.get(sort_key, "")))
    payload = "".join(
        json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
        for item in sorted_records
    )
    atomic_write_bytes(file_path, payload.encode("utf-8"))
    return file_path


def upsert_jsonl(path: str | Path, key: str, record: dict[str, Any]) -> Path:
    if key not in record:
        raise CoverageValidationError(f"record missing key: {key}")
    records = [item for item in read_jsonl(path) if item.get(key) != record[key]]
    records.append(record)
    return write_jsonl(path, records, key)


def coverage_status(root: str | Path) -> dict[str, Any]:
    base = Path(root)
    screening = read_jsonl(base / SCREENING_FILE)
    queue = read_jsonl(base / RESEARCH_QUEUE_FILE)
    companies = read_jsonl(base / COMPANIES_FILE)
    runs = read_jsonl(base / RUNS_FILE)
    return {
        "schema_version": 1,
        "root": str(base),
        "companies": {"total": len(companies)},
        "screening": {
            "total": len(screening),
            "by_decision": _sorted_counts(item.get("decision") for item in screening),
        },
        "research_queue": {
            "total": len(queue),
            "by_status": _sorted_counts(item.get("status") for item in queue),
        },
        "runs": {"total": len(runs)},
    }


@serialized_coverage_write
def reconcile_research_queue(
    root: str | Path,
    research_root: str | Path,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    base = Path(root)
    research_base = Path(research_root)
    queue_path = base / RESEARCH_QUEUE_FILE
    records = read_jsonl(queue_path)
    reconciled: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    blocked: list[dict[str, str]] = []
    eligible_statuses = {"pending", "running", "failed", "requires_rebaseline"}

    for record in records:
        updated = dict(record)
        if record.get("task_type") in PRE_REPORT_TASK_TYPES:
            # Quick profiles and scoped research deliberately precede a full
            # company report. Company-level rebaseline state must not erase
            # their finite-capacity queue status.
            reconciled.append(updated)
            continue
        if record.get("status") not in eligible_statuses | {"completed"}:
            reconciled.append(updated)
            continue
        company_dir = _resolve_company_dir(record, research_base)
        if not (company_dir / "meta.json").exists():
            reconciled.append(updated)
            continue

        try:
            meta = validate_company_dir(company_dir)
            symbol = meta["identity"]["symbol"]
            latest_report = meta["reports"]["latest"]
            if symbol != record.get("symbol"):
                raise AssetValidationError(
                    f"company asset symbol {symbol} does not match queue symbol "
                    f"{record.get('symbol')}"
                )
            rebaseline_required = meta["research"]["rebaseline_required"]
            if latest_report is None and not rebaseline_required:
                raise AssetValidationError(
                    f"company asset has no structured latest report: {symbol}"
                )
        except AssetValidationError as exc:
            blocked.append(
                {
                    "symbol": str(record.get("symbol", "")),
                    "company_dir": str(company_dir),
                    "error": str(exc),
                }
            )
            reconciled.append(updated)
            continue

        if rebaseline_required:
            if record.get("status") == "requires_rebaseline":
                reconciled.append(updated)
                continue
            updated.update(
                {
                    "status": "requires_rebaseline",
                    "assigned_agent": None,
                    "started_at": None,
                    "finished_at": None,
                    "result_path": None,
                    "failure_reason": None,
                    "next_action": (
                        "按 v2 研究协议重建初研，并在结构化报告验证通过后重新承保。"
                    ),
                }
            )
            changes.append(
                {
                    "symbol": symbol,
                    "from_status": record.get("status"),
                    "to_status": "requires_rebaseline",
                    "result_path": None,
                }
            )
            reconciled.append(updated)
            continue

        if record.get("status") not in eligible_statuses:
            reconciled.append(updated)
            continue

        updated.update(
            {
                "status": "completed",
                "result_path": latest_report,
                "failure_reason": None,
                "next_action": "查看 reports/ 下最新报告。",
            }
        )
        if not updated.get("finished_at"):
            updated["finished_at"] = meta["updated_at"]
        changes.append(
            {
                "symbol": symbol,
                "from_status": record["status"],
                "to_status": "completed",
                "result_path": latest_report,
            }
        )
        reconciled.append(updated)

    if apply and changes:
        write_jsonl(queue_path, reconciled)

    return {
        "schema_version": 1,
        "applied": apply,
        "change_count": len(changes),
        "changes": changes,
        "blocked_count": len(blocked),
        "blocked": blocked,
    }


def validate_coverage_root(root: str | Path) -> dict[str, Any]:
    base = Path(root)
    files = [
        (COMPANIES_FILE, None),
        (SCREENING_FILE, _validate_screening_record),
        (RESEARCH_QUEUE_FILE, _validate_queue_record),
        (RUNS_FILE, None),
    ]
    for file_name, validator in files:
        _validate_file(base / file_name, validator)
    return coverage_status(base)


@serialized_coverage_write
def set_screening(
    root: str | Path,
    *,
    symbol: str,
    name: str,
    decision: str,
    priority: int | None,
    reason: str,
    evidence: list[str],
    next_action: str,
) -> Path:
    record = {
        "symbol": symbol,
        "name": name,
        "decision": decision,
        "priority": priority,
        "reason": reason,
        "evidence": evidence,
        "next_action": next_action,
    }
    _validate_screening_record(record, Path(root) / SCREENING_FILE)
    return upsert_jsonl(Path(root) / SCREENING_FILE, "symbol", record)


@serialized_coverage_write
def enqueue_research(
    root: str | Path,
    *,
    symbol: str,
    name: str,
    priority: int,
    reason: str,
    task_type: str = "initial_research",
    status: str = "pending",
    target_company_dir: str | None = None,
    effort_budget_hours: float | None = None,
    preceding_stage: str | None = None,
    stop_conditions: list[str] | None = None,
) -> Path:
    ticker = _ticker_from_symbol(symbol)
    next_actions = {
        "rapid_triage": (
            "在15分钟预算内完成快速甄别；封存后等待全批次横向比较，"
            "不得按完成顺序直接晋级正式画像。"
        ),
        "quick_profile": (
            "按 playbooks/research-capital-allocation.md 完成快速投资画像；"
            "只能晋级范围研究、定向补证或结构化停止。"
        ),
        "scoped_research": (
            "只解决快速画像列出的决定性问题，完成正常化盈利和粗估值后决定是否深研。"
        ),
        "targeted_followup": "只补齐快速画像列出的一个或少数决定性证据缺口。",
        "deep_research": "按 playbooks/company-research.md 写完整中文初始研究报告。",
        "monitoring_update": "只更新触发器命中的价格、证据或论点，不重复完整研究。",
        "initial_research": "按 playbooks/company-research.md 写中文初始研究报告。",
        "followup_review": "按最新触发器更新公司研究，不覆盖历史报告。",
    }
    record: dict[str, Any] = {
        "symbol": symbol,
        "name": name,
        "task_type": task_type,
        "priority": priority,
        "status": status,
        "reason": reason,
        "target_company_dir": target_company_dir or f"research/companies/CN/{ticker}",
        "assigned_agent": None,
        "started_at": None,
        "finished_at": None,
        "result_path": None,
        "failure_reason": None,
        "next_action": next_actions.get(task_type, ""),
    }
    if effort_budget_hours is not None:
        record["effort_budget_hours"] = effort_budget_hours
    if preceding_stage is not None:
        record["preceding_stage"] = preceding_stage
    if stop_conditions is not None:
        record["stop_conditions"] = stop_conditions
    _validate_queue_record(record, Path(root) / RESEARCH_QUEUE_FILE)
    return upsert_jsonl(Path(root) / RESEARCH_QUEUE_FILE, "symbol", record)


def get_symbol(root: str | Path, symbol: str) -> dict[str, Any]:
    base = Path(root)
    result = {
        "symbol": symbol,
        "companies": _matching_records(base / COMPANIES_FILE, symbol),
        "screening": _matching_records(base / SCREENING_FILE, symbol),
        "research_queue": _matching_records(base / RESEARCH_QUEUE_FILE, symbol),
    }
    if not result["companies"] and not result["screening"] and not result["research_queue"]:
        raise CoverageValidationError(f"symbol not found: {symbol}")
    return result


def list_screening(root: str | Path, decision: str | None = None) -> list[dict[str, Any]]:
    records = read_jsonl(Path(root) / SCREENING_FILE)
    if decision is None:
        return records
    if decision not in DECISIONS:
        raise CoverageValidationError(f"invalid decision: {decision}")
    return [item for item in records if item.get("decision") == decision]


def _validate_file(path: Path, validator: Any) -> None:
    seen: set[str] = set()
    for item in read_jsonl(path):
        symbol = item.get("symbol")
        if path.name != RUNS_FILE and isinstance(symbol, str):
            if symbol in seen:
                raise CoverageValidationError(f"duplicate symbol in {path}: {symbol}")
            seen.add(symbol)
        if validator is not None:
            validator(item, path)


def _validate_screening_record(record: dict[str, Any], path: Path) -> None:
    _require_symbol(record, path)
    _require_non_empty_string(record, "name", path)
    decision = record.get("decision")
    if decision not in DECISIONS:
        raise CoverageValidationError(f"invalid decision in {path}: {decision}")
    priority = record.get("priority")
    if priority is not None and (not isinstance(priority, int) or not 1 <= priority <= 5):
        raise CoverageValidationError(f"priority must be null or 1-5 in {path}")
    _require_non_empty_string(record, "reason", path)
    if not isinstance(record.get("evidence"), list) or not record["evidence"]:
        raise CoverageValidationError(f"evidence must be a non-empty list in {path}")
    _require_non_empty_string(record, "next_action", path)


def _validate_queue_record(record: dict[str, Any], path: Path) -> None:
    _require_symbol(record, path)
    _require_non_empty_string(record, "name", path)
    if record.get("task_type") not in TASK_TYPES:
        raise CoverageValidationError(f"invalid task_type in {path}: {record.get('task_type')}")
    priority = record.get("priority")
    if not isinstance(priority, int) or not 1 <= priority <= 5:
        raise CoverageValidationError(f"priority must be 1-5 in {path}")
    if record.get("status") not in QUEUE_STATUSES:
        raise CoverageValidationError(f"invalid status in {path}: {record.get('status')}")
    _require_non_empty_string(record, "reason", path)
    _require_non_empty_string(record, "target_company_dir", path)
    task_type = record["task_type"]
    effort = record.get("effort_budget_hours")
    if effort is not None and (
        isinstance(effort, bool)
        or not isinstance(effort, (int, float))
        or effort <= 0
    ):
        raise CoverageValidationError(
            f"effort_budget_hours must be positive in {path}"
        )
    if task_type in BUDGETED_TASK_TYPES:
        if effort is None:
            raise CoverageValidationError(
                f"effort_budget_hours is required for {task_type} in {path}"
            )
        _require_non_empty_string(record, "preceding_stage", path)
        stops = record.get("stop_conditions")
        if (
            not isinstance(stops, list)
            or not stops
            or not all(isinstance(item, str) and item.strip() for item in stops)
        ):
            raise CoverageValidationError(
                f"stop_conditions must be a non-empty string array for {task_type} in {path}"
            )


def _require_symbol(record: dict[str, Any], path: Path) -> None:
    symbol = record.get("symbol")
    if not isinstance(symbol, str) or not SYMBOL_RE.match(symbol):
        raise CoverageValidationError(f"symbol must match CN:000000 in {path}")


def _require_non_empty_string(record: dict[str, Any], key: str, path: Path) -> None:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CoverageValidationError(f"{key} must be a non-empty string in {path}")


def _matching_records(path: Path, symbol: str) -> list[dict[str, Any]]:
    return [item for item in read_jsonl(path) if item.get("symbol") == symbol]


def _ticker_from_symbol(symbol: str) -> str:
    if not SYMBOL_RE.match(symbol):
        raise CoverageValidationError(f"symbol must match CN:000000: {symbol}")
    return symbol.split(":", 1)[1]


def _resolve_company_dir(record: dict[str, Any], research_root: Path) -> Path:
    target = Path(str(record.get("target_company_dir", "")))
    if target.is_absolute():
        return target
    if target.parts and target.parts[0] == research_root.name:
        return research_root.parent / target
    if target.parts and target.parts[0] == "companies":
        return research_root / target
    return research_root.parent / target


def _sorted_counts(values: Any) -> dict[str, int]:
    return dict(sorted(Counter(str(value) for value in values if value is not None).items()))

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

DECISIONS = {
    "deep_research",
    "watch_only",
    "skip_risk",
    "skip_too_small",
    "skip_not_in_scope",
    "needs_manual_review",
}
QUEUE_STATUSES = {
    "pending",
    "running",
    "completed",
    "failed",
    "skipped",
    "needs_review",
}
TASK_TYPES = {"initial_research", "followup_review"}
SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")

COMPANIES_FILE = "companies.jsonl"
SCREENING_FILE = "screening.jsonl"
RESEARCH_QUEUE_FILE = "research_queue.jsonl"
RUNS_FILE = "runs.jsonl"


class CoverageValidationError(ValueError):
    """Raised when coverage JSONL files are invalid."""


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
    file_path.write_text(payload, encoding="utf-8")
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
) -> Path:
    ticker = _ticker_from_symbol(symbol)
    record = {
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
        "next_action": "按 playbooks/company-research.md 写中文初始研究报告。",
    }
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


def _sorted_counts(values: Any) -> dict[str, int]:
    return dict(sorted(Counter(str(value) for value in values if value is not None).items()))

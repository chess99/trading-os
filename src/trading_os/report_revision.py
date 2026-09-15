"""Explicit, scope-limited correction of a current report for an authorized audit.

This exception does not replace the normal append-only research completion flow.
The caller supplies the frozen audit scope and the exact report it reviewed.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from trading_os.research_assets.research_flow import (
    _FORMAL_REPORT_RE,
    CompanyStatus,
    ResearchFlow,
    ResearchResult,
    TaskStatus,
    ValidationError,
    _atomic_write_text,
    _exclusive_lock,
    _nonblank,
    _timestamp,
    _urls,
)


def _reject_links(root: Path, path: Path) -> None:
    """Reject links in the target or any of its workspace ancestors."""
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ValidationError("revision path escapes the workspace") from exc
    cursor = root
    for part in (None, *relative.parts):
        if part is not None:
            cursor /= part
        # is_junction is available on Python 3.12+ and matters on Windows.
        if cursor.is_symlink() or getattr(cursor, "is_junction", lambda: False)():
            raise ValidationError(f"revision does not allow symlinks or junctions: {cursor}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValidationError("revision path escapes the workspace")


def _report_target(root: Path, symbol: str, relative: str) -> Path:
    if not isinstance(relative, str):
        raise ValidationError("audit scope requires a report path")
    pure = PurePosixPath(relative)
    prefix = ("research", "companies", "CN", symbol.split(":", 1)[1], "reports")
    if (
        pure.is_absolute()
        or len(pure.parts) != 6
        or pure.parts[:5] != prefix
        or pure.as_posix() != relative
        or not _FORMAL_REPORT_RE.fullmatch(pure.name)
    ):
        raise ValidationError("revision requires a dated formal report for this company")
    target = root.joinpath(*pure.parts)
    _reject_links(root, target)
    if not target.is_file():
        raise ValidationError("current report does not exist")
    return target


def _restore_bytes(path: Path, content: bytes | None) -> None:
    """Restore exact bytes, independent of the writer that may have failed."""
    if content is None:
        path.unlink(missing_ok=True)
        return
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def revise_current(
    root: Path,
    result: ResearchResult,
    *,
    allowed_reports: Mapping[str, str],
    expected_report: str,
    reviewed_at: str,
    rationale: str,
    display_issue: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Correct one authorized current report and its compact state together.

    Keep the original information cutoff: new facts require the normal full
    update flow. A stale report remains stale and its pending task survives.
    Exception recovery restores the exact report/state/watchlist bytes while
    the normal research state lock remains held. This is not a crash journal.
    """
    root = Path(root).absolute()
    normalized = ResearchFlow._normalized_result(result)
    symbol = normalized["symbol"]
    if not isinstance(reviewed_at, str) or not isinstance(rationale, str):
        raise ValidationError("reviewed_at and rationale must be explicit text")
    timestamp = _timestamp(_nonblank(reviewed_at, "reviewed_at"))
    reason = _nonblank(rationale, "rationale")
    issue = None
    if display_issue is not None:
        issue = {
            "event_date": date.fromisoformat(display_issue["event_date"]).isoformat(),
            "reason": _nonblank(display_issue.get("reason"), "display issue reason"),
            "source_url": _urls([display_issue.get("source_url")])[0],
        }
        if not normalized["information_cutoff"][:10] < issue["event_date"] <= timestamp[:10]:
            raise ValidationError("display issue must be an observed post-cutoff event")
    if not isinstance(expected_report, str) or not expected_report.strip():
        raise ValidationError("revision requires the exact nonblank original report")
    relative = allowed_reports.get(symbol)
    if relative is None:
        raise ValidationError(f"company is outside the authorized audit scope: {symbol}")
    flow = ResearchFlow(root)
    for path in (flow.state_path, flow.queue_path, flow.watchlist_path, flow.lock_path):
        _reject_links(root, path)

    with _exclusive_lock(flow.lock_path):
        target = _report_target(root, symbol, relative)
        states = flow._states()
        state = states.get(symbol)
        if state is None or state.get("report_path") != relative:
            raise ValidationError("audit report is no longer the company's current report")
        reports = flow._formal_reports(symbol)
        if not reports or reports[-1] != target:
            raise ValidationError("revision cannot rewrite an older formal report")
        if state.get("status") not in {
            CompanyStatus.COVERED.value,
            CompanyStatus.IGNORE.value,
            CompanyStatus.STALE.value,
        }:
            raise ValidationError("revision requires an existing researched company")
        if any(
            task.symbol == symbol and task.status is TaskStatus.RUNNING for task in flow._tasks()
        ):
            raise ValidationError("company has a running research task")
        if normalized["information_cutoff"] != state.get("information_cutoff"):
            raise ValidationError("revision must retain the original information_cutoff")
        for value in (state["updated_at"], state["information_cutoff"]):
            if datetime.fromisoformat(timestamp) < datetime.fromisoformat(_timestamp(value)):
                raise ValidationError("revision review time predates the current state")
        if target.read_text(encoding="utf-8") != expected_report:
            raise ValidationError("current report changed since it was reviewed")

        paths = (target, flow.state_path, flow.watchlist_path)
        snapshots = {path: path.read_bytes() if path.exists() else None for path in paths}
        state.update(
            {
                key: normalized[key]
                for key in (
                    "summary",
                    "key_logic",
                    "risks",
                    "value_range",
                    "valuation_note",
                    "return_model",
                    "return_model_note",
                    "event_triggers",
                    "source_urls",
                )
            }
        )
        # Security identity/scope and event invalidation are not audit decisions.
        if state["status"] != CompanyStatus.STALE.value:
            state["status"] = normalized["outcome"]
        state["updated_at"] = timestamp
        state["last_research_at"] = timestamp
        previous_issue = (state.get("last_revision") or {}).get("display_issue")
        state["last_revision"] = {"reviewed_at": timestamp, "rationale": reason}
        if issue is not None:
            state["last_revision"]["display_issue"] = {
                **issue, "base_report": relative,
                "model_as_of": normalized["information_cutoff"],
            }
        elif previous_issue and previous_issue.get("base_report") == relative:
            state["last_revision"]["display_issue"] = previous_issue
        try:
            _atomic_write_text(target, normalized["report_markdown"].rstrip() + "\n")
            flow._write_states(states)
            flow.validate()
        except BaseException as failure:
            restore_failures = []
            for path, original in snapshots.items():
                try:
                    _restore_bytes(path, original)
                except OSError as exc:
                    restore_failures.append(f"{path}: {exc}")
            if restore_failures:
                raise RuntimeError(
                    "revision failed and rollback needs repair: " + "; ".join(restore_failures)
                ) from failure
            raise
        return dict(state)

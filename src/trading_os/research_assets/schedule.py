from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from .company import validate_company_dir
from .index import _company_dirs
from .sealing import atomic_write_bytes


def build_review_schedule(
    research_root: str | Path,
    *,
    as_of: dt.datetime | None = None,
) -> dict[str, Any]:
    root = Path(research_root)
    if as_of is None:
        local_now = dt.datetime.now().astimezone()
        cutoff = dt.datetime.combine(
            local_now.date(),
            dt.time.max,
            tzinfo=local_now.tzinfo,
        )
    else:
        cutoff = as_of
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("schedule as_of must include timezone information")
    items: list[dict[str, Any]] = []
    companies_root = root / "companies"
    if companies_root.exists():
        for company_dir in _company_dirs(companies_root):
            meta = validate_company_dir(company_dir)
            identity = meta["identity"]
            latest_report = _latest_report(root, company_dir, meta)
            if meta["research"]["rebaseline_required"]:
                items.append(
                    {
                        "trigger_id": "research-rebaseline",
                        "symbol": identity["symbol"],
                        "name": identity["name"],
                        "type": "rebaseline",
                        "condition": {"rebaseline_required": True},
                        "reason": (
                            "历史证据可作线索，但旧评级和估值不可执行；须按 v2 协议重建并重新承保。"
                        ),
                        "latest_report": latest_report,
                        "source": "research_rebaseline",
                        "state": "due",
                    }
                )
                continue
            for trigger in meta["triggers"]:
                if not trigger["active"]:
                    continue
                items.append(
                    {
                        "trigger_id": trigger["trigger_id"],
                        "symbol": identity["symbol"],
                        "name": identity["name"],
                        "type": trigger["type"],
                        "condition": trigger["condition"],
                        "reason": trigger["reason"],
                        "latest_report": latest_report,
                        "source": "company_trigger",
                        "state": _trigger_state(trigger, as_of=cutoff),
                    }
                )
            refresh_due_at = meta["research"].get("refresh_due_at")
            if refresh_due_at is not None and not _refresh_already_scheduled(
                refresh_due_at, meta["triggers"]
            ):
                items.append(
                    {
                        "trigger_id": "research-refresh-due",
                        "symbol": identity["symbol"],
                        "name": identity["name"],
                        "type": "date",
                        "condition": {"due_at": refresh_due_at},
                        "reason": "快速研究证据到期后进行增量复核。",
                        "latest_report": latest_report,
                        "source": "research_refresh_due",
                        "state": _date_state(refresh_due_at, as_of=cutoff),
                    }
                )
            evidence_valid_until = meta["underwriting"].get(
                "evidence_valid_until"
            )
            if evidence_valid_until is not None:
                items.append(
                    {
                        "trigger_id": "underwriting-evidence-expiry",
                        "symbol": identity["symbol"],
                        "name": identity["name"],
                        "type": "date",
                        "condition": {"due_at": evidence_valid_until},
                        "reason": "独立承保证据有效期届满前必须重新核验证据。",
                        "latest_report": latest_report,
                        "source": "evidence_expiry",
                        "state": _date_state(evidence_valid_until, as_of=cutoff),
                    }
                )
            invalidation = _invalidation(meta)
            if invalidation is not None:
                items.append(
                    {
                        "trigger_id": "conclusion-invalid",
                        "symbol": identity["symbol"],
                        "name": identity["name"],
                        "type": "thesis",
                        "condition": {"conclusion_status": invalidation},
                        "reason": "当前研究结论不可作为组合买入依据，必须重新建立或复核。",
                        "latest_report": latest_report,
                        "source": "conclusion_invalidation",
                        "state": "due",
                    }
                )
    items.sort(key=lambda item: (item["symbol"], item["type"], item["trigger_id"]))
    return {
        "schema_version": 2,
        "as_of": cutoff.isoformat(),
        "item_count": len(items),
        "items": items,
    }


def write_review_schedule(
    research_root: str | Path,
    output_path: str | Path,
    *,
    as_of: dt.datetime | None = None,
) -> Path:
    payload = build_review_schedule(research_root, as_of=as_of)
    target = Path(output_path)
    content = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return atomic_write_bytes(target, content)


def _latest_report(root: Path, company_dir: Path, meta: dict[str, Any]) -> str | None:
    latest = meta["reports"]["latest"]
    return (company_dir.relative_to(root) / latest).as_posix() if latest else None


def _invalidation(meta: dict[str, Any]) -> str | None:
    if meta["research"]["rebaseline_required"]:
        return "requires_rebaseline"
    status = meta["underwriting"]["status"]
    if status is None:
        if meta["research"].get("latest_rapid_triage") is not None:
            return None
        return "not_underwritten"
    if status != "passed":
        return str(status)
    return None


def _trigger_state(trigger: dict[str, Any], *, as_of: dt.datetime) -> str:
    if trigger.get("type") == "date":
        condition = trigger.get("condition")
        if isinstance(condition, dict):
            due_at = condition.get("due_at")
            if isinstance(due_at, str):
                return _date_state(due_at, as_of=as_of)
            date_text = condition.get("date")
            if isinstance(date_text, str):
                try:
                    return (
                        "due"
                        if dt.date.fromisoformat(date_text) <= as_of.date()
                        else "scheduled"
                    )
                except ValueError:
                    return "watching"
        return "watching"
    return "watching"


def _date_state(value: str, *, as_of: dt.datetime) -> str:
    try:
        due_at = dt.datetime.fromisoformat(value)
    except ValueError:
        try:
            return (
                "due"
                if dt.date.fromisoformat(value) <= as_of.date()
                else "scheduled"
            )
        except ValueError:
            return "watching"
    if due_at.tzinfo is None or due_at.utcoffset() is None:
        return "watching"
    return "due" if due_at <= as_of else "scheduled"


def _refresh_already_scheduled(
    refresh_due_at: str, triggers: list[dict[str, Any]]
) -> bool:
    try:
        refresh = dt.datetime.fromisoformat(refresh_due_at)
    except ValueError:
        return False
    for trigger in triggers:
        if not trigger.get("active") or trigger.get("type") != "date":
            continue
        condition = trigger.get("condition")
        if not isinstance(condition, dict):
            continue
        due_at = condition.get("due_at")
        if isinstance(due_at, str):
            try:
                if dt.datetime.fromisoformat(due_at) == refresh:
                    return True
            except ValueError:
                pass
        date_text = condition.get("date")
        if isinstance(date_text, str):
            try:
                if dt.date.fromisoformat(date_text) == refresh.date():
                    return True
            except ValueError:
                pass
    return False

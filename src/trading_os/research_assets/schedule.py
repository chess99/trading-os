from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .company import validate_company_dir
from .index import _company_dirs
from .sealing import atomic_write_bytes


def build_review_schedule(research_root: str | Path) -> dict[str, Any]:
    root = Path(research_root)
    items: list[dict[str, Any]] = []
    companies_root = root / "companies"
    if companies_root.exists():
        for company_dir in _company_dirs(companies_root):
            meta = validate_company_dir(company_dir)
            identity = meta["identity"]
            latest_report = _latest_report(root, company_dir, meta)
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
                    }
                )
    items.sort(key=lambda item: (item["symbol"], item["type"], item["trigger_id"]))
    return {"schema_version": 2, "item_count": len(items), "items": items}


def write_review_schedule(research_root: str | Path, output_path: str | Path) -> Path:
    payload = build_review_schedule(research_root)
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
        return "not_underwritten"
    if status != "passed":
        return str(status)
    return None

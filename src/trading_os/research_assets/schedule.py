from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .company import validate_company_dir
from .index import _company_dirs


def build_review_schedule(research_root: str | Path) -> dict[str, Any]:
    root = Path(research_root)
    items: list[dict[str, Any]] = []
    companies_root = root / "companies"
    if companies_root.exists():
        for company_dir in _company_dirs(companies_root):
            meta = validate_company_dir(company_dir)
            rel_company = company_dir.relative_to(root)
            for trigger in meta.get("review_triggers", []):
                if trigger.get("type") != "date":
                    continue
                items.append(
                    {
                        "date": trigger["date"],
                        "symbol": meta["symbol"],
                        "name": meta["name"],
                        "reason": trigger["reason"],
                        "latest_report": (
                            rel_company / meta["latest_report"]
                        ).as_posix(),
                    }
                )
    items.sort(key=lambda item: (item["date"], item["symbol"]))
    return {"schema_version": 1, "item_count": len(items), "items": items}


def write_review_schedule(research_root: str | Path, output_path: str | Path) -> Path:
    payload = build_review_schedule(research_root)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target

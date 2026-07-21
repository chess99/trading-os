from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .company import AssetValidationError, validate_company_dir
from .sealing import atomic_write_bytes


@dataclass(frozen=True, slots=True)
class WriteResult:
    ok: bool
    path: Path
    errors: list[str]


def build_index(research_root: str | Path) -> dict[str, Any]:
    root = Path(research_root)
    companies_root = root / "companies"
    companies: list[dict[str, Any]] = []
    if companies_root.exists():
        for company_dir in _company_dirs(companies_root):
            meta = validate_company_dir(company_dir)
            identity = meta["identity"]
            research = meta["research"]
            reports = meta["reports"]
            underwriting = meta["underwriting"]
            valuation = meta["valuation"]
            rel_company = company_dir.relative_to(root)
            companies.append(
                {
                    "symbol": identity["symbol"],
                    "market": identity["market"],
                    "ticker": identity["ticker"],
                    "name": identity["name"],
                    "currency": identity["currency"],
                    "security_status": identity["security_status"],
                    "coverage_status": research["coverage_status"],
                    "rebaseline_required": research["rebaseline_required"],
                    "information_cutoff": research["information_cutoff"],
                    "latest_report": _relative_report(rel_company, reports["latest"]),
                    "latest_by_type": {
                        report_type: _relative_report(rel_company, path)
                        for report_type, path in sorted(reports["latest_by_type"].items())
                    },
                    "underwriting": dict(underwriting),
                    "valuation": dict(valuation),
                    "conclusion_status": _conclusion_status(meta),
                    "active_trigger_count": sum(
                        bool(trigger["active"]) for trigger in meta["triggers"]
                    ),
                    "updated_at": meta["updated_at"],
                }
            )
    companies.sort(key=lambda item: item["symbol"])
    return {"schema_version": 2, "company_count": len(companies), "companies": companies}


def write_index(research_root: str | Path) -> WriteResult:
    root = Path(research_root)
    target = root / "index.json"
    try:
        payload = build_index(root)
    except AssetValidationError as exc:
        return WriteResult(ok=False, path=target, errors=[str(exc)])
    atomic_write_bytes(target, _pretty_json_bytes(payload))
    return WriteResult(ok=True, path=target, errors=[])


def _company_dirs(companies_root: Path) -> list[Path]:
    paths: list[Path] = []
    for market_dir in sorted(path for path in companies_root.iterdir() if path.is_dir()):
        for company_dir in sorted(path for path in market_dir.iterdir() if path.is_dir()):
            if (company_dir / "meta.json").is_file():
                paths.append(company_dir)
    return paths


def _conclusion_status(meta: Mapping[str, Any]) -> str:
    if meta["research"]["rebaseline_required"]:
        return "requires_rebaseline"
    status = meta["underwriting"]["status"]
    if status is None:
        return "not_underwritten"
    if status == "passed":
        return "valid"
    if status == "stale":
        return "stale"
    return "blocked"


def _relative_report(rel_company: Path, report: str | None) -> str | None:
    return (rel_company / report).as_posix() if report is not None else None


def _pretty_json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

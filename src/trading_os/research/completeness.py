from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CORE_COMPANY_DATASETS = ("quotes", "fundamentals", "bars")
ENRICHMENT_COMPANY_DATASETS = ("estimates", "news")


@dataclass(frozen=True, slots=True)
class ResearchCompleteness:
    status: str
    score: float
    core_missing: list[str]
    enrichment_missing: list[str]

    @property
    def complete(self) -> bool:
        return self.status == "complete"

    def to_manifest(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "complete": self.complete,
            "core_missing": self.core_missing,
            "enrichment_missing": self.enrichment_missing,
        }


def evaluate_company_research_completeness(
    datasets: dict[str, bool],
) -> ResearchCompleteness:
    core_missing = [name for name in CORE_COMPANY_DATASETS if datasets.get(name) is not True]
    enrichment_missing = [
        name for name in ENRICHMENT_COMPANY_DATASETS if datasets.get(name) is not True
    ]
    core_score = (len(CORE_COMPANY_DATASETS) - len(core_missing)) / len(CORE_COMPANY_DATASETS)
    enrichment_score = (
        (len(ENRICHMENT_COMPANY_DATASETS) - len(enrichment_missing))
        / len(ENRICHMENT_COMPANY_DATASETS)
        if ENRICHMENT_COMPANY_DATASETS
        else 1.0
    )
    score = round(core_score * 0.75 + enrichment_score * 0.25, 4)
    status = "complete" if not core_missing else "incomplete"
    return ResearchCompleteness(
        status=status,
        score=score,
        core_missing=core_missing,
        enrichment_missing=enrichment_missing,
    )


def status_from_company_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    explicit_status = str(manifest.get("status") or "").strip().lower()
    if explicit_status in {"failed", "incomplete"}:
        return {"status": explicit_status}
    completeness = manifest.get("completeness")
    if isinstance(completeness, dict):
        status = str(completeness.get("status") or "").strip().lower()
        if status and status != "complete":
            return {
                "status": status,
                "missing_core_datasets": list(completeness.get("core_missing") or []),
                "missing_enrichment_datasets": list(
                    completeness.get("enrichment_missing") or []
                ),
            }
    if manifest.get("complete") is False or manifest.get("is_complete") is False:
        return {"status": "incomplete", "reason": "company research marked incomplete"}

    datasets = manifest.get("datasets")
    if isinstance(datasets, dict):
        evaluated = evaluate_company_research_completeness(
            {str(key): bool(value) for key, value in datasets.items()}
        )
        if not evaluated.complete:
            return {
                "status": evaluated.status,
                "missing_core_datasets": evaluated.core_missing,
                "missing_enrichment_datasets": evaluated.enrichment_missing,
            }
    return {"status": "ok"}

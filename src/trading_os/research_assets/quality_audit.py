from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .sealing import SealingError, canonical_json_bytes, seal_json, verify_sealed


class QualityAuditError(ValueError):
    """Raised when a quality-audit contract or sealed asset is invalid."""


STOP_STRATA = (
    "catalog",
    "price_watch",
    "conditional_stop",
    "reassign_or_stop",
)
ALL_STRATA = ("hard_exclusion", *STOP_STRATA)
STOP_DISPOSITIONS = set(STOP_STRATA)
ALL_DISPOSITIONS = STOP_DISPOSITIONS | {"triage_candidate"}
FINDING_SEVERITIES = {"minor", "material", "major"}
ERROR_SEMANTICS = {
    "finding_severity_v1",
    "routing_disagreement_v1",
}
IDENTITY_VERDICTS = {"hard_exclusion", "eligible", "exception"}
PROVENANCE_FIELDS = {"agent", "model", "tools", "generated_at"}
SOURCE_FIELDS = {"source_id", "tier", "title", "accessed_at", "url", "local_path"}
POLICY_FIELDS = {
    "schema_version",
    "policy_id",
    "version",
    "effective_at",
    "kind",
    "payload",
}
POLICY_PAYLOAD_FIELDS = {
    "sampling_algorithm",
    "stable_seed",
    "strata",
    "expansion",
    "independence",
}
STRATUM_POLICY_FIELDS = {
    "initial_sample_rate",
    "minimum_sample_count",
    "material_error_rate_threshold",
}
EXPANSION_FIELDS = {
    "rule",
    "multiplier",
    "minimum_increment",
    "on_full_census_over_threshold",
}
INDEPENDENCE_FIELDS = {
    "reviewer_must_differ_from_original_agent",
    "one_active_company_per_reviewer",
}
SYMBOL_RE = re.compile(r"^CN:[0-9]{6}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")


def validate_quality_audit_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize the dedicated quality-audit policy."""

    _exact_fields(policy, POLICY_FIELDS, "quality-audit policy")
    if policy.get("schema_version") != 2:
        raise QualityAuditError("quality-audit policy schema_version must be 2")
    policy_id = _text(policy.get("policy_id"), "policy_id")
    version = _text(policy.get("version"), "version")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise QualityAuditError("quality-audit policy version must be semantic")
    effective_at = _datetime(policy.get("effective_at"), "effective_at")
    if policy.get("kind") != "triage_quality_audit":
        raise QualityAuditError(
            "quality-audit policy kind must be triage_quality_audit"
        )
    payload = policy.get("payload")
    _exact_fields(payload, POLICY_PAYLOAD_FIELDS, "quality-audit policy payload")
    if payload.get("sampling_algorithm") != "sha256_stratified_v1":
        raise QualityAuditError("unsupported quality-audit sampling_algorithm")
    seed = _text(payload.get("stable_seed"), "stable_seed")

    raw_strata = payload.get("strata")
    if not isinstance(raw_strata, Mapping) or set(raw_strata) != set(ALL_STRATA):
        raise QualityAuditError(f"quality-audit strata must be exactly {sorted(ALL_STRATA)}")
    strata: dict[str, dict[str, Any]] = {}
    for name in ALL_STRATA:
        raw = raw_strata[name]
        _exact_fields(raw, STRATUM_POLICY_FIELDS, f"stratum policy {name}")
        rate = _fraction(raw.get("initial_sample_rate"), f"{name}.initial_sample_rate")
        minimum = _non_negative_int(raw.get("minimum_sample_count"), f"{name}.minimum_sample_count")
        threshold = _fraction(
            raw.get("material_error_rate_threshold"),
            f"{name}.material_error_rate_threshold",
        )
        if name == "hard_exclusion" and rate != 1.0:
            raise QualityAuditError("hard_exclusion initial_sample_rate must be 1.0")
        strata[name] = {
            "initial_sample_rate": rate,
            "minimum_sample_count": minimum,
            "material_error_rate_threshold": threshold,
        }

    expansion = payload.get("expansion")
    _exact_fields(expansion, EXPANSION_FIELDS, "quality-audit expansion")
    if expansion.get("rule") != "double_cumulative_sample_v1":
        raise QualityAuditError("unsupported quality-audit expansion rule")
    multiplier = _positive_int(expansion.get("multiplier"), "expansion.multiplier")
    if multiplier < 2:
        raise QualityAuditError("expansion.multiplier must be at least 2")
    minimum_increment = _positive_int(
        expansion.get("minimum_increment"), "expansion.minimum_increment"
    )
    if expansion.get("on_full_census_over_threshold") != "redo_entire_stratum":
        raise QualityAuditError("unsupported full-census expansion action")

    independence = payload.get("independence")
    _exact_fields(independence, INDEPENDENCE_FIELDS, "quality-audit independence")
    for field in INDEPENDENCE_FIELDS:
        if independence.get(field) is not True:
            raise QualityAuditError(f"quality-audit {field} must be true")

    return {
        "schema_version": 2,
        "policy_id": policy_id,
        "version": version,
        "effective_at": effective_at.isoformat(),
        "kind": "triage_quality_audit",
        "payload": {
            "sampling_algorithm": "sha256_stratified_v1",
            "stable_seed": seed,
            "strata": strata,
            "expansion": {
                "rule": "double_cumulative_sample_v1",
                "multiplier": multiplier,
                "minimum_increment": minimum_increment,
                "on_full_census_over_threshold": "redo_entire_stratum",
            },
            "independence": {field: True for field in sorted(INDEPENDENCE_FIELDS)},
        },
    }


def load_quality_audit_policy(path: str | Path) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QualityAuditError(f"invalid quality-audit policy: {path}") from exc
    if not isinstance(raw, Mapping):
        raise QualityAuditError("quality-audit policy must be an object")
    return validate_quality_audit_policy(raw)


def quality_policy_sha256(policy: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(validate_quality_audit_policy(policy))).hexdigest()


def deterministic_stratified_sample(
    population: Sequence[Mapping[str, Any]],
    *,
    stratum: str,
    subject_binding_sha256: str,
    policy: Mapping[str, Any],
    already_sampled_symbols: Sequence[str] = (),
) -> dict[str, Any]:
    """Return a stable initial or expanded sample without investment ordering."""

    normalized_policy = validate_quality_audit_policy(policy)
    if stratum not in ALL_STRATA:
        raise QualityAuditError(f"unsupported quality-audit stratum: {stratum}")
    binding_sha = _sha256(subject_binding_sha256, "subject_binding_sha256")
    normalized = _normalize_population(population, stratum=stratum)
    sampled = {_symbol(value) for value in already_sampled_symbols}
    unknown = sampled - {item["symbol"] for item in normalized}
    if unknown:
        raise QualityAuditError(
            f"already-sampled symbols are outside population: {sorted(unknown)}"
        )
    policy_sha = quality_policy_sha256(normalized_policy)
    seed = normalized_policy["payload"]["stable_seed"]
    ranked = sorted(
        normalized,
        key=lambda item: (
            hashlib.sha256(
                "|".join(
                    (
                        seed,
                        policy_sha,
                        binding_sha,
                        stratum,
                        item["symbol"],
                        item["source_subject_sha256"],
                    )
                ).encode("utf-8")
            ).hexdigest(),
            item["symbol"],
        ),
    )
    stratum_policy = normalized_policy["payload"]["strata"][stratum]
    initial_count = min(
        len(ranked),
        max(
            stratum_policy["minimum_sample_count"],
            math.ceil(len(ranked) * stratum_policy["initial_sample_rate"]),
        ),
    )
    if sampled:
        current = len(sampled)
        expansion = normalized_policy["payload"]["expansion"]
        target_count = min(
            len(ranked),
            max(
                current + expansion["minimum_increment"],
                current * expansion["multiplier"],
            ),
        )
    else:
        target_count = initial_count
    selected = [item for item in ranked if item["symbol"] not in sampled][
        : max(0, target_count - len(sampled))
    ]
    return {
        "schema_version": 1,
        "stratum": stratum,
        "population_count": len(ranked),
        "already_sampled_count": len(sampled),
        "target_cumulative_count": target_count,
        "selected_count": len(selected),
        "selected_symbols": [item["symbol"] for item in selected],
        "ranked_symbols": [item["symbol"] for item in ranked],
        "policy_sha256": policy_sha,
        "subject_binding_sha256": binding_sha,
    }


def seal_scope_identity_audit_plan(
    *,
    output_dir: str | Path,
    audit_id: str,
    scope_id: str,
    scope_path: str,
    scope_sha256: str,
    hard_exclusions: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    created_at: dt.datetime,
) -> dict[str, Any]:
    """Seal a 100% hard-exclusion identity-review plan and blind packets."""

    _aware(created_at, "created_at")
    normalized_policy = validate_quality_audit_policy(policy)
    audit = _identifier(audit_id, "audit_id")
    scope = _identifier(scope_id, "scope_id")
    binding_sha = _sha256(scope_sha256, "scope_sha256")
    population = _normalize_scope_population(hard_exclusions)
    sample = deterministic_stratified_sample(
        population,
        stratum="hard_exclusion",
        subject_binding_sha256=binding_sha,
        policy=normalized_policy,
    )
    if sample["selected_count"] != len(population):
        raise QualityAuditError("hard-exclusion identity audit must sample 100%")
    base = Path(output_dir)
    items = []
    for ordinal, item in enumerate(population, 1):
        audit_item_id = f"{audit}:{item['symbol'].replace(':', '-')}"
        packet = _scope_fact_packet(
            audit_id=audit,
            audit_item_id=audit_item_id,
            scope_id=scope,
            item=item,
            created_at=created_at,
        )
        packet_path = base / "packets" / f"{item['symbol'].split(':')[1]}.facts.json"
        sealed = _seal(packet_path, packet, "scope_identity_audit_fact_packet", created_at)
        items.append(
            {
                "ordinal": ordinal,
                "audit_item_id": audit_item_id,
                "symbol": item["symbol"],
                "name": item["name"],
                "stratum": "hard_exclusion",
                "source_subject_sha256": item["source_subject_sha256"],
                "original_agent": item.get("original_agent"),
                "facts_packet_path": packet_path.relative_to(base).as_posix(),
                "facts_packet_sha256": sealed.sha256,
            }
        )
    plan = {
        "schema_version": 1,
        "audit_id": audit,
        "subject_kind": "scope_identity",
        "scope_id": scope,
        "scope_path": _text(scope_path, "scope_path"),
        "scope_sha256": binding_sha,
        "policy": _policy_reference(normalized_policy),
        "created_at": created_at.isoformat(),
        "population_count": len(population),
        "sampled_count": len(items),
        "items": items,
        "portfolio_action": None,
    }
    sealed_plan = _seal(base / "plan.json", plan, "scope_identity_audit_plan", created_at)
    return _plan_result(base, sealed_plan, plan)


def seal_scope_identity_audit_result(
    *,
    plan_path: str | Path,
    reviews: Sequence[Mapping[str, Any]],
    completed_at: dt.datetime,
) -> dict[str, Any]:
    _aware(completed_at, "completed_at")
    path = Path(plan_path)
    plan, base = _load_plan(path, "scope_identity_audit_plan")
    if plan.get("subject_kind") != "scope_identity":
        raise QualityAuditError("identity audit result requires a scope identity plan")
    review_by_id = _unique_reviews(reviews)
    expected = {item["audit_item_id"] for item in plan["items"]}
    _exact_review_coverage(review_by_id, expected)
    rows = []
    reopen = []
    for item in plan["items"]:
        packet = _load_bound_packet(base, item, "scope_identity_audit_fact_packet")
        review = _validate_identity_review(
            review_by_id[item["audit_item_id"]], item=item, packet=packet, completed_at=completed_at
        )
        major = review["identity_verdict"] != "hard_exclusion"
        if major:
            reopen.append(item["symbol"])
        rows.append(
            {
                "audit_item_id": item["audit_item_id"],
                "symbol": item["symbol"],
                "identity_verdict": review["identity_verdict"],
                "major_disagreement": major,
                "review": review,
            }
        )
    result = {
        "schema_version": 1,
        "audit_id": plan["audit_id"],
        "subject_kind": "scope_identity",
        "plan_sha256": verify_sealed(path).sha256,
        "completed_at": completed_at.isoformat(),
        "reviewed_count": len(rows),
        "major_disagreement_count": len(reopen),
        "reopen_required": bool(reopen),
        "reopen_symbols": reopen,
        "status": "reopen_required" if reopen else "passed",
        "rows": rows,
        "portfolio_action": None,
    }
    sealed = _seal(base / "result.json", result, "scope_identity_audit_result", completed_at)
    return _result_summary(base, sealed, result)


def seal_cycle_quality_audit_plan(
    *,
    output_dir: str | Path,
    audit_id: str,
    cycle_id: str,
    cohort_path: str,
    cohort_sha256: str,
    records: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    created_at: dt.datetime,
    already_sampled_symbols: Mapping[str, Sequence[str]] | None = None,
    force_full_census_strata: Sequence[str] = (),
    error_semantics: str = "routing_disagreement_v1",
) -> dict[str, Any]:
    """Seal a stratified half-blind cycle plan and per-company fact packets."""

    _aware(created_at, "created_at")
    normalized_policy = validate_quality_audit_policy(policy)
    audit = _identifier(audit_id, "audit_id")
    cycle = _identifier(cycle_id, "cycle_id")
    if error_semantics not in ERROR_SEMANTICS:
        raise QualityAuditError(
            f"unsupported quality-audit error semantics: {error_semantics}"
        )
    binding_sha = _sha256(cohort_sha256, "cohort_sha256")
    population = _normalize_cycle_population(records)
    base = Path(output_dir)
    items = []
    strata_rows = []
    sampled_map = already_sampled_symbols or {}
    forced_strata = set(force_full_census_strata)
    unknown_forced = forced_strata - set(STOP_STRATA)
    if unknown_forced:
        raise QualityAuditError(
            f"unsupported forced full-census strata: {sorted(unknown_forced)}"
        )
    for stratum in STOP_STRATA:
        stratum_population = [item for item in population if item["disposition"] == stratum]
        if stratum in forced_strata:
            ranked = deterministic_stratified_sample(
                stratum_population,
                stratum=stratum,
                subject_binding_sha256=binding_sha,
                policy=normalized_policy,
            )["ranked_symbols"]
            sample = {
                "selected_symbols": ranked,
                "ranked_symbols": ranked,
            }
        else:
            sample = deterministic_stratified_sample(
                stratum_population,
                stratum=stratum,
                subject_binding_sha256=binding_sha,
                policy=normalized_policy,
                already_sampled_symbols=sampled_map.get(stratum, ()),
            )
        selected = set(sample["selected_symbols"])
        selected_records = [item for item in stratum_population if item["symbol"] in selected]
        selected_records.sort(key=lambda item: sample["selected_symbols"].index(item["symbol"]))
        for item in selected_records:
            audit_item_id = f"{audit}:{item['symbol'].replace(':', '-')}"
            packet = _cycle_fact_packet(
                audit_id=audit,
                audit_item_id=audit_item_id,
                cycle_id=cycle,
                item=item,
                created_at=created_at,
            )
            packet_path = base / "packets" / f"{item['symbol'].split(':')[1]}.facts.json"
            sealed = _seal(packet_path, packet, "triage_quality_audit_fact_packet", created_at)
            items.append(
                {
                    "audit_item_id": audit_item_id,
                    "symbol": item["symbol"],
                    "name": item["name"],
                    "stratum": stratum,
                    "source_subject_sha256": item["source_subject_sha256"],
                    "original_agent": item["original_agent"],
                    "facts_packet_path": packet_path.relative_to(base).as_posix(),
                    "facts_packet_sha256": sealed.sha256,
                }
            )
        strata_rows.append(
            {
                "stratum": stratum,
                "population_count": len(stratum_population),
                "already_sampled_count": (
                    0 if stratum in forced_strata else len(sampled_map.get(stratum, ()))
                ),
                "sampled_count": len(selected_records),
                "full_census_redo": stratum in forced_strata,
                "ranked_symbols": sample["ranked_symbols"],
            }
        )
    plan = {
        "schema_version": 2,
        "audit_id": audit,
        "subject_kind": "triage_false_negative",
        "error_semantics": error_semantics,
        "cycle_id": cycle,
        "cohort_path": _text(cohort_path, "cohort_path"),
        "cohort_sha256": binding_sha,
        "policy": _policy_reference(normalized_policy),
        "created_at": created_at.isoformat(),
        "population_count": len(population),
        "sampled_count": len(items),
        "population": [
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "stratum": item["disposition"],
                "source_subject_sha256": item["source_subject_sha256"],
            }
            for item in population
        ],
        "strata": strata_rows,
        "items": items,
        "portfolio_action": None,
    }
    sealed_plan = _seal(base / "plan.json", plan, "triage_quality_audit_plan", created_at)
    return _plan_result(base, sealed_plan, plan)


def seal_cycle_quality_audit_result(
    *,
    plan_path: str | Path,
    reviews: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    completed_at: dt.datetime,
) -> dict[str, Any]:
    """Reveal sealed source dispositions and seal disagreement/expansion status."""

    _aware(completed_at, "completed_at")
    normalized_policy = validate_quality_audit_policy(policy)
    path = Path(plan_path)
    plan, base = _load_plan(path, "triage_quality_audit_plan")
    if plan.get("subject_kind") != "triage_false_negative":
        raise QualityAuditError("cycle audit result requires a triage quality plan")
    if plan.get("policy") != _policy_reference(normalized_policy):
        raise QualityAuditError("quality-audit result policy does not match sealed plan")
    review_by_id = _unique_reviews(reviews)
    expected = {item["audit_item_id"] for item in plan["items"]}
    _exact_review_coverage(review_by_id, expected)

    rows = []
    reopen_symbols: list[str] = []
    reviewer_agents: set[str] = set()
    stats = {
        stratum: {
            "stratum": stratum,
            "population_count": next(
                row["population_count"] for row in plan["strata"] if row["stratum"] == stratum
            ),
            "reviewed_count": 0,
            "material_error_count": 0,
            "major_disagreement_count": 0,
        }
        for stratum in STOP_STRATA
    }
    for item in plan["items"]:
        packet = _load_bound_packet(base, item, "triage_quality_audit_fact_packet")
        review = _validate_cycle_review(
            review_by_id[item["audit_item_id"]], item=item, packet=packet, completed_at=completed_at
        )
        _require_unique_reviewer(review, reviewer_agents)
        original = item["stratum"]
        recommended = review["recommended_disposition"]
        finding_severities = {finding["severity"] for finding in review["findings"]}
        error_semantics = plan.get("error_semantics", "finding_severity_v1")
        if error_semantics not in ERROR_SEMANTICS:
            raise QualityAuditError(
                f"unsupported quality-audit error semantics: {error_semantics}"
            )
        if error_semantics == "routing_disagreement_v1":
            major = bool(
                recommended == "triage_candidate"
                or (original == "conditional_stop")
                != (recommended == "conditional_stop")
            )
            material = bool(major or recommended != original)
        else:
            major = bool(
                recommended == "triage_candidate"
                or (original == "conditional_stop")
                != (recommended == "conditional_stop")
                or "major" in finding_severities
            )
            material = bool(
                major or recommended != original or "material" in finding_severities
            )
        if major:
            reopen_symbols.append(item["symbol"])
        stat = stats[original]
        stat["reviewed_count"] += 1
        stat["material_error_count"] += int(material)
        stat["major_disagreement_count"] += int(major)
        rows.append(
            {
                "audit_item_id": item["audit_item_id"],
                "symbol": item["symbol"],
                "original_disposition": original,
                "recommended_disposition": recommended,
                "material_error": material,
                "major_disagreement": major,
                "review": review,
            }
        )

    expansion_symbols: dict[str, list[str]] = {}
    redo_strata: list[str] = []
    plan_strata = {
        _text(row.get("stratum"), "plan stratum"): row
        for row in (_mapping(value, "plan stratum") for value in plan["strata"])
    }
    for stratum, stat in stats.items():
        reviewed = stat["reviewed_count"]
        rate = stat["material_error_count"] / reviewed if reviewed else 0.0
        threshold = normalized_policy["payload"]["strata"][stratum]["material_error_rate_threshold"]
        stat["observed_material_error_rate"] = rate
        stat["material_error_rate_threshold"] = threshold
        stat["over_threshold"] = reviewed > 0 and rate > threshold
        if not stat["over_threshold"]:
            stat["next_sample_symbols"] = []
            continue
        plan_stratum = plan_strata[stratum]
        if plan_stratum.get("full_census_redo") is True:
            stat["next_sample_symbols"] = []
            continue
        ranked_raw = plan_stratum.get("ranked_symbols")
        if not isinstance(ranked_raw, Sequence) or isinstance(
            ranked_raw, (str, bytes)
        ):
            raise QualityAuditError(
                f"plan stratum {stratum} ranked_symbols must be an array"
            )
        ranked = [
            _symbol(value)
            for value in ranked_raw
        ]
        already_sampled_count = _non_negative_int(
            plan_stratum.get("already_sampled_count", 0),
            f"plan stratum {stratum} already_sampled_count",
        )
        if already_sampled_count > len(ranked):
            raise QualityAuditError(
                f"plan stratum {stratum} already_sampled_count exceeds population"
            )
        current_reviewed_symbols = {
            row["symbol"] for row in rows if row["original_disposition"] == stratum
        }
        cumulative_reviewed_symbols = set(ranked[:already_sampled_count])
        cumulative_reviewed_symbols.update(current_reviewed_symbols)
        if len(cumulative_reviewed_symbols) >= stat["population_count"]:
            redo_strata.append(stratum)
            next_symbols: list[str] = []
        else:
            expansion = normalized_policy["payload"]["expansion"]
            cumulative_reviewed_count = len(cumulative_reviewed_symbols)
            target = min(
                stat["population_count"],
                max(
                    cumulative_reviewed_count + expansion["minimum_increment"],
                    cumulative_reviewed_count * expansion["multiplier"],
                ),
            )
            next_symbols = [
                symbol
                for symbol in ranked
                if symbol not in cumulative_reviewed_symbols
            ][
                : target - cumulative_reviewed_count
            ]
            expansion_symbols[stratum] = next_symbols
        stat["next_sample_symbols"] = next_symbols

    reopen_symbols = sorted(set(reopen_symbols))
    expansion_required = bool(expansion_symbols)
    redo_required = bool(redo_strata)
    if reopen_symbols:
        status = "reopen_required"
    elif redo_required:
        status = "redo_required"
    elif expansion_required:
        status = "expansion_required"
    else:
        status = "passed"
    result = {
        "schema_version": 1,
        "audit_id": plan["audit_id"],
        "subject_kind": "triage_false_negative",
        "cycle_id": plan["cycle_id"],
        "error_semantics": plan.get("error_semantics", "finding_severity_v1"),
        "plan_sha256": verify_sealed(path).sha256,
        "policy": _policy_reference(normalized_policy),
        "completed_at": completed_at.isoformat(),
        "reviewed_count": len(rows),
        "material_error_count": sum(row["material_error"] for row in rows),
        "major_disagreement_count": sum(row["major_disagreement"] for row in rows),
        "reopen_required": bool(reopen_symbols),
        "reopen_symbols": reopen_symbols,
        "expansion_required": expansion_required,
        "expansion_symbols": expansion_symbols,
        "redo_required": redo_required,
        "redo_strata": sorted(redo_strata),
        "status": status,
        "strata": [stats[name] for name in STOP_STRATA],
        "rows": rows,
        "portfolio_action": None,
    }
    sealed = _seal(base / "result.json", result, "triage_quality_audit_result", completed_at)
    return _result_summary(base, sealed, result)


def quality_audit_status(path: str | Path) -> dict[str, Any]:
    """Return a verified status summary for a sealed quality plan or result."""

    target = Path(path)
    try:
        sealed = verify_sealed(target)
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise QualityAuditError(f"quality-audit artifact is invalid: {target}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise QualityAuditError("quality-audit artifact must be an object")
    if sealed.artifact_type.endswith("_plan"):
        return {
            "schema_version": 1,
            "audit_id": payload.get("audit_id"),
            "subject_kind": payload.get("subject_kind"),
            "status": "pending_reviews",
            "sampled_count": payload.get("sampled_count"),
            "artifact_path": str(target),
            "artifact_sha256": sealed.sha256,
        }
    if sealed.artifact_type not in {
        "scope_identity_audit_result",
        "triage_quality_audit_result",
    }:
        raise QualityAuditError(f"unsupported quality-audit artifact type: {sealed.artifact_type}")
    return {
        "schema_version": 1,
        "audit_id": payload.get("audit_id"),
        "subject_kind": payload.get("subject_kind"),
        "status": payload.get("status"),
        "reopen_required": bool(payload.get("reopen_required")),
        "expansion_required": bool(payload.get("expansion_required")),
        "redo_required": bool(payload.get("redo_required")),
        "artifact_path": str(target),
        "artifact_sha256": sealed.sha256,
    }


def _normalize_population(
    population: Sequence[Mapping[str, Any]], *, stratum: str
) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for raw in population:
        if not isinstance(raw, Mapping):
            raise QualityAuditError("quality-audit population row must be an object")
        symbol = _symbol(raw.get("symbol"))
        if symbol in seen:
            raise QualityAuditError(f"duplicate quality-audit symbol: {symbol}")
        seen.add(symbol)
        if raw.get("disposition", stratum) != stratum:
            raise QualityAuditError(f"population row has the wrong stratum: {symbol}")
        rows.append(
            {
                "symbol": symbol,
                "source_subject_sha256": _sha256(
                    raw.get("source_subject_sha256"), f"{symbol}.source_subject_sha256"
                ),
            }
        )
    return rows


def _normalize_scope_population(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise QualityAuditError("hard-exclusion row must be an object")
        symbol = _symbol(raw.get("symbol"))
        if symbol in seen:
            raise QualityAuditError(f"duplicate hard-exclusion symbol: {symbol}")
        seen.add(symbol)
        result.append(
            {
                "symbol": symbol,
                "name": _text(raw.get("name"), f"{symbol}.name"),
                "source_subject_sha256": _sha256(
                    raw.get("source_subject_sha256"), f"{symbol}.source_subject_sha256"
                ),
                "identity_facts": copy.deepcopy(
                    _mapping(raw.get("identity_facts"), f"{symbol}.identity_facts")
                ),
                "sources": _normalize_sources(raw.get("sources"), symbol=symbol),
                "original_agent": _optional_text(raw.get("original_agent")),
            }
        )
    return sorted(result, key=lambda item: item["symbol"])


def _normalize_cycle_population(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise QualityAuditError("triage audit row must be an object")
        symbol = _symbol(raw.get("symbol"))
        if symbol in seen:
            raise QualityAuditError(f"duplicate triage audit symbol: {symbol}")
        seen.add(symbol)
        disposition = raw.get("disposition")
        if disposition not in STOP_DISPOSITIONS:
            raise QualityAuditError(f"triage quality population is not a stop: {symbol}")
        price = _mapping(raw.get("price_snapshot"), f"{symbol}.price_snapshot")
        current_price = _positive_number(price.get("price"), f"{symbol}.price")
        result.append(
            {
                "symbol": symbol,
                "name": _text(raw.get("name"), f"{symbol}.name"),
                "disposition": disposition,
                "source_subject_sha256": _sha256(
                    raw.get("source_subject_sha256"), f"{symbol}.source_subject_sha256"
                ),
                "original_agent": _text(raw.get("original_agent"), f"{symbol}.original_agent"),
                "information_cutoff": _datetime(
                    raw.get("information_cutoff"), f"{symbol}.information_cutoff"
                ).isoformat(),
                "price_snapshot": {
                    "price": current_price,
                    "price_as_of": _datetime(
                        price.get("price_as_of"), f"{symbol}.price_as_of"
                    ).isoformat(),
                    "source_id": _text(price.get("source_id"), f"{symbol}.price.source_id"),
                },
                "sources": _normalize_sources(raw.get("sources"), symbol=symbol),
            }
        )
    return sorted(result, key=lambda item: item["symbol"])


def _scope_fact_packet(
    *,
    audit_id: str,
    audit_item_id: str,
    scope_id: str,
    item: Mapping[str, Any],
    created_at: dt.datetime,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "audit_id": audit_id,
        "audit_item_id": audit_item_id,
        "subject_kind": "scope_identity",
        "scope_id": scope_id,
        "created_at": created_at.isoformat(),
        "symbol": item["symbol"],
        "company_name": item["name"],
        "source_subject_commitment_sha256": item["source_subject_sha256"],
        "identity_facts": copy.deepcopy(item["identity_facts"]),
        "sources": copy.deepcopy(item["sources"]),
        "blind_contract": {"omitted_fields": ["original_scope_classification", "original_agent"]},
        "portfolio_action": None,
    }


def _cycle_fact_packet(
    *,
    audit_id: str,
    audit_item_id: str,
    cycle_id: str,
    item: Mapping[str, Any],
    created_at: dt.datetime,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "audit_id": audit_id,
        "audit_item_id": audit_item_id,
        "subject_kind": "triage_false_negative",
        "cycle_id": cycle_id,
        "created_at": created_at.isoformat(),
        "symbol": item["symbol"],
        "company_name": item["name"],
        "information_cutoff": item["information_cutoff"],
        "price_snapshot": copy.deepcopy(item["price_snapshot"]),
        "source_subject_commitment_sha256": item["source_subject_sha256"],
        "sources": copy.deepcopy(item["sources"]),
        "blind_contract": {
            "omitted_fields": [
                "original_disposition",
                "business_summary",
                "change_summary",
                "normalized_earnings_view",
                "expectations_view",
                "counterevidence",
                "reason_codes",
                "revisit_triggers",
                "original_agent",
                "allocation_decision",
            ]
        },
        "portfolio_action": None,
    }


def _normalize_sources(raw: Any, *, symbol: str) -> list[dict[str, Any]]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        raise QualityAuditError(f"{symbol}.sources must be a non-empty array")
    result = []
    seen = set()
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise QualityAuditError(f"{symbol}.sources[{index}] must be an object")
        source_id = _text(item.get("source_id"), f"{symbol}.sources[{index}].source_id")
        if source_id in seen:
            raise QualityAuditError(f"duplicate source_id for {symbol}: {source_id}")
        seen.add(source_id)
        tier = item.get("tier")
        if tier not in {"S1", "S2", "S3"}:
            raise QualityAuditError(f"invalid source tier for {symbol}: {tier}")
        url = _optional_text(item.get("url"))
        local_path = _optional_text(item.get("local_path"))
        if url is None and local_path is None:
            raise QualityAuditError(f"source must have url or local_path for {symbol}")
        result.append(
            {
                "source_id": source_id,
                "tier": tier,
                "title": _text(item.get("title"), f"{symbol}.sources[{index}].title"),
                "accessed_at": _datetime(
                    item.get("accessed_at"), f"{symbol}.sources[{index}].accessed_at"
                ).isoformat(),
                "url": url,
                "local_path": local_path,
            }
        )
    return result


def _validate_identity_review(
    raw: Mapping[str, Any],
    *,
    item: Mapping[str, Any],
    packet: Mapping[str, Any],
    completed_at: dt.datetime,
) -> dict[str, Any]:
    expected = {
        "schema_version",
        "audit_item_id",
        "facts_packet_sha256",
        "symbol",
        "identity_verdict",
        "reason",
        "source_ids",
        "provenance",
    }
    _exact_fields(raw, expected, "scope identity review")
    common = _validate_review_common(raw, item=item, packet=packet, completed_at=completed_at)
    verdict = raw.get("identity_verdict")
    if verdict not in IDENTITY_VERDICTS:
        raise QualityAuditError("scope identity review verdict is invalid")
    return {
        **common,
        "identity_verdict": verdict,
        "reason": _text(raw.get("reason"), "identity review reason"),
        "source_ids": _source_ids(raw.get("source_ids"), packet),
    }


def _validate_cycle_review(
    raw: Mapping[str, Any],
    *,
    item: Mapping[str, Any],
    packet: Mapping[str, Any],
    completed_at: dt.datetime,
) -> dict[str, Any]:
    expected = {
        "schema_version",
        "audit_item_id",
        "facts_packet_sha256",
        "symbol",
        "recommended_disposition",
        "decisive_question",
        "findings",
        "provenance",
    }
    _exact_fields(raw, expected, "triage quality review")
    common = _validate_review_common(raw, item=item, packet=packet, completed_at=completed_at)
    disposition = raw.get("recommended_disposition")
    if disposition not in ALL_DISPOSITIONS:
        raise QualityAuditError("triage quality recommended_disposition is invalid")
    raw_findings = raw.get("findings")
    if not isinstance(raw_findings, list):
        raise QualityAuditError("triage quality findings must be an array")
    findings = []
    ids = set()
    for finding in raw_findings:
        _exact_fields(
            finding,
            {"finding_id", "severity", "category", "statement", "source_ids"},
            "triage quality finding",
        )
        finding_id = _identifier(finding.get("finding_id"), "finding_id")
        if finding_id in ids:
            raise QualityAuditError(f"duplicate finding_id: {finding_id}")
        ids.add(finding_id)
        severity = finding.get("severity")
        if severity not in FINDING_SEVERITIES:
            raise QualityAuditError(f"invalid finding severity: {severity}")
        findings.append(
            {
                "finding_id": finding_id,
                "severity": severity,
                "category": _text(finding.get("category"), "finding.category"),
                "statement": _text(finding.get("statement"), "finding.statement"),
                "source_ids": _source_ids(finding.get("source_ids"), packet),
            }
        )
    return {
        **common,
        "recommended_disposition": disposition,
        "decisive_question": _text(raw.get("decisive_question"), "decisive_question"),
        "findings": findings,
    }


def _validate_review_common(
    raw: Mapping[str, Any],
    *,
    item: Mapping[str, Any],
    packet: Mapping[str, Any],
    completed_at: dt.datetime,
) -> dict[str, Any]:
    if raw.get("schema_version") != 1:
        raise QualityAuditError("quality review schema_version must be 1")
    if raw.get("audit_item_id") != item["audit_item_id"]:
        raise QualityAuditError("quality review audit_item_id does not match plan")
    if raw.get("facts_packet_sha256") != item["facts_packet_sha256"]:
        raise QualityAuditError("quality review facts packet SHA does not match plan")
    if raw.get("symbol") != item["symbol"]:
        raise QualityAuditError("quality review symbol does not match plan")
    provenance = _provenance(raw.get("provenance"), completed_at=completed_at)
    packet_created_at = _datetime(packet.get("created_at"), "facts_packet.created_at")
    if _datetime(provenance["generated_at"], "provenance.generated_at") < packet_created_at:
        raise QualityAuditError("quality review cannot predate the sealed facts packet")
    original_agent = item.get("original_agent")
    if isinstance(original_agent, str) and provenance["agent"] == original_agent:
        raise QualityAuditError("quality reviewer must differ from original Agent")
    return {
        "schema_version": 1,
        "audit_item_id": item["audit_item_id"],
        "facts_packet_sha256": item["facts_packet_sha256"],
        "symbol": item["symbol"],
        "provenance": provenance,
    }


def _require_unique_reviewer(review: Mapping[str, Any], reviewer_agents: set[str]) -> None:
    agent = str(review["provenance"]["agent"])
    if agent in reviewer_agents:
        raise QualityAuditError(
            f"one quality-review Agent cannot review multiple companies: {agent}"
        )
    reviewer_agents.add(agent)


def _provenance(raw: Any, *, completed_at: dt.datetime) -> dict[str, Any]:
    _exact_fields(raw, PROVENANCE_FIELDS, "quality review provenance")
    generated_at = _datetime(raw.get("generated_at"), "provenance.generated_at")
    if generated_at > completed_at:
        raise QualityAuditError("quality review cannot be generated after completion")
    tools = raw.get("tools")
    if not isinstance(tools, list) or not tools:
        raise QualityAuditError("quality review provenance tools must be non-empty")
    normalized_tools = [_text(item, "provenance tool") for item in tools]
    if len(set(normalized_tools)) != len(normalized_tools):
        raise QualityAuditError("quality review provenance tools must be unique")
    return {
        "agent": _text(raw.get("agent"), "provenance.agent"),
        "model": _text(raw.get("model"), "provenance.model"),
        "tools": normalized_tools,
        "generated_at": generated_at.isoformat(),
    }


def _source_ids(raw: Any, packet: Mapping[str, Any]) -> list[str]:
    if not isinstance(raw, list) or not raw:
        raise QualityAuditError("quality review source_ids must be non-empty")
    values = [_text(item, "source_id") for item in raw]
    available = {item["source_id"] for item in packet["sources"]}
    unknown = set(values) - available
    if unknown:
        raise QualityAuditError(f"quality review cites unknown sources: {sorted(unknown)}")
    return values


def _load_plan(path: Path, artifact_type: str) -> tuple[dict[str, Any], Path]:
    try:
        sealed = verify_sealed(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise QualityAuditError(f"quality-audit plan is invalid: {path}: {exc}") from exc
    if sealed.artifact_type != artifact_type:
        raise QualityAuditError(f"quality-audit plan artifact type is not {artifact_type}")
    if not isinstance(payload, dict):
        raise QualityAuditError("quality-audit plan must be an object")
    return payload, path.parent


def _load_bound_packet(base: Path, item: Mapping[str, Any], artifact_type: str) -> dict[str, Any]:
    path = base / item["facts_packet_path"]
    try:
        sealed = verify_sealed(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise QualityAuditError(f"quality-audit facts packet is invalid: {path}: {exc}") from exc
    if sealed.artifact_type != artifact_type or sealed.sha256 != item["facts_packet_sha256"]:
        raise QualityAuditError("quality-audit facts packet does not match sealed plan")
    if not isinstance(payload, dict):
        raise QualityAuditError("quality-audit facts packet must be an object")
    return payload


def _unique_reviews(reviews: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result = {}
    for review in reviews:
        if not isinstance(review, Mapping):
            raise QualityAuditError("quality review must be an object")
        audit_item_id = _identifier(review.get("audit_item_id"), "review.audit_item_id")
        if audit_item_id in result:
            raise QualityAuditError(f"duplicate quality review: {audit_item_id}")
        result[audit_item_id] = review
    return result


def _exact_review_coverage(reviews: Mapping[str, Any], expected: set[str]) -> None:
    if set(reviews) != expected:
        missing = sorted(expected - set(reviews))
        extra = sorted(set(reviews) - expected)
        raise QualityAuditError(
            "quality reviews must cover every sampled item exactly once; "
            f"missing={missing}, extra={extra}"
        )


def _policy_reference(policy: Mapping[str, Any]) -> dict[str, str]:
    normalized = validate_quality_audit_policy(policy)
    return {
        "policy_id": normalized["policy_id"],
        "version": normalized["version"],
        "sha256": quality_policy_sha256(normalized),
    }


def _plan_result(base: Path, sealed: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "audit_id": payload["audit_id"],
        "subject_kind": payload["subject_kind"],
        "population_count": payload["population_count"],
        "sampled_count": payload["sampled_count"],
        "plan_path": str(sealed.path),
        "plan_sha256": sealed.sha256,
        "packet_root": str(base / "packets"),
        "status": "pending_reviews",
    }


def _result_summary(base: Path, sealed: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "audit_id": payload["audit_id"],
        "subject_kind": payload["subject_kind"],
        "status": payload["status"],
        "reopen_required": payload["reopen_required"],
        "expansion_required": bool(payload.get("expansion_required")),
        "redo_required": bool(payload.get("redo_required")),
        "result_path": str(base / "result.json"),
        "result_sha256": sealed.sha256,
    }


def _seal(path: Path, payload: Mapping[str, Any], artifact_type: str, at: dt.datetime) -> Any:
    try:
        return seal_json(path, payload, artifact_type=artifact_type, sealed_at=at)
    except SealingError as exc:
        raise QualityAuditError(f"cannot seal quality-audit artifact: {path}: {exc}") from exc


def _exact_fields(value: Any, fields: set[str], label: str) -> None:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise QualityAuditError(f"{label} fields must be exactly {sorted(fields)}")


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise QualityAuditError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QualityAuditError(f"{label} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise QualityAuditError("optional text must be null or non-empty")
    return value.strip()


def _identifier(value: Any, label: str) -> str:
    result = _text(value, label)
    if not ID_RE.fullmatch(result):
        raise QualityAuditError(f"{label} is invalid")
    return result


def _symbol(value: Any) -> str:
    result = _text(value, "symbol")
    if not SYMBOL_RE.fullmatch(result):
        raise QualityAuditError(f"invalid CN symbol: {result}")
    return result


def _sha256(value: Any, label: str) -> str:
    result = _text(value, label)
    if len(result) != 64 or any(char not in "0123456789abcdef" for char in result):
        raise QualityAuditError(f"{label} must be a lowercase SHA-256")
    return result


def _datetime(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise QualityAuditError(f"{label} must be an ISO datetime")
    try:
        result = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise QualityAuditError(f"{label} must be an ISO datetime") from exc
    _aware(result, label)
    return result


def _aware(value: dt.datetime, label: str) -> None:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise QualityAuditError(f"{label} must include timezone information")


def _fraction(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise QualityAuditError(f"{label} must be a number from 0 to 1")
    result = float(value)
    if not math.isfinite(result) or not 0 <= result <= 1:
        raise QualityAuditError(f"{label} must be a number from 0 to 1")
    return result


def _non_negative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise QualityAuditError(f"{label} must be a non-negative integer")
    return value


def _positive_int(value: Any, label: str) -> int:
    result = _non_negative_int(value, label)
    if result == 0:
        raise QualityAuditError(f"{label} must be positive")
    return result


def _positive_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise QualityAuditError(f"{label} must be a positive number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise QualityAuditError(f"{label} must be a positive number")
    return result

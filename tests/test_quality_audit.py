from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path

import pytest

NOW = dt.datetime.fromisoformat("2026-07-30T10:00:00+08:00")


def _policy() -> dict:
    return json.loads(
        (Path(__file__).parents[1] / "policies" / "triage-quality-audit.json").read_text(
            encoding="utf-8"
        )
    )


def _source(index: int = 1) -> dict:
    return {
        "source_id": f"source-{index}",
        "tier": "S1",
        "title": f"定期报告 {index}",
        "accessed_at": (NOW - dt.timedelta(hours=2)).isoformat(),
        "url": f"https://example.test/{index}",
        "local_path": None,
        "supports": ["original conclusion must not enter blind packet"],
    }


def _cycle_record(index: int, disposition: str = "catalog") -> dict:
    ticker = f"{index:06d}"
    return {
        "symbol": f"CN:{ticker}",
        "name": f"公司{index}",
        "disposition": disposition,
        "source_subject_sha256": f"{index % 16:x}" * 64,
        "original_agent": f"/root/original-{ticker}",
        "information_cutoff": (NOW - dt.timedelta(hours=1)).isoformat(),
        "price_snapshot": {
            "price": 10.0 + index,
            "price_as_of": (NOW - dt.timedelta(hours=1)).isoformat(),
            "source_id": "price",
        },
        "sources": [_source(index)],
    }


def _cycle_review(item: dict, *, disposition: str, severity: str | None = None) -> dict:
    findings = []
    if severity is not None:
        findings.append(
            {
                "finding_id": f"finding-{item['symbol'][-6:]}",
                "severity": severity,
                "category": "false_negative" if severity == "major" else "routing",
                "statement": "独立复核发现原研究去向需要重新判断。",
                "source_ids": [f"source-{int(item['symbol'][-6:])}"],
            }
        )
    return {
        "schema_version": 1,
        "audit_item_id": item["audit_item_id"],
        "facts_packet_sha256": item["facts_packet_sha256"],
        "symbol": item["symbol"],
        "recommended_disposition": disposition,
        "decisive_question": "最新一手证据是否足以支持当前研究去向？",
        "findings": findings,
        "provenance": {
            "agent": f"/root/auditor-{item['symbol'][-6:]}",
            "model": "test-model",
            "tools": ["source-reader"],
            "generated_at": NOW.isoformat(),
        },
    }


def _load_plan(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_policy_requires_full_hard_exclusion_and_complete_strata():
    from trading_os.research_assets.quality_audit import (
        QualityAuditError,
        validate_quality_audit_policy,
    )

    normalized = validate_quality_audit_policy(_policy())
    assert normalized["payload"]["strata"]["hard_exclusion"]["initial_sample_rate"] == 1.0

    invalid = copy.deepcopy(_policy())
    invalid["payload"]["strata"]["hard_exclusion"]["initial_sample_rate"] = 0.99
    with pytest.raises(QualityAuditError, match="hard_exclusion"):
        validate_quality_audit_policy(invalid)

    missing = copy.deepcopy(_policy())
    missing["payload"]["strata"].pop("price_watch")
    with pytest.raises(QualityAuditError, match="strata"):
        validate_quality_audit_policy(missing)


def test_stratified_sample_is_order_independent_and_expands_stably():
    from trading_os.research_assets.quality_audit import deterministic_stratified_sample

    population = [
        {
            "symbol": f"CN:{index:06d}",
            "disposition": "catalog",
            "source_subject_sha256": f"{index % 16:x}" * 64,
        }
        for index in range(1, 21)
    ]
    first = deterministic_stratified_sample(
        population,
        stratum="catalog",
        subject_binding_sha256="a" * 64,
        policy=_policy(),
    )
    reordered = deterministic_stratified_sample(
        list(reversed(population)),
        stratum="catalog",
        subject_binding_sha256="a" * 64,
        policy=_policy(),
    )
    assert first == reordered
    assert first["selected_count"] == 2

    expanded = deterministic_stratified_sample(
        population,
        stratum="catalog",
        subject_binding_sha256="a" * 64,
        policy=_policy(),
        already_sampled_symbols=first["selected_symbols"],
    )
    assert expanded["target_cumulative_count"] == 4
    assert expanded["selected_count"] == 2
    assert set(expanded["selected_symbols"]).isdisjoint(first["selected_symbols"])


def test_scope_identity_plan_samples_every_exclusion_and_seals_result(tmp_path: Path):
    from trading_os.research_assets.quality_audit import (
        quality_audit_status,
        seal_scope_identity_audit_plan,
        seal_scope_identity_audit_result,
    )
    from trading_os.research_assets.sealing import verify_sealed

    exclusions = [
        {
            "symbol": f"CN:{index:06d}",
            "name": f"退市证券{index}",
            "source_subject_sha256": f"{index:x}" * 64,
            "identity_facts": {
                "security_type": "common_stock",
                "listing_status": "delisted",
            },
            "sources": [_source(index)],
            "original_agent": "/root/scope-classifier",
        }
        for index in range(1, 4)
    ]
    created = seal_scope_identity_audit_plan(
        output_dir=tmp_path / "scope-quality",
        audit_id="scope-audit-001",
        scope_id="scope-001",
        scope_path="coverage/cn-a/scopes/scope-001/manifest.json",
        scope_sha256="a" * 64,
        hard_exclusions=exclusions,
        policy=_policy(),
        created_at=NOW,
    )
    assert created["population_count"] == created["sampled_count"] == 3
    plan = _load_plan(created["plan_path"])
    reviews = []
    for item in plan["items"]:
        reviews.append(
            {
                "schema_version": 1,
                "audit_item_id": item["audit_item_id"],
                "facts_packet_sha256": item["facts_packet_sha256"],
                "symbol": item["symbol"],
                "identity_verdict": "hard_exclusion",
                "reason": "交易所身份来源确认证券已经退市。",
                "source_ids": [f"source-{int(item['symbol'][-6:])}"],
                "provenance": {
                    "agent": f"/root/identity-{item['symbol'][-6:]}",
                    "model": "test-model",
                    "tools": ["source-reader"],
                    "generated_at": NOW.isoformat(),
                },
            }
        )
    result = seal_scope_identity_audit_result(
        plan_path=created["plan_path"],
        reviews=reviews,
        completed_at=NOW + dt.timedelta(minutes=1),
    )
    assert result["status"] == "passed"
    assert verify_sealed(result["result_path"]).artifact_type == ("scope_identity_audit_result")
    assert quality_audit_status(result["result_path"])["status"] == "passed"


def test_scope_identity_disagreement_requires_reopen(tmp_path: Path):
    from trading_os.research_assets.quality_audit import (
        seal_scope_identity_audit_plan,
        seal_scope_identity_audit_result,
    )

    created = seal_scope_identity_audit_plan(
        output_dir=tmp_path / "scope-quality",
        audit_id="scope-audit-002",
        scope_id="scope-002",
        scope_path="coverage/cn-a/scopes/scope-002/manifest.json",
        scope_sha256="f" * 64,
        hard_exclusions=[
            {
                "symbol": "CN:000001",
                "name": "身份冲突证券",
                "source_subject_sha256": "1" * 64,
                "identity_facts": {"listing_status": "listed"},
                "sources": [_source(1)],
                "original_agent": "/root/scope-classifier",
            }
        ],
        policy=_policy(),
        created_at=NOW,
    )
    item = _load_plan(created["plan_path"])["items"][0]
    result = seal_scope_identity_audit_result(
        plan_path=created["plan_path"],
        reviews=[
            {
                "schema_version": 1,
                "audit_item_id": item["audit_item_id"],
                "facts_packet_sha256": item["facts_packet_sha256"],
                "symbol": item["symbol"],
                "identity_verdict": "eligible",
                "reason": "交易所身份来源显示仍为正常上市普通股。",
                "source_ids": ["source-1"],
                "provenance": {
                    "agent": "/root/identity-auditor",
                    "model": "test-model",
                    "tools": ["source-reader"],
                    "generated_at": NOW.isoformat(),
                },
            }
        ],
        completed_at=NOW + dt.timedelta(minutes=1),
    )
    payload = json.loads(Path(result["result_path"]).read_text(encoding="utf-8"))
    assert result["status"] == "reopen_required"
    assert payload["reopen_symbols"] == ["CN:000001"]


def test_cycle_fact_packet_is_half_blind_and_reviewer_must_be_independent(tmp_path: Path):
    from trading_os.research_assets.quality_audit import (
        QualityAuditError,
        seal_cycle_quality_audit_plan,
        seal_cycle_quality_audit_result,
    )

    created = seal_cycle_quality_audit_plan(
        output_dir=tmp_path / "cycle-quality",
        audit_id="cycle-audit-001",
        cycle_id="cycle-001",
        cohort_path="coverage/cn-a/triage/cycle-001/cohort.json",
        cohort_sha256="b" * 64,
        records=[_cycle_record(index) for index in range(1, 21)],
        policy=_policy(),
        created_at=NOW,
    )
    plan = _load_plan(created["plan_path"])
    assert len(plan["items"]) == 2
    item = plan["items"][0]
    packet = json.loads(
        (Path(created["plan_path"]).parent / item["facts_packet_path"]).read_text(encoding="utf-8")
    )
    serialized = json.dumps(packet, ensure_ascii=False)
    assert "original_disposition" not in packet
    assert "original_agent" not in packet
    assert "supports" not in serialized
    assert "business_summary" not in packet

    reviews = [
        _cycle_review(candidate, disposition=candidate["stratum"]) for candidate in plan["items"]
    ]
    reviews[0]["provenance"]["agent"] = plan["items"][0]["original_agent"]
    with pytest.raises(QualityAuditError, match="differ from original"):
        seal_cycle_quality_audit_result(
            plan_path=created["plan_path"],
            reviews=reviews,
            policy=_policy(),
            completed_at=NOW + dt.timedelta(minutes=1),
        )

    reviews = [
        _cycle_review(candidate, disposition=candidate["stratum"]) for candidate in plan["items"]
    ]
    reviews[1]["provenance"]["agent"] = reviews[0]["provenance"]["agent"]
    with pytest.raises(QualityAuditError, match="multiple companies"):
        seal_cycle_quality_audit_result(
            plan_path=created["plan_path"],
            reviews=reviews,
            policy=_policy(),
            completed_at=NOW + dt.timedelta(minutes=1),
        )


def test_major_disagreement_reopens_and_over_threshold_requests_expansion(tmp_path: Path):
    from trading_os.research_assets.quality_audit import (
        seal_cycle_quality_audit_plan,
        seal_cycle_quality_audit_result,
    )

    created = seal_cycle_quality_audit_plan(
        output_dir=tmp_path / "cycle-quality",
        audit_id="cycle-audit-002",
        cycle_id="cycle-002",
        cohort_path="coverage/cn-a/triage/cycle-002/cohort.json",
        cohort_sha256="c" * 64,
        records=[_cycle_record(index) for index in range(1, 21)],
        policy=_policy(),
        created_at=NOW,
    )
    plan = _load_plan(created["plan_path"])
    reviews = []
    for index, item in enumerate(plan["items"]):
        reviews.append(
            _cycle_review(
                item,
                disposition="triage_candidate" if index == 0 else "catalog",
                severity="major" if index == 0 else None,
            )
        )
    result = seal_cycle_quality_audit_result(
        plan_path=created["plan_path"],
        reviews=reviews,
        policy=_policy(),
        completed_at=NOW + dt.timedelta(minutes=1),
    )
    payload = json.loads(Path(result["result_path"]).read_text(encoding="utf-8"))
    assert result["status"] == "reopen_required"
    assert result["reopen_required"] is True
    assert result["expansion_required"] is True
    assert payload["major_disagreement_count"] == 1
    assert len(payload["expansion_symbols"]["catalog"]) == 2
    assert payload["reopen_symbols"] == [plan["items"][0]["symbol"]]


def test_continuation_expansion_uses_cumulative_sample_without_repeats(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.quality_audit import (
        seal_cycle_quality_audit_plan,
        seal_cycle_quality_audit_result,
    )

    records = [_cycle_record(index) for index in range(1, 13)]
    initial = seal_cycle_quality_audit_plan(
        output_dir=tmp_path / "cycle-quality-initial",
        audit_id="cycle-audit-cumulative-initial",
        cycle_id="cycle-cumulative",
        cohort_path="coverage/cn-a/triage/cycle-cumulative/cohort.json",
        cohort_sha256="d" * 64,
        records=records,
        policy=_policy(),
        created_at=NOW,
    )
    initial_plan = _load_plan(initial["plan_path"])
    initial_symbols = [item["symbol"] for item in initial_plan["items"]]
    assert len(initial_symbols) == 2

    continuation = seal_cycle_quality_audit_plan(
        output_dir=tmp_path / "cycle-quality-continuation",
        audit_id="cycle-audit-cumulative-round-0002",
        cycle_id="cycle-cumulative",
        cohort_path="coverage/cn-a/triage/cycle-cumulative/cohort.json",
        cohort_sha256="d" * 64,
        records=records,
        policy=_policy(),
        created_at=NOW + dt.timedelta(minutes=1),
        already_sampled_symbols={"catalog": initial_symbols},
    )
    continuation_plan = _load_plan(continuation["plan_path"])
    continuation_symbols = [item["symbol"] for item in continuation_plan["items"]]
    assert len(continuation_symbols) == 2
    assert set(continuation_symbols).isdisjoint(initial_symbols)

    reviews = [
        _cycle_review(
            item,
            disposition="triage_candidate" if index == 0 else "catalog",
        )
        for index, item in enumerate(continuation_plan["items"])
    ]
    for review in reviews:
        review["provenance"]["generated_at"] = (
            NOW + dt.timedelta(minutes=2)
        ).isoformat()
    result = seal_cycle_quality_audit_result(
        plan_path=continuation["plan_path"],
        reviews=reviews,
        policy=_policy(),
        completed_at=NOW + dt.timedelta(minutes=2),
    )
    payload = json.loads(Path(result["result_path"]).read_text(encoding="utf-8"))
    next_symbols = payload["expansion_symbols"]["catalog"]
    assert len(next_symbols) == 4
    assert set(next_symbols).isdisjoint(initial_symbols)
    assert set(next_symbols).isdisjoint(continuation_symbols)


def test_full_census_redo_does_not_request_another_redo(tmp_path: Path) -> None:
    from trading_os.research_assets.quality_audit import (
        seal_cycle_quality_audit_plan,
        seal_cycle_quality_audit_result,
    )

    created = seal_cycle_quality_audit_plan(
        output_dir=tmp_path / "cycle-quality-full-redo",
        audit_id="cycle-audit-full-redo",
        cycle_id="cycle-full-redo",
        cohort_path="coverage/cn-a/triage/cycle-full-redo/cohort.json",
        cohort_sha256="e" * 64,
        records=[_cycle_record(index) for index in range(1, 4)],
        policy=_policy(),
        created_at=NOW,
        force_full_census_strata=["catalog"],
    )
    plan = _load_plan(created["plan_path"])
    reviews = [
        _cycle_review(item, disposition="triage_candidate")
        for item in plan["items"]
    ]
    result = seal_cycle_quality_audit_result(
        plan_path=created["plan_path"],
        reviews=reviews,
        policy=_policy(),
        completed_at=NOW + dt.timedelta(minutes=1),
    )
    payload = json.loads(Path(result["result_path"]).read_text(encoding="utf-8"))
    assert payload["status"] == "reopen_required"
    assert payload["reopen_symbols"] == [
        "CN:000001",
        "CN:000002",
        "CN:000003",
    ]
    assert payload["redo_required"] is False
    assert payload["redo_strata"] == []
    assert payload["expansion_required"] is False


def test_routing_error_semantics_do_not_treat_issuer_risk_as_audit_error(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.quality_audit import (
        seal_cycle_quality_audit_plan,
        seal_cycle_quality_audit_result,
    )

    records = [
        _cycle_record(index, "conditional_stop") for index in range(1, 3)
    ]
    created = seal_cycle_quality_audit_plan(
        output_dir=tmp_path / "cycle-quality",
        audit_id="cycle-audit-routing-semantics",
        cycle_id="cycle-routing-semantics",
        cohort_path="coverage/cn-a/triage/cycle-routing-semantics/cohort.json",
        cohort_sha256="9" * 64,
        records=records,
        policy=_policy(),
        created_at=NOW,
    )
    plan = _load_plan(created["plan_path"])
    reviews = [
        _cycle_review(item, disposition="conditional_stop", severity="major")
        for item in plan["items"]
    ]
    result = seal_cycle_quality_audit_result(
        plan_path=created["plan_path"],
        reviews=reviews,
        policy=_policy(),
        completed_at=NOW + dt.timedelta(minutes=1),
    )
    payload = json.loads(Path(result["result_path"]).read_text(encoding="utf-8"))
    assert payload["error_semantics"] == "routing_disagreement_v1"
    assert payload["material_error_count"] == 0
    assert payload["major_disagreement_count"] == 0
    assert payload["redo_required"] is False
    assert payload["status"] == "passed"


def test_forced_full_census_plan_is_stable_and_explicit(tmp_path: Path) -> None:
    from trading_os.research_assets.quality_audit import seal_cycle_quality_audit_plan

    records = [_cycle_record(index, "conditional_stop") for index in range(1, 5)]
    created = seal_cycle_quality_audit_plan(
        output_dir=tmp_path / "cycle-quality",
        audit_id="cycle-audit-full-census",
        cycle_id="cycle-full-census",
        cohort_path="coverage/cn-a/triage/cycle-full-census/cohort.json",
        cohort_sha256="8" * 64,
        records=records,
        policy=_policy(),
        created_at=NOW,
        already_sampled_symbols={
            "conditional_stop": [record["symbol"] for record in records]
        },
        force_full_census_strata=["conditional_stop"],
    )
    plan = _load_plan(created["plan_path"])
    row = next(
        value for value in plan["strata"] if value["stratum"] == "conditional_stop"
    )
    assert row["full_census_redo"] is True
    assert row["already_sampled_count"] == 0
    assert [item["symbol"] for item in plan["items"]] == row["ranked_symbols"]


def test_error_rate_equal_to_threshold_does_not_expand(tmp_path: Path):
    from trading_os.research_assets.quality_audit import (
        seal_cycle_quality_audit_plan,
        seal_cycle_quality_audit_result,
    )

    records = [_cycle_record(index, "price_watch") for index in range(1, 41)]
    created = seal_cycle_quality_audit_plan(
        output_dir=tmp_path / "cycle-quality",
        audit_id="cycle-audit-003",
        cycle_id="cycle-003",
        cohort_path="coverage/cn-a/triage/cycle-003/cohort.json",
        cohort_sha256="d" * 64,
        records=records,
        policy=_policy(),
        created_at=NOW,
    )
    plan = _load_plan(created["plan_path"])
    assert len(plan["items"]) == 10
    reviews = []
    for index, item in enumerate(plan["items"]):
        reviews.append(
            _cycle_review(
                item,
                disposition="catalog" if index == 0 else "price_watch",
            )
        )
    result = seal_cycle_quality_audit_result(
        plan_path=created["plan_path"],
        reviews=reviews,
        policy=_policy(),
        completed_at=NOW + dt.timedelta(minutes=1),
    )
    payload = json.loads(Path(result["result_path"]).read_text(encoding="utf-8"))
    price_stat = next(row for row in payload["strata"] if row["stratum"] == "price_watch")
    assert price_stat["observed_material_error_rate"] == pytest.approx(0.1)
    assert price_stat["over_threshold"] is False
    assert result["expansion_required"] is False
    assert result["status"] == "passed"


def test_plan_or_packet_tampering_is_rejected(tmp_path: Path):
    from trading_os.research_assets.quality_audit import (
        QualityAuditError,
        quality_audit_status,
        seal_cycle_quality_audit_plan,
        seal_cycle_quality_audit_result,
    )

    created = seal_cycle_quality_audit_plan(
        output_dir=tmp_path / "cycle-quality",
        audit_id="cycle-audit-004",
        cycle_id="cycle-004",
        cohort_path="coverage/cn-a/triage/cycle-004/cohort.json",
        cohort_sha256="e" * 64,
        records=[_cycle_record(index) for index in range(1, 21)],
        policy=_policy(),
        created_at=NOW,
    )
    plan = _load_plan(created["plan_path"])
    reviews = [_cycle_review(item, disposition=item["stratum"]) for item in plan["items"]]
    packet_path = Path(created["plan_path"]).parent / plan["items"][0]["facts_packet_path"]
    packet_path.write_bytes(packet_path.read_bytes() + b" ")

    with pytest.raises(QualityAuditError, match="facts packet"):
        seal_cycle_quality_audit_result(
            plan_path=created["plan_path"],
            reviews=reviews,
            policy=_policy(),
            completed_at=NOW + dt.timedelta(minutes=1),
        )

    Path(created["plan_path"]).write_bytes(Path(created["plan_path"]).read_bytes() + b" ")
    with pytest.raises(QualityAuditError, match="artifact is invalid"):
        quality_audit_status(created["plan_path"])

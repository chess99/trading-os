from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest

from trading_os.research_assets.quality_workflow import (
    QualityWorkflowError,
    cycle_quality_gate_status,
    cycle_quality_status,
    load_quality_policy_snapshot,
    materialize_cycle_quality_reopens,
    prepare_cycle_quality_audit,
    prepare_cycle_quality_audit_continuation,
    prepare_cycle_quality_correction,
    prepare_scope_identity_quality_audit,
    record_cycle_quality_audit_continuation,
    record_cycle_quality_correction_resolution,
    scope_quality_status,
    seal_quality_policy_snapshot,
)
from trading_os.research_assets.scope_workflow import freeze_all_a_scope
from trading_os.research_assets.sealing import canonical_json_bytes, seal_json, verify_sealed

NOW = dt.datetime.fromisoformat("2026-07-30T10:00:00+08:00")
CUTOFF = dt.datetime.fromisoformat("2026-07-30T09:00:00+08:00")
RUN = "2026-07-30-quality-test"
CYCLE = "2026-07-30-quality-cycle"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _policy() -> dict:
    return {
        "schema_version": 2,
        "policy_id": "triage-quality-audit.test",
        "version": "1.0.0",
        "effective_at": "2026-07-30T00:00:00+08:00",
        "kind": "triage_quality_audit",
        "payload": {
            "sampling_algorithm": "sha256_stratified_v1",
            "stable_seed": "quality-workflow-test",
            "strata": {
                "hard_exclusion": {
                    "initial_sample_rate": 1.0,
                    "minimum_sample_count": 0,
                    "material_error_rate_threshold": 0.0,
                },
                "catalog": {
                    "initial_sample_rate": 0.1,
                    "minimum_sample_count": 2,
                    "material_error_rate_threshold": 0.1,
                },
                "price_watch": {
                    "initial_sample_rate": 0.25,
                    "minimum_sample_count": 2,
                    "material_error_rate_threshold": 0.1,
                },
                "conditional_stop": {
                    "initial_sample_rate": 1.0,
                    "minimum_sample_count": 0,
                    "material_error_rate_threshold": 0.0,
                },
                "reassign_or_stop": {
                    "initial_sample_rate": 1.0,
                    "minimum_sample_count": 0,
                    "material_error_rate_threshold": 0.0,
                },
            },
            "expansion": {
                "rule": "double_cumulative_sample_v1",
                "multiplier": 2,
                "minimum_increment": 1,
                "on_full_census_over_threshold": "redo_entire_stratum",
            },
            "independence": {
                "reviewer_must_differ_from_original_agent": True,
                "one_active_company_per_reviewer": True,
            },
        },
    }


def _company(
    symbol: str,
    *,
    security_type: str = "common_stock",
    listing_status: str = "listed",
) -> dict:
    ticker = symbol.split(":", 1)[1]
    return {
        "symbol": symbol,
        "ticker": ticker,
        "name": f"测试公司{ticker}",
        "exchange": "SZSE",
        "security_type": security_type,
        "listing_status": listing_status,
        "as_of": "2026-07-30",
        "fetched_at": "2026-07-30T08:30:00+08:00",
        "source": "https://example.com/universe",
    }


def _screen(company: dict, decision: str = "catalog") -> dict:
    return {
        "symbol": company["symbol"],
        "ticker": company["ticker"],
        "name": company["name"],
        "as_of": "2026-07-30",
        "decision": decision,
        "priority": None,
        "reason": "用于测试冻结范围和身份复核。",
        "evidence": ["source:https://example.com/security-identity"],
        "next_action": "等待正式流程。",
    }


def _repo(
    tmp_path: Path,
    *,
    all_eligible: bool = False,
    company_count: int = 5,
) -> tuple[Path, Path]:
    repository = tmp_path / "repo"
    root = repository / "coverage" / "cn-a"
    symbols = [f"CN:{index:06d}" for index in range(1, company_count + 1)]
    companies = [_company(symbol) for symbol in symbols]
    if not all_eligible:
        companies[1] = _company(symbols[1], security_type="fund")
        companies[2] = _company(symbols[2], listing_status="delisted")
    screening = [_screen(company) for company in companies]
    queue = [
        {
            "symbol": company["symbol"],
            "name": company["name"],
            "task_type": "initial_research",
            "status": "requires_rebaseline",
        }
        for company in companies
    ]
    _write_jsonl(root / "companies.jsonl", companies)
    _write_jsonl(root / "screening.jsonl", screening)
    _write_jsonl(root / "research_queue.jsonl", queue)
    _write_jsonl(root / "runs.jsonl", [])
    policy_path = repository / "policies" / "triage-quality-audit.json"
    _write_json(policy_path, _policy())
    freeze_all_a_scope(
        root=root,
        run_id=RUN,
        scope_cutoff=CUTOFF,
        frozen_at=CUTOFF,
        mode="auto",
    )
    # This module verifies the legacy rapid-triage audit chain. New scope
    # production materializes manager_screen, so make the legacy fixture
    # explicit instead of weakening the production intake guard.
    queue_path = root / "research_queue.jsonl"
    legacy_queue = [
        json.loads(line)
        for line in queue_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for item in legacy_queue:
        if item.get("status") != "requires_rebaseline":
            continue
        item.update(
            {
                "task_type": "rapid_triage",
                "effort_budget_hours": 0.25,
                "preceding_stage": "scope_to_queue_intake",
                "stop_conditions": ["legacy quality-workflow fixture"],
            }
        )
    _write_jsonl(queue_path, legacy_queue)
    return root, policy_path


def _package(
    symbol: str,
    *,
    disposition: str,
    cycle_id: str = CYCLE,
    package_symbol: str | None = None,
) -> dict:
    ticker = symbol.split(":", 1)[1]
    values = {
        "business_legibility": "clear",
        "survival_status": "pass",
        "governance_status": "acceptable",
        "valuation_signal": "possible",
        "research_value": "medium",
    }
    if disposition == "catalog":
        values["research_value"] = "low"
    elif disposition == "price_watch":
        values["valuation_signal"] = "unattractive"
    elif disposition == "conditional_stop":
        values["survival_status"] = "fail"
    elif disposition == "reassign_or_stop":
        values["business_legibility"] = "opaque"
    return {
        "schema_version": 2,
        "cycle_id": cycle_id,
        "symbol": package_symbol or symbol,
        "company_name": f"测试公司{ticker}",
        "as_of": "2026-07-30",
        "information_cutoff": "2026-07-30T09:00:00+08:00",
        "price_as_of": "2026-07-30T08:55:00+08:00",
        "price_source_id": "quote",
        "current_price": 10.0,
        "review_mode": "baseline_recheck",
        "prior_research_path": None,
        "trigger_context": "全覆盖基线复核。",
        "business_summary": "已核对主营业务和盈利来源。",
        "change_summary": "未发现足以跳过复核的重大变化。",
        "normalized_earnings_view": "正常化盈利仍需后续核验。",
        "expectations_view": "当前价格隐含温和增长。",
        "counterevidence": ["现金流仍需核验", "周期位置不确定"],
        **values,
        "earnings_legibility": "plausible",
        "decisive_question": "下一小时能否核清正常化所有者收益？",
        "reason_codes": ["latest_filing_and_price_checked"],
        "revisit_triggers": [
            {
                "trigger_id": "routine-refresh",
                "type": "ttl",
                "condition": {"days": 90},
                "reason": "九十天后重新快速复核。",
            }
        ],
        "sources": [
            {
                "source_id": "filing",
                "tier": "S1",
                "title": "最新定期报告",
                "accessed_at": "2026-07-30T08:30:00+08:00",
                "url": "https://example.com/filing",
                "local_path": None,
                "supports": ["business", "earnings", "governance"],
            },
            {
                "source_id": "quote",
                "tier": "S2",
                "title": "最新行情",
                "accessed_at": "2026-07-30T08:55:00+08:00",
                "url": "https://example.com/quote",
                "local_path": None,
                "supports": ["current_price"],
            },
        ],
        "provenance": {
            "agent": f"agent-{ticker}",
            "model": "test-model",
            "tools": ["repository", "browser"],
            "generated_at": "2026-07-30T09:15:00+08:00",
        },
    }


def _cycle(
    root: Path,
    *,
    schema_version: int = 2,
    parent_sha_override: str | None = None,
    package_overrides: dict[str, dict] | None = None,
    dispositions: list[str] | None = None,
) -> None:
    repository = root.parent.parent
    scope_path = root / "scopes" / RUN / "manifest.json"
    intake_path = root / "scopes" / RUN / "baseline-intake.json"
    scope_seal = verify_sealed(scope_path)
    intake_seal = verify_sealed(intake_path)
    if dispositions is None:
        dispositions = [
            "catalog",
            "price_watch",
            "conditional_stop",
            "reassign_or_stop",
            "triage_candidate",
        ]
    symbols = [f"CN:{index:06d}" for index in range(1, len(dispositions) + 1)]
    cohort = {
        "schema_version": schema_version,
        "cycle_id": CYCLE,
        "frozen_at": "2026-07-30T09:20:00+08:00",
        "selection_basis": "stable symbol order only; no investment ranking",
        "request": {
            "mode": "explicit_symbols",
            "queue_status": "requires_rebaseline",
            "limit": len(symbols),
            "after_symbol": None,
            "symbols": symbols,
        },
        "cohort_count": len(symbols),
        "members": [
            {
                "ordinal": index,
                "symbol": symbol,
                "name": f"测试公司{symbol.split(':')[1]}",
                "intake_reason_codes": ["missing_current_rapid_triage_terminal"],
                "prior_task_type": "rapid_triage",
                "prior_status": "requires_rebaseline",
                "prior_reason": "冻结 baseline intake。",
                "prior_result_path": None,
            }
            for index, symbol in enumerate(symbols, 1)
        ],
        "portfolio_action": None,
    }
    if schema_version == 2:
        cohort["parent_scope"] = {
            "run_id": RUN,
            "scope_cutoff": CUTOFF.isoformat(),
            "manifest_path": scope_path.relative_to(repository).as_posix(),
            "manifest_sha256": parent_sha_override or scope_seal.sha256,
            "baseline_intake_path": intake_path.relative_to(repository).as_posix(),
            "baseline_intake_sha256": intake_seal.sha256,
        }
    cohort_path = root / "triage" / CYCLE / "cohort.json"
    seal_json(
        cohort_path,
        cohort,
        artifact_type="rapid_triage_cohort",
        sealed_at=dt.datetime.fromisoformat("2026-07-30T09:20:00+08:00"),
    )
    for symbol, disposition in zip(symbols, dispositions, strict=True):
        package = _package(symbol, disposition=disposition)
        package.update((package_overrides or {}).get(symbol, {}))
        path = (
            root
            / "triage"
            / CYCLE
            / symbol.split(":", 1)[1]
            / "20260730T093000+0800.triage.json"
        )
        seal_json(
            path,
            package,
            artifact_type="rapid_triage_package",
            sealed_at=NOW,
        )


def _quality_review(
    item: dict,
    *,
    disposition: str | None = None,
    minute: int = 1,
) -> dict:
    return {
        "schema_version": 1,
        "audit_item_id": item["audit_item_id"],
        "facts_packet_sha256": item["facts_packet_sha256"],
        "symbol": item["symbol"],
        "recommended_disposition": disposition or item["stratum"],
        "decisive_question": "独立事实是否支持当前研究路由？",
        "findings": [],
        "provenance": {
            "agent": f"quality-{item['symbol'].replace(':', '-')}-m{minute}",
            "model": "test-model",
            "tools": ["source-reader"],
            "generated_at": (NOW + dt.timedelta(minutes=minute)).isoformat(),
        },
    }


def test_policy_snapshot_binds_raw_and_normalized_sha_and_rejects_tamper(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    policy_path = repository / "policies" / "quality.json"
    _write_json(policy_path, _policy())
    output = repository / "coverage" / "cn-a" / "quality-test"
    result = seal_quality_policy_snapshot(
        output_dir=output,
        policy_path=policy_path,
        repository_root=repository,
        subject_kind="scope_identity",
        subject_id=RUN,
        sealed_at=NOW,
    )
    payload = load_quality_policy_snapshot(
        snapshot_path=result["snapshot_path"],
        expected_subject_kind="scope_identity",
        expected_subject_id=RUN,
    )
    assert payload["policy_path"] == "policies/quality.json"
    assert payload["policy_file_sha256"] == hashlib.sha256(policy_path.read_bytes()).hexdigest()
    assert verify_sealed(result["snapshot_path"]).artifact_type == (
        "triage_quality_audit_policy_snapshot"
    )
    Path(result["snapshot_path"]).write_bytes(b"{}")
    with pytest.raises(QualityWorkflowError, match="not validly sealed"):
        load_quality_policy_snapshot(snapshot_path=result["snapshot_path"])


def test_policy_snapshot_rejects_non_dedicated_policy_kind(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    policy = _policy()
    policy["kind"] = "research_allocation"
    path = repository / "policies" / "quality.json"
    _write_json(path, policy)
    with pytest.raises(QualityWorkflowError, match="quality policy is invalid"):
        seal_quality_policy_snapshot(
            output_dir=repository / "quality",
            policy_path=path,
            repository_root=repository,
            subject_kind="scope_identity",
            subject_id=RUN,
            sealed_at=NOW,
        )


def test_scope_adapter_audits_all_hard_exclusions_with_real_identity_facts(
    tmp_path: Path,
) -> None:
    root, policy_path = _repo(tmp_path)
    status = prepare_scope_identity_quality_audit(
        root=root,
        run_id=RUN,
        policy_path=policy_path,
        created_at=NOW,
    )
    assert status["status"] == "pending_reviews"
    assert status["population_count"] == 2
    assert status["sampled_count"] == 2
    plan_path = Path(status["canonical_paths"]["plan"])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert [item["symbol"] for item in plan["items"]] == ["CN:000002", "CN:000003"]
    packet_path = plan_path.parent / plan["items"][0]["facts_packet_path"]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assert packet["identity_facts"]["company_identity"]["security_type"] == "fund"
    assert packet["identity_facts"]["scope_member"]["partition"] == "hard_excluded"
    assert packet["sources"][0]["local_path"] == "coverage/cn-a/companies.jsonl"
    assert "original_scope_classification" in packet["blind_contract"]["omitted_fields"]
    assert status["canonical_paths"]["binding"].endswith("quality\\identity\\binding.json")


def test_scope_adapter_rejects_source_or_manifest_tampering(tmp_path: Path) -> None:
    root, policy_path = _repo(tmp_path)
    companies_path = root / "companies.jsonl"
    companies_path.write_bytes(companies_path.read_bytes() + b"\n")
    with pytest.raises(QualityWorkflowError, match="universe source sha256"):
        prepare_scope_identity_quality_audit(
            root=root,
            run_id=RUN,
            policy_path=policy_path,
            created_at=NOW,
        )

    root2, policy_path2 = _repo(tmp_path / "second")
    manifest_path = root2 / "scopes" / RUN / "manifest.json"
    manifest_path.write_bytes(b"{}")
    with pytest.raises(QualityWorkflowError, match="not validly sealed"):
        prepare_scope_identity_quality_audit(
            root=root2,
            run_id=RUN,
            policy_path=policy_path2,
            created_at=NOW,
        )


def test_cycle_adapter_requires_v2_parent_binding_and_verified_packages(
    tmp_path: Path,
) -> None:
    root, policy_path = _repo(tmp_path, all_eligible=True)
    _cycle(root)
    status = prepare_cycle_quality_audit(
        root=root,
        cycle_id=CYCLE,
        policy_path=policy_path,
        created_at=NOW,
    )
    assert status["status"] == "pending_reviews"
    assert status["population_count"] == 4
    plan = json.loads(Path(status["canonical_paths"]["plan"]).read_text(encoding="utf-8"))
    assert {row["stratum"] for row in plan["population"]} == {
        "catalog",
        "price_watch",
        "conditional_stop",
        "reassign_or_stop",
    }
    assert "CN:000005" not in {row["symbol"] for row in plan["population"]}
    assert status["canonical_paths"]["plan"].endswith("quality\\plan.json")


@pytest.mark.parametrize("failure", ["legacy", "parent", "package_binding", "package_tamper"])
def test_cycle_adapter_rejects_nonproduction_proof(tmp_path: Path, failure: str) -> None:
    root, policy_path = _repo(tmp_path, all_eligible=True)
    if failure == "legacy":
        _cycle(root, schema_version=1)
        match = "legacy rapid-triage cohort"
    elif failure == "parent":
        _cycle(root, parent_sha_override="0" * 64)
        match = "parent scope binding"
    elif failure == "package_binding":
        _cycle(root, package_overrides={"CN:000001": {"cycle_id": "wrong-cycle"}})
        match = "package binding"
    else:
        _cycle(root)
        package_path = next((root / "triage" / CYCLE / "000001").glob("*.triage.json"))
        package_path.write_bytes(b"{}")
        match = "not validly sealed"
    with pytest.raises(QualityWorkflowError, match=match):
        prepare_cycle_quality_audit(
            root=root,
            cycle_id=CYCLE,
            policy_path=policy_path,
            created_at=NOW,
        )


def test_status_rejects_packet_tamper_and_wrong_result_plan_binding(tmp_path: Path) -> None:
    root, policy_path = _repo(tmp_path)
    status = prepare_scope_identity_quality_audit(
        root=root,
        run_id=RUN,
        policy_path=policy_path,
        created_at=NOW,
    )
    plan = json.loads(Path(status["canonical_paths"]["plan"]).read_text(encoding="utf-8"))
    packet_path = Path(status["canonical_paths"]["plan"]).parent / plan["items"][0][
        "facts_packet_path"
    ]
    original = packet_path.read_bytes()
    packet_path.write_bytes(b"{}")
    with pytest.raises(QualityWorkflowError, match="not validly sealed"):
        scope_quality_status(root=root, run_id=RUN)
    packet_path.write_bytes(original)

    result_path = Path(status["canonical_paths"]["result"])
    fake_result = {
        "schema_version": 1,
        "audit_id": f"{RUN}:identity",
        "subject_kind": "scope_identity",
        "plan_sha256": "0" * 64,
        "status": "passed",
        "reopen_required": False,
    }
    seal_json(
        result_path,
        fake_result,
        artifact_type="scope_identity_audit_result",
        sealed_at=NOW,
    )
    with pytest.raises(QualityWorkflowError, match="does not bind the plan"):
        scope_quality_status(root=root, run_id=RUN)


def test_cycle_status_rejects_binding_tamper(tmp_path: Path) -> None:
    root, policy_path = _repo(tmp_path, all_eligible=True)
    _cycle(root)
    status = prepare_cycle_quality_audit(
        root=root,
        cycle_id=CYCLE,
        policy_path=policy_path,
        created_at=NOW,
    )
    binding_path = Path(status["canonical_paths"]["binding"])
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding["plan"]["sha256"] = "0" * 64
    binding_path.write_bytes(canonical_json_bytes(binding))
    with pytest.raises(QualityWorkflowError, match="not validly sealed"):
        cycle_quality_status(root=root, cycle_id=CYCLE)


def test_schema_v3_cohort_binds_passed_scope_quality_and_blocks_compare_until_cycle_audit(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.quality_audit import (
        seal_scope_identity_audit_result,
    )
    from trading_os.research_assets.research_allocation import ResearchAllocationError
    from trading_os.research_assets.triage_cohort import freeze_rapid_triage_cohort
    from trading_os.research_assets.triage_workflow import (
        build_rapid_triage_comparison_packet,
    )

    root, policy_path = _repo(tmp_path, all_eligible=True)
    quality = prepare_scope_identity_quality_audit(
        root=root,
        run_id=RUN,
        policy_path=policy_path,
        created_at=NOW,
    )
    seal_scope_identity_audit_result(
        plan_path=quality["canonical_paths"]["plan"],
        reviews=[],
        completed_at=NOW + dt.timedelta(minutes=1),
    )
    quality = scope_quality_status(root=root, run_id=RUN)
    assert quality["status"] == "passed"
    symbols = [f"CN:00000{index}" for index in range(1, 6)]
    cohort = freeze_rapid_triage_cohort(
        root=root,
        cycle_id=CYCLE,
        frozen_at=NOW + dt.timedelta(minutes=2),
        queue_status="requires_rebaseline",
        symbols=symbols,
        scope_run_id=RUN,
        quality_policy_snapshot_path=quality["canonical_paths"]["policy_snapshot"],
        scope_identity_audit_result_path=quality["canonical_paths"]["result"],
    )
    payload = json.loads(
        (root.parent.parent / cohort["cohort_path"]).read_text(encoding="utf-8")
    )
    assert payload["schema_version"] == 3
    assert payload["quality_contract"]["scope_identity_result_sha256"] == verify_sealed(
        quality["canonical_paths"]["result"]
    ).sha256
    with pytest.raises(ResearchAllocationError, match="quality audit is missing"):
        build_rapid_triage_comparison_packet(
            root=root,
            cycle_id=CYCLE,
            created_at=NOW + dt.timedelta(minutes=3),
        )


def test_cycle_quality_continuation_binds_expansion_and_full_census_redo(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.quality_audit import (
        seal_cycle_quality_audit_result,
    )

    dispositions = ["price_watch"] * 8 + ["conditional_stop"] * 2
    root, policy_path = _repo(
        tmp_path,
        all_eligible=True,
        company_count=len(dispositions),
    )
    _cycle(root, dispositions=dispositions)
    initial = prepare_cycle_quality_audit(
        root=root,
        cycle_id=CYCLE,
        policy_path=policy_path,
        created_at=NOW,
    )
    initial_plan = json.loads(
        Path(initial["canonical_paths"]["plan"]).read_text(encoding="utf-8")
    )
    reviews = [_quality_review(item) for item in initial_plan["items"]]
    price_indexes = [
        index
        for index, item in enumerate(initial_plan["items"])
        if item["stratum"] == "price_watch"
    ]
    conditional_indexes = [
        index
        for index, item in enumerate(initial_plan["items"])
        if item["stratum"] == "conditional_stop"
    ]
    reviews[price_indexes[0]]["recommended_disposition"] = "catalog"
    reviews[conditional_indexes[0]]["recommended_disposition"] = "price_watch"
    seal_cycle_quality_audit_result(
        plan_path=initial["canonical_paths"]["plan"],
        reviews=reviews,
        policy=_policy(),
        completed_at=NOW + dt.timedelta(minutes=2),
    )

    continuation = prepare_cycle_quality_audit_continuation(
        root=root,
        cycle_id=CYCLE,
        created_at=NOW + dt.timedelta(minutes=3),
    )
    assert continuation["round_number"] == 2
    assert continuation["status"] == "pending_reviews"
    assert continuation["sampled_count"] == 4
    plan_path = Path(continuation["canonical_paths"]["plan"])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["error_semantics"] == "routing_disagreement_v1"
    assert sum(item["stratum"] == "price_watch" for item in plan["items"]) == 2
    assert sum(item["stratum"] == "conditional_stop" for item in plan["items"]) == 2
    conditional = next(
        row for row in plan["strata"] if row["stratum"] == "conditional_stop"
    )
    assert conditional["full_census_redo"] is True
    binding = json.loads(
        Path(continuation["canonical_paths"]["binding"]).read_text(encoding="utf-8")
    )
    assert binding["schema_version"] == 2
    assert binding["predecessor_result"]["sha256"] == verify_sealed(
        initial["canonical_paths"]["result"]
    ).sha256

    repeated = prepare_cycle_quality_audit_continuation(
        root=root,
        cycle_id=CYCLE,
        created_at=NOW + dt.timedelta(minutes=4),
    )
    assert repeated["idempotent"] is True
    assert repeated["round_number"] == 2
    recorded = record_cycle_quality_audit_continuation(
        root=root,
        cycle_id=CYCLE,
        reviews=[_quality_review(item, minute=4) for item in plan["items"]],
        completed_at=NOW + dt.timedelta(minutes=5),
    )
    assert recorded["status"] == "passed"
    materialized = materialize_cycle_quality_reopens(root=root, cycle_id=CYCLE)
    assert materialized["result_count"] == 2
    assert materialized["reopen_count"] == 1
    assert materialized["symbols"] == [
        initial_plan["items"][conditional_indexes[0]]["symbol"]
    ]
    with pytest.raises(QualityWorkflowError, match="does not require expansion"):
        prepare_cycle_quality_audit_continuation(
            root=root,
            cycle_id=CYCLE,
            created_at=NOW + dt.timedelta(minutes=6),
        )


def test_quality_correction_cohort_resolves_reopens_with_new_packages(
    tmp_path: Path,
) -> None:
    from trading_os.research_assets.quality_audit import (
        seal_cycle_quality_audit_result,
        seal_scope_identity_audit_result,
    )
    from trading_os.research_assets.triage_cohort import freeze_rapid_triage_cohort

    correction_cycle = f"{CYCLE}-correction-001"
    root, policy_path = _repo(tmp_path, all_eligible=True, company_count=4)
    policy = _policy()
    policy["payload"]["strata"]["price_watch"][
        "material_error_rate_threshold"
    ] = 1.0
    _write_json(policy_path, policy)
    scope_quality = prepare_scope_identity_quality_audit(
        root=root,
        run_id=RUN,
        policy_path=policy_path,
        created_at=NOW,
    )
    seal_scope_identity_audit_result(
        plan_path=scope_quality["canonical_paths"]["plan"],
        reviews=[],
        completed_at=NOW + dt.timedelta(minutes=1),
    )
    scope_quality = scope_quality_status(root=root, run_id=RUN)
    symbols = [f"CN:{index:06d}" for index in range(1, 5)]
    freeze_rapid_triage_cohort(
        root=root,
        cycle_id=CYCLE,
        frozen_at=NOW + dt.timedelta(minutes=2),
        queue_status="requires_rebaseline",
        symbols=symbols,
        scope_run_id=RUN,
        quality_policy_snapshot_path=scope_quality["canonical_paths"]["policy_snapshot"],
        scope_identity_audit_result_path=scope_quality["canonical_paths"]["result"],
    )
    for symbol in symbols:
        path = (
            root
            / "triage"
            / CYCLE
            / symbol.split(":", 1)[1]
            / "20260730T100300+0800.triage.json"
        )
        seal_json(
            path,
            _package(symbol, disposition="price_watch"),
            artifact_type="rapid_triage_package",
            sealed_at=NOW + dt.timedelta(minutes=3),
        )
    source_quality = prepare_cycle_quality_audit(
        root=root,
        cycle_id=CYCLE,
        policy_path=policy_path,
        created_at=NOW + dt.timedelta(minutes=4),
    )
    source_plan = json.loads(
        Path(source_quality["canonical_paths"]["plan"]).read_text(encoding="utf-8")
    )
    reviews = [_quality_review(item, minute=5) for item in source_plan["items"]]
    reviews[0]["recommended_disposition"] = "triage_candidate"
    seal_cycle_quality_audit_result(
        plan_path=source_quality["canonical_paths"]["plan"],
        reviews=reviews,
        policy=policy,
        completed_at=NOW + dt.timedelta(minutes=6),
    )
    materialized = materialize_cycle_quality_reopens(root=root, cycle_id=CYCLE)
    assert materialized["reopen_count"] == 1
    reopened_symbol = source_plan["items"][0]["symbol"]

    correction = prepare_cycle_quality_correction(
        root=root,
        cycle_id=CYCLE,
        correction_cycle_id=correction_cycle,
        created_at=NOW + dt.timedelta(minutes=7),
    )
    assert correction["symbols"] == [reopened_symbol]
    correction_package = _package(
        reopened_symbol,
        disposition="triage_candidate",
        cycle_id=correction_cycle,
    )
    correction_package["provenance"]["agent"] = "/root/correction-agent-000001"
    correction_path = (
        root
        / "triage"
        / correction_cycle
        / reopened_symbol.split(":", 1)[1]
        / "20260730T100800+0800.triage.json"
    )
    seal_json(
        correction_path,
        correction_package,
        artifact_type="rapid_triage_package",
        sealed_at=NOW + dt.timedelta(minutes=8),
    )
    correction_quality = prepare_cycle_quality_audit(
        root=root,
        cycle_id=correction_cycle,
        policy_path=policy_path,
        created_at=NOW + dt.timedelta(minutes=9),
    )
    correction_plan = json.loads(
        Path(correction_quality["canonical_paths"]["plan"]).read_text(encoding="utf-8")
    )
    assert correction_plan["sampled_count"] == 0
    seal_cycle_quality_audit_result(
        plan_path=correction_quality["canonical_paths"]["plan"],
        reviews=[],
        policy=policy,
        completed_at=NOW + dt.timedelta(minutes=10),
    )
    resolution = record_cycle_quality_correction_resolution(
        root=root,
        cycle_id=CYCLE,
        correction_cycle_id=correction_cycle,
        completed_at=NOW + dt.timedelta(minutes=11),
    )
    assert resolution["status"] == "passed"
    gate = cycle_quality_gate_status(root=root, cycle_id=CYCLE)
    assert gate["status"] == "passed"
    assert gate["resolved_packages"] == [
        {
            "symbol": reopened_symbol,
            "path": correction_path.relative_to(root.parent.parent).as_posix(),
            "sha256": verify_sealed(correction_path).sha256,
            "cycle_id": correction_cycle,
            "disposition": "triage_candidate",
            "research_agent": "/root/correction-agent-000001",
        }
    ]
    from trading_os.research_assets.triage_workflow import _completed_cohort_packages

    members = []
    for symbol in symbols:
        original_path = next((root / "triage" / CYCLE / symbol[-6:]).glob("*.triage.json"))
        members.append(
            {
                "symbol": symbol,
                "name": f"测试公司{symbol[-6:]}",
                "stage_history": [
                    {
                        "stage": "rapid_triage",
                        "status": "completed",
                        "cycle_id": CYCLE,
                        "result_path": original_path.relative_to(
                            root.parent.parent
                        ).as_posix(),
                    }
                ],
            }
        )
    packages = _completed_cohort_packages(
        members,
        cycle=CYCLE,
        repository_root=root.parent.parent,
        allow_unscoped_history=False,
        package_overrides={
            row["symbol"]: row for row in gate["resolved_packages"]
        },
    )
    corrected = next(package for item, package, _ in packages if item["symbol"] == reopened_symbol)
    assert corrected["cycle_id"] == correction_cycle

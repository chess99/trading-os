from __future__ import annotations

import copy
import datetime as dt
import json
import subprocess
from pathlib import Path

import pytest

from automation.scripts.build_review_prompt import (
    PromptBuildError,
    build_run_prompt,
    build_synthesis_prompt,
    render_prompt,
)
from automation.scripts.review_dispatch import (
    AgentResult,
    DraftDirectoryRunner,
    DispatchError,
    ReviewDispatcher,
    SubprocessRunner,
)
from tests.test_cli import T0, T1, _attach_research_claims
from tests.test_company_assets import write_company

NOW = dt.datetime.fromisoformat(T1)


def _assessment(
    *,
    accounting_failure: bool = False,
    risk_flag: str | None = None,
) -> dict[str, object]:
    risk_flags = {
        "governance_material_doubt": False,
        "cycle_position_uncertain": False,
        "permanent_loss_risk": False,
    }
    tier = "standard"
    if risk_flag is not None:
        risk_flags[risk_flag] = True
        tier = "severe" if risk_flag == "permanent_loss_risk" else "elevated"
    return {
        "confidence": "high",
        "safety_margin_tier": tier,
        "normalization": {
            "method": "five_year_mid_cycle",
            "years_used": 5,
            "single_quarter_annualized": False,
            "peak_profit_used": False,
            "normalized_profit": 100.0,
        },
        "accounting_checks": {
            "nonrecurring_items_handled": not accounting_failure,
            "net_debt_handled": True,
            "minority_interests_handled": True,
            "dilution_handled": True,
            "cash_flow_divergence_explained": True,
            "working_capital_anomalies_explained": True,
        },
        "bridges": {
            "earnings_quality_complete": True,
            "cash_flow_complete": True,
            "normalized_earnings_complete": True,
        },
        "valuation": {
            "methods": [
                {"name": "dcf", "value": 108.0},
                {"name": "normalized_earnings", "value": 112.0},
            ],
            "scenarios": {"bear": 60.0, "base": 110.0, "bull": 140.0},
            "fair_value_range": [100.0, 120.0],
            "buy_zone": [70.0, 80.0],
            "formulas_reproducible": True,
            "sensitivity_complete": True,
            "market_implied_assumptions_complete": True,
            "government_bond_yield": 0.03,
            "equity_cost": 0.11,
            "required_return_used": 0.11,
        },
        "counterevidence": ["需求下降", "成本上升", "竞争加剧"],
        "claim_reviews": [
            {"claim_id": "claim-business-quality", "result": "confirmed"}
        ],
        "risk_flags": risk_flags,
    }


def _evidence(price: float = 75.0) -> dict[str, object]:
    timestamp = NOW.isoformat()
    common = {
        "period": "2026",
        "original_basis": "reported",
        "adjusted_basis": "none",
        "source_locator": "p.1",
        "observed_at": timestamp,
        "retrieved_at": timestamp,
        "cross_checked": True,
        "review_result": "confirmed",
    }
    return {
        "ledger": [
            {
                **common,
                "evidence_id": "E-FILING",
                "claim_id": "claim-business-quality",
                "source_id": "annual-report",
                "fact_type": "critical_financial",
                "claim_role": "fact",
                "value": 100.0,
                "source_tier": "S1",
                "source_uri_or_path": "sources/annual-report.pdf",
            },
            {
                **common,
                "evidence_id": "E-PRICE",
                "claim_id": "market-price",
                "source_id": "quote",
                "fact_type": "market_price",
                "claim_role": "context",
                "value": price,
                "source_tier": "S3",
                "source_uri_or_path": "https://example.test/quote",
            },
        ],
        "share_count_bridge": {
            "base_shares": 100.0,
            "events": [],
            "diluted_shares": 100.0,
        },
    }


def _return_model(terminal_value: float = 112.0) -> dict[str, object]:
    return {
        "schema_version": 1,
        "method": "annual_cashflow_irr_v1",
        "currency": "CNY",
        "model_as_of": NOW.isoformat(),
        "base_case_distributions_per_share": [0.0],
        "base_case_terminal_value_per_share": terminal_value,
    }


def _envelope(
    task,
    *,
    packet_sha256: str,
    accounting_failure: bool = False,
    risk_flag: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 3,
        "assessment_id": f"{task.task_id}-assessment",
        "review_id": task.run_id,
        "packet_sha256": packet_sha256,
        "symbol": task.symbol,
        "information_cutoff": NOW.isoformat(),
        "assessment": _assessment(
            accounting_failure=accounting_failure,
            risk_flag=risk_flag,
        ),
        "evidence": _evidence(),
        "portfolio_inputs": {
            "current_price": 75.0,
            "price_as_of": NOW.isoformat(),
            "reduce_zone": [130.0, 140.0],
            "industry": "食品饮料",
            "economic_risk_clusters": ["premium_consumption"],
            "return_model": _return_model(),
        },
    }


class MachineContractRunner:
    def __init__(
        self,
        *,
        company_dir: Path,
        run_id: str,
        accounting_failure: bool = False,
        risk_flag: str | None = None,
        illegal_reveal_status: bool = False,
    ):
        from trading_os.research_assets.sealing import verify_sealed

        packet_path = company_dir / "underwriting" / run_id / "claim-packet.json"
        self.packet_sha256 = verify_sealed(packet_path).sha256
        self.company_dir = company_dir
        self.run_id = run_id
        self.accounting_failure = accounting_failure
        self.risk_flag = risk_flag
        self.illegal_reveal_status = illegal_reveal_status
        self.tasks = []
        self.runs_root: Path | None = None

    def run(self, task):
        from trading_os.research_assets.sealing import verify_sealed

        self.tasks.append(task)
        if task.stage == "blind":
            return AgentResult(
                ok=True,
                payload=_envelope(
                    task,
                    packet_sha256=self.packet_sha256,
                    accounting_failure=self.accounting_failure,
                    risk_flag=self.risk_flag,
                ),
            )
        if task.stage == "reveal":
            blind_path = (
                self.company_dir
                / "underwriting"
                / self.run_id
                / "blind-assessment.json"
            )
            payload = {
                "schema_version": 3,
                "review_id": task.run_id,
                "symbol": task.symbol,
                "blind_assessment_sha256": verify_sealed(blind_path).sha256,
                "difference_findings": [],
            }
            if self.illegal_reveal_status:
                payload["underwriting_status"] = "passed"
                payload["challenger_required"] = False
            return AgentResult(ok=True, payload=payload)
        if task.stage == "challenger":
            assert "blind-assessment" not in task.prompt
            assert [path.name for path in task.allowed_read_paths] == [
                "claim-packet.json"
            ]
            return AgentResult(
                ok=True,
                payload=_envelope(
                    task,
                    packet_sha256=self.packet_sha256,
                    accounting_failure=False,
                    risk_flag=self.risk_flag,
                ),
            )
        if task.stage == "arbitration":
            assert "challenger-assessment" in task.prompt
            assert self.runs_root is not None
            review_dir = (
                self.company_dir / "underwriting" / self.run_id
            )
            links = {
                "claim_packet": verify_sealed(
                    review_dir / "claim-packet.json"
                ).sha256,
                "blind_assessment": verify_sealed(
                    review_dir / "blind-assessment.json"
                ).sha256,
                "reveal_assessment": verify_sealed(
                    review_dir / "reveal-assessment.json"
                ).sha256,
                "primary_evaluation": verify_sealed(
                    review_dir / "primary-evaluation.json"
                ).sha256,
                "challenger_assessment": verify_sealed(
                    review_dir / "challenger-assessment.json"
                ).sha256,
                "challenger_evaluation": verify_sealed(
                    review_dir / "challenger-evaluation.json"
                ).sha256,
                "policy_snapshot": verify_sealed(
                    self.runs_root
                    / self.run_id
                    / "policy-snapshot.json"
                ).sha256,
            }
            payload = _envelope(
                task,
                packet_sha256=self.packet_sha256,
                accounting_failure=False,
                risk_flag=self.risk_flag,
            )
            payload["input_artifact_sha256s"] = links
            return AgentResult(
                ok=True,
                payload=payload,
            )
        raise AssertionError(task.stage)


def _prepared_review(
    tmp_path: Path,
    *,
    claim_category: str = "business",
):
    from trading_os.research_assets.review_workflow import create_review, prepare_review

    company_dir = write_company(tmp_path)
    _attach_research_claims(
        company_dir,
        claim_category=claim_category,
    )
    runs_root = tmp_path / "automation" / "runs"
    policy_root = Path("policies").resolve()
    run_id = "memory-2026-07-21"
    create_review(
        runs_root=runs_root,
        run_id=run_id,
        scope_type="industry",
        market="CN",
        description="存储产业链",
        candidates=[
            {
                "symbol": "CN:600519",
                "name": "贵州茅台",
                "target_company_dir": str(company_dir),
            }
        ],
        policy_root=policy_root,
        created_at=dt.datetime.fromisoformat(T0),
    )
    prepare_review(runs_root=runs_root, run_id=run_id, prepared_at=NOW)
    return runs_root, policy_root, company_dir, run_id


def _dispatcher(runs_root, policy_root, runner):
    if hasattr(runner, "runs_root"):
        runner.runs_root = Path(runs_root)
    return ReviewDispatcher(
        runs_root=runs_root,
        policy_root=policy_root,
        runner=runner,
        timeout_seconds=60,
        lease_seconds=120,
    )


def test_blind_prompt_contains_packet_but_not_prior_decision(tmp_path: Path):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)
    runner = MachineContractRunner(company_dir=company_dir, run_id=run_id)

    result = _dispatcher(runs_root, policy_root, runner).dispatch(run_id, now=NOW)

    assert result.status == "blind_sealed"
    prompt = runner.tasks[0].prompt
    assert "claim-business-quality" in prompt
    assert "2026-07-21-initial-research.md" not in prompt
    assert '"portfolio_eligible"' not in prompt


def test_reveal_prompt_rejects_prior_report_drift(tmp_path: Path):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)
    runner = MachineContractRunner(company_dir=company_dir, run_id=run_id)
    assert _dispatcher(runs_root, policy_root, runner).dispatch(
        run_id,
        now=NOW,
    ).status == "blind_sealed"
    meta = json.loads(
        (company_dir / "meta.json").read_text(encoding="utf-8")
    )
    report_path = company_dir / meta["reports"]["latest"]
    report_path.write_text(
        report_path.read_text(encoding="utf-8") + "\nmaterial drift\n",
        encoding="utf-8",
    )

    with pytest.raises(PromptBuildError, match="frozen claim packet"):
        build_run_prompt(
            stage="reveal",
            run_id=run_id,
            symbol="CN:600519",
            runs_root=runs_root,
            policy_root=policy_root,
        )


def test_draft_directory_runner_reads_only_the_task_draft(tmp_path: Path):
    task = type(
        "Task",
        (),
        {"stage": "blind", "symbol": "CN:600519"},
    )()
    expected = {"schema_version": 3, "symbol": "CN:600519"}
    (
        tmp_path / "blind-CN-600519.draft.json"
    ).write_text(json.dumps(expected), encoding="utf-8")
    (
        tmp_path / "challenger-CN-600519.draft.json"
    ).write_text(json.dumps({"wrong": True}), encoding="utf-8")

    result = DraftDirectoryRunner(tmp_path).run(task)

    assert result == AgentResult(ok=True, payload=expected)


def test_malformed_blind_payload_cannot_enter_production_chain(tmp_path: Path):
    runs_root, policy_root, _, run_id = _prepared_review(tmp_path)

    class MalformedRunner:
        def run(self, task):
            return AgentResult(ok=True, payload={"symbol": task.symbol, "passed": True})

    result = _dispatcher(
        runs_root,
        policy_root,
        MalformedRunner(),
    ).dispatch(run_id, now=NOW)

    assert result.status == "blind_reviewing"
    assert "machine contract" in result.failed[0][1]


def test_resume_rejects_existing_v2_stage_artifact(tmp_path: Path):
    from types import SimpleNamespace

    from trading_os.research_assets.sealing import seal_json

    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)
    runner = MachineContractRunner(company_dir=company_dir, run_id=run_id)
    legacy_payload = _envelope(
        SimpleNamespace(
            task_id="legacy-blind",
            run_id=run_id,
            symbol="CN:600519",
        ),
        packet_sha256=runner.packet_sha256,
    )
    legacy_payload["schema_version"] = 2
    seal_json(
        company_dir
        / "underwriting"
        / run_id
        / "blind-assessment.json",
        legacy_payload,
        artifact_type="blind_assessment",
        sealed_at=NOW,
    )

    result = _dispatcher(runs_root, policy_root, runner).dispatch(
        run_id,
        now=NOW,
    )

    assert result.status == "blind_reviewing"
    assert result.failed
    assert "schema_version must be 3" in result.failed[0][1]
    assert runner.tasks == []


def test_nonfinite_market_evidence_cannot_enter_production_chain(
    tmp_path: Path,
):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)

    class NonfiniteRunner(MachineContractRunner):
        def run(self, task):
            result = super().run(task)
            if not result.ok or task.stage != "blind":
                return result
            payload = copy.deepcopy(result.payload)
            market = next(
                item
                for item in payload["evidence"]["ledger"]
                if item["fact_type"] == "market_price"
            )
            market["value"] = float("nan")
            return AgentResult(ok=True, payload=payload)

    result = _dispatcher(
        runs_root,
        policy_root,
        NonfiniteRunner(company_dir=company_dir, run_id=run_id),
    ).dispatch(run_id, now=NOW)

    assert result.status == "blind_reviewing"
    assert result.failed and "finite" in result.failed[0][1]


def test_agent_cannot_self_report_status_or_suppress_challenger(tmp_path: Path):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)
    runner = MachineContractRunner(
        company_dir=company_dir,
        run_id=run_id,
        illegal_reveal_status=True,
    )
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    reveal = dispatcher.dispatch(run_id, now=NOW)

    assert reveal.status == "revealing"
    assert "fields do not match contract" in reveal.failed[0][1]


@pytest.mark.parametrize("illegal_stage", ["blind", "challenger", "arbitration"])
def test_assessment_agents_cannot_add_machine_decision_fields(
    tmp_path: Path,
    illegal_stage: str,
):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)

    class SelfDecidingRunner(MachineContractRunner):
        def run(self, task):
            result = super().run(task)
            if not result.ok or task.stage != illegal_stage:
                return result
            payload = copy.deepcopy(result.payload)
            payload["underwriting_status"] = "passed"
            payload["challenger_required"] = False
            return AgentResult(ok=True, payload=payload)

    runner = SelfDecidingRunner(company_dir=company_dir, run_id=run_id)
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    result = dispatcher.dispatch(run_id, now=NOW)
    if illegal_stage != "blind":
        assert result.status == "blind_sealed"
        result = dispatcher.dispatch(
            run_id,
            now=NOW + dt.timedelta(seconds=1),
        )
        assert result.status == "challenging"
        result = dispatcher.dispatch(
            run_id,
            now=NOW + dt.timedelta(seconds=2),
        )

    assert result.failed
    assert "fields do not match machine contract" in result.failed[0][1]
    assert not (
        company_dir
        / "underwriting"
        / run_id
        / "final-underwriting-decision.json"
    ).exists()


def test_machine_overrides_accounting_failure_even_without_agent_status(
    tmp_path: Path,
):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)
    runner = MachineContractRunner(
        company_dir=company_dir,
        run_id=run_id,
        accounting_failure=True,
    )
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch(run_id, now=NOW).status == "company_reviews_complete"

    candidate = json.loads(
        (
            company_dir
            / "underwriting"
            / run_id
            / "portfolio-candidate.primary.json"
        ).read_text(encoding="utf-8")
    )
    assert candidate["underwriting_status"] == "failed"
    assert "nonrecurring_items_unhandled" in candidate["reason_codes"]


@pytest.mark.parametrize(
    ("evidence_failure", "expected_status", "expected_blocker"),
    [
        ("stale", "stale", "stale_cyclical_data"),
        (
            "insufficient",
            "insufficient_evidence",
            "critical_financial_not_s1",
        ),
    ],
)
def test_evidence_failure_is_not_sent_to_challenger(
    tmp_path: Path,
    evidence_failure: str,
    expected_status: str,
    expected_blocker: str,
):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)

    class EvidenceFailureRunner(MachineContractRunner):
        def run(self, task):
            result = super().run(task)
            if not result.ok or task.stage != "blind":
                return result
            payload = copy.deepcopy(result.payload)
            filing = next(
                item
                for item in payload["evidence"]["ledger"]
                if item["evidence_id"] == "E-FILING"
            )
            if evidence_failure == "stale":
                filing["fact_type"] = "cyclical_price_inventory"
                filing["observed_at"] = (
                    NOW - dt.timedelta(days=31)
                ).isoformat()
            else:
                filing["source_tier"] = "S2"
            return AgentResult(ok=True, payload=payload)

    runner = EvidenceFailureRunner(
        company_dir=company_dir,
        run_id=run_id,
        risk_flag="cycle_position_uncertain",
    )
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch(run_id, now=NOW).status == (
        "company_reviews_complete"
    )

    primary = json.loads(
        (
            company_dir
            / "underwriting"
            / run_id
            / "primary-evaluation.json"
        ).read_text(encoding="utf-8")
    )
    assert primary["status"] == expected_status
    assert expected_blocker in primary["blockers"]
    assert "cycle_position_uncertain" in primary["challenger_triggers"]
    assert primary["challenger_required"] is False
    assert [task.stage for task in runner.tasks] == ["blind", "reveal"]


@pytest.mark.parametrize(
    "risk_flag",
    [
        "governance_material_doubt",
        "cycle_position_uncertain",
        "permanent_loss_risk",
    ],
)
def test_machine_risk_rules_force_challenger(tmp_path: Path, risk_flag: str):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)
    runner = MachineContractRunner(
        company_dir=company_dir,
        run_id=run_id,
        risk_flag=risk_flag,
    )
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch(run_id, now=NOW).status == "challenging"
    primary = json.loads(
        (
            company_dir
            / "underwriting"
            / run_id
            / "primary-evaluation.json"
        ).read_text(encoding="utf-8")
    )
    assert risk_flag in primary["challenger_triggers"]


def test_full_dispatch_machine_selects_top_five_and_arbitrates(tmp_path: Path):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)
    runner = MachineContractRunner(company_dir=company_dir, run_id=run_id)
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch(run_id, now=NOW).status == "challenging"
    final = dispatcher.dispatch(run_id, now=NOW)

    assert final.status == "company_reviews_complete"
    assert [task.stage for task in runner.tasks] == [
        "blind",
        "reveal",
        "challenger",
        "arbitration",
    ]
    primary = json.loads(
        (
            company_dir
            / "underwriting"
            / run_id
            / "primary-evaluation.json"
        ).read_text(encoding="utf-8")
    )
    candidate = json.loads(
        (
            company_dir
            / "underwriting"
            / run_id
            / "portfolio-candidate.final.json"
        ).read_text(encoding="utf-8")
    )
    assert primary["proposed_top_five"] is True
    assert "proposed_top_five_position" in primary["challenger_triggers"]
    assert candidate["underwriting_status"] == "passed"
    assert candidate["independent_challenger_completed"] is True
    assert "portfolio_eligible" not in candidate
    assert "rank_score" not in candidate
    assert "expected_annual_return" not in candidate


def test_arbitrator_cannot_replace_independent_candidate_economics(
    tmp_path: Path,
):
    from trading_os.research_assets.portfolio import (
        portfolio_candidate_core_sha256,
    )
    from trading_os.research_assets.sealing import verify_sealed

    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)

    class EconomicRewriteRunner(MachineContractRunner):
        def run(self, task):
            result = super().run(task)
            if not result.ok:
                return result
            payload = copy.deepcopy(result.payload)
            if task.stage == "challenger":
                valuation = payload["assessment"]["valuation"]
                valuation["methods"] = [
                    {"name": "dcf", "value": 98.0},
                    {"name": "normalized_earnings", "value": 102.0},
                ]
                valuation["scenarios"] = {
                    "bear": 55.0,
                    "base": 100.0,
                    "bull": 130.0,
                }
                valuation["fair_value_range"] = [90.0, 110.0]
                valuation["buy_zone"] = [60.0, 70.0]
                payload["portfolio_inputs"]["reduce_zone"] = [115.0, 125.0]
                payload["portfolio_inputs"]["return_model"] = _return_model(100.0)
            elif task.stage == "arbitration":
                valuation = payload["assessment"]["valuation"]
                valuation["methods"] = [
                    {"name": "dcf", "value": 440.0},
                    {"name": "normalized_earnings", "value": 460.0},
                ]
                valuation["scenarios"] = {
                    "bear": 300.0,
                    "base": 450.0,
                    "bull": 600.0,
                }
                valuation["fair_value_range"] = [400.0, 500.0]
                valuation["buy_zone"] = [250.0, 300.0]
                payload["portfolio_inputs"]["reduce_zone"] = [900.0, 1000.0]
                payload["portfolio_inputs"]["return_model"] = _return_model(1000.0)
            return AgentResult(ok=True, payload=payload)

    runner = EconomicRewriteRunner(company_dir=company_dir, run_id=run_id)
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch(run_id, now=NOW).status == "challenging"
    assert (
        dispatcher.dispatch(run_id, now=NOW).status
        == "company_reviews_complete"
    )

    review_dir = company_dir / "underwriting" / run_id
    candidate = json.loads(
        (review_dir / "portfolio-candidate.final.json").read_text(
            encoding="utf-8"
        )
    )
    decision = json.loads(
        (review_dir / "final-underwriting-decision.json").read_text(
            encoding="utf-8"
        )
    )
    assert candidate["underwriting_status"] == "passed"
    assert candidate["fair_value_range"] == [90.0, 110.0]
    assert candidate["bear_value"] == 55.0
    assert candidate["reduce_zone"] == [115.0, 125.0]
    assert (
        candidate["return_model"]["base_case_terminal_value_per_share"]
        == 100.0
    )
    assert decision["candidate_source_stage"] == "challenger"
    assert (
        decision["candidate_source_assessment_sha256"]
        == verify_sealed(review_dir / "challenger-assessment.json").sha256
    )
    assert (
        decision["portfolio_candidate_core_sha256"]
        == portfolio_candidate_core_sha256(candidate)
    )


def test_material_return_model_disagreement_cannot_be_arbitrated_away(
    tmp_path: Path,
):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)

    class ReturnModelDisagreementRunner(MachineContractRunner):
        def run(self, task):
            result = super().run(task)
            if not result.ok or task.stage != "challenger":
                return result
            payload = copy.deepcopy(result.payload)
            payload["portfolio_inputs"]["return_model"] = _return_model(60.0)
            return AgentResult(ok=True, payload=payload)

    runner = ReturnModelDisagreementRunner(
        company_dir=company_dir,
        run_id=run_id,
    )
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch(run_id, now=NOW).status == "challenging"
    assert (
        dispatcher.dispatch(run_id, now=NOW).status
        == "company_reviews_complete"
    )

    candidate = json.loads(
        (
            company_dir
            / "underwriting"
            / run_id
            / "portfolio-candidate.final.json"
        ).read_text(encoding="utf-8")
    )
    assert candidate["underwriting_status"] == "failed"
    assert "challenger_no_return_model_consensus" in candidate["reason_codes"]


@pytest.mark.parametrize(
    ("adverse_kind", "expected_blocker"),
    [
        (
            "risk",
            "consensus_risk_flag:permanent_loss_risk",
        ),
        (
            "claim",
            "consensus_investment_claim_disproven:claim-business-quality",
        ),
    ],
)
def test_consensus_adverse_finding_cannot_be_cleared_by_arbitration(
    tmp_path: Path,
    adverse_kind: str,
    expected_blocker: str,
):
    runs_root, policy_root, company_dir, run_id = _prepared_review(
        tmp_path,
        claim_category=(
            "investment" if adverse_kind == "claim" else "business"
        ),
    )

    class ConsensusAdverseRunner(MachineContractRunner):
        def run(self, task):
            result = super().run(task)
            if not result.ok:
                return result
            payload = copy.deepcopy(result.payload)
            if task.stage in {"blind", "challenger"}:
                if adverse_kind == "risk":
                    payload["assessment"]["risk_flags"][
                        "permanent_loss_risk"
                    ] = True
                    payload["assessment"]["safety_margin_tier"] = "severe"
                else:
                    payload["assessment"]["claim_reviews"][0][
                        "result"
                    ] = "disproven"
            elif task.stage == "arbitration":
                payload["assessment"]["risk_flags"][
                    "permanent_loss_risk"
                ] = False
                payload["assessment"]["safety_margin_tier"] = "standard"
                payload["assessment"]["claim_reviews"][0][
                    "result"
                ] = "confirmed"
            return AgentResult(ok=True, payload=payload)

    runner = ConsensusAdverseRunner(
        company_dir=company_dir,
        run_id=run_id,
    )
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch(run_id, now=NOW).status == "challenging"
    assert (
        dispatcher.dispatch(run_id, now=NOW).status
        == "company_reviews_complete"
    )

    candidate = json.loads(
        (
            company_dir
            / "underwriting"
            / run_id
            / "portfolio-candidate.final.json"
        ).read_text(encoding="utf-8")
    )
    assert candidate["underwriting_status"] == "failed"
    assert expected_blocker in candidate["reason_codes"]


def test_arbitration_can_conservatively_resolve_investment_claim_disagreement(
    tmp_path: Path,
):
    runs_root, policy_root, company_dir, run_id = _prepared_review(
        tmp_path,
        claim_category="investment",
    )

    class ConservativeClaimResolutionRunner(MachineContractRunner):
        def run(self, task):
            result = super().run(task)
            if not result.ok or task.stage not in {"challenger", "arbitration"}:
                return result
            payload = copy.deepcopy(result.payload)
            payload["assessment"]["claim_reviews"][0]["result"] = "weakened"
            return AgentResult(ok=True, payload=payload)

    runner = ConservativeClaimResolutionRunner(
        company_dir=company_dir,
        run_id=run_id,
    )
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch(run_id, now=NOW).status == "challenging"
    assert (
        dispatcher.dispatch(run_id, now=NOW).status
        == "company_reviews_complete"
    )

    candidate = json.loads(
        (
            company_dir
            / "underwriting"
            / run_id
            / "portfolio-candidate.final.json"
        ).read_text(encoding="utf-8")
    )
    assert candidate["underwriting_status"] == "passed"
    assert (
        "unresolved_investment_claim:claim-business-quality"
        not in candidate["reason_codes"]
    )


def test_optimistic_arbitration_cannot_erase_weaker_independent_claim(
    tmp_path: Path,
):
    runs_root, policy_root, company_dir, run_id = _prepared_review(
        tmp_path,
        claim_category="investment",
    )

    class OptimisticClaimArbitrationRunner(MachineContractRunner):
        def run(self, task):
            result = super().run(task)
            if not result.ok or task.stage != "challenger":
                return result
            payload = copy.deepcopy(result.payload)
            payload["assessment"]["claim_reviews"][0]["result"] = "weakened"
            return AgentResult(ok=True, payload=payload)

    runner = OptimisticClaimArbitrationRunner(
        company_dir=company_dir,
        run_id=run_id,
    )
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch(run_id, now=NOW).status == "challenging"
    assert (
        dispatcher.dispatch(run_id, now=NOW).status
        == "company_reviews_complete"
    )

    candidate = json.loads(
        (
            company_dir
            / "underwriting"
            / run_id
            / "portfolio-candidate.final.json"
        ).read_text(encoding="utf-8")
    )
    assert candidate["underwriting_status"] == "failed"
    assert (
        "unresolved_investment_claim:claim-business-quality"
        in candidate["reason_codes"]
    )


def test_conservative_claim_resolution_cannot_clear_new_arbitration_risk(
    tmp_path: Path,
):
    runs_root, policy_root, company_dir, run_id = _prepared_review(
        tmp_path,
        claim_category="investment",
    )

    class AdverseClaimResolutionRunner(MachineContractRunner):
        def run(self, task):
            result = super().run(task)
            if not result.ok or task.stage not in {"challenger", "arbitration"}:
                return result
            payload = copy.deepcopy(result.payload)
            payload["assessment"]["claim_reviews"][0]["result"] = "weakened"
            if task.stage == "arbitration":
                payload["assessment"]["risk_flags"][
                    "permanent_loss_risk"
                ] = True
                payload["assessment"]["safety_margin_tier"] = "severe"
            return AgentResult(ok=True, payload=payload)

    runner = AdverseClaimResolutionRunner(
        company_dir=company_dir,
        run_id=run_id,
    )
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch(run_id, now=NOW).status == "challenging"
    assert (
        dispatcher.dispatch(run_id, now=NOW).status
        == "company_reviews_complete"
    )

    candidate = json.loads(
        (
            company_dir
            / "underwriting"
            / run_id
            / "portfolio-candidate.final.json"
        ).read_text(encoding="utf-8")
    )
    assert candidate["underwriting_status"] == "failed"
    assert (
        "arbitration_risk_flag:permanent_loss_risk"
        in candidate["reason_codes"]
    )


def test_consensus_cycle_uncertainty_can_pass_after_independent_challenge(
    tmp_path: Path,
):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)

    class ConsensusCycleRunner(MachineContractRunner):
        def run(self, task):
            result = super().run(task)
            if not result.ok or task.stage not in {"blind", "challenger"}:
                return result
            payload = copy.deepcopy(result.payload)
            payload["assessment"]["risk_flags"][
                "cycle_position_uncertain"
            ] = True
            payload["assessment"]["safety_margin_tier"] = "elevated"
            return AgentResult(ok=True, payload=payload)

    runner = ConsensusCycleRunner(company_dir=company_dir, run_id=run_id)
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch(run_id, now=NOW).status == "challenging"
    assert (
        dispatcher.dispatch(run_id, now=NOW).status
        == "company_reviews_complete"
    )

    candidate = json.loads(
        (
            company_dir
            / "underwriting"
            / run_id
            / "portfolio-candidate.final.json"
        ).read_text(encoding="utf-8")
    )
    assert candidate["underwriting_status"] == "passed"
    assert "cycle_position_uncertain" in candidate["reason_codes"]
    assert (
        "consensus_risk_flag:cycle_position_uncertain"
        not in candidate["reason_codes"]
    )


def test_arbitration_can_degrade_but_never_upgrade_independent_consensus(
    tmp_path: Path,
):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)

    class ArbitrationVetoRunner(MachineContractRunner):
        def run(self, task):
            result = super().run(task)
            if not result.ok or task.stage != "arbitration":
                return result
            payload = copy.deepcopy(result.payload)
            payload["assessment"]["accounting_checks"][
                "nonrecurring_items_handled"
            ] = False
            return AgentResult(ok=True, payload=payload)

    runner = ArbitrationVetoRunner(company_dir=company_dir, run_id=run_id)
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch(run_id, now=NOW).status == "challenging"
    assert (
        dispatcher.dispatch(run_id, now=NOW).status
        == "company_reviews_complete"
    )

    candidate = json.loads(
        (
            company_dir
            / "underwriting"
            / run_id
            / "portfolio-candidate.final.json"
        ).read_text(encoding="utf-8")
    )
    assert candidate["underwriting_status"] == "failed"
    assert "nonrecurring_items_unhandled" in candidate["reason_codes"]


def test_primary_evaluation_uses_reveal_time_not_blind_time(tmp_path: Path):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)
    runner = MachineContractRunner(company_dir=company_dir, run_id=run_id)
    dispatcher = _dispatcher(runs_root, policy_root, runner)
    reveal_time = NOW + dt.timedelta(hours=2)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch(run_id, now=reveal_time).status == "challenging"

    primary = json.loads(
        (
            company_dir
            / "underwriting"
            / run_id
            / "primary-evaluation.json"
        ).read_text(encoding="utf-8")
    )
    assert primary["evaluated_at"] == reveal_time.isoformat()


def test_arbitration_rejects_incorrect_input_artifact_sha256(tmp_path: Path):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)

    class WrongArbitrationLinkRunner(MachineContractRunner):
        def run(self, task):
            result = super().run(task)
            if not result.ok or task.stage != "arbitration":
                return result
            payload = copy.deepcopy(result.payload)
            payload["input_artifact_sha256s"]["primary_evaluation"] = "0" * 64
            return AgentResult(ok=True, payload=payload)

    runner = WrongArbitrationLinkRunner(
        company_dir=company_dir,
        run_id=run_id,
    )
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert (
        dispatcher.dispatch(
            run_id,
            now=NOW + dt.timedelta(seconds=1),
        ).status
        == "challenging"
    )
    result = dispatcher.dispatch(
        run_id,
        now=NOW + dt.timedelta(seconds=2),
    )

    assert result.status == "challenging"
    assert result.failed
    assert "input artifact SHA-256 links do not match" in result.failed[0][1]
    assert not (
        company_dir
        / "underwriting"
        / run_id
        / "final-underwriting-decision.json"
    ).exists()


def test_challenger_hard_blocker_cannot_be_erased_by_clean_arbitration(
    tmp_path: Path,
):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)

    class ChallengerFailureRunner(MachineContractRunner):
        def run(self, task):
            result = super().run(task)
            if not result.ok or task.stage != "challenger":
                return result
            payload = copy.deepcopy(result.payload)
            payload["assessment"]["accounting_checks"][
                "nonrecurring_items_handled"
            ] = False
            return AgentResult(ok=True, payload=payload)

    runner = ChallengerFailureRunner(company_dir=company_dir, run_id=run_id)
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch(run_id, now=NOW).status == "challenging"
    assert (
        dispatcher.dispatch(run_id, now=NOW).status
        == "company_reviews_complete"
    )

    candidate = json.loads(
        (
            company_dir
            / "underwriting"
            / run_id
            / "portfolio-candidate.final.json"
        ).read_text(encoding="utf-8")
    )
    assert candidate["underwriting_status"] == "failed"
    assert "independent_machine_validation_failed" in candidate["reason_codes"]
    assert (
        "challenger_blocker:nonrecurring_items_unhandled"
        in candidate["reason_codes"]
    )


def test_challenger_stale_evidence_remains_stale_instead_of_failed(
    tmp_path: Path,
):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)

    class StaleChallengerRunner(MachineContractRunner):
        def run(self, task):
            result = super().run(task)
            if not result.ok or task.stage != "challenger":
                return result
            payload = copy.deepcopy(result.payload)
            filing = next(
                item
                for item in payload["evidence"]["ledger"]
                if item["evidence_id"] == "E-FILING"
            )
            filing["fact_type"] = "cyclical_price_inventory"
            filing["observed_at"] = (
                NOW - dt.timedelta(days=31)
            ).isoformat()
            return AgentResult(ok=True, payload=payload)

    runner = StaleChallengerRunner(company_dir=company_dir, run_id=run_id)
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch(run_id, now=NOW).status == "challenging"
    assert (
        dispatcher.dispatch(run_id, now=NOW).status
        == "company_reviews_complete"
    )

    candidate = json.loads(
        (
            company_dir
            / "underwriting"
            / run_id
            / "portfolio-candidate.final.json"
        ).read_text(encoding="utf-8")
    )
    assert candidate["underwriting_status"] == "stale"
    assert "independent_evidence_invalid" in candidate["reason_codes"]
    assert "stale_cyclical_data" in candidate["reason_codes"]
    assert "independent_machine_validation_failed" not in candidate[
        "reason_codes"
    ]


def test_agent_failure_is_isolated_and_resume_retries_only_failed_work(
    tmp_path: Path,
):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)
    valid = MachineContractRunner(company_dir=company_dir, run_id=run_id)

    class FlakyRunner:
        def __init__(self):
            self.fail = True
            self.calls = 0

        def run(self, task):
            self.calls += 1
            if self.fail:
                return AgentResult(ok=False, error="simulated timeout")
            return valid.run(task)

    runner = FlakyRunner()
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    first = dispatcher.dispatch(run_id, now=NOW)
    assert first.status == "blind_reviewing"
    runner.fail = False
    second = dispatcher.dispatch(run_id, now=NOW + dt.timedelta(seconds=1))

    assert second.status == "blind_sealed"
    assert runner.calls == 2


def test_phase_prompt_contract_rejects_extra_cross_stage_data():
    with pytest.raises(PromptBuildError, match="unknown"):
        render_prompt(
            "challenger",
            {
                "company_name": "测试",
                "symbol": "CN:000001",
                "output_path": "out.json",
                "claim_packet": {},
                "packet_sha256": "0" * 64,
                "underwriting_policy": {},
                "primary_review": {"secret": True},
            },
        )


def test_synthesis_prompt_is_gated_by_state_and_sealed_machine_outputs(
    tmp_path: Path,
):
    from trading_os.research_assets.review_store import ReviewRunStore
    from trading_os.research_assets.sealing import seal_json

    runs_root, policy_root, _, run_id = _prepared_review(tmp_path)
    with pytest.raises(PromptBuildError, match="completed company reviews"):
        build_synthesis_prompt(
            run_id=run_id,
            runs_root=runs_root,
            research_root=tmp_path / "research",
            policy_root=policy_root,
            output_path=tmp_path / "synthesis.md",
        )
    store = ReviewRunStore(runs_root)
    for status in (
        "blind_reviewing",
        "blind_sealed",
        "revealing",
        "company_reviews_complete",
        "synthesizing",
    ):
        store.transition(run_id, status, actor="test", at=NOW)
    batch_dir = tmp_path / "research" / "batches" / run_id
    seal_json(
        batch_dir / "quotes.json",
        [{"symbol": "CN:600519", "price": 10.0}],
        artifact_type="quote_snapshot",
        sealed_at=NOW,
    )
    seal_json(
        batch_dir / "portfolio.json",
        {"schema_version": 3, "positions": [], "cash_weight": 1.0},
        artifact_type="model_portfolio",
        sealed_at=NOW,
    )

    prompt = build_synthesis_prompt(
        run_id=run_id,
        runs_root=runs_root,
        research_root=tmp_path / "research",
        policy_root=policy_root,
        output_path=tmp_path / "synthesis.md",
    )

    assert '"cash_weight": 1.0' in prompt


def test_subprocess_runner_reports_timeout(monkeypatch, tmp_path: Path):
    from automation.scripts.review_dispatch import AgentTask

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["agent"], timeout=1)

    monkeypatch.setattr(subprocess, "run", timeout)
    task = AgentTask(
        run_id="run",
        task_id="task",
        stage="blind",
        symbol="CN:000001",
        prompt="prompt",
        output_path=tmp_path / "out.json",
        allowed_read_paths=(),
        allowed_write_paths=(tmp_path / "out.json",),
        timeout_seconds=1,
    )

    result = SubprocessRunner(["agent"]).run(task)

    assert result.ok is False
    assert result.error == "timeout after 1s"


def test_dispatcher_rejects_lease_shorter_than_agent_timeout(tmp_path: Path):
    with pytest.raises(DispatchError, match="exceed"):
        ReviewDispatcher(
            runs_root=tmp_path / "runs",
            policy_root=Path("policies"),
            runner=object(),
            timeout_seconds=60,
            lease_seconds=60,
        )

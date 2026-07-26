from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from automation.scripts.review_dispatch import AgentResult
from tests.test_review_dispatch import (
    NOW,
    MachineContractRunner,
    _dispatcher,
    _envelope,
    _prepared_review,
)


def _activation_price() -> float:
    return 180.0 / (1.12**5)


def test_corrupt_claim_packet_text_forces_insufficient_evidence():
    from trading_os.research_assets.underwriting_contract import (
        evaluate_assessment_envelope,
    )

    packet_sha256 = "a" * 64
    payload = _envelope(
        SimpleNamespace(
            task_id="corrupt-claim-packet",
            run_id="memory-2026-07-21",
            symbol="CN:600519",
        ),
        packet_sha256=packet_sha256,
    )
    claim_packet = {
        "schema_version": 2,
        "review_id": "memory-2026-07-21",
        "symbol": "CN:600519",
        "claims": [
            {
                "claim_id": "claim-business-quality",
                "category": "business",
                "claim": "????????????",
                "verification_metrics": ["渠道库存"],
                "falsifiers": ["渠道库存持续恶化"],
            }
        ],
        "allowed_sources": [
            {
                "source_id": "annual-report",
                "tier": "S1",
                "uri_or_path": "sources/annual-report.pdf",
            }
        ],
    }
    policy = json.loads(
        Path("policies/underwriting.json").read_text(encoding="utf-8")
    )["payload"]

    result = evaluate_assessment_envelope(
        payload,
        expected_symbol="CN:600519",
        expected_review_id="memory-2026-07-21",
        expected_packet_sha256=packet_sha256,
        claim_packet=claim_packet,
        underwriting_policy=policy,
        evaluated_at=NOW,
        prior_fair_value_range=None,
    )

    assert result.evidence.blockers == ("corrupt_claim_packet_text",)
    assert result.evidence.is_stale is False
    assert result.evaluation.status == "insufficient_evidence"


class RepricingRunner(MachineContractRunner):
    def __init__(
        self,
        *,
        initial_price: float,
        force_risk_challenger: bool = False,
        **kwargs,
    ):
        super().__init__(
            risk_flag=(
                "governance_material_doubt"
                if force_risk_challenger
                else None
            ),
            **kwargs,
        )
        self.initial_price = initial_price

    def run(self, task):
        result = super().run(task)
        if not result.ok or task.stage == "reveal":
            return result
        payload = copy.deepcopy(result.payload)
        assessment = payload["assessment"]
        assessment["valuation"].update(
            {
                "methods": [
                    {"name": "dcf", "value": 135.0},
                    {"name": "normalized_earnings", "value": 145.0},
                ],
                "scenarios": {"bear": 60.0, "base": 140.0, "bull": 180.0},
                "fair_value_range": [130.0, 150.0],
                "buy_zone": [70.0, 110.0],
            }
        )
        for item in payload["evidence"]["ledger"]:
            if item["fact_type"] == "market_price":
                item["value"] = self.initial_price
        payload["portfolio_inputs"].update(
            {
                "current_price": self.initial_price,
                "reduce_zone": [170.0, 190.0],
                "return_model": {
                    "schema_version": 1,
                    "method": "annual_cashflow_irr_v1",
                    "currency": "CNY",
                    "model_as_of": NOW.isoformat(),
                    "base_case_distributions_per_share": [0.0] * 5,
                    "base_case_terminal_value_per_share": 180.0,
                },
            }
        )
        return AgentResult(ok=True, payload=payload)


def _complete_company_review(tmp_path: Path, *, initial_price: float):
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)
    runner = RepricingRunner(
        company_dir=company_dir,
        run_id=run_id,
        initial_price=initial_price,
    )
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    reveal = dispatcher.dispatch(run_id, now=NOW)
    if reveal.status == "challenging":
        assert (
            dispatcher.dispatch(run_id, now=NOW).status
            == "company_reviews_complete"
        )
    else:
        assert reveal.status == "company_reviews_complete"
    return runs_root, policy_root, company_dir, run_id


@pytest.mark.parametrize(
    ("initial_delta", "quote_delta", "expected_action"),
    [
        (0.5, -0.5, "buy_now"),
        (-0.5, 0.5, "watch"),
    ],
)
def test_fresh_quote_reprices_return_and_crosses_hurdle_both_directions(
    tmp_path: Path,
    initial_delta: float,
    quote_delta: float,
    expected_action: str,
):
    from trading_os.research_assets.review_workflow import synthesize_review

    activation = _activation_price()
    runs_root, policy_root, company_dir, run_id = _complete_company_review(
        tmp_path,
        initial_price=activation + initial_delta,
    )
    quote_price = activation + quote_delta
    quotes_path = tmp_path / "quotes.json"
    quotes_path.write_text(
        json.dumps(
            [
                {
                    "symbol": "CN:600519",
                    "price": quote_price,
                    "as_of": NOW.isoformat(),
                }
            ]
        ),
        encoding="utf-8",
    )

    synthesized = synthesize_review(
        runs_root=runs_root,
        research_root=tmp_path / "research",
        policy_root=policy_root,
        run_id=run_id,
        quotes_path=quotes_path,
        synthesized_at=NOW,
    )
    if synthesized["status"] == "portfolio_challenging":
        runner = RepricingRunner(
            company_dir=company_dir,
            run_id=run_id,
            initial_price=activation + initial_delta,
        )
        dispatcher = _dispatcher(runs_root, policy_root, runner)
        assert (
            dispatcher.dispatch(
                run_id,
                now=NOW + dt.timedelta(seconds=1),
            ).status
            == "company_reviews_complete"
        )
        synthesize_review(
            runs_root=runs_root,
            research_root=tmp_path / "research",
            policy_root=policy_root,
            run_id=run_id,
            quotes_path=quotes_path,
            synthesized_at=NOW + dt.timedelta(seconds=2),
        )

    portfolio = json.loads(
        (
            tmp_path / "research" / "batches" / run_id / "portfolio.json"
        ).read_text(encoding="utf-8")
    )
    decision = portfolio["positions"][0]
    assert portfolio["schema_version"] == 3
    assert decision["action"] == expected_action
    assert decision["evidence_stale"] is False
    assert decision["current_price"] == pytest.approx(quote_price)
    assert decision["minimum_return_activation_price"] == pytest.approx(activation)
    assert decision["expected_return_gap"] == pytest.approx(
        decision["expected_annual_return"] - 0.12
    )
    assert decision["buy_now_price_ceiling"] == pytest.approx(activation)
    assert len(decision["portfolio_candidate_sha256"]) == 64
    if expected_action == "watch":
        assert "expected_return_below_minimum" in decision["reason_codes"]
        assert "expected_return_near_miss" in decision["reason_codes"]


@pytest.mark.parametrize("price", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_quote_is_rejected_before_portfolio_build(
    tmp_path: Path,
    price: float,
):
    from trading_os.research_assets.review_workflow import (
        ReviewWorkflowError,
        synthesize_review,
    )

    runs_root, policy_root, _, run_id = _complete_company_review(
        tmp_path,
        initial_price=_activation_price() - 0.25,
    )
    quotes_path = tmp_path / "quotes.json"
    quotes_path.write_text(
        json.dumps(
            [{"symbol": "CN:600519", "price": price, "as_of": NOW.isoformat()}]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ReviewWorkflowError, match="invalid quote price"):
        synthesize_review(
            runs_root=runs_root,
            research_root=tmp_path / "research",
            policy_root=policy_root,
            run_id=run_id,
            quotes_path=quotes_path,
            synthesized_at=NOW,
        )


def test_machine_generated_portfolio_can_be_recomputed_from_sealed_return_model(
    tmp_path: Path,
):
    from trading_os.research_assets.portfolio import (
        activation_price,
        expected_annual_return,
    )
    from trading_os.research_assets.review_workflow import (
        synthesize_review,
        write_review_report,
    )

    activation = _activation_price()
    runs_root, policy_root, _, run_id = _complete_company_review(
        tmp_path,
        initial_price=activation - 0.25,
    )
    quote = activation - 0.75
    quotes_path = tmp_path / "quotes.json"
    quotes_path.write_text(
        json.dumps(
            [{"symbol": "CN:600519", "price": quote, "as_of": NOW.isoformat()}]
        ),
        encoding="utf-8",
    )
    synthesize_review(
        runs_root=runs_root,
        research_root=tmp_path / "research",
        policy_root=policy_root,
        run_id=run_id,
        quotes_path=quotes_path,
        synthesized_at=NOW,
    )
    decision = json.loads(
        (
            tmp_path / "research" / "batches" / run_id / "portfolio.json"
        ).read_text(encoding="utf-8")
    )["positions"][0]

    assert decision["expected_annual_return"] == pytest.approx(
        expected_annual_return(quote, decision["return_model"])
    )
    assert decision["minimum_return_activation_price"] == pytest.approx(
        activation_price(
            decision["return_model"],
            minimum_expected_annual_return=0.12,
        )
    )
    write_review_report(
        runs_root=runs_root,
        research_root=tmp_path / "research",
        run_id=run_id,
        reported_at=NOW,
    )
    report = (
        tmp_path / "research" / "batches" / run_id / "synthesis.md"
    ).read_text(encoding="utf-8")
    assert "预期年化" in report
    assert "12%激活价" in report


def test_synthesis_rejects_candidate_bound_to_wrong_machine_decision(
    tmp_path: Path,
    monkeypatch,
):
    from trading_os.research_assets.review_workflow import (
        ReviewWorkflowError,
        synthesize_review,
    )
    from trading_os.research_assets.sealing import seal_json

    activation = _activation_price()
    runs_root, policy_root, company_dir, run_id = _complete_company_review(
        tmp_path,
        initial_price=activation - 0.25,
    )
    review_dir = company_dir / "underwriting" / run_id
    source_candidate_path = (
        review_dir / "portfolio-candidate.primary.json"
    )
    candidate_path = (
        review_dir / "portfolio-candidate.tampered.json"
    )
    candidate = json.loads(source_candidate_path.read_text(encoding="utf-8"))
    candidate["source_machine_decision_sha256"] = "0" * 64
    seal_json(
        candidate_path,
        candidate,
        artifact_type="portfolio_candidate",
        sealed_at=NOW + dt.timedelta(seconds=1),
    )
    monkeypatch.setattr(
        "trading_os.research_assets.review_workflow."
        "_active_portfolio_candidate_path",
        lambda *_: candidate_path,
    )
    quotes_path = tmp_path / "quotes.json"
    quotes_path.write_text(
        json.dumps(
            [
                {
                    "symbol": "CN:600519",
                    "price": activation - 0.5,
                    "as_of": NOW.isoformat(),
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ReviewWorkflowError,
        match="portfolio candidate machine decision mismatch",
    ):
        synthesize_review(
            runs_root=runs_root,
            research_root=tmp_path / "research",
            policy_root=policy_root,
            run_id=run_id,
            quotes_path=quotes_path,
            synthesized_at=NOW,
        )


def test_synthesis_rejects_resealed_candidate_economics_with_correct_machine_link(
    tmp_path: Path,
    monkeypatch,
):
    from trading_os.research_assets.review_workflow import (
        ReviewWorkflowError,
        synthesize_review,
    )
    from trading_os.research_assets.sealing import seal_json, verify_sealed

    activation = _activation_price()
    runs_root, policy_root, company_dir, run_id = _complete_company_review(
        tmp_path,
        initial_price=activation - 0.25,
    )
    review_dir = company_dir / "underwriting" / run_id
    source_candidate_path = review_dir / "portfolio-candidate.primary.json"
    machine_decision_path = review_dir / "primary-evaluation.json"
    candidate = json.loads(source_candidate_path.read_text(encoding="utf-8"))
    original_machine_link = candidate["source_machine_decision_sha256"]
    assert original_machine_link == verify_sealed(machine_decision_path).sha256

    candidate["fair_value_range"] = [1.0, 999.0]
    candidate["return_model"]["base_case_terminal_value_per_share"] = 999.0
    assert candidate["source_machine_decision_sha256"] == original_machine_link
    candidate_path = review_dir / "portfolio-candidate.tampered.json"
    seal_json(
        candidate_path,
        candidate,
        artifact_type="portfolio_candidate",
        sealed_at=NOW + dt.timedelta(seconds=1),
    )
    monkeypatch.setattr(
        "trading_os.research_assets.review_workflow."
        "_active_portfolio_candidate_path",
        lambda *_: candidate_path,
    )
    quotes_path = tmp_path / "quotes.json"
    quotes_path.write_text(
        json.dumps(
            [
                {
                    "symbol": "CN:600519",
                    "price": activation - 0.5,
                    "as_of": NOW.isoformat(),
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ReviewWorkflowError,
        match="portfolio candidate core SHA-256 mismatch",
    ):
        synthesize_review(
            runs_root=runs_root,
            research_root=tmp_path / "research",
            policy_root=policy_root,
            run_id=run_id,
            quotes_path=quotes_path,
            synthesized_at=NOW,
        )


def test_latest_quote_reorders_actual_top_five_and_dispatches_challenger(
    tmp_path: Path,
):
    from trading_os.research_assets.review_store import ReviewRunStore
    from trading_os.research_assets.review_workflow import synthesize_review

    activation = _activation_price()
    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)
    runner = RepricingRunner(
        company_dir=company_dir,
        run_id=run_id,
        initial_price=activation + 0.5,
        force_risk_challenger=False,
    )
    dispatcher = _dispatcher(runs_root, policy_root, runner)

    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert (
        dispatcher.dispatch(run_id, now=NOW).status
        == "company_reviews_complete"
    )
    quote_time = NOW + dt.timedelta(seconds=1)
    quotes_path = tmp_path / "quotes.json"
    quotes_path.write_text(
        json.dumps(
            [
                {
                    "symbol": "CN:600519",
                    "price": activation - 0.5,
                    "as_of": quote_time.isoformat(),
                }
            ]
        ),
        encoding="utf-8",
    )

    preflight = synthesize_review(
        runs_root=runs_root,
        research_root=tmp_path / "research",
        policy_root=policy_root,
        run_id=run_id,
        quotes_path=quotes_path,
        synthesized_at=quote_time,
    )
    assert preflight["status"] == "portfolio_challenging"
    assert preflight["symbols"] == ["CN:600519"]
    assert not (
        tmp_path / "research" / "batches" / run_id / "portfolio.json"
    ).exists()

    completed = dispatcher.dispatch(
        run_id,
        now=quote_time + dt.timedelta(seconds=1),
    )
    assert completed.status == "company_reviews_complete"
    assert (
        company_dir
        / "underwriting"
        / run_id
        / "portfolio-candidate.final.json"
    ).is_file()

    synthesized = synthesize_review(
        runs_root=runs_root,
        research_root=tmp_path / "research",
        policy_root=policy_root,
        run_id=run_id,
        quotes_path=quotes_path,
        synthesized_at=quote_time + dt.timedelta(seconds=2),
    )
    assert synthesized["status"] == "synthesizing"
    portfolio = json.loads(
        (
            tmp_path / "research" / "batches" / run_id / "portfolio.json"
        ).read_text(encoding="utf-8")
    )
    assert portfolio["positions"][0]["action"] == "buy_now"
    assert (
        ReviewRunStore(runs_root).load_run(run_id)["status"]
        == "synthesizing"
    )


def test_tampered_blind_artifact_cannot_reach_reveal_or_portfolio(
    tmp_path: Path,
):
    from trading_os.research_assets.sealing import SealingError, verify_sealed

    runs_root, policy_root, company_dir, run_id = _prepared_review(tmp_path)
    runner = RepricingRunner(
        company_dir=company_dir,
        run_id=run_id,
        initial_price=_activation_price() - 0.25,
    )
    dispatcher = _dispatcher(runs_root, policy_root, runner)
    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"

    blind_path = (
        company_dir / "underwriting" / run_id / "blind-assessment.json"
    )
    blind_path.write_bytes(blind_path.read_bytes() + b" ")
    with pytest.raises(SealingError, match="sha256"):
        verify_sealed(blind_path)

    result = dispatcher.dispatch(run_id, now=NOW + dt.timedelta(seconds=1))
    assert result.status == "revealing"
    assert result.failed and "sha256" in result.failed[0][1]
    assert not any(task.stage == "reveal" for task in runner.tasks)
    assert not (
        company_dir
        / "underwriting"
        / run_id
        / "portfolio-candidate.primary.json"
    ).exists()
    assert not (
        company_dir
        / "underwriting"
        / run_id
        / "portfolio-candidate.final.json"
    ).exists()


def test_stale_quotes_require_resume_and_fresh_snapshot_before_buy(
    tmp_path: Path,
):
    from trading_os.research_assets.review_store import ReviewRunStore
    from trading_os.research_assets.review_workflow import (
        ReviewWorkflowError,
        resume_review,
        synthesize_review,
    )

    activation = _activation_price()
    runs_root, policy_root, _, run_id = _complete_company_review(
        tmp_path,
        initial_price=activation - 0.25,
    )
    synthesis_time = NOW + dt.timedelta(minutes=1)
    quotes_path = tmp_path / "quotes.json"
    quotes_path.write_text(
        json.dumps(
            [
                {
                    "symbol": "CN:600519",
                    "price": activation - 0.5,
                    "as_of": (
                        synthesis_time - dt.timedelta(days=4)
                    ).isoformat(),
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ReviewWorkflowError, match="stale"):
        synthesize_review(
            runs_root=runs_root,
            research_root=tmp_path / "research",
            policy_root=policy_root,
            run_id=run_id,
            quotes_path=quotes_path,
            synthesized_at=synthesis_time,
        )

    store = ReviewRunStore(runs_root)
    assert store.load_run(run_id)["status"] == "stale_quotes"
    assert not (
        tmp_path / "research" / "batches" / run_id / "portfolio.json"
    ).exists()

    resumed = resume_review(
        runs_root=runs_root,
        run_id=run_id,
        resumed_at=synthesis_time + dt.timedelta(seconds=1),
    )
    assert resumed["status"] == "company_reviews_complete"
    fresh_time = synthesis_time + dt.timedelta(seconds=2)
    quotes_path.write_text(
        json.dumps(
            [
                {
                    "symbol": "CN:600519",
                    "price": activation - 0.5,
                    "as_of": fresh_time.isoformat(),
                }
            ]
        ),
        encoding="utf-8",
    )
    synthesize_review(
        runs_root=runs_root,
        research_root=tmp_path / "research",
        policy_root=policy_root,
        run_id=run_id,
        quotes_path=quotes_path,
        synthesized_at=fresh_time,
    )
    portfolio = json.loads(
        (
            tmp_path / "research" / "batches" / run_id / "portfolio.json"
        ).read_text(encoding="utf-8")
    )
    assert portfolio["positions"][0]["action"] == "buy_now"

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from automation.scripts.review_dispatch import AgentResult, ReviewDispatcher
from tests.test_company_assets import write_company

NOW = dt.datetime.fromisoformat("2026-07-21T09:01:00+08:00")
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "underwriting" / "conflicting-seven"


def _cases() -> list[dict[str, Any]]:
    return json.loads((FIXTURE_ROOT / "cases.json").read_text(encoding="utf-8"))


def _policy_root(tmp_path: Path) -> Path:
    root = tmp_path / "policies"
    root.mkdir()
    shutil.copyfile("policies/underwriting.json", root / "underwriting.json")
    portfolio_path = root / "portfolio.json"
    shutil.copyfile("policies/portfolio.json", portfolio_path)
    portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
    portfolio["payload"]["max_economic_risk_cluster_weight"] = 0.05
    portfolio_path.write_text(
        json.dumps(portfolio, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return root


def _write_case_company(tmp_path: Path, case: dict[str, Any]) -> Path:
    from trading_os.research_assets.sealing import seal_json

    ticker = case["symbol"].split(":", 1)[1]
    seed = write_company(tmp_path / f"seed-{case['case_id']}")
    company_dir = seed.with_name(ticker)
    seed.rename(company_dir)

    report_path = company_dir / "reports" / "2026-07-21-initial-research.md"
    report_text = report_path.read_text(encoding="utf-8")
    report_text = report_text.replace(
        '"symbol": "CN:600519"',
        f'"symbol": "{case["symbol"]}"',
    ).replace(
        '"sealed_artifacts": []',
        '"sealed_artifacts": [\n    "evidence/research-claims.json"\n  ]',
    )
    report_lines = report_text.splitlines()
    title_index = next(
        index for index, line in enumerate(report_lines) if line.startswith("# ")
    )
    report_lines[title_index] = f"# 公司研究：{case['name']}（{case['symbol']}）"
    report_text = "\n".join(report_lines) + "\n"
    report_path.write_text(report_text, encoding="utf-8")

    claims = {
        "schema_version": 2,
        "report_id": f"fixture-{case['case_id']}",
        "symbol": case["symbol"],
        "claims": [
            {
                "claim_id": f"claim-{case['case_id']}",
                "category": "investment",
                "claim": "该经营主张需要用原始披露和现金流证据重新核验。",
                "verification_metrics": ["经营现金流与利润的匹配关系"],
                "falsifiers": ["原始披露无法支持该经营主张"],
                "source_ids": ["filing"],
            }
        ],
        "sources": [
            {
                "source_id": "filing",
                "tier": "S1",
                "uri_or_path": "sources/filing.pdf",
            }
        ],
        "decision": {
            "rating": "legacy-watch",
            "fair_value_range": case["prior_fair_value_range"],
            "buy_zone": [50.0, 60.0],
            "reduce_zone": [180.0, 190.0],
            "conclusion": f"legacy-conclusion-{case['case_id']}",
        },
    }
    seal_json(
        company_dir / "evidence" / "research-claims.json",
        claims,
        artifact_type="research_claims",
        sealed_at=NOW,
    )

    meta_path = company_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["identity"].update(
        {
            "symbol": case["symbol"],
            "ticker": ticker,
            "name": case["name"],
        }
    )
    meta["reports"]["history"][0]["sha256"] = hashlib.sha256(
        report_path.read_bytes()
    ).hexdigest()
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return company_dir


def _assessment(case: dict[str, Any]) -> dict[str, Any]:
    fair = case["fair_value_range"]
    fair_midpoint = sum(fair) / 2
    assessment: dict[str, Any] = {
        "confidence": "high",
        "cyclical_or_governance_risk": False,
        "normalization": {
            "method": "five_year_mid_cycle",
            "years_used": 5,
            "single_quarter_annualized": False,
            "peak_profit_used": False,
            "normalized_profit": 100.0,
        },
        "accounting_checks": {
            "nonrecurring_items_handled": True,
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
                {"name": "dcf", "value": fair_midpoint - 5},
                {"name": "normalized_pe", "value": fair_midpoint + 5},
            ],
            "scenarios": {
                "bear": case["buy_zone"][0] - 10,
                "base": fair_midpoint,
                "bull": fair[1] + 20,
            },
            "fair_value_range": fair,
            "buy_zone": case["buy_zone"],
            "formulas_reproducible": True,
            "sensitivity_complete": True,
            "market_implied_assumptions_complete": True,
            "government_bond_yield": 0.03,
            "equity_cost": 0.11,
            "required_return_used": 0.11,
        },
        "counterevidence": ["需求下行", "成本上升", "竞争加剧"],
        "claim_reviews": [
            {
                "claim_id": f"claim-{case['case_id']}",
                "category": "investment",
                "result": "confirmed",
            }
        ],
        "risk_flags": {
            "governance_material_doubt": False,
            "cycle_position_uncertain": False,
            "permanent_loss_risk": False,
        },
    }
    if case["defect"] == "nonrecurring_items_unhandled":
        assessment["accounting_checks"]["nonrecurring_items_handled"] = False
    elif case["defect"] == "peak_profit_used":
        assessment["normalization"]["peak_profit_used"] = True
    elif case["defect"] == "cash_flow_divergence_unexplained":
        assessment["accounting_checks"]["cash_flow_divergence_explained"] = False
    return assessment


def _portfolio_candidate(
    case: dict[str, Any], status: str, reason_codes: tuple[str, ...]
) -> dict[str, Any]:
    assessment = _assessment(case)
    valuation = assessment["valuation"]
    reasons = list(reason_codes) or [f"underwriting_{status}"]
    return {
        "symbol": case["symbol"],
        "name": case["name"],
        "underwriting_status": status,
        "evidence_stale": False,
        "portfolio_eligible": True,
        "current_price": case["initial_price"],
        "bear_value": valuation["scenarios"]["bear"],
        "fair_value_range": case["fair_value_range"],
        "buy_zone": case["buy_zone"],
        "reduce_zone": [case["fair_value_range"][1] + 20, case["fair_value_range"][1] + 30],
        "confidence": "high",
        "industry": f"fixture-industry-{case['case_id']}",
        "economic_risk_clusters": [case["risk_cluster"]],
        "expected_annual_return": 0.18,
        "bear_case_loss_fraction": 0.20,
        "allowed_loss_weight": 0.01,
        "rank_score": case["rank_score"],
        "held": False,
        "reason_codes": reasons,
    }


class FixtureRunner:
    def __init__(self, cases: list[dict[str, Any]], *, timeout_symbol: str | None = None):
        self.cases = {case["symbol"]: case for case in cases}
        self.timeout_symbol = timeout_symbol
        self.timeout_consumed = False
        self.tasks = []

    def run(self, task):
        from trading_os.research_assets.evidence import EvidenceValidationResult
        from trading_os.research_assets.underwriting import evaluate_underwriting

        self.tasks.append(task)
        case = self.cases[task.symbol]
        if task.stage == "blind":
            assert f"legacy-conclusion-{case['case_id']}" not in task.prompt
            assert '"position_plan"' not in task.prompt
            if task.symbol == self.timeout_symbol and not self.timeout_consumed:
                self.timeout_consumed = True
                return AgentResult(ok=False, error="simulated timeout")
            return AgentResult(ok=True, payload=_assessment(case))
        if task.stage == "reveal":
            evaluation = evaluate_underwriting(
                _assessment(case),
                evidence=EvidenceValidationResult(True, False, (), ()),
                prior_claim_ids={f"claim-{case['case_id']}"},
                prior_fair_value_range=case["prior_fair_value_range"],
            )
            assert (evaluation.status == "needs_challenger") is case["challenger"]
            reasons = evaluation.blockers + evaluation.challenger_triggers
            return AgentResult(
                ok=True,
                payload={
                    "challenger_required": case["challenger"],
                    "challenger_reasons": list(evaluation.challenger_triggers),
                    "claim_reviews": _assessment(case)["claim_reviews"],
                    "underwriting_status": evaluation.status,
                    "reason_codes": list(reasons) or ["underwriting_passed"],
                    "portfolio_candidate": _portfolio_candidate(
                        case,
                        evaluation.status,
                        reasons,
                    ),
                },
            )
        if task.stage == "challenger":
            assert "normalized_profit" not in task.prompt
            assert "legacy-conclusion" not in task.prompt
            return AgentResult(
                ok=True,
                payload={"symbol": task.symbol, "independent_value": 155.0},
            )
        if task.stage == "arbitration":
            assert "independent_value" in task.prompt
            return AgentResult(
                ok=True,
                payload={
                    "underwriting_status": "passed",
                    "reason_codes": ["challenger_resolved"],
                    "claim_reviews": _assessment(case)["claim_reviews"],
                    "portfolio_candidate": _portfolio_candidate(
                        case,
                        "passed",
                        ("challenger_resolved",),
                    ),
                },
            )
        raise AssertionError(task.stage)


def _setup_review(
    tmp_path: Path,
    cases: list[dict[str, Any]],
    *,
    run_id: str,
) -> tuple[Path, Path, list[dict[str, Any]]]:
    from trading_os.research_assets.review_workflow import create_review, prepare_review

    companies = [_write_case_company(tmp_path, case) for case in cases]
    candidates = [
        {
            "symbol": case["symbol"],
            "name": case["name"],
            "target_company_dir": str(company),
        }
        for case, company in zip(cases, companies, strict=True)
    ]
    policy_root = _policy_root(tmp_path)
    runs_root = tmp_path / "automation" / "runs"
    create_review(
        runs_root=runs_root,
        run_id=run_id,
        scope_type="industry",
        market="CN",
        description="匿名冲突案例",
        candidates=candidates,
        policy_root=policy_root,
        created_at=NOW,
    )
    prepare_review(runs_root=runs_root, run_id=run_id, prepared_at=NOW)
    return runs_root, policy_root, candidates


def _dispatcher(
    runs_root: Path,
    policy_root: Path,
    runner: FixtureRunner,
) -> ReviewDispatcher:
    return ReviewDispatcher(
        runs_root=runs_root,
        policy_root=policy_root,
        runner=runner,
        concurrency=4,
        timeout_seconds=60,
        lease_seconds=120,
    )


def _write_quotes(path: Path, cases: list[dict[str, Any]], *, as_of: dt.datetime) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "symbol": case["symbol"],
                    "price": case["quote_price"],
                    "as_of": as_of.isoformat(),
                }
                for case in cases
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_conflicting_seven_complete_half_blind_underwriting_and_portfolio(tmp_path: Path):
    from trading_os.research_assets.review_store import ReviewRunStore, ReviewStoreError
    from trading_os.research_assets.review_workflow import (
        synthesize_review,
        write_review_report,
    )
    from trading_os.research_assets.sealing import verify_sealed

    cases = _cases()
    run_id = "conflicting-seven"
    runs_root, policy_root, candidates = _setup_review(tmp_path, cases, run_id=run_id)
    store = ReviewRunStore(runs_root)
    frozen_hash = store.load_run(run_id)["candidate_set"]["sha256"]
    changed = copy.deepcopy(candidates)
    changed[0]["name"] = "不得修改"
    with pytest.raises(ReviewStoreError, match="frozen"):
        store.freeze_candidates(run_id, changed, actor="test", at=NOW)

    for candidate in candidates:
        packet_path = (
            Path(candidate["target_company_dir"])
            / "underwriting"
            / run_id
            / "claim-packet.json"
        )
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        serialized = json.dumps(packet, ensure_ascii=False)
        assert "decision" not in packet
        assert "fair_value_range" not in serialized
        assert "position_plan" not in serialized
        assert verify_sealed(packet_path).artifact_type == "claim_packet"

    runner = FixtureRunner(cases, timeout_symbol="CN:000002")
    dispatcher = _dispatcher(runs_root, policy_root, runner)
    first = dispatcher.dispatch(run_id, now=NOW)
    assert first.status == "blind_reviewing"
    assert first.failed == (("CN:000002", "simulated timeout"),)
    assert len(first.completed) == 6

    second = dispatcher.dispatch(run_id, now=NOW + dt.timedelta(seconds=1))
    assert second.status == "blind_sealed"
    assert sum(task.stage == "blind" for task in runner.tasks) == 8
    assert sum(
        task.stage == "blind" and task.symbol == "CN:000001" for task in runner.tasks
    ) == 1

    reveal = dispatcher.dispatch(run_id, now=NOW + dt.timedelta(seconds=2))
    assert reveal.status == "challenging"
    final = dispatcher.dispatch(run_id, now=NOW + dt.timedelta(seconds=3))
    assert final.status == "company_reviews_complete"
    assert [task.stage for task in runner.tasks if task.symbol == "CN:000004"] == [
        "blind",
        "reveal",
        "challenger",
        "arbitration",
    ]
    assert all(
        task.stage not in {"challenger", "arbitration"} or task.symbol == "CN:000004"
        for task in runner.tasks
    )

    quotes_path = tmp_path / "quotes.json"
    synthesis_time = NOW + dt.timedelta(minutes=1)
    _write_quotes(quotes_path, cases, as_of=synthesis_time)
    synthesize_review(
        runs_root=runs_root,
        research_root=tmp_path / "research-output",
        policy_root=policy_root,
        run_id=run_id,
        quotes_path=quotes_path,
        synthesized_at=synthesis_time,
    )
    portfolio_path = tmp_path / "research-output" / "batches" / run_id / "portfolio.json"
    portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
    positions = {item["symbol"]: item for item in portfolio["positions"]}

    assert {symbol: item["action"] for symbol, item in positions.items()} == {
        case["symbol"]: case["expected_action"] for case in cases
    }
    assert {symbol: item["underwriting_status"] for symbol, item in positions.items()} == {
        case["symbol"]: case["expected_underwriting"] for case in cases
    }
    assert "price_change_invalidated_conclusion" in positions["CN:000004"]["reason_codes"]
    assert "risk_cluster_limit_exhausted" in positions["CN:000005"]["reason_codes"]
    assert positions["CN:000006"]["target_weight"] == pytest.approx(0.05)
    assert positions["CN:000006"]["initial_entry_weight"] == pytest.approx(0.05 / 3)
    assert {item["symbol"] for item in portfolio["exclusions"]} == {
        "CN:000001",
        "CN:000002",
        "CN:000003",
        "CN:000004",
        "CN:000005",
        "CN:000007",
    }
    assert all(
        positions[symbol]["action"] != "buy_now"
        for symbol in ("CN:000001", "CN:000002", "CN:000003", "CN:000004")
    )
    assert all(
        {
            "current_price",
            "bear_value",
            "fair_value_range",
            "buy_zone",
            "underwriting_status",
            "action",
            "target_weight",
            "initial_entry_weight",
        }
        <= set(item)
        for item in positions.values()
    )
    assert store.load_run(run_id)["candidate_set"]["sha256"] == frozen_hash

    report = write_review_report(
        runs_root=runs_root,
        research_root=tmp_path / "research-output",
        run_id=run_id,
        reported_at=synthesis_time + dt.timedelta(seconds=1),
    )
    assert report["status"] == "completed"
    assert report["company_finalization"]["synced_count"] == len(cases)
    report_text = Path(report["path"]).read_text(encoding="utf-8")
    assert "匿名案例 F（CN:000006）" in report_text
    assert "置信度" in report_text

    for case, candidate in zip(cases, candidates, strict=True):
        meta = json.loads(
            (Path(candidate["target_company_dir"]) / "meta.json").read_text(
                encoding="utf-8"
            )
        )
        decision = positions[case["symbol"]]
        expected_status = (
            "stale"
            if decision["underwriting_status"] == "passed"
            and decision["evidence_stale"]
            else decision["underwriting_status"]
        )
        assert meta["underwriting"]["status"] == expected_status
        assert meta["underwriting"]["review_id"] == run_id
        assert meta["valuation"]["fair_value_range"] == decision["fair_value_range"]
        assert meta["valuation"]["buy_zone"] == decision["buy_zone"]
        assert meta["valuation"]["price_as_of"] == synthesis_time.isoformat()

    repeated = write_review_report(
        runs_root=runs_root,
        research_root=tmp_path / "research-output",
        run_id=run_id,
        reported_at=synthesis_time + dt.timedelta(minutes=2),
    )
    assert repeated["company_finalization"]["already_finalized"] is True


def test_tampered_blind_artifact_cannot_reach_reveal_or_buy(tmp_path: Path):
    from trading_os.research_assets.sealing import SealingError, verify_sealed

    case = next(item for item in _cases() if item["case_id"] == "F")
    run_id = "tampered-blind"
    runs_root, policy_root, candidates = _setup_review(tmp_path, [case], run_id=run_id)
    runner = FixtureRunner([case])
    dispatcher = _dispatcher(runs_root, policy_root, runner)
    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"

    blind_path = (
        Path(candidates[0]["target_company_dir"])
        / "underwriting"
        / run_id
        / "blind-assessment.json"
    )
    blind_path.write_bytes(blind_path.read_bytes() + b" ")
    with pytest.raises(SealingError, match="sha256"):
        verify_sealed(blind_path)

    result = dispatcher.dispatch(run_id, now=NOW + dt.timedelta(seconds=1))
    assert result.status == "revealing"
    assert result.failed and "sha256" in result.failed[0][1]
    assert not any(task.stage == "reveal" for task in runner.tasks)
    assert not (
        Path(candidates[0]["target_company_dir"])
        / "underwriting"
        / run_id
        / "portfolio-candidate.json"
    ).exists()


def test_stale_quotes_require_resume_and_fresh_snapshot_before_buy(tmp_path: Path):
    from trading_os.research_assets.review_store import ReviewRunStore
    from trading_os.research_assets.review_workflow import (
        ReviewWorkflowError,
        resume_review,
        synthesize_review,
    )

    case = next(item for item in _cases() if item["case_id"] == "F")
    run_id = "stale-quote-resume"
    runs_root, policy_root, _ = _setup_review(tmp_path, [case], run_id=run_id)
    runner = FixtureRunner([case])
    dispatcher = _dispatcher(runs_root, policy_root, runner)
    assert dispatcher.dispatch(run_id, now=NOW).status == "blind_sealed"
    assert (
        dispatcher.dispatch(run_id, now=NOW + dt.timedelta(seconds=1)).status
        == "company_reviews_complete"
    )

    synthesis_time = NOW + dt.timedelta(minutes=1)
    quotes_path = tmp_path / "quotes.json"
    _write_quotes(
        quotes_path,
        [case],
        as_of=synthesis_time - dt.timedelta(days=4),
    )
    with pytest.raises(ReviewWorkflowError, match="stale"):
        synthesize_review(
            runs_root=runs_root,
            research_root=tmp_path / "research-output",
            policy_root=policy_root,
            run_id=run_id,
            quotes_path=quotes_path,
            synthesized_at=synthesis_time,
        )
    store = ReviewRunStore(runs_root)
    assert store.load_run(run_id)["status"] == "stale_quotes"
    assert not (
        tmp_path / "research-output" / "batches" / run_id / "portfolio.json"
    ).exists()

    resumed = resume_review(
        runs_root=runs_root,
        run_id=run_id,
        resumed_at=synthesis_time + dt.timedelta(seconds=1),
    )
    assert resumed["status"] == "company_reviews_complete"
    _write_quotes(
        quotes_path,
        [case],
        as_of=synthesis_time + dt.timedelta(seconds=2),
    )
    synthesize_review(
        runs_root=runs_root,
        research_root=tmp_path / "research-output",
        policy_root=policy_root,
        run_id=run_id,
        quotes_path=quotes_path,
        synthesized_at=synthesis_time + dt.timedelta(seconds=2),
    )
    portfolio_path = tmp_path / "research-output" / "batches" / run_id / "portfolio.json"
    portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
    assert portfolio["positions"][0]["action"] == "buy_now"

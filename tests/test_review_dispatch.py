from __future__ import annotations

import datetime as dt
import subprocess
import threading
import time
from pathlib import Path

import pytest

from automation.scripts.build_review_prompt import (
    PromptBuildError,
    build_synthesis_prompt,
    render_prompt,
)
from automation.scripts.review_dispatch import (
    AgentResult,
    DispatchError,
    ReviewDispatcher,
    SubprocessRunner,
)
from tests.test_cli import T0, T1, _attach_research_claims
from tests.test_company_assets import write_company

NOW = dt.datetime.fromisoformat(T1)


def _portfolio_candidate(symbol: str = "CN:600519") -> dict[str, object]:
    return {
        "symbol": symbol,
        "name": symbol,
        "underwriting_status": "passed",
        "evidence_stale": False,
        "portfolio_eligible": True,
        "current_price": 75.0,
        "bear_value": 60.0,
        "fair_value_range": [95.0, 105.0],
        "buy_zone": [70.0, 80.0],
        "reduce_zone": [120.0, 130.0],
        "confidence": "high",
        "industry": "食品饮料",
        "economic_risk_clusters": ["premium_consumption"],
        "expected_annual_return": 0.18,
        "bear_case_loss_fraction": 0.20,
        "allowed_loss_weight": 0.01,
        "rank_score": 90.0,
        "held": False,
        "reason_codes": ["underwriting_passed"],
    }


def _reveal_payload(symbol: str, *, challenger: bool) -> dict[str, object]:
    return {
        "challenger_required": challenger,
        "challenger_reasons": ["material_disagreement"] if challenger else [],
        "claim_reviews": [
            {
                "claim_id": "claim-business-quality",
                "category": "business",
                "result": "confirmed",
            }
        ],
        "underwriting_status": "needs_challenger" if challenger else "passed",
        "reason_codes": ["independent_review_complete"],
        "portfolio_candidate": _portfolio_candidate(symbol),
    }


def _arbitration_payload(symbol: str) -> dict[str, object]:
    return {
        "underwriting_status": "passed",
        "reason_codes": ["challenger_resolved"],
        "claim_reviews": [
            {
                "claim_id": "claim-business-quality",
                "category": "business",
                "result": "confirmed",
            }
        ],
        "portfolio_candidate": _portfolio_candidate(symbol),
    }


class RecordingRunner:
    def __init__(self, *, challenger: bool = False):
        self.challenger = challenger
        self.tasks = []

    def run(self, task):
        self.tasks.append(task)
        if task.stage == "blind":
            return AgentResult(
                ok=True,
                payload={"symbol": task.symbol, "marker": "PRIMARY_SECRET"},
            )
        if task.stage == "reveal":
            return AgentResult(
                ok=True,
                payload=_reveal_payload(task.symbol, challenger=self.challenger),
            )
        if task.stage == "challenger":
            assert "PRIMARY_SECRET" not in task.prompt
            assert "等待安全边际" not in task.prompt
            assert [path.name for path in task.allowed_read_paths] == [
                "claim-packet.json"
            ]
            return AgentResult(
                ok=True,
                payload={"symbol": task.symbol, "marker": "CHALLENGER_SECRET"},
            )
        if task.stage == "arbitration":
            assert "PRIMARY_SECRET" in task.prompt
            assert "CHALLENGER_SECRET" in task.prompt
            return AgentResult(ok=True, payload=_arbitration_payload(task.symbol))
        raise AssertionError(task.stage)


def _prepared_review(tmp_path: Path):
    from trading_os.research_assets.review_workflow import create_review, prepare_review

    company_dir = write_company(tmp_path)
    _attach_research_claims(company_dir)
    runs_root = tmp_path / "automation" / "runs"
    policy_root = Path("policies").resolve()
    create_review(
        runs_root=runs_root,
        run_id="memory-2026-07-21",
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
    prepare_review(
        runs_root=runs_root,
        run_id="memory-2026-07-21",
        prepared_at=NOW,
    )
    return runs_root, policy_root, company_dir


def _manual_packet_run(tmp_path: Path, symbols: list[str]):
    from trading_os.research_assets.review_store import ReviewRunStore
    from trading_os.research_assets.sealing import seal_json

    runs_root = tmp_path / "automation" / "runs"
    store = ReviewRunStore(runs_root)
    store.create_run(
        "parallel-run",
        scope={"type": "custom", "market": "CN", "description": "parallel"},
        policy_versions={"underwriting.default": "1.0.0"},
        created_at=NOW,
    )
    candidates = []
    for symbol in symbols:
        company_dir = tmp_path / "companies" / symbol.replace(":", "-")
        candidates.append(
            {"symbol": symbol, "name": symbol, "target_company_dir": str(company_dir)}
        )
    store.freeze_candidates("parallel-run", candidates, actor="test", at=NOW)
    for candidate in candidates:
        packet_path = (
            Path(candidate["target_company_dir"])
            / "underwriting"
            / "parallel-run"
            / "claim-packet.json"
        )
        seal_json(
            packet_path,
            {"schema_version": 2, "symbol": candidate["symbol"], "claims": []},
            artifact_type="claim_packet",
            sealed_at=NOW,
        )
    store.transition("parallel-run", "packets_ready", actor="test", at=NOW)
    return runs_root, Path("policies").resolve(), store


def test_blind_prompt_contains_packet_but_not_prior_decision(tmp_path: Path):
    runs_root, policy_root, _ = _prepared_review(tmp_path)
    runner = RecordingRunner()
    dispatcher = ReviewDispatcher(
        runs_root=runs_root,
        policy_root=policy_root,
        runner=runner,
        timeout_seconds=60,
        lease_seconds=120,
    )

    result = dispatcher.dispatch("memory-2026-07-21", now=NOW)

    assert result.status == "blind_sealed"
    prompt = runner.tasks[0].prompt
    assert "claim-business-quality" in prompt
    assert "等待安全边际" not in prompt
    assert '"position_plan"' not in prompt
    assert "2026-07-21-initial-research.md" not in prompt


def test_full_dispatch_serializes_company_phases_and_arbitrates_challenge(
    tmp_path: Path,
):
    runs_root, policy_root, company_dir = _prepared_review(tmp_path)
    runner = RecordingRunner(challenger=True)
    dispatcher = ReviewDispatcher(
        runs_root=runs_root,
        policy_root=policy_root,
        runner=runner,
        timeout_seconds=60,
        lease_seconds=120,
    )

    assert dispatcher.dispatch("memory-2026-07-21", now=NOW).status == "blind_sealed"
    assert dispatcher.dispatch("memory-2026-07-21", now=NOW).status == "challenging"
    final = dispatcher.dispatch("memory-2026-07-21", now=NOW)

    assert final.status == "company_reviews_complete"
    assert [task.stage for task in runner.tasks] == [
        "blind",
        "reveal",
        "challenger",
        "arbitration",
    ]
    assert (
        company_dir
        / "underwriting"
        / "memory-2026-07-21"
        / "portfolio-candidate.json"
    ).is_file()


def test_different_companies_run_concurrently(tmp_path: Path):
    runs_root, policy_root, _ = _manual_packet_run(
        tmp_path, ["CN:000001", "CN:000002"]
    )

    class ConcurrentRunner:
        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.lock = threading.Lock()

        def run(self, task):
            with self.lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            time.sleep(0.05)
            with self.lock:
                self.active -= 1
            return AgentResult(ok=True, payload={"symbol": task.symbol, "ok": True})

    runner = ConcurrentRunner()
    dispatcher = ReviewDispatcher(
        runs_root=runs_root,
        policy_root=policy_root,
        runner=runner,
        concurrency=2,
        timeout_seconds=60,
        lease_seconds=120,
    )

    result = dispatcher.dispatch("parallel-run", now=NOW)

    assert result.status == "blind_sealed"
    assert runner.max_active == 2


def test_agent_failure_is_isolated_and_resume_skips_completed_work(tmp_path: Path):
    runs_root, policy_root, _ = _manual_packet_run(
        tmp_path, ["CN:000001", "CN:000002"]
    )

    class FlakyRunner:
        def __init__(self):
            self.fail = True
            self.calls: list[str] = []

        def run(self, task):
            self.calls.append(task.symbol)
            if self.fail and task.symbol == "CN:000002":
                return AgentResult(ok=False, error="simulated timeout")
            return AgentResult(ok=True, payload={"symbol": task.symbol, "ok": True})

    runner = FlakyRunner()
    dispatcher = ReviewDispatcher(
        runs_root=runs_root,
        policy_root=policy_root,
        runner=runner,
        concurrency=2,
        timeout_seconds=60,
        lease_seconds=120,
    )

    first = dispatcher.dispatch("parallel-run", now=NOW)
    assert first.status == "blind_reviewing"
    assert first.failed[0][0] == "CN:000002"

    runner.fail = False
    second = dispatcher.dispatch("parallel-run", now=NOW + dt.timedelta(seconds=1))

    assert second.status == "blind_sealed"
    assert runner.calls.count("CN:000001") == 1
    assert runner.calls.count("CN:000002") == 2


def test_phase_prompt_contract_rejects_extra_cross_stage_data():
    with pytest.raises(PromptBuildError, match="unknown"):
        render_prompt(
            "challenger",
            {
                "company_name": "测试",
                "symbol": "CN:000001",
                "output_path": "out.json",
                "claim_packet": {},
                "underwriting_policy": {},
                "primary_review": {"secret": True},
            },
        )


def test_synthesis_prompt_is_gated_by_state_and_sealed_machine_outputs(tmp_path: Path):
    from trading_os.research_assets.sealing import seal_json

    runs_root, policy_root, store = _manual_packet_run(tmp_path, ["CN:000001"])
    with pytest.raises(PromptBuildError, match="completed company reviews"):
        build_synthesis_prompt(
            run_id="parallel-run",
            runs_root=runs_root,
            research_root=tmp_path / "research",
            policy_root=policy_root,
            output_path=tmp_path / "synthesis.md",
        )

    for status in (
        "blind_reviewing",
        "blind_sealed",
        "revealing",
        "company_reviews_complete",
        "synthesizing",
    ):
        store.transition("parallel-run", status, actor="test", at=NOW)
    batch_dir = tmp_path / "research" / "batches" / "parallel-run"
    seal_json(
        batch_dir / "quotes.json",
        [{"symbol": "CN:000001", "price": 10.0}],
        artifact_type="quote_snapshot",
        sealed_at=NOW,
    )
    seal_json(
        batch_dir / "portfolio.json",
        {"schema_version": 2, "positions": [], "cash_weight": 1.0},
        artifact_type="model_portfolio",
        sealed_at=NOW,
    )

    prompt = build_synthesis_prompt(
        run_id="parallel-run",
        runs_root=runs_root,
        research_root=tmp_path / "research",
        policy_root=policy_root,
        output_path=tmp_path / "synthesis.md",
    )

    assert '"cash_weight": 1.0' in prompt
    assert "不得修改操作、仓位和排除原因" in prompt


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
            runner=RecordingRunner(),
            timeout_seconds=60,
            lease_seconds=60,
        )

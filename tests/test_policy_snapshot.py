from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from automation.scripts.build_review_prompt import build_run_prompt


NOW = dt.datetime.fromisoformat("2026-07-25T12:00:00+08:00")
POLICY_FIELDS = {
    "schema_version",
    "policy_id",
    "version",
    "effective_at",
    "kind",
    "payload",
}


def test_create_review_seals_every_complete_policy_record(tmp_path: Path):
    from trading_os.research_assets.policy_snapshot import (
        load_review_policy_snapshot,
    )
    from trading_os.research_assets.review_store import ReviewRunStore
    from trading_os.research_assets.review_workflow import create_review
    from trading_os.research_assets.sealing import verify_sealed

    runs_root = tmp_path / "automation" / "runs"
    run_id = "policy-snapshot-2026-07-25"
    create_review(
        runs_root=runs_root,
        run_id=run_id,
        scope_type="custom",
        market="CN",
        description="policy snapshot test",
        candidates=[
            {
                "symbol": "CN:600519",
                "name": "贵州茅台",
                "target_company_dir": str(tmp_path / "company"),
            }
        ],
        policy_root=Path("policies"),
        created_at=NOW,
    )

    path = runs_root / run_id / "policy-snapshot.json"
    seal = verify_sealed(path)
    assert seal.artifact_type == "review_policy_snapshot"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["run_id"] == run_id
    assert raw["policies"]
    assert all(set(record) == POLICY_FIELDS for record in raw["policies"].values())

    state = ReviewRunStore(runs_root).load_run(run_id)
    loaded = load_review_policy_snapshot(
        runs_root=runs_root,
        run_id=run_id,
        state=state,
    )
    assert loaded.sha256 == seal.sha256
    assert dict(loaded.policy_versions) == state["policy_versions"]


def test_prompt_uses_sealed_snapshot_when_live_policy_root_is_unavailable(
    tmp_path: Path,
):
    from tests.test_review_dispatch import _prepared_review

    runs_root, _, _, run_id = _prepared_review(tmp_path)
    prompt = build_run_prompt(
        stage="blind",
        run_id=run_id,
        symbol="CN:600519",
        runs_root=runs_root,
        policy_root=tmp_path / "deleted-live-policy-root",
    )

    assert '"minimum_valuation_discount_rate": 0.085' in prompt


def test_synthesis_uses_snapshot_and_links_portfolio_to_its_hash(tmp_path: Path):
    from tests.test_underwriting_e2e import (
        _activation_price,
        _complete_company_review,
    )
    from trading_os.research_assets.policy_snapshot import (
        load_review_policy_snapshot,
    )
    from trading_os.research_assets.review_store import ReviewRunStore
    from trading_os.research_assets.review_workflow import (
        ReviewWorkflowError,
        _validate_portfolio_payload,
        synthesize_review,
    )

    runs_root, _, _, run_id = _complete_company_review(
        tmp_path,
        initial_price=_activation_price() - 0.5,
    )
    quotes_path = tmp_path / "quotes.json"
    quotes_path.write_text(
        json.dumps(
            [
                {
                    "symbol": "CN:600519",
                    "price": _activation_price() - 0.75,
                    "as_of": NOW.isoformat(),
                }
            ]
        ),
        encoding="utf-8",
    )
    synthesize_review(
        runs_root=runs_root,
        research_root=tmp_path / "research",
        policy_root=tmp_path / "deleted-live-policy-root",
        run_id=run_id,
        quotes_path=quotes_path,
        synthesized_at=NOW,
    )

    state = ReviewRunStore(runs_root).load_run(run_id)
    snapshot = load_review_policy_snapshot(
        runs_root=runs_root,
        run_id=run_id,
        state=state,
    )
    portfolio = json.loads(
        (
            tmp_path / "research" / "batches" / run_id / "portfolio.json"
        ).read_text(encoding="utf-8")
    )
    assert portfolio["policy_snapshot_sha256"] == snapshot.sha256
    mismatched = dict(portfolio)
    mismatched["policy_snapshot_sha256"] = "0" * 64
    with pytest.raises(ReviewWorkflowError, match="does not match"):
        _validate_portfolio_payload(
            mismatched,
            expected_policy_snapshot_sha256=snapshot.sha256,
        )

    null_snapshot = dict(portfolio)
    null_snapshot["policy_snapshot_sha256"] = None
    with pytest.raises(ReviewWorkflowError, match="is invalid"):
        _validate_portfolio_payload(
            null_snapshot,
            expected_policy_snapshot_sha256=snapshot.sha256,
        )

    with pytest.raises(
        ReviewWorkflowError,
        match="expected policy_snapshot_sha256 is invalid",
    ):
        _validate_portfolio_payload(
            portfolio,
            expected_policy_snapshot_sha256=None,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("legacy_hash", ["missing", None])
def test_old_run_without_valid_policy_snapshot_hash_fails_explicitly(
    tmp_path: Path,
    legacy_hash,
):
    from trading_os.research_assets.review_store import ReviewRunStore
    from trading_os.research_assets.review_workflow import (
        ReviewWorkflowError,
        validate_review,
    )

    runs_root = tmp_path / "runs"
    run_id = "old-run-without-snapshot"
    store = ReviewRunStore(runs_root)
    store.create_run(
        run_id,
        scope={"type": "custom", "market": "CN", "description": "legacy"},
        policy_versions={"underwriting.default": "1.0.0"},
        policy_snapshot_sha256="f" * 64,
        created_at=NOW,
    )
    store.freeze_candidates(
        run_id,
        [
            {
                "symbol": "CN:600519",
                "name": "贵州茅台",
                "target_company_dir": str(tmp_path / "company"),
            }
        ],
        actor="test",
        at=NOW,
    )
    state_path = runs_root / run_id / "state.json"
    legacy_state = json.loads(state_path.read_text(encoding="utf-8"))
    if legacy_hash == "missing":
        legacy_state.pop("policy_snapshot_sha256")
    else:
        legacy_state["policy_snapshot_sha256"] = legacy_hash
    state_path.write_text(
        json.dumps(legacy_state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ReviewWorkflowError, match="policy_snapshot_sha256"):
        validate_review(runs_root=runs_root, run_id=run_id, strict=False)


def test_snapshot_rejects_incomplete_policy_and_state_version_drift(tmp_path: Path):
    from trading_os.research_assets.policy_snapshot import (
        PolicySnapshotError,
        load_review_policy_snapshot,
    )
    from trading_os.research_assets.review_store import ReviewRunStore
    from trading_os.research_assets.sealing import (
        canonical_json_bytes,
        seal_json,
    )
    import hashlib

    runs_root = tmp_path / "runs"
    run_id = "incomplete-policy-snapshot"
    store = ReviewRunStore(runs_root)
    malformed_snapshot = {
        "schema_version": 1,
        "run_id": run_id,
        "policies": {
            "underwriting.default": {
                "schema_version": 2,
                "policy_id": "underwriting.default",
                "version": "2.0.0",
                "effective_at": NOW.isoformat(),
                "kind": "underwriting",
            }
        },
    }
    state = store.create_run(
        run_id,
        scope={"type": "custom", "market": "CN", "description": "invalid"},
        policy_versions={"underwriting.default": "2.0.0"},
        policy_snapshot_sha256=hashlib.sha256(
            canonical_json_bytes(malformed_snapshot)
        ).hexdigest(),
        created_at=NOW,
    )
    seal_json(
        runs_root / run_id / "policy-snapshot.json",
        malformed_snapshot,
        artifact_type="review_policy_snapshot",
        sealed_at=NOW,
    )

    with pytest.raises(PolicySnapshotError, match="incomplete"):
        load_review_policy_snapshot(
            runs_root=runs_root,
            run_id=run_id,
            state=state,
        )


def test_snapshot_rejects_state_policy_version_mismatch(tmp_path: Path):
    from trading_os.research_assets.policy_snapshot import (
        PolicySnapshotError,
        build_policy_snapshot,
        load_review_policy_snapshot,
        seal_review_policy_snapshot,
    )
    from trading_os.research_assets.review_store import ReviewRunStore
    from trading_os.research_assets.sealing import canonical_json_bytes
    import hashlib

    runs_root = tmp_path / "runs"
    run_id = "policy-version-mismatch"
    payload = build_policy_snapshot(Path("policies"), run_id=run_id)
    versions = {
        policy_id: record["version"]
        for policy_id, record in payload["policies"].items()
    }
    drifted = dict(versions)
    first_policy = next(iter(drifted))
    drifted[first_policy] = "99.0.0"
    state = ReviewRunStore(runs_root).create_run(
        run_id,
        scope={"type": "custom", "market": "CN", "description": "drift"},
        policy_versions=drifted,
        policy_snapshot_sha256=hashlib.sha256(
            canonical_json_bytes(payload)
        ).hexdigest(),
        created_at=NOW,
    )
    seal_review_policy_snapshot(
        runs_root=runs_root,
        run_id=run_id,
        payload=payload,
        sealed_at=NOW,
    )

    with pytest.raises(PolicySnapshotError, match="state.policy_versions"):
        load_review_policy_snapshot(
            runs_root=runs_root,
            run_id=run_id,
            state=state,
        )

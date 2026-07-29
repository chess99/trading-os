from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest

NOW = dt.datetime(2026, 7, 30, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
SHA_A = hashlib.sha256(b"a").hexdigest()
SHA_B = hashlib.sha256(b"b").hexdigest()


def _trigger(trigger_type: str = "filing", trigger_id: str = "h1-filing") -> dict:
    return {
        "trigger_id": trigger_id,
        "type": trigger_type,
        "source_kind": "company_trigger",
        "definition_ref": "research/companies/CN/000001/meta.json",
        "definition_source_sha256": SHA_A,
        "definition": {
            "type": trigger_type,
            "condition": {"description": "observe a real occurrence"},
            "active": True,
        },
    }


def _fact_observation(
    *,
    occurrence_key: str = "announcement-1",
    idempotency_key: str = "observer:announcement-1",
    effective_at: dt.datetime = NOW - dt.timedelta(hours=2),
    symbol: str = "CN:000001",
) -> dict:
    return {
        "schema_version": 1,
        "symbol": symbol,
        "workflow_target": "company_research",
        "trigger_ref": _trigger(),
        "effective_at": effective_at.isoformat(),
        "observed_at": (NOW - dt.timedelta(hours=1)).isoformat(),
        "occurrence_evidence": {
            "kind": "filing",
            "occurrence_key": occurrence_key,
            "source_id": occurrence_key,
            "source_ref": f"https://example.test/{occurrence_key}",
            "source_sha256": SHA_B,
            "published_at": effective_at.isoformat(),
        },
        "actor": "test-observer",
        "idempotency_key": idempotency_key,
    }


def test_fact_observation_requires_evidence_and_is_idempotent(tmp_path: Path):
    from trading_os.research_assets.trigger_hits import (
        TriggerHitError,
        observe_fact_hit,
        verify_trigger_hit_ledger,
    )

    root = tmp_path / "coverage" / "cn-a"
    observation = _fact_observation()
    first = observe_fact_hit(root=root, observation=observation, recorded_at=NOW)
    replay = observe_fact_hit(root=root, observation=observation, recorded_at=NOW)
    duplicate = dict(observation)
    duplicate["idempotency_key"] = "second-observer:same-announcement"
    deduplicated = observe_fact_hit(root=root, observation=duplicate, recorded_at=NOW)

    assert first["idempotent"] is False
    assert replay["idempotent"] is True
    assert duplicate["idempotency_key"] != observation["idempotency_key"]
    assert deduplicated["deduplicated"] is True
    assert {first["hit_id"], replay["hit_id"], deduplicated["hit_id"]} == {
        first["hit_id"]
    }
    assert verify_trigger_hit_ledger(root=root)["ledger_line_count"] == 1

    missing_evidence = dict(observation)
    missing_evidence.pop("occurrence_evidence")
    with pytest.raises(TriggerHitError, match="occurrence_evidence"):
        observe_fact_hit(root=root, observation=missing_evidence, recorded_at=NOW)

    conflicting = _fact_observation(occurrence_key="announcement-2")
    with pytest.raises(TriggerHitError, match="idempotency key conflicts"):
        observe_fact_hit(root=root, observation=conflicting, recorded_at=NOW)


def test_hash_chain_tampering_is_detected(tmp_path: Path):
    from trading_os.research_assets.sealing import canonical_json_bytes
    from trading_os.research_assets.trigger_hits import (
        TriggerHitError,
        observe_fact_hit,
        verify_trigger_hit_ledger,
    )

    root = tmp_path / "coverage" / "cn-a"
    observe_fact_hit(root=root, observation=_fact_observation(), recorded_at=NOW)
    ledger = root / "trigger-hits" / "events.jsonl"
    event = json.loads(ledger.read_text(encoding="utf-8"))
    event["payload"]["actor"] = "tampered"
    ledger.write_bytes(canonical_json_bytes(event) + b"\n")

    with pytest.raises(TriggerHitError, match="event hash mismatch"):
        verify_trigger_hit_ledger(root=root)


def test_state_projection_drift_is_detected_and_rebuildable(tmp_path: Path):
    from trading_os.research_assets.sealing import canonical_json_bytes
    from trading_os.research_assets.trigger_hits import (
        TriggerHitError,
        observe_fact_hit,
        rebuild_trigger_hit_state,
        verify_trigger_hit_ledger,
    )

    root = tmp_path / "coverage" / "cn-a"
    observe_fact_hit(root=root, observation=_fact_observation(), recorded_at=NOW)
    state_path = root / "trigger-hits" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["hits"][0]["state"] = "consumed"
    state_path.write_bytes(canonical_json_bytes(state))

    with pytest.raises(TriggerHitError, match="projection does not match"):
        verify_trigger_hit_ledger(root=root)
    rebuilt = rebuild_trigger_hit_state(root=root)
    assert rebuilt["hit_count"] == 1
    assert verify_trigger_hit_ledger(root=root)["open_hit_count"] == 1


def test_price_episode_requires_false_rearm_before_second_hit(tmp_path: Path):
    from trading_os.research_assets.trigger_hits import (
        observe_price_condition,
        verify_trigger_hit_ledger,
    )

    root = tmp_path / "coverage" / "cn-a"
    trigger = _trigger("price", "price-below-10")

    def observe(met: bool, minute: int, price: float):
        observed_at = NOW + dt.timedelta(minutes=minute)
        return observe_price_condition(
            root=root,
            trigger=trigger,
            quote_evidence={
                "symbol": "CN:000001",
                "quote_as_of": observed_at.isoformat(),
                "observed_price": price,
                "source_ref": f"quote-{minute}",
                "source_sha256": SHA_B,
            },
            condition_met=met,
            actor="price-observer",
            recorded_at=observed_at,
        )

    first = observe(True, 0, 9.0)
    held = observe(True, 1, 8.9)
    rearmed = observe(False, 2, 10.5)
    already_armed = observe(False, 3, 11.0)
    second = observe(True, 4, 9.5)

    assert held["action"] == "condition_still_true"
    assert held["hit_id"] == first["hit_id"]
    assert rearmed["action"] == "rearmed"
    assert already_armed["action"] == "already_armed"
    assert second["hit_id"] != first["hit_id"]
    status = verify_trigger_hit_ledger(root=root)
    assert status["ledger_line_count"] == 3
    assert status["open_hit_count"] == 2
    assert status["price_monitor_count"] == 1


def test_schedule_due_is_one_shot_and_rebaseline_is_not_a_hit(tmp_path: Path):
    from trading_os.research_assets.trigger_hits import (
        TriggerHitError,
        observe_schedule_hit,
        verify_trigger_hit_ledger,
    )

    root = tmp_path / "coverage" / "cn-a"
    item = {
        "trigger_id": "research-refresh-due",
        "symbol": "CN:000001",
        "type": "date",
        "condition": {"due_at": (NOW - dt.timedelta(days=1)).isoformat()},
        "reason": "evidence TTL expired",
        "source": "research_refresh_due",
        "state": "due",
    }
    first = observe_schedule_hit(
        root=root,
        item=item,
        schedule_as_of=NOW,
        schedule_ref="automation/review_schedule.json",
        schedule_sha256=SHA_A,
        actor="schedule-observer",
        recorded_at=NOW,
    )
    replay = observe_schedule_hit(
        root=root,
        item=item,
        schedule_as_of=NOW,
        schedule_ref="automation/review_schedule.json",
        schedule_sha256=SHA_A,
        actor="schedule-observer",
        recorded_at=NOW,
    )
    assert first["hit_id"] == replay["hit_id"]
    assert replay["idempotent"] is True
    assert verify_trigger_hit_ledger(root=root)["ledger_line_count"] == 1

    baseline_item = dict(item)
    baseline_item.update(
        {"trigger_id": "research-rebaseline", "type": "rebaseline", "source": "x"}
    )
    with pytest.raises(TriggerHitError, match="baseline intake"):
        observe_schedule_hit(
            root=root,
            item=baseline_item,
            schedule_as_of=NOW,
            schedule_ref="automation/review_schedule.json",
            schedule_sha256=SHA_A,
            actor="schedule-observer",
            recorded_at=NOW,
        )

    thesis_item = dict(item)
    thesis_item.update({"trigger_id": "thesis-invalid", "type": "thesis"})
    with pytest.raises(TriggerHitError, match="date or ttl"):
        observe_schedule_hit(
            root=root,
            item=thesis_item,
            schedule_as_of=NOW,
            schedule_ref="automation/review_schedule.json",
            schedule_sha256=SHA_A,
            actor="schedule-observer",
            recorded_at=NOW,
        )


def _write_scope(tmp_path: Path, *, run_id: str, cutoff: dt.datetime) -> Path:
    from trading_os.research_assets.sealing import seal_json

    scope = tmp_path / "coverage" / "cn-a" / "scopes" / run_id / "manifest.json"
    frozen_at = cutoff + dt.timedelta(minutes=1)
    seal_json(
        scope,
        {
            "schema_version": 1,
            "run_id": run_id,
            "scope_cutoff": cutoff.isoformat(),
            "frozen_at": frozen_at.isoformat(),
            "members": [
                {"symbol": "CN:000001", "partition": "eligible"},
                {"symbol": "CN:000002", "partition": "hard_excluded"},
            ],
        },
        artifact_type="all_a_scope_manifest",
        sealed_at=frozen_at,
    )
    return scope


def test_checkpoint_binds_cutoff_and_isolated_ledger_head(tmp_path: Path):
    from trading_os.research_assets.sealing import verify_sealed
    from trading_os.research_assets.trigger_hits import (
        create_trigger_hit_checkpoint,
        observe_fact_hit,
        verify_trigger_hit_checkpoint,
    )

    root = tmp_path / "coverage" / "cn-a"
    cutoff = NOW
    scope = _write_scope(tmp_path, run_id="run-1", cutoff=cutoff)
    before = _fact_observation(
        occurrence_key="before", idempotency_key="before", effective_at=NOW - dt.timedelta(days=1)
    )
    after = _fact_observation(
        occurrence_key="after", idempotency_key="after", effective_at=NOW + dt.timedelta(hours=1)
    )
    after["observed_at"] = (NOW + dt.timedelta(hours=2)).isoformat()
    observe_fact_hit(root=root, observation=before, recorded_at=NOW)
    observe_fact_hit(root=root, observation=after, recorded_at=NOW + dt.timedelta(hours=2))

    checkpointed_at = NOW + dt.timedelta(hours=3)
    first = create_trigger_hit_checkpoint(
        root=root,
        run_id="run-1",
        scope_manifest_path=scope,
        checkpointed_at=checkpointed_at,
    )
    checkpoint_path = tmp_path / first["checkpoint_path"]
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert first["eligible_hit_count"] == 1
    assert payload["counts"]["after_scope_cutoff"] == 1
    assert verify_sealed(checkpoint_path).artifact_type == "trigger_hit_checkpoint"

    late_discovery = _fact_observation(
        occurrence_key="late-discovery",
        idempotency_key="late-discovery",
        effective_at=NOW - dt.timedelta(days=2),
    )
    late_discovery["observed_at"] = (NOW + dt.timedelta(hours=4)).isoformat()
    observe_fact_hit(
        root=root,
        observation=late_discovery,
        recorded_at=NOW + dt.timedelta(hours=4),
    )
    replay = create_trigger_hit_checkpoint(
        root=root,
        run_id="run-1",
        scope_manifest_path=scope,
        checkpointed_at=NOW + dt.timedelta(hours=5),
    )
    assert replay["checkpoint_sha256"] == first["checkpoint_sha256"]
    assert replay["ledger_line_count"] == 2
    assert replay["eligible_hit_count"] == 1
    verified = verify_trigger_hit_checkpoint(root=root, checkpoint_path=checkpoint_path)
    assert verified["checkpoint_sha256"] == first["checkpoint_sha256"]


def test_consume_requires_sealed_package_and_published_timeline(tmp_path: Path):
    from trading_os.research_assets.sealing import seal_json
    from trading_os.research_assets.trigger_hits import (
        consume_trigger_hits,
        observe_fact_hit,
        verify_trigger_hit_ledger,
    )

    root = tmp_path / "coverage" / "cn-a"
    observed = observe_fact_hit(
        root=root,
        observation=_fact_observation(),
        recorded_at=NOW,
    )
    package = root / "triage" / "cycle-1" / "000001" / "package.json"
    package_payload = {
        "schema_version": 2,
        "symbol": "CN:000001",
        "review_mode": "triggered_update",
        "handled_hit_ids": [observed["hit_id"]],
    }
    package_seal = seal_json(
        package,
        package_payload,
        artifact_type="rapid_triage_package",
        sealed_at=NOW,
    )
    company = tmp_path / "research" / "companies" / "CN" / "000001"
    report = company / "reports" / "2026-07-30-rapid-triage-example.md"
    report.parent.mkdir(parents=True)
    report.write_text("published\n", encoding="utf-8")
    meta = company / "meta.json"
    meta.write_text(
        json.dumps(
            {
                "identity": {"symbol": "CN:000001"},
                "research": {
                    "latest_rapid_triage": {
                        "source_package_path": package.relative_to(tmp_path).as_posix(),
                        "source_package_sha256": package_seal.sha256,
                        "report_path": report.relative_to(company).as_posix(),
                    }
                },
                "reports": {
                    "latest_by_type": {
                        "rapid_triage": report.relative_to(company).as_posix()
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    first = consume_trigger_hits(
        root=root,
        package_path=package,
        handled_hit_ids=[observed["hit_id"]],
        timeline_evidence={"meta_path": meta.relative_to(tmp_path).as_posix()},
        consumed_at=NOW + dt.timedelta(minutes=1),
        actor="timeline-publisher",
    )
    replay = consume_trigger_hits(
        root=root,
        package_path=package,
        handled_hit_ids=[observed["hit_id"]],
        timeline_evidence={"meta_path": meta.relative_to(tmp_path).as_posix()},
        consumed_at=NOW + dt.timedelta(minutes=2),
        actor="timeline-publisher",
    )
    assert first["newly_consumed_count"] == 1
    assert replay["idempotent"] is True
    status = verify_trigger_hit_ledger(root=root)
    assert status["consumed_hit_count"] == 1
    assert status["open_hit_count"] == 0

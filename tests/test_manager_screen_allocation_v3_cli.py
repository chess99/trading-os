from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

RUN_ID = "2026-07-31-all-a-continuous-001"
AT = dt.datetime(2026, 8, 1, 2, 15, tzinfo=dt.timezone(dt.timedelta(hours=8)))


def test_allocation_v3_freeze_cli_forwards_manager_policy_reason_and_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import trading_os.cli as cli

    captured: dict[str, object] = {}

    def fake_freeze(**kwargs):
        captured.update(kwargs)
        return {
            "state": "frozen",
            "contract_sha256": "a" * 64,
            "revocable_commitment_count": 181,
        }

    monkeypatch.setattr(cli, "freeze_manager_screen_allocation_v3_contract", fake_freeze)
    root = tmp_path / "coverage" / "cn-a"
    prior_policy = tmp_path / "policies" / "manager-screening.json"
    future_policy = tmp_path / "policies" / "manager-screening-allocation-v3.json"

    assert (
        cli.main(
            [
                "coverage",
                "manager-screen-allocation-v3-freeze",
                RUN_ID,
                "--root",
                str(root),
                "--prior-policy",
                str(prior_policy),
                "--future-policy",
                str(future_policy),
                "--manager-agent",
                "/root",
                "--manager-model",
                "gpt-test",
                "--manager-tool",
                "sealed manager results",
                "--manager-tool",
                "bound queue snapshot",
                "--reason",
                "Freeze an auditable v3 allocation contract.",
                "--at",
                AT.isoformat(),
            ]
        )
        == 0
    )

    assert captured == {
        "root": str(root),
        "run_id": RUN_ID,
        "manager": {
            "agent": "/root",
            "model": "gpt-test",
            "tools": ["sealed manager results", "bound queue snapshot"],
        },
        "reason": "Freeze an auditable v3 allocation contract.",
        "frozen_at": AT,
        "prior_policy_path": str(prior_policy),
        "future_policy_path": str(future_policy),
    }
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert output["state"] == "frozen"
    assert output["revocable_commitment_count"] == 181


def test_allocation_v3_status_cli_calls_activation_drift_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import trading_os.cli as cli

    captured: dict[str, object] = {}

    def fake_status(**kwargs):
        captured.update(kwargs)
        return {
            "run_id": RUN_ID,
            "contract_valid": True,
            "drifted": False,
            "portfolio_action": None,
        }

    monkeypatch.setattr(
        cli,
        "manager_screen_allocation_v3_activation_drift_status",
        fake_status,
    )
    root = tmp_path / "coverage" / "cn-a"

    assert (
        cli.main(
            [
                "coverage",
                "manager-screen-allocation-v3-status",
                RUN_ID,
                "--root",
                str(root),
            ]
        )
        == 0
    )
    assert captured == {"root": str(root), "run_id": RUN_ID}
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert output["contract_valid"] is True
    assert output["drifted"] is False


def test_allocation_v3_suspend_cli_forwards_manager_reason_and_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import trading_os.cli as cli

    captured: dict[str, object] = {}

    def fake_suspend(**kwargs):
        captured.update(kwargs)
        return {
            "candidate_state": "candidate_unfunded",
            "suspended_commitment_count": 181,
            "suspension_sha256": "b" * 64,
        }

    monkeypatch.setattr(
        cli,
        "suspend_manager_screen_allocation_v3_revocable_commitments",
        fake_suspend,
    )
    root = tmp_path / "coverage" / "cn-a"

    assert (
        cli.main(
            [
                "coverage",
                "manager-screen-allocation-v3-suspend",
                RUN_ID,
                "--root",
                str(root),
                "--manager-agent",
                "/root",
                "--manager-model",
                "gpt-test",
                "--manager-tool",
                "sealed allocation contract",
                "--manager-tool",
                "coverage projection",
                "--reason",
                "Suspend every still-pristine inherited commitment.",
                "--at",
                AT.isoformat(),
            ]
        )
        == 0
    )
    assert captured == {
        "root": str(root),
        "run_id": RUN_ID,
        "manager": {
            "agent": "/root",
            "model": "gpt-test",
            "tools": ["sealed allocation contract", "coverage projection"],
        },
        "reason": "Suspend every still-pristine inherited commitment.",
        "suspended_at": AT,
    }
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert output["candidate_state"] == "candidate_unfunded"
    assert output["suspended_commitment_count"] == 181


def test_allocation_v3_suspension_status_cli_calls_verifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import trading_os.cli as cli

    captured: dict[str, object] = {}

    def fake_status(**kwargs):
        captured.update(kwargs)
        return {
            "run_id": RUN_ID,
            "candidate_state": "candidate_unfunded",
            "materialization": {"fully_materialized": True},
        }

    monkeypatch.setattr(
        cli,
        "verify_manager_screen_allocation_v3_suspension",
        fake_status,
    )
    root = tmp_path / "coverage" / "cn-a"

    assert (
        cli.main(
            [
                "coverage",
                "manager-screen-allocation-v3-suspension-status",
                RUN_ID,
                "--root",
                str(root),
            ]
        )
        == 0
    )
    assert captured == {"root": str(root), "run_id": RUN_ID}
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert output["materialization"]["fully_materialized"] is True


@pytest.mark.parametrize(
    ("command", "attribute", "error_class", "error_code"),
    [
        (
            "manager-screen-allocation-v3-status",
            "manager_screen_allocation_v3_activation_drift_status",
            "ManagerScreenAllocationV3Error",
            "manager_screen_allocation_v3_error",
        ),
        (
            "manager-screen-allocation-v3-suspension-status",
            "verify_manager_screen_allocation_v3_suspension",
            "ManagerScreenAllocationV3SuspensionError",
            "manager_screen_allocation_v3_suspension_error",
        ),
    ],
)
def test_allocation_v3_cli_maps_domain_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
    attribute: str,
    error_class: str,
    error_code: str,
) -> None:
    import trading_os.cli as cli

    domain_error = getattr(cli, error_class)

    def fail(**_kwargs):
        raise domain_error("sealed governance state is invalid")

    monkeypatch.setattr(cli, attribute, fail)
    root = tmp_path / "coverage" / "cn-a"

    assert (
        cli.main(
            [
                "coverage",
                command,
                RUN_ID,
                "--root",
                str(root),
            ]
        )
        == 1
    )
    error = json.loads(capsys.readouterr().err)
    assert error["ok"] is False
    assert error["error_code"] == error_code

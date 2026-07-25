from __future__ import annotations

import copy
import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .models import PolicyKind, validate_policy
from .sealing import SealedArtifact, SealingError, seal_json, verify_sealed


class PolicySnapshotError(ValueError):
    """Raised when a review policy snapshot is missing, incomplete, or inconsistent."""


POLICY_SNAPSHOT_FILENAME = "policy-snapshot.json"
POLICY_SNAPSHOT_ARTIFACT_TYPE = "review_policy_snapshot"
_SNAPSHOT_FIELDS = {"schema_version", "run_id", "policies"}
_POLICY_FIELDS = {
    "schema_version",
    "policy_id",
    "version",
    "effective_at",
    "kind",
    "payload",
}


@dataclass(frozen=True, slots=True)
class ReviewPolicySnapshot:
    path: Path
    sha256: str
    run_id: str
    policies: Mapping[str, Mapping[str, Any]]
    policy_versions: Mapping[str, str]

    def require_kind(self, kind: PolicyKind | str) -> Mapping[str, Any]:
        kind_value = kind.value if isinstance(kind, PolicyKind) else str(kind)
        matches = [
            record
            for record in self.policies.values()
            if record["kind"] == kind_value
        ]
        if len(matches) != 1:
            raise PolicySnapshotError(
                "review policy snapshot must contain exactly one "
                f"{kind_value} policy, found {len(matches)}"
            )
        return matches[0]


def build_policy_snapshot(
    policy_root: str | Path,
    *,
    run_id: str,
) -> dict[str, Any]:
    """Read and validate every policy record for an immutable review snapshot."""

    run_id = _require_text(run_id, "run_id")
    root = Path(policy_root)
    if not root.is_dir():
        raise PolicySnapshotError(f"policy directory does not exist: {root}")

    records: dict[str, dict[str, Any]] = {}
    paths = sorted(root.rglob("*.json"), key=lambda item: item.as_posix())
    for path in paths:
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PolicySnapshotError(f"invalid policy JSON: {path}") from exc
        if not isinstance(raw, dict):
            raise PolicySnapshotError(f"policy must be a JSON object: {path}")
        try:
            policy = validate_policy(raw)
        except ValueError as exc:
            raise PolicySnapshotError(f"invalid policy record: {path}: {exc}") from exc
        if policy.policy_id in records:
            raise PolicySnapshotError(f"duplicate policy_id: {policy.policy_id}")
        records[policy.policy_id] = copy.deepcopy(raw)

    if not records:
        raise PolicySnapshotError(f"no policies found under: {root}")
    return {
        "schema_version": 1,
        "run_id": run_id,
        "policies": dict(sorted(records.items())),
    }


def policy_versions_from_snapshot(payload: Mapping[str, Any]) -> dict[str, str]:
    """Validate a complete snapshot payload and derive its state version map."""

    _, versions = _validate_snapshot_payload(payload)
    return versions


def seal_review_policy_snapshot(
    *,
    runs_root: str | Path,
    run_id: str,
    payload: Mapping[str, Any],
    sealed_at: dt.datetime,
) -> SealedArtifact:
    """Seal the already-validated snapshot beside the review run state."""

    policies, _ = _validate_snapshot_payload(payload)
    normalized = {
        "schema_version": 1,
        "run_id": _require_text(run_id, "run_id"),
        "policies": {key: copy.deepcopy(dict(value)) for key, value in policies.items()},
    }
    if normalized["run_id"] != payload.get("run_id"):
        raise PolicySnapshotError("policy snapshot run_id does not match review run")
    try:
        return seal_json(
            Path(runs_root) / run_id / POLICY_SNAPSHOT_FILENAME,
            normalized,
            artifact_type=POLICY_SNAPSHOT_ARTIFACT_TYPE,
            sealed_at=sealed_at,
        )
    except SealingError as exc:
        raise PolicySnapshotError(f"cannot seal review policy snapshot: {exc}") from exc


def load_review_policy_snapshot(
    *,
    runs_root: str | Path,
    run_id: str,
    state: Mapping[str, Any],
) -> ReviewPolicySnapshot:
    """Load a sealed snapshot and bind it to the review's immutable state."""

    run_id = _require_text(run_id, "run_id")
    if not isinstance(state, Mapping):
        raise PolicySnapshotError("review state must be an object")
    if state.get("run_id") != run_id:
        raise PolicySnapshotError("review state run_id does not match requested run")
    expected_snapshot_sha256 = state.get("policy_snapshot_sha256")
    if (
        not isinstance(expected_snapshot_sha256, str)
        or len(expected_snapshot_sha256) != 64
        or any(
            char not in "0123456789abcdef"
            for char in expected_snapshot_sha256
        )
    ):
        raise PolicySnapshotError(
            "review state is missing a valid policy_snapshot_sha256; "
            "legacy run requires a new review"
        )

    path = Path(runs_root) / run_id / POLICY_SNAPSHOT_FILENAME
    try:
        sealed = verify_sealed(path)
    except SealingError as exc:
        raise PolicySnapshotError(
            f"review policy snapshot is missing or invalid: {path}: {exc}"
        ) from exc
    if sealed.artifact_type != POLICY_SNAPSHOT_ARTIFACT_TYPE:
        raise PolicySnapshotError("review policy snapshot has the wrong artifact type")
    if expected_snapshot_sha256 != sealed.sha256:
        raise PolicySnapshotError(
            "review policy snapshot SHA-256 does not match review state"
        )

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PolicySnapshotError(f"invalid review policy snapshot JSON: {path}") from exc
    if not isinstance(raw, dict):
        raise PolicySnapshotError("review policy snapshot must be an object")
    policies, versions = _validate_snapshot_payload(raw)
    if raw["run_id"] != run_id:
        raise PolicySnapshotError("review policy snapshot run_id does not match review run")

    state_versions = state.get("policy_versions")
    if not isinstance(state_versions, Mapping):
        raise PolicySnapshotError("review state policy_versions must be an object")
    normalized_state_versions = {
        _require_text(policy_id, "state policy_id"): _require_text(
            version, "state policy version"
        )
        for policy_id, version in state_versions.items()
    }
    normalized_state_versions = dict(sorted(normalized_state_versions.items()))
    if versions != normalized_state_versions:
        raise PolicySnapshotError(
            "review policy snapshot versions do not match state.policy_versions"
        )

    frozen_policies = {
        policy_id: MappingProxyType(copy.deepcopy(dict(record)))
        for policy_id, record in policies.items()
    }
    return ReviewPolicySnapshot(
        path=path,
        sha256=sealed.sha256,
        run_id=run_id,
        policies=MappingProxyType(frozen_policies),
        policy_versions=MappingProxyType(dict(versions)),
    )


def _validate_snapshot_payload(
    payload: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    if not isinstance(payload, Mapping) or set(payload) != _SNAPSHOT_FIELDS:
        raise PolicySnapshotError(
            f"review policy snapshot fields must be {sorted(_SNAPSHOT_FIELDS)}"
        )
    if payload.get("schema_version") != 1:
        raise PolicySnapshotError("review policy snapshot schema_version must be 1")
    _require_text(payload.get("run_id"), "policy snapshot run_id")

    raw_policies = payload.get("policies")
    if not isinstance(raw_policies, Mapping) or not raw_policies:
        raise PolicySnapshotError("review policy snapshot policies must be non-empty")
    policies: dict[str, dict[str, Any]] = {}
    versions: dict[str, str] = {}
    for key, raw_record in raw_policies.items():
        policy_id = _require_text(key, "policy snapshot policy_id")
        if not isinstance(raw_record, Mapping):
            raise PolicySnapshotError(f"policy record must be an object: {policy_id}")
        if set(raw_record) != _POLICY_FIELDS:
            raise PolicySnapshotError(
                f"policy record is incomplete or has unknown fields: {policy_id}"
            )
        record = copy.deepcopy(dict(raw_record))
        try:
            policy = validate_policy(record)
        except ValueError as exc:
            raise PolicySnapshotError(
                f"invalid policy record in snapshot: {policy_id}: {exc}"
            ) from exc
        if policy.policy_id != policy_id:
            raise PolicySnapshotError(
                f"policy snapshot key does not match record policy_id: {policy_id}"
            )
        policies[policy_id] = record
        versions[policy_id] = policy.version
    return dict(sorted(policies.items())), dict(sorted(versions.items()))


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicySnapshotError(f"{label} must be a non-empty string")
    return value.strip()

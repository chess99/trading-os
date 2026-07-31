from __future__ import annotations

import codecs
import datetime as dt
import hashlib
import json
import os
import re
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import unquote


class AssetGcError(ValueError):
    """Raised when a conservative asset reachability plan cannot be built."""


MANAGED_ROOTS = (
    Path("research"),
    Path("coverage"),
    Path("automation") / "runs",
    Path("policies"),
)
SCRATCH_PARTS = {
    ".cache",
    ".scratch",
    ".tmp",
    "__pycache__",
    "cache",
    "scratch",
    "tmp",
}
TEXT_SUFFIXES = {
    ".csv",
    ".html",
    ".json",
    ".jsonl",
    ".md",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
MANIFEST_SUFFIXES = TEXT_SUFFIXES | {".manifest", ".ndjson", ".toml"}
SHA256_RE = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")
REPOSITORY_PATH_RE = re.compile(
    r"(?:(?:research|coverage|automation|policies)[\\/]"
    r"[^\s\"'<>|)\]}]+)"
)
LOCAL_ASSET_PATH_RE = re.compile(
    r"(?:(?:reports|evidence|sources|underwriting)[\\/]"
    r"[^\s\"'<>|)\]}]+)"
)
GC_PLAN_ROOT = Path("research") / "archives" / "gc-plans"


@dataclass(frozen=True)
class _FileIdentity:
    device: int
    inode: int
    size_bytes: int
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True)
class _CandidateSnapshot:
    size_bytes: int
    sha256: str | None


def build_asset_gc_plan(
    *,
    repository_root: str | Path,
    planned_at: dt.datetime,
    hash_candidate_content: bool = True,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a read-only, conservative reachability plan.

    Formal reports, sealed artifacts, coverage state, run state, and policies
    are roots. Company source payloads, migration payloads, and scratch/cache
    files become candidates only when neither a path nor a SHA-256 reference
    reaches them. This function never deletes or moves a file.
    """

    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise AssetGcError(f"repository root is missing: {root}")
    planned = _aware(planned_at, "planned_at")
    files = _managed_files(root)
    roots = {path for path in files if _is_reference_root(path, root=root)}
    initial_identities = _file_identities(files, repository_root=root)
    reachable = set(roots)
    reasons: dict[Path, set[str]] = {path: {_relative(path, root)} for path in roots}
    queue: deque[Path] = deque(sorted(roots))
    referenced_sha256: set[str] = set()

    _follow_path_references(
        queue=queue,
        reachable=reachable,
        reasons=reasons,
        referenced_sha256=referenced_sha256,
        repository_root=root,
        existing=files,
        roots=roots,
    )

    candidates = sorted(path for path in files if _candidate_kind(path, root=root))
    candidate_snapshots = {
        path: _stable_candidate_snapshot(path, hash_content=hash_candidate_content)
        for path in candidates
    }
    if hash_candidate_content:
        candidates_by_hash: dict[str, list[Path]] = {}
        for path, snapshot in candidate_snapshots.items():
            digest = snapshot.sha256
            if digest is None:
                raise AssetGcError(f"candidate hash snapshot is missing: {_relative(path, root)}")
            candidates_by_hash.setdefault(digest, []).append(path)

        # A candidate reached only by content hash may itself be a manifest
        # that references more payloads by path or hash. Resolve to a fixed
        # point so those transitive dependencies are protected too.
        resolved_hashes: set[str] = set()
        while queue or referenced_sha256 - resolved_hashes:
            for digest in sorted(referenced_sha256 - resolved_hashes):
                resolved_hashes.add(digest)
                for path in candidates_by_hash.get(digest, ()):
                    reasons.setdefault(path, set()).add(f"sha256:{digest}")
                    if path not in reachable:
                        reachable.add(path)
                        queue.append(path)
            _follow_path_references(
                queue=queue,
                reachable=reachable,
                reasons=reasons,
                referenced_sha256=referenced_sha256,
                repository_root=root,
                existing=files,
                roots=roots,
            )

    unreachable = [path for path in candidates if path not in reachable]
    protected_candidates = [path for path in candidates if path in reachable]
    proposed = [
        _candidate_row(path, root=root, snapshot=candidate_snapshots[path])
        for path in unreachable
    ]
    protected = [
        {
            **_candidate_row(path, root=root, snapshot=candidate_snapshots[path]),
            "reachable_from": sorted(reasons.get(path, set())),
        }
        for path in protected_candidates
    ]
    category_counts = _category_summary(proposed)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": "asset_gc_reachability_plan",
        "planned_at": planned.isoformat(),
        "repository_root": root.as_posix(),
        "mode": "read_only_plan",
        "delete_performed": False,
        "root_file_count": len(roots),
        "managed_file_count": len(files),
        "candidate_file_count": len(candidates),
        "reachable_candidate_count": len(protected_candidates),
        "proposed_candidate_count": len(proposed),
        "proposed_candidate_bytes": sum(item["size_bytes"] for item in proposed),
        "protected_candidate_bytes": sum(item["size_bytes"] for item in protected),
        "hash_candidate_content": hash_candidate_content,
        "referenced_sha256_count": len(referenced_sha256),
        "categories": category_counts,
        "proposed_candidates": proposed,
        "protected_candidates": protected,
        "safety": {
            "formal_reports_are_roots": True,
            "sealed_artifacts_are_roots": True,
            "coverage_and_run_state_are_roots": True,
            "path_references_are_followed": True,
            "sha256_references_are_followed": hash_candidate_content,
            "hash_only_references_may_be_unprotected": (not hash_candidate_content),
            "default_action": "manual_review",
            "destructive_action_requires_separate_explicit_approval": True,
        },
        "portfolio_action": None,
    }
    _assert_scan_unchanged(
        repository_root=root,
        files=files,
        roots=roots,
        initial_identities=initial_identities,
    )
    if output_path is not None:
        target = Path(output_path)
        if not target.is_absolute():
            target = root / target
        target = target.resolve()
        allowed_root = (root / GC_PLAN_ROOT).resolve()
        try:
            relative_output = target.relative_to(allowed_root)
        except ValueError as exc:
            raise AssetGcError("GC plan output must stay under research/archives/gc-plans") from exc
        if not relative_output.parts or target.suffix.lower() != ".json":
            raise AssetGcError(
                "GC plan output must be a JSON file under research/archives/gc-plans"
            )
        encoded = (
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
        _write_bytes_exclusive(target, encoded)
        payload["output_path"] = _relative(target, root)
        payload["output_sha256"] = hashlib.sha256(encoded).hexdigest()
    return payload


def gc_plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": plan["schema_version"],
        "kind": plan["kind"],
        "planned_at": plan["planned_at"],
        "mode": plan["mode"],
        "delete_performed": plan["delete_performed"],
        "managed_file_count": plan["managed_file_count"],
        "candidate_file_count": plan["candidate_file_count"],
        "reachable_candidate_count": plan["reachable_candidate_count"],
        "proposed_candidate_count": plan["proposed_candidate_count"],
        "proposed_candidate_bytes": plan["proposed_candidate_bytes"],
        "protected_candidate_bytes": plan["protected_candidate_bytes"],
        "categories": plan["categories"],
        "output_path": plan.get("output_path"),
        "output_sha256": plan.get("output_sha256"),
        "candidate_sample": list(plan["proposed_candidates"][:20]),
        "safety": plan["safety"],
        "portfolio_action": None,
    }


def _managed_files(root: Path) -> set[Path]:
    result: set[Path] = set()
    for relative in MANAGED_ROOTS:
        base = root / relative
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_file() and not _is_plan_output(path, root=root):
                result.add(path.resolve())
    return result


def _is_plan_output(path: Path, *, root: Path) -> bool:
    relative = path.resolve().relative_to(root)
    return len(relative.parts) >= 3 and relative.parts[:3] == ("research", "archives", "gc-plans")


def _is_reference_root(path: Path, *, root: Path) -> bool:
    relative = path.relative_to(root)
    parts = relative.parts
    if path.name.endswith(".seal.json"):
        return True
    if not parts:
        return False
    if _candidate_kind(path, root=root) is not None:
        return False
    if parts[0] in {"coverage", "automation", "policies"}:
        return True
    if parts[0] != "research":
        return False
    return True


def _candidate_kind(path: Path, *, root: Path) -> str | None:
    relative = path.relative_to(root)
    parts = relative.parts
    lowered = {part.lower() for part in parts}
    if lowered & SCRATCH_PARTS:
        return "scratch_or_cache"
    if len(parts) >= 2 and parts[:2] == ("research", "migrations"):
        return "legacy_migration_payload"
    if (
        len(parts) >= 5
        and parts[0] == "research"
        and parts[1] == "companies"
        and parts[4] == "sources"
    ):
        return "company_source"
    return None


def _path_references(
    text: str,
    *,
    source: Path,
    repository_root: Path,
    existing: set[Path],
) -> set[Path]:
    raw_values: set[str] = set()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if parsed is not None:
        raw_values.update(_strings(parsed))
    raw_values.update(_markdown_targets(text))
    raw_values.update(REPOSITORY_PATH_RE.findall(text))
    raw_values.update(LOCAL_ASSET_PATH_RE.findall(text))

    result: set[Path] = set()
    company_root = _company_root(source, repository_root=repository_root)
    for raw in raw_values:
        for candidate in _reference_candidates(
            raw,
            source=source,
            repository_root=repository_root,
            company_root=company_root,
        ):
            if candidate in existing:
                result.add(candidate)
    if source.name.endswith(".seal.json"):
        try:
            seal = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AssetGcError(f"seal manifest is not valid JSON: {source}") from exc
        if not isinstance(seal, Mapping):
            raise AssetGcError(f"seal manifest must be a JSON object: {source}")
        artifact = seal.get("artifact")
        if (
            not isinstance(artifact, str)
            or not artifact.strip()
            or Path(artifact).name != artifact
        ):
            raise AssetGcError(f"seal manifest artifact is invalid: {source}")
        target = (source.parent / artifact).resolve()
        try:
            target.relative_to(repository_root)
        except ValueError as exc:
            raise AssetGcError(f"seal manifest artifact escapes repository: {source}") from exc
        if target not in existing:
            raise AssetGcError(f"seal manifest artifact is missing: {target}")
        result.add(target)
    return result


def _follow_path_references(
    *,
    queue: deque[Path],
    reachable: set[Path],
    reasons: dict[Path, set[str]],
    referenced_sha256: set[str],
    repository_root: Path,
    existing: set[Path],
    roots: set[Path],
) -> None:
    while queue:
        source = queue.popleft()
        text = _read_text(
            source,
            is_root=source in roots,
            is_candidate=_candidate_kind(source, root=repository_root) is not None,
        )
        if text is None:
            continue
        referenced_sha256.update(match.lower() for match in SHA256_RE.findall(text))
        for target in _path_references(
            text,
            source=source,
            repository_root=repository_root,
            existing=existing,
        ):
            reasons.setdefault(target, set()).add(_relative(source, repository_root))
            if target not in reachable:
                reachable.add(target)
                queue.append(target)


def _reference_candidates(
    raw: str,
    *,
    source: Path,
    repository_root: Path,
    company_root: Path | None,
) -> Iterable[Path]:
    value = raw.strip().strip("<>`\"'")
    if not value or "://" in value or value.startswith("data:"):
        return ()
    value = value.split("#", 1)[0].strip()
    value = value.rstrip(".,;:")
    if not value:
        return ()
    value = unquote(value)
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    bases = [repository_root, source.parent]
    if company_root is not None:
        bases.append(company_root)
    resolved: list[Path] = []
    if path.is_absolute():
        resolved.append(path.resolve())
    else:
        for base in bases:
            resolved.append((base / path).resolve())
    return tuple(dict.fromkeys(resolved))


def _markdown_targets(text: str) -> Iterable[str]:
    """Yield inline Markdown destinations without optional link titles."""

    cursor = 0
    while True:
        marker = text.find("](", cursor)
        if marker < 0:
            return
        position = marker + 2
        while position < len(text) and text[position].isspace():
            position += 1
        if position >= len(text):
            return

        destination: list[str] = []
        if text[position] == "<":
            position += 1
            while position < len(text):
                char = text[position]
                if char == "\\" and position + 1 < len(text):
                    destination.extend((char, text[position + 1]))
                    position += 2
                    continue
                if char == ">":
                    break
                destination.append(char)
                position += 1
        else:
            depth = 0
            while position < len(text):
                char = text[position]
                if char == "\\" and position + 1 < len(text):
                    destination.extend((char, text[position + 1]))
                    position += 2
                    continue
                if char.isspace() and depth == 0:
                    break
                if char == "(":
                    depth += 1
                elif char == ")":
                    if depth == 0:
                        break
                    depth -= 1
                destination.append(char)
                position += 1

        if destination:
            yield _markdown_unescape("".join(destination))
        cursor = max(position + 1, marker + 2)


def _markdown_unescape(value: str) -> str:
    return re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\]^_`{|}~\s])", r"\1", value)


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def _company_root(path: Path, *, repository_root: Path) -> Path | None:
    current = path.parent
    while current != repository_root and repository_root in current.parents:
        if current.parent.name in {"CN", "HK", "US"} and current.parent.parent.name == "companies":
            return current
        current = current.parent
    return None


def _read_text(path: Path, *, is_root: bool, is_candidate: bool) -> str | None:
    is_declared_text = (
        path.suffix.lower() in MANIFEST_SUFFIXES
        or not path.suffix
        or path.name.endswith(".seal.json")
    )
    if not is_candidate and not is_declared_text:
        return None
    try:
        payload = _stable_read_bytes(path)
        return _decode_text(payload)
    except UnicodeDecodeError as exc:
        if is_root or is_declared_text:
            raise AssetGcError(f"text root or manifest is not decodable: {path}") from exc
        return None


def _decode_text(payload: bytes) -> str:
    if payload.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        return payload.decode("utf-32")
    if payload.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return payload.decode("utf-16")
    if payload.startswith(codecs.BOM_UTF8):
        return payload.decode("utf-8-sig")
    return payload.decode("utf-8")


def _candidate_row(
    path: Path,
    *,
    root: Path,
    snapshot: _CandidateSnapshot,
) -> dict[str, Any]:
    kind = _candidate_kind(path, root=root)
    if kind is None:
        raise AssetGcError(f"non-candidate entered candidate plan: {path}")
    action = (
        "delete_after_review" if kind == "scratch_or_cache" else "archive_or_delete_after_review"
    )
    row = {
        "path": _relative(path, root),
        "category": kind,
        "proposed_action": action,
        "size_bytes": snapshot.size_bytes,
    }
    if snapshot.sha256 is not None:
        row["sha256"] = snapshot.sha256
    return row


def _category_summary(rows: list[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for row in rows:
        category = str(row["category"])
        summary = result.setdefault(category, {"file_count": 0, "size_bytes": 0})
        summary["file_count"] += 1
        summary["size_bytes"] += int(row["size_bytes"])
    return dict(sorted(result.items()))


def _stable_candidate_snapshot(path: Path, *, hash_content: bool) -> _CandidateSnapshot:
    digest = hashlib.sha256() if hash_content else None
    size_bytes = 0
    try:
        before = _identity(path.stat())
        with path.open("rb") as handle:
            opened = _identity(os.fstat(handle.fileno()))
            if not _same_open_file(opened, before):
                raise AssetGcError(f"candidate changed while opening: {path}")
            if digest is None:
                size_bytes = opened.size_bytes
            else:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    size_bytes += len(chunk)
                    digest.update(chunk)
            closed = _identity(os.fstat(handle.fileno()))
        after = _identity(path.stat())
    except AssetGcError:
        raise
    except OSError as exc:
        raise AssetGcError(f"candidate is unreadable: {path}") from exc
    if (
        not _same_open_file(opened, closed)
        or before != after
        or size_bytes != before.size_bytes
    ):
        raise AssetGcError(f"candidate changed while hashing: {path}")
    return _CandidateSnapshot(
        size_bytes=size_bytes,
        sha256=digest.hexdigest() if digest is not None else None,
    )


def _stable_read_bytes(path: Path) -> bytes:
    try:
        before = _identity(path.stat())
        with path.open("rb") as handle:
            opened = _identity(os.fstat(handle.fileno()))
            if not _same_open_file(opened, before):
                raise AssetGcError(f"file changed while opening: {path}")
            payload = handle.read()
            closed = _identity(os.fstat(handle.fileno()))
        after = _identity(path.stat())
    except AssetGcError:
        raise
    except OSError as exc:
        raise AssetGcError(f"file is unreadable: {path}") from exc
    if (
        not _same_open_file(opened, closed)
        or before != after
        or len(payload) != before.size_bytes
    ):
        raise AssetGcError(f"file changed while reading: {path}")
    return payload


def _file_identities(
    files: set[Path],
    *,
    repository_root: Path,
) -> dict[Path, _FileIdentity]:
    result: dict[Path, _FileIdentity] = {}
    for path in sorted(files):
        try:
            result[path] = _identity(path.stat())
        except OSError as exc:
            raise AssetGcError(
                f"managed file disappeared before scan: {_relative(path, repository_root)}"
            ) from exc
    return result


def _assert_scan_unchanged(
    *,
    repository_root: Path,
    files: set[Path],
    roots: set[Path],
    initial_identities: Mapping[Path, _FileIdentity],
) -> None:
    current_files = _managed_files(repository_root)
    if current_files != files:
        raise AssetGcError("managed file set changed during GC scan; retry")
    current_roots = {
        path for path in current_files if _is_reference_root(path, root=repository_root)
    }
    if current_roots != roots:
        raise AssetGcError("reference root set changed during GC scan; retry")
    for path, expected in initial_identities.items():
        try:
            current = _identity(path.stat())
        except OSError as exc:
            raise AssetGcError(f"managed file disappeared during GC scan: {path}") from exc
        if current != expected:
            raise AssetGcError(f"managed file changed during GC scan: {path}")


def _identity(stat: os.stat_result) -> _FileIdentity:
    return _FileIdentity(
        device=stat.st_dev,
        inode=stat.st_ino,
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        ctime_ns=stat.st_ctime_ns,
    )


def _same_open_file(left: _FileIdentity, right: _FileIdentity) -> bool:
    # Windows reports a different st_ctime_ns through fstat() than stat().
    # The path-level before/after comparison still includes ctime.
    return (
        left.device,
        left.inode,
        left.size_bytes,
        left.mtime_ns,
    ) == (
        right.device,
        right.inode,
        right.size_bytes,
        right.mtime_ns,
    )


def _write_bytes_exclusive(target: Path, payload: bytes) -> None:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        handle = _open_exclusive(target)
    except FileExistsError:
        try:
            existing = target.read_bytes()
        except OSError as exc:
            raise AssetGcError(
                f"GC plan output conflicts with an existing file: {target}"
            ) from exc
        if existing != payload:
            raise AssetGcError(
                f"GC plan output conflicts with an existing file: {target}"
            ) from None
        return
    except OSError as exc:
        raise AssetGcError(f"cannot create GC plan output: {target}") from exc

    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise AssetGcError(f"cannot write GC plan output: {target}") from exc


def _open_exclusive(target: Path) -> BinaryIO:
    return target.open("xb")


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _aware(value: dt.datetime, field: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise AssetGcError(f"{field} must include a UTC offset")
    return value

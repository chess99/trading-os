from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest

PLANNED_AT = dt.datetime.fromisoformat("2026-07-31T15:00:00+08:00")


def _write(path: Path, payload: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(payload, encoding="utf-8")


def test_gc_plan_follows_paths_and_only_proposes_unreachable_managed_payloads(
    tmp_path: Path,
):
    from trading_os.research_assets.asset_gc import build_asset_gc_plan

    company = tmp_path / "research" / "companies" / "CN" / "000001"
    _write(
        company / "meta.json",
        json.dumps(
            {
                "schema_version": 2,
                "reports": {
                    "latest": "reports/live.md",
                    "history": [{"path": "reports/live.md"}],
                },
            }
        ),
    )
    _write(company / "reports" / "live.md", "[source](../sources/keep.pdf)")
    _write(company / "sources" / "keep.pdf", b"reachable")
    _write(company / "sources" / "orphan.pdf", b"orphan")
    _write(
        tmp_path / "research" / "migrations" / "legacy" / "unused.json",
        "{}",
    )
    _write(tmp_path / "coverage" / "cn-a" / "screening.jsonl", "")

    plan = build_asset_gc_plan(
        repository_root=tmp_path,
        planned_at=PLANNED_AT,
    )

    proposed = {item["path"]: item for item in plan["proposed_candidates"]}
    protected = {item["path"]: item for item in plan["protected_candidates"]}
    assert "research/companies/CN/000001/sources/keep.pdf" in protected
    assert proposed["research/companies/CN/000001/sources/orphan.pdf"]["category"] == (
        "company_source"
    )
    assert proposed["research/migrations/legacy/unused.json"]["category"] == (
        "legacy_migration_payload"
    )
    assert plan["delete_performed"] is False


def test_gc_plan_preserves_candidate_referenced_only_by_sha256(tmp_path: Path):
    from trading_os.research_assets.asset_gc import build_asset_gc_plan

    company = tmp_path / "research" / "companies" / "CN" / "000001"
    source = b"hash-bound-source"
    digest = hashlib.sha256(source).hexdigest()
    _write(company / "reports" / "live.md", f"source sha256: {digest}")
    _write(company / "sources" / "hash-only.pdf", source)
    _write(company / "sources" / "unbound.pdf", b"unbound")

    plan = build_asset_gc_plan(
        repository_root=tmp_path,
        planned_at=PLANNED_AT,
    )

    protected = {item["path"]: item for item in plan["protected_candidates"]}
    proposed = {item["path"] for item in plan["proposed_candidates"]}
    row = protected["research/companies/CN/000001/sources/hash-only.pdf"]
    assert row["sha256"] == digest
    assert f"sha256:{digest}" in row["reachable_from"]
    assert "research/companies/CN/000001/sources/unbound.pdf" in proposed


def test_gc_plan_hashes_candidates_even_without_sha256_references(tmp_path: Path):
    from trading_os.research_assets.asset_gc import build_asset_gc_plan

    source = b"orphan-with-no-hash-reference"
    path = (
        tmp_path
        / "research"
        / "companies"
        / "CN"
        / "000001"
        / "sources"
        / "orphan.pdf"
    )
    _write(path, source)

    plan = build_asset_gc_plan(
        repository_root=tmp_path,
        planned_at=PLANNED_AT,
    )

    row = plan["proposed_candidates"][0]
    assert row["sha256"] == hashlib.sha256(source).hexdigest()
    assert row["size_bytes"] == len(source)


def test_gc_plan_follows_transitive_references_from_hash_only_candidate(tmp_path: Path):
    from trading_os.research_assets.asset_gc import build_asset_gc_plan

    company = tmp_path / "research" / "companies" / "CN" / "000001"
    child = b"transitively-bound-source"
    child_digest = hashlib.sha256(child).hexdigest()
    manifest = json.dumps(
        {
            "path_child": "sources/path-child.pdf",
            "hash_child_sha256": child_digest,
        }
    )
    manifest_digest = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
    _write(company / "reports" / "live.md", f"manifest sha256: {manifest_digest}")
    _write(company / "sources" / "manifest.json", manifest)
    _write(company / "sources" / "path-child.pdf", b"path-bound")
    _write(company / "sources" / "hash-child.pdf", child)
    _write(company / "sources" / "orphan.pdf", b"orphan")

    plan = build_asset_gc_plan(
        repository_root=tmp_path,
        planned_at=PLANNED_AT,
    )

    protected = {item["path"]: item for item in plan["protected_candidates"]}
    proposed = {item["path"] for item in plan["proposed_candidates"]}
    assert "research/companies/CN/000001/sources/manifest.json" in protected
    assert "research/companies/CN/000001/sources/path-child.pdf" in protected
    assert "research/companies/CN/000001/sources/hash-child.pdf" in protected
    assert "research/companies/CN/000001/sources/orphan.pdf" in proposed


def test_gc_plan_probes_bom_manifest_with_nonstandard_suffix_after_hash_reach(
    tmp_path: Path,
):
    from trading_os.research_assets.asset_gc import build_asset_gc_plan

    company = tmp_path / "research" / "companies" / "CN" / "000001"
    manifest = b"\xef\xbb\xbf" + json.dumps(
        {"path": "sources/path-child.pdf"},
        ensure_ascii=False,
    ).encode("utf-8")
    manifest_digest = hashlib.sha256(manifest).hexdigest()
    _write(company / "reports" / "live.md", f"manifest sha256: {manifest_digest}")
    _write(company / "sources" / "index.manifest", manifest)
    _write(company / "sources" / "path-child.pdf", b"path-bound")

    plan = build_asset_gc_plan(
        repository_root=tmp_path,
        planned_at=PLANNED_AT,
    )

    protected = {item["path"] for item in plan["protected_candidates"]}
    assert "research/companies/CN/000001/sources/index.manifest" in protected
    assert "research/companies/CN/000001/sources/path-child.pdf" in protected


def test_gc_plan_parses_markdown_titles_percent_encoding_and_escapes(tmp_path: Path):
    from trading_os.research_assets.asset_gc import build_asset_gc_plan

    report = tmp_path / "research" / "batches" / "run-1" / "live.md"
    _write(
        report,
        "\n".join(
            [
                '[title](../../migrations/legacy/with-title.pdf "2025 annual report")',
                '[encoded](<../../migrations/legacy/file%20name.pdf> "source title")',
                r"[escaped](../../migrations/legacy/with\)paren.pdf)",
            ]
        ),
    )
    migrations = tmp_path / "research" / "migrations" / "legacy"
    _write(migrations / "with-title.pdf", b"title")
    _write(migrations / "file name.pdf", b"encoded")
    _write(migrations / "with)paren.pdf", b"escaped")

    plan = build_asset_gc_plan(
        repository_root=tmp_path,
        planned_at=PLANNED_AT,
    )

    protected = {item["path"] for item in plan["protected_candidates"]}
    assert "research/migrations/legacy/with-title.pdf" in protected
    assert "research/migrations/legacy/file name.pdf" in protected
    assert "research/migrations/legacy/with)paren.pdf" in protected


def test_gc_plan_reads_utf16_bom_root_and_fails_closed_on_undecodable_root(
    tmp_path: Path,
):
    from trading_os.research_assets.asset_gc import AssetGcError, build_asset_gc_plan

    company = tmp_path / "research" / "companies" / "CN" / "000001"
    report = company / "reports" / "live.md"
    _write(report, "[source](../sources/keep.pdf)".encode("utf-16"))
    _write(company / "sources" / "keep.pdf", b"reachable")

    plan = build_asset_gc_plan(
        repository_root=tmp_path,
        planned_at=PLANNED_AT,
    )
    protected = {item["path"] for item in plan["protected_candidates"]}
    assert "research/companies/CN/000001/sources/keep.pdf" in protected

    _write(report, b"\xff\xff\xff")
    with pytest.raises(AssetGcError, match="not decodable"):
        build_asset_gc_plan(
            repository_root=tmp_path,
            planned_at=PLANNED_AT,
        )


def test_gc_plan_fails_closed_on_corrupt_seal(tmp_path: Path):
    from trading_os.research_assets.asset_gc import AssetGcError, build_asset_gc_plan

    company = tmp_path / "research" / "companies" / "CN" / "000001"
    _write(company / "sources" / "sealed.json", "{}")
    _write(company / "sources" / "sealed.json.seal.json", "{")

    with pytest.raises(AssetGcError, match="seal manifest is not valid JSON"):
        build_asset_gc_plan(
            repository_root=tmp_path,
            planned_at=PLANNED_AT,
        )


def test_gc_plan_does_not_make_coverage_or_run_scratch_a_root(tmp_path: Path):
    from trading_os.research_assets.asset_gc import build_asset_gc_plan

    _write(tmp_path / "coverage" / "cn-a" / "screening.jsonl", "")
    _write(tmp_path / "coverage" / "cn-a" / "tmp" / "orphan.json", "{}")
    _write(tmp_path / "automation" / "runs" / "run-1" / ".cache" / "orphan.bin", b"x")

    plan = build_asset_gc_plan(
        repository_root=tmp_path,
        planned_at=PLANNED_AT,
    )

    proposed = {item["path"]: item for item in plan["proposed_candidates"]}
    assert proposed["coverage/cn-a/tmp/orphan.json"]["category"] == "scratch_or_cache"
    assert (
        proposed["automation/runs/run-1/.cache/orphan.bin"]["category"]
        == "scratch_or_cache"
    )


def test_assets_gc_cli_writes_plan_without_deleting_candidates(
    tmp_path: Path,
    capsys,
):
    from trading_os.cli import main

    source = tmp_path / "research" / "companies" / "CN" / "000001" / "sources"
    _write(source / "orphan.pdf", b"do-not-delete")
    before = (source / "orphan.pdf").read_bytes()

    assert (
        main(
            [
                "assets",
                "gc",
                "--plan",
                "--repository-root",
                str(tmp_path),
                "--output",
                "research/archives/gc-plans/test-plan.json",
                "--at",
                PLANNED_AT.isoformat(),
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["delete_performed"] is False
    assert summary["proposed_candidate_count"] == 1
    assert (source / "orphan.pdf").read_bytes() == before
    assert (tmp_path / "research" / "archives" / "gc-plans" / "test-plan.json").is_file()


def test_gc_plan_output_is_confined_and_never_overwrites_conflicting_file(
    tmp_path: Path,
):
    from trading_os.research_assets.asset_gc import (
        AssetGcError,
        build_asset_gc_plan,
    )

    _write(
        tmp_path / "research" / "companies" / "CN" / "000001" / "sources" / "orphan.pdf",
        b"candidate",
    )
    with pytest.raises(AssetGcError, match="research/archives/gc-plans"):
        build_asset_gc_plan(
            repository_root=tmp_path,
            planned_at=PLANNED_AT,
            output_path="coverage/gc-plan.json",
        )
    assert not (tmp_path / "coverage" / "gc-plan.json").exists()

    conflict = tmp_path / "research" / "archives" / "gc-plans" / "existing.json"
    _write(conflict, b"unrelated-existing-content")
    before = conflict.read_bytes()
    with pytest.raises(AssetGcError, match="conflicts with an existing file"):
        build_asset_gc_plan(
            repository_root=tmp_path,
            planned_at=PLANNED_AT,
            output_path=conflict,
        )
    assert conflict.read_bytes() == before


def test_gc_plan_detects_candidate_drift_after_stable_hash(
    tmp_path: Path,
    monkeypatch,
):
    import trading_os.research_assets.asset_gc as asset_gc

    source = (
        tmp_path
        / "research"
        / "companies"
        / "CN"
        / "000001"
        / "sources"
        / "orphan.pdf"
    )
    _write(source, b"before")
    real_snapshot = asset_gc._stable_candidate_snapshot

    def snapshot_then_mutate(path: Path, *, hash_content: bool):
        snapshot = real_snapshot(path, hash_content=hash_content)
        if path == source:
            path.write_bytes(b"after-is-different")
        return snapshot

    monkeypatch.setattr(asset_gc, "_stable_candidate_snapshot", snapshot_then_mutate)

    with pytest.raises(asset_gc.AssetGcError, match="managed file changed"):
        asset_gc.build_asset_gc_plan(
            repository_root=tmp_path,
            planned_at=PLANNED_AT,
        )


def test_gc_plan_detects_new_root_added_during_scan(tmp_path: Path, monkeypatch):
    import trading_os.research_assets.asset_gc as asset_gc

    source = (
        tmp_path
        / "research"
        / "companies"
        / "CN"
        / "000001"
        / "sources"
        / "orphan.pdf"
    )
    _write(source, b"candidate")
    real_snapshot = asset_gc._stable_candidate_snapshot

    def snapshot_then_add_root(path: Path, *, hash_content: bool):
        snapshot = real_snapshot(path, hash_content=hash_content)
        _write(tmp_path / "coverage" / "cn-a" / "new-state.json", "{}")
        return snapshot

    monkeypatch.setattr(asset_gc, "_stable_candidate_snapshot", snapshot_then_add_root)

    with pytest.raises(asset_gc.AssetGcError, match="managed file set changed"):
        asset_gc.build_asset_gc_plan(
            repository_root=tmp_path,
            planned_at=PLANNED_AT,
        )


def test_gc_plan_detects_existing_root_content_drift(tmp_path: Path, monkeypatch):
    import trading_os.research_assets.asset_gc as asset_gc

    company = tmp_path / "research" / "companies" / "CN" / "000001"
    report = company / "reports" / "live.md"
    _write(report, "initial root")
    _write(company / "sources" / "orphan.pdf", b"candidate")
    real_snapshot = asset_gc._stable_candidate_snapshot

    def snapshot_then_mutate_root(path: Path, *, hash_content: bool):
        snapshot = real_snapshot(path, hash_content=hash_content)
        report.write_text("changed root contents", encoding="utf-8")
        return snapshot

    monkeypatch.setattr(asset_gc, "_stable_candidate_snapshot", snapshot_then_mutate_root)

    with pytest.raises(asset_gc.AssetGcError, match="managed file changed"):
        asset_gc.build_asset_gc_plan(
            repository_root=tmp_path,
            planned_at=PLANNED_AT,
        )


def test_gc_plan_output_exclusive_create_loses_race_without_overwrite(
    tmp_path: Path,
    monkeypatch,
):
    import trading_os.research_assets.asset_gc as asset_gc

    _write(
        tmp_path / "research" / "companies" / "CN" / "000001" / "sources" / "orphan.pdf",
        b"candidate",
    )
    output = tmp_path / "research" / "archives" / "gc-plans" / "race.json"
    competing = b"competing-writer"

    def lose_create_race(target: Path):
        target.write_bytes(competing)
        raise FileExistsError

    monkeypatch.setattr(asset_gc, "_open_exclusive", lose_create_race)

    with pytest.raises(asset_gc.AssetGcError, match="conflicts with an existing file"):
        asset_gc.build_asset_gc_plan(
            repository_root=tmp_path,
            planned_at=PLANNED_AT,
            output_path=output,
        )
    assert output.read_bytes() == competing


def test_assets_gc_no_content_hashes_reports_weaker_safety_truthfully(
    tmp_path: Path,
    capsys,
):
    from trading_os.cli import main

    source = b"hash-only-source"
    digest = hashlib.sha256(source).hexdigest()
    company = tmp_path / "research" / "companies" / "CN" / "000001"
    _write(company / "reports" / "live.md", f"sha256: {digest}")
    _write(company / "sources" / "hash-only.pdf", source)

    assert (
        main(
            [
                "assets",
                "gc",
                "--plan",
                "--no-content-hashes",
                "--repository-root",
                str(tmp_path),
                "--output",
                "research/archives/gc-plans/no-hashes.json",
                "--at",
                PLANNED_AT.isoformat(),
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["safety"]["path_references_are_followed"] is True
    assert summary["safety"]["sha256_references_are_followed"] is False
    assert summary["safety"]["hash_only_references_may_be_unprotected"] is True
    assert summary["proposed_candidate_count"] == 1
    assert summary["candidate_sample"][0]["path"].endswith("hash-only.pdf")

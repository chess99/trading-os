from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from trading_os.cli import main
from trading_os.research_assets.legacy_salvage import (
    LEGACY_TAG,
    LegacyCandidateScan,
    LegacyReportCandidate,
    LegacyReportSalvager,
    LegacySalvageError,
)
from trading_os.research_assets.research_flow import (
    CompanyRef,
    ResearchFlow,
    ResearchResult,
    ScreenDecision,
    ValueRange,
)

AT = "2026-08-09T18:00:00+08:00"


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", *args],
        cwd=root,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _old_meta(symbol: str, name: str) -> str:
    return json.dumps(
        {
            "schema_version": 2,
            "identity": {"symbol": symbol, "name": name},
            "valuation": {"fair_value_range": [999, 1999]},
        },
        ensure_ascii=False,
    )


def _current_result(symbol: str, name: str) -> ResearchResult:
    return ResearchResult(
        symbol=symbol,
        name=name,
        outcome="researched",
        summary="当前结论",
        key_logic=("当前逻辑",),
        risks=("当前风险",),
        value_range=ValueRange(10, 20),
        buy_below=12,
        event_triggers=("下一份财报",),
        source_urls=("https://example.com/current",),
        report_markdown=f"# {name}\n\n这是当前有效研究。",
    )


@pytest.fixture
def legacy_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "test")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "core.autocrlf", "false")

    old_reports = {
        "research/companies/CN/000001/reports/2026-07-10-memory-followup.md": (
            "# 甲公司（CN:000001）跟踪研究\n\n"
            "## 估值与买入区\n合理价值区间需要结合现金流。\n\n"
            "## 风险与触发\n财报发布后复核毛利率和现金流。\n\n"
            "来源：https://example.com/old-followup\n"
        ),
        "research/companies/CN/000001/reports/2026-07-12-rapid-triage-a.md": (
            "# 甲公司（CN:000001）快速更新\n\n最新公告没有改变基本判断。\n"
        ),
        "research/companies/CN/000002/reports/2026-07-18-investment-committee-review.md": (
            "# 乙公司（CN:000002）投委会复核\n\n"
            "合理价值、风险、触发条件、现金流和原始披露均已讨论。\n"
            "https://example.com/committee\n"
        ),
        "research/companies/CN/000003/reports/2026-07-07-initial.md": (
            "# 丙公司（CN:000003）初步研究\n\n简短旧报告。\n"
        ),
        "research/companies/CN/000004/reports/2026-07-15-deep-review.md": (
            "# 丁公司（CN:000004）深度复核\n\n"
            "估值、风险、触发、现金流与来源均需要持续核验。\n"
            "https://example.com/deep\n"
        ),
        "research/companies/CN/000005/reports/2026-07-16-memory-followup.md": (
            "# 戊公司跟踪研究\n\n估值、风险、触发和现金流均需复核。\n"
        ),
        "research/companies/CN/300619/reports/2026-07-14-chatgpt.md": (
            "# 先导智能（300450.SZ）深度研究\n\n"
            "这份正文属于另一家公司，不能迁入路径对应的公司。\n"
        ),
    }
    for path, body in old_reports.items():
        _write(root, path, body)
    for ticker, name in {
        "000001": "旧甲公司名",
        "000002": "乙公司",
        "000003": "丙公司",
        "000004": "丁公司",
        "000005": "戊公司",
        "300619": "金银河",
    }.items():
        declared_symbol = "CN:000006" if ticker == "000005" else f"CN:{ticker}"
        _write(
            root,
            f"research/companies/CN/{ticker}/meta.json",
            _old_meta(declared_symbol, name),
        )
    _git(root, "add", "research")
    _git(root, "commit", "-q", "-m", "legacy fixture")
    _git(root, "tag", LEGACY_TAG)

    shutil.rmtree(root / "research")
    flow = ResearchFlow(root)
    flow.register_universe(
        [
            CompanyRef("CN:000001", "甲公司"),
            CompanyRef("CN:000002", "乙公司"),
            CompanyRef("CN:000003", "丙公司"),
            CompanyRef("CN:000004", "丁公司"),
            CompanyRef("CN:000005", "戊公司"),
            CompanyRef("CN:300619", "金银河"),
        ],
        at=AT,
    )
    queued = flow.apply_screening(
        [ScreenDecision("CN:000002", "research_now", "已经有当前正式研究")],
        screen_id="existing-current",
        mode="event",
        at=AT,
    ).enqueued_tasks[0]
    dispatched = flow.dispatch_tasks(limit=1, at=AT)[0]
    assert queued.task_id == dispatched.task_id
    flow.apply_result(_current_result("CN:000002", "乙公司"), task_id=queued.task_id, at=AT)
    flow.validate()
    return root


def _candidate(scan: LegacyCandidateScan, symbol: str, kind: str) -> LegacyReportCandidate:
    candidates = scan.candidates
    return next(
        item for item in candidates if item.symbol == symbol and item.report_kind == kind
    )


def _condensed_result(symbol: str = "CN:000001") -> dict:
    return {
        "symbol": symbol,
        "name": "甲公司（已核验）",
        "outcome": "researched",
        "summary": "现金流改善可能带来重估，但仍需下一期财报确认。",
        "key_logic": ["业务质量改善", "现金流决定估值上沿"],
        "risks": ["改善无法持续", "行业需求回落"],
        "value_range": {"low": 18, "high": 26, "currency": "CNY"},
        "price_levels": [
            {"id": "attention", "label": "关注价", "threshold": 19, "rearm_above": 20}
        ],
        "event_triggers": ["下一期财报发布"],
        "source_urls": ["https://example.com/revalidated-primary-source"],
        "report_markdown": (
            "# 甲公司当前研究\n\n"
            "旧稿中仍有效的是业务与现金流框架；这里是重新核验后的压缩结论。"
        ),
    }


def _migrate_decision(candidate: LegacyReportCandidate, result: dict | None = None) -> dict:
    return {
        "candidate_id": candidate.candidate_id,
        "symbol": candidate.symbol,
        "legacy_path": candidate.legacy_path,
        "legacy_blob_oid": candidate.legacy_blob_oid,
        "action": "migrate",
        "reason": "已结合最新公开披露重新核验，保留仍有效的框架",
        "reviewed_legacy_paths": [candidate.legacy_path, *candidate.newer_report_paths],
        "result": result or _condensed_result(candidate.symbol),
    }


def test_candidate_scan_is_batched_read_only_and_excludes_current(legacy_repo: Path):
    flow = ResearchFlow(legacy_repo)
    before_states = flow.read_states()
    before_queue = flow.list_tasks()
    before_watchlist = flow.read_watchlist()

    scan = LegacyReportSalvager(legacy_repo).list_candidates(limit=20)

    assert scan.tag == LEGACY_TAG
    assert scan.reports_scanned == 7
    assert scan.reports_excluded_for_current == 1
    assert {item.symbol for item in scan.candidates}.isdisjoint({"CN:000002", "CN:300619"})
    assert scan.candidates[0].report_kind == "deep_review"
    followup = _candidate(scan, "CN:000001", "followup")
    assert followup.name == "旧甲公司名"
    assert followup.newer_report_paths == (
        "research/companies/CN/000001/reports/2026-07-12-rapid-triage-a.md",
    )
    assert any(
        item["legacy_path"].endswith("300619/reports/2026-07-14-chatgpt.md")
        and item["reason"] == "identity_mismatch"
        and item["detected_symbols"] == ("CN:300450",)
        for item in scan.identity_mismatches
    )
    assert any(
        item["legacy_path"].endswith("000005/reports/2026-07-16-memory-followup.md")
        and item["reason"] == "metadata_identity_mismatch"
        and item["detected_symbols"] == ("CN:000006",)
        for item in scan.identity_mismatches
    )
    assert flow.read_states() == before_states
    assert flow.list_tasks() == before_queue == ()
    assert flow.read_watchlist() == before_watchlist


def test_apply_migrates_only_explicit_condensation_through_current_flow(legacy_repo: Path):
    salvager = LegacyReportSalvager(legacy_repo)
    scan = salvager.list_candidates(limit=20)
    followup = _candidate(scan, "CN:000001", "followup")
    deep_review = _candidate(scan, "CN:000004", "deep_review")
    payload = {
        "batch_id": "fixture-a",
        "at": AT,
        "decisions": [
            _migrate_decision(followup),
            {
                "candidate_id": deep_review.candidate_id,
                "symbol": deep_review.symbol,
                "legacy_path": deep_review.legacy_path,
                "legacy_blob_oid": deep_review.legacy_blob_oid,
                "action": "skip",
                "reason": "基本面信息已经过期",
            },
        ],
    }

    result = salvager.apply_decisions(payload)

    assert [item["symbol"] for item in result.migrated] == ["CN:000001"]
    assert [item["symbol"] for item in result.skipped] == ["CN:000004"]
    flow = ResearchFlow(legacy_repo)
    states = {item["symbol"]: item for item in flow.read_states()}
    migrated = states["CN:000001"]
    assert migrated["status"] == "researched"
    assert migrated["name"] == "甲公司（已核验）"
    assert migrated["value_range"] == {"currency": "CNY", "high": 26.0, "low": 18.0}
    assert "999" not in json.dumps(migrated, ensure_ascii=False)
    assert followup.legacy_path in migrated["last_screening"]["reason"]
    assert states["CN:000004"]["status"] == "unseen"
    current = legacy_repo / "research/companies/CN/000001/current.md"
    assert current.read_text(encoding="utf-8") == _condensed_result()["report_markdown"] + "\n"
    assert flow.list_tasks() == ()
    flow.validate()


def test_apply_requires_newer_reports_to_be_reviewed_before_migration(legacy_repo: Path):
    salvager = LegacyReportSalvager(legacy_repo)
    candidate = _candidate(salvager.list_candidates(limit=20), "CN:000001", "followup")
    decision = _migrate_decision(candidate)
    decision["reviewed_legacy_paths"] = [candidate.legacy_path]

    with pytest.raises(LegacySalvageError, match="has not reviewed"):
        salvager.apply_decisions(
            {"batch_id": "missing-newer-review", "at": AT, "decisions": [decision]}
        )

    state = next(
        item for item in ResearchFlow(legacy_repo).read_states() if item["symbol"] == "CN:000001"
    )
    assert state["status"] == "unseen"
    assert ResearchFlow(legacy_repo).list_tasks() == ()


def test_apply_rejects_raw_report_restore_and_tampered_identity(legacy_repo: Path):
    salvager = LegacyReportSalvager(legacy_repo)
    candidate = _candidate(salvager.list_candidates(limit=20), "CN:000004", "deep_review")
    old_body = _git(legacy_repo, "show", f"{LEGACY_TAG}:{candidate.legacy_path}")
    copied = _condensed_result("CN:000004")
    copied["name"] = "丁公司"
    copied["report_markdown"] = old_body
    copied_decision = _migrate_decision(candidate, copied)

    with pytest.raises(LegacySalvageError, match="raw legacy report"):
        salvager.apply_decisions(
            {"batch_id": "raw-copy", "at": AT, "decisions": [copied_decision]}
        )

    tampered = _migrate_decision(candidate, _condensed_result("CN:000004"))
    tampered["legacy_blob_oid"] = "0" * len(candidate.legacy_blob_oid)
    with pytest.raises(LegacySalvageError, match="identity changed"):
        salvager.apply_decisions(
            {"batch_id": "tampered", "at": AT, "decisions": [tampered]}
        )
    assert ResearchFlow(legacy_repo).list_tasks() == ()
    assert not (legacy_repo / "research/companies/CN/000004/current.md").exists()


def test_body_symbol_mismatch_is_never_migratable(legacy_repo: Path):
    commit = _git(legacy_repo, "rev-parse", f"refs/tags/{LEGACY_TAG}^{{commit}}")
    path = "research/companies/CN/300619/reports/2026-07-14-chatgpt.md"
    blob_oid = _git(legacy_repo, "rev-parse", f"{LEGACY_TAG}:{path}")
    candidate_id = hashlib.sha256(f"{commit}\0{path}\0{blob_oid}".encode()).hexdigest()[:24]
    decision = {
        "candidate_id": candidate_id,
        "symbol": "CN:300619",
        "legacy_path": path,
        "legacy_blob_oid": blob_oid,
        "action": "migrate",
        "reason": "错误地尝试迁移",
        "reviewed_legacy_paths": [path],
        "result": _condensed_result("CN:300619"),
    }

    with pytest.raises(LegacySalvageError, match="identity_mismatch.*CN:300450"):
        LegacyReportSalvager(legacy_repo).apply_decisions(
            {"batch_id": "identity-mismatch", "at": AT, "decisions": [decision]}
        )
    assert not (legacy_repo / "research/companies/CN/300619/current.md").exists()


def test_cli_lists_candidates_and_template_is_valid(legacy_repo: Path, capsys):
    code = main(
        [
            "--root",
            str(legacy_repo),
            "legacy-salvage",
            "candidates",
            "--limit",
            "2",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0, captured.err
    output = json.loads(captured.out)
    assert output["tag"] == LEGACY_TAG
    assert len(output["candidates"]) == 2
    template = Path(__file__).resolve().parents[1] / "templates/legacy-salvage-decisions.json"
    assert json.loads(template.read_text(encoding="utf-8"))["decisions"]
    assert asdict(LegacyReportSalvager(legacy_repo).list_candidates(limit=1))["candidates"]

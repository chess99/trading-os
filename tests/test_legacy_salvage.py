from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from trading_os.cli import main
from trading_os.research_assets.legacy_salvage import (
    LEGACY_TAG,
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


def _meta(symbol: str, name: str) -> str:
    return json.dumps(
        {"schema_version": 2, "identity": {"symbol": symbol, "name": name}},
        ensure_ascii=False,
    )


def _current_result() -> ResearchResult:
    return ResearchResult(
        symbol="CN:000001",
        name="甲公司",
        outcome="covered",
        summary="当前结论",
        key_logic=("当前逻辑",),
        risks=("当前风险",),
        value_range=ValueRange(10, 20),
        event_triggers=("下一份财报",),
        source_urls=("https://example.com/current",),
        information_cutoff=AT,
        report_markdown=(
            "# 甲公司当前研究\n\n"
            "信息截止：2026-08-09\n\n"
            "## 一句话结论\n\n这是当前有效研究。\n\n"
            "## 财务质量\n\n现金收益可以复核。\n\n"
            "## 估值与核心合理价值区间\n\n核心合理价值区间：10—20 元。\n\n"
            "## 核心风险\n\n当前风险需要持续观察。\n\n"
            "## 来源清单\n\n- https://example.com/current"
        ),
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
        "research/companies/CN/000001/reports/2026-07-07-initial.md": (
            "# 甲公司（CN:000001）初步研究\n\n简短旧报告。\n"
        ),
        "research/companies/CN/000001/reports/2026-07-11-memory-followup.md": (
            "# 甲公司（CN:000001）跟踪研究\n\n"
            "## 商业模式与估值\n现金流决定合理价值区间。\n\n"
            "## 风险与触发\n财报发布后复核毛利率和现金流。\n\n"
            "来源：https://example.com/old-followup\n"
        ),
        "research/companies/CN/000002/reports/2026-07-18-investment-committee-review.md": (
            "# 乙公司（CN:000002）投委会流程记录\n\n不应优先保留。\n"
        ),
        "research/companies/CN/000002/reports/2026-07-16-initial-research-v2.md": (
            "# 乙公司（CN:000002）正式研究\n\n"
            "商业模式、现金流、估值、风险和来源均已讨论。\n"
            "https://example.com/b\n"
        ),
        "research/companies/CN/000003/reports/2026-07-10-initial.md": (
            "# 丙公司（CN:000003）初步研究\n\n只有这一份，但仍作为历史资料保留。\n"
        ),
        "research/companies/CN/000004/reports/2026-07-15-deep-review.md": (
            "# 另一家公司（CN:300450）深度研究\n\n路径身份错误。\n"
        ),
        "research/companies/CN/000004/reports/2026-07-10-initial.md": (
            "# 丁公司（CN:000004）初步研究\n\n正确身份的旧报告。\n"
        ),
        "research/companies/CN/000005/reports/2026-07-10-initial.md": (
            "# 戊公司初步研究\n\n正文和元数据均不能证明路径身份。\n"
        ),
    }
    for path, body in old_reports.items():
        _write(root, path, body)
    identities = {
        "000001": ("CN:000001", "甲公司"),
        "000002": ("CN:000002", "乙公司"),
        "000003": ("CN:000003", "丙公司"),
        "000004": ("CN:000004", "丁公司"),
        "000005": ("CN:000006", "错误元数据"),
    }
    for ticker, (symbol, name) in identities.items():
        _write(root, f"research/companies/CN/{ticker}/meta.json", _meta(symbol, name))
    _git(root, "add", "research")
    _git(root, "commit", "-q", "-m", "legacy fixture")
    _git(root, "tag", LEGACY_TAG)

    shutil.rmtree(root / "research")
    flow = ResearchFlow(root)
    flow.register_universe(
        [CompanyRef(f"CN:{ticker}", name) for ticker, (_symbol, name) in identities.items()],
        at=AT,
    )
    first = flow.apply_screening(
        [ScreenDecision("CN:000001", "research_now", "建立当前覆盖")],
        screen_id="current-a",
        mode="event",
        at=AT,
    ).enqueued_tasks[0]
    flow.dispatch_tasks(limit=1, at=AT)
    flow.apply_result(_current_result(), task_id=first.task_id, at=AT)
    flow.apply_screening(
        [ScreenDecision("CN:000002", "research_now", "保留一个活动任务验证隔离")],
        screen_id="queued-b",
        mode="event",
        at=AT,
    )
    flow.validate()
    return root


def _facts(root: Path) -> tuple[bytes, bytes, bytes]:
    return tuple(
        (root / path).read_bytes()
        for path in (
            "coverage/cn-a/research_state.jsonl",
            "coverage/cn-a/research_queue.jsonl",
            "research/watchlist.jsonl",
        )
    )


def test_candidate_scan_is_read_only_and_includes_current_companies(legacy_repo: Path):
    before = _facts(legacy_repo)
    scan = LegacyReportSalvager(legacy_repo).list_candidates(limit=20)

    assert scan.tag == LEGACY_TAG
    assert scan.reports_scanned == 8
    assert scan.reports_excluded_for_current == 0
    assert "CN:000001" in {item.symbol for item in scan.candidates}
    assert all(item.report_kind != "process_review" for item in scan.candidates)
    assert any(
        item["legacy_path"].endswith("000004/reports/2026-07-15-deep-review.md")
        and item["reason"] == "identity_mismatch"
        for item in scan.identity_mismatches
    )
    assert _facts(legacy_repo) == before


def test_archive_keeps_one_best_report_per_company_without_touching_facts(
    legacy_repo: Path,
):
    before = _facts(legacy_repo)
    result = LegacyReportSalvager(legacy_repo).archive_best()

    assert result.companies_seen == 5
    assert result.companies_archived == 4
    assert result.companies_skipped == 1
    assert _facts(legacy_repo) == before

    archive_a = legacy_repo / "research/companies/CN/000001/legacy/2026-07-11.md"
    assert archive_a.is_file()
    body = archive_a.read_text(encoding="utf-8")
    assert "仅供历史参考，不代表当前公司状态、估值或价格结论" in body
    assert "现金流决定合理价值区间" in body
    assert not (legacy_repo / "research/companies/CN/000001/legacy/2026-07-07.md").exists()
    assert (legacy_repo / "research/companies/CN/000002/legacy/2026-07-16.md").is_file()
    assert (legacy_repo / "research/companies/CN/000004/legacy/2026-07-10.md").is_file()
    assert not (legacy_repo / "research/companies/CN/000005/legacy").exists()
    assert (legacy_repo / "research/companies/CN/000001/reports/2026-08-09.md").is_file()


def test_archive_is_idempotent_but_refuses_a_conflicting_local_archive(legacy_repo: Path):
    salvager = LegacyReportSalvager(legacy_repo)
    first = salvager.archive_best()
    second = salvager.archive_best()
    assert first.companies_archived == 4
    assert second.companies_archived == 0
    assert second.already_archived == 4

    conflict = legacy_repo / "research/companies/CN/000001/legacy/manual.md"
    conflict.write_text("用户自己的历史文件", encoding="utf-8")
    with pytest.raises(LegacySalvageError, match="different report for CN:000001"):
        salvager.archive_best()


def test_cli_archives_best_reports(legacy_repo: Path, capsys):
    code = main(["--root", str(legacy_repo), "legacy-salvage", "archive-best"])
    captured = capsys.readouterr()
    assert code == 0, captured.err
    output = json.loads(captured.out)
    assert output["companies_archived"] == 4
    assert output["companies_skipped"] == 1

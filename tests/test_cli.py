from __future__ import annotations

import json
from pathlib import Path

import pytest

import trading_os.cli as cli_module
from trading_os.cli import main
from trading_os.research_assets.market_data import Announcement

AT = "2026-08-08T17:00:00+08:00"
ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _call(tmp_path: Path, capsys: pytest.CaptureFixture[str], *args: str) -> dict:
    code = main(["--root", str(tmp_path), *args])
    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert captured.err == ""
    return json.loads(captured.out)


def _full_result(symbol: str, task_id: str | None = None) -> dict:
    payload = {
        "symbol": symbol,
        "name": "示例公司",
        "outcome": "covered",
        "summary": "需求成立，现金流仍需验证。",
        "key_logic": ["需求增长", "现金流转化决定估值"],
        "risks": ["客户集中", "资本开支回报不及预期"],
        "value_range": {"low": 58, "high": 82, "currency": "CNY"},
        "event_triggers": ["下一期财报发布"],
        "source_urls": ["https://example.com/report"],
        "information_cutoff": AT,
        "report_markdown": "# 示例公司\n\n需求成立，但现金流转化仍需验证。",
    }
    return {"task_id": task_id, "at": AT, "result": payload} if task_id else payload


def _screen_and_dispatch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    symbol: str,
    *,
    trigger_id: str,
) -> str:
    source = _write(
        tmp_path / f"screen-{trigger_id}.json",
        {
            "screen_id": trigger_id,
            "mode": "event",
            "at": AT,
            "decisions": [
                {
                    "symbol": symbol,
                    "route": "research_now",
                    "reason": "值得完整研究",
                }
            ],
        },
    )
    queued = _call(
        tmp_path,
        capsys,
        "screen",
        "record",
        "--input",
        str(source),
    )
    dispatched = _call(tmp_path, capsys, "research", "next", "--limit", "1", "--at", AT)
    assert dispatched["count"] == 1
    assert dispatched["tasks"][0]["task_id"] == queued["enqueued"][0]["task_id"]
    return dispatched["tasks"][0]["task_id"]


def test_help_contains_only_the_compact_workflow(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    assert exc.value.code == 0
    output = capsys.readouterr().out
    for command in (
        "status",
        "validate",
        "universe",
        "screen",
        "research",
        "updates",
        "watchlist",
        "events",
    ):
        assert command in output
    for removed in ("underwriting", "challenger", "allocation", "calibration", "claim"):
        assert removed not in output.lower()

    with pytest.raises(SystemExit) as research_exc:
        main(["research", "--help"])
    assert research_exc.value.code == 0
    assert "enqueue" not in capsys.readouterr().out


def test_research_assets_package_exports_only_the_compact_flow():
    import trading_os.research_assets as assets

    assert assets.ResearchFlow
    assert assets.ResearchResult
    assert assets.ResearchUpdate
    for removed in (
        "AssetValidationError",
        "CompanyTimelineError",
        "DetailLevel",
        "publish_rapid_triage_to_company_timeline",
        "write_index",
    ):
        assert not hasattr(assets, removed)


def test_empty_status_and_validate_are_readable(tmp_path: Path, capsys):
    status = _call(tmp_path, capsys, "status")
    assert status == {
        "companies": 0,
        "active": 0,
        "candidates": 0,
        "covered": 0,
        "ignored": 0,
        "queued": 0,
        "inactive": 0,
        "running": 0,
        "stale": 0,
        "unseen": 0,
        "watchlist": 0,
    }
    validated = _call(tmp_path, capsys, "validate")
    assert validated["ok"] is True


@pytest.mark.parametrize("jsonl", [False, True])
def test_universe_register_accepts_wrapper_json_and_jsonl(tmp_path: Path, capsys, jsonl: bool):
    companies = [
        {"symbol": "CN:000001", "name": "甲公司"},
        {"symbol": "CN:000002", "name": "乙公司"},
    ]
    source = tmp_path / ("universe.jsonl" if jsonl else "universe.json")
    if jsonl:
        source.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in companies) + "\n",
            encoding="utf-8",
        )
    else:
        _write(source, {"companies": companies})

    output = _call(tmp_path, capsys, "universe", "register", "--input", str(source), "--at", AT)

    assert output == {"added": 2, "companies": 2}


def test_universe_sync_uses_a_complete_active_snapshot(tmp_path: Path, capsys):
    first = _write(
        tmp_path / "first.json",
        {"companies": [{"symbol": "CN:000001"}, {"symbol": "CN:000002"}]},
    )
    second = _write(
        tmp_path / "second.json",
        {"companies": [{"symbol": "CN:000002"}, {"symbol": "CN:000003"}]},
    )
    _call(tmp_path, capsys, "universe", "register", "--input", str(first), "--at", AT)

    synced = _call(tmp_path, capsys, "universe", "sync", "--input", str(second), "--at", AT)
    status = _call(tmp_path, capsys, "status")

    assert synced == {
        "added": 1,
        "enqueued_tasks": [],
        "inactivated": 1,
        "reactivated": 0,
        "renamed": 0,
        "total": 2,
    }
    assert (status["companies"], status["active"], status["inactive"]) == (3, 2, 1)


def test_screen_record_only_enqueues_research_now(tmp_path: Path, capsys):
    source = _write(
        tmp_path / "screen.json",
        {
            "screen_id": "baseline-2026-08-08",
            "mode": "baseline",
            "at": AT,
            "decisions": [
                {
                    "symbol": "CN:000001",
                    "route": "ignore",
                    "reason": "暂不值得研究",
                    "event_triggers": ["下一份年报出现业务转型"],
                },
                {
                    "symbol": "CN:000002",
                    "route": "ignore",
                    "reason": "当前没有值得研究的新事实",
                },
                {"symbol": "CN:000003", "route": "research_now", "reason": "出现拐点"},
            ],
        },
    )

    output = _call(tmp_path, capsys, "screen", "record", "--input", str(source))

    assert (output["ignore"], output["research_now"]) == (2, 1)
    assert [task["symbol"] for task in output["enqueued"]] == ["CN:000003"]


def test_screen_next_and_explicit_requeue_have_no_fixed_concurrency(tmp_path: Path, capsys):
    source = _write(
        tmp_path / "three-research-tasks.json",
        {
            "screen_id": "2026-h1",
            "mode": "event",
            "at": AT,
            "decisions": [
                {"symbol": symbol, "route": "research_now", "reason": "半年报变化"}
                for symbol in ("CN:000001", "CN:000002", "CN:000003")
            ],
        },
    )
    screened = _call(tmp_path, capsys, "screen", "record", "--input", str(source))
    assert len(screened["enqueued"]) == 3

    dispatched = _call(tmp_path, capsys, "research", "next", "--limit", "2", "--at", AT)
    assert dispatched["count"] == 2
    task_id = dispatched["tasks"][0]["task_id"]
    restored = _call(tmp_path, capsys, "research", "requeue", task_id)
    assert restored["task"]["status"] == "queued"

    from_end = _call(
        tmp_path,
        capsys,
        "research",
        "next",
        "--limit",
        "1",
        "--from-end",
        "--at",
        AT,
    )
    assert from_end["count"] == 1


def test_research_complete_writes_dated_report_and_full_watchlist(tmp_path: Path, capsys):
    task_id = _screen_and_dispatch(
        tmp_path,
        capsys,
        "CN:601138",
        trigger_id="initial",
    )
    result = _write(tmp_path / "result.json", _full_result("CN:601138", task_id))

    completed = _call(tmp_path, capsys, "research", "complete", "--input", str(result))
    listed = _call(tmp_path, capsys, "watchlist", "list")

    assert completed["status"] == "covered"
    assert completed["report_path"] == ("research/companies/CN/601138/reports/2026-08-08.md")
    assert (tmp_path / completed["report_path"]).is_file()
    company = listed["companies"][0]
    assert company["key_logic"] == ["需求增长", "现金流转化决定估值"]
    assert company["value_range"] == {"currency": "CNY", "high": 82.0, "low": 58.0}
    assert "price_levels" not in company


def test_retired_security_price_fields_are_rejected(tmp_path: Path, capsys):
    task_id = _screen_and_dispatch(tmp_path, capsys, "CN:601138", trigger_id="old-input")
    payload = _full_result("CN:601138", task_id)
    payload["result"]["price_levels"] = [{"id": "attention", "threshold": 55}]
    source = _write(tmp_path / "old-result.json", payload)

    code = main(
        ["--root", str(tmp_path), "research", "complete", "--input", str(source)]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "已退役字段" in json.loads(captured.err)["error"]


def test_watchlist_has_no_close_price_commands(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["watchlist", "--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "build" in output and "list" in output
    for removed in ("scan-close", "fetch-close", "run-close"):
        assert removed not in output


def test_watchlist_build_and_validate_detect_a_consistent_projection(tmp_path: Path, capsys):
    task_id = _screen_and_dispatch(
        tmp_path,
        capsys,
        "CN:601138",
        trigger_id="watchlist-fixture",
    )
    result = _write(tmp_path / "result.json", _full_result("CN:601138", task_id))
    _call(tmp_path, capsys, "research", "complete", "--input", str(result), "--at", AT)

    built = _call(tmp_path, capsys, "watchlist", "build")
    validated = _call(tmp_path, capsys, "validate")

    assert built == {"count": 1, "path": "research/watchlist.jsonl"}
    assert validated["status"]["covered"] == 1


def test_updates_record_reaffirms_or_invalidates_without_patching_valuation(
    tmp_path: Path,
    capsys,
):
    task_id = _screen_and_dispatch(tmp_path, capsys, "CN:601138", trigger_id="initial")
    result = _write(tmp_path / "result.json", _full_result("CN:601138", task_id))
    completed = _call(tmp_path, capsys, "research", "complete", "--input", str(result))

    update = _write(
        tmp_path / "update.json",
        {
            "symbol": "CN:601138",
            "title": "合同公告核对",
            "impact": "reaffirmed",
            "reviewed_at": "2026-08-09T17:00:00+08:00",
            "information_cutoff": "2026-08-09T16:00:00+08:00",
            "summary": "合同规模仍在原报告情景内。",
            "analysis": "不改变正常化利润、核心逻辑、风险排序或价值区间。",
            "conclusion": "当前正式报告继续有效。",
            "event_ids": ["event-001"],
            "source_urls": ["https://example.com/announcement"],
        },
    )
    recorded = _call(tmp_path, capsys, "updates", "record", "--input", str(update))
    listed = _call(tmp_path, capsys, "watchlist", "list")
    assert recorded["impact"] == "reaffirmed"
    assert recorded["enqueued_task"] is None
    assert listed["companies"][0]["report_path"] == completed["report_path"]
    assert listed["companies"][0]["value_range"] == completed["value_range"]
    assert (tmp_path / recorded["update_path"]).is_file()


def test_events_fetch_requires_explicit_bootstrap_and_only_advances_after_exact_judgment(
    tmp_path: Path,
    capsys,
    monkeypatch,
):
    universe = _write(
        tmp_path / "universe.json",
        {
            "companies": [
                {"symbol": "CN:000001", "name": "平安银行"},
                {"symbol": "CN:601138", "name": "工业富联"},
            ]
        },
    )
    _call(
        tmp_path,
        capsys,
        "universe",
        "register",
        "--input",
        str(universe),
        "--at",
        AT,
    )

    code = main(["--root", str(tmp_path), "events", "fetch"])
    error = json.loads(capsys.readouterr().err)
    assert code == 1
    assert "--since" in error["error"]

    announcement = Announcement(
        announcement_id="1225000001",
        symbol="CN:000001",
        title="2026年半年度报告",
        published_at="2026-08-08T08:00:00+08:00",
        url="https://static.cninfo.com.cn/finalpage/2026-08-08/1225000001.PDF",
    )
    calls: list[tuple[tuple[str, ...], str, str]] = []

    def fake_discover(companies, start, end):
        calls.append((tuple(companies), start, end))
        return (announcement,) if len(calls) == 1 else ()

    monkeypatch.setattr(
        cli_module,
        "discover_cninfo_announcements_for_companies",
        fake_discover,
    )
    packet = _call(
        tmp_path,
        capsys,
        "events",
        "fetch",
        "--since",
        "2026-08-08T00:00:00+08:00",
        "--until",
        "2026-08-09T00:00:00+08:00",
    )
    packet_path = _write(tmp_path / "event-packet.json", packet)
    incomplete = _write(tmp_path / "incomplete.json", {"successfully_judged_ids": []})

    code = main(
        [
            "--root",
            str(tmp_path),
            "events",
            "complete",
            "--packet",
            str(packet_path),
            "--input",
            str(incomplete),
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "missing" in json.loads(captured.err)["error"]
    assert not (tmp_path / "coverage/cn-a/event_scan_state.json").exists()

    complete = _write(
        tmp_path / "complete.json",
        {"successfully_judged_ids": ["1225000001"]},
    )
    advanced = _call(
        tmp_path,
        capsys,
        "events",
        "complete",
        "--packet",
        str(packet_path),
        "--input",
        str(complete),
    )
    assert advanced["advanced"] is True
    assert advanced["last_successful_at"] == "2026-08-09T00:00:00+08:00"

    next_packet = _call(
        tmp_path,
        capsys,
        "events",
        "fetch",
        "--until",
        "2026-08-10T00:00:00+08:00",
    )
    assert next_packet["announcement_count"] == 0
    assert calls[0][0] == ("CN:000001", "CN:601138")
    assert calls[1][1] == "2026-08-08T00:00:00+08:00"


def test_events_fetch_can_write_a_utf8_packet_inside_the_repository(
    tmp_path: Path,
    capsys,
    monkeypatch,
):
    monkeypatch.setattr(
        cli_module,
        "discover_cninfo_announcements_for_companies",
        lambda _companies, _start, _end: (),
    )
    result = _call(
        tmp_path,
        capsys,
        "events",
        "fetch",
        "--since",
        "2026-08-08T00:00:00+08:00",
        "--until",
        "2026-08-09T00:00:00+08:00",
        "--output",
        "tmp/event-packet.json",
    )

    packet_path = tmp_path / result["packet_path"]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assert result["announcement_count"] == 0
    assert packet["scan_start"] == "2026-08-08T00:00:00+08:00"
    assert packet["announcements"] == []


def test_research_complete_rejects_missing_task_id(tmp_path: Path, capsys):
    result = _write(tmp_path / "result.json", _full_result("CN:601138"))

    code = main(
        [
            "--root",
            str(tmp_path),
            "research",
            "complete",
            "--input",
            str(result),
            "--at",
            AT,
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "task_id" in json.loads(captured.err)["error"]
    assert not (tmp_path / "coverage/cn-a/research_state.jsonl").exists()


def test_research_complete_rejects_a_task_that_was_not_dispatched(tmp_path: Path, capsys):
    source = _write(
        tmp_path / "queued-screen.json",
        {
            "screen_id": "not-dispatched",
            "mode": "event",
            "at": AT,
            "decisions": [
                {
                    "symbol": "CN:601138",
                    "route": "research_now",
                    "reason": "值得完整研究",
                }
            ],
        },
    )
    queued = _call(
        tmp_path,
        capsys,
        "screen",
        "record",
        "--input",
        str(source),
    )
    task_id = queued["enqueued"][0]["task_id"]
    result = _write(tmp_path / "result.json", _full_result("CN:601138", task_id))

    code = main(
        [
            "--root",
            str(tmp_path),
            "research",
            "complete",
            "--input",
            str(result),
            "--at",
            AT,
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "must be running" in json.loads(captured.err)["error"]
    dispatched = _call(tmp_path, capsys, "research", "next", "--limit", "1", "--at", AT)
    assert dispatched["tasks"][0]["task_id"] == task_id


def test_invalid_input_returns_one_compact_json_error(tmp_path: Path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")

    code = main(["--root", str(tmp_path), "universe", "register", "--input", str(bad)])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error["ok"] is False
    assert error["error"]


def test_input_templates_are_valid_and_contain_only_the_compact_model():
    names = (
        "universe.json",
        "screen-decisions.json",
        "research-result.json",
        "research-update.json",
        "event-judgments.json",
    )
    combined = ""
    for name in names:
        text = (ROOT / "templates" / name).read_text(encoding="utf-8")
        assert json.loads(text)
        combined += text.lower()
    for removed in ("underwriting", "challenger", "allocation", "calibration", "claim"):
        assert removed not in combined
    for retired in ("price_levels", "price_monitor", "buy_below", "rearm_above"):
        assert retired not in combined

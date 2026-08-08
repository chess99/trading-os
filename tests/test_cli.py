from __future__ import annotations

import json
from pathlib import Path

import pytest

from trading_os.cli import main

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
        "outcome": "researched",
        "summary": "需求成立，现金流仍需验证。",
        "key_logic": ["需求增长", "现金流转化决定估值"],
        "risks": ["客户集中", "资本开支回报不及预期"],
        "value_range": {"low": 58, "high": 82, "currency": "CNY"},
        "price_levels": [
            {"id": "attention", "label": "关注区", "threshold": 55, "rearm_above": 57},
            {"id": "attractive", "label": "高吸引力区", "threshold": 50, "rearm_above": 52},
        ],
        "event_triggers": ["下一期财报发布"],
        "source_urls": ["https://example.com/report"],
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
    for command in ("status", "validate", "universe", "screen", "research", "watchlist"):
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
    assert assets.PriceLevel
    assert assets.ResearchResult
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
        "dispatched": 0,
        "ignored": 0,
        "queued": 0,
        "researched": 0,
        "unseen": 0,
        "watched": 0,
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
                    "route": "watch",
                    "reason": "等待价格",
                    "price_levels": [{"id": "buy", "label": "关注区", "threshold": 10}],
                },
                {"symbol": "CN:000003", "route": "research_now", "reason": "出现拐点"},
            ],
        },
    )

    output = _call(tmp_path, capsys, "screen", "record", "--input", str(source))

    assert (output["ignore"], output["watch"], output["research_now"]) == (1, 1, 1)
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


def test_research_complete_writes_current_report_and_full_watchlist(tmp_path: Path, capsys):
    task_id = _screen_and_dispatch(
        tmp_path,
        capsys,
        "CN:601138",
        trigger_id="initial",
    )
    result = _write(tmp_path / "result.json", _full_result("CN:601138", task_id))

    completed = _call(tmp_path, capsys, "research", "complete", "--input", str(result))
    listed = _call(tmp_path, capsys, "watchlist", "list")

    assert completed["status"] == "researched"
    assert completed["report_path"] == "research/companies/CN/601138/current.md"
    assert (tmp_path / completed["report_path"]).is_file()
    company = listed["companies"][0]
    assert company["key_logic"] == ["需求增长", "现金流转化决定估值"]
    assert [level["id"] for level in company["price_levels"]] == [
        "attention",
        "attractive",
    ]


def test_watchlist_close_scan_emits_independent_price_levels(tmp_path: Path, capsys):
    task_id = _screen_and_dispatch(
        tmp_path,
        capsys,
        "CN:601138",
        trigger_id="price-scan-fixture",
    )
    result = _write(tmp_path / "result.json", _full_result("CN:601138", task_id))
    _call(tmp_path, capsys, "research", "complete", "--input", str(result), "--at", AT)
    quotes = _write(
        tmp_path / "quotes.json",
        {"trading_date": "2026-08-11", "quotes": [{"symbol": "CN:601138", "close": 49}]},
    )

    scanned = _call(
        tmp_path,
        capsys,
        "watchlist",
        "scan-close",
        "--input",
        str(quotes),
        "--at",
        AT,
    )

    assert scanned["hit_count"] == 2
    assert [hit["level_id"] for hit in scanned["hits"]] == ["attention", "attractive"]
    assert all("enqueued" not in hit and "task_id" not in hit for hit in scanned["hits"])
    pending = _call(tmp_path, capsys, "research", "next", "--limit", "1", "--at", AT)
    assert pending == {"count": 0, "tasks": []}


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
    assert validated["status"]["researched"] == 1


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
    assert "must be dispatched" in json.loads(captured.err)["error"]
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
        "close-quotes.json",
    )
    combined = ""
    for name in names:
        text = (ROOT / "templates" / name).read_text(encoding="utf-8")
        assert json.loads(text)
        combined += text.lower()
    for removed in ("underwriting", "challenger", "allocation", "calibration", "claim"):
        assert removed not in combined

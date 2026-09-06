from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from trading_os.cli import main
from trading_os.screening_pool import QualityPoolError, QualityPoolStore, parse_quality_pool


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _call(tmp_path: Path, capsys: pytest.CaptureFixture[str], *args: str) -> dict:
    code = main(["--root", str(tmp_path), *args])
    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert captured.err == ""
    return json.loads(captured.out)


def _pool_payload() -> dict:
    return {
        "schema_version": 2,
        "as_of": "2026-08-31",
        "universe": {
            "as_of": "2026-08-31",
            "sources": [{"title": "独立证券清单", "url": "https://example.com/securities"}],
            "securities": {"CN:600519": "贵州茅台", "CN:600900": "长江电力"},
        },
        "review": {
            "baseline_as_of": "2026-07-31",
            "baseline_count": 2,
            "missing_baseline_symbols": [],
            "reviewed_symbols": ["CN:600519", "CN:600900"],
            "scope_note": "本轮复核两家企业的商业质量。",
            "omission_check": "补查长寿命资产。",
            "admission_check": "核对渠道与负债。",
        },
        "methodology": "prompts/screening/cn-a-value-quality.md",
        "philosophy": "商业质量与价格分开判断。",
        "companies": [
            {
                "symbol": "CN:600519",
                "name": "贵州茅台",
                "industry": "白酒Ⅱ",
                "tier": "core_moat",
                "group": "consumer_brand_network",
                "moat": "品牌、渠道和供给约束构成长期壁垒。",
                "owner_cash": "先款后货与较低维护投入支持普通股现金。",
                "risks": "渠道库存与终端需求可能削弱现金收益。",
                "tier_reason": "跨周期的品牌复购与收现支持核心资格。",
                "sources": [{"title": "茅台年报", "url": "https://example.com/maotai"}],
            },
            {
                "symbol": "CN:600900",
                "name": "长江电力",
                "industry": "电力",
                "tier": "quality_research",
                "group": "infrastructure_finance_resource",
                "moat": "梯级调度和稀缺水电资产。",
                "owner_cash": "经营现金扣除维修和债务支付后支持分配。",
                "risks": "来水、电价与项目债务。",
                "tier_reason": "需验证新项目对现金的占用。",
                "sources": [{"title": "长电年报", "url": "https://example.com/power"}],
            },
        ],
    }


def _prepare_methodology(tmp_path: Path) -> None:
    path = tmp_path / "prompts/screening/cn-a-value-quality.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# 筛选规范\n", encoding="utf-8")


def test_quality_pool_replace_validate_status_and_list(tmp_path: Path, capsys):
    _prepare_methodology(tmp_path)
    source = _write(tmp_path / "input.json", _pool_payload())

    replaced = _call(tmp_path, capsys, "quality-pool", "replace", "--input", str(source))
    validated = _call(tmp_path, capsys, "quality-pool", "validate")
    status = _call(tmp_path, capsys, "quality-pool", "status")
    core = _call(tmp_path, capsys, "quality-pool", "list", "--tier", "core_moat")

    assert replaced["pool_count"] == 2
    assert replaced["tier_counts"] == {"core_moat": 1, "quality_research": 1}
    assert validated == {"ok": True, "status": status}
    assert core["count"] == 1
    assert core["companies"][0]["symbol"] == "CN:600519"
    assert (tmp_path / replaced["pool_path"]).is_file()
    current = (tmp_path / replaced["current_path"]).read_text(encoding="utf-8")
    assert "本池只表达商业质量" in current
    assert "贵州茅台" in current and "长江电力" in current
    assert not (tmp_path / "coverage/cn-a/research_state.jsonl").exists()
    assert not (tmp_path / "coverage/cn-a/research_queue.jsonl").exists()
    assert not (tmp_path / "research/watchlist.jsonl").exists()


def test_quality_pool_rejects_research_and_market_coupling_fields(tmp_path: Path, capsys):
    _prepare_methodology(tmp_path)
    payload = _pool_payload()
    payload["companies"][0]["report_path"] = "research/companies/CN/600519/report.md"
    source = _write(tmp_path / "coupled.json", payload)

    code = main(["--root", str(tmp_path), "quality-pool", "replace", "--input", str(source)])
    error = json.loads(capsys.readouterr().err)

    assert code == 1
    assert "不得耦合" in error["error"]
    assert not (tmp_path / "screening/cn-a/value-quality/pool.json").exists()


def test_quality_pool_requires_unique_companies_and_normalizes_order(tmp_path: Path, capsys):
    _prepare_methodology(tmp_path)
    duplicate = _pool_payload()
    duplicate["companies"][1]["symbol"] = "CN:600519"
    source = _write(tmp_path / "duplicate.json", duplicate)

    code = main(["--root", str(tmp_path), "quality-pool", "replace", "--input", str(source)])
    assert code == 1
    assert "重复证券" in json.loads(capsys.readouterr().err)["error"]

    wrong_order = _pool_payload()
    wrong_order["companies"].reverse()
    source = _write(tmp_path / "wrong-order.json", wrong_order)
    code = main(["--root", str(tmp_path), "quality-pool", "replace", "--input", str(source)])
    assert code == 0
    capsys.readouterr()
    rows = json.loads(
        (tmp_path / "screening/cn-a/value-quality/pool.json").read_text(encoding="utf-8")
    )["companies"]
    assert rows[0]["tier"] == "core_moat"


def test_research_and_quality_pool_validation_are_independent(tmp_path: Path, capsys):
    _prepare_methodology(tmp_path)
    source = _write(tmp_path / "input.json", _pool_payload())
    _call(tmp_path, capsys, "quality-pool", "replace", "--input", str(source))
    current = tmp_path / "screening/cn-a/value-quality/current.md"
    current.write_text("被手工改坏\n", encoding="utf-8")

    research_validation = _call(tmp_path, capsys, "validate")
    assert research_validation["ok"] is True

    code = main(["--root", str(tmp_path), "quality-pool", "validate"])
    error = json.loads(capsys.readouterr().err)
    assert code == 1
    assert "确定性投影" in error["error"]


@pytest.mark.parametrize("field", ["moat", "owner_cash", "risks", "tier_reason", "sources"])
def test_missing_judgment_evidence_rejected(field):
    payload = _pool_payload()
    del payload["companies"][0][field]
    with pytest.raises(QualityPoolError):
        parse_quality_pool(payload)


@pytest.mark.parametrize(
    "content",
    [
        "现价100元",
        "低于80元买入",
        "PE 10倍",
        "IRR 20%",
        "需要折价",
        "report_path=x",
    ],
)
def test_market_and_research_content_rejected(content):
    payload = _pool_payload()
    payload["companies"][0]["risks"] = content
    with pytest.raises(QualityPoolError, match="耦合内容"):
        parse_quality_pool(payload)


def test_operating_price_and_cash_risks_are_allowed():
    payload = _pool_payload()
    payload["companies"][0]["risks"] = "品牌溢价、产品售价、贷款收益率与资本开支需要检验。"
    assert parse_quality_pool(payload).companies[0].risks.startswith("品牌溢价")


@pytest.mark.parametrize("patch", [{"symbol": "CN:999999"}, {"name": "错误名称"}])
def test_identity_mismatch_rejected(patch):
    payload = _pool_payload()
    payload["companies"][0].update(patch)
    with pytest.raises(QualityPoolError, match="独立证券清单"):
        parse_quality_pool(payload)


@pytest.mark.parametrize("version", [True, 2.0, 1, "2"])
def test_strict_schema_version(version):
    payload = _pool_payload()
    payload["schema_version"] = version
    with pytest.raises(QualityPoolError, match="schema_version"):
        parse_quality_pool(payload)


@pytest.mark.parametrize(
    "sources",
    [[], [{"title": "本地报告", "url": "file:///report.md"}], [{"title": "空链接", "url": ""}]],
)
def test_invalid_sources_rejected(sources):
    payload = _pool_payload()
    payload["companies"][0]["sources"] = sources
    with pytest.raises(QualityPoolError):
        parse_quality_pool(payload)


def test_empty_pool_and_missing_review_record():
    payload = _pool_payload()
    payload["companies"] = []
    assert parse_quality_pool(payload).status()["pool_count"] == 0
    payload = _pool_payload()
    payload["review"]["reviewed_symbols"] = []
    with pytest.raises(QualityPoolError, match="reviewed_symbols"):
        parse_quality_pool(payload)


def test_projection_failure_is_explicit_committed_success_and_recoverable(
    tmp_path, capsys, monkeypatch
):
    import trading_os.screening_pool as module

    _prepare_methodology(tmp_path)
    store = QualityPoolStore(tmp_path)
    payload = _pool_payload()
    store.replace(payload)
    payload["philosophy"] = "修订后的长期经营质量判断。"
    source = _write(tmp_path / "new.json", payload)
    original = module._atomic_write_text

    def fail_projection(path, text):
        if path == store.current_path:
            raise OSError("模拟磁盘写入错误")
        original(path, text)

    with monkeypatch.context() as scoped:
        scoped.setattr(module, "_atomic_write_text", fail_projection)
        result = _call(tmp_path, capsys, "quality-pool", "replace", "--input", str(source))
    assert result["committed"] is True
    assert result["projection_current"] is False
    assert "名单已保存" in result["warning"]
    assert store.read().philosophy == payload["philosophy"]
    status = _call(tmp_path, capsys, "quality-pool", "status")
    listed = _call(tmp_path, capsys, "quality-pool", "list")
    assert not status["projection_current"] and listed["count"] == 2
    with pytest.raises(QualityPoolError, match="rebuild"):
        store.validate()
    before = store.pool_path.read_bytes()
    _call(tmp_path, capsys, "quality-pool", "rebuild")
    assert store.pool_path.read_bytes() == before
    store.validate()


def test_failed_source_write_preserves_both_old_files(tmp_path, monkeypatch):
    import trading_os.screening_pool as module

    _prepare_methodology(tmp_path)
    store = QualityPoolStore(tmp_path)
    payload = _pool_payload()
    store.replace(payload)
    before = (store.pool_path.read_bytes(), store.current_path.read_bytes())
    payload["philosophy"] = "新原则。"

    def fail(*args):
        raise OSError("源文件写入失败")

    monkeypatch.setattr(module, "_atomic_write_text", fail)
    with pytest.raises(OSError):
        store.replace(payload)
    assert (store.pool_path.read_bytes(), store.current_path.read_bytes()) == before


def test_concurrent_process_writers_leave_matching_source_and_projection(tmp_path):
    _prepare_methodology(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    script = (
        "import json,sys;from pathlib import Path;"
        "from trading_os.screening_pool import QualityPoolStore;"
        "p=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'));"
        "s=QualityPoolStore(Path(sys.argv[1]));"
        "[s.replace(p) for _ in range(12)]"
    )
    processes = []
    for n in range(3):
        payload = _pool_payload()
        payload["philosophy"] = f"长期经营质量原则第{n}版。"
        source = _write(tmp_path / f"source-{n}.json", payload)
        processes.append(
            subprocess.Popen(
                [sys.executable, "-c", script, str(tmp_path), str(source)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        )
    for process in processes:
        _, error = process.communicate(timeout=30)
        assert process.returncode == 0, error
    store = QualityPoolStore(tmp_path)
    store.validate()
    assert not list(store.pool_path.parent.glob(".*.tmp"))


def test_unreadable_encoding_projection_is_recoverable(tmp_path):
    _prepare_methodology(tmp_path)
    store = QualityPoolStore(tmp_path)
    store.replace(_pool_payload())
    store.current_path.write_bytes(b"\xff\xfe\x80")
    assert not store.projection_current(store.read())
    with pytest.raises(QualityPoolError, match="rebuild"):
        store.validate()
    store.rebuild()
    store.validate()
    store.pool_path.write_bytes(b"\xff")
    with pytest.raises(QualityPoolError, match="无法读取"):
        store.read()

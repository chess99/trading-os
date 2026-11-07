"""Storage boundaries do not certify company financial assumptions."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = load_script("scripts/check-research-artifacts.py", "artifact_budget")
verifier = load_script("research/pilots/2026-Q3/verify-models.py", "publication_contract")


def save(root, name, body):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_delivery_budget_excludes_historical_review_documents(tmp_path):
    save(tmp_path, "docs/reviews/old.json", " " * (checker.FILE_BUDGET + 1))
    save(tmp_path, "research/companies/CN/000001/models/2026-Q3-input.json", '{"growth": 0.02}')
    assert checker.issues(tmp_path) == ([], 1)


@pytest.mark.parametrize(
    "name,body,reason",
    [
        ("2026-Q3-output.json.xz", "archive", "可读文本"),
        ("2026-Q3-snapshot.json", "{}", "过程轨迹"),
        ("2026-Q3.py", "PAYLOAD = '" + "A" * 9000 + "'", "内嵌数据"),
        ("2026-Q3-output.json", '{"encoding":"gzip-base64-json-v1"}', "压缩载荷"),
        ("2026-Q3-input.json", " " * (checker.FILE_BUDGET + 1), "单文件"),
    ],
    ids=["archive", "process-note", "embedded-payload", "transport-envelope", "file-budget"],
)
def test_archive_and_payload_evasions_are_rejected(tmp_path, name, body, reason):
    save(tmp_path, "research/companies/CN/000001/models/" + name, body)
    errors, _ = checker.issues(tmp_path)
    assert any(reason in error for error in errors)


def test_company_period_budget_cannot_be_evaded_by_text_parts(tmp_path):
    for name in ("assumptions", "sources-assumptions", "notes"):
        save(tmp_path, f"research/companies/CN/000001/models/2026-Q3-{name}.md", "a" * 800000)
    errors, _ = checker.issues(tmp_path)
    assert any("公司周期" in error for error in errors)


@pytest.mark.parametrize("prefix", ["2026-Q3", "author/2026-Q3"])
def test_nested_period_sources_share_one_budget(tmp_path, prefix):
    for folder in ("author", "independent", "shared"):
        save(
            tmp_path,
            f"research/companies/CN/000001/models/{prefix}/{folder}/assumptions.md",
            "a" * 800000,
        )
    errors, _ = checker.issues(tmp_path)
    assert any("2026-Q3" in error and "公司周期" in error for error in errors)
    assert not any("须归入" in error for error in errors)


def test_first_period_component_owns_nested_period_named_files(tmp_path):
    for period in ("2027-FY", "2028-FY", "2029-FY"):
        save(
            tmp_path,
            f"research/companies/CN/000001/models/2026-Q3/{period}-assumptions.md",
            "a" * 800000,
        )
    errors, _ = checker.issues(tmp_path)
    assert any("2026-Q3" in error and "公司周期" in error for error in errors)


def test_encoded_archive_cannot_evade_detection_by_short_literal_chunks(tmp_path):
    source = "PARTS = (" + repr("A" * 5000) + ", " + repr("B" * 5000) + ")\n"
    save(tmp_path, "research/companies/CN/000001/models/2026-Q3.py", source)
    errors, _ = checker.issues(tmp_path)
    assert any("分段编码" in error for error in errors)


def test_repeated_encoded_literal_is_checked_without_building_its_payload(tmp_path):
    save(tmp_path, "research/companies/CN/000001/models/2026-Q3.py", "PAYLOAD = 'A' * 20000\n")
    errors, _ = checker.issues(tmp_path)
    assert any("分段编码" in error for error in errors)


def test_wrapped_base64_lines_cannot_hide_inside_a_short_string_array(tmp_path):
    source = "PARTS = [" + ",".join(repr("A" * 80) for _ in range(130)) + "]\n"
    save(tmp_path, "research/companies/CN/000001/models/2026-Q3.py", source)
    errors, _ = checker.issues(tmp_path)
    assert any("分段编码" in error for error in errors)


def test_period_report_obeys_file_budget_without_scanning_legacy(tmp_path):
    save(tmp_path, "research/companies/CN/000001/reports/2026-Q3.md", "a" * checker.FILE_BUDGET)
    save(
        tmp_path,
        "research/companies/CN/000001/legacy/2020-01-01.md",
        "a" * (checker.FILE_BUDGET + 1),
    )
    save(
        tmp_path,
        "research/companies/CN/000001/reports/2020-01-01.md",
        "a" * (checker.FILE_BUDGET + 1),
    )
    assert checker.issues(tmp_path) == ([], 0)
    save(
        tmp_path, "research/companies/CN/000001/reports/2026-Q3.md", "a" * (checker.FILE_BUDGET + 1)
    )
    errors, _ = checker.issues(tmp_path)
    assert len(errors) == 1
    assert "reports/2026-Q3.md" in errors[0] and "单文件" in errors[0]


def publication(tmp_path, value=6):
    data = {
        "schema": "example",
        "symbol": "CN:000001",
        "report_period": "2026-Q3",
        "value_range": None if value is None else {"low": value, "high": value, "currency": "CNY"},
        "return_model": None,
        "valuation_note": "关键经营变量无法约束" if value is None else "测试计算",
        "return_model_note": "未来分配无法可靠构造",
    }
    report = "research/companies/CN/000001/reports/2026-Q3.md"
    row = {**data, "basis_report_path": report}
    save(tmp_path, "coverage/cn-a/research_state.jsonl", json.dumps(row) + "\n")
    save(tmp_path, report, "# 公司研究\n")
    save(tmp_path, "research/companies/CN/000001/models/2026-Q3-output.json", json.dumps(data))
    return data


def test_null_result_is_readable_without_claiming_numeric_verification(tmp_path):
    publication(tmp_path, None)
    result = verifier.verify(tmp_path, recompute=True)
    assert result["contract_checked"] == 1
    assert result["numeric_recomputed"] == 0
    assert result["numeric_unavailable"] == 1


def test_a_diagnostic_script_does_not_certify_an_unavailable_equity_model(tmp_path):
    publication(tmp_path, None)
    save(
        tmp_path,
        "research/companies/CN/000001/models/2026-Q3.py",
        "raise AssertionError('diagnostic scripts are run separately "
        "from adopted equity models')\n",
    )
    result = verifier.verify(tmp_path, recompute=True)
    assert result["numeric_recomputed"] == 0
    assert result["numeric_unavailable"] == 1


def test_recomputation_runs_actual_producer_and_rejects_stale_result(tmp_path):
    data = publication(tmp_path)
    source = """import json
low = sum([1, 2, 3])
data = {"symbol": "CN:000001", "report_period": "2026-Q3",
        "value_range": {"low": low, "high": low, "currency": "CNY"}, "return_model": None}
print(json.dumps(data))
"""
    save(tmp_path, "research/companies/CN/000001/models/2026-Q3.py", source)
    assert verifier.verify(tmp_path)["numeric_recomputed"] == 0
    assert verifier.verify(tmp_path, recompute=True)["numeric_recomputed"] == 1
    data["value_range"]["low"] = 7
    data["value_range"]["high"] = 7
    state = json.loads(
        (tmp_path / "coverage/cn-a/research_state.jsonl").read_text(encoding="utf-8")
    )
    state["value_range"] = data["value_range"]
    save(tmp_path, "coverage/cn-a/research_state.jsonl", json.dumps(state))
    save(tmp_path, "research/companies/CN/000001/models/2026-Q3-output.json", json.dumps(data))
    with pytest.raises(ValueError, match="实际复算"):
        verifier.verify(tmp_path, recompute=True)


def test_current_result_must_match_state_before_any_recomputation(tmp_path):
    publication(tmp_path)
    saved = tmp_path / "research/companies/CN/000001/models/2026-Q3-output.json"
    changed = json.loads(saved.read_text(encoding="utf-8"))
    changed["value_range"]["low"] = 5
    saved.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="value_range"):
        verifier.verify(tmp_path)

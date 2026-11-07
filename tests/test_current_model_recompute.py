"""Current plain adapters must work with only current source and model inputs."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("symbol", ["CN:000063", "CN:000333"])
def test_plain_model_recomputes_in_repository_shaped_isolated_source(symbol, tmp_path):
    # A later completed period must not invalidate this retained model's portability.
    period = "2026-Q3"
    company = Path("research/companies/CN") / symbol.split(":", 1)[1]
    original = ROOT / company / "models"
    destination = tmp_path / company / "models"
    destination.mkdir(parents=True)
    for source in original.rglob("*"):
        relative = source.relative_to(original)
        if (
            source.is_file()
            and "__pycache__" not in relative.parts
            and relative.parts[0].startswith(period)
        ):
            copied = destination / relative
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, copied)
    shutil.copyfile(ROOT / "research/model_io.py", tmp_path / "research/model_io.py")
    report = company / "reports" / f"{period}.md"
    (tmp_path / report).parent.mkdir(parents=True)
    shutil.copyfile(ROOT / report, tmp_path / report)
    published = json.loads((original / f"{period}-output.json").read_text(encoding="utf-8"))
    contract = {
        "symbol": symbol,
        "report_period": period,
        "basis_report_path": report.as_posix(),
        "value_range": published["value_range"],
        "return_model": published["return_model"],
    }
    state = tmp_path / "coverage/cn-a/research_state.jsonl"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps(contract) + "\n", encoding="utf-8")
    assert not (tmp_path / ".git").exists()
    path = ROOT / "research/pilots/2026-Q3/verify-models.py"
    spec = importlib.util.spec_from_file_location("current_publication_verifier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.verify(tmp_path, symbols=[symbol], recompute=True)
    assert result["contract_checked"] == result["numeric_recomputed"] == 1
    assert result["numeric_unavailable"] == 0

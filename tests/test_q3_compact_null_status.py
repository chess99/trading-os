"""Current metadata/evidence contract only. No financial computations."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
IDENTITIES = json.loads(Path(__file__).with_name("compact-null-current-identities.json").read_text())

@pytest.mark.parametrize("symbol", sorted(IDENTITIES))
def test_current_evidence_exact_identity(symbol):
    for name, expected in IDENTITIES[symbol].items():
        raw = (ROOT / name).read_bytes()
        assert len(raw) == expected["bytes"]
        assert hashlib.sha256(raw).hexdigest() == expected["sha256"]
        if name.endswith(".py"):
            ast.parse(raw)

@pytest.mark.parametrize("symbol", sorted(IDENTITIES))
@pytest.mark.parametrize("role", ["2026-Q3.py", "2026-Q3-independent-recompute.py"])
def test_current_null_status_isolated_metadata_only(symbol, role, tmp_path):
    source = ROOT / "research/companies/CN" / symbol / "models"
    for name in [role, "2026-Q3-output.json"]:
        shutil.copyfile(source / name, tmp_path / name)
    result = subprocess.run([sys.executable, "-B", str(tmp_path / role)], cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert result.returncode == 2, result.stderr
    expected = json.loads((source / "2026-Q3-output.json").read_text())
    actual = json.loads(result.stdout)
    assert actual == expected
    assert actual["value_range"] is None and actual["return_model"] is None
    assert actual["valuation_note"] and actual["return_model_note"]
    assert sorted(x.name for x in tmp_path.iterdir()) == sorted([role, "2026-Q3-output.json"])

@pytest.mark.parametrize("symbol", sorted(IDENTITIES))
@pytest.mark.parametrize("role", ["2026-Q3.py", "2026-Q3-independent-recompute.py"])
def test_corrupt_null_status_is_not_adopted(symbol, role, tmp_path):
    source = ROOT / "research/companies/CN" / symbol / "models"
    shutil.copyfile(source / role, tmp_path / role)
    data = json.loads((source / "2026-Q3-output.json").read_text())
    data["value_range"] = [1, 2]
    (tmp_path / "2026-Q3-output.json").write_text(json.dumps(data))
    result = subprocess.run([sys.executable, "-B", str(tmp_path / role)], cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert not result.stdout.strip()

@pytest.mark.parametrize("helper", ["huaming_null_contract_helpers", "kedali_null_contract_helpers", "xingyu_null_contract_helpers"])
def test_preserved_substantive_current_contract(helper, tmp_path):
    import importlib
    result = importlib.import_module(helper).assert_null_current(ROOT, tmp_path)
    assert result == {'metadata_expected_exit': 2, 'model_numeric_pass': False, 'historical_financial_executions': 0}

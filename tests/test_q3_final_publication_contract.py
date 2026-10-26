"""Accepted corrected models remain bound to their production state and reader files."""
import hashlib
import json
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = json.loads((ROOT / 'tests/q3-final-test-migration.json').read_text())['companies']

@pytest.mark.parametrize('entry', MIGRATIONS, ids=lambda entry: entry['code'])
def test_corrected_publication_matches_accepted_interface_and_reader(entry):
    code = entry['code']
    company = ROOT / 'research/companies/CN' / code
    report_path = company / 'reports/2026-Q3.md'
    report = report_path.read_bytes()
    assert hashlib.sha256(report).hexdigest() == entry['published_report_sha256']
    accepted = json.loads((ROOT / 'tests/q3_final_helpers' / code / 'expected-result.json').read_text())
    assert accepted['symbol'] == 'CN:' + code
    assert accepted['report_period'] == '2026-Q3'
    assert company.name == code and report_path.name == '2026-Q3.md'
    states = [json.loads(line) for line in (ROOT / 'coverage/cn-a/research_state.jsonl').read_text().splitlines()]
    state = next(row for row in states if row['symbol'] == 'CN:' + code)
    actual = {key: state['status'] if key == 'outcome' else state[key] for key in accepted}
    assert actual == accepted
    assert state['basis_report_path'] == str(report_path.relative_to(ROOT))
    for name in entry['required_model_artifacts']:
        assert (company / 'models' / name).is_file(), name
    for link in re.findall(r'\]\(([^)]+)\)', report.decode()):
        if not link.startswith(('http:', 'https:', '#', 'mailto:')):
            assert (report_path.parent / link.split('#')[0]).is_file(), link

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
    publication = entry.get('current_publication', entry)
    assert hashlib.sha256(report).hexdigest() == publication['published_report_sha256']
    historical_result = ROOT / 'tests/q3_final_helpers' / code / 'expected-result.json'
    accepted = json.loads(historical_result.read_text())
    if 'current_publication' in entry:
        assert hashlib.sha256(historical_result.read_bytes()).hexdigest() == publication['historical_expected_result_sha256']
        current_path = ROOT / publication['expected_result_file']
        assert current_path.parent == historical_result.parent
        accepted = json.loads(current_path.read_text())
    assert accepted['symbol'] == 'CN:' + code
    assert accepted['report_period'] == '2026-Q3'
    assert company.name == code and report_path.name == '2026-Q3.md'
    states = [json.loads(line) for line in (ROOT / 'coverage/cn-a/research_state.jsonl').read_text().splitlines()]
    state = next(row for row in states if row['symbol'] == 'CN:' + code)
    actual = {key: state['status'] if key == 'outcome' else state[key] for key in accepted}
    assert actual == accepted
    assert state['basis_report_path'] == str(report_path.relative_to(ROOT))
    for name in entry['required_model_artifacts'] + (publication['required_model_artifacts'] if publication is not entry else []):
        assert (company / 'models' / name).is_file(), name
    for link in re.findall(r'\]\(([^)]+)\)', report.decode()):
        if not link.startswith(('http:', 'https:', '#', 'mailto:')):
            assert (report_path.parent / link.split('#')[0]).is_file(), link

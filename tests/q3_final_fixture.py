"""Portable staging for accepted standalone tests; never duplicate production outputs.

The result is reconstructed from authoritative repository state. The candidate is
an independent accepted interface snapshot, with the current published report.
Both are compared by the original tests; divergence is an integration failure.
"""
import atexit
from functools import lru_cache
import json
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]

@lru_cache(None)
def staged_company(code):
    temporary_root = Path(tempfile.mkdtemp(prefix=f'q3-final-{code}-'))
    atexit.register(shutil.rmtree, temporary_root, ignore_errors=True)
    folder = temporary_root / 'models'
    folder.mkdir()
    company = ROOT / 'research/companies/CN' / code
    for source in (company / 'models').glob('2026-Q3*'):
        if source.is_file():
            shutil.copy2(source, folder / source.name)
    helpers = Path(__file__).parent / 'q3_final_helpers' / code
    for source in helpers.iterdir():
        if source.is_file():
            shutil.copy2(source, folder / source.name)
    report = (company / 'reports/2026-Q3.md').read_text()
    (folder / 'report.md').write_text(report)
    (folder / '2026-Q3.md').write_text(report)
    accepted = json.loads((helpers / 'expected-result.json').read_text())
    assert accepted['symbol'] == f'CN:{code}'
    assert accepted['report_period'] == '2026-Q3'
    state = next(json.loads(line) for line in (ROOT / 'coverage/cn-a/research_state.jsonl').read_text().splitlines()
                 if json.loads(line)['symbol'] == f'CN:{code}')
    result = {key: state['status'] if key == 'outcome' else state[key] for key in accepted}
    result['report_markdown'] = report
    accepted['report_markdown'] = report
    (folder / 'result.json').write_text(json.dumps(result, ensure_ascii=False))
    (folder / 'candidate.json').write_text(json.dumps({'result': accepted}, ensure_ascii=False))
    return folder

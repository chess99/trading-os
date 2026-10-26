"""Standalone persistent regression tests. Run: python -m pytest -v test_300627_persistent.py
Requires pytest; all other code is stdlib. No repo, original package or network required.
"""
import base64
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

from q3_final_fixture import staged_company
ROOT = staged_company("300627")
MODEL_SHA = 'c11a14fbb62770083fe2fccab93538a9380ab5c5cb8ea7b3429fa5f1d217d965'
PACK_SHA = '47dc2cc561aa8f30c7695664fe7bd6f48b5ffe77aab9e130ac0d74106337a8ed'
READER_SHA = 'd32168b7c043e25ee3c79865b4865607ea61ae12829e2642a71f5705ca6e2b9e'
FULL_SHA = '93b3b4e8992a084f20cbc5f1e34ba0b5a1224398542947d016ded179b4ef7f30'

def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

@pytest.fixture(scope='session')
def model():
    return module('huace_production', '2026-Q3.py')

@pytest.fixture(scope='session')
def literal():
    return module('huace_literal', 'independent_literal.py')

@pytest.fixture(scope='session')
def payload():
    wrapper = json.loads((ROOT / '2026-Q3-output.json').read_text(encoding='utf-8'))
    compressed = base64.b64decode(wrapper['payload_base64'], validate=True)
    raw = gzip.decompress(compressed)
    return wrapper, compressed, raw, json.loads(raw)

@pytest.fixture
def zero_case(model):
    p = copy.deepcopy(model.P)
    p.update(sales=[100.] * 5, margin=[0.] * 5, wc_ratio=0., fixed_ratio=0.,
      opening_wc=0., opening_fixed=0., tax=.25, cash_yield=0., debt_rate=0.,
      opening_cash=[100.,0.,0.], opening_debt=[0.,0.,0.], opening_legal=[0.,0.,0.],
      parent_statutory=0., parent_registered=100., weights=[1.,0.,0.],
      cash_weights=[1.,0.,0.], floor_ratio=0., new_shares=[0.] * 5,
      opening_shares=10., opening_equity=100., opening_intercompany=[0.,0.],
      annual_minority=0., payout=0., fund_call=0., locked_deposits=[0.,0.,0.],
      nonmodelled_assets=0., debt_limit=[0.,0.,0.])
    return p

def test_frozen_model_pack_reader_identity():
    for name, expected in [('2026-Q3.py',MODEL_SHA), ('2026-Q3-output.json',PACK_SHA), ('report.md',READER_SHA)]:
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected

def test_wrapper_full_canonical_identity(payload):
    w, compressed, raw, full = payload
    assert w['format'] == 'gzip-base64-json-v1'
    assert compressed[4:8] == bytes(4)
    assert hashlib.sha256(compressed).hexdigest() == w['gzip_sha256']
    assert hashlib.sha256(raw).hexdigest() == w['payload_sha256'] == FULL_SHA
    assert len(raw) == w['payload_bytes'] == 25690033
    assert raw == (json.dumps(full, ensure_ascii=False, sort_keys=True, separators=(',',':'))+'\n').encode()
    assert len(full['cases']) == 18
    assert (ROOT/'2026-Q3-output.json').stat().st_size == 7685522 < 16*1024*1024

def test_reduce_capital_really_pays_fee_preserves_protected_debt(model):
    assert model.reduce_capital(200.,50.,10.,100.,10.,40.) == (150.,60.,6.)

def test_reduce_capital_failure_keeps_creditors_fees_shares(model):
    with pytest.raises(model.SettlementError) as e:
        model.reduce_capital(20.,30.,10.,100.,10.,5.)
    assert e.value.state == dict(cash=20., debt=30., unpaid_fees=10., registered=100., shares=10., capital_return=0.)

def test_recovery_fees_exceed_gross_is_negative_cash_no_tax_refund(model):
    assert model.capital_recovery(100.,5.,10.,.25,.6) == dict(principal=0., accounting_gain=-63., tax=0., net_cash=-3.)

def test_simulate_fee_hits_cash_legal_equity_and_original_holder(model, zero_case):
    zero_case.update(capital_return_year=1, capital_return_amount=40., capital_return_cost=10.)
    row = model.simulate(zero_case,1)[0]
    for field, expected in dict(net_profit=-10., parent_legal=-10., equity=50., shares=6., holder_units=.6, dps=4., bps=5.).items():
        assert row[field] == pytest.approx(expected)
    assert row['cash'] == [50.,0.,0.]

@pytest.mark.parametrize('failure', ['recovery_fee', 'capital_creditor', 'exit_fee', 'exit_debt_and_fee'])
def test_simulate_failed_transactions_preserve_unpaid_obligations_and_shares(model, zero_case, failure):
    changes = {
      'recovery_fee': dict(opening_cash=[0.,0.,0.], nonmodelled_assets=100., investment_recovery_year=1, investment_recovery_ratio=.05, investment_exit_cost=2.),
      'capital_creditor': dict(opening_debt=[80.,0.,0.], capital_return_year=1, capital_return_amount=40., capital_return_cost=10.),
      'exit_fee': dict(exit_year=1, exit_cost=200.),
      'exit_debt_and_fee': dict(opening_debt=[80.,0.,0.], opening_equity=20., exit_year=1, exit_cost=200.)}[failure]
    zero_case.update(changes)
    before = copy.deepcopy(zero_case)
    with pytest.raises(model.SettlementError) as e:
        model.simulate(zero_case,1)
    state = e.value.state
    assert zero_case == before  # the input is not mutated to conceal failed payment
    assert state['shares'] == 10. and state['registered'] == 100.
    assert state['capital_return'] == 0.
    if failure == 'recovery_fee':
        assert state['unpaid_fees'] == 5. and state['investment'] == 100.
        assert state['cash'] == [0.,0.,0.] and state['debt'] == [0.,0.,0.]
    elif failure == 'capital_creditor':
        assert state['debt'] == pytest.approx([80.-80./3,0.,0.])
        assert state['paid_fees'] == 10. and state['parent_legal'] == -10.
        assert state['cash'] == pytest.approx(100.-10.-80./3)
        assert state['equity_before_distribution'] == 90.
    elif failure == 'exit_debt_and_fee':
        assert state['debt'] == pytest.approx([80.-80./3,0.,0.])
        assert state['cash'] == pytest.approx([100.-80./3,0.,0.])
        assert state['unpaid_fees'] == pytest.approx(180.) and state['exit_distribution'] == 0.
    else:
        assert state['unpaid_fees'] == 100. and state['exit_distribution'] == 0.
        assert state['cash'] == [100.,0.,0.] and state['debt'] == [0.,0.,0.]

def test_all_formal_manual_and_boundary_cases_reexecute(model, payload):
    _,_,_,full = payload
    assert model.corrected_tests() == full['manual_tests']
    assert model.boundary_tests() == full['boundary_tests']
    assert len(full['boundary_tests']['checks']) == 11
    assert all(full['boundary_tests']['checks'].values())

CASE_NAMES = list(module('literal_names','independent_literal.py').VAR)
@pytest.mark.parametrize('name', CASE_NAMES)
def test_independent_literal_all_18_cases_350_rows_and_450_tail(literal, payload, name):
    _,_,_,full = payload
    assert len(CASE_NAMES) == 18 and set(CASE_NAMES) == set(full['cases'])
    rows = literal.rebuild(literal.VAR[name],350)
    expected = full['cases'][name]
    assert len(rows) == len(expected['rows']) == 350
    for row, want in zip(rows, expected['rows']):
        for key, value in row.items():
            pairs = zip(value,want[key]) if isinstance(value,list) else [(value,want[key])]
            for actual, target in pairs:
                assert abs(actual-target) < max(1e-6,abs(target)*1e-11), (name,row['year'],key)
    for rate in [.095,.1,.105]:
        pv = sum(x['dps']/(1+rate)**x['year'] for x in rows)
        tv = sum(x['dps']/(1+rate)**(x['year']-5) for x in rows[5:])
        assert pv == pytest.approx(expected['valuations'][str(rate)]['value'],abs=1e-8)
        assert tv == pytest.approx(expected['valuations'][str(rate)]['tv5'],abs=1e-8)
    tail = literal.rebuild(literal.VAR[name],450)
    assert sum(x['dps']/1.095**x['year'] for x in tail) == pytest.approx(full['all_case_tail_checks'][name]['pv_450'],abs=1e-8)

def test_fresh_single_file_regeneration_and_expand_exact_full_bytes(tmp_path, payload):
    _,_,raw,_ = payload
    model = tmp_path/'2026-Q3.py'
    shutil.copy(ROOT/'2026-Q3.py',model)
    assert list(tmp_path.iterdir()) == [model]
    subprocess.run([sys.executable,str(model)],check=True,capture_output=True)
    assert (tmp_path/'2026-Q3-output.json').read_bytes() == (ROOT/'2026-Q3-output.json').read_bytes()
    subprocess.run([sys.executable,str(model),'--expand'],check=True,capture_output=True)
    assert (tmp_path/'2026-Q3-output.full.json').read_bytes() == raw
    target = tmp_path/'explicit-target.json'
    subprocess.run([sys.executable,str(model),'--expand',str(target)],check=True,capture_output=True)
    assert target.read_bytes() == raw
    result = subprocess.run([sys.executable,str(model),'--expand',str(tmp_path/'2026-Q3-output.json')],capture_output=True)
    assert result.returncode != 0
    assert (tmp_path/'2026-Q3-output.json').read_bytes() == (ROOT/'2026-Q3-output.json').read_bytes()

def test_reader_publication_model_identity_and_real_expand_command(tmp_path, payload):
    _,_,raw,_ = payload
    report = (ROOT/'report.md').read_text()
    candidate = json.loads((ROOT/'candidate.json').read_text())
    candidate = candidate.get('result',candidate)
    assert candidate['report_markdown'] == report
    assert json.loads((ROOT/'result.json').read_text()) == candidate
    reports = tmp_path/'research/companies/CN/300627/reports';reports.mkdir(parents=True)
    models = reports.parent/'models';models.mkdir()
    (reports/'2026-Q3.md').write_text(report)
    for name in ['2026-Q3.py','2026-Q3-output.json']:
        shutil.copy(ROOT/name,models/name)
        assert (models/name).read_bytes() == (ROOT/name).read_bytes()
    links = [x for x in re.findall(r'\]\(([^)]+)\)', report) if not x.startswith(('http','https','#'))]
    assert set(links) == {'../models/2026-Q3.py','../models/2026-Q3-output.json'}
    assert all((reports/link).is_file() for link in links)
    assert '`--expand [target]`' in report
    target = tmp_path/'reader-expanded.json'
    subprocess.run([sys.executable,'../models/2026-Q3.py','--expand',str(target)],cwd=reports,check=True,capture_output=True)
    assert target.read_bytes() == raw

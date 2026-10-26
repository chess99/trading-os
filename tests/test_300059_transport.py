"""Portable persistent regression tests. Run: python -m pytest -q test_300059_transport.py

Place beside the packed artifacts, or set CN300059_ARTIFACT_DIR to their directory.
No repository imports, network, frozen source directory, or mutable shared state.
All generated files are written solely beneath pytest tmp_path.
"""
import base64
from copy import deepcopy
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys

import pytest

from q3_final_fixture import staged_company
ARTIFACTS = staged_company("300059")
CANONICAL_SHA256 = 'a5b48a7d5004d0caa7d69a1396902e7c233a7730a490145d4735aee409928c7c'
CANONICAL_BYTES = 19456153
CASES = ['base','cyclical_2027_2029','structural_2027_on','optimistic_2027_on',
         'capital_10pct_2027','funding_plus100bp_2027_on','upstream_delayed_two_years',
         'maturity_release_delayed_to2037','no_tax_expiry_after2030',
         'nonsec_capacity_50pct','nonsec_capacity_zero_until_exit',
         'principal_recovery_delayed_10years','principal_recovery_half_then_balance',
         'parent_negative_2027','liquidity_failure']

@pytest.fixture(scope='module')
def packed():
    envelope=json.loads((ARTIFACTS/'2026-Q3-output.json').read_text(encoding='utf-8'))
    compressed=base64.b64decode(envelope['payload_base64'],validate=True)
    raw=gzip.decompress(compressed)
    return envelope,compressed,raw,json.loads(raw)

@pytest.fixture
def model():
    return runpy.run_path(str(ARTIFACTS/'2026-Q3.py'))

def test_full_canonical_payload_identity(packed):
    e,z,raw,full=packed
    assert e['schema']=='cn-equity-model-output-gzip-base64-v1'
    assert len(raw)==e['full_output_bytes']==CANONICAL_BYTES
    assert hashlib.sha256(raw).hexdigest()==e['full_output_sha256']==CANONICAL_SHA256
    assert len(z)==e['compressed_bytes']
    assert hashlib.sha256(z).hexdigest()==e['compressed_sha256']
    assert int.from_bytes(z[4:8],'little')==e['gzip_mtime']==0
    assert set(full['scenarios'])==set(CASES)
    assert (ARTIFACTS/'2026-Q3-output.json').stat().st_size<16*1024*1024

@pytest.mark.parametrize('shock',[
    {'asset_haircut':10.}, {'extra_external_debt':10000.},
    {'securities_exit_cost':10000.}, {'other_exit_cost':10000.}],
    ids=['zero_asset_recovery','unfunded_external_debt','unpayable_securities_fees','unpayable_other_fees'])
def test_failed_exit_is_unexecuted_and_preserves_creditors(model,monkeypatch,shock):
    p=model['path'](years=20);before=deepcopy(p);last=deepcopy(p['rows'][-1])
    def forbidden(*args,**kwargs):
        raise AssertionError('Rejected exit must not dispose investment or cancel shares')
    ns=model['close_path'].__globals__
    monkeypatch.setitem(ns,'investment_exit',forbidden)
    monkeypatch.setitem(ns,'capital_return',forbidden)
    failed=model['close_path'](p,20,**shock)
    assert p==before and failed['rows']==p['rows']
    assert not failed['feasible'] and not failed['finite_exit']
    assert model['valued'](failed,.105) is None
    assert failed['exit_attempt']['executed'] is False
    assert failed['exit_attempt']['shares_cancelled']==0
    assert failed['exit_attempt']['post_exit_shares']==15.824105875
    assert 'exit' not in failed['rows'][-1]
    assert 'parent_investment' not in failed['exit_attempt']
    for key,value in last.items():assert failed['terminal_state'][key]==value
    assert failed['terminal_state']['parent_cash']==last['parent_cash']
    assert failed['terminal_state']['parent_receivable']==last['parent_receivable']
    assert failed['terminal_state']['shares']==15.824105875
    assert failed['terminal_state']['securities_total_debt']==last['sec_external_and_internal_funding']+shock.get('extra_external_debt',0)
    assert any(not failed['exit_attempt'][side]['settlement_complete'] for side in ['securities','other_economic_net_assets'])

@pytest.mark.parametrize('args,expected',[
    ((0,30,20,1),(0,1,0,20,False)),
    ((15,15,20,1),(1,0,14,6,False)),
    ((3,3,20,5),(3,2,0,20,False)),
    ((30,30,20,2),(2,0,20,0,True))])
def test_literal_creditor_waterfall(model,args,expected):
    q=model['liquidation'](*args)
    assert tuple(q[k] for k in ['exit_cost_paid','exit_cost_unpaid','external_debt_paid','external_debt_unpaid','settlement_complete'])==expected

def test_ownership_does_not_scale_senior_debt(model):
    q=model['liquidation'](30,30,20,2,ownership=.4)
    assert q['ordinary_proceeds']==3.2 and q['external_debt_paid']==20

def test_positive_exit_cost_once_and_shares_cancelled(model):
    p=model['path'](years=20);last=p['rows'][-1]
    baseline=model['close_path'](p,20)['rows'][-1]['exit']
    higher=model['close_path'](p,20,securities_exit_cost=2)['rows'][-1]['exit']
    sec_net=last['sec_equity']-.02*last['sec_operating_gross_assets']-1
    dividend=min(max(0,last['sec_up'])+last['sec_stat'],sec_net)
    tax=max(0,sec_net-dividend-40.51227686503)*.25
    expected=sec_net-tax+last['other_equity']-1-.15*last['nonsec_economic_equity']
    assert baseline['shareholder_cash']==pytest.approx(expected,abs=1e-10)
    assert baseline['post_exit_shares']==0
    assert baseline['securities']['ordinary_proceeds']-higher['securities']['ordinary_proceeds']==1
    assert baseline['shareholder_cash']-higher['shareholder_cash']==pytest.approx(1+higher['parent_investment']['tax']-baseline['parent_investment']['tax'],abs=1e-10)

def test_required_capital_retained_and_earns_without_forced_shutdown(model):
    p=model['path'](years=260)
    assert p['feasible'] and not p.get('finite_exit')
    for r in p['rows']:
        assert 'exit' not in r
        assert r['sec_equity']>=r['sec_required']-1e-8
        assert r['sec_equity']>=r['sec_risk']+r['sec_stat']+12.7-1e-8
        assert r['sec_operating_profit']>0 and r['core_net_capital']>0
    last=p['rows'][-1]
    assert last['sec_equity']==pytest.approx(last['sec_required'],abs=1e-7)
    assert last['other_equity']==pytest.approx(last['other_required']+1,abs=1e-7)
    assert last['sec_up']>0 and last['sec_risk']>0
    no_yield=model['path']({'cash_yield':0},years=260)
    assert no_yield['feasible']
    assert no_yield['rows'][-1]['sec_operating_profit']==last['sec_operating_profit']
    assert all(r['sec_surplus_income']==0 for r in no_yield['rows'])
    # DCF contains shareholder payments plus cash-chain tail, no second NAV addback.
    r=.105;ds=[z['distribution_per_share'] for z in p['rows']]
    expected=sum(d/(1+r)**i for i,d in enumerate(ds,1))+ds[-1]*1.03/(r-.03)/(1+r)**260
    assert model['valued'](p,r)['current_value']==pytest.approx(expected,abs=1e-10)

def test_required_capital_shortfall_never_invents_donor_financing(model):
    p=model['path']({'capital_multiplier':2,'zero_dividend':True})
    assert not p['feasible']
    assert p['rows'][0]['sec_upstream_dividend']==0
    assert p['rows'][0]['ordinary_dividend']==0
    assert p['rows'][0]['capital_funding_gap']==pytest.approx(70.296992)
    assert model['valued'](p,.105) is None

def test_old_loan_collection_no_profit_or_double_principal(model):
    a=model['path'](years=6)['rows'][-1]
    b=model['path']({'principal_year':10000},years=6)['rows'][-1]
    for key in ['sec_equity','sec_up','group_profit','sec_operating_profit','sec_external_and_internal_funding']:
        assert a[key]==pytest.approx(b[key],abs=1e-10)
    assert a['receivable_collection']==1.5
    assert a['sec_external_funding']-b['sec_external_funding']==pytest.approx(1.5,abs=1e-10)
    assert a['parent_legal_profit']==pytest.approx(a['parent_direct_profit']+a['nonsec_economic_payment']+a['sec_upstream_dividend'],abs=1e-10)

@pytest.fixture(scope='module')
def literal_result(tmp_path_factory):
    t=tmp_path_factory.mktemp('literal_envelope_only')
    for name in ['independent-literal.py','2026-Q3-output.json']:
        shutil.copyfile(ARTIFACTS/name,t/name)
    # No production Python or gzip file is provided to literal reconstruction.
    subprocess.run([sys.executable,str(t/'independent-literal.py')],cwd=t,check=True,capture_output=True,text=True)
    return json.loads((t/'independent-output.json').read_text())

@pytest.mark.parametrize('name',CASES)
def test_all_15_paths_independent_literal(name,literal_result,packed):
    q=literal_result['checks'][name]
    assert q['annual_max_absolute_difference_bn']<1e-7
    assert q['rows']==len(packed[3]['scenarios'][name]['path']['rows'])
    assert q==json.loads((ARTIFACTS/'independent-output.json').read_text())['checks'][name]
    if packed[3]['scenarios'][name]['path']['feasible']:
        for bucket in ['securities','other']:
            assert literal_result['all_future_vintage_rebuild'][name+'/'+bucket]['max_absolute_difference_bn']<1e-6

def test_literal_tail_and_auxiliary_identity(literal_result):
    expected=json.loads((ARTIFACTS/'independent-output.json').read_text())
    assert literal_result==expected
    assert set(map(int,literal_result['convergence']))=={120,160,200,260}
    assert literal_result['auxiliary']['low']==pytest.approx(6.651952256407572)
    assert literal_result['auxiliary']['high']==pytest.approx(7.509394999316933)

def test_fresh_isolated_single_file_regeneration_and_expand(tmp_path,packed):
    t=tmp_path/'single';t.mkdir()
    shutil.copyfile(ARTIFACTS/'2026-Q3.py',t/'2026-Q3.py')
    unrelated=tmp_path/'unrelated';unrelated.mkdir()
    subprocess.run([sys.executable,str(t/'2026-Q3.py')],cwd=unrelated,check=True,capture_output=True,text=True)
    for name in ['2026-Q3-output.json','summary.json']:
        assert (t/name).read_bytes()==(ARTIFACTS/name).read_bytes()
    assert (t/'2026-Q3-output.json.gz').read_bytes()==packed[1]
    (t/'2026-Q3-output.json.gz').unlink()
    subprocess.run([sys.executable,str(t/'2026-Q3.py'),'--expand'],cwd=unrelated,check=True,capture_output=True,text=True)
    assert (t/'2026-Q3-output.expanded.json').read_bytes()==packed[2]
    target=tmp_path/'chosen-target.json'
    subprocess.run([sys.executable,str(t/'2026-Q3.py'),'--expand',str(target)],cwd=unrelated,check=True,capture_output=True,text=True)
    assert target.read_bytes()==packed[2]

def test_reader_identity_and_actual_relative_links(tmp_path,packed):
    md=(ARTIFACTS/'report.md').read_text();r=json.loads((ARTIFACTS/'result.json').read_text());c=json.loads((ARTIFACTS/'candidate.json').read_text())
    assert c['result']==r and r['report_markdown']==md
    assert r['symbol']=='CN:300059' and r['report_period']=='2026-Q3'
    assert r['information_cutoff']==r['return_model']['model_as_of']=='2026-10-26T11:15:00+00:00'
    assert r['return_model']['base_case_distributions_per_share']==packed[3]['core_distributions']
    for side in ['low','high']:
        assert r['return_model']['base_case_terminal_equity_value_range_per_share']['year_5'][side]==packed[3]['core_endpoints'][side]['year5_value']
    root=tmp_path/'research/companies/CN/300059';(root/'reports').mkdir(parents=True);(root/'models').mkdir()
    shutil.copyfile(ARTIFACTS/'report.md',root/'reports/2026-Q3.md')
    for name in ['2026-Q3.py','2026-Q3-output.json']:shutil.copyfile(ARTIFACTS/name,root/'models'/name)
    links=re.findall(r'\]\((\.\./models/[^)]+)\)',md)
    assert set(links)=={'../models/2026-Q3.py','../models/2026-Q3-output.json'}
    for link in links:assert (root/'reports'/link).resolve().is_file()

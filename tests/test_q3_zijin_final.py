from pathlib import Path
import json,gzip,base64,hashlib,importlib.util,subprocess,sys,shutil
from q3_final_fixture import staged_company
P = staged_company("601899")
s=importlib.util.spec_from_file_location('zijin_final',P/'2026-Q3.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def full():
 w=json.loads((P/'2026-Q3-output.json').read_text());b=gzip.decompress(base64.b64decode(w['payload_base64']));assert hashlib.sha256(b).hexdigest()==w['expanded_sha256'];return json.loads(b)
def test_actual_36_paths_and_operating_capital():
 d=full();assert len(d['cases'])==36
 for n,a in d['cases'].items():
  assert a==m.run(m.CASES[n])
  ledgers={x[0]:0. for x in m.MINES}
  for op in a['operations']:
   for z in op['details']:
    ledgers[z['mine']]+=z['nwc_addition']-z['nwc_tax_basis_released']
    assert abs(z['nwc_recovery']+z['nwc_loss']-z['nwc_tax_basis_released'])<1e-8
    assert abs(ledgers[z['mine']]-z['nwc_closing_balance'])<1e-8
  assert all(abs(v)<1e-8 for v in ledgers.values())
  pools=a['opening_working_capital'];st=[z for op in a['operations'] for z in op['opening_nwc_settlements']]
  assert len(st)==len(pools)
  assert abs(sum(z['full_liabilities_paid'] for z in st)-sum(x['amounts'][3] for x in pools))<1e-8
  assert all(abs(z['net_cash']-z['gross_realization']+z['full_liabilities_paid'])<1e-8 for z in st)
def test_actual_stream_and_exit_shortfall():
 a=m.run(m.BASE);stream=[op['details'][18] for op in a['operations']]
 assert abs(sum(z['chifeng_stream_stage1_delivery_tonnes'] for z in stream)-(240000-213807.41)*.0000311034768)<1e-9
 for i,z in enumerate(stream):
  expected=(z['chifeng_stream_stage1_delivery_tonnes']*.8+z['chifeng_stream_stage2_delivery_tonnes']*.7)*850*1.015**i/1000*(.2585*.62*.9)
  assert abs(z['chifeng_stream_cash_loss']-expected)<1e-9
 for args,expected in [((0,0,0,10,0),10),((0,10,0,9,0),1.4),((2,0,3,5,0),6)]:
  r=m.liquidation(*args);assert not r['feasible'];assert r['equity']==0;assert abs(r['total_obligation_shortfall']-expected)<1e-8
 r=m.legal_profit(-10,0,100,5);assert r[0]==-5 and r[2]==0
 r=m.legal_profit(0,49,100,100);assert r[2]==1
 rows=a['financing'];rows[-1].update(parent_cash=0,sub_cash=0,parent_debt=0,sub_debt=0,assets=0,outstanding_declared_dividends=0)
 try:m.values(a['operations'],rows,m.BASE)
 except AssertionError as e:assert 'Exit obligations unpaid' in str(e)
 else:raise AssertionError('unpaid exit accepted')
def test_independent_literal_four(tmp_path):
 for n in ['2026-Q3-output.json','independent-literal.py']:shutil.copy2(P/n,tmp_path/n)
 subprocess.run([sys.executable,'-B',str(tmp_path/'independent-literal.py')],cwd=tmp_path,check=True,capture_output=True)
 d=json.loads((tmp_path/'independent-literal-output.json').read_text());assert len(d)==4;assert max(x['max_absolute_error'] for x in d.values())<1e-8
def test_single_file_and_reader(tmp_path):
 shutil.copy2(P/'2026-Q3.py',tmp_path/'2026-Q3.py');subprocess.run([sys.executable,'-B','2026-Q3.py'],cwd=tmp_path,check=True,capture_output=True)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(P/'2026-Q3-output.json').read_bytes()
 subprocess.run([sys.executable,'-B','2026-Q3.py','--expand','expanded.json'],cwd=tmp_path,check=True,capture_output=True)
 assert hashlib.sha256((tmp_path/'expanded.json').read_bytes()).hexdigest()=='2253dff6d95457037d4f30145d834805b8fbaef85ebffe083d3a32b8eedcf62c'
 r=json.loads((P/'result.json').read_text());assert r==json.loads((P/'candidate.json').read_text())['result'];assert r['report_markdown']==(P/'report.md').read_text()
 assert '../models/2026-Q3.py' in r['report_markdown'] and '../models/2026-Q3-output.json' in r['report_markdown']

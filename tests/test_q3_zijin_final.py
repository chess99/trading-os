from pathlib import Path
import json,lzma,hashlib,importlib.util,subprocess,sys,shutil
from q3_final_fixture import staged_company
P = staged_company("601899")
s=importlib.util.spec_from_file_location('zijin_final',P/'2026-Q3.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def full():
    """Closed single-XZ transport; validate every compressed/expanded byte."""
    import hashlib, lzma, tempfile
    descriptor=json.loads((P/'2026-Q3-output.json').read_text())
    assert descriptor['schema']=='trading_os_lossless_json_xz_v1'
    assert descriptor['artifact_kind']=='transport_manifest_not_model_result'
    assert descriptor['compression']=='xz' and descriptor['file']=='2026-Q3-output.json.xz'
    assert 0<descriptor['compressed_bytes']<=100*1024**2
    assert 0<descriptor['expanded_bytes']<=512*1024**2
    decoder=lzma.LZMADecompressor(format=lzma.FORMAT_XZ,memlimit=256*1024**2)
    encoded_hash=hashlib.sha256();decoded_hash=hashlib.sha256();encoded_size=decoded_size=0
    with (P/descriptor['file']).open('rb')as source,tempfile.TemporaryFile()as decoded:
        while chunk:=source.read(65536):
            assert not decoder.eof
            encoded_size+=len(chunk);encoded_hash.update(chunk)
            assert encoded_size<=descriptor['compressed_bytes']
            data=chunk
            while True:
                part=decoder.decompress(data,max_length=1048576);data=b''
                decoded_size+=len(part);assert decoded_size<=descriptor['expanded_bytes']
                decoded_hash.update(part);decoded.write(part)
                if decoder.needs_input or decoder.eof:break
            assert not decoder.unused_data
        assert decoder.eof and not decoder.unused_data
        assert encoded_size==descriptor['compressed_bytes'] and encoded_hash.hexdigest()==descriptor['compressed_sha256']
        assert decoded_size==descriptor['expanded_bytes'] and decoded_hash.hexdigest()==descriptor['expanded_sha256']
        decoded.seek(0);return json.load(decoded)
def test_actual_49_paths_and_operating_capital():
 d=full();assert len(d['cases'])==49
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
def test_independent_literal_eighteen(tmp_path):
 for n in ['2026-Q3-output.json.xz','independent-literal.py']:shutil.copy2(P/n,tmp_path/n)
 with (tmp_path/'independent-literal-output.json').open('wb')as out:
  subprocess.run([sys.executable,'-B',str(tmp_path/'independent-literal.py'),'--compare',str(tmp_path/'2026-Q3-output.json.xz')],cwd=tmp_path,check=True,stdout=out)
 d=json.loads((tmp_path/'independent-literal-output.json').read_text())['checks'];assert len(d)==18;assert max(x['max_absolute_error'] for x in d.values())<1e-8
def test_single_file_and_reader(tmp_path):
 shutil.copy2(P/'2026-Q3.py',tmp_path/'2026-Q3.py')
 with (tmp_path/'expanded.json').open('wb')as out:
  subprocess.run([sys.executable,'-B','2026-Q3.py'],cwd=tmp_path,check=True,stdout=out)
 assert hashlib.sha256((tmp_path/'expanded.json').read_bytes()).hexdigest()=='b1390671ff362fc9675ad6d69ab932b592de06a17de2dc2d2d5f7b4c444905a6'
 with lzma.open(P/'2026-Q3-output.json.xz','rb')as frozen,(tmp_path/'expanded.json').open('rb')as fresh:
  while chunk:=fresh.read(1048576):assert frozen.read(len(chunk))==chunk
  assert frozen.read(1)==b''
 assert json.loads((tmp_path/'expanded.json').read_text())==full()
 r=json.loads((P/'result.json').read_text());assert r==json.loads((P/'candidate.json').read_text())['result'];assert r['report_markdown']==(P/'report.md').read_text()
 assert '../models/2026-Q3.py' in r['report_markdown'] and '../models/2026-Q3-output.json' in r['report_markdown']

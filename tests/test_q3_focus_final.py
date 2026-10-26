"""Portable pytest/unittest acceptance tests using actual production functions."""
import unittest,json,importlib.util,copy,subprocess,sys,tempfile,shutil,re,hashlib
from pathlib import Path
from q3_final_fixture import staged_company
D=staged_company("002315")
sp=importlib.util.spec_from_file_location('m',D/'2026-Q3.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
class OpeningTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.o=m.expand_traces(json.loads((D/'2026-Q3-output.json').read_text()))
 def test_01_registered_not_paid_threshold(self):
  self.assertEqual(m.legal_profit(0,10,5,20)[2],1)
  self.assertEqual(m.legal_profit(-6,10,0,20)[2],.4)
  self.assertEqual(m.legal_profit(0,10,10,20)[2],0)
  self.assertEqual(m.legal_profit(0,10,10,20,True)[2],1)
 def test_02_actual_formal_hand_examples(self):self.assertGreater(len(m.tests()),5)
 def test_03_declaration_receipt_and_capital(self):
  s=dict(cash=5.,debt=0.,re=-20.,reserve=0.,capital=20.,wc=0.)
  state,row=m.cash_year(s,0,0,0,0,0,0,0,receipt=7,desired=100)
  self.assertEqual((state['cash'],row['profit'],row['distribution']),(12,0,0))
  state,row=m.cash_year(dict(s,re=0),0,0,0,0,0,0,0,mature=7,desired=100)
  self.assertEqual((state['cash'],row['profit'],row['distribution']),(12,0,0))
 def test_04_zero_dividend_not_fake_financing(self):
  with self.assertRaises(ValueError):m.cash_year(dict(cash=0.,debt=0.,re=0.,reserve=0.,capital=20.,wc=0.),100,-1,0,0,0,0,10,borrow_limit=0,desired=0)
 def test_05_bridge_is_once_not_payroll_again(self):
  rr=m.run();prior=m.run(opening_noa=.045*2134.324686)
  self.assertAlmostEqual(rr[0]['P']['delta_wc']-prior[0]['P']['delta_wc'],68.40327434,9)
  self.assertEqual(rr[0]['P']['tax'],prior[0]['P']['tax'])
  self.assertEqual(rr[0]['dps'],prior[0]['dps'])
  self.assertTrue(all(a['dps']<b['dps']for a,b in zip(rr[1:5],prior[1:5])))
 def test_06_principal_recovery_despite_profit_hurdle(self):
  rr=m.run(sub_upstream=False,sub_loss=-650)
  self.assertGreater(rr[9]['S']['economic_realization_parent_net'],0)
  self.assertTrue(all(z['S']['distribution']==0 for z in rr))
  self.assertEqual(rr[9]['S']['cash'],20)
  self.assertGreater(rr[10]['P']['receipt'],rr[9]['P']['receipt'])
 def test_07_actual_cost_tax_ownership_sensitivities(self):
  s=self.o['sensitivity']
  self.assertLess(s['recovery_friction25']['value'],m.pv(m.run(),.1,.025)['value'])
  self.assertLess(s['recovery_zero_tax_basis']['value'],m.pv(m.run(),.1,.025)['value'])
  self.assertGreater(s['recovery_zero_tax_basis']['annual_trace'][9]['S']['economic_realization_tax'],0)
  self.assertLess(s['loan_exit20_direct_only']['value'],s['loan_exit20']['value'])
 def test_08_exit_removes_cash_yield_no_doublecount(self):
  for year in (20,40):
   rr=m.run(loan_exit_year=year);e=rr[year-1]['L']
   self.assertGreater(e['exit_gross_cash'],e['exit_parent_net'])
   self.assertNotEqual(e['exit_parent_net'],e['exit_parent_profit'])
   self.assertTrue(all(z['L']['cash']==0 and z['L']['financial_interest']==0 for z in rr[year:]))
 def test_09_capital_cancellation_claim_priority(self):
  rr=m.run()
  for z in rr:
   p=z['P']
   self.assertAlmostEqual(z['dps'],(p['distribution']+p['capital_payment'])/z['pre_cancel_shares']*z['pre_cancel_holder_factor'],12)
   if p['capital_payment']>0:
    self.assertGreater(p['capital_reduction_fee'],0)
    self.assertGreaterEqual(p['cash']+1e-7,p['creditor_cash_protection_for_capital_action'])
    self.assertAlmostEqual(z['shares']/z['pre_cancel_shares'],z['holder_share_factor']/z['pre_cancel_holder_factor'],12)
    self.assertLess(z['shares'],z['pre_cancel_shares'])
 def test_10_full_lossless_hash_and_tamper(self):
  packed=json.loads((D/'2026-Q3-output.json').read_text());self.assertEqual(m.expand_traces(m.pack_traces(self.o)),self.o)
  packed['units']='tampered'
  with self.assertRaises(AssertionError):m.expand_traces(packed)
 def test_11_exact_reader_candidate_result(self):
  r=json.loads((D/'result.json').read_text());c=json.loads((D/'candidate.json').read_text())['result'];self.assertEqual(r,c)
  report=(D/'2026-Q3.md').read_text();self.assertEqual(r['report_markdown'],report);self.assertEqual(r['return_model'],self.o['return_model'])
  for key,idx in [('low',0),('high',1)]:self.assertEqual(r['value_range'][key],self.o['scenarios']['base'][idx]['current']);self.assertIn(str(r['value_range'][key]),report)
  for x in r['return_model']['base_case_distributions_per_share']:self.assertIn(str(x),report)
  for link in re.findall(r'\]\(([^)]+)\)',report):
   if not link.startswith('http'):
    self.assertIn(link, ['../models/2026-Q3.py','../models/2026-Q3-output.json'])
    self.assertTrue((D/Path(link).name).is_file(),link)
 def test_12_independent_literal_rebuild(self):
  subprocess.run([sys.executable,str(D/'independent-literal-rebuild.py')],check=True,stdout=subprocess.DEVNULL)
  x=json.loads((D/'independent-literal-output.json').read_text());self.assertTrue(x['pass'])
 def test_13_full_audit_fresh_regeneration(self):
  subprocess.run([sys.executable,str(D/'validate-opening.py')],check=True,stdout=subprocess.DEVNULL)
  x=json.loads((D/'validation.json').read_text());self.assertTrue(x['fresh_generation_bytes_equal']);self.assertEqual(x['opening_endpoint_convergence_paths'],96)
if __name__=='__main__':unittest.main()

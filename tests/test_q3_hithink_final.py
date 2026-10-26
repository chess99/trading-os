#!/usr/bin/env python3
"""Portable frozen 300033 tests. Run: python test_q3_hithink_final.py -v
Only sibling model/manifest/cases/report/result/candidate are required.
No old workspace paths, network, prices, repository edits or persistent outputs.
Independent literal inputs are embedded, not read from production parameters.
Fresh generation occurs in TemporaryDirectory and is removed automatically.
"""
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from q3_final_fixture import staged_company
D = staged_company("300033")
EXPECTED_SHA = "e418829f7a2fb484c811f67dea720fdcb11075542d1d6dfff3624db95f47f4d5"
EXPECTED_BYTES = 74023217

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def load_model(path):
    spec = importlib.util.spec_from_file_location("hithink_model", path)
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    return model

def calculate(structural=False,r=.1,ga=.04,g=.02,ml=.42,begin=10,interval=5,delivery=.5,fee_rate=.02,capital_share=1.,parent_begin=15,parent_fee=.02,basis=1.,zero_yield=False,revseq=None,marseq=None,rates=None,capratio=.2,construction=None,initial_capacity=None,downshare=.5,continued=False,lag=False,upstream=.8,release_start=6,exit_year=10,realization=.9,offshore_cost=.4007804,offshore_basis=1.,legacytax=False,initial_reserve=None,initial_cash=None,uniform_tax=None):
 C=[2.4,.325,1.45,.3,2.4,2.36567701089,.918,.325];U=[2.7,.35,.9,.2,1.2,1.1,.5,.35];S=[.36081535125,0,0,0,0,0,0,0]
 K=[.75264,.03,.3,.01,.20766,.055];W=[0,.115,.27,.22,.16,.12,0,.115];T=[.25,.15,.15,.25,.15,.25,.2,.2];L=[0.]*8;E=[0.]*8
 costs=[0,.00133118242,.30,.01,.20766,.055,0,.2317];shares=.75264
 owed=[0.]*8
 if rates:T=rates[:]
 if initial_reserve:S=initial_reserve[:]
 if initial_cash:C=initial_cash[:]
 OT=T if uniform_tax is None else [uniform_tax]*8
 if initial_capacity:U=initial_capacity[:]
 W[1]=.23*(1-downshare);W[7]=.23*downshare
 V=7.8;F=1.70810491672;N=.078;B=3.09069063185;rows=[]
 for t in range(1,301):
  rev=(revseq or ([6.8,6.5,6.3,6.2,6.2] if structural else [7.8,8.346,8.84676,9.3775656,9.84644388]))[t-1] if t<=5 else V*(1+ (0 if structural else ga*(1-min((t-5)/10,1))+g*min((t-5)/10,1)))
  mar=(marseq or ([.35,.30,.27,.26,.26] if structural else [.48]*5))[t-1] if t<=5 else ((marseq[-1] if marseq else (.26 if structural else .48)))*(1-min((t-5)/10,1))+(.24 if structural else ml)*min((t-5)/10,1)
  settle=t>10 and (t-10)%5==0
  pret=[-.16*rev/7.8]+[(rev*mar+.16*rev/7.8)*x for x in W[1:]]
  ii=[-sum(L)*.03]+[x*.03 for x in L[1:]]
  inc=[C[i]*(0 if zero_yield else .012) for i in range(8)]
  P=[pret[i]-max(pret[i],0)*OT[i]+inc[i]-E[i]*.05-ii[i]-(max(pret[i]+inc[i]/(1-T[i])-ii[i],0)-max(pret[i]+inc[i]/(1-T[i]),0))*T[i] for i in range(8)]
  if legacytax:P=[-.16*rev/7.8+inc[0]-E[0]*.05-ii[0]-(max(pret[0]+inc[0]/(1-T[0])-ii[0],0)-max(pret[0]+inc[0]/(1-T[0]),0))*T[0]]+[(rev*mar*.85+.16*rev/7.8)*W[i]+inc[i]-E[i]*.05-ii[i]-(max(pret[i]+inc[i]/(1-T[i])-ii[i],0)-max(pret[i]+inc[i]/(1-T[i]),0))*T[i] for i in range(1,8)]
  target=max(.6,1.70810491672+capratio*(rev-7.8)+sum((construction or [.18,.11,.06,0,0])[:min(t,5)]));df=max(target-F,-rev*.02);target=F+df
  nw=rev*.01;nb=rev*3.09069063185/7.8;invest=df+nw-N;floor=[.3]+[(rev*(.16 if structural else .12)+nb)*x for x in W[1:]]
  C=[C[i]+P[i]-(invest-(nb-B))*W[i] for i in range(8)]
  for i in range(1,8):C[i]-=owed[i];C[1 if i==7 else 0]+=owed[i];owed[i]=0.
  for i in range(1,8):
   q=min(max(floor[i]-C[i],0),max(C[0]-.3,0)) if i<=5 else 0;C[0]-=q;C[i]+=q;L[i]+=q
   q=min(max(floor[i]-C[i],0),max(.5-sum(E),0));C[i]+=q;E[i]+=q;assert C[i]>=floor[i]-1e-8
  for i in range(8):q=min(max(C[i]-floor[i],0),E[i]);C[i]-=q;E[i]-=q
  for i in range(1,8):q=min(max(C[i]-floor[i],0),max(L[i],0));C[i]-=q;C[0]+=q;L[i]-=q
  taxable=pret[0]+inc[0]/.75-ii[0]-E[0]*.05;gain=loss=tx=0
  if t==exit_year and C[6]>0:
   gross=C[6];tx=max(gross*realization-offshore_cost*offshore_basis,0);tax=(max(taxable+tx,0)-max(taxable,0))*.25;net=gross*realization-tax;gain=net-offshore_cost;loss=gross-net;C[6]=0;C[0]+=net;P[0]+=gain
  Q=P[:];D=[0.]*8
  for i in [7,1,2,3,4,5,6]:
   reserve=(.1*max(Q[i]+min(U[i],0),0) if continued else min(.1*max(Q[i]+min(U[i],0),0),max(.5*K[i]-S[i],0))) if i<6 else 0;S[i]+=reserve;U[i]+=Q[i]-reserve
   free=max(C[i]-floor[i],0);d=min(max(Q[i],0)*upstream,max(U[i],0),free);d+=min(max(U[i]-d,0),max(free-d,0)*.2) if t>=release_start else 0;U[i]-=d;D[i]=d;j=1 if i==7 else 0;Q[j]+=d
   offset=min(d,max(-L[i],0)) if j==0 else 0;L[i]+=offset
   if lag:owed[i]=d-offset
   else:C[i]-=d-offset;C[j]+=d-offset
   if begin is None and 1<=i<=5 and t>=10 and not settle:
    q=min(max(C[i]-floor[i]-max(U[i],0),0),max([0,.325,1.45,.3,2.4,2.36567701089][i]-max(-L[i],0),0));C[i]-=q;C[0]+=q;L[i]-=q
  event=begin is not None and t>=begin and (t-begin)%interval==0
  fees=0.;exit_tax=0.;exit_gain_taxable=0.
  if event:
   total=sum(max(C[i]-floor[i]-owed[i]-max(-L[i],0),0)*delivery for i in [1,2,3,4,5,7]);rate=min(total*capital_share,sum(costs))/total if total else 0
   for i in [1,2,3,4,5,7]:
    gross=max(C[i]-floor[i]-owed[i]-max(-L[i],0),0)*delivery;capital=gross*rate;div=gross-capital;fee=gross*fee_rate
    taxable_gain=capital*(1-basis);tax=.25*(max(taxable+exit_gain_taxable+taxable_gain,0)-max(taxable+exit_gain_taxable,0));exit_gain_taxable+=taxable_gain;exit_tax+=tax
    C[i]-=gross;C[0]+=gross-fee-tax;cb=sum(costs);costs=[max(0,x*(1-capital/cb)) for x in costs] if cb else costs;Q[0]+=div-fee-tax;U[i]-=min(div,max(U[i],0));fees+=fee
  taxable+=exit_gain_taxable
  tax=(max(taxable+tx+D[6],0)-max(taxable+tx,0))*.25;P[0]-=tax;Q[0]-=tax;C[0]-=tax
  dues=[max(-x,0) if settle else 0 for x in L];q=min(max(.3+sum(dues)-C[0],0),max(.5-sum(E),0));C[0]+=q;E[0]+=q;assert C[0]>=.3+sum(dues)-1e-8
  for i in range(1,8):C[0]-=dues[i];C[i]+=dues[i];L[i]+=dues[i]
  reserve=.1*max(Q[0]+min(U[0],0),0) if continued else min(.1*max(Q[0]+min(U[0],0),0),max(.5*K[0]-S[0],0));S[0]+=reserve;U[0]+=Q[0]-reserve
  free=max(C[0]-.3,0);d=min(max(sum(P)-gain-loss-fees-exit_tax,0)*.8,max(U[0],0),free);d+=min(max(U[0]-d,0),max(free-d,0)*(1 if event else .2)) if t>=release_start else 0;C[0]-=d;U[0]-=d
  if event and parent_begin is not None and t>=parent_begin:
   gross=min(max(C[0]-.3-max(U[0],0),0),max(K[0]-.05,0));fee=gross*parent_fee;C[0]-=gross;K[0]-=gross;shares-=gross;U[0]-=fee;d+=gross-fee
  rows.append(dict(year=t,dividend=d,cash=C[:],capacity=U[:],loans=L[:],reserve=S[:],fixed=target,floor=floor,shares=shares,costs=costs[:],external=E[:],payable=owed[:],registered=K[:],revenue=rev,working=nw,contract=nb));V=rev;F=target;N=nw;B=nb
 return rows

def literal_definitions():
 definitions={'base':{},'core_low':dict(r=.105,ga=.03,g=.015,ml=.40),'core_high':dict(r=.095,ga=.045,g=.025,ml=.44),'structural_adverse':dict(structural=True),'old_profit_capacity_no_realization':dict(begin=None),'structural_old_no_realization':dict(structural=True,begin=None),'realization_delay20':dict(begin=20),'structural_delay20':dict(structural=True,begin=20),'realization_fee10':dict(fee_rate=.10),'realization_capacity25':dict(delivery=.25),'structural_capacity25':dict(structural=True,delivery=.25),'realization_interval10':dict(interval=10),'capital_return_share50':dict(capital_share=.5),'realization_capacity100':dict(delivery=1.),'no_parent_capital_return':dict(parent_begin=None),'parent_capital_return_delay30':dict(parent_begin=30),'parent_reduction_fee10':dict(parent_fee=.10),'domestic_zero_tax_basis':dict(basis=0.),'zero_financial_yield_fromY1':dict(zero_yield=True)}
 definitions.update({'cyclical_weak':dict(revseq=[6,6.3,7.1,8.1,9],marseq=[.32,.34,.40,.44,.46]),'optimistic':dict(revseq=[8.5,9.52,10.5672,11.62392,12.6700728],marseq=[.50,.51,.51,.50,.50],ga=.05,g=.025,ml=.45),'margin_minus5pp_fromY1':dict(marseq=[.43]*5,ml=.37),'growth_lower_fromY6':dict(ga=.02,g=0),'capital_double_fromY1':dict(capratio=.4,construction=[.36,.22,.12,0,0]),'zero_sub_opening_retained':dict(initial_capacity=[2.7,0,0,0,0,0,0,0]),'downstream_old_loss350m':dict(initial_capacity=[2.7,.35,.9,.2,1.2,1.1,.5,-.35]),'downstream_share0':dict(downshare=0),'downstream_share100':dict(downshare=1),'continued_reserves':dict(continued=True),'one_year_upstream_lag_release11':dict(lag=True,release_start=11),'subs_upstream40_release11':dict(upstream=.4,release_start=11),'offshore_exit_delay20':dict(exit_year=20),'offshore_realization50':dict(realization=.5),'offshore_realization100':dict(realization=1.),'offshore_zero_tax_basis':dict(offshore_basis=0.),'offshore_all_parent_cost':dict(offshore_cost=1.20647158242),'no_offshore_exit':dict(exit_year=None),'tax_qualification_not_renewed':dict(rates=[.25,.25,.25,.25,.15,.25,.2,.2]),'downstream_tax25':dict(rates=[.25,.15,.15,.25,.15,.25,.2,.25]),'legacy_uniform15_budget':dict(legacytax=True),'capital_return_share10_slow_diagnostic':dict(capital_share=.1)})
 definitions.update({'domestic_reserves_already_full':dict(initial_reserve=[.36081535125,.015,.15,.005,.10383,.0275,0,0]),'downstream_old_retained0':dict(initial_capacity=[2.7,.7,.9,.2,1.2,1.1,.5,0]),'downstream_old_retained_all':dict(initial_capacity=[2.7,0,.9,.2,1.2,1.1,.5,.7]),'normalized_operating_tax20':dict(uniform_tax=.20),'offshore_immediate_recovery_upper_bound':dict(initial_cash=[2.4,.325,1.45,.3,2.4,2.36567701089,0,.325],initial_capacity=[2.7-.918,.35,.9,.2,1.2,1.1,0,.35]),'no_reverse_domestic_loans':{},'reverse_no_periodic_settlement':{},'reverse_maturity15_no_renewal':{},'reverse_loans_delayed20':{},'structural_reverse_maturity15':dict(structural=True),'structural_no_reverse':dict(structural=True)})
 return definitions

class HithinkFinalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Finish the independent 52x300 calculations before importing production.
        cls.definitions = literal_definitions()
        cls.literal = {name: calculate(**params) for name, params in cls.definitions.items()}
        cls.model = load_model(D / "2026-Q3.py")
        cls.manifest = json.loads((D / "2026-Q3-output.json").read_text())
        cls.output = cls.model.expand_output(cls.manifest, D)
        cls.full = canonical(cls.output)
        cls.evidence = {}

    def close(self, actual, expected, tolerance=1e-10):
        self.assertLessEqual(abs(actual-expected), tolerance, (actual, expected))

    def fixture(self):
        p = copy.deepcopy(self.model.PARAM)
        p.update(revenue=[0]*5, margin=[0]*5, parent_cost=0, cash_yield=0,
                 loan_rate=0, external_rate=0, capital_ratio=0, working_ratio=0,
                 contract_ratio=0, construction=[0]*5, liquidity_ratio=0,
                 normal_payout=0, upstream_payout=0, release_start=999,
                 external_limit=0, economic_realization_start=1,
                 economic_realization_interval=5, economic_dividend_capacity_ratio=1,
                 economic_realization_fee=.02, economic_capital_share=1,
                 domestic_parent_cost_budget=[0,.4,0,0,0,0,0,0],
                 parent_capital_return_start=None)
        st = dict(cash=[.3,1,0,0,0,0,0,0], capacity_budget=[0]*8,
                  reserve_budget=[0]*8, registered_capital_budget=[0]*8,
                  loans=[0]*8, external=[0]*8, payable=[0]*8,
                  rev=0, fixed=p['initial_fixed'], working=0, contract=0)
        return p, st

    def test_01_reader_and_56_model_files(self):
        self.assertEqual(self.manifest['schema'], 'cn300033_complete_case_manifest_v1')
        self.assertEqual(len(self.manifest['case_files']), 54)
        files = ['2026-Q3.py', '2026-Q3-output.json'] + [v['file'] for v in self.manifest['case_files'].values()]
        self.assertEqual(len(set(files)), 56)
        for filename in files:
            self.assertTrue((D/filename).is_file(), filename)
            self.assertLess((D/filename).stat().st_size, 16*1024*1024)
        self.assertEqual(len(self.full), EXPECTED_BYTES)
        self.assertEqual(hashlib.sha256(self.full).hexdigest(), EXPECTED_SHA)
        self.assertEqual(self.manifest['expanded_canonical_sha256'], EXPECTED_SHA)
        report = (D/'report.md').read_text()
        result = json.loads((D/'result.json').read_text())
        candidate = json.loads((D/'candidate.json').read_text())['result']
        self.assertEqual(result, candidate)
        self.assertEqual(result['report_markdown'], report)
        self.assertEqual(result['value_range'], self.output['core']['value_range'])
        self.assertEqual(result['return_model']['base_case_distributions_per_share'], self.output['core']['distributions'])
        self.assertEqual(result['return_model']['base_case_terminal_equity_value_range_per_share']['year_5'], self.output['core']['tv5'])
        self.assertIn('固定的是按截止日原一股持续持有权益组合计算的归一分母', report)
        self.assertNotIn('未来股数固定', report)
        self.assertIn('未获批准的条件预测特别分派', report)
        self.assertNotIn('经核准条件预算', report)
        self.assertNotIn('国内零税基在核心因母税务亏损非约束', report)
        self.assertIn('1.56834943497亿元', report)
        self.assertIn('python 2026-Q3.py --expand 2026-Q3-output.json > 2026-Q3-expanded.json', report)
        self.assertIn('54个具名场景文件', report)
        base = self.output['cases']['base']
        zero = self.output['cases']['domestic_zero_tax_basis']
        self.close(base['annual_rows'][14]['state']['issued_shares'], .13066376882999964)
        self.close(zero['annual_rows'][9]['domestic_exit_incremental_cash_tax'], .1568349434965122)
        self.close(zero['valuation']['value']-base['valuation']['value'], -.08033941859739)
        self.evidence['reader_identity'] = {'model_files':len(files), 'full_sha256':EXPECTED_SHA,
            'full_bytes':len(self.full), 'three_reader_corrections':'pass', 'core_D_TV_exact':True}

    def test_02_actual_legal_roll_and_old_receivable(self):
        m = self.model
        self.assertEqual(m.legal_roll(0,5,20,10), (9,6,1))
        self.assertEqual(m.legal_roll(-3,0,20,5), (1.8,.2,.2))
        self.assertEqual(m.legal_roll(0,10,20,10), (10,10,0))
        self.assertEqual(m.legal_roll(0,5,10,10), (10,5,0))
        self.assertEqual(m.legal_roll(0,None,None,10), (10,None,0))
        p, st = self.fixture(); p['economic_realization_start'] = None
        st['payable'][1] = .5
        row = m.run(p,1,st)[0]
        self.close(row['state']['cash'][0], .8)
        self.close(row['parent_profit_capacity_budget'], 0)
        self.close(row['state']['capacity_budget'][0], 0)

    def test_03_actual_expense_tax_principal_and_source_cash(self):
        p, st = self.fixture()
        row = self.model.run(p,1,st)[0]
        event = row['economic_surplus_realization'][0]
        for key, expected in dict(gross=1, mother_cost_released=.4, fee=.02,
                                  net_to_parent=.98, mother_profit_effect=.58).items():
            self.close(event[key], expected)
        self.close(row['state']['cash'][1], 0)
        self.close(sum(row['state']['domestic_parent_cost_remaining']), 0)
        p['domestic_capital_tax_basis_ratio'] = 0
        taxed = self.model.run(p,1,st)[0]['economic_surplus_realization'][0]
        self.close(taxed['cash_tax'], .1)
        self.close(taxed['net_to_parent'], .88)
        self.close(taxed['mother_profit_effect'], .48)
        p['domestic_capital_tax_basis_ratio']=1; p['cash_yield']=.012
        rows = self.model.run(p,2,st)
        self.close(rows[0]['state']['cash'][1],0)
        self.close(rows[1]['own_profit_capacity_budget'][1],0)
        self.close(rows[1]['state']['cash'][1],0)
        self.evidence['expense_and_tax_handcase'] = {'gross':1,'cost':.4,'fee':.02,
            'net':.98,'profit':.58,'zero_basis_tax':.1,'zero_basis_net':.88,
            'released_source_future_yield':0}

    def test_04_actual_claim_priority_and_operating_floor(self):
        p, st = self.fixture()
        p['domestic_parent_cost_budget'] = [0,.1,0,0,0,0,0,0]
        st['payable'][1]=.15; st['external'][1]=.25; st['loans'][1]=.20
        row=self.model.run(p,1,st)[0]
        self.close(row['subs_prior_settlement'][1],.15)
        self.close(row['external_repaid'][1],.25)
        self.close(row['shareholder_loan_repayment'][1],.20)
        event=row['economic_surplus_realization'][0]
        self.close(event['gross'],.40)
        self.close(event['fee'],.008)
        self.close(event['net_to_parent'],.392)
        self.close(event['mother_profit_effect'],.292)
        self.close(row['state']['cash'][0],1.042)
        self.close(row['state']['cash'][1],0)
        self.close(sum(row['state']['external']),0)
        self.close(sum(row['state']['loans']),0)
        p, st=self.fixture()
        st['loans'][1]=-.2
        row=self.model.run(p,1,st)[0]
        self.close(row['economic_surplus_realization'][0]['gross'],.8)
        self.close(row['state']['cash'][1],.2)
        self.close(row['state']['loans'][1],-.2)
        p, st=self.fixture()
        p.update(revenue=[1]*5, liquidity_ratio=.4, weights=[0,1,0,0,0,0,0,0])
        st['rev']=1
        row=self.model.run(p,1,st)[0]
        self.close(row['cash_floor'][1],.4)
        self.close(row['economic_surplus_realization'][0]['gross'],.6)
        self.close(row['state']['cash'][1],.4)
        self.evidence['claim_priority_handcase']={'prior_dividend':.15,'external_principal':.25,
            'parent_loan_repaid':.20,'source_surplus_after_claims':.40,'net_after_fee':.392,
            'reverse_claim_reserved':.20,'operating_floor_preserved':.40}

    def test_05_actual_capital_cancellation_original_share_bundle(self):
        p, st=self.fixture()
        p.update(parent_capital_return_start=1,parent_reduction_fee=.02,parent_minimum_registered=.05)
        st['registered_capital_budget'][0]=.75264
        st['cash']=[.5,0,0,0,0,0,0,0]
        row=self.model.run(p,1,st)[0]
        e=row['parent_proportionate_capital_return']
        self.close(e['gross'],.2);self.close(e['fee'],.004)
        self.close(e['net_to_original_holders'],.196)
        self.close(e['shares_cancelled'],.2)
        self.close(row['state']['issued_shares'],.55264)
        self.close(row['state']['registered_capital_budget'][0],.55264)
        self.close(row['parent_profit_capacity_budget'],0)
        self.close(row['state']['capacity_budget'][0],-.004)
        self.close(row['dividend_per_share'],.196/.75264)
        original_bundle=e['shares_per_original_share']
        self.close(original_bundle/.55264,1/.75264)
        self.close(self.model.valuation([row],.1)['value'],.196/1.1/.75264)
        p['parent_extra_cost']=2
        with self.assertRaises(ValueError): self.model.run(p,1,st)
        self.evidence['capital_return_handcase']={'gross':.2,'fee':.004,'net':.196,
            'shares_cancelled':.2,'remaining_shares':.55264,'denominator_original':.75264,
            'no_accounting_profit':True,'zero_distribution_insolvency':'raised ValueError'}

    def test_06_independent_literal_52_complete_annual_paths(self):
        self.assertEqual(len(self.literal),52)
        self.assertEqual(set(self.literal),set(self.model.cases()))
        errors={}
        for name, independent in self.literal.items():
            target=self.output['cases'][name]['annual_rows']
            self.assertEqual(len(independent),300);self.assertEqual(len(target),300)
            peak=0
            for a,b in zip(independent,target):
                self.assertEqual(a['year'],b['year'])
                pairs=[(a['dividend'],b['dividend']),(a['fixed'],b['state']['fixed']),
                       (a['shares'],b['state']['issued_shares']),(a['working'],b['state']['working']),
                       (a['contract'],b['state']['contract']),(a['revenue'],b['revenue'])]
                for left,right in [('cash','cash'),('capacity','capacity_budget'),('loans','loans'),
                                   ('costs','domestic_parent_cost_remaining'),('external','external'),('payable','payable')]:
                    pairs.extend(zip(a[left],b['state'][right]))
                pairs.extend(zip(a['floor'],b['cash_floor']))
                pairs.extend(zip(a['reserve'][:6],b['state']['reserve_budget'][:6]))
                pairs.extend(zip(a['registered'],b['state']['registered_capital_budget'][:6]))
                for x,y in pairs: peak=max(peak,abs(x-y))
            self.assertLess(peak,1e-8,(name,peak));errors[name]=peak
        self.evidence['independent_literal']={'paths':52,'years_each':300,
            'max_absolute_error':max(errors.values()),'all_path_errors':errors}

    def test_07_all_actual_paths_cash_priority_and_share_normalization(self):
        maximum=0
        for name,case in self.output['cases'].items():
            p=case['parameters'];previous=sum(p['cash']);shares=.75264
            for row in case['annual_rows']:
                expected=previous+sum(row['cashflow_before_financing'])+sum(row['external_new'])-sum(row['external_repaid'])-row['dividend']-row['offshore_financial_portfolio_exit']['friction']-row['economic_realization_fees']-row['domestic_exit_incremental_cash_tax']
                maximum=max(maximum,abs(sum(row['state']['cash'])-expected));previous=sum(row['state']['cash'])
                returned=row['parent_proportionate_capital_return'];shares-=returned['shares_cancelled']
                self.close(row['state']['issued_shares'],shares,1e-8)
                self.close(row['state']['issued_shares'],row['state']['registered_capital_budget'][0],1e-8)
                self.close(row['dividend_per_share'],row['dividend']/.75264,1e-8)
                self.assertGreaterEqual(shares,.05-1e-8)
                for i in range(8): self.assertGreaterEqual(row['state']['cash'][i],row['cash_floor'][i]-1e-8)
                for event in row['economic_surplus_realization']:
                    self.close(event['net_to_parent'],event['gross']-event['fee']-event['cash_tax'],1e-8)
                    self.close(event['mother_profit_effect'],event['qualified_dividend_budget']-event['fee']-event['cash_tax'],1e-8)
        self.assertLess(maximum,1e-7)
        self.evidence['full_cash_bridge']={'cases_including_shadow':54,'max_error':maximum}

    def test_08_isolated_singlepy_55_json_and_cli(self):
        with tempfile.TemporaryDirectory(prefix='hithink-final-') as tmp:
            target=Path(tmp);shutil.copyfile(D/'2026-Q3.py',target/'2026-Q3.py')
            self.assertEqual([x.name for x in target.iterdir()],['2026-Q3.py'])
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            subprocess.run([sys.executable,str(target/'2026-Q3.py')],cwd=target,env=env,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=240)
            files=['2026-Q3-output.json']+[v['file'] for v in self.manifest['case_files'].values()]
            self.assertEqual(len(files),55)
            self.assertEqual(set(x.name for x in target.glob('*.json')),set(files))
            for filename in files:self.assertEqual((target/filename).read_bytes(),(D/filename).read_bytes(),filename)
            for args in [['--expand',str(target/'2026-Q3-output.json')],['--expand']]:
                proc=subprocess.run([sys.executable,str(target/'2026-Q3.py'),*args],cwd=target,env=env,
                                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=120)
                self.assertEqual(proc.stdout,self.full+b'\n')
                self.assertEqual(json.loads(proc.stdout),self.output)
            broken=copy.deepcopy(self.manifest);broken['expanded_canonical_sha256']='0'*64
            with self.assertRaises(AssertionError):self.model.expand_output(broken,D)
            missing=target/self.manifest['case_files']['base']['file'];missing.unlink()
            with self.assertRaises(FileNotFoundError):self.model.expand_output(self.manifest,target)
        self.evidence['isolated_singlepy']={'only_input':'2026-Q3.py','generated_json_files':55,
            'byte_identical':True,'both_expand_cli_modes':'complete canonical bytes + newline',
            'expanded_sha256':EXPECTED_SHA,'missing_file_and_bad_sha':'explicit failures'}

    @classmethod
    def tearDownClass(cls):
        print('\nCONCRETE_PASS_EVIDENCE='+json.dumps(cls.evidence,ensure_ascii=False,sort_keys=True), flush=True)

if __name__=='__main__':
    sys.dont_write_bytecode=True
    unittest.main(verbosity=2)

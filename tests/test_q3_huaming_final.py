"""Read-only audit. Literal independent recurrence first; production loaded only for comparison/tests."""
import json,runpy,pathlib,math
R=pathlib.Path(__file__).resolve().parents[1]/"research/companies/CN/002270/models"
SRC=R
def independent(rate=.0975,n=600,margin_delta=0,upstream=1):
    p=.06;b=.73213186815-p;u=.21176170033;s=0;reg=.896225431
    debt=.78858193369;pd=0;arrears=.39698138794;rev=2.36;cnc=.153;cap=3
    due={};pdue={};rows=[]
    for y in range(1,n+1):
        old=rev;rev*=1+[.09,.09,.08,.07,.06,.05,.04,.03,.025,.02][min(y-1,9)]
        oldc=cnc;cnc*=1+(.03 if y<6 else .02)
        m=.34-.002*min(y,10)+margin_delta;e=rev*m
        inv=max(rev-old,0)*m/(.25 if y<=5 else .18)+max(cnc-oldc,0)*.055/.12
        solar=.187 if y<=20 else 0;dep=.01925 if y<=20 else 0;maint=.025*solar
        prof=e+(.055*(cnc+solar))+b*.015-debt*.045-e*(.007+.000336+.0025)-cnc*.055*.03-e*.004
        pf=p*.015-pd*.045;hq=.02*1.02**(y-1)
        b+=prof+dep-maint-inv;cap+=inv-dep+maint
        repay=min(debt,(.78858193369/8 if y<=8 else 0)+due.pop(y,0));debt-=repay;b-=repay
        pr=min(pd,pdue.pop(y,0));pd-=pr;p-=pr
        floor=.085*(rev+cnc+solar);pmin=.03*1.02**(y-1)
        payold=min(arrears,max(0,b-floor));arrears-=payold;b-=payold;p+=payold
        c=max(prof,0)*(.65 if y<=5 else min(.95,.65+.06*(y-5)))*upstream
        release=max(b-floor-c-arrears,0)*.2*upstream if y>=6 else 0
        d=min(c+release,max(0,b-floor));b-=d;p+=d
        recovery=.07 if y==2 else .02 if y==3 else 0
        loss=-.00695481108 if y==3 else 0
        if y==20:
            b+=.01875
            ext=min(.01875*upstream,max(b-floor,0));d+=ext;b-=ext;p+=ext
        p+=recovery+pf-hq
        pp=d+pf-hq+loss
        add=min(max(reg/2-s,0),max(pp-min(max(-u,0),max(pp,0)),0)/10)
        u+=pp-add;s+=add
        if y==1:p-=.125001897
        support=min(max(0,floor-b),max(p-pmin,0));b+=support;p-=support
        borrow=min(max(floor-b,0),max(.95-debt-pd,0));b+=borrow;debt+=borrow
        if borrow>1e-12:
            for j in [y+1,y+2]:due[j]=due.get(j,0)+borrow/2
        target=max(prof+pf-hq,0)*.7 if y<=5 else max(p-pmin,0)
        div=min(max(u,0),max(p-pmin,0),target);u-=div;p-=div
        refund=fee=0
        if y>=12:
            request=.4 if y==12 else max(p-pmin,0)/1.02
            refund=min(max(p-pmin,0)/1.02,reg*.49,request);fee=refund*.02;p-=refund+fee;u-=fee;reg-=refund
        pb=min(max(pmin-p,0),max(.95-debt-pd,0));p+=pb;pd+=pb
        if pb>1e-12:
            for j in [y+1,y+2]:pdue[j]=pdue.get(j,0)+pb/2
        rows.append(dict(dps=(div+refund)/.896225431,parent_cash=p,budget_cash=b,retained=u,statutory=s,registered=reg,shares=reg,old_ar=arrears,debt=debt,parent_debt=pd,operating_capital=cap))
    return {'pv':sum(x['dps']/(1+rate)**(j+1) for j,x in enumerate(rows)),'tv5':sum(x['dps']/(1+rate)**(j-4) for j,x in enumerate(rows) if j>=5),'first5':[x['dps'] for x in rows[:5]],'rows':rows}

def test_huaming_independent_full_paths_and_actual():
 
 configs=[(.105,0,1),(.09,0,1),(.0975,-.03,1),(.0975,0,.8)]
 results=[independent(r,margin_delta=m,upstream=u) for r,m,u in configs]
 p=runpy.run_path(str(R/'2026-Q3.py'))
 out={'comparisons':[]}
 for cfg,a in zip(configs,results):
     r,m,u=cfg;b=p['run'](discount=r,margin_shift=m,upstream_scale=u)
     errors=[]
     for ar,br in zip(a['rows'],b['rows']):
         for k,v in ar.items():
             w=br['dps'] if k=='dps' else br['end'][k]
             errors.append(abs(v-w)/max(1,abs(v)))
     assert max(errors)<1e-10,(cfg,max(errors))
     out['comparisons'].append(dict(config=cfg,pv=a['pv'],tv5=a['tv5'],first5=a['first5'],max_relative_state_error=max(errors)))
 # Hand-defined counterexamples invoke actual production functions, not worker assertions.
 r=p['reserve_step'];assert r(0,5,20,10,10)==(9,6,1);assert r(-8,0,20,10)==(1.8,.2,.2);assert r(0,10,20,10)==(10,10,0);assert r(0,10,24,10)==(9,11,1)
 a=p['asset_exit'](12,10,1,.25,.7);assert math.isclose(a['cash'],7.525) and math.isclose(a['profit'],.525)
 c=p['capital_return'](10,20,20,4,.05,.65);assert c['profit']==0 and c['shares']==16 and c['registered']==16 and c['paid']==2.6 and c['minority']==1.4 and c['fees']==.2
 z=p['run'](extra_payment=10,debt_limit=0);assert not z['feasible'] and z['rows'][0]['dividend']==0
 base=p['run']();row=base['rows'][0];assert abs(row['parent_profit']-(row['upstream_declared']+.0009-.02))<1e-12
 # Renewal actual effective years and operational downside feasibility.
 out['paths']={}
 for name,kw in [('base',{}),('structural',{'mode':'structural'}),('tax',{'tax_fail':True}),('lowup_slow',{'upstream_scale':.8,'release_rate':.1,'release_start':10}),('noreturn',{'redemption':0}),('issue',{'issue':.5})]:
     v=p['run'](**kw);rows=v['rows'];out['paths'][name]={'pv':v['pv'],'tv5':v['tv5'],'feasible':v['feasible'],'reserve_years':[x['year'] for x in rows if x['parent_statutory_add']>1e-9],'release_years_first20':[x['year'] for x in rows[:20] if x['financial_release_budget']>1e-9], 'year20_solar_exit':rows[19]['solar_exit'],'year21_solar_cash_adjust':rows[20]['solar_cash_adjust'],'min_cash_headroom':min(min(x['end']['parent_cash']-x['parent_floor'],x['end']['budget_cash']-x['budget_floor']) for x in rows)}
 out['convergence']={str(n):p['run'](years=n,discount=.09)['pv'] for n in [100,300,600,900]}
 # Reconstruct cash liability mismatch if applicable (does not change production).

def test_huaming_all_future_policy():
 p=R;m=runpy.run_path(str(R/"2026-Q3.py"));run=m["run"];full=m["expand_output"](json.loads((R/"2026-Q3-output.json").read_text()))
 result={'all_paths':{},'cohorts':[],'production_counterexamples':{},'policy_bridge':{}}
 # Historical and explicit refusal paths remain visible counterfactuals, never claimed fully realised.
 excluded={'no_reduction','single_reduction_oldpolicy','bridge_reserve0','bridge_minor_asset','bridge_finite_solar'}
 for name,path in full['paths'].items():
  if name.startswith(('old_','same_budget_')) or name in excluded:continue
  rows=path['rows'];start=25 if name in ['reduction_year20','principal_1bn_probe'] else 24 if name=='residual_sweep_year20' else 18
  residual=max(max(x['end']['parent_cash']-x['parent_floor'],0)/max(1,x['parent_floor']) for x in rows if x['year']>=start)
  assert residual<1e-7,(name,residual)
  result['all_paths'][name]={'feasible':path['feasible'],'post_window_max_parent_excess_normalized':residual,'year13_cash':rows[12]['end']['parent_cash'],'year13_floor':rows[12]['parent_floor'],'capitalised_opening_total':sum(x['capitalised_opening_surplus'] for x in rows),'capitalised_issue_total':sum(x['capitalised_issue_premium'] for x in rows)}
 # Both total stock and separately born principal batches; 1bn = RMB10亿元, not merely 0.01bn.
 for mode in ['base','cyclical','structural','upside']:
  for born in [6,13,20,30,50,100,200,500]:
   x=run(mode=mode,principal_recovery_year=born,principal_recovery_amount=1.)
   assert x['feasible'],(mode,born,x['failure'])
   z=x['rows'][born-1];assert z['probe_recovery']==1 and z['end']['probe_basis']==0
   # Recovery itself must not create accounting income; compare declared+finance/HQ+disposal only.
   before=z['begin'];hq=.02*((1.01 if mode=='structural' else 1.02)**(born-1))
   expected=z['upstream_declared']+before['parent_cash']*.015-before['parent_debt']*.045-hq+z['asset_disposal_profit']
   assert abs(z['parent_profit']-expected)<1e-9
   first=max(18,born+4);remaining=max(max(r['end']['parent_cash']-r['parent_floor'],0)/max(1,r['parent_floor']) for r in x['rows'][first-1:])
   assert remaining<1e-7,(mode,born,remaining)
   result['cohorts'].append({'mode':mode,'born':born,'principal_bn':1,'no_excess_from_year':first,'max_excess_normalized':remaining,'capitalised_opening_bn':sum(r['capitalised_opening_surplus'] for r in x['rows']),'pv':x['pv'],'tv5':x['tv5']})
 # Simultaneous total 1bn existing principal, twenty independently born 0.05bn batches.
 schedule=tuple((20+5*k,.05) for k in range(20));x=run(principal_recovery_schedule=schedule)
 assert x['feasible']
 for born,amount in schedule:
  assert math.isclose(x['rows'][born-1]['probe_recovery'],amount)
  assert max(x['rows'][born+3]['end']['parent_cash']-x['rows'][born+3]['parent_floor'],0)<1e-7
 assert abs(x['rows'][-1]['end']['probe_basis'])<1e-12
 result['joint_twenty_cohorts']={'total_principal_bn':1,'schedule':schedule,'pv':x['pv'],'tv5':x['tv5'],'all_batches_clear_within_four_years':True,'no_fifo_cancellation':True}
 # All conversion/issue/cancellation paths preserve the same original holder fraction.
 for kw in [dict(issue=.5),dict(principal_recovery_year=20,principal_recovery_amount=1.)]:
  z=run(**kw);fraction=.896225431/(.896225431+kw.get('issue',0)/10)
  for row in z['rows']:
   opening=row['begin'];end=row['end'];issue_nominal=row['equity']/10
   converted=row['capitalised_issue_premium']+row['capitalised_opening_surplus']
   assert abs(end['registered']-(opening['registered']+issue_nominal+converted-row['capital_return']))<1e-8
   assert abs(end['shares']-(opening['shares']+issue_nominal+row['bonus_shares']-row['cancellation']))<1e-8
   assert abs(row['dps']-(row['dividend']+row['capital_return'])/.896225431*fraction)<1e-8
  result['original_holder_fraction_'+str(kw)]=fraction
 # Explicit no credit: avoid passing this diagnostic off as legal certainty.
 x=run(principal_recovery_year=20,principal_recovery_amount=1,capitalisation_budget=0)
 result['par_only_1bn_diagnostic']={'pv':x['pv'],'year100_excess':x['rows'][99]['end']['parent_cash']-x['rows'][99]['parent_floor'],'reason':'Without conditional capital-surplus conversion, nominal registration is not a complete economic realisation route.'}
 # Genuine incremental productive capital stays invested and earns rather than being mislabeled cash.
 x=run(capital_shock_year=20,capital_shock_amount=1.)
 assert x['feasible'] and x['rows'][19]['probe_investment']==1 and x['rows'][20]['probe_profit']==.18 and x['rows'][-1]['end']['probe_capital']==1
 result['incremental_productive_1bn']={'pv':x['pv'],'tv5':x['tv5'],'year20_investment':1,'annual_posttax_income_from21':.18,'capital_still_operating_at600':1,'definition':'Additional continuing 100%-owned operating capacity, no separate terminal principal credit.'}
 cr=m['capital_return'](10,20,20,4,fee_rate=.05,ownership=.65,creditor_hold=9)
 assert math.isclose(cr['paid'],1/1.05*.65) and cr['cash']>=9 and cr['profit']==0
 z=m['capital_return'](10,20,20,4,creditor_hold=11);assert z['paid']==0 and z['shares']==20
 x=run(extra_payment=10,debt_limit=0);assert not x['feasible']
 result['production_counterexamples']={'creditor_hold_limits_payout':cr,'insufficient_creditor_assets_zero_payout':z,'zero_dividend_no_finance_failure':x['failure'],'reserve_registered_not_paid_in':m['reserve_step'](0,5,20,10,10),'capital_return_tax':'No company taxable gain on own capital repayment; recipient-specific tax not included. Asset disposal still separately taxable.'}
 for mode in ['base','cyclical','structural','upside']:
  old=run(mode=mode,annual_sweep=False);new=run(mode=mode)
  assert old['first5']==new['first5']
  result['policy_bridge'][mode]={'single_return':{k:old[k] for k in ['pv','tv5','first5']},'annual_residual_policy':{k:new[k] for k in ['pv','tv5','first5']},'delta_pv':new['pv']-old['pv']}

def test_huaming_singlefile_regeneration(tmp_path):
 import subprocess,sys
 (tmp_path/'2026-Q3.py').write_bytes((R/'2026-Q3.py').read_bytes())
 subprocess.run([sys.executable,'-I',str(tmp_path/'2026-Q3.py')],cwd=tmp_path,check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(R/'2026-Q3-output.json').read_bytes()
 subprocess.run([sys.executable,'-I',str(tmp_path/'2026-Q3.py'),'--expand',str(tmp_path/'expanded.json')],cwd=tmp_path,check=True)
 m=runpy.run_path(str(R/'2026-Q3.py'));assert json.loads((tmp_path/'expanded.json').read_text())==m['expand_output'](json.loads((R/'2026-Q3-output.json').read_text()))

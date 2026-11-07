"""CPIC 2026-Q3; CNY million; entirely self-contained stdlib model.
Run anywhere: python model.py > model-output.json. No price or external files.
"""
import json, math
S=9620.341455
OWN=[.98292,.985,1.0]
INIT=[dict(name='life',equity=173309.95,total=421019.11,core=293061.64,minimum=203822.59,cash=20000.,legal=0.),dict(name='pc',equity=72659.55,total=80679.59,core=67175.10,minimum=34338.70,cash=10000.,legal=0.),dict(name='other',equity=12209.527196,total=12209.527196,core=12209.527196,minimum=12209.527196,cash=2000.,legal=0.)]
SCENARIOS={
 'base':dict(profits=[29000.,9500.,1000.],growth=[.03,.025,.02],long=.02,r=.095,stress='none'),
 'core_low':dict(profits=[28000.,9000.,900.],growth=[.025,.02,.02],long=.02,r=.10,stress='none'),
 'core_high':dict(profits=[30000.,10000.,1100.],growth=[.035,.03,.02],long=.02,r=.09,stress='none'),
 'cyclical':dict(profits=[29000.,9500.,1000.],growth=[.03,.025,.02],long=.02,r=.10,stress='cycle'),
 'structural':dict(profits=[20000.,6500.,700.],growth=[0.,.01,0.],long=.01,r=.105,stress='structural'),
 'upside':dict(profits=[32000.,11000.,1200.],growth=[.05,.04,.03],long=.025,r=.09,stress='none'),
 'capital_tighter':dict(profits=[27000.,9000.,1000.],growth=[.02,.02,.02],long=.02,r=.095,stress='capital'),
 'conversion_now':dict(profits=[29000.,9500.,1000.],growth=[.03,.025,.02],long=.02,r=.095,stress='convert'),
 'capital_growth_persists':dict(profits=[29000.,9500.,1000.],growth=[.03,.025,.02],long=.02,r=.095,stress='fastcapital'),
 'regulatory_drag_high':dict(profits=[29000.,9500.,1000.],growth=[.03,.025,.02],long=.02,r=.095,stress='draghigh'),
 'unfunded_statutory_reserves':dict(profits=[29000.,9500.,1000.],growth=[.03,.025,.02],long=.02,r=.095,stress='reserves'),
 'remittance_delay':dict(profits=[29000.,9500.,1000.],growth=[.03,.025,.02],long=.02,r=.095,stress='delay'),
}
def close(a,b):
 assert abs(a-b)<=min(.01,1e-7+2e-13*max(abs(a),abs(b))),(a,b)

def holding_start(assets,investment_cost,liabilities,cb_liability,cash,declared_payable):
 own=assets-investment_cost-liabilities
 gross_noncash=assets-investment_cost-cash
 other_liabilities=liabilities-cb_liability
 paid_cash=cash-declared_payable
 remaining_other=other_liabilities-declared_payable
 net_noncash=gross_noncash-remaining_other
 resources=paid_cash+net_noncash
 close(resources,own+cb_liability)
 return dict(own_equity=own,net_resources=resources,cash=paid_cash,net_noncash=net_noncash,gross_noncash_assets=gross_noncash,other_liabilities_before=other_liabilities,other_liabilities_after=remaining_other,paid_dividend=declared_payable)

def sub_step(s,profit,g,target,ratios,reserve_rate=.1,delay=.05,shock=0.,reg_drag=0.,fixed_risk_budget=0.):
 """Profit is AFTER policyholder obligations, tax, perp coupon/other capital costs.
 Shareholder margin cash is explicitly distinct from policyholder premium cash.
 Regulatory conversion = retained common earnings only; no assumed CSM uplift.
 """
 old=s.copy(); minimum=s['minimum']*(1+g)
 total=s['total']+profit+shock-reg_drag; core=s['core']+profit+shock-reg_drag
 # Support common loss/capital stress by retaining first; top-up explicit if needed.
 topup=max(0.,ratios[0]*minimum-total,ratios[1]*minimum-core)
 total+=topup;core+=topup
 income=profit+shock
 distributable_before=s['legal']+income
 reserve_basis=max(0.,min(income,distributable_before))
 registered=s.get('registered_capital',0.)
 statutory_open=s.get('statutory_reserve',registered*.5)
 statutory_add=min(.1*reserve_basis,max(0.,registered*.5-statutory_open))
 risk_add=min(reserve_basis,reserve_rate*reserve_basis+fixed_risk_budget)
 statutory=statutory_open+statutory_add
 risk=s.get('general_risk_reserve',0.)+risk_add
 legal=distributable_before-statutory_add-risk_add
 head=max(0.,min(total-ratios[0]*minimum,core-ratios[1]*minimum))
 # Releasing only lawful accumulated earnings, not paid-in capital.
 wanted=max(0.,target*max(0.,profit)+(.20*head if target>=.999 else 0.))
 div=max(0.,min(wanted,head,legal))
 total-=div;core-=div;legal-=div
 eq=s['equity']+profit+shock+topup-div
 nondist=s.get('other_nondistributable',s['equity']-s['legal']-statutory_open-s.get('general_risk_reserve',0.))+topup
 close(eq,legal+statutory+risk+nondist)
 rec=delay*max(0.,profit)
 cash_margin=profit+old.get('receivable',0.)-rec
 cash_target=min(eq*.25,.08*minimum)
 # Invest retained margin or realize liquid shareholder assets to fund cash target.
 before=old['cash']+cash_margin+topup-div
 asset_purchase=before-cash_target
 invested=old.get('invested',old['equity']-old['cash'])+asset_purchase+shock
 cash=cash_target
 assert cash>=-1e-7 and invested>=-1e-7 and legal>=-1e-7
 close(eq,cash+invested+rec)
 close(total,old['total']+profit+shock-reg_drag+topup-div)
 close(core,old['core']+profit+shock-reg_drag+topup-div)
 assert total+1e-6>=ratios[0]*minimum and core+1e-6>=ratios[1]*minimum
 return dict(name=s['name'],equity=eq,total=total,core=core,minimum=minimum,cash=cash,invested=invested,receivable=rec,legal=legal,other_nondistributable=nondist,registered_capital=registered,statutory_reserve=statutory,statutory_add=statutory_add,general_risk_reserve=risk,general_risk_add=risk_add,profit=profit,dividend=div,topup=topup,asset_purchase=asset_purchase,cash_margin=cash_margin,shock=shock,regulatory_adjustment=-reg_drag,core_ratio=core/minimum,total_ratio=total/minimum)

def run(p,years=500):
 subs=[dict(x) for x in INIT]; rows=[]
 for j,x in enumerate(subs):
  x['registered_capital']=[8628.2,19948.08765,0.][j]
  x['statutory_reserve']=x['registered_capital']*.5*(0 if p['stress']=='reserves' else 1)
  x['general_risk_reserve']=0. # Only new restricted reserve tracked; existing included in initial nondistributable book.
 opening=holding_start(165139.,70032.,19090.,13257.,16653.,4040.5434111)
 parent_own=opening['own_equity']; parent_legal=51190.; parent_cost=70032.;parent_equity=146049.
 debt=13257.; cash=opening['cash']
 assets=opening['net_resources']; invested=opening['net_noncash']
 shares=S;legal_floor=parent_equity-parent_legal
 arrears=0.; normal=list(p['profits']); operating_scale=[1.,1.,1.]
 ratio=[(2.,1.4),(2.2,1.8),(1.,1.)]
 if p['stress']=='capital':ratio=[(2.15,1.5),(2.35,1.95),(1.,1.)]
 conversion=0.;parent_statutory=4810.1707275;parent_registered=9620.341455
 if p['stress']=='convert':
  conversion=debt;parent_own+=debt;parent_equity+=debt;legal_floor+=debt;debt=0.;shares+=15556000/36.89/1000
  reserve_add=(shares-parent_registered)*.5;parent_registered=shares;parent_statutory+=reserve_add;parent_legal-=reserve_add;legal_floor+=reserve_add
 for t in range(1,years+1):
  prev_parent_eq=parent_equity;prev_own=parent_own;prev_assets=assets;prev_cash=cash;prev_inv=invested;prev_debt=debt;prev_legal=parent_legal
  out=[]; profit_common=0.;declared=0.;topups=0.;minority_transfer=0.
  target=min(1.,.4+max(0,t-5)*.06)
  for j,s in enumerate(subs):
   g=p['growth'][j] if t<=5 else (p['growth'][j]+(p['long']-p['growth'][j])*min(1.,(t-5)/10))
   # minimum capital volume growth: profitability does not mechanically free capital.
   cg=([.035,.025,.02][j] if t<=5 else ([.035,.025,.02][j]+(p['long']-[.035,.025,.02][j])*min(1.,(t-5)/10)))
   if p['stress']=='capital':cg=.02
   if p['stress']=='fastcapital':cg=([.06,.04,.02][j] if t<=5 else ([.06,.04,.02][j]+(p['long']-[.06,.04,.02][j])*min(1.,(t-5)/10)))
   if p['stress']=='structural':cg=[.03,.02,.01][j] if t<=3 else .01
   if p['stress']=='cycle' and t<=2:factor=[.55,.6,.8][j]
   elif p['stress']=='cycle' and t==3:factor=.85
   else:factor=1.
   excess=max(0.,s['equity']-INIT[j]['equity']*operating_scale[j])
   pr=normal[j]*factor+.025*excess
   if 'roe_start' in p:
    roe=p['roe_start'][j]+(p['roe_end'][j]-p['roe_start'][j])*min(1.,(t-1)/10)
    pr=roe*s['equity']
   drag=[6000.,500.,0.][j]*(1+p['long'])**(t-1)
   if p['stress']=='structural':drag=[10000.,1000.,0.][j]*(1+p['long'])**(t-1)
   if p['stress']=='cycle' and t<=2:drag*=2
   if p['stress'] in ['capital','draghigh']:drag*=1.5
   sh=(-15000. if j==0 and t==1 and p['stress']=='structural' else 0.)
   ns=sub_step(s,pr,cg,target if j<2 else 1.,ratio[j],reserve_rate=.1 if j<2 else 0.,fixed_risk_budget=300.*(1+p['long'])**(t-1) if j==2 else 0.,delay=.10 if p['stress']=='delay' and t<=2 else .05,shock=sh,reg_drag=drag)
   # Existing signed/approved investment commitments reallocate assets, not expense.
   reallocation=([4000.,4000.,3000.,1539.,0.][t-1] if t<=5 and j==0 else 0.)
   locked=s.get('committed_illiquid_assets',0.)+reallocation
   ns['committed_asset_reallocation']=reallocation;ns['committed_illiquid_assets']=locked
   ns['remaining_commitment']=12539.-locked if j==0 else 0.
   ns['liquid_invested_assets']=ns['invested']-locked
   assert ns['liquid_invested_assets']>=-1e-6
   normal[j]*=(1+g);operating_scale[j]*=(1+g)
   out.append(ns);profit_common+=OWN[j]*(pr+sh);declared+=OWN[j]*ns['dividend'];topups+=ns['topup'];minority_transfer+=(1-OWN[j])*ns['topup']
  # Parent-funded strategy creates assets and cost basis, not a cash expense.
  strategy=[2500.,4000.,4000.,3500.,0.][t-1] if t<=5 else 0.
  out[2]['equity']+=strategy;out[2]['invested']+=strategy;out[2]['total']+=strategy;out[2]['core']+=strategy;out[2]['topup']+=strategy;out[2]['other_nondistributable']+=strategy
  topups+=strategy
  subs=out
  # Announced upstream dividends recognized once, actual receipts separately.
  new_arrears=declared*(.5 if p['stress']=='delay' and t<=2 else .05)
  receipt=declared+arrears-new_arrears
  # Parent portfolio income excludes dividends, which are internal transfers.
  inv_income=.03*prev_assets;overhead=900.*(1+p['long'])**(t-1)
  accretion=(15556*.91-13257.)/2 if t<=2 and p['stress']!='convert' else 0.
  own_profit=inv_income-overhead-accretion
  redeem=0.
  debt+=accretion
  if t==2 and debt:redeem=debt;debt=0.
  parent_profit=declared+own_profit-minority_transfer
  parent_legal+=parent_profit
  parent_cost+=topups-minority_transfer
  own_required=max(15000.*(1+p['long'])**(t-1),legal_floor-parent_cost)
  common_profit=profit_common+own_profit-minority_transfer
  wanted=min(.4*max(0.,common_profit),.9*max(0.,parent_profit)) if t<=5 else max(0.,parent_profit)+.2*max(0.,prev_own-own_required)
  # Cash and available securities both verified; repayments have priority.
  available=prev_assets+receipt+inv_income-overhead-redeem-topups-5000.
  div=max(0.,min(wanted,parent_legal,available,prev_own+parent_profit+minority_transfer-topups-own_required))
  parent_legal-=div
  parent_own+=parent_profit+minority_transfer-topups-div
  parent_equity+=parent_profit-div
  assets+=receipt+inv_income-overhead-redeem-topups-div
  cash=min(assets,5000.*(1+p['long'])**(t-1))
  asset_purchase=prev_cash+receipt+inv_income-overhead-redeem-topups-div-cash
  invested+=asset_purchase
  close(assets,cash+invested)
  close(parent_own,assets+new_arrears-debt)
  close(parent_equity,parent_own+parent_cost)
  close(parent_equity,prev_parent_eq+parent_profit-div)
  close(parent_legal,prev_legal+parent_profit-div)
  close(parent_own,prev_own+parent_profit+minority_transfer-topups-div)
  group=parent_own+sum(OWN[j]*s['equity'] for j,s in enumerate(subs))
  oldgroup=(rows[-1]['common_equity'] if rows else 330146.+conversion)
  close(group,oldgroup+common_profit-div)
  assert parent_legal>=-1e-6 and cash>=-1e-6 and invested>=-1e-6 and parent_own+1e-6*max(1,own_required)>=own_required,(p,t,parent_legal,cash,invested,parent_own,own_required)
  rows.append(dict(year=t,subsidiaries=out,parent=dict(own_equity=parent_own,equity=parent_equity,investment_cost=parent_cost,legal_capacity=parent_legal,legal_floor=legal_floor,registered_capital=parent_registered,statutory_reserve=parent_statutory,assets=assets,cash=cash,invested=invested,receivable=new_arrears,declared_upstream=declared,cash_received=receipt,own_profit=own_profit,statutory_profit=parent_profit,topups=topups,minority_transfer=minority_transfer,debt=debt,accretion=accretion,redemption=redeem,dividend=div,asset_purchase=asset_purchase,own_required=own_required),common_profit=common_profit,common_equity=group,shares=shares,dividend_per_share=div/shares))
  arrears=new_arrears
 r=p['r'];pv=sum(z['dividend_per_share']/(1+r)**z['year'] for z in rows)
 tail=sum(z['dividend_per_share']/(1+r)**(z['year']-5) for z in rows[5:])
 # Uniform policy, not a new terminal payout ratio. Verify continuing growth converges.
 growth_end=rows[-1]['dividend_per_share']/rows[-2]['dividend_per_share']-1
 assert abs(growth_end-p['long'])<1e-4,(growth_end,p['long'])
 residual_bound=rows[-1]['dividend_per_share']*(1+p['long'])/(r-p['long'])/(1+r)**years
 assert residual_bound<1e-8
 return dict(parameters=p,value_per_share=pv,year5_terminal=tail,terminal_pv_share=tail/(1+r)**5/pv,first5=[z['dividend_per_share'] for z in rows[:5]],tail_omitted_bound=residual_bound,end_growth=growth_end,annual=rows)

def auxiliary(roe=.115,r=.095,g=.02):
 """Independent consolidated residual-income steady economics; NO parent uplift.
 Capital is opening ordinary common equity, no CSM/EV separately added.
 10-year linear ROE fade to 9.5%, growth constrained by retained equity.
 """
 b=330146.;v=b;years=[]
 for t in range(1,41):
  q=roe+(0.095-roe)*min(1,(t-1)/10)
  pr=q*b;keep=g*b;dist=pr-keep;ri=pr-r*b
  v+=ri/(1+r)**t;years.append(dict(year=t,opening_equity=b,roe=q,profit=pr,retention=keep,distribution=dist,residual_income=ri,closing_equity=b+keep));b+=keep
 terminal_ri=(.095-r)*b/(r-g)
 v+=terminal_ri/(1+r)**40
 return dict(value_per_share=v/S,roe_start=roe,roe_terminal=.095,r=r,g=g,annual=years,terminal_residual_income_value=terminal_ri)

def tests():
 z=holding_start(100.,30.,20.,10.,40.,5.)
 close(z['own_equity'],50.);close(z['cash'],35.);close(z['net_noncash'],25.);close(z['net_resources'],60.)
 # Same production sub_step, exact hand case: 100 equity, 10 earned, 5 dividends.
 z=sub_step(dict(name='test',equity=100.,cash=10.,total=100.,core=100.,minimum=40.,legal=0.),10.,0.,.5,(2.,2.),reserve_rate=0.,delay=0.)
 close(z['dividend'],5.);close(z['equity'],105.);close(z['cash'],3.2);close(z['invested'],101.8)
 # Legal reserve binds: only 9 out of 10 profit available, no invented old reserve.
 z=sub_step(dict(name='test',equity=100.,cash=10.,total=100.,core=100.,minimum=40.,legal=0.),10.,0.,1.,(2.,2.),delay=0.)
 close(z['dividend'],9.);close(z['legal'],0.)
 # Actual legal branch: replenish old loss before capped statutory and general reserves.
 z=sub_step(dict(name='test',equity=100.,cash=10.,total=200.,core=200.,minimum=40.,legal=-5.,registered_capital=20.,statutory_reserve=0.),10.,0.,1.,(2.,2.),delay=0.)
 close(z['dividend'],4.);close(z['statutory_reserve'],.5);close(z['general_risk_reserve'],.5)
 # Regulatory capital deficit produces explicit top-up, not negative dividend.
 z=sub_step(dict(name='test',equity=100.,cash=10.,total=100.,core=100.,minimum=60.,legal=0.),10.,0.,.4,(2.,2.),delay=0.)
 close(z['topup'],10.);close(z['dividend'],0.)
 return True
if __name__=='__main__':
 tests();o={'unit':'CNY million unless per-share','test_status':'passed','scenarios':{k:run(v) for k,v in SCENARIOS.items()},'auxiliary':{k:auxiliary(*v) for k,v in {'low':(.105,.10,.02),'base':(.115,.095,.02),'high':(.125,.09,.02)}.items()}}
 o['opening_parent_payment_bridge']=holding_start(165139.,70032.,19090.,13257.,16653.,4040.5434111)
 o['auxiliary_owner_cash']={}
 for label,start,discount in [('low',[.16,.125,.075],.10),('base',[.17,.13,.08],.095),('high',[.18,.135,.085],.09)]:
  o['auxiliary_owner_cash'][label]=run(dict(profits=[0.,0.,0.],growth=[.03,.025,.02],long=.02,r=discount,stress='none',roe_start=start,roe_end=[.08,.10,.065]))
 base=o['scenarios']['base']['annual']
 o['holder_terminal_from_base_year5']={label:sum(z['dividend_per_share']/(1+rate)**(z['year']-5) for z in base[5:]) for label,rate in [('low',.10),('high',.09)]}
 print(json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))

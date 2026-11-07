"""603855 owner cash model. All money CNY million; shares million.
Self-contained stdlib literal inputs. Forecast legal capacities are budgets, not audited
subsidiary RE. Parent actuals are Q3; other opening allocations explicitly estimates.
No prices, market multiples, external input files or network.
"""
import copy,json,math
ASOF='2026-10-29T00:19:00+00:00'
SHARES=337.511 # Q3 actual registered; conditional 66,240 cancellation in Y1
CANCEL=.066240
TREASURY=4.310023
# P parent; L lighting; M MENA via wholly-owned ME; H Huanyu; S Saudi;
# W other wholly-owned domestic/ME businesses: modeling pool, legal cap budget only.
# cash, revenue anchor, gross working assets, operating liabilities, fixed assets,
# retained-profit budget, legal reserve budget, registered capital, bank debt,
# parent historical carrying investment, ownership, pre-bonus EBIT margin, tax
LITERALS={
 'P':[508.67277667,2850,2978.97073094,2216.99580618,493.469786,854.07963252,182.22843409,337.511,290.16997216,0,1,.153,.15],
 'L':[20,190,110,112.51992991,214.60231366,2.08238375,0,230,0,230,1,-.025,.25],
 'M':[55,260,130,149.5916,38.3443,35,5,7,8.0057639,0,.51,.155,.15],
 'H':[10,60,35,22,15,-10,0,12,0,31.11077002,.9,-.03,.15],
 'S':[5,15,12,8,10,-2,0,2,0,7.253016,.51,-.10,.20],
 'W':[51.73384787,110,55,40,35,20,0,50,0,63.14019863,1,.09,.20]
}
# W is mixed wholly-owned operations: its 10% buffer is a forecast covenant budget,
# not a claim that China reserve law applies to overseas W assets.
# M's registration 7m is RMB-equivalent budget, NOT the contradictory filed
# AED100k vs USD1m exact legal amount. No Chinese statutory reserve applied abroad.
SCENARIOS={
 'base':dict(g=.05,margin=0,bonus=.07,delay=0,fee_release=0,cap=.035,loan_years=3,overseas_delay=1,exit_l=0,exit_h=0,invest_hair=.75),
 'core_low':dict(g=.04,margin=-.005,bonus=.09,delay=.01,fee_release=.015,cap=.037,loan_years=3,overseas_delay=2,exit_l=0,exit_h=0,invest_hair=.65),
 'core_high':dict(g=.06,margin=.003,bonus=.05,delay=0,fee_release=0,cap=.033,loan_years=3,overseas_delay=1,exit_l=0,exit_h=0,invest_hair=.85),
 'cycle':dict(g=.045,margin=0,bonus=.07,delay=.06,fee_release=.04,cap=.035,loan_years=3,overseas_delay=3,exit_l=0,exit_h=0,invest_hair=.65),
 'damage':dict(g=.0,margin=-.045,bonus=.03,delay=.12,fee_release=.10,cap=.035,loan_years=2,overseas_delay=4,exit_l=3,exit_h=3,invest_hair=.3),
 'optimistic':dict(g=.085,margin=.008,bonus=.07,delay=0,fee_release=0,cap=.04,loan_years=3,overseas_delay=1,exit_l=0,exit_h=0,invest_hair=1),
 'bonus_max':dict(g=.05,margin=0,bonus=.15,delay=0,fee_release=0,cap=.035,loan_years=3,overseas_delay=1,exit_l=0,exit_h=0,invest_hair=.75),
 'bonus_zero':dict(g=.05,margin=0,bonus=0,delay=0,fee_release=0,cap=.035,loan_years=3,overseas_delay=1,exit_l=0,exit_h=0,invest_hair=.75),
 'no_rollover':dict(g=.05,margin=0,bonus=.07,delay=0,fee_release=0,cap=.035,loan_years=1,overseas_delay=1,exit_l=0,exit_h=0,invest_hair=.75),
 'collection_delay':dict(g=.05,margin=0,bonus=.07,delay=.10,fee_release=.05,cap=.035,loan_years=3,overseas_delay=3,exit_l=0,exit_h=0,invest_hair=.75),
 'subs_no_legacy_profit':dict(g=.05,margin=0,bonus=.07,delay=0,fee_release=0,cap=.035,loan_years=3,overseas_delay=5,exit_l=0,exit_h=0,invest_hair=.75)
}
SCENARIOS['no_extra_support']=dict(SCENARIOS['base'],internal_limit=0)
SCENARIOS['credit_cost']=dict(SCENARIOS['base'],bank_rate=.06)
def opening():
 st={}
 for name,a in LITERALS.items():
  c,r,wa,wl,fa,re,res,capital,debt,inv,own,margin,tax=a
  st[name]=dict(cash=c,revenue=r,wa=wa,wl=wl,fa=fa,re=re,reserve=res,capital=capital,debt=debt,investment=inv,ownership=own,margin=margin,tax=tax,loan=18.37126906 if name=='H' else 0.,loan_receivable=18.37126906 if name=='P' else 0.,dividend_payable=0.,dividend_receivable=0.,tax_loss=0.,closed=False,defaulted=False,loan_loss_allowance=0.,unpaid_creditors=0.,additional_loan_drawn=0.,sbc_capital=0.,treasury_cost=79.95217983 if name=='P' else 0.)
 # Existing consolidated declared dividends belong to non-parent claims;
 # reserve genuine cash, not a newly recognized parent dividend.
 st['M']['dividend_payable']=6.4084208
 # Huanyu loan principal observed FY25; Q3 allocation uncertainty tested in notes.
 st['P']['financial_investment']=171.10834151
 st['P']['other_liability']=19.999
 st['P']['refund_due']=.56304
 # Capped owner-approved forecast support: initial actual cash not assumed larger.
 # Book a 20m parent-to-lighting loan, repaid before any dividends.
 st['P']['cash']-=20.;st['P']['loan_receivable']+=20.;st['L']['cash']+=20.;st['L']['loan']=20.
 return st

def settle_declared(st):
 paid={};p=st['P']
 for n,s in st.items():
  if n=='P':continue
  cash=min(s['cash'],s['dividend_payable']);s['cash']-=cash;s['dividend_payable']-=cash
  due_parent=min(p['dividend_receivable'],cash*s['ownership'])
  p['cash']+=due_parent;p['dividend_receivable']-=due_parent
  paid[n]=dict(paid=cash,parent_received=due_parent,nci_received=cash-due_parent)
 return paid

def reserve(s,n,profit):
 # Losses first. Domestic actual parent reserve above 50%; other domestic budgets.
 covered=max(0,min(profit,-min(0,s['re'])))
 elig=max(0,profit-covered)
 take=min(elig*.1,max(0,s['capital']*.5-s['reserve'])) if n in ('P','L','H','W') else 0.
 s['reserve']+=take;s['re']+=profit-take
 return take

def liquidate(s,hair=.65):
 # All current operating liabilities paid before equity; unpaid debt survives.
 opening_cash=s['cash'];recover=s['wa']*.75+s['fa']*hair
 costs=15 if s['capital']>100 else 5
 pool=opening_cash+recover
 priority=s['wl']+costs+s['debt']+s['dividend_payable']+s['unpaid_creditors']
 pay=min(pool,priority);unpaid=priority-pay;pool-=pay
 internal=min(pool,s['loan']);s['loan']-=internal;pool-=internal
 equity=max(0,pool)
 loss=s['wa']+s['fa']-recover+costs
 s['re']-=loss;s['cash']=0;s['wa']=0;s['fa']=0;s['wl']=0;s['debt']=0;s['dividend_payable']=0
 s['unpaid_creditors']=unpaid;s['closed']=True
 return dict(opening_cash=opening_cash,asset_recovery=recover,exit_cost=costs,external_due=priority,external_paid=pay,external_unpaid=unpaid,internal_paid=internal,internal_unpaid=s['loan'],equity_distribution=equity,accounting_exit_loss=loss)

def step(st,year,params,tail_margin=0,earnings_power=False):
 st=copy.deepcopy(st);p=st['P'];start_cash=sum(s['cash']for s in st.values());declared=settle_declared(st)
 audit={};inflows=0.;nci=0.;newdecl=0.;internal_income=0.;parent_investment_loss=0.;funding_gap=0.
 # legacy financial assets recover in Y8, not at horizon; no pre-booked interest value.
 investment_recovery=0.;investment_loss=0.
 if year==8:
  investment_recovery=p['financial_investment']*params['invest_hair'];investment_loss=p['financial_investment']-investment_recovery
  p['cash']+=investment_recovery;p['financial_investment']=0.;p['re']-=investment_loss
 if year==1:
  p['capital']-=CANCEL # conditional completion budget, not an observed opening reduction
  # Incremental conditional FY2026 pre-cutoff catch-up: 278m earned x bonus.
  catchup=(278.01591211+35)*params['bonus']
  paid=min(p['cash'],p['other_liability']+p['refund_due']);p['cash']-=paid;p['other_liability']=max(0,p['other_liability']+p['refund_due']-paid);p['refund_due']=0
 else:paid=0.;catchup=0.
 for n in ['L','M','H','S','W','P']:
  s=st[n];o=copy.deepcopy(s)
  if s['closed']:
   audit[n]={'closed':True,'state':copy.deepcopy(s)};continue
  if (n=='L' and year==params['exit_l'])or(n=='H'and year==params['exit_h'])or (n!='P' and s['defaulted']):
   x=liquidate(s);rec=x['equity_distribution']*s['ownership'];nci+=x['equity_distribution']-rec
   p['cash']+=rec+x['internal_paid'];p['loan_receivable']-=x['internal_paid'];cost=s['investment'];s['investment']=0.
   parent_investment_loss+=cost-rec
   # parent loss includes unpaid intercompany principal, retained as claim in both states.
   if x['internal_unpaid']:
    parent_investment_loss+=x['internal_unpaid'];p['loan_loss_allowance']+=x['internal_unpaid']
   audit[n]={'exit':x,'parent_historical_cost':cost,'parent_equity_recovery':rec,'state':copy.deepcopy(s)};continue
  g=params['g'] if year<=5 else params['g']*max(0,(15-year)/10)
  if n in ('L','H','S'):g=min(g,.03)
  if earnings_power:g=0. # independent revenue/earnings-power economic hypothesis
  rev=s['revenue']*(1+g)
  if params is SCENARIOS.get('cycle') and year in (1,2):rev=s['revenue']*(.90 if year==1 else 1.0)
  if params is SCENARIOS.get('cycle') and year==3:rev=s['revenue']*1.15
  if params is SCENARIOS.get('damage')and year<=3:rev=s['revenue']*.92
  margin=s['margin']+params['margin']+(tail_margin if year>5 else 0)
  if n=='L':margin=max(-.025,min(.025,-.025+.01*(year-1)))+params['margin']
  if n=='H':margin=min(.04,-.03+.015*(year-1))+params['margin']
  if n=='S':margin=min(.07,-.10+.04*(year-1))+params['margin']
  if params is SCENARIOS.get('cycle') and year<=2:margin-=.02
  if earnings_power:
   # Alternative uses mature revenue * net operating earnings, zero future growth.
   margin={'P':.145,'L':.005,'M':.14,'H':.015,'S':.025,'W':.07}[n]+params['margin']
  # Explicit recurring credit cost is embedded in above margin, no gain from releases.
  incremental_sbc=79.95217983/2 if n=='P' and year<=2 else 0.
  ebit=rev*margin-incremental_sbc
  if earnings_power:
   # Independent entry: historical adjusted attributable earnings, not forecast sales margin.
   historical=[305.127,357.857,452.590,448.143,353.854]
   normalized=(sorted(historical)[2]-24.) if params['margin']<0 else sum(historical)/5
   weight={'P':.86,'L':.003,'M':.075,'H':.003,'S':.001,'W':.058}[n]
   # Normalized parent earnings -> gross entity EBIT: ownership, tax and legacy interest bridge.
   ebit=normalized*weight/s['ownership']/(1-s['tax'])+LITERALS[n][8]*.035-incremental_sbc
  # 2026 scheme is conditional through 2028 only. Rolling Y1/Y2 full; Y3 2/12.
  # Thereafter recurring incentives replace the scheme economically, separately labeled.
  scheme_weight=1. if year<=2 else (2/12 if year==3 else 0.)
  reward_rate=params['bonus']*scheme_weight+.03*(1-scheme_weight)
  interest=s['debt']*params.get('bank_rate',.035)
  internal_interest=s['loan']*.035
  bonus=max(0,ebit-interest)*(1-s['tax'])*reward_rate
  if n=='P':bonus+=catchup
  if n!='P':
   interest+=internal_interest;s['loan']+=internal_interest;p['loan_receivable']+=internal_interest;internal_income+=internal_interest
  pretax=ebit-bonus-interest
  taxable=max(0,pretax+incremental_sbc);s['tax_loss']+=max(0,-pretax) # no assumed tax refunds or unverified carryforward benefit
  tax=taxable*s['tax'];np=pretax-tax
  da=rev*.025 if n=='P'else rev*.03
  # Asset expansion uses positive growth and fades; upkeep cannot vanish in terminal.
  capex=da+rev*max(0,g)*(params['cap']/.05)
  delay=params['delay']*max(0,(5-year)/4) if params['exit_l']==0 else params['delay']
  feeshift=params['fee_release']*min(year/3,1)
  ar_ratio=LITERALS[n][2]/LITERALS[n][1]
  payable_ratio=LITERALS[n][3]/LITERALS[n][1]
  wa=rev*(ar_ratio+delay);wl=rev*max(0,payable_ratio-feeshift)
  dwc=(wa-wl)-(s['wa']-s['wl']);s['wa']=wa;s['wl']=wl;s['fa']+=capex-da;s['revenue']=rev
  # SBC actual old grant costs largely amortized; future reward modeled cash.
  # Treasury reused Y2 as zero-price employee allocation, no second labor charge:
  # 79.952m past cash is sunk; reclassification only; recurring compensation stays.
  sbc=incremental_sbc;s['sbc_capital']+=sbc
  s['cash']+=np+da-capex-dwc+sbc+(internal_interest if n!='P' else 0.)
  # Forecast internal bridge capped at 60m additional principal, not limitless refinancing.
  if n!='P' and s['cash']<0:
   need=-s['cash'];used=sum(v['additional_loan_drawn']for v in st.values());advance=min(need,max(0,params.get('internal_limit',60)-used),max(0,p['cash']-180))
   s['cash']+=advance;s['loan']+=advance;s['additional_loan_drawn']+=advance;p['cash']-=advance;p['loan_receivable']+=advance
  reserve_taken=reserve(s,n,np)
  repay=min(s['debt'],LITERALS[n][8]/params['loan_years']) if year<=params['loan_years'] else s['debt']
  # Limited normal rollover: no new net draw, outstanding scheduled debt tracked.
  actual_repay=min(repay,max(0,s['cash']));s['debt']-=actual_repay;s['cash']-=actual_repay
  arrears=repay-actual_repay;# Scheduled arrears stay in bank debt, not duplicated as other debt.
  funding_gap+=arrears
  # Avoid negative cash; failed operations leave a real payable claim, not magic loan.
  short=max(0,-s['cash']);s['cash']=max(0,s['cash']);s['unpaid_creditors']+=short;funding_gap+=short
  # Residual cash deficit is specifically current cash operating/service costs left unpaid.
  # Failure of capped funding or scheduled bank payment triggers next-year cessation budget.
  s['defaulted']=short+arrears>1e-6
  assert not (n=='P' and s['defaulted']), 'Parent default requires whole-group insolvency branch, no going-concern value'
  unpaid_paid=min(s['unpaid_creditors'],s['cash']);s['cash']-=unpaid_paid;s['unpaid_creditors']-=unpaid_paid
  if n=='P':
   reserve(s,n,newdecl+internal_income*.85-parent_investment_loss);p['cash']-=internal_income*.15
   if year==2:p['sbc_capital']-=p['treasury_cost'];p['treasury_cost']=0.
  else:
   # Loan recovery ahead of new dividends, no compulsory unlimited parent financing.
   lr=min(s['loan'],max(0,s['cash']-rev*.10));s['loan']-=lr;s['cash']-=lr;p['cash']+=lr;p['loan_receivable']-=lr
   # Overseas distributability is a budget with local accounts/consent condition.
   wait=params['overseas_delay'] if n in ('M','S','W') else 1
   if params is SCENARIOS.get('subs_no_legacy_profit')and year==1:s['re']=min(0,s['re'])
   capacity=max(0,s['re'])
   budget=max(0,s['cash']-rev*.10-s['unpaid_creditors'])
   d=min(capacity,budget) if year>wait else 0.
   if s['loan']>1e-8:d=0.
   s['re']-=d;s['dividend_payable']+=d
   parent_share=d*s['ownership'];newdecl+=parent_share;p['dividend_receivable']+=parent_share
   # Cash-backed declaration is escrowed; cash remains until next year settlement.
  audit[n]=dict(sbc_expense=sbc,sbc_cash_addback=sbc,internal_interest=internal_interest,unpaid_paid=unpaid_paid,shortfall_payable_created=short,revenue=rev,ebit=ebit,bonus=bonus,pretax=pretax,tax=tax,np=np,da=da,capex=capex,dwc=dwc,interest=interest,scheduled_repay=repay,actual_repay=actual_repay,funding_gap=short+arrears,reserve_taken=reserve_taken,state=copy.deepcopy(s))
 # P state profit adds legally declared sub income ONCE; receipts do not create RE.
 p=st['P'];floor=p['revenue']*.065
 # Y1-5 pay 65% of positive own earnings plus received dividends, constrained by cash/RE.
 received=sum(x['parent_received']for x in declared.values())
 target=(max(0,audit['P'].get('np',0))*.65+received) if year<=5 else max(0,p['cash']-floor)
 d=min(target,max(0,p['re']),max(0,p['cash']-floor-p['unpaid_creditors']))
 p['cash']-=d;p['re']-=d
 for n,s in st.items():
  assert s['cash']>=-1e-7 and s['dividend_payable']<=s['cash']+1e-7,(n,year,'unbacked')
  assert s['loan']>=-1e-7
  if n in ('P','L','H','W'):assert s['reserve']>=0
 shares=SHARES-CANCEL-TREASURY if year==1 else SHARES-CANCEL
 # Independent balance-of-cash assertion: build from external movements, not state delta.
 expected=start_cash-sum(x['nci_received']for x in declared.values())+investment_recovery-paid-internal_income*.15-d
 for n,a in audit.items():
  if 'exit' in a:
   x=a['exit'];expected+=-x['opening_cash']+a['parent_equity_recovery']+x['internal_paid']
  elif 'np' in a:
   expected+=a['np']+a['da']-a['capex']-a['dwc']+a['sbc_cash_addback']+(a['internal_interest']if n!='P'else 0)-a['actual_repay']+a['shortfall_payable_created']-a['unpaid_paid']
 assert abs(expected-sum(s['cash']for s in st.values()))<1e-6,(year,expected,sum(s['cash']for s in st.values()))
 # record full state after all parent and subsidiary transfers (audit earlier may precede parent)
 for a in audit.values():a.pop('state',None) # one complete post-settlement state per year; no duplicate intermediate copies
 return st,dict(year=year,shares=shares,distribution=d,distribution_per_share=d/shares,entities=audit,state=copy.deepcopy(st),old_dividends_settled=declared,new_parent_dividend_income=newdecl,parent_investment_loss=parent_investment_loss,financial_recovery=investment_recovery,financial_loss=investment_loss,legacy_cash_payment=paid,nci_liquidation=nci,initial_group_cash=start_cash,final_group_cash=sum(s['cash']for s in st.values()),cash_conservation_residual=expected-sum(s['cash']for s in st.values()),funding_gap=funding_gap)

def run(params,years=1200,initial=None,start=1,tail_margin=0,earnings_power=False):
 st=opening()if initial is None else copy.deepcopy(initial);rows=[]
 for y in range(start,years+1):st,r=step(st,y,params,tail_margin,earnings_power);rows.append(r)
 return st,rows

def pv(rows,k,at=0):return sum(r['distribution_per_share']/(1+k)**(r['year']-at)for r in rows)
def norm_state(st):
 # RE/tax-loss may be affine in permanently weak business; no tail capitalizes it.
 return {n:{k:v for k,v in s.items()if k not in ('re','tax_loss','unpaid_creditors')}for n,s in st.items()}
def tail_check(rows):
 a,b,c=rows[-3:];diff1={};diff2={}
 for n in b['state']:
  for key,val in b['state'][n].items():
   if isinstance(val,(float,int))and not isinstance(val,bool):
    diff1[n+'.'+key]=val-a['state'][n][key];diff2[n+'.'+key]=c['state'][n][key]-val
 err=max(abs(diff1[k]-diff2[k])for k in diff1)
 # Check every field's second difference and distribution drift. Affine tail permitted
 # only when operating, cash, debt, liabilities are stable and no funding deficit.
 stable=max(abs(c['state'][n][k]-b['state'][n][k])for n in b['state']for k in ['cash','revenue','wa','wl','fa','debt','loan','dividend_receivable','dividend_payable'])
 return dict(full_state_affine_residual=err,economic_state_stationarity_residual=stable,distribution_drift=c['distribution_per_share']-b['distribution_per_share'],state_drift=diff2,eligible=max(abs(v)for v in diff2.values())<1e-7 and err<1e-7 and stable<1e-7 and c['funding_gap']<1e-8 and max(s['unpaid_creditors']for s in c['state'].values())<1e-8)
def valued(rows,k,at=0):
 check=tail_check(rows);tail=rows[-1]['distribution_per_share']/k/(1+k)**(rows[-1]['year']-at)if check['eligible']else None
 failed=any(r['funding_gap']>1e-6 for r in rows)
 return dict(value=None if tail is None or failed else pv(rows,k,at)+tail,explicit_pv=pv(rows,k,at),residual_pv=tail,terminal_check=check)
def main():
 allout={};
 for name,par in SCENARIOS.items():
  st,rows=run(par);v=valued(rows,.105)
  allout[name]=dict(parameters=par,annual=rows,valuation=v,infeasible=any(r['funding_gap']>1e-6 for r in rows))
 # Y5 alternatives branch off SAME base Y5 full state, not re-run low/high prefixes.
 base5=allout['base']['annual'][4]['state'];tails={}
 for side,k,m in [('low',.115,-.005),('high',.095,.003)]:
  st,rr=run(SCENARIOS['base'],initial=base5,start=6,tail_margin=m)
  tails[side]=dict(discount=k,annual=rr,valuation_at_year5=valued(rr,k,5))
 auxiliary={}
 for side,k,margin in [('low',.115,-.005),('high',.095,.003)]:
  par=copy.deepcopy(SCENARIOS['base']);par['margin']=margin
  _,rr=run(par,earnings_power=True)
  auxiliary[side]=dict(annual=rr,valuation=valued(rr,k))
 # additional longer horizon is ACTUAL extended run; all-state residual PV compared.
 extended={}
 for name,par in SCENARIOS.items():
  _,rr=run(par,years=2400);extended[name]=dict(annual=rr,valuation=valued(rr,.105))
 for side,k,m in [('low',.115,-.005),('high',.095,.003)]:
  _,rr=run(SCENARIOS['base'],years=2400,initial=base5,start=6,tail_margin=m)
  extended['y5_'+side]=dict(annual=rr,valuation=valued(rr,k,5))
  par=copy.deepcopy(SCENARIOS['base']);par['margin']=m
  _,rr=run(par,years=2400,earnings_power=True)
  extended['aux_'+side]=dict(annual=rr,valuation=valued(rr,k))
 checks={'base_h1200_vs_h2400':abs(extended['base']['valuation']['value']-allout['base']['valuation']['value']),'extended_all_paths':extended,'same_base_y5':base5}
 # Call production engine in hand-checkable zero business special case.
 zero=opening()
 for s in zero.values():
  for key in ['revenue','wa','wl','fa','cash','debt','loan','loan_receivable','dividend_receivable','dividend_payable','unpaid_creditors']:s[key]=0.
  s['re']=0.;s['margin']=0.
 zero['P']['cash']=100.;zero['P']['re']=100.;zero['P']['financial_investment']=0.;zero['P']['other_liability']=0.;zero['P']['refund_due']=0.
 _,z=step(zero,6,SCENARIOS['base']);assert abs(z['distribution']-100)<1e-9
 checks['same_engine_zero_business_cash100_distribution']=z
 return dict(symbol='CN:603855',information_cutoff=ASOF,unit='CNY million; shares million',core_value={'low':valued(allout['core_low']['annual'],.115)['value'],'high':valued(allout['core_high']['annual'],.095)['value']},holder_distributions=[r['distribution_per_share']for r in allout['base']['annual'][:5]],holder_terminal={s:tails[s]['valuation_at_year5']['value']for s in tails},scenarios=allout,y5_branches=tails,auxiliary_earnings_power=auxiliary,tests=checks)
if __name__=='__main__':print(json.dumps(main(),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))

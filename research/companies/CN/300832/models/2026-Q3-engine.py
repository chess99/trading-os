#!/usr/bin/env python3
"""新产业2026Q3重建新快照；仅标准库、内嵌输入、stdout完整JSON。金额十亿元，股数十亿。"""
import json,copy
ASOF='2026-10-27T21:05:00+00:00'
F=dict(sales25=4.57675948311,sales9m26=3.70066084295,sales9m25=3.42761963756,cash=1.30048744846,restricted=.00009959529,trading=1.43891959046,due1=1.53941028660,customer_due1=.26369097642,bonds=.90353396601,private_equity_fvpl=.05699861502,equity_investments=.12094390894,parent_equity=.0955516,lease=.00262547296,shares=.785718785,treasury=.20003659462,treasury_shares=.004147588,awards=.004138)
D=dict(g=[.08,.08,.07,.06,.05,.045,.04,.035,.03,.025],m=[.35]*5+[.348,.346,.344,.342,.34],k=[.07]*10,w=[.42]*10,da=.047,floor=.12,payout=.6,release=.2,r=.095,g_inf=.02,roic=.16,drag=0.,fy=.015,recovery=.85,sale=5,sub=[.03]*10,maturity=[.5,.3,.2]+[0.]*7,
 rev=F['sales25']+F['sales9m26']-F['sales9m25'],cash=F['cash']-F['restricted']-.13,financial=F['trading']+F['due1']-F['customer_due1']+F['bonds'],opcap=5.016,subcash=.13,sub_loss=.08,wc_ratio=.42,wc_extra=0.,retained=6.57634543043,reserve=.3928593925,registered=.785718785,capreserve=1.33837574584,group_equity=9.39975995561,p_eq=.0955516,s_eq=.12094390894-.0955516,oci=.06175114,shares=.785718785,credit=.85,loanrate=.045,lease=.00262547296,treasury=.20003659462,award_cash=.004138*35,award_cost=.20003659462*.004138/.004147588,project=.482181598*.8547+.0575*.9,project_weights=[.3,.35,.35]+[0.]*7,maintenance=.04,private_equity=.05699861502,private_recovery=.75,private_sale=6,private_income=0.,treasury_shares=.004147588,award_shares=.004138,award_total_expense=.0485801,recognized_sbc=.00599457185,personal_ratio=1.,cancel_year=3,calendar_override=None)
def cfg(**kw):
 d=copy.deepcopy(D);d.update(kw);return d

def incentive(d):
 # Calendar budgets, not reported actuals: Q4 seasonality from FY2025; CY2027 overlapping rolling years.
 y1=d['rev']*(1+d['g'][0]);y2=y1*(1+d['g'][1])
 cy26=3.70066084295+(4.57675948311-3.42761963756)*y1/4.57675948311
 cy27=.75*y1+.25*y2
 if d['calendar_override'] is not None:cy26,cy27=d['calendar_override']
 def ratio(sales,trigger,full):
  g=sales/4.57675948311-1
  return 0. if g+1e-12<trigger else min(1.,max(.8,.8+.2*(g-trigger)/(full-trigger)))
 ratios=[ratio(cy26,.10,.15)*d['personal_ratio'],ratio(cy27,.21,.3225)*d['personal_ratio']]
 tranche=[d['award_total_expense']*.5*x for x in ratios]
 expense=[tranche[0]+.75*tranche[1]-d['recognized_sbc'],.25*tranche[1]]+[0.]*8
 return dict(calendar_2026_sales=cy26,calendar_2027_sales=cy27,tranche_vesting_ratios=ratios,vest=[.5*x for x in ratios]+[0.]*8,expense=expense)

def simulate(d):
 inc=incentive(d)
 rev=d['rev'];wc=rev*d['wc_ratio']+d['wc_extra'];cash=d['cash'];fin=d['financial'];opcap=d['opcap'];book=d['group_equity'];re=d['retained'];reserve=d['reserve'];capres=d['capreserve'];subre=-d['sub_loss'];sc=d['subcash'];loan=0.;treasury=d['treasury'];project=d['project'];peq=d['p_eq'];seq=d['s_eq'];private=d['private_equity'];shares=d['shares'];registered=d['registered'];stockshares=d['treasury_shares'];initial_eligible=shares-stockshares;rows=[]
 for i in range(10):
  y=i+1;oldcash=cash;oldwc=wc;oldsc=sc;oldre=re;oldbook=book;oldloan=loan;oldtreasury=treasury;oldcapres=capres
  rev*=1+d['g'][i];sbc=inc['expense'][i];nopat=rev*d['m'][i]-sbc;da=rev*d['da'];pc=d['project']*d['project_weights'][i];project-=pc;maint=rev*d['maintenance'];capex=max(rev*d['k'][i],pc+maint);growthcapex=capex-pc-maint
  wc=rev*d['w'][i];dwc=wc-oldwc;opcap+=capex-da+dwc
  private_income=private*d['private_income'];income=(max(cash,0)+fin)*d['fy']+private_income;li=loan*d['loanrate'];redeem=d['financial']*d['maturity'][i];fin-=redeem
  ps=peq*d['recovery'] if y==d['sale'] else 0.;ss=seq*d['recovery'] if y==d['sale'] else 0.;pl=ps-peq if y==d['sale'] else 0.;sl=ss-seq if y==d['sale'] else 0.;oci=d['oci'] if y==d['sale'] else 0.
  if y==d['sale']:peq=seq=0.
  private_sale=private*d['private_recovery'] if y==d['private_sale'] else 0.;private_loss=private_sale-private if y==d['private_sale'] else 0.
  if y==d['private_sale']:private=0.
  ps+=private_sale;pl+=private_loss
  subprofit=-d['sub'][i]+sl;subre+=subprofit;support=max(0.,d['subcash']-(sc+ss-d['sub'][i]));sc+=ss-d['sub'][i]+support
  pp=nopat+d['sub'][i]+income-li+pl;gp=nopat+income-li+pl+sl;fcfe=nopat+da+sbc-capex-dwc
  vest=inc['vest'][i];grant=d['award_cash']*vest;cost=d['award_cost']*vest;vestshares=d['award_shares']*vest;stockshares-=vestshares;treasury-=cost;capres+=grant+sbc-cost
  cancelled=stockshares if y==d['cancel_year'] else 0.;cancelcost=treasury if y==d['cancel_year'] else 0.
  if cancelled:
   shares-=cancelled;registered-=cancelled;capres-=cancelcost-cancelled;treasury=0.;stockshares=0.
  eligible=shares-stockshares
  lease=d['lease'] if y==1 else 0.
  cash+=fcfe+d['sub'][i]+income-li+redeem+ps-support+grant-lease
  reserve_add=min(max(0.,.5*registered-reserve),.1*max(0.,pp+min(0.,re)));reserve+=reserve_add;re+=pp-reserve_add+oci
  floor=rev*d['floor'];borrow=min(max(0.,floor-cash),max(0.,d['credit']-loan));loan+=borrow;cash+=borrow;feasible=cash>=floor-1e-8
  repay=min(loan,max(0.,cash-floor));loan-=repay;cash-=repay
  target=max(0.,gp)*d['payout'] if y<=5 else fcfe+income-li+max(0.,cash-floor-fcfe-income+li)*d['release']
  div=min(max(0.,target),max(0.,re),max(0.,cash-floor));cash-=div;re-=div;book+=gp+grant+sbc-div
  casherr=cash-(oldcash+fcfe+d['sub'][i]+income-li+redeem+ps-support+grant-lease+borrow-repay-div)
  grouperr=cash+sc-(oldcash+oldsc+fcfe+income-li+redeem+ps+ss+grant-lease+borrow-repay-div)
  equityerr=book-oldbook-gp-grant-sbc+div
  stockerr=(capres-oldcapres)-(treasury-oldtreasury)-grant-sbc-cancelled
  assert max(abs(casherr),abs(grouperr),abs(equityerr),abs(stockerr))<1e-8
  assert min(cash,treasury,fin,project,growthcapex)>=-1e-8 and div<=max(0.,oldre+pp-reserve_add+oci)+1e-8
  rows.append(dict(year=y,revenue=rev,nopat=nopat,depreciation=da,capex=capex,construction_capex=pc,construction_remaining=project,maintenance_capex=maint,other_growth_capex=growthcapex,working_capital=wc,change_working_capital=dwc,operating_capital=opcap,operating_fcfe=fcfe,parent_profit=pp,subsidiary_profit=subprofit,group_profit=gp,share_based_payment_expense=sbc,financial_income=income,financial_principal_redeemed=redeem,financial_principal_end=fin,parent_equity_sale=ps,subsidiary_equity_sale=ss,parent_cash_begin=oldcash,parent_cash_end=cash,subsidiary_cash_end=sc,subsidiary_support=support,subsidiary_upstream_dividend=0.,subsidiary_accumulated_profit=subre,parent_legal_profit_begin=oldre,parent_legal_profit_end=re,statutory_reserve_add=reserve_add,statutory_reserve_end=reserve,capital_reserve_end=capres,treasury_stock_begin=oldtreasury,treasury_stock_cost_released=cost,treasury_stock_end=treasury,oci_to_legal_profit=oci,award_cash=grant,loan_begin=oldloan,loan_borrowed=borrow,loan_repaid=repay,loan_end=loan,loan_interest=li,lease_cash=lease,cash_floor=floor,dividend=div,dividend_per_share=div/eligible,issued_shares_end=shares,eligible_shares=eligible,treasury_shares_end=stockshares,vested_shares=vestshares,cancelled_shares=cancelled,cancelled_treasury_cost=cancelcost,registered_capital_end=registered,private_equity_sale=private_sale,private_equity_loss=private_loss,private_equity_end=private,group_equity_begin=oldbook,group_equity_end=book,feasible=feasible,parent_cash_conservation_error=casherr,group_cash_conservation_error=grouperr,equity_conservation_error=equityerr,treasury_capital_bridge_error=stockerr))
 r=d['r'];g=d['g_inf'];n11=rev*(1+g)*d['m'][-1];invest=n11*g/d['roic']+rev*(1+g)*d['drag'];terminal_op=(n11-invest)/(r-g);residual=max(0.,cash-rev*(1+g)*d['floor']-loan)
 assert residual<=max(0.,re+n11)+1e-8 and abs(fin)+abs(peq)+abs(seq)+abs(private)<1e-8
 terminal=terminal_op+residual/(1+r);pv=sum(z['dividend']/(1+r)**z['year'] for z in rows);tvpv=terminal/(1+r)**10;value=pv+tvpv;v5=sum(z['dividend']/(1+r)**(z['year']-5) for z in rows[5:])+terminal/(1+r)**5
 assert abs(value-sum(z['dividend']/(1+r)**z['year'] for z in rows[:5])-v5/(1+r)**5)<1e-8
 pervalue=sum(z['dividend_per_share']/(1+r)**z['year'] for z in rows)+terminal/eligible/(1+r)**10
 per5=sum(z['dividend_per_share']/(1+r)**(z['year']-5) for z in rows[5:])+terminal/eligible/(1+r)**5
 dc=rows[4]['operating_capital']-rows[0]['operating_capital']
 return dict(inputs=d,incentive=inc,years=rows,current_equity_value=pervalue*initial_eligible,current_value_per_share=pervalue,year5_equity_value=per5*rows[4]['eligible_shares'],year5_terminal_per_share=per5,year10_operating_terminal=terminal_op,year11_nopat=n11,year11_necessary_reinvestment=invest,year11_steady_fcfe=n11-invest,year11_residual_cash_distribution=residual,year10_terminal_total=terminal,explicit_dividends_pv=sum(z['dividend_per_share']/(1+r)**z['year'] for z in rows)*initial_eligible,terminal_pv=terminal/eligible/(1+r)**10*initial_eligible,terminal_pv_share=(terminal/eligible/(1+r)**10)/pervalue,incremental_roic_year1_to5=(rows[4]['nopat']-rows[0]['nopat'])/dc if dc else None,all_years_feasible=all(z['feasible'] for z in rows))
def hand():
 d=cfg(rev=100.,g=[0.]*10,m=[.2]*10,k=[0.]*10,w=[0.]*10,da=0.,floor=0.,wc_ratio=0.,payout=.5,release=1.,r=.1,g_inf=0.,fy=0.,cash=0.,financial=0.,p_eq=0.,s_eq=0.,subcash=0.,sub=[0.]*10,sub_loss=0.,oci=0.,retained=1000.,registered=0.,reserve=0.,capreserve=0.,group_equity=100.,opcap=100.,shares=1.,award_cash=0.,award_cost=0.,treasury=0.,project=0.,maintenance=0.,lease=0.,private_equity=0.,treasury_shares=0.,award_shares=0.,award_total_expense=0.,recognized_sbc=0.)
 z=simulate(d);expected=sum(10/1.1**t for t in range(1,6))+70/1.1**6+sum(20/1.1**t for t in range(7,11))+200/1.1**10
 assert abs(z['current_equity_value']-expected)<1e-9
 d.update(retained=-25.,registered=10.,m=[.2]*9+[.5]);q=simulate(d);assert q['years'][0]['dividend']==0 and q['years'][0]['statutory_reserve_add']==0 and abs(q['years'][1]['statutory_reserve_add']-1.5)<1e-9
 return dict(passed=True,production=z['current_equity_value'],manual=expected,year6_dividend=z['years'][5]['dividend'],loss_case_y2_reserve=q['years'][1]['statutory_reserve_add'])
def main():
 paths=dict(base=cfg(),core_low=cfg(r=.1,g_inf=.015,roic=.14),core_high=cfg(r=.09,g_inf=.02,roic=.18),cyclical=cfg(g=[-.05,0.,.1,.1,.07,.05,.04,.035,.03,.025],m=[.29,.30,.33,.35,.35,.348,.346,.344,.342,.34],w=[.48,.48,.45,.43]+[.42]*6,sub=[.05,.05,.04]+[.03]*7),structural=cfg(g=[-.1,-.05,0.,.01,.01,.01,.01,0.,0.,0.],m=[.29,.27]+[.25]*8,w=[.52]*10,k=[.08]*10,g_inf=0.,roic=.08,drag=.033,r=.105,sub=[.06]*10),upside=cfg(g=[.12,.12,.10,.09,.08,.06,.05,.04,.035,.03],m=[.36,.36,.365,.365,.365,.36,.355,.35,.345,.34],k=[.08]*5+[.07]*5,w=[.40]*10,g_inf=.025,roic=.18,r=.09),sensitivity_margin_minus_2pp=cfg(m=[x-.02 for x in D['m']]),sensitivity_financial_delay=cfg(maturity=[.2]*5+[0.]*5,release=.1,sale=8,private_sale=10,private_recovery=.5),sensitivity_customer_due1_plus_100m=cfg(financial=D['financial']-.1,opcap=5.116,wc_extra=.1),sensitivity_parent_cash_minus_200m=cfg(cash=D['cash']-.2,subcash=.33),sensitivity_awards_unvested=cfg(personal_ratio=0.))
 out={k:simulate(v) for k,v in paths.items()};b=out['base']
 # Auxiliary economic-profit method: book capital + PV residual earnings + terminal capital excess.
 # All construction, maintenance, WC and necessary cash increases change invested capital.
 aux_cases={}
 for name in ['core_low','core_high']:
  z=out[name];d=z['inputs'];r=d['r'];capital=d['opcap'];cashfloor=d['rev']*.12;epv=0.;rows=[]
  for row in z['years']:
   opening=capital;floor=row['cash_floor'];dcash=floor-cashfloor;cashfloor=floor
   capital+=row['capex']-row['depreciation']+row['change_working_capital']+dcash
   profit=row['nopat']+row['share_based_payment_expense']+floor*.015
   residual_profit=profit-r*opening;epv+=residual_profit/(1+r)**row['year']
   rows.append(dict(year=row['year'],opening_capital=opening,closing_capital=capital,capex=row['capex'],construction_capex=row['construction_capex'],necessary_cash_increase=dcash,profit=profit,residual_profit=residual_profit))
  g=d['g_inf'];terminal_cash_income=cashfloor*(1+g)*.015
  tail=(z['year11_steady_fcfe']+terminal_cash_income-cashfloor*g)/(r-g)
  operating=d['opcap']+epv+(tail-capital)/(1+r)**10
  fin=d['financial'];bridge=d['cash']-d['rev']*.12;financial_rows=[]
  for y in range(1,11):
   income=fin*.015;redeem=d['financial']*d['maturity'][y-1];fin-=redeem
   eq=(d['p_eq']+d['s_eq'])*d['recovery'] if y==d['sale'] else 0.
   private=d['private_equity']*d['private_recovery'] if y==d['private_sale'] else 0.
   amount=income+redeem+eq+private-(d['lease'] if y==1 else 0.)+z['years'][y-1]['award_cash']
   bridge+=amount/(1+r)**y;financial_rows.append(dict(year=y,income=income,redemption=redeem,equity_sale=eq,private_equity_sale=private,net_cash=amount))
  assert all(x['vested_shares']==0 for x in z['years']), 'Auxiliary common-share denominator must be rebuilt if base vests'
  aux_cases[name]=dict(operating_capital_start=d['opcap'],residual_profit_pv=epv,operating_value=operating,financial_bridge=bridge,current_value_per_share=(operating+bridge)/(d['shares']-d['treasury_shares']),years=rows,financial_years=financial_rows)
 aux=dict(method='economic_profit_plus_explicit_asset_realisation',cases=aux_cases,low_per_share=aux_cases['core_low']['current_value_per_share'],high_per_share=aux_cases['core_high']['current_value_per_share'],shared_assumptions=True)
 result=dict(schema='snibe_q3_rebuilt_full_cash_v2',units='CNY billions except per-share; shares billions',model_as_of=ASOF,facts=F,scenarios=out,auxiliary=aux,production_hand_tests=hand(),value_range=dict(low=round(out['core_low']['current_value_per_share'],2),high=round(out['core_high']['current_value_per_share'],2),currency='CNY'),return_model=dict(schema_version=1,method='annual_common_equity_irr_v1',currency='CNY',model_as_of=ASOF,base_case_distributions_per_share=[round(z['dividend_per_share'],6) for z in b['years'][:5]],base_case_terminal_equity_value_range_per_share=dict(year_5=dict(low=round(out['core_low']['year5_terminal_per_share'],6),high=round(out['core_high']['year5_terminal_per_share'],6)))))
 print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False))
if __name__=='__main__':main()

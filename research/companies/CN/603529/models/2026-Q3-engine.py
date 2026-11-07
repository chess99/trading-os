"""603529 ordinary-common economic cash budget. CNY million; no prices; stdlib only.
Only P is a legal ledger. B is an economic repatriation budget, NOT a subsidiary.
Run standalone to regenerate the complete output byte-for-byte.
"""
import copy,json,pathlib
S=863.320284
I=dict(cash=9286.,parent_cash=1800.,debt=2970.,parent_retained=1838.,
       parent_registered=863.320284,parent_statutory=433.946478,parent_discretionary=0.,
       source_earnings_budget=5000.,collateral=5000.,minimum_cash=2000.,
       parent_minimum=400.,sub_minimum=1600.,previous_revenue=22500.,operating_capital=7000.)
BASE=dict(revenue=[24000,26000,27500,28600,29700],margin=[.055,.061,.065,.066,.066],
 capex=[2000,1500,1200,1100,1150],depreciation=[850,900,950,1000,1050],
 wc_ratio=.03,collateral_ratio=.22,gross_wc_ratio=.08,supplier_finance_ratio=.27,
 wc_extra=[300,0,0,0,0],parent_cost=300.,upstream_ratio=.8,arrival=1.,payout=.5,
 rate=.035,financial_yield=.015,repay=[0,0,2200,0,970],extra_debt_cap=1500.,
 terminal_margin=.066,g=.015,roic=.12,r=.10,release_lag=3,release_fee=.02,
 source_realizability=1.,parent_voluntary_reserve=0.,cash_pulse_year=0,cash_pulse=0.)
SCENARIOS={
 'cyclical':dict(revenue=[21500,22500,25500,28000,29700],margin=[.04,.045,.06,.065,.066],wc_extra=[1000,300,-300,-300,0],capex=[2000,1400,1200,1100,1150],arrival=.75,release_lag=5),
 'structural':dict(revenue=[22000,21500,21000,21000,21000],margin=[.035,.025,.025,.025,.025],wc_extra=[2000,1000,0,0,0],capex=[2000,1200,950,950,950],arrival=.65,terminal_margin=.025,g=0.,roic=.08,r=.11,release_lag=5,release_fee=.05),
 'upside':dict(revenue=[25000,28000,30500,32500,34000],margin=[.06,.067,.07,.07,.07],capex=[2200,1700,1500,1350,1350],terminal_margin=.07,g=.02,roic=.15,r=.095),
 'liquidity_extreme':dict(revenue=[18000]*5,margin=[-.02]*5,wc_extra=[6500,1000,0,0,0],arrival=.2,extra_debt_cap=500.),
}
SENSITIVITIES={
 'margin_minus_1pp':dict(margin=[x-.01 for x in BASE['margin']],terminal_margin=.056),
 'arrival_50pct':dict(arrival=.5),
 'capex_plus_300':dict(capex=[x+300 for x in BASE['capex']]),
 'tax_25pct':dict(margin=[x*.75/.8 for x in BASE['margin']],terminal_margin=.066*.75/.8,roic=.12*.75/.8),
 'release_lag_5':dict(release_lag=5),
 'release_lag_1':dict(release_lag=1),
 'realizability_80pct':dict(source_realizability=.8,release_lag=5,release_fee=.05),
 'voluntary_parent_10pct':dict(parent_voluntary_reserve=.1),
}
def legal_close(retained,reserve,registered,profit,voluntary=0.):
 """China parent: current losses offset retained immediately; losses precede reserve.
 Registered, not paid capital or investment carrying amount, sets threshold.
 """
 eligible=max(0.,profit+min(retained,0.))
 statutory=min(eligible*.1,max(registered*.5-reserve,0.))
 discretionary=eligible*voluntary
 return dict(retained=retained+profit-statutory-discretionary,
             statutory=reserve+statutory,statutory_add=statutory,discretionary_add=discretionary)
def dispose(cash,proceeds,external_debt,exit_cost,tax_basis,owner_fraction=1.,tax_rate=.25):
 """Optional genuine exit, never used to close a profitable core business.
 A shortfall is failure with unpaid claims, NEVER a clipped equity liquidation.
 """
 tax=max(proceeds-tax_basis-exit_cost,0.)*tax_rate
 residual=cash+proceeds-exit_cost-tax-external_debt
 return dict(feasible=residual>=-1e-9,unpaid_claims=max(-residual,0.),
   debt_claim=external_debt,cost_claim=exit_cost,tax=tax,
   distributable=residual*owner_fraction if residual>=-1e-9 else None,
   loss=proceeds-tax_basis-exit_cost-tax,ownership=owner_fraction)
def capital_reduction(cash,amount,registered,shares,book_investment,external_debt=0.,cost=0.):
 if registered<=0 or amount<0 or cost<0 or amount>registered or cash-amount-cost<external_debt:
  return dict(feasible=False,debt_claim=external_debt,shares=shares,cash=cash)
 fraction=amount/registered
 return dict(feasible=True,cash=cash-amount-cost,shares=shares*(1-fraction),
   registered=registered-amount,principal=amount,profit=-cost,
   investment_basis_remaining=book_investment*(1-fraction))
def path(p,initial=None,shares=S,years=120,legacy_budget=False):
 q=copy.deepcopy(I if initial is None else initial)
 pc=q['parent_cash'];sc=q['cash']-pc;d=q['debt'];pr=q['parent_retained'];reserve=q['parent_statutory'];disc=q['parent_discretionary']
 budget=q['source_earnings_budget'];ar=0.;drawn=0.;rev0=q['previous_revenue'];capital=q['operating_capital'];pledged=q['collateral'];rows=[];history={};oldminimum=q['minimum_cash']
 for year in range(1,years+1):
  t=year-1;oldc=pc+sc;oldd=d;oldar=ar;oldbudget=budget;oldpr=pr
  if year<=5:
   rev=p['revenue'][t];margin=p['margin'][t];da=p['depreciation'][t];capex=p['capex'][t]
   wc=(rev-rev0)*p['wc_ratio']+p['wc_extra'][t];minimum=q['minimum_cash'];pcost=p['parent_cost'];repay=p['repay'][t]
  else:
   rev=rev0*(1+p['g']);margin=p['terminal_margin'];da=p['depreciation'][-1]*(1+p['g'])**(year-5)
   minimum=q['minimum_cash']*rev/p['revenue'][-1];pcost=p['parent_cost']*rev/p['revenue'][-1];repay=0.
   wc=(rev-rev0)*p['wc_ratio'];reinvestment=rev*margin*p['g']/p['roic'];capex=da+reinvestment-wc-(minimum-oldminimum)
   if capex<0:return dict(feasible=False,rows=rows,failure_year=year,reason='negative maintenance/growth capex decomposition')
  pmin=minimum*q['parent_minimum']/q['minimum_cash'];smin=minimum-pmin
  op=rev*margin;cb=min(d,2000.) if year<=3 and p['repay'][2]>=2200 else 0.
  coupon=([30.,36.,0.,0.,0.][t] if year<=5 and cb else 0.)
  finance=oldc*p['financial_yield']-(d-cb)*p['rate']-coupon
  premium=200. if repay>=2200 else 0.;principal=min(max(repay-premium,0.),d)
  ni=op+finance-premium;source_profit=ni+pcost
  # This is a forecast economic earnings-availability budget, NOT a legal retained account.
  # Legacy comparator deliberately reproduces the old indefinite 10% synthetic reserve.
  friction=.1*max(source_profit,0.) if legacy_budget else 0.
  budget+=source_profit-friction
  fcf=ni+da-capex-wc
  pulse=p['cash_pulse'] if p['cash_pulse_year']==year else 0.
  # Test pulse represents return of financial principal already owned, no new earnings.
  sc+=fcf+pcost+pulse;pc-=pcost+principal;d-=principal
  collateral_add=(rev-rev0)*p['collateral_ratio'];pledged+=collateral_add
  gross_wc=(rev-rev0)*p['gross_wc_ratio'];supplier=(rev-rev0)*p['supplier_finance_ratio']
  extra=p['wc_extra'][t] if year<=5 else 0.
  assert abs(wc-(collateral_add+gross_wc-supplier+extra))<1e-6
  # All surplus vintages get a finite opportunity to release. Year5 surplus first reviewed at year8.
  due=history.get(year-p['release_lag'],0.) if year>5 else 0.
  normal=max(0.,source_profit*p['upstream_ratio'])
  desired_special=min(due,max(sc-smin,0.))
  capacity=max(budget,0.)*p['source_realizability']
  declared_normal=min(normal,capacity,max(sc-smin-ar,0.))
  available_budget=max(budget-declared_normal,0.)*p['source_realizability']
  declared_special=min(desired_special,available_budget/(1+p['release_fee']),max(sc-smin-ar-declared_normal,0.)/(1+p['release_fee']))
  fee=declared_special*p['release_fee']
  sc-=fee;ni-=fee;fcf-=fee;source_profit-=fee;budget-=fee
  declared=declared_normal+declared_special;budget-=declared;ar+=declared
  received=ar*p['arrival'];ar-=received;sc-=received;pc+=received
  legal=legal_close(pr,reserve,q['parent_registered'],-pcost+declared,p['parent_voluntary_reserve'] if year<=5 else 0.)
  pr=legal['retained'];reserve=legal['statutory'];disc+=legal['discretionary_add']
  needp=max(pmin-pc,0.);needs=max(smin-sc,0.);need=needp+needs
  draw=min(need,max(p['extra_debt_cap']-drawn,0.));drawn+=draw;d+=draw
  pd=min(draw,needp);pc+=pd;sc+=draw-pd
  feasible=pc>=pmin-1e-7 and sc>=smin-1e-7
  normal_target=max(ni*p['payout'],0.)
  ordinary=min(normal_target,max(pr,0.),max(pc-pmin,0.),max(pc+sc-minimum-d,0.)) if feasible else 0.
  pc-=ordinary;pr-=ordinary
  special=min(due,max(pr,0.),max(pc-pmin,0.),max(pc+sc-minimum-d,0.)) if feasible else 0.
  pc-=special;pr-=special;c=pc+sc;dividend=ordinary+special
  capital+=capex-da+wc+(minimum-oldminimum)
  history[year]=max(c-minimum-d,0.) if year>=5 else 0.
  assert abs(c-(oldc+fcf-principal+draw-dividend+pulse))<1e-6
  assert abs(d-(oldd-principal+draw))<1e-7
  assert abs(ar-(oldar+declared-received))<1e-7
  assert abs(budget-(oldbudget+source_profit-friction-declared))<1e-6
  assert abs(pr-(oldpr-pcost+declared-legal['statutory_add']-legal['discretionary_add']-dividend))<1e-6
  rows.append(dict(year=year,revenue=rev,operating_common_profit=op,finance=finance,net_income=ni,
   capex=capex,depreciation=da,working_capital_increase=wc,minimum_cash=minimum,
   restricted_collateral=pledged,collateral_increase=collateral_add,gross_operating_wc_increase=gross_wc,
   incremental_supplier_finance=supplier,fcf=fcf,source_earnings_budget=budget,
   source_profit_budget=source_profit,synthetic_legacy_reserve=friction,
   declared_normal=declared_normal,declared_special=declared_special,realization_fee=fee,
   declared=declared,received=received,upstream_receivable=ar,parent_legal_retained=pr,
   parent_statutory=reserve,parent_statutory_add=legal['statutory_add'],parent_discretionary=disc,
   parent_cash=pc,source_cash_budget=sc,cash=c,debt=d,new_debt=draw,ordinary_dividend=ordinary,
   special_dividend=special,dividend=dividend,dps=dividend/shares,shares=shares,capital=capital,
   due_surplus_budget=due,post_distribution_surplus=history[year],financial_principal_pulse=pulse,feasible=feasible))
  if not feasible:return dict(feasible=False,rows=rows,failure_year=year,reason='zero distributions and finite funding fail necessary liquidity',unfunded=need-draw,debt_claim=d)
  rev0=rev;oldminimum=minimum
 return dict(feasible=True,rows=rows)
def value(run,p):
 if not run['feasible']:return None
 r=p['r'];g=p['g'];a=run['rows'];n=len(a)
 # 120 years is numerical integration, not an asserted legal forecast. Residual cash includes
 # only the final unspent economic financial pool. Tail cash flows converge in separate tests.
 next_profit=a[-1]['revenue']*(1+g)*p['terminal_margin']
 terminal_operating=next_profit*(1-g/p['roic'])/(r-g)
 surplus=a[-1]['cash']-a[-1]['minimum_cash']-a[-1]['debt']
 residual=terminal_operating+surplus
 pv=sum(x['dividend']/(1+r)**x['year'] for x in a)+residual/(1+r)**n
 tv5=(sum(x['dividend']/(1+r)**(x['year']-5) for x in a[5:])+residual/(1+r)**(n-5))
 return dict(value_per_share=pv/a[0]['shares'],terminal_year5_per_share=tv5/a[0]['shares'],
  pv_distributions_first5=sum(x['dividend']/(1+r)**x['year'] for x in a[:5]),
  pv_after5=tv5/(1+r)**5,terminal_contribution=(tv5/(1+r)**5)/pv,
  numerical_residual_pv=residual/(1+r)**n,terminal_operating_at_n=terminal_operating,
  final_surplus=surplus,years=n)
def case(ch=None,initial=None,shares=S,years=120,legacy=False):
 p=copy.deepcopy(BASE);p.update(ch or {});run=path(p,initial,shares,years,legacy)
 return dict(changed=ch or {},inputs=p,initial=initial or I,path=run,valuation=value(run,p),
  effective='year1 operating/arrival changes; tail after year5; source is economic budget, parent is China legal person')
def main():
 out=dict(schema='603529-economic-budget-v2',units='CNY million; million shares; CNY/share',shares=S,initial=I,
  scope='China parent legal ledger + disclosed domestic whole-owned economic cash-source budget; no fabricated subsidiary reserves; foreign and minority proceeds not separately added',
  core_low=case(),core_high=case(dict(r=.095,g=.02,roic=.15)),
  scenarios={k:case(v) for k,v in SCENARIOS.items()},sensitivities={k:case(v) for k,v in SENSITIVITIES.items()})
 ii=dict(I,debt=970.,parent_registered=S+1999.497/36.70)
 out['scenarios']['upside_full_conversion']=case(dict(SCENARIOS['upside'],repay=[0,0,0,0,970]),ii,S+1999.497/36.70)
 out['sensitivities']['parent_cash_and_receipt']=case(dict(arrival=.5),dict(I,parent_cash=800.))
 out['sensitivities']['additional_restricted_500']=case(initial=dict(I,cash=8786.))
 out['sensitivities']['zero_source_opening_earnings_budget']=case(initial=dict(I,source_earnings_budget=0.))
 out['method_comparison_same_economics']={side:{'old_synthetic_budget':case(ch,legacy=True),'new_economic_budget':case(ch)} for side,ch in [('low',{}),('high',dict(r=.095,g=.02,roic=.15))]}
 out['method2']=dict(normalized_operating_common_profit=1600.,multiples=[11,14],
  current_net_financial_assets=I['cash']-I['minimum_cash']-I['debt'],
  realized_financial_pv=(I['cash']-I['minimum_cash']-I['debt'])*.98*(1.015/1.10)**3,
  value_range=[(1600*m+(I['cash']-I['minimum_cash']-I['debt'])*.98*(1.015/1.10)**3)/S for m in [11,14]])
 out['convergence']={str(n):case(years=n)['valuation'] for n in [60,120,240]}
 pathlib.Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()

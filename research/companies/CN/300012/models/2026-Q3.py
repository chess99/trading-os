"""CN:300012 independent Q3 model. CNY billion, shares billion; no spot price/IRR.
Earnings already attributable to common shareholders and after recurring rent,
research expense and expected credit losses; cash financial income excluded.
Non-lease debt interest is excluded from forecast earnings (debt deducted once).
"""
import json, math
from pathlib import Path
SHARES=1.682828214
# Q3 other-current financial deposit split not disclosed; H1 0.283042bn guides range.
BRIDGE={'cash_equivalents':.61314537045,'trading_financial_assets':.36761189194,'other_current_financial_assets_estimate':.28,'noncurrent_financial_assets':.01011858241,'operating_cash':-.45,'common_attribution_reserve':-.03,'interest_debt_reserve':-.067,'legacy_acquisition_payable_reserve':-.06524846766}
CASH=sum(BRIDGE.values())
# Each year is next 12 months ended October 21, beginning 2027.
BASE_E=[1.30,1.43,1.54,1.65,1.75]
REVENUE=[8.1,8.85,9.55,10.25,10.9]
DA=[.48,.52,.56,.60,.64] # excludes ROU depreciation (rent remains expense)
CAPEX=[.75,.78,.81,.84,.87]
NWC=[.17,.19,.19,.19,.18]
ACQUISITIONS=[.30,.30,.30,.25,.25]
RENT_GAP=[.02,.02,.02,.02,.02]
DPS=[.23,.26,.29,.32,.35]

def calc(k=.09, terminal_g=.03, roi=.15, e_scale=1, investment_scale=1, extra_cash=0, tail_g=None, earnings_factors=None):
 e=[x*e_scale*f for x,f in zip(BASE_E,earnings_factors or [1]*5)]
 reinv=[(c-d+w+a+l)*investment_scale for c,d,w,a,l in zip(CAPEX,DA,NWC,ACQUISITIONS,RENT_GAP)]
 fcf=[p-i for p,i in zip(e,reinv)]
 tail_g=tail_g or [.05,.045,.04,.035,.03]
 for g in tail_g:
  prev=e[-1]; e.append(prev*(1+g));reinv.append((e[-1]-prev)/roi);fcf.append(e[-1]-reinv[-1])
 terminal_next=e[-1]*(1+terminal_g)*(1-terminal_g/roi)
 tv=terminal_next/(k-terminal_g)
 pv_cf=sum(c/(1+k)**t for t,c in enumerate(fcf,1))
 pv_tv=tv/(1+k)**10
 cash=CASH+extra_cash
 value=(pv_cf+pv_tv+cash)/SHARES
 # Payout model accumulates only unspent free cash, never all accounting profit.
 balances=[];balances_zero_yield=[];bal=cash;bal0=cash
 for c,dps in zip(fcf[:5],DPS):
  dividend=dps*SHARES
  old=bal;bal=old*1.015+c-dividend;bal0+=c-dividend
  assert abs(bal-(old+old*.015+c-dividend))<1e-10
  balances.append(bal);balances_zero_yield.append(bal0)
 cont5=sum(fcf[t-1]/(1+k)**(t-5) for t in range(6,11))+tv/(1+k)**5
 terminal5=(cont5+balances[-1])/SHARES
 assert len(DPS)==5 and all(c>0 for c in balances)
 # With cash earning the valuation rate instead, PV(distributions+terminal)=DCF.
 faircash=cash
 for c,d in zip(fcf[:5],DPS):faircash=faircash*(1+k)+c-d*SHARES
 check=sum(d/(1+k)**t for t,d in enumerate(DPS,1))+(cont5+faircash)/SHARES/(1+k)**5
 assert abs(check-value)<1e-10
 actual_payout_value=sum(d/(1+k)**t for t,d in enumerate(DPS,1))+terminal5/(1+k)**5
 return {'value_per_share':actual_payout_value,'immediate_fcfe_value_per_share':value,'terminal_share_y5':terminal5,'terminal_operating_value_y5_bn':cont5,'terminal_cash_y5_bn':balances[-1], 'terminal_pv_share_of_operating_value':pv_tv/(pv_cf+pv_tv),'earnings_bn':e,'reinvestment_bn':reinv,'fcf_bn':fcf,'cash_balances_bn':balances,'cash_balances_zero_yield_bn':balances_zero_yield,'discount_rate':k,'terminal_growth':terminal_g,'terminal_incremental_return':roi,'enterprise_continuation_y10_bn':tv}

if __name__=='__main__':
 # Core range varies required equity capital cost, sustainable growth and return
 # while retaining one observed operating pathway, not all scenario extremes.
 out={'bridge_bn':BRIDGE,'net_extra_financial_assets_bn':CASH,'shares_bn':SHARES,'dps':DPS,'base':calc(),'core_low':calc(k=.095,terminal_g=.025,roi=.14),'core_high':calc(k=.085,terminal_g=.03,roi=.16),'sensitivity_roi12':calc(roi=.12),'sensitivity_k10':calc(k=.10),'cycle_weak':calc(earnings_factors=[.85,.9,.95,1,1],investment_scale=1.05),'structural_weak':calc(k=.10,terminal_g=.015,roi=.10,e_scale=.8,investment_scale=1.15,tail_g=[.02,.02,.02,.02,.02]),'optimistic':calc(k=.085,terminal_g=.035,roi=.18,e_scale=1.1,investment_scale=.95)}
 capital0=8.39990558255-CASH
 capital5=capital0+sum(out['base']['reinvestment_bn'][:5])
 ri={}
 for tag,k,g,roe in [('low',.095,.025,.14),('high',.085,.03,.16)]:
  op5=capital5*(roe-g)/(k-g)
  tv5=(op5+out['base']['terminal_cash_y5_bn'])/SHARES
  pv=sum(d/(1+k)**t for t,d in enumerate(DPS,1))+tv5/(1+k)**5
  ri[tag]={'value_per_share':pv,'capital0_bn':capital0,'capital5_bn':capital5,'mature_roe':roe,'operating_value_y5_bn':op5}
 out['residual_income_crosscheck']=ri
 out['revenue_bn']=REVENUE
 out['normal_margin']=[p/r for p,r in zip(BASE_E,REVENUE)]
 out['parent_cash_budget_bn']=[a+b-c for a,b,c in zip([.20,.22,.24,.26,.28],[.23,.25,.28,.31,.34],[.04,.03,.03,.03,.03])]
 out['dividend_cash_bn']=[d*SHARES for d in DPS]
 assert all(c>=d for c,d in zip(out['parent_cash_budget_bn'],out['dividend_cash_bn']))
 out['incremental_return_y1_to_y5']=(BASE_E[-1]-BASE_E[0])/sum(out['base']['reinvestment_bn'][1:5])
 # Independent constant-cash no-growth analytical sanity check.
 pv10=sum(1/1.1**t for t in range(1,11))+10/1.1**10
 assert abs(pv10-10)<1e-12

 print(json.dumps(out,ensure_ascii=False,indent=2))

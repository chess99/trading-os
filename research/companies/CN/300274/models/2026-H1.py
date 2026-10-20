# -*- coding: utf-8 -*-
"""人民币亿元、亿股；无网络。债务续作，净借款零；少数现金和终值单独扣除。"""
import json
from pathlib import Path
S=20.73211424
D=[1.20,1.25,1.30,1.35,1.40]
CASH0=336.74-150-3.25+35.879*.5-3.265
DEBT=86.67
INTEREST=DEBT*.0375*(1-.20)
MINORITY=30.42
MINORITY_CASH=2.0
CASES={
 'low':dict(revenue=[650,690,730,770,800],nopat=[85,91,97,102,105],gross_capex=[40,41,42,42,42],depreciation=[15,16,18,20,22],delta_wc=[13,15,14,13,12],g=.018,roic=.09,wacc=.10,ke=.105),
 'high':dict(revenue=[700,760,820,870,920],nopat=[92,100,107,112,118],gross_capex=[36,38,39,40,41],depreciation=[15,16,18,20,22],delta_wc=[11,12,11,10,9],g=.022,roic=.11,wacc=.09,ke=.095),
}
def run(c,extra_capital=0,terminal_roic=None,minority=MINORITY):
 cash=CASH0; rows=[]
 for i in range(5):
  investment=c['gross_capex'][i]-c['depreciation'][i]+c['delta_wc'][i]+extra_capital
  fcff=c['nopat'][i]-investment
  common=fcff-INTEREST-MINORITY_CASH
  distribution=D[i]*S
  cash+=common-distribution
  rows.append(dict(year=i+1,revenue=c['revenue'][i],nopat=c['nopat'][i],gross_capex=c['gross_capex'][i],depreciation=c['depreciation'][i],delta_wc=c['delta_wc'][i],net_investment=investment,fcff=fcff,after_tax_interest=INTEREST,minority_cash=MINORITY_CASH,common_cash=common,distribution=distribution,ending_cash=cash))
  assert abs(fcff-common-INTEREST-MINORITY_CASH)<1e-9
  assert cash>=0 and common>distribution
 roi=terminal_roic or c['roic']
 n6=c['nopat'][-1]*(1+c['g']); reinvest6=n6*c['g']/roi; fcff6=n6-reinvest6
 ev=fcff6/(c['wacc']-c['g']); eq=ev+cash-DEBT-minority; tv=eq/S
 pvdiv=sum(d/(1+c['ke'])**t for t,d in enumerate(D,1)); pvt=tv/(1+c['ke'])**5
 assert abs(cash-(CASH0+sum(x['common_cash']-x['distribution'] for x in rows)))<1e-8
 assert abs(reinvest6/n6*roi-c['g'])<1e-10
 return dict(rows=rows,nopat6=n6,reinvestment6=reinvest6,fcff6=fcff6,terminal_ev=ev,terminal_cash=cash,terminal_debt=DEBT,terminal_minority=minority,terminal_equity=eq,terminal_per_share=tv,value_per_share=pvdiv+pvt,terminal_pv_share=pvt/(pvdiv+pvt),incremental_roic_1_to_5=(c['nopat'][-1]-c['nopat'][0])/sum(x['net_investment'] for x in rows[1:]))
def main():
 out=dict(units='亿元/亿股',shares=S,dividends_per_share=D,initial_excess_financial_assets=CASH0,debt=DEBT,after_tax_interest=INTEREST,cases={},sensitivities={})
 for k,c in CASES.items():
  out['cases'][k]=run(c)
  out['sensitivities'][k]=dict(extra_10_annual_capital=run(c,extra_capital=10)['value_per_share'],terminal_roic_2pp_lower=run(c,terminal_roic=c['roic']-.02)['value_per_share'],minority_double=run(c,minority=MINORITY*2)['value_per_share'])
 # known identities, not target-range tests
 zero_growth=dict(CASES['low'],g=0.0)
 assert abs(run(zero_growth)['fcff6']-105)<1e-9
 for key,c in CASES.items():
  delta=out['cases'][key]['value_per_share']-out['sensitivities'][key]['extra_10_annual_capital']
  assert abs(delta-50/S/(1+c['ke'])**5)<1e-9
 out['auxiliary_pe']={'low':85*12/S,'high':105*14/S}
 assert abs(100/(.10-.02)-1250)<1e-10
 assert abs(sum(D)*S-sum(x['distribution'] for x in out['cases']['low']['rows']))<1e-9
 Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()

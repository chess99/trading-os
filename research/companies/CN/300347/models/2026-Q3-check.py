"""用另一套直接算式复算经营DCF、关键扰动、资金守恒及股本桥。"""
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
data=json.loads((ROOT/'2026-Q3-inputs.json').read_text(encoding='utf-8'))
spec=importlib.util.spec_from_file_location('tigermed_q3',ROOT/'2026-Q3.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
actual=m.compute(data)

# Independent loop does not call the producer's operating or DCF functions.
a=data['operating_assumptions']
def independent(shift=0.,rate=.105):
    rev=a['opening_revenue']; pv=0.
    for year in range(1,11):
        newrev=rev*(1+a['growth'][year-1])
        profit=newrev*(a['margins'][year-1]+shift)*(1-a['tax'])
        fcf=profit-(newrev-rev)*(a['working_capital_ratio']+a['growth_ppe_ratio'])
        pv+=fcf/(1+rate)**year
        rev=newrev
    end=profit*1.025*(1-.025/.16)/(rate-.025)/(1+rate)**10
    return pv+end

for side,rate in [('low',.115),('reference',.105),('high',.095)]:
    assert abs(independent(rate=rate)-actual['operating_diagnostic']
               ['discounted_business'][side]['business_enterprise_value'])<1e-10
assert abs(independent(-.01)-independent()-actual['operating_diagnostic']
           ['one_percentage_point_margin_effect'])<1e-10

# Actual Q3 standalone reconciliation, not a copied rounded conclusion.
f=data['facts']; q=actual['quarter_reconciliation']
assert abs(q['revenue']-2.08396789314)<1e-10
assert abs(q['common_adjusted_profit']-.17234586717)<1e-10
assert abs(q['operating_cf']-(.77131192345-.42578233529))<1e-10
assert abs(actual['parent_h1_dividend_cash_implied_by_balance_bridge']-
           (.26610742593+.16728456878-.15040956878))<1e-10

# Aggregate cash bridge from source inputs to result, independently of per-year
# producer assertions. New borrowings are obligations, not operating income.
for case in actual['consolidated_funding_boundaries'].values():
    rs=case['rows']
    delta=sum(r['deposit_release']+r['exits']+r['operation_fcf']+
              r['award_cash']-r['call']-r['financing_interest'] for r in rs)
    other=f['other_investment_commitment']+f['acquisition_tail']
    expected=f['cash_equivalents_q3']+delta-other+case['ending_additional_debt']
    assert abs(expected-rs[-1]['closing_cash'])<1e-10

s=actual['share_bridge']
assert round(s['registered_after_cancellations']*1e9)==855142270
assert round(s['treasury_after_cancellations']*1e9)==20963478
assert round(s['outside_current']*1e9)==834178792
assert round(s['fully_diluted_if_awards_vest']*1e9)==843353562
assert actual['value_range'] is None and actual['return_model'] is None
print('PASS: independent operating DCF endpoints and margin effect; Q3, dividends, cash/debt, and share bridges; publication nulls preserved')

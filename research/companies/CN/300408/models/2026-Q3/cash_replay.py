import hashlib,copy
from pathlib import Path
# NEW_RECONSTRUCTION: cached operating inputs; current cash recursion.
# No original main/build or full-company scenario generator is included.
CACHE_ROWS = None
TAIL_ROWS = None
EVENT_DELTA_CASH = 0.0
TREASURY_SHARES = .003566367

import json, math, argparse, tempfile, subprocess, sys, hashlib

from pathlib import Path

SHARES=1.996718571

FACTS={'revenue_9m':11.50279609524,'profit_9m':3.865199634,'revenue_q3':5.07946433904,'profit_q3':1.93308139329,'cash':11.57188087185,'liquid_investments':3.06164445722,'other_noncurrent':5.54262411258,'long_deposit_budget':5.30,'debt_and_lease':1.66953126187,'post_balance_buyback_budget':.50,'minority_equity':.00419001671,'parent_retained_H1':6.76403078395,'parent_reserve_H1':1.13113825124,'issued_shares_bn':SHARES}

OPEN_CASH=FACTS['cash']+FACTS['liquid_investments']+FACTS['long_deposit_budget']-FACTS['debt_and_lease']-FACTS['post_balance_buyback_budget']-FACTS['minority_equity']

NAMES=['潮州三环母公司','南充三环','德阳三环','其他正留存预算组（香港/深圳/苏州等）','境外未弥亏预算组（具体法人未披露；境外实际主体含Frontier/Vermes/Glory）']

OP=[.45,.25,.20,.08,.02]

CAP=[.22,.35,.33,.08,.02]

N=len(OP)

FLOOR=[.5,.225,.175,.08,.02]

CAPITAL=[SHARES,.06,.20,.90,.10]

RESERVE=[1.13113825124,.03,.10,.05,0.]

RETAINED=[6.76403078395,4.,3.,1.,-.08387549836]

INITIAL=[OPEN_CASH-5.2,2.2,1.7,1.1,.2]

LOANS=[0.,1.4,.9,.205,.05]

BASE={'rate':.10,'margin_shift':0.,'revenue_scale':1.,'capex_scale':1.,'legal_scale':1.,'cash_delay':0,'repatriation_haircut':.10,'foreign_delay':2,'interest_net':.015,'special_cap':2.,'terminal_margin':.24,'operating_tax':.15}

def legal_step(retained,reserve,capital,profit,cash_available,wanted,reserve_rate=.10):
    """Same production chain in every entity, including hand-calculable tests."""
    healed=max(0.,profit+min(retained,0.))
    appropriation=min(reserve_rate*healed,max(0.,.5*capital-reserve))
    legal=max(0.,retained+profit-appropriation)
    dividend=min(max(0.,wanted),max(0.,cash_available),legal)
    return {'retained':retained+profit-appropriation-dividend,'reserve':reserve+appropriation,'reserve_add':appropriation,'legal_capacity':legal,'dividend':dividend}

def model(cfg,years=240):
    rows=[]; cash=INITIAL[:]; cash[0]+=cfg.get('opening_cash_delta',0.); ret=[x*cfg['legal_scale'] if x>=0 else x for x in RETAINED]; reserve=RESERVE[:]; loans=LOANS[:]
    retained_cash_release_year=None
    book_ppe=8.166
    for econ in CACHE_ROWS[:years]:
        t=econ['year']; book_ppe+=econ['capex']-econ['depreciation']; opening=sum(cash); fin=[c*cfg['interest_net'] for c in cash]
        profits=[econ['operating_profit']*w+fin[i] for i,w in enumerate(OP)]
        minimum=[econ['revenue']*.10*w for w in FLOOR]
        flows=[profits[i]+econ['depreciation']*CAP[i]-econ['capex']*CAP[i]-econ['delta_wc']*OP[i] for i in range(N)]
        # Known overseas loss bucket is separate; withholding occurs only on actual remittance.
        foreign_tax=0.
        for i in range(N): cash[i]+=flows[i]
        # Parent equity injections as needed; no fictitious external funding.
        injections=[0.]*N
        for i in range(1,N):
            if cash[i]<minimum[i]:
                injections[i]=minimum[i]-cash[i]; cash[0]-=injections[i]; cash[i]+=injections[i]
        assert cash[0]>=-1e-8,'Unfunded capital plan'
        # Real intercompany loan repayments budget, does NOT create parent legal earnings.
        repayments=[0.]*N
        if 6<=t<=10:
            for i in range(1,N):
                repayments[i]=min(loans[i],LOANS[i]/5,max(0.,cash[i]-minimum[i]))
                loans[i]-=repayments[i]; cash[i]-=repayments[i]; cash[0]+=repayments[i]
        dividends=[]; entity=[]; up=0.
        for i in range(1,N):
            wanted=0. if t<=max(cfg['cash_delay'],cfg['foreign_delay'] if i==4 else 0) else max(0.,cash[i]-minimum[i])
            # Capital-use funds: no excess distribution during first five construction years;
            # only current realized earnings/cash conversion can be remitted.
            if t<=5: wanted=min(wanted,max(0.,profits[i])*.70)
            st=legal_step(ret[i],reserve[i],CAPITAL[i],profits[i],cash[i]-minimum[i],wanted,reserve_rate=0. if i==4 else .10)
            ret[i]=st['retained']; reserve[i]=st['reserve']; cash[i]-=st['dividend']; tax=st['dividend']*cfg['repatriation_haircut'] if i==4 else 0.; foreign_tax+=tax;up+=st['dividend']-tax
            entity.append(dict(name=NAMES[i],profit=profits[i],cashflow=flows[i],loan_repayment=repayments[i],injection=injections[i],minimum_cash=minimum[i],closing_cash=cash[i],withholding_tax=tax,**st))
        cash[0]+=up
        parent_profit=profits[0]+up # dividend declaration and receipt same year budget.
        # Actual known opening HK dividend receivable excluded from incremental profit and cash;
        # immaterial 0.008826bn, no duplicate gain.
        payout=[.25,.30,.35,.40,.45][t-1] if t<=5 else 1.
        wanted=max(0.,econ['operating_profit'])*payout
        if t>=6: wanted+=max(0.,sum(fin)-foreign_tax)+cfg['special_cap']
        st=legal_step(ret[0],reserve[0],CAPITAL[0],parent_profit,cash[0]-minimum[0],wanted)
        ret[0]=st['retained']; reserve[0]=st['reserve']; cash[0]-=st['dividend']
        entity.insert(0,dict(name=NAMES[0],profit=parent_profit,own_profit=profits[0],upstream_dividend=up,cashflow=flows[0],minimum_cash=minimum[0],closing_cash=cash[0],**st))
        closing=sum(cash); div=st['dividend']; totalflow=sum(flows)-foreign_tax
        liquidation=0.
        if t in [cfg.get('capital_return_year'),cfg.get('foreign_capital_return_year')]:
            # Explicit conditional legal-entity capital return, NOT approved policy.
            # Parent budget limited to 60% of disclosed 13.0169bn capital reserve;
            # the register/creditor/tax process must separately permit a proportional
            # return. Reference ownership units unchanged, nominal shares may shrink.
            # Overseas unidentified-loss bucket: only allocated .2bn initial financial
            # resources as an economic ceiling, subject to EACH relevant local entity's
            # solvency/capital tests. No inference that PRC rules authorize foreign return.
            indices=([0] if t==cfg.get('capital_return_year') else [])+([4] if t==cfg.get('foreign_capital_return_year') else [])
            for i in indices:
                ceiling=13.01691792502*.60 if i==0 else .2
                gross=min(max(0.,cash[i]-minimum[i]),ceiling)
                cost=min(gross,.02*gross+.2) if i==0 else min(gross,.10*gross+.02)
                if i==4:
                    # Two legs: foreign capital proceeds to parent, then separately
                    # approved supplementary parent proportional capital return.
                    cost+=min(gross-cost,.02*(gross-cost)+.02)
                    entity[0]['supplementary_capital_return_from_foreign']=gross-cost
                payment=gross-cost
                cash[i]-=gross; div+=payment;liquidation+=payment;totalflow-=cost
                entity[i]['conditional_capital_return_gross']=gross
                entity[i]['conditional_capital_return_ceiling']=ceiling
                entity[i]['conditional_capital_return_cost']=cost
                entity[i]['conditional_capital_return']=payment
                entity[i]['closing_cash']=cash[i]
            closing=sum(cash)
        assert abs(opening+totalflow-div-closing)<1e-8*max(1.,closing)
        assert all(c>=-1e-9 for c in cash)
        if retained_cash_release_year is None and t>5 and closing<=sum(minimum)+.001: retained_cash_release_year=t
        rows.append(dict(**econ,opening_cash=opening,financial_income=sum(fin),foreign_tax=foreign_tax,group_cashflow=totalflow,dividend=div,dps=div/SHARES,closing_cash=closing,minimum_cash=sum(minimum),book_ppe=book_ppe,liquidation_distribution=liquidation,entities=entity))
    r=cfg['rate']; pv=sum(z['dps']/(1+r)**z['year'] for z in rows)
    # Mature cash is necessary working liquidity, no excess financial principal stranded.
    # 240-year omitted PV is immaterial; explicit truncation convergence reported below.
    term=sum(z['dps']/(1+r)**(z['year']-5) for z in rows[5:])
    return {'config':cfg,'value':pv,'year5_terminal':term,'terminal_pv_fraction':term/(1+r)**5/pv,'dps':[z['dps'] for z in rows[:5]],'excess_cash_exhausted_year':retained_cash_release_year,'rows':rows}


import importlib.util,sys,stat,os
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
CODE='300408'
CHECKER_NAME='2026-Q3-capital-20261103-check.py'
CHECKER_SHA='36fb331abf95aeaacb7761a7e3b41f642b3406fdfdb22bea3df835af3b1f5160'
EVENT={'fees': 'All source transactions exclude fees; no exact fee inferred', 'future_cancellation_only_not_current': '1991471471', 'historical_budget_fields': 'third_plan_preserved_budget/replacement_total_post_q3_reserve describe Nov2, not current completed cash', 'holder_denominator_policy': 'Original all-issued reference shares; no cancellation benefit', 'net_additional_cash_vs_original': '4858029.78', 'registered_A': '1916497371', 'registered_H': '80221200', 'registered_shares_unchanged': '1996718571', 'replacement_total_post_q3_cash': '504858029.78', 'replacement_total_post_q3_reserve': '504894688.00', 'rounded_average_not_exact_payment': True, 'same_base_terminal_discount_rates': ['0.105', '0.10', '0.095'], 'second_plan_completed_paid': '999979500.18', 'second_plan_paid_q3': '995084812.18', 'second_plan_post_q3_cash': '4894688.00', 'source_ids': ['1225598801', '1225605527', '1225605526', '1225652669', '1225652670', '1225652593'], 'third_plan_completed_cash': '499963341.78', 'third_plan_completed_shares': '5247100', 'third_plan_nov2_paid_included_not_additional': '5006512.00', 'third_plan_preserved_budget': '500000000.00', 'third_plan_unused_budget_released': '36658.22'}
OUTPUT_META={'classification': 'NEW_RECONSTRUCTION_NOT_OLD189_BYTE_RECOVERY', 'event': {'fees': 'All source transactions exclude fees; no exact fee inferred', 'future_cancellation_only_not_current': '1991471471', 'historical_budget_fields': 'third_plan_preserved_budget/replacement_total_post_q3_reserve describe Nov2, not current completed cash', 'holder_denominator_policy': 'Original all-issued reference shares; no cancellation benefit', 'net_additional_cash_vs_original': '4858029.78', 'registered_A': '1916497371', 'registered_H': '80221200', 'registered_shares_unchanged': '1996718571', 'replacement_total_post_q3_cash': '504858029.78', 'replacement_total_post_q3_reserve': '504894688.00', 'rounded_average_not_exact_payment': True, 'same_base_terminal_discount_rates': ['0.105', '0.10', '0.095'], 'second_plan_completed_paid': '999979500.18', 'second_plan_paid_q3': '995084812.18', 'second_plan_post_q3_cash': '4894688.00', 'source_ids': ['1225598801', '1225605527', '1225605526', '1225652669', '1225652670', '1225652593'], 'third_plan_completed_cash': '499963341.78', 'third_plan_completed_shares': '5247100', 'third_plan_nov2_paid_included_not_additional': '5006512.00', 'third_plan_preserved_budget': '500000000.00', 'third_plan_unused_budget_released': '36658.22'}, 'event_asof': '2026-11-03', 'event_input_sha256': 'c15a5d1c0a5235489d2ad2aaee220a7c7648d9a87f5495d8d72082741c824121', 'historical_field_roles': {}, 'old_diagnostics_are_historical_not_updated': True, 'operating_forecast_recomputed': False, 'original_baseline_sha256': 'd5f22281da17e87e249e9479cf7a87e72c33a2ac38e8d6845e1930215952b8e3', 'period': '2026-Q3', 'scope': '3 core x240 cash +2 auxiliary x240 cash; no operating forecast; other9 and release sensitivities historical', 'scope_note': 'Original full company forecast dispatcher not executed; operating rows reused. Original finite terminal/NOPAT and normalized earning-power formulas are evaluated where required for selected cash valuation, not called new researched forecasts.', 'symbol': 'CN:300408', 'public_delivery_note': 'New reconstruction of selected current cash from exact published operating budgets. Old unselected diagnostics remain historical. This is not recovery of the lost original189 bytes.'}

def selected_cash(old,event,changed):
    m=sys.modules[__name__]
    delta = float(event['net_additional_cash_vs_original'])/1e9 if changed else 0.
    m.INITIAL[0] -= delta
    result = {'cases': {}, 'auxiliary': []}
    wanted = ('year', 'revenue', 'margin', 'operating_profit', 'depreciation', 'capex', 'delta_wc')
    for name in ('base', 'core_low', 'core_high'):
        saved = old['cases'][name]
        m.CACHE_ROWS = [{k: row[k] for k in wanted} for row in saved['rows']]
        assert len(m.CACHE_ROWS) == 240
        result['cases'][name] = m.model(copy.deepcopy(saved['config']), 240)
    for saved in old['auxiliary_earnings_power']:
        m.CACHE_ROWS = [{k: row[k] for k in wanted} for row in saved['rows']]
        result['auxiliary'].append(m.model(copy.deepcopy(saved['config']), 240))
    oracle = {'cases': {k: old['cases'][k] for k in result['cases']}, 'auxiliary': []}
    for new, saved in zip(result['auxiliary'], old['auxiliary_earnings_power']):
        oracle['auxiliary'].append({k: saved[k] for k in ('config', 'value', 'year5_terminal', 'excess_cash_exhausted_year', 'rows')})
    projection = {'cases': result['cases'], 'auxiliary': [{k: v[k] for k in oracle['auxiliary'][i]} for i, v in enumerate(result['auxiliary'])]}
    scope = '3 core x240 cash +2 auxiliary x240 cash; no operating forecast; other9 and release sensitivities historical'

    return result,projection,oracle,scope

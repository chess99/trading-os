import hashlib,copy
from pathlib import Path
# NEW_RECONSTRUCTION: cached operating inputs; current cash recursion.
# No original main/build or full-company scenario generator is included.
CACHE_ROWS = None
TAIL_ROWS = None
EVENT_DELTA_CASH = 0.0
TREASURY_SHARES = .003566367

from pathlib import Path

from copy import deepcopy

import argparse,json

SHARES=4.01133

CASH=13.1208052057+4.957272599+1.8638702753+.7

SHORT=12.5004688889

LONG=.340825

BASE={
 'revenue':[72,78,84.5,91,96.5], 'margin':[.07,.08,.09,.095,.10],
 'growthcap':[6,5.5,4.5,3,1], 'maintenance':[2.5,2.7,3,3.3,3.5],
 'da':[2.3,2.5,2.8,3.1,3.3], 'parentcap':[2.3,2.5,1.8,1,.7],
 'payout':[.2,.25,.3,.3,.35], 'fixed':[0,.65,0,0,0],
 'brandrev':[1,1.6,2.2,2.8,3.4], 'brandmargin':.05,
 'buyback':[.6636085757,0,0,0,0], 'subscription':[0]*5,
 'registered':[4.01133]*5, 'shares':SHARES,
 'cash':CASH, 'parentcash':11., 'parentretained':2.6796800999,
 'parentreserve':.9290301779, 'parentshort':7.5505157778,
 'wc_rate':.1, 'revenue_open':71.5612458114, 'tax':.25,
 'deposit':.015, 'interest':.038, 'parent_nopat_share':.45,
 'parent_da_share':.45, 'parent_wc_share':.4,
 'group_floor':5., 'parent_floor':1., 'sub_floor':3.,
 'full_nonrenewal':False, 'growth6_10':[.06,.055,.045,.035,.03],
 'marginal_roic':.15, 'steady_roic':.12, 'steady_g':.02,
 'maintenance_gap':.2, 'r':.105,
}

def statutory_profit(retained,earned,reserve,registered_capital):
    recovered=min(max(-retained,0),max(earned,0))
    appropriation=min(max(0,registered_capital*.5-reserve),max(earned-recovered,0)*.1)
    return retained+earned-appropriation,reserve+appropriation,appropriation

def brand_earnout(revenue,margin):
    return (1. if revenue>=5 else .5 if revenue>=3 else 0.) if margin>0 else 0.

def continuation(nopat,r,growth,roic,g,steady_roic,gap):
    assert r>g and roic>0 and steady_roic>0
    rows=[]; pv=0.
    for t,rate in enumerate(growth,1):
        new=nopat*(1+rate); invest=(new-nopat)/roic
        fcf=new-invest-gap; pv+=fcf/(1+r)**t
        rows.append({'year':t+5,'nopat':new,'growth':rate,'reinvestment':invest,'maintenance_gap':gap,'fcff':fcf})
        nopat=new
    steady=nopat*(1+g)*(1-g/steady_roic)-gap
    distant=steady/(r-g)/(1+r)**5
    return {'ev5':pv+distant,'explicit6_10_pv_at5':pv,'distant_pv_at5':distant,'year11_fcff':steady,'rows':rows}

def roll(spec):
    s=deepcopy(spec); cash=s['cash']; pc=s['parentcash']; retained=s['parentretained'];reserve=s['parentreserve']
    short=SHORT; ps=s['parentshort']; rev=s['revenue_open']; rows=[]
    cal28=.75*s['brandrev'][1]+.25*s['brandrev'][2]
    earnout=brand_earnout(cal28,s['brandmargin'])
    for i in range(5):
        opening=cash; po=pc; so=short; pso=ps
        revenue=CACHE_ROWS[i]['revenue']; nopat=CACHE_ROWS[i]['nopat']
        netinterest=(opening*s['deposit']-(short+LONG)*s['interest'])*(1-s['tax'])
        ni=nopat+netinterest; wc=CACHE_ROWS[i]['wc']; da=CACHE_ROWS[i]['da']
        op=ni+da-wc
        own=nopat*s['parent_nopat_share']+(po*s['deposit']-ps*s['interest'])*(1-s['tax'])
        pop=own+da*s['parent_da_share']-wc*s['parent_wc_share']
        legal,reserve,allocation=statutory_profit(retained,own,reserve,s['registered'][i])
        cap=s['growthcap'][i]+s['maintenance'][i]; pcap=s['parentcap'][i]
        acquisition=s['fixed'][i]+(earnout if i==2 else 0.)
        buy=s['buyback'][i]; sub=s['subscription'][i]
        gpre=opening+op-cap-acquisition-buy+sub
        ppre=po+pop-pcap-acquisition-buy+sub
        repay=short
        if s['full_nonrenewal']:
            net=short
        elif i>=2:
            net=min(short,2.,max(0,gpre-7.))
        else: net=0.
        renewal=repay-net
        prep=ps; pnet=net*ps/short if short>0 else 0.; prenew=prep-pnet
        srep=repay-prep; srenew=renewal-prenew
        gpre-=net; ppre-=pnet; short-=net; ps-=pnet
        # Treasury support increases subsidiary cash but never parent profit or group cash.
        support=max(0,ppre-(gpre-s['sub_floor']))
        ppre-=support
        requested=max(0,ni)*s['payout'][i]
        dividend=max(0,min(requested,gpre-s['group_floor'],ppre-s['parent_floor'],max(0,legal)))
        cash=gpre-dividend; pc=ppre-dividend; retained=legal-dividend
        subclose=(opening-po)+(op-pop)-(cap-pcap)-srep+srenew+support
        # Acquisition/buyback/subscription all borne by parent; their net group/sub difference is zero.
        conservation=(opening+op-cap-acquisition-buy+sub-repay+renewal-dividend)-cash
        parentcheck=(po+pop-pcap-acquisition-buy+sub-prep+prenew-support-dividend)-pc
        assert abs(conservation)<1e-9 and abs(parentcheck)<1e-9
        assert abs(subclose-(cash-pc))<1e-9
        assert cash>=s['group_floor']-1e-9 and pc>=s['parent_floor']-1e-9 and subclose>=s['sub_floor']-1e-9, (i,cash,pc,subclose)
        rows.append(dict(year=i+1,period=f'{2026+i}-10/{2027+i}-09',revenue=revenue,margin=s['margin'][i],nopat=nopat,ni=ni,da=da,wc=wc,operating_cash=op,growth_capex=s['growthcap'][i],maintenance_capex=s['maintenance'][i],capex=cap,acquisition=acquisition,buyback=buy,subscription=sub,cash_open=opening,bank_debt_open=so+LONG,external_short_repayment=repay,external_short_renewal=renewal,net_short_repayment=net,dividend_requested=requested,dividend=dividend,dps=dividend/s['shares'],cash_close=cash,bank_debt_close=short+LONG,parent_cash_open=po,parent_own_profit=own,parent_operating_cash=pop,parent_capex=pcap,parent_short_open=pso,parent_short_repayment=prep,parent_short_renewal=prenew,parent_short_close=ps,parent_support_downstream=support,parent_cash_close=pc,parent_legal_before_distribution=legal,parent_retained_close=retained,parent_reserve=reserve,parent_appropriation=allocation,registered_capital=s['registered'][i],subsidiary_short_repayment=srep,subsidiary_short_renewal=srenew,subsidiary_cash_close=subclose,upstream_dividend=0.,nci_distribution=0.,conservation_error=conservation,parent_conservation_error=parentcheck))
        rev=revenue
    return {'assumptions':s,'npfg_calendar2028_revenue':cal28,'npfg_contingent':earnout,'rows':rows}

def value(result,r=None):
    s=result['assumptions']; r=s['r'] if r is None else r; end=result['rows'][-1]
    c=continuation(end['nopat'],r,s['growth6_10'],s['marginal_roic'],s['steady_g'],s['steady_roic'],s['maintenance_gap'])
    netcash=end['cash_close']-end['bank_debt_close']; terminal=(c['ev5']+netcash)/s['shares']
    divpv=sum(row['dps']/(1+r)**(i+1) for i,row in enumerate(result['rows']))
    terminalpv=terminal/(1+r)**5
    return dict(r=r,value_per_share=divpv+terminalpv,dividend_pv=divpv,terminal_pv=terminalpv,terminal_per_share=terminal,terminal_net_cash=netcash,terminal_pv_fraction=terminalpv/(divpv+terminalpv),distant_value_fraction=c['distant_pv_at5']/s['shares']/(1+r)**5/(divpv+terminalpv),continuation=c)


import importlib.util,sys,stat,os
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
CODE='301498'
CHECKER_NAME='2026-Q3-capital-20261102-check.py'
CHECKER_SHA='92db3706e84473b18f33a5a07d458ab5be8837a652f464a46e8181ed359db8c1'
EVENT={'book_vs_transaction_basis_difference_not_verified_fee': '9874.83', 'fees': 'Transaction figures exclude fees; no unsupported exact fee invented', 'model_shares_unchanged': '401133000', 'old_model_future_book_based_budget': '66360857.57', 'opening_q3_cash_unchanged': True, 'paid_transaction_oct31': '49988835.60', 'paid_transaction_q3': '33629267.60', 'post_q3_paid_transaction': '16359568.00', 'post_q3_total_transaction_budget': '66370732.40', 'preserved_minimum_transaction_budget': '100000000.00', 'remaining_transaction_budget_after_oct31': '50011164.40', 'shares_added_to_treasury_since_q3': '425900', 'source_ids': ['1225596515', '1225652027']}
OUTPUT_META={'classification': 'NEW_RECONSTRUCTION_NOT_OLD189_BYTE_RECOVERY', 'event': {'book_vs_transaction_basis_difference_not_verified_fee': '9874.83', 'fees': 'Transaction figures exclude fees; no unsupported exact fee invented', 'model_shares_unchanged': '401133000', 'old_model_future_book_based_budget': '66360857.57', 'opening_q3_cash_unchanged': True, 'paid_transaction_oct31': '49988835.60', 'paid_transaction_q3': '33629267.60', 'post_q3_paid_transaction': '16359568.00', 'post_q3_total_transaction_budget': '66370732.40', 'preserved_minimum_transaction_budget': '100000000.00', 'remaining_transaction_budget_after_oct31': '50011164.40', 'shares_added_to_treasury_since_q3': '425900', 'source_ids': ['1225596515', '1225652027']}, 'event_asof': '2026-11-02', 'event_input_sha256': 'a9066dcee15bb2d581c6beb08786a203d576365544e8b16d7b3137f8fcdf3169', 'historical_field_roles': {}, 'old_diagnostics_are_historical_not_updated': True, 'operating_forecast_recomputed': False, 'original_baseline_sha256': 'fd99d77bf59c34b31502eb38e113e90498a9c601401622bfebaf25e7df24c0c1', 'period': '2026-Q3', 'scope': 'base5 cash +3 original discount endpoints; other13 historical', 'scope_note': 'Original full company forecast dispatcher not executed; operating rows reused. Original finite terminal/NOPAT and normalized earning-power formulas are evaluated where required for selected cash valuation, not called new researched forecasts.', 'symbol': 'CN:301498', 'public_delivery_note': 'New reconstruction of selected current cash from exact published operating budgets. Old unselected diagnostics remain historical. This is not recovery of the lost original189 bytes.'}

def selected_cash(old,event,changed):
    m=sys.modules[__name__]
    saved = old['scenarios']['base']
    spec = copy.deepcopy(saved['assumptions'])
    if changed:
        spec['buyback'][0] = float(event['post_q3_total_transaction_budget'])/1e8
    m.CACHE_ROWS = saved['rows']
    base = m.roll(spec)
    for key in ('valuation', 'low', 'high'):
        base[key] = m.value(base, saved[key]['r'])
    result = {'base': base}
    oracle = {'base': saved}
    projection = result
    scope = 'base5 cash +3 original discount endpoints; other13 historical'

    return result,projection,oracle,scope

#!/usr/bin/env python3
"""Literal independent cash/legal rebuild; no official functions or input imports."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'research/companies/CN/688475/models'

def rebuild(md=0.,years=61):
    rev=[3500.,1300.,500.,600.,850.]; rates=[.05,.13,.03,.08,.15]; margins=[.42,.49,.25,.72,.72]
    pc=2314.40609369; sc=3968.35261672-pc; pr=397.18677070; sr=1000.; pres=173.85715231; sres=30.
    loan=1555.79576224; debt=21.; oldrev=6259.14558695; oldmin=.1*oldrev; bv=6091.70646697; ppe=2454.79436444; liability=493.40713005
    other=bv-3968.35261672+21.+12.46136551+liability-ppe; rows=[]
    for y in range(1,years+1):
        if y>1: rev=[v*(1+(g if y<=5 else .02+(g-.02)*max(0,(15-y)/10))) for v,g in zip(rev,rates)]
        sales=sum(rev); change=sales-oldrev; minimum=.1*sales
        op=(sum(v*(m+md) for v,m in zip(rev,margins))-sales*(.165+.145+.04+.01+.005+.004-.009))*.88
        da=190*sales/6750; capex=da+max(change,0)*(.15 if y<=5 else .25)+(9.121 if y==1 else 0)
        wc=.3*change-([150,100][y-1] if y<=2 else 0); pay=493.40713005*([.6,.4][y-1] if y<=2 else 0)
        fcf=op+da-capex-wc-pay; po=120*sales/6750; so=op-po
        pi=pc*.01; si=sc*.01; interest=debt*.04; il=loan*.03; pinet=il*.75; sinet=il-min(il,max(so,0)/.85)*.15; wedge=sinet-pinet
        collection=5.24429857 if y==1 else 0
        pc+=po+pi+pinet+collection+.25*(da-capex-pay)-.7*wc
        sc+=so+si-interest-sinet+.75*(da-capex-pay)-.3*wc
        dedicated=max(0,526.4-(493.40713005-liability)-pay-9.121) if y<3 else 0
        pm=.6*minimum+12.46136551; sm=.4*minimum+dedicated
        assert pc>=pm and sc>=sm  # This independent base/margin diagnostic requires no new funding.
        repayloan=min(200,loan,max(0,sc-sm)); pc+=repayloan;sc-=repayloan;loan-=repayloan
        sn=so+si-interest-sinet; sr+=sn
        a=min(.1*max(0,min(sn,sr)),max(0,75-sres));sr-=a;sres+=a
        up=min((max(sn,0)*.70 if y<=5 else max(sr,0)),max(sr,0),max(0,sc-sm))
        sr-=up;sc-=up;pc+=up
        pn=po+pi+pinet+up;pr+=pn
        a=min(.1*max(0,min(pn,pr)),max(0,393.75-pres));pr-=a;pres+=a
        ni=op+pi+si-interest-wedge
        request=max(ni,0)*.55 if y<=5 else max(0,fcf-(minimum-oldmin)+pi+si-interest-wedge)
        ordinary=min(request,max(pr,0),max(pc-pm,0));pr-=ordinary;pc-=ordinary
        extra=min(max(pr,0),max(pc-pm,0)) if y>=6 else 0;pr-=extra;pc-=extra
        paid=ordinary+extra
        repay=min(debt,max(0,sc-sm));sc-=repay;debt-=repay
        bv+=ni-paid;ppe+=capex-da;other+=wc-collection;liability-=pay
        assert abs(pc+sc-debt-12.46136551-liability+ppe+other-bv)<1e-6
        rows.append(dict(year=y,revenue=sales,nopat=op,cash_dividend=paid,ordinary_dividend=ordinary,additional_principal_release_dividend=extra,parent_cash=pc,subs_cash=sc,parent_retained=pr,subs_retained_budget=sr,parent_reserve=pres,subs_reserve_budget=sres,internal_loan_balance=loan,internal_interest_tax_wedge=wedge,book_equity=bv,upstream_dividend_declared_and_collected=up,cash_min=minimum))
        oldrev=sales;oldmin=minimum
    values=[]
    for k in [.105,.095,.10]:
        constant=12.46136551*.01
        terminal=(rows[-1]['cash_dividend']-constant)/(k-.02)+constant/k
        tv=sum(r['cash_dividend']/(1+k)**(r['year']-5) for r in rows[5:-1])+terminal/(1+k)**(years-1-5)
        pv=sum(r['cash_dividend']/(1+k)**r['year'] for r in rows[:5])+tv/(1+k)**5
        values.append(dict(k=k,value=pv/787.5,tv5=tv/787.5))
    return dict(values=values,annual_entity_states=rows)


def test_ezviz_literal_inputs_full_tail():
    out={'base':rebuild(),'margin_minus_1pp':rebuild(-.01)}
    
    reference=json.loads((ROOT/'2026-Q3-output.json').read_text())
    errors=[]
    for name,calc in out.items():
        official=reference['scenarios'][name]
        for a,b in zip(calc['values'],official['valuation_endpoints']+[official['central']]): errors += [abs(a['value']-b['value_per_share']),abs(a['tv5']-b['terminal_year5_per_share'])]
        for a,b in zip(calc['annual_entity_states'],official['trajectory']['rows']):
            errors.extend(abs(v-b[k]) for k,v in a.items())
    convergence=[]
    for n in [81,101]:
        alt=rebuild(years=n)
        convergence.append({'years':n,'values':alt['values'],'max_delta_vs_61':max(abs(a[k]-b[k]) for a,b in zip(alt['values'],out['base']['values']) for k in ['value','tv5'])})
    assert max(errors)<1e-7,max(errors)
    assert max(x['max_delta_vs_61'] for x in convergence)<1e-9
    out.update(max_absolute_difference=max(errors),convergence=convergence,result='PASS: literal base and 1pp margin, both endpoints/TV5, 61 yearly entity states, 81/101-year closure')

def test_ezviz_actual_functions_and_principal_chain():
 import runpy,pytest
 m=runpy.run_path(str(ROOT/'2026-Q3.py'));m['tests']()
 o=json.loads((ROOT/'2026-Q3-output.json').read_text());base=o['scenarios']['base'];r=base['trajectory']['rows']
 assert base['central']['all_financial_excess_released_by_year']==20
 assert base['central']['terminal_cash_closed']
 excess=r[4]['group_cash']-r[4]['cash_min']-12.46136551
 assert sum(x['additional_principal_release_dividend'] for x in r[5:])==pytest.approx(excess,abs=1e-7)
 assert r[7]['internal_loan_balance']==0
 assert not o['scenarios']['funding_failure']['trajectory']['feasible']

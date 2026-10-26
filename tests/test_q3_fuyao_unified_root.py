"""Literal reconstruction: does not import production functions or read their configs."""
import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"research/companies/CN/600660/models"
import importlib.util
import pytest

def literal(rate=.095,margin=.18):
    cash=21.806995594; debt=22.562762740;parent=19.304904628;retained=8.667059178-.7314667124;reserves=5.020531741+.7314667124;ar=.073878614;prev=46.5
    rows=[];divs=[]
    for j,(rev,cap,da) in enumerate(zip([47,50,53,56,58.8],[6.3,6,5.7,5.3,5],[3,3.3,3.5,3.7,3.9]),1):
        n=rev*margin
        op=n-cap+da-.12*(rev-prev)
        interest=.016*cash-.024*debt
        declaration=.75*n;charge=.01*declaration
        fce=op+interest-charge;profit=n+interest-charge
        received=declaration;old_collection=.9*ar;ar-=old_collection
        pprofit=declaration-.35-charge
        appropriation=.1*max(0,pprofit)
        retained+=pprofit-appropriation;reserves+=appropriation
        parent+=received+old_collection-1.45-charge
        dividend=max(0,min(.6*profit,fce,cash+fce-.08*rev,parent-3,retained))
        assert cash+fce-dividend>=.08*rev and parent-dividend>=3
        cash+=fce-dividend;parent-=dividend;retained-=dividend
        divs.append(dividend);rows.append(dict(cash=cash,parent=parent,retained=retained,reserves=reserves,dividend=dividend));prev=rev
    n=58.8*margin;ev=0;factor=.9+.1*.97/(1+rate)**3
    for t,g in enumerate([.04,.035,.03,.0275,.025],1):
        n*=1+g;f=n*(1-g/.15);ev+=.99*f*factor/(1+rate)**t
    terminal=n*1.025*(1-.025/.15)*.99*factor/(rate-.025)
    ev+=terminal/(1+rate)**5
    liquid=min(cash-4.704,parent-3);other=cash-4.704-liquid
    fin=liquid+other*.97/(1+rate)**3-debt
    tv=(ev+fin)/2.609743532
    pv=sum(d/(1+rate)**t for t,d in enumerate(divs,1))/2.609743532+tv/(1+rate)**5
    return dict(pv=pv,tv=tv,rows=rows,ev5=ev,tail10=terminal)


@pytest.mark.parametrize("key,rate,margin",[("base",.095,.18),("core_low",.10,.18),("core_high",.09,.18),("margin_minus_100bp",.095,.17)])
def test_fuyao_literal_full_parent_cash(key,rate,margin):
    own=literal(rate,margin)
    actual=json.loads((ROOT/"2026-Q3-output.json").read_text())[key]
    assert own["pv"]==pytest.approx(actual["current_value"],abs=1e-11)
    assert own["tv"]==pytest.approx(actual["terminal_per_share"],abs=1e-11)
    for a,b in zip(own["rows"],actual["rows"],strict=True):
        for x,y in [("cash","cash"),("parent","parent_cash"),("retained","parent_legal_profit"),("reserves","parent_statutory_reserve"),("dividend","dividend")]:
            assert a[x]==pytest.approx(b[y],abs=1e-11)

def test_fuyao_production_functions_and_own_debt_bridge():
    spec=importlib.util.spec_from_file_location("fuyao",ROOT/"2026-Q3.py")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    m.tests()
    assert m.PARENT_EXTERNAL_DEBT==pytest.approx(9.971459299,abs=1e-12)
    all_results=json.loads((ROOT/"2026-Q3-output.json").read_text())
    for b in all_results.values():
        if not isinstance(b,dict) or "rows" not in b:continue
        z=b["parent_financial_bridge"]
        assert z["parent_delayed_realization"]==0
        assert z["debt_repaid"]<=9.971459299+1e-12
        assert z["profit_backed_distribution"]<=b["rows"][-1]["parent_legal_profit"]
        assert z["remaining_group_debt"]+z["debt_repaid"]==pytest.approx(b["rows"][-1]["debt"])
        r=b["rate"];lag=max(b["config"]["delay"],5 if b is all_results.get("slow_recovery") else 3)
        cost=.10 if b is all_results.get("slow_recovery") else .03
        expected=b["parent_excess_year5"]+b["child_excess_year5"]*(1-cost)/(1+r)**lag-b["rows"][-1]["debt"]
        assert expected==pytest.approx(b["financial_value_year5"],abs=1e-10)
    assert m.finance_step(0,-3,0,0,2) is None
    assert m.owner_cash(10,0,.09,.01)==9.9
    assert m.legal_step(0,2,10,20,policy=0)[0]==2

def test_fuyao_all_future_cash_cohorts_have_finite_realization():
    out=json.loads((ROOT/"2026-Q3-output.json").read_text())
    for key in ["base","structural","upside","no_us_remit"]:
        b=out[key];r=b["rate"];g=b["tail_growth"];n=b["tail_rows"][-1]["nopat"]
        # Independently price cash at receipt year for all new annual cohorts.
        total=0
        for k in range(1,1201):
            free=n*(1+g)**k*(1-g/b["tail_roic"]-b["tail_extra_maintenance"])*(1-b["transfer_friction"])
            total+=free*(1-b["delayed_fraction"])/(1+r)**k
            total+=free*b["delayed_fraction"]*(1-b["recovery_cost"])/(1+r)**(k+b["recovery_lag"])
        assert total==pytest.approx(b["terminal_ev_year10"],abs=1e-9)

"""Independent literal full cash/legal economic loops, no production imports or input reads."""
from pathlib import Path
import json

def literal(rate=.10,shift=0.,structural=False,source_payout=.72,realize=.7,realize_guard=.3,release_year=10,release_loss=0.,mother_share=.10):
    initial=3.11039224728+1.23308011310+.38220270827+.35562269185-.9895-1.54880849806-.00364909872-.03593239247-.001477064-.015-.008
    pc=1.20;sc=initial-pc;pl=1.71515294101;sl=0.;ar=0.;restricted=.46
    shares=.505856969-.009460417;treasury=.009460417
    revs=[7.70,8.10,8.50,8.90,9.30];margins=[.093,.096,.097,.097,.097];caps=[.13,.10,.08,.08,.08];wcs=[.10,.072,.072,.072,.072];g=.02;tm=.097;payout=.70
    if structural:revs=[7.,6.8,6.6,6.5,6.5];margins=[.05,.035,.03,.03,.03];caps=[.08,.04,.03,.02,.02];wcs=[.20,.10,.05,0,0];g=0.;tm=.03;payout=.50;source_payout=.50
    margins=[m+shift for m in margins];tm+=shift
    out=[];priorrev=revs[0]
    for y in range(1,321):
        if y<=5:rev=revs[y-1];margin=margins[y-1];cap=caps[y-1];wc=wcs[y-1];minority=.005
        else:rev=revs[-1]*(1+g)**(y-5);margin=tm;cap=(rev-priorrev)*.5;wc=0.;minority=.005*(1+g)**(y-5)
        op=rev*margin-max(0.,rev*margin)*.25;mo=op*mother_share-(.15 if structural and y==1 else 0.);so=op*(1-mother_share)-minority
        mi=pc*.015;si=sc*.015;mf=mo+mi-.2*(cap+wc);sf=so+si-.8*(cap+wc)
        transfer=.30 if structural and y==1 else 0.;pc+=mf-transfer;sc+=sf+transfer
        restricted=max(0.,restricted-.8*cap);mg=sg=0.;unlock=0.;recovery=0.
        if y==release_year:
            unlock=restricted;sc-=restricted*release_loss;sg+=restricted*release_loss;restricted=0.
        if y==10:
            mb=.06056887145;sb=.21359620125-mb;pc+=mb*realize;sc+=sb*realize;recovery=.21359620125*realize;mg+=mb*realize_guard;sg+=sb*realize_guard
        sp=so+si-sg;eligible=max(0.,sp-max(0.,-sl));buffer=eligible*(.10 if y<=10 else 0.);sl+=sp-buffer
        floor=rev*(.8/7.4)-.30+restricted
        oldpaid=min(ar,max(0.,sc-floor));sc-=oldpaid;pc+=oldpaid;ar-=oldpaid
        extra=.10*max(0.,sc-floor-ar) if y>=6 else 0.
        declared=max(0.,min(sl,max(0.,so+si)*source_payout+extra,max(0.,sc-floor)/.75))
        paid=declared*.75;sl-=declared;ar+=declared-paid;sc-=paid;pc+=paid
        parent_profit=mo+mi+declared-mg;pl+=parent_profit
        buy=min(.05-.001477064,max(0.,pc-.3),max(0.,pc+sc-.3-floor)) if y==1 else 0.
        pc-=buy;shares-=buy/20;treasury+=buy/20
        eq=0.
        if y==2:eq=treasury*20;pc+=eq;shares+=treasury;treasury=0.
        target=max(0.,op-minority)*payout+(.10*max(0.,pc-.3) if y>=6 else 0.)
        dividend=min(target,max(0.,pl),max(0.,pc-.3),max(0.,pc+sc-.3-floor));pc-=dividend;pl-=dividend
        assert pc>=.3-1e-9 and sc>=floor-1e-9
        out.append(dict(year=y,parent_cash=pc,subs_cash=sc,parent_retained=pl,source_earnings_budget=sl,dividend_receivable=ar,declaration=declared,distribution=dividend,dps=dividend/shares,restricted=restricted,restriction_unlocked=unlock,illiquid_net_recovery=recovery,parent_realization_guard=mg,source_realization_guard=sg,shares=shares))
        priorrev=rev
    pv=sum(z['dps']/(1+rate)**z['year'] for z in out);tv=sum(z['dps']/(1+rate)**(z['year']-5) for z in out[5:]);return dict(value=pv,terminal=tv,rows=out)


import importlib.util,copy
import pytest
ROOT=Path(__file__).resolve().parents[1]/"research/companies/CN/002557/models"
@pytest.mark.parametrize("path,kw",[
 ("core/0.105",{"rate":.105}), ("core/0.1",{}),("core/0.095",{"rate":.095}),
 ("sensitivity/margin_minus_1pp",{"shift":-.01}),
 ("scenario_values/structural",{"rate":.115,"structural":True}),
 ("capital_governance/source_half_payout",{"source_payout":.36}),
 ("capital_governance/illiquid_recovery_50pct",{"realize":.5,"realize_guard":.5}),
 ("capital_governance/structural_restriction_late_loss",{"rate":.115,"structural":True,"release_year":15,"release_loss":.1}),
 ("capital_governance/parent_operating_zero",{"mother_share":0.}),
 ("capital_governance/parent_operating_5pct",{"mother_share":.05})])
def test_qiaqia_literal_320_year_cash_legal_and_value(path,kw):
    own=literal(**kw)
    target=json.loads((ROOT/"2026-Q3-output.json").read_text())
    for k in path.split('/'):target=target[k]
    assert own['value']==pytest.approx(target['value'],abs=1e-10)
    assert own['terminal']==pytest.approx(target['terminal'],abs=1e-10)
    for a,b in zip(own['rows'],target['explicit_rows']+target['tail_rows'],strict=True):
        for k in a:assert a[k]==pytest.approx(b[k],abs=1e-8)

def test_qiaqia_actual_negative_tax_and_funding_failure_and_future_cash():
    sp=importlib.util.spec_from_file_location('qiaqia',ROOT/'2026-Q3.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
    assert m.production_tests()['negative_operating_tax_test']==-.5
    q=copy.deepcopy(m.BASE);q['margins']=[-.15]*5;q['debt_limit']=0
    actual=m.run(q)
    assert actual['rows'][0]['nopat']==pytest.approx(-1.155)
    out=json.loads((ROOT/'2026-Q3-output.json').read_text())
    fail=out['paths']['liquidity_failure'];assert not fail['feasible'] and fail['failure_year']==1
    assert fail['rows'][0]['unfunded_even_zero_dividend']==pytest.approx(.8188177645736825)
    assert out['scenario_values']['liquidity_failure']['value'] is None
    for v in list(out['core'].values())+list(out['scenario_values'].values())+list(out['capital_governance'].values()):
        if not v.get('asset_recovery'):continue
        for cohort in v['asset_recovery']['later_cash_cohorts'].values():assert cohort['unpaid']<1e-7
    assert out['scenario_values']['structural']['tail_rows'][0]['maintenance']>0
    assert out['scenario_values']['structural']['tail_rows'][0]['growth_capex']==0

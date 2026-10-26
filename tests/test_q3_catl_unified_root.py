"""Independent literal reconstruction and actual terminal capacity."""
import json
from pathlib import Path
import pytest
P=Path(__file__).resolve().parents[1]/"research/companies/CN/300750/models"
def rebuild(rate=.095,growth=.025,mult=1,extra=0,cycle=False,collect=.75,opening_parent=100,cost=.02,optional=0,buyback=16.697,share_start=4.616304838):
    earnings=[78,87.01,96.78,106.60,115.10]
    capital=[42,44,45,46,47]
    for gr,ret in [(0.06,.16),(.05,.15),(.04,.14),(.03,.13),(.03,.12)]:
        previous=earnings[-1]; earnings.append(previous*(1+gr));capital.append(previous*gr/ret)
    net=369.813786+62.779978+.629346-1.646355-39.897579-16.8711-76.354823-52.737747-4.064886-90-15-1.632147
    sh=share_start-buyback/300
    a=opening_parent;b=net-a;re=145.440692-4.598335875*1.411;res=2.313325;registration=4.65;ar=.008228;loan=132.661171;invest=19.9788624
    pays=[];states=[]
    for t in range(10):
        start=a+b; ia=.02*a;ib=.02*b
        p=earnings[t]*mult-(20 if cycle and t==0 else 15 if cycle and t==1 else 0)
        f=p-capital[t]*mult-(extra if t<5 else 0)
        a+=ia+.55*f;b+=ib+.45*f
        announced=min(max(0,.22*p if t<5 else .45*f),max(0,b-ar))
        ar+=announced
        collected=min(max(0,b),ar*(collect if t<5 else 1));ar-=collected;a+=collected;b-=collected
        profit=.55*p+announced+ia
        eligible=max(0,profit+min(re,0));required=min(eligible/10,max(0,registration/2-res));res+=required;re+=profit-required-optional*eligible
        if t==0:a-=buyback;registration-=buyback/300
        if t<5:desired=[8.5,9.5,10.5,12,13][t]*sh
        else:
            principal=min(max(0,b-ar)/(10-t),loan);b-=principal;a+=principal;loan-=principal
            sold=invest/(10-t);invest-=sold;a+=sold*(1-cost);re-=sold*cost
            desired=max(0,f+ia+ib)+(max(0,start)+19.9788624)/5
        paid=min(desired,max(0,a),max(0,re));a-=paid;re-=paid;pays.append(paid/sh);states.append([a,b,re,res,ar])
    residual=(a+b+invest)*(1-cost)
    forever=earnings[-1]*mult*(1+growth)*(1-growth/.12)/(rate-growth)
    future=(forever+residual/(1+rate)**2)/sh
    pv=sum(pays[t]/(1+rate)**(t+1) for t in range(10))+future/(1+rate)**10
    tv=sum(pays[t]/(1+rate)**(t-4) for t in range(5,10))+future/(1+rate)**5
    return dict(PV=pv,TV5=tv,D=pays[:5],states=states)

spec={'base':{},'core_low':dict(rate=.10,growth=.02),'core_high':dict(rate=.09,growth=.03),'cycle':dict(cycle=True),'structural':dict(rate=.105,growth=.015,mult=.7,extra=10),'optimistic':dict(rate=.09,growth=.03,mult=1.15),'discount_plus1pp':dict(rate=.105),'extra_reinvestment10':dict(extra=10),'operating_cash_minus10pct':dict(mult=.9),'upstream_delay':dict(collect=.25),'parent_cash_minus30':dict(opening_parent=70),'joint_transfer_stress':dict(opening_parent=40,collect=.25),'realisation_friction10pct':dict(cost=.1),'voluntary_reserve10pct':dict(optional=.1),'no_further_buyback':dict(buyback=0)}


def test_catl_literal_all_scenarios():
    computed={k:rebuild(**v) for k,v in spec.items()}
    production=json.loads((P/'2026-Q3-output.json').read_text())
    for key,value in computed.items():
        actual=production[key]
        assert value['PV']==pytest.approx(actual['PV'],abs=1e-9)
        assert value['TV5']==pytest.approx(actual['TV5'],abs=1e-9)
        assert value['D']==pytest.approx(actual['D'],abs=1e-10)
        for state,row in zip(value['states'],actual['rows']):
            assert state==pytest.approx([row[k] for k in ['closing_parent_cash','closing_remote_cash','closing_parent_retained','closing_statutory_reserve','closing_dividend_receivable']],abs=1e-8)

def test_catl_finite_principal_and_actual_tail_capacity():
    production=json.loads((P/'2026-Q3-output.json').read_text())
    for key in spec:
        c=production[key]
        assert c['feasible']
        assert c['realisation_rows'][-1]['closing_financial']==pytest.approx(0,abs=1e-8)
        assert c['terminal_parent_legal_capacity']*(1-c['parameters']['voluntary'])>=c['terminal_cash']-1e-8
        assert c['rows'][-1]['closing_remote_cash']==pytest.approx(0,abs=1e-8)
        r=c['parameters']['r']
        assert c['PV']==pytest.approx(sum(d/(1+r)**(i+1) for i,d in enumerate(c['D']))+c['TV5']/(1+r)**5)
    assert production['structural']['D'][-1]<13
    assert production['joint_transfer_stress']['D'][1]<9.5

#!/usr/bin/env python3
"""CATL ordinary-owner model. CNY billion; shares billion. Standard library only.
Parent legal gate is a forecast, not audited future accounts. Other operations
are economic budgets, NEVER legal entities or consolidated reserve pools.
"""
import json, math
S0=4.627250-.010945162
BB=16.697
FIN=369.813786+62.779978+.629346-1.646355-(39.897579+16.871100+76.354823+52.737747+4.064886)-90-15-1.632147
OTHER=(13.148849+11.824729)*.8
P=[78,87.01,96.78,106.6,115.1]
I=[42,44,45,46,47]
for g,k in zip([.06,.05,.04,.03,.03],[.16,.15,.14,.13,.12]):
 P.append(P[-1]*(1+g)); I.append((P[-1]-P[-2])/k)

def legal_step(retained,reserve,registered,profit,voluntary=0):
    """Negative retained absorbs new profit first; threshold is registered, not paid."""
    eligible=max(0.,profit+min(0.,retained))
    statutory=min(.1*eligible,max(0.,.5*registered-reserve))
    optional=max(0.,voluntary)*eligible
    return retained+profit-statutory-optional,reserve+statutory,statutory,optional

def disposal(proceeds,cost,expense,tax,ownership):
    gain=proceeds-cost-expense
    taxcash=max(0.,gain)*tax
    return dict(capital=cost*ownership,gain=gain*ownership,tax=taxcash*ownership,cash=(proceeds-expense-taxcash)*ownership)

def capital_reduce(cash,registered,shares,amount,retired,fee):
    assert 0<=amount+fee<=cash and 0<=retired<=shares
    return cash-amount-fee,registered-retired,shares-retired,amount

def transfer(old_receivable,new_declaration,collection):
    assert 0<=collection<=old_receivable+new_declaration+1e-9
    return old_receivable+new_declaration-collection,new_declaration,collection

def run(r=.095,g=.025,scale=1.,extra=0.,cycle=False,upstream=.75,release_end=10,friction=.02,parent_start=100.,parent_earn=.55,bb=BB,shares0=S0,reg=4.65,voluntary=0.):
    # Upper-bound registered budget 4.65: known Q3 book share capital4.627250;
    # registration date unverified. Using upper bound cannot fabricate cash.
    shares=shares0-bb/300
    total=FIN; parent=min(parent_start,total); remote=total-parent
    retained=145.440692-4.598335875*1.411; reserve=2.313325
    receivable=.008228; intercompany=132.661171
    rows=[]; feasible=True; initial_other=OTHER; other=OTHER
    for n in range(1,11):
        op=P[n-1]*scale
        invest=I[n-1]*scale+(extra if n<=5 else 0)
        disruption=20 if cycle and n==1 else 15 if cycle and n==2 else 0
        op-=disruption
        owner=op-invest
        # Existing financial debt netted once at inception; normal refinancing
        # keeps net debt constant. No new borrowing is available to fill gaps.
        opening=parent+remote
        py=parent*.02; ry=remote*.02
        own_cash=.55*owner; remote_cash=.45*owner
        parent+=py+own_cash; remote+=ry+remote_cash
        declared=(.22*op if n<=5 else max(0.,remote_cash))
        # Forecast declaration bounded by source cash, no made-up entity reserves.
        declared=min(max(0.,declared),max(0.,remote-receivable))
        receipt=min(max(0.,remote),max(0.,receivable+declared)* (upstream if n<=5 else 1))
        receivable,declared,receipt=transfer(receivable,declared,receipt)
        remote-=receipt; parent+=receipt
        # Deployment already subtracted at group level. Parent-side forecast
        # profits separate from cash: cost-method new dividends, never old receipts.
        legal_profit=parent_earn*op+declared+py
        retained,reserve,stat,opt=legal_step(retained,reserve,reg,legal_profit,voluntary)
        buyback=bb if n==1 else 0.
        # Cancellation at year-end; registered legal budget falls by face value,
        # not by buyback market consideration. Continuing holders do not get BB.
        if buyback:
            if parent<buyback: feasible=False
            if parent>=buyback:
                parent,reg,postshares,_=capital_reduce(parent,reg,shares0,buyback,bb/300,0.)
                assert abs(postshares-shares)<1e-10
            else:
                parent-=buyback; reg-=bb/300
        realised=0.; friction_cash=0.; cap_repayment=0.; gain=0.; sale_tax=0.
        if n>=6:
            remaining=max(1,release_end-n+1)
            cap_repayment=min(max(0.,remote-receivable)/remaining,intercompany)
            remote-=cap_repayment; parent+=cap_repayment; intercompany-=cap_repayment
            # Financial investment marked at already haircut value. Sell in equal
            # installments, basis equal to carried forecast value: no new gain.
            realised=other/remaining
            sale=disposal(realised,realised,realised*friction,0.25,1.)
            other-=realised; parent+=sale['cash']; friction_cash=realised*friction
            gain=sale['gain']; sale_tax=sale['tax']
            retained+=gain-sale_tax
            wanted=max(0.,owner+py+ry)+(max(0.,opening)+initial_other)/5 if n<=release_end else max(0.,owner+py+ry)
            # Faster target only distributes available cash/legal profits.
        else: wanted=[8.5,9.5,10.5,12,13][n-1]*shares
        available=max(0.,parent)
        dividend=min(wanted,available,max(0.,retained))
        parent-=dividend; retained-=dividend
        total=parent+remote
        gap=max(0.,-parent)+max(0.,-remote)
        if gap>1e-9: feasible=False
        assert abs(total-(opening+py+ry+owner-buyback-dividend+realised-friction_cash-sale_tax))<1e-7
        assert abs(parent+remote-total)<1e-8
        rows.append(dict(year=n,operating_profit=op,reinvestment=invest,cycle_cash_loss=disruption,owner_cash=owner,opening_financial=opening,parent_own_cash=own_cash,remote_economic_cash=remote_cash,parent_fin_income=py,remote_fin_income=ry,new_dividend_declaration=declared,dividend_receipt=receipt,closing_dividend_receivable=receivable,parent_legal_profit=legal_profit,statutory_reserve_addition=stat,voluntary_reserve_addition=opt,closing_statutory_reserve=reserve,registered_budget=reg,closing_parent_retained=retained,intercompany_principal_repayment=cap_repayment,closing_intercompany_receivable=intercompany,financial_disposal_proceeds=realised,financial_disposal_basis=realised,disposal_gain=gain,disposal_tax=sale_tax,realisation_cost=friction_cash,other_financial=other,buyback=buyback,dividend=dividend,dps=dividend/shares,closing_parent_cash=parent,closing_remote_cash=remote,closing_financial=total,shares=shares,new_financing=0.,cash_gap=gap,legal_dividend_shortfall=max(0.,wanted-dividend)))
    # Remaining net financial wealth is realised by a 2-year orderly transfer /
    # sale budget, not locked behind a century of invented subsidiary profit.
    # It is NOT added at par at t10; no operating principal is liquidated.
    residue=parent+remote+other
    residual_cost=residue*friction
    residual_paid=min(max(0.,residue-residual_cost),max(0.,retained-residual_cost))
    # All observed scenarios have remote=0 by year10 and ample parent profits.
    # An unpayable residue is a failed scenario, not silently valued at par.
    feasible &= remote < 1e-8 and abs(residual_paid-(residue-residual_cost)) < 1e-8
    residual_pv10=residual_paid/(1+r)**2
    realisation_rows=[dict(year=11,opening_financial=residue,distribution=0.,closing_financial=residue,new_profit=0.,new_financing=0.),dict(year=12,opening_financial=residue,realisation_cost=residual_cost,distribution=residual_paid,dps=residual_paid/shares,closing_financial=residue-residual_cost-residual_paid,new_profit=-residual_cost,closing_parent_retained=retained-residual_cost-residual_paid,new_financing=0.)]
    terminal_profit=P[-1]*scale*(1+g)
    terminal_cash=terminal_profit*(1-g/.12)
    terminal_operating=terminal_cash/(r-g)
    # Normal tail requires parent cash/profit >= distributions. Parent own
    # profit + source cash declarations >= total owner cash because op>=FCF.
    tail_legal_capacity=parent_earn*terminal_profit+.45*terminal_cash
    tail_legal_pass=tail_legal_capacity>=terminal_cash-1e-9
    feasible &= tail_legal_pass
    tv10=(terminal_operating+residual_pv10)/shares
    pv=sum(x['dps']/(1+r)**x['year'] for x in rows)+tv10/(1+r)**10
    tv5=sum(x['dps']/(1+r)**(x['year']-5) for x in rows[5:])+tv10/(1+r)**5
    return dict(parameters=dict(r=r,g=g,scale=scale,extra=extra,cycle=cycle,upstream=upstream,release_end=release_end,friction=friction,parent_start=parent_start,parent_earn=parent_earn,bb=bb,shares0=shares0,voluntary=voluntary),rows=rows,PV=pv,TV5=tv5,D=[x['dps'] for x in rows[:5]],shares=shares,feasible=feasible,terminal_operating=terminal_operating,terminal_cash=terminal_cash,terminal_parent_legal_capacity=tail_legal_capacity,financial_residue10=residue,realisation_rows=realisation_rows,residue_realisation_year=12,residue_realisation_cost=residue*friction,residual_pv10=residual_pv10,TV_fraction=tv5/(1+r)**5/pv if pv else None,perpetuity_fraction=terminal_operating/shares/(1+r)**10/pv if pv else None)

def hand_tests():
    assert legal_step(0,5,20,10)[:3]==(9.,6.,1.) # paid10 is irrelevant
    assert legal_step(-8,0,20,10)[:3]==(1.8,.2,.2)
    assert legal_step(0,10,20,10)[:3]==(10.,10.,0.)
    assert legal_step(0,10,24,10)[2]==1
    assert transfer(5,0,5)==(0,0,5)
    assert capital_reduce(10,20,20,6,3,1)==(3,17,17,6)
    d=disposal(10,10,1,.25,.6)
    assert d==dict(capital=6.,gain=-.6,tax=0.,cash=5.3999999999999995)
    # actual whole-path function: initial liquidity zero is not inventively financed
    x=run(parent_start=0,parent_earn=0,scale=0,extra=200)
    assert not x['feasible'] and all(t['new_financing']==0 for t in x['rows'])
    return 'passed: registered/paid, loss, full reserve, registered increase, old receivable, capital/shares, minority disposal, no financing'

def main():
    specs={'base':{},'core_low':{'r':.10,'g':.02},'core_high':{'r':.09,'g':.03},'cycle':{'cycle':True},'structural':{'r':.105,'g':.015,'scale':.70,'extra':10},'optimistic':{'r':.09,'g':.03,'scale':1.15},'discount_plus1pp':{'r':.105},'extra_reinvestment10':{'extra':10},'operating_cash_minus10pct':{'scale':.9},'upstream_delay':{'upstream':.25},'parent_cash_minus30':{'parent_start':70},'joint_transfer_stress':{'parent_start':40,'upstream':.25},'realisation_friction10pct':{'friction':.10},'voluntary_reserve10pct':{'voluntary':.10},'no_further_buyback':{'bb':0}}
    out={k:run(**v) for k,v in specs.items()}
    assert out['core_low']['D']==out['core_high']['D']==out['base']['D']
    out['hand_tests']=hand_tests()
    aux=[]
    for r in [.10,.09]:
        multiple=sum(1.1**t*.5/(1+r)**(t+1) for t in range(5))+1.1**4*1.03*.75/(r-.03)/(1+r)**5
        realised_bridge=FIN*(1.02/(1+r))**7+OTHER*.98/(1+r)**7
        aux.append(dict(r=r,multiple=multiple,realised_bridge=realised_bridge,PV=(78*multiple+realised_bridge-BB/(1+r))/out['base']['shares']))
    out['auxiliary']=aux
    out['schema']='All monetary aggregates CNY bn, shares bn; PV/TV/D CNY/share. Annual rows retained in full; source budgets not legal entities.'
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

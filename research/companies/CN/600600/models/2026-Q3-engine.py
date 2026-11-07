#!/usr/bin/env python3
"""600600, CNY billion except per share/volume million kl. Stdlib, no input files.
All entity budgets are estimates, not undisclosed statutory accounts. No net new external borrowing (replacement leases only). A funding gap raises immediately. Equity injected into loss sources
is capital, never income or distributable reserve. Internal cash movements cancel.
"""
import json, copy, math
SHARES=1.364195121
ASOF='2026-10-28T21:00:00+08:00'
# Cash is externally backed treasury AFTER allocation of deposit/settlement claims;
# not sum of gross parent cash and finance-company gross financial assets.
OPEN={
 'parent':dict(cash=16.0,u=11.336138976,reserve=1.400704380,capital=1.364195121,floor=0.,share=1.),
 'xian':dict(cash=.80,u=.90,reserve=.118488364,capital=.236976728,floor=.02,share=1.),
 'shenzhen':dict(cash=.20,u=.15,reserve=.05,capital=.21,floor=.12,share=.51),
 'profitable_others':dict(cash=3.0,u=2.,reserve=.7,capital=2.,floor=0.,share=.97),
 'southeast_loss':dict(cash=.30,u=-.20,reserve=0.,capital=.40,floor=.10,share=1.),
 'finance':dict(cash=2.5,u=1.,reserve=.30,capital=3.,floor=3.35,share=1.)}
# Full gross external financial-resource bridge, no off-model discarded cash.
# 5.83 non-interest operational cash REPLACES 5.83 of the former 5.97
# operating floors; finance regulatory floor3.35 is separate. Budget not legal lock.
RING={'parent':4.,'xian':.33,'shenzhen':0.,'profitable_others':1.5,'southeast_loss':0.,'finance':0.}
EXIT={'parent_basis':.15,'reference_parent_cost_southeast_marketing':.299076285,
      'noncash_assets':.22,'old_liabilities':.32,'sale_proceeds':.10,
      'year4_debt_settlement':.22,'year5_debt_settlement':.10,
      'liability_budget_components':{'supplier':.12,'employee_accrual':.10,'lease_and_restoration':.10}}
BASE=dict(revenue=31.6,margin=.174,growth=.012,capex=2.,dep=1.40,r=.09,
          cash_yield=.0225,collection_lag=0,opening_scale=1.,sweep=.05,cycle=False,
          structural=False,optimistic=False,aux=False,legal_scale=1.,buffer_scale=1.,exit_basis=.15)
CASES={'base':BASE,
 'core_low':dict(BASE,margin=.170,growth=.008,r=.095),
 'core_high':dict(BASE,margin=.178,growth=.016,r=.085),
 'cycle':dict(BASE,cycle=True),
 'structural':dict(BASE,structural=True,margin=.148,growth=-.015,capex=2.2),
 'optimistic':dict(BASE,optimistic=True,margin=.190,growth=.022,capex=2.15),
 'discount_10pct':dict(BASE,r=.10),
 'margin_minus_100bp':dict(BASE,margin=.164),
 'faster_cash_return':dict(BASE,sweep=.20),
 'upstream_delay':dict(BASE,collection_lag=1),
 'legal_capacity_half':dict(BASE,legal_scale=.5),
 'treasury_less_3bn':dict(BASE,opening_scale=(22.5-3)/22.5),
 'operating_buffer_half':dict(BASE,buffer_scale=.5),
 'operating_buffer_zero':dict(BASE,buffer_scale=0.),
 'exit_basis_full_reference':dict(BASE,exit_basis=.299076285),
 'financial_yield_1pct':dict(BASE,cash_yield=.01),
 'terminal_low':dict(BASE,margin=.170,growth=.008,r=.095,prefix_base=True),
 'terminal_high':dict(BASE,margin=.178,growth=.016,r=.085,prefix_base=True),
 'aux_unit':dict(BASE,aux=True)}

def step(s,profit,cashflow,request,capital_in=0.,capital_out=0.,floor=None):
    """Production legal/cash waterfall: losses first, reserve second, D third."""
    old=copy.deepcopy(s); floor=s['floor'] if floor is None else floor
    total=s['u']+profit
    reserve_add=min(max(0.,profit-max(0.,-s['u']))*.1,
                    max(0.,.5*s['capital']-s['reserve']))
    s['reserve']+=reserve_add;s['u']=total-reserve_add
    s['cash']+=cashflow+capital_in-capital_out
    s['capital']+=capital_in-capital_out
    if s['cash'] < -1e-8: raise ValueError('FUNDING GAP')
    d=max(0.,min(request,max(0.,s['u']),max(0.,s['cash']-floor)))
    s['cash']-=d;s['u']-=d
    assert abs(s['cash']-(old['cash']+cashflow+capital_in-capital_out-d))<1e-7
    assert abs(s['u']+s['reserve']-(old['u']+old['reserve']+profit-d))<1e-7
    assert d>=0 and d<=max(0.,total-reserve_add)+1e-8
    assert s['reserve']>=0 and s['cash']>=-1e-8
    return d,dict(begin=old,profit=profit,cashflow=cashflow,capital_in=capital_in,
                  capital_out=capital_out,reserve_add=reserve_add,distribution=d,end=copy.deepcopy(s))

def budget(c,y,previous_revenue=None):
    # Growth fades to 0 by year15. No permanent recovery in structural scenario.
    rate=c['growth']*(1 if y<=5 else max(0,(15-y)/10))
    rev=c['revenue']
    for t in range(2,y+1): rev*=1+c['growth']*(1 if t<=5 else max(0,(15-t)/10))
    if c.get('prefix_base') and y>5:
        assert previous_revenue is not None
        rev=previous_revenue*(1+rate)
    margin=c['margin'];shock=1.
    if c['cycle'] and y<=3: shock=[.90,.94,.98][y-1];margin-= [.025,.015,.005][y-1]
    rev*=shock
    dep=c['dep']*rev/c['revenue']
    capex=(c['capex'] if y<=5 else c['dep']+(c['capex']-c['dep'])*max(0,(15-y)/10))*rev/c['revenue']
    ebit=rev*margin
    aux=None
    if c['aux']:
        # Independent operating build, NOT solving for main-model margin.
        volume=7.25*(rev/c['revenue']);asp=4350.;production=2230.;excise=280.;route=680.;fixed=1.65
        ebit=volume*(asp-production-excise-route)/1000-fixed-dep
        aux=dict(volume_million_kl=volume,asp_cny_kl=asp,production_cash_kl=production,
                 excise_kl=excise,route_cash_kl=route,fixed_cash=fixed)
    wc=.06*(rev-budget_revenue(c,y-1)) if y>1 else .15
    if y>15: wc=0.
    return dict(revenue=rev,ebit=ebit,dep=dep,capex=capex,purchases=capex-.045,lease_principal=.045,lease_interest=.004,lease_open=.111544538,lease_new=.045,lease_close=.111544538,wc=wc,aux=aux,rate=rate)

def budget_revenue(c,y):
    rev=c['revenue']
    for t in range(2,y+1): rev*=1+c['growth']*(1 if t<=5 else max(0,(15-t)/10))
    if c['cycle'] and y<=3: rev*=[.90,.94,.98][y-1]
    return rev

def run(c,n=800,rows=True):
    states=copy.deepcopy(OPEN)
    for s in states.values():
        s['cash']*=c['opening_scale'];s['u']*=c['legal_scale']
    states['southeast_loss']=copy.deepcopy(OPEN['southeast_loss'])
    ring={k:v*c['buffer_scale'] for k,v in RING.items()}
    for k in states: states[k]['cash']+=RING[k]-ring[k]
    exit_assets=EXIT['noncash_assets'];exit_liabilities=EXIT['old_liabilities'];parent_basis=c['exit_basis']
    debt=2.202016667 # parent payable to finance, eliminated at group level
    receivable=0.; distributions=[];history=[];res=[]
    for y in range(1,n+1):
        b=budget(BASE if c.get('prefix_base') and y<=5 else c,y,history[-1]['budget']['revenue'] if history else None)
        if y>1: b['wc']=.06*(b['revenue']-history[-1]['budget']['revenue'])
        startcash=sum(s['cash'] for s in states.values());ring_begin=copy.deepcopy(ring)
        ring_transfers={}
        for k in ring:
            target=RING[k]*c['buffer_scale']*b['revenue']/BASE['revenue']
            ring_transfers[k]=target-ring[k]
            states[k]['cash']-=ring_transfers[k];ring[k]=target
        # Entity budget allocations BEFORE tax; pooled residual only profitable payers.
        # Known loss source never tax-offset against profitable sources.
        weights={'parent':.43,'xian':.18,'shenzhen':.024,'profitable_others':.346,'finance':.02}
        # Finance external return modeled from its principal only: reallocate .02 EBIT to parent.
        weights['parent']+=weights.pop('finance')
        entity={};upcash=receivable;upprofit=0.;receivable=0.;minority=0.;external=0.
        # Internal loan repayment in Y1 is transfer only; interest separately paid/earned.
        repay=debt if y==1 else 0.;interest=debt*.025;debt-=repay
        states['parent']['cash']-=repay+interest;states['finance']['cash']+=repay+interest
        # Budget closing balance sheet, not an asserted legal liquidation.
        # Opening .30 cash +.22 noncash -.32 liabilities =.20 net assets.
        exit_start=dict(noncash_assets=exit_assets,liabilities=exit_liabilities,parent_basis=parent_basis)
        sale=EXIT['sale_proceeds'] if y==4 else 0.
        settlement=EXIT['year4_debt_settlement'] if y==4 else (EXIT['year5_debt_settlement'] if y==5 else 0.)
        impairment=exit_assets-sale if y==4 else 0.
        lossprofit=-.06 if y<4 else -impairment
        losscf=-.06 if y<4 else sale-settlement
        if y==4:exit_assets=0.
        exit_liabilities-=settlement
        if y>=5:states['southeast_loss']['floor']=0.
        support=max(0.,(.1 if y<=4 else 0.)-states['southeast_loss']['cash']-losscf)
        states['parent']['cash']-=support;parent_basis+=support
        _,entity['southeast_loss']=step(states['southeast_loss'],lossprofit,losscf,0,capital_in=support)
        # At closure decision Y4 mother writes off actual budget cost plus all support.
        # No tax shield assumed, no second cash deduction. No proceeds returned to mother.
        parent_basis_loss=parent_basis if y==4 else 0.
        parent_basis-=parent_basis_loss
        entity['southeast_loss']['closure_bridge']=dict(begin=exit_start,sale_cash=sale,
            asset_disposal_loss=impairment,old_liabilities_paid=settlement,
            end_noncash_assets=exit_assets,end_liabilities=exit_liabilities,
            parent_cost_addition=support,parent_cost_loss=parent_basis_loss,parent_cost_end=parent_basis)
        net=states['southeast_loss']['cash']+exit_assets-exit_liabilities
        assert abs(net-(states['southeast_loss']['capital']+states['southeast_loss']['u']+states['southeast_loss']['reserve']))<1e-7
        if y>=5:assert abs(net)+abs(exit_assets)+abs(exit_liabilities)+abs(parent_basis)<1e-7
        external+=losscf
        for key in ['xian','shenzhen','profitable_others','finance']:
            s=states[key];w=weights.get(key,0.)
            oper=(b['ebit']-b['lease_interest'])*w;fin=s['cash']*c['cash_yield'];pbt=oper+fin+(interest if key=='finance' else 0.)
            tax=max(0,pbt)*.25;profit=pbt-tax
            cf=oper+fin-tax+b['dep']*w-b['capex']*w-b['wc']*w
            # Internal interest already physically transferred above.
            request=.70*max(profit,0)+c['sweep']*max(0,s['cash']-s['floor'])
            d,entity[key]=step(s,profit,cf,request)
            entity[key].update(operating_ebit=oper,financial_income=fin,tax=tax,dep=b['dep']*w,
                              capex=b['capex']*w,working_capital=b['wc']*w)
            gross=d*s['share'];minority+=d-gross;upprofit+=gross
            if c['collection_lag']: receivable+=gross
            else: upcash+=gross
            external+=cf
        p=states['parent'];w=weights['parent'];oper=(b['ebit']-b['lease_interest'])*w;fin=p['cash']*c['cash_yield']
        tax=max(0,oper+fin-interest)*.25
        profit=oper+fin-interest-tax+upprofit-parent_basis_loss
        owncf=oper+fin-tax+b['dep']*w-b['capex']*w-b['wc']*w
        request=.70*max(0,profit)+c['sweep']*max(0,p['cash']-p['floor'])
        d,entity['parent']=step(p,profit,owncf+upcash,request)
        entity['parent'].update(operating_ebit=oper,financial_income=fin,tax=tax,dep=b['dep']*w,
             capex=b['capex']*w,working_capital=b['wc']*w,upstream_declared=upprofit,
             upstream_received=upcash,internal_debt_paid=repay,internal_interest=interest,parent_investment_cost_loss=parent_basis_loss,parent_investment_cost_end=parent_basis)
        external+=owncf
        endcash=sum(s['cash'] for s in states.values())
        # Undelivered subsidiary D is still bank cash in transit, on receivable ledger;
        # total economic cash includes receivable to prevent destroying delayed money.
        if y==1: prior_receivable=0.
        else: prior_receivable=history[-1]['receivable']
        assert abs(endcash+sum(ring.values())+receivable-startcash-sum(ring_begin.values())-prior_receivable-(external-d-minority))<1e-6
        distributions.append(d/SHARES)
        row=dict(year=y,budget=b,entities=entity,ordinary_D=d,minority_D=minority,
                 external_cashflow=external,group_cash=endcash,operating_cash_begin=ring_begin,operating_cash_end=copy.deepcopy(ring),operating_cash_transfers=ring_transfers,full_external_cash=endcash+sum(ring.values()),receivable=receivable,internal_debt=debt)
        history.append(row)
    # Only use perpetuity AFTER SAME policy has converged. No cash/r, no principal plug.
    for key,s in states.items():
        prev=history[-2]['entities'][key]['end']
        assert abs(s['cash']-prev['cash'])<1e-7,(key,'cash unstable')
        assert abs(s['reserve']-prev['reserve'])<1e-7,(key,'reserve unstable')
        assert abs(s['u']-prev['u'])<1e-7,(key,'legal retained earnings unstable')
    assert abs(distributions[-1]-distributions[-2])<1e-8
    assert all(abs(ring[k]-history[-2]['operating_cash_end'][k])<1e-8 for k in ring)
    r=c['r'];tail=distributions[-1]/r
    pv=sum(d/(1+r)**(i+1) for i,d in enumerate(distributions))+tail/(1+r)**n
    tv5=sum(distributions[i]/(1+r)**(i-4) for i in range(5,n))+tail/(1+r)**(n-5)
    assert abs(pv-(sum(distributions[i]/(1+r)**(i+1) for i in range(5))+tv5/(1+r)**5))<1e-7
    return dict(value=pv,distributions_5=distributions[:5],terminal_5=tv5,
                terminal_pv_fraction=(tv5/(1+r)**5)/pv,steady_D=distributions[-1],
                terminal_state=states,terminal_operating_cash=ring,years=history if rows else [],params=c)

def tests():
    # Production-chain literal hand cases. Loss FIRST means only 2 eligible of 10 profit.
    s=dict(cash=20.,u=-8.,reserve=0.,capital=10.,floor=0.,share=1.)
    d,x=step(s,10,10,99);assert abs(d-1.8)<1e-12 and abs(s['reserve']-.2)<1e-12 and abs(s['cash']-28.2)<1e-12
    s=dict(cash=5.,u=30.,reserve=5.,capital=10.,floor=2.,share=1.)
    d,x=step(s,4,1,99);assert d==4 and s['cash']==2 and s['u']==30
    # 3 debt repayment consumes cash, NOT profits: starting10+4CF-3 repayment-2floor=9D.
    s=dict(cash=10.,u=20.,reserve=5.,capital=10.,floor=2.,share=1.)
    s['cash']-=3;d,x=step(s,4,4,99);assert d==9 and s['u']==15 and s['cash']==2
    # Parent basis writeoff is legal profit loss, never a second cash payment.
    s=dict(cash=10.,u=1.,reserve=5.,capital=10.,floor=0.,share=1.)
    d,x=step(s,-.25,0,99);assert d==.75 and s['cash']==9.25 and s['u']==0
    try:
        step(dict(cash=1.,u=0.,reserve=0.,capital=1.,floor=0.,share=1.),-2,-2,0)
        raise AssertionError('gap not stopped')
    except ValueError: pass
    return 'production_lossfirst_reserve_cash_debt_noncash_basis_gap_tests_PASS'

def main():
    output={'units':'CNY billion, per-share CNY','asof':ASOF,'shares_billion':SHARES,
            'opening':OPEN,'opening_operating_cash':RING,'opening_total_external_resources':sum(x['cash'] for x in OPEN.values())+sum(RING.values()),'closure_budget':EXIT,'tests':tests(),'scenarios':{},'convergence':{}}
    for name,c in CASES.items():
        output['scenarios'][name]=run(c)
        vals=[run(c,n,False)['value'] for n in (800,1200,1600)]
        assert max(vals)-min(vals)<1e-8
        output['convergence'][name]=dict(horizons=[800,1200,1600],values=vals,max_difference=max(vals)-min(vals))
    print(json.dumps(output,ensure_ascii=False,sort_keys=True,separators=(",",":" )))
if __name__=='__main__': main()

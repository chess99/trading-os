#!/usr/bin/env python3
"""Livzon owner-cash model. CNY billion; forecast/budget, not entity accounts.
Run with Python standard library only. All financial principal ultimately traverses
actual cash and legal dividend limits; no year-5 blanket cash add-back.
"""
import json, math
from pathlib import Path
from copy import deepcopy
SHARES=.887907171
OWN={'W':1.,'Shanghai':.51,'New':.906443,'Diagnostic':.47425,'IMP':.6787,'Bio':.6752}
P0=3.8
G0=7.14989826687-.65273064722
CASH={'P':P0,'W':1.1,'Shanghai':.45,'New':.75,'Diagnostic':.20,'IMP':G0-P0-2.50,'Bio':0.}
DEBT={'W':2.6,'New':.60,'IMP':.18441458806}
# Gross normalized after-tax operating earnings; excludes all financial returns.
PROF={'P':[-.06,-.06,-.055,-.05,-.05], 'W':[1.05,1.10,1.16,1.22,1.28],
'Shanghai':[.60,.61,.625,.64,.66], 'New':[.52,.55,.575,.60,.63],
'Diagnostic':[.09,.095,.10,.11,.12], 'IMP':[.04,.05,.06,.07,.08],
'Bio':[-.18,-.16,-.13,-.10,-.07]}
REVENUE=[9.9,10.3,10.75,11.25,11.8]
# Includes incremental working capital, physical capex less D&A, capitalized R&D.
INV=[.31,.33,.35,.38,.40]
INV_WEIGHT={'P':.03,'W':.45,'Shanghai':.12,'New':.27,'Diagnostic':.04,'IMP':.09,'Bio':0.}
BUFFER={'P':.6,'W':.35,'Shanghai':.12,'New':.25,'Diagnostic':.08,'IMP':.10,'Bio':0.}
PORT=[(8,.65,'wholly_owned_asset_plans'),(9,.65,'wholly_owned_asset_plans'),(10,.35,'wholly_owned_asset_plans'),(10,.30,'parent_nonlisted_equity'),(11,.575,'attributable_associates'),(12,.575,'attributable_associates')]
SCENARIOS={
'base':dict(factors=[1]*5,extra_inv=[0]*5,old_pay=[.20,.15,.10,0,0],bio=[-.18,-.16,-.13,-.10,-.07],g=.0175,roic=.135,delay=0),
'cyclical':dict(factors=[.75,.85,.95,1,1],extra_inv=[.25,.10,-.12,-.10,-.05],old_pay=[.30,.20,.10,0,0],bio=[-.22,-.20,-.15,-.10,-.07],g=.0175,roic=.135,delay=1),
'structural':dict(factors=[.70,.65,.62,.60,.60],extra_inv=[.12,.12,.08,.06,.04],old_pay=[.45,.35,.20,.10,0],bio=[-.25,-.25,-.25,-.22,-.20],g=0,roic=.085,delay=5),
'optimistic':dict(factors=[1.03,1.07,1.12,1.17,1.22],extra_inv=[.05,.08,.10,.12,.15],old_pay=[.20,.15,.10,0,0],bio=[-.15,-.10,-.05,0,.025],g=.0225,roic=.16,delay=0)}

def legal_update(retained,profit,rate=.1):
    # Loss carryforward cannot be reset. Reserve on positive current profit only
    # after any accumulated deficit is covered. Parent rate=0: documented cap met.
    reserve=max(0.,min(profit,retained+profit))*rate
    return retained+profit-reserve,reserve

def pv_cash(distributions,terminal,r,shares=SHARES):
    return (sum(d/(1+r)**(i+1) for i,d in enumerate(distributions))+terminal/(1+r)**len(distributions))/shares

def run(name='base',r=.0975,g=None,roic=None,delay=None,parent_shift=0.,no_offset=False,hand_case=False,liquidity_shock=0.,operating_loss_shock=0.,remittance_delay=0):
    s=deepcopy(SCENARIOS[name]);g=s['g'] if g is None else g;roic=s['roic'] if roic is None else roic;delay=s['delay'] if delay is None else delay
    cash=deepcopy(CASH);cash['P']+=parent_shift;cash['W']-=parent_shift
    debt=deepcopy(DEBT);ret={'P':6.73840844216,'W':0.,'Shanghai':.20,'New':0.,'Diagnostic':.20,'IMP':.10,'Bio':-3.0}
    loans={'P_owes_W':2.0,'Bio_owes_P':.8} # forecast residual funding-pool debt, NOT reported Q3 balance
    capital=0.;bio_funded=0.;port=3.1;rows=[];divs=[];owners_cf=[]
    reserves={k:0. for k in OWN}
    reserve_caps={'W':1.,'Shanghai':.04366445,'New':.11994385,'Diagnostic':.10,'IMP':.50,'Bio':.65}
    cash['P']-=liquidity_shock
    if cash['P']<0:raise ValueError('No authorized financing for opening liquidity shortfall')
    if hand_case:
        cash={k:0. for k in cash};cash['P']=1.;debt={k:0. for k in debt};port=0.;loans['P_owes_W']=0.;ret={k:0. for k in ret};ret['P']=1.
    for y in range(1,41):
        buffer={k:v*(1+g)**max(0,y-5) for k,v in BUFFER.items()}
        if hand_case:buffer={k:0. for k in BUFFER}
        oldcash=sum(cash.values());external_in=0.;external_out=0.;profit={};invest={};minor=0.;up=0.;offset=0.;reserve={};settled_debt=0.
        if y<=5:
            f=s['factors'][y-1]
            for k in cash:
                profit[k]=PROF[k][y-1]*f if PROF[k][y-1]>0 else PROF[k][y-1]
            profit['Bio']=s['bio'][y-1]
            inv=INV[y-1]+s['extra_inv'][y-1];rev=REVENUE[y-1]*f
        else:
            f=s['factors'][4];rev=REVENUE[-1]*f*(1+g)**(y-5)
            for k in cash:profit[k]=PROF[k][-1]*f*(1+g)**(y-5) if PROF[k][-1]>0 else PROF[k][-1]*(1+g)**(y-5)
            # Base has 3 more years of modest loss; no valuation of a speculative
            # pipeline exit or dividends from the loss entity. Losses remain on ledger.
            profit['Bio']=(-.05 if y==6 else -.025 if y==7 else 0.) if name!='structural' else (-.025 if y==6 else 0.)
            # Structural year6 has final .025 cash cost, then no further operating profit or sale proceeds.
            if name=='optimistic':profit['Bio']=0. # no unproved perpetual antibody profit
            owner_positive=sum(OWN.get(k,1)*max(v,0) for k,v in profit.items())
            inv=owner_positive*g/roic/max(.8,sum(OWN.get(k,1)*v for k,v in INV_WEIGHT.items()))
        if y==1:profit['W']-=operating_loss_shock
        if hand_case:
            profit={k:0. for k in cash};profit['W']=1.;inv=0.;rev=1.
        capital+=inv
        operating_owner=sum(OWN.get(k,1)*profit[k] for k in cash)-max(0,-profit['Bio'])*(1-OWN['Bio'])
        repayment_by={}
        # Deposit yield is separately added, never capitalized in operating TV.
        for k in cash:
            deposit=cash[k]*(0 if hand_case else .01);profit[k]+=deposit
            invest[k]=inv*INV_WEIGHT[k]
            cash[k]+=profit[k]-invest[k];external_in+=profit[k];external_out+=invest[k]
        # Internal interest: exact matched receipt and payment, no consolidated gain.
        intr=loans['P_owes_W']*.02;cash['P']-=intr;cash['W']+=intr;profit['P']-=intr;profit['W']+=intr
        # Third-party debt: no new borrowing, scheduled staged amortization, cap frozen.
        for k in debt:
            interest=debt[k]*.03;cash[k]-=interest;profit[k]-=interest;external_out+=interest
            repay=min(debt[k],DEBT[k]/8,max(0,cash[k]-buffer[k]));cash[k]-=repay;debt[k]-=repay;external_out+=repay;settled_debt+=repay;repayment_by[k]=repay
        portfolio_income=port*.02;cash['P']+=portfolio_income;profit['P']+=portfolio_income;external_in+=portfolio_income
        realized=0
        for yy,amt,label in PORT:
            if yy+delay==y:realized+=amt
        port-=realized;cash['P']+=realized;external_in+=realized
        # Book value realization is capital cash, not newly created legal earnings.
        # Initial parent's accumulated distributable profit provides release cover.
        oldpay=s['old_pay'][y-1] if y<=5 and not hand_case else 0
        cash['P']-=oldpay;external_out+=oldpay
        purchase=.1066958 if y==1 and not hand_case else 0.;cash['P']-=purchase;external_out+=purchase
        # Remaining committed parent->bio subscription budget: .48 in year 1.
        # Additional funding capped at .8 total, all parent-funded absent minority cash.
        subscription=.48 if y==1 and not hand_case else 0
        need=max(0,-cash['Bio']);inject=max(subscription,need)
        if bio_funded+inject>1.2+1e-9:raise ValueError('Bio capital budget exceeded')
        bio_funded+=inject;cash['P']-=inject;cash['Bio']+=inject
        bio_loan_repayment=min(loans['Bio_owes_P'],max(0,cash['Bio'])) if y>5 else 0.
        cash['Bio']-=bio_loan_repayment;cash['P']+=bio_loan_repayment;loans['Bio_owes_P']-=bio_loan_repayment
        for k in cash:
            after,required=legal_update(ret[k],profit[k],0 if k=='P' else .1)
            actual=min(required,max(0,reserve_caps.get(k,0)-reserves.get(k,0)))
            reserve[k]=actual;ret[k]+=profit[k]-actual
            if k!='P':reserves[k]+=actual
        # Subsidiaries distribute max 80% current profit, no use of unverified legacy
        # retained earnings. Cash gate must cover buffer and remaining debt service.
        detail={}
        for k in OWN:
            target=max(0,profit[k])*.80 if y<=5+remittance_delay else max(0,cash[k]-buffer[k])
            available=max(0,cash[k]-buffer[k])
            planned=min(target,max(0,ret[k]))
            off=min(.20,loans['P_owes_W'],planned) if k=='W' and y<=5 and not no_offset else 0.
            # A legally documented receivable/payable net settlement is a budget.
            # The no-offset sensitivity forbids it and keeps the loan outstanding.
            paid=min(max(0,planned-off),available)
            declared=paid+off
            ret[k]-=declared;cash[k]-=paid
            cash['P']+=paid*OWN[k];up+=paid*OWN[k];minor+=paid*(1-OWN[k]);external_out+=paid*(1-OWN[k])
            ret['P']+=declared*OWN[k]
            loans['P_owes_W']-=off;offset+=off
            detail[k]={'profit':profit[k],'reserve':reserve[k],'investment':invest[k],'declared':declared,'cash_paid':paid,'parent_received':paid*OWN[k],'minority_paid':paid*(1-OWN[k]),'closing_cash':cash[k],'legal_retained':ret[k],'external_debt':debt.get(k,0)}
        # No trapped old receivable is recognized as new profit or a second cash receipt.
        target=SHARES*[2.1,1.5,1.6,1.7,1.8][y-1] if y<=5 else max(0,cash['P']-buffer['P'])
        if 5<y<=5+remittance_delay:target=SHARES*1.8*(1+g)**(y-5)
        if min(cash.values())<0:target=0.
        if hand_case:target=10.
        d=min(target,max(0,ret['P']),max(0,cash['P']-buffer['P']))
        cash['P']-=d;ret['P']-=d;external_out+=d;divs.append(d)
        if min(cash.values()) < -1e-8:raise ValueError(('Cash failure even after zero common distribution; no new financing',name,y,cash,d))
        assert abs(sum(cash.values())-oldcash-external_in+external_out)<1e-8,(name,y,'cash conservation')
        assert min(debt.values())>=-1e-9 and sum(debt.values())<=sum(DEBT.values())+1e-9
        if hand_case:return {'distribution':d,'parent_cash':cash['P'],'subsidiary_cash':cash['W'],'parent_legal_retained':ret['P'],'subsidiary_legal_retained':ret['W'],'reserve':reserves['W']}
        owner_cf=operating_owner-sum(OWN.get(k,1)*v for k,v in invest.items())-oldpay-purchase
        buffer_growth=sum(BUFFER[k]*OWN.get(k,1) for k in BUFFER)*((1+g)**(y-5)-(1+g)**(y-6)) if y>5 else 0.
        owner_cf-=buffer_growth
        owners_cf.append(owner_cf)
        rows.append({'year':y,'revenue':rev,'owner_operating_fcfe':owner_cf,'buffer_growth':buffer_growth,'legal_reserves':deepcopy(reserves),'operating_owner_profit':operating_owner,'net_investment':inv,'capital_accumulated':capital,'parent_distribution':d,'distribution_per_share':d/SHARES,'parent_cash':cash['P'],'group_cash':sum(cash.values()),'parent_legal_retained':ret['P'],'subsidiary_cash_received':up,'noncash_offset':offset,'internal_interest_eliminated':intr,'remaining_internal_loan':loans['P_owes_W'],'minority_cash_paid':minor,'external_debt':sum(debt.values()),'debt_repaid':settled_debt,'bio_loan_repayment':bio_loan_repayment,'bio_loan_remaining':loans['Bio_owes_P'],'bio_capital_paid':inject,'bio_funding_cumulative':bio_funded,'bio_loss_carryforward':ret['Bio'],'portfolio_remaining':port,'portfolio_capital_realized':realized,'portfolio_income':portfolio_income,'old_payables_paid':oldpay,'purchase_new_share':purchase,'entities':detail})
    # By year 40 all scheduled portfolios are realized, existing debt has been
    # repaid and profitable entities' reserve caps have been met. EVERY previous
    # capital receipt went through subsidiary/parent legal and cash accounts.
    # The remaining buffer is necessary operating capital, not extra principal.
    assert sum(debt.values())<1e-8 and abs(port)<1e-8
    assert all(abs(cash[k]-buffer[k])<1e-7 for k in cash if k!='Bio'),('terminal sweep incomplete',cash,buffer)
    assert cash['Bio']<1e-8,('unreleased Bio financial capital',cash['Bio'])
    last=rows[-1]
    # Actual Y40 distribution is the production cash waterfall, including all
    # investment, reserve, treasury interest and parent obligations. Test Y39->40
    # homogeneity rather than silently plugging a different terminal FCFE formula.
    assert abs(divs[-1]/divs[-2]-(1+g))<1e-8,('terminal not stable',divs[-2:])
    terminal=divs[-1]*(1+g)/(r-g)
    value=pv_cash(divs,terminal,r)
    tv5=(sum(divs[y-1]/(1+r)**(y-5) for y in range(6,41))+terminal/(1+r)**35)/SHARES
    pvd5=sum(divs[y-1]/SHARES/(1+r)**y for y in range(1,6))
    init_owner_cash=sum((CASH[k]-BUFFER[k])*OWN.get(k,1) for k in CASH)
    debt0_owner=sum(DEBT[k]*OWN[k] for k in DEBT)
    aux=(sum(owners_cf[i]/(1+r)**(i+1) for i in range(40))+owners_cf[-1]*(1+g)/(r-g)/(1+r)**40+init_owner_cash-debt0_owner+sum(a/(1+r)**(yy+delay) for yy,a,_ in PORT))/SHARES
    return {'scenario':name,'r':r,'g':g,'roic':roic,'delay':delay,'value_per_share':value,'tv5_per_share':tv5,'first5_dps':[v/SHARES for v in divs[:5]],'pv_first5_dps':pvd5,'tv5_pv_share':(value-pvd5)/value,'aux_value_per_share':aux,'terminal40':terminal,'terminal_distribution_growth_check':divs[-1]/divs[-2]-1,'rows':rows}

def tests():
    # Same production valuation function, independently known 2-year hand example.
    assert abs(pv_cash([1,1],10,.1,1)-(1/1.1+11/1.21))<1e-12
    a,res=legal_update(-2,1);assert a==-1 and res==0
    a,res=legal_update(-.5,1);assert abs(a-.45)<1e-12 and abs(res-.05)<1e-12
    a,res=legal_update(2,1);assert abs(a-2.9)<1e-12 and abs(res-.1)<1e-12
    h=run(hand_case=True)
    # P opens with cash/profit 1; W earns 1 cash, reserves .1, declares/pays .8.
    # P pays 1.8, W retains .2 cash and .1 legally distributable earnings.
    assert all(abs(h[k]-v)<1e-10 for k,v in {'distribution':1.8,'parent_cash':0.,'subsidiary_cash':.2,'parent_legal_retained':0.,'subsidiary_legal_retained':.1,'reserve':.1}.items()),h
    try:run(liquidity_shock=10.)
    except ValueError:pass
    else:raise AssertionError('unbounded financing failure not detected')
    try:run(operating_loss_shock=10.)
    except ValueError as e:assert 'zero common distribution' in str(e)
    else:raise AssertionError('operating loss did not force zero-D cash failure')
    return {'production_operating_legal_cash_hand_case':h,'zero_available_cash_financing_failure':True,'production_pv_hand_case':True,'accumulated_loss_and_reserve_cases':True}

def main():
    out={'units':'CNY billion, shares billion; forecasts/budgets','shares':SHARES,'opening_cash':CASH,'opening_external_debt':DEBT,'opening_parent_legal_retained':6.73840844216,'portfolio_release_budget':PORT,'scenario_inputs':SCENARIOS,'tests':tests(),
    'core_low':run(r=.102,g=.015,roic=.12),'core_high':run(r=.092,g=.02,roic=.15),'base':run(),
    'cyclical':run('cyclical'),'structural':run('structural'),'optimistic':run('optimistic'),
    'all_financial_release_plus5':run(delay=5,remittance_delay=5),'delay_plus5':run(delay=5),'no_legal_offset':run(no_offset=True),'parent_cash_minus05':run(parent_shift=-.5),
    'r_plus1pct':run(r=.1075)}
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:{t:v[t] for t in ['value_per_share','tv5_per_share','first5_dps','aux_value_per_share']} for k,v in out.items() if isinstance(v,dict) and 'value_per_share' in v},indent=2))
if __name__=='__main__':main()

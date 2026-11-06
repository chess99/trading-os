#!/usr/bin/env python3
"""Livzon owner-cash model. CNY billion; forecast/budget, not entity accounts.
Run with Python standard library only. Only the listed parent is a statutory ledger. W/Shanghai/New/Diagnostic/IMP/Bio
are ECONOMIC SOURCE BUDGETS, not fabricated corporations or consolidated legal
retained earnings. Their source capacity is an explicitly conditional remittance
budget; no Chinese reserve law is applied to a foreign company or a composite.
"""
import json, math, gzip, hashlib, base64, sys
from pathlib import Path
from copy import deepcopy
SHARES=.887907171
OWN={'W':1.,'Shanghai':.51,'New':.906443,'Diagnostic':.47425,'IMP':.6787,'Bio':.6752}
P0=3.8
G0=7.14989826687-.65273064722
CASH={'P':P0,'W':1.1,'Shanghai':.45,'New':.75,'Diagnostic':.20,'IMP':G0-P0-2.50,'Bio':0.}
DEBT={'W':1.7795019,'New':.60,'IMP':.18441458806,'Bio':.8204981}
BIO_EQUITY_COST=2.45223079315
BIO_ASSET_BOOK_BUDGET=.52860906544
BIO_OTHER_CREDITORS=.33158314088 # H1 antibody total debt less guaranteed bank debt; platform proxy, not audited whole-platform balance
# Normalized source-shareholder after-tax operating earnings: net of nested
# minorities, before OWN top-level attribution; excludes financial returns.
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

def statutory(retained,profit,registered,reserve,voluntary=0.):
    eligible=max(0.,min(profit,retained+profit))
    addition=min(eligible*.1,max(0.,registered*.5-reserve))
    optional=min(max(0.,retained+profit-addition),max(0.,voluntary))
    return retained+profit-addition-optional,reserve+addition,addition,optional

def settle_receivable(cash,profit,receivable,amount):
    paid=min(receivable,amount)
    return cash+paid,profit,receivable-paid

def capital_realization(proceeds,basis,cost,tax,ownership,shares,cancel_fraction=0.):
    # Disposal/return of investment cost: no full-proceeds accounting profit.
    gain=proceeds-basis-cost
    taxpaid=max(0.,gain)*tax
    net=(proceeds-cost-taxpaid)*ownership
    return dict(cash=net,profit=(gain-taxpaid)*ownership,tax=taxpaid,
                principal=min(proceeds-cost,basis)*ownership,
                shares=shares*(1-cancel_fraction))

def pv_cash(distributions,terminal,r,shares=SHARES):
    return (sum(d/(1+r)**(i+1) for i,d in enumerate(distributions))+terminal/(1+r)**len(distributions))/shares

def bio_realize(gross,fees_rate,other_creditors,loans,equity_cost,ownership,asset_book):
    # Economic platform realization budget, with named claims and explicit uncertainty.
    # Creditors rank ahead of the new shareholder loans; equity is last.
    fees=gross*fees_rate
    taxable_gain=max(0.,gross-fees-asset_book)
    tax=taxable_gain*.25
    available=gross-fees-tax-other_creditors
    support=max(0.,-available)
    loan_repaid=min(loans,max(0.,available))
    residual=max(0.,available-loan_repaid)
    equity_parent=residual*ownership
    minority=residual*(1-ownership)
    loan_writeoff=loans-loan_repaid
    parent_equity_loss=equity_cost-equity_parent
    return dict(gross=gross,fees=fees,tax=tax,other_creditors=other_creditors,
        shortfall_support=support,loan_repaid=loan_repaid,equity_parent=equity_parent,
        minority_paid=minority,loan_writeoff=loan_writeoff,
        parent_legal_loss=loan_writeoff+parent_equity_loss+support,
        parent_net_cash=loan_repaid+equity_parent-support,
        underlying_asset_profit=gross-fees-tax-asset_book)

def run(name='base',r=.0975,g=None,roic=None,delay=None,parent_shift=0.,no_offset=False,hand_case=False,liquidity_shock=0.,operating_loss_shock=0.,remittance_delay=0,horizon=240,source_cost=0.,foreign_friction=.05,internal_tax=.25,probe_year=0,probe_amount=0.,source_capacity_scale=1.,old_source_scale=1.,bio_gross=None,bio_other_creditors=BIO_OTHER_CREDITORS,bio_exit_delay=0,bio_ownership=.6752):
    s=deepcopy(SCENARIOS[name]);g=s['g'] if g is None else g;roic=s['roic'] if roic is None else roic;delay=s['delay'] if delay is None else delay
    cash=deepcopy(CASH);cash['P']+=parent_shift;cash['W']-=parent_shift
    debt=deepcopy(DEBT);ret={'P':6.73840844216,'W':.25,'Shanghai':.20,'New':0.,'Diagnostic':.20,'IMP':.10,'Bio':-3.0}
    for key in ['Shanghai','Diagnostic','IMP']:ret[key]*=old_source_scale
    loans={'P_owes_W':2.0,'Bio_owes_P':0.} # forecast residual funding-pool debt, NOT reported Q3 balance
    capital=0.;bio_funded=0.;port=3.1;rows=[];divs=[];owners_cf=[]; group_ret=11.85092911057
    bio_equity_cost=BIO_EQUITY_COST;bio_subscription_paid=0.;bio_operating_loans=0.;bio_service_loans=0.;bio_exit_support=0.
    bio_exit_year=(9 if name=='structural' else 10)+bio_exit_delay
    bio_gross=(.30 if name=='structural' else .45) if bio_gross is None else bio_gross
    bio_exit_record=None;bio_closed=False;bio_carry_loans=0.
    reserves={'P':.47711529203}; parent_registered=.887907171
    # These are economic source capacity budgets, NOT consolidated statutory profits.
    capacity_open=deepcopy(ret); sale_losses=0.; old_receivable=.047425
    # No invented subsidiary statutory reserve capital caps.
    cash['P']-=liquidity_shock
    if cash['P']<0:raise ValueError('No authorized financing for opening liquidity shortfall')
    if hand_case:
        cash={k:0. for k in cash};cash['P']=1.;debt={k:0. for k in debt};port=0.;loans['P_owes_W']=0.;ret={k:0. for k in ret};ret['P']=1.
    for y in range(1,horizon+1):
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
            # Structural Y6 employee/program wind-down cost .025; asset realization is separate at Y9.
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
        taxcash=max(0.,intr)*internal_tax if not hand_case else 0.
        cash['W']-=taxcash;profit['W']-=taxcash;external_out+=taxcash
        # Parent has operating losses: no immediate tax credit assumed.
        internal_principal=min(loans['P_owes_W'],max(0.,cash['P']-buffer['P'])) if y>=6 else 0.
        cash['P']-=internal_principal;cash['W']+=internal_principal;loans['P_owes_W']-=internal_principal
        # Third-party debt total unchanged. Bio bank debt is supported by H1 guarantee table.
        # Parent lends the actual debt-service cash to technology platform, earmarked
        # onward to antibody borrower; this creates a recoverable claim, not equity.
        bio_service_this_year=0.
        for k in debt:
            if k=='Bio':
                interest=debt[k]*.03
                repay=min(debt[k],DEBT[k]/8)
                service=interest+repay
                cash['P']-=service;external_out+=service;profit['Bio']-=interest
                debt[k]-=repay;settled_debt+=repay;repayment_by[k]=repay
                loans['Bio_owes_P']+=service;bio_service_loans+=service;bio_service_this_year=service
                continue
            interest=debt[k]*.03;cash[k]-=interest;profit[k]-=interest;external_out+=interest
            repay=min(debt[k],DEBT[k]/8,max(0,cash[k]-buffer[k]));cash[k]-=repay;debt[k]-=repay;external_out+=repay;settled_debt+=repay;repayment_by[k]=repay
        bio_carry=.005 if (6 if name=='structural' else 7)<y<bio_exit_year and not hand_case else 0.
        cash['P']-=bio_carry;profit['Bio']-=bio_carry;external_out+=bio_carry
        loans['Bio_owes_P']+=bio_carry;bio_carry_loans+=bio_carry
        if bio_carry_loans>.10+1e-9:raise ValueError('Bio realization holding-cost limit exceeded')
        portfolio_income=port*.02;cash['P']+=portfolio_income;profit['P']+=portfolio_income;external_in+=portfolio_income
        realized=0
        for yy,amt,label in PORT:
            if yy+delay==y:realized+=amt
        port-=realized
        # Proceeds already include realization haircut; basis losses affect legal P&L, not cash twice.
        realized_basis=realized*(3.391/3.1)
        sale=capital_realization(realized/.99,realized_basis,realized/.99*.01,.25,1.,SHARES)
        cash['P']+=sale['cash'];profit['P']+=sale['profit'];external_in+=sale['cash'];sale_losses+=sale['profit']
        # Old diagnostic dividend collection is inside the opening-cash allocation,
        # not an extra income or a second asset. This optional test injects future
        # financial principal into W at cost without inventing profit.
        probe=probe_amount if y==probe_year else 0.
        cash['W']+=probe;external_in+=probe
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
        bio_subscription_paid+=subscription;bio_equity_cost+=subscription
        new_bio_loan=inject-subscription
        assert new_bio_loan>=-1e-12
        loans['Bio_owes_P']+=new_bio_loan;bio_operating_loans+=new_bio_loan
        bio_loan_repayment=min(loans['Bio_owes_P'],max(0,cash['Bio'])) if y>5 else 0.
        cash['Bio']-=bio_loan_repayment;cash['P']+=bio_loan_repayment;loans['Bio_owes_P']-=bio_loan_repayment
        bio_parent_impairment=0.;bio_realization_parent_cash=0.
        if y==bio_exit_year and not hand_case:
            assert debt['Bio']<1e-9, 'Existing bank debt must be serviced before this realization budget'
            # Existing Bio cash is already on consolidated balance sheet; only asset sale
            # gross is new external cash. Remaining working/other creditors settle once.
            opening_bio_cash=cash['Bio']
            z=bio_realize(bio_gross+opening_bio_cash,.05,bio_other_creditors,
                          loans['Bio_owes_P'],bio_equity_cost,bio_ownership,
                          BIO_ASSET_BOOK_BUDGET+opening_bio_cash)
            # Do not charge disposal fees on plain existing cash.
            if opening_bio_cash:
                z=bio_realize(bio_gross,.05,bio_other_creditors-opening_bio_cash,
                              loans['Bio_owes_P'],bio_equity_cost,bio_ownership,BIO_ASSET_BOOK_BUDGET)
            if z['shortfall_support']>.25+1e-9:raise ValueError('Bio exit creditor-support ceiling exceeded')
            bio_exit_support+=z['shortfall_support']
            cash['P']+=z['parent_net_cash'];cash['Bio']=0.
            external_in+=bio_gross
            external_out+=z['fees']+z['tax']+bio_other_creditors+z['minority_paid'];minor+=z['minority_paid']
            bio_parent_impairment=z['parent_legal_loss']
            profit['P']-=bio_parent_impairment
            profit['Bio']+=z['underlying_asset_profit']
            bio_realization_parent_cash=z['parent_net_cash']
            bio_exit_record=dict(year=y,**z,old_parent_equity_cost=bio_equity_cost,
                                 prior_loan_balance=loans['Bio_owes_P'],existing_cash=opening_bio_cash)
            loans['Bio_owes_P']=0.;bio_equity_cost=0.;bio_closed=True
        for k in cash:
            if k=='P':
                ret[k],reserves[k],required,optional=statutory(ret[k],profit[k],parent_registered,reserves[k])
                reserve[k]=required
            else:
                # Source earnings budget is NOT a legal netting of unrelated losses.
                # Negative Bio cannot be offset against mature-source capacity.
                ret[k]+=profit[k]*source_capacity_scale if profit[k]>0 else profit[k]
                reserve[k]=0.
        # Subsidiaries distribute max 80% current profit, no use of unverified legacy
        # retained earnings. Cash gate must cover buffer and remaining debt service.
        # Parent impairment of intra-group debt/equity eliminates in consolidation.
        # Only underlying asset disposal result enters group earnings again.
        group_profit=profit['P']+sum(profit[k]*OWN[k] for k in OWN)+bio_parent_impairment
        total_friction=0.;detail={}
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
            friction=paid*OWN[k]*(source_cost+(foreign_friction if k=='IMP' else 0.))
            received=paid*OWN[k]-friction;total_friction+=friction
            cash['P']+=received;up+=received;minor+=paid*(1-OWN[k]);external_out+=paid*(1-OWN[k])+friction
            ret['P']+=declared*OWN[k]-friction
            loans['P_owes_W']-=off;offset+=off
            detail[k]={'profit':profit[k],'reserve':reserve[k],'investment':invest[k],'declared':declared,'cash_paid':paid,'parent_received':received,'friction':friction,'minority_paid':paid*(1-OWN[k]),'closing_cash':cash[k],'economic_earnings_capacity':ret[k],'external_debt':debt.get(k,0)}
        # Repay remaining internal treasury principal after actual dividends arrive.
        post_repay=min(loans['P_owes_W'],max(0.,cash['P']-buffer['P'])) if y>=6 else 0.
        cash['P']-=post_repay;cash['W']+=post_repay;loans['P_owes_W']-=post_repay
        internal_principal+=post_repay
        # No trapped old receivable is recognized as new profit or a second cash receipt.
        target=SHARES*[2.1,1.5,1.6,1.7,1.8][y-1] if y<=5 else max(0,cash['P']-buffer['P'])
        if 5<y<=5+remittance_delay:target=SHARES*1.8*(1+g)**(y-5)
        if min(cash.values())<0:target=0.
        if hand_case:target=10.
        group_ret+=group_profit-total_friction
        d=min(target,max(0,ret['P']),max(0,group_ret),max(0,cash['P']-buffer['P']))
        group_ret-=d
        cash['P']-=d;ret['P']-=d;external_out+=d;divs.append(d)
        if min(cash.values()) < -1e-8:raise ValueError(('Cash failure even after zero common distribution; no new financing',name,y,cash,d))
        assert abs(sum(cash.values())-oldcash-external_in+external_out)<1e-6,(name,y,'cash conservation')
        assert min(debt.values())>=-1e-9 and sum(debt.values())<=sum(DEBT.values())+1e-9
        if hand_case:return {'distribution':d,'parent_cash':cash['P'],'subsidiary_cash':cash['W'],'parent_legal_retained':ret['P'],'subsidiary_legal_retained':ret['W'],'reserve':0.}
        owner_cf=operating_owner-sum(OWN.get(k,1)*v for k,v in invest.items())-oldpay-purchase
        buffer_growth=sum(BUFFER[k]*OWN.get(k,1) for k in BUFFER)*((1+g)**(y-5)-(1+g)**(y-6)) if y>5 else 0.
        owner_cf-=buffer_growth+taxcash+total_friction
        owner_cf+=bio_realization_parent_cash-bio_carry
        owners_cf.append(owner_cf)
        rows.append({'year':y,'revenue':rev,'owner_operating_fcfe':owner_cf,'buffer_growth':buffer_growth,'parent_statutory_reserve':reserves['P'],'source_capacity_open_budget':capacity_open,'total_remittance_friction':total_friction,'internal_interest_tax':taxcash,'internal_principal_repaid':internal_principal,'realization_legal_profit':sale['profit'],'future_principal_probe':probe,'maintenance_capex':.60*(1+g)**max(0,y-5),'maintenance_depreciation':.60*(1+g)**max(0,y-5),'operating_owner_profit':operating_owner,'net_investment':inv,'capital_accumulated':capital,'parent_distribution':d,'distribution_per_share':d/SHARES,'parent_cash':cash['P'],'group_cash':sum(cash.values()),'parent_legal_retained':ret['P'],'consolidated_earnings_budget':group_ret,'group_profit_budget':group_profit,'subsidiary_cash_received':up,'noncash_offset':offset,'internal_interest_eliminated':intr,'remaining_internal_loan':loans['P_owes_W'],'minority_cash_paid':minor,'external_debt':sum(debt.values()),'debt_repaid':settled_debt,'bio_carry_cost_loan_added':bio_carry,'bio_subscription_paid':subscription,'bio_operating_loan_added':new_bio_loan,'bio_bank_service_loan_added':bio_service_this_year,'bio_equity_cost':bio_equity_cost,'bio_parent_impairment':bio_parent_impairment,'bio_exit_record':bio_exit_record,'bio_closed':bio_closed,'bio_loan_repayment':bio_loan_repayment,'bio_loan_remaining':loans['Bio_owes_P'],'bio_capital_paid':inject,'bio_funding_cumulative':bio_funded,'bio_loss_carryforward':ret['Bio'],'portfolio_remaining':port,'portfolio_capital_realized':realized,'portfolio_income':portfolio_income,'old_payables_paid':oldpay,'purchase_new_share':purchase,'entities':detail})
    # Every source is an ECONOMIC remittance budget, not a statutory pool.
    # All extra cash has actually left; only necessary operating buffers remain.
    assert sum(debt.values())<1e-8 and abs(port)<1e-8
    assert all(abs(cash[k]-buffer[k])<1e-7 for k in cash if k!='Bio'),('terminal sweep incomplete',cash,buffer)
    assert cash['Bio']<1e-8,('unreleased Bio financial capital',cash['Bio'])
    assert bio_closed and abs(loans['Bio_owes_P'])<1e-9 and bio_equity_cost==0.
    last=rows[-1]
    # Actual final-year cash waterfall: terminal homogeneity must hold;
    # no parallel formula that bypasses retained capital, tax or financing.
    assert abs(divs[-1]/divs[-2]-(1+g))<1e-8,('terminal not stable',name,divs[-2:])
    terminal=divs[-1]*(1+g)/(r-g)
    value=pv_cash(divs,terminal,r)
    tv5=(sum(divs[y-1]/(1+r)**(y-5) for y in range(6,horizon+1))+terminal/(1+r)**(horizon-5))/SHARES
    pvd5=sum(divs[y-1]/SHARES/(1+r)**y for y in range(1,6))
    init_owner_cash=sum((CASH[k]-BUFFER[k])*OWN.get(k,1) for k in CASH)
    # Parent funds Bio bank service in full absent realized counter-guarantee payment.
    debt0_owner=sum(DEBT[k]*(1 if k=='Bio' else OWN[k]) for k in DEBT)
    aux=(sum(owners_cf[i]/(1+r)**(i+1) for i in range(horizon))+owners_cf[-1]*(1+g)/(r-g)/(1+r)**horizon+init_owner_cash-debt0_owner+sum(a/(1+r)**(yy+delay) for yy,a,_ in PORT))/SHARES
    return {'scenario':name,'r':r,'g':g,'roic':roic,'delay':delay,'value_per_share':value,'tv5_per_share':tv5,'first5_dps':[v/SHARES for v in divs[:5]],'pv_first5_dps':pvd5,'tv5_pv_share':(value-pvd5)/value,'aux_value_per_share':aux,'bio_exit_record':bio_exit_record,'bio_subscription_cumulative':bio_subscription_paid,'bio_operating_loans_cumulative':bio_operating_loans,'bio_service_loans_cumulative':bio_service_loans,'bio_exit_support':bio_exit_support,'bio_carry_loans_cumulative':bio_carry_loans,'terminal_horizon':horizon,'terminal_at_horizon':terminal,'source_capacity_scale':source_capacity_scale,'source_cost':source_cost,'foreign_friction':foreign_friction,'internal_tax':internal_tax,'terminal_distribution_growth_check':divs[-1]/divs[-2]-1,'rows':rows}

def tests():
    # Same production valuation function, independently known 2-year hand example.
    assert abs(pv_cash([1,1],10,.1,1)-(1/1.1+11/1.21))<1e-12
    a,res=legal_update(-2,1);assert a==-1 and res==0
    a,res=legal_update(-.5,1);assert abs(a-.45)<1e-12 and abs(res-.05)<1e-12
    a,res=legal_update(2,1);assert abs(a-2.9)<1e-12 and abs(res-.1)<1e-12
    h=run(hand_case=True)
    # P opens with cash/profit 1; economic W source earns 1 and pays .8.
    # P pays 1.8, W retains .2 cash and .2 economic earnings capacity.
    assert all(abs(h[k]-v)<1e-10 for k,v in {'distribution':1.8,'parent_cash':0.,'subsidiary_cash':.2,'parent_legal_retained':0.,'subsidiary_legal_retained':.2,'reserve':0.}.items()),h
    try:run(liquidity_shock=10.)
    except ValueError:pass
    else:raise AssertionError('unbounded financing failure not detected')
    try:run(operating_loss_shock=10.)
    except ValueError as e:assert 'zero common distribution' in str(e)
    else:raise AssertionError('operating loss did not force zero-D cash failure')
    assert statutory(0.,10.,20.,5.)[2]==1.
    assert statutory(-8.,10.,20.,0.)[2]==.2
    assert statutory(0.,10.,20.,10.)[2]==0.
    assert statutory(0.,10.,40.,10.)[2]==1.
    assert statutory(0.,10.,20.,10.,voluntary=1.)[3]==1.
    assert settle_receivable(2.,3.,1.,1.)==(3.,3.,0.)
    cr=capital_realization(10.,10.,1.,.25,.6,100.,.1)
    assert abs(cr['cash']-5.4)<1e-10 and abs(cr['profit']+.6)<1e-10 and cr['shares']==90.
    assert capital_realization(12.,10.,0.,.25,.5,100.)['cash']==5.75
    z=bio_realize(10.,.1,2.,4.,8.,.6,10.)
    assert z['loan_repaid']==4. and abs(z['equity_parent']-1.8)<1e-10 and abs(z['minority_paid']-1.2)<1e-10
    assert z['shortfall_support']==0. and abs(z['parent_legal_loss']-6.2)<1e-10
    z=bio_realize(1.,0.,2.,3.,8.,.6,5.)
    assert z['shortfall_support']==1. and z['loan_writeoff']==3. and z['parent_legal_loss']==12.
    assert z['tax']==0.
    return {'production_operating_legal_cash_hand_case':h,'zero_available_cash_financing_failure':True,'production_pv_hand_case':True,'accumulated_loss_and_reserve_cases':True}

def cases():
    return {'core_low':dict(r=.102,g=.015,roic=.12),'core_high':dict(r=.092,g=.02,roic=.15),
    'base':{},'cyclical':dict(name='cyclical'),'structural':dict(name='structural'),
    'optimistic':dict(name='optimistic'),'all_financial_release_plus5':dict(delay=5,remittance_delay=5),
    'delay_plus5':dict(delay=5),'no_legal_offset':dict(no_offset=True),'parent_cash_minus05':dict(parent_shift=-.5),
    'r_plus1pct':dict(r=.1075),'source_friction_5pct':dict(source_cost=.05),
    'foreign_friction_15pct':dict(foreign_friction=.15),'zero_growth':dict(g=0),
    'remittance_plus10':dict(remittance_delay=10),
    'without_internal_tax':dict(internal_tax=0.),'no_opening_source_earnings':dict(old_source_scale=0.),
    'bio_low_recovery':dict(bio_gross=.30,bio_other_creditors=.50),
    'bio_high_recovery':dict(bio_gross=.65,bio_other_creditors=.20),
    'bio_exit_delay5':dict(bio_exit_delay=5),
    'bio_ownership_6654':dict(bio_ownership=.6654),
    'future_cash_20':dict(probe_year=20,probe_amount=.1),
    'future_cash_80':dict(probe_year=80,probe_amount=.1),
    'future_cash_160':dict(probe_year=160,probe_amount=.1),
    'horizon_80':dict(horizon=80),'horizon_160':dict(horizon=160),'horizon_320':dict(horizon=320)}

def build_full():
    out={'units':'CNY billion / billion initial common shares','shares':SHARES,
        'method':'Real parent statutory constraint, named economic source remittance budgets (not legal subsidiaries)',
        'opening_cash':CASH,'opening_debt':DEBT,'profit_budgets':PROF,'scenario_inputs':SCENARIOS,
        'case_inputs':cases(),'tests':tests()}
    for k,v in cases().items():out[k]=run(**v)
    # Cross-scope 2024 technology creditors may exceed the H1 antibody-derived proxy.
    # Do not silently cap them at the convenient .50bn sensitivity endpoint.
    try:run(bio_gross=.30,bio_other_creditors=.95)
    except ValueError as e:
        out['bio_unfunded_platform_creditor_stress']={'inputs':{'bio_gross':.30,'bio_other_creditors':.95},'feasible':False,'year':10,'value_per_share':None,'shortfall':.95-.30*.95,'support_limit':.25,'unfunded_gap':.95-.30*.95-.25,'reason':str(e)}
    else:raise AssertionError('Whole-platform creditor stress must fail finite support')
    return out

def full_bytes(out):return json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()+b'\n'
def pack_output(out):
 raw=full_bytes(out);z=gzip.compress(raw,compresslevel=9,mtime=0)
 summary={k:{a:v[a] for a in ['value_per_share','tv5_per_share','first5_dps','aux_value_per_share']} for k,v in out.items() if isinstance(v,dict) and 'rows' in v}
 summary['bio_unfunded_platform_creditor_stress']=out['bio_unfunded_platform_creditor_stress']
 return {'schema':'lossless_json_gzip_base64_v1','units':out['units'],'readable_summary':summary,'expanded_filename':'expanded-complete.json','expanded_bytes':len(raw),'expanded_sha256':hashlib.sha256(raw).hexdigest(),'gzip_mtime':0,'gzip_sha256':hashlib.sha256(z).hexdigest(),'top_level_fields':sorted(out),'data':base64.b64encode(z).decode('ascii'),'expand_command':'python 2026-Q3.py --expand 2026-Q3-output.json expanded-complete.json','complete_schema':'All original fields retained: inputs, actual tests,27 complete scenario objects including every annual source cash/profit/capital/loan/debt/dividend row; failed platform-creditor stress explicitly value null. readable_summary is not the complete annual output.'}
def expand_output(p):
 z=gzip.decompress(base64.b64decode(p['data']));assert len(z)==p['expanded_bytes'] and hashlib.sha256(z).hexdigest()==p['expanded_sha256'];o=json.loads(z);assert sorted(o)==p['top_level_fields'];return o
if __name__=='__main__':
 if len(sys.argv)==4 and sys.argv[1]=='--expand':Path(sys.argv[3]).write_bytes(full_bytes(expand_output(json.loads(Path(sys.argv[2]).read_text()))))
 else:
  o=build_full();p=pack_output(o);assert expand_output(p)==o;Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(p,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n');print(json.dumps(p['readable_summary'],ensure_ascii=False))

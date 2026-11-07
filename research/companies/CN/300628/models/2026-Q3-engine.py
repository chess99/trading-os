#!/usr/bin/env python3
"""CN:300628 2026-Q3. Stdlib only. Units CNY billion, shares billion.
Run: python 2026-Q3.py [--output PATH] [--expand PATH]
No prices. Parent legal/cash constraints plus explicitly conditional subsidiary economic upstream budgets.
"""
import argparse, copy, hashlib, json, math, gzip, base64
from pathlib import Path

SPEC={'revenue':6.8,'nwc':2.6,'fixed':1.45,'shares':1.266918377,'cash':[4.5,.30,.14427769984],
      'capital_premium':.97939268030,'retained':[6.65,0.,0.],'reserve':[.6333735575,0.,0.],'paid':[1.266918377,None,None],
      'registered':[1.266918377,.5052,None],'debt':[.01116919063,0.,0.],
      'interloan':[.65,.23332019278],'pending':[0.,0.],'r':.095,
      'fin_yield':.02,'credit':[.5,.10,.05],'borrow_rate':.06,'transfer_tax':[0.,.06],'loan_rate':.03,
      'floor':[.09,.01,.005],'operating_share':[.94,.04,.02],'capital_share':[.8,.15,.05],
      'normal_payout':.7,'special_early':.15,'special_mature':1.,'issue':.003,'issue_price':16.58,
      'nwc_ratio':.36,'fixed_ratio':.20,'margin_shift':0.,'sub_paid_fraction':.8,'sub_distribution_rates':[.8,.8],'upstream_realizable':[.5,.5],
      'investment_book':.27356827427,'investment_recovery':.20,'investment_exit_fee':.005,'principal_repay':[.075,.025],'tax_rate':[.15,.25,.21],
      'initial_loss':0.,'deposit':.10686556179,'name':'base'}

def annual_operating(t,p):
    g=[.08,.08,.07,.06,.05][t-1] if t<=5 else .045-.005*(t-6) if t<=10 else .025-.001*(t-10) if t<=20 else .015
    margin=.46-.04*(t-1)/9 if t<=10 else .42-.006*(t-10) if t<=20 else .36
    ratio=p['nwc_ratio']; fixed_ratio=p['fixed_ratio']; loss=0.
    if p['name']=='cyclical':
        if t<=5: g=[-.12,0.,.12,.10,.08][t-1]
        if t<=2: margin-=[.06,.03][t-1]; ratio=.43
    if p['name']=='structural':
        g=-.08 if t==1 else 0. if t<=5 else -.01
        margin=.32-.10*min(t-1,9)/9; ratio=.44; fixed_ratio=.24; loss=.3 if t==2 else 0.
    if p['name']=='optimistic':
        g=[.12,.12,.10,.08,.06][t-1] if t<=5 else .06-.005*(t-6) if t<=10 else .04-.0025*(t-10) if t<=20 else .015
        margin+=.02
    if 'manual' in p:
        g=p['manual'].get('growth',0.); margin=p['manual'].get('margin',0.)
    shift=p['margin_shift'] if t>=p.get('shift_start',1) else 0.
    return g,margin+shift,ratio,fixed_ratio,loss+(p['initial_loss'] if t==1 else 0.)

def legal_credit(entity,profit,domestic=True):
    # Only positive annual profit AFTER replenishing prior losses enters reserve.
    eligible=max(0.,min(profit,entity['retained']+profit))
    addition=min(max(0.,entity['registered']*.5-entity['reserve']),eligible*.1) if domestic else 0.
    entity['reserve']+=addition; entity['retained']+=profit-addition
    return addition

def realize_financial_asset(book, gross, fee, debt=0., ownership=1.):
    """Actual cash waterfall; failure preserves unsatisfied claims, no invented recovery.
    Investment sale is used by run. No assumed subsidiary liquidation is asserted.
    """
    assert min(book,gross,fee,debt)>=0 and 0<=ownership<=1
    fee_paid=min(gross,fee); after_fee=gross-fee_paid
    debt_paid=min(after_fee,debt); residual=after_fee-debt_paid
    return {'gross_cash':gross,'fee_paid':fee_paid,'fee_claim':fee-fee_paid,
            'debt_paid':debt_paid,'debt_claim':debt-debt_paid,
            'net_proceeds':residual,'parent_equity_cash':residual*ownership,
            'minority_cash':residual*(1-ownership),'profit':gross-fee-book,
            'feasible':gross>=fee+debt}

def wind_down_budget(cash, debt, loan, due, nwc, fixed, capital_shares, transfer_rates,
                     wc_recovery=.8, fixed_recovery=.4, fees=.15, tax_friction=.03):
    """Finite realization ECONOMIC budget, not reconstructed statutory subsidiary accounts.
    All amounts CNY bn. Pending dividends/loans are prior claims, not new earnings.
    Tax friction is an explicit total-tax budget; no assumed loss tax credit.
    No liquidation/cancellation is treated complete unless every debt/fee is paid.
    """
    c=list(cash); external=list(debt); l=list(loan); q=list(due)
    gross=[nwc*wc_recovery*x+fixed*fixed_recovery*x for x in capital_shares]
    book=[(nwc+fixed)*x for x in capital_shares]
    fee=[fees*x for x in capital_shares]; taxes=[x*tax_friction for x in gross]
    fee_claim=[];tax_claim=[]
    for i in range(3):
        c[i]+=gross[i]
        paid=min(max(0.,c[i]),fee[i]);fee_claim.append(fee[i]-paid);fee[i]=paid;c[i]-=paid
        paid=min(max(0.,c[i]),taxes[i]);tax_claim.append(taxes[i]-paid);taxes[i]=paid;c[i]-=paid
    ext_paid=[]
    for i in range(3):
        paid=min(external[i],max(0.,c[i])); external[i]-=paid;c[i]-=paid;ext_paid.append(paid)
    loanpaid=[]; oldpaid=[]; leak=0.
    for j in range(2):
        i=j+1; z=min(q[j],max(0.,c[i]));q[j]-=z;c[i]-=z;c[0]+=z*(1-transfer_rates[j]);leak+=z*transfer_rates[j];oldpaid.append(z)
        z=min(l[j],max(0.,c[i]));l[j]-=z;c[i]-=z;c[0]+=z;loanpaid.append(z)
    feasible=min(c)>=-1e-9 and max(external+l+q+fee_claim+tax_claim)<=1e-9
    subsidiary_equity=[max(0,c[i]) for i in [1,2]]
    payout=0.
    if feasible:
        for j in range(2):
            z=c[j+1];c[j+1]=0.;c[0]+=z*(1-transfer_rates[j]);leak+=z*transfer_rates[j]
        payout=c[0];c[0]=0.
    assert abs(sum(c)+payout-(sum(cash)+sum(gross)-sum(fee)-sum(taxes)-sum(ext_paid)-leak))<1e-8
    return {'feasible':feasible,'gross_asset_proceeds':gross,'book_assets_removed':book,
      'realization_loss_before_tax':[gross[i]-book[i]-fee[i] for i in range(3)],
      'exit_fees_paid':fee,'exit_fee_claims':fee_claim,'exit_tax_claims':tax_claim,
      'exit_tax_budget_paid':taxes,'external_debt_paid':ext_paid,'external_debt_claims':external,
      'old_dividend_paid':oldpaid,'dividend_claims':q,'interloan_paid':loanpaid,'interloan_claims':l,
      'subsidiary_equity_proceeds':subsidiary_equity,'transfer_tax_paid':leak,
      'shareholder_cash':payout,'remaining_cash':c,'equity_extinguished':feasible}

def capital_return(e, requested, fee, shares, ownership=1.):
    """Conditional pro-rata registered-capital reduction, not dividend profit.
    Requires caller's legal approval assumption. No payment or cancellation on failure.
    Ordinary shares retired pro rata; a continuing holder retains the same fraction.
    """
    capital_base=e['paid']+e.get('premium',0.)
    if requested<0 or requested>capital_base or e['cash']<requested+fee or shares<=0:
        return {'paid':0.,'fee_paid':0.,'shares':shares,'holder_fraction':1.,'claim':requested,'feasible':False}
    fraction=requested/capital_base if capital_base else 0.
    e['cash']-=requested+fee; e['paid']*=1-fraction
    if 'premium' in e: e['premium']*=1-fraction
    e['registered']*=1-fraction; e['retained']-=fee
    return {'paid':requested*ownership,'minority_paid':requested*(1-ownership),'fee_paid':fee,
            'shares':shares*(1-fraction),'holder_fraction':1-fraction,'claim':0.,'feasible':True}

def run(p=None, years=160):
    p=copy.deepcopy(SPEC if p is None else p)
    E=[{k:p[k][i] for k in ['cash','retained','reserve','paid','registered','debt']} for i in range(3)]
    E[0]['premium']=p['capital_premium']; holder_fraction=1.
    subsidiary_cost_budget=[.505,.0539143104] # H1 mother investment book cost; NOT subsidiary registered capital.
    returned_sub_capital=[0.,0.]
    sales=p['revenue']; nwc=p['nwc']; fixed=p['fixed']; shares=p['shares']; loan=list(p['interloan']); pending=list(p['pending']); rows=[]
    for t in range(1,years+1):
        start=copy.deepcopy(E); oldloan=loan; oldpending=pending; oldshares=shares
        g,margin,wr,kr,loss=annual_operating(t,p); sales*=1+g
        target=sales*wr; dnwc=target-nwc; depreciation=fixed*.1
        capex=max(0.,sales*kr-fixed+depreciation); capital_use=capex+dnwc-depreciation
        ebit=sales*margin; intr=[x*p['loan_rate'] for x in loan]
        realization=realize_financial_asset(p['investment_book'],p['investment_recovery']+p['investment_exit_fee'],p['investment_exit_fee']) if t==3 else None
        realized=realization['profit'] if realization else 0.
        ni=[]; taxes=[]; ebt=[]; interests=[]; yieldcash=[]
        for i,e in enumerate(E):
            fy=(e['cash']+(p['deposit'] if i==0 and t<=2 else 0.))*p['fin_yield']; fi=e['debt']*p['borrow_rate']; yieldcash.append(fy); interests.append(fi)
            before=ebit*p['operating_share'][i]+fy-fi+(sum(intr) if i==0 else -intr[i-1])+(realized-loss if i==0 else 0.)
            tax=max(0.,before)*p['tax_rate'][i]; profit=before-tax; ebt.append(before); taxes.append(tax); ni.append(profit)
            e['cash']+=profit-capital_use*p['capital_share'][i]
        # Investment loss was booked above; restore book principal to produce actual proceeds only.
        principal_recovery=p['investment_book'] if t==3 else 0.
        deposit_release=p['deposit'] if t==2 else 0.
        E[0]['cash']+=principal_recovery+deposit_release
        issuance=p['issue'] if t<=3 else 0.; shares+=issuance; E[0]['paid']+=issuance; E[0]['registered']+=issuance; issue_cash=issuance*p['issue_price']; E[0]['cash']+=issue_cash; E[0]['premium']+=issue_cash-issuance
        floors=[sales*x for x in p['floor']]; borrowed=[]
        for i,e in enumerate(E):
            required=floors[i]+(pending[i-1] if i>0 else 0.)
            borrowing=min(max(0.,required-e['cash']),max(0.,p['credit'][i]-e['debt']))
            e['debt']+=borrowing; e['cash']+=borrowing; borrowed.append(borrowing)
            if e['cash']<required-1e-9:
                return {'name':p['name'],'failure':{'year':t,'entity':['parent','domestic_sub','foreign_sub'][i],'cash':e['cash'],'required':required,'credit_cap':p['credit'][i],'year_state':{'revenue':sales,'ebit':ebit,'ebt':ebt,'net_income':ni,'cash_taxes':taxes,'capital_use':capital_use,'capex':capex,'depreciation':depreciation,'nwc_target':target,'cash_floor':floors,'entities':E,'shares':shares,'issue_cash':issue_cash,'interloan':loan,'pending_dividend':pending,'distribution':None}},'pv':None,'tv5':None,'d':None,'rows':rows}
        old_payment=list(pending); repayments=[]; debt_repaid=[]
        for i in [1,2]:
            j=i-1; E[i]['cash']-=old_payment[j]; E[0]['cash']+=old_payment[j]*(1-p['transfer_tax'][j]); pending[j]=0.
            rloan=min(p['principal_repay'][j],loan[j],max(0.,E[i]['cash']-floors[i])); loan[j]-=rloan
            E[i]['cash']-=rloan; E[0]['cash']+=rloan; repayments.append(rloan)
        for i,e in enumerate(E):
            repayment_external=min(e['debt'],max(0.,e['cash']-floors[i])); e['debt']-=repayment_external; e['cash']-=repayment_external; debt_repaid.append(repayment_external)
        sub_reserve=[]; declared=[]; new_payment=[]
        for i in [1,2]:
            j=i-1; sub_reserve.append(0.); E[i]['retained']+=ni[i] # economic earnings budget, NOT a legal distributable pool
            liquidity_buffer=floors[i]
            if i==2:
                ng,nm,nwr,nkr,nloss=annual_operating(t+1,p); ns=sales*(1+ng)
                nk=fixed-depreciation+capex; nd=nk*.1; nc=max(0.,ns*nkr-nk+nd); nw=ns*nwr-target
                future_ebt=ns*nm*p['operating_share'][i]-E[i]['debt']*p['borrow_rate']-loan[j]*p['loan_rate']
                future_fcf=future_ebt-max(0.,future_ebt)*p['tax_rate'][i]-(nc+nw-nd)*p['capital_share'][i]
                liquidity_buffer=max(liquidity_buffer,ns*p['floor'][i]-future_fcf)
            rate=p['sub_distribution_rates'][j]
            if t<=p.get('suspend_until',0) and i in p.get('suspend_entities',[1,2]): rate=0.
            dec=min(max(0.,E[i]['retained'])*p['upstream_realizable'][j],max(0.,E[i]['cash']-liquidity_buffer)*rate); declared.append(dec)
            payment=dec*p['sub_paid_fraction']; new_payment.append(payment); pending[j]=dec-payment
            E[i]['retained']-=dec; E[i]['cash']-=payment; E[0]['cash']+=payment*(1-p['transfer_tax'][j])
        sub_capital_cash=[0.,0.]; sub_capital_fee=[0.,0.]; sub_capital_tax=[0.,0.]; sub_capital_gain=[0.,0.]
        if p.get('conditional_recapitalization') and t>=30 and t%5==0:
            for i in [1,2]:
                j=i-1
                # Conditional entity-by-entity reduction/realization envelope; actual approvals are unknown.
                # Unchanged 100% control; parent's investment basis falls, never credited to legal income.
                available=max(0.,E[i]['cash']-pending[j]-floors[i]-max(0.,E[i]['retained']))
                amount=available*.5/1.01
                basis_used=min(amount,subsidiary_cost_budget[j]);gain=amount-basis_used
                gain_tax=gain*.25;sub_capital_gain[j]=gain
                fee=amount*.01; tax=amount*p['transfer_tax'][j]+gain_tax
                E[i]['cash']-=amount+fee;E[0]['cash']+=amount-tax
                E[i]['retained']-=fee;ni[i]-=fee
                subsidiary_cost_budget[j]-=basis_used;returned_sub_capital[j]+=amount
                sub_capital_cash[j]=amount;sub_capital_fee[j]=fee;sub_capital_tax[j]=tax
        leakage=sum((old_payment[j]+new_payment[j])*p['transfer_tax'][j] for j in range(2))+sum(sub_capital_tax)
        parent_profit=ni[0]+sum(declared)+sum(sub_capital_gain)-leakage; parent_reserve=legal_credit(E[0],parent_profit)
        normal_request=max(0.,ebit*sum(p['operating_share'][i]*(1-p['tax_rate'][i]) for i in range(3))*p['normal_payout'])
        normal=min(normal_request,max(0.,E[0]['retained']),max(0.,E[0]['cash']-floors[0]))
        E[0]['cash']-=normal; E[0]['retained']-=normal
        special_request=max(0.,E[0]['cash']-floors[0])*(p['special_early'] if t<=10 else p['special_mature'])
        special=min(special_request,max(0.,E[0]['retained']),max(0.,E[0]['cash']-floors[0]))
        E[0]['cash']-=special; E[0]['retained']-=special
        ordinary_distribution=holder_fraction*(normal+special)/shares
        return_of_capital=None; capital_cash=0.;capital_fee=0.
        # Only excess financial cash; preserve operating assets and liquidity. Three-year authorization lag,
        # then periodic pro-rata redemption; no forced operating shutdown and no invented accounting profit.
        if p.get('conditional_recapitalization') and t>=55 and t%5==0 and E[0]['retained']<=.000001:
            requested=min(max(0.,E[0]['cash']-floors[0])*.5/1.01,(E[0]['paid']+E[0]['premium'])*.5)
            return_of_capital=capital_return(E[0],requested,requested*.01,shares)
            if return_of_capital['feasible']:
                capital_cash=return_of_capital['paid'];capital_fee=return_of_capital['fee_paid']
                ordinary_distribution+=holder_fraction*capital_cash/shares
                holder_fraction*=return_of_capital['holder_fraction'];shares=return_of_capital['shares']
        distribution=ordinary_distribution
        expected=sum(x['cash'] for x in start)+sum(ni)-capital_use+principal_recovery+deposit_release+issue_cash+sum(borrowed)-sum(debt_repaid)-leakage-normal-special-capital_cash-capital_fee
        error=sum(e['cash'] for e in E)-expected
        assert abs(error)<1e-8*max(1,sales),('cash bridge',t,error)
        assert abs(E[0]['retained']-(start[0]['retained']+parent_profit-parent_reserve-normal-special-capital_fee))<1e-8*max(1,sales)
        for i in [1,2]:
            assert abs(E[i]['retained']-(start[i]['retained']+ni[i]-sub_reserve[i-1]-declared[i-1]))<1e-8*max(1,sales)
        assert E[0]['reserve']>=0 # Existing reserve may exceed 50% after a lawful capital reduction.
        assert all(e['cash']>=floors[i]-1e-9 for i,e in enumerate(E))
        assert all(E[i]['cash']-pending[i-1]>=floors[i]-1e-9 for i in [1,2])
        fixed=fixed-depreciation+capex; nwc=target
        row={'year':t,'calendar_label':2026+t,'revenue':sales,'growth':g,'ebit_margin':margin,'ebit':ebit,'rd_expense':sales*.09,'sales_management_expense':sales*.10,'gross_margin':margin+.19,'investment_balance':p['investment_book'] if t<3 else 0.,'tax_parent':taxes[0],'tax_sub':sum(taxes[1:]),
             'net_parent_before_dividend':ni[0],'net_sub':sum(ni[1:]),'parent_legal_profit':parent_profit,'depreciation':depreciation,'capex':capex,'dnwc':dnwc,'nwc':nwc,'fixed':fixed,
             'finance_yield_parent':yieldcash[0],'finance_yield_sub':sum(yieldcash[1:]),'interest_parent':interests[0],'interest_sub':sum(interests[1:]),
             'cash_parent':E[0]['cash'],'cash_sub':sum(e['cash'] for e in E[1:]),'debt_parent':E[0]['debt'],'debt_sub':sum(e['debt'] for e in E[1:]),
             'retained_parent':E[0]['retained'],'economic_earnings_sub':sum(e['retained'] for e in E[1:]),'reserve_parent':E[0]['reserve'],'reserve_sub':None,
             'reserve_add_parent':parent_reserve,'reserve_add_sub':None,'paid_parent':E[0]['paid'],'paid_sub':None,
             'floor_parent':floors[0],'floor_sub':sum(floors[1:]),'borrowed_parent':borrowed[0],'borrowed_sub':sum(borrowed[1:]),
             'external_repaid_parent':debt_repaid[0],'external_repaid_sub':sum(debt_repaid[1:]),'interloan':sum(loan),'interloan_repaid':sum(repayments),'interloan_interest':sum(intr),
             'dividend_declared':sum(declared),'old_dividend_paid':sum(old_payment),'new_dividend_paid':sum(new_payment),'dividend_receivable':sum(pending),'transfer_tax_cash':leakage,
             'investment_recovery_cash':p['investment_recovery'] if t==3 else 0.,'investment_gross_cash':realization['gross_cash'] if realization else 0.,'investment_exit_fee_paid':realization['fee_paid'] if realization else 0.,'investment_profit':realized,'deposit_remaining':p['deposit'] if t<2 else 0.,'deposit_release':deposit_release,'litigation_cash':loss,
             'normal_request':normal_request,'normal_cash':normal,'special_request':special_request,'special_cash':special,'distribution':distribution,
             'subsidiary_investment_cost_remaining':list(subsidiary_cost_budget),'subsidiary_capital_return_cash':sub_capital_cash,'subsidiary_capital_return_fees_paid':sub_capital_fee,'subsidiary_capital_return_tax_paid':sub_capital_tax,'subsidiary_capital_realization_gain':sub_capital_gain,'subsidiary_ownership_after_return':[1.,1.],
             'shares':shares,'holder_fraction':holder_fraction,'capital_return_cash':capital_cash,'capital_return_fee_paid':capital_fee,'conditional_capital_return':return_of_capital,'issued_shares':issuance,'issue_cash':issue_cash,'minority_profit':0.,'minority_distribution':0.,'cash_bridge_error':error}
        for i,label in enumerate(['parent','domestic','foreign']):
            for field,value in E[i].items():
                if i and field=='reserve': row[label+'_legal_reserve']=None
                elif i and field=='retained': row[label+'_economic_earnings']=value
                else: row[label+'_'+field]=value
            row[label+'_tax']=taxes[i]; row[label+'_net']=ni[i]
            if i: row[label+'_interloan']=loan[i-1]; row[label+'_dividend_due']=pending[i-1]
        if t==p.get('exit_year'):
            exit_budget=wind_down_budget([e['cash'] for e in E],[e['debt'] for e in E],loan,pending,nwc,fixed,p['capital_share'],p['transfer_tax'])
            row['finite_exit']=exit_budget
            if not exit_budget['feasible']:
                return {'name':p['name'],'failure':{'year':t,'exit_budget':exit_budget},'pv':None,'tv5':None,'d':None,'rows':rows+[row]}
            row['distribution']+=holder_fraction*exit_budget['shareholder_cash']/shares
            row['capital_realization_per_share']=holder_fraction*exit_budget['shareholder_cash']/shares
            # Annual operating closing states above are pre-exit; explicit post-exit states avoid silently deleting claims.
            row['post_exit_shares']=0.;row['post_exit_cash']=exit_budget['remaining_cash']
            rows.append(row)
            break
        rows.append(row)
    rate=p['r']; pv=sum(v['distribution']/(1+rate)**v['year'] for v in rows); tv=sum(v['distribution']/(1+rate)**(v['year']-5) for v in rows if v['year']>5)
    return {'name':p['name'],'failure':None,'pv':pv,'tv5':tv,'d':[x['distribution'] for x in rows[:5]],'terminal_pv_share':tv/(1+rate)**5/pv if pv else None,'parameters':p,'rows':rows}

def scenario(name,**kw):
    p=copy.deepcopy(SPEC); p.update(name=name,**kw); return p

def verify():
    # Exact single-year production function case: revenue1, EBIT .2, tax0, no assets/funding;
    # subsidiary zero, no reserves required, all shareholder cash = .2, PV=.2/1.1.
    p=scenario('hand',revenue=1.,nwc=0.,fixed=0.,shares=1.,cash=[0.,0.,0.],retained=[0.,0.,0.],reserve=[0.,0.,0.],paid=[0.,0.,0.],registered=[0.,0.,0.],debt=[0.,0.,0.],interloan=[0.,0.],pending=[0.,0.],r=.1,
       fin_yield=0.,deposit=0.,credit=[0.,0.,0.],floor=[0.,0.,0.],operating_share=[1.,0.,0.],capital_share=[1.,0.,0.],normal_payout=1.,issue=0.,nwc_ratio=0.,fixed_ratio=0.,tax_rate=[0.,0.,0.],manual={'growth':0.,'margin':.2})
    hand=run(p,1); assert abs(hand['pv']-.2/1.1)<1e-12
    p.update(paid=[.2,0.,0.],registered=[1.,0.,0.]); registered_test=run(p,1)
    assert abs(registered_test['rows'][0]['reserve_add_parent']-.02)<1e-12
    # Real legal-loss catchup: previous retained -.15, profit .2, reserve .005 leaves .045 payout.
    p.update(retained=[-.15,0.,0.],paid=[1.,0.,0.],registered=[1.,0.,0.]); q=run(p,1); assert abs(q['rows'][0]['normal_cash']-.045)<1e-12
    # Old receivable only adds cash, not profit: no operation; .1 collection permits no legal distribution.
    p.update(retained=[0.,0.,0.],paid=[0.,0.,0.],registered=[0.,0.,0.],cash=[0.,.1,0.],pending=[.1,0.],transfer_tax=[0.,0.],manual={'growth':0.,'margin':0.})
    old=run(p,1); assert old['rows'][0]['parent_legal_profit']==0 and old['d']==[0.]
    bad=run(scenario('funding_failure',cash=[0.,0.,0.],initial_loss=12.),160); assert bad['pv'] is None and bad['tv5'] is None
    e={'registered':20.,'paid':10.,'reserve':5.,'retained':0.,'cash':10.}
    assert legal_credit(e,10.)==1.
    e={'registered':20.,'paid':10.,'reserve':10.,'retained':0.,'cash':10.}
    assert legal_credit(e,10.)==0.
    e['registered']=24.; assert legal_credit(e,10.)==1.
    # Tax exempt subsidiary dividend still enters parent accounting profit/reserve.
    e={'registered':20.,'paid':10.,'reserve':5.,'retained':0.,'cash':10.}
    assert legal_credit(e,2.)==.2
    realized=realize_financial_asset(10.,10.,1.,3.,.6)
    assert realized['fee_paid']==1 and realized['debt_paid']==3 and abs(realized['parent_equity_cash']-3.6)<1e-12
    assert realized['profit']==-1 and abs(realized['minority_cash']-2.4)<1e-12
    failed=realize_financial_asset(10.,.5,1.,3.,.6)
    assert not failed['feasible'] and failed['fee_claim']==.5 and failed['debt_claim']==3 and failed['parent_equity_cash']==0
    e={'registered':20.,'paid':10.,'reserve':5.,'retained':0.,'cash':6.}
    reduced=capital_return(e,5.,1.,10.)
    assert reduced['paid']==5 and reduced['shares']==5 and e['cash']==0 and e['retained']==-1 and e['registered']==10
    before=copy.deepcopy(e); refusal=capital_return(e,1.,1.,5.)
    assert not refusal['feasible'] and refusal['shares']==5 and e==before
    w=wind_down_budget([1.,2.,3.],[0.,0.,0.],[.2,.3],[.1,.1],0.,0.,[.8,.15,.05],[0.,0.],fees=1.,tax_friction=0.)
    assert w['feasible'] and abs(w['shareholder_cash']-5.)<1e-12 and sum(w['exit_fees_paid'])==1.
    broken=wind_down_budget([0.,0.,0.],[1.,0.,0.],[0.,0.],[0.,0.],0.,0.,[1.,0.,0.],[0.,0.],fees=0.,tax_friction=0.)
    assert not broken['feasible'] and broken['external_debt_claims'][0]==1 and not broken['equity_extinguished']
    unpaidfee=wind_down_budget([0.,0.,0.],[0.,0.,0.],[0.,0.],[0.,0.],0.,0.,[1.,0.,0.],[0.,0.],fees=1.,tax_friction=0.)
    assert not unpaidfee['feasible'] and unpaidfee['exit_fee_claims']==[1.,0.,0.] and unpaidfee['remaining_cash']==[0.,0.,0.]
    combined=[]
    for exit_year in [55,80,160]:
        v=run(scenario('structural',conditional_recapitalization=True,exit_year=exit_year))
        # Literal original-holder ownership: first 3 years new share issues dilute one original share.
        # Later proportional redemptions do not change its percentage of company cash.
        # Deliberately uses neither output shares nor holder_fraction to derive the entitlement.
        independently_received=[]
        for row in v['rows']:
            cash=row['normal_cash']+row['special_cash']+row['capital_return_cash']
            cash+=row.get('finite_exit',{}).get('shareholder_cash',0.)
            issued_capital=1.266918377+.003*min(row['year'],3)
            independently_received.append(cash/issued_capital)
        independent_pv=sum(amount/1.095**(i+1) for i,amount in enumerate(independently_received))
        max_error=max(abs(a-row['distribution']) for a,row in zip(independently_received,v['rows']))
        last=v['rows'][-1]
        independent_final_cash=last['finite_exit']['shareholder_cash']/1.275918377
        assert last['holder_fraction']<1 and last['capital_return_cash']>=0
        assert abs(last['capital_realization_per_share']-independent_final_cash)<1e-12
        assert max_error<1e-12 and abs(v['pv']-independent_pv)<1e-12
        prior_bug_extra=(last['finite_exit']['shareholder_cash']/last['shares']-independent_final_cash)/1.095**exit_year
        assert prior_bug_extra>0
        combined.append({'exit_year':exit_year,'production_pv':v['pv'],'literal_original_holder_pv':independent_pv,
           'max_annual_original_holder_cash_difference':max_error,'holder_fraction_before_exit':last['holder_fraction'],
           'liquidation_cash_per_original_share':independent_final_cash,'prior_bug_overstatement':prior_bug_extra})
    base=run(); long=run(years=240)
    return {'combined_recapitalization_exit_regressions':combined,'extended_production_regressions':{'registered20_paid10_reserve5_profit10_add':1,'full_reserve_add':0,'new_registered24_add':1,'tax_exempt_dividend_reserve':.2,'asset_realization':realized,'unpaid_claims':failed,'finite_realization':w,'failed_realization':broken,'unpaid_exit_fee':unpaidfee,'capital_return':reduced,'failed_capital_return':refusal},'hand_pv':hand['pv'],'hand_expected':.2/1.1,'loss_catchup_cash':q['rows'][0]['normal_cash'],'old_receivable_profit':old['rows'][0]['parent_legal_profit'],'registered_not_paid_reserve':registered_test['rows'][0]['reserve_add_parent'],
            'failure_test':bad['failure'],'convergence_same_function_160_240':{'pv160':base['pv'],'pv240':long['pv'],'absolute_difference':long['pv']-base['pv']}}

def independently_run(kind='base',years=160):
    R=6.8; K=1.45; W=2.6; shares=1.266918377
    cash=[4.5,.30,.14427769984]; debt=[.01116919063,0.,0.]; earned=[6.65,0.,0.]; reserve=[.6333735575,0.,0.]
    paid=[1.266918377,None,None]; registered=[1.266918377,.5052,None]
    principal=[.65,.23332019278]; due=[0.,0.]; rows=[]; values=[]
    rate={'low':.10,'high':.09}.get(kind,.095)
    for t in range(1,years+1):
        g=([.08,.08,.07,.06,.05][t-1] if t<=5 else .045-.005*(t-6) if t<=10 else .025-.001*(t-10) if t<=20 else .015)
        m=(.46-.04*(t-1)/9 if t<=10 else .42-.006*(t-10) if t<=20 else .36)+{'low':-.01,'high':.01,'margin_down':-.02}.get(kind,0.)
        R*=1+g; newW=.36*R; dep=.1*K; cap=max(0,.2*R-K+dep); dw=newW-W; ops=R*m
        loan_interest=[.03*x for x in principal]; earnings=[]; cash_tax=[]
        for i in range(3):
            earnings.append(ops*[.94,.04,.02][i]+(cash[i]+(.10686556179 if i==0 and t<=2 else 0))*.02-debt[i]*.06+(sum(loan_interest) if i==0 else -loan_interest[i-1])-(.07356827427 if i==0 and t==3 else 0.))
            cash_tax.append(max(0.,earnings[-1])*[.15,.25,.21][i]); earnings[-1]-=cash_tax[-1]
            cash[i]+=earnings[-1]+(dep-cap-dw)*[.8,.15,.05][i]
        cash[0]+=(.27356827427 if t==3 else 0.)+(.10686556179 if t==2 else 0.)
        issue=.003 if t<=3 else 0.; shares+=issue; paid[0]+=issue; registered[0]+=issue; cash[0]+=issue*16.58
        floors=[R*.09,R*.01,R*.005]
        for i in range(3):
            need=max(0,floors[i]+(due[i-1] if i else 0)-cash[i]); draw=min(need,max(0,[.5,.10,.05][i]-debt[i])); cash[i]+=draw; debt[i]+=draw
            if cash[i]<floors[i]+(due[i-1] if i else 0)-1e-9: return {'pv':None,'failure':t}
        receipts=list(due)
        for i in [1,2]:
            cash[i]-=due[i-1]; cash[0]+=due[i-1]*(1-[0.,.06][i-1]); due[i-1]=0.
            repay=min([.075,.025][i-1],principal[i-1],max(0,cash[i]-floors[i])); principal[i-1]-=repay; cash[i]-=repay; cash[0]+=repay
        for i in range(3):
            repayment=min(debt[i],max(0,cash[i]-floors[i])); debt[i]-=repayment; cash[i]-=repayment
        announcements=[]; paidnow=[]
        for i in [1,2]:
            earned[i]+=earnings[i]
            declaration=min(max(0,earned[i])*.5,max(0,cash[i]-floors[i])*.8); announcements.append(declaration)
            settled=declaration*.8; paidnow.append(settled); cash[i]-=settled; cash[0]+=settled*(1-[0.,.06][i-1]); due[i-1]=declaration-settled; earned[i]-=declaration
        profit=earnings[0]+sum(announcements)-(receipts[1]+paidnow[1])*.06
        a=min(max(0,registered[0]*.5-reserve[0]),max(0,min(profit,earned[0]+profit))*.1); reserve[0]+=a; earned[0]+=profit-a
        regular=min(max(0,ops*(.94*.85+.04*.75+.02*.79)*.7),max(0,earned[0]),max(0,cash[0]-floors[0])); earned[0]-=regular; cash[0]-=regular
        special=min(max(0,earned[0]),max(0,cash[0]-floors[0])*(.15 if t<=10 else 1)); earned[0]-=special; cash[0]-=special
        d=(regular+special)/shares; values.append(d); W=newW; K=K-dep+cap
        row={'year':t,'revenue':R,'ebit':ops,'cash_parent':cash[0],'cash_sub':sum(cash[1:]),'debt_parent':debt[0],'debt_sub':sum(debt[1:]),'retained_parent':earned[0],'economic_earnings_sub':sum(earned[1:]),'reserve_parent':reserve[0],'reserve_sub':None,'interloan':sum(principal),'dividend_receivable':sum(due),'shares':shares,'distribution':d,'nwc':W,'fixed':K}
        for i,name in enumerate(['parent','domestic','foreign']):
            for key,ary in [('cash',cash),('debt',debt),('retained',earned),('reserve',reserve),('paid',paid),('registered',registered),('tax',cash_tax),('net',earnings)]:
                if i and key=='reserve': row[name+'_legal_reserve']=None
                elif i and key=='retained': row[name+'_economic_earnings']=ary[i]
                else: row[name+'_'+key]=ary[i]
            if i:row[name+'_interloan']=principal[i-1];row[name+'_dividend_due']=due[i-1]
        rows.append(row)
    return {'pv':sum(x/(1+rate)**(i+1) for i,x in enumerate(values)),'tv5':sum(x/(1+rate)**(i-4) for i,x in enumerate(values) if i>=5),'d':values[:5],'rows':rows}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',default=str(Path(__file__).with_name('2026-Q3-output.json'))); parser.add_argument('--expand'); a=parser.parse_args()
    if a.expand:
        x=json.loads(Path(a.expand).read_text())
        if x.get('encoding')=='gzip+base64':
            raw=gzip.decompress(base64.b64decode(x['payload']))
            assert hashlib.sha256(raw).hexdigest()==x['expanded_sha256']
            print(raw.decode(),end='')
        else: print(json.dumps(x,ensure_ascii=False,separators=(',',':'),sort_keys=True),end='')
        return
    configs={'base':scenario('base'),'low':scenario('low',r=.10,margin_shift=-.01),'high':scenario('high',r=.09,margin_shift=.01),
       'cyclical':scenario('cyclical'),'structural':scenario('structural',conditional_recapitalization=True),'structural_exit_alternative':scenario('structural',exit_year=30),'optimistic':scenario('optimistic'),'structural_continuing_trap_diagnostic':dict(scenario('structural'),name='structural'),
       'holder_low':scenario('holder_low',r=.10,margin_shift=-.01,shift_start=6),'holder_high':scenario('holder_high',r=.09,margin_shift=.01,shift_start=6),
       'margin_down':scenario('margin_down',margin_shift=-.02),'upstream_delay':scenario('upstream_delay',sub_paid_fraction=0.),
       'capital_intensity':scenario('capital_intensity',nwc_ratio=.44,fixed_ratio=.24),'slower_release':scenario('slower_release',special_early=.05),'partial_mature_release':scenario('partial_mature_release',special_mature=.5),
       'recap_then_exit55':scenario('structural',conditional_recapitalization=True,exit_year=55),
       'recap_then_exit80':scenario('structural',conditional_recapitalization=True,exit_year=80),
       'recap_then_exit160':scenario('structural',conditional_recapitalization=True,exit_year=160),
       'funding_failure':scenario('funding_failure',cash=[0.,0.,0.],initial_loss=12.),'no_credit':scenario('no_credit',credit=[0.,0.,0.]),
       'permanent_refusal_diagnostic':scenario('permanent_refusal_diagnostic',sub_distribution_rates=[0.,0.]),'permanent_foreign_refusal_diagnostic':scenario('permanent_foreign_refusal_diagnostic',sub_distribution_rates=[.8,0.]),
       'ten_year_sub_suspension':scenario('ten_year_sub_suspension',suspend_until=10),'ten_year_foreign_suspension':scenario('ten_year_foreign_suspension',suspend_until=10,suspend_entities=[2]),
       'sub_loss_budget':scenario('sub_loss_budget',retained=[6.65,-.10,-.05],reserve=[.6333735575,0.,0.])}
    results={k:run(v) for k,v in configs.items()}
    for k in ['holder_low','holder_high']:
        assert results[k]['rows'][:5]==results['base']['rows'][:5]
    # Auxiliary no-growth earnings-power capitalization. Excludes financial earnings; counts liquid surplus once,
    # normalised EBIT 6.8*.44, tax15%, maintenance capex=DA; operating cash floor6.8*.105.
    auxiliary={'method':'no_growth_owner_earnings_power','normalized_owner_earnings':6.8*.44*(.94*.85+.04*.75+.02*.79),'required_cash':6.8*.105,
      'financial_surplus':5.05114326163-6.8*.105-.01116919063,'noncurrent_recovery':.2,'issue_proceeds_pv':sum(.003*16.58/1.095**t for t in [1,2,3]),'diluted_shares':1.275918377}
    auxiliary['low']=(auxiliary['normalized_owner_earnings']/.10+auxiliary['financial_surplus']+.2+auxiliary['issue_proceeds_pv'])/1.275918377
    auxiliary['high']=(auxiliary['normalized_owner_earnings']/.09+auxiliary['financial_surplus']+.2+auxiliary['issue_proceeds_pv'])/1.275918377
    checks=verify()
    # Independent output is used only for ex-post comparison, never a model input.
    oracle={k:independently_run(k) for k in ['base','low','high','margin_down']}
    diffs={}
    for k in oracle:
        delta=max(abs(results[k]['rows'][j][field]-val) for j,row in enumerate(oracle[k]['rows']) for field,val in row.items() if isinstance(val,(int,float)))
        assert delta<1e-8 and abs(results[k]['pv']-oracle[k]['pv'])<1e-8
        diffs[k]={'max_annual_state_difference':delta,'pv_difference':results[k]['pv']-oracle[k]['pv'],'tv5_difference':results[k]['tv5']-oracle[k]['tv5']}
    checks['independent_comparison']=diffs
    checks['structural_tail']={str(n):{'pv':v['pv'],'last_row':v['rows'][-1]} for n in [160,240,400] for v in [run(scenario('structural',conditional_recapitalization=True),n)]}
    checks['all_major_400_year_paths']={k:{'failure':v['failure'],'pv':v['pv']} for k in ['base','cyclical','structural','optimistic'] for v in [run(scenario(k,**({'conditional_recapitalization':True} if k=='structural' else {})),400)]}
    assert all(v['failure'] is None for v in checks['all_major_400_year_paths'].values())
    checks['residual_financial_cash_bounds']={str(n):{
        'parent_surplus':max(0.,v['rows'][-1]['cash_parent']-v['rows'][-1]['floor_parent']),
        'group_budget_surplus':max(0.,v['rows'][-1]['cash_parent']-v['rows'][-1]['floor_parent'])+max(0.,v['rows'][-1]['cash_sub']-v['rows'][-1]['floor_sub']),
        'parent_current_pv_gross_bound':max(0.,v['rows'][-1]['cash_parent']-v['rows'][-1]['floor_parent'])/1.275918377/1.095**n,
        'group_current_pv_gross_bound':(max(0.,v['rows'][-1]['cash_parent']-v['rows'][-1]['floor_parent'])+max(0.,v['rows'][-1]['cash_sub']-v['rows'][-1]['floor_sub']))/1.275918377/1.095**n,
        'caveat':'Gross no-fee upper-bound for residual financial cash only, not proof of full realization or legal execution; cannot be added on top of future distributions that already realize the same cash.'}
        for n in [160,240,400] for v in [run(scenario('structural',conditional_recapitalization=True),n)]}
    checks['same_economics_method_comparison']={k:{'old_pv':results['structural_continuing_trap_diagnostic']['pv'],'new_pv':results['structural']['pv'],'delta':results['structural']['pv']-results['structural_continuing_trap_diagnostic']['pv']} for k in ['conditional_financial_capital_return']}
    checks['sensitivity_year1_and20']={k:{str(t):results[k]['rows'][t-1]['distribution'] for t in [1,20]} for k in ['base','margin_down','capital_intensity','slower_release']}
    output={'schema':'yealink_entity_distribution_v1','units':'CNY billion except per-share CNY, shares billion','years':160,'as_of':'2026-10-26T20:36:00+00:00','legal_scope':'Only listed parent is a legal profit/reserve pool. Domestic and foreign subsidiary aggregates are economic cash/upstream-budget pools, not legal entities; no statutory reserve pooling. Future declared upstream is an explicit realizability assumption, tested with ten-year upstream suspension followed by finite recovery; not a permanent financial-principal trap.',
            'valuation_scope':{'structural_continuing_trap_diagnostic':'Old shrinking perpetual-run cash-distribution diagnostic. Year52 profit capacity exhausted; unreturned claims/capital remain, not a total fair-value conclusion.', 'permanent_refusal_diagnostic':'Only PV of actual forecast distributions. Undistributed subsidiary equity/claims remain in annual rows; this is a governance/cash-realization diagnostic, NOT total fair value or a conclusion of zero principal value.','permanent_foreign_refusal_diagnostic':'Same boundary for foreign upstream only.'},'scenarios':results,'auxiliary':auxiliary,'verification':checks}
    canonical=json.dumps(output,ensure_ascii=False,separators=(',',':'),sort_keys=True)
    assert json.loads(canonical)==output
    raw=canonical.encode()
    summary={k:{f:v[f] for f in ['pv','tv5','d','failure']} for k,v in results.items()}
    package={'symbol':'CN:300628','name':'亿联网络','period':'2026-Q3','schema':'lossless_annual_model_package_v1','encoding':'gzip+base64',
       'expanded_sha256':hashlib.sha256(raw).hexdigest(),'expanded_bytes':len(raw),'units':output['units'],
       'years':160,'annual_schema':sorted(set().union(*(row.keys() for result in results.values() for row in result['rows']))),'summary':summary,'auxiliary':auxiliary,'verification':checks,
       'expand':'python 2026-Q3.py --expand 2026-Q3-output.json > expanded.json',
       'payload':base64.b64encode(gzip.compress(raw,mtime=0)).decode()}
    assert gzip.decompress(base64.b64decode(package['payload']))==raw
    packed=json.dumps(package,ensure_ascii=False,separators=(',',':'),sort_keys=True)
    Path(a.output).write_text(packed); Path(a.output+'.sha256').write_text(hashlib.sha256(packed.encode()).hexdigest()+'\n')
    print(json.dumps({'values':{k:{f:v[f] for f in ['pv','tv5','d','failure']} for k,v in results.items()},'auxiliary':auxiliary,'verification':checks},ensure_ascii=False,indent=2))
if __name__=='__main__': main()

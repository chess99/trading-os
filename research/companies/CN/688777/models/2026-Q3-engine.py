#!/usr/bin/env python3
"""CNY billion and billion shares. Source-led, explicit conditional budgets.
Five rolling twelve-month holder periods; years 6-10 fade; terminal at end 10.
Full results only XZ. No quotes, IRR, trading logic, or external dependencies.
"""
import copy,json,math,lzma,hashlib,pathlib,numbers
ROOT=pathlib.Path(__file__).resolve().parent
SOURCE=json.loads('{\n  "inputs": {\n    "base": {\n      "rev": [\n        8.2,\n        8.75,\n        9.3,\n        9.85,\n        10.4\n      ],\n      "gross": [\n        0.319,\n        0.324,\n        0.329,\n        0.332,\n        0.335\n      ],\n      "rd": [\n        0.96,\n        1,\n        1.04,\n        1.08,\n        1.12\n      ],\n      "sga": [\n        1.4,\n        1.46,\n        1.52,\n        1.58,\n        1.64\n      ],\n      "vat": 0.02,\n      "loss": 0.02,\n      "nwc": 0.27\n    },\n    "weak": {\n      "rev": [\n        7.5,\n        7.7,\n        8,\n        8.3,\n        8.6\n      ],\n      "gross": [\n        0.31,\n        0.311,\n        0.312,\n        0.313,\n        0.315\n      ],\n      "rd": [\n        0.95,\n        0.96,\n        0.98,\n        1,\n        1.01\n      ],\n      "sga": [\n        1.4,\n        1.42,\n        1.45,\n        1.47,\n        1.5\n      ],\n      "vat": 0.018,\n      "loss": 0.022,\n      "nwc": 0.3\n    },\n    "reuse": {\n      "rev": [\n        8.5,\n        9.3,\n        10.2,\n        11.1,\n        12\n      ],\n      "gross": [\n        0.325,\n        0.334,\n        0.342,\n        0.348,\n        0.352\n      ],\n      "rd": [\n        1,\n        1.05,\n        1.1,\n        1.15,\n        1.2\n      ],\n      "sga": [\n        1.45,\n        1.53,\n        1.62,\n        1.71,\n        1.8\n      ],\n      "vat": 0.02,\n      "loss": 0.019,\n      "nwc": 0.26\n    }\n  },\n  "rows": {\n    "base": [\n      {\n        "year": 2027,\n        "rev": 8.2,\n        "ebit": 0.19019999999999992,\n        "nwc": 2.214,\n        "fcff": 0.10417600000000016\n      },\n      {\n        "year": 2028,\n        "rev": 8.75,\n        "ebit": 0.30500000000000016,\n        "nwc": 2.3625000000000003,\n        "fcff": 0.06739999999999988\n      },\n      {\n        "year": 2029,\n        "rev": 9.3,\n        "ebit": 0.42530000000000046,\n        "nwc": 2.5110000000000006,\n        "fcff": 0.16996400000000006\n      },\n      {\n        "year": 2030,\n        "rev": 9.85,\n        "ebit": 0.5313999999999997,\n        "nwc": 2.6595,\n        "fcff": 0.2600320000000003\n      },\n      {\n        "year": 2031,\n        "rev": 10.4,\n        "ebit": 0.6408000000000003,\n        "nwc": 2.8080000000000003,\n        "fcff": 0.3530039999999999\n      }\n    ],\n    "weak": [\n      {\n        "year": 2027,\n        "rev": 7.5,\n        "ebit": -0.11499999999999999,\n        "nwc": 2.25,\n        "fcff": -0.20999999999999983\n      },\n      {\n        "year": 2028,\n        "rev": 7.7,\n        "ebit": -0.0777000000000001,\n        "nwc": 2.31,\n        "fcff": -0.18390000000000017\n      },\n      {\n        "year": 2029,\n        "rev": 8,\n        "ebit": -0.030000000000000027,\n        "nwc": 2.4,\n        "fcff": -0.1679999999999999\n      },\n      {\n        "year": 2030,\n        "rev": 8.3,\n        "ebit": 0.028299999999999992,\n        "nwc": 2.49,\n        "fcff": -0.11489600000000033\n      },\n      {\n        "year": 2031,\n        "rev": 8.6,\n        "ebit": 0.09579999999999989,\n        "nwc": 2.5799999999999996,\n        "fcff": -0.05729599999999954\n      }\n    ],\n    "reuse": [\n      {\n        "year": 2027,\n        "rev": 8.5,\n        "ebit": 0.2529999999999999,\n        "nwc": 2.21,\n        "fcff": 0.16164000000000006\n      },\n      {\n        "year": 2028,\n        "rev": 9.3,\n        "ebit": 0.46110000000000007,\n        "nwc": 2.418,\n        "fcff": 0.14196799999999993\n      },\n      {\n        "year": 2029,\n        "rev": 10.2,\n        "ebit": 0.6969999999999996,\n        "nwc": 2.6519999999999997,\n        "fcff": 0.3181600000000001\n      },\n      {\n        "year": 2030,\n        "rev": 11.1,\n        "ebit": 0.9250999999999996,\n        "nwc": 2.886,\n        "fcff": 0.5134879999999993\n      },\n      {\n        "year": 2031,\n        "rev": 12,\n        "ebit": 1.1399999999999995,\n        "nwc": 3.12,\n        "fcff": 0.6971999999999994\n      }\n    ]\n  }\n}\n')['inputs']
AI_MIX={
 'base':dict(ai=[.95,1.2,1.5,1.8,2.1],gross=[.38,.40,.42,.44,.45]),
 'weak':dict(ai=[.7,.8,.95,1.1,1.2],gross=[.30,.31,.32,.33,.34]),
 'reuse':dict(ai=[1.1,1.6,2.2,2.8,3.5],gross=[.38,.41,.44,.46,.48])}
ISSUED=.791189527; TREASURY=.013743431; ACTIVE=ISSUED-TREASURY
OPEN_GROUP_CASH=2.44516053239+1.68000000164-.16261763475
OPEN_DEBT=.94633739716+.00681609903+.01413246791
# Parent as-of budget, not a disclosed September standalone balance:
# H1 unrestricted parent cash+wealth minus entire group H1->Q3 liquidity decline
# and known Oct repurchases. Debt is retained/renewed, not subtracted from cash.
OPEN_PARENT_CASH=.80715919528+1.60000000164-((2.80223757987+1.60000000164)-(2.44516053239+1.68000000164))-.16261763475
OPEN_NWC=2.711144717; OPEN_LONG=1.277 # explicit rounded operating asset budget; not liquidation value
OPEN_COMMON_PAYABLE=(ISSUED-TREASURY)*.10
PARENT_RE=1.80-OPEN_COMMON_PAYABLE; PARENT_RESERVE=.3955947635
CHILDREN=[
 dict(name='富阳',profit=.042813,cash=0.,re=0.,reserve=0.,capital=.072,ownership=1.,direct=1.,loan=.16817455933,floor=.020),
 dict(name='流体',profit=.0289244,cash=0.,re=0.,reserve=0.,capital=.1,ownership=.982731,direct=.982731,loan=.09934020139,floor=.020),
 dict(name='自动化仪表',profit=.1071798,cash=0.,re=0.,reserve=0.,capital=.05002,ownership=1.,direct=.720232,loan=.0122805558,floor=.040),
 dict(name='软件',profit=.0025512,cash=0.,re=0.,reserve=0.,capital=.04,ownership=1.,direct=1.,loan=0.,floor=.005),
 dict(name='工自仪控股',profit=.0095814,cash=0.,re=0.,reserve=0.,capital=.4,ownership=1.,direct=1.,loan=0.,floor=.020)]

def reserve_transfer(open_re, own_profit, new_dividend, balance, capital, continuing=False):
    # Annual aggregate against ORIGINAL opening RE; no sequential loss/reserve bug.
    annual_profit=own_profit+new_dividend
    post_loss=max(0.,open_re+annual_profit)
    earned_after_old_loss=max(0.,annual_profit+min(0.,open_re))
    capacity=math.inf if continuing else max(0.,.5*capital-balance)
    transfer=min(.1*earned_after_old_loss,post_loss,capacity)
    return transfer,open_re+annual_profit-transfer

def legal_step(state, own_profit, own_cash, child_inputs, target_cash_dividend,
               other_cash=0., prior_dividend_collection=0., continuing=False,
               parent_floor=.6, child_start=True, child_lag=1):
    """Production parent+children one-year ledger; used for paths AND handcases.
    Child current declaration is parent current profit. Prior dividend receipt is cash only.
    Declaration immediately reduces child RE and creates a payable when lagged.
    No intercompany legal netting. Intermediary share is NOT immediate parent cash.
    """
    s=copy.deepcopy(state); opening=copy.deepcopy(s); child_rows=[]
    parent_new=0.; parent_received=prior_dividend_collection; parent_loan=0.; nci_paid=0.; indirect_paid=0.
    for ch,ci in zip(s['children'],child_inputs):
        opencash=ch['cash']; openre=ch['re']; oldpay=ch.get('payable',0.)
        ch['cash']+=ci['cash']
        paid_old=min(oldpay,max(0.,ch['cash']-ci.get('floor',0.)))
        ch['cash']-=paid_old; ch['payable']=oldpay-paid_old
        parent_received+=paid_old*ch['direct']; nci_paid+=paid_old*(1-ch['ownership']);indirect_paid+=paid_old*(ch['ownership']-ch['direct'])
        loan_payment=min(ch['loan'],max(0.,ci.get('loan_payment',0.)),max(0.,ch['cash']-ci.get('floor',0.)-ch['payable']))
        ch['cash']-=loan_payment;ch['loan']-=loan_payment;parent_loan+=loan_payment
        tr,lawful=reserve_transfer(ch['re'],ci['profit'],0.,ch['reserve'],ch['capital'],ci.get('continuing',False))
        ch['reserve']+=tr
        dec=min(max(0.,lawful),max(0.,ci.get('declare',0.)),max(0.,ch['cash']-ci.get('floor',0.)-ch['payable'])) if child_start else 0.
        ch['re']=lawful-dec;parent_new+=dec*ch['direct']
        if child_lag:
            ch['payable']+=dec
        else:
            ch['cash']-=dec;parent_received+=dec*ch['direct'];nci_paid+=dec*(1-ch['ownership']);indirect_paid+=dec*(ch['ownership']-ch['direct'])
        child_rows.append(dict(name=ch['name'],opening_cash=opencash,opening_re=openre,profit=ci['profit'],cash_generated=ci['cash'],old_paid=paid_old,loan_cash=loan_payment,new_declared=dec,reserve_transfer=tr,closing=copy.deepcopy(ch)))
        assert ch['cash']>=-1e-10 and ch['payable']>=-1e-10
        assert abs(ch['re']-(openre+ci['profit']-tr-dec))<1e-9
    p=s['parent'];oc=p['cash'];ore=p['re'];old_dr=p.get('div_receivable',0.)
    p['cash']+=own_cash+other_cash+parent_received+parent_loan
    p['div_receivable']=old_dr+parent_new-parent_received+prior_dividend_collection
    # prior_dividend_collection external fixture belongs to old recorded receivable.
    if prior_dividend_collection:p['div_receivable']-=prior_dividend_collection
    tr,lawful=reserve_transfer(ore,own_profit,parent_new,p['reserve'],p['capital'],continuing)
    p['reserve']+=tr
    old_common=min(p.get('common_payable',0.),max(0.,p['cash']-parent_floor))
    p['cash']-=old_common;p['common_payable']=p.get('common_payable',0.)-old_common
    new_actual=min(max(0.,target_cash_dividend-old_common),max(0.,lawful),max(0.,p['cash']-parent_floor))
    actual=old_common+new_actual
    p['cash']-=new_actual;p['re']=lawful-new_actual
    assert abs(p['cash']-(oc+own_cash+other_cash+parent_received+parent_loan-actual))<1e-9
    assert abs(p['re']-(ore+own_profit+parent_new-tr-new_actual))<1e-9
    assert p['div_receivable']>=-1e-9
    return s,dict(parent_open_cash=oc,parent_open_re=ore,parent_own_profit=own_profit,parent_own_cash=own_cash,parent_other_cash=other_cash,parent_new_dividend=parent_new,parent_received_dividend=parent_received,parent_loan_collected=parent_loan,parent_reserve_transfer=tr,parent_legal_before_dividend=lawful,parent_old_common_paid=old_common,parent_new_common_declared_and_paid=new_actual,parent_actual_dividend=actual,parent_target_dividend=target_cash_dividend,parent_closing=copy.deepcopy(p),children=child_rows,nci_cash_paid=nci_paid,indirect_cash_paid=indirect_paid)

def performance(value,trigger,mid,target):
    if value<trigger:return 0.
    if value<mid:return .8+(value-trigger)/(mid-trigger)*.1
    if value<target:return .9+(value-mid)/(target-mid)*.1
    return 1.

def operating_rows(kind='base',nwc_add=0.,margin_delta=0.,g=.015,ai_margin_override=None):
    p=SOURCE[kind]; prev_rev=7.75; prev_nwc=OPEN_NWC;long=OPEN_LONG
    rows=[]
    ratios=([.33,.325,.32,.315,.31] if kind=='base' else ([.36,.36,.355,.35,.35] if kind=='weak' else [.32,.31,.30,.29,.28]))
    for t in range(1,11):
        if t<=5:
            r=p['rev'][t-1];ai_revenue=AI_MIX[kind]['ai'][t-1];other_revenue=r-ai_revenue
            default_ai_gross=AI_MIX[kind]['gross'][t-1]
            other_gross=(p['gross'][t-1]*r-ai_revenue*default_ai_gross)/other_revenue
            ai_gross=default_ai_gross if ai_margin_override is None else ai_margin_override
            gross=(other_revenue*other_gross+ai_revenue*ai_gross)/r+margin_delta
            rd=p['rd'][t-1];sga=p['sga'][t-1]
            ebit=r*(gross+p['vat']-.008-p['loss'])-rd-sga
            ratio=ratios[t-1]+nwc_add
        else:
            growth=max(g,.045-(t-6)*.006)
            r=prev_rev*(1+growth)
            # explicit fade from Y5 margin toward 5.8/1.2/8.5%; not instant maturity
            target={'base':.058,'weak':.012,'reuse':.085}[kind]+margin_delta
            if ai_margin_override is not None:target+=(ai_margin_override-AI_MIX[kind]['gross'][-1])*AI_MIX[kind]['ai'][-1]/p['rev'][-1]
            ebit_margin=rows[4]['ebit']/rows[4]['revenue']+(target-rows[4]['ebit']/rows[4]['revenue'])*(t-5)/5
            ebit=r*ebit_margin;ratio=ratios[-1]+nwc_add
            gross=None;rd=None;sga=None;ai_revenue=None;other_revenue=None;ai_gross=None;other_gross=None
        nwc=max(prev_nwc,r*ratio) if kind=='weak' else r*ratio
        # Weak path has no automatic release of overdue opening assets.
        da=.018*r
        maintenance=da+.015*(r/7.75)
        growth_capex=.09*max(0.,r-prev_rev)
        capex=maintenance+growth_capex
        tax=max(0.,ebit)*.12 # no cash refund for loss/DTA
        nopat=ebit-tax
        opcf=nopat+da-capex-(nwc-prev_nwc)
        long+=capex-da
        buffer=.125*r
        k=nwc+long+buffer+.06211754214-.07190187803
        rows.append(dict(t=t,revenue=r,ai_revenue=ai_revenue,other_revenue=other_revenue,ai_gross=ai_gross,other_gross=other_gross,gross_margin=gross,rd=rd,sga=sga,ebit=ebit,tax=tax,nopat=nopat,da=da,maintenance=maintenance,growth_capex=growth_capex,capex=capex,nwc=nwc,delta_nwc=nwc-prev_nwc,long_assets=long,buffer=buffer,operating_capital=k,operating_cash=opcf))
        prev_rev=r;prev_nwc=nwc
    return rows

def run_path(kind='base',k=.105,g=.015,asset_recovery=.80,acq_funding=.20,acq_recovery=.75,
             calls=.30,exercise=False,continue_reserve=False,extra_div=0.,extra_div_year=3,
             nwc_add=0.,margin_delta=0.,parent_cash_delta=0.,deal_close=True,
             debt_repay=0.,grant_ai=None,terminal_cash_delay=3,ai_margin_override=None,upstream_start=3,asset_tax_basis_ratio=.70,prior_dividend_eligible=True):
    # Mathematical domains are distinct from economic source support. Negative g
    # above -100% and recoveries above book are allowed; invalid/bool/nonfinite rejected.
    numeric=dict(k=k,g=g,asset_recovery=asset_recovery,acq_funding=acq_funding,acq_recovery=acq_recovery,calls=calls,extra_div=extra_div,nwc_add=nwc_add,margin_delta=margin_delta,parent_cash_delta=parent_cash_delta,debt_repay=debt_repay,terminal_cash_delay=terminal_cash_delay,asset_tax_basis_ratio=asset_tax_basis_ratio)
    if ai_margin_override is not None:numeric['ai_margin_override']=ai_margin_override
    for name,value in numeric.items():
        if isinstance(value,bool) or not isinstance(value,numbers.Real) or not math.isfinite(value):raise ValueError(name+' must be a finite real number, not bool')
    if k<=-1 or g<=-1 or k<=g:raise ValueError('discount domain requires k > g and both k,g > -1')
    if terminal_cash_delay<0:raise ValueError('terminal_cash_delay must be nonnegative')
    for name in ['asset_recovery','acq_funding','acq_recovery','extra_div','debt_repay','asset_tax_basis_ratio']:
        if numeric[name]<0:raise ValueError(name+' must be nonnegative')
    if not isinstance(kind,str) or kind not in SOURCE:raise ValueError('unknown operating kind')
    for name,value in [('exercise',exercise),('continue_reserve',continue_reserve),('deal_close',deal_close),('prior_dividend_eligible',prior_dividend_eligible)]:
        if not isinstance(value,bool):raise ValueError(name+' must be bool')
    for name,value in [('extra_div_year',extra_div_year),('upstream_start',upstream_start)]:
        if isinstance(value,bool) or not isinstance(value,int) or value<1:raise ValueError(name+' must be a positive integer')
    if grant_ai is not None:
        if not isinstance(grant_ai,(list,tuple)) or len(grant_ai)!=3:raise ValueError('grant_ai must contain three finite revenue values')
        for value in grant_ai:
            if isinstance(value,bool) or not isinstance(value,numbers.Real) or not math.isfinite(value) or value<0:raise ValueError('invalid grant_ai revenue')
    rows=operating_rows(kind,nwc_add,margin_delta,g,ai_margin_override)
    s={'parent':dict(cash=OPEN_PARENT_CASH+parent_cash_delta,re=PARENT_RE,reserve=PARENT_RESERVE,capital=ISSUED,div_receivable=0.,common_payable=OPEN_COMMON_PAYABLE),'children':copy.deepcopy(CHILDREN)}
    group_cash=OPEN_GROUP_CASH;debt=OPEN_DEBT;parent_debt=.8999515365
    nci=.05949932871;issued=ISSUED;treasury=TREASURY;active=issued-treasury
    # Separate cash and taxable/book profit. Disposal losses consume parent legal RE.
    # Domestic associations other than Pucheng, equity holdings, Skyline: assumptions,
    # not realizable price quotations. Pucheng retained as a going concern.
    assets={'domestic_other':1.78722421417-.71131726430+.04464445163,'skyline':.66167006463,'new_fund':0.,'target':0.,'target_support':0.}
    starting_assets=copy.deepcopy(assets)
    private_book=sum(assets.values());pucheng_value=.06*(10 if asset_recovery<=.8 else 12)
    ai=grant_ai or ({'base':[.85,1.10,1.35],'weak':[.70,.85,1.0],'reuse':[.90,1.70,2.60]}[kind])
    recs=[];private_sales=[];realized_nci=0.;earmarked=1.5195731 # remaining R&D allocation 1.5338415-.0142684; not all GDR balance
    for o in rows:
        t=o['t'];opening_group_cash=group_cash;opening_debt=debt;opening_assets=copy.deepcopy(assets)
        # 50%-profit payout tendency is a budget, not FCF=dividends.
        target_dps=[.20,.12,.14,.16,.18][t-1] if t<=5 else None
        financial_income=max(0.,group_cash)*.015
        bank_interest=debt*.025
        assoc_profit=.06 if kind!='weak' else .04
        assoc_cash=.03 if kind!='weak' else .02 # FY25 zero / FY24 .0208 / H1 .0644, not annualize H1
        group_np=o['nopat']+financial_income-bank_interest+assoc_profit
        child_inputs=[];named_profit=0.;named_cash=0.
        for ch in s['children']:
            profit=next(x['profit'] for x in CHILDREN if x['name']==ch['name'])*(o['revenue']/7.75)
            if kind=='weak':profit*=.70
            cash=profit*.70
            named_profit+=profit;named_cash+=cash
            child_inputs.append(dict(profit=profit,cash=cash,floor=ch['floor'],loan_payment=cash*.20 if t<=5 else 0.,declare=profit*.50 if t>=upstream_start else 0.))
        other_sub_profit=.010*(o['revenue']/7.75) # net including overseas losses; observed group-parent reconciliation uncertainty
        other_sub_cash=.015*(o['revenue']/7.75)
        parent_fin=max(0.,s['parent']['cash'])*.015
        parent_interest=parent_debt*.025
        parent_own_profit=group_np-named_profit-other_sub_profit-(financial_income-parent_fin)+(bank_interest-parent_interest)
        parent_own_cash=o['operating_cash']-named_cash-other_sub_cash+parent_fin-parent_interest+assoc_cash
        fund=0.08 if t in (1,2) else 0.
        assets['new_fund']+=fund
        acq_cash=.03 if t==1 and deal_close else 0.
        acq_noncash=.02 if t==1 and deal_close else 0.
        acq_injection=acq_funding/2 if t in (1,2) and deal_close else 0.
        if t==1 and deal_close:assets['target']=.05
        assets['target_support']+=acq_injection
        # Receivable consideration removed from existing operating assets: it is a
        # noncash acquisition cost, not group cash or legal netting against the target.
        # To keep original business working capital unchanged, replacement funding is
        # explicitly budgeted; no benefit from both claim and acquired equity.
        working_capital_replacement=acq_noncash
        sale_cash=0.;parent_sale_cash=0.;parent_sale_profit=0.;sales=[]
        if t==5 and deal_close:
            book=assets['target_support'];recovery=acq_funding*acq_recovery
            sale_cash+=recovery;parent_sale_cash+=recovery;parent_sale_profit+=recovery-book-(assets['target']-.0466738)
            assets['target_support']=0.;assets['target']=.0466738
            sales.append(dict(asset='target_support',book=book,cash=recovery,tax=0.,source='conditional customer/supplier working-capital settlement and gross parent loan repayment; not target equity sale; unrecovered support impaired'))
        if t==8:
            oldbook=assets['domestic_other'];newbook=assets['new_fund'];book=oldbook+newbook
            gross=book*asset_recovery
            tax=.25*(max(0.,oldbook*asset_recovery-oldbook*asset_tax_basis_ratio)+max(0.,newbook*asset_recovery-newbook)) # no loss refund or cross-asset loss credit
            recovery=gross-tax
            sale_cash+=recovery;parent_sale_cash+=recovery;parent_sale_profit+=recovery-book
            assets['domestic_other']=assets['new_fund']=0.;sales.append(dict(asset='domestic_other_and_fund',book=book,gross_cash=gross,cash=recovery,tax=tax,tax_basis_existing_budget=oldbook*asset_tax_basis_ratio,tax_basis_new_fund=newbook))
        if t==10:
            book=assets['skyline'];gross=book*asset_recovery;tax=.25*max(0.,gross-.71884);recovery=gross-tax
            sale_cash+=recovery;assets['skyline']=0.;sales.append(dict(asset='skyline',book=book,gross_cash=gross,cash=recovery,tax=tax,tax_basis_documented_nominal=.71884,parent_receipt=0.,reason='legal holding entity not mapped; no immediate parent receipt assumed'))
        private_sales+=sales
        group_np+=parent_sale_profit+sum(x['cash']-x['book'] for x in sales if x['asset']=='skyline')
        nci_profit=.005*(o['revenue']/7.75) # includes direct fluid share, other minorities; no double subtraction
        # Restricted grants: calendar-year qualification distinct from rolling operations.
        grant=0.;grant_cash=0.;sbc_addback=0.
        if exercise and t<=3:
            triggers=[(.8,.9,1.),(1.5,2.,2.5),(3.,4.,5.)][t-1]
            qual=performance(ai[t-1],*triggers)
            grant=(.0154455+.0009345)*[.4,.3,.3][t-1]*qual
            # Company contractual distribution history, NOT this holder's personal
            # record-date eligibility, drives vesting-price adjustments.
            paid_before=.10 if t==1 else sum(r['company_contract_dividend_per_share'] for r in recs if r['t']<t)
            price=max(0.,57.70-paid_before)
            grant_cash=grant*price
            from_treasury=min(treasury,grant);treasury-=from_treasury;issued+=grant-from_treasury
            active=issued-treasury;sbc_addback=.05*qual if grant>0 else 0.
            parent_own_cash+=sbc_addback
        # Unused treasury cancellation after statutory-use windows is a budget only;
        # it changes legal capital and treasury together, never active shares or cash.
        cancelled=0.
        if t==3:
            cancelled=treasury;issued-=treasury;treasury=0.;active=issued;s['parent']['capital']=issued
        internal_call=calls/2 if t in (1,2) else 0.
        repayment=debt_repay if t==2 else 0.;repayment=min(repayment,debt,parent_debt)
        debt-=repayment;parent_debt-=repayment
        if target_dps is None:target_dps=.50*max(0.,group_np-nci_profit)/active
        target_div=target_dps*active+(extra_div if t==extra_div_year else 0.)
        parent_other=grant_cash-fund-acq_cash-acq_injection-working_capital_replacement-internal_call-repayment+parent_sale_cash
        parent_own_profit+=parent_sale_profit
        floor=.075*o['revenue']
        prelegal=copy.deepcopy(s)
        s,legal=legal_step(s,parent_own_profit,parent_own_cash,child_inputs,target_div,parent_other,continuing=continue_reserve,parent_floor=floor,child_lag=1)
        earmarked_used=min(earmarked,.38 if kind!='weak' else .19)
        earmarked-=earmarked_used
        group_cash_floor=o['buffer']+earmarked
        group_before_div=opening_group_cash+o['operating_cash']+financial_income-bank_interest+assoc_cash+sbc_addback+grant_cash-fund-acq_cash-acq_injection-working_capital_replacement-repayment+sale_cash-legal['nci_cash_paid']
        group_capacity=max(0.,group_before_div-group_cash_floor)
        if legal['parent_actual_dividend']>group_capacity:
            s,legal=legal_step(prelegal,parent_own_profit,parent_own_cash,child_inputs,min(target_div,group_capacity),parent_other,continuing=continue_reserve,parent_floor=floor,child_lag=1)
        buffer_drawdown=False
        if s['parent']['cash']<floor-1e-9:
            # Remediation: suspend common payout, consume discretionary second month
            # cash cushion; never use cash below one-month operating floor.
            floor=.04*o['revenue'];buffer_drawdown=True
        actual=legal['parent_actual_dividend'];company_dps=actual/active
        # Company pays the pre-existing liability even when today's holder lacks
        # the record-date claim. New award shares do not retrospectively share it.
        company_old_record_dps=legal['parent_old_common_paid']/ACTIVE
        old_claim_dps=company_old_record_dps if prior_dividend_eligible else 0.
        new_claim_dps=legal['parent_new_common_declared_and_paid']/active
        contract_dps=company_old_record_dps+new_claim_dps
        dps=new_claim_dps+old_claim_dps
        nci_cash=legal['nci_cash_paid'];nci+=nci_profit-nci_cash;realized_nci+=nci_cash
        group_cash+=(o['operating_cash']+financial_income-bank_interest+assoc_cash+sbc_addback+grant_cash-fund-acq_cash-acq_injection-working_capital_replacement-repayment+sale_cash-actual-nci_cash)
        assert abs(group_cash-(opening_group_cash+o['operating_cash']+financial_income-bank_interest+assoc_cash+sbc_addback+grant_cash-fund-acq_cash-acq_injection-working_capital_replacement-repayment+sale_cash-actual-nci_cash))<1e-9
        named_cash_balance=sum(c['cash'] for c in s['children']);residual_cash=group_cash-s['parent']['cash']-named_cash_balance
        # Residual includes named indirect recipient and unidentified internal creditor.
        # It is not swept into parent; no invented loan netting/upstream dividend.
        row={**o,**legal,'group_cash_open':opening_group_cash,'group_cash_close':group_cash,'debt_open':opening_debt,'debt_close':debt,'parent_debt':parent_debt,'group_np':group_np,'parent_own_profit_including_disposals':parent_own_profit,'financial_income':financial_income,'bank_interest':bank_interest,'assoc_profit':assoc_profit,'assoc_cash':assoc_cash,'fund_contribution':fund,'acquisition_cash_price':acq_cash,'acquisition_noncash_price':acq_noncash,'acquisition_funding':acq_injection,'replacement_of_seller_receivable':working_capital_replacement,'private_sales':sales,'assets_close':copy.deepcopy(assets),'grant_shares':grant,'grant_cash':grant_cash,'sbc_cash_addback':sbc_addback,'treasury_cancelled':cancelled,'issued_shares':issued,'treasury_shares':treasury,'active_shares':active,'internal_gross_call':internal_call,'debt_repayment':repayment,'dividend_total':actual,'company_dividend_per_share':company_dps,'company_contract_dividend_per_share':contract_dps,'holder_old_dividend_per_share':old_claim_dps,'holder_new_dividend_per_share':new_claim_dps,'dividend_per_share':dps,'dividend_clipped':max(0.,target_div-actual),'group_unallocated_cash':residual_cash,'nci_book':nci,'nci_profit':nci_profit,'earmarked_rd_used_within_expense':earmarked_used,'earmarked_rd_remaining':earmarked,'group_required_liquid_cash':group_cash_floor,'group_liquidity_headroom':group_cash-group_cash_floor,'parent_required_liquid_cash':floor,'parent_buffer_drawdown':buffer_drawdown,'parent_liquidity_headroom':s['parent']['cash']-floor}
        recs.append(row)
        if row['parent_liquidity_headroom'] < -1e-9 or row['group_liquidity_headroom'] < -1e-9 or residual_cash < -1e-9:
            return dict(status='unresolved_funding',failure_year=t,failure_reason='After cutting common dividend, disclosed-source liquidity budget still fails; no assumed sweep of unallocated subsidiary cash or free refinancing. No executable continuation is valued.',parameters=dict(kind=kind,k=k,g=g,calls=calls,acq_funding=acq_funding,continue_reserve=continue_reserve,nwc_add=nwc_add,margin_delta=margin_delta,debt_repay=debt_repay),rows=recs,terminal=None,today_value=None,first5_dividend_pv=None,year5_value=None,year5_terminal_pv_share=None,method2_normalized_value=None,incremental_return_Y1_to_Y5=None,constraints=dict(min_parent_liquidity=row['parent_liquidity_headroom'],min_group_liquidity=row['group_liquidity_headroom'],min_unallocated_cash=residual_cash,clipped_dividends=sum(x['dividend_clipped'] for x in recs)))
    last=recs[-1];next_rev=last['revenue']*(1+g);steady_margin=last['ebit']/last['revenue']
    nopat11=next_rev*steady_margin*.88
    reinvest11=.09*max(0.,next_rev-last['revenue'])+(last['nwc']/last['revenue']+.125)*(next_rev-last['revenue'])+.015*(next_rev/7.75)
    fcff11=nopat11-reinvest11
    terminal_ev=fcff11/(k-g)
    cash_bridge=last['group_cash_close']-last['debt_close']-last['buffer']-last['nci_book']
    # Delayed ordinary capital access is an explicitly conditional continuation budget,
    # not a declared dividend. Interest is retained while waiting; no instant haircut.
    cash_access_pv=cash_bridge*((1.015)/(1+k))**terminal_cash_delay
    terminal_total=terminal_ev+pucheng_value+cash_access_pv+sum(assets.values())
    terminal_per_share=terminal_total/last['active_shares']
    pv_div=sum(r['dividend_per_share']/(1+k)**r['t'] for r in recs)
    today=pv_div+terminal_per_share/(1+k)**10
    tv5=sum(r['dividend_per_share']/(1+k)**(r['t']-5) for r in recs[5:])+terminal_per_share/(1+k)**5
    first5pv=sum(r['dividend_per_share']/(1+k)**r['t'] for r in recs[:5])
    assert abs(today-first5pv-tv5/(1+k)**5)<1e-10
    # Independent EPV cross-check: current normalized business, no early recovery FCF.
    # Independent no-growth product reconstruction from FY25/H1 gross margins;
    # does NOT reuse forecast Y5 EBIT or forecast AI margin.
    normalized_products=[('automation',4.30,.40),('instruments',1.10,.18),('software',1.05,.35),('service',.60,.32),('S2B',.65,.055),('other',.05,.40)]
    normalized_gross=sum(revenue*margin for _,revenue,margin in normalized_products)
    norm_ebit=normalized_gross-1.30-.95-.06-.14+.18
    norm_nopat=max(0.,norm_ebit)*.88
    normalized_operating_value=(norm_nopat-.015)/k
    normal_cash_bridge=(OPEN_GROUP_CASH-OPEN_DEBT-1.0-.05949932871-OPEN_COMMON_PAYABLE)*((1.015)/(1+k))**(10+terminal_cash_delay)
    normal_private=(starting_assets['domestic_other']*asset_recovery-.25*max(0.,starting_assets['domestic_other']*(asset_recovery-asset_tax_basis_ratio)))/(1+k)**8+(starting_assets['skyline']*asset_recovery-.25*max(0.,starting_assets['skyline']*asset_recovery-.71884))/(1+k)**10
    normal_associate=sum(.03/(1+k)**t for t in range(1,11))+pucheng_value/(1+k)**10
    normal_fund=-.08/(1+k)-.08/(1+k)**2+(.16*asset_recovery-.25*max(0.,.16*(asset_recovery-1)))/(1+k)**8
    normal_acq=(-( .05+acq_funding/2)/(1+k)-acq_funding/2/(1+k)**2+acq_funding*acq_recovery/(1+k)**5+.0466738/(1+k)**10) if deal_close else 0.
    normal_pending_dividend=OPEN_COMMON_PAYABLE/(1+k) if prior_dividend_eligible else 0.
    normalized_value=(normalized_operating_value+normal_cash_bridge+normal_private+normal_associate+normal_fund+normal_acq+normal_pending_dividend)/ACTIVE
    return dict(status='conditional_viable',parameters=dict(kind=kind,k=k,g=g,asset_recovery=asset_recovery,acq_funding=acq_funding,acq_recovery=acq_recovery,calls=calls,exercise=exercise,continue_reserve=continue_reserve,extra_div=extra_div,extra_div_year=extra_div_year,nwc_add=nwc_add,margin_delta=margin_delta,parent_cash_delta=parent_cash_delta,deal_close=deal_close,debt_repay=debt_repay,terminal_cash_delay=terminal_cash_delay,ai_margin_override=ai_margin_override,upstream_start=upstream_start,asset_tax_basis_ratio=asset_tax_basis_ratio,prior_dividend_eligible=prior_dividend_eligible),opening=dict(group_cash=OPEN_GROUP_CASH,parent_cash=OPEN_PARENT_CASH+parent_cash_delta,debt=OPEN_DEBT,nwc=OPEN_NWC,parent_re=PARENT_RE,issued=ISSUED,treasury=TREASURY,private_assets=starting_assets),rows=recs,terminal=dict(year=10,next_revenue=next_rev,nopat11=nopat11,reinvestment11=reinvest11,fcff11=fcff11,operating_value=terminal_ev,pucheng_value=pucheng_value,cash_bridge_before_access_delay=cash_bridge,cash_access_pv=cash_access_pv,ordinary_total=terminal_total,per_share=terminal_per_share),today_value=today,first5_dividend_pv=first5pv,year5_value=tv5,year5_terminal_pv_share=(tv5/(1+k)**5)/today,method2_normalized_value=normalized_value if not exercise else None,method2_scope="independent current-product no-growth cash-compensation benchmark; not an exercised-award scenario valuation",method2_components=dict(products=normalized_products,normalized_gross=normalized_gross,normalized_ebit=norm_ebit,normalized_nopat=norm_nopat,maintenance_excess=.015,operating_value=normalized_operating_value,cash_value=normal_cash_bridge,private_value=normal_private,associate_value=normal_associate,fund_npv=normal_fund,acquisition_npv=normal_acq,pending_dividend_pv=normal_pending_dividend,shares=ACTIVE),incremental_return_Y1_to_Y5=(recs[4]['nopat']-recs[0]['nopat'])/(recs[4]['operating_capital']-recs[0]['operating_capital']),constraints=dict(min_parent_liquidity=min(x['parent_liquidity_headroom'] for x in recs),min_group_liquidity=min(x['group_liquidity_headroom'] for x in recs),min_unallocated_cash=min(x['group_unallocated_cash'] for x in recs),clipped_dividends=sum(x['dividend_clipped'] for x in recs)))

def build():
    configs={
      'base_low':dict(k=.11,g=.01,asset_recovery=.65,acq_funding=.30,acq_recovery=.50,terminal_cash_delay=8),
      'base_high':dict(k=.10,g=.02,asset_recovery=.90,acq_funding=.15,acq_recovery=.85,terminal_cash_delay=3),
      'base_mid':dict(),
      'weak_cash_conversion':dict(kind='weak',k=.115,g=.005,asset_recovery=.50,acq_funding=.45,acq_recovery=.25,calls=.60,terminal_cash_delay=5),
      'repeatable_ai':dict(kind='reuse',k=.10,g=.02,asset_recovery=.85,acq_funding=.15,acq_recovery=.85,exercise=True,terminal_cash_delay=3),
      'base_exercise':dict(exercise=True),
      'continue_reserve':dict(continue_reserve=True),
      'internal_call_900m':dict(calls=.90),
      'internal_call_1500m':dict(calls=1.50),
      'bank_rollover_reduction':dict(debt_repay=.60),
      'parent_cash_less_200m':dict(parent_cash_delta=-.20),
      'working_capital_plus_5pt':dict(nwc_add=.05),
      'margin_less_1pt':dict(margin_delta=-.01),
      'actual_parent_extra_distribution':dict(extra_div=.30),
      'no_deal':dict(deal_close=False),
      'target_gross_obligation_bound':dict(acq_funding=1.0938237,acq_recovery=0.,asset_recovery=.65,calls=.60),
      'extra_capital_access_delay':dict(terminal_cash_delay=8),
      'capital_access_immediate_diagnostic':dict(terminal_cash_delay=0),
      'capital_access_15yr':dict(terminal_cash_delay=15),
      'private_recovery_half':dict(asset_recovery=.50),
      'prior_dividend_not_entitled_mid':dict(prior_dividend_eligible=False),
      'prior_dividend_not_entitled_low':dict(k=.11,g=.01,asset_recovery=.65,acq_funding=.30,acq_recovery=.50,terminal_cash_delay=8,prior_dividend_eligible=False),
      'prior_dividend_not_entitled_high':dict(k=.10,g=.02,asset_recovery=.90,acq_funding=.15,acq_recovery=.85,terminal_cash_delay=3,prior_dividend_eligible=False),
      'ai_revenue_without_reuse_margin':dict(ai_margin_override=.32),
      'no_new_subsidiary_dividend':dict(upstream_start=99),
      'zero_domestic_tax_basis_bound':dict(asset_tax_basis_ratio=0.)
    }
    return {k:run_path(**v) for k,v in configs.items()}

if __name__=='__main__':
 __import__('sys').stdout.write(json.dumps(build(),ensure_ascii=False,separators=(',',':')))

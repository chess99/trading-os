#!/usr/bin/env python3
"""SIPG economic budget; all amounts CNY bn. Standalone stdlib deterministic stdout.
Not a legal certification of distributable subsidiary reserves. Public observations
and budget allocations are differentiated in accompanying sources and report.
"""
import json,math,copy,sys
SHARES=23.279960504
ASOF='2026-10-30T07:26:16Z'
# name, ownership, cash budget, revenue base, EBITDA margin, productive assets,
# working capital, external face budget, internal face, paid-in capital, reserve,
# available RE budget, old dividend liability, parent investment tax-cost budget
DATA=[
 ('shengdong',.8,6.0,3.32,.65,12.13+5.4,.4,1.2,8,12.5125,1.0,2.0,0,10.6364),
 ('guandong',.8,1.1,2.93,.62,9.0,.25,0,0,6.5,1.2,2.5,0,6.7316),
 ('mingdong',.5,2.3,2.59,.57,3.8,.25,.2,0,4,.4,.5,0,2.5614),
 ('hudong',.51,.8,1.8,.55,4.4,.18,.8,0,1.1,.15,.15,0,.5573),
 ('pudong',.4,1.05,1.24,.60,1.2,.12,0,0,1.9,.4,.25,0,.7826),
 ('jinjiang',.85,6.44194841570,7.65,.32,4.63,.65,.1,0,1.29412,.36790095277,1.11466269912,0,2.4829),
 ('logistics',1,2.1,4.7,.34,4.0,.6,.1,0,2.5,.4,1.0,2.01156438911,2.5723),
 ('other_ports',.85,1.5,7.6,.25,9.5,.7,.3,0,3,.5,1.5,1.25240758235,3.0),
 ('property',1,1.0,0,0,15.36663190018,0,.4,0,6.65,.2,-.2,3.86092250732,5.8),
 ('bayport',.75,.247293559,1.05,.39,3.8,.12,.1,2.04327,1.5,0,-.25,0,.5),
]
# Consolidated cash budgets reconcile exactly; residual is HK, not free parent cash.
Q3_GROUP_CASH=42.83034223862
PAID_INTERIM=1.16399802520
# Announced October15 payment discharges an existing payable, no second RE charge.
MATCHED_POOL=4.62740427939
NET_POOL=4.02308385466
GROUP_CASH=Q3_GROUP_CASH-PAID_INTERIM
PARENT_CASH=17.26742153230-PAID_INTERIM
HK_CASH=GROUP_CASH-PARENT_CASH-sum(x[2] for x in DATA)
Q3_DEBT_BOOK=59.19719989512
# Q3 current lease split is undisclosed: 1.2bn budget vs H1 1.969975bn.
LEASE_FACE=.65673103561+1.2
HK_FACE=1.5*6.8109
GROUP_FACE=Q3_DEBT_BOOK-LEASE_FACE+(HK_FACE-10.12224838265)
PARENT_FACE=GROUP_FACE-HK_FACE-sum(x[7] for x in DATA)
SCENARIOS={
 'base':{}, 'core_low':{'price':-.005,'cost':.008,'discount':.005},
 'core_high':{'price':.005,'cost':-.005,'discount':-.005},
 'cycle':{'cycle':True}, 'structural':{'structural':True},
 'upside':{'price':.015,'cost':-.01,'growth':.01},
 'remittance_delay':{'delay':5}, 'low_legal_pools':{'low_re':True},
 'no_new_finance':{'no_finance':True}, 'capital_overrun':{'overrun':.25},
 'minority_rights':{'nci_extra':.1},'minority_refuses_funding':{'nci_refuses':True}, 'cash_bridge':{'cash_shift':-1},
 'cash_pool_timing':{'pool_delay':3}, 'bayport_note_lower_face':{'bp_face':.285*6.8109}, 'bayport_deferred_reclassification':{'bp_deferred':.005*6.8109},
 'cash_pool_low':{'pool':2.},'cash_pool_high':{'pool':6.},
 'north_util_low':{'north_util':.8},'north_util_high':{'north_util':1.},
 'north_bridge_low':{'north_bridge':0.}, 'north_bridge_high':{'north_bridge':2.05095010928},
 'lease_current_high':{'lease_current':1.96997499617},
 'foreign_credit_unavailable':{'foreign_credit':0.}, 'hk_cash_slower':{'hk_release':.10},
 'basis_haircut':{'basis_haircut':.35}, 'bank_credit':{'bank_shock':True}
}
def levy(taxable,losses,t,rate=.25,jurisdiction='CN',source='business',qualified=True):
    """One taxpayer's eligible loss pool; None expiry means no calendar expiry.
    No group transfer, exempt-source loss, or capital loss is admitted here.
    Qualification is an explicit economic budget, not a filed tax determination.
    """
    assert jurisdiction in ('CN','HK','IL')
    valid_sources={'CN':('business','business_asset_gain'),
                   'HK':('business','taxable_interest','revenue_redemption'),
                   'IL':('business','business_asset_gain')}
    if jurisdiction=='CN':
        losses=[(y,x) for y,x in losses if y is not None and y>=t]
    else:
        # Aggregate only within this taxpayer/category. Annual snapshots preserve changes.
        gross=sum(x for y,x in losses)
        losses=[(None,gross)] if gross else []
    if source=='exempt':return 0.,losses
    eligible=qualified and source in valid_sources[jurisdiction]
    if not eligible:return max(0.,taxable)*rate,losses
    if taxable<0:
        if jurisdiction=='CN':losses.append((t+5,-taxable))
        else:losses=[(None,sum(x for _,x in losses)-taxable)]
        return 0.,losses
    rem=taxable;new=[]
    for y,x in losses:
        use=min(x,rem);rem-=use
        if x>use:new.append((y,x-use))
    return rem*rate,new

def statutory(re,reserve,paidin,profit):
    pre=re;re+=profit
    # Loss recovery first; reserve accrual only on the remaining current profit.
    eligible=max(0.,profit+min(pre,0.))
    accr=min(max(0.,paidin*.5-reserve),eligible*.1)
    return re-accr,reserve+accr,accr

def legalpay(cash,re,required,want):
    return min(max(0.,cash-required),max(0.,re),max(0.,want))

def init():
    es={}
    for x in DATA:
        n,own,cash,rev,marg,ppe,wc,debt,internal,capital,reserve,re,due,cost=x
        es[n]=dict(name=n,own=own,cash=cash,rev0=rev,margin=marg,ppe=ppe,wc=wc,debt=debt,
          internal=internal,paidin=capital,reserve=reserve,re=re,due=due,parentcost=cost,
          taxbasis=ppe,taxloss=[],taxloss_jurisdiction='IL' if n=='bayport' else 'CN',taxloss_qualification='conditional_same_taxpayer_business_budget',closed=False,volume=1.,land=ppe*.18,
          debt_tranches=[[debt,debt/5,1]],other_payables=5.3 if n=='property' else 0.,last_revenue=rev,last_north_revenue=0.,initial_debt=debt,initial_ppe=ppe,initial_wc=wc,cip=13.13 if n=='shengdong' else 0.,north_commissioned=0.,land_cost=ppe*.18,land_remaining=40,loan_face=(.322 if n=='shengdong' else .147 if n=='hudong' else 2.214 if n=='other_ports' else 0.),pool_claim=(NET_POOL+MATCHED_POOL)/2 if n in ('logistics','other_ports') else 0.,pool_debt=MATCHED_POOL/2 if n in ('logistics','other_ports') else 0.,restricted_north=2. if n=='shengdong' else 0.,nci_carry=.95452960860 if n=='bayport' else 0.,loan_allowance=0.,outside_note=.68109 if n=='bayport' else 0.,internal_allowance=0.,note_cost=.285*6.8109 if n=='bayport' else 0.,note_tax_basis=.285*6.8109 if n=='bayport' else 0.,loan_cost=(.322 if n=='shengdong' else .147 if n=='hudong' else 2.214 if n=='other_ports' else 0.),claim_tranches=claim_schedule(n),effective_own=own)
        if n=='shengdong':es[n]['ppe']-=12.13;es[n]['initial_ppe']-=12.13;es[n]['taxbasis']+=1.
        if n=='jinjiang':es[n]['legal_cash']=2.36906049297;es[n]['legal_re']=1.11466269912;es[n]['legal_reserve']=.36790095277;es[n]['restricted_ipo']=1.54666468450
    return es


def claim_schedule(name):
    # [gross face, historical cost/tax basis, allowance, coupon, model maturity year,
    # fraction of first forecast year before contractual maturity, impaired starting face]
    specs={'shengdong':[(.322,.016,1,349/365)],
      'hudong':[(.098,.016,1,319/365),(.049,.016,1,229/365)],
      'other_ports':[(2.214/3,.018,y,1.) for y in (1,2,3)],
      'parent':[(.165,.018,1,1.)]}
    return [[f,f,0.,rate,y,frac,0.] for f,rate,y,frac in specs.get(name,[])]

def claim_step(tranches,t,stress=False):
    interest=paid=impaired=reversal=cost_return=reinvest=0.
    for q in tranches:
        if stress and t==1:
            charge=q[0]*.20;q[2]+=charge;q[6]=charge;impaired+=charge
        fraction=q[5] if t==1 and q[4]==1 else 1.
        if t<=q[4]:interest+=q[0]*q[3]*fraction
        cash=max(0,q[0]-q[2]) if t==q[4] else min(q[0],q[6]*.10) if 6<=t<=10 else 0.
        release=min(q[2],cash) if t>q[4] else 0.
        q[0]-=cash;q[1]-=cash;q[2]-=release
        paid+=cash;cost_return+=cash;reversal+=release
        if t==1:reinvest+=cash*.013*(1-fraction)
    return dict(interest=interest,cash=paid,impairment=impaired,reversal=reversal,cost_return=cost_return,reinvestment_interest=reinvest,
      face=sum(q[0] for q in tranches),cost=sum(q[1] for q in tranches),allowance=sum(q[2] for q in tranches))

def pool_add(pools,name,income,credit=0.):
    pools[name][0]+=income;pools[name][1]+=max(0,credit)
    # Loss/cost consumes accumulated earnings and the attached credit, not cash twice.
    negative=-sum(min(0,v[0]) for v in pools.values());positive=sum(max(0,v[0]) for v in pools.values())
    if negative and positive:
        used=min(negative,positive)
        for v in pools.values():
            if v[0]>0:
                reduction=used*v[0]/positive;v[1]*=(v[0]-reduction)/v[0];v[0]-=reduction
            elif v[0]<0:v[0]*=(negative-used)/negative
    for v in pools.values():
        if v[0]<=1e-12:v[1]=0.

def pool_pay(pools,amount,credit_fraction=1.):
    total=sum(max(0,v[0]) for v in pools.values());details={};credit=0.;attached_total=0.
    for n,v in pools.items():
        take=amount*max(0,v[0])/total if total else 0.
        attached=v[1]*take/v[0] if v[0]>0 else 0.
        v[0]-=take;v[1]-=attached
        eligible=attached*credit_fraction;credit+=eligible;attached_total+=attached;details[n]=[take,attached,eligible]
    gross=amount+attached_total;assessment=gross*.25;used=min(assessment,credit)
    return assessment-used,details,gross,used

def op_step(s,t,method,cfg):
    """Actual production transition used also by hand cases; no implicit rescue."""
    old=copy.deepcopy(s);n=s['name'];g=.03+cfg.get('growth',0) if t<=5 else .02 if t<=15 else .015
    if n=='bayport':g=.025 if t<=10 else .01
    duration=11/12 if n=='bayport' and t==20 else 1.
    s['volume']*=(1+g)**duration
    demand=1.;margin=s['margin']-cfg.get('cost',0)
    if cfg.get('cycle') and t<=3: demand=[.85,.9,.97][t-1];margin-=.035
    if cfg.get('structural'):
        demand=.82 if t>=2 else .95;margin-=.07
    price=(1+cfg.get('price',0))**min(t,10)
    revenue=s['rev0']*s['volume']*price*demand*duration
    # North Yangshan capex is 100% project cash; minority funding is below.
    north=[6.-cfg.get('north_bridge',1.),7.,7.,6.,5.,4.,4.17][t-1] if n=='shengdong' and t<=7 else 0.
    growcap=north*(1+cfg.get('overrun',0))
    ipo_interest=0.
    if n=='jinjiang':
        ipo_interest=s['restricted_ipo']*.013
        s['restricted_ipo']+=ipo_interest
        ipospend=1.47721635588/3 if t<=3 else s['restricted_ipo'] if t==4 else 0.
        growcap+=ipospend;s['restricted_ipo']=max(0,s['restricted_ipo']-ipospend)
    if n=='other_ports' and t<=2:growcap+=.81/2
    newvol=(min(max(t-1,0),12)/12)*11.6*cfg.get('north_util',.90) if n=='shengdong' else 0
    revenue+=newvol*.36*(1.015**max(t-5,0))*demand
    # Actual assets already built are not paid for twice. 40-year renewal charged.
    commission=0.
    if n=='shengdong':
        s['restricted_north']=max(0,s['restricted_north']-growcap)
        s['cip']+=growcap
        target=min(s['cip']+s['north_commissioned'],51.3*min(t/8,1.))
        commission=max(0,target-s['north_commissioned'])
        s['cip']-=commission;s['north_commissioned']+=commission;s['ppe']+=commission
    landdep=min(s['land'],s['land_cost']/40) if n not in ('bayport','jinjiang') else 0.
    dep=(max(0,s['ppe']-s['land'])/(20 if n=='jinjiang' else 35)+landdep)*duration
    maint=(dep-landdep)*(1.03 if t<=10 else 1.)
    renewal=s['land_cost']*(1.015**40) if t%40==0 and n not in ('bayport','jinjiang') else 0.
    capital_already_in_cip=growcap if n=='shengdong' else 0.
    north_revenue=newvol*.36*(1.015**max(t-5,0))*demand
    ordinary_growth=max(0.,revenue-old['last_revenue']-(north_revenue-old['last_north_revenue']))
    growcap+=ordinary_growth*(1.2 if n=='jinjiang' else 2.5) if t<=15 else old['ppe']*.015
    s['last_revenue']=revenue;s['last_north_revenue']=north_revenue
    if duration<1:growcap=0.
    if method=='volume':ebitda=revenue*margin
    else:
        # Independent capital-productivity entry: starting capital × normalized
        # after-depreciation pretax return. New north assets have low incremental ROI.
        rates={'shengdong':.25,'guandong':.13,'mingdong':.29,'hudong':.16,
          'pudong':.49,'jinjiang':.32,'logistics':.34,'other_ports':.16,'bayport':.065}
        mature=(s['initial_ppe']+s['initial_wc'])*rates[n]*(1.03**min(t,5))*(1.02**max(min(t-5,10),0))*(1.015**max(t-15,0))
        if n=='shengdong':mature+=newvol*.36*.58-newvol/11.6*51.3/40
        ebitda=(mature*demand*price*duration+dep)-revenue*cfg.get('cost',0)
        if cfg.get('structural'):ebitda-=revenue*.06
    newwc=revenue*.08
    dwc=newwc-s['wc'];s['wc']=newwc
    interest=(s['debt']*.028+s['internal']*.02)*duration
    poolinterest=s['pool_claim']*.016
    poolprincipal=min(s['pool_claim'],(cfg.get('pool',NET_POOL)+MATCHED_POOL)/10) if t<=5 else 0.
    s['pool_claim']-=poolprincipal
    matched_interest=s['pool_debt']*.016
    matched_principal=min(s['pool_debt'],MATCHED_POOL/(6 if cfg.get('pool_delay') else 10)) if t>cfg.get('pool_delay',0) else 0.
    s['pool_debt']-=matched_principal
    interest+=matched_interest
    claim=claim_step(s['claim_tranches'],t,cfg.get('structural',False))
    loaninterest=claim['interest'];loanrepay=recovered=claim['cash'];impairment=claim['impairment']
    s['loan_face']=claim['face'];s['loan_cost']=claim['cost'];s['loan_allowance']=claim['allowance']
    intincome=s['cash']*.013*duration+loaninterest+poolinterest+claim['reinvestment_interest']
    profitpretax=ebitda-dep-interest+intincome-impairment+claim['reversal']
    # Economic impairment is not an assumed tax deduction without a qualifying loss.
    tax,s['taxloss']=levy(profitpretax+impairment-claim['reversal'],s['taxloss'],t,.23 if n=='bayport' else .25,jurisdiction='IL' if n=='bayport' else 'CN')
    profit=profitpretax-tax
    if n=='bayport':s['re']+=profit;reserveadd=0.
    else:s['re'],s['reserve'],reserveadd=statutory(s['re'],s['reserve'],s['paidin'],profit)
    s['ppe']+=maint+(growcap-capital_already_in_cip)+renewal-dep;s['taxbasis']+=maint+growcap+renewal-dep
    s['land']=max(0,s['land']-landdep)+renewal
    if renewal:s['land_cost']=renewal
    cashflow=ebitda-interest+intincome-tax-maint-growcap-renewal-dwc+recovered+poolprincipal-matched_principal
    s['cash']+=cashflow
    # Project debt draw, subsequently amortised. No borrowing to meet dividends.
    draw=0 if cfg.get('no_finance') else north*.60
    s['cash']+=draw;s['debt']+=draw
    if draw:s['debt_tranches'].append([draw,draw/25,8])
    maturity=0.
    for tr in s['debt_tranches']:
        payment=min(tr[0],tr[1]) if t>=tr[2] else 0.
        tr[0]-=payment;maturity+=payment
    s['debt_tranches']=[tr for tr in s['debt_tranches'] if tr[0]>1e-12]
    # On a renewal year capex financing is budgeted at same coverage, not a gift.
    if renewal and not cfg.get('no_finance'):
        draw+=renewal*.4;s['cash']+=renewal*.4;s['debt']+=renewal*.4
        s['debt_tranches'].append([renewal*.4,renewal*.4/20,t+1])
    required=max(.1,revenue/duration*.15)
    if n=='jinjiang':required+=s['restricted_ipo']
    # Finance cash gap by pari-passu equity from parent and outside owners.
    capitalcall=max(0.,required+maturity-s['cash'])
    s['cash']+=capitalcall;s['paidin']+=capitalcall
    s['debt']-=maturity;s['cash']-=maturity
    oldpayment=min(s['due'],max(0.,s['cash']-required)*(.0 if t<=cfg.get('delay',0) else .4))
    s['due']-=oldpayment;s['cash']-=oldpayment
    note_ratio=(s['outside_note']/s['internal']) if s['internal'] else 0.
    internalrepay=min(s['internal'],max(0.,s['cash']-required)*.3/(1+note_ratio))
    outside_note_repay=internalrepay*note_ratio
    s['outside_note']-=outside_note_repay;s['cash']-=outside_note_repay
    note_cost_return=s['note_cost']*internalrepay/s['internal'] if n=='bayport' and s['internal'] else 0.
    note_basis_return=s['note_tax_basis']*internalrepay/s['internal'] if n=='bayport' and s['internal'] else 0.
    note_income=internalrepay-note_cost_return if n=='bayport' else 0.
    note_taxable_gain=internalrepay-note_basis_return if n=='bayport' else 0.
    s['note_cost']-=note_cost_return;s['note_tax_basis']-=note_basis_return
    s['internal']-=internalrepay;s['cash']-=internalrepay
    want=max(0.,profit)*(.40 if t<=5 else min(.95,.4+(t-5)*.06))
    if t>15:want=max(want,s['cash']-required)
    if (n=='shengdong' and t<=7) or duration<1:want=0
    if t<=cfg.get('delay',0):want=0
    div=legalpay(s['cash'],s['re'],required,want)
    # Jinjiang is itself a holding company: subsidiary remittance is a separate budget.
    legal_receipt=0.;legal_cost=0.
    if n=='jinjiang':
        operating_cash=max(0,s['cash']-old['cash']+div)
        legal_receipt=min(max(0,s['cash']-s['legal_cash']-required),max(0,profit)*(.65 if t<=5 else .90))
        if t<=cfg.get('delay',0):legal_receipt=0.
        legal_cost=.025*(1.015**(t-1))
        s['legal_cash']+=legal_receipt-legal_cost
        s['legal_re'],s['legal_reserve'],_=statutory(s['legal_re'],s['legal_reserve'],1.29412,legal_receipt-legal_cost)
        div=min(div,legalpay(s['legal_cash'],s['legal_re'],.30,want))
        s['legal_cash']-=div;s['legal_re']-=div
        s['cash']-=legal_cost;s['re']-=legal_cost
    s['cash']-=div;s['re']-=div
    own=s['effective_own']
    # All new equity is pari-passu, preserving economic ownership.
    received=div*own+oldpayment+internalrepay+old['internal']*.02*duration
    equityinvestment=capitalcall*own;s['parentcost']+=equityinvestment
    extra_loan=capitalcall*(1-own) if cfg.get('nci_refuses') else 0.
    if extra_loan:
        s['paidin']-=extra_loan;s['internal']+=extra_loan
        if n=='bayport':s['note_cost']+=extra_loan;s['note_tax_basis']+=extra_loan
    investment=equityinvestment+extra_loan
    nci=div*(1-own)+outside_note_repay;ncifunding=capitalcall*(1-own)-extra_loan
    if n=='bayport':s['nci_carry']+=profit*(1-own)+ncifunding-nci
    expected=old['cash']+cashflow+draw+capitalcall-maturity-oldpayment-internalrepay-div-legal_cost-outside_note_repay
    assert abs(s['cash']-expected)<1e-7*max(1,abs(expected))
    assert abs(s['re']-(old['re']+profit-reserveadd-div-legal_cost))<1e-7*max(1,abs(s['re']))
    assert min(s['cash'],s['debt'],s['internal'],s['due'])>-1e-8
    return dict(claim=claim,note_cost_return=note_cost_return,note_basis_return=note_basis_return,note_income=note_income,note_taxable_gain=note_taxable_gain,parent_interest=old['internal']*.02*duration,parent_dividend=div*own,effective_own=own,matched_pool_principal=matched_principal,matched_pool_interest=matched_interest,cash_pool_principal=poolprincipal,cash_pool_interest=poolinterest,operating_year_fraction=duration,ipo_interest=ipo_interest,outside_capital_note_paid=outside_note_repay,loan_interest=loaninterest,loan_face_repaid=loanrepay,loan_cash_recovered=recovered,loan_impairment=impairment,commissioned=commission,jinjiang_legal_receipt=legal_receipt,jinjiang_holding_cost=legal_cost,revenue=revenue,ebitda=ebitda,dep=dep,maintenance=maint,growth_capex=growcap,
      renewal=renewal,wc_change=dwc,interest=interest,interest_income=intincome,tax=tax,
      profit=profit,reserve_add=reserveadd,draw=draw,principal=maturity,
      capital_call=capitalcall,new_internal_loan=extra_loan,parent_equity_funding=equityinvestment,parent_funding=investment,nci_funding=ncifunding,
      old_dividend_cash=oldpayment,internal_repayment=internalrepay,dividend=div,
      parent_cash=received,parent_income=div*own+old['internal']*.02*duration+note_income,nci_cash=nci,
      cash_residual=s['cash']-expected,required_cash=required,state=copy.deepcopy(s))

def property_step(s,t,cfg):
    old=copy.deepcopy(s);own=s['effective_own']
    # Twelve-year orderly asset realization, not a year-five book-value release.
    finish=.87/3 if t<=3 else 0.
    s['ppe']+=finish;s['taxbasis']+=finish;s['cash']-=finish
    rental=s['ppe']*(9.11945727265/15.36663190018)*.05
    sold=min(s['ppe'],(15.36663190018+.87)/12)
    gross=sold*(1.12 if not cfg.get('structural') else .80)
    selling=gross*.05;basis=sold*(1-cfg.get('basis_haircut',0))
    tax,s['taxloss']=levy(gross-selling-basis+rental,s['taxloss'],t)
    profit=gross-selling-sold+rental-tax
    s['re'],s['reserve'],acc=statutory(s['re'],s['reserve'],s['paidin'],profit)
    s['ppe']-=sold;s['taxbasis']=max(0,s['taxbasis']-basis)
    s['cash']+=gross-selling+rental-tax
    payable=min(s['other_payables'],max(0,s['cash']-.2));s['other_payables']-=payable;s['cash']-=payable
    pay=min(s['debt'],s['cash']);s['cash']-=pay;s['debt']-=pay
    oldpay=min(s['due'],max(0,s['cash']-.2)) if t>cfg.get('delay',0) else 0
    s['due']-=oldpay;s['cash']-=oldpay
    div=legalpay(s['cash'],s['re'],.2,max(0,s['cash']-.2));s['cash']-=div;s['re']-=div
    capital=0.;gain=0.;exit_tax=0.;costloss=0.
    if t==12:
        closecost=.12;exit_fee=min(closecost,s['cash']);s['cash']-=exit_fee
        # Existing debt and dividends paid before any return to residual owners.
        extra=min(s['due'],max(0.,s['cash']));s['due']-=extra;s['cash']-=extra;oldpay+=extra
        capital=s['cash'];s['cash']=0.;s['debt_tranches']=[];gain=max(0,capital*own-s['parentcost']);
        costloss=max(0,s['parentcost']-capital*own);exit_tax=gain*.25
        profit-=exit_fee
        s['closed']=True;s['paidin']=0;s['reserve']=0;s['re']=0;s['parentcost']=0;s['taxbasis']=0.;s['land']=0.
    return dict(rental_cash_net_maintenance=rental,completion_capex=finish,other_payables_paid=payable,revenue=gross,sold_basis=basis,tax=tax,profit=profit,principal=pay,
      parent_cash=oldpay+div*own+capital*own-exit_tax,parent_income=div*own+gain-exit_tax-costloss,parent_dividend=div*own,parent_interest=0.,effective_own=own,
      capital_return=capital,parent_exit_tax=exit_tax,parent_capital_loss=costloss,
      old_dividend_cash=oldpay,parent_funding=0,nci_cash=(div+capital)*(1-own),nci_funding=0,state=copy.deepcopy(s))

def bank_step(b,t,cfg):
    old=copy.deepcopy(b)
    roe=b['roe']-(min(t,15)/15)*.015
    if cfg.get('bank_shock') or cfg.get('structural'):roe-=.025
    profit=b['equity']*roe
    growth=.055 if t<=5 else .03 if t<=15 else .015
    target_rwa=b['rwa']*(1+growth)
    # CET1 constraint on paying dividend; no free external bank capital.
    retain_need=max(0,target_rwa*b['min_cet']-b['cet1'])
    want=profit*(.31 if t<=5 else min(.85,.31+.04*(t-5)))
    div=min(max(0,profit-retain_need),max(0,b['re']+profit),want)
    retained=profit-div
    b['equity']+=retained;b['cet1']+=retained;b['re']+=retained
    b['rwa']=min(target_rwa,b['cet1']/b['min_cet'])
    return dict(profit=profit,dividend=div,retained=retained,cash=div,
       curtailed_rwa_growth=max(0,target_rwa-b['rwa']),state=copy.deepcopy(b))

def run_core(method='volume',scenario='base',years=480,calendar_budgets=None):
    cfg=SCENARIOS[scenario];es=init()
    if 'bp_face' in cfg:es['bayport']['internal']=cfg['bp_face']
    rights_transfer=0.;hk_rights_transfer=0.
    for n,e in es.items():
        e['effective_own']=max(0,e['own']-cfg.get('nci_extra',0))
        moved=e['parentcost']*(1-e['effective_own']/e['own']) if e['own'] else 0.
        e['parentcost']-=moved
        if n=='bayport':e['nci_carry']+=moved;hk_rights_transfer+=moved
        else:rights_transfer+=moved
    delta=cfg.get('north_bridge',1.)-1.
    es['shengdong']['cip']+=delta;es['shengdong']['taxbasis']+=delta
    for name in ('logistics','other_ports'):es[name]['pool_claim']=(cfg.get('pool',NET_POOL)+MATCHED_POOL)/2
    if cfg.get('low_re'):
        for s in es.values():s['re']=-s['paidin']*.20;s['reserve']=0
    # Whole underlying bank economically scaled to SIPG interest. Not additional NAV.
    banks={
      'psbc':dict(equity=37.8776,cet1=37.6010848,rwa=374.556332,roe=.096,min_cet=.095,re=20.),
      'shbank':dict(equity=22.0581,cet1=21.943,rwa=205.39196,roe=.105,min_cet=.10,re=12.)}
    parent=dict(cash=PARENT_CASH+cfg.get('cash_shift',0),re=53.08968110687-rights_transfer,
      reserve=12.31743357744,paidin=SHARES,debt=PARENT_FACE,taxloss=[],capital_losses=0.,cash_pool_payable=cfg.get('pool',NET_POOL)+MATCHED_POOL,cash_pool_receivable=MATCHED_POOL,refinance_tranches=[],ppe=15.33,land=3.,land_cost=3.,taxbasis=15.33,external_loan_face=.165,external_loan_allowance=0.,external_loan_cost=.165,claim_tranches=claim_schedule('parent'))
    hk=dict(cash=HK_CASH,debt=HK_FACE,re=(-3. if cfg.get('low_re') else 8.)-hk_rights_transfer,reserve=0.,paidin=3.56814866276,taxloss=[],taxloss_jurisdiction='HK',taxloss_qualification='conditional_taxable_treasury_business_expense_allocation' ,parent_loan=0.,refinanced_original=0.,deferred_sale_face=cfg.get('bp_deferred',0.),deferred_sale_allowance=0.,capital_losses=0.)
    hk['tax_pools']={n:[0.,0.] for n in ('opening','bank','shipping','bayport','local')}
    hk['tax_pools']['opening']=[hk['re'],max(0,hk['re'])*.15/.85];hk['bp_credit_pool']=0.
    # OOIL at the acquired ordinary stake; liquidity includes >3m deposits, yielding interest.
    oo=dict(cash=5.783120*6.8109*.09068,ppe=10.701133*6.8109*.09068,
      debt=1.272120*6.8109*.09068,re=6.,cost=9.32207240058)
    funds=dict(value=5.06959670418-cfg.get('bp_deferred',0.),cost=3.7-cfg.get('bp_deferred',0.))
    lease=dict(face=.65673103561+cfg.get('lease_current',1.2),rate=.028)
    parent['debt']-=cfg.get('lease_current',1.2)-1.2
    assoc=dict(capital=24.,re=8.,reserve=2.,paidin=8.)
    nci_equity=16.86853380615+rights_transfer+hk_rights_transfer
    calendar_budgets=calendar_budgets or [17.3,17.3,17.8]
    rows=[];failed=None;shares=SHARES
    discount=.085+cfg.get('discount',0)
    for t in range(1,years+1):
        if failed:
            previous=rows[-1]
            frozen=dict(year=t,parent=copy.deepcopy(parent),subsidiaries={n:{'state':copy.deepcopy(v)} for n,v in es.items()},
              banks={n:{'state':copy.deepcopy(v)} for n,v in banks.items()},ooil={'state':copy.deepcopy(oo)},hk={'state':copy.deepcopy(hk)},
              funds=copy.deepcopy(funds),associates={'state':copy.deepcopy(assoc)},lease={'state':copy.deepcopy(lease)},
              distribution=0.,per_share=0.,discounted_distribution=0.,ceased_after_failure=True,
              nci_equity=nci_equity,nci_distributions=0.,nci_contributions=0.,shares=shares,discount=discount,
              cash_residual=0.,re_residual=0.)
            rows.append(frozen);continue
        pold=copy.deepcopy(parent);hko=copy.deepcopy(hk)
        p_cash=0.;p_inc=0.;p_fund=0.;hk_cash=0.;hk_inc=0.;nci=0.;nci_in=0.;states={}
        domestic_interest=0.;bp_interest=0.;bp_dividend=0.;note_taxable=0.;bp_profit_tax=0.;hk_exit_tax=0.
        for n,s in es.items():
            if s['closed']:states[n]={'state':copy.deepcopy(s)};continue
            if n=='property':row=property_step(s,t,cfg)
            elif n=='bayport' and t==20:
                # Known concession expiry; no franchise terminal. Equipment recycling,
                # restoration provision, external face and capital notes paid in order.
                last_operation=op_step(s,t,method,cfg)
                salvage=max(0,s['ppe']-s['land'])*.12+s['wc']
                tax,s['taxloss']=levy(max(0,salvage-s['taxbasis']),s['taxloss'],t,.23,jurisdiction='IL',source='business_asset_gain')
                restoration=min(.25,max(0,s['cash']+salvage-tax))
                s['cash']+=salvage-tax-restoration
                ext=min(max(s['cash'],0),s['debt']);s['cash']-=ext;s['debt']-=ext
                total_notes=s['internal']+s['outside_note'];note_pool=min(max(0,s['cash']),total_notes)
                intr=note_pool*s['internal']/total_notes if total_notes else 0
                outnote=note_pool-intr
                exit_note_cost=s['note_cost'];exit_note_basis=s['note_tax_basis']
                cost_return=exit_note_cost*intr/s['internal'] if s['internal'] else 0.
                basis_return=exit_note_basis*intr/s['internal'] if s['internal'] else 0.
                s['note_cost']-=cost_return;s['note_tax_basis']-=basis_return
                s['cash']-=note_pool;s['internal']-=intr;s['outside_note']-=outnote
                cap=max(0,s['cash']);own=s['effective_own'];gain=max(0,cap*own-s['parentcost'])
                tax2=gain*.165;loss=max(0,s['parentcost']-cap*own)
                # Unrecovered note face remains a legal claim, with full economic
                # allowance after expiry and no assets. Not a fictitious forgiveness.
                s['internal_allowance']=s['note_cost']
                nci_exit_loss=max(0,s['nci_carry']-cap*(1-own)-outnote);s['nci_carry']=0.
                deferred_sale=hk['deferred_sale_face']*(note_pool/total_notes if total_notes else 1.)
                hk['deferred_sale_face']-=deferred_sale
                hk['deferred_sale_allowance']=hk['deferred_sale_face']
                row=dict(parent_cash=intr+cap*own-tax2+deferred_sale+last_operation['parent_cash'],parent_income=gain-tax2-loss+intr-cost_return-s['internal_allowance']-hk['deferred_sale_allowance']+last_operation['parent_income'],
                  parent_funding=last_operation['parent_funding'],nci_cash=cap*(1-own)+outnote+last_operation['nci_cash'],nci_funding=last_operation['nci_funding'],profit=last_operation['profit']+salvage-s['ppe']-s['wc']-restoration-tax,
                  parent_dividend=last_operation['parent_dividend'],parent_interest=last_operation['parent_interest'],effective_own=own,note_taxable_gain=intr-basis_return+last_operation['note_taxable_gain'],
                  bp_operating_profit=last_operation['profit'],bp_profit_tax=last_operation['tax'],
                  final_operation=last_operation,
                  nci_exit_loss=nci_exit_loss,concession_exit=True,parent_exit_tax=tax2,exit_tax=tax+tax2,external_face_paid=ext,
                  internal_face_paid=intr,internal_note_cost=exit_note_cost,internal_note_cost_return=cost_return,internal_note_basis_return=basis_return,internal_note_income=intr-cost_return-s['internal_allowance'],outside_capital_note_paid=outnote,deferred_sale_cash=deferred_sale,
                  unsettled_face=s['debt']+s['internal']+s['outside_note'],creditor_loss=s['internal_allowance'])
                s['cash']=0;s['ppe']=0;s['wc']=0;s['paidin']=0;s['re']=0;s['reserve']=0;s['closed']=True
                s['taxbasis']=0.;s['parentcost']=0.;s['land']=0.;s['debt_tranches']=[]
                row['state']=copy.deepcopy(s)
                if s['debt']>1e-7:failed=failed or ['concession_external_face_shortfall',t]
            else:row=op_step(s,t,method,cfg)
            states[n]=row
            if n=='bayport':
                hk_cash+=row['parent_cash']-row['parent_funding'];hk_inc+=row['parent_income']
                bp_interest+=row.get('parent_interest',0.);bp_dividend+=row.get('parent_dividend',0.)
                hk_exit_tax+=row.get('parent_exit_tax',0.);note_taxable+=row.get('note_taxable_gain',0.);bp_profit_tax+=row.get('bp_profit_tax',row.get('tax',0.))*s['effective_own']
            else:
                p_cash+=row['parent_cash'];p_inc+=row['parent_income'];p_fund+=row['parent_funding']
                domestic_interest+=row.get('parent_interest',0.)
            parent['capital_losses']+=row.get('parent_capital_loss',0)
            if n=='bayport':hk['capital_losses']+=row.get('creditor_loss',0)
            nci+=row['nci_cash'];nci_in+=row['nci_funding']
        br={};bank_wht=0.;hk_bank_income=0.
        for n,b in banks.items():
            z=bank_step(b,t,cfg);br[n]=z
            direct=.818/3.620 if n=='psbc' else 1.
            p_cash+=z['dividend']*direct;p_inc+=z['dividend']*direct
            wht=z['dividend']*(1-direct)*.10;bank_wht+=wht
            hk_cash+=z['dividend']*(1-direct)-wht;hk_inc+=z['dividend']*(1-direct)-wht;hk_bank_income+=z['dividend']*(1-direct)-wht
        # Other associates: retain actual productive capital, no book added separately.
        assoc_cap=assoc['capital']
        assoc_profit=assoc_cap*(.06 if not cfg.get('structural') else .035)
        assoc['re'],assoc['reserve'],assoc_reserve=statutory(assoc['re'],assoc['reserve'],assoc['paidin'],assoc_profit)
        assoc_div=min(max(0,assoc['re']),max(0,assoc_profit-assoc_cap*(.025 if t<=15 else .015)))
        assoc['capital']+=assoc_profit-assoc_div;assoc['re']-=assoc_div
        p_cash+=assoc_div;p_inc+=assoc_div
        # OOIL normalizes rather than annualizing the Q3 revenue-per-box surge.
        oold=copy.deepcopy(oo);orev=(10.8 if t<=2 else 9.5)*6.8109*.09068*(1.015**(t-1))
        om=.17 if t<=2 else .14
        if cfg.get('cycle') and t<=3:om-=.055
        if cfg.get('structural'):om=.09
        oda=oo['ppe']/18;oint=oo['debt']*.035;oi=oo['cash']*.025
        otax=max(0,orev*om-oda-oint+oi)*.10
        op=orev*om-oda-oint+oi-otax
        ocap=oda+(5.447048*6.8109*.09068/5 if t<=5 else orev*.015)
        oo['cash']+=orev*om-oint+oi-otax-ocap;oo['ppe']+=ocap-oda
        orepaid=min(oo['debt'],max(0,oo['cash']-.7)*.20);oo['debt']-=orepaid;oo['cash']-=orepaid
        oo['re']+=op
        od=legalpay(oo['cash'],oo['re'],orev*.15,max(0,op)*(.5 if t<=10 else .9))
        oo['cash']-=od;oo['re']-=od
        if oo['cash']<0:
            failed=failed or ['ooil_funding_gap',t];oo['unpaid_cash_obligations']=-oo['cash'];oo['cash']=0.
        hk_cash+=od;hk_inc+=od
        # Funds: finite orderly monetization, gains taxed against historic cost.
        proceeds=0.;fgain=0.;ftax=0
        if 3<=t<=10:
            proceeds=(5.06959670418-cfg.get('bp_deferred',0.))/8*(.8 if cfg.get('structural') else 1.)
            cb=(3.7-cfg.get('bp_deferred',0.))/8*(1-cfg.get('basis_haircut',0));fgain=proceeds-cb;ftax=max(0,fgain)*.25
            funds['value']-=(5.06959670418-cfg.get('bp_deferred',0.))/8;funds['cost']-=(3.7-cfg.get('bp_deferred',0.))/8
            p_cash+=proceeds-ftax;p_inc+=fgain-ftax
        # Offshore holding: actual receipts pay own costs/debt before upstream.
        hi=hk['debt']*.03;hcost=.06*(1.015**(t-1));hint=hk['cash']*.013
        hloaninterest=hk['parent_loan']*.02
        p_cash+=hloaninterest;p_inc+=hloaninterest
        hk_deductible=(hi+hcost+hloaninterest)*cfg.get('hk_expense_qualification',1.)
        hk['taxloss_deductible_expense_budget']=hk_deductible
        hk['taxloss_nonqualifying_expense']=hi+hcost+hloaninterest-hk_deductible
        hktax,hk['taxloss']=levy(bp_interest+note_taxable+hint-hk_deductible,hk['taxloss'],t,.165,jurisdiction='HK',source='taxable_interest')
        hprofit=hk_inc+hint-hi-hcost-hloaninterest-hktax
        hk['bp_credit_pool']+=bp_profit_tax
        bp_credit=min(hk['bp_credit_pool'],bp_dividend*.23/.77);hk['bp_credit_pool']-=bp_credit
        pool_add(hk['tax_pools'],'bank',hk_bank_income)
        pool_add(hk['tax_pools'],'shipping',od)
        pool_add(hk['tax_pools'],'bayport',bp_dividend,bp_credit)
        pool_add(hk['tax_pools'],'local',hprofit-hk_bank_income-od-bp_dividend,hktax+hk_exit_tax)
        assert abs(sum(v[0] for v in hk['tax_pools'].values())-(hko['re']+hprofit))<1e-7*max(1,abs(hprofit))
        hk['re']+=hprofit;hr=0.
        hk['cash']+=hk_cash+hint-hi-hcost-hloaninterest-hktax
        # Existing USD bond principal: 0.8bn USD due 2029, 0.7bn in 2030.
        # Normal refinancing is a new legal obligation, never debt forgiveness.
        hmaturity=min(hk['debt'],(.8*6.8109 if t==3 else .7*6.8109 if t==4 else hk['refinanced_original']/10 if t>=5 else 0.))
        havailable=max(0,hk['cash']-.5)
        hroll=max(0,hmaturity-havailable) if not cfg.get('no_finance') else 0.
        hguarantee=max(0,hmaturity-havailable) if cfg.get('no_finance') else 0.
        hk['parent_loan']+=hguarantee;p_fund+=hguarantee
        hk['cash']+=hroll+hguarantee
        hprincipal=hmaturity
        hk['cash']-=hprincipal;hk['debt']+=hroll-hprincipal
        hk['refinanced_original']+=hroll
        hloanrepay=min(hk['parent_loan'],max(0,hk['cash']-.5)*.30)
        hk['parent_loan']-=hloanrepay;hk['cash']-=hloanrepay;p_cash+=hloanrepay
        # Keep operating floor and next 24 months' known debt; amortizing refinancing
        # remains a real use. Release 35% of genuinely surplus cash each year, not a terminal sweep.
        next_maturities=sum({3:.8*6.8109,4:.7*6.8109}.get(y,0.) for y in (t+1,t+2))
        if t>=4:next_maturities+=min(hk['debt'],hk['refinanced_original']/10*2)
        hk_required=.5+min(hk['debt'],next_maturities)+hk['parent_loan']*.30
        surplus=max(0,hk['cash']-hk_required)
        hd=legalpay(hk['cash'],hk['re'],hk_required,max(0,hprofit)*(.7 if t<10 else 1.)+surplus*cfg.get('hk_release',.35))
        foreign_tax,foreign_alloc,foreign_gross,foreign_credit=pool_pay(hk['tax_pools'],hd,cfg.get('foreign_credit',1.))
        hk['cash']-=hd;hk['re']-=hd;p_cash+=hd;p_inc+=hd
        if hk['cash']<0:
            failed=failed or ['hk_funding_gap',t];hk['unpaid_cash_obligations']=-hk['cash'];hk['cash']=0.
        # Parent direct port operations excludes dividends/financial FV income.
        factor=(1.03**min(t,5))*(1.02**max(min(t-5,10),0))*(1.015**max(t-15,0))
        pr=9.*factor
        lease_interest=lease['face']*.028
        lease_cash=1.38*(1.015**(t-1))
        lease_principal=min(lease['face'],max(0,lease_cash-lease_interest));lease['face']-=lease_principal
        parent_rent=.78*factor*(1.25 if cfg.get('structural') else 1.)
        pebit=(3.48*factor if method=='volume' else (15.33*.221)*factor)-parent_rent
        if cfg.get('structural'):pebit*=.7
        if cfg.get('cycle') and t<=3:pebit*=.8
        pebit-=pr*cfg.get('cost',0)
        poolinterest=parent['cash_pool_payable']*.016
        poolprincipal=min(parent['cash_pool_payable'],(cfg.get('pool',NET_POOL)+MATCHED_POOL)/5) if t<=5 else 0.
        parent['cash_pool_payable']-=poolprincipal
        matched_interest=parent['cash_pool_receivable']*.016
        matched_collection=min(parent['cash_pool_receivable'],MATCHED_POOL/(3 if cfg.get('pool_delay') else 5)) if t>cfg.get('pool_delay',0) else 0.
        parent['cash_pool_receivable']-=matched_collection
        pint=parent['debt']*.027+poolinterest
        parent_claim=claim_step(parent['claim_tranches'],t,cfg.get('structural',False))
        ploaninterest=parent_claim['interest'];ploanrepay=parent_claim['cash']
        parent['external_loan_face']=parent_claim['face'];parent['external_loan_cost']=parent_claim['cost'];parent['external_loan_allowance']=parent_claim['allowance']
        pcashi=parent['cash']*.013+ploaninterest+matched_interest+parent_claim['reinvestment_interest']
        domestic_tax,parent['taxloss']=levy(pebit-pint+pcashi+domestic_interest+hloaninterest,parent['taxloss'],t)
        ptax=domestic_tax+foreign_tax
        pp=pebit-pint+pcashi-ptax+p_inc-parent_claim['impairment']+parent_claim['reversal']
        parent['re'],parent['reserve'],rr=statutory(parent['re'],parent['reserve'],parent['paidin'],pp)
        # Maintenance equals direct depreciation plus recurring renewal budget.
        plandamort=min(parent['land'],parent['land_cost']/40)
        pdep=max(0,parent['ppe']-parent['land'])/35+plandamort
        pmaint=pdep-plandamort
        prenew=parent['land_cost']*(1.015**40) if t%40==0 else 0.
        pgrowth=.25*factor if t<=15 else max(0,parent['ppe']-parent['land'])*.015
        pcap=pgrowth+prenew
        parent['ppe']+=pmaint+pcap-pdep;parent['taxbasis']+=pmaint+pcap-pdep
        parent['land']=max(0,parent['land']-plandamort)+prenew
        if prenew:parent['land_cost']=prenew
        pcashop=pebit-pint+pcashi-ptax+plandamort-pcap-poolprincipal+matched_collection
        parent['cash']+=pcashop+p_cash-p_fund+ploanrepay
        # Normal debt rollover preserves face until earned cash pays it; all maturities
        # shown gross, never assumed extinguished merely at the forecast endpoint.
        # Public domestic bonds/MTNs: maturity map in model years ending October30.
        # Residual bank-face maturity spread over three years is a budget, not a contract claim.
        bond_due={1:2.,2:2.,3:9.,4:5.,5:11.,8:2.,9:3.,10:4.}.get(t,0.)
        bank_due=max(0,PARENT_FACE-38.)/3 if t<=3 else 0.
        rolled_due=0.
        for tr in parent['refinance_tranches']:
            pay=min(tr[0],tr[1]) if t>=tr[2] else 0.;tr[0]-=pay;rolled_due+=pay
        parent['refinance_tranches']=[tr for tr in parent['refinance_tranches'] if tr[0]>1e-12]
        scheduled=min(parent['debt'],bond_due+bank_due+rolled_due)
        planned_refinance=0. if cfg.get('no_finance') else scheduled*.65
        cash_principal=min(scheduled-planned_refinance,max(0,parent['cash']-3.0))
        rollover=scheduled-cash_principal if not cfg.get('no_finance') else 0.
        principal=scheduled if cfg.get('no_finance') else cash_principal
        if rollover:parent['refinance_tranches'].append([rollover,rollover/8,t+1])
        parent['cash']-=principal;parent['debt']-=principal
        # Consolidate actual external profit first, then allocate once. Legal investor
        # note/equity gains and impairment are eliminated; external taxes remain costs.
        group_total_profit=pp-p_inc
        group_total_profit+=sum(z.get('profit',0)-z.get('jinjiang_holding_cost',0) for z in states.values())
        group_total_profit+=sum(b['profit'] for b in br.values())+op+assoc_profit+hprofit-hk_inc+fgain-ftax-bank_wht
        group_total_profit+=domestic_interest+bp_interest+hloaninterest
        group_total_profit-=sum(z.get('parent_exit_tax',0.) for z in states.values())
        nci_profit=0.
        for n,z in states.items():
            if z.get('concession_exit'):nci_profit+=z['bp_operating_profit']*(1-es[n]['effective_own'])-z['nci_exit_loss']
            else:nci_profit+=(z.get('profit',0)-z.get('jinjiang_holding_cost',0))*(1-es[n]['effective_own'])
        group_owner_profit=group_total_profit-nci_profit
        prior_interim=[.05,.05,.055][t-1] if t<=3 else 0.
        next_interim=[.05,.055,.06][t-1] if t<=3 else 0.
        calendar_basis=calendar_budgets[t-1] if t<=3 else 0.
        plan_final_due=max(0,calendar_basis*.30-SHARES*prior_interim) if t<=3 else 0.
        discretionary_next_interim=SHARES*next_interim
        plan_cash_floor=plan_final_due+discretionary_next_interim
        want=max(SHARES*[.23,.24,.25,.24,.24][t-1],plan_cash_floor) if t<=5 else max(0,pp)*min(.98,.40+.04*(t-5))
        if t>20:want=max(want,parent['cash']-3.*factor)
        dividend=legalpay(parent['cash'],parent['re'],3.*factor,want)
        parent['cash']-=dividend;parent['re']-=dividend
        funding_gap=max(0,-parent['cash'])
        if funding_gap:
            failed=failed or ['parent_funding_gap',t];parent['unpaid_cash_obligations']=funding_gap;parent['cash']=0.
        cfres=parent['cash']-(pold['cash']+pcashop+p_cash-p_fund+ploanrepay-principal-dividend+funding_gap)
        reres=parent['re']-(pold['re']+pp-rr-dividend)
        assert abs(cfres)<1e-7*max(1,parent['cash']) and abs(reres)<1e-7*max(1,abs(parent['re']))
        nci_open=nci_equity;nci_equity+=nci_profit+nci_in-nci
        group_cash=parent['cash']+hk['cash']+sum(v['cash'] for v in es.values())
        rows.append(dict(year=t,parent=copy.deepcopy(parent),subsidiaries=states,banks=br,
          ooil=dict(state=copy.deepcopy(oo),revenue=orev,profit=op,capex=ocap,tax=otax,dividend=od,principal=orepaid),
          hk=dict(state=copy.deepcopy(hk),profit=hprofit,tax=hktax,taxable_before_loss=bp_interest+note_taxable+hint-hk_deductible,required_cash=hk_required,foreign_dividend_tax=foreign_tax,foreign_tax_gross=foreign_gross,foreign_credit_used=foreign_credit,foreign_source_allocation=foreign_alloc,dividend=hd,principal=hprincipal,gross_maturity=hmaturity,refinancing_draw=hroll,parent_guarantee_funding=hguarantee,parent_loan_repaid=hloanrepay,parent_loan_interest=hloaninterest),
          lease=dict(state=copy.deepcopy(lease),cash_already_in_operating_cost=lease_cash,interest_component=lease_interest,principal_component=lease_principal),
          funds=copy.deepcopy(funds),fund_proceeds=proceeds,fund_tax=ftax,
          associates=dict(opening_capital=assoc_cap,profit=assoc_profit,dividend=assoc_div,state=copy.deepcopy(assoc)),
          group_total_profit=group_total_profit,domestic_internal_interest=domestic_interest,parent_domestic_tax=domestic_tax,parent_foreign_tax=foreign_tax,parent_claim=parent_claim,plan_final_due=plan_final_due,research_next_interim=discretionary_next_interim,funding_gap=funding_gap,parent_depreciation=pdep,parent_maintenance=pmaint,parent_growth_capex=pgrowth,parent_land_renewal=prenew,parent_operating_cash=pcashop,parent_receipts=p_cash,parent_new_income=p_inc,
          parent_funding=p_fund,calendar_prior_year_profit_budget=calendar_basis,plan_window_floor=plan_cash_floor,dividend_cash_capacity=max(0,parent['cash']+dividend-3.*factor),dividend_RE_capacity=max(0,parent['re']+dividend),policy_requested=want,group_owner_profit=group_owner_profit,bank_withholding_tax=bank_wht,parent_loan_repaid=ploanrepay,parent_rent=parent_rent,parent_profit=pp,parent_tax=ptax,parent_principal=principal,
          parent_gross_maturities=scheduled,parent_rollover=rollover,parent_cash_pool_interest=poolinterest,parent_cash_pool_principal=poolprincipal,parent_matched_pool_collection=matched_collection,parent_matched_pool_interest=matched_interest,
          group_cash=group_cash,nci_open=nci_open,nci_profit=nci_profit,nci_equity=nci_equity,
          internal_face_parent=sum(v['internal'] for n,v in es.items() if n!='bayport'),internal_face_hk=es['bayport']['internal'],
          old_dividend_claim=sum(v['due'] for v in es.values()),
          nci_distributions=nci,nci_contributions=nci_in,distribution=dividend,
          per_share=dividend/shares,cash_residual=cfres,re_residual=reres,
          shares=shares,discount=discount,discounted_distribution=dividend/(1+discount)**t))
    pv=sum(r['discounted_distribution'] for r in rows)/SHARES
    y5=sum(r['distribution']/(1+discount)**(r['year']-5) for r in rows if r['year']>5)/SHARES
    first=[r['per_share'] for r in rows[:5]]
    return dict(calendar_profit_budgets=calendar_budgets,method=method,scenario=scenario,years=years,feasible=failed is None,failure=failed,
      present_value=pv if failed is None else None,y5=y5 if failed is None else None,
      diagnostic_unconditional_pv=pv,first_five=first,
      tail_pv_fraction=y5/(1+discount)**5/pv if pv else None,annual=rows)

def run(method='volume',scenario='base',years=480):
    # Explicit monthly calendar bridge, solved with actual cash/tax policy feedback.
    # Model periods are Nov-Oct (two-day simplification); FY26 Q4 is a forecast,
    # not a replacement for the disclosed nine-month profit.
    calendars=[17.3,17.3,17.8]
    for _ in range(20):
        probe=run_core(method,scenario,4,calendars)
        profits=[r.get('group_owner_profit',0.) for r in probe['annual']]
        if probe['failure']:break
        new=[13.08509110656+profits[0]/4,profits[0]*10/12+profits[1]*2/12,profits[1]*10/12+profits[2]*2/12]
        if max(abs(a-b) for a,b in zip(calendars,new))<1e-10:
            calendars=new;break
        calendars=new
    return run_core(method,scenario,years,calendars)

def selftest():
    assert statutory(-2,0,10,1)==(-1,0,0)
    assert statutory(-2,0,10,4)==(1.8,.2,.2)
    assert legalpay(2,5,1,4)==1
    s=init()['mingdong'];s.update(cash=10,rev0=0,margin=0,ppe=0,wc=0,debt=0,internal=0,re=2,reserve=2,paidin=4,volume=1,initial_debt=0,land=0,land_cost=0,last_revenue=0,debt_tranches=[])
    x=op_step(s,1,'volume',{})
    # interest 0.13, tax .0325, profit .0975, div .039, WC0, capex0
    assert abs(x['tax']-.0325)<1e-12 and abs(x['dividend']-.039)<1e-12
    assert abs(s['cash']-10.0585)<1e-12
    s=init()['mingdong'];s.update(cash=.05,re=-20,debt=100,initial_debt=100,debt_tranches=[[100,4,1]])
    x=op_step(s,1,'volume',{'no_finance':True})
    assert x['dividend']==0 and x['capital_call']>0 and s['cash']>=0
    return {'production_hand_case':True,'loss_before_reserve':True,'liquidity_cap':True,
      'actual_production_finance_and_loss_counterexample':True}

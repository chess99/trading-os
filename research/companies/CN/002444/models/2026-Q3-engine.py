#!/usr/bin/env python3
"""Self-contained GreatStar ordinary-holder model. All money CNY bn.
Distribution budgets for entity pools are economic envelopes, NOT legal opinions.
No data reads, network, prices, imports of research inputs, or terminal magic releases.
"""
import json, math, sys
ASOF='2026-10-29T21:00:00+00:00'
SHARES=1.194478182

def profit_reserve(re,reserve,profit,cap):
    # Current losses reduce retained earnings; recovery first fills prior deficits.
    appropriation=min(max(0.0,cap-reserve),.1*max(0.0,profit+min(0.0,re)))
    return re+profit-appropriation,reserve+appropriation,appropriation

def disposal(proceeds,cost,fee,tax):
    expense=proceeds*fee
    gain=proceeds-expense-cost
    taxpaid=max(0.,gain)*tax
    return proceeds-expense-taxpaid,gain,taxpaid

def operations(t,last,scenario,method):
    # Independent operating entrances: channel unit economics versus product cohorts.
    if scenario=='unit_cash': return 0.,0.,0.,0.,0.
    if method=='channels':
        g=[.065,.060,.050,.040,.030][t-1] if t<=5 else max(.015,.03-.003*(t-5))
        rev=last*(1+g)
        obm=min(.53,.469+.006*t)
        gm=obm*.350+(1-obm)*.307
        opex=.162
        if scenario=='core_low': gm-=.003
        if scenario=='core_high': gm+=.003
        ebit=rev*(gm-opex)
    else:
        # Product base independent of channel projections. 10.8/1.8/3.2bn.
        rates=(.045,.080,.020)
        years=min(t,7)
        revenues=[b*(1+g)**years*1.015**max(0,t-7) for b,g in zip((10.8,1.8,3.2),rates)]
        rev=sum(revenues)
        ebit=sum(x*m for x,m in zip(revenues,(.168,.123,.156)))
        if scenario=='core_low': ebit-=rev*.003
        if scenario=='core_high': ebit+=rev*.003
    # Trade impacts are realized demand, pricing, costs, inventory and investment.
    extra_wc=0.; extra_cap=0.; shock=0.
    if scenario=='cycle':
        factor=(.92,.95,.98)[t-1] if t<=3 else 1.
        rev*=factor; ebit*=factor
        if t<=3: ebit-=rev*(.018,.012,.005)[t-1];extra_wc=.025*rev;extra_cap=.10
    if scenario=='structural':
        rev*=.975;ebit=rev*.118;extra_wc=.035*rev;extra_cap=.012*rev
    if scenario=='upside':
        rev*=1.015 if t<=7 else 1.;ebit+=.009*rev
    if scenario=='funding_failure' and t==1:shock=8.
    # Long-run competitive fade, not constant peak margin forever.
    if t>10:ebit-=rev*min(.012,(t-10)*.001)
    return rev,ebit,extra_wc,extra_cap,shock

def run(scenario='base',method='channels',horizon=180,k=.10):
    # 9/30 available cash less paid 10/23 dividend and bank settlement reserve.
    # Bank settled-share cost is represented ONCE as an investment, not an expense.
    total_cash=5.09629196820-.35834345460-.32452341760
    cash=[1.8754765824,1.45,total_cash-1.8754765824-1.45-.025,.025]
    deposits=[1.65,1.10,.13644010764,0.]
    restricted=[.00141583283,.015,.02024632212,0.]
    debt=[2.61,.50,.32150039057,0.]
    notes=2.61
    face=[0.,.21247224256,.30008870679,0.]
    allowance=.04636293251
    olddiv=.0294798
    re=[7.97583415245-.35834345460,0.,0.,0.]
    reserves=[.92719228433,0.,0.,0.]
    # Conservative reserve budget at subsidiaries; ceilings are research envelopes.
    reserve_caps=[SHARES*.5,.50,1.50,.0025]
    sub_cost=[0.,1.66702926398,4.63340857998,.231174]
    owners=[1.,.98,.985,.60]
    assoc=4.32021894933; assoc_cost=1.22406768
    bank=.32452341760; bank_cost=bank
    other_equity=.090936;other_cost=other_equity
    minority_equity=.40095048193
    nwc=4.80; fixed=6.3257557615
    prev_rev=15.8; rows=[]; pv=0.; dividends=[]; accrued_tax=0.
    if scenario=='acquisition_unmatched':
        cash[0]-=.231174;cash[3]+=.025;fixed+=.231174-.60*.07677121659+(.07677121659-.025);minority_equity+=.40*.07677121659
    if scenario=='unit_cash':
        cash=[2.,0.,0.,0.];deposits=[0.]*4;restricted=[0.]*4;debt=[0.]*4;face=[0.]*4;re=[3.,0.,0.,0.];reserves=[.92719228433,0.,0.,0.];notes=allowance=olddiv=assoc=bank=other_equity=minority_equity=nwc=fixed=prev_rev=0.
    opening_cash=sum(cash)+sum(restricted)
    for t in range(1,horizon+1):
        start_cash=sum(cash)+sum(restricted); start_deposits=sum(deposits)
        startdebt=sum(debt); startassoc=assoc; startbank=bank
        rev,ebit,extra_wc,extra_cap,shock=operations(t,prev_rev,scenario,method)
        desired_nwc=rev*.30+extra_wc
        dwc=desired_nwc-nwc;nwc=desired_nwc
        da=rev*.025
        maintenance=rev*.030
        growth=max(0.,rev-prev_rev)*.18+(.15 if t<=2 else .06 if t<=4 else 0.)+extra_cap
        if scenario=='unit_cash':growth=0.
        capex=maintenance+growth
        fixed+=capex-da
        # Previously incurred engineering payable 0.1171 paid y1; not expensed twice.
        old_cap_pay=.11707693060 if t==1 and scenario!='unit_cash' else 0.
        if scenario=='repatriation_delay':foreign_gate=t>=4
        else:foreign_gate=True
        financial_interest=[(cash[i]+deposits[i]+restricted[i])*.018 for i in range(4)]
        debt_interest=[debt[i]*(.045 if scenario=='cycle' and t<=3 else .035) for i in range(4)]
        internal_interest=[0.]+[face[i]*.03 for i in range(1,4)]
        # All affiliates are already ordinary-attributable; do not multiply total net assets.
        ar=.115 if t<=5 else max(.085,.115-.005*(t-5))
        if scenario=='associate_return_low':ar=.04
        ap=assoc*ar
        target_growth=.03 if t<=5 else .015
        ad=0. if t<=2 else ap*{3:.20,4:.35,5:.50,6:.60,7:.65}[t] if t<=7 else max(0.,ap-assoc*target_growth)
        if scenario=='associate_delay' and t<=10:ad=0.
        if scenario=='associate_exit' and t==8:
            proceeds,gain,etax=disposal(assoc*.85,assoc_cost,.02,.25)
            ad=proceeds;assoc=0.;ap=0.
        else:
            gain=0.;etax=0.;assoc+=ap-ad
        bp=bank*.07;bd=bp*.4 if t<=5 else bp-bank*.015
        bank+=bp-bd
        oi=other_equity*.025
        # Parent standalone earnings include dividends, NOT all subsidiary profits.
        weights=[.22,.28,.49,.01]
        taxes=[]; profits=[]; op_cash=[]; maturities=[]; repay=[]
        for i in range(4):
            pretax=ebit*weights[i]+financial_interest[i]-debt_interest[i]-internal_interest[i]
            if i==0:pretax+=sum(internal_interest)
            rate=(.15,.20,.22,.25)[i]
            tax=max(0.,pretax)*rate
            profit=pretax-tax
            taxes.append(tax);profits.append(profit)
            cf=profit+(da-capex-dwc-old_cap_pay-shock)*weights[i]
            op_cash.append(cf)
            mature=deposits[i]*(.55 if t==1 else 1. if t==2 else 0.)
            deposits[i]-=mature;maturities.append(mature)
            pay=min(debt[i],(.522 if i==0 else (.25 if i==1 else .160750195285)) if t<=5 else debt[i])
            if scenario=='no_rollover' and t==1:pay=debt[i]
            repay.append(pay);debt[i]-=pay
            cash[i]+=cf+mature-pay
            re[i],reserves[i],reserve_add=profit_reserve(re[i],reserves[i],profit,reserve_caps[i])
        notes=max(0.,notes-repay[0])
        # Financial principal yields not mixed into operating EBITDA / NOPAT.
        cash[0]+=ad+bd+oi
        parent_investment_profit=(ap if scenario!='associate_exit' or t!=8 else gain-etax)+bd+oi
        re[0]+=parent_investment_profit
        # Domestic eligible-company dividends tax-exempt budget; external disposal tax separate.
        # The cash receipt of old dividend is not fresh earnings.
        if t==1:
            cash[1]-=olddiv;cash[0]+=olddiv;old_paid=olddiv;olddiv=0.
        else:old_paid=0.
        internal_paid=[];allow_reversal=0.
        for i in range(1,4):
            due=min(face[i],(.21247224256 if i==1 else .30008870679 if i==2 else 0.)/5)
            paid=min(due,max(0.,cash[i]-.10))
            before=sum(face)
            face[i]-=paid;cash[i]-=paid;cash[0]+=paid
            reversal=allowance*(paid/before) if before else 0.
            allowance-=reversal;allow_reversal+=reversal
            internal_paid.append(paid)
        # Reversals only parent-book: tax provision conservatively charged on release.
        reversal_tax=allow_reversal*.15
        cash[0]-=reversal_tax;re[0]+=allow_reversal-reversal_tax
        floor=[rev*.045,rev*.035,rev*.045,rev*.002]
        gross_div=[];minor_div=0.;withholding=0.;upstream=0.
        for i in range(1,4):
            gate=foreign_gate if i==2 else True
            payout=min(max(0.,re[i]),max(0.,cash[i]-floor[i]),max(0.,profits[i])*(.8 if t<=3 else 1.)+max(0.,cash[i]-floor[i])* .25) if gate else 0.
            cash[i]-=payout;re[i]-=payout
            common=payout*owners[i];minor_div+=payout-common
            wht=common*.05 if i==2 else 0.
            withholding+=wht;upstream+=common-wht;cash[0]+=common-wht
            re[0]+=common-wht
            gross_div.append(payout)
        # New loans are explicit, repayable claims; no invisible group pooling.
        new_internal=[0.,0.,0.,0.]
        for i in range(1,4):
            needed=max(0.,floor[i]-cash[i])
            can=min(needed,max(0.,cash[0]-floor[0]))
            cash[i]+=can;cash[0]-=can;face[i]+=can;new_internal[i]=can
        borrow=[0.,0.,0.,0.]
        for i in range(4):
            short=max(0.,-cash[i])
            credit=max(0.,.40-sum(debt))
            added=min(short,credit);cash[i]+=added;debt[i]+=added;borrow[i]=added
        if min(cash)<-1e-9:
            return {'scenario':scenario,'method':method,'feasible':False,'failure_year':t,'unfunded':-min(cash),'value':None,'years':rows,'failure_cash':cash}
        common_profit=profits[0]+sum(profits[i]*owners[i] for i in range(1,4))+ap+bd+oi-withholding
        ordinary=max(0.,common_profit)*.34
        cash_return=.10 if scenario=='cash_return_fast' else .02 if scenario=='cash_return_slow' else .05
        wanted=ordinary+cash_return*max(0.,cash[0]-floor[0]-ordinary)
        d=min(wanted,max(0.,re[0]),max(0.,cash[0]-floor[0]))
        cash[0]-=d;re[0]-=d
        # Restricted cash belongs to shareholders, earns interest, remains in all future states.
        minority_profit=sum(profits[i]*(1-owners[i]) for i in range(1,4))
        minority_equity+=minority_profit-minor_div
        shareholder=d/SHARES;dividends.append(shareholder)
        pv+=shareholder/(1+k)**t
        # Consolidated cash identity: internal loans/dividends cancel; no securities multiples.
        rhs=start_cash+sum(op_cash)+sum(maturities)-sum(repay)+sum(borrow)+ad+bd+oi-minor_div-withholding-reversal_tax-d
        residual=sum(cash)+sum(restricted)-rhs
        assert abs(residual)<1e-8*max(1.,abs(rhs)),(t,residual)
        assert abs(start_deposits-sum(deposits)-sum(maturities))<1e-8
        assert abs(startdebt-sum(debt)-sum(repay)+sum(borrow))<1e-8
        assert min(cash)>=-1e-9 and all(x>=-1e-9 for x in face)
        row={'year':t,'revenue':rev,'ebit':ebit,'nwc':nwc,'fixed_intangibles_goodwill':fixed,'da':da,'maintenance':maintenance,'growth':growth,'capex':capex,'cash_taxes':taxes,'operating_cash_after_investment':op_cash,'cash':cash[:],'restricted':restricted[:],'financial_principal':deposits[:],'financial_interest':financial_interest,'external_debt':debt[:],'notes_linked_debt':notes,'debt_interest':debt_interest,'debt_repaid':repay,'new_external_debt':borrow,'internal_loan_face':face[:],'internal_loan_allowance':allowance,'internal_interest':internal_interest,'internal_repaid':internal_paid,'internal_new':new_internal,'allowance_reversal':allow_reversal,'allowance_tax':reversal_tax,'parent_sub_investment_cost':sub_cost[:],'parent_re':re[0],'retained_earnings':re[:],'statutory_reserve_budget':reserves[:],'associate_open':startassoc,'associate_profit':ap,'associate_cash':ad,'associate_equity':assoc,'associate_tax_basis':assoc_cost,'associate_disposal_gain':gain,'associate_exit_tax':etax,'bank_open':startbank,'bank_profit':bp,'bank_dividend':bd,'bank_equity':bank,'bank_cost':bank_cost,'other_equity':other_equity,'old_dividend_paid':old_paid,'old_dividend_receivable':olddiv,'upstream_gross':gross_div,'upstream_net':upstream,'upstream_tax':withholding,'minority_profit':minority_profit,'minority_dividend':minor_div,'minority_equity':minority_equity,'distribution':d,'per_share':shareholder,'shares':SHARES,'treasury_shares':0.,'option_shares':0.,'cash_identity_residual':residual,'cumulative_pv':pv,'operating_cash_floor':floor,'common_profit':common_profit}
        rows.append(row);prev_rev=rev
    # Horizon is numerical quadrature, NOT sale or maturity: all economic states continue.
    terminal5=sum(dividends[i]/(1+k)**(i-4) for i in range(5,len(dividends)))
    return {'scenario':scenario,'method':method,'feasible':True,'discount_rate':k,'horizon':horizon,'value':pv,'D5':dividends[:5],'Y5':terminal5,'PV5':sum(dividends[i]/(1+k)**(i+1) for i in range(min(5,len(dividends)))),'opening_total_cash_including_restricted':opening_cash,'years':rows}

def tests():
    # Actual production chains, exact hand cases.
    assert profit_reserve(-2.,.1,1.,1.)==(-1.,.1,0.)
    a=profit_reserve(-2.,.1,3.,1.);assert abs(a[0]-.9)<1e-12 and abs(a[1]-.2)<1e-12
    a=disposal(10.,6.,.02,.25);assert all(abs(x-y)<1e-12 for x,y in zip(a,(8.85,3.8,.95)))
    low=run('core_low',horizon=12);high=run('core_high',horizon=12)
    assert low['value']<high['value']
    fail=run('funding_failure',horizon=5);assert not fail['feasible'] and fail['value'] is None
    unit=run('unit_cash',horizon=1,k=.1)
    assert abs(unit['years'][0]['cash'][0]-1.9191862)<1e-12
    assert abs(unit['years'][0]['distribution']-.1114138)<1e-12
    assert abs(unit['value']-.1114138/SHARES/1.1)<1e-12
    return {'production_hand_cases':4,'dominant_margin_ordering':True,'funding_failure_halts':True}

if __name__=='__main__':
    cases={}
    for name,k in [('base',.10),('core_low',.105),('core_high',.095),('cycle',.10),('structural',.10),('upside',.10),('repatriation_delay',.10),('no_rollover',.10),('associate_exit',.10),('associate_delay',.10),('associate_return_low',.10),('cash_return_fast',.10),('cash_return_slow',.10),('acquisition_unmatched',.10),('funding_failure',.10)]:
        cases[name]=run(name,k=k)
    for name,k in [('core_low',.105),('core_high',.095)]:cases['product_'+name]=run(name,'products',k=k)
    cases['holder_base_low']=run(k=.105)
    cases['holder_base_high']=run(k=.095)
    tail={str(n):run(horizon=n) for n in (120,240,360)}
    result={'as_of':ASOF,'currency':'CNY','units':'billion except per-share','entity_order':['listed_parent','domestic_sub_pool','overseas_sub_pool','cleaning_60pct'],'tests':tests(),'cases':cases,'tail':tail}
    json.dump(result,sys.stdout,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False);print()

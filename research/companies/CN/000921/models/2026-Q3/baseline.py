#!/usr/bin/env python3
"""Units CNY bn. B actual entity gross; R economic common-owned portfolio, NOT a legal entity.
Only P is a statutory rollforward. B/R capacity is economic upstream budget, not legal reserve.
Finite cohorts apply to ALL retained cash. No terminal principal plug, no market price.
"""
import json,gzip,copy,math,importlib.util,types,base64,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).parent
SH=1.384861171; OWN=.492; ASOF='2026-10-26T14:00:00+08:00'
PATHS={
'base':([2.3,2.4,2.5,2.6,2.7],[.35,.45,.6,.7,.8],[.45]*5,[.5,.45,.4,.35,.35]),
'cycle':([1.9,2.1,2.3,2.5,2.7],[.1,.2,.4,.6,.8],[.55,.55,.5,.45,.45],[.6,.55,.45,.4,.35]),
'structural':([2,1.8,1.6,1.5,1.4],[.1,0,-.1,-.1,.2],[.55]*5,[.6,.55,.5,.6,.35]),
'upside':([2.5,2.7,2.9,3.1,3.3],[.5,.65,.8,1,1.2],[.55]*5,[.6,.6,.55,.5,.5])}

def statute(profit,retained,registered,reserve,voluntary=0):
    # Full losses first; statutory cap uses registered, not paid-in or investment cost.
    eligible=max(0,profit-max(0,-retained))
    add=min(eligible*.1,max(0,registered*.5-reserve))
    voluntary_add=min(max(0,retained+profit-add),max(0,voluntary))
    return retained+profit-add-voluntary_add,reserve+add,add,voluntary_add

def parent_step(cash,retained,reserve,new_dividend,interest,old_receivable=0,loan_repayment=0,capital_principal=0,capital_gain=0,desired=1e99,registered=SH):
    # Redemption/old receivable/principal are cash only; gain and NEW dividend enter income.
    income=new_dividend+interest+capital_gain
    legal,rs,add,va=statute(income,retained,registered,reserve)
    available=cash+new_dividend+interest+old_receivable+loan_repayment+capital_principal+capital_gain
    if available < -1e-9:return dict(feasible=False,shortfall=-available)
    d=max(0,min(desired,available,legal))
    return dict(feasible=True,cash=available-d,retained=legal-d,reserve=rs,reserve_add=add,income=income,distribution=d)

def exit_asset(proceeds,basis,cost,tax,ownership,delay,r,shares,redeem_fraction=0):
    # Asset sale/solvent capital reduction: explicit cost, gain tax, shareholder ownership.
    gain=max(0,proceeds-basis-cost); tax_paid=gain*tax
    net=max(0,proceeds-cost-tax_paid)
    returned_basis=min(basis,net); realized_gain=max(0,net-basis)
    return dict(net=net,principal=returned_basis,gain=realized_gain,tax=tax_paid,cost=cost,
      parent_cash=ownership*net,parent_profit=ownership*(net-basis),realized_loss=max(0,basis-net),
      remaining_shares=shares*(1-redeem_fraction),holder_cash_per_original_share=net*ownership/shares,
      pv_per_original_share=net*ownership/(1+r)**delay/shares)

def new_batch(batches,amount,t,delay,term):
    if amount>1e-11:batches.append(dict(origin=t,initial=amount,balance=amount,start=t+delay+1,end=t+delay+term,paid=0.,used=0.))

def consume(batches,amount):
    # Pro rata spending: no FIFO trick leaving newer cohorts indefinitely unvalued.
    total=sum(x['balance'] for x in batches)
    if amount>total+1e-8:return False
    if total:
        for x in batches:
            spent=x['balance']*amount/total;x['balance']-=spent;x['used']+=spent
    return True

def release(batches,t,capacity):
    due=[]
    for x in batches:
        if t>=x['start']:
            amount=x['balance'] if t>=x['end'] else x['balance']/(x['end']-t+1)
            due.append((x,amount))
    total=sum(a for _,a in due);factor=min(1,max(0,capacity)/total) if total else 0
    for x,a in due:
        x['balance']-=a*factor;x['paid']+=a*factor
        if a*factor>1e-11:x['last_payment']=t
    return total*factor,total

def japan_state(loss=.81068195,basis=1.24038777677*.7094/.7488):
    return dict(cash=0.,profit_budget=-loss,capital_headroom=0.,reorganized=False,
      capital_reduction_remaining=(21.899211610+14.196235)*.04205-.3,
      basis_common=basis,batches=[],cumulative_support=0.)

def japan_step(state,profit,investment,t,reorg_year=15,hold=10,term=5,friction=.10):
    """Full Japanese layer amounts, ordinary and capital realization routed separately.
    Historical consolidated loss is a conditional availability proxy, not Japanese legal ledger.
    Reorganization requires creditor/solvency approval and capital+premium sufficient to clear
    remaining loss AND establish a return-of-capital source for accumulated incremental cash.
    No old debt is charged again. Capital reduction without share cancellation is proportional;
    all Sanden ownership percentages and listed-parent shares remain unchanged.
    """
    st=state;opening=st['cash'];interest=opening*.02*(1-.305)
    income=profit+interest;st['profit_budget']+=income
    cf=income-investment;support=max(0,-(opening+cf))
    if cf>=0:new_batch(st['batches'],cf,t,hold,term)
    else:consume(st['batches'],min(opening,-cf))
    st['cumulative_support']+=support
    st['cash']=sum(b['balance'] for b in st['batches'])
    clearing=conversion=0.
    if not st['reorganized'] and reorg_year is not None and t>=reorg_year:
      clearing=max(0,-st['profit_budget'])
      conversion=max(0,st['cash']-max(0,st['profit_budget']))
      required=clearing+conversion
      if required<=st['capital_reduction_remaining']+1e-10:
        st['profit_budget']+=clearing
        st['capital_headroom']+=conversion
        st['capital_reduction_remaining']-=required;st['reorganized']=True
      else:clearing=conversion=0.
    ordinary_capacity=max(0,st['profit_budget'])
    paid,due=release(st['batches'],t,ordinary_capacity+st['capital_headroom'])
    ordinary=min(paid,ordinary_capacity);capital=paid-ordinary
    st['profit_budget']-=ordinary;st['capital_headroom']-=capital
    st['cash']=sum(b['balance'] for b in st['batches'])
    common_ordinary=ordinary*.7094;common_capital=capital*.7094
    basis_return=min(st['basis_common'],common_capital)
    st['basis_common']-=basis_return
    gain_tax=max(0,common_capital-basis_return)*.25
    ordinary_net=common_ordinary*(1-friction)
    capital_net=(common_capital-gain_tax)*(1-friction)
    capital_pnl=capital_net-basis_return
    residual=opening+income-investment+support-paid-st['cash']
    assert abs(residual)<1e-8 and st['cash']>=-1e-10
    return dict(opening_cash=opening,interest=interest,interest_gross=opening*.02,
      interest_tax=opening*.02*.305,operating_profit=profit,investment=investment,
      support=support,common_support=support*.7094,minority_support=support*.2906,
      cash=st['cash'],profit_budget=st['profit_budget'],capital_headroom=st['capital_headroom'],
      capital_clearing=clearing,capital_conversion=conversion,
      capital_reduction_remaining=st['capital_reduction_remaining'],reorganized=st['reorganized'],
      ordinary_distribution=ordinary,capital_distribution=capital,due=due,
      common_dividend_received=ordinary_net,common_capital_principal=basis_return,
      common_capital_pnl=capital_pnl,common_capital_cash=capital_net,
      common_realization_leakage=(ordinary+capital)*.7094-ordinary_net-capital_net,
      capital_gain_tax=gain_tax,remaining_basis_common=st['basis_common'],cash_residual=residual)

def run(path='base',finance=18.,bfinance=8.,r=.10,g=.015,years=240,term=30,delay=5,
        budget_b=0.,budget_r=4.5,tax_b=.15,tax_r=.23,y=.015,friction=.015,
        parent_start=1.5,extra_wc=0.,reserve_buffer=.5,shock_year=None,shock_amount=0.,op_scale=1.,necessary_finance=3.,necessary_release_start=4,necessary_release_years=3,j_reorg_year=15,j_hold=10,j_term=5,j_friction=.10,j_basis=1.24038777677*.7094/.7488,j_loss=.81068195,j_scale=1.):
    """B/R opening distribution capacity is an ECONOMIC budget, not legal fact.
    Unknown detailed reserves represented by finite .5bn B / .5bn R availability buffer,
    not endless 10% nor registration proxy. P statutory uses real reported reserve.
    Core B zero; R 4.5bn historical upstream capacity is an economic budget,
    approximately half of residual consolidated retained earnings, NOT a legal balance.
    It is constrained by consolidated retained earnings less Bosch attribution, NOT a
    claim that different entities can net losses or that this is legal distributable profit.
    Positive capacity is sensitivity only, not a legal ledger or measured reserve.
    """
    if path=='structural':g=0
    p1,p2,i1,i2=PATHS[path]
    cash=[bfinance,finance-OWN*bfinance-parent_start-extra_wc,parent_start]
    if min(cash)<0:return {'feasible':False,'reason':'negative opening cash'}
    batches=[[],[],[]]
    for k in range(3):new_batch(batches[k],cash[k],0,delay,term)
    capacity=[budget_b,budget_r]; buffer=[reserve_buffer,reserve_buffer]
    # Actual mother reported reserve, not consolidated surplus or arbitrary paid-in proxy.
    lp=6.03298055478;rp=.694073685
    necessary_initial=necessary_finance
    js=japan_state(j_loss,j_basis)
    rows=[];ds=[];maxgap=[0,0];cumprofit=[0,0];cumdiv=[0,0];capital=[0.,0.]
    for t in range(1,years+1):
        start=cash[:];ints=[cash[0]*y/.85*(1-tax_b),cash[1]*y/.77*(1-tax_r),cash[2]*y]
        if t<=5:nb,nr,ib,ir=p1[t-1],p2[t-1],i1[t-1],i2[t-1]
        else:
            nb=p1[-1]*(1+g)**(t-5);nr=p2[-1]*(1+g)**(t-5)
            ib=max(nb,0)*g/.14+(.15 if g==0 else 0)
            ir=max(nr,0)*g/.14+(.2 if g==0 else 0)
        # Explicit pre-tax base budget. Negative profit has no instantaneous tax shield.
        eb=nb/.85*op_scale
        # Japan loss is taxed separately, never netted against domestic taxable profit.
        jpath=[-.2,-.2,-.15,-.1,0] if path=='structural' else [-.1,-.05,0,.025,.05]
        jp0=(jpath[t-1] if t<=5 else jpath[-1]*(1+g)**(t-5))*j_scale
        jafter0=(jp0-max(jp0,0)*.305)*.7094
        domestic_after0=nr-jafter0
        er=(domestic_after0/.77 if domestic_after0>=0 else domestic_after0)*op_scale
        jp=jp0*op_scale;jtax=max(jp,0)*.305;jcommon=(jp-jtax)*.7094
        tb=max(eb,0)*tax_b;tr=max(er,0)*tax_r
        nb=eb-tb;domestic_np=er-tr
        nr=domestic_np+jcommon
        necessary_gross_interest=necessary_finance*.02
        necessary_tax=necessary_gross_interest*.25
        nr+=necessary_gross_interest-necessary_tax
        necessary_release=0.
        if necessary_release_start is not None and t>=necessary_release_start:
            necessary_release=min(necessary_finance,necessary_initial/necessary_release_years)
            necessary_finance-=necessary_release
            new_batch(batches[1],necessary_release,t,delay,term)
            cash[1]+=necessary_release;start[1]+=necessary_release
        # Necessary capital earns via specified profit path; it isn't parked as idle cash.
        if t>5 and g>0:ib=nb*g/.14;ir=max(nr-necessary_gross_interest+necessary_tax,0)*g/.14
        original_ir=ir
        japan_investment=max(jp-jtax,0)*g/.14 if t>5 else 0.
        jr=japan_step(js,jp-jtax,japan_investment,t,j_reorg_year,j_hold,j_term,j_friction)
        ir-=.7094*japan_investment
        nr=domestic_np+necessary_gross_interest-necessary_tax-jr['common_support']
        nps=[nb,nr];invs=[ib,ir]
        dividends=[];releases=[];due=[];adds=[]
        if shock_year==t:
            new_batch(batches[1],shock_amount,t,delay,term);cash[1]+=shock_amount
            start[1]+=shock_amount # designated diagnostic outside operating earnings; capital gain NOT created
        for k in range(2):
            capital[k]+=invs[k]
            profit=nps[k]+ints[k];cumprofit[k]+=profit
            # Availability buffer consumes forecast positive earnings after past budget losses first.
            replenishment=max(0,profit-max(0,-capacity[k]))
            buf=min(buffer[k],replenishment*.1);buffer[k]-=buf
            capacity[k]+=profit-buf
            fcf=nps[k]-invs[k]
            planned=max(0,nps[k]*(.7 if k==0 else .5)) if t<=5 else max(0,fcf)*.90
            # interest paid as income; 10% long-run operating cash deferral remains a finite batch.
            available=sum(x['balance'] for x in batches[k])+fcf+ints[k]
            if available<-1e-8:return dict(feasible=False,failure_year=2026+t,reason='cash exhausted without financing',rows=rows)
            ordinary=min(planned+ints[k],max(0,capacity[k]),max(0,available))
            delta=fcf+ints[k]-ordinary
            if delta>=0:new_batch(batches[k],delta,t,delay,term)
            elif not consume(batches[k],-delta):raise AssertionError('finance double spend')
            capacity[k]-=ordinary
            rel,wanted=release(batches[k],t,max(0,capacity[k]));capacity[k]-=rel
            d=ordinary+rel;cumdiv[k]+=d
            dividends.append(d);releases.append(rel);due.append(wanted);adds.append(max(delta,0))
            cash[k]=sum(x['balance'] for x in batches[k])
            maxgap[k]=max(maxgap[k],cumdiv[k]-cumprofit[k])
        # Both are NEW dividend budgets from true sources; minority deducted ONLY on gross B.
        gross_up=OWN*dividends[0]+dividends[1]
        fee=gross_up*friction
        up=gross_up-fee+jr['common_dividend_received']
        jcapital_cash=jr['common_capital_cash']
        desired=[.65,.75,.85,.95,1.05][t-1]*SH if t<=5 else up+ints[2]+jcapital_cash
        # parent retention also batched, not an initial-only release.
        parent_capacity=max(0,lp+up+ints[2]+jr['common_capital_pnl'])
        prelease,wanted=release(batches[2],t,max(0,parent_capacity-desired))
        if t>5:desired+=prelease
        z=parent_step(cash[2],lp,rp,up,ints[2],capital_principal=jr['common_capital_principal'],capital_gain=jr['common_capital_pnl'],desired=desired)
        assert z['feasible'];d=z['distribution'];lp=z['retained'];rp=z['reserve']
        # Reconcile parent batches after actual payout, preventing pre-release double counting.
        expected=cash[2]+up+ints[2]+jcapital_cash-d
        tracked=sum(x['balance'] for x in batches[2])
        if expected>tracked:new_batch(batches[2],expected-tracked,t,delay,term)
        elif not consume(batches[2],tracked-expected):raise AssertionError('parent cash failure')
        cash[2]=expected
        end=OWN*cash[0]+cash[1]+cash[2]+.7094*js['cash']
        equation=OWN*start[0]+start[1]+start[2]+.7094*jr['opening_cash']+OWN*(nb-ib+ints[0])+domestic_np+necessary_gross_interest-necessary_tax+.7094*(jp-jtax+jr['interest'])-original_ir+ints[1]+ints[2]-fee-jr['common_realization_leakage']-d-end
        assert abs(equation)<1e-7*max(1,end)
        assert min(cash)>-1e-9
        ds.append(d/SH)
        rows.append(dict(t=t,year=2026+t,shares=SH,B=dict(identity='青岛海信博世空调系统有限公司/经济上划预算',ownership=OWN,pretax=eb,tax=tb,np=nb,interest=ints[0],financial_gross_interest=start[0]*y/.85,financial_tax=start[0]*y/.85*tax_b,investment=ib,cumulative_investment=capital[0],dividend=dividends[0],minority_dividend=.508*dividends[0],capacity_budget=capacity[0],remaining_buffer=buffer[0],cash=cash[0],cohort_add=adds[0],principal_release=releases[0],principal_due=due[0]),J=dict(identity='三电株式会社日本层经济税额预算，非单体法定分红账',ownership=.7094,pretax=jp,tax_rate=.305,tax=jtax,common_profit=jcommon,dividend_budget=jr['ordinary_distribution'],route=jr,registered_capital_jpy=21848976610+50235000,registered_cash_increase_jpy=50235000,share_premium_increase_jpy=50235000),R=dict(identity='其他归母经营及上划能力预算，非法律主体',ownership=1,pretax_equivalent=er,tax_budget=tr,np=nr,interest=ints[1],financial_gross_interest=(start[1]-necessary_release-(shock_amount if shock_year==t else 0))*y/.77,financial_tax=(start[1]-necessary_release-(shock_amount if shock_year==t else 0))*y/.77*tax_r,investment=ir,cumulative_investment=capital[1],dividend=dividends[1],capacity_budget=capacity[1],remaining_buffer=buffer[1],cash=cash[1],cohort_add=adds[1],principal_release=releases[1],principal_due=due[1]),P=dict(identity='海信家电集团股份有限公司单体',new_dividend=up,transfer_cost=fee,interest=ints[2],financial_gross_interest=start[2]*y/.75,financial_tax=start[2]*y/.75*.25,profit=z['income'],old_receivable=0,internal_loan_principal=0,capital_return=jr['common_capital_principal'],capital_realization_pnl=jr['common_capital_pnl'],japan_ordinary_dividend=jr['common_dividend_received'],japan_capital_cash=jcapital_cash,cash=cash[2],retained=lp,statutory_reserve=rp,reserve_add=z['reserve_add'],dividend=d,cohort_release=prelease),necessary_finance=necessary_finance,necessary_release=necessary_release,necessary_gross_interest=necessary_gross_interest,necessary_finance_tax=necessary_tax,common_cash=end+necessary_finance,available_common_cash=end-.7094*js['cash'],japan_restricted_common_cash=.7094*js['cash'],dividend_per_share=d/SH,cash_residual=equation))
    pv=sum(d/(1+r)**(i+1) for i,d in enumerate(ds));tv=sum(ds[i]/(1+r)**(i-4) for i in range(5,len(ds)))
    return dict(feasible=True,value=pv,tv5=tv,d5=ds[:5],tv_pv_share=tv/(1+r)**5/pv if pv else 0,params=dict(path=path,finance=finance,bfinance=bfinance,r=r,g=g,years=years,term=term,delay=delay,budget_b=budget_b,budget_r=budget_r,tax_b=tax_b,tax_r=tax_r,y=y,friction=friction,parent_start=parent_start,extra_wc=extra_wc,reserve_buffer=reserve_buffer,op_scale=op_scale,necessary_finance=necessary_initial,necessary_release_start=necessary_release_start,necessary_release_years=necessary_release_years,j_reorg_year=j_reorg_year,j_hold=j_hold,j_term=j_term,j_friction=j_friction,j_basis=j_basis,j_loss=j_loss,j_scale=j_scale,shock_year=shock_year,shock_amount=shock_amount),rows=rows,cohorts=batches,japan_cohorts=js['batches'],required_opening_capacity=maxgap)

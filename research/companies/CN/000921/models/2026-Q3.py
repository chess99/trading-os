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


LEGACY_SOURCE='#!/usr/bin/env python3\n"""海信家电2026Q3，人民币十亿元；慢恢复与逐年金融释放的核心持有人模型；原证、研究假设与敏感性分开。\n实际分红受资金及法定利润双约束；历史现金分项冲突保留，不反改原表。\n"""\nimport json, math\nfrom pathlib import Path\nSHARES=1.384861171 # 保持已发行全部股数，未执行注销不提前享受\nOWN=.492\n\ndef pv_flows(flows,r):\n    return sum(x/(1+r)**(i+1) for i,x in enumerate(flows))\n\ndef treasury_value(principal,rate,yield_rate,delay,release_years):\n    """利息每年支付；本金delay年后等额release_years年回收；None=不回收本金。\n    仅是治理/期限单因素诊断，未声称已授权特别分红。"""\n    if release_years is None:\n        return principal*yield_rate/rate\n    balance=principal; flows=[]\n    for year in range(1,delay+release_years+1):\n        interest=balance*yield_rate\n        release=principal/release_years if year>delay else 0\n        balance-=release; flows.append(interest+release)\n    assert abs(balance)<1e-8\n    return pv_flows(flows,rate)\n\ndef operating_dcf(np_b,np_other,investment_b,investment_other,r=.10,g=.015,roi=.14):\n    """已经按实际权益归属；其他为归母净数，不能再次扣三电少数。\n    np剔除金融收益，投资为DA后净固定/营运追加，借款税后成本超过金融收益率的净利差已入其他税后利润。\n    TV再投资与g/ROI相容；不自动计入金融本金。"""\n    cf=[OWN*(p-i)+q-j for p,q,i,j in zip(np_b,np_other,investment_b,investment_other)]\n    n=len(cf)\n    np_next=(OWN*np_b[-1]+np_other[-1])*(1+g)\n    terminal_cf=np_next*(1-g/roi)\n    tv=terminal_cf/(r-g)\n    pv=pv_flows(cf,r)+tv/(1+r)**n\n    return dict(common_profit=[OWN*p+q for p,q in zip(np_b,np_other)],common_fcfe=cf,operating_value=pv,operating_terminal=tv,terminal_pv_share=tv/(1+r)**n/pv)\n\ndef parent_budget(np_b,np_other,dividend_ps,initial_cash=1.5,initial_legal=6.03298055478,y=.015):\n    """辅助诊断普通分红候选的付款约束；海信博世70%和其他50%宣派且当年到账是条件。\n    初始现金1.5为H1余额扣已宣股息及缓冲后的量级，非已核Q3母公司余额。\n    不把应收股利收回再次计为利润；不以该诊断发布return_model。"""\n    cash=initial_cash; legal=initial_legal; rows=[]\n    for i,(p,q,d) in enumerate(zip(np_b,np_other,dividend_ps)):\n        up=OWN*p*.7+max(q,0)*.5\n        income=up+cash*y\n        desired=d*SHARES\n        actual=max(0,min(desired,cash+income,legal+income))\n        before=cash;cash+=income-actual;legal+=income-actual\n        assert abs(before+income-actual-cash)<1e-10\n        assert cash>=-1e-10 and legal>=-1e-10\n        rows.append(dict(year=2027+i,upstream_declared_and_received=up,parent_profit=income,desired_dividend=desired,actual_dividend=actual,parent_cash=cash,parent_legal_profit=legal,constrained=actual<desired-1e-10))\n    return rows\n\nPATHS={\n \'partial_recovery\':dict(np_b=[2.3,2.4,2.5,2.6,2.7],np_other=[.35,.45,.6,.7,.8],investment_b=[.45]*5,investment_other=[.5,.45,.4,.35,.35]),\n \'cyclical_delay\':dict(np_b=[1.9,2.1,2.3,2.5,2.7],np_other=[.1,.2,.4,.6,.8],investment_b=[.55,.55,.5,.45,.45],investment_other=[.6,.55,.45,.4,.35]),\n \'structural_loss\':dict(np_b=[2.0,1.8,1.6,1.5,1.4],np_other=[.1,0,-.1,-.1,.2],investment_b=[.55]*5,investment_other=[.6,.55,.5,.6,.35]),\n \'better_execution\':dict(np_b=[2.5,2.7,2.9,3.1,3.3],np_other=[.5,.65,.8,1.,1.2],investment_b=[.55]*5,investment_other=[.6,.6,.55,.5,.5])}\n\ndef owner_run(inputs, common_finance=21., bosch_finance=8., release=.03, r=.10, g=.015, years=200, other_legal=6., parent_start=1.5, parent_legal=6.03298055478,exit_other=False,bosch_legal=5.5,yield_rate=.015):\n    # C为扣外债/必要经营资金后的净金融等效余额；负债正常续作的税后净利差已入其他经营NP。\n    # 博世bucket为全额；R为其他业务已扣少数的权益组合，三电不承担上划预算。\n    cb=bosch_finance; cr=common_finance-OWN*cb-parent_start; cp=parent_start\n    lb=bosch_legal;lr=other_legal;lp=parent_legal\n    assert min(cb,cr,cp)>=0\n    rows=[]; distributions=[]; cap_b=cap_r=0; reserve_b=reserve_r=reserve_p=0\n    for t in range(1,years+1):\n        if t<=5:\n            nb=inputs[\'np_b\'][t-1];nr=inputs[\'np_other\'][t-1]\n            ib=inputs[\'investment_b\'][t-1];ir=inputs[\'investment_other\'][t-1]+(1. if exit_other and t==5 else 0)\n        else:\n            nb=inputs[\'np_b\'][-1]*(1+g)**(t-5);nr=inputs[\'np_other\'][-1]*(1+g)**(t-5)\n            ib=nb*g/.14+(0.15 if g==0 else 0);ir=max(nr,0)*g/.14+(0.2 if g==0 else 0)\n            if exit_other:nr=0;ir=0\n        cap_b+=ib;cap_r+=ir\n        old=(cb,cr,cp);interest_b=cb*yield_rate;interest_r=cr*yield_rate;interest_p=cp*yield_rate\n        pb=nb+interest_b;pr=nr+interest_r\n        # 未逐主体证明公积已达上限：每年正利润保守提10%，亏损全额结转。\n        # 即使尚有未弥补亏损也提取正利润的10%，且不假设未来达到上限停止；因此偏保守。\n        rb=max(pb,0)*.10;rr=max(pr,0)*.10\n        reserve_b+=rb;reserve_r+=rr\n        cb+=pb-ib;cr+=pr-ir;lb+=pb-rb;lr+=pr-rr\n        # 资金不足时停止新增分配；负cash属于融资不可行，不能默许无偿注资。\n        if min(cb,cr)<-1e-9:\n            return {\'feasible\':False,\'failure_year\':2026+t,\'reason\':\'subsidiary net liquidity exhausted\',\'rows\':rows}\n        if t<=5:\n            desired_b=max(0,.7*nb);desired_r=max(0,.5*nr)\n        else:\n            # 仅逐年释放余额2%-4%，同时派出当年经营净现金与金融利息；没有第五年全部释放。\n            ramp=min(1.,.6+.08*(t-5))\n            desired_b=max(0,nb-ib)*ramp+interest_b+release*ramp*old[0]\n            desired_r=max(0,nr-ir)*ramp+interest_r+release*ramp*old[1]\n        db=max(0,min(desired_b,cb,lb));dr=max(0,min(desired_r,cr,lr))\n        cb-=db;cr-=dr;lb-=db;lr-=dr\n        up=OWN*db+dr\n        # 子股利不二次提取；母自有金融正收益仍保守提10%，不影响现金守恒。\n        rp=max(interest_p,0)*.10;reserve_p+=rp\n        cp+=up+interest_p;lp+=up+interest_p-rp\n        desired=([.65,.75,.85,.95,1.05][t-1]*SHARES if t<=5 else up+interest_p+release*min(1.,.6+.08*(t-5))*old[2])\n        d=max(0,min(desired,cp,lp));cp-=d;lp-=d\n        start=OWN*old[0]+old[1]+old[2];end=OWN*cb+cr+cp\n        assert abs(start+OWN*(pb-ib)+(pr-ir)+interest_p-d-end)<1e-8\n        assert min(cb,cr,cp)>-1e-8\n        assert not (lb < -1e-8 and db > 1e-8)\n        assert not (lr < -1e-8 and dr > 1e-8)\n        assert not (lp < -1e-8 and d > 1e-8)\n        distributions.append(d)\n        rows.append(dict(year=2026+t,bosch_reserve_addition=rb,other_reserve_addition=rr,parent_reserve_addition=rp,bosch_cumulative_reserve=reserve_b,other_cumulative_reserve=reserve_r,parent_cumulative_reserve=reserve_p,bosch_operating_np=nb,other_common_operating_np=nr,bosch_net_investment=ib,other_net_investment=ir,bosch_declared_dividend=db,external_bosch_dividend=(1-OWN)*db,other_upstream=dr,parent_cash=cp,parent_legal=lp,bosch_cash=cb,other_common_cash=cr,bosch_legal=lb,other_legal=lr,common_net_finance=end,common_dividend=d,dividend_per_share=d/SHARES,dividend_capped=d<desired-1e-10))\n    pv=pv_flows(distributions,r)/SHARES\n    tv=sum(distributions[t-1]/(1+r)**(t-5) for t in range(6,years+1))/SHARES\n    return dict(feasible=True,value_per_share=pv,terminal_year5=tv,distributions_first5=[d/SHARES for d in distributions[:5]],terminal_pv_share=(tv/(1+r)**5/pv if pv else 0),rows=rows,tail_note=\'200年后剩余现金与经营现值未加，误差以再跑300年检验\')\n\ndef run():\n    out={\'status\':\'owner_cash_model\',\'information_cutoff\':\'2026-10-26T14:00:00+08:00\',\'unit\':\'CNY billion, per_share CNY\',\'value_range\':None,\'return_model\':None,\'shares_billion\':SHARES,\'paths\':{}}\n    for key,inputs in PATHS.items():\n        structural=key==\'structural_loss\'\n        op=operating_dcf(**inputs,r=.11 if structural else .10,g=0 if structural else .015,roi=.10 if structural else .14)\n        op[\'parent_budget\']=parent_budget(inputs[\'np_b\'],inputs[\'np_other\'],[.65,.75,.85,.95,1.05])\n        op[\'operating_value_per_share\']=op[\'operating_value\']/SHARES\n        # 资本化仅诊断盈利持续性。9-12倍由10%成本/0-1.5%增速/必要再投约束，不取同业均值。\n        op[\'earnings_power_operating_per_share\']=[(pv_flows(op[\'common_fcfe\'],.11 if structural else .10)+op[\'common_profit\'][-1]*pe/(1+(.11 if structural else .10))**5)/SHARES for pe in [9,12]]\n        out[\'paths\'][key]=op\n    out[\'treasury_sensitivity\']={}\n    for principal in [12.,20.]:\n        out[\'treasury_sensitivity\'][str(principal)]={}\n        for label,delay,years in [(\'interest_only\',0,None),(\'release_6_25\',5,20),(\'release_11_30\',10,20)]:\n            out[\'treasury_sensitivity\'][str(principal)][label]=treasury_value(principal,.10,.015,delay,years)/SHARES\n    # 正式计算函数的可手算特例\n    assert abs(pv_flows([11,12.1],.1)-20)<1e-10\n    assert abs(treasury_value(100,.10,0,0,1)-100/1.1)<1e-10\n    assert abs(treasury_value(100,.10,.02,0,None)-20)<1e-10\n    # 当利润恒定、零再投、零增长、首期现金同于永续时，DCF=全年普通利润/r。\n    v=operating_dcf([1]*5,[0]*5,[0]*5,[0]*5,r=.1,g=0)\n    assert abs(v[\'operating_value\']-.492/.1)<1e-10\n    budget=parent_budget([0],[0],[1],initial_cash=.5,initial_legal=.2,y=0)\n    assert abs(budget[0][\'actual_dividend\']-.2)<1e-10\n    assert abs(budget[0][\'parent_cash\']-.3)<1e-10\n    base=PATHS[\'partial_recovery\']\n    owner={}\n    for name,params in {\'low\':dict(common_finance=19,bosch_finance=12,release=.02,r=.105),\'center\':dict(common_finance=21,bosch_finance=8,release=.03,r=.10),\'high\':dict(common_finance=23,bosch_finance=4,release=.04,r=.095)}.items():\n        owner[name]=owner_run(base,**params)\n        assert owner[name][\'feasible\']\n        extended=owner_run(base,years=300,**params)\n        assert abs(extended[\'value_per_share\']-owner[name][\'value_per_share\'])<.0001\n    out[\'value_range\']={\'low\':round(owner[\'low\'][\'value_per_share\'],2),\'high\':round(owner[\'high\'][\'value_per_share\'],2),\'currency\':\'CNY\'}\n    # 回报模型固定中点的同一资金、法定留存和分配路径，仅重估折现率。\n    return_terminal={label:owner_run(base,common_finance=21,bosch_finance=8,release=.03,r=rate) for label,rate in [(\'low\',.105),(\'high\',.095)]}\n    out[\'return_terminal_fixed_center\']={label:dict(terminal_year5=v[\'terminal_year5\'],discount_rate=.105 if label==\'low\' else .095) for label,v in return_terminal.items()}\n    out[\'return_model\']={\'schema_version\':1,\'method\':\'annual_common_equity_irr_v1\',\'currency\':\'CNY\',\'model_as_of\':out[\'information_cutoff\'],\'base_case_distributions_per_share\':[round(d,4) for d in owner[\'center\'][\'distributions_first5\']],\'base_case_terminal_equity_value_range_per_share\':{\'year_5\':{\'low\':round(return_terminal[\'low\'][\'terminal_year5\'],2),\'high\':round(return_terminal[\'high\'][\'terminal_year5\'],2)}}}\n    out[\'auxiliary_total_range\']=[owner[\'center\'][\'value_per_share\']+p-out[\'paths\'][\'partial_recovery\'][\'operating_value_per_share\'] for p in out[\'paths\'][\'partial_recovery\'][\'earnings_power_operating_per_share\']]\n    out[\'finance_bridge\']={\'gross_financial_assets_estimate\':35.5,\'restricted\':1.16,\'operating_buffer\':4.5,\'external_interest_debt\':4.4,\'other_cash_obligations\':.6,\'group_net_finance\':24.84,\'bosch_total_net_finance_low_high\':[4,12],\'other_minority_net_debt_adjustment\':.6,\'common_net_finance_derived\':[24.84-.508*12+.6,24.84-.508*4+.6],\'common_net_finance_model\':[19,23],\'parent_cash_bridge\':[3.56801452721,-1.75184938132,-.03080368884,-.2,-.08],\'parent_statutory_profit_bridge\':[7.06649564879,.71833428731,-1.75184938132]}\n    out[\'owner_model\']=owner\n    out[\'owner_scenarios\']={name:owner_run(inp,common_finance=21,bosch_finance=8,release=.03,r=.11 if name==\'structural_loss\' else .10,g=0 if name==\'structural_loss\' else .015,exit_other=False) for name,inp in PATHS.items()}\n    out[\'owner_sensitivity\']={\n      \'no_principal_release\':owner_run(base,release=0),\n      \'other_legal_zero\':owner_run(base,other_legal=0),\n      \'both_subsidiary_legal_zero\':owner_run(base,other_legal=0,bosch_legal=0),\n      \'parent_cash_minus_1bn\':owner_run(base,parent_start=.5),\n      \'working_capital_extra_3bn\':owner_run(base,common_finance=18)}\n    # 同一完整函数手算：首年无经营/利息无法隔离因固定收益，利用零资金与零利润零分配应全零。\n    zero=dict(np_b=[0]*5,np_other=[0]*5,investment_b=[0]*5,investment_other=[0]*5)\n    z=owner_run(zero,common_finance=0,bosch_finance=0,parent_start=0,parent_legal=0,other_legal=0,years=5)\n    assert z[\'value_per_share\']==0 and z[\'distributions_first5\']==[0]*5\n    # 单年正常经营B=1,R=0,C=0：B上划.7，其中母.3444，实际全部付出；B现金.3，归母末现金.1476。\n    simple=dict(np_b=[1],np_other=[0],investment_b=[0],investment_other=[0])\n    z=owner_run(simple,common_finance=0,bosch_finance=0,parent_start=0,parent_legal=0,other_legal=0,years=1)\n    assert abs(z[\'rows\'][0][\'common_dividend\']-.3444)<1e-10\n    assert abs(z[\'rows\'][0][\'common_net_finance\']-.1476)<1e-10\n    loss=dict(np_b=[-1,.5,1],np_other=[0]*3,investment_b=[0]*3,investment_other=[0]*3)\n    z=owner_run(loss,common_finance=.984,bosch_finance=2,parent_start=0,parent_legal=0,other_legal=0,bosch_legal=0,years=3,yield_rate=0)\n    # 法定利润-1 -> -.55 -> .35（分配前）；第二年恢复盈利但亏损未填平，不能分红。\n    assert abs(z[\'rows\'][0][\'bosch_legal\']+1)<1e-10\n    assert abs(z[\'rows\'][1][\'bosch_legal\']+.55)<1e-10\n    assert [row[\'bosch_declared_dividend\'] for row in z[\'rows\'][:2]]==[0,0]\n    assert abs(z[\'rows\'][2][\'bosch_declared_dividend\']-.35)<1e-10\n    assert abs(z[\'rows\'][2][\'bosch_cash\']-2.15)<1e-10\n    assert abs(z[\'rows\'][2][\'common_dividend\']-.1722)<1e-10\n    out[\'statutory_loss_test\']=z\n    out[\'tests\']=\'positive profits reserve 10%, full losses carried forward, actual-function loss recovery test; analytic function cases, owner cash conservation, legal constraints and 200/300-year convergence passed\'\n    return out\nif __name__==\'__main__\':\n    data=run();Path(__file__).with_name(\'2026-Q3-output.json\').write_text(json.dumps(data,ensure_ascii=False,indent=2));print(json.dumps(data,ensure_ascii=False,indent=2))\n'

def make():
    m=types.SimpleNamespace(**globals())
    cases={
    'core_low':dict(finance=17,bfinance=10,r=.105),
    'base':dict(),
    'core_high':dict(finance=19,bfinance=6,r=.095),
    'return_low':dict(r=.105),'return_high':dict(r=.095),
    'cycle':dict(path='cycle'),
    'structural':dict(path='structural',r=.11),
    'upside':dict(path='upside'),
    'historical_capacity_10':dict(budget_r=10),
    'no_historical_capacity':dict(budget_r=0),
    'old_liquidity_budget':dict(finance=21,necessary_finance=0),
    'liquidity_extra_6':dict(finance=15,necessary_finance=6),
    'liquidity_extra_12':dict(finance=9,necessary_finance=12),
    'capacity_5':dict(budget_r=5),
    'necessary_permanent':dict(necessary_release_start=None),
    'necessary_release_year10':dict(necessary_release_start=10),
    'cash_release_20':dict(term=20),
    'cash_release_40':dict(term=40),
    'cash_delay_10':dict(delay=10),
    'bosch_tax_expiry':dict(tax_b=.25),
    'other_effective_tax_30':dict(tax_r=.30),
    'operating_profit_minus20':dict(op_scale=.8),
    'finance_loss_3':dict(finance=15),
    'working_capital_extra3':dict(extra_wc=3),
    'parent_location_minus1':dict(parent_start=.5),
    'upstream_friction_5pct':dict(friction=.05),
    'financial_yield_0':dict(y=0),
    'g0_maintained':dict(g=0),
    'no_availability_buffer':dict(reserve_buffer=0),
    'buffer_1':dict(reserve_buffer=1),
    'japan_reorg_year25':dict(j_reorg_year=25),
    'japan_friction20pct':dict(j_friction=.20),
    'japan_basis_zero':dict(j_basis=0),
    'japan_hold20':dict(j_hold=20),
    
    }
    out={'schema':'hisense-economic-budget-v2','unit':'CNY billion except per share CNY','information_cutoff':m.ASOF,'cases':{k:m.run(**v) for k,v in cases.items()}}
    assert all(v['feasible'] for v in out['cases'].values())
    # Same economy old/new; separately identify changed tax/friction/distribution forecasts.
    legacy_ns={'__name__':'embedded_legacy','__file__':__file__}
    exec(compile(LEGACY_SOURCE,'embedded_legacy','exec'),legacy_ns)
    old=types.SimpleNamespace(**legacy_ns)
    out['comparison']={}
    for name,oldname in [('base','partial_recovery'),('cycle','cyclical_delay'),('structural','structural_loss'),('upside','better_execution')]:
      o=old.owner_run(old.PATHS[oldname],r=.11 if name=='structural' else .10,g=0 if name=='structural' else .015,years=240)
      # Exact same nominal operating profit and investment, finance, yield, shareholder ownership.
      n=m.run(path=name,finance=21,necessary_finance=0,friction=0,r=.11 if name=='structural' else .10)
      out['comparison'][name]={'old':o,'new_same_economy':n,'new_economic_budget':out['cases'][name],
        'delta_pv_method':n['value']-o['value_per_share'],'delta_pv_liquidity_reclassification_and_friction':out['cases'][name]['value']-n['value']}
    # Original endpoint operating economy reproduced on both engines; final revised endpoints separate.
    for key,par in [('core_low',dict(common_finance=19,bosch_finance=12,release=.02,r=.105)),('core_high',dict(common_finance=23,bosch_finance=4,release=.04,r=.095))]:
      o=old.owner_run(old.PATHS['partial_recovery'],years=240,**par)
      n=m.run(finance=par['common_finance'],bfinance=par['bosch_finance'],necessary_finance=0,r=par['r'],friction=0)
      out['comparison'][key]={'old':o,'new_same_economy':n,'new_core':out['cases'][key],'delta_pv_method':n['value']-o['value_per_share'],'delta_new_economic_inputs':out['cases'][key]['value']-n['value']}
    # Full cohort test for late cash, not initial FIFO only. Inject windfall CASH, no fake income.
    out['late_cash_tests']={}
    for t in [20,80,160]:
      x=m.run(shock_year=t,shock_amount=1,years=260)
      b=next(b for b in x['cohorts'][1] if b['origin']==t and b['initial']==1)
      assert b['balance']<1e-9 and b.get('last_payment',999)<=t+50
      out['late_cash_tests'][str(t)]={'full_case':x,'tagged_batch':b,'incremental_value':x['value']-m.run(years=260)['value']}
    out['convergence']={}
    for k in ['core_low','base','core_high','structural','bosch_tax_expiry','cash_release_40']:
      x=m.run(**cases[k],years=360)
      out['convergence'][k]={'pv_240':out['cases'][k]['value'],'pv_360':x['value'],'difference':x['value']-out['cases'][k]['value'],'extended':x}
      assert abs(x['value']-out['cases'][k]['value'])<1e-6
    # Finite asset realisation as separate production valuation component; no extra core credit.
    exit_cases={
    'principal_only':(10,10,0,0,.492,2,.10,100,0),
    'cost_gain_tax':(12,10,1,.25,.492,2,.10,100,0),
    'proportional_redemption':(10,10,1,.25,.492,2,.10,100,.2),
    'japanese_conditional_asset_exit':(1.3064,1.1,.15,.305,.7094,3,.11,m.SH,0)}
    out['finite_asset_scenarios']={k:m.exit_asset(*v) for k,v in exit_cases.items()}
    # Calling the SAME production functions, independent arithmetic expected.
    tests=[]
    def ck(n,a,b):
      assert abs(a-b)<1e-9,(n,a,b);tests.append({'test':n,'actual':a,'expected':b})
    ck('registered20_paid10_reserve5_profit10',m.statute(10,0,20,5)[2],1)
    ck('loss_first_profit3_oldloss2',m.statute(3,-2,20,5)[2],.1)
    ck('full_reserve_stop',m.statute(10,0,20,10)[2],0)
    ck('registered_conversion20to30',m.statute(10,0,30,10)[2],1)
    ck('voluntary_is_separate',m.statute(10,0,20,10,2)[3],2)
    z=m.parent_step(0,0,0,0,0,old_receivable=3,loan_repayment=4,capital_principal=2)
    ck('old_receivable_loan_principal_no_income',z['income'],0);ck('cash_only_no_profit_no_dividend',z['distribution'],0);ck('cash_remains',z['cash'],9)
    z=m.parent_step(0,0,10,5,0,registered=20)
    ck('new_dividend_parent_income',z['income'],5);ck('new_dividend_full_reserve_paid',z['distribution'],5)
    z=m.parent_step(0,0,0,5,0,registered=20)
    ck('new_dividend_not_exempt_reserve',z['distribution'],4.5)
    assert not m.parent_step(-1,0,0,0,0)['feasible'];tests.append({'test':'zero_dividend_no_invented_financing','passed':True})
    x=m.exit_asset(12,10,1,.25,.492,2,.10,100)
    ck('finite_exit_cost_tax_net',x['net'],10.75);ck('principal_is_not_profit',x['parent_profit'],.369)
    ck('finite_exit_pv_no_doublecount',x['pv_per_original_share'],10.75*.492/1.21/100)
    x=m.exit_asset(10,10,1,.25,.492,2,.10,100,.2)
    ck('shares_redeemed',x['remaining_shares'],80);ck('original_holder_denominator',x['holder_cash_per_original_share'],9*.492/100)
    # Zero-profit/zero-capital main loop hand case uses temporary PATHS entry, no alternative engine.
    original=m.PATHS['base'];m.PATHS['base']=([0]*5,[0]*5,[0]*5,[0]*5)
    z=m.run(finance=0,bfinance=0,parent_start=0,necessary_finance=0,j_scale=0,years=5,y=0,budget_r=0,reserve_buffer=0)
    ck('main_run_zero_cash_profit',z['value'],0)
    m.PATHS['base']=([1]*5,[0]*5,[0]*5,[0]*5)
    z=m.run(finance=0,bfinance=0,parent_start=0,necessary_finance=0,j_scale=0,years=1,y=0,budget_r=0,reserve_buffer=0,friction=0)
    ck('main_run_one_year_B_1_paid70pct',z['rows'][0]['P']['dividend'],.7*.492)
    ck('main_run_one_year_cash',z['rows'][0]['common_cash'],.3*.492)
    m.PATHS['base']=([-1,.5,1,0,0],[0]*5,[0]*5,[0]*5)
    z=m.run(finance=.984,bfinance=2,parent_start=0,necessary_finance=0,j_scale=0,years=3,y=0,budget_r=0,reserve_buffer=0,friction=0)
    # Pre-tax negative -1/.85 is intentional: no credit on negative earnings (not old NP scaled).
    ck('negative_tax_no_immediate_shield',z['rows'][0]['B']['tax'],0)
    assert z['rows'][1]['B']['dividend']==0
    m.PATHS['base']=original
    # Actual Japan routing hand cases, not a parallel identity.
    j=m.japan_state(loss=0,basis=10)
    a=m.japan_step(j,1,0,1,reorg_year=3,hold=1,term=1,friction=.1)
    ck('Japan_positive_profit_not_cash_remittance',a['common_dividend_received'],0)
    ck('Japan_retained_cash_exists',a['cash'],1)
    a=m.japan_step(j,0,0,2,reorg_year=3,hold=1,term=1,friction=.1)
    ck('Japan_cash_not_paid_before_batch_due',a['common_dividend_received'],0)
    a=m.japan_step(j,0,0,3,reorg_year=3,hold=1,term=1,friction=.1)
    ck('Japan_year3_old_cohort_dividend_after_friction',a['common_dividend_received'],1*.7094*.9)
    j=m.japan_state(loss=1,basis=1)
    a=m.japan_step(j,1,0,1,reorg_year=2,hold=0,term=1,friction=0)
    ck('Japan_loss_covered_no_false_profit_capacity',a['profit_budget'],0)
    a=m.japan_step(j,0,0,2,reorg_year=2,hold=0,term=1,friction=0)
    ck('Japan_capital_route_not_new_profit',a['common_capital_pnl'],0)
    assert a['common_capital_principal']>0 and a['capital_conversion']>0
    j=m.japan_state(loss=0,basis=0)
    a=m.japan_step(j,-1,0,1,reorg_year=None)
    ck('Japan_negative_cash_support_once',a['common_support'],.7094)
    ck('Japan_loss_no_negative_cash',a['cash'],0)
    ck('disposal_loss_not_clipped',m.exit_asset(10,10,1,.25,.492,2,.10,100)['parent_profit'],-.492)
    out['actual_function_tests']=tests
    # Auxiliary earnings power: substitute 9/12x operating normal profit for full operating DCF.
    cf=[.492*(p-i)+q-j for p,q,i,j in zip(*m.PATHS['base'])]
    np5=.492*2.7+.8
    g=.015;r=.1;op=sum(c/(1+r)**(i+1) for i,c in enumerate(cf))+np5*(1+g)*(1-g/.14)/(r-g)/(1+r)**5
    aux=[(sum(c/(1+r)**(i+1) for i,c in enumerate(cf))+np5*pe/(1+r)**5-op)/m.SH+out['cases']['base']['value'] for pe in [9,12]]
    out['auxiliary']={'operating_dcf':op,'np5':np5,'pe_range':[9,12],'value_per_share':aux,'financial_and_distribution_adjustments':'same as base; replace operating continuation only'}
    summary={k:{'value':v['value'],'tv5':v['tv5'],'d5':v['d5'],'tv_pv_share':v['tv_pv_share'],'required_historical_capacity':v['required_opening_capacity'],'initial_batch_final_payment':[b[0].get('last_payment') for b in v['cohorts']]} for k,v in out['cases'].items()}
    summary['auxiliary']=out['auxiliary'];summary['actual_function_tests']=tests
    
    assert m.exit_asset(10,10,1,.25,.492,2,.10,100)['parent_profit']==-.492
    return out

def canonical_bytes(o):
 return json.dumps(o,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode('utf-8')

def pack_output(o):
 def summary(x):
  if isinstance(x,dict):return {k:summary(v) for k,v in x.items() if k not in ('rows','tail_rows','cohorts','japan_cohorts')}
  if isinstance(x,list):return [summary(v) for v in x]
  return x
 raw=canonical_bytes(o);p=summary(o)
 p['_complete_output']={'encoding':'gzip-mtime0-base64-json-utf8','expanded_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'schema':'Complete all scenarios including Japan-routing sensitivities, all annual entity/cash/cohort records, old/new same-economy comparisons, future cash probes, 360-year numerical convergence, actual-function tests and auxiliary economics. Outer object is readable summary excluding rows/cohorts. Monetary units CNY billion except CNY per share.','expand_command':'python 2026-Q3.py --expand 2026-Q3-output.json expanded.json','data':base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode('ascii')}
 assert expand_output(p)==o
 return p

def expand_output(o):
 a=o['_complete_output'];raw=gzip.decompress(base64.b64decode(a['data']))
 assert len(raw)==a['expanded_bytes'] and hashlib.sha256(raw).hexdigest()==a['sha256']
 return json.loads(raw)

if __name__=='__main__':
 if len(sys.argv)==4 and sys.argv[1]=='--expand':
  src=json.loads(Path(sys.argv[2]).read_text());Path(sys.argv[3]).write_bytes(canonical_bytes(expand_output(src)))
 else:
  o=make();Path(__file__).with_name('2026-Q3-output.json').write_bytes(canonical_bytes(pack_output(o)));print({k:o['cases'][k]['value'] for k in ['core_low','core_high','base']})

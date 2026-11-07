#!/usr/bin/env python3
"""中国巨石: ownership cash waterfall. Python stdlib only; CNY billion.
The integration horizon is a convergence device, NOT a literal forecast.
Only P is a legal distribution budget; ALL other rows are economic source budgets, not standalone legal accounts.
No spot price, IRR, mechanical cash principal add-back or perpetual profit multiple.
"""
import json, math, copy, gzip, base64, hashlib, sys
from pathlib import Path
SHARES=4.003136728
CUTOFF='2026-10-26T09:00:00+00:00'
# Leaf-to-root order: (name, owner, ownership, profit weight, capex weight,
# cash, external debt, finite additional facility, registered capital, intercompany loan to P)
NODES=[
 ('JJ','G',1.,.16,.16,.20,.60,.25,1.291,.383241303),
 ('CD','G',1.,.10,.13,.15,.80,1.20,1.5,0.),
 ('HA','G',1.,.20,.34,.25,2.30,3.00,1.99988347,1.204223357),
 ('EG','G',.7501,.08,.07,.25,.80,.20,None,0.),
 ('US','P',.70,.04,.04,.10,.15,.15,None,0.),
 ('W','Z',.80,.01,.01,.059480663,.128548324,.10,.30,.361010719),
 ('L','Z',1.,0.,0.,.03,0.,1.50,.30,0.),
 ('Z','P',1.,0.,0.,0.,0.,.05,.60,0.),
 ('G','P',1.,.40,.25,.42,3.15,.85,5.255313048,1.317516638),
 ('P',None,1.,.01,0.,.80,6.90,1.20,SHARES,0.)]
NAMES={'JJ':'巨石九江（含不重大原料子公司预算）','CD':'巨石成都','HA':'巨石淮安','EG':'巨石埃及','US':'巨石美国股份','W':'巨石新能源淮安','L':'巨石绿色能源涟水','Z':'浙江巨石新能源','G':'巨石集团本部（含不重大销售子公司预算）','P':'中国巨石股份母公司'}
SCENARIOS={
 'base':dict(description='核心路径：电子布价差回落，新增产能有序消化；第1年起各经营主体', rev_factor=1., margin_shift=0., growth_factor=1., capex_factor=1., rate=.03, lag=.15, wc_shock=0., start=1),
 'cycle':dict(description='周期弱：第1-3年全集团需求和价差下行，第4年起恢复原竞争力；先削分红而非减必要维护', rev_factor=1.,margin_shift=0.,growth_factor=1.,capex_factor=1.,rate=.04,lag=.25,wc_shock=.6,start=1),
 'structural':dict(description='结构不利：第2年起电子产品溢价永久收窄，资本效率下降；全部经营法人',rev_factor=.90,margin_shift=-.075,growth_factor=1.,capex_factor=1.08,rate=.045,lag=.20,wc_shock=.3,start=2),
 'upside':dict(description='较强：第2年起薄布认证与高模升级兑现，收入+8%、利润率+2点，但资本开支+12%',rev_factor=1.08,margin_shift=.02,growth_factor=1.1,capex_factor=1.12,rate=.03,lag=.15,wc_shock=0.,start=2),
 'margin_minus_2pp':dict(description='单因素诊断：第2年起经营毛利/利润率永久少2点；经营、法定利润、融资分配全链重算',rev_factor=1.,margin_shift=-.02,growth_factor=1.,capex_factor=1.,rate=.03,lag=.15,wc_shock=0.,start=2),
 'parent_settlement_delay':dict(description='第1年母公司客户回款延后10亿元，第3年收回；同额形成母公司应收款，不新生利润；子股利到账延期至40%',rev_factor=1.,margin_shift=0.,growth_factor=1.,capex_factor=1.,rate=.03,lag=.40,wc_shock=1.,start=1),
 'capex_plus_20pct':dict(description='第1年起同收入经营路径下所有经营主体资本开支永久增20%，诊断资本强度',rev_factor=1.,margin_shift=0.,growth_factor=1.,capex_factor=1.20,rate=.03,lag=.15,wc_shock=0.,start=1),
 'unfundable':dict(description='失败测试：第1年全集团额外不可延付建设款200亿元，零分红仍不能融资，不给有效估值',rev_factor=1.,margin_shift=0.,growth_factor=1.,capex_factor=1.,rate=.04,lag=.15,wc_shock=0.,start=1)
}

for label,amount in [('opening_dividend_receivable_zero',0.),('opening_dividend_receivable_full',1.3)]:
    SCENARIOS[label]=dict(SCENARIOS['base'],opening_old_dividend=amount,description='第1年期初旧应收股利边界；母子应收应付同额改变，收款绝不增加法定利润')

for label,amount in [('parent_retained_unreserved',.13953489235),('parent_retained_plus_Q3_1bn',1.00385265745)]:
    SCENARIOS[label]=dict(SCENARIOS['base'],parent_retained=amount,description='第1年母公司期初法定留存诊断，额外留存不是额外现金')

def parameters(y,s):
    if y>=6 and s.get('mature_price_normalization'):
        # Independent economic cross-check: Y5 quantities, lower selling prices.
        # Cloth 1.65bn m*(6.7-6.0) + coarse 4.1mt*(4150-4100)=1.36bn.
        # Fixed/operating costs and depreciation do not vanish with a price fall.
        scale=1.015**(y-5)
        rev=(28.4-1.36)*scale; ebit=(7.1-1.36)*scale
        dep=3.4*scale
        # Expansion capital follows physical volume at Y5 replacement prices.
        cap=dep+1.6*28.4*.015*1.015**(y-6)
        return dict(revenue=rev,ebit=ebit,ebit_margin=ebit/rev,depreciation=dep,capex=cap)
    revs=[24.81,24.565,25.67,27.05,28.40]
    margins=[.29,.26,.25,.25,.25]
    caps=[7.5,6.5,5.0,4.2,4.3]
    if y<=5: rev=revs[y-1]; margin=margins[y-1]; dep=2.8+.15*(y-1); cap=caps[y-1]
    else:
        rev=28.4
        for k in range(6,y+1): rev*=1+([.04,.035,.03,.025,.02][k-6] if k<=10 else .015)
        margin=.25-min(y-5,5)*.004
        dep=3.4*rev/28.4
        prev=rev/(1+([.04,.035,.03,.025,.02][y-6] if y<=10 else .015))
        cap=dep+1.6*(rev-prev)
    if y>=s['start']:
        rev*=s['rev_factor']; margin+=s['margin_shift']; cap*=s['capex_factor']
        if y>5: rev*=s['growth_factor']**min((y-5)/5,1)  # bounded level effect; same long-run nominal g
    if s is SCENARIOS['cycle'] and y<=3:
        rev*=[.88,.92,.96][y-1]; margin-=[.09,.07,.04][y-1]
    if s is SCENARIOS['unfundable'] and y==1: cap+=20
    return {'revenue':rev,'ebit':rev*margin,'ebit_margin':margin,'depreciation':dep,'capex':cap}

def node_budget(y,name,pw,cw,op,s):
    # Known construction cash: new electronic lines, Chengdu, wind and cold repair.
    grids={1:{'JJ':.6,'CD':1.2,'HA':3.,'EG':.3,'US':.2,'W':.1,'L':.9,'G':1.2,'P':0.,'Z':0.},
           2:{'JJ':.55,'CD':1.,'HA':2.4,'EG':.3,'US':.2,'W':.1,'L':.82449,'G':1.12551,'P':0.,'Z':0.},
           3:{'JJ':.55,'CD':.8,'HA':1.65,'EG':.3,'US':.2,'W':.1,'L':.1,'G':1.3,'P':0.,'Z':0.}}
    lprofit=([.02,.12,.22,.24,.25][y-1] if y<=5 else .25*op['revenue']/28.4)
    ldep=([.01,.05,.09,.10,.10][y-1] if y<=5 else .10*op['revenue']/28.4)
    cap=grids[y][name]*(op['capex']/(7.5,6.5,5.)[y-1]) if y<=3 else op['capex']*(.025 if name=='L' else cw-(.025 if name=='G' else 0))
    w_adjust=.13*op['revenue']/24.-op['ebit']*.01
    ebit=op['ebit']*pw+(w_adjust if name=='W' else -w_adjust if name=='G' else 0.)+(lprofit if name=='L' else -lprofit if name=='G' else 0.)
    dep=op['depreciation']*cw+(ldep if name=='L' else -ldep if name=='G' else 0.)
    inject=.3 if y==1 else .2 if y==2 else 0.
    ei=inject if name in ('L','Z') else 0.; eo=inject if name in ('P','Z') else 0.
    return ebit,dep,cap,ei,eo

def legal_step(retained,reserve,capital,profit):
    after=retained+profit
    # Loss carryforward first. Existing negative retained cannot be reset annually.
    base=max(0.,profit+min(0.,retained))
    addition=min(max(0.,capital*.5-reserve),base*.1)
    return after-addition,reserve+addition,addition


# Child rows are economic source budgets. Registered capital shown in NODES is metadata
# ONLY; no child statutory computation uses it. Existing reserve/loss unknown != zero.
# Governance retention 10% held three years represents future capacity availability,
# not a local-law reserve. Foreign taxes are explicit scenario estimates.
SCENARIOS['long_upstream_delay']=dict(SCENARIOS['base'],hold_years=5,hold_fraction=.25,lag=.4,description='All source budgets:25% earnings capacity postponed five years;40% declared payment lag')
SCENARIOS['reserve_unknown']=dict(SCENARIOS['base'],parent_reserve=0.,description='Parent statutory portion unverified boundary: none of reported surplus reserve qualifies for cap')
SCENARIOS['foreign_friction']=dict(SCENARIOS['base'],foreign_tax=.15,hold_years=5,description='Foreign withholding budget15%; all source capacity delayed5 years')
SCENARIOS['same_year_parent_loss']=dict(SCENARIOS['base'],parent_loss=1.,description='Y2 parent real cash loss1bn reduces same-year lawful profit and cash')
SCENARIOS['capital_return_fee_shortfall']=dict(SCENARIOS['base'],mandatory_fee=30.,description='Y1 compulsory fees30bn: no dividend and finite debt cannot fund; explicit failure')
SCENARIOS['parent_retained_unreserved']['parent_reserve']=1.33955207603

def node_step(a,p,inc_decl,inc_cash,loan_income,loan_repay_received,params):
    """Production waterfall. p['is_parent'] distinguishes legal from economic capacity."""
    old=copy.deepcopy(a); parent=p.get('is_parent',False)
    if p.get('capital_receipt',0.) > a.get('investment_cost',0.)+1e-9:
        return dict(feasible=False,shortfall=p['capital_receipt']-a.get('investment_cost',0.),reason='capital receipt exceeds verified/budget cost basis; disposal gain requires separate model')
    int_exp=a['debt']*params['rate']; loan_int=a['loan']*.025
    financial_interest=a['cash']*params.get('deposit_rate',.012)
    taxable=p['ebit']+financial_interest+loan_income-int_exp-loan_int
    tax=max(0.,taxable)*params.get('tax',.18)
    fees=p.get('mandatory_fee',0.)
    own_profit=taxable-tax+p.get('affiliate_income',0.)-p.get('real_loss',0.)-fees
    profit=own_profit+inc_decl
    capital=a['capital']+p.get('registration_delta',0.) # never automatic upon paid injection
    held=[(t-1,v) for t,v in a['held'] if t>1]
    reserve=a['reserve']; add=0.
    if parent:
        available,reserve,add=legal_step(a['retained'],reserve,capital,profit)
        room=max(0.,available)
    else:
        available=a['retained']+profit
        # Losses reduce the SAME year's capacity, no pooling profits against another row.
        h=params.get('hold_fraction',.1)*max(0.,profit+min(0.,a['retained']))
        held.append((params.get('hold_years',3),h))
        room=max(0.,available-sum(v for _,v in held))
    pre=(a['cash']+own_profit+p['dep']-p['capex']-p['dnwc']+inc_cash+
         loan_repay_received-a['payable']+p.get('equity_in',0.)-p.get('equity_out',0.)+
         p.get('capital_receipt',0.))
    draw=min(max(0.,p['minimum']-pre),max(0.,a['limit']-a['debt']))
    pre+=draw
    if pre+1e-10<p['minimum']:
        return dict(feasible=False,shortfall=p['minimum']-pre,cash_before_funding=pre-draw,draw=draw,profit=profit,mandatory_fee=fees)
    loanrepay=min(a['loan'],max(0.,pre-p['minimum'])*.1); pre-=loanrepay
    repay=min(a['debt']+draw,max(0.,pre-p['minimum'])*params.get('repay_fraction',.25)); pre-=repay
    normal=min(room,max(0.,pre-p['minimum']),max(0.,p['target']))
    sweep=min(max(0.,room-normal),max(0.,pre-p['minimum']-normal)) if params['sweep'] else 0.
    declare=normal+sweep
    paid_new=declare*(1-params['lag']); payable=declare-paid_new
    cash=pre-paid_new
    # Only genuinely surplus financial cash, AFTER creditors and dividend reservation.
    # Parent finite registered-capital reduction budget is conditional corporate action.
    # Source capital recovery only for separately tracked new excess contributed basis.
    surplus=max(0.,cash-p['minimum']-payable)
    excess_basis=a.get('excess_basis',0.)+p.get('excess_basis_in',0.)
    age=a.get('surplus_age',0)+1 if surplus>1e-9 else 0
    capital_return=0.; return_fee=0.; shares=a['shares']
    if params.get('capital_release',True) and age>=3 and surplus>0 and (parent or excess_basis>0):
        # Do not return unneeded cash merely due to ordinary policy deferral. Only
        # profit-capacity blocked cash or earmarked contributed financial principal.
        blocked=max(0.,surplus-max(0.,available-declare)) if parent else min(surplus,excess_basis)
        basis=capital*.95 if parent else excess_basis
        capital_return=min(blocked,basis)/(1+params.get('return_fee_rate',.02))
        return_fee=capital_return*params.get('return_fee_rate',.02)
        # Real fee/loss reduces current legal retained, and never paid by clipping shortfall.
        if cash-capital_return-return_fee < p['minimum']+payable-1e-9:
            return dict(feasible=False,shortfall=p['minimum']+payable-(cash-capital_return-return_fee),profit=profit)
        cash-=capital_return+return_fee
        if parent:
            available,reserve,add=legal_step(a['retained'],a['reserve'],a['capital']+p.get('registration_delta',0.),profit-return_fee)
        else:
            available-=return_fee
            held[-1]=(held[-1][0],params.get('hold_fraction',.1)*max(0.,profit-return_fee+min(0.,a['retained'])))
        if parent and capital_return:
            shares*=1-capital_return/capital; capital-=capital_return
        if not parent: excess_basis-=capital_return+return_fee
    # If fee creates unlawful already-declared dividends, recompute ordinary payment
    # before execution (the fee must not be ignored by max(0)).
    if parent and declare>max(0.,available)+1e-10:
        reduction=declare-max(0.,available); declare-=reduction
        cash+=reduction*(1-params['lag']); payable=declare*params['lag']; paid_new=declare-payable
        normal=min(normal,declare); sweep=declare-normal
    end=dict(dividend_receivable=a['dividend_receivable']+inc_decl-inc_cash,
             cash=cash,debt=a['debt']+draw-repay,limit=a['limit'],capital=capital,
             reserve=reserve,retained=available-declare,loan=a['loan']-loanrepay,
             payable=payable,held=held,surplus_age=age,shares=shares,excess_basis=excess_basis,
             investment_cost=a.get('investment_cost',0.)+p.get('equity_out',0.)-p.get('capital_receipt',0.))
    assert end['dividend_receivable']>=-1e-7
    assert cash>=p['minimum']+payable-1e-8
    expected=old['cash']+own_profit+p['dep']-p['capex']-p['dnwc']+inc_cash+loan_repay_received-old['payable']+p.get('equity_in',0.)-p.get('equity_out',0.)+p.get('capital_receipt',0.)+draw-loanrepay-repay-paid_new-capital_return-return_fee
    assert math.isclose(cash,expected,abs_tol=1e-7)
    return dict(feasible=True,opening=old,own_profit=own_profit-return_fee,
       capacity_profit=profit-return_fee,child_declarations=inc_decl,child_receipts=inc_cash,
       capital_receipts=p.get('capital_receipt',0.),interest_expense=int_exp,loan_interest_paid=loan_int,
       loan_interest_received=loan_income,loan_principal_received=loan_repay_received,
       financial_interest=financial_interest,tax=tax,reserve_addition=add,
       legal_or_economic_capacity_before_distribution=available,draw=draw,
       external_principal_repaid=repay,shareholder_loan_repaid=loanrepay,
       old_dividend_paid=old['payable'],ordinary_declared=normal,excess_declared=sweep,
       new_dividend_declared=declare,new_dividend_paid=paid_new,total_dividend_paid=old['payable']+paid_new,
       capital_return=capital_return,capital_return_fee=return_fee,
       original_holder_cash=old['payable']+paid_new+capital_return,end=end,**p)

def initial():
    a={}
    for name,owner,share,pw,cw,cash,debt,head,capital,loan in NODES:
        a[name]=dict(dividend_receivable=.65 if name=='P' else 0.,cash=cash,debt=debt,
           limit=debt+head,capital=SHARES if name=='P' else 0.,
           reserve=1.33955207603 if name=='P' else 0.,
           retained=.13953489229 if name=='P' else 0.,loan=loan,
           payable=.65 if name=='G' else 0.,held=[],surplus_age=0,shares=SHARES if name=='P' else 1.,excess_basis=0.,investment_cost=10.46536040559 if name=='P' else 0.)
    return a

def run(s,years=240,start_state=None,start_y=1,prior_revenue=24.,keep=True):
    a=copy.deepcopy(start_state) if start_state else initial()
    if not start_state:
        if 'opening_old_dividend' in s:
            a['G']['payable']=s['opening_old_dividend']; a['P']['dividend_receivable']=s['opening_old_dividend']
        for key in ['parent_retained','parent_reserve']:
            if key in s:a['P'][key.split('_')[1]]=s[key]
    trace=[]; divs=[]; prev=prior_revenue; invested=44.; nwc=5.6
    for y in range(start_y,years+1):
        op=parameters(y,s); rev=op['revenue']; dnwc=.2*(rev-prev)+(1. if y==1 else -.4 if y==2 else -.3 if y==3 else 0.)
        shock=s['wc_shock']*((y==s['start'])-(y==s['start']+2))
        incomingD={n[0]:0. for n in NODES}; incomingC=incomingD.copy(); incomingK=incomingD.copy()
        interest_loans=sum(x['loan']*.025 for x in a.values()); loan_receipts=0.
        owner_profit=minority_profit=minority_paid=withholding=payments=0.; rows={}; oldsum=sum(v['cash'] for v in a.values())
        for name,owner,share,pw,cw,_,_,_,_,_ in NODES:
            rw=.41 if name=='G' else 0. if name=='P' else pw
            minimum=(.45 if name=='P' else .02 if name in ('Z','L') else 1.35*rw)*rev/24.
            ebit,dep,cap,ei,eo=node_budget(y,name,pw,cw,op,s)
            target=1e9 if name!='P' else max(0.,owner_profit)*(.45 if y<=5 else .70 if y<=10 else 1.)
            p=dict(is_parent=name=='P',ebit=ebit,dep=dep,capex=cap,equity_in=ei,equity_out=eo,
              dnwc=dnwc*rw+(shock if name=='P' else 0.),minimum=minimum,target=target,
              affiliate_income=.10*rev/24 if name=='P' else 0.,capital_receipt=incomingK[name],
              real_loss=s.get('parent_loss',0.) if name=='P' and y==2 else 0.,
              mandatory_fee=s.get('mandatory_fee',0.) if name=='P' and y==1 else 0.)
            par=dict(rate=s['rate'] if y>=s['start'] else .03,lag=0. if name=='P' else s['lag'] if y>=s['start'] else .15,
                     sweep=y>=6,repay_fraction=.25,hold_fraction=s.get('hold_fraction',.1),hold_years=s.get('hold_years',3),
                     capital_release=s.get('capital_release',True))
            x=node_step(a[name],p,incomingD[name],incomingC[name],interest_loans if name=='P' else 0.,loan_receipts if name=='P' else 0.,par)
            rows[name]=x
            if not x['feasible']:
                return dict(feasible=False,failed_year=y,failed_node=name,shortfall=x['shortfall'],trace=trace+[dict(year=y,nodes=rows,operating=op,feasible=False)],value=None)
            a[name]=x['end']; loan_receipts+=x['shareholder_loan_repaid']
            owner_profit+=x['own_profit']*share; minority_profit+=x['own_profit']*(1-share)
            if owner:
                wt=s.get('foreign_tax',.05) if name in ('EG','US') else 0.
                incomingD[owner]+=x['new_dividend_declared']*share*(1-wt)
                incomingC[owner]+=x['total_dividend_paid']*share*(1-wt)
                incomingK[owner]+=x['capital_return']*share
                minority_paid+=(x['total_dividend_paid']+x['capital_return'])*(1-share)
                withholding+=x['total_dividend_paid']*share*wt
            else:payments=x['original_holder_cash']
        nwc+=dnwc+shock; invested+=op['capex']-op['depreciation']+dnwc+shock
        endsum=sum(v['cash'] for v in a.values()); ownsum=sum(x['own_profit'] for x in rows.values())
        draws=sum(x['draw'] for x in rows.values()); repayments=sum(x['external_principal_repaid'] for x in rows.values())
        assert math.isclose(endsum,oldsum+ownsum+op['depreciation']-op['capex']-dnwc-shock+draws-repayments-payments-minority_paid-withholding,rel_tol=1e-8,abs_tol=1e-7),(y,endsum)
        trace.append(dict(year=y,calendar_label=2026+y,feasible=True,operating=op,delta_nwc=dnwc+shock,nwc=nwc,
          invested_capital=invested,owner_profit=owner_profit,minority_profit=minority_profit,minority_cash_paid=minority_paid,
          foreign_withholding=withholding,distribution=payments,distribution_per_share=payments/SHARES,
          surviving_shares_billion=a['P']['shares'],cash_per_surviving_share=payments/a['P']['shares'],
          group_cash=endsum,external_debt=sum(v['debt'] for v in a.values()),new_external_financing=draws,
          external_debt_repayment=repayments,nodes=rows))
        divs.append(payments/SHARES);prev=rev
    return dict(feasible=True,trace=trace,distributions=divs,closing_state=a)

def pv(d,r,start=0):return sum(v/(1+r)**(i+1) for i,v in enumerate(d[start:]))
def valuation(x):
    if not x['feasible']:return None
    d=x['distributions'];out={}
    for tag,k in [('low',.1025),('high',.09)]:
        out['value_'+tag]=pv(d,k);out['terminal_y5_'+tag]=pv(d,k,5)
        out['tv5_pv_fraction_'+tag]=pv(d,k,5)/(1+k)**5/pv(d,k)
    out['distribution_first5']=d[:5]
    return out

def independently_rebuild(which,years=240):
    """Literal re-entry and ledger reconstruction; no production functions/data read."""
    specs=[('JJ','G',1,.16,.16,.2,.6,.85,.383241303),('CD','G',1,.10,.13,.15,.8,2,0),
      ('HA','G',1,.20,.34,.25,2.3,5.3,1.204223357),('EG','G',.7501,.08,.07,.25,.8,1,0),
      ('US','P',.70,.04,.04,.1,.15,.3,0),('W','Z',.80,.01,.01,.059480663,.128548324,.228548324,.361010719),
      ('L','Z',1,0,0,.03,0,1.5,0),('Z','P',1,0,0,0,0,.05,0),('G','P',1,.4,.25,.42,3.15,4,1.317516638),
      ('P',None,1,.01,0,.8,6.9,8.1,0)]
    # Independent scenario literals, deliberately not taken from SCENARIOS.
    cases={'base':(1,1.,0.,1.,1.,.03,.15,0.,.1,3,.05),
      'margin_minus_2pp':(2,1.,-.02,1.,1.,.03,.15,0.,.1,3,.05),
      'long_upstream_delay':(1,1.,0.,1.,1.,.03,.4,0.,.25,5,.05),
      'structural':(2,.9,-.075,1.,1.08,.045,.2,.3,.1,3,.05),
      'cycle':(1,1.,0.,1.,1.,.04,.25,.6,.1,3,.05),
      'upside':(2,1.08,.02,1.1,1.12,.03,.15,0.,.1,3,.05),
      'capex_plus_20pct':(1,1.,0.,1.,1.2,.03,.15,0.,.1,3,.05),
      'foreign_friction':(1,1.,0.,1.,1.,.03,.15,0.,.1,5,.15)}
    start,rf,ms,gf,cf,rate,lag,wc,hf,hy,wt=cases[which]
    z={n:dict(cash=c,debt=d,limit=l,loan=b,capital=4.003136728 if n=='P' else 0.,
      reserve=1.33955207603 if n=='P' else 0.,retained=.13953489229 if n=='P' else 0.,
      payable=.65 if n=='G' else 0.,dividend_receivable=.65 if n=='P' else 0.,held=[],surplus_age=0,
      shares=4.003136728 if n=='P' else 1.,excess_basis=0.,investment_cost=10.46536040559 if n=='P' else 0.)
      for n,u,f,p,cw,c,d,l,b in specs}
    records=[];distributions=[];last=24.
    for t in range(1,years+1):
        if t<=5:
            sales=(24.81,24.565,25.67,27.05,28.4)[t-1];mar=(.29,.26,.25,.25,.25)[t-1]
            depreciation=2.8+.15*(t-1);spend=(7.5,6.5,5.,4.2,4.3)[t-1]
        else:
            changes=(1.04,1.035,1.03,1.025,1.02)
            sales=28.4*math.prod(changes[:min(5,t-5)])*1.015**max(0,t-10)
            mar=.25-.004*min(5,t-5);depreciation=3.4*sales/28.4
            spend=depreciation+1.6*sales*(1-1/(changes[t-6] if t<=10 else 1.015))
        if t>=start:
            sales*=rf;mar+=ms;spend*=cf
            if t>5:sales*=gf**min(1,(t-5)/5)
        if which=='cycle' and t<=3:sales*=(.88,.92,.96)[t-1];mar-=(.09,.07,.04)[t-1]
        networking=(sales-last)/5+({1:1.,2:-.4,3:-.3}.get(t,0.));shock=wc*((t==start)-(t==start+2))
        accrued={n:0. for n in z};received=accrued.copy();capital_cash=accrued.copy()
        interinterest=sum(v['loan'] for v in z.values())/40;loanreturn=0.;earn=0.;row={};cashout=0.
        for idx,(n,u,share,pw,cw,*_) in enumerate(specs):
            old=z[n];rw=.41 if n=='G' else 0 if n=='P' else pw
            floor=(.45 if n=='P' else .02 if n in ('L','Z') else 1.35*rw)*sales/24
            grid={1:(.6,1.2,3.,.3,.2,.1,.9,0,1.2,0),2:(.55,1.,2.4,.3,.2,.1,.82449,0,1.12551,0),3:(.55,.8,1.65,.3,.2,.1,.1,0,1.3,0)}
            capitalspend=grid[t][idx]*spend/(7.5,6.5,5)[t-1] if t<4 else spend*(.025 if n=='L' else cw-(.025 if n=='G' else 0))
            wind=.13*sales/24-sales*mar*.01
            lp=(.02,.12,.22,.24,.25)[t-1] if t<6 else .25*sales/28.4
            ld=(.01,.05,.09,.1,.1)[t-1] if t<6 else .1*sales/28.4
            eb=sales*mar*pw+(wind if n=='W' else -wind if n=='G' else 0)+(lp if n=='L' else -lp if n=='G' else 0)
            dd=depreciation*cw+(ld if n=='L' else -ld if n=='G' else 0)
            pretax=eb+old['cash']*.012+(interinterest if n=='P' else 0)-old['debt']*(rate if t>=start else .03)-old['loan']*.025
            net=pretax-.18*max(pretax,0)+(.1*sales/24 if n=='P' else 0)
            capacity=net+accrued[n]+old['retained'];held=[(age-1,v) for age,v in old['held'] if age>1]
            if n=='P':
                provision=min(max(0.,old['capital']/2-old['reserve']),max(0.,net+accrued[n]+min(old['retained'],0))/10)
                capacity-=provision;usable=max(0,capacity)
            else:
                provision=0.;held.append((hy,hf*max(0,net+accrued[n]+min(old['retained'],0))))
                usable=max(0,capacity-sum(v for age,v in held))
            transfer=.3 if t==1 else .2 if t==2 else 0
            add=transfer if n in ('L','Z') else 0;deduct=transfer if n in ('P','Z') else 0
            money=old['cash']+net+dd-capitalspend-networking*rw-(shock if n=='P' else 0)+received[n]+(loanreturn if n=='P' else 0)-old['payable']+add-deduct+capital_cash[n]
            borrowing=min(max(0,floor-money),max(0,old['limit']-old['debt']));money+=borrowing
            if money<floor-1e-10:return dict(feasible=False,failed_year=t,failed_node=n)
            lpay=min(old['loan'],.1*max(0,money-floor));money-=lpay
            amort=min(old['debt']+borrowing,.25*max(0,money-floor));money-=amort
            target=max(0,earn)*(.45 if t<=5 else .7 if t<=10 else 1) if n=='P' else 1e9
            regular=min(usable,max(0,money-floor),target);extra=min(max(0,usable-regular),max(0,money-floor-regular)) if t>=6 else 0
            declared=regular+extra;deferred=0 if n=='P' else lag if t>=start else .15
            newpaid=declared*(1-deferred);payable=declared*deferred;money-=newpaid
            excess=max(0,money-floor-payable);age=old['surplus_age']+1 if excess>1e-9 else 0
            reduction=0.;fee=0.;capital=old['capital'];shares=old['shares'];basis=old['excess_basis']
            if age>=3 and excess>0 and (n=='P' or basis>0):
                blocked=max(0,excess-max(0,capacity-declared)) if n=='P' else min(excess,basis)
                reduction=min(blocked,capital*.95 if n=='P' else basis)/1.02;fee=.02*reduction
                money-=reduction+fee;capacity-=fee
                if n=='P' and reduction:shares*=1-reduction/capital;capital-=reduction
                if n!='P':basis-=reduction+fee
            if n=='P' and declared>max(0,capacity)+1e-10:
                undo=declared-max(0,capacity);declared-=undo;money+=undo*(1-deferred);payable=declared*deferred;newpaid=declared-payable
            z[n]=dict(cash=money,debt=old['debt']+borrowing-amort,limit=old['limit'],loan=old['loan']-lpay,
              capital=capital,reserve=old['reserve']+provision,retained=capacity-declared,
              payable=payable,dividend_receivable=old['dividend_receivable']+accrued[n]-received[n],held=held,
              surplus_age=age,shares=shares,excess_basis=basis,investment_cost=old['investment_cost']+deduct-capital_cash[n])
            earn+=(net-fee)*share;loanreturn+=lpay
            if u:
                factor=share*(1-wt if n in ('EG','US') else 1)
                accrued[u]+=declared*factor;received[u]+=(old['payable']+newpaid)*factor;capital_cash[u]+=reduction*share
            else:cashout=(old['payable']+newpaid+reduction)/4.003136728
            row[n]=copy.deepcopy(z[n])
        records.append(dict(year=t,states=row,distribution_per_share=cashout));distributions.append(cashout);last=sales
    return dict(feasible=True,trace=records,distributions=distributions,
      value_low=sum(v/1.1025**(t+1) for t,v in enumerate(distributions)),
      value_high=sum(v/1.09**(t+1) for t,v in enumerate(distributions)),
      terminal_y5_low=sum(v/1.1025**(t+1) for t,v in enumerate(distributions[5:])),
      terminal_y5_high=sum(v/1.09**(t+1) for t,v in enumerate(distributions[5:])))

def tests():
    a=dict(cash=1.,debt=0.,limit=0.,capital=20.,reserve=5.,retained=0.,loan=0.,payable=0.,
      dividend_receivable=0.,held=[],surplus_age=0,shares=20.,excess_basis=0.,investment_cost=1.)
    p=dict(is_parent=True,ebit=10.,dep=0.,capex=0.,dnwc=0.,minimum=0.,target=100.,affiliate_income=0.)
    q=dict(rate=0.,lag=0.,sweep=True,tax=0.,repay_fraction=0.,deposit_rate=0.,capital_release=False)
    x=node_step(a,p,0.,0.,0.,0.,q)
    assert x['reserve_addition']==1. and x['new_dividend_paid']==9. # registered20, paid10 irrelevant
    l=node_step(dict(a,retained=-3.),p,0.,0.,0.,0.,q)
    assert abs(l['reserve_addition']-.7)<1e-12 and abs(l['new_dividend_paid']-6.3)<1e-12
    full=node_step(dict(a,reserve=10.),p,0.,0.,0.,0.,q);assert full['reserve_addition']==0.
    registered=node_step(dict(a,reserve=10.),dict(p,registration_delta=10.),0.,0.,0.,0.,q)
    paid=node_step(dict(a,reserve=10.),dict(p,equity_in=10.),0.,0.,0.,0.,q)
    assert registered['reserve_addition']==1. and paid['reserve_addition']==0.
    old=node_step(dict(a,dividend_receivable=2.),p,0.,2.,0.,0.,q)
    assert old['capacity_profit']==x['capacity_profit'] and old['end']['cash']==x['end']['cash']+2.
    loss=node_step(a,dict(p,real_loss=12.),0.,0.,0.,0.,q)
    assert not loss['feasible'] and loss['shortfall']==1.
    neg=node_step(dict(a,cash=20.),dict(p,real_loss=12.),0.,0.,0.,0.,q)
    assert neg['new_dividend_paid']==0. and neg['end']['retained']==-2.
    fee2=node_step(a,dict(p,mandatory_fee=2.),0.,0.,0.,0.,q)
    assert fee2['capacity_profit']==8. and abs(fee2['reserve_addition']-.8)<1e-12 and abs(fee2['new_dividend_paid']-7.2)<1e-12
    fee=node_step(a,dict(p,mandatory_fee=12.),0.,0.,0.,0.,q)
    assert not fee['feasible'] and fee['shortfall']==1.
    failure=node_step(a,dict(p,capex=20.),0.,0.,0.,0.,q)
    assert not failure['feasible'] and failure['shortfall']==9.
    # Financial principal: no earnings, no liquidation of the operating business.
    z=dict(a,cash=1.,reserve=10.);zero=dict(p,ebit=0.)
    for t in range(3):
        cr=node_step(z,zero,0.,0.,0.,0.,dict(q,capital_release=True));z=cr['end']
    assert abs(cr['capital_return']-1/1.02)<1e-12
    assert abs(cr['capital_return_fee']-.02/1.02)<1e-12
    assert abs(z['cash'])<1e-12 and abs(z['shares']-(20-1/1.02))<1e-12
    assert cr['new_dividend_paid']==0. and abs(z['retained']+.02/1.02)<1e-12
    # Source recovery with 70% economic ownership: only original common owners'70% travels.
    zz=dict(a,cash=1.,capital=0.,reserve=0.,excess_basis=1.,surplus_age=2)
    source=node_step(zz,dict(zero,is_parent=False),0.,0.,0.,0.,dict(q,capital_release=True))
    received=source['capital_return']*.7
    parent=node_step(dict(a,cash=0.,investment_cost=.7),zero,0.,0.,0.,0.,dict(q,capital_release=False))
    parent2=node_step(dict(a,cash=0.,investment_cost=.7),dict(zero,capital_receipt=received),0.,0.,0.,0.,q)
    assert parent2['capacity_profit']==parent['capacity_profit']==0.
    assert abs(parent2['end']['investment_cost']-(.7-received))<1e-12
    assert abs(received+source['capital_return']*.3+source['capital_return_fee']-1.)<1e-12
    # Any future year: incremental free financial cash is released promptly; actual chain.
    b=run(SCENARIOS['base'],140);late=[]
    for year in [7,40,80,120]:
        row=b['trace'][year-1]['nodes']['P'];state=copy.deepcopy(row['opening']);state['cash']+=.1
        args={k:row[k] for k in ['is_parent','ebit','dep','capex','equity_in','equity_out','dnwc','minimum','target','affiliate_income','capital_receipt','real_loss','mandatory_fee']}
        params=dict(rate=.03,lag=0.,sweep=True,repay_fraction=.25,hold_fraction=.1,hold_years=3)
        modified=node_step(state,args,row['child_declarations'],row['child_receipts'],row['loan_interest_received'],row['loan_principal_received'],params)
        assert modified['feasible']
        # Incremental cash either immediately reaches holders or repays real debt;
        # residual is interest/timing reserve, checked by subsequent cash-floor state.
        benefit=modified['original_holder_cash']-row['original_holder_cash']+modified['external_principal_repaid']-row['external_principal_repaid']
        assert benefit>.099
        late.append(dict(year=year,incremental_cash=.1,immediate_holder_or_creditor_benefit=benefit))
    return dict(registered_not_paid=True,loss_first=True,full_reserve=True,registration_not_payment=True,
      old_receipt_not_profit=True,same_year_loss_and_fee=True,zero_dividend_funding_failure=True,
      finite_capital_recovery=dict(gross=cr['capital_return'],fee=cr['capital_return_fee'],remaining_shares=z['shares']),
      minority_and_investment_basis=True,late_year_surplus_tests=late)

def compact_output(full):
    raw=json.dumps(full,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return dict(encoding='gzip-base64-json-v1',company='CN:600176',schema='Full JSON: scenarios contain every year and every economic source/parent state; values in CNY billion except per original share.',
      summary=full['summary'],uncompressed_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
      data=base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode())
def expand_output(packed):
    if packed.get('encoding')!='gzip-base64-json-v1':return packed
    raw=gzip.decompress(base64.b64decode(packed['data']));assert hashlib.sha256(raw).hexdigest()==packed['sha256'];assert len(raw)==packed['uncompressed_bytes']
    return json.loads(raw)

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--expand':
        src=Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).with_name('2026-Q3-output.json')
        text=json.dumps(expand_output(json.loads(src.read_text())),ensure_ascii=False,indent=2)
        if len(sys.argv)>3:Path(sys.argv[3]).write_text(text+'\n')
        else:print(text)
        return
    output=dict(company='CN:600176',information_cutoff=CUTOFF,unit='CNY billion except per ORIGINAL share',
       current_original_shares_billion=SHARES,source_budget_metadata=NODES,source_budget_columns=['budget_id','economic_aggregation_recipient_not_legal_parent','economic_ownership','profit_weight','capex_weight','opening_cash_budget','opening_external_debt_budget','finite_facility_budget','historical_registered_metadata_not_used_for_children','intercompany_loan'],
       methodology='P: actual legal-person constrained budget. Other rows: economic source budgets NOT individual legal accounts; no foreign Chinese statutory rules. Paid support does not change registered capital.',
       scenario_inputs=SCENARIOS,tests=tests(),scenarios={},independent_reconstruction={},integration_extension={})
    for name,s in SCENARIOS.items():
        x=run(s);x['valuation']=valuation(x);output['scenarios'][name]=x
    for name in ['base','margin_minus_2pp','long_upstream_delay','cycle','structural','upside','capex_plus_20pct','foreign_friction']:
        independent=independently_rebuild(name);actual=output['scenarios'][name]
        assert independent['feasible']==actual['feasible']
        for rr,aa in zip(independent['trace'],actual['trace']):
            assert abs(rr['distribution_per_share']-aa['distribution_per_share'])<1e-7
            for n,ss in rr['states'].items():
                for k,v in ss.items():
                    other=aa['nodes'][n]['end'][k]
                    if isinstance(v,list):
                        assert len(v)==len(other)
                        assert all(t==u and math.isclose(x,y,rel_tol=1e-8,abs_tol=1e-7) for (t,x),(u,y) in zip(v,other))
                    else:assert math.isclose(v,other,rel_tol=1e-8,abs_tol=1e-7),(name,rr['year'],n,k)
        for key in ['value_low','value_high','terminal_y5_low','terminal_y5_high']:assert abs(independent[key]-actual['valuation'][key])<1e-7
        output['independent_reconstruction'][name]=independent
    b=output['scenarios']['base'];output['summary']=b['valuation']
    output['all_scenario_tail_checks']={}
    for name,scenario in SCENARIOS.items():
        extended=run(scenario,320);original=output['scenarios'][name]
        assert extended['feasible']==original['feasible']
        if extended['feasible']:
            vv=valuation(extended);delta={k:vv[k]-original['valuation'][k] for k in ['value_low','value_high','terminal_y5_low','terminal_y5_high']}
            assert max(abs(v) for v in delta.values())<2e-5
            worst=min(rr['end']['cash']-rr['minimum']-rr['end']['payable'] for yr in extended['trace'] for rr in yr['nodes'].values())
            assert worst>=-1e-7
            output['all_scenario_tail_checks'][name]=dict(years=320,valuation_delta_320_minus_240=delta,min_cash_after_operating_floor_and_old_declared_reservation=worst,all_320_year_cash_and_cost_assertions=True)
        else:
            assert extended['failed_year']==original['failed_year']
            output['all_scenario_tail_checks'][name]=dict(feasible=False,failed_year=extended['failed_year'],failed_node=extended['failed_node'],shortfall=extended['shortfall'])
    for count in [160,320]:
        x=run(SCENARIOS['base'],count);x['valuation']=valuation(x);output['integration_extension'][str(count)]=x
    assert abs(output['integration_extension']['320']['valuation']['value_high']-b['valuation']['value_high'])<1e-5
    restart=run(SCENARIOS['base'],240,{k:v['end'] for k,v in b['trace'][4]['nodes'].items()},6,b['trace'][4]['operating']['revenue'])
    assert all(abs(a-c)<1e-9 for a,c in zip(restart['distributions'],b['distributions'][5:]))
    output['same_year5_restart']=restart
    alt=run(dict(SCENARIOS['base'],mature_price_normalization=True));assert alt['feasible'];alt['valuation']=valuation(alt)
    assert alt['trace'][:5]==b['trace'][:5]
    ep=alt['trace'][30]['owner_profit'];payout=alt['trace'][30]['distribution']/ep
    aux=dict(method='Normalized mature earning-power capitalization; independent lower selling prices after Y5; same physical capital and financing constraints',
      capitalized_year=30,earnings_year31=ep,payout_ratio=payout,growth=.015,full_path=alt)
    for label,k in [('low',.1025),('high',.09)]:
        aux[label]=pv(alt['distributions'][:30],k)+ep*payout/(k-.015)/SHARES/(1+k)**30
        assert abs(aux[label]-alt['valuation']['value_'+label])<.01
    output['auxiliary']=aux
    packed=compact_output(output);assert expand_output(packed)==json.loads(json.dumps(output))
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(packed,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps(dict(summary=output['summary'],auxiliary={k:v for k,v in aux.items() if k!='full_path'},tests=output['tests'],scenarios={k:dict(feasible=v['feasible'],valuation=v['valuation'],failure=[v.get('failed_year'),v.get('failed_node'),v.get('shortfall')]) for k,v in output['scenarios'].items()}),ensure_ascii=False,indent=2))
if __name__=='__main__':main()

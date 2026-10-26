#!/usr/bin/env python3
"""中国巨石: ownership cash waterfall. Python stdlib only; CNY billion.
The 240-year integration is a convergence device, NOT a 240-year forecast.
All legal-node budget allocations are estimates, not reported standalone accounts.
No spot price, IRR, mechanical cash principal add-back or perpetual profit multiple.
"""
import json, math, copy
from pathlib import Path
SHARES=4.003136728
CUTOFF='2026-10-26T09:00:00+00:00'
# Leaf-to-root order: (name, owner, ownership, profit weight, capex weight,
# cash, external debt, finite additional facility, registered capital, intercompany loan to P)
NODES=[
 ('JJ','G',1.,.16,.16,.20,.60,.25,1.291,.383241303),
 ('CD','G',1.,.10,.13,.15,.80,1.20,1.5,0.),
 ('HA','G',1.,.20,.34,.25,2.30,3.00,1.99988347,1.204223357),
 ('EG','G',.7501,.08,.07,.25,.80,.20,.21,0.),
 ('US','P',.70,.04,.04,.10,.15,.15,1.4,0.),
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

def node_step(a,p,inc_decl,inc_cash,loan_income,loan_repay_received,params):
    """Actual production function; tested below with a hand-computable case."""
    taxrate=params.get('tax',.18)
    int_exp=a['debt']*params['rate']
    loan_int=a['loan']*.025
    financial_interest=a['cash']*.012
    taxable=p['ebit']+financial_interest+loan_income-int_exp-loan_int
    tax=max(0.,taxable)*taxrate
    own_profit=taxable-tax+p.get('affiliate_income',0.)
    legal_profit=own_profit+inc_decl
    capital=a['capital']+p.get('equity_in',0.)
    available,reserve,res_add=legal_step(a['retained'],a['reserve'],capital,legal_profit)
    # Old dividend receipt is already in inc_cash, never inc_decl.
    pre=p.get('equity_in',0.)-p.get('equity_out',0.)+a['cash']+own_profit+p['dep']-p['capex']-p['dnwc']+inc_cash+loan_repay_received-a['payable']
    # Own affiliate income equals cash paid; no additional affiliate principal is added.
    draw=min(max(0.,p['minimum']-pre),max(0.,a['limit']-a['debt']))
    pre+=draw
    if pre+1e-10<p['minimum']:
        return {'feasible':False,'shortfall':p['minimum']-pre,'cash_before_funding':pre-draw,'draw':draw,'legal_profit':legal_profit}
    # Repay old shareholder loans, then a fraction of free cash to external creditors.
    loanrepay=min(a['loan'],max(0.,pre-p['minimum'])*.10)
    pre-=loanrepay
    repay=min(a['debt']+draw,max(0.,pre-p['minimum'])*params.get('repay_fraction',.25))
    pre-=repay
    # Ordinary dividend uses legal profit first; excess cash sweep cannot reuse that legal room.
    normal=min(max(0.,available),max(0.,pre-p['minimum']),max(0.,p['target']))
    sweep=min(max(0.,available-normal),max(0.,pre-p['minimum']-normal)) if params['sweep'] else 0.
    declare=normal+sweep
    paid_new=declare*(1-params['lag']); payable=declare-paid_new
    endcash=pre-paid_new
    debt=a['debt']+draw-repay
    assert endcash+1e-9>=p['minimum']+payable
    assert available-declare>=-1e-9 or available<0 and declare==0
    # cash conservation includes all cash movements, not merely FCF identity.
    expected=p.get('equity_in',0.)-p.get('equity_out',0.)+a['cash']+own_profit+p['dep']-p['capex']-p['dnwc']+inc_cash+loan_repay_received-a['payable']+draw-loanrepay-repay-paid_new
    assert math.isclose(expected,endcash,abs_tol=1e-8)
    receivable=a.get('dividend_receivable',0.)+inc_decl-inc_cash
    assert receivable>=-1e-8
    end=dict(dividend_receivable=receivable,cash=endcash,debt=debt,limit=a['limit'],capital=capital,reserve=reserve,retained=available-declare,loan=a['loan']-loanrepay,payable=payable)
    row=dict(feasible=True,opening=copy.deepcopy(a),own_profit=own_profit,legal_profit=legal_profit,child_declarations=inc_decl,child_receipts=inc_cash,loan_interest_received=loan_income,loan_principal_received=loan_repay_received,interest_expense=int_exp,loan_interest_paid=loan_int,financial_interest=financial_interest,tax=tax,legal_available_before_dividend=available,reserve_addition=res_add,cash_before_new_financing=pre-draw+loanrepay+repay,draw=draw,external_principal_repaid=repay,shareholder_loan_repaid=loanrepay,old_dividend_paid=a['payable'],ordinary_declared=normal,excess_declared=sweep,new_dividend_declared=declare,new_dividend_paid=paid_new,total_dividend_paid=a['payable']+paid_new,end=end,**p)
    return row

def initial():
    a={}
    for name,owner,share,pw,cw,cash,debt,head,capital,loan in NODES:
        a[name]=dict(dividend_receivable=(.65 if name=='P' else 0.),cash=cash,debt=debt,limit=debt+head,capital=capital,reserve=(1.475234311 if name=='P' else 0.),retained=(.00385265745 if name=='P' else 0.),loan=loan,payable=(.65 if name=='G' else 0.))
    return a

def run(s,years=240,start_state=None,start_y=1,prior_revenue=24.,keep=True):
    a=copy.deepcopy(start_state) if start_state else initial()
    if not start_state and 'opening_old_dividend' in s:
        a['G']['payable']=s['opening_old_dividend']; a['P']['dividend_receivable']=s['opening_old_dividend']
    if not start_state and 'parent_retained' in s:
        a['P']['retained']=s['parent_retained']
        if s['parent_retained']<1.: a['P']['reserve']=1.339552076
    trace=[]; divs=[]; total_unremitted=0.; nwc=5.6; invested=44.; prev=prior_revenue
    for y in range(start_y,years+1):
        op=parameters(y,s); rev=op['revenue']
        dnwc=.20*(rev-prev)+(1. if y==1 else -.4 if y==2 else -.3 if y==3 else 0.)
        # Preserve suppliers' and clients' funds; only normal operational change, no perpetual float draw.
        shock=s['wc_shock']*(1 if y==s['start'] else -1 if y==s['start']+2 else 0)
        rows={}; incomingD={n[0]:0. for n in NODES}; incomingC=incomingD.copy()
        interest_loans=sum(x['loan']*.025 for x in a.values()); loan_receipts=0.
        owner_profit=0.; minority_profit=0.; minority_paid=0.; withholding=0.
        oldsum=sum(v['cash'] for v in a.values()); payments=0.
        for name,owner,share,pw,cw,_,_,_,_,_ in NODES:
            revenue_weight=pw if name!='G' else .41
            if name=='P': revenue_weight=0.
            minimum=(.45 if name=='P' else .02 if name in ('Z','L') else 1.35*revenue_weight)*rev/24.
            ebit,dep,cap,ei,eo=node_budget(y,name,pw,cw,op,s)
            target=1e9 if name!='P' else max(0.,owner_profit)*( .45 if y<=5 else .70 if y<=10 else 1.)
            p=dict(ebit=ebit,dep=dep,capex=cap,equity_in=ei,equity_out=eo,dnwc=dnwc*revenue_weight+(shock if name=='P' else 0.),minimum=minimum,target=target,affiliate_income=(.10*(rev/24.) if name=='P' else 0.))
            x=node_step(a[name],p,incomingD[name],incomingC[name],interest_loans if name=='P' else 0.,loan_receipts if name=='P' else 0.,dict(rate=(s['rate'] if y>=s['start'] else .03),lag=0. if name=='P' else (s['lag'] if y>=s['start'] else .15),sweep=y>=6,repay_fraction=.25))
            rows[name]=x
            if not x['feasible']:
                return dict(feasible=False,failed_year=y,failed_node=name,shortfall=x['shortfall'],trace=trace+[{'year':y,'nodes':rows,'operating':op,'feasible':False}],value=None)
            a[name]=x['end']; loan_receipts+=x['shareholder_loan_repaid']
            # Parent group attribution for direct/indirect economic claims.
            ownership=share if name not in ('Z','L','G','P') else 1.
            owner_profit+=x['own_profit']*ownership; minority_profit+=x['own_profit']*(1-ownership)
            if owner:
                # EG/US cash withholding: budget 5%, separately paid outside group.
                wt=.05 if name in ('EG','US') else 0.
                incomingD[owner]+=x['new_dividend_declared']*share*(1-wt)
                incomingC[owner]+=x['total_dividend_paid']*share*(1-wt)
                minority_paid+=x['total_dividend_paid']*(1-share)
                withholding+=x['total_dividend_paid']*share*wt
            else:
                payments=x['total_dividend_paid']
        nwc+=dnwc+shock; invested+=op['capex']-op['depreciation']+dnwc+shock
        endsum=sum(v['cash'] for v in a.values())
        # Internal dividends, loan principal/interest cancel. Foreign withholding remains external.
        ownsum=sum(x['own_profit'] for x in rows.values())
        draws=sum(x['draw'] for x in rows.values()); repayments=sum(x['external_principal_repaid'] for x in rows.values())
        cash_check=oldsum+ownsum+op['depreciation']-op['capex']-dnwc-shock+draws-repayments-payments-minority_paid-withholding
        # Withholding on declaration (parent profit) versus actual cash has timing effect:
        # ownsum excludes internal dividends, so net tax only in cash check above.
        assert math.isclose(endsum,cash_check,rel_tol=1e-8,abs_tol=1e-7),(y,endsum,cash_check)
        row=dict(year=y,calendar_label=2026+y,feasible=True,operating=op,delta_nwc=dnwc+shock,nwc=nwc,invested_capital=invested,owner_profit=owner_profit,minority_profit=minority_profit,minority_cash_paid=minority_paid,foreign_withholding=withholding,distribution=payments,distribution_per_share=payments/SHARES,group_cash=endsum,external_debt=sum(v['debt'] for v in a.values()),new_external_financing=draws,external_debt_repayment=repayments,nodes=rows)
        trace.append(row); divs.append(payments/SHARES); prev=rev
    return dict(feasible=True,trace=trace,distributions=divs,closing_state=a)

def pv(distributions,r,start=0): return sum(v/(1+r)**(i+1) for i,v in enumerate(distributions[start:]))
def valuation(x):
    if not x['feasible']: return None
    d=x['distributions']; rates=[.1025,.09]
    return {'value_low':pv(d,rates[0]),'value_high':pv(d,rates[1]),'terminal_y5_low':pv(d,rates[0],5),'terminal_y5_high':pv(d,rates[1],5),'rate_low_value':rates[0],'rate_high_value':rates[1],'distribution_first5':d[:5],'tv5_pv_fraction_low':pv(d,rates[0],5)/(1+rates[0])**5/pv(d,rates[0]),'tv5_pv_fraction_high':pv(d,rates[1],5)/(1+rates[1])**5/pv(d,rates[1])}

# Separate full-chain reconstruction: independent algebra for legal, financing and payouts.
def independently_rebuild(s,years=240):
    # Independently re-entered reported/budget inputs, no initial()/NODES use.
    raw=[('JJ','G',1.,.16,.16,.2,.6,.85,1.291,.383241303),
         ('CD','G',1.,.1,.13,.15,.8,2.,1.5,0.),
         ('HA','G',1.,.2,.34,.25,2.3,5.3,1.99988347,1.204223357),
         ('EG','G',.7501,.08,.07,.25,.8,1.,.21,0.),
         ('US','P',.7,.04,.04,.1,.15,.3,1.4,0.),
         ('W','Z',.8,.01,.01,.059480663,.128548324,.228548324,.3,.361010719),
         ('L','Z',1.,0.,0.,.03,0.,1.5,.3,0.),
         ('Z','P',1.,0.,0.,0.,0.,.05,.6,0.),
         ('G','P',1.,.4,.25,.42,3.15,4.,5.255313048,1.317516638),
         ('P',None,1.,.01,0.,.8,6.9,8.1,4.003136728,0.)]
    state={n:dict(dividend_receivable=.65 if n=='P' else 0.,cash=c,debt=d,limit=l,capital=k,reserve=1.475234311 if n=='P' else 0.,retained=.00385265745 if n=='P' else 0.,loan=loan,payable=.65 if n=='G' else 0.) for n,up,own,w,cw,c,d,l,k,loan in raw}
    records=[]; prev=24.; vals=[]
    for t in range(1,years+1):
        # Independent reconstruction of original operating assumptions, not reading official outputs.
        if t<6:
            rr=(24.81,24.565,25.67,27.05,28.40)[t-1]; mm=(.29,.26,.25,.25,.25)[t-1]
            dd=2.8+.15*(t-1); cc=(7.5,6.5,5.0,4.2,4.3)[t-1]
        else:
            factors=(1.04,1.035,1.03,1.025,1.02)
            rr=28.4*math.prod(factors[:min(t-5,5)])*1.015**max(t-10,0)
            mm=.25-.004*min(t-5,5); dd=3.4*rr/28.4
            lastfactor=factors[t-6] if t<=10 else 1.015
            cc=dd+1.6*rr*(1-1/lastfactor)
        if t>=s['start']:
            rr*=s['rev_factor']; mm+=s['margin_shift']; cc*=s['capex_factor']
            if t>5: rr*=s['growth_factor']**min((t-5)/5,1)
        if s is SCENARIOS['cycle'] and t<=3:
            rr*=(.88,.92,.96)[t-1]; mm-=(.09,.07,.04)[t-1]
        if s is SCENARIOS['unfundable'] and t==1: cc+=20
        op=dict(revenue=rr,ebit=rr*mm,depreciation=dd,capex=cc)
        rev=op['revenue']; netwc=(rev-prev)/5+(1. if t==1 else -.4 if t==2 else -.3 if t==3 else 0.)
        shock=s['wc_shock']*((t==s['start'])-(t==s['start']+2)); dc={n[0]:[0.,0.] for n in raw}
        ir=sum(z['loan'] for z in state.values())*.025; principal=0.; earn=0.; out=0.
        rec={}
        for name,up,own,w,cw,_,_,_,_,_ in raw:
            z=state[name]; rw=.41 if name=='G' else 0. if name=='P' else w
            floor=(.45 if name=='P' else .02 if name in ('Z','L') else 1.35*rw)*rev/24
            cash_grids={1:[.6,1.2,3.,.3,.2,.1,.9,0.,1.2,0.],2:[.55,1.,2.4,.3,.2,.1,.82449,0.,1.12551,0.],3:[.55,.8,1.65,.3,.2,.1,.1,0.,1.3,0.]}
            idx=[n[0] for n in raw].index(name)
            capnode=cash_grids[t][idx]*op['capex']/(7.5,6.5,5.)[t-1] if t<=3 else op['capex']*(.025 if name=='L' else cw-(.025 if name=='G' else 0))
            lp=(.02,.12,.22,.24,.25)[t-1] if t<=5 else .25*rev/28.4
            ld=(.01,.05,.09,.10,.10)[t-1] if t<=5 else .10*rev/28.4
            depnode=op['depreciation']*cw+(ld if name=='L' else -ld if name=='G' else 0)
            equity=.3 if t==1 else .2 if t==2 else 0
            ei=equity if name in ('L','Z') else 0; eo=equity if name in ('P','Z') else 0
            wa=.13*rev/24-op['ebit']*.01
            operating=op['ebit']*w+(wa if name=='W' else -wa if name=='G' else 0)+(lp if name=='L' else -lp if name=='G' else 0); interest=z['cash']*.012; cost=z['debt']*(s['rate'] if t>=s['start'] else .03)+z['loan']*.025
            pretax=operating+interest-cost+(ir if name=='P' else 0.)
            ownprofit=pretax-.18*max(pretax,0)+(.1*rev/24 if name=='P' else 0)
            legal=ownprofit+dc[name][0]
            replenish=min(max(.5*(z['capital']+ei)-z['reserve'],0),.1*max(legal+min(z['retained'],0),0))
            room=z['retained']+legal-replenish
            cash=ei-eo+z['cash']+ownprofit+depnode-capnode-netwc*rw-(shock if name=='P' else 0)+dc[name][1]+(principal if name=='P' else 0)-z['payable']
            newdebt=min(max(floor-cash,0),max(z['limit']-z['debt'],0)); cash+=newdebt
            if cash<floor-1e-10: return {'feasible':False,'year':t,'node':name}
            interpay=min(z['loan'],.1*max(cash-floor,0)); cash-=interpay
            redeem=min(z['debt']+newdebt,.25*max(cash-floor,0)); cash-=redeem
            want=max(earn,0)*(.45 if t<=5 else .7 if t<=10 else 1) if name=='P' else 1e9
            regular=min(max(room,0),max(cash-floor,0),max(want,0))
            extra=min(max(room-regular,0),max(cash-floor-regular,0)) if t>=6 else 0
            declared=regular+extra; lag=0 if name=='P' else (s['lag'] if t>=s['start'] else .15); paid=declared*(1-lag)
            transfer=z['payable']+paid; cash-=paid
            state[name]={'dividend_receivable':z.get('dividend_receivable',0)+dc[name][0]-dc[name][1],'cash':cash,'debt':z['debt']+newdebt-redeem,'limit':z['limit'],'capital':z['capital']+ei,'reserve':z['reserve']+replenish,'retained':room-declared,'loan':z['loan']-interpay,'payable':declared-paid}
            earn+=ownprofit*own; principal+=interpay
            if up:
                factor=own*(.95 if name in ('EG','US') else 1)
                dc[up][0]+=declared*factor; dc[up][1]+=transfer*factor
            else: out=transfer/4.003136728
            rec[name]=copy.deepcopy(state[name])
        records.append({'year':t,'states':rec,'owner_profit':earn,'distribution_per_share':out}); vals.append(out); prev=rev
    return dict(feasible=True,trace=records,distributions=vals,valuation={'low':sum(v*(1.1025)**(-i-1) for i,v in enumerate(vals)),'high':sum(v*(1.09)**(-i-1) for i,v in enumerate(vals)),'terminal_low':sum(v*(1.1025)**(-i-1) for i,v in enumerate(vals[5:])),'terminal_high':sum(v*(1.09)**(-i-1) for i,v in enumerate(vals[5:]))})

def tests():
    a=dict(cash=1.,debt=0.,limit=0.,capital=2.,reserve=0.,retained=0.,loan=0.,payable=0.)
    p=dict(ebit=1.,dep=.2,capex=.2,dnwc=0.,minimum=1.,target=1.,affiliate_income=0.)
    x=node_step(a,p,0.,0.,0.,0.,dict(rate=0.,lag=0.,sweep=False,tax=0.,repay_fraction=0.))
    # 1.012 profit incl .012 interest; reserve .1012; dividend .9108; close cash 1.1012.
    assert abs(x['new_dividend_paid']-.9108)<1e-12 and abs(x['end']['cash']-1.1012)<1e-12
    retained,res,add=legal_step(-2.,.9,2.,1.); assert retained==-1. and res==.9 and add==0.
    retained,res,add=legal_step(-1.,.9,2.,3.); assert abs(retained-1.9)<1e-12 and res==1.
    # Increasing paid-in capital reopens reserve capacity, no hard-coded cap.
    assert legal_step(0.,1.,4.,2.)[1]==1.2
    aold=dict(a,dividend_receivable=.5)
    old=node_step(aold,p,0.,.5,0.,0.,dict(rate=0.,lag=0.,sweep=False,tax=0.,repay_fraction=0.))
    assert abs(old['legal_profit']-x['legal_profit'])<1e-12
    assert abs(old['end']['cash']-x['end']['cash']-.5)<1e-12
    assert old['end']['dividend_receivable']==0.
    p2=dict(p,capex=5.)
    assert not node_step(a,p2,0.,0.,0.,0.,dict(rate=0.,lag=0.,sweep=False,tax=0.,repay_fraction=0.))['feasible']
    return {'production_chain_hand_test':'pass','old_dividend_receipt_not_profit':'pass','loss_carryforward':'pass','changing_capital_reserve_cap':'pass','zero_distribution_funding_failure':'pass','hand_case':x}

def compact_output(original):
    """Lossless column-schema/object table. [index] is a reference to objects[index].
    Row tag 0 is an original list; tag -(schema+1) is an original dictionary.
    Interning shares only EXACTLY identical data, never drops years or decimals.
    """
    schemas=[]; schema_ids={}; objects=[]; object_ids={}
    def encode(x):
        if not isinstance(x,(list,tuple,dict)): return x
        if isinstance(x,dict):
            keys=tuple(x.keys())
            if keys not in schema_ids: schema_ids[keys]=len(schemas); schemas.append(list(keys))
            row=[-schema_ids[keys]-1]+[encode(v) for v in x.values()]
        else: row=[0]+[encode(v) for v in x]
        signature=json.dumps(row,ensure_ascii=False,separators=(',',':'))
        if signature not in object_ids: object_ids[signature]=len(objects); objects.append(row)
        return [object_ids[signature]]
    root=encode(original)
    return {'encoding':'lossless-schema-object-table-v1','description':'All annual records retained. Use expand_output from linked Python model; object references share identical values only.','company':original['company'],'summary':original['summary'],'schemas':schemas,'objects':objects,'root':root}

def expand_output(packed):
    """Pure data decoder: does not run any economic calculation."""
    if packed.get('encoding')!='lossless-schema-object-table-v1': return packed
    result=[]
    def read(v): return result[v[0]] if isinstance(v,list) else v
    for row in packed['objects']:
        values=[read(v) for v in row[1:]]
        result.append(values if row[0]==0 else dict(zip(packed['schemas'][-row[0]-1],values)))
    return read(packed['root'])

def main():
    output={'company':'CN:600176','information_cutoff':CUTOFF,'unit':'CNY billion except per share','fully_diluted_shares_billion':SHARES,'integration_years':240,'nodes':NODES,'node_names':NAMES,'assumptions':SCENARIOS,'tests':tests(),'scenarios':{}}
    for name,s in SCENARIOS.items():
        x=run(s); x['valuation']=valuation(x); output['scenarios'][name]=x
    output['independent_reconstruction']={}
    for name in ['base','margin_minus_2pp']:
        raw_s=dict(start=1 if name=='base' else 2,rev_factor=1.,margin_shift=0. if name=='base' else -.02,growth_factor=1.,capex_factor=1.,rate=.03,lag=.15,wc_shock=0.)
        x=independently_rebuild(raw_s); z=output['scenarios'][name]
        assert x['feasible']==z['feasible']
        if x['feasible']:
            for u,v in zip(x['trace'],z['trace']):
                assert math.isclose(u['distribution_per_share'],v['distribution_per_share'],abs_tol=1e-8)
                for node in u['states']:
                    for key,val in u['states'][node].items(): assert math.isclose(val,v['nodes'][node]['end'][key],rel_tol=1e-8,abs_tol=1e-7),(name,u['year'],node,key)
            for aa,bb in [('low','value_low'),('high','value_high'),('terminal_low','terminal_y5_low'),('terminal_high','terminal_y5_high')]:
                assert abs(x['valuation'][aa]-z['valuation'][bb])<1e-8
        output['independent_reconstruction'][name]=x
    # Entire tails are regenerated, retaining full annual outputs in every run.
    output['integration_extension']={}
    for n in [160,320]:
        x=run(SCENARIOS['base'],n); x['valuation']=valuation(x); output['integration_extension'][str(n)]=x
    b=output['scenarios']['base']; assert b['feasible']
    # Fifth-year terminal explicitly restart the SAME physical/legal balance sheet.
    restart=run(SCENARIOS['base'],240,{k:v['end'] for k,v in b['trace'][4]['nodes'].items()},6,b['trace'][4]['operating']['revenue'])
    assert all(abs(x-y)<1e-9 for x,y in zip(restart['distributions'],b['distributions'][5:]))
    output['same_year5_state_terminal_restart']={'verified':True,'opening_state':{k:v['end'] for k,v in b['trace'][4]['nodes'].items()},'valuation_low':pv(restart['distributions'],.1025),'valuation_high':pv(restart['distributions'],.09),'trace':restart['trace']}
    for key in ['value_low','value_high']:
        assert abs(output['integration_extension']['320']['valuation'][key]-b['valuation'][key])<1e-5
    # Earnings-capitalization cross-check at a mature debt-free actual budget state.
    # Use the SAME legal payouts/reinvestment, not a separately asserted profit multiple.
    year=30; nxt=b['trace'][year]; ep=nxt['owner_profit']; payout=nxt['distribution']/ep; g=.015
    aux={'capitalization_at_year':year,'next_owner_earnings':ep,'actual_budget_payout_ratio':payout,'g':g,'formula':'PV(actual D1..30)+E31*payout31/(k-g)/(1+k)^30/shares; no principal addition','shared_operating_assumptions':True}
    for label,k in [('low',.1025),('high',.09)]:
        aux[label]=pv(b['distributions'][:year],k)+(ep*payout/(k-g)/SHARES)/(1+k)**year
        aux['implied_forward_PE_'+label]=payout/(k-g)
    output['same_path_terminal_capitalization_check']=aux
    alternative_inputs=dict(SCENARIOS['base'],mature_price_normalization=True,description='Independent mature earning-power perspective: from Y6 cloth price 6.0 CNY/m, coarse 4100 CNY/t; Y5 quantity base grows only 1.5%; existing cost retained; reinvestment follows physical volume, not falling price')
    alternative=run(alternative_inputs); assert alternative['feasible']
    assert alternative['trace'][:5]==b['trace'][:5]
    alternative['valuation']=valuation(alternative)
    year=30; nextrow=alternative['trace'][year]; earnings=nextrow['owner_profit']; payout=nextrow['distribution']/earnings
    altpe={'method':'mature normalized earning-power capitalization after constrained transition','capitalization_at_year':year,'same_year5_state_verified':True,'inputs':alternative_inputs,'next_owner_earnings':earnings,'actual_budget_payout_ratio':payout,'g':.015,'formula':'PV(actual D1..30)+normalized E31*legal/cash payout31/(k-g)/(1+k)^30/shares; Y6+ independently normalized selling prices and volume growth; no principal add-back','complete_budget':alternative}
    for label,k in [('low',.1025),('high',.09)]:
        altpe[label]=pv(alternative['distributions'][:year],k)+(earnings*payout/(k-.015)/SHARES)/(1+k)**year
        altpe['implied_forward_PE_'+label]=payout/(k-.015)
        assert abs(altpe[label]-alternative['valuation']['value_'+label])<.01
    output['auxiliary_normalized_PE']=altpe
    output['summary']=b['valuation']
    output['lossless_serialized_roundtrip_verification']={'status':'asserted every generation','comparison':'expand_output(json.loads(json.dumps(compact_output(full)))) == json.loads(json.dumps(full))','scope':'every key, number, year, node and scenario including independent rebuild and extensions','independent_rebuild_function':'independently_rebuild; raw tuples and raw_s literals separately entered'}
    packed=compact_output(output)
    assert expand_output(json.loads(json.dumps(packed,ensure_ascii=False,separators=(',',':'))))==json.loads(json.dumps(output,ensure_ascii=False,separators=(',',':'))), 'Lossless annual-data serialized round trip failed'
    path=Path(__file__).with_name('2026-Q3-output.json'); path.write_text(json.dumps(packed,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps({'summary':output['summary'],'scenarios':{k:dict(feasible=v['feasible'],valuation=v['valuation'],failure=(v.get('failed_year'),v.get('failed_node'),v.get('shortfall'))) for k,v in output['scenarios'].items()},'auxiliary':{k:v for k,v in output['auxiliary_normalized_PE'].items() if k!='complete_budget'}},ensure_ascii=False,indent=2))
if __name__=='__main__': main()

"""CN000999: CNY billion, economic subgroups NOT legal entities; stdlib only.
Year ends 26 October. Non-parent remittances are explicitly conditional budgets.
Full annual tail, no synthetic statutory reserves, no terminal cash confiscation.
"""
import json,copy,gzip,pathlib,base64,hashlib,sys
S=1.664217858
W=[1.,1.,.28,.2908]
CASH=[1.7-.69065041107,1.10909007747,3.1-(.94880497180-.69065041107),1.2]
DEBT=[2.,.2,.5,1.2925144079]
MINC=[.4,.7,.6,.5]
BASE=dict(name='base',growth=.025,r=.095,g=.015,roic=.14,margin=1.,capex_mult=1.,delay=.25,old_receipt=[.55,.55],pool_payment=0.,debt_rate=.035,cash_yield=.01,payout=.50,sub_payout=.45,cash_transfer_to_T=0.,rev=[3.,17.5,8.3,3.8],nopat=[.4,2.45,1.6,-.25],capital=[2.5,7.,6.,3.5],da_rate=[.04,.075,.065,.06],maintenance_ratio=1.12,nonop_asset=.65,release_every=5,friction=.03,parent_tax=.15,sub_shield=0.,parent_opening=8.77745218836,years=240,external_caps=[2.8,.5,.8,3.5],tax_loss=False,profit_scale=1.)

def statutory(retained,profit,registered,reserve,voluntary_rate=0.):
    """PRC real legal entity only. Registration, not paid-in/cost. Loss first."""
    eligible=max(0.,profit-max(0.,-retained))
    statutory_add=min(max(0.,registered*.5-reserve),eligible*.10)
    voluntary_add=max(0.,eligible-statutory_add)*voluntary_rate
    return retained+profit-statutory_add-voluntary_add,reserve+statutory_add,statutory_add,voluntary_add

def settle_old(cash,retained,receipt):return cash+receipt,retained

def realize(principal,basis,fee,tax,ownership,shares,cancel_fraction=0.):
    """Net asset-sale/capital recovery; tax gains only, cancellation explicitly paired.
    No automatic tax credit for negative gains. Per continuing original share cash.
    This helper also prices finite-lived non-operating capital in production.
    """
    cost=principal*fee;gain=principal-cost-basis;taxcash=max(0.,gain)*tax
    cash=(principal-cost-taxcash)*ownership
    return dict(gross=principal,cost=cost,tax=taxcash,gain=gain,principal_return=min(basis,max(0,principal-cost))*ownership,cash=cash,shares_after=shares*(1-cancel_fraction),cash_per_original_share=cash/shares)

def net_financing_cost(gross_interest,normalized_nopat,tax_rate):
    # Tax benefit cannot exceed same-source current operating tax paid.
    assert 0<=tax_rate<1 and gross_interest>=0
    available_pretax=max(0.,normalized_nopat)/(1-tax_rate)
    return gross_interest-min(gross_interest,available_pretax)*tax_rate

def operating(p):
    if 'literal_ops' in p:return copy.deepcopy(p['literal_ops'])
    rev=p['rev'][:];cap=p['capital'][:];n=p['nopat'][:];out=[]
    for t in range(1,p['years']+1):
        gr=p['growth'] if t<=5 else p['growth']+(p['g']-p['growth'])*(t-5)/5 if t<=10 else p['g']
        if p['name']=='cyclical' and t<=2:gr=-.04 if t==1 else 0
        if p['name'].startswith('structural'):gr=-.01 if t<=5 else 0
        rows=[]
        for i in range(4):
            oldrev=rev[i];oldcap=cap[i];rev[i]*=1+gr
            if t<=10:
                if i==3:
                    schedule=[-.25,-.1,0,.12,.2,.22,.24,.26,.28,.3]
                    if p['name']=='structural':schedule=[-.5,-.4,-.25,-.1,0,.1,.15,.2,.2,.2]
                    if p['name']=='structural_unfunded':schedule=[-.5]*5+[-.25,-.1,0,0,0]
                    if p['name']=='optimistic':schedule=[-.1,.1,.3,.4,.5,.55,.6,.65,.7,.75]
                    nop=schedule[t-1]
                else:n[i]*=1+gr;nop=n[i]*p['margin'];nop*= (.85 if t==1 else .92) if p['name']=='cyclical' and t<=2 else 1
                nop*=p['profit_scale']
                if p['tax_loss'] and i==0 and nop>0:nop*=.75/.85 # diagnostic tax-qualification loss, no negative refund
                da=cap[i]*p['da_rate'][i];maintenance=da*p['maintenance_ratio']
                expansion=max(0.,rev[i]-oldrev)*.15;wc=(rev[i]-oldrev)*.12
                if p['name']=='cyclical' and t==1:wc+=.15
                if p['name']=='cyclical' and t==3:wc-=.15
                capex=(maintenance+expansion)*p['capex_mult'];cap[i]+=capex-da
            else:
                nop=out[-1][i]['nopat']*(1+gr)
                # all replacement retained; incremental invested capital = delta NOPAT / ROIC.
                # Not an independent additional growth charge on first-decade capex.
                da=cap[i]*p['da_rate'][i];maintenance=da
                expansion=max(0.,nop-out[-1][i]['nopat'])/p['roic']
                wc=0.;capex=(da+expansion)*p['capex_mult'];cap[i]+=expansion*p['capex_mult'] # extra upkeep replaces assets, creates no new capacity
            rows.append(dict(revenue=rev[i],nopat=nop,da=da,maintenance=maintenance,capex=capex,delta_wc=wc,capital_begin=oldcap,capital_end=cap[i],nonproductive_replacement=capex-da-(cap[i]-oldcap),fcff=nop+da-capex-wc))
        out.append(rows)
    return out

def simulate(p):
    cash=CASH[:];debt=DEBT[:];cash[0]-=p['cash_transfer_to_T'];cash[2]+=p['cash_transfer_to_T'];pending=[0.]*4
    parent=p['parent_opening'];reserve=.832108929;registered=S;old=1.1;hist=[];ops=operating(p);nonop_done=False
    for t,rows in enumerate(ops,1):
        begin=cash[:];debt_begin=debt[:];parent_begin=parent;reserve_begin=reserve
        floor=[x*(1+p['g'])**max(0,t-10) for x in MINC]
        interest=[];net=[];earn=[];borrow=[0.]*4;repay=[0.]*4;decl=[0.]*4;receipts=[0.]*4;friction=[0.]*4
        for i,row in enumerate(rows):
            shield=p['parent_tax'] if i==0 else p['sub_shield']
            intr=net_financing_cost(debt[i]*p['debt_rate'],row['nopat'],shield)
            y=cash[i]*p['cash_yield'];interest.append(intr);earn.append(y);net.append(row['nopat']-intr+y);cash[i]+=row['fcff']-intr+y
        oldpay=min(old,p['old_receipt'][t-1] if t<=len(p['old_receipt']) else 0,max(0,cash[1]-floor[1]));cash[1]-=oldpay;cash[0],parent=settle_old(cash[0],parent,oldpay);old-=oldpay
        settlement=p['pool_payment'] if t==1 else 0.;cash[0]-=settlement;cash[1]+=settlement
        minority=0.
        # pay last year's declared budgets before any new distributions.
        for i in [1,2,3]:
            rec=min(pending[i],max(0,cash[i]-floor[i]));pending[i]-=rec;cash[i]-=rec;receipts[i]+=rec
            target=max(0,net[i])*(p['sub_payout'] if i==1 else .5)
            new=min(target,max(0,cash[i]-floor[i]-pending[i]));decl[i]+=new
            now=new*(1-p['delay']);cash[i]-=now;pending[i]+=new-now;receipts[i]+=now
            # surplus first retires debt; then every recurring release cycle all new
            # vintages are evaluated. Unpaid declared liabilities reserved in cash.
            repay[i]=min(debt[i],max(0,cash[i]-2*floor[i]-pending[i]));cash[i]-=repay[i];debt[i]-=repay[i]
            if t%p['release_every']==0:
                gross=max(0,cash[i]-2*floor[i]-pending[i]);friction[i]=gross*p['friction'];special=gross-friction[i]
                cash[i]-=gross;decl[i]+=special;receipts[i]+=special
            cash[0]+=receipts[i]*W[i];minority+=receipts[i]*(1-W[i])
        # finite investment realization at year 4: principal changes cash, not new dividend income.
        capital_sale=realize(p['nonop_asset'],p['nonop_asset'],p['friction'],.25,1,S) if t==4 else dict(cash=0.,gain=0.,cost=0.,tax=0.,principal_return=0.)
        cash[0]+=capital_sale['cash']
        profit_parent=net[0]+sum(decl[i]*W[i] for i in [1,2,3])+capital_sale['gain']-capital_sale['tax']
        parent,reserve,res_add,vol_add=statutory(parent,profit_parent,registered,reserve)
        # lending limits are budgets, not bank promises. No invented financing.
        feasible=True
        for i in range(4):
            need=max(0,floor[i]-cash[i]);head=max(0,p['external_caps'][i]-debt[i]);borrow[i]=min(need,head);debt[i]+=borrow[i];cash[i]+=borrow[i]
            if need>head+1e-9:feasible=False
        target=max(0,sum(net[i]*W[i] for i in range(4)))*p['payout']
        dividend=min(target,max(0,parent),max(0,cash[0]-floor[0]));cash[0]-=dividend;parent-=dividend
        repay[0]=min(debt[0],max(0,cash[0]-2*floor[0]));cash[0]-=repay[0];debt[0]-=repay[0]
        special_parent=0.
        if t%p['release_every']==0:
            special_parent=min(max(0,parent),max(0,cash[0]-2*floor[0]));cash[0]-=special_parent;parent-=special_parent;dividend+=special_parent
        netcf=sum(rows[i]['fcff']-interest[i]+earn[i] for i in range(4))
        error=sum(cash)-sum(begin)-netcf-capital_sale['cash']+dividend+minority+sum(friction)-sum(borrow)+sum(repay)
        assert abs(error)<1e-6
        assert abs(parent-parent_begin-profit_parent+res_add+vol_add+dividend)<1e-7
        hist.append(dict(year=t,ops=rows,cash_begin=begin,cash=cash[:],debt_begin=debt_begin,debt=debt[:],liquidity_floor=floor,parent_retained_begin=parent_begin,parent_retained=parent,parent_profit=profit_parent,registered_capital=registered,parent_statutory_reserve=reserve,reserve_add=res_add,voluntary_add=vol_add,net_profit_budget=net,interest=interest,financial_income=earn,common_profit=sum(net[i]*W[i] for i in range(4)),declarations_budget=decl,receipts=receipts,pending=pending[:],old_receipt=oldpay,old_receivable_end=old,minority_cash=minority,friction=friction,finite_asset_realization=capital_sale,dividend=dividend,ordinary_dividend=dividend-special_parent,special_dividend=special_parent,dps=dividend/S,shares=S,borrowing=borrow,repayment=repay,common_cash=sum(W[i]*cash[i] for i in range(4)),common_debt=sum(W[i]*debt[i] for i in range(4)),cash_error=error,feasible=feasible))
    return hist

def value(p):
    h=simulate(p);r=p['r'];pv=sum(z['dividend']/(1+r)**z['year'] for z in h);tail5=sum(z['dividend']/(1+r)**(z['year']-5) for z in h[5:]);after10=sum(z['dividend']/(1+r)**z['year'] for z in h[10:])
    # residual is NOT secretly added as principal: convergence independently shown.
    normal=sum(W[i]*(h[0]['ops'][i]['nopat']+h[0]['ops'][i]['da']-h[0]['ops'][i]['maintenance']) for i in range(4));net0=sum(W[i]*(CASH[i]-DEBT[i]-MINC[i]) for i in range(4))
    aux=[(normal*m+net0+p['nonop_asset']*(1-p['friction'])/(1+r)**4)/S for m in [13,15]]
    feasible=all(z['feasible'] for z in h)
    return dict(parameters=p,diagnostic_pv_if_funding_ignored=pv/S,value_per_share=pv/S if feasible else None,terminal5_per_share=tail5/S if feasible else None,terminal_pv_share=after10/pv if pv else 0,auxiliary_range=aux,history=h,feasible=all(z['feasible'] for z in h))

CHANGES={'base':{},'core_low':dict(r=.10,growth=.02,roic=.12),'core_high':dict(r=.09,growth=.03,roic=.15),'terminal_low':dict(r=.10),'terminal_high':dict(r=.09),'cyclical':dict(name='cyclical'),'structural':dict(name='structural',margin=.8,g=0.,roic=.10,capex_mult=1.1),'structural_unfunded':dict(name='structural_unfunded',margin=.8,g=0.,roic=.10,capex_mult=1.1),'optimistic':dict(name='optimistic',growth=.045,margin=1.05),'upstream_delay':dict(delay=1.,old_receipt=[],pool_payment=1.,release_every=8),'capital_plus20':dict(capex_mult=1.2),'discount_plus100bp':dict(r=.105),'profit_minus10':dict(margin=.9),'debt_rate_plus200bp':dict(debt_rate=.055),'sub_payout30':dict(sub_payout=.30),'opening_attribution':dict(cash_transfer_to_T=.5),'nonop_zero':dict(nonop_asset=0.),'release3':dict(release_every=3),'release8':dict(release_every=8),'friction15':dict(friction=.15),'parent_tax_qualification_loss':dict(tax_loss=True,parent_tax=.25),'no_new_credit':dict(external_caps=DEBT),'foreign_unknown_haircut':dict(profit_scale=.97),'sub_tax_shield15':dict(sub_shield=.15)}

def selftest():
    global S,W,CASH,DEBT,MINC
    tests={}
    assert abs(net_financing_cost(.07,.01,.15)-(.07-.01/.85*.15))<1e-12
    assert net_financing_cost(.07,-.01,.15)==.07
    saved=S,W,CASH,DEBT,MINC
    try:
        S=1.;W=[1.,0.,0.,0.];CASH=[0.]*4;DEBT=[0.]*4;MINC=[0.]*4
        p=copy.deepcopy(BASE);p.update(r=.1,payout=1.,old_receipt=[],nonop_asset=0.,cash_yield=0.,parent_opening=0.,release_every=5)
        p['literal_ops']=[[dict(revenue=0.,nopat=1. if i==0 else 0.,da=0.,maintenance=0.,capex=0.,delta_wc=0.,capital_end=0.,fcff=1. if i==0 else 0.) for i in range(4)] for _ in range(240)]
        q=value(p);expected=(1-1.1**-240)/.1
        assert abs(q['value_per_share']-expected)<1e-10
        assert all(abs(z['dps']-1)<1e-10 for z in q['history'])
        tests['full_value_flat_cash']={'actual':q['value_per_share'],'hand':expected}
        p['literal_ops']=[[dict(revenue=0.,nopat=0.,da=0.,maintenance=0.,capex=0.,delta_wc=0.,capital_end=0.,fcff=0.) for i in range(4)] for _ in range(240)]
        p.update(nonop_asset=1.,parent_opening=10.,payout=0.)
        q=value(p);expected=.97/1.1**5
        assert abs(q['value_per_share']-expected)<1e-10
        assert q['history'][3]['parent_profit']==-.03 or abs(q['history'][3]['parent_profit']+.03)<1e-12
        assert abs(sum(z['dividend'] for z in q['history'])-.97)<1e-12
        tests['full_value_finite_principal_no_double_count']={'actual':q['value_per_share'],'hand':expected,'new_operating_profit':0,'cash_received_year5':.97}

    finally:S,W,CASH,DEBT,MINC=saved
    assert statutory(0,10,20,5)==(9.,6.,1.,0.);tests['registration_not_paid_in']=[9,6,1]
    assert statutory(-10,5,20,0)[2]==0
    assert statutory(-1,1.5,20,0)[2]==.05;tests['loss_before_reserve']=statutory(-1,1.5,20,0)
    assert statutory(0,10,20,10)[2]==0
    assert statutory(0,10,40,10)[2]==1;tests['effective_registration_increase']=True
    assert settle_old(1,2,3)==(4,2);tests['old_receipt_not_profit']=True
    q=realize(10,10,.02,.25,.28,2,.1);assert abs(q['cash']-2.744)<1e-12 and q['tax']==0 and q['shares_after']==1.8;tests['finite_principal_cost_minority_shares']=q
    q=realize(10,4,.02,.25,.28,2);assert abs(q['tax']-1.45)<1e-12;tests['tax_gain_only']=q
    p=copy.deepcopy(BASE);p.update(name='structural',margin=-2,external_caps=[0]*4,years=10);z=value(p);assert not z['feasible'];tests['no_fake_financing']=True
    for batch in [20,80,160]:
        p=copy.deepcopy(BASE);p['years']=batch+10;h=simulate(p);# inspect future new ordinary cash and periodic extra payout
        assert sum(z['special_dividend'] for z in h[batch:batch+5])>0
    tests['all_future_release_batches']=[20,80,160]
    # parent legal function in production, no same-year negative tax credit.
    return tests

def main():
    root=pathlib.Path(__file__).parent;cases={}
    for name,c in CHANGES.items():p=copy.deepcopy(BASE);p.update(c);cases[name]=value(p)
    convergence={}
    for n in [80,160,240,320]:p=copy.deepcopy(BASE);p['years']=n;convergence[n]=value(p)['value_per_share']
    out=dict(units='CNY billion; per share CNY',shares=S,weights=W,cash=CASH,debt=DEBT,base=BASE,cases=cases,convergence=convergence,selftest=selftest())
    payload=json.dumps(out,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    with (root/'2026-Q3-output.json.gz').open('wb') as f:
        with gzip.GzipFile(fileobj=f,mode='wb',mtime=0) as g:g.write(payload)
    summary={k:{x:v[x] for x in ['value_per_share','terminal5_per_share','terminal_pv_share','auxiliary_range','feasible']}|{'dps':[z['dps'] for z in v['history'][:5]]} for k,v in cases.items()}
    packed={'schema':'lossless-gzip-base64-v1','summary':summary,'convergence':convergence,'units':out['units'],'full_payload_sha256':hashlib.sha256(payload).hexdigest(),'expanded_bytes':len(payload),'encoding':'gzip-mtime0/base64','expand_command':'python 2026-Q3.py --expand > expanded.json','payload':base64.b64encode(gzip.compress(payload,mtime=0)).decode()}
    (root/'2026-Q3-output.json').write_text(json.dumps(packed,ensure_ascii=False,separators=(',',':'))+'\n')
    (root/'model-summary.json').write_text(json.dumps(dict(cases=summary,convergence=convergence,selftest=out['selftest']),ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':
    if '--expand' in sys.argv:
        obj=json.loads(pathlib.Path(__file__).with_name('2026-Q3-output.json').read_text());raw=gzip.decompress(base64.b64decode(obj['payload']));assert hashlib.sha256(raw).hexdigest()==obj['full_payload_sha256'];sys.stdout.buffer.write(raw+b'\n')
    else:main()

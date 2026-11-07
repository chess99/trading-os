#!/usr/bin/env python3
"""艾力斯2026Q3新研究快照。stdlib单文件；金额十亿元，股数十亿，输出元/股。
python /absolute/path/2026-Q3.py > output.json；无外部输入，无行情。
预算非审计法定利润、未来授权或精确清算底。
"""
import json,copy
ASOF='2026-10-27T21:26:00+00:00'
FACTS=dict(cash=1.12214593170,trading=2.67422590483,current_deposits=.48101753424,long_other=3.90268976167,
 nonfinancial_h1_exclusion=.10610467038,strategic_equity=.26027692924,deferred_tax=.01817129237,
 shares=.45,actual_buyback=.06929323637,buyback_budget=.2,parent_h1_retained=3.51853945402,q3_paid_dividend=.27,
 parent_capital=.45,parent_reserve=.225,subs_capital=.245,opening_nwc=-.35816603907)

def assumptions(kind='base',rate=.105,price=1.,delay=0,extra=0):
    main=[7.2,7.8,8.4,8.8,9,9.1,9.1,8.5,4.675,3.74,2.992,2.3936,1.91488,1.531904]
    other=[.5,.7,.9,1,1.1,1.15,1.2,1.2,1.1,1,.85,.7,.55,.4]
    rd=[.65,.75,.85,.95,1,1,1,.95,.8,.65,.5,.4,.3,.2]
    lic=[.1,.15,.2,.2,.2,.15,.15,.1,.05,.03,0,0,0,0]
    cap=[.12,.15,.18,.2,.2,.15,.12,.1,.08,.07,.06,.05,.04,.03]
    dep=[.08,.09,.1,.11,.12,.12,.12,.12,.1,.09,.08,.07,.06,.05]
    sell=[.36,.35,.34,.34,.34,.34,.35,.36,.4,.4,.4,.4,.4,.4]
    if kind=='cyclical':
        for i,m in enumerate([.85,.9,.97]):main[i]*=m;other[i]*=m
        sell[:2]=[.39,.38]
    if kind=='structural':
        main=[x*.7*.93**i for i,x in enumerate(main)];other=[x*.65 for x in other];sell=[.42]*14
        rd=[x*(1 if i<3 else .75) for i,x in enumerate(rd)]
    if kind=='optimistic':
        main=[x*m for x,m in zip(main,[1,1.1,1.18,1.25,1.3,1.3,1.3,1.3,1.15,1.15,1.15,1.15,1.15,1.15])]
        other=[x*1.25 for x in other];rd=[x*1.2 for x in rd];lic=[x*1.5 for x in lic];cap=[x*1.2 for x in cap]
    for j in range(1,extra+1):
        main.append(1.531904*.8**j);other.append(.4*.75**j);rd.append(.2*.8**j);lic.append(0.)
        cap.append(.03*.8**j);dep.append(.05*.8**j);sell.append(.4)
    rows=[]
    for i in range(len(main)):
        revenue=main[i]*price+other[i];cogs=main[i]*price*.04+other[i]*.30
        sales=revenue*sell[i];admin=revenue*.025+.03;surcharge=revenue*.013
        pretax=revenue-cogs-sales-admin-surcharge-rd[i]-lic[i]-dep[i];op=pretax-max(0.,pretax)*.15
        rows.append(dict(year=2027+i,revenue=revenue,main_revenue=main[i]*price,other_revenue=other[i],cogs=cogs,sales=sales,admin=admin,surcharge=surcharge,rd=rd[i],license=lic[i],dep=dep[i],capex=cap[i],pretax=pretax,op=op,nwc=revenue*(.10 if kind=='cyclical' and i<2 else .06),payout=.25 if i<5 else .7,main_net_price_index=.95**(i+1),implied_volume=main[i]*price/(6.468*.95**(i+1))))
    return dict(kind=kind,rate=rate,rows=rows,delay=delay,parent_cash=3.6-FACTS['actual_buyback'],subs_cash=FACTS['cash']+FACTS['trading']-3.6,deposits=FACTS['current_deposits']+FACTS['long_other']-FACTS['nonfinancial_h1_exclusion'],parent_retained=FACTS['parent_h1_retained']-FACTS['q3_paid_dividend'],subs_retained=0.,parent_reserve=.225,subs_reserve=0.,parent_capital=.45,subs_capital=.245,opening_nwc=FACTS['opening_nwc'],shares=.45,buyback=FACTS['buyback_budget']-FACTS['actual_buyback'],settlements=[.4,.4,.318],parent_fraction=.8,cash_yield=.015,parent_floor=.65,subs_floor=.15,release=.2,asset_exit=.15,equity_exit=FACTS['strategic_equity']-FACTS['deferred_tax'],debt_limit=.5,debt_rate=.05)

def run(p):
    """正式与手算同函数；全部当期母利润包括子宣派统一弥亏/公积，次期收现不再计利润。"""
    cp,cs,locked=p['parent_cash'],p['subs_cash'],p['deposits'];lp,ls=p['parent_retained'],p['subs_retained']
    rp,rs=p['parent_reserve'],p['subs_reserve'];nwc=p['opening_nwc'];debt=pending=0.;out=[]
    def legal(retained,reserve,capital,profit):
        add=min(max(0.,capital*.5-reserve),max(0.,profit+min(0.,retained))*.1)
        return retained+profit-add,reserve+add,add
    for i,r in enumerate(p['rows']):
        start=cp+cs+locked-debt;received=pending;cp+=received;cs-=received;pending=0.
        mature=min(locked,p['deposits']/3) if p['delay']<=i<p['delay']+3 else 0.;locked-=mature;cp+=mature
        ip=(cp+locked)*p['cash_yield'];iss=cs*p['cash_yield'];interest=debt*p['debt_rate'];fp=p['parent_fraction']
        loss=p.get('parent_oneoff_loss',0.) if i==0 else 0.
        old_payable=p.get('parent_old_claim_in_nwc',0.) if i==0 else 0.
        pp=r['op']*fp+ip-interest-loss;sp=r['op']*(1-fp)+iss
        ls,rs,sa=legal(ls,rs,p['subs_capital'],sp)
        nwc_change=r['nwc']-nwc
        fcf=r['op']+r['dep']-r['capex']-nwc_change;nwc=r['nwc'];# 已入账旧款在首年NWC恢复支出里：先从通用80/20拆分取出，再完整归母支付。
        cp+=(fcf+old_payable)*fp+ip-interest-loss-old_payable;cs+=(fcf+old_payable)*(1-fp)+iss
        settlement=p['settlements'][i] if i<len(p['settlements']) else 0.;cp-=settlement;cs+=settlement
        buy=p['buyback'] if i==0 else 0.;cp-=buy
        need=max(0.,p['parent_floor']-cp)
        if need:
            if debt+need>p['debt_limit']+1e-9:raise ValueError('母公司融资预算不足，路径不可行')
            debt+=need;cp+=need
        repay=min(debt,max(0.,cp-p['parent_floor']));cp-=repay;debt-=repay
        declared=min(max(0.,ls),max(0.,cs-p['subs_floor']))*.5 if i>=5 else 0.
        ls-=declared;pending=declared;pp+=declared
        lp,rp,pa=legal(lp,rp,p['parent_capital'],pp)
        target=max(0.,r['op']*r['payout'])+(max(0.,cp-p['parent_floor'])*p['release'] if i>=5 else 0.)
        div=min(target,max(0.,lp),max(0.,cp-p['parent_floor']));cp-=div;lp-=div
        end=cp+cs+locked-debt
        assert abs(end-(start+fcf+ip+iss-interest-buy-div-loss))<1e-8
        assert min(cp,cs,locked)>=-1e-9
        out.append(dict(**r,fcf=fcf,nwc_cash_change=nwc_change,shared_nwc_cash_change=nwc_change-old_payable,parent_old_claim_paid_from_nwc=old_payable,parent_total_claim_cash=old_payable+loss,parent_oneoff_loss=loss,group_cash_after_oneoff=fcf-loss,parent_profit=pp,subs_profit=sp,parent_reserve_add=pa,subs_reserve_add=sa,parent_reserve=rp,subs_reserve=rs,parent_retained=lp,subs_retained=ls,parent_cash=cp,subs_cash=cs,deposits=locked,debt=debt,interest=interest,financial_income=ip+iss,settlement=settlement,buyback=buy,sub_declared=declared,sub_received=received,dividend_receivable=pending,dividend=div,dps=div/p['shares'],financial_net=end,target_dividend=target))
    # 2040/2045有限可见期处置预算；不声称正现金自然耗尽或已有清算决定。
    bridge=dict(parent_cash=cp,subs_cash=cs,deposits=locked,debt=-debt,nwc_release=nwc,operating_asset_net=p['asset_exit'],strategic_equity_net=p['equity_exit'])
    ex=sum(bridge.values());n=len(out);r=p['rate'];pv=sum(y['dividend']/(1+r)**(i+1) for i,y in enumerate(out));exitpv=ex/(1+r)**n;value=(pv+exitpv)/p['shares']
    tv=(sum(y['dividend']/(1+r)**(i+1-5) for i,y in enumerate(out) if i>=5)+ex/(1+r)**(n-5))/p['shares'] if n>=5 else None
    return dict(assumptions=p,years=out,value=value,terminal5=tv,exit=ex,exit_bridge=bridge,terminal5_pv_fraction=(tv*p['shares']/(1+r)**5)/(pv+exitpv) if tv is not None else None,exit_pv_fraction=exitpv/(pv+exitpv),dps5=[y['dps'] for y in out[:5]])

def hand_tests():
    p=assumptions();p.update(rows=[dict(year=1,op=2.,dep=0.,capex=0.,nwc=0.,payout=.5)],parent_cash=10.,subs_cash=0.,deposits=0.,parent_retained=3.,subs_retained=0.,parent_reserve=.5,subs_reserve=0.,parent_capital=1.,subs_capital=0.,opening_nwc=0.,shares=1.,buyback=0.,settlements=[],parent_fraction=1.,cash_yield=0.,parent_floor=0.,subs_floor=0.,asset_exit=0.,equity_exit=0.,rate=.1)
    a=run(p);assert a['years'][0]['dividend']==1 and a['exit']==11 and abs(a['value']-12/1.1)<1e-12
    p.update(parent_retained=-2.,parent_reserve=0.);p['rows'][0].update(op=3.,payout=1.)
    b=run(p);assert abs(b['years'][0]['dividend']-.9)<1e-12
    z=copy.deepcopy(p);z.update(parent_retained=0.,parent_reserve=.5,parent_oneoff_loss=1.5);z['rows'][0].update(op=2.,payout=.5)
    mother_loss=run(z);assert mother_loss['years'][0]['parent_profit']==.5 and mother_loss['years'][0]['subs_profit']==0. and mother_loss['years'][0]['dividend']==.5 and mother_loss['exit']==10.
    assert abs(mother_loss['value']-10.5/1.1)<1e-12
    p.update(rows=[dict(year=i+1,op=1.,dep=0.,capex=0.,nwc=0.,payout=0.) for i in range(7)],parent_cash=0.,subs_cash=10.,parent_retained=0.,parent_reserve=0.,parent_capital=10.,parent_fraction=0.,release=0.)
    c=run(p);assert abs(c['years'][5]['parent_reserve']-.3)<1e-12 and abs(c['years'][5]['parent_retained']-2.7)<1e-12
    p['parent_retained']=-1.;d=run(p)
    assert abs(d['years'][5]['parent_retained']-1.8)<1e-12 and abs(d['years'][5]['parent_reserve']-.2)<1e-12
    assert d['years'][6]['sub_received']==3. and d['years'][6]['parent_profit']==2. and abs(d['years'][6]['parent_retained']-3.6)<1e-12
    return dict(cash=a,loss=b,mother_only_oneoff=mother_loss,sub_profit_reserve=c,sub_profit_loss_then_collection=d)

def auxiliary():
    results=[]
    opening=FACTS['cash']+FACTS['trading']+FACTS['current_deposits']+FACTS['long_other']-FACTS['nonfinancial_h1_exclusion']-FACTS['buyback_budget']
    for cf,r in [(3.,.115),(3.4,.095)]:
        prior=FACTS['opening_nwc'];pv=0.;years=[]
        for t in range(1,15):
            fade=1 if t<=8 else .75**(t-8);wc=.462*fade;change=wc-prior;cash=cf*fade-change;prior=wc;pv+=cash/(1+r)**t
            years.append(dict(year=2026+t,before_nwc=cf*fade,nwc=wc,nwc_change=change,cash=cash))
        bridge=dict(nwc_release=prior,operating_asset_net=.15,strategic_equity_net=FACTS['strategic_equity']-FACTS['deferred_tax'])
        exitpv=sum(bridge.values())/(1+r)**14
        results.append(dict(normal_cash_before_nwc=cf,rate=r,opening_financial_net_full_buyback=opening,years=years,exit_bridge=bridge,exit_pv=exitpv,operating_pv=pv,value=(opening+pv+exitpv)/.45))
    return results

def main():
    cases={k:run(assumptions(k)) for k in ['base','cyclical','structural','optimistic']}
    low=run(assumptions(rate=.115,price=.97));high=run(assumptions(rate=.095,price=1.03))
    sens={'price_minus10':run(assumptions(price=.9)),'deposit_delay3':run(assumptions(delay=3)),'discount_plus1':run(assumptions(rate=.115)),'finite_tail2045':run(assumptions(extra=5))}
    for label,key,value in [('no_extra_release','release',0.),('internal_pay_early','settlements',[1.118]),('equity_zero','equity_exit',0.)]:
        p=assumptions();p[key]=value;sens[label]=run(p)
    p=assumptions();p['deposits']-=.1;sens['principal_minus100m']=run(p)
    # 当前修订请求251,963,843.89减已入账18,800,047.34；旧款已在NWC结算，不重复扣。
    # 新增损失/现金仅归母公司；经营利润与25%/70%目标不因一次性仲裁机械改变。
    p=assumptions();p['parent_oneoff_loss']=.23316379655;p['parent_old_claim_in_nwc']=.01880004734;sens['arbitration_loss']=run(p)
    rm=dict(schema_version=1,method='annual_common_equity_irr_v1',currency='CNY',model_as_of=ASOF,base_case_distributions_per_share=[round(v,6) for v in cases['base']['dps5']],base_case_terminal_equity_value_range_per_share={'year_5':{'low':round(run(assumptions(rate=.115))['terminal5'],2),'high':round(run(assumptions(rate=.095))['terminal5'],2)}})
    output=dict(information_cutoff=ASOF,units='十亿元、十亿股；价值元/股',facts=FACTS,core_low=low,core_high=high,cases=cases,sensitivities=sens,auxiliary=auxiliary(),hand_tests=hand_tests(),value_range=dict(low=round(low['value'],2),high=round(high['value'],2),currency='CNY'),return_model=rm)
    print(json.dumps(output,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False))
if __name__=='__main__':main()

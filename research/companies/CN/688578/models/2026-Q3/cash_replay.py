"""当前资本现金与权益计算核；经营输入由同次实际计算生成。"""

import copy, math, json, hashlib

from bridge_common import EconomicFailure, CacheMissing, require, freeze_equal

FACTS=dict(cash=1.12214593170,trading=2.67422590483,current_deposits=.48101753424,long_other=3.90268976167,
 nonfinancial_h1_exclusion=.10610467038,strategic_equity=.26027692924,deferred_tax=.01817129237,
 shares=.45,actual_buyback=.06929323637,buyback_budget=.2,parent_h1_retained=3.51853945402,q3_paid_dividend=.27,
 parent_capital=.45,parent_reserve=.225,subs_capital=.245,opening_nwc=-.35816603907)

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
            if debt+need>p['debt_limit']+1e-9:raise EconomicFailure('parent_credit_exhausted', {'year': i+1, 'need': need, 'debt': debt, 'debt_limit': p['debt_limit'], 'rows': out, 'parent_cash_before_funding': cp, 'subs_cash': cs, 'locked': locked})
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

def replay(saved, *, delta=0.06458974679, rate=None):
    p = copy.deepcopy(saved['assumptions'])
    p['parent_cash'] -= delta
    p['buyback'] -= delta
    if rate is not None:
        p['rate'] = rate
    require(p['buyback'] >= 0, 'negative_remaining_budget')
    return run(p)

def auxiliary_replay(saved, *, paid=0.13388298316, budget=0.2):
    from auxiliary_components import parameter_event
    global LAST_AUXILIARY_EVENT
    LAST_AUXILIARY_EVENT=parameter_event('688578',paid)
    if budget!=0.2:raise ValueError('Only fixed 200m auxiliary total is admitted')
    # Same producer's immediate-full-budget economic convention, with refreshed split.
    opening = (FACTS['cash']+FACTS['trading']+FACTS['current_deposits']+
               FACTS['long_other']-FACTS['nonfinancial_h1_exclusion']-budget)
    out = copy.deepcopy(saved)
    out['opening_financial_net_full_buyback'] = opening
    out['operating_pv'] = 0.
    for i,y in enumerate(out['years']):
        out['operating_pv'] += y['cash']/(1+out['rate'])**(i+1)
    out['exit_pv'] = sum(out['exit_bridge'].values())/(1+out['rate'])**len(out['years'])
    out['value'] = (opening+out['operating_pv']+out['exit_pv'])/FACTS['shares']
    return out

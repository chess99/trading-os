"""独立端点及支配变量复算：Decimal另写计算链，不调用生产估值函数计算预期值。"""
from decimal import Decimal as D, getcontext
from copy import deepcopy
import importlib.util
from pathlib import Path
getcontext().prec=36
spec=importlib.util.spec_from_file_location('producer',Path(__file__).with_name('2026-Q3.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def d(x): return D(str(x))

def rebuild(p):
    revenue=[]; profit=[]; trade=[]; fixed=[]; fcff=[]; mincash=[]
    old_trade=d(m.INITIAL_TRADE);old_provision=d(m.FACT['provisions'])
    f=d(m.INITIAL_FIXED);old_cash=D(12)
    for i in range(5):
        s=d(p['storage_gwh'][i])*d(p['storage_asp'][i])
        sales=d(p['electronics'][i])+s+d(p['other_revenue'][i])
        gross=d(p['electronics'][i])*d(p['electronics_gm'][i])+s*d(p['storage_gm'][i])+d(p['other_revenue'][i])*d(p['other_gm'][i])
        operating=(gross-max(sales*d(p['opex'][i]),D('12.3')+D('.7')*i))*D('.82')
        cost=sales-gross
        need=sales*(d(p['ar_ratio'][i])+D('.025')-d(p['advance_revenue'][i]))+cost*(d(p['inventory_cogs'][i])+d(p['prepay_cogs'][i])-d(p['ap_cogs'][i]))
        reserve=d(p['warranty'][i]);cash=max(D(12),sales*D('.15'))
        cashflow=operating+d(p['depreciation'][i])-d(p['capex'][i])-(need-old_trade)+(reserve-old_provision)-(cash-old_cash)
        f+=d(p['capex'][i])-d(p['depreciation'][i])
        revenue.append(sales);profit.append(operating);trade.append(need);fixed.append(f);fcff.append(cashflow);mincash.append(cash)
        old_trade=need;old_provision=reserve;old_cash=cash
    return revenue,profit,trade,fixed,fcff,mincash

def independent_high(p):
    sales,profit,trade,fixed,flows,need=rebuild(p)
    _,baseprofit,_,_,_,_=rebuild(m.BASE)
    group=d(m.INITIAL_CASH);parent=d(m.PARENT_START);debt=d(m.INITIAL_DEBT)
    for i in range(5):
        repayment=d(m.FACT['current_debt'])+d(m.FACT['long_payable']) if i==0 else D(0)
        fund=D('.2502') if i==0 else D(0)
        acquisition=D('.15') if i==0 else D(0)
        interest=debt*D('.035')*D('.82')
        bank=max(group-(D(12) if i==0 else need[i-1]),0)*D('.015')
        div=d(m.PAYOUT[i])*d(m.SHARES)
        minority_div=D('.10')+D('.025')*i
        group=group+flows[i]+bank-interest-repayment-fund-acquisition-minority_div-div
        debt-=repayment
        delta=profit[i]-baseprofit[i]
        parent+=d([2.4,2.8,3,3.2,3.4][i])+D('.30')*delta-d([1.5,1.8,2,2,2][i])-max(-delta,0)*D('.15')-(D('.174') if i==0 else 0)-div
    capital=fixed[-1]+trade[-1]+need[-1]-d(p['warranty'][-1])+D('.3')
    nopat=profit[-1];ev=D(0);discount=D(1)+d(p['wacc'])
    for t,g in enumerate(p['fade'],1):
        next_profit=nopat*(1+d(g))
        investment=max((next_profit-nopat)/d(p['fade_roic']),capital*d(g))
        ev+=(next_profit-investment)/(discount**t)
        capital+=investment;nopat=next_profit
    growth=d(p['terminal_growth'])
    next_profit=nopat*(1+growth)
    reinvest=max(next_profit*growth/d(p['terminal_roic']),capital*growth)
    ev+=(next_profit-reinvest)/(d(p['wacc'])-growth)/(discount**5)
    surplus=group-need[-1]
    tax=max(surplus-max(parent-D(6),0),0)*D('.025')
    financial=d(m.INITIAL_OTHER_ASSET)+D('.2502')*D('.70')
    terminal=(ev+surplus-tax+financial-debt-(d(m.FACT['minority'])-D('.10')))/d(m.SHARES)
    current=sum(d(v)/(1+d(p['cost_equity']))**(i+1) for i,v in enumerate(m.PAYOUT))+terminal/(1+d(p['cost_equity']))**5
    return current,terminal,profit[-1]

if __name__=='__main__':
    v,t,p=independent_high(m.HIGH)
    out=m.run(m.HIGH)
    assert abs(v-d(out['value']))<D('1e-10')
    assert abs(t-d(out['terminal_per_share']))<D('1e-10')
    assert abs(p-D('15.5554'))<D('1e-12') # 手算：(41×39%+60×29%+14×12%−115×14%)×82%。
    altered=deepcopy(m.HIGH);altered['storage_gm']=[x+.01 for x in altered['storage_gm']]
    sv,st,_=independent_high(altered)
    changed=m.run(altered)
    assert abs(sv-d(changed['value']))<D('1e-10')
    assert abs(st-d(changed['terminal_per_share']))<D('1e-10')
    m.checks()
    print('Independent high endpoint:',round(v,8),'year5:',round(t,8))
    print('Storage gross margin +1pp:',round(sv,8),'change:',round(sv-v,8))
    print('Formal-chain hand cases: 100 and 102; cash/location/share checks passed.')

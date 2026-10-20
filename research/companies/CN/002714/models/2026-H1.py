"""牧原经营与普通股现金模型；金额十亿元，股数十亿。标准库，无网络。"""
import json
from pathlib import Path
S=5.701920021
CASH=13.629-.143144211-.048699351
DEBT=62.473
CB_BOOK=9.7914037
CB_CASH=9.5429474*1.07
CB_AMORT=CB_CASH-CB_BOOK
FIN=1.0052
SHARE_CB=.220289644
PRICE=[11.6,13,13.5,13.5,13.4,13.4]
COST=[9.85,9.85,9.9,9.95,10,10.05]
Q=[76,75,76,77,78,78]
DA=[15.2,14.8,14.4,14,13.6,13.2]
BIO_DA=[2,2.1,2.2,2.2,2.2,2.2]
MAINT=[6.5,6.8,7,7.3,7.6,13.2]
GROW=[1,.8,.5,.5,.5,1]
BIO=[3.5,3,3,3.1,3.1,3.2]
OVER=[1.2,1.5,1.5,1.2,1,0]
WC=[1,.6,.5,.5,.5,.5]
REPAY=[5.519,10.709,5.933,6.23,6.108]
def model(price_shift=0,cost_shift=0,bio_override=None,maint_override=None,cap=15,price_path=None):
    cash=CASH; debt=DEBT; equity=80.1866-1.0171-.048699351
    parent_cash=10.677-.143144211-.048699351; parent_re=9.935
    fixed=96.7679; rows=[]; cumulative_borrow=0; feasible=True
    for i in range(6):
        price=(PRICE[i]+(price_shift if i>=1 else 0)) if price_path is None else price_path[i]
        cost=COST[i]+cost_shift
        pig=Q[i]*125/1000*(price-cost)
        slaughter=[34.5,36,37,38,39,40][i]*[40,42,44,45,46,46][i]/1000
        ebitda=pig+slaughter+.15
        tax=.25*max(slaughter-.4*1.02**i,0)+.2875
        ebit=ebitda-DA[i]-BIO_DA[i]
        bio=BIO[i] if bio_override is None else bio_override
        maint=MAINT[i] if maint_override is None else maint_override[i]
        spend=maint+GROW[i]+bio+OVER[i]+WC[i]
        fcff=ebitda-tax-spend
        if i==5:
            terminal={'ebit':ebit,'economic_ebit':ebit-(bio-BIO_DA[i]),'fcff':fcff,'tax':tax,'capex_wc':spend,'pig_margin':pig}
            break
        interest=debt*.035+(.2625 if i==0 else 0)
        ni=ebit-tax-interest-(CB_AMORT if i==0 else 0)
        fcfe=fcff-interest
        parent_cost=.35+debt*.8*.035+(.2625+CB_AMORT if i==0 else 0)
        sub_profit=ni+parent_cost
        upstream=.8*max(sub_profit,0)
        legal=min(.0573,max(upstream-parent_cost,0)*.1) if i==0 else 0
        parent_re+=upstream-parent_cost-legal
        # Group financing includes CB redemption and maintains consolidated minimum 6.
        # Parent protects remaining overseas budget; subsidiaries retain minimum 3.
        parent_floor=3+sum(OVER[i+1:5]); floor=parent_floor+3
        repayment=REPAY[i]
        redemption=CB_CASH if i==0 else 0
        available=cash+fcfe-redemption-repayment
        dividend=min(max(ni,0)*.4,max(parent_re,0),max(available-floor,0))
        # Borrow only the calculated liquidity shortfall after scheduled repayments.
        borrowing=max(0,floor-(available-dividend))
        cumulative_borrow+=borrowing
        if cumulative_borrow>cap+1e-9: feasible=False
        newcash=available-dividend+borrowing
        # Parent income is subsidiary dividends less parent costs; expenses/overseas
        # remain within group cash flow. Net intercompany repayment settles balance.
        parent_pre=parent_cash+upstream-parent_cost+(CB_AMORT if i==0 else 0)-OVER[i]-redemption+borrowing-dividend
        intercompany_settlement=parent_floor-parent_pre
        parent_cash=parent_floor
        sub_cash=newcash-parent_cash
        parent_re-=dividend
        if parent_re<0: feasible=False
        debt=debt+borrowing-repayment
        equity+=ni-dividend+(1.0171 if i==0 else 0)
        fixed+=maint+GROW[i]-DA[i]
        assert abs(newcash-(cash+fcfe-redemption-repayment-dividend+borrowing))<1e-9
        assert sub_cash>=3-1e-8 and parent_re>=-1e-8 or not feasible
        rows.append(dict(year=i+1,price=price,cost=cost,pig_margin=pig,slaughter_ebitda=slaughter,tax=tax,ebit=ebit,ni=ni,fcff=fcff,fcfe=fcfe,capital_and_wc=spend,dividend=dividend,dps=dividend/S,borrowing=borrowing,repayment=repayment,debt=debt,cash=newcash,parent_cash=parent_cash,subsidiary_cash=sub_cash,parent_re=parent_re,upstream=upstream,intercompany_settlement=intercompany_settlement,equity=equity,fixed_assets=fixed))
        cash=newcash
    bridge=-(DEBT+CB_CASH)+(CASH-6)+FIN
    dcf={str(w):(sum(x['fcff']/(1+w)**x['year'] for x in rows)+terminal['fcff']/(w-.01)/(1+w)**5+bridge)/S for w in [.095,.11]}
    tv={str(m):(terminal['economic_ebit']*m-debt+cash-6+FIN)/S for m in [9,11]}
    dist={str(k):sum(x['dps']/(1+k)**x['year'] for x in rows)+tv[str(m)]/(1+k)**5 for k,m in [(.12,9),(.105,11)]}
    return dict(rows=rows,terminal=terminal,dcf=dcf,tv=tv,distribution_value=dist,feasible=feasible,new_financing=cumulative_borrow,bridge=bridge)
def main():
    out={k:model(**v) for k,v in {
      'base':{},'core_low':{'price_shift':-.2,'cost_shift':.1},'core_high':{'price_shift':.2,'cost_shift':-.1},
      'price_stress':{'price_shift':-.5},'cyclical':{'price_path':[10.5,11.3,13.5,13.5,13.4,13.4]},'structural':{'price_path':[11,11,11,11,11,11],'cost_shift':.6},'population_stress':{'bio_override':6},
      'maintenance_stress':{'maint_override':[10,10.5,11,11.5,12,13.2]},'no_new_financing':{'cap':0}
    }.items()}
    assert all(out[k]['feasible'] for k in ['base','core_low','core_high'])
    assert not out['no_new_financing']['feasible']
    assert all(out[k]['new_financing']<=15 and all(x['parent_re']>=0 and x['parent_cash']>=3 and x['subsidiary_cash']>=3-1e-8 for x in out[k]['rows']) for k in ['base','core_low','core_high'])
    assert out['core_low']['dcf']['0.11']<out['base']['dcf']['0.11']<out['core_high']['dcf']['0.11']
    assert abs(out['base']['terminal']['economic_ebit']-18.2525)<1e-9
    assert all(abs(x['fcfe']-(x['fcff']-((DEBT if i==0 else out['base']['rows'][i-1]['debt'])*.035+(.2625 if i==0 else 0))))<1e-9 for i,x in enumerate(out['base']['rows']))
    out['core_range']=[round(out['core_low']['dcf']['0.11'],1),round(out['core_high']['dcf']['0.095'],1)]
    Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:{'dcf':v['dcf'],'tv':v['tv'],'dps':[round(x['dps'],4) for x in v['rows']],'feasible':v['feasible'],'financing':v['new_financing']} for k,v in out.items() if isinstance(v,dict)},indent=2))
if __name__=='__main__':main()

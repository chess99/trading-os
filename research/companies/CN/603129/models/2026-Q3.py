"""CFMOTO 2026-Q3. CNY bn; shares bn. Stdlib, deterministic, no live price.
Economic subsidiary remittance budget is NOT statutory accounts of a synthetic entity.
Parent statutory accounts are separate; unknown subsidiary ledgers remain conditional.
"""
import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
S0=.153482763; BOND=2.178763; C0=14.18865953524-.34007697939; P0=7.65825519985
REVENUE=[9.4,5.8,8.2,2.5,1.7]
GROWTH=[[.12,.10,.09,.07,.05],[.15,.12,.10,.08,.06],[.14,.12,.10,.08,.06],[.20,.18,.15,.10,.08],[.12,.10,.09,.07,.05]]
def statutory(retained,profit,reserve,registered):
    earnings=retained+profit
    add=min(max(registered*.5-reserve,0),.1*max(0,min(profit,earnings)))
    return earnings-add,reserve+add,add

def realize(principal,cost_basis,fees,creditors,ownership=1.,tax=.25,share_count=None,cancel_fraction=0.):
    """Conditional asset disposal / exit; failure is explicit before shareholder residual."""
    gain=principal-cost_basis-fees
    tax_due=max(0,gain)*tax
    residual=principal-fees-tax_due-creditors
    return dict(feasible=residual>=0,shortfall=max(0,-residual),cash_to_owner=residual*ownership if residual>=0 else None,
                remaining_shares=None if share_count is None else share_count*(1-cancel_fraction) if residual>=0 else share_count,cancelled_shares=None if share_count is None else share_count*cancel_fraction if residual>=0 else 0.,accounting_profit=gain-tax_due,capital_recovery=min(principal-fees,cost_basis),creditors_paid=creditors if residual>=0 else None)

def reduce_lots(lots,limit):
    # A cash need can consume deferred surplus; newest cohorts consumed first.
    excess=sum(x[1] for x in lots)-max(0,limit)
    for x in reversed(lots):
        used=min(x[1],max(0,excess));x[1]-=used;excess-=used
    return [x for x in lots if x[1]>1e-12]

def run(kind='base',r=.11,roic=.20,g=.03,margin=0.,delay=3,remit=.8,friction=.07,parent_delay=0.,extra_capex=0.,convert=False,horizon=320,inject_year=0,inject_cash=0.,old_options=.0023994,old_strike=102.15,source_inject_year=0,source_inject_cash=0.,source_inject_capacity=0.):
    rev=REVENUE[:];nwc=-5.9;cash=C0;parent=P0-parent_delay;shares=S0
    retained=4.15847860839;reserve=.083022672;debt=0 if convert else BOND
    capacity=0.;pending=0.;capacity_queue={};lots=[[1+delay,max(0,cash-8.)]];rows=[];cum_dps=0.;op=0.;floor=8.;parentfloor=4.;capital=6.1
    for y in range(1,horizon+1):
        t=y-1;opening=cash;opening_parent=parent;opening_floor=floor;oldprofit=op
        if y<=5:
            rev=[v*(1+GROWTH[i][t]) for i,v in enumerate(rev)];obs=rev[:]
            m=[.09,.12,.08,[-.04,-.01,.01,.025,.03][t],.12]
            capex=[1.8,1.7,1.5,1.3,1.2][t]+(extra_capex if y==1 else 0);dep=[.30,.38,.46,.53,.60][t]
            ratio=[-.19,-.17,-.15,-.15,-.15][t]
            if kind=='cyclical':
                obs[0]*=[.82,.9,.98,1,1][t];obs[1]*=[.82,.9,.98,1,1][t]
                m[0]-=[.025,.015,.005,0,0][t];m[1]-=[.015,.008,.003,0,0][t];capex*=.95;ratio=[-.14,-.14,-.15,-.15,-.15][t]
            if kind=='structural':
                obs[0]*=.5;obs[1]*=.88;obs[2]*=.92;m=[.015,.085,.065,-.08,.09];capex=[1.8,1.5,1.2,1.,1.][t];ratio=-.1
            if kind=='upside':obs=[v*(1+.025*y) for v in obs];m=[.105,.13,.09,[0,.02,.04,.05,.05][t],.13];capex*=1.2
            m=[x+margin for x in m];sales=sum(obs);op=sum(v*x for v,x in zip(obs,m));electric=obs[3]*m[3]
            newnwc=sales*ratio;dnwc=newnwc-nwc;nwc=newnwc;floor=8*sales/27.6
            if kind=='structural':floor=max(6,floor)
            netinvestment=capex-dep+dnwc+(floor-opening_floor)
            ownop=.60*(op-electric);ownfcf=ownop+.45*dep-.55*capex-.60*dnwc-.20-(.25 if kind=='structural' else 0)
            sbc=[.15,.08,.04,.02,.02][t]
        else:
            growth=([.02]*5 if kind=='structural' else [.07,.06,.05,.04,.03])[y-6] if y<=10 else g
            op*=1+growth;sales*=1+growth
            # Total reinvestment includes liquidity; maintenance >= depreciation is retained.
            netinvestment=(op-oldprofit)/roic;floor*=1+growth
            dep=.6*(sales/44.175);dnwc=0.;capex=dep+netinvestment-(floor-opening_floor)
            if capex<dep:raise AssertionError('growth budget cannot maintain assets')
            ownop=.60*op;ownfcf=.60*(op-netinvestment+(floor-opening_floor));sbc=0.;obs=[]
        capital+=netinvestment;parentfloor=.5*floor
        proceeds=0.;newshares=0.
        if y==1:
            newshares=old_options+.0006+(BOND/241.70 if convert else 0)
            proceeds=old_options*old_strike+.0006*145.91
        if y in [2,3,4] and kind!='structural':
            add=.004151875*{2:.3,3:.3,4:.4}[y];newshares+=add;proceeds+=add*max(0,233.45-cum_dps)
        shares+=newshares
        interest=debt*[.001,.003,.006,.015,.018][t] if y<=5 else 0.
        redemption=debt*1.08 if y==6 else 0.
        premium=debt*.08 if y==6 else 0.
        if y==6:debt=0.
        fin=max(0,opening-opening_floor)*.015;parent_fin=max(0,opening_parent-.5*opening_floor)*.015
        fcf=op+dep-capex-dnwc-interest-redemption
        receipt=pending*(1-friction);tax=pending*friction;pending=0.
        # Disclosed equity investment realized in year8 with 10% friction; proceeds remain outside parent, no fake dividend income.
        sale=realize(.1651183581,.1651183581,.01651183581,0.) if y==8 else dict(cash_to_owner=0.,accounting_profit=0.)
        investment_sale=sale["cash_to_owner"]
        injected=inject_cash if y==inject_year else 0.
        source_injected=source_inject_cash if y==source_inject_year else 0.
        source_rights=source_inject_capacity if y==source_inject_year else 0.
        cash+=fcf+fin+proceeds-tax+investment_sale+injected+source_injected
        parent+=ownfcf+parent_fin+proceeds-interest-redemption+receipt+injected
        source_fin=fin-parent_fin
        subprofit=op-ownop-.25*sbc+source_fin+sale["accounting_profit"]
        # Cash yield belongs to the same source budget as its underlying surplus.
        # Pre-existing distribution rights in diagnostic injections are NOT current profit.
        capacity+=source_rights
        capacity+=capacity_queue.pop(y,0.)
        if subprofit>=0:
            capacity+=remit*subprofit
            capacity_queue[y+3]=capacity_queue.get(y+3,0.)+(1-remit)*subprofit
        else:capacity+=subprofit
        # Conditional consolidated budget, excludes source-side cash needed for solvency and pending dividend.
        subcash=cash-parent
        declaration=min(max(0,capacity),max(0,subcash-.5*floor)) if y>5 else 0.
        capacity-=declaration;pending=declaration
        ownprofit=ownop-.75*sbc-interest-premium+parent_fin
        # Only newly declared dividend enters parent profits; next-year receipt has no second income.
        retained,reserve,addreserve=statutory(retained,ownprofit+declaration*(1-friction),reserve,shares)
        # parent cash delay is an intercompany balance budget, not a permanent loss; release in year 4.
        settlement=parent_delay if y==4 else 0.
        parent+=settlement
        debt_escrow=debt*1.08*min(1,y/5)
        liquid_floor=floor+debt_escrow;payment_floor=parentfloor+debt_escrow
        shortfall=max(0,liquid_floor-cash,payment_floor-parent,parent-cash)
        if shortfall>1e-8:
            rows.append(dict(year=y,feasible=False,cash=cash,parent_cash=parent,required_group_floor=liquid_floor,required_parent_floor=payment_floor,shortfall=shortfall,debt_redemption=redemption,distribution=0.))
            return dict(feasible=False,kind=kind,rows=rows,failure_year=y,shortfall=shortfall,current=None,terminal=None)
        target=0. if kind=="structural" and y<=5 else .4*max(0,op-sbc+fin-interest-premium)
        ordinary=min(target,max(0,retained),max(0,cash-liquid_floor),max(0,parent-payment_floor))
        cash-=ordinary;parent-=ordinary;retained-=ordinary
        lots=reduce_lots(lots,cash-floor)
        matured=sum(v for due,v in lots if due<=y)
        special=0. if kind=="structural" and y<=5 else min(matured,max(0,retained),max(0,cash-liquid_floor),max(0,parent-payment_floor))
        cash-=special;parent-=special;retained-=special
        left=special
        for lot in lots:
            if lot[0]<=y:
                d=min(left,lot[1]);lot[1]-=d;left-=d
        lots=reduce_lots(lots,cash-floor)
        newlot=max(0,cash-floor-sum(x[1] for x in lots))
        if newlot>1e-12:lots.append([y+max(1,delay),newlot])
        dps=(ordinary+special)/shares;cum_dps+=dps
        assert abs(cash-opening-fcf-fin-proceeds+tax-investment_sale-injected-source_injected+ordinary+special)<1e-7*max(1,cash)
        assert retained>=-1e-8 or ordinary+special==0
        assert cash-parent>=-1e-7
        rows.append(dict(year=y,feasible=True,revenue=sales,segment_revenue=obs,operating_profit=op,accounting_profit=op-sbc-interest-premium,consolidated_accounting_profit=op-sbc-interest-premium+fin+sale["accounting_profit"]-tax,net_investment=netinvestment,capex=capex,depreciation=dep,delta_nwc=dnwc,operating_capital=capital,cash_floor=floor,parent_floor=parentfloor,
            fcf=fcf,financial_income=fin,shares=shares,new_shares=newshares,registered_capital_budget=shares,exercise_proceeds=proceeds,debt=debt,debt_interest=interest,debt_redemption=redemption,investment_sale_cash=investment_sale,investment_sale_profit=sale["accounting_profit"],
            source_economic_profit=subprofit,source_financial_income=source_fin,source_sbc=.25*sbc,parent_financial_income=parent_fin,source_injected_cash=source_injected,source_injected_preexisting_capacity=source_rights,source_economic_budget=capacity,source_delayed_capacity=dict(capacity_queue),debt_escrow=debt_escrow,new_dividend_declared=declaration,old_dividend_receipt=receipt,remittance_friction=tax,pending_dividend=pending,parent_own_profit=ownprofit,parent_statutory_profit=ownprofit+declaration*(1-friction),parent_reserve=reserve,parent_reserve_add=addreserve,parent_retained=retained,parent_cash=parent,cash=cash,
            ordinary=ordinary,special=special,distribution=ordinary+special,distribution_per_share=dps,queued_surplus=[x[:] for x in lots],financing=0.,shortfall=0.,injected_surplus=injected))
    flows=[x['distribution_per_share'] for x in rows]
    pv=sum(d/(1+r)**(i+1) for i,d in enumerate(flows))
    tv5=sum(d/(1+r)**(i-4) for i,d in enumerate(flows) if i>=5)
    return dict(feasible=True,kind=kind,current=pv,terminal=tv5,terminal_pv_share=tv5/(1+r)**5/pv,rows=rows,parameters=dict(r=r,roic=roic,g=g,margin=margin,delay=delay,remit=remit,friction=friction,parent_delay=parent_delay,extra_capex=extra_capex,convert=convert,horizon=horizon,old_options=old_options,old_strike=old_strike,source_inject_year=source_inject_year,source_inject_cash=source_inject_cash,source_inject_capacity=source_inject_capacity))

def results():
    specs={'central':{},'core_low':dict(r=.115,roic=.16,g=.025),'core_high':dict(r=.105,roic=.20,g=.03),'cyclical':dict(kind='cyclical'),'structural':dict(kind='structural',r=.12,roic=.12,g=.02,convert=False),'upside':dict(kind='upside'),
      'margin_minus_1pp':dict(margin=-.01),'roic_12pct':dict(roic=.12),'release_delay_5':dict(delay=5),'release_delay_1':dict(delay=1),'remit_50pct':dict(remit=.5),'friction_15pct':dict(friction=.15),'parent_delay_2bn':dict(parent_delay=2),'extra_capex_2bn':dict(extra_capex=2),'conversion':dict(convert=True),'financing_failure':dict(parent_delay=10)}
    paths={k:run(**v) for k,v in specs.items()}
    aux={}
    for label,rate,multiple in [('low',.115,10),('high',.105,12)]:
        row=paths['central']['rows'][4]
        surplus=(row['cash']-row['cash_floor'])*.93*(1.015/(1+rate))**3
        netdebt=row['debt']*1.08/(1+rate)
        investment=.14860652229*.93/(1+rate)**4
        terminal=(row['operating_profit']*multiple+surplus-netdebt+investment)/row['shares']
        pv=sum(z['distribution_per_share']/(1+rate)**z['year'] for z in paths['central']['rows'][:5])+terminal/(1+rate)**5
        aux[label]=dict(current=pv,terminal=terminal,multiple=multiple,r=rate,cash_asset=surplus,debt_present_at_year5=netdebt,investment_present_at_year5=investment)
    return {'units':'CNY billion; shares billion; per share CNY','information_cutoff':'2026-10-26T00:00:00+00:00','specs':specs,'paths':paths,'auxiliary_earnings_multiple':aux}
if __name__=='__main__':
    out=results();(ROOT/'2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:{x:v[x] for x in ['feasible','current','terminal']} for k,v in out['paths'].items()},indent=2))

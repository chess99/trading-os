#!/usr/bin/env python3
"""Salted-snack equity cash model. CNY million, million shares. Python stdlib only.
Run: python 2026-Q3.py [--output FILE] [--expand PACKED FILE].
All entity starting balances except explicitly sourced parent/aggregate fields are budgets;
no pooling of legal profit, minority cash or reserve across legal entities.
"""
import copy,json,math,sys,hashlib,gzip,lzma,base64
from pathlib import Path
SYMBOL="CN:002847"; NAME="盐津铺子"; PERIOD="2026-Q3"
COST=dict(zip([x for x in ["parent","jiangxi","technology","shiye","henan","guangxi","xinjiang","egg","changsha_processing","xiushui_processing","supply","thai","ecommerce","jinjiang","jinxiang","jincheng","qujing","testing"]],[0,80,50,100,30,35,100.08,100,16.8537644,20,10,39.95846891,42.45,16,22.26875819,48.3,.55,19.8]))
# name, ownership, registered RMBm, paid RMBm, physical capital share, EBIT share, early tax
ENT=[('parent',1,270.186388,270.186388,.40,.10,.25),('jiangxi',1,80,80,.20,.18,.15),('technology',1,50,50,.02,.22,.15),('shiye',1,100,100,.02,.36,.09),('henan',1,30,30,.06,.025,.25),('guangxi',1,35,35,.04,.02,.15),('xinjiang',1,100.08,100.08,.06,.015,0),('egg',1,100,100,.07,.015,0),('changsha_processing',1,20,16.8537644,.01,.005,0),('xiushui_processing',1,20,20,.01,.005,0),('supply',1,10,10,.005,.005,.25),('thai',1,50,39.95846891,.005,.005,.20),('ecommerce',.94,15,15,.01,.02,.25),('jinjiang',.80,20,20,.025,.01,.25),('jinxiang',.85,30,26.19853905,.02,.007,.25),('jincheng',.70,69,69,.035,.006,.25),('qujing',.55,1,1,.005,.001,0),('testing',.99,20,20,.005,.001,.25)]
# Early tax concessions fade to 25% in Y6; actual agricultural exemption retained.
BASE=dict(growth=[.08,.07,.06,.05,.04],margin=[.135]*5,tail_growth=.02,tail_margin=.12,rate=.095,life=13,capital_ratio=.45,wc_ratio=.105,cash_floor=.035,parent_min_cash=80,parent_cash=100,parent_debt=760,deposit=.015,loan_rate=.035,internal_rate=.03,upstream=.90,lag=0,settlement=100,extra_wc=0,extra_wc_release=2,maintenance=1.0,refund_seed=750,loan_cap=150,credit_until=5,loan_due=6,subscription_cap=300,initial_rp=0,engineering=89.39749,rollover=True,tail_start=6,release_year=15,release_interval=10,release_fee=.02,thai_reserve_rate=.05,thai_reserve_cap=.10,legacy=False,other_wc_mode="fixed",other_wc_years=3,other_asset_years=3,other_liability_years=3)
SCEN={ 'base':{},'core_low':dict(growth=[.06,.06,.05,.04,.03],margin=[.13]*5,tail_margin=.115,rate=.10), 'core_high':dict(growth=[.09,.08,.07,.06,.05],margin=[.14]*5,tail_margin=.125,rate=.09), 'tv_low':dict(tail_margin=.11,tail_growth=.015), 'tv_high':dict(tail_margin=.13,tail_growth=.025), 'cycle':dict(growth=[-.04,.03,.10,.08,.05],margin=[.10,.115,.13,.135,.135],extra_wc=100,extra_wc_release=3,loan_rate=.045,refund_seed=700), 'structural':dict(growth=[-.08,-.03,0,.01,.01],margin=[.10,.09,.085,.085,.085],tail_margin=.075,tail_growth=0,capital_ratio=.52,wc_ratio=.135,loan_rate=.05,rate=.11,life=11,refund_seed=650), 'optimistic':dict(growth=[.12,.10,.09,.08,.06],margin=[.14,.145,.15,.15,.15],tail_margin=.135,capital_ratio=.42,wc_ratio=.095,rate=.09,refund_seed=820), 'margin_minus_1pp':dict(margin=[.125]*5,tail_margin=.11), 'short_life':dict(life=12), 'life10_failure':dict(life=10), 'opening_losses':dict(initial_rp=-10), 'no_old_engineering':dict(engineering=0), 'upstream_lag':dict(lag=1), 'settlement_extra':dict(settlement=250), 'wc_permanent':dict(extra_wc=150,extra_wc_release=0), 'parent_cash_low':dict(parent_cash=50), 'parent_debt_high':dict(parent_debt=860), 'no_credit':dict(loan_cap=0), 'no_rollover':dict(rollover=False,loan_cap=0), 'failure':dict(growth=[-.35,-.15,0,0,0],margin=[-.15]*5,loan_cap=0,subscription_cap=0,extra_wc=300,extra_wc_release=0)}

SCEN['structural_repair']={**SCEN['structural'],'loan_cap':180}
SCEN.update(release_early=dict(release_year=10),release_late=dict(release_year=20),release_fee_high=dict(release_fee=.05),thai_restrictive=dict(thai_reserve_rate=.10,thai_reserve_cap=.50),structural_release_late={**SCEN['structural_repair'],'release_year':20},structural_release_early={**SCEN['structural_repair'],'release_year':10})

# Q3 actual balance-sheet items; share-refund liability is paid separately, never twice.
OTHER_WC={'other_current_assets':140.48833926,'other_receivables':7.82197781,
          'employee_payable':-145.56552701,'tax_payable':-74.04927213,
          'other_payables_ex_refund':-(199.45866766-105.50482),'other_current_liabilities':-11.340035}
SCEN.update(other_wc_revenue=dict(other_wc_mode='revenue'),
            other_wc_runoff_1=dict(other_wc_mode='runoff',other_wc_years=1),
            other_wc_runoff_3=dict(other_wc_mode='runoff',other_wc_years=3),
            other_wc_runoff_5=dict(other_wc_mode='runoff',other_wc_years=5),
            other_wc_assets_delayed=dict(other_wc_mode='split',other_asset_years=3,other_liability_years=1),
            other_wc_liabilities_delayed=dict(other_wc_mode='split',other_asset_years=1,other_liability_years=3))

def other_working_capital(year,revenue,p,weight=1):
    balances={}
    for name,opening in OTHER_WC.items():
        mode=p['other_wc_mode']
        if mode=='fixed':factor=1
        elif mode=='revenue':factor=revenue/5900
        else:
            duration=p['other_wc_years'] if mode=='runoff' else p['other_asset_years'] if opening>0 else p['other_liability_years']
            factor=max(0,1-year/duration)
        balances[name]=opening*weight*factor
    return balances

def legal(rp,res,reg,profit,appropriation=.10,cap=.50):
    # Prior accumulated losses absorb profit before mandatory reserve allocation.
    covered=min(max(profit,0),max(-rp,0))
    transfer=min(max(reg*cap-res,0),max(profit-covered,0)*appropriation)
    return rp+profit-transfer,res+transfer,transfer,covered

def settle_old_dividend(sub,parent,floor):
    paid=min(sub['dividend_payable'],max(0,sub['cash']-floor))
    sub['cash']-=paid;sub['dividend_payable']-=paid
    parent['div_receivable']-=paid*sub['ownership'];parent['cash']+=paid*sub['ownership']
    return paid

def capital_return(state,floor,fee_rate=.02,tax_rate=.25,min_registered=0):
    """Conditional proportionate paid-capital reduction, not a liquidation of production.
    Model budget, subject to creditor notice/settlement, actual paid capital confirmation,
    shareholder approval and registered effectiveness. Unknown paid is never treated as fact.
    No priority claims/declared dividends may remain. Keep 20% registered capital and all
    productive assets, WC and operating liquidity. Parent investment cost is separate.
    """
    zero=dict(gross=0,fee=0,parent_cash=0,minority_cash=0,basis_recovered=0,parent_gain=0,parent_tax=0,registered_reduced=0,units_cancelled=0)
    if state['debt']+state['credit']+state['dividend_payable']>1e-8:return zero
    blocked=max(0,state['cash']-floor-max(state['rp'],0))
    gross=min(blocked,max(0,state['cash']-floor)/(1+fee_rate),max(0,state['reg']-min_registered),state['paid_budget']*.8)
    if gross<=1e-10:return zero
    frac=gross/state['reg'];owned=gross*state['ownership'];basis=state['investment_cost']*frac
    gain=owned-basis;tax=max(gain,0)*tax_rate;fee=gross*fee_rate
    units=state['share_units']*frac
    state['cash']-=gross+fee;state['reg']-=gross;state['paid_budget']-=gross
    state['investment_cost']-=basis;state['share_units']-=units
    state['nci_equity']-=(gross+fee)*(1-state['ownership'])
    # Fees are a real local expense; no immediate tax refund is assumed.
    state['rp']-=fee
    return dict(gross=gross,fee=fee,parent_cash=owned-tax,minority_cash=gross-owned,basis_recovered=basis,parent_gain=gain,parent_tax=tax,registered_reduced=gross,units_cancelled=units)

def cash_tax(state,income,rate,year):
    ledger=[list(x) for x in state.get('loss_vintages',[]) if x[0]>=year and x[1]>1e-12]
    remaining=max(0,income);used=0
    for x in ledger:
        take=min(remaining,x[1]);x[1]-=take;remaining-=take;used+=take
    if income<0:ledger.append([year+5,-income])
    state['loss_vintages']=[x for x in ledger if x[1]>1e-12]
    state['tax_loss']=sum(x[1] for x in state['loss_vintages'])
    return remaining*rate,used

def income_tax_buckets(state,operating,financial,external_interest,internal_interest,rate,year,agricultural_exempt=False):
    # Borrowing/internal interest finances productive assets/working capital in this model.
    # Absent tracing evidence none is allocated to bank deposits to manufacture a deduction.
    operating_net=operating-external_interest-internal_interest
    taxable=financial if agricultural_exempt else operating_net+financial
    applied_rate=.25 if agricultural_exempt else rate
    tax,used=cash_tax(state,taxable,applied_rate,year)
    return tax,used,dict(qualified_operating_income=operating_net if agricultural_exempt else 0,
                        ordinary_taxable_income=taxable,ordinary_rate=applied_rate,
                        operating_financing_expense=external_interest+internal_interest,
                        finance_expense_allocated=0,financial_income=financial,
                        exempt_operating_losses_not_offset=max(0,-operating_net) if agricultural_exempt else 0)

def run(overrides=None,horizon=220,rows=True,entities=None,start=None):
    p=copy.deepcopy(BASE);p.update(overrides or {})
    entries=copy.deepcopy(entities or ENT)
    assert abs(sum(x[4] for x in entries)-1)<1e-9 and abs(sum(x[5] for x in entries)-1)<1e-9
    initial=start or dict(revenue=5900,asset=2800,wc=519 if p['legacy'] else 518.94914213+p['engineering'],cash=251.15336155,debt=997.84723323,shares=270.186388)
    initial=copy.deepcopy(initial)
    initial['other_wc_net']=sum(OTHER_WC.values()) if not start else 0
    initial['total_operating_wc']=initial['wc']+initial['other_wc_net']
    r=initial['revenue'];shares=initial['shares'];records=[];pv=0;tail=0;cum_credit=0;cum_sub=0;score=p['refund_seed'];fail=None
    state={}
    for name,own,reg,paid,aw,ew,tax in entries:
        parent=name=='parent';cash=p['parent_cash'] if parent else (initial['cash']-p['parent_cash'])*ew/.9
        debt=p['parent_debt'] if parent else (initial['debt']-p['parent_debt'])*aw/.6
        state[name]=dict(other_wc=other_working_capital(0,5900,p,ew),cash=cash,debt=debt,credit=0,asset=initial['asset']*aw,wc=(initial['wc']*ew if start or p['legacy'] else 518.94914213*ew+p['engineering']*aw),rp=473.85692443 if parent else p['initial_rp'],reserve=136.4099295 if parent else 0,reg=reg,registered_initial=reg,paid_budget=paid,investment_cost=COST.get(name,0),share_units=1,ownership=own,tax_loss=0,loss_vintages=[],loan=52 if name=='jinjiang' else 38 if name=='jinxiang' else 0,div_receivable=0,dividend_payable=0,nci_equity=23.9459537*ew/.045 if own<1 else 0)
    # Test-only opening values remain on the very same calculation chain.
    if start and 'states' in start: state=copy.deepcopy(start['states'])
    for y in range(1,horizon+1):
        oldr=r;g=p['growth'][y-1] if y<=5 else p['tail_growth']+max(0,11-y)/5*(p['growth'][-1]-p['tail_growth'])
        r*=1+g
        m=p['margin'][y-1] if y<=5 else p['tail_margin']+max(0,11-y)/5*(p['margin'][-1]-p['tail_margin'])
        yr=dict(year=y,revenue=r,growth=g,ebit_margin_budget=m,entities={},shares_open=shares)
        begin_cash=sum(a['cash'] for a in state.values());external_cf=0;group_profit=0;minority=0;new_decl=0;upcash=0;subcontrib=0;internal_interest=0
        for name,own,reg,paid,aw,ew,tax in entries:
            s=state[name];o=copy.deepcopy(s);parent=name=='parent'
            dep=s['asset']/p['life'];refdep=s['asset']/13
            ebit=r*m*ew+refdep-dep
            target=r*p['capital_ratio']*aw
            maintain=dep*p['maintenance'];growthcap=max(0,target-s['asset']+dep-maintain)
            capex=maintain+growthcap
            # H1 unpaid engineering obligation is not in physical stock cash; pay once.
            engineering=p['engineering']*aw if y==1 else 0
            # Paid preconstruction (already in 2800 physical stock) is never paid twice.
            wc=r*p['wc_ratio']*ew+(p['extra_wc']*ew if y==1 or (p['extra_wc_release']==0 and y>=1) or (1<y<p['extra_wc_release']) else 0)
            other_close=other_working_capital(y,r,p,ew) if not start else s.get('other_wc',{})
            other_open=s.get('other_wc',{});other_delta=sum(other_close.values())-sum(other_open.values());s['other_wc']=other_close
            dwc=wc-s['wc']+other_delta;floor=max(r*p['cash_floor']*ew,p['parent_min_cash']*r/5900 if parent else 0)
            deposit=max(s['cash'],0)*p['deposit'];interest=s['debt']*p['loan_rate']+s['credit']*.06
            internal=s['loan']*p['internal_rate'];internal_interest+=internal
            taxable=ebit+deposit-interest-internal
            rate=tax if tax==0 or name=='thai' else (tax if y<=1 else min(.25,tax+(.25-tax)*min(1,(y-1)/4)))
            taxpaid,loss_used,tax_buckets=income_tax_buckets(s,ebit,deposit,interest,internal,rate,y,tax==0)
            profit=taxable-taxpaid
            repay=min(s['debt'],(p['parent_debt'] if parent else (initial['debt']-p['parent_debt'])*aw/.6)/5) if y<=5 else s['debt']
            gross_due=max(repay,s['debt']*(.50 if y<=4 else 1))
            refinanced=max(0,gross_due-repay) if p['rollover'] else 0
            repay=gross_due-refinanced
            credit_repay=s['credit'] if y==p['loan_due'] else 0
            loanrep=min(s['loan'],(52 if name=='jinjiang' else 38 if name=='jinxiang' else 0)/8) if y<=8 else 0
            s['loan']-=loanrep
            s['cash']+=profit+dep-capex-dwc-engineering-repay-credit_repay-loanrep
            s['debt']-=repay;s['credit']-=credit_repay;s['asset']+=capex-dep;s['wc']=wc
            s['rp'],s['reserve'],reserve_add,loss_cover=legal(s['rp'],s['reserve'],s['reg'],profit,p['thai_reserve_rate'] if name=='thai' and not p['legacy'] else .10,p['thai_reserve_cap'] if name=='thai' and not p['legacy'] else .50)
            record=dict(other_wc_delta=other_delta,other_wc_open=other_open,other_wc_close=other_close,tax_buckets=tax_buckets,open=o,ebit=ebit,profit=profit,tax=taxpaid,tax_rate=rate,accounting_profit_before_tax=taxable,taxable=tax_buckets['ordinary_taxable_income'],tax_loss_used=loss_used,deposit_interest=deposit,external_interest=interest,internal_interest=internal,depreciation=dep,maintenance=maintain,growth_capex=growthcap,capex=capex,engineering_paid=engineering,wc_delta=dwc,cash_floor=floor,debt_gross_due=gross_due,debt_refinanced=refinanced,debt_repayment=repay,credit_repayment=credit_repay,internal_principal_paid=loanrep,loss_covered=loss_cover,reserve_added=reserve_add,subscription=0,minority_subscription=0,credit_draw=0,dividend_declared=0,dividend_paid=0,old_receivable_collected=0)
            yr['entities'][name]=record
            group_profit+=profit;minority+=profit*(1-s['ownership']);external_cf+=profit+dep-capex-dwc-engineering-repay-credit_repay+internal
        par=state['parent'];pr=yr['entities']['parent']
        # Existing intercompany principal returns cash only. New interest is taxable parent income,
        # and tax benefit at debtor is conditioned on that debtor's actual current taxable income.
        collected=sum(v['internal_principal_paid'] for v in yr['entities'].values())
        par['cash']+=collected+internal_interest
        extra_tax,internal_loss_used=cash_tax(par,internal_interest,pr['tax_rate'],y)
        par['cash']-=extra_tax;interestnet=internal_interest-extra_tax
        par['rp'],par['reserve'],a,b=legal(par['rp'],par['reserve'],par['reg'],interestnet)
        pr['reserve_added']+=a;pr['profit']+=interestnet;pr['tax']+=extra_tax;pr['internal_interest_received']=internal_interest;pr['internal_principal_received']=collected
        group_profit+=interestnet;external_cf-=extra_tax
        # Settle already-recognised parent-to-Shiye trading balances, no new P&L.
        settlement=p['settlement'] if y==1 else 0
        par['cash']-=settlement;state['shiye']['cash']+=settlement
        pr['old_trade_paid']=settlement;yr['entities']['shiye']['old_trade_received']=settlement
        # All subsidiaries: finite proportionate cash capital when otherwise below floor.
        for name,own,reg,paid,aw,ew,tax in entries:
            if name=='parent':continue
            s=state[name];v=yr['entities'][name];floor=v['cash_floor']
            need=max(0,floor-s['cash'])
            if need>1e-8:
                total=min(need,max(0,p['subscription_cap']-cum_sub))
                cum_sub+=total;parentpay=total*s['ownership'];ncipay=total-parentpay
                par['cash']-=parentpay;s['cash']+=total;s['paid_budget']+=total;s['reg']+=total;s['investment_cost']+=parentpay;s['share_units']*=1+total/max(s['reg']-total,1e-9);s['nci_equity']+=ncipay
                # Proportionate subscription: ownership unchanged; actual cash and capital both rise.
                v['subscription']=total;v['minority_subscription']=ncipay;external_cf+=ncipay;subcontrib+=parentpay
            if s['cash']<floor-1e-7:fail=dict(year=y,entity=name,reason='cash_below_required_floor_even_at_zero_dividend',cash=s['cash'],floor=floor)
        # Subsidiary dividends use their own reserve/accumulated P&L and cash.
        # Pending last-year declarations are paid before new declarations.
        for name,own,reg,paid,aw,ew,tax in entries:
            if name=='parent':continue
            s=state[name];v=yr['entities'][name];floor=v['cash_floor']
            payold=settle_old_dividend(s,par,floor)
            upcash+=payold*s['ownership'];v['old_receivable_collected']=payold
            if s['dividend_payable']>1e-7:fail=dict(year=y,entity=name,reason='declared_dividend_overdue',unpaid=s['dividend_payable'])
            available=max(0,s['cash']-floor);decl=min(max(s['rp'],0),available)*p['upstream']
            s['rp']-=decl;new_decl+=decl*s['ownership'];par['rp']+=decl*s['ownership'] if p['legacy'] else 0
            # Dividend from domestic subsidiaries exempt; Thai assumed withholding 10% on repatriation.
            wht=decl*s['ownership']*.10 if name=='thai' else 0;par['rp']-=wht if p['legacy'] else 0;external_cf-=wht
            if not p['legacy']:group_profit-=wht
            if p['lag']:
                s['dividend_payable']+=decl;par['div_receivable']+=decl*s['ownership'];par['cash']-=wht
            else:
                s['cash']-=decl;par['cash']+=decl*s['ownership']-wht;upcash+=decl*s['ownership'];v['dividend_paid']=decl
            v['dividend_declared']=decl
            # Minority distributions actually paid leave group cash; declared accrual tracked.
            nci_paid=(payold+(decl if not p['lag'] else 0))*(1-s['ownership'])
            external_cf-=nci_paid;s['nci_equity']+=v['profit']*(1-s['ownership'])-decl*(1-s['ownership'])
        # Parent reserve on subsidiary new declarations, not old receivable collection.
        # Parent reserve cap already achieved except genuinely issued new capital; apply only shortage.
        if p['legacy']:
            reserve_on_div=min(max(0,par['reg']*.5-par['reserve']),max(new_decl,0)*.10)
            par['rp']-=reserve_on_div;par['reserve']+=reserve_on_div
        else:
            net_new_div=new_decl-sum(v['dividend_declared']*state[n]['ownership']*.10 for n,v in yr['entities'].items() if n=='thai')
            par['rp'],par['reserve'],reserve_on_div,div_loss_cover=legal(par['rp'],par['reserve'],par['reg'],net_new_div)
        pr['reserve_on_new_dividend']=reserve_on_div
        # Finite periodic surplus-capital realization after debt payoff; production continues.
        # Book cost recovery is not dividend income. Minority cash and fees leave the group.
        for name,s in state.items():
            rec=dict(gross=0,fee=0,parent_cash=0,minority_cash=0,basis_recovered=0,parent_gain=0,parent_tax=0,registered_reduced=0,units_cancelled=0)
            if name!='parent' and y>=p['release_year'] and (y-p['release_year'])%p['release_interval']==0 and not p['legacy'] and not fail:
                rec=capital_return(s,yr['entities'][name]['cash_floor'],max(p['release_fee'],.05) if name=='thai' else p['release_fee'],min_registered=s['registered_initial']*(.25 if name=='thai' else .20))
                par['cash']+=rec['parent_cash']
                par['rp'],par['reserve'],ra,lc=legal(par['rp'],par['reserve'],par['reg'],rec['parent_gain']-rec['parent_tax'])
                external_cf-=rec['minority_cash']+rec['fee']+rec['parent_tax']
                group_profit-=rec['fee']+rec['parent_tax'];minority-=rec['fee']*(1-s['ownership'])
            yr['entities'][name]['capital_return']=rec
        # Refund failed tranches: seed is CY2026 adjusted profit; subsequent CY approximation
        # comes from model annual ordinary profit, not market price or management target.
        refund=cancel=0
        if y<=3:
            if y>1: score+=max(0,group_profit-minority)
            target=[850,1850,3100][y-1];vest=1 if score>=target else .8 if score>=.9*target else 0
            cancel=2.999*[.4,.3,.3][y-1]*(1-vest);refund=cancel*35.18*(1+.01*y)
            par['cash']-=refund;shares-=cancel;par['paid_budget']-=cancel;par['reg']-=cancel;external_cf-=refund
        pr['refund_paid']=refund;pr['shares_cancelled']=cancel;pr['parent_subscriptions']=subcontrib
        # Only a capped short bridge; expires Y6, cannot perpetually refinance failure.
        floor=pr['cash_floor'];need=max(0,floor-par['cash']);draw=0
        if y<=p['credit_until'] and need>0:
            draw=min(need,max(0,p['loan_cap']-cum_credit));cum_credit+=draw;par['cash']+=draw;par['credit']+=draw;external_cf+=draw
        pr['credit_draw']=draw
        if par['cash']<floor-1e-7:fail=dict(year=y,entity='parent',reason='cash_below_required_floor_even_at_zero_dividend',cash=par['cash'],floor=floor)
        ordinary_target=max(0,group_profit-minority)*(.45 if y<=5 else .80)
        ordinary=min(ordinary_target,max(par['rp'],0),max(par['cash']-floor,0)) if not fail else 0
        par['cash']-=ordinary;par['rp']-=ordinary
        # Extra retained cash paid gradually, same legal profit pool; never a Y5 balance add-on.
        special=min(max(par['cash']-floor,0)*(.0 if y<=5 else .50),max(par['rp'],0)) if not fail else 0
        par['cash']-=special;par['rp']-=special;div=ordinary+special;external_cf-=div
        end_cash=sum(s['cash'] for s in state.values());error=end_cash-begin_cash-external_cf
        assert abs(error)<1e-5*max(1,abs(end_cash)),(y,error)
        for name,s in state.items():
            v=yr['entities'][name];v['close']=copy.deepcopy(s)
            if not fail:assert s['cash']>=v['cash_floor']-1e-6 and s['reserve']>=0 and s['paid_budget']>=0
        dps=div/shares
        yr.update(group_profit=group_profit,minority_profit=minority,common_profit=group_profit-minority,upstream_new_profit=new_decl,upstream_cash=upcash,ordinary=ordinary,special=special,dividend_per_share=dps,shares_close=shares,cash_open=begin_cash,cash_close=end_cash,cash_flow_external=external_cf,cash_conservation_error=error,failure=copy.deepcopy(fail))
        records.append(yr)
        if fail:break
        pv+=dps/(1+p['rate'])**y
        if y>5:tail+=dps/(1+p['rate'])**(y-5)
    return dict(parameters=p,initial=initial,entity_inputs=[list(x) for x in entries],horizon=horizon,feasible=not fail,failure=fail,pv_per_share=pv if not fail else None,tv5_per_share=tail if not fail else None,distributions=[v['dividend_per_share'] for v in records[:5]],terminal_pv_share=(tail/(1+p['rate'])**5/pv if pv and not fail else None),years=records if rows else [],last_state=state)

def tests():
    # Production legal function hand checks: previous loss -20, profit50 -> 3 reserve, RP27.
    assert legal(-20,0,100,50)==(27,3,3,20)
    assert legal(5,49,100,30)==(34,50,1,0)
    assert legal(0,0,100,-10)==(-10,0,0,0)
    zero=dict(cash=0,debt=0,credit=0,asset=0,wc=0,rp=0,reserve=0,reg=0,paid_budget=0,investment_cost=0,share_units=1,ownership=1,tax_loss=0,loss_vintages=[],loan=0,div_receivable=0,dividend_payable=0,nci_equity=0)
    hand=run(dict(growth=[0]*5,margin=[.1]*5,capital_ratio=0,wc_ratio=0,cash_floor=0,parent_min_cash=0,deposit=0,loan_rate=0,internal_rate=0,upstream=1,settlement=0,engineering=0,refund_seed=1000),horizon=1,entities=[('parent',1,0,0,.5,.5,0),('shiye',1,0,0,.5,.5,0)],start=dict(revenue=100,asset=0,wc=0,cash=0,debt=0,shares=100,states={'parent':copy.deepcopy(zero),'shiye':copy.deepcopy(zero)}))
    # EBIT10, legal profit10, ordinary cash4.5, parent residual5.5, per-share .045.
    assert hand['feasible'] and abs(hand['distributions'][0]-.045)<1e-12 and abs(hand['last_state']['parent']['cash']-5.5)<1e-12
    # Registered capital, not the separate paid budget, sets the PRC reserve threshold.
    assert legal(0,5,20,10)==(9,6,1,0)
    assert legal(0,10,20,10)==(10,10,0,0)
    assert legal(0,10,40,10)==(9,11,1,0) # registration actually increases first
    assert legal(-8,0,20,10)==(1.8,.2,.2,8)
    assert legal(0,0,20,10,.05,.10)==(9.5,.5,.5,0) # Thai-specific condition
    lossstate={'loss_vintages':[]}
    assert cash_tax(lossstate,-10,.25,1)==(0,0)
    assert cash_tax(lossstate,6,.25,2)==(0,6)
    assert cash_tax(lossstate,10,.25,7)==(2.5,0)
    # Same production tax chain: exempt operating loss cannot shield deposit interest.
    bucketstate={'loss_vintages':[]}
    tx,used,buckets=income_tax_buckets(bucketstate,-100,4,2,3,0,1,True)
    assert tx==1 and used==0 and bucketstate['tax_loss']==0 and buckets['qualified_operating_income']==-105
    assert income_tax_buckets({'loss_vintages':[]},100,4,2,3,0,1,True)[0]==1
    assert income_tax_buckets({'loss_vintages':[]},100,4,2,3,.25,1,False)[0]==24.75
    assert abs(sum(OTHER_WC.values())+176.59836473)<1e-9
    ow=dict(BASE,other_wc_mode='runoff',other_wc_years=1)
    assert sum(other_working_capital(1,5900,ow).values())==0
    assert sum(other_working_capital(1,5900,BASE).values())==sum(OTHER_WC.values())
    # Positive cash with no distributable profit can return capital after priority claims.
    k=dict(cash=100,debt=0,credit=0,dividend_payable=0,rp=0,reg=100,paid_budget=100,investment_cost=80,ownership=.8,share_units=1,nci_equity=20)
    cr=capital_return(k,20,.02)
    assert abs(cr['gross']-80/1.02)<1e-10 and abs(cr['parent_gain'])<1e-10
    assert abs(k['cash']-20)<1e-10 and abs(k['share_units']-(1-cr['gross']/100))<1e-10
    assert abs(cr['parent_cash']+cr['minority_cash']+cr['fee']-80)<1e-10
    assert k['rp']==-cr['fee'] # principal never becomes new distributable profit
    qk=dict(k);qk.update(cash=100,debt=1);assert capital_return(qk,20)['gross']==0
    assert capital_return(k,20)['gross']==0 # no double realization
    oldsub=dict(cash=20,dividend_payable=10,ownership=.8,rp=0)
    oldpar=dict(cash=5,div_receivable=8,rp=-4)
    assert settle_old_dividend(oldsub,oldpar,5)==10
    assert oldpar==dict(cash=13,div_receivable=0,rp=-4)
    b=run(rows=False);f=run(SCEN['failure']);assert not f['feasible'] and f['pv_per_share'] is None and f['tv5_per_share'] is None
    # Real cash model identity: no terminal financial-asset plug, TV is exactly later dividends.
    q=run(horizon=10);assert abs(q['pv_per_share']-sum(q['distributions'][i]/1.095**(i+1) for i in range(5))-q['tv5_per_share']/1.095**5)<1e-9
    return dict(legal_hand_checks=True,real_chain_hand_dps=hand['distributions'][0],real_chain_hand_parent_cash=hand['last_state']['parent']['cash'],real_failure=f['failure'],ten_year_same_chain=True,registered_not_paid=True,thai_rule=True,capital_return_principal_fees_priority_shares=True,old_receivable_cash_only=True,no_instant_loss_tax_refund=True,agricultural_and_financial_tax_buckets=True,other_wc_runoff_and_fixed_actual_function=True)

def generate():
    result={n:run(v) for n,v in SCEN.items()}
    assert result['tv_low']['years'][:5]==result['tv_high']['years'][:5]==result['base']['years'][:5]
    # Independent economic method: no-growth productive earning-power replacement budget.
    epv=[]
    for revenue,ebit,tax,maintenance_excess,cost in [(6000,.12,.24,25,.095),(6200,.13,.24,20,.09)]:
        cash=revenue*ebit*(1-tax)-maintenance_excess
        # All debt incl leases, unrestricted cash less operating liquidity, NCI economic claim,
        # engineering payable and existing restricted-share refunds consistently deducted.
        equity=cash/cost+251.15336155-210-997.84723323-23.9459537-89.39749-105.50482
        epv.append(dict(revenue=revenue,ebit=ebit,tax=tax,maintenance_excess=maintenance_excess,asset_cost=cost,fcff=cash,equity=equity,value=equity/267.187388))
    conv={str(h):run(horizon=h,rows=False)['pv_per_share'] for h in [120,180,220,300]}
    effects={}
    for n,z in result.items():
        diffs=[a['year'] for a,b in zip(z['years'],result['base']['years']) if a!=b]
        cashdiff=[a['year'] for a,b in zip(z['years'],result['base']['years']) if abs(a['dividend_per_share']-b['dividend_per_share'])>1e-12 or abs(a['cash_close']-b['cash_close'])>1e-8]
        effects[n]=dict(declared_input_start=6 if n.startswith('tv_') else z['parameters']['release_year'] if 'release' in n and not n.startswith('structural') else 1,actual_first_annual_change=diffs[0] if diffs else None,actual_first_distribution_or_cash_change=cashdiff[0] if cashdiff else None,changed_parameters=SCEN[n],unchanged_parameters='all other BASE entries; financing/dividends recomputed, not frozen',scope='real entities in entity_inputs; no product line is a legal person')
    return dict(scenario_effective_years=effects,other_wc_opening_components=OTHER_WC,identity=dict(symbol=SYMBOL,name=NAME,period=PERIOD),schema='entity-distributable-cash-v3',units='CNY million and million shares; per share CNY',scenarios=result,independent_economic_method=epv,convergence=conv,tests=tests())

def canonical(o):return json.dumps(o,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode()
if __name__=='__main__':
    if '--expand' in sys.argv:
        i=sys.argv.index('--expand');p=json.load(open(sys.argv[i+1]));raw=(lzma.decompress if p['schema']=='xz-base64-json-v1' else gzip.decompress)(base64.b64decode(p['payload']))
        assert hashlib.sha256(raw).hexdigest()==p['expanded_canonical_sha256'];open(sys.argv[i+2],'wb').write(raw);sys.exit()
    obj=generate();raw=canonical(obj);out=sys.argv[sys.argv.index('--output')+1] if '--output' in sys.argv else str(Path(__file__).with_name('2026-Q3-output.json'))
    if len(raw)>16000000:
        packed=dict(identity=dict(symbol=SYMBOL,name=NAME,period=PERIOD),schema='xz-base64-json-v1',expanded_canonical_sha256=hashlib.sha256(raw).hexdigest(),summary={k:{z:v[z] for z in ['feasible','pv_per_share','tv5_per_share','distributions']} for k,v in obj['scenarios'].items()},payload=base64.b64encode(lzma.compress(raw,preset=9)).decode())
        assert lzma.decompress(base64.b64decode(packed['payload']))==raw
        raw=canonical(packed)
    open(out,'wb').write(raw)
    print(json.dumps({k:{z:v[z] for z in ['feasible','pv_per_share','tv5_per_share','distributions','failure']} for k,v in obj['scenarios'].items()},ensure_ascii=False,indent=2))

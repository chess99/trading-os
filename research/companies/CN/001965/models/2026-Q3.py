#!/usr/bin/env python3
"""001965 finite-rights ordinary-equity budget. Standard library; no file inputs.
Run from any directory: python /path/2026-Q3.py [--output /path/output.json]
Readable complete years: python /path/2026-Q3.py --expand --output 2026-Q3-expanded.json
Default JSON includes a readable scenario summary and gzip/base64 complete payload.
The expanded file uses explicit ENTITY_COLUMNS/PARENT_COLUMNS; no economic fields are dropped.
All amounts CNY billion except per-share. Full rows use lossless columnar encoding.
"""
import argparse, copy, json, math, gzip, base64, hashlib
from datetime import date
from pathlib import Path
SHARES=6.795094992
ROAD_DATA=[
 ['甬台温',1.06696,2030,.51],['北仑港',.38956,2027,1],['九瑞',.25011,2040,1],['桂兴',.32554,2042,1],['桂阳',.30667,2037,1],['阳平',.20975,2037,1],['灵三',.07092,2038,1],['京津塘旧权',.58896,2029,1],['鄂东',.23270,2040,.5461],['渝黔',.39909,2037,.6],['沪渝',.49581,2043,.6],['机场',.04146,2027,.6],['京台',.89823,2046,.95*.55],['岑兴',.74297,2038,.51*.66],['岑梧',.18631,2036,.51*.8319],['全兴',.28809,2038,.51*.66],['富砚',.46728,2038,.51*.90],['垫忠',.29280,2035,.51*.80],['绵遂',.29487,2040,.51],['平正',.13291,2038,.51],['德商',.49246,2033,.51],['榆神',.52515,2041,.51],['神佳米',.06656,2046,.51]]
REGISTERED={'甬台温':1,'北仑港':.64436378191,'九瑞':.832,'桂兴':1.03,'桂阳':1.13,'阳平':.82,'灵三':.5439,'鄂东':.1,'渝黔':.8,'沪渝':.9175,'京台':.5,'岑兴':1.80705,'岑梧':.1202,'全兴':.677,'富砚':.4,'垫忠':1.49341273747,'绵遂':1.64,'平正':.528,'德商':.1,'榆神':.40476,'神佳米':.2}
ENTITY_COLUMNS=['year','id','opening_cash','revenue','operating_cash_before_tax_interest','depreciation','interest','cash_tax','profit','capital_spend','debt_repayment','equity_paid_in','minority_paid_in','reserve_add','ordinary_dividend','liquidation_cash','ending_cash','cash_floor','debt','paid_capital','reserve','legal_retained','parent_exit_accounting_basis_budget','loss_carry','registered_capital','cumulative_support','object_kind','economic_remittance_capacity','unremitted_cash','exit_gross','exit_fee','exit_tax']
PARENT_COLUMNS=['year','opening_cash','declared_income','equity_method_adjustment','actual_receipts','old_AR_collection','new_AR','capital_calls','new_project_capex','new_borrowing','old_debt_repayment','new_debt_repayment','perpetual_redemption','interest','perpetual_coupon','financial_interest','direct_operating_cash','head_office_cost','direct_cash_tax','legal_profit','reserve_add','ordinary_distribution','liquidation_distribution','ending_cash','cash_floor','legal_retained','reserve','old_debt','new_debt','perpetual','AR','tech_cash_support_and_exit_cost','financial_dividend','financial_asset_and_tech_cash_release','old_JJT_operating_cash','old_JJT_depreciation','old_JJT_maintenance','old_JJT_cash_floor','JV_direct_equity_profit','JV_intermediate_cash_income','final_debt_settlement','capital_return','capital_return_fee','ending_shares','ending_registered_capital','cancelled_shares','liquidation_fee','capital_reserve','statutory_loss_offset','capital_reserve_loss_offset','voluntary_reserve_add']

# H1 mother-only cost-method carrying amounts, note p164; not registered capital.
DIRECT_PARENT_BOOK={'甬台温':1.84335172986,'九瑞':.3966329,'桂兴':1.2732992,'桂阳':1.092258,'阳平':.5964915,'灵三':0.,'鄂东':1.22177612233,'渝黔':1.19498463402,'沪渝':.55091385443}
ZHONGTIE_NAMES=['岑兴','岑梧','全兴','富砚','垫忠','绵遂','平正','德商','榆神','神佳米']
FINAL_DATES={'甬台温':(2030,9,30),'桂兴':(2042,6,19),'桂阳':(2037,10,18),'阳平':(2037,9,4),'灵三':(2038,6,16),'鄂东':(2040,12,15),'渝黔':(2037,6,3),'沪渝':(2044,3,10),'岑兴':(2038,2,6),'岑梧':(2036,3,25),'全兴':(2038,9,16),'绵遂':(2040,12,29)}
def correct_basis(states):
    group_revenue=sum(x['r'] for x in states if x['id'] in ZHONGTIE_NAMES)
    for st in states:
        n=st['id']
        if n in DIRECT_PARENT_BOOK:st['basis']=DIRECT_PARENT_BOOK[n]/st['share']
        elif n=='京台':st['basis']=3.56/st['share'] # whole holding-cost allocation budget, NOT subsidiary legal basis
        elif n in ZHONGTIE_NAMES:st['basis']=5.76504897992*st['r']/group_revenue/st['share']
        # Beilun not separately in mother cost note: prior 2x revenue remains an explicit sensitivity budget.

def tax_charge(pre, losses, yr):
    remaining=max(0,pre); out=[]
    for when,amount in losses:
        if yr-when>5:continue
        used=min(remaining,amount);remaining-=used
        if amount-used>0:out.append((when,amount-used))
    if pre<0:out.append((yr,-pre))
    return remaining*.25,out

def legal_add(ret,res,registered,profit):
    available=max(0,profit+min(0,ret))
    add=min(.1*available,max(0,.5*registered-res))
    return ret+profit-add,res+add,add

def entity_step(s,year,operating,capmult=1,legal_scale=1):
    """Single legal pool, no cross-entity cash or loss offsets. Sponsor cash calls explicit."""
    s.setdefault('registered',s['paid']);s.setdefault('support_used',0.)
    start=s['cash']; row=dict.fromkeys(ENTITY_COLUMNS,0);row.update(year=year,id=s['id'],opening_cash=start,registered_capital=s['registered'],object_kind='domestic_legal_entity_budget',cumulative_support=s['support_used'])
    if year>s['end']+1:
        row.update(ending_cash=0,paid_capital=s['paid'],reserve=s['res'],legal_retained=s['ret'],parent_exit_accounting_basis_budget=s['basis']);return row,0,0,0,0,None
    if year==s['end']+1:
        gross=s.get('exit_gross',0)*s['r']; fee=s.get('exit_fee',0)*s['r']; exit_tax=gross*.25
        recovery=s['cash']-s['debt']+gross-exit_tax-fee
        row.update(exit_gross=gross,exit_fee=fee,exit_tax=exit_tax)
        if recovery< -1e-9:return row,0,0,0,0,'liquidation insolvent'
        gain=recovery-s['basis'];s['cash']=0;s['debt']=0;s['basis']=0
        s['paid']=s['registered']=s['res']=s['ret']=0
        row.update(liquidation_cash=recovery,ending_cash=0,exit_gross=gross,exit_fee=fee,exit_tax=exit_tax,registered_capital=0,paid_capital=s['paid'],reserve=s['res'],legal_retained=s['ret'])
        return row,recovery*s['share'],gain*s['share'],0,0,None
    trend=1.01**(year-2027)*(.96**max(0,year-2035) if s['jv'] else 1)
    fraction=s.get('final_fraction',1) if year==s['end'] else 1
    trend*=fraction
    revenue=s['r']*trend*operating
    op=.92*revenue-.20*s['r']*trend
    da=s['a']*trend*operating; interest=s['debt']*.03
    tax,s['losses']=tax_charge(op-da-interest,s['losses'],year)
    profit=op-da-interest-tax
    cap=(s['cap'] if s['jv'] else revenue*.03)*capmult
    repayment=min(s['amort'],s['debt']);s['debt']-=repayment
    before_injection=start+op-tax-interest-cap-repayment
    floor=s.get('floor',s['r']*.15)
    equity=max(0,floor-before_injection)
    s['support_used']+=equity
    s['cash']=before_injection+equity;s['paid']+=equity;s['registered']+=equity;s['basis']+=equity # funded, approved capital increase budget; not cashless registration
    s['ret'],s['res'],reserve_add=legal_add(s['ret'],s['res'],s['registered'],profit)
    distribution=min(max(0,s['ret']),max(0,s['cash']-floor))
    s['ret']-=distribution;s['cash']-=distribution
    equity_adjustment=(profit-distribution)*s['share'] if s['jv'] else 0
    if s['jv']:s['basis']+=profit-distribution
    assert abs(s['cash']-(start+op-interest-tax-cap-repayment+equity-distribution))<1e-8
    assert s['cash']>=floor-1e-9 and s['debt']>=-1e-9
    row.update(revenue=revenue,operating_cash_before_tax_interest=op,depreciation=da,interest=interest,cash_tax=tax,profit=profit,capital_spend=cap,debt_repayment=repayment,equity_paid_in=equity,minority_paid_in=equity*(1-s['share']),reserve_add=reserve_add,ordinary_dividend=distribution,ending_cash=s['cash'],cash_floor=floor,debt=s['debt'],paid_capital=s['paid'],reserve=s['res'],legal_retained=s['ret'],parent_exit_accounting_basis_budget=s['basis'],loss_carry=sum(v for _,v in s['losses']),registered_capital=s['registered'],cumulative_support=s['support_used'])
    return row,distribution*s['share'],distribution*s['share'],equity_adjustment,equity*s['share'],('cumulative equity support exceeds finite budget' if s['support_used']>s.get('support_limit',2)+1e-9 else None)

def jv_step(s,year,factor,capital=1,remit_cap=.8,realization=.8):
    """Economic attributable upflow budget, NOT a legal entity or statutory reserve pool.
    No fictitious registered/paid capital. Embedded debt/capital are diagnostic economics.
    Direct mother equity earnings are separate from mediated cost-method income.
    """
    row=dict.fromkeys(ENTITY_COLUMNS,0);start=s['cash']
    row.update(year=year,id=s['id'],opening_cash=start,object_kind='economic_upflow_budget',cumulative_support=s['support_used'])
    for k in ('paid_capital','registered_capital','reserve','legal_retained','reserve_add'):row[k]=None
    if year>s['end']+1:return row,0,0,0,0,None,0,0
    if year==s['end']+1:
        net=s['cash']-s['debt']
        if net<0:return row,0,0,0,0,'economic recovery insolvent',0,0
        recovery=net*realization
        # Sale/realisation of finite economic claim; not a declaration of corporate liquidation.
        gain=recovery-s['basis'];s['cash']=0;s['basis']=0;s['debt']=0
        row.update(liquidation_cash=recovery,ending_cash=0,parent_exit_accounting_basis_budget=0)
        return row,recovery,gain,0,0,None,0,0
    scale=1.01**(year-2027)*.96**max(0,year-2035)
    revenue=s['r']*scale*factor;idle_interest=max(0,start-s['floor'])*s.get('idle_yield',0)
    op=.92*revenue-.20*s['r']*scale+idle_interest
    da=s['a']*scale*factor;interest=s['debt']*.03
    tax,s['losses']=tax_charge(op-da-interest,s['losses'],year);profit=op-da-interest-tax
    cap=s['cap']*capital;repay=min(s['amort'],s['debt']);s['debt']-=repay
    free=start+op-tax-interest-cap-repay
    need=max(0,s['floor']-free);s['support_used']+=need
    available=max(0,free+need-s['floor'])
    capacity=max(0,profit)*remit_cap
    div=min(available,capacity)
    s['cash']=free+need-div
    assert abs(s['cash']-(start+op-tax-interest-cap-repay+need-div))<1e-9
    assert s['cash']>=s['floor']-1e-9
    # Calibrated parent-only equity-accounted income (H1 mother 2.073bn versus group2.457bn),
    # not group profit treated as mother's legal earnings.
    direct_profit=s['mother_profit']*profit/s['normal_profit']
    direct_div=div*s['direct_fraction'];mediated=div-direct_div
    eq=direct_profit-direct_div;s['basis']+=direct_profit-direct_div+need
    row.update(revenue=revenue,operating_cash_before_tax_interest=op,depreciation=da,interest=interest,cash_tax=tax,profit=profit,capital_spend=cap,debt_repayment=repay,equity_paid_in=need,ordinary_dividend=div,ending_cash=s['cash'],cash_floor=s['floor'],debt=s['debt'],parent_exit_accounting_basis_budget=s['basis'],loss_carry=sum(v for _,v in s['losses']),cumulative_support=s['support_used'],economic_remittance_capacity=capacity,unremitted_cash=max(0,s['cash']-s['floor']))
    err='cumulative economic support budget exceeded' if s['support_used']>s['support_limit']+1e-9 else None
    return row,div,div,eq,need,err,direct_profit,mediated


def initialize(legal_scale=1,jv_end=2044,support_limit=2):
    denominator=sum(r*(end-2026) for name,r,end,share in ROAD_DATA if name not in ['甬台温','北仑港','机场','京津塘旧权'])
    states=[];cash_den=sum(x[1] for x in ROAD_DATA if x[0]!='机场')
    for name,r,end,share in ROAD_DATA:
        if name in ('机场','京津塘旧权'):continue
        loan=.1 if name=='甬台温' else 0 if name=='北仑港' else 34.54045708778*r*(end-2026)/denominator
        revenue=r/1.03
        states.append(dict(id=name,r=revenue,end=end,share=share,debt=loan,amort=loan/(end-2026),cash=5*r/cash_den,paid=REGISTERED[name],registered=REGISTERED[name],res=REGISTERED[name]/2*legal_scale,ret=.5*revenue*legal_scale,basis=2*revenue,a=.25*revenue,jv=False,losses=[],support_used=0.,support_limit=support_limit))
    # The three rows partition economic claims, not legal entities. Book carrying amount
    # is Q3 58.72507353254; NH/WT H1 reported group carrying balances, remainder residual.
    data=[('宁沪归属预算',.57,.2,.30,5.74430412271,1.,.66),('皖通归属预算',.53,.2,.28,4.58365762669,261216477.72/316099701.72,.94),('其余参联营归属预算',3.85,1.3,2.72,48.39711178314,.85,2.55)]
    for name,p,amort,div,basis,direct,mp in data:
        debt=25*p/4.95; revenue=(p/.75+debt*.03+amort)/.72
        states.append(dict(id=name,r=revenue,end=jv_end,share=1.,debt=debt,amort=debt/(jv_end-2026),cash=.2*p,basis=basis,a=amort,floor=.2*p,cap=p+amort-div-debt/18,jv=True,losses=[],support_used=0.,support_limit=support_limit,mother_profit=mp,normal_profit=p,direct_fraction=direct))
    return states


def reduce_capital(available,shares,registered,limit=.5,fee_rate=.01):
    """Conditional equal-proportion nominal reduction, not dividend or free earnings.
    Available is AFTER cash provision for all existing debt and operating floor.
    Creditor process, shareholder approval and registration are scenario conditions.
    """
    amount=min(max(0,available)/(1+fee_rate),limit,max(0,registered-.1))
    cancelled=shares*amount/registered if registered else 0
    return amount,amount*fee_rate,cancelled,shares-cancelled,registered-amount

def run(rate=.075,toll=1.,capital=1.,cycle=False,structural=False,optimistic=False,credit_limit=12.5,opening_cash=4.,arrival_fraction=1.,legal_scale=1.,extra_payment=0.,project_right=True,jv_end=2044,initial_ar=.05,jv_remit_cap=.8,jv_realization=.8,support_limit=2,jv_embedded_debt=25,jv_parent_basis_factor=1,exit_gross=.05,exit_fee=.02,idle_yield=.015,capital_recovery=False,parent_exit_fee=.05,parent_loss_cover=0,project_exit_net=.03,basis_mode="source",voluntary_reserve_rate=0,precise_expiry=True,timing_stub=True,debt_shift_to_zhongtie=0):
    states=initialize(legal_scale,jv_end,support_limit)
    if basis_mode=='source':correct_basis(states)
    parent=[]; entity_rows=[]; errors=[]; funding_failures=[]; status=[]; shares=SHARES; registered=SHARES; capital_reserve=36.05897948415; eligible_loss_cover=parent_loss_cover
    for st in states:
        st.update(exit_gross=exit_gross,exit_fee=exit_fee,idle_yield=idle_yield)
        if precise_expiry and st['id'] in FINAL_DATES:
            y,mo,day=FINAL_DATES[st['id']];st['end']=y
            st['final_fraction']=(date(y,mo,day)-date(y,1,1)).days/((date(y+1,1,1)-date(y,1,1)).days)+1/((date(y+1,1,1)-date(y,1,1)).days)
            # Existing debt budget is retained; final contractual year determines level repayment term.
            st['amort']=st['debt']/(y-2026)
    # Allocation diagnostic: same total external road debt, no borrowing or cash transfer.
    # Positive delta moves opening debt from wholly-owned roads to Zhongtie roads.
    full=[st for st in states if not st['jv'] and st['share']==1 and st['debt']>0]
    zt=[st for st in states if st['id'] in ZHONGTIE_NAMES]
    source,target=(full,zt) if debt_shift_to_zhongtie>=0 else (zt,full)
    move=abs(debt_shift_to_zhongtie);den_source=sum(st['debt'] for st in source);den_target=sum(st['debt'] for st in target)
    assert move<=den_source+1e-12
    for st in source:st['debt']-=move*st['debt']/den_source;st['amort']=st['debt']/(st['end']-2026)
    for st in target:st['debt']+=move*st['debt']/den_target;st['amort']=st['debt']/(st['end']-2026)
    opening_road_debt={st['id']:st['debt'] for st in states if not st['jv']}
    for state in states:
        if state['jv']:
            state['basis']*=jv_parent_basis_factor
            delta=(jv_embedded_debt-25)*state['r']/sum(x['r'] for x in states if x['jv'])
            state['debt']+=delta;state['amort']=state['debt']/(jv_end-2026)
    old_jjt_cash=5*.58896/sum(x[1] for x in ROAD_DATA if x[0]!='机场')
    cash=opening_cash+old_jjt_cash;ret=12*legal_scale;res=3.45480841708;debt=18.4;newloan=0;perp=7.3;ar=initial_ar;used_credit=0
    for year in range(2027,2057):
        snapshot=copy.deepcopy(states); mother_snapshot=(cash,ret,res,debt,newloan,perp,ar,used_credit,shares,registered,capital_reserve,eligible_loss_cover); nrows=len(entity_rows)
        receipt=decl=eqprofit=calls=direct_jv=mediated_jv=0
        factor=toll
        if cycle:factor*={2027:.8,2028:.85,2029:.95}.get(year,1.)
        if structural:factor*=.85*.98**(year-2027)
        if optimistic:factor*=1.03**min(year-2027,5)
        for state in states:
            if state['jv']:
                row,received,income,eq,call,err,dp,mi=jv_step(state,year,factor,capital,jv_remit_cap,jv_realization);direct_jv+=dp;mediated_jv+=mi
            else:row,received,income,eq,call,err=entity_step(state,year,factor,capital)
            entity_rows.append([row[k] for k in ENTITY_COLUMNS]);receipt+=received;decl+=income;eqprofit+=eq;calls+=call
            if err:errors.append([year,state['id'],err])
        begin=cash;oldar=ar;current_receipt=receipt*arrival_fraction;ar=receipt-current_receipt
        idx=year-2027; construction=([3.5,4,3.5,1.5][idx] if idx<4 else 0)*capital
        draw=min(construction*.8,max(0,credit_limit-used_credit));used_credit+=draw
        ni=newloan*.035;newloan+=draw
        repay_new=min(newloan,used_credit/25) if year>=2031 else 0;newloan-=repay_new
        oi=debt*.03;repay_old=min(debt,18.4/18);debt-=repay_old
        pc=perp*.035;redeem=min(perp,1.46) if 2032<=year<=2036 else 0;perp-=redeem
        project=(.75*1.01**(year-2031)*factor if 2031<=year<=2055 and project_right else 0)
        # Core/single-factor toll diagnostic affects existing roads/JV only, not new-road pricing.
        if not (cycle or structural or optimistic):project=(.75*1.01**(year-2031) if 2031<=year<=2055 and project_right else 0)
        depreciation=.62 if 2031<=year<=2055 else 0
        overhead=.18 if year<=2055 else 0
        fi=max(0,begin)*.015
        old_r=.58896/1.03*1.01**(year-2027) if year<=2029 else 0
        old_op=old_r*(.92*factor-.20);old_da=old_r*.25*factor;old_cap=old_r*factor*.03*capital
        old_floor=.58896/1.03*.15 if year<=2029 else 0
        operating_profit=project+old_op-depreciation-old_da-overhead-oi-ni+fi
        # No cross-company or immediate negative-tax refund. Conservative no parent tax loss benefit.
        ct=max(0,operating_profit)*.25
        techcost=.08 if year<=2031 else .2 if year==2032 else 0
        financial=.03 if year<=2032 else 0
        assetcash=(.84979999762+1.03215890687 if year==2032 else 0)+(project_exit_net if year==2056 else 0)
        legal_profit=decl+eqprofit+operating_profit-ct-pc-techcost+financial
        prior_ret=ret
        ret,res,added=legal_add(ret,res,registered,legal_profit)
        voluntary_add=max(0,voluntary_reserve_rate*max(0,legal_profit+min(0,prior_ret))-added)
        ret-=voluntary_add;res+=voluntary_add
        offset_statutory=offset_capital=0.
        if parent_loss_cover>0 and year>=2045 and ret<0:
            offset_statutory=min(-ret,res);res-=offset_statutory;ret+=offset_statutory
            offset_capital=min(-ret,capital_reserve,eligible_loss_cover);capital_reserve-=offset_capital;eligible_loss_cover-=offset_capital;ret+=offset_capital
        cash+=current_receipt+oldar+project+old_op-old_cap-overhead-oi-ni-pc+fi-ct-construction+draw-repay_old-repay_new-redeem-calls-techcost+financial+assetcash-(extra_payment if year==2027 else 0)
        floor=(1.+old_floor) if year<=2055 else 0.
        bridge=min(max(0,floor-cash),max(0,credit_limit-used_credit)) if year<=2035 else 0
        draw+=bridge;used_credit+=bridge;newloan+=bridge;cash+=bridge
        if cash<floor-1e-9:errors.append([year,'母体','necessary cash floor shortfall',floor-cash])
        target=[.38,.39,.40,.41,.42][idx]*SHARES if idx<5 else max(0,cash-floor)
        ordinary=min(target,max(0,ret),max(0,cash-floor)) if year<=2055 and not errors else 0
        return_capital=0.; cancelled=0.; return_fee=0.
        if capital_recovery and ret>=0 and year>=2046 and year<=2055 and not errors:
            # Conditional pro-rata creditor-protected nominal capital reduction.
            # Reserve every remaining debt/perpetual face amount plus necessary cash.
            available=max(0,cash-ordinary-floor-debt-newloan-perp)
            return_capital,return_fee,cancelled,shares,registered=reduce_capital(available,shares,registered)
        liquidation=max(0,cash-debt-newloan-perp-parent_exit_fee) if year==2056 and not errors else 0
        liquidation_fee=parent_exit_fee if year==2056 and not errors else 0
        if year==2056 and cash-debt-newloan-perp-parent_exit_fee< -1e-9:errors.append([year,'母体','insolvent liquidation'])
        settled=debt+newloan+perp if year==2056 and not errors else 0
        if year==2056 and not errors:debt=newloan=perp=0.
        cash-=ordinary+liquidation+settled+return_capital+return_fee+liquidation_fee;ret-=ordinary
        if year==2056 and not errors:shares=registered=0.
        row=[year,begin,decl,eqprofit,current_receipt,oldar,ar,calls,construction,draw,repay_old,repay_new,redeem,oi+ni,pc,fi,project,overhead,ct,legal_profit,added,ordinary,liquidation,cash,floor,ret,res,debt,newloan,perp,ar,techcost,financial,assetcash,old_op,old_da,old_cap,old_floor,direct_jv,mediated_jv,settled,return_capital,return_fee,shares,registered,cancelled,liquidation_fee,capital_reserve,offset_statutory,offset_capital,voluntary_add]
        parent.append(row)
        check=begin+current_receipt+oldar+project+old_op-old_cap-overhead-oi-ni-pc+fi-ct-construction+draw-repay_old-repay_new-redeem-calls-techcost+financial+assetcash-(extra_payment if year==2027 else 0)-ordinary-liquidation-settled-return_capital-return_fee-liquidation_fee
        assert abs(cash-check)<1e-8
        assert ordinary<=max(0,ret+ordinary)+1e-8
        if errors:
            # Atomic annual funding gate: an unfunded plan is NOT an executed capital injection.
            # Preserve last funded assets, debts and shares; record proposed obligations separately.
            funding_failures.append({'year':year,'unexecuted_parent_plan':dict(zip(PARENT_COLUMNS,row)),
                'unexecuted_entity_plans':[dict(zip(ENTITY_COLUMNS,r)) for r in entity_rows[nrows:]],
                'opening_funded_parent_state':list(mother_snapshot),'unpaid_due_interest_and_coupon':row[13]+row[14],
                'unpaid_project_contract_budget':construction,'unpaid_capital_calls':calls,'unpaid_exit_cost':sum(r[30] for r in entity_rows[nrows:])+(parent_exit_fee if year==2056 else 0),
                'legal_status':'unresolved funding/default; no presumption of forgiveness or rescue'})
            cash,ret,res,debt,newloan,perp,ar,used_credit,shares,registered,capital_reserve,eligible_loss_cover=mother_snapshot
            states=snapshot;parent.pop();del entity_rows[nrows:]
            for remaining_year in range(year,2057):
                pr=[0]*len(PARENT_COLUMNS);pr[0]=remaining_year;pr[1]=pr[23]=cash;pr[25]=ret;pr[26]=res
                pr[27:30]=[debt,newloan,perp];pr[30]=ar;pr[43]=shares;pr[44]=registered;pr[47]=capital_reserve;parent.append(pr)
                for st in states:
                    er=dict.fromkeys(ENTITY_COLUMNS,0);er.update(year=remaining_year,id=st['id'],opening_cash=st['cash'],ending_cash=st['cash'],debt=st['debt'],parent_exit_accounting_basis_budget=st['basis'],cumulative_support=st['support_used'],object_kind='unresolved_funding_snapshot')
                    for key,statekey in [('paid_capital','paid'),('registered_capital','registered'),('reserve','res'),('legal_retained','ret')]:er[key]=st.get(statekey)
                    entity_rows.append([er[k] for k in ENTITY_COLUMNS])
                status.append({'year':remaining_year,'state':'unresolved; balances preserved; no further cash payments assumed'})
            break
        status.append({'year':year,'state':'funded conditional budget'})
    distribution=[(r[21]+r[22]+r[41])/SHARES for r in parent]
    stub=((date(2027,12,31)-date(2026,10,26)).days/365.25-1) if timing_stub else 0
    pv=sum(d/(1+rate)**(i+1+stub) for i,d in enumerate(distribution)) if not errors else None
    tv=sum(d/(1+rate)**(i-4) for i,d in enumerate(distribution) if i>=5) if not errors else None
    return dict(feasible=not errors,errors=errors,opening_road_debt=opening_road_debt,funding_failures=funding_failures,annual_status=status,pv=pv,tv5=tv,D=distribution[:5],annual_distributions=distribution,parent=parent,entities=entity_rows,discount_rate=rate,discount_time_first_year=1+stub,terminal_pv_share=(tv/(1+rate)**(5+stub)/pv if pv else None))

def tests():
    # Same production legal/entity chain: 10 cash, 100 revenue, 72 operating,25 DA, no debt,
    # 11.75 tax,3 capex, floor15 =>52.25 cash dividend limited by 200 legal reserves.
    s=dict(id='hand',r=100,end=2028,share=.6,debt=0,amort=0,cash=10,paid=100,res=50,ret=200,basis=100,a=25,jv=False,losses=[])
    row,receipt,_,_,call,err=entity_step(s,2027,1)
    assert abs(row['ordinary_dividend']-52.25)<1e-10 and abs(receipt-31.35)<1e-10 and call==0 and err is None
    assert legal_add(-5,0,10,4)==(-1,0,0)
    assert legal_add(-5,0,10,10)==(4.5,.5,.5)
    assert legal_add(0,5,10,10)==(10,5,0)
    # Registered 20, actually paid 10: reserve must not stop at paid-capital 5.
    assert legal_add(0,5,20,10)==(9,6,1)
    failing=run(opening_cash=0,credit_limit=0,extra_payment=20)
    assert not failing['feasible'] and failing['pv'] is None and failing['tv5'] is None
    a=run(rate=.085);b=run(rate=.07)
    assert a['parent'][:5]==b['parent'][:5] and a['entities'][:5*24]==b['entities'][:5*24]
    assert len(a['annual_distributions'])==30
    ar_test=run(initial_ar=.15)
    assert abs(ar_test['parent'][0][19]-run()['parent'][0][19])<1e-12
    assert abs(ar_test['parent'][0][5]-run()['parent'][0][5]-.1)<1e-12
    cap_case=dict(id='capital_hand',r=1,end=2028,share=.6,debt=0,amort=0,cash=0,paid=1,res=.5,ret=0,basis=1,a=.25,jv=False,losses=[])
    cr,*_=entity_step(cap_case,2027,0)
    assert abs(cr['equity_paid_in']-.35)<1e-12 and abs(cr['minority_paid_in']-.14)<1e-12
    assert abs(cr['paid_capital']-1.35)<1e-12 and cr['ordinary_dividend']==0
    # Real continuous cumulative support counterexample: each call <2, aggregate>2.
    cc=dict(id='cumulative',r=1,end=2040,share=.6,debt=0,amort=0,cash=0,paid=1,res=.5,ret=0,basis=1,a=.25,jv=False,losses=[],support_limit=2)
    results=[]
    for y in range(2027,2038):
        rr,*rest=entity_step(cc,y,0);results.append(rest[-1]);assert rr['equity_paid_in']<2
    assert results[0] is None and results[-1] is not None and cc['support_used']>2
    assert all(x['id']!='京津塘旧权' for x in initialize())
    assert all('registered' not in x for x in initialize() if x['jv'])
    assert abs(sum(x['basis'] for x in initialize() if x['jv'])-58.72507353254)<1e-10
    assert run()['parent'][0][34]>0 and run()['parent'][3][34]==0
    assert all(r[24] is None for r in a['entities'] if r[26]=='economic_upflow_budget')
    reduction=reduce_capital(2.02,10,10,limit=2)
    assert reduction==(2, .02, 2.,8.,8.)
    assert legal_add(0,5,20,10)==(9,6,1) # newly registered 20 after conversion
    assert all(r[41]==0 for r in failing['parent'])
    assert failing['funding_failures'][0]['unpaid_project_contract_budget']>0
    assert all(r[11]==0 for r in failing['entities'])
    assert failing['parent'][-1][27]==18.4 and failing['parent'][-1][43]==SHARES
    ss=dict(id='recover',r=1,end=2026,share=.6,debt=.2,amort=0,cash=1,paid=1,registered=1,res=.5,ret=-10,basis=2,a=.25,jv=False,losses=[],exit_gross=.1,exit_fee=.02)
    rr,recv,income,_,call,err=entity_step(ss,2027,1)
    assert abs(recv-(1-.2+.1-.025-.02)*.6)<1e-12 and income<0 and call==0 and err is None
    assert rr['ordinary_dividend']==0 and rr['exit_fee']==.02
    assert ss['registered']==0 and ss['paid']==0
    fee_fail=run(exit_fee=100)
    assert not fee_fail['feasible'] and fee_fail['funding_failures'][0]['unpaid_exit_cost']>0
    cap_run=run(capital_recovery=True,parent_loss_cover=36.05897948415,jv_parent_basis_factor=.85)
    assert cap_run['feasible'] and sum(r[41] for r in cap_run['parent'])>0
    for r in cap_run['parent']:
        if r[41]>0:
            assert r[25]>=-1e-9 and r[23]>=sum(r[27:30])+r[24]-1e-9
            assert abs(r[41]-r[45])<1e-9 and abs(r[42]-.01*r[41])<1e-9
    # Same asset recovery with a different true ownership changes both proceeds and gain.
    low_share=dict(id='recover20',r=1,end=2026,share=.2,debt=.2,amort=0,cash=1,paid=1,registered=1,res=.5,ret=-10,basis=2,a=.25,jv=False,losses=[],exit_gross=.1,exit_fee=.02)
    _,recv20,gain20,*_=entity_step(low_share,2027,1)
    assert abs(recv20*3-recv)<1e-12 and abs(gain20*3-income)<1e-12
    # Short final-year operating cash truly changes the producing function, not just labels.
    partial=dict(id='partial',r=100,end=2027,share=.6,debt=0,amort=0,cash=10,paid=100,res=50,ret=200,basis=100,a=25,jv=False,losses=[],final_fraction=.5)
    pr,*_=entity_step(partial,2027,1);assert pr['revenue']==50 and pr['operating_cash_before_tax_interest']==36

    # Lossless transposition check, no rounding or numeric casts.
    rows=a['parent']; expanded=[dict(zip(PARENT_COLUMNS,r)) for r in rows]
    assert [[r[k] for k in PARENT_COLUMNS] for r in expanded]==rows
    return ['production hand case','loss-before-reserve','reserve cap','real funding failure null PV/TV','first-five full-state identity','30-year full tail','lossless compact expansion','old AR cash not profit','real capital paid and minority linkage','registered 20 vs paid 10 reserve threshold counterexample','cumulative support actual function counterexample','no old-JJT or JV fictitious statutory pools','Q3 JV carrying reconciliation','funding failure rolls back unpaid injections and preserves debt/shares/fee obligations','profit-limited capital recovery with exit tax and fees at60% interest','pro-rata nominal capital return with1% fees reduces shares and registered capital']

def compact(out):
    result=copy.deepcopy(out)
    pools={'parent':[],'entities':[]};indexes={'parent':{},'entities':{}}
    for run in result['runs'].values():
        for table in pools:
            ids=[]
            for row in run[table]:
                key=tuple(row)
                if key not in indexes[table]:indexes[table][key]=len(pools[table]);pools[table].append(row)
                ids.append(indexes[table][key])
            run[table+'_row_ids']=ids;del run[table]
    result['row_pools']=pools
    return result

def expand(compacted):
    result=copy.deepcopy(compacted);pools=result.pop('row_pools')
    for run in result['runs'].values():
        for table in pools:run[table]=[pools[table][i] for i in run.pop(table+'_row_ids')]
    return result

def build():
    checks=tests()
    cases={'base':{},'debt_to_ZT_1bn':{'debt_shift_to_zhongtie':1},'debt_from_ZT_1bn':{'debt_shift_to_zhongtie':-1},'debt_to_ZT_3bn':{'debt_shift_to_zhongtie':3},'debt_from_ZT_3bn':{'debt_shift_to_zhongtie':-3},'no_new_finance':{'credit_limit':0},'new_finance_10bn':{'credit_limit':10},'core_low':{'rate':.085},'core_high':{'rate':.07},'toll_down10':{'toll':.9},'capital_up20':{'capital':1.2},'cyclical':{'cycle':True},'structural':{'structural':True,'capital':1.2,'project_right':False},'optimistic':{'optimistic':True},'arrival_delay':{'arrival_fraction':.5},'legal_half':{'legal_scale':.5},'legal_zero':{'legal_scale':0},'net_payment_1bn':{'extra_payment':1},'cash_minus1bn':{'opening_cash':3},'cash_plus1bn':{'opening_cash':5},'AR_H1_upper':{'initial_ar':1.18137263668},'no_new_right':{'project_right':False},'JV_short_2038':{'jv_end':2038},'JV_long_2050':{'jv_end':2050},'funding_failure':{'opening_cash':0,'credit_limit':0,'extra_payment':20},'JV_remit_60':{'jv_remit_cap':.6},'JV_remit_100':{'jv_remit_cap':1.},'JV_realization_50':{'jv_realization':.5},'JV_realization_100':{'jv_realization':1.},'JV_debt_30':{'jv_embedded_debt':30},'support_limit_1':{'support_limit':1.},'support_limit_001_stress':{'support_limit':.01,'toll':.8},'JV_parent_basis_85':{'jv_parent_basis_factor':.85},'approved_capital_recovery':{'capital_recovery':True,'parent_loss_cover':36.05897948415},'limited_capital_recovery':{'capital_recovery':True,'parent_loss_cover':30},'no_capital_reduction':{'capital_recovery':False},'zero_residual_diagnostic':{'exit_gross':0,'exit_fee':0,'project_exit_net':0},'residual_double':{'exit_gross':.10,'exit_fee':.02,'project_exit_net':.06},'exit_cost_double':{'exit_fee':.04,'parent_exit_fee':.1},'exit_cost_unfunded':{'exit_fee':100},'no_idle_yield':{'idle_yield':0},'voluntary_reserve_10':{'voluntary_reserve_rate':.1},'rounded_expiry':{'precise_expiry':False},'no_date_stub':{'timing_stub':False},'approved_recovery_lower_basis':{'capital_recovery':True,'parent_loss_cover':36.05897948415,'jv_parent_basis_factor':.85},'old_cost_budget':{'basis_mode':'legacy'},'legacy_economics':{'basis_mode':'legacy','precise_expiry':False,'timing_stub':False,'exit_gross':0,'exit_fee':0,'idle_yield':0,'capital_recovery':False,'parent_exit_fee':0,'project_exit_net':0},'method_only_no_new_remit_cap':{'jv_remit_cap':100.,'jv_realization':1.}}
    runs={name:run(**args) for name,args in cases.items()}
    for result in runs.values():
        if result['feasible']:assert result['parent'][-1][23]==0 and sum(result['parent'][-1][27:30])==0
    for nm in ('debt_to_ZT_1bn','debt_from_ZT_1bn','debt_to_ZT_3bn','debt_from_ZT_3bn'):
        assert abs(sum(runs[nm]['opening_road_debt'].values())-sum(runs['base']['opening_road_debt'].values()))<1e-10
        assert runs[nm]['pv']!=runs['base']['pv']
    assert not runs['no_new_finance']['feasible'] and runs['no_new_finance']['errors'][0][0]==2028
    assert abs(runs['new_finance_10bn']['pv']-runs['base']['pv'])<1e-12 and max(abs(x-y) for a,b in zip(runs['new_finance_10bn']['parent'],runs['base']['parent']) for x,y in zip(a,b))<1e-10
    checks.append('actual same-total debt allocation shifts change interest amortisation cash minority and distributions;0 finance fails2028;10bn matches base')
    checks.append('all feasible terminal cash and debt fully settled, not residual stranded balances')
    # Independent economic method: adjusted carrying assets, no DCF output as input.
    # 2026Q3 common book NAV; rights and associates impairments applied before minority share.
    subgroup_bridges={};ownership={x[0]:x[3] for x in ROAD_DATA}
    for name,names,cost in [('Langfang',['京台'],3.56),('Zhongtie',ZHONGTIE_NAMES,5.76504897992)]:
        rr=[x for x in runs['base']['entities'] if x[1] in names]
        subgroup_bridges[name]={'net_parent_cash_pv_bn':sum((x[14]+x[15]-x[11])*ownership[x[1]]/1.075**(x[0]-2027+runs['base']['discount_time_first_year']) for x in rr),'undiscounted_net_parent_cash_bn':sum((x[14]+x[15]-x[11])*ownership[x[1]] for x in rr),'mother_investment_cost_book_bn':cost,'scope':'before parent overhead; finite existing rights, after debt/minority/capital calls; cost is not repayment promise'}
    common_book=77.31192316565-7.31637100457
    asset=[]
    project_npv=sum((.75*1.01**(y-2031)-max(0,.75*1.01**(y-2031)-.62)*.25)/1.075**(y-2026) for y in range(2031,2056))-sum(c/1.075**(i+1) for i,c in enumerate([3.5,4,3.5,1.5]))+.03/1.075**30
    project_npv/=1.075**((date(2027,12,31)-date(2026,10,26)).days/365.25-1)
    for right_factor,jv_factor in [(.65,.80),(.75,.90)]:
        # Group toll-right revaluation attributed 70% to parent, JV already common-owned claim.
        value=(common_book-84.64801138663*(1-right_factor)*.70-58.72507353254*(1-jv_factor)+project_npv)/SHARES
        asset.append(value)
    return {'schema':'finite_owner_cash_v3','name':'招商公路','ticker':'CN:001965','information_cutoff':'2026-10-26','units':'CNY bn; shares bn; PV/TV/D CNY per common share','row_encoding':'lossless arrays under explicit columns; all years retained even infeasible','parent_columns':PARENT_COLUMNS,'entity_columns':ENTITY_COLUMNS,'discount_timing':'2027 year-end is 1.1800136892539357 years after 2026-10-26; TV5 at 2031 year-end. Q4 net cash bridge budget zero, tested by opening cash +/-1bn and extra payment1bn. Known partial expiry days are prorated; other year-end dates remain disclosed overview/budget, not precise permits.','assumption_limits':'21 domestic road entity budgets; old JJT is mother operating unit. Three JV economic upflow budgets have NO statutory registered/reserve pools; parent equity earnings separately calibrated. 2bn support per object is cumulative, not annual. No renewals except separately funded conditional JJT 2031-2055. No book principal added to terminal.','entity_source_rows':ROAD_DATA,'disclosed_registered_capital_bn':REGISTERED,'direct_mother_cost_method_book_bn':DIRECT_PARENT_BOOK,'detailed_permit_expiry_dates':{k:list(v) for k,v in FINAL_DATES.items()},'scenario_arguments':cases,'subgroup_valuation_bridge':subgroup_bridges,'financing_boundary':'12.5bn new credit is conditional forecast ceiling, not committed facility; 10bn equals base, zero fails2028. Core range varies discount rate only, not all debt allocation/JV life/non-road exit uncertainty.','runs':runs,'auxiliary_asset_method':{'common_book_equity_bn':common_book,'rights_parent_fraction':.70,'project_incremental_NPV_bn':project_npv,'value_range':asset,'independent_assumptions':[['rights_factor',.65,.75],['JV_factor',.80,.90]]},'tests':checks}
def pack_full(out):
    raw=json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return {'encoding':'gzip+base64 stdlib; canonical expanded JSON SHA256','ticker':'CN:001965','name':'招商公路','full_sha256':hashlib.sha256(raw).hexdigest(),'full_bytes':len(raw),'subgroup_valuation_bridge':out['subgroup_valuation_bridge'],'financing_boundary':out['financing_boundary'],'summary':{k:{x:v[x] for x in ('feasible','pv','tv5','D')} for k,v in out['runs'].items()},'payload':base64.b64encode(gzip.compress(raw,mtime=0)).decode()}
def unpack_full(p):
    raw=gzip.decompress(base64.b64decode(p['payload']));assert hashlib.sha256(raw).hexdigest()==p['full_sha256'];return json.loads(raw)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(__file__).with_name('2026-Q3-output.json'));ap.add_argument('--expand',action='store_true');args=ap.parse_args()
    out=build();packed=pack_full(out);assert unpack_full(packed)==out
    args.output.write_text(json.dumps(out if args.expand else packed,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(packed['summary'],ensure_ascii=False,indent=2))

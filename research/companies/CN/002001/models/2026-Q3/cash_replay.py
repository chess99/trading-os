#!/usr/bin/env python3
"""当前资本现金与权益计算核；经营输入由同次实际计算生成。"""
import copy
import json

# STATIC CANDIDATE. No financial acceptance implied.
# FROZEN_ROWS and FROZEN_RESULT are complete selected old raw, installed by the controller.
# EVENT_ADVANCE is in original model monetary units. No date/fee invented.
FROZEN_ROWS = None
FROZEN_RESULT = None
EVENT_ADVANCE = 0.0
EVENT_TREASURY_ADDITION = 0.0
REPLAY_COMPLETE = None
SHARES=30.7342168
COMMON=.995
FACTS={'revenue_9m':192.3133321352,'profit_parent_9m':58.6774427798,'cfo_9m':52.2761469817,'capex_9m':19.8728406624,'cash':88.8501376416,'trading_assets':29.9034945546,'debt':80.3851060175,'associate_assets':12.1871039662,'parent_H1_liquid':10.7417255915,'parent_H1_retained':58.2620187972,'shares':SHARES,'consolidated_equity':367.103146168}
NUTRITION={'methionine_revenue':90.,'vitamins_other_revenue':80.,'methionine_margin':.45,'vitamins_other_margin':.38}
def nutrition_margin(methionine,vitamins):
    return (90*methionine+80*vitamins)/170
BASE={'name':'base','revenues':[170.,42.,26.,22.],'growth':[.025,.03,.085,.025],'margins':[nutrition_margin(.45,.38),.47,.32,.18],'expense':.105,'tax':.15,'net_invest':[21,21,19,17,15,14,14,14,14,14],'r':.095,'g':.02,'terminal_roic':.12,'fin_yield':.015,'debt_rate':.026,'parent_cash0':FACTS['parent_H1_liquid'],'sub_retained0':100.,'parent_retained0':FACTS['parent_H1_retained'],'sub_reserve0':0.,'sub_registered':11.,'parent_registered':30.7342168,'parent_reserve0':15.45453678,'cash_lag':0.,'parent_extra_payment':0.,'payout_per_share':[1,1,1.05,1.10,1.15],'repurchase':[1.01,0,0,0,0,0,0,0,0,0],'early_profit_multipliers':[1]*10,'permanent_margin_cut':0.,'assoc_dividend':1.5,'assoc_recovery':1.,'terminal_asset_release':True,'slow_capital_return':False}
def law_step(retained,reserve,capital,profit):
    eligible=max(0.,profit+min(0.,retained))
    provision=min(eligible*.1,max(0.,capital*.5-reserve))
    return retained+profit-provision,reserve+provision,provision

def cash_step(opening,flow,payment):
    closing=opening+flow-payment
    assert abs(closing-opening-flow+payment)<1e-8
    return closing

def present_value(cashflows,terminal,r):
    return sum(v/(1+r)**(i+1) for i,v in enumerate(cashflows))+terminal/(1+r)**len(cashflows)

def economic_failure(boundary, state):
    """Only explicit economic branches call this. Schema/assert faults are never converted."""
    snapshot={}
    for key,value in state.items():
        if key in ('snapshot','state'):continue
        try:json.dumps(value,allow_nan=False)
        except (TypeError,ValueError):continue
        snapshot[key]=copy.deepcopy(value)
    return {'feasible':False,'economic_status':'INFEASIBLE','boundary':boundary,
            'full_partial':snapshot,'failed_year':state.get('y',state.get('i',-1)+1),
            'value':None,'terminal':None}

def production(spec,common=COMMON):
    s=copy.deepcopy(spec);revenues=s['revenues'][:]
    if EVENT_ADVANCE:s['parent_cash0']-=EVENT_ADVANCE;s['repurchase'][0]-=EVENT_ADVANCE
    liquid=(FACTS['cash']+FACTS['trading_assets'])*common-EVENT_ADVANCE # issuer external payment is NOT multiplied by common
    pc=s['parent_cash0'];sc=liquid-pc;pr=s['parent_retained0'];sr=s['sub_retained0'];ps=s['parent_reserve0'];ss=s['sub_reserve0']
    pdebt=52*common;sdebt=FACTS['debt']*common-pdebt;assoc=FACTS['associate_assets']*common
    receivable=0.;rows=[]
    cap=(FACTS['consolidated_equity']+FACTS['debt']-FACTS['cash']-FACTS['trading_assets']+15-FACTS['associate_assets'])*common
    for k in range(10):
        y=k+1
        frozen=FROZEN_ROWS[k]
        revenues=copy.deepcopy(frozen['segment_revenue']);margins=copy.deepcopy(frozen['segment_margin'])
        op=frozen['nopat_common'];inv=frozen['net_reinvestment_common']
        opminp=3*common*1.02**k;opmins=12*common*1.02**k
        debt_reserve_fraction=max(0,y-5)/5
        minp=opminp+pdebt*debt_reserve_fraction;mins=opmins+sdebt*debt_reserve_fraction
        p_interest=pdebt*s['debt_rate']*(1-s['tax']);s_interest=sdebt*s['debt_rate']*(1-s['tax'])
        pf=max(pc,0)*s['fin_yield'];sf=max(sc,0)*s['fin_yield']
        p_profit=op*.08-p_interest+pf;sub_profit=op*.92-s_interest+sf
        p_flow=p_profit-.8-s['parent_extra_payment']
        sub_flow=sub_profit-(inv-.8)+s['assoc_dividend']*common
        sr,ss,sreserve=law_step(sr,ss,s['sub_registered'],sub_profit)
        desired_up=(27+2*k)*s['early_profit_multipliers'][k] if y<=5 else (35*1.02**(y-5) if s['slow_capital_return'] else max(0,sub_flow)+max(0,sc-mins)*.18)
        declared=min(max(0,sr),max(0,sc+sub_flow-mins-receivable),max(0,desired_up))
        paid_new=declared*(1-s['cash_lag']);collected=receivable
        receivable=declared-paid_new;upstream=paid_new+collected
        sc=cash_step(sc,sub_flow,upstream);sr-=declared
        pr,ps,preserve=law_step(pr,ps,s['parent_registered'],p_profit+declared)  # declarations enter legal profit; later receipt does not
        desired=s['payout_per_share'][k]*SHARES if y<=5 else (1.15*SHARES*1.02**(y-5) if s['slow_capital_return'] else max(0,p_flow+upstream)+max(0,pc-minp)*.18)
        buy=s['repurchase'][k]
        actual=min(max(0,desired),max(0,pr),max(0,pc+p_flow+upstream-minp-buy))
        pc=cash_step(pc,p_flow+upstream,actual+buy);pr-=actual;cap=frozen['operating_capital_end']
        rows.append({'year':y,'revenue':sum(revenues),'segment_revenue':revenues[:],'segment_margin':margins,'nopat_common':op,'net_reinvestment_common':inv,'operating_capital_end':cap,'parent_profit_ex_upstream':p_profit,'subs_profit':sub_profit,'parent_interest':p_interest,'subs_interest':s_interest,'financial_income':pf+sf,'parent_flow':p_flow,'subs_flow':sub_flow,'declared_upstream':declared,'received_upstream':upstream,'dividend_receivable':receivable,'parent_reserve_add':preserve,'subs_reserve_add':sreserve,'parent_retained':pr,'subs_retained':sr,'parent_reserve':ps,'subs_reserve':ss,'parent_cash':pc,'subs_cash':sc,'minimum_cash':opminp+opmins,'debt_cash_reserve':(pdebt+sdebt)*debt_reserve_fraction,'parent_debt':pdebt,'subs_debt':sdebt,'ordinary_dividend':actual,'dividend_per_share':actual/SHARES,'repurchase':buy,'financing_net':0.,'payout_cut':max(0,desired-actual)})
        if min(pc,sc)<-1e-7:return economic_failure("NEGATIVE_ENTITY_CASH_AFTER_REQUIRED_PAYMENT",locals())
        assert min(pc,sc)>=-1e-7
        assert actual<=max(0.,pr+actual)+1e-7 and declared<=max(0.,sr+declared)+1e-7  # signed loss carries forward; distributions cannot exceed legal profits
    if not (pc>=pdebt+opminp-1e-7 and sc>=sdebt+opmins-1e-7):return economic_failure("DEBT_REPAYMENT_AND_MINIMUM_UNFUNDED",locals())
    assert pc>=pdebt+opminp-1e-7 and sc>=sdebt+opmins-1e-7,'Debt repayment must be funded; do not truncate negative equity'
    liquidation_cash=pc+sc-rows[-1]['minimum_cash']-pdebt-sdebt+assoc*s['assoc_recovery']
    if liquidation_cash<-1e-7:return economic_failure("NEGATIVE_LIQUIDATION_RESOURCES",locals())
    assert liquidation_cash>=-1e-7
    legal=max(0,pr+sr)
    principal_release=min(liquidation_cash,legal) if s['terminal_asset_release'] else 0.
    trapped=liquidation_cash-principal_release
    deferred_principal_pv=trapped*((1+s['fin_yield'])/(1+s['r']))**5
    tail_cash=FROZEN_RESULT['tail_cash_y11']
    tail_operating=FROZEN_RESULT['terminal_operating_y10']
    terminal10=tail_operating+principal_release+deferred_principal_pv
    pv_div=sum(z['ordinary_dividend']/(1+s['r'])**z['year'] for z in rows)
    pv_terminal=terminal10/(1+s['r'])**10
    value=present_value([z['ordinary_dividend'] for z in rows],terminal10,s['r'])/SHARES
    terminal5=(sum(z['ordinary_dividend']/(1+s['r'])**(z['year']-5) for z in rows[5:])+terminal10/(1+s['r'])**5)/SHARES
    aux_cash=rows[0]['nopat_common']*(1+s['g'])*(1-s['g']/s['terminal_roic'])
    aux=(aux_cash/(s['r']-s['g'])+liquid-15*common-FACTS['debt']*common+assoc)/SHARES
    capdelta=rows[4]['operating_capital_end']-rows[0]['operating_capital_end']
    return {'inputs':s,'common_allocation':common,'years':rows,'value_per_share':value,'terminal_y5_per_share':terminal5,'terminal_y10':terminal10,'terminal_operating_y10':tail_operating,'tail_cash_y11':tail_cash,'principal_release_y10':principal_release,'trapped_principal_y10':trapped,'deferred_principal_pv_y10':deferred_principal_pv,'financial_assets_after_debt_y10':liquidation_cash,'legal_profit_pool_y10':legal,'pv_distributions':pv_div,'pv_terminal':pv_terminal,'terminal_pv_share':pv_terminal/(pv_div+pv_terminal),'auxiliary_normalized_fcff_capitalization':aux,'incremental_ROIC_y1_to_y5':(rows[4]['nopat_common']-rows[0]['nopat_common'])/capdelta if capdelta else None}

def changed(**kw):
    s=copy.deepcopy(BASE);s.update(kw);return s


# The sequential controller imports definitions only; original main/build/tests are never called.

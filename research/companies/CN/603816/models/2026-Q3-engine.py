#!/usr/bin/env python3
"""KUKA 2026-Q3 owner-value model. Python 3 stdlib only; amounts CNY bn.
Run from ANY cwd: python /path/2026-Q3.py [--output-dir DIR]. Default output is script directory.
Economic budgets, NOT audited/legal dividend certifications. No market price input.
"""
from copy import deepcopy
from pathlib import Path
from decimal import Decimal, getcontext
import argparse, csv, json, math
INFORMATION_CUTOFF='2026-10-27T11:53:16+00:00'
SHARES=0.925623012
FUTURE_SHARES=0.925527012
CASH_BRIDGE={'cash':4.49024886743,'trading_financial_assets':2.23031437318,
 'one_year_deposits_assumed_same_nature_as_H1':.39761027038,
 'other_deposits_estimate':.20,'minority_net_financial_claim_estimate':-.10}
OPEN_CASH=sum(CASH_BRIDGE.values())
OPEN_DEBT=2.00141580513+.028259
BASE={
'name':'base','shares':SHARES,'future_shares':[FUTURE_SHARES]*5,'registered_capitals':[.925637012]*5,'share_cancellation_cash':[.00087168,0,0,0,0],'dom0':9.10,'exp0':10.20,'other0':.55,
'dom_growth':[-.02,.02,.03,.03,.02],'exp_growth':[.04,.05,.05,.04,.03],
'other_growth':[0,.02,.02,.02,.02],
'dom_margin':[.135,.138,.14,.14,.14],'exp_margin':[.085,.088,.09,.09,.09],
'other_margin':[.14]*5,'tax':.22,'minority_profit_share':.018,
'owned_da':[.55,.60,.65,.69,.72], 'capex':[1.50,1.55,1.30,1.00,.75],
'working_capital_ratio':.08,'working_capital_shock':[.10,0,0,0,0],
'min_cash_ratio':.075,'restricted_operating_buffer':1.20,
'cash0':OPEN_CASH,'debt0':OPEN_DEBT,'cash_yield':.016,'debt_cost':.035,
'scheduled_debt_pay':[.40,.40,.40,.40,.42967480513], 'max_new_debt':2.0,
'parent_bank_limit':1.0,'parent_incremental_bank_cost':.05,'payout':.60,'parent_cash0':1.0,'parent_min_cash':.40,
'parent_legal_retained0':1.97762124926,'parent_stat_reserve0':.4109457595,
'parent_registered_capital':.925733012,
'parent_own_profit0':.22,'parent_own_cash_conversion':1.0,
'parent_impairment':[0]*5,'parent_extra_settlement':[0]*5,
'parent_equity_injection':[.15,.05,0,0,0],'parent_project_capex':[.25,.32,.34,.278,0],
'ningbo_profit0':.50,'hk_profit0':.50,'ningbo_ownership':1.0,'hk_ownership':1.0,
'ningbo_upstream_ratio':.80,'hk_upstream_ratio':.75,
'ningbo_capex_fraction':.20,'hk_capex_fraction':.20,
'upstream_cash_fraction':[1]*5,'terminal_g':.015,'terminal_roic':.13,
'valuation_rate':.0975,'terminal_earnings_haircut':0.0,'financial_release_years':6,
'parent_claim_recovery_budget':2.60,'terminal_other_profit_eligibility_fraction':.50,
'event':'next five 12-month periods; domestic stabilization, overseas slowing, retain project capital',
'finance_haircut':[0]*5,
}

def parent_legal_step(retained,reserve,profit,registered_capital):
    # Losses consume distributable earnings. Reserve charged only to profit remaining after past losses.
    taxable_for_reserve=max(0.0,profit+min(retained,0.0))
    charge=min(max(registered_capital*.50-reserve,0.0),taxable_for_reserve*.10)
    return retained+profit-charge,reserve+charge,charge

def terminal_operating_value(common_operating_profit,g,roic,r,haircut=0):
    if r<=g or roic<=g: raise ValueError('invalid steady-state capital economics')
    # Required operating reinvestment, including minimum working cash, is g/ROIC.
    next_earn=common_operating_profit*(1-haircut)*(1+g)
    cf=next_earn*(1-g/roic)
    return cf/(r-g),cf

def discount_stream(distributions,terminal,r):
    return sum(d/(1+r)**i for i,d in enumerate(distributions,1))+terminal/(1+r)**len(distributions)

def financial_release(c, last, rate=None):
    """Value Y5 excess financial principal through Y6+ remittance budgets, NOT immediate full cash.
    Known-parent net intercompany claims + projected unremitted new subsidiary earnings are routes.
    Additional declarations use ONLY other entities' Y1-5 forecast earnings never previously upstreamed.
    No Y6+ ordinary operating payout/reinvestment profit is reused. No opening subsidiary reserves.
    No invented subsidiary opening statutory reserves; no required operating cash released.
    """
    r=c['valuation_rate'] if rate is None else rate
    excess=last['cash_end']-last['debt_end']-last['minimum_operating_cash']
    if excess<=0: return {'net_value':excess,'gross_release_pv':excess,'operating_cash_diversion_pv':0.,'rows':[]}
    n=c['financial_release_years']; principal=excess
    claims=max(0,c['parent_claim_recovery_budget']-last.get('parent_bank_debt_end',0))
    claim_limit=claims/n
    accumulated={k:v['unremitted_current_earnings_budget'] for k,v in last['subsidiary_budgets'].items()}
    accumulated['other']=last['other_entities_cumulative_unremitted_profit_budget']*c['terminal_other_profit_eligibility_fraction']
    initial_accumulated=dict(accumulated)
    parent_headroom=max(0,last['parent_cash_end']-c['parent_min_cash'])
    retained=last['parent_legal_retained_end']; reserve=last['parent_statutory_reserve_end']
    gross_pv=0.; rows=[]
    for t in range(1,n+1):
        opening=principal; target=excess/n
        # Yield is after group tax/minority; 1.5% additional blended collection friction.
        interest=principal*c['cash_yield']*(1-c['tax'])*.985
        from_parent=min(parent_headroom,target);parent_headroom-=from_parent
        from_claims=min(claims,claim_limit,target-from_parent);claims-=from_claims
        needed=target-from_parent-from_claims; declaration=0.;fees=0.
        for k in ('ningbo','hk','other'):
            cost=.03 if k in ('hk','other') else 0.
            use=min(accumulated[k],initial_accumulated[k]/n,max(0,needed))
            accumulated[k]-=use;declaration+=use;fees+=use*cost;needed-=use
        # Legal retained earnings already earned by mother are separate from actual cash routes.
        temp_ret,temp_res,charge=parent_legal_step(retained,reserve,declaration-fees+interest,c['registered_capitals'][-1])
        payout=target+interest-fees
        diversion=max(0,needed,payout-temp_ret)
        if diversion>1e-8:
            raise ValueError('terminal release exceeds identified current-profit route capacity: '+c['name'])
        # No future operating cash/profit top-up is permitted; all remaining routes must be prior Y1-5 earnings.
        temp_ret,temp_res,charge2=parent_legal_step(temp_ret,temp_res,diversion,c['registered_capitals'][-1])
        if temp_ret+1e-9<payout: raise ValueError('terminal legal budget infeasible')
        retained=temp_ret-payout;reserve=temp_res;principal-=target
        gross_pv+=payout/(1+r)**t
        rows.append({'year_after_year5':t,'financial_principal_open':opening,'principal_released':target,
          'interest_after_tax_and_collection_cost':interest,'from_parent_cash':from_parent,'intercompany_principal_collected':from_claims,
          'previously_unremitted_new_earnings_declared':declaration,'remittance_fees':fees,
          'unused_other_profit_eligibility_budget':accumulated['other'],
          'future_operating_cash_diverted_and_removed_from_operating_value':0.,
          'holder_extra_cash':payout,'parent_legal_retained_after_extra_distribution':retained,
          'parent_statutory_reserve':reserve,'financial_principal_end':principal})
    assert abs(principal)<1e-8
    return {'net_value':gross_pv,'gross_release_pv':gross_pv,'operating_cash_diversion_pv':0.,'rows':rows}

def project(c):
    dom,exp,other=c['dom0'],c['exp0'],c['other0']; prev_sales=dom+exp+other
    cash,debt=c['cash0'],c['debt0']; parent_cash=c['parent_cash0']
    retained,reserve=c['parent_legal_retained0'],c['parent_stat_reserve0']
    sub_earn={'ningbo':0.0,'hk':0.0}; upstream_receivable=0.0
    rows=[]; new_debt_used=0.0; parent_bank=0.0; other_earnings=0.0
    for i in range(5):
        cash_start,debt_start,parent_cash_start=cash,debt,parent_cash
        dom*=1+c['dom_growth'][i];exp*=1+c['exp_growth'][i];other*=1+c['other_growth'][i]
        sales=dom+exp+other
        ebit=dom*c['dom_margin'][i]+exp*c['exp_margin'][i]+other*c['other_margin'][i]
        tax=max(0,ebit)*c['tax'] # no unearned cash tax refund in losses
        common_op=(ebit-tax)*(1-c['minority_profit_share'])
        finance_income=cash_start*c['cash_yield']*(1-c['tax'])
        interest=((debt_start-parent_bank)*c['debt_cost']+parent_bank*c['parent_incremental_bank_cost'])*(1-c['tax'])
        economic_profit=common_op+finance_income-interest-c['finance_haircut'][i]
        delta_wc=(sales-prev_sales)*c['working_capital_ratio']+c['working_capital_shock'][i]
        fcf=economic_profit+c['owned_da'][i]-c['capex'][i]-delta_wc
        # Actual source budgets: entirely owned Ningbo and HK Trade subgroup common profits.
        # NO opening subsidiary reserves are invented or used. Their cash is constrained separately.
        growth_capex=max(c['capex'][i]-c['owned_da'][i]+delta_wc,0)
        sub_detail={}; declaration=0.0
        for key,revenue,rev0,margin,margin0 in [
          ('ningbo',dom,c['dom0'],c['dom_margin'][i],.135),
          ('hk',exp,c['exp0'],c['exp_margin'][i],.085)]:
            profit=c[key+'_profit0']*(revenue/rev0)*(margin/margin0)
            own=c[key+'_ownership']; profit*=own
            # The 10% Ningbo buffer is an economic withholding, not a claimed statutory reserve balance.
            buffer=.10*max(0,profit+min(0,sub_earn[key])) if key=='ningbo' else 0.0
            sub_earn[key]+=profit-buffer
            source_cash=max(0,profit-growth_capex*c[key+'_capex_fraction'])
            d=min(max(0,sub_earn[key]),max(0,profit)*c[key+'_upstream_ratio'],source_cash)
            sub_earn[key]-=d;declaration+=d
            sub_detail[key]={'forecast_common_profit':profit,'reserve_cash_buffer':buffer,
              'unremitted_current_earnings_budget':sub_earn[key],'cash_available_after_reinvestment':source_cash,
              'declared_dividend_budget':d}
        collected=upstream_receivable+declaration*c['upstream_cash_fraction'][i]
        upstream_receivable=declaration*(1-c['upstream_cash_fraction'][i])
        parent_incremental_interest=parent_bank*c['parent_incremental_bank_cost']*(1-c['tax'])
        own_profit=c['parent_own_profit0']*(sales/(c['dom0']+c['exp0']+c['other0']))-parent_incremental_interest
        # Foreign remittance tax/transaction frictions conservatively 3%; not shareholder personal tax.
        remittance_cost=.03*sub_detail['hk']['declared_dividend_budget']
        other_earnings+=common_op-own_profit-sum(x['forecast_common_profit'] for x in sub_detail.values())
        parent_profit=own_profit+declaration-remittance_cost-c['parent_impairment'][i]
        retained,reserve,reserve_charge=parent_legal_step(retained,reserve,parent_profit,c['registered_capitals'][i])
        parent_cash+=own_profit*c['parent_own_cash_conversion']+collected-remittance_cost-c['parent_extra_settlement'][i]-c['parent_equity_injection'][i]-c['parent_project_capex'][i]-c['share_cancellation_cash'][i]
        # Parent liquidity is not identical to group liquidity. Additional bank funding remains debt, not profit.
        parent_financing=min(max(0,c['parent_min_cash']-parent_cash),max(0,c['parent_bank_limit']-parent_bank))
        parent_cash+=parent_financing;parent_bank+=parent_financing
        # Internal equity injections and settlements only reallocate group cash; not new group costs.
        cash+=fcf-remittance_cost-c['share_cancellation_cash'][i]+parent_financing;debt+=parent_financing
        min_cash=sales*c['min_cash_ratio']+c['restricted_operating_buffer']
        # Repay only from cash above operational buffer; otherwise roll normal debt, not automatic distress.
        repay=min(max(0,debt-parent_bank),max(0,cash-min_cash),c['scheduled_debt_pay'][i]);cash-=repay;debt-=repay
        financing=0.0
        if cash<min_cash:
            financing=min(min_cash-cash,max(0,c['max_new_debt']-new_debt_used));cash+=financing;debt+=financing;new_debt_used+=financing
        if cash<min_cash-1e-8: raise ValueError('operating path infeasible without unauthorized capital: '+c['name'])
        desired=max(0,economic_profit)*c['payout']
        dividend=min(desired,max(0,retained),max(0,parent_cash-c['parent_min_cash']),max(0,cash-min_cash))
        retained-=dividend;parent_cash-=dividend;cash-=dividend
        rows.append({'year':i+1,'domestic_revenue':dom,'export_revenue':exp,'other_revenue':other,'revenue':sales,
          'operating_profit_before_tax':ebit,'common_operating_profit':common_op,'finance_income_after_tax':finance_income,
          'bank_interest_after_tax':interest,'common_economic_profit':economic_profit,'owned_da':c['owned_da'][i],
          'capex':c['capex'][i],'delta_working_capital':delta_wc,'pre_dividend_fcf':fcf,
          'cash_open':cash_start,'debt_open':debt_start,'debt_repayment':repay,'new_debt':financing+parent_financing,'parent_new_bank_debt':parent_financing,'parent_bank_debt_end':parent_bank,'parent_incremental_interest':parent_incremental_interest,
          'dividend_desired':desired,'dividend':dividend,'dividend_per_share':dividend/c['future_shares'][i],'fully_diluted_shares':c['future_shares'][i],'share_cancellation_cash':c['share_cancellation_cash'][i],
          'cash_end':cash,'debt_end':debt,'minimum_operating_cash':min_cash,
          'net_financial_assets_after_operating_buffer':cash-debt-min_cash,
          'parent_cash_open':parent_cash_start,'parent_own_profit':own_profit,'parent_profit':parent_profit,
          'parent_cash_end':parent_cash,'parent_legal_retained_end':retained,'parent_statutory_reserve_end':reserve,
          'parent_statutory_reserve_charge':reserve_charge,'parent_equity_injection':c['parent_equity_injection'][i],'parent_project_capex':c['parent_project_capex'][i],
          'parent_extra_settlement':c['parent_extra_settlement'][i],'subsidiary_declared_dividends':declaration,
          'subsidiary_cash_collected':collected,'dividend_receivable_end':upstream_receivable,
          'other_entities_cumulative_unremitted_profit_budget':max(0,other_earnings),'remittance_cost':remittance_cost,'subsidiary_budgets':sub_detail})
        assert abs(cash-(cash_start+fcf-remittance_cost-c['share_cancellation_cash'][i]-repay+financing+parent_financing-dividend))<1e-8
        assert abs(debt-(debt_start-repay+financing+parent_financing))<1e-8
        assert dividend<=max(0,retained+dividend)+1e-9
        assert parent_cash>=c['parent_min_cash']-1e-9, 'parent liquidity fails before dividend'
        assert abs(parent_cash-(parent_cash_start+own_profit*c['parent_own_cash_conversion']+collected-remittance_cost-c['parent_extra_settlement'][i]-c['parent_equity_injection'][i]-c['parent_project_capex'][i]-c['share_cancellation_cash'][i]+parent_financing-dividend))<1e-8
        prev_sales=sales
    last=rows[-1]
    op_value,terminal_cf=terminal_operating_value(last['common_operating_profit'],c['terminal_g'],c['terminal_roic'],c['valuation_rate'],c['terminal_earnings_haircut'])
    # All distributed cash removed above. Operating cash cannot be released; incremental future cash in ROIC.
    finance_bridge_raw=cash-debt-last['minimum_operating_cash']
    recovery=financial_release(c,last)
    finance_bridge=recovery['net_value']
    terminal=op_value+finance_bridge
    divs=[r['dividend_per_share'] for r in rows];pv=discount_stream(divs,terminal/c['future_shares'][-1],c['valuation_rate'])
    # Alternative: FY1 normalized earnings power with steady growth, current cash bridge and remaining growth-capital charge.
    initial_excess=c['cash0']-c['debt0']-((c['dom0']+c['exp0']+c['other0'])*c['min_cash_ratio']+c['restricted_operating_buffer'])
    aux_op,_=terminal_operating_value(rows[0]['common_operating_profit'],c['terminal_g'],c['terminal_roic'],c['valuation_rate'],c['terminal_earnings_haircut'])
    committed_extra=sum(max(r['capex']-r['owned_da'],0)/(1+c['valuation_rate'])**r['year'] for r in rows)
    # Current cash is not assumed instantly distributable in the cross-check either.
    cash_recovery_factor=sum(((1+c['cash_yield']*(1-c['tax']))/(1+c['valuation_rate']))**t for t in range(1,c['financial_release_years']+1))/c['financial_release_years']
    aux=aux_op+initial_excess*cash_recovery_factor-committed_extra
    return {'inputs':c,'rows':rows,'value_per_share':pv,
     'incremental_return_Y1_to_Y5':None if c['name']=='hand_perpetuity' else (rows[-1]['common_operating_profit']-rows[0]['common_operating_profit'])/(sum(x['capex']-x['owned_da']+x['delta_working_capital'] for x in rows[1:])+rows[-1]['minimum_operating_cash']-rows[0]['minimum_operating_cash']),
     'terminal_financial_release':recovery,'terminal_per_share':terminal/c['future_shares'][-1],'terminal_financial_bridge_raw':finance_bridge_raw,'terminal_operating_value':op_value,'terminal_financial_bridge':finance_bridge,
     'terminal_common_equity_value':terminal,'terminal_next_year_operating_cash':terminal_cf,
     'terminal_pv_share':terminal/c['future_shares'][-1]/(1+c['valuation_rate'])**5/pv,
     'alternative_earnings_power_value_per_share':aux/c['shares'],'alternative_committed_extra_capex_pv':committed_extra}

def scenarios():
    cases={'base':deepcopy(BASE)}
    for name,r,g,dm,em,roic in [('core_low',.105,.01,.132,.082,.12),('core_high',.09,.015,.145,.092,.14)]:
        c=deepcopy(BASE);c.update(name=name,valuation_rate=r,terminal_g=g,terminal_roic=roic,
          dom_margin=[dm,dm+.002,dm+.004,dm+.004,dm+.004],exp_margin=[em,em+.002,em+.004,em+.004,em+.004]);cases[name]=c
    c=deepcopy(BASE);c.update(name='cyclical_weak',event='Y1-2 domestic renovation demand/overseas order delay; recover Y3-5; projects completed slower',
      dom_growth=[-.12,-.05,.04,.05,.04],exp_growth=[-.08,0,.06,.06,.05],dom_margin=[.10,.105,.12,.13,.135],exp_margin=[.065,.07,.08,.085,.088],
      capex=[1.35,1.40,1.55,1.15,.75],working_capital_shock=[.65,-.25,-.20,-.20,0],payout=.45,
      parent_impairment=[.15,0,0,0,0],parent_extra_settlement=[.25,0,0,0,0],upstream_cash_fraction=[.60,.85,1,1,1],
      valuation_rate=.105,terminal_g=.01,terminal_roic=.12);cases[c['name']]=c
    c=deepcopy(BASE);c.update(name='structural_adverse',event='Y1 onward domestic channel/price erosion and foreign customer bargaining; no recovery to old margin; Y1 parent write-off and WC loss',
      dom_growth=[-.18,-.08,-.03,0,0],exp_growth=[-.12,-.05,0,.01,.01],dom_margin=[.025,.055,.075,.08,.08],exp_margin=[.02,.04,.05,.055,.055],
      capex=[1.30,1.25,1.10,.90,.65],owned_da=[.55,.58,.58,.56,.55],working_capital_shock=[1.20,.20,0,0,0],
      restricted_operating_buffer=1.45,working_capital_ratio=.11,payout=.35,ningbo_upstream_ratio=.60,hk_upstream_ratio=.55,
      parent_own_profit0=.12,parent_impairment=[.80,.20,0,0,0],parent_extra_settlement=[.30,0,0,0,0],
      upstream_cash_fraction=[.50,.75,1,1,1],debt_cost=.05,finance_haircut=[.25,0,0,0,0],
      valuation_rate=.115,terminal_g=0,terminal_roic=.08,terminal_earnings_haircut=.10,parent_claim_recovery_budget=1.56);cases[c['name']]=c
    c=deepcopy(BASE);c.update(name='upside',event='Y1 onward domestic OMO conversion proven; overseas localization utilization improves; additional capex and inventory required',
      dom_growth=[.03,.06,.06,.05,.04],exp_growth=[.08,.08,.07,.06,.05],dom_margin=[.145,.15,.155,.155,.155],exp_margin=[.09,.095,.10,.10,.10],
      capex=[1.65,1.75,1.55,1.15,.85],owned_da=[.56,.63,.72,.78,.83],working_capital_ratio=.09,
      payout=.60,valuation_rate=.09,terminal_g=.02,terminal_roic=.15);cases[c['name']]=c
    c=deepcopy(BASE);c.update(name='parent_delay',event='Y1-2 legally declared upstream cash delays; extra parent working settlement 0.4bn in Y1; no effect on group economics except timing',
      upstream_cash_fraction=[.30,.70,1,1,1],parent_extra_settlement=[.40,0,0,0,0],financial_release_years=8);cases[c['name']]=c
    c=deepcopy(BASE);c.update(name='claims_slow',event='same business; 40 percent fewer mother intercompany claims repay over 10 post-Y5 years; other entities Y1-5 undistributed profits supply remaining routes',parent_claim_recovery_budget=1.56,financial_release_years=10);cases[c['name']]=c
    return cases

def independent_endpoint(result):
    # Arithmetic formatting check only; separate independent_recompute.py recomputes the economic chain from literal inputs.
    getcontext().prec=40;D=lambda x:Decimal(str(x));c=result['inputs'];r=D(c['valuation_rate']);g=D(c['terminal_g']);roic=D(c['terminal_roic'])
    p=D(result['rows'][-1]['common_operating_profit'])*(1-D(c['terminal_earnings_haircut']))
    bridge=sum((D(x['holder_extra_cash'])-D(x['future_operating_cash_diverted_and_removed_from_operating_value']))/(1+r)**x['year_after_year5'] for x in result['terminal_financial_release']['rows']) if result['terminal_financial_release']['rows'] else D(result['terminal_financial_bridge_raw'])
    tv=(p*(1+g)*(1-g/roic)/(r-g)+bridge)/D(c['future_shares'][-1])
    v=sum(D(x['dividend'])/D(c['future_shares'][x['year']-1])/(1+r)**D(x['year']) for x in result['rows'])+tv/(1+r)**5
    return float(v)

def tests(outputs):
    # Known hand-calculable perpetuity is passed into SAME formal project() as every scenario.
    c=deepcopy(BASE); c.update(name='hand_perpetuity',shares=1.,future_shares=[1.]*5,registered_capitals=[1.]*5,share_cancellation_cash=[0]*5,parent_project_capex=[0]*5,financial_release_years=1,dom0=1.,exp0=0.,other0=0.,dom_growth=[0]*5,exp_growth=[0]*5,other_growth=[0]*5,
      dom_margin=[1.]*5,exp_margin=[0]*5,other_margin=[0]*5,tax=0.,minority_profit_share=0.,owned_da=[0]*5,capex=[0]*5,
      working_capital_ratio=0.,working_capital_shock=[0]*5,min_cash_ratio=0.,restricted_operating_buffer=0.,cash0=0.,debt0=0.,
      cash_yield=0.,debt_cost=0.,scheduled_debt_pay=[0]*5,payout=1.,parent_cash0=0.,parent_min_cash=0.,
      parent_legal_retained0=0.,parent_stat_reserve0=.5,parent_registered_capital=1.,parent_own_profit0=1.,parent_equity_injection=[0]*5,
      ningbo_profit0=0.,hk_profit0=0.,terminal_g=0.,terminal_roic=.2,valuation_rate=.1)
    # Avoid zero/zero source denominators, while zero profits make these source numerators irrelevant.
    c['exp0']=1e-20;c['other0']=1e-20
    hand=project(c);assert abs(hand['value_per_share']-10)<1e-8;assert all(abs(x['dividend']-1)<1e-8 for x in hand['rows'])
    # Legal kernel is the one used inside project(): prior loss consumes income before reserve and distribution.
    x=parent_legal_step(.10,.0,-.30,1.);assert abs(x[0]+.20)<1e-9 and x[2]==0
    y=parent_legal_step(x[0],x[1],.10,1.);assert abs(y[0]+.10)<1e-9 and y[2]==0
    z=parent_legal_step(y[0],y[1],.30,1.);assert abs(z[0]-.18)<1e-9 and abs(z[2]-.02)<1e-9
    cap=parent_legal_step(0,.49,1.,1.);assert abs(cap[2]-.01)<1e-9
    errs={k:independent_endpoint(v)-v['value_per_share'] for k,v in outputs.items()};assert max(abs(v) for v in errs.values())<1e-8
    # Dominant parameter: 100bp export margin shock must affect profit, dividends/cash and terminal, not just a label.
    shocked=deepcopy(BASE);shocked['exp_margin']=[x-.01 for x in shocked['exp_margin']];shocked['name']='export_margin_minus_100bp'
    s=project(shocked);ind=independent_endpoint(s);assert abs(ind-s['value_per_share'])<1e-8
    assert s['value_per_share']<outputs['base']['value_per_share'] and s['terminal_common_equity_value']<outputs['base']['terminal_common_equity_value']
    # Delay scenario must reduce near-term actual payout; already declared receivables don't create second legal profit.
    assert outputs['parent_delay']['rows'][0]['dividend']<outputs['base']['rows'][0]['dividend']
    for v in outputs.values():
        assert len(v['rows'])==5
        assert all(x['cash_end']>=x['minimum_operating_cash']-1e-8 for x in v['rows'])
    sensitivities={}
    for name,change in [('other_deposits_zero',{'cash0':OPEN_CASH-.20}),('minority_claim_extra_020',{'cash0':OPEN_CASH-.20}),('parent_cash_start_070',{'parent_cash0':.70}),('capex_extra_050',{'capex':[1.75,1.80,1.30,1.00,.75]}),('base_r_plus_100bp',{'valuation_rate':.1075})]:
        q=deepcopy(BASE);q.update(name=name,**change);zcase=project(q);sensitivities[name]={'value':zcase['value_per_share'],'delta':zcase['value_per_share']-outputs['base']['value_per_share'],'full_output':zcase}
    bad=deepcopy(BASE);bad.update(name='unfunded_terminal_route',parent_claim_recovery_budget=1.30,financial_release_years=10)
    try: project(bad)
    except ValueError: rejected_unfunded_terminal=True
    else: raise AssertionError('unsupported terminal principal release was not rejected')
    assert sum(x['parent_new_bank_debt'] for x in outputs['structural_adverse']['rows'])>0
    assert outputs['structural_adverse']['rows'][1]['dividend']==0
    return {'unsupported_terminal_route_rejected':rejected_unfunded_terminal,'sensitivity_diagnostics':sensitivities,'hand_perpetuity_expected':10,'hand_perpetuity_actual':hand['value_per_share'],
      'legal_loss_case':[x,y,z],'reserve_50_percent_cap_case':cap,'independent_endpoint_errors':errs,
      'export_margin_minus_100bp':{'value':s['value_per_share'],'independent_value':ind,'delta':s['value_per_share']-outputs['base']['value_per_share'],'full_output':s},
      'parent_bank_funding_structural':sum(x['parent_new_bank_debt'] for x in outputs['structural_adverse']['rows']),'cash_conservation':'passed all rows and scenarios','periods_and_ownership':'passed','parent_cash_delay':'recomputed, not forced original distribution'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parent);a=ap.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    out={k:project(v) for k,v in scenarios().items()};t=tests(out)
    b=out['base']; br=b['rows'][-1];tvr={}
    for label,r,g,roic in [('low',.105,.01,.12),('high',.09,.015,.14)]:
        ov,_=terminal_operating_value(br['common_operating_profit'],g,roic,r)
        fb=financial_release(BASE,br,rate=r)['net_value']
        tvr[label]=(ov+fb)/BASE['future_shares'][-1]
    data={'information_cutoff':INFORMATION_CUTOFF,'base_terminal_range_per_share':tvr,'units':'CNY bn; per share CNY','cash_bridge':CASH_BRIDGE,'scenarios':out,'tests':t}
    (a.output_dir/'2026-Q3-output.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    fields=[k for k in out['base']['rows'][0] if k!='subsidiary_budgets']
    with (a.output_dir/'annual-scenarios.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['scenario']+fields);w.writeheader()
        for key,v in out.items():
            for row in v['rows']:w.writerow({'scenario':key,**{k:row[k] for k in fields}})
    (a.output_dir/'tests.json').write_text(json.dumps(t,ensure_ascii=False,indent=2)+'\n')
    for k,v in out.items():print(k,'current',round(v['value_per_share'],4),'year5',round(v['terminal_per_share'],4),'aux',round(v['alternative_earnings_power_value_per_share'],4),'div',[round(x['dividend_per_share'],4) for x in v['rows']])
    print('Tests passed. Outputs:',a.output_dir)
if __name__=='__main__':main()

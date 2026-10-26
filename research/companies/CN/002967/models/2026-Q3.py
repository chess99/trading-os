#!/usr/bin/env python3
"""广电计量 2026Q3: actual legal-entity cash distributions; CNY million.
Stdlib only. No market price. Forecast years are successive 12-month budgets.
Financial principal is NOT separately added: it is released only by cash/legal
surplus through the same entity waterfall as operating distributions.
"""
import json, copy, pathlib, math
ASOF='2026-10-26T09:00:00+00:00'
INPUTS={
 'revenue0':4000.,'cash0':1459.742356+1176.32257546,
 'debt0':392.73004860+780.29275422+998.87765451+85.65907578,
 'current_bank_debt_estimate':85.65907578,'current_lease_estimate':75.06698696,
 'issued_shares':639.621152,'treasury_shares':22.858144,'remaining_options':5.18075,'exercise_price':13.71,'exercise_price_year2':13.40,
 'growth':[.12,.11,.10,.09,.08,.07,.06,.05,.04,.03],
 'nopat_margins':[.13,.133,.136,.138,.14,.137,.134,.13,.125,.12],
 'growth_capex':[350.,400.,300.,150.,100.],
 'da_rate':.09,'maintenance_rate':.085,'wc_increment':.25,
 'terminal_growth':.02,'terminal_roic':.11,'terminal_margin':.12,
 'debt_rate':.035,'tax':.15,'cash_yield':.013,
 'max_extra_borrow':500.,'refinance_year3':500.,'min_cash_ratio':.15,
 'old_dividend_receivable':0.,'parent_retained0':666.89041865-92.5144512,
 'parent_reserve0':166.61911677,'reserve_rate':.10,
 'repayments':[847.,100.,1000.,100.,100.],
 'years':140,'rates':[.10,.09],
 'pool_notes':'母公司/无锡/成都/天津单列；其他全资盈利实体仅按逐家正利润预算汇总，亏损和少数主体独立，禁止跨主体弥补；未知储备不加价。',
 'entities':[
  {'name':'parent','weight':.45,'ownership':1.,'cash':2050.,'capital':639.621152,'reserve':166.61911677,'retained':574.37596745},
  {'name':'Wuxi','weight':.08,'ownership':1.,'cash':120.,'capital':250.,'reserve':30.,'retained':0.},
  {'name':'Chengdu','weight':.06,'ownership':1.,'cash':60.,'capital':100.,'reserve':10.,'retained':0.},
  {'name':'Tianjin','weight':.06,'ownership':1.,'cash':60.,'capital':50.,'reserve':5.,'retained':0.},
  {'name':'other_wholly_profitable','weight':.32,'ownership':1.,'cash':260.,'capital':1200.,'reserve':100.,'retained':0.},
  {'name':'other_minorities','weight':.03,'ownership':.65,'cash':60.,'capital':100.,'reserve':10.,'retained':0.},
  {'name':'ZhongAn','weight':0.,'ownership':.8128,'cash':26.06493146,'capital':100.,'reserve':0.,'retained':-60.}
 ]}

def legal_update(retained,reserve,capital,profit,rate=.1):
    """New legal profit first offsets accumulated loss, then statutory reserve."""
    covered=min(max(profit,0.),max(-retained,0.))
    accrual=min(max(0.,profit-covered)*rate,max(0.,capital*.5-reserve))
    return retained+profit-accrual,reserve+accrual,accrual

def pay(cash,retained,minimum,request):
    dividend=max(0.,min(request,retained,cash-minimum))
    return cash-dividend,retained-dividend,dividend

def inject_at_par(entity,amount):
    """Parent subscribes newly issued registered capital alone, at par.
    This is a negotiated forecast, not an existing right or free minority transfer.
    Pre-injection ownership applies to earnings accrued before year-end injection;
    post-injection ownership applies to dividends subsequently declared.
    """
    old=entity['capital'];before=entity['ownership']
    entity['capital']=old+amount
    entity['ownership']=(old*before+amount)/(old+amount)
    entity['cash']+=amount
    return entity['ownership']

def params(kind='base'):
    p=copy.deepcopy(INPUTS);p['scenario']=kind;p['effective_year']=1;p['scope']='all operating entities unless noted';p['margin_shift']=0.;p['wc_delay']=0.;p['support_loss']=[-25.,-20.,-12.,-5.,0.];p['upstream_delay']=False
    if kind=='cyclical':
        p['growth']=[.02,.05,.14,.12,.09,.07,.06,.05,.04,.03];p['nopat_margins']=[.105,.115,.13,.138,.14,.137,.134,.13,.125,.12];p['wc_delay']=150.;p['support_loss']=[-40.,-30.,-20.,-10.,0.]
    elif kind=='structural':
        p['growth']=[.07,.06,.05,.04,.03,.025,.02,.02,.02,.02];p['nopat_margins']=[.11,.10,.095,.09,.09,.09,.09,.09,.09,.09];p['terminal_margin']=.09;p['terminal_roic']=.075;p['wc_increment']=.38;p['growth_capex']=[350.,400.,300.,130.,100.];p['support_loss']=[-40.,-40.,-35.,-30.,-25.];p['permanent_ehs_loss']=25.
    elif kind=='optimistic':
        p['growth']=[.15,.14,.13,.12,.10,.08,.07,.06,.04,.03];p['nopat_margins']=[.14,.145,.15,.15,.15,.145,.14,.135,.13,.125];p['terminal_margin']=.125;p['terminal_roic']=.13;p['growth_capex']=[400.,450.,350.,180.,130.];p['support_loss']=[-15.,-8.,0.,0.,0.]
    elif kind=='margin_minus_1pp_y2':p['margin_shift']=-.01;p['effective_year']=2
    elif kind=='wc_plus_10pp_y2':p['wc_increment']=.35;p['effective_year']=2
    elif kind=='upstream_delay_y2':p['upstream_delay']=True;p['effective_year']=2;p['scope']='all subsidiaries cash settlement delayed one year; declared dividends recognized once'
    elif kind=='no_refinance':p['refinance_year3']=0.;p['max_extra_borrow']=0.;p['effective_year']=1;p['payout_policy']=[0.,0.,.25,.35,.40]
    elif kind=='funding_break':p['growth']=[-.25,-.10,0.,.01,.02];p['nopat_margins']=[-.03,-.02,0.,.03,.05];p['refinance_year3']=0.;p['max_extra_borrow']=0.
    elif kind=='parent_cash_minus400':p['entities'][0]['cash']-=400.;p['entities'][4]['cash']+=400.;p['scope']='opening cash location only: parent to other wholly owned subsidiaries'
    elif kind=='minority_ownership50':p['entities'][5]['ownership']=.50;p['scope']='other minority entities only'
    elif kind=='capex_plus_200_y2':p['growth_capex'][1]+=200.;p['effective_year']=2
    p['frozen']='share schedule, tax, reserve law, opening entity cash and retained earnings; only declared scenario inputs differ'
    return p

def simulate(p):
    entities=copy.deepcopy(p['entities']);parent=entities[0]
    debt=p['debt0'];rev=p['revenue0'];shares=p['issued_shares']-p['treasury_shares'];used_extra=0.;pending=0.;rows=[];ok=True;reason=None
    for t in range(1,p['years']+1):
        oldrev=rev;g=p['growth'][t-1] if t<=len(p['growth']) else p['terminal_growth'];rev*=1+g
        m=p['nopat_margins'][t-1] if t<=len(p['nopat_margins']) else p['terminal_margin']
        if t>=p['effective_year']:m+=p['margin_shift']
        nopat=rev*m
        ehs=p['support_loss'][t-1] if t<=5 else -p.get('permanent_ehs_loss',0.)*(1+p['terminal_growth'])**(t-5)
        interest=debt*p['debt_rate']*(1-p['tax'])
        wc=p['wc_increment'] if t>=p['effective_year'] else INPUTS['wc_increment']
        if t<=5:
            da=rev*p['da_rate'];maintenance=rev*p['maintenance_rate'];growthcap=p['growth_capex'][t-1];dnwc=(rev-oldrev)*wc
            if t==1:dnwc+=p['wc_delay']
            if t==3:dnwc-=p['wc_delay']
            reinvest=maintenance+growthcap-da+dnwc
        else:
            # Fade capital intensity to sustainable g/ROIC, no free growth.
            roic=p['terminal_roic'];reinvest=(rev-oldrev)*m/roic;dnwc=(rev-oldrev)*wc;da=rev*p['da_rate'];maintenance=da;growthcap=reinvest-dnwc
        earmarked=max(0.,1050.-sum(p['growth_capex'][:min(t,3)]));minimum=rev*p['min_cash_ratio']+earmarked;before=sum(e['cash'] for e in entities)
        exercise=p['remaining_options']/2 if t<=2 else 0.;released=p['treasury_shares']/5 if t<=5 else 0.;shares+=exercise+released
        proceeds=exercise*(p['exercise_price'] if t==1 else p['exercise_price_year2']);parent['cash']+=proceeds;parent['capital']+=exercise
        old_receipt=p['old_dividend_receivable'] if t==1 else 0.;parent['cash']+=old_receipt
        prior_pending=pending;parent['cash']+=prior_pending;pending=0.
        # Receiving old recognized dividend NEVER creates new legal income.
        maturity=p['repayments'][t-1] if t<=5 else min(100.,debt)
        maturity=min(maturity,debt);borrow=p['refinance_year3'] if t==3 else 0.
        debt+=borrow-maturity;parent['cash']+=borrow-maturity
        fin_total=0.;group_ni=0.;owner_ni=0.;opowner=0.;detail=[];sub_div=0.;minor_div=0.;support=0.
        for e in entities:
            weight=e['weight'];own=e['ownership'];cash_start=e['cash'];ret_start=e['retained'];res_start=e['reserve']
            # Minimum cash earns no separately credited yield; cash above it does.
            floor=minimum*weight if weight else 20.
            financial=max(0.,cash_start-floor)*p['cash_yield']*(1-p['tax'])
            operating=nopat*weight-(interest if e['name']=='parent' else 0.)+(ehs if e['name']=='ZhongAn' else 0.)
            profit=operating+financial;fin_total+=financial;group_ni+=profit;owner_ni+=profit*own;opowner+=operating*own
            investment=reinvest*weight;e['cash']+=profit-investment
            e['retained'],e['reserve'],reserveadd=legal_update(e['retained'],e['reserve'],e['capital'],profit,p['reserve_rate'])
            d={'entity':e['name'],'ownership':own,'cash_before_operations':cash_start,'retained_start':ret_start,'reserve_start':res_start,'capital':e['capital'],'operating_profit_after_tax':operating,'financial_profit_after_tax':financial,'legal_profit_before_upstream':profit,'reserve_add':reserveadd,'investment':investment,'minimum_cash':floor,'support':0.,'declared':0.,'received_by_parent':0.,'minority_distribution':0.}
            detail.append(d)
        # Capital support uses parent cash, not new group profit or legal earnings.
        for e,d in zip(entities[1:],detail[1:]):
            gap=max(0.,d['minimum_cash']-e['cash'])
            if gap:
                parent['cash']-=gap;support+=gap;d['support']=gap
                inject_at_par(e,gap)
                d['capital']=e['capital'];d['ownership_after_injection']=e['ownership']
            request=max(0.,d['legal_profit_before_upstream'])*.7 if t<=5 else max(0.,e['retained'])
            e['cash'],e['retained'],div=pay(e['cash'],e['retained'],d['minimum_cash'],request)
            up=div*e['ownership'];minor=div-up;sub_div+=up;minor_div+=minor;d['declared']=div;d['minority_distribution']=minor
            if p['upstream_delay'] and t==2:pending+=up
            else:parent['cash']+=up;d['received_by_parent']=up
        # Only newly declared dividends enter parent legal profit.
        parent['retained'],parent['reserve'],upreserve=legal_update(parent['retained'],parent['reserve'],parent['capital'],sub_div,p['reserve_rate'])
        detail[0]['upstream_declared']=sub_div;detail[0]['upstream_reserve_add']=upreserve
        # Limited emergency line, permitted only to fund operations/obligations, never dividends.
        pmin=minimum*parent['weight'];needed=max(0.,pmin-parent['cash']);extra=min(needed,max(0.,p['max_extra_borrow']-used_extra))
        used_extra+=extra;debt+=extra;parent['cash']+=extra;borrow+=extra
        if parent['cash']+1e-8<pmin:ok=False;reason={'year':t,'cash':parent['cash'],'required':pmin,'zero_dividend_funding_gap':pmin-parent['cash']}
        ordinary_request=max(0.,opowner)*(p.get('payout_policy',[.40,.40,.42,.45,.45])[t-1] if t<=5 else 1.)
        # After five years, normal cash earnings net of ALL necessary reinvestment/debt service have priority.
        if t>5:ordinary_request=max(0.,opowner-reinvest*sum(e['weight']*d['ownership'] for e,d in zip(entities,detail))-maturity+borrow)
        parent['cash'],parent['retained'],ordinary=pay(parent['cash'],parent['retained'],pmin,ordinary_request) if ok else (parent['cash'],parent['retained'],0.)
        # Extra capital can only be paid with remaining legal profit AND cash, not a PV add-on.
        parent['cash'],parent['retained'],special=pay(parent['cash'],parent['retained'],pmin,parent['retained']) if ok and t>5 else (parent['cash'],parent['retained'],0.)
        for e,d in zip(entities,detail):d.update(cash_end=e['cash'],retained_end=e['retained'],reserve_end=e['reserve'],capital_end=e['capital'],ownership_end=e['ownership'])
        after=sum(e['cash'] for e in entities)
        expected=before+proceeds+old_receipt+prior_pending+group_ni-reinvest+borrow-maturity-minor_div-ordinary-special-pending
        assert abs(after-expected)<1e-6,(t,after,expected)
        assert all(e['reserve']<=e['capital']*.5+1e-8 for e in entities)
        row={'year':t,'revenue':rev,'growth':g,'nopat_margin':m,'nopat':nopat,'ehs_profit':ehs,'interest_after_tax':interest,'financial_profit':fin_total,'net_profit':group_ni,'owner_net_profit':owner_ni,'da':da,'maintenance_capex':maintenance,'growth_capex':growthcap,'working_capital_investment':dnwc,'net_reinvestment':reinvest,'earmarked_project_cash':earmarked,'opening_cash':before,'ending_cash':after,'debt_end':debt,'maturity':maturity,'borrow':borrow,'emergency_line_used':used_extra,'capital_support':support,'minority_dividends':minor_div,'subsidiary_upstream':sub_div,'dividend_receivable':pending,'old_dividend_receipt':old_receipt,'share_issue_cash':proceeds,'shares':shares,'ordinary':ordinary,'special':special,'distribution_per_share':(ordinary+special)/shares,'cash_conservation_error':after-expected,'feasible':ok,'entities':detail}
        rows.append(row)
        if not ok:break
    return {'parameters':p,'feasible':ok,'failure':reason,'rows':rows}

def valuation(sim,r):
    if not sim['feasible']:return {'feasible':False,'value_per_share':None,'reason':sim['failure']}
    rows=sim['rows'];n=len(rows);g=sim['parameters']['terminal_growth'];last=rows[-1]
    # Tail approximates recurring legally paid cash ONLY. Unreleased cash remains
    # explicit in entity states; horizon_check quantifies convergence and bounds.
    tail=last['distribution_per_share']*(1+g)/(r-g)
    pv=sum(x['distribution_per_share']/(1+r)**x['year'] for x in rows)+tail/(1+r)**n
    tv5=sum(x['distribution_per_share']/(1+r)**(x['year']-5) for x in rows if x['year']>5)+tail/(1+r)**(n-5)
    assert abs(pv-sum(x['distribution_per_share']/(1+r)**x['year'] for x in rows[:5])-tv5/(1+r)**5)<1e-8
    return {'feasible':True,'discount_rate':r,'value_per_share':pv,'year5_terminal_per_share':tv5,'year5_terminal_pv_fraction':tv5/(1+r)**5/pv,'tail_year':n,'tail_value_per_share':tail,'tail_pv_fraction':tail/(1+r)**n/pv,'first5_distributions':[x['distribution_per_share'] for x in rows[:5]]}

def selftests():
    # The same legal and cash waterfall called above; true independently hand-computable cases.
    a=legal_update(-20.,45.,100.,30.);assert a==(9.,46.,1.)
    b=pay(40.,a[0],10.,20.);assert b==(31.,0.,9.)
    c=legal_update(0.,49.,100.,50.);assert c==(49.,50.,1.)
    d=pay(100.,-2.,10.,50.);assert d==(100.,-2.,0.)
    entity={'capital':100.,'ownership':.6,'cash':0.}
    assert inject_at_par(entity,100.)==.8 and entity['capital']==200. and entity['cash']==100.
    # Formal valuation function: perpetual 1/share from t1, r10%, g0 => 10, TV5=10.
    s={'feasible':True,'parameters':{'terminal_growth':0.},'rows':[{'year':i,'distribution_per_share':1.} for i in range(1,61)]}
    v=valuation(s,.1);assert abs(v['value_per_share']-10.)<1e-10 and abs(v['year5_terminal_per_share']-10.)<1e-10
    # A required zero-dividend financing failure must never be priced.
    fail=simulate(params('funding_break'));assert not fail['feasible'] and valuation(fail,.1)['value_per_share'] is None
    return {'at_par_support':'pass: parent owns60/100 and funds100 alone =>160/200=80%', 'legal_loss_then_reserve_then_dividend':'pass: profit30 offsets loss20; reserve1; cash dividend9','reserve_cap':'pass: reserve49 to50 only1','negative_retained':'pass: no dividend','formal_valuation_perpetuity':'pass: PV10 and TV5=10','finite_funding_failure':'pass','scope':'legal waterfall / valuation chain and cash conservation; not business assumptions'}

def horizon_check(sim):
    if not sim['feasible']:return {'feasible':False,'failure':sim['failure']}
    result={}
    for n in (60,100,140):
        rows=sim['rows'][:n];last=rows[-1];g=sim['parameters']['terminal_growth']
        rates={str(r):valuation(dict(sim,rows=rows),r) for r in INPUTS['rates']}
        ds=[rows[i]['distribution_per_share']/rows[i-1]['distribution_per_share']-1 for i in range(n-5,n) if rows[i-1]['distribution_per_share']>0]
        assert max(abs(v-g) for v in ds)<1e-6, ('nonconverged_distribution_tail',sim['parameters']['scenario'],n,ds)
        assert abs(last['debt_end'])<1e-8 and abs(last['dividend_receivable'])<1e-8, ('unresolved_finance',n)
        blocked=sum(d['cash_end']*d['ownership_end'] for d in last['entities'] if d['retained_end']<=0)
        excess=sum(max(0,d['cash_end']-d['minimum_cash'])*d['ownership_end'] for d in last['entities'])
        result[str(n)]={'feasible':True,'full_year_state':last,'last_five_distribution_growth':ds,'max_growth_error_vs_g':max(abs(v-g) for v in ds),'unreleased_legally_blocked_cash_owner':blocked,'cash_above_operating_and_project_minima_owner':excess,'blocked_cash_upper_value_if_immediate_release_at_horizon':{str(r):blocked/last['shares']/(1+r)**n for r in INPUTS['rates']},'blocked_cash_undiscounted_per_share_bound':blocked/last['shares'],'valuations':rates,'boundary_note':'未分配本金留在主体现金，未加进终值。累亏主体现金仅给无成本合法退出上限；经营最低现金支持已估值业务，不可同时作为清算现金加值。'}
    result['value_convergence']={str(r):{'delta_60_to_100':result['100']['valuations'][str(r)]['value_per_share']-result['60']['valuations'][str(r)]['value_per_share'],'delta_100_to_140':result['140']['valuations'][str(r)]['value_per_share']-result['100']['valuations'][str(r)]['value_per_share']} for r in INPUTS['rates']}
    assert all(abs(d['delta_100_to_140'])<.001 for d in result['value_convergence'].values()),result['value_convergence']
    return result

def build():
    cases={k:simulate(params(k)) for k in ['base','cyclical','structural','optimistic','margin_minus_1pp_y2','wc_plus_10pp_y2','upstream_delay_y2','no_refinance','capex_plus_200_y2','parent_cash_minus400','minority_ownership50','funding_break']}
    vals={k:{str(r):valuation(s,r) for r in INPUTS['rates']} for k,s in cases.items()}
    b=cases['base'];lo=vals['base']['0.1'];hi=vals['base']['0.09']
    # Secondary residual-income / justified PB on fully diluted common equity.
    bv=5036.94792766
    secondary_values=[]
    for rate,roe in [(.10,.105),(.09,.12)]:
        option_pv=sum(INPUTS['remaining_options']/2*(INPUTS['exercise_price'] if t==1 else INPUTS['exercise_price_year2'])/(1+rate)**t for t in [1,2])
        fd=INPUTS['issued_shares']+INPUTS['remaining_options']
        secondary_values.append((bv+option_pv)/fd*(roe-.02)/(rate-.02))
    secondary={'opening_common_book_equity':bv,'fully_diluted_shares':fd,'normalized_roe':[.105,.12],'discount_rates':[.10,.09],'growth':.02,'value_range':secondary_values,'method':'剩余收益/合理PB=(ROE-g)/(r-g)；普通股账面净资产已扣债务、少数和库存股，未来期权现金折现计入；不另加净现金。'}
    return {'company':'CN:002967','model_as_of':ASOF,'units':'CNY million except per-share CNY and shares million','inputs':INPUTS,'core_value_range':{'low':round(lo['value_per_share'],2),'high':round(hi['value_per_share'],2)},'year5_terminal_range':{'low':round(lo['year5_terminal_per_share'],2),'high':round(hi['year5_terminal_per_share'],2)},'base_distributions':[round(x['distribution_per_share'],6) for x in b['rows'][:5]],'valuations':vals,'horizon_checks':{k:horizon_check(s) for k,s in cases.items()},'scenarios':cases,'secondary':secondary,'tests':selftests()}
if __name__=='__main__':
    out=build();path=pathlib.Path(__file__).with_name('2026-Q3-output.json');path.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'))+'\n');print(json.dumps({k:out[k] for k in ['core_value_range','year5_terminal_range','base_distributions','secondary','tests']},ensure_ascii=False,indent=2))

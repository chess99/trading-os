#!/usr/bin/env python3
"""广电计量 2026Q3: named-entity constraints and explicit economic remittance budgets; CNY million.
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
 'legacy_tax':False,'node_tax_rates':[.15]*7,'qualification_fail_from':None,'tax_loss_years':5,
 'zhong_nested_minor_buffer':.75,'zhong_parent_claim':0., 'debt_rate':.035,'tax':.15,'cash_yield':.013,
 'max_extra_borrow':500.,'refinance_year3':500.,'min_cash_ratio':.15,
 'old_dividend_receivable':0.,'parent_retained0':666.89041865-92.5144512,
 'parent_reserve0':166.61911677,'reserve_rate':.10,
 'repayments':[847.,100.,1000.,100.,100.],
 'years':140,'rates':[.10,.09],
 'parent_registered_h1':637.279952,'parent_registered_start_budget':639.621152,
 'entity_evidence':{'parent':'H1注册637.279952；Q3股本639.621152是登记预算，法定166.61911677/留存666.89041865减已派92.5144512来自母表。','Wuxi/Chengdu/Tianjin':'注册250/100/50实披；储备30/10/5与留存0、现金及未来利润均预算。','ZhongAn':'H1注册50、母81.28%实披；期初亏损-60及储备0预算。未来单方at-par需批准，现金到位/登记分别测试。','other_pools':'非法律主体；资本/储备字段为经济留存预算，不是注册/法定余额，不进行虚构法人股权稀释。'},
 'pool_notes':'母公司/无锡/成都/天津单列；其他全资盈利实体仅按逐家正利润预算汇总，亏损和少数主体独立，禁止跨主体弥补；未知储备不加价。',
 'entities':[
  {'name':'parent','weight':.45,'ownership':1.,'cash':2050.,'capital':639.621152,'reserve':166.61911677,'retained':574.37596745},
  {'name':'Wuxi','weight':.08,'ownership':1.,'cash':120.,'capital':250.,'reserve':30.,'retained':0.},
  {'name':'Chengdu','weight':.06,'ownership':1.,'cash':60.,'capital':100.,'reserve':10.,'retained':0.},
  {'name':'Tianjin','weight':.06,'ownership':1.,'cash':60.,'capital':50.,'reserve':5.,'retained':0.},
  {'name':'other_wholly_profitable','weight':.32,'ownership':1.,'cash':260.,'capital':1200.,'reserve':100.,'retained':0.},
  {'name':'other_minorities','weight':.03,'ownership':.65,'cash':60.,'capital':100.,'reserve':10.,'retained':0.},
  {'name':'ZhongAn','weight':0.,'ownership':.8128,'cash':26.06493146,'capital':50.,'reserve':0.,'retained':-60.}
 ]}

def legal_update(retained,reserve,capital,profit,rate=.1):
    """New legal profit first offsets accumulated loss, then statutory reserve."""
    covered=min(max(profit,0.),max(-retained,0.))
    accrual=min(max(0.,profit-covered)*rate,max(0.,capital*.5-reserve))
    return retained+profit-accrual,reserve+accrual,accrual

def governance_update(available,budget_buffer,reference_capital,forecast_profit,rate=.1):
    """Finite economic retention budget for unallocated small entities, NOT a
    Company Law statutory pool. No cross-entity legal account is asserted.
    The two proxy buffers are explicitly stress-tested; legal facts stay null.
    """
    held=min(max(0.,forecast_profit-min(max(forecast_profit,0.),max(-available,0.)))*rate,max(reference_capital*.5-budget_buffer,0.))
    return available+forecast_profit-held,budget_buffer+held,held

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

def cash_tax_bridge(normalized_after_tax_operating,ehs,gross_financial,gross_interest,rate,loss_buckets,year,loss_years=5,proxy=False):
    # The NOPAT margin is a normalized post15% operating budget, not a reported entity tax rate.
    gross=normalized_after_tax_operating/.85 if normalized_after_tax_operating>0 else normalized_after_tax_operating
    gross+=ehs
    buckets=[v[:] for v in loss_buckets if v[0]>=year];available=sum(v[1] for v in buckets)
    def tax(x):return max(x-available,0.)*rate
    t0=tax(gross);t1=tax(gross-gross_interest);t2=tax(gross-gross_interest+gross_financial)
    net_interest=gross_interest-(t0-t1);net_op=gross-t0-net_interest
    net_fin=gross_financial-(t2-t1);base=gross-gross_interest+gross_financial
    used=min(max(base,0.),available);remaining=used
    for v in buckets:
        take=min(v[1],remaining);v[1]-=take;remaining-=take
    if base<0 and not proxy and loss_years:buckets.append([year+loss_years,-base])
    buckets=[v for v in buckets if v[1]>1e-10]
    return dict(operating_net=net_op,financial_net=net_fin,cash_tax=t2,interest_net=net_interest,
       tax_rate=rate,pretax_operating=gross,taxable_before_losses=base,loss_used=used,loss_buckets=buckets,
       current_interest_shield=t0-t1,generated_loss=max(-base,0.))

def liquidation_waterfall(cash,current_assets,noncurrent_assets,current_recovery,noncurrent_recovery,friction,total_liabilities,parent_claim,ownership,parent_equity_cost,tax_rate=.15,nested_minor_buffer=0.):
    # Haircut assets, not net assets. Full creditor face paid before shareholder residual.
    assert 0<=parent_claim<=total_liabilities and 0<=ownership<=1
    sales=current_assets*current_recovery+noncurrent_assets*noncurrent_recovery
    costs=(cash+sales)*friction
    asset_gain=sales-current_assets-noncurrent_assets-costs
    asset_tax=max(asset_gain,0.)*tax_rate # no instant refund for losses; no unverified opening tax credits
    available=max(cash+sales-costs-asset_tax,0.)
    external=total_liabilities-parent_claim
    paid_external=min(available,external);available-=paid_external
    paid_parent_claim=min(available,parent_claim);available-=paid_parent_claim
    shortage=external-paid_external+parent_claim-paid_parent_claim
    residual=available if shortage<1e-8 else 0.
    nested_minor=min(max(nested_minor_buffer,0.),residual)
    parent_equity=(residual-nested_minor)*ownership;minority=residual-parent_equity
    gain=parent_equity-parent_equity_cost
    parent_tax=max(gain,0.)*tax_rate # conservative realized positive gain tax budget
    return dict(feasible=shortage<1e-8,creditor_shortfall=shortage,asset_sale_proceeds=sales,
       closure_friction=costs,asset_tax=asset_tax,external_creditors_due=external,external_creditors_paid=paid_external,
       parent_claim_due=parent_claim,parent_claim_repaid=paid_parent_claim,shareholder_residual=residual,
       nested_minor_buffer_paid=nested_minor,parent_equity_receipt=parent_equity,minority_receipt=minority,parent_equity_cost=parent_equity_cost,
       parent_equity_disposal_result=gain,parent_disposal_tax=parent_tax,
       parent_total_cash=paid_parent_claim+parent_equity-parent_tax)

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
    if kind=='registration_delay_1y':
        p['registration_delay']=True;p['entities'][0]['capital']=p['parent_registered_h1'];p['scope']='cash support now; registered/share-right effect next year; parent H1 registered anchor plus catch-up next year'
    elif kind=='pooled_retention_double':
        for e in p['entities'][4:6]:e['capital']*=2
        p['scope']='economic retention reference budgets only; not statutory registered capital'
    elif kind=='pooled_retention_zero':
        for e in p['entities'][4:6]:e['capital']=e['reserve']*2
        p['scope']='no additional proxy retention; still cash/earnings/reinvestment constrained, not free upstream'
    if kind=='pool_tax25':p['node_tax_rates'][4:6]=[.25,.25]
    if kind=='pool_tax5':p['node_tax_rates'][4:6]=[.05,.05]
    if kind=='named_qualification_fail_y1':p['qualification_fail_from']=1
    if kind=='named_qualification_fail_y3':p['qualification_fail_from']=3
    if kind=='no_generated_tax_loss_credit':p['tax_loss_years']=0
    if kind=='zhong_parent_claim_upper':p['zhong_parent_claim']=18.67373031
    if kind=='zhong_nested_minor_zero':p['zhong_nested_minor_buffer']=0.
    if kind=='zhong_nested_minor_double':p['zhong_nested_minor_buffer']=1.5
    if kind=='zhong_debt_overlap_upper':p['zhong_parent_claim']=51.66769031
    if kind=='zhong_creditor_shortfall':p.update(zhong_current_asset_recovery=.05,zhong_noncurrent_asset_recovery=0.)
    if kind!='structural':p.setdefault('zhong_exit_year',10)
    if kind=='zhong_exit_delay_y20':p['zhong_exit_year']=20
    if kind=='zhong_no_exit_extreme':p['zhong_exit_year']=0
    if kind=='zhong_asset_recovery_low':p.update(zhong_current_asset_recovery=.7,zhong_noncurrent_asset_recovery=.3,zhong_exit_friction=.1)
    if kind=='zhong_asset_recovery_high':p.update(zhong_current_asset_recovery=.95,zhong_noncurrent_asset_recovery=.7,zhong_exit_friction=.03)
    p['frozen']='share schedule, tax, reserve law, opening entity cash and retained earnings; only declared scenario inputs differ'
    return p

def simulate(p):
    entities=copy.deepcopy(p['entities']);parent=entities[0]
    debt=p['debt0'];rev=p['revenue0'];shares=p['issued_shares']-p['treasury_shares'];used_extra=0.;pending=0.;rows=[];ok=True;reason=None
    zhong_basis=p.get('zhong_parent_investment_carrying_cost',235.85082384);zhong_closed=False
    loss_buckets=[[] for _ in entities]
    registration_pending=[0.]*len(entities)
    if p.get('registration_delay'):registration_pending[0]=p['parent_registered_start_budget']-p['parent_registered_h1']
    for t in range(1,p['years']+1):
        # Delayed-registration case does not defer cash payment or create free funding.
        if p.get('registration_delay') and t>1:
            for i,e in enumerate(entities):
                amt=registration_pending[i]
                if amt:
                    old=e['capital'];e['capital']+=amt
                    if i>0:e['ownership']=(old*e['ownership']+amt)/e['capital']
            registration_pending=[0.]*len(entities)
        oldrev=rev;g=p['growth'][t-1] if t<=len(p['growth']) else p['terminal_growth'];rev*=1+g
        m=p['nopat_margins'][t-1] if t<=len(p['nopat_margins']) else p['terminal_margin']
        if t>=p['effective_year']:m+=p['margin_shift']
        nopat=rev*m
        ehs=p['support_loss'][t-1] if t<=5 else -p.get('permanent_ehs_loss',0.)*(1+p['terminal_growth'])**(t-5)
        if zhong_closed:ehs=0.
        gross_debt_interest=debt*p['debt_rate'];interest=gross_debt_interest*(1-p['tax'])
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
        proceeds=exercise*(p['exercise_price'] if t==1 else p['exercise_price_year2']);parent['cash']+=proceeds
        if p.get('registration_delay'):registration_pending[0]+=exercise
        else:parent['capital']+=exercise
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
            floor=0. if e.get('closed') else minimum*weight if weight else 20.
            financial=0. if e.get('closed') else max(0.,cash_start-floor)*p['cash_yield']*(1-p['tax'])
            operating=nopat*weight-(interest if e['name']=='parent' else 0.)+(ehs if e['name']=='ZhongAn' else 0.)
            tax_detail={}
            idx=entities.index(e)
            if not p.get('legacy_tax',False):
                rate=p['node_tax_rates'][idx]
                if p.get('qualification_fail_from') is not None and t>=p['qualification_fail_from'] and idx not in [4,5]:rate=.25
                gross_fin=0. if e.get('closed') else max(cash_start-floor,0.)*p['cash_yield']
                tax_detail=cash_tax_bridge(nopat*weight,ehs if idx==6 else 0.,gross_fin,gross_debt_interest if idx==0 else 0.,rate,loss_buckets[idx],t,p['tax_loss_years'],e['name'].startswith('other_'))
                loss_buckets[idx]=tax_detail['loss_buckets'];operating=tax_detail['operating_net'];financial=tax_detail['financial_net']
                if idx==0:interest=tax_detail['interest_net']
            profit=operating+financial;fin_total+=financial;group_ni+=profit;owner_ni+=profit*own;opowner+=operating*own
            investment=reinvest*weight;e['cash']+=profit-investment
            is_proxy=e['name'].startswith('other_')
            update=governance_update if is_proxy else legal_update
            e['retained'],e['reserve'],reserveadd=update(e['retained'],e['reserve'],e['capital'],profit,p['reserve_rate'])
            d={'tax_details':tax_detail,'node_kind':'economic_governance_pool' if is_proxy else 'named_company','registered_capital_open':None if is_proxy else e['capital'],'capital_evidence':'budget proxy' if is_proxy else 'reported base plus forecast registered changes','entity':e['name'],'ownership':own,'cash_before_operations':cash_start,'retained_start':ret_start,'reserve_start':res_start,'capital':e['capital'],'operating_profit_after_tax':operating,'financial_profit_after_tax':financial,'legal_profit_before_upstream':profit,'reserve_add':reserveadd,'investment':investment,'minimum_cash':floor,'support':0.,'declared':0.,'received_by_parent':0.,'minority_distribution':0.}
            detail.append(d)
        # Capital support uses parent cash, not new group profit or legal earnings.
        for e,d in zip(entities[1:],detail[1:]):
            gap=max(0.,d['minimum_cash']-e['cash'])
            if gap:
                parent['cash']-=gap;support+=gap;d['support']=gap
                if e['name']=='ZhongAn':zhong_basis+=gap
                if e['name'].startswith('other_'):
                    # Governance support budget, not issuance by a fictitious company.
                    # Ownership remains portfolio assumption; no invented at-par dilution.
                    e['cash']+=gap;e['capital']+=gap
                elif p.get('registration_delay'):
                    e['cash']+=gap;registration_pending[entities.index(e)]+=gap
                else:inject_at_par(e,gap)
                d['capital']=e['capital'];d['ownership_after_injection']=e['ownership']
            request=max(0.,d['legal_profit_before_upstream'])*.7 if t<=5 else max(0.,e['retained'])
            e['cash'],e['retained'],div=pay(e['cash'],e['retained'],d['minimum_cash'],request)
            up=div*e['ownership'];minor=div-up;sub_div+=up;minor_div+=minor;d['declared']=div;d['minority_distribution']=minor
            if p['upstream_delay'] and t==2:pending+=up
            else:parent['cash']+=up;d['received_by_parent']=up
        # Optional approved cash-only closure. Not a compulsory liquidation core assumption.
        # Investment carrying cost is not registered capital. No tax credit for disposal loss.
        exit_record=None;exit_cost=0.;exit_minor=0.;exit_asset_recovery=0.;exit_liability_settlement=0.
        if t==p.get('zhong_exit_year',0):
            z=entities[-1];zd=detail[-1];gross=max(z['cash'],0.)
            noncash_current=201.25409215-26.06493146;noncurrent=45.57958246
            waterfall=liquidation_waterfall(gross,noncash_current,noncurrent,p.get('zhong_current_asset_recovery',.8),p.get('zhong_noncurrent_asset_recovery',.5),p.get('zhong_exit_friction',.03),51.66769031,p.get('zhong_parent_claim',0.),z['ownership'],zhong_basis,(.25 if p.get('qualification_fail_from') is not None and t>=p['qualification_fail_from'] else p['node_tax_rates'][6]),0. if p.get('legacy_tax',False) else p.get('zhong_nested_minor_buffer',.75))
            if not waterfall['feasible']:
                return {'parameters':p,'feasible':False,'failure':{'year':t,'reason':'closure assets insufficient for full creditor face; no automatic parent guarantee','waterfall':waterfall},'rows':rows}
            exit_asset_recovery=waterfall['asset_sale_proceeds'];exit_liability_settlement=waterfall['external_creditors_paid']
            exit_cost=waterfall['closure_friction']+waterfall['asset_tax']+waterfall['parent_disposal_tax'];exit_minor=waterfall['minority_receipt']
            parent_receipt=waterfall['parent_total_cash'];parent['cash']+=parent_receipt
            parent_disposal_result=waterfall['parent_equity_disposal_result']-waterfall['parent_disposal_tax']
            parent['retained'],parent['reserve'],disposal_reserve=legal_update(parent['retained'],parent['reserve'],parent['capital'],parent_disposal_result,p['reserve_rate'])
            exit_record={'assumed_approved_closure_year':t,'cash_before_closure':gross,'creditor_and_closure_friction':exit_cost,'parent_ownership':z['ownership'],'parent_receipt':parent_receipt,'minority_receipt':exit_minor,'parent_investment_carrying_cost':zhong_basis,'parent_disposal_result':parent_disposal_result,'parent_disposal_reserve':disposal_reserve,'noncash_current_asset_book_budget':noncash_current,'noncurrent_asset_book_budget':noncurrent,'noncash_asset_sale_proceeds':exit_asset_recovery,'liabilities_settled_at_face':51.66769031,'external_liabilities_paid':exit_liability_settlement,'noncash_asset_disposal_result':exit_asset_recovery-noncash_current-noncurrent,'tax_credit':0.,'waterfall':waterfall,'original_parent_units':50*.8128,'original_minority_units':50*(1-.8128),'subscribed_new_units':z['capital']-50,'equity_units_cancelled':z['capital'],'parent_equity_cost_cancelled':zhong_basis,'parent_claim_cancelled':waterfall['parent_claim_repaid']}
            z.update(cash=0.,retained=0.,reserve=0.,capital=0.,closed=True);zhong_closed=True;registration_pending[-1]=0.
            zd['exit_record']=exit_record;zd['minimum_cash']=0.
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
        for e,d in zip(entities,detail):d.update(registered_capital_end=None if e['name'].startswith('other_') else e['capital'],pending_registered_contribution=registration_pending[entities.index(e)],cash_end=e['cash'],retained_end=e['retained'],reserve_end=e['reserve'],capital_end=e['capital'],ownership_end=e['ownership'])
        after=sum(e['cash'] for e in entities)
        expected=before+proceeds+old_receipt+prior_pending+group_ni-reinvest+borrow-maturity-minor_div-ordinary-special-pending+exit_asset_recovery-exit_liability_settlement-exit_cost-exit_minor
        assert abs(after-expected)<1e-6,(t,after,expected)
        assert all(e['reserve']<=e['capital']*.5+1e-8 for e in entities)
        row={'capital_realization':exit_record,'year':t,'revenue':rev,'growth':g,'nopat_margin':m,'nopat':nopat,'ehs_profit':ehs,'interest_after_tax':interest,'financial_profit':fin_total,'net_profit':group_ni,'owner_net_profit':owner_ni,'da':da,'maintenance_capex':maintenance,'growth_capex':growthcap,'working_capital_investment':dnwc,'net_reinvestment':reinvest,'earmarked_project_cash':earmarked,'opening_cash':before,'ending_cash':after,'debt_end':debt,'maturity':maturity,'borrow':borrow,'emergency_line_used':used_extra,'capital_support':support,'minority_dividends':minor_div,'subsidiary_upstream':sub_div,'dividend_receivable':pending,'old_dividend_receipt':old_receipt,'share_issue_cash':proceeds,'shares':shares,'ordinary':ordinary,'special':special,'distribution_per_share':(ordinary+special)/shares,'cash_conservation_error':after-expected,'feasible':ok,'entities':detail}
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
    assert legal_update(0.,5.,20.,10.)==(9.,6.,1.) # registered20 paid10 remains below threshold
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
    cases={k:simulate(params(k)) for k in ['base','cyclical','structural','optimistic','margin_minus_1pp_y2','wc_plus_10pp_y2','upstream_delay_y2','no_refinance','capex_plus_200_y2','parent_cash_minus400','minority_ownership50','funding_break','registration_delay_1y','pooled_retention_double','pooled_retention_zero','zhong_exit_delay_y20','zhong_no_exit_extreme','zhong_asset_recovery_low','zhong_asset_recovery_high','pool_tax25','pool_tax5','named_qualification_fail_y1','named_qualification_fail_y3','no_generated_tax_loss_credit','zhong_parent_claim_upper','zhong_debt_overlap_upper','zhong_nested_minor_zero','zhong_nested_minor_double','zhong_creditor_shortfall']}
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
def pack_output(out):
    """Lossless deterministic per-scenario encoding; valuation summaries remain readable."""
    import base64,gzip,hashlib
    result=copy.deepcopy(out)
    for scenario in result['scenarios'].values():
        rows=scenario.pop('rows')
        raw=json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()
        scenario['annual_rows']={'encoding':'gzip+base64','row_count':len(rows),
            'expanded_sha256':hashlib.sha256(raw).hexdigest(),
            'data':base64.b64encode(gzip.compress(raw,mtime=0)).decode('ascii')}
    result['output_layout']={'schema':'lossless_scenario_gzip_base64_v1',
        'expand':'python 2026-Q3.py --expand > expanded.json',
        'note':'Decode each scenarios.*.annual_rows.data with base64 then gzip; JSON array is original rows, all fields and float precision retained.'}
    return result

def expand_output(packed):
    import base64,gzip,hashlib
    result=copy.deepcopy(packed);result.pop('output_layout',None)
    for scenario in result['scenarios'].values():
        encoded=scenario.pop('annual_rows')
        raw=gzip.decompress(base64.b64decode(encoded['data']))
        assert hashlib.sha256(raw).hexdigest()==encoded['expanded_sha256']
        scenario['rows']=json.loads(raw)
        assert len(scenario['rows'])==encoded['row_count']
    return result

if __name__=='__main__':
    import sys
    path=pathlib.Path(__file__).with_name('2026-Q3-output.json')
    if '--expand' in sys.argv:
        print(json.dumps(expand_output(json.loads(path.read_text())),ensure_ascii=False,separators=(',',':')))
    else:
        out=build();packed=pack_output(out)
        assert expand_output(packed)==out
        data=json.dumps(packed,ensure_ascii=False,separators=(',',':'))+'\n'
        assert len(data.encode())<16*1024*1024
        path.write_text(data)
        print(json.dumps({k:out[k] for k in ['core_value_range','year5_terminal_range','base_distributions','secondary','tests']},ensure_ascii=False,indent=2))

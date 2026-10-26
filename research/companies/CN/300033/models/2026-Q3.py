#!/usr/bin/env python3
"""CN300033. CNY billion, shares billion. Standard library only; no live prices.
Individual company allocations are distribution budgets, not audited segment forecasts.
Annual periods end 2027-10-26 onward; far years are numerical integration only.
"""
import json, copy, math, gzip, base64, hashlib, sys
from pathlib import Path
NAMES=['listed_parent','Hexin_Software','Intelligent_Technology','Zhifu_Software','Data_Development','Network_Technology','offshore_economic_recovery_budget','Hexin_downstream_distribution_budget']
SHARES=.75264
ASOF='2026-10-26T00:00:00+08:00'
PARAM={
 'revenue':[7.8,8.346,8.84676,9.3775656,9.84644388], 'margin':[.48]*5,
 'g_after5':.04,'g_long':.02,'margin_long':.42,'tax':.15,'discount':.10,
 'cash':[2.4,.325,1.45,.30,2.4,2.36567701089,.918,.325],
 'capacity_budget':[2.7,.35,.9,.2,1.2,1.1,.5,.35],
 'registered_capital_budget':[.75264,.03,.30,.01,.20766,.055,None,None],
 'reserve_budget':[.36081535125,0.,0.,0.,0.,0.,None,None],
 'weights':[0.,.115,.27,.22,.16,.12,0.,.115],
 'parent_cost':.16,'cash_yield':.012,'loan_rate':.03,'external_rate':.05,'external_limit':.5,
 'liquidity_ratio':.12,'contract_ratio':3.09069063185/7.8,'working_ratio':.01,
 'capital_ratio':.20,'initial_fixed':1.70810491672,'initial_working':.078,
 'construction':[.18,.11,.06,0,0], 'normal_payout':.80,'upstream_payout':.80,'release_fraction':.20,
 'release_start':6,'upstream_lag':0,'parent_extra_cost':0.,'terminal_mode':'base',
 'receiver':[None,0,0,0,0,0,0,1], 'upstream_order':[7,1,2,3,4,5,6],
 'opening_distribution':0.,'continue_reserve':False,
 'tax_mode':'entity','operating_tax_rates':[.25,.15,.15,.25,.15,.25,.20,.20],
 'reverse_loan_start':10,'reverse_maturity_year':None,'reverse_periodic_settlement':5,'reverse_loan_limits':[0,.325,1.45,.30,2.4,2.36567701089,0,0],
 'offshore_exit_year':10,'offshore_realizability':.90,'offshore_cost_budget':.4007804,'offshore_tax_basis_ratio':1.,
 'marginal_interest_tax':[.25,.15,.15,.25,.15,.25,.20,.20],
 'hk_parent_investment_cost':.4007804,
 'parent_capital_return_start':15,'parent_minimum_registered':.05,'parent_reduction_fee':.02, 'economic_realization_start':10,'economic_realization_interval':5,'economic_realization_fee':.02,'economic_dividend_capacity_ratio':.5,'economic_capital_share':1.,'domestic_capital_tax_basis_ratio':1.,'domestic_parent_cost_budget':[0,.00133118242,.30,.01,.20766,.055,0,.2317],
 'notes':'Point cash and remittance-capacity allocations are economic budgets, not certified individual legal balances. Original-holder bundles remain normalized by initial0.75264bn shares after proportional cancellation; issued_shares tracks actual future shares. Native foreign capital and parent carrying cost are separate facts; no synthetic registration. Loan direction and principal/declared-profit offsets explicit.'}

def legal_roll(retained,reserve,capital,profit,continue_reserve=False):
    # Prior losses consumed first; capital injection changes the reserve ceiling through capital.
    if capital is None:return retained+profit,None,0. # budget nodes have NO Chinese statutory pool
    old=retained; eligible=max(profit-max(-old,0),0)
    add=.10*eligible if continue_reserve else min(.10*eligible,max(.50*capital-reserve,0))
    return retained+profit-add,reserve+add,add

def annual_inputs(p,t,previous_revenue):
    if t<=5: rev=p['revenue'][t-1];margin=p['margin'][t-1]
    else:
        f=min((t-5)/10,1);g=p['g_after5']*(1-f)+p['g_long']*f
        rev=previous_revenue*(1+g)
        margin=p['margin'][-1]*(1-f)+p['margin_long']*f
    return rev,margin

def run(p,years=300,initial=None,start=1):
    p=copy.deepcopy(p);m=len(NAMES);w=p['weights']; rows=[]
    s=copy.deepcopy(initial) if initial else {'cash':p['cash'][:],'capacity_budget':p['capacity_budget'][:], 'reserve_budget':p['reserve_budget'][:], 'registered_capital_budget':p['registered_capital_budget'][:], 'loans':[0.]*m,'external':[0.]*m,'payable':[0.]*m,'rev':7.8,'fixed':p['initial_fixed'],'working':p['initial_working'],'contract':3.09069063185,'issued_shares':SHARES, 'original_holder_fraction':1.,'domestic_parent_cost_remaining':p.get('domestic_parent_cost_budget',[0.]*m)[:], 'offshore_parent_investment_cost_budget_remaining':p.get('hk_parent_investment_cost',.4007804)}
    for t in range(start,start+years):
        opening=copy.deepcopy(s);rev,margin=annual_inputs(p,t,s['rev'])
        periodic=p.get('reverse_periodic_settlement');settle_reverse=(t==p.get('reverse_maturity_year') or (periodic and t>p['reverse_loan_start'] and (t-p['reverse_loan_start'])%periodic==0))
        parent_cost=p['parent_cost']*(rev/7.8)
        own_pretax=[-parent_cost-p['parent_extra_cost']]+[(rev*margin+parent_cost)*w[i] for i in range(1,m)]
        rates=p['operating_tax_rates'] if p.get('tax_mode')=='entity' else [p['tax']]*m
        operating_taxes=[max(x,0)*rates[i] for i,x in enumerate(own_pretax)]
        own=[own_pretax[i]-operating_taxes[i] for i in range(m)];operating=sum(own)
        if p.get('tax_mode')=='legacy_aftertax_allocation':
            operating=rev*margin*(1-p['tax'])
            own=[-parent_cost-p['parent_extra_cost']]+[(operating+parent_cost)*w[i] for i in range(1,m)]
        interest=[x*p['cash_yield'] for x in s['cash']]
        financing=[s['external'][i]*p['external_rate'] for i in range(m)]
        interinterest=[0.]+[s['loans'][i]*p['loan_rate'] for i in range(1,m)];interinterest[0]=-sum(interinterest)
        # Operating own[] and cash_yield are after-tax economic budgets. Loan3% is
        # pretax: separately budget marginal cash tax with no instant loss refund.
        marginal_tax=p.get('marginal_interest_tax',[0.]*m)
        interest_tax=[]
        for i in range(m):
            rate=marginal_tax[i];base=own_pretax[i]+interest[i]/(1-rate)
            interest_tax.append((max(base-interinterest[i],0)-max(base,0))*rate)
        profits=[own[i]+interest[i]-financing[i]-interinterest[i]-interest_tax[i] for i in range(m)]
        fixed_target=p['initial_fixed']+p['capital_ratio']*(rev-7.8)+sum(p['construction'][:min(t,5)])
        fixed_target=max(fixed_target,.6);growth_capex=fixed_target-s['fixed']
        depreciation=rev*.02;capex=depreciation+growth_capex
        # Asset shrinkage requires realised disposal; limit disposal to depreciation, avoiding fictional sale proceeds.
        if capex<0: capex=0.;growth_capex=-depreciation;fixed_target=s['fixed']+growth_capex
        working=rev*p['working_ratio'];dworking=working-s['working']
        contract=rev*p['contract_ratio'];dcontract=contract-s['contract']
        reinvest=growth_capex+dworking
        cashflow=[profits[0]]+[profits[i]-reinvest*w[i]+dcontract*w[i] for i in range(1,m)]
        s['cash']=[s['cash'][i]+cashflow[i] for i in range(m)]
        # Prior declared dividends settle as cash only: no repeated income/profit at parent.
        settlements=[0.]*m
        for i in range(1,m):
            settlements[i]=s['payable'][i];s['cash'][i]-=settlements[i];s['cash'][p['receiver'][i]]+=settlements[i];s['payable'][i]=0.
        floors=[.3]+[(rev*p['liquidity_ratio']+contract)*w[i] for i in range(1,m)]
        newloans=[0.]*m;loanrepay=[0.]*m;external_new=[0.]*m;external_repaid=[0.]*m
        # Explicit shareholder loans, not anonymous liquidity. No assumed new equity or infinite finance.
        for i in range(1,m):
            need=max(floors[i]-s['cash'][i],0);lend=min(need,max(s['cash'][0]-floors[0],0)) if i in (1,2,3,4,5) else 0.
            s['cash'][0]-=lend;s['cash'][i]+=lend;s['loans'][i]+=lend;newloans[i]=lend
        for i in range(1,m):
            need=max(floors[i]-s['cash'][i],0);borrow=min(need,max(p['external_limit']-sum(s['external']),0))
            s['cash'][i]+=borrow;s['external'][i]+=borrow;external_new[i]=borrow
            if s['cash'][i]<floors[i]-1e-8: raise ValueError('Unfunded even with zero dividends: '+NAMES[i]+' year '+str(t))
        for i in range(m):
            repay=min(max(s['cash'][i]-floors[i],0),s['external'][i]);s['cash'][i]-=repay;s['external'][i]-=repay;external_repaid[i]=repay
        for i in range(1,m):
            repay=min(max(s['cash'][i]-floors[i],0),max(s['loans'][i],0));s['cash'][i]-=repay;s['cash'][0]+=repay;s['loans'][i]-=repay;loanrepay[i]=repay
        recovery={'gross':0.,'net':0.,'friction':0.,'investment_cost_released':0.,'parent_profit_effect':0.,'cash_tax':0.,'scope':'conditional disposal/repatriation of financial offshore portfolio; named HK holding cost is budget anchor, not portfolio registration or confirmed holding chain'}
        parent_base_taxable=own_pretax[0]+interest[0]/.75-interinterest[0]-financing[0]
        offshore_exit_taxable=0.
        if t==p.get('offshore_exit_year') and s['cash'][6]>0:
            gross=max(0,s['cash'][6]-floors[6]-s['payable'][6]);cost=p['offshore_cost_budget']
            proceeds=gross*p['offshore_realizability'];offshore_exit_taxable=max(proceeds-cost*p['offshore_tax_basis_ratio'],0)
            tax=(max(parent_base_taxable+offshore_exit_taxable,0)-max(parent_base_taxable,0))*.25
            net=proceeds-tax;gain=net-cost
            s['cash'][6]-=gross;s['cash'][0]+=net;profits[0]+=gain
            s['offshore_parent_investment_cost_budget_remaining']=0.
            recovery.update(gross=gross,net=net,friction=gross-net,investment_cost_released=cost,parent_profit_effect=gain,cash_tax=tax)
        economic_event=(p.get('economic_realization_start') is not None and t>=p['economic_realization_start'] and (t-p['economic_realization_start'])%p['economic_realization_interval']==0)
        economic_release=[];economic_fees=0.;domestic_exit_tax=0.;domestic_exit_taxable=0.
        s.setdefault('domestic_parent_cost_remaining',p.get('domestic_parent_cost_budget',[0.]*m)[:])
        reverse_loans=[0.]*m;dividend_loan_offsets=[0.]*m
        appropriations=[0.]*m;declared=[0.]*m;paid=[0.]*m;normal=[0.]*m;extra=[0.]*m
        statutory_profit=profits[:]
        for i in p['upstream_order']:
            s['capacity_budget'][i],s['reserve_budget'][i],appropriations[i]=legal_roll(s['capacity_budget'][i],s['reserve_budget'][i],s['registered_capital_budget'][i],statutory_profit[i],p.get('continue_reserve',False))
            free=max(s['cash'][i]-floors[i],0)
            normal[i]=min(max(statutory_profit[i],0)*p['upstream_payout'],max(s['capacity_budget'][i],0),free)
            # Ordinary payment consumes both cash AND statutory profit before releasing old capital.
            extra[i]=min(max(s['capacity_budget'][i]-normal[i],0),max(free-normal[i],0)*p['release_fraction']) if t>=p['release_start'] else 0.
            declared[i]=normal[i]+extra[i];s['capacity_budget'][i]-=declared[i]
            statutory_profit[p['receiver'][i]]+=declared[i]
            # True named domestic lender can settle the parent's debt by offset
            # against a newly declared dividend: income once, no imaginary cash receipt.
            offset=min(declared[i],max(-s['loans'][i],0)) if p['receiver'][i]==0 else 0.
            s['loans'][i]+=offset;dividend_loan_offsets[i]=offset
            if p['upstream_lag']:
                s['payable'][i]=declared[i]-offset
            else:
                paid[i]=declared[i]-offset;s['cash'][i]-=paid[i];s['cash'][p['receiver'][i]]+=paid[i]
            # Finite, cash-funded reverse loan; no equity created, no statutory profit.
            # Limits are opening cash-based budgets, not committed credit facilities.
            if p.get('economic_realization_start') is None and not settle_reverse and t>=p.get('reverse_loan_start',10) and i in (1,2,3,4,5) and (p.get('reverse_maturity_year') is None or t<p['reverse_maturity_year']):
                blocked=max(s['cash'][i]-floors[i]-s['payable'][i]-max(s['capacity_budget'][i],0),0)
                amount=min(blocked,max(p['reverse_loan_limits'][i]-max(-s['loans'][i],0),0))
                s['cash'][i]-=amount;s['cash'][0]+=amount;s['loans'][i]-=amount;reverse_loans[i]=amount
        # Economic surplus realization budget, NOT a legal distribution ledger for each child.
        # The node allocations are cash-source attribution only; parent actual profit remains separate.
        # Mandatory customer/operating cash and fixed/working assets remain funded.
        if economic_event:
            total_gross=sum(max(s['cash'][i]-floors[i]-s['payable'][i]-max(-s['loans'][i],0),0)*p['economic_dividend_capacity_ratio'] for i in (1,2,3,4,5,7))
            planned_capital=min(total_gross*p['economic_capital_share'],sum(s['domestic_parent_cost_remaining']))
            capital_rate=planned_capital/total_gross if total_gross else 0.
            for i in (1,2,3,4,5,7):
                gross=max(s['cash'][i]-floors[i]-s['payable'][i]-max(-s['loans'][i],0),0)
                gross*=p['economic_dividend_capacity_ratio']
                capital=gross*capital_rate
                qualified_dividend=gross-capital
                fee=gross*p['economic_realization_fee'];taxable_capital=capital*(1-p['domestic_capital_tax_basis_ratio']);tax=.25*(max(parent_base_taxable+domestic_exit_taxable+taxable_capital,0)-max(parent_base_taxable+domestic_exit_taxable,0));domestic_exit_taxable+=taxable_capital;domestic_exit_tax+=tax;net=gross-fee-tax
                # No gain from capital returned at its carrying amount. No instant tax refund for fees.
                s['cash'][i]-=gross;s['cash'][0]+=net
                cost_before=sum(s['domestic_parent_cost_remaining'])
                if cost_before>0:s['domestic_parent_cost_remaining']=[max(0,x*(1-capital/cost_before)) for x in s['domestic_parent_cost_remaining']]
                statutory_profit[0]+=qualified_dividend-fee-tax
                # Unknown prior earned-surplus budget is re-underwritten at each planned event.
                # This is not new group profit or a claim about actual subsidiary legal retained earnings.
                old_capacity=s['capacity_budget'][i]
                s['capacity_budget'][i]=old_capacity-min(qualified_dividend,max(old_capacity,0))
                economic_fees+=fee
                economic_release.append({'source_budget_node':i,'gross':gross,'qualified_dividend_budget':qualified_dividend,'capital_return_budget':capital,'mother_cost_released':capital,'fee':fee,'net_to_parent':net,'mother_profit_effect':qualified_dividend-fee-tax,'cash_tax':tax,'conditional_tax_basis_released':capital*p['domestic_capital_tax_basis_ratio'],'prior_capacity_budget':old_capacity,'new_earned_capacity_assumption':max(qualified_dividend-max(old_capacity,0),0)})
        parent_base_taxable+=domestic_exit_taxable
        foreign_dividend_tax=(max(parent_base_taxable+offshore_exit_taxable+declared[6],0)-max(parent_base_taxable+offshore_exit_taxable,0))*.25
        profits[0]-=foreign_dividend_tax;statutory_profit[0]-=foreign_dividend_tax;s['cash'][0]-=foreign_dividend_tax;cashflow[0]-=foreign_dividend_tax
        reverse_due=[max(-s['loans'][i],0) if settle_reverse else 0. for i in range(m)]
        need=max(floors[0]+sum(reverse_due)-s['cash'][0],0)
        borrow=min(need,max(p['external_limit']-sum(s['external']),0))
        s['cash'][0]+=borrow;s['external'][0]+=borrow;external_new[0]=borrow
        if s['cash'][0]<floors[0]+sum(reverse_due)-1e-8: raise ValueError('Unfunded parent even with zero dividend after reverse-loan maturity, year '+str(t))
        for i in range(1,m):
            s['cash'][0]-=reverse_due[i];s['cash'][i]+=reverse_due[i];s['loans'][i]+=reverse_due[i]
        parent_profit=statutory_profit[0]
        s['capacity_budget'][0],s['reserve_budget'][0],appropriations[0]=legal_roll(s['capacity_budget'][0],s['reserve_budget'][0],s['registered_capital_budget'][0],parent_profit,p.get('continue_reserve',False))
        group_profit=sum(profits)-recovery['parent_profit_effect']-recovery['friction']-economic_fees-domestic_exit_tax
        free=max(s['cash'][0]-floors[0],0)
        normal[0]=min(max(group_profit,0)*p['normal_payout'],max(s['capacity_budget'][0],0),free)
        extra[0]=min(max(s['capacity_budget'][0]-normal[0],0),max(free-normal[0],0)*(1. if economic_event else p['release_fraction'])) if t>=p['release_start'] else 0.
        dividend=normal[0]+extra[0];s['cash'][0]-=dividend;s['capacity_budget'][0]-=dividend
        parent_capital={'gross':0.,'fee':0.,'net_to_original_holders':0.,'shares_cancelled':0.}
        s.setdefault('issued_shares',SHARES)
        if economic_event and p.get('parent_capital_return_start') is not None and t>=p['parent_capital_return_start']:
            # Conditional proportionate paid capital reduction: no new accounting profit.
            # Shares cancelled at RMB1 par, all original owners retain proportional rights.
            gross=min(max(s['cash'][0]-floors[0]-max(s['capacity_budget'][0],0),0),max(s['registered_capital_budget'][0]-p['parent_minimum_registered'],0))
            fee=gross*p['parent_reduction_fee'];net=gross-fee
            s['cash'][0]-=gross;s['registered_capital_budget'][0]-=gross;s['issued_shares']-=gross
            s['capacity_budget'][0]-=fee
            economic_fees+=fee
            dividend+=net
            parent_capital={'gross':gross,'fee':fee,'net_to_original_holders':net,'shares_cancelled':gross,'remaining_shares':s['issued_shares'],'shares_per_original_share':s['issued_shares']/SHARES}
        s.update(rev=rev,fixed=fixed_target,working=working,contract=contract)
        assert min(s['cash'])>=-1e-8
        assert max(abs(s['cash'][i]-floors[i]) if s['cash'][i]<floors[i]-1e-7 else 0 for i in range(m))<1e-6
        cash_expected=sum(opening['cash'])+sum(cashflow)+sum(external_new)-sum(external_repaid)-dividend-recovery['friction']-economic_fees-domestic_exit_tax
        assert abs(sum(s['cash'])-cash_expected)<1e-5*max(1,sum(s['cash']))
        assert abs(sum(interinterest))<1e-10
        rows.append({'parent_proportionate_capital_return':parent_capital,'economic_surplus_realization':economic_release,'domestic_exit_incremental_cash_tax':domestic_exit_tax,'economic_realization_fees':economic_fees,'year':t,'period_end':str(2026+t)+'-10-26','revenue':rev,'ebit_margin':margin,'operating_nopat':operating,'parent_foreign_dividend_incremental_tax':foreign_dividend_tax,'own_pretax_operating_budget':own_pretax,'operating_cash_tax':operating_taxes,'reverse_domestic_loans':reverse_loans,'reverse_loan_maturity_repayment':reverse_due,'new_dividend_offset_parent_debt':dividend_loan_offsets,'financial_income':sum(interest),'external_interest':sum(financing),'group_profit':group_profit,'own_profit_capacity_budget':profits,'total_node_profit_capacity_budget':statutory_profit,'parent_profit_capacity_budget':parent_profit,'intercompany_incremental_cash_tax':interest_tax,'offshore_financial_portfolio_exit':recovery,'depreciation':depreciation,'capex':capex,'delta_working':dworking,'delta_contract':dcontract,'cashflow_before_financing':cashflow,'cash_floor':floors,'normal_distribution':normal,'extra_release':extra,'subs_declared':declared,'subs_paid_current':paid,'subs_prior_settlement':settlements,'reserve_add':appropriations,'new_shareholder_loans':newloans,'shareholder_loan_repayment':loanrepay,'external_new':external_new,'external_repaid':external_repaid,'equity_injection':[0.]*m,'dividend':dividend,'dividend_per_share':dividend/SHARES,'state':copy.deepcopy(s)})
    return rows

def valuation(rows,r,opening_distribution=0.):
    pv=(opening_distribution+sum(x['dividend']/(1+r)**x['year'] for x in rows))/SHARES
    d5=sum(x['dividend']/(1+r)**x['year'] for x in rows if x['year']<=5)/SHARES
    tv=sum(x['dividend']/(1+r)**(x['year']-5) for x in rows if x['year']>5)/SHARES
    return {'value':pv,'opening_distribution':opening_distribution,'pv_first5':d5,'tv5':tv,'tv5_pv_share':1-d5/pv,'last_cash':rows[-1]['state']['cash'],'last_retained':rows[-1]['state']['capacity_budget'],'last_external':rows[-1]['state']['external']}

def cases():
    low=copy.deepcopy(PARAM);low.update(discount=.105,g_after5=.03,g_long=.015,margin_long=.40)
    high=copy.deepcopy(PARAM);high.update(discount=.095,g_after5=.045,g_long=.025,margin_long=.44)
    cyc=copy.deepcopy(PARAM);cyc.update(revenue=[6.0,6.3,7.1,8.1,9.0],margin=[.32,.34,.40,.44,.46],g_after5=.04,margin_long=.42)
    structural=copy.deepcopy(PARAM);structural.update(revenue=[6.8,6.5,6.3,6.2,6.2],margin=[.35,.30,.27,.26,.26],g_after5=0.,g_long=0.,margin_long=.24,liquidity_ratio=.16)
    bull=copy.deepcopy(PARAM);bull.update(revenue=[8.5,9.52,10.5672,11.62392,12.6700728],margin=[.50,.51,.51,.50,.50],g_after5=.05,g_long=.025,margin_long=.45)
    zero=copy.deepcopy(PARAM);zero['capacity_budget']=[2.7,0,0,0,0,0,0,0]
    lag=copy.deepcopy(PARAM);lag['upstream_lag']=1;lag['release_start']=11
    stuck=copy.deepcopy(PARAM);stuck['upstream_payout']=.4;stuck['release_start']=11
    m=copy.deepcopy(PARAM);m['margin']=[x-.05 for x in m['margin']];m['margin_long']-=.05
    g=copy.deepcopy(PARAM);g['g_after5']=.02;g['g_long']=0.
    y=copy.deepcopy(PARAM);y['cash_yield']=0.
    heavy=copy.deepcopy(PARAM);heavy['capital_ratio']=.4;heavy['construction']=[.36,.22,.12,0,0]
    down0=copy.deepcopy(PARAM);down0['weights'][1]=.23;down0['weights'][7]=0.
    down100=copy.deepcopy(PARAM);down100['weights'][1]=0.;down100['weights'][7]=.23
    downold0=copy.deepcopy(PARAM);downold0['capacity_budget'][1]=.7;downold0['capacity_budget'][7]=0.
    downoldall=copy.deepcopy(PARAM);downoldall['capacity_budget'][1]=0.;downoldall['capacity_budget'][7]=.7
    offshore=copy.deepcopy(PARAM);offshore['opening_distribution']=offshore['cash'][6];offshore['capacity_budget'][0]-=offshore['opening_distribution']
    for field in ('cash','capacity_budget'):offshore[field][6]=0.
    offshore['reserve_budget'][6]=None;offshore['registered_capital_budget'][6]=None
    offshore['opening_event']='Abstract economic100% net-realization upper bound, NOT a verified whole-offshore legal transaction: conditional immediate solvent liquidation of offshore cash budget; all proceeds paid through parent using existing parent statutory retained; no tax/fees, upper bound only. Initial investment capital removed, not operating income.'
    new={}
    for label,patch in [('old_profit_capacity_no_realization',{'economic_realization_start':None}),('realization_delay20',{'economic_realization_start':20}),('realization_fee10',{'economic_realization_fee':.10}),('realization_capacity25',{'economic_dividend_capacity_ratio':.25}),('realization_interval10',{'economic_realization_interval':10}),('capital_return_share50',{'economic_capital_share':.5}),('capital_return_share10_slow_diagnostic',{'economic_capital_share':.1}),('realization_capacity100',{'economic_dividend_capacity_ratio':1.}),('no_parent_capital_return',{'parent_capital_return_start':None}),('domestic_zero_tax_basis',{'domestic_capital_tax_basis_ratio':0.}),('parent_capital_return_delay30',{'parent_capital_return_start':30}),('parent_reduction_fee10',{'parent_reduction_fee':.10})]:
        v=copy.deepcopy(PARAM);v.update(patch);new[label]=v
    for label,patch in [('legacy_uniform15_budget',{'tax_mode':'legacy_aftertax_allocation'}),('downstream_tax25',{'operating_tax_rates':[.25,.15,.15,.25,.15,.25,.20,.25]}),('offshore_exit_delay20',{'offshore_exit_year':20}),('offshore_realization50',{'offshore_realizability':.5}),('offshore_realization100',{'offshore_realizability':1.}),('offshore_zero_tax_basis',{'offshore_tax_basis_ratio':0.}),('offshore_all_parent_cost',{'offshore_cost_budget':1.20647158242}),('no_offshore_exit',{'offshore_exit_year':None}),('no_reverse_domestic_loans',{'reverse_loan_limits':[0.]*8}),('reverse_no_periodic_settlement',{'reverse_periodic_settlement':None}),('reverse_maturity15_no_renewal',{'reverse_maturity_year':15}),('reverse_loans_delayed20',{'reverse_loan_start':20}),('tax_qualification_not_renewed',{'operating_tax_rates':[.25,.25,.25,.25,.15,.25,.20,.20],'marginal_interest_tax':[.25,.25,.25,.25,.15,.25,.20,.20]})]:
        v=copy.deepcopy(PARAM);v.update(patch);new[label]=v
    for label,patch in [('structural_reverse_maturity15',{'reverse_maturity_year':15}),('structural_no_reverse',{'reverse_loan_limits':[0.]*8}),('structural_delay20',{'economic_realization_start':20}),('structural_capacity25',{'economic_dividend_capacity_ratio':.25}),('structural_old_no_realization',{'economic_realization_start':None})]:
        v=copy.deepcopy(structural);v.update(patch);new[label]=v
    full=copy.deepcopy(PARAM);full['reserve_budget']=[.36081535125,.015,.15,.005,.10383,.0275,None,None];new['domestic_reserves_already_full']=full
    cont=copy.deepcopy(PARAM);cont['continue_reserve']=True;new['continued_reserves']=cont
    tax20=copy.deepcopy(PARAM);tax20['tax']=.20;tax20['tax_mode']='uniform';new['normalized_operating_tax20']=tax20
    downloss=copy.deepcopy(PARAM);downloss['capacity_budget'][7]=-.35;new['downstream_old_loss350m']=downloss
    return {**new,'downstream_share0':down0,'downstream_share100':down100,'downstream_old_retained0':downold0,'downstream_old_retained_all':downoldall,'offshore_immediate_recovery_upper_bound':offshore,'base':PARAM,'core_low':low,'core_high':high,'cyclical_weak':cyc,'structural_adverse':structural,'optimistic':bull,'zero_sub_opening_retained':zero,'one_year_upstream_lag_release11':lag,'subs_upstream40_release11':stuck,'margin_minus5pp_fromY1':m,'growth_lower_fromY6':g,'zero_financial_yield_fromY1':y,'capital_double_fromY1':heavy}

def tests():
    # Exact hand-computable special case goes through the production engine.
    p=copy.deepcopy(PARAM);p.update(revenue=[10]*5,margin=[.1]*5,tax=0.,tax_mode='uniform',parent_cost=0.,cash_yield=0.,liquidity_ratio=0.,contract_ratio=0.,working_ratio=0.,capital_ratio=0.,construction=[0]*5,normal_payout=1.,upstream_payout=1.,release_start=999,weights=[0,1,0,0,0,0,0,0],cash=[.3,3.09069063185,0,0,0,0,0,0],retained=[0]*8,capital=[0]*8,reserve=[0]*8,initial_working=0.,external_limit=0.)
    # Initial contract is a cash liability: run from explicit zero-liability opening.
    s={'cash':[.3,0,0,0,0,0,0,0],'capacity_budget':[0]*8,'reserve_budget':[0]*8,'registered_capital_budget':[0]*8,'loans':[0]*8,'external':[0]*8,'payable':[0]*8,'rev':10.,'fixed':p['initial_fixed'],'working':0.,'contract':0.}
    rr=run(p,years=1,initial=s);assert abs(rr[0]['dividend']-1)<1e-9
    assert abs(valuation(rr,.1)['value']-1/1.1/SHARES)<1e-9
    nested=copy.deepcopy(p);nested['weights']=[0,0,0,0,0,0,0,1]
    nr=run(nested,years=1,initial=s)[0]
    assert abs(nr['dividend']-1)<1e-9 and abs(nr['group_profit']-1)<1e-9
    assert nr['subs_declared'][7]==1 and nr['subs_declared'][1]==1
    assert legal_roll(-2,0,10,1)==(-1,0,0)
    assert legal_roll(-1,0,10,2)==(.9,.1,.1)
    assert abs(legal_roll(0,.36,.75264,1)[2]-.01632)<1e-9
    # Zero distributions do not repair an unfinanceable operating deficit.
    broken=copy.deepcopy(PARAM);broken.update(parent_extra_cost=50.,external_limit=0.,normal_payout=0.,release_fraction=0.)
    try: run(broken,1)
    except ValueError: pass
    else: raise AssertionError('Should reject insolvent path')
    return {'production_engine_hand_case':'profit=1; cash distribution=1; PV=1/1.1/0.75264','two_tier_dividend_hand_case':'downstream operating profit1 -> declared1 to Hexin -> declared1 to parent -> owner1, group profit remains1','continuous_loss_and_new_capital_reserve_ceiling':'pass','zero_distribution_insolvency':'rejected as required'}

def pack_output(output):
    """Deterministic complete case files, each below upload limits; no field removed."""
    canonical=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    full=canonical(output);header={k:v for k,v in output.items() if k!='cases'}
    manifest={}
    for name,case in output['cases'].items():
        packed=copy.deepcopy(case)
        rows=json.dumps(packed.pop('annual_rows'),ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
        packed['annual_trace_encoding']='gzip+base64; UTF-8 compact JSON full annual row dictionaries; mtime=0'
        packed['annual_trace_sha256']=hashlib.sha256(rows).hexdigest()
        packed['annual_trace_gzip_base64']=base64.b64encode(gzip.compress(rows,compresslevel=9,mtime=0)).decode('ascii')
        filename='2026-Q3-case-'+name+'.json';raw=canonical(packed)
        assert len(raw)<16*1024*1024,'case exceeds per-file limit'
        Path(__file__).with_name(filename).write_bytes(raw+b'\n')
        manifest[name]={'file':filename,'bytes':len(raw)+1,'file_sha256':hashlib.sha256(raw+b'\n').hexdigest(),
                        'expanded_case_canonical_sha256':hashlib.sha256(canonical(case)).hexdigest()}
    return {'schema':'cn300033_complete_case_manifest_v1',
            'encoding':'named complete case JSON files; annual_rows losslessly gzip+base64; mtime=0; decode with same standard-library single Python file',
            'expanded_canonical_bytes':len(full),'expanded_canonical_sha256':hashlib.sha256(full).hexdigest(),
            'model_header':header,'case_files':manifest,
            'summary':{'core':output['core'],'auxiliary':output['auxiliary'],'case_count':len(output['cases']),
                       'case_values':{name:case['valuation']['value'] for name,case in output['cases'].items()}},
            'expand_command':'python 2026-Q3.py --expand 2026-Q3-output.json > 2026-Q3-expanded.json'}

def expand_output(output,base_dir=None):
    if output.get('schema')=='cn300033_complete_case_manifest_v1':
        base_dir=Path(base_dir) if base_dir is not None else Path(__file__).parent
        canonical=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
        result=copy.deepcopy(output['model_header']);result['cases']={}
        for name,entry in output['case_files'].items():
            assert Path(entry['file']).name==entry['file'],'case filename must be local basename'
            raw=(base_dir/entry['file']).read_bytes()
            assert len(raw)==entry['bytes'],'case file byte-count mismatch'
            assert hashlib.sha256(raw).hexdigest()==entry['file_sha256'],'case file SHA256 mismatch'
            case=expand_output({'cases':{name:json.loads(raw)}})['cases'][name]
            assert hashlib.sha256(canonical(case)).hexdigest()==entry['expanded_case_canonical_sha256'],'expanded case SHA256 mismatch'
            result['cases'][name]=case
        full=canonical(result)
        assert len(full)==output['expanded_canonical_bytes'],'full expanded byte-count mismatch'
        assert hashlib.sha256(full).hexdigest()==output['expanded_canonical_sha256'],'full expanded SHA256 mismatch'
        assert output['summary']=={'core':result['core'],'auxiliary':result['auxiliary'],'case_count':len(result['cases']),'case_values':{name:case['valuation']['value'] for name,case in result['cases'].items()}},'summary mismatch'
        return result
    expanded=copy.deepcopy(output)
    for case in expanded['cases'].values():
        if 'annual_trace_gzip_base64' in case:
            raw=gzip.decompress(base64.b64decode(case.pop('annual_trace_gzip_base64')))
            assert hashlib.sha256(raw).hexdigest()==case.pop('annual_trace_sha256'),'annual trace SHA256 mismatch'
            case.pop('annual_trace_encoding');case['annual_rows']=json.loads(raw)
        elif isinstance(case.get('annual_rows'),dict):
            table=case['annual_rows'];case['annual_rows']=[dict(zip(table['columns'],v)) for v in table['values']]
    return expanded

def main():
    output={'unit':'CNY billion; shares billion','shares':SHARES,'asof':ASOF,'entities':NAMES,'node_scope':['CN_real_parent','CN_real_Hexin','CN_real_Intelligent','CN_real_Zhifu','CN_real_Data','CN_real_Network','MULTI_economic_offshore_budget_not_HK_individual','economic_downstream_remittance_budget_not_legal_person'],'actual_Q3_legal_reserve':[None]*8,'actual_Q3_legal_retained':[None]*8,'actual_paid_capital':[None]*8,'HK_fact':{'name':'同花顺国际(香港)有限公司','jurisdiction':'HK','registered_native_USD':60000000,'parent_investment_cost_CNY':400780400,'ownership':1.,'cash_of_this_legal_person':None},'account_schema':{'capacity_budget':'Economically constrained distribution capacity, not disclosed actual legal balance; on real domestic nodes apply PRC reserve budget, on6/7 no invented corporation law','reserve_budget':'Mother H1actual360815351.25; domestic5 incremental0 starting reserve budget unknown actual; offshore/downstreamNone, no PRC statutory reserve','registered_capital_budget':'Actual mainland named entities inCNY; foreign/mixed nodesNone, native HKUSD60m in facts not investment-cost conversion','support':'Explicit economic intercompany funding budget; unidentified downstream cannot be treated as named legal borrower. No share issue or registry change inferred','offshore_recovery':'Mixed offshore financial portfolio net-realization budget, not a named HK capital reduction. HK mother book cost anchor distinct from registration and conditional tax basis; all foreign future cash yield removed after exit. Actual holding chain, approvals and tax require verification.','economic_realization':'Core domestic surplus source allocations are economic budgets, not literal individual legal retained accounts. Every five years fromY10,50% excess is budgeted remittance. First return pooled domestic parent investment carrying cost up to remaining0.80569118242bn; excess is conditional legally distributable earned surplus.2% fees; conditional actual taxbasis. Parent fromY15 pro-rata paid capital reduction cancels equal RMB1-par shares; per-original-share ownership bundle normalization, minimum registered capital50m is a modelling floor not a claim about applicable legal minimum. No approved transaction claimed.', 'reverse_loans':'Legacy diagnostic only in old_profit_capacity_no_realization. Only five named wholly owned domestic lenders. Cash-funded at 3% pretax, capacity not created; new declared dividends offset principal once. Full cash maturity each fifth year, no lending on maturity year; nonrenewal stress separately. Conditional lawful corporate approvals and creditor protection, not announced commitment.'},'tests':tests(),'cases':{}}
    for name,p in cases().items():
        if p.get('opening_distribution',0)>0:
            assert abs(sum(PARAM['cash'])-sum(p['cash'])-p['opening_distribution'])<1e-9
            assert p['capacity_budget'][0]>=0 and abs(PARAM['capacity_budget'][0]-p['capacity_budget'][0]-p['opening_distribution'])<1e-9
            assert p['cash'][6]==p['capacity_budget'][6]==0 and p['registered_capital_budget'][6] is None and p['reserve_budget'][6] is None
        rr=run(p);out={'parameters':p,'valuation':valuation(rr,p['discount'],p.get('opening_distribution',0.)),'annual_rows':rr}
        out['convergence_200_300_400']={str(n):valuation(run(p,n),p['discount'],p.get('opening_distribution',0.))['value'] for n in (200,300,400)}
        out['integration_tail_bound_300_to400']=out['convergence_200_300_400']['400']-out['convergence_200_300_400']['300']
        output['cases'][name]=out
    # Same year-five operating and financial state across core endpoints.
    assert output['cases']['core_low']['annual_rows'][4]['state']==output['cases']['core_high']['annual_rows'][4]['state']
    output['offshore_cash_recovery_boundary']={'initial_principal':PARAM['cash'][6],'year5_cash':output['cases']['base']['annual_rows'][4]['state']['cash'][6],'year30_cash':output['cases']['base']['annual_rows'][29]['state']['cash'][6],'year300_undistributed_cash':output['cases']['base']['annual_rows'][-1]['state']['cash'][6],'immediate_net_value_increment_upper_bound':output['cases']['offshore_immediate_recovery_upper_bound']['valuation']['value']-output['cases']['base']['valuation']['value'],'not_an_extra_addon_to_core':True}
    output['core']={'value_range':{'low':output['cases']['core_low']['valuation']['value'],'high':output['cases']['core_high']['valuation']['value'],'currency':'CNY'},'distributions':[x['dividend_per_share'] for x in output['cases']['base']['annual_rows'][:5]],'tv5':{'low':output['cases']['core_low']['valuation']['tv5'],'high':output['cases']['core_high']['valuation']['tv5']}}
    # Auxiliary operating earnings capitalization excludes ALL cash yield; add only legally paid extra release PV.
    aux={}
    for label,r,multiple in [('low',.105,16.),('high',.095,20.)]:
        rr=output['cases']['core_'+label]['annual_rows']
        # Controlled subtraction: re-run legal cash engine without opening excess cash.
        # This captures only the incremental owner distributions caused by existing cash,
        # not extra distributions of future operating profits already capitalized below.
        cashless=copy.deepcopy(output['cases']['core_'+label]['parameters'])
        cashless['cash']=[.3]+[(7.8*cashless['liquidity_ratio']+3.09069063185)*v for v in cashless['weights'][1:]]
        shadow=run(cashless)
        release=valuation(rr,r)['value']-valuation(shadow,r)['value']
        output['cases']['cash_attribution_shadow_'+label]={'parameters':cashless,'annual_rows':shadow,'valuation':valuation(shadow,r)}
        op=sum((PARAM['revenue'][0]*.48+PARAM['parent_cost'])*PARAM['weights'][i]*(1-PARAM['operating_tax_rates'][i]) for i in range(1,8))-PARAM['parent_cost']-(.2*(PARAM['revenue'][1]-PARAM['revenue'][0])+.01*(PARAM['revenue'][1]-PARAM['revenue'][0]))
        aux[label]={'operating_cash_earnings':op,'multiple':multiple,'opening_cash_incremental_legal_distribution_pv':release,'value':op*multiple/SHARES+release}
    output['auxiliary']=aux
    packed=pack_output(output)
    assert expand_output(packed)==output
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(packed,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps({'core':output['core'],'cases':{k:v['valuation']['value'] for k,v in output['cases'].items()},'auxiliary':aux},ensure_ascii=False,indent=2))
if __name__=='__main__':
    if len(sys.argv) in (2,3) and sys.argv[1]=='--expand':
        target=Path(sys.argv[2]) if len(sys.argv)==3 else Path(__file__).with_name('2026-Q3-output.json')
        print(json.dumps(expand_output(json.loads(target.read_text()),target.parent),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
    else: main()

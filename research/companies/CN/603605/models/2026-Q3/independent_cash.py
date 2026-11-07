"""当前数学计算组件；输入由必要事实、预算及同次经营计算生成。"""
import copy
from common import positive,legal,check,economic,Technical,anniversary,dated_pv,cents_half_up

def at(values,year,q):return q(values[min(year,len(values))-1])

def opening(case,event,phase,q):
    p=case['financial_parameters'];f=p['finance'];h=p['parent'];stock=p['shares']
    delta=(q(event['new_paid_yuan'])-q(event['old_paid_yuan']))/q(1000000) if phase=='current' else q(0)
    bank=q(f['reported_cash'])+q(f['reported_trading_assets'])-q(f['paid_october_dividend'])-q(f['minority_liquid_assets_estimate'])-q(case['opening_operating_cash'])
    mother=q(h['opening_excess_cash'])
    if delta!=0:bank-=delta;mother-=delta
    treasury=q(event['new_incentive_shares'])/q(1000000) if phase=='current' else q(stock['treasury_incentive'])
    return {'group_cash':bank,'parent_cash':mother,'parent_re':q(h['opening_legal_retained']),'parent_reserve':q(h['opening_statutory_reserve']),'subs_re':q(h['opening_subsidiary_common_legal_retained']),'issued':q(stock['issued']),'cancel_inventory':q(stock['treasury_cancel_proposed']),'incentive_inventory':treasury,'bond_book':q(f['bond_opening_book']),'loan':q(0),'conversion_dividend_adjustment':q(0),'opening_delta':delta}

def advance(state,op,params,q,emit=None):
    """Shared actual company/formal production step, not a parallel hand calculation."""
    start=copy.deepcopy(state);s=copy.deepcopy(state);y=op['year'];f=params['finance'];h=params['parent'];stock=params['shares']
    if stock['cancellation_year_budget']==y:s['issued']-=s['cancel_inventory'];s['cancel_inventory']=q(0)
    grant_cash=q(0)
    if stock['incentive_release_year_budget']==y:s['incentive_inventory']=q(0);grant_cash=q(stock['incentive_cash_proceeds'])
    bond_cash=bond_cost=new_shares=q(0);conversion_price=None
    if y==1:
        bond_cash=q(f['bond_coupon_y1']);bond_cost=q(f['bond_book_charge_y1']);s['bond_book']+=bond_cost-bond_cash
    elif y==2:
        branch=f['bond_mode']
        if branch=='repay':bond_cash=q(f['bond_redemption_y2']);bond_cost=bond_cash-s['bond_book']
        elif branch=='convert':
            conversion_price=q(f['bond_conversion_price'])-start['conversion_dividend_adjustment']
            if conversion_price<=0:raise Technical('conditional conversion price is nonpositive',{'state':s,'op':op,'conversion_price':conversion_price})
            new_shares=q(f['bond_face'])/conversion_price;s['issued']+=new_shares
        else:raise Technical('unknown bond settlement branch',{'branch':branch})
        s['bond_book']=q(0)
    participants=s['issued']-s['cancel_inventory']-s['incentive_inventory']
    if participants<=0:raise Technical('ordinary participating denominator is nonpositive',s)
    group_yield=positive(start['group_cash'])*q(f['after_tax_cash_yield']);parent_yield=positive(start['parent_cash'])*q(f['after_tax_cash_yield'])
    loan_cost=start['loan']*q(f['conditional_new_loan_rate']);book_cost=bond_cost+loan_cost;tax_rate=q(f['parent_tax_rate'])
    if not 0<=tax_rate<1:raise Technical('invalid parent tax fraction')
    taxable_capacity=positive(q(op['parent_own_operating_profit']))*tax_rate/(q(1)-tax_rate)
    shield=min(positive(book_cost)*tax_rate,taxable_capacity)
    group_profit=q(op['common_operating_accounting_profit'])+group_yield-book_cost+shield
    mother_profit=q(op['parent_own_operating_profit'])+parent_yield-book_cost+shield
    subsidiary_profit=group_profit-mother_profit;s['subs_re']+=subsidiary_profit
    relocation=at(h['cash_settlement_delay'],y,q)
    group_pre=start['group_cash']+q(op['operating_common_fcf'])+group_yield+shield-bond_cash-loan_cost+grant_cash
    parent_pre=start['parent_cash']+q(op['parent_own_operating_cash'])+parent_yield+shield-bond_cash-loan_cost+grant_cash-relocation
    request_up=at(h['upstream_fraction'],y,q)*positive(subsidiary_profit)
    upstream=min(request_up,positive(s['subs_re']),positive(group_pre-parent_pre))
    s['subs_re']-=upstream;parent_pre+=upstream;parent_profit=mother_profit+upstream
    law=legal(start['parent_re'],start['parent_reserve'],s['issued'],parent_profit,q('0.1'),q)
    s['parent_re']=law['pre_distribution_re'];s['parent_reserve']=law['reserve']
    funding_need=max(q(0),-group_pre,-parent_pre);headroom=positive(q(f['conditional_new_loan_limit'])-s['loan'])
    borrowing=min(funding_need,headroom);s['loan']+=borrowing;group_pre+=borrowing;parent_pre+=borrowing
    support=min(positive(parent_pre-group_pre),positive(parent_pre));parent_pre-=support
    gap=max(q(0),-group_pre,-parent_pre)
    repayment=min(s['loan'],positive(min(group_pre,parent_pre)));s['loan']-=repayment;group_pre-=repayment;parent_pre-=repayment
    target=positive(group_profit)*at(h['payout_fraction'],y,q)+at(h['distribution_target_addition'],y,q)
    paid=max(q(0),min(target,positive(group_pre),positive(parent_pre),positive(s['parent_re'])))
    s['group_cash']=group_pre-paid;s['parent_cash']=parent_pre-paid;s['parent_re']-=paid
    dps=paid/participants;s['conversion_dividend_adjustment']=cents_half_up(paid/s['issued'],q)
    if emit:emit('before_checks',{'opening':start,'closing':s,'operating_reference':op,'parameters':params,'bond_cash':bond_cash,'bond_book_cost':bond_cost,'conversion_price':conversion_price,'new_shares':new_shares,'group_yield':group_yield,'parent_yield':parent_yield,'loan_interest':loan_cost,'tax_capacity':taxable_capacity,'tax_shield':shield,'group_profit':group_profit,'mother_profit':mother_profit,'subsidiary_profit':subsidiary_profit,'upstream_request':request_up,'upstream':upstream,'parent_law':law,'funding_need':funding_need,'loan_headroom':headroom,'borrowed':borrowing,'support':support,'gap':gap,'repayment':repayment,'target':target,'paid':paid,'dps':dps,'participants':participants})
    residues={
      'group_cash':check(s['group_cash'],start['group_cash']+q(op['operating_common_fcf'])+group_yield+shield-bond_cash-loan_cost+grant_cash+borrowing-repayment-paid,'Proya common cash',q),
      'parent_cash':check(s['parent_cash'],start['parent_cash']+q(op['parent_own_operating_cash'])+parent_yield+shield-bond_cash-loan_cost+grant_cash-relocation+upstream+borrowing-support-repayment-paid,'Proya parent cash',q),
      'parent_re':check(s['parent_re'],start['parent_re']+parent_profit-law['reserve_add']-paid,'Proya parent legal RE',q),
      'subs_re':check(s['subs_re'],start['subs_re']+subsidiary_profit-upstream,'Proya subsidiary legal RE',q),
      'loan':check(s['loan'],start['loan']+borrowing-repayment,'Proya external loan',q),
      'distribution':check(dps*participants,paid,'Proya participating rights',q)}
    return {'year':y,'opening':start,'closing':s,'operating_reference':copy.deepcopy(op),'group':{'net_yield':group_yield,'common_profit':group_profit,'cash_before_financing_and_distribution':group_pre+repayment-borrowing},'parent':{'net_yield':parent_yield,'own_profit':mother_profit,'new_upstream_income':upstream,'total_legal_profit':parent_profit,'settlement_delay':relocation,'subsidiary_cash_support':support,'law':law},'subsidiary':{'profit':subsidiary_profit,'upstream_request':request_up,'actual_new_declared_received':upstream},'bond':{'cash_paid':bond_cash,'book_charge':bond_cost,'end_book':s['bond_book'],'conditional_price':conversion_price,'conversion_shares':new_shares},'finance':{'loan_interest':loan_cost,'total_book_interest':book_cost,'taxable_profit_capacity':taxable_capacity,'interest_tax_shield':shield,'funding_need':funding_need,'loan_headroom':headroom,'draw':borrowing,'repayment':repayment,'unfinanced_gap':gap},'rights':{'issued':s['issued'],'participating':participants,'cancel_inventory':s['cancel_inventory'],'incentive_inventory':s['incentive_inventory'],'grant_cash':grant_cash,'conversion_dividend_adjustment':s['conversion_dividend_adjustment']},'distribution':{'target':target,'cash':paid,'dps':dps},'self_residuals':residues}

def path(case,event,phase,q,emit,same_base=None):
    params=case['financial_parameters'];ops=case['operating_rows'];state=opening(case,event,phase,q);rows=[];economic_gaps=[]
    if len(ops)!=11 or [r['year'] for r in ops]!=list(range(1,12)):raise Technical('Proya requires the complete original11 operating rows')
    emit('opening',state);first=copy.deepcopy(state)
    if same_base is None:
        for op in ops[:5]:
            try:record=advance(state,op,params,q,lambda label,obj:emit('year-'+str(op['year'])+'.'+label,obj))
            except Exception as error:
                emit('technical_partial',{'opening':first,'completed_rows':rows,'inflight_opening':state,'inflight_op':op,'failure_state':getattr(error,'state',None),'reason':str(error)});raise
            emit('year-'+str(op['year']),record);rows.append(record);state=record['closing']
            tolerance=q(0) if hasattr(record['finance']['unfinanced_gap'],'denominator') else q('1e-57')
            if record['finance']['unfinanced_gap']>tolerance:economic_gaps.append({'year':op['year'],'gap':record['finance']['unfinanced_gap']})
    else:
        if same_base['phase']!=phase or same_base['opening']!=first or same_base['operating_path'][:5]!=ops[:5]:raise Technical('Proya holder is not the same actual base cash state',{'phase':phase})
        if len(same_base['rows'])!=5:raise Technical('Proya base cash dependency is incomplete')
        rows=copy.deepcopy(same_base['rows']);state=copy.deepcopy(same_base['base_y5_state']);economic_gaps=copy.deepcopy(same_base['economic_gaps']);emit('same_base_first5_reused',{'rows':rows,'state5':state})
    rate=q(params['discount_rate']);growth=q(params['steady_growth']);f=params['finance']
    if rate<=growth or rate<=0:raise Technical('invalid primary/auxiliary discount-growth budget',{'rate':rate,'growth':growth,'rows':rows})
    continuations=[q(r['operating_common_fcf'])/(q(1)+rate)**(r['year']-5) for r in ops[5:10]]
    stable_operating=q(ops[10]['operating_common_fcf'])/(rate-growth)
    operating5=sum(continuations,q(0))+stable_operating/(q(1)+rate)**5
    noncash=q(f['noncash_investments_book'])*q(f['noncash_recovery_fraction'])*(q(1)+q(f['noncash_annual_return']))**5
    bridge=state['group_cash']+noncash-state['loan'];whole_terminal=operating5+bridge
    aux_operating=q(ops[4]['zero_growth_maintainable_common_cash_profit'])/rate;aux_terminal=aux_operating+bridge
    shares=rows[-1]['rights']['participating'];anchor=case['metadata']['valuation_date'];dates=[anniversary(anchor,k) for k in range(1,6)]
    if dates[-1]!=case['metadata']['year_5_date']:raise Technical('original Y5 date contract differs')
    ps=whole_terminal/shares;aps=aux_terminal/shares
    valuation=dated_pv(anchor,dates,[r['distribution']['dps'] for r in rows],rate,q,dates[-1],ps)
    auxiliary=dated_pv(anchor,dates,[r['distribution']['dps'] for r in rows],rate,q,dates[-1],aps)
    if state['bond_book']!=0:raise Technical('bond unresolved at Y5',state)
    full={'status':'COMPLETE_OWN_LEDGER_NOT_COMPARED','phase':phase,'metadata':copy.deepcopy(case['metadata']),'opening':first,'rows':rows,'operating_path':copy.deepcopy(ops),'base_y5_state':copy.deepcopy(state),'same_base_first_five_rows':copy.deepcopy(rows),'D5':[r['distribution']['dps'] for r in rows],'year5':{'continuation_pv_terms':continuations,'stable_operating_at10':stable_operating,'operating_value':operating5,'noncash_investments':noncash,'finance_bridge':bridge,'terminal_equity':whole_terminal,'terminal_shares':shares,'terminal_per_share':ps,'auxiliary_operating':aux_operating,'auxiliary_terminal_equity':aux_terminal,'auxiliary_terminal_per_share':aps},'valuation':valuation,'auxiliary_valuation':auxiliary,'opening_bond_deduction':q(0),'no_new_operating_forecast':True,'economic_gaps':economic_gaps}
    full['same_base_first5_reused']=same_base is not None
    full['metadata']['information_cutoff']=event['cutoff'];full['metadata']['model_as_of']=event['cutoff']
    full['method_gap_fraction']=abs(valuation['value']-auxiliary['value'])/abs(valuation['value']) if valuation['value'] else None
    full['terminal_pv_share']=valuation['terminal_pv']/valuation['value'] if valuation['value'] else None
    if economic_gaps or whole_terminal<0 or aux_terminal<0:
        full['status']='ECONOMIC_INFEASIBLE';full['reason']='unfunded_cash' if economic_gaps else 'negative_terminal_without_supported_floor';full['unchecked_diagnostic']={'primary':valuation,'auxiliary':auxiliary};full['value']=None;full['terminal5']=None;full['valuation']['economic_acceptance']=False;full['auxiliary_valuation']['economic_acceptance']=False
    else:full['value']=valuation['value'];full['terminal5']=ps
    return full

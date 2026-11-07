"""Actual legal-cash/RE chain and the SAME transition for dividend shadows."""
from common import *
import tax_bridge as tb


def strict_required_cash_snapshot(s,c):
    """All callers use identical location, legacy/new tax and operating requirements."""
    return tb.requirements(s,c)


def initial_state(c,pack):
    op=pack['initial_operating'];o,a=c['observed'],c['assumptions']
    if c.get('mode')=='fixture':
        supplied=c['fixture']['initial']
        s={k:M(v) for k,v in supplied.items() if k not in ('legal_shares','treasury_shares')}
        s['legal_shares']=int(supplied['legal_shares']);s['treasury_shares']=int(supplied['treasury_shares'])
    else:
        ratio=D(a['mother_ratio']);delta_treas=D(o['treasury_book_q3'])-D(o['treasury_book_h1']);pastD=D(o['interim_dividend_paid_before_cutoff'])
        mother=M(D(o['h1_mother_cash'])+ratio*(D(o['q3_cash'])-D(o['h1_cash'])+pastD+delta_treas)-pastD-delta_treas)
        mother_re=M(D(o['h1_mother_re'])+ratio*D(o['q3_parent_profit_single'])-pastD)
        e_share=pack['annual_budgets'][2026]['energy_revenue_share']*D(a['nci_entity_energy_share'])
        s={'cash':M(o['q3_cash']),'mother_cash':mother,'mother_re':mother_re,
           'mother_reserve':M(o['h1_mother_statutory_reserve']),
           'nci_cash':M(D(o['q3_cash'])*e_share),'nci_re':M(D(o['q3_nci_book'])/D(a['nci_minority_fraction'])),
           'nci_reserve':ZERO,'nci_parent_loan':sum(M(v) for v in o['parent_loan_to_nci_entity_by_age']),
           'old_face':M(o['bond_face']),'old_book':M(o['q3_bond_book']),
           'legal_shares':int(o['legal_shares']),'treasury_shares':int(o['treasury_shares'])}
    for k in ('buffer','deposits','nci_buffer','nci_deposits'):
        s[k]=M(op.get(k,0))
    s['capital_stock']=copy.deepcopy(op.get('capital_stock'))
    defaults={'cash':ZERO,'mother_cash':ZERO,'mother_re':ZERO,'mother_reserve':ZERO,'nci_cash':ZERO,'nci_re':ZERO,
              'nci_reserve':ZERO,'nci_parent_loan':ZERO,'old_face':ZERO,'old_book':ZERO}
    for k,v in defaults.items():s.setdefault(k,v)
    s.update({'date':ds(c['initial_date']),'conversion_price':D(o.get('conversion_price',1)),
              'new_face':ZERO,'new_issued':False,'new_repaid':False,'new_book_fee_left':ZERO,
              'old_amort_cumulative':ZERO,'new_amort_cumulative':ZERO,'new_coupon_accruals':{},'shield_queue':{},
              'mother_taxable_ytd':{},'deduction_used_ytd':{},'year_profit':{},'financing_events':[],
              'shield_events':[],'equity_events':[],'distributions':[],
              'release_batch':None,'refinancing_issue':None,'refinancing_maturity':None,
              'tax_queue':copy.deepcopy(op.get('tax_queue',{})),'entity_tax_queue':copy.deepcopy(op.get('entity_tax_queue',{}))})
    # Total future expense is accrued; actual contractual payments occur separately.
    s['old_amort_base_date']=s['date'];s['old_amort_base_book']=s['old_book']
    s['old_amort_contract_total']=M(s['old_face']*D(c['events']['redemption_multiple'])+s['old_face']*D(c['events']['coupon_rate']))-s['old_book']
    if c.get('mode')=='fixture':
        s['year_profit']={str(k):M(v) for k,v in c['fixture'].get('year_profit',{}).items()}
    else:
        s['year_profit']['2026']=M(D(o['nine_month_core_ex_fx_management_estimate'])-D(o['tariff_refund_parent_profit_estimate']))
    tb.initialize(s,c)
    return s


def financing(s,d,cash,kind,**details):
    s['financing_events'].append({'date':d,'cash':M(cash),'kind':kind,**details})


def accrue_shield(s,c,d,interest):
    a=c['assumptions'];year=str(d.year);taxbase=max(ZERO,s['mother_taxable_ytd'].get(year,ZERO))
    used=s['deduction_used_ytd'].get(year,ZERO);deductible=min(max(ZERO,D(interest)),max(ZERO,taxbase-used))
    s['deduction_used_ytd'][year]=used+deductible
    value=M(deductible*D(a['mother_tax_rate']));due=iso(tax_due(d))
    s['shield_queue'][due]=s['shield_queue'].get(due,ZERO)+value
    return value


def financial_return(s,c,days):
    return tb.returns(s,c,days)


def advance(state,p,c):
    """Pure deterministic transition, no ordinary D. Reused without shortcuts by shadow."""
    s=copy.deepcopy(state);a,e=c['assumptions'],c['events'];d=p['date'];minority=D(a['nci_minority_fraction'])
    prior_cash=s['cash'];prior_mother=s['mother_cash'];prior_entity=s['nci_cash']
    fy=financial_return(s,c,p['days']);gi,mi,ei=fy['group'],fy['mother'],fy['entity']
    s['cash']+=p['group']['actual_cash']+gi;s['nci_cash']+=p['entity']['actual_cash']+ei
    taxflow=tb.apply_income(s,p,c,fy);mother_op_cash=taxflow['mother_operating_actual']
    mother_profit=taxflow['mother_direct_profit']+mi;entity_profit=p['entity']['profit']+ei
    year=str(d.year);s['mother_taxable_ytd'][year]=s['mother_taxable_ytd'].get(year,ZERO)+taxflow['mother_direct_taxable']
    for k in ('buffer','deposits','nci_buffer','nci_deposits'):s[k]=p['endpoints'][k]
    if 'capital_stock' in p['endpoints']:s['capital_stock']=copy.deepcopy(p['endpoints']['capital_stock'])
    s['tax_queue']=copy.deepcopy(p['tax_queue']);s['entity_tax_queue']=copy.deepcopy(p['entity_tax_queue'])
    legacy=tb.legacy_event(s,c,d);mother_profit-=legacy['parent_expense']
    # New actual quarter dividend is only a transfer of identified NEW profit, net of its tax.
    upstream=tb.settle_quarter(s,c,d);mother_profit+=upstream['net_mother']
    old_expense=ZERO;new_expense=ZERO;fees=ZERO
    # Linear remaining expense bridge, not extra cash or immediate tax deduction.
    mat=ds(e['maturity'])
    if s['old_face']>0 and state['date']<mat:
        end=min(d,mat);total_days=(mat-s['old_amort_base_date']).days
        cum=M(s['old_amort_contract_total']*D((end-s['old_amort_base_date']).days)/D(total_days))
        old_expense=cum-s['old_amort_cumulative'];s['old_amort_cumulative']=cum;s['old_book']+=old_expense
    if s['new_issued'] and not s['new_repaid']:
        issue=s['refinancing_issue'];maturity=s['refinancing_maturity'];end=min(d,maturity)
        elapsed=D((end-issue).days);whole=D((maturity-issue).days)
        new_fee_total=s['new_original_fee'];cum=M(new_fee_total*elapsed/whole)
        fee_amort=cum-s['new_amort_cumulative'];s['new_amort_cumulative']=cum;s['new_book_fee_left']=new_fee_total-cum
        # Coupon accrual uses exact contractual annual boundaries, not a leap-day 365 overcharge.
        coupon_accrual=ZERO
        for k in range(1,int(a['refinancing_term_years'])+1):
            b=date(issue.year+k-1,issue.month,issue.day);z=date(issue.year+k,issue.month,issue.day)
            lo=max(state['date'],b);hi=min(d,z)
            if hi>lo:
                accrued=M(s['new_original_face']*D(a['refinancing_coupon'])*D((hi-b).days)/D((z-b).days))
                coupon_accrual+=accrued-s['new_coupon_accruals'].get(str(k),ZERO)
                s['new_coupon_accruals'][str(k)]=accrued
        new_expense=coupon_accrual+fee_amort
    mother_profit-=old_expense+new_expense
    # Sale of previously owned asset adds cash AND removes the receivable in valuation.
    asset_receipt=ZERO
    if d==ds(e['sale_receivable_collection']):
        asset_receipt=M(c['observed'].get('h1_equity_sale_receivable_net',0));s['cash']+=asset_receipt;s['mother_cash']+=asset_receipt
    if D(a.get('future_buybacks',0))!=0:raise ValueError('new buyback schedule required; nonzero placeholder unsupported')
    subscription=ZERO
    if a['grant_enabled'] and d==ds(e['grant']):
        shares=int(c['observed']['grant_shares']);strike=D(c['observed']['grant_strike'])
        if shares>s['treasury_shares']:raise ValueError('award exceeds existing treasury shares')
        subscription=M(D(shares)*strike);s['treasury_shares']-=shares;s['cash']+=subscription;s['mother_cash']+=subscription
        s['equity_events'].append({'date':d,'kind':'treasury_delivery','new_eligible_shares':shares,'subscription':subscription,'legal_shares':s['legal_shares']})
    if a['bond_branch']=='convert' and d==ds(e['conversion']) and s['old_face']>0:
        requested=M(s['old_face']*D(a['conversion_fraction']));price=s['conversion_price']
        if price<=0:raise ClaimIncompatibility('nonpositive adjusted conversion price')
        shares=int(requested//price);used=M(D(shares)*price);oldface=s['old_face'];s['old_face']-=used
        s['old_book']=M(s['old_book']*s['old_face']/oldface);s['legal_shares']+=shares
        s['equity_events'].append({'date':d,'kind':'conversion','new_eligible_shares':shares,'subscription':ZERO,'converted_face':used,'unconverted_face':s['old_face'],'price_yuan_per_real_share':price})
        s['old_amort_base_date']=d;s['old_amort_base_book']=s['old_book'];s['old_amort_cumulative']=ZERO
        remaining_coupon=s['old_face']*D(e['coupon_rate']) if d<ds(e['coupon']) else ZERO
        s['old_amort_contract_total']=M(s['old_face']*D(e['redemption_multiple'])+remaining_coupon)-s['old_book']
    if a['bond_branch']=='refinance' and d==ds(e['refinancing']):
        if s['new_issued']:raise ValueError('second refinancing forbidden')
        req=strict_required_cash_snapshot(s,c);old_service=M(s['old_face']*D(e['redemption_multiple']))
        gap=max(ZERO,old_service+req['required_group']-s['cash'],old_service+req['required_mother']-s['mother_cash'])
        fee_rate=D(a['refinancing_fee_rate'])
        if not ZERO<=fee_rate<ONE:raise ValueError('invalid financing fee')
        face=ceil_money(gap/(1-fee_rate));fees=M(face*fee_rate);net=face-fees
        if net<gap:face+=CENT;fees=M(face*fee_rate);net=face-fees
        if face>0:
            s['cash']+=net;s['mother_cash']+=net;s['new_face']=face;s['new_issued']=True
            s['new_original_face']=face;s['new_original_fee']=fees;s['new_book_fee_left']=fees
            s['refinancing_issue']=d;s['refinancing_maturity']=date(d.year+int(a['refinancing_term_years']),d.month,d.day)
            financing(s,d,net,'one_gap_loan_net_proceeds',face=face,fee=fees,uncommitted=True)
    debt_cash=ZERO;deductible=ZERO
    if d==ds(e['coupon']) and s['old_face']>0:
        cash=M(s['old_face']*D(e['coupon_rate']));debt_cash+=cash;deductible+=cash;s['old_book']-=cash
        financing(s,d,-cash,'old_coupon')
    if d==mat and s['old_face']>0:
        cash=M(s['old_face']*D(e['redemption_multiple']));debt_cash+=cash
        deductible+=M(s['old_face']*(D(e['redemption_multiple'])-1 if a['premium_tax_shield'] else D(e['final_embedded_coupon_rate'])))
        # Finish any cumulative cent accounting residue explicitly; no second cash coupon.
        residual=cash-s['old_book'];old_expense+=residual;mother_profit-=residual;s['old_book']=ZERO;s['old_face']=ZERO
        financing(s,d,-cash,'old_115pct_redemption_including_final_coupon')
    if s['new_issued'] and not s['new_repaid'] and d.month==s['refinancing_issue'].month and d.day==s['refinancing_issue'].day and d>s['refinancing_issue']:
        k=d.year-s['refinancing_issue'].year
        if k<=int(a['refinancing_term_years']):
            coupon=M(s['new_original_face']*D(a['refinancing_coupon']));principal=s['new_face'] if d==s['refinancing_maturity'] else ZERO
            debt_cash+=coupon+principal;deductible+=coupon
            financing(s,d,-coupon-principal,'new_debt_service',coupon=coupon,principal=principal)
            if principal or d==s['refinancing_maturity']:s['new_face']=ZERO;s['new_repaid']=True
    s['cash']-=debt_cash;s['mother_cash']-=debt_cash
    eligible_shield=accrue_shield(s,c,d,deductible) if deductible else ZERO
    mother_profit+=eligible_shield  # Profit recognition now; cash follows the dated queue once.
    shield=s['shield_queue'].pop(iso(d),ZERO)
    if shield:
        s['cash']+=shield;s['mother_cash']+=shield
        s['shield_events'].append({'date':d,'cash':shield,'kind':'available_cash_interest_tax_shield'})
    # Entity legal profit and reserve precede actual repayment/dividend, never group averages.
    erate=D(c['reconstruction']['entity_statutory_reserve_rate'])
    ereserve=M(max(ZERO,entity_profit)*erate);s['nci_reserve']+=ereserve;s['nci_re']+=entity_profit-ereserve
    req=strict_required_cash_snapshot(s,c);support=ZERO;repay=ZERO;entitydiv=ZERO;minoritycash=ZERO;parentdiv=ZERO
    if s['nci_cash']<req['required_entity']:
        support=req['required_entity']-s['nci_cash'];s['nci_cash']=req['required_entity'];s['mother_cash']-=support;s['nci_parent_loan']+=support
    else:
        excess=s['nci_cash']-req['required_entity'];repay=min(excess,s['nci_parent_loan'])
        s['nci_cash']-=repay;s['mother_cash']+=repay;s['nci_parent_loan']-=repay
        if s['nci_parent_loan']==0:
            entitydiv=max(ZERO,min(s['nci_cash']-req['required_entity'],s['nci_re']))
            minoritycash=M(entitydiv*minority);parentdiv=entitydiv-minoritycash
            s['nci_cash']-=entitydiv;s['nci_re']-=entitydiv;s['mother_cash']+=parentdiv;s['cash']-=minoritycash;mother_profit+=parentdiv
    cap=M(D(s['legal_shares'])*D(a['statutory_reserve_share_cap']))
    reserve=min(max(ZERO,cap-s['mother_reserve']),M(max(ZERO,mother_profit)*D(a['statutory_reserve_rate'])))
    s['mother_reserve']+=reserve;s['mother_re']+=mother_profit-reserve
    normal_common=p['group']['profit']+gi-M(minority*entity_profit)-old_expense-new_expense+eligible_shield-taxflow['new_tax_accrual']
    s['year_profit'][year]=s['year_profit'].get(year,ZERO)+normal_common
    s['date']=d
    row={'date':d,'group_operating_actual':p['group']['actual_cash'],'entity_operating_actual':p['entity']['actual_cash'],
         'mother_operating_actual':mother_op_cash,'group_financial_return':gi,'mother_financial_return':mi,'entity_financial_return':ei,
         'entity_profit':entity_profit,'normal_common_profit':normal_common,'mother_profit':mother_profit,'mother_reserve_added':reserve,
         'old_debt_expense':old_expense,'new_debt_expense':new_expense,'financing_fees_issued_not_immediate_expense':fees,
         'debt_cash':debt_cash,'tax_shield_new_eligible':eligible_shield,'tax_shield_cash':shield,
         'entity_support':support,'entity_parent_loan_repayment':repay,'entity_dividend':entitydiv,'nci_cash_dividend':minoritycash,
         'parent_entity_dividend':parentdiv,'subscription':subscription,'asset_receipt':asset_receipt,
         'prior_cash':prior_cash,'prior_mother_cash':prior_mother,'prior_entity_cash':prior_entity,
         'foreign_financial_return':fy['foreign'],'other_financial_return':fy['other'],
         'tax_location':taxflow,'legacy_tax':legacy,'new_upstream':upstream}
    return s,row


def pay_dividend(s,c,value):
    value=M(value);eligible=s['legal_shares']-s['treasury_shares']
    if value<0 or eligible<=0:raise ValueError('invalid ordinary distribution')
    if value>0 and value>s['mother_re']-s['old_tax_parent_RE_hold']:raise ValueError('ordinary D exceeds RE after unrecognized legacy tax hold')
    s['cash']-=value;s['mother_cash']-=value;s['mother_re']-=value
    if value:
        s['distributions'].append({'date':s['date'],'total':value,'eligible_shares':eligible,'per_share':value/D(eligible)})
        if s['old_face']>0:s['conversion_price']=M(s['conversion_price']-value/D(s['legal_shares']))


def horizon(s,c):
    if s['new_issued'] and not s['new_repaid']:return s['refinancing_maturity']
    if s['old_face']>0:return ds(c['events']['maturity'])
    return s['date']


def shadow(s,periods,start,c,amount,keep_trace=False):
    state=copy.deepcopy(s);pay_dividend(state,c,amount);stop=horizon(state,c)
    snaps=[{'date':state['date'],**strict_required_cash_snapshot(state,c)}]
    # A proposed future loan exists ONLY within this clearly conditional scenario.
    for p in periods[start:]:
        if p['date']>stop:break
        state,_=advance(state,p,c)
        snaps.append({'date':state['date'],**strict_required_cash_snapshot(state,c)})
    feasible=all(x['strict_feasible'] for x in snaps)
    return {'feasible':feasible,'horizon':stop,'trace':snaps if keep_trace else [],'end_cash':state['cash'],'end_mother_cash':state['mother_cash']}


def dividend_capacity(s,periods,start,c):
    req=strict_required_cash_snapshot(s,c)
    current=max(ZERO,min(req['mother_available_RE'],req['slacks']['mother'],req['slacks']['group']))
    zero=shadow(s,periods,start,c,ZERO,True)
    if not zero['feasible']:return ZERO,{'zero':zero,'selected':zero,'zero_distribution_feasible':False}
    lo=0;hi=int(current/CENT)
    while lo<hi:
        mid=(lo+hi+1)//2
        if shadow(s,periods,start,c,D(mid)*CENT)['feasible']:lo=mid
        else:hi=mid-1
    value=D(lo)*CENT
    return value,{'zero':zero,'selected':shadow(s,periods,start,c,value,True),'zero_distribution_feasible':True,'capacity':value}


def activate_release_batch(s,c,capacity,target):
    years=int(c['assumptions']['cash_release_years'])
    total=max(ZERO,capacity-target)
    if years>0 and s['old_face']==0 and s['release_batch'] is None and total>0:
        slots=1 if c['reconstruction'].get('release_immediately',False) else years*2
        s['release_batch']={'original':total,'remaining':total,'installments':slots,'paid_slots':0,'arrears':ZERO}


def project(c,pack,journal):
    periods=pack['periods'];s=initial_state(c,pack);rows=[{'date':s['date'],'state':copy.deepcopy(s),'required':strict_required_cash_snapshot(s,c)}]
    journal.event('initial_state_raw',rows[0]);failures=[];shadows=[]
    if not rows[0]['required']['strict_feasible']:failures.append({'date':s['date'],'kind':'initial_required_cash','snapshot':rows[0]['required']})
    for i,p in enumerate(periods):
        journal.event('cash_transition_inputs_raw',{'state':s,'period':p})
        s,flow=advance(s,p,c);div=ZERO;target=ZERO;projection=None
        if iso(s['date'])[5:] in c['events']['dividend_month_days']:
            if c.get('mode')=='fixture' and 'targets' in c['fixture']:
                target=M(c['fixture']['targets'].get(iso(s['date']),0))
            else:target=M(max(ZERO,s['year_profit'].get(str(s['date'].year-1),ZERO))*D(c['assumptions']['payout'])/2)
            capacity,projection=dividend_capacity(s,periods,i+1,c)
            if not projection['zero_distribution_feasible']:failures.append({'date':s['date'],'kind':'zero_future_D_infeasible','projection':projection})
            activate_release_batch(s,c,capacity,target)
            extra=ZERO;b=s['release_batch']
            if b and b['remaining']>0:
                nominal=M(b['original']/D(b['installments']))
                extra=min(b['remaining'],nominal+b['arrears'])
            div=min(capacity,target+extra)
            base_paid=min(div,target);extra_paid=div-base_paid
            if b and b['remaining']>0:
                b['remaining']-=extra_paid;b['arrears']=max(ZERO,extra-extra_paid);b['paid_slots']+=1
            pay_dividend(s,c,div);shadows.append({'date':s['date'],'target':target,'actual':div,'projection':projection})
        snap=strict_required_cash_snapshot(s,c)
        row={'date':s['date'],'period':p,'flow':flow,'distribution':div,'target_distribution':target,'state':copy.deepcopy(s),'required':snap}
        journal.event('cash_period_raw',row)  # Persist BEFORE classifying.
        if snap['location_cash_residual']!=0:raise ValueError('group versus four cash locations must conserve exactly')
        if not snap['strict_feasible']:failures.append({'date':s['date'],'kind':'required_cash','snapshot':snap})
        rows.append(row)
    out={'identity':'NEW_RECONSTRUCTION','tax_policy':copy.deepcopy(c['tax_bridge']),'financial_return_parameters':{k:c['assumptions'][k] for k in ('financial_yield_pretax','mother_tax_rate','tax_rate')},'rows':rows,'funding_failures':failures,'dividend_projections':shadows,
         'tax_events':s['tax_events'],'financing_events':s['financing_events'],'tax_shield_events':s['shield_events'],'equity_events':s['equity_events'],'distributions':s['distributions']}
    journal.save('projection-complete.raw.json',out)
    # Keep completed cash history even if an economic constraint fails. Never create success values then.
    if failures:raise FundingIncompatibility('strict legal-cash/issued-service constraints failed; complete projection retained')
    return out

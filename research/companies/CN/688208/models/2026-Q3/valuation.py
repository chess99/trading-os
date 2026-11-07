"""NEW APV, entity capital floor, zero-growth auxiliary and equity-delivery recursion."""
from common import *
import tax_bridge as tb


def periodic_value(at,pretax_maintenance,tax,growth_capital,g,r,tax_queue):
    """Monthly normalized continuation. Annual growth cycles; cash tax paid next quarter.
    Annual amounts are NEXT-cycle amounts. Same implementation for A tail and B(g=0).
    Existing payable is paid once at its real queued date; it is never also in NWC.
    """
    g=D(g);r=D(r)
    if r<=g:raise TerminalCapitalIncompatibility('r_U must exceed continuation growth')
    numerator=ZERO
    for k in range(1,13):
        month=(at.month+k-1)%12+1
        extra=(3-month%3)%3+3
        numerator+=(D(pretax_maintenance)-D(growth_capital))/12*df(r,D(k)/12)
        numerator-=D(tax)/12*df(r,D(k+extra)/12)
    value=numerator/(1-(1+g)/(1+r))
    pending=sum(pv(v,ds(d),at,r) for d,v in tax_queue.items() if ds(d)>at)
    return {'value':value-pending,'new_activity_before_existing_tax':value,'existing_tax_queue_PV':pending,'monthly_numerator':numerator}


def terminal_contract(c,pack,projection,journal):
    a=c['assumptions'];g=D(a['g_terminal']);roic=D(a['terminal_incremental_roic']);r=D(a['r_u'])
    last=pack['periods'][-1];b=last['annual'];s=projection['rows'][-1]['state'];ep=last['endpoints'];at=last['date']
    if roic<=0:raise ValueError('positive target incremental ROIC required')
    parts={};incompatible=[]
    for part in ('entity','rest'):
        ann=b[part] if part in b else {k:b['group'][k]-b['entity'][k] for k in b['group']}
        en=part=='entity'
        nwc=ep['entity_nwc'] if en else ep['nwc']-ep['entity_nwc']
        buffer=ep['nci_buffer'] if en else ep['buffer']-ep['nci_buffer']
        deposits=ep['nci_deposits'] if en else ep['deposits']-ep['nci_deposits']
        maintenance_before_overlay=ann['pretax_maintenance']-ann['tax_accrual']
        overlay=ZERO if en else tb.operating_tax(c,maintenance_before_overlay)
        maint_profit=maintenance_before_overlay-overlay
        next_profit=maint_profit*(1+g)
        required=ann['growth']*(1+g)+g*(nwc+buffer+deposits)
        target=g*next_profit/roic if g>0 and maint_profit>0 else ZERO
        if g>0 and maint_profit<=0 and required>0:
            incompatible.append({'component':part,'maintenance_profit':maint_profit,'required_capital':required,'g':g,'roic_target':roic})
        actual=max(required,target)  # True investment floor, not cosmetic effective-ROIC label.
        if actual<0:actual=ZERO  # A net liquidation is NOT inferred from negative operating liabilities.
        queue=s['entity_tax_queue'] if en else {d:s['tax_queue'].get(d,ZERO)-s['entity_tax_queue'].get(d,ZERO) for d in set(s['tax_queue'])|set(s['entity_tax_queue'])}
        result=periodic_value(at,(ann['pretax_maintenance']-overlay)*(1+g),ann['tax_accrual']*(1+g),actual,g,r,queue)
        parts[part]={'maintenance_before_new_tax':maintenance_before_overlay,'new_tax_full_preparation':overlay,'maintenance_profit':maint_profit,'next_profit':next_profit,'required_capital':required,
                     'target_capital':target,'actual_capital':actual,'terminal_fcff_accrual_tax':next_profit-actual,
                     'effective_incremental_roic':g*next_profit/actual if actual>0 else None,'periodic':result}
    contract={'date':at,'components':parts,'group_actual_growth_capital':sum(p['actual_capital'] for p in parts.values()),
              'group_terminal_fcff_accrual_tax':sum(p['terminal_fcff_accrual_tax'] for p in parts.values()),
              'group_terminal_value':sum(p['periodic']['value'] for p in parts.values()),
              'entity_terminal_value':parts['entity']['periodic']['value'],'incompatible':incompatible}
    journal.save('terminal-contract.raw.json',contract)
    if incompatible:raise TerminalCapitalIncompatibility('negative/nonpositive component profit with positive growth and required capital; no target fitting')
    return contract


def values(c,pack,projection,terminal,journal):
    a,o=c['assumptions'],c['observed'];ru=D(a['r_u']);rd=D(a['r_d']);rc=D(a['r_common']);minority=D(a['nci_minority_fraction'])
    rows=projection['rows'];indices={iso(row['date']):i for i,row in enumerate(rows)};memo={};bridges=[]
    def operating(i,method):
        at=rows[i]['date'];state=rows[i]['state']
        if method=='A':
            group=sum(pv(p['group']['fcff']-tb.operating_tax(c,p['rest']['profit']),p['date'],at,ru) for p in pack['periods'] if p['date']>at)
            entity=sum(pv(p['entity']['fcff'],p['date'],at,ru) for p in pack['periods'] if p['date']>at)
            tailg=pv(terminal['group_terminal_value'],terminal['date'],at,ru);taile=pv(terminal['entity_terminal_value'],terminal['date'],at,ru)
            split={'explicit':group,'continuation':tailg}
            return group+tailg,entity+taile,split
        annual=pack['annual_budgets'].get(at.year,pack['periods'][0]['annual'])
        rest_maint=annual['group']['pretax_maintenance']-annual['entity']['pretax_maintenance']-annual['group']['tax_accrual']+annual['entity']['tax_accrual']
        overlay=tb.operating_tax(c,rest_maint)
        g=periodic_value(at,annual['group']['pretax_maintenance']-overlay,annual['group']['tax_accrual'],ZERO,ZERO,ru,state['tax_queue'])
        g['annual_new_tax_full_preparation']=overlay
        e=periodic_value(at,annual['entity']['pretax_maintenance'],annual['entity']['tax_accrual'],ZERO,ZERO,ru,state['entity_tax_queue'])
        return g['value'],e['value'],{'group_periodic':g,'entity_periodic':e}
    def equity(i,method):
        key=(i,method)
        if key in memo:return memo[key]
        row=rows[i];at=row['date'];s=row['state'];op,entityop,opdetails=operating(i,method)
        req=s['buffer']+s['deposits'];ereq=s['nci_buffer']+s['nci_deposits']
        collection=ds(c['events']['sale_receivable_collection'])
        receivable=pv(o.get('h1_equity_sale_receivable_net',0),collection,at,ru) if collection>at else ZERO
        assets=s['cash']-req+D(o.get('q3_trading_assets',0))+D(o.get('q3_noncurrent_equity_assets',0))+receivable
        entityassets=s['nci_cash']-ereq+D(a['nci_other_nonoperating_assets'])
        priority=s['nci_parent_loan']+D(a['nci_external_debt'])+D(a['nci_other_priority_claims'])
        nci=minority*max(ZERO,entityop+entityassets-priority)
        fin=sum(pv(x['cash'],x['date'],at,rd) for x in projection['financing_events'] if x['date']>at)
        shields=sum(pv(x['cash'],x['date'],at,ru) for x in projection['tax_shield_events'] if x['date']>at)
        # End-of-projection eligible shields (if any) must not vanish.
        shields+=sum(pv(v,ds(d),at,ru) for d,v in rows[-1]['state']['shield_queue'].items() if ds(d)>rows[-1]['date'])
        taxclaims=tb.claims(s)
        before=op+assets+fin+shields-taxclaims['total']-nci
        claims=[]
        for ev in reversed(projection['equity_events']):
            if ev['date']<=at:continue
            k=indices[iso(ev['date'])];post=equity(k,method)
            net=D(ev['new_eligible_shares'])*post['per_share']-D(ev['subscription'])
            # Existing rights are an option-like obligation, not a compulsory negative claim.
            claim=max(ZERO,net);discounted=pv(claim,ev['date'],at,rc)
            claims.append({'event':ev,'post_event_per_share':post['per_share'],'net_delivery_claim':claim,'PV':discounted,'exercise_value_below_subscription':net<0})
        total=before-sum(x['PV'] for x in claims);eligible=s['legal_shares']-s['treasury_shares']
        if eligible<=0:raise ValueError('no eligible common shares')
        result={'date':at,'method':method,'operating':op,'operating_detail':opdetails,'entity_operating':entityop,
                'consolidated_nonoperating_assets':assets,'entity_nonoperating_assets':entityassets,'entity_priority_claims':priority,
                'nci_residual_claim':nci,'financing_cash_leg_PV':fin,'limited_tax_shield_PV':shields,
                'legacy_repatriation_tax_claim':taxclaims['old'],'new_repatriation_tax_claim':taxclaims['new'],
                'tax_cash_holds_not_second_asset_deduction':True,
                'net_equity_delivery_claims':claims,'equity':total,'eligible_shares':eligible,'per_share':total/D(eligible)}
        memo[key]=result;bridges.append(result);return result
    current_i=indices[c['asof']];y5_i=indices[c['y5']]
    current={m:equity(current_i,m) for m in ('A','B')};y5={m:equity(y5_i,m) for m in ('A','B')}
    start=ds(c['asof']);distributions=[]
    for k in range(1,6):
        end=date(start.year+k,start.month,start.day);begin=date(start.year+k-1,start.month,start.day)
        distributions.append(sum(x['per_share'] for x in projection['distributions'] if begin<x['date']<=end))
    journal.save('valuation-bridges.raw.json',bridges)
    # Finite-life auxiliary is OPERATING ONLY, not a substitute common-equity endpoint.
    annual=pack['annual_budgets'].get(start.year,pack['periods'][0]['annual'])
    maintenance=annual['group']['pretax_maintenance']-annual['group']['tax_accrual']
    maintenance-=tb.operating_tax(c,maintenance-annual['entity']['pretax_maintenance']+annual['entity']['tax_accrual'])
    diagnostic=[]
    for life in a['b_life_years']:
        for decay in a['b_decay_rates']:
            val=sum(maintenance*(1-D(decay))**(k-1)*df(ru,D(k)) for k in range(1,int(life)+1))
            diagnostic.append({'life_years':life,'decay':decay,'operating_only_value':val,'residual':ZERO})
    return {'identity':'NEW_RECONSTRUCTION_not_original_result','status':'economic_path_passed_model_constraints_not_adopted',
            'current':current,'Y5':y5,'D':distributions,'current_state':rows[current_i]['state'],'Y5_state':rows[y5_i]['state'],
            'terminal_contract':terminal,'finite_life_B_operating_only':diagnostic,'full_projection':projection,
            'date_convention':'D is actual-date cash grouped into five October31 windows; no price or IRR calculated'}

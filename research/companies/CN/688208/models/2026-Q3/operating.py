"""New, explicit monthly generator; lost v4 caches are NOT reused or imitated."""
from common import *

SEGMENTS=('repair','software','energy','new_ai','other')
FLOW_KEYS=('ebit','tax_accrual','da','maintenance','growth','pretax_maintenance','profit')
CAP_KEYS=('da_physical','da_development','da_longterm','maintenance_physical','maintenance_development','maintenance_longterm','growth_physical','growth_development')

def advance_tax_queue(queue, accrual, end):
    due=iso(tax_due(end))
    queue[due]=queue.get(due,ZERO)+M(accrual)
    return queue.pop(iso(end),ZERO)

def cumulative_slice(total, elapsed_days, month_days, already):
    cumulative=M(D(total)*D(elapsed_days)/D(month_days))
    return cumulative-D(already),cumulative

def operating_fcff(b):
    return b['ebit']-b['cash_tax']+b['da']-b['maintenance']-b['growth']-b['nwc_change']-b['buffer_change']-b['deposit_change']

def validate_pack(pack):
    prev=pack['initial_operating']
    for p in pack['periods']:
        ep=p['endpoints']
        if 'stocks' in ep:
            if sum(ep['stocks'].values())!=ep['nwc']:raise ValueError('group stock/scalar NWC discrepancy')
            if sum(ep['entity_stocks'].values())!=ep['entity_nwc']:raise ValueError('entity stock/scalar NWC discrepancy')
            for k in ('deferred_short','deferred_long'):
                if ep['entity_stocks'][k]!=0:raise ValueError('software advance assigned to energy')
        for part,nk in (('group','nwc'),('entity','entity_nwc')):
            b=p[part]
            if b['nwc_change']!=ep[nk]-prev[nk]:raise ValueError('NWC flow/stock change discrepancy')
            if b['fcff']!=operating_fcff(b):raise ValueError('FCFF components discrepancy')
            if b['actual_cash']!=b['fcff']+b['buffer_change']+b['deposit_change']:raise ValueError('cash/buffer bridge discrepancy')
        for k in p['group']:
            if p['group'][k]!=p['entity'][k]+p['rest'][k]:raise ValueError('entity/rest do not conserve '+k)
        if 'capital_flow' in p:
            cf=p['capital_flow'];stocks=ep['capital_stock'];before=p['capital_before']
            if before!=prev['capital_stock']:raise ValueError('capital opening differs from preceding actual close')
            expected={'physical':before['physical']+cf['maintenance_physical']+cf['growth_physical']-cf['da_physical'],
                      'development':before['development']+cf['maintenance_development']+cf['growth_development']-cf['da_development'],
                      'longterm':before['longterm']+cf['maintenance_longterm']-cf['da_longterm']}
            if stocks!=expected:raise ValueError('real-period capital does not conserve')
            if p['date'].month==12 and p['date'].day==31:
                for asset in ('physical','development','longterm'):
                    if stocks[asset]!=p['annual'][asset+'_end']:raise ValueError('year-end actual capital differs from next-year opening budget')
        prev=ep


def segment_mix(o):
    raw={'repair':sum(D(o[k]) for k in ('h1_diagnostics','h1_tpms','h1_adas','h1_repair_other')),
         'software':D(o['h1_ai_software'])-D(o['h1_new_ai_rounded']),
         'energy':D(o['h1_energy']),'new_ai':D(o['h1_new_ai_rounded']),'other':D(o['h1_other_revenue'])}
    total=sum(raw.values())
    if total!=D(o['h1_revenue']): raise ValueError('H1 mutually exclusive revenue components do not sum')
    return {k:v/total for k,v in raw.items()}

def annual_budgets(c):
    o,a,n,al=c['observed'],c['assumptions'],c['reconstruction'],c['allocation']
    mix=segment_mix(o)
    q4g=D(o['q3_2026_revenue_growth']) if n['q4_growth_override'] is None else D(n['q4_growth_override'])
    q4=M(D(o['revenue_quarters_2025'][3])*(1+q4g))
    base=M(D(o['revenue_9m_2026'])+q4)
    r={s:M(base*mix[s]) for s in SEGMENTS};r['other']+=base-sum(r.values())
    phy=D(o['q3_fixed_assets']);dev=D(o['q3_intangible_assets'])+D(o['q3_development_assets']);longterm=D(o['q3_longterm_prepaid'])
    phy_da_rate=2*D(o['h1_physical_depreciation'])/D(o['h1_fixed_assets'])
    dev_da_rate=2*D(o['h1_intangible_amortization'])/(D(o['h1_intangible_assets'])+D(o['h1_development_assets']))
    longterm_da_rate=2*D(o['h1_longterm_amortization'])/D(o['h1_longterm_prepaid'])
    phyratio=D(o['h1_fixed_assets'])/(2*D(o['h1_revenue']))
    capshare=D(o['h1_rd_capitalized'])/D(o['h1_rd_total'])
    rou=max(ZERO,D(o['h1_fixed_and_rou_depreciation'])-D(o['h1_physical_depreciation']))
    rdrou=min(rou,D(o['h1_rd_da']))
    rdnonrou=max(ZERO,D(o['h1_rd_da'])-rdrou)
    othergm=1-D(o['h1_other_cost'])/D(o['h1_other_revenue'])
    building=D(al['physical_asset_building_net_anchor'])/D(al['physical_asset_total_net_anchor'])
    previous_r=base
    budgets={}
    for year in range(2026,2038):
        if year>2026:
            for s in SEGMENTS:
                if year<=2029: g=D(a['growth_2027_2029'][s])
                elif year<=2031: g=D(a['growth_2030_2031'][s])
                else:
                    w=min(ONE,D(year-2031)/5)
                    g=D(a['growth_2030_2031'][s])*(1-w)+D(a['g_terminal'])*w
                r[s]=M(r[s]*(1+g))
        revenue=sum(r.values()); f=revenue/(2*D(o['h1_revenue']))
        rates_w=min(ONE,max(ZERO,D(year-2026)/5))
        rd_rate=D(a['rd_rate_initial'])*(1-rates_w)+D(a['rd_rate_2031'])*rates_w
        admin=D(a['admin_rate_initial'])*(1-rates_w)+D(a['admin_rate_2031'])*rates_w
        resource=M(revenue*rd_rate);kdev=M(resource*capshare)
        da_phy=M(phy*phy_da_rate); da_dev=M(min(dev+kdev,dev*dev_da_rate))
        da_other=M(longterm*longterm_da_rate)
        rd_nonrou=M(min(da_phy+da_dev+da_other,2*rdnonrou*f))
        rd_rou=M(2*rdrou*f)
        expensed_rd_cash=resource-kdev-rd_nonrou-rd_rou
        if expensed_rd_cash<0: raise ValueError('negative RD cash resource decomposition')
        # All cash GM, sales/admin and RD resource budgets EXCLUDE cash lease rent.
        # Historical book margins/resources calibrate levels, not a claimed lease/DA reversal.
        sales=M(revenue*D(a['sales_rate']));administration=M(revenue*admin)
        rent=M(2*D(o['h1_cash_rent_total'])*f)
        losses=M(revenue*sum(D(x) for x in o['q3_credit_and_asset_losses'])/D(o['revenue_9m_2026']))
        surtax=M(revenue*D(o['q3_nonincome_taxes'])/D(o['revenue_9m_2026']))
        shared=sales+administration+expensed_rd_cash+rent+losses+surtax
        gp={s:M(r[s]*(othergm if s=='other' else D(a['gross_margins'][s]))) for s in SEGMENTS}
        costs={s:r[s]-gp[s] for s in SEGMENTS};cogs=sum(costs.values())
        physical_share={s:building*r[s]/revenue+(1-building)*costs[s]/cogs for s in SEGMENTS}
        ebit={s:M(gp[s]-shared*r[s]/revenue-da_phy*physical_share[s]-(da_dev+da_other)*r[s]/revenue) for s in SEGMENTS}
        ebit['other']+=sum(gp.values())-shared-da_phy-da_dev-da_other-sum(ebit.values())
        taxes={s:M(max(ZERO,ebit[s])*D(a['tax_rate'])) for s in SEGMENTS}
        maint_phy=M(da_phy*D(a['physical_maintenance_multiplier']))
        maint_dev=M(kdev*D(a['rd_maintenance_share']))
        maint_other=da_other  # recurring fit-out replacement once; not a second rent payment
        target_phy=M(phy if year==2026 else revenue*phyratio)
        growth_phy=M(max(ZERO,target_phy-(phy+maint_phy-da_phy)))
        growth_dev=kdev-maint_dev
        capital={'da_physical':da_phy,'da_development':da_dev,'da_longterm':da_other,
                 'maintenance_physical':maint_phy,'maintenance_development':maint_dev,'maintenance_longterm':maint_other,
                 'growth_physical':growth_phy,'growth_development':growth_dev}
        # FY2026 is a normalization flow rate, but opening stocks are actual September30.
        # ONLY Q4 modeled cash/DA advances those stocks into January2027.
        covered_weight=q4/base if year==2026 else ONE
        covered={k:M(v*covered_weight) for k,v in capital.items()}
        phy_end=phy+covered['maintenance_physical']+covered['growth_physical']-covered['da_physical']
        dev_end=dev+covered['maintenance_development']+covered['growth_development']-covered['da_development']
        longterm_end=longterm+covered['maintenance_longterm']-covered['da_longterm']
        if min(phy_end,dev_end,longterm_end)<0: raise ValueError('capital stock negative')
        cash_cost=sales+administration+expensed_rd_cash+rent+M(r['energy']*D(n['buffer_warranty_cost_share_of_energy_revenue']))
        # 1% energy sales is a buffer-only warranty-cost proxy WITHIN existing COGS.
        buffer=ceil_money(cash_cost*D(a['cash_buffer_months'])/12)
        alpha=D(a['nci_entity_energy_share']); revshare=r['energy']/revenue; pshare=physical_share['energy']
        entity={'ebit':M(alpha*ebit['energy']), 'tax_accrual':M(alpha*taxes['energy']),
                'da':M(alpha*(da_phy*pshare+(da_dev+da_other)*revshare)),
                'maintenance':M(alpha*(maint_phy*pshare+(maint_dev+maint_other)*revshare)),
                'growth':M(alpha*(growth_phy*pshare+growth_dev*revshare))}
        group={'ebit':sum(ebit.values()),'tax_accrual':sum(taxes.values()),'da':da_phy+da_dev+da_other,
               'maintenance':maint_phy+maint_dev+maint_other,'growth':growth_phy+growth_dev}
        for block in (group,entity):
            block['profit']=block['ebit']-block['tax_accrual']
            block['pretax_maintenance']=block['ebit']+block['da']-block['maintenance']
        budgets[year]={'year':year,'revenue':revenue,'revenues':dict(r),'cogs':cogs,'segment_cogs':costs,
                       'segment_ebit':ebit,'segment_tax_accrual':taxes,'group':group,'entity':entity,
                       'buffer':buffer,'nci_buffer':ceil_money(buffer*revshare*alpha),
                       'physical_share':pshare,'energy_revenue_share':revshare,'energy_cogs_share':costs['energy']/cogs,
                       'physical_begin':phy,'physical_end':phy_end,'development_begin':dev,'development_end':dev_end,
                       'longterm_begin':longterm,'longterm_end':longterm_end,'covered_weight':covered_weight,
                       'capital_annual':capital,'capital_covered_period':covered,
                       'rd_resource':resource,'rd_capital_cash':kdev,'rd_expensed_cash':expensed_rd_cash,
                       'rd_rou_in_resource_not_DA_addback':rd_rou,'rd_nonROU_in_total_DA_once':rd_nonrou,
                       'q4_revenue_seed':q4,'cash_cost_for_buffer':cash_cost}
        previous_r=revenue;phy=phy_end;dev=dev_end;longterm=longterm_end
    return budgets


def stock_targets(c,budgets,year):
    o,a=c['observed'],c['assumptions'];b=budgets[year];base=budgets[2026]
    rr=b['revenue']/base['revenue']; cr=b['cogs']/base['cogs'];sw=b['revenues']['software']/base['revenues']['software']
    values={'ar':M(D(o['q3_ar_net'])*rr),'inventory':M(D(o['q3_inventory_net'])*cr),
            'prepay':M(D(o['q3_prepay'])*cr),'vat':M(D(o['h1_input_vat_credit_rounded'])*cr),
            'ap':-M(D(o['q3_ap'])*cr),'notes':-M(D(o['q3_trade_notes'])*cr),
            'deferred_short':-M(D(o['q3_deferred_short'])*sw),'deferred_long':-M(D(o['q3_deferred_long'])*sw),
            'payroll':-M(D(o['q3_payroll_accrual'])*rr),'warranty':-M(D(o['h1_warranty_liability'])*cr),
            'energy_stress':ZERO if year==2026 else M(b['segment_cogs']['energy']*D(a['inventory_days_stress_energy'])/365)}
    return values


def endpoint(c,budgets,d):
    year=d.year; b=budgets[year];alpha=D(c['assumptions']['nci_entity_energy_share']);al=c['allocation'];n=c['reconstruction']
    # 2026 Q3 actual net NWC retained through year-end; no surprise Q4 release.
    current=stock_targets(c,budgets,year)
    prev=stock_targets(c,budgets,max(2026,year-1))
    w=ZERO if year==2026 else D(d.month)/12
    if d.day!=calendar.monthrange(year,d.month)[1]: raise ValueError('endpoint requires month end')
    stocks={k:M(prev[k]+(current[k]-prev[k])*w) for k in current}
    rs=b['energy_revenue_share'];cs=b['energy_cogs_share']
    den=n['energy_density_override'];ard=D(al['energy_ar_density'] if den is None else den)
    invd=D(al['energy_inventory_density'] if den is None else den);wd=D(al['energy_warranty_density'] if den is None else den)
    dense=lambda share,density: density*share/(1+(density-1)*share)
    def weights_for(rr,cc):
        return {'ar':dense(rr,ard),'inventory':dense(cc,invd),'prepay':cc,'vat':cc,'ap':cc,'notes':cc,
                'deferred_short':ZERO,'deferred_long':ZERO,'payroll':rr,'warranty':dense(cc,wd),'energy_stress':ONE}
    p=budgets[max(2026,year-1)]
    weights=weights_for(rs,cs);previous_weights=weights_for(p['energy_revenue_share'],p['energy_cogs_share'])
    entity_start={k:M(prev[k]*previous_weights[k]*alpha) for k in prev}
    entity_target={k:M(current[k]*weights[k]*alpha) for k in current}
    entity={k:M(entity_start[k]+(entity_target[k]-entity_start[k])*w) for k in stocks}
    rest={k:stocks[k]-entity[k] for k in stocks}
    buffer=ceil_money(p['buffer']+(b['buffer']-p['buffer'])*w)
    eb=ceil_money(p['nci_buffer']+(b['nci_buffer']-p['nci_buffer'])*w)
    dep0=D(c['observed']['q3_cash'])-D(c['observed']['q3_cash_equivalents'])
    dr=b['revenue']/budgets[2026]['revenue'];pr=p['revenue']/budgets[2026]['revenue']
    deposits=ceil_money(dep0*(pr+(dr-pr)*w))
    ed_start=ceil_money(dep0*pr*p['energy_cogs_share']*alpha)
    ed_target=ceil_money(dep0*dr*cs*alpha)
    ed=ceil_money(ed_start+(ed_target-ed_start)*w)
    return {'date':d,'stocks':stocks,'entity_stocks':entity,'rest_stocks':rest,
            'nwc':sum(stocks.values()),'entity_nwc':sum(entity.values()),'rest_nwc':sum(rest.values()),
            'buffer':buffer,'nci_buffer':eb,'deposits':deposits,'nci_deposits':ed}


def all_dates(c):
    start,end=ds(c['initial_date']),ds(c['end']);dates=set()
    m=add_months(start,1)
    while m<=end: dates.add(m);m=add_months(m,1)
    for key,value in c['events'].items():
        if isinstance(value,str) and len(value)==10:
            d=ds(value)
            if start<d<=end: dates.add(d)
    for year in range(start.year,end.year+1):
        for md in c['events']['dividend_month_days']:
            d=ds(str(year)+'-'+md)
            if start<d<=end: dates.add(d)
    refi=ds(c['events']['refinancing'])
    for k in range(1,int(c['assumptions']['refinancing_term_years'])+1):
        d=date(refi.year+k,refi.month,refi.day)
        if start<d<=end: dates.add(d)
    dates.update((ds(c['asof']),ds(c['y5'])))
    return sorted(dates)


def build_company_pack(c,journal):
    budgets=annual_budgets(c);journal.save('annual-budgets.raw.json',budgets)
    start=ds(c['initial_date']);initial=endpoint(c,budgets,start)
    o,a=c['observed'],c['assumptions'];qweights=[D(x)/sum(D(v) for v in o['revenue_quarters_2025']) for x in o['revenue_quarters_2025']]
    queue={};equeue={}
    # Initial tax payable is a NEW bounded normalisation, not a Q3 tax footnote fact.
    q3weight=qweights[2]
    initial_tax=M(budgets[2026]['group']['tax_accrual']*q3weight)
    initial_etax=M(budgets[2026]['entity']['tax_accrual']*q3weight)
    queue['2026-12-31']=initial_tax;equeue['2026-12-31']=initial_etax
    initial['tax_queue']=dict(queue);initial['entity_tax_queue']=dict(equeue)
    periods=[];prev=initial;prev_date=start
    month_totals={};month_allocated={};capital_totals={};capital_allocated={}
    initial['capital_stock']={'physical':D(o['q3_fixed_assets']),
                              'development':D(o['q3_intangible_assets'])+D(o['q3_development_assets']),
                              'longterm':D(o['q3_longterm_prepaid'])}
    capital_stock=dict(initial['capital_stock'])
    # Cumulative allocation to each within-month cut ensures no lost/repeated cent.
    for end in all_dates(c):
        b=budgets[end.year];me=month_end(end.year,end.month);ms=date(end.year,end.month,1)
        before=month_end(end.year-1,12) if end.month==1 else month_end(end.year,end.month-1)
        prior_ep=endpoint(c,budgets,before);next_ep=endpoint(c,budgets,me)
        w=D(end.day)/D(me.day)
        ep={k:M(prior_ep[k]+(next_ep[k]-prior_ep[k])*w) for k in ('nwc','entity_nwc','buffer','nci_buffer','deposits','nci_deposits')}
        ep['stocks']={k:M(prior_ep['stocks'][k]+(next_ep['stocks'][k]-prior_ep['stocks'][k])*w) for k in prior_ep['stocks']}
        ep['entity_stocks']={k:M(prior_ep['entity_stocks'][k]+(next_ep['entity_stocks'][k]-prior_ep['entity_stocks'][k])*w) for k in prior_ep['entity_stocks']}
        # Stocks, not separately interpolated scalar sums, are authoritative in NEW generator.
        ep['nwc']=sum(ep['stocks'].values());ep['entity_nwc']=sum(ep['entity_stocks'].values())
        key=(end.year,end.month)
        if key not in month_totals:
            if end.year==2026:
                cy=b['covered_weight'] if end.month==12 else b['covered_weight']*D(end.month-9)/3
                py=b['covered_weight']*D(end.month-10)/3
            else:
                qi=(end.month-1)//3; within=(end.month-1)%3+1
                py=sum(qweights[:qi])+qweights[qi]*D(within-1)/3
                cy=sum(qweights[:qi])+qweights[qi]*D(within)/3
                if end.month==12:cy=ONE
            # Difference of cumulative amounts: all full-year/stub cents close exactly.
            month_totals[key]={part:{k:M(b[part][k]*cy)-M(b[part][k]*py) for k in FLOW_KEYS} for part in ('group','entity')}
            month_allocated[key]={part:{k:ZERO for k in FLOW_KEYS} for part in ('group','entity')}
            capital_totals[key]={k:M(b['capital_annual'][k]*cy)-M(b['capital_annual'][k]*py) for k in CAP_KEYS}
            capital_allocated[key]={k:ZERO for k in CAP_KEYS}
        blocks={}
        for part in ('group','entity'):
            block={}
            for field in FLOW_KEYS:
                slice_value,cum=cumulative_slice(month_totals[key][part][field],end.day,me.day,month_allocated[key][part][field])
                block[field]=slice_value;month_allocated[key][part][field]=cum
            # Arithmetic identities exact after primitive amounts are rounded.
            block['profit']=block['ebit']-block['tax_accrual']
            block['pretax_maintenance']=block['ebit']+block['da']-block['maintenance']
            blocks[part]=block
        capital_flow={}
        for field in CAP_KEYS:
            sliced,cum=cumulative_slice(capital_totals[key][field],end.day,me.day,capital_allocated[key][field])
            capital_flow[field]=sliced;capital_allocated[key][field]=cum
        capital_before=dict(capital_stock)
        capital_stock['physical']+=capital_flow['maintenance_physical']+capital_flow['growth_physical']-capital_flow['da_physical']
        capital_stock['development']+=capital_flow['maintenance_development']+capital_flow['growth_development']-capital_flow['da_development']
        capital_stock['longterm']+=capital_flow['maintenance_longterm']-capital_flow['da_longterm']
        ep['capital_stock']=dict(capital_stock)
        blocks['group']['da']=capital_flow['da_physical']+capital_flow['da_development']+capital_flow['da_longterm']
        blocks['group']['maintenance']=capital_flow['maintenance_physical']+capital_flow['maintenance_development']+capital_flow['maintenance_longterm']
        blocks['group']['growth']=capital_flow['growth_physical']+capital_flow['growth_development']
        blocks['group']['pretax_maintenance']=blocks['group']['ebit']+blocks['group']['da']-blocks['group']['maintenance']
        cash_tax=advance_tax_queue(queue,blocks['group']['tax_accrual'],end)
        ecash_tax=advance_tax_queue(equeue,blocks['entity']['tax_accrual'],end)
        for part,prefix,tax in (('group','',cash_tax),('entity','entity_',ecash_tax)):
            block=blocks[part];block['cash_tax']=tax
            block['nwc_change']=ep[prefix+'nwc']-prev[prefix+'nwc']
            bk='buffer' if part=='group' else 'nci_buffer';dk='deposits' if part=='group' else 'nci_deposits'
            block['buffer_change']=ep[bk]-prev[bk];block['deposit_change']=ep[dk]-prev[dk]
            block['fcff']=operating_fcff(block)
            block['actual_cash']=block['fcff']+block['buffer_change']+block['deposit_change']
        rest={k:blocks['group'][k]-blocks['entity'][k] for k in blocks['group']}
        p={'start':prev_date,'date':end,'days':(end-prev_date).days,'group':blocks['group'],'entity':blocks['entity'],'rest':rest,
           'endpoints':ep,'capital_flow':capital_flow,'capital_before':capital_before,'tax_queue':dict(queue),'entity_tax_queue':dict(equeue),'annual':b}
        journal.event('operating_period_raw',p)
        for k in blocks['group']:
            if blocks['group'][k]!=blocks['entity'][k]+rest[k]: raise ValueError('entity conservation '+k)
        if ep['entity_stocks']['deferred_short']!=0 or ep['entity_stocks']['deferred_long']!=0: raise ValueError('software financing leaked to energy')
        periods.append(p);prev=ep;prev_date=end
    return {'mode':'company_NEW_RECONSTRUCTION','initial_operating':initial,'periods':periods,'annual_budgets':budgets}

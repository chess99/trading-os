"""Self-contained owner-cash model. Python stdlib only; CNY million.
Core is the SAME simulate() chain for formal and stressed distributions.
No files/network are read by functions. CLI reads only the supplied JSON.
"""
import math, json, copy, sys

class DomainError(ValueError): pass

def finite_tree(x):
    if isinstance(x, bool): return
    if isinstance(x, (int,float)) and not math.isfinite(x): raise DomainError('nonfinite input')
    if isinstance(x, dict):
        for v in x.values(): finite_tree(v)
    if isinstance(x, list):
        for v in x: finite_tree(v)

def number(x,label):
    # bool is an int subclass in Python, but not a financial amount/rate.
    if type(x) not in (int,float) or not math.isfinite(x): raise DomainError('numeric type/finite: '+label)

def validate(p,e):
    finite_tree(p); finite_tree(e)
    scalar=['shares','cash0','parent_cash0','minority_cash0','ppe0_full','joint_capital0',
      'debt0','retirement0','nwc0_full','parent_legal0','sub_legal0','joint_receivable0',
      'financial_asset0','borrowing_limit','freeze_amount','internal_net_payment_y1','internal_receivable0',
      'minority_asset_fraction','parent_operating_fraction','parent_buffer_fraction','tax_rate',
      'sub_payout','joint_payout','joint_cash_same_year','common_payout','freeze_loss_fraction',
      'cash_yield_net','financial_asset_yield','borrowing_rate','cash_buffer_ratio','research_ratio',
      'other_operating_cost_ratio','other_margin','minority_profit_y1','joint_profit_y1','joint_growth_first_five']
    for k in scalar: number(p[k],k)
    for k in ['g','ke']: number(e[k],k)
    if type(p.get('release_policy',True)) is not bool: raise DomainError('release_policy must be boolean')
    if not (0 <= e['g'] < e['ke'] <= .3): raise DomainError('g/ke')
    if type(e['release_year']) is not int or not 6 <= e['release_year'] <= 15: raise DomainError('release horizon')
    if p['shares'] <= 0: raise DomainError('shares')
    for k in ['cash0','parent_cash0','ppe0_full','joint_capital0','debt0','retirement0',
      'joint_receivable0','financial_asset0','borrowing_limit','freeze_amount','internal_net_payment_y1','internal_receivable0','joint_profit_y1']:
        if p[k] < 0: raise DomainError(k)
    # NWC and accumulated legal profit are signed; deficits are not physical assets.
    if not 0 <= p['minority_cash0'] <= p['cash0'] or p['parent_cash0'] > p['cash0']-p['minority_cash0']: raise DomainError('cash attribution')
    for k in ['minority_asset_fraction','parent_operating_fraction','parent_buffer_fraction','tax_rate','sub_payout','joint_payout','joint_cash_same_year','common_payout','freeze_loss_fraction']:
        if not 0 <= p[k] <= 1: raise DomainError(k)
    for k in ['sub_delay_years','joint_extra_delay_years']:
        if type(p[k]) is not int or not 0 <= p[k] <= 2: raise DomainError(k)
    if type(p['freeze_release_year']) is not int or not 2 <= p['freeze_release_year'] <= 5: raise DomainError('freeze_release_year')
    if p['freeze_amount'] > p['parent_cash0']: raise DomainError('freeze outside parent cash')
    if not 0<=p['cash_yield_net']<=.05 or not 0<=p['financial_asset_yield']<=.15 or not 0<=p['borrowing_rate']<=.2: raise DomainError('yield')
    sizes={'initial_revenue':3,'growth_first_five':3,'instrument_margin':5,'material_margin':5,
      'sales_ratio':5,'admin_ratio':5,'nwc_ratio':5,'maintenance_capex':5,'growth_capex':5,'depreciation':5}
    for k,n in sizes.items():
        if type(p[k]) is not list or len(p[k])!=n: raise DomainError('vector shape: '+k)
        for v in p[k]: number(v,k)
    for k in ['sales_ratio','admin_ratio']:
        if any(not 0<=v<=1 for v in p[k]): raise DomainError(k)
    for k in ['maintenance_capex','growth_capex','depreciation']:
        if any(v<0 for v in p[k]): raise DomainError(k)
    if any(not -1<=v<=.6 for v in p['instrument_margin']+p['material_margin']): raise DomainError('supported instrument/material margin')
    if not -1<=p['other_margin']<=1: raise DomainError('other_margin')
    if any(not -1<=v<=1 for v in p['nwc_ratio']): raise DomainError('nwc_ratio')
    if any(v<0 for v in p['initial_revenue']) or sum(p['initial_revenue'])<=0: raise DomainError('revenue')
    if any(not -.2<=v<=.2 for v in p['growth_first_five']) or not -.2<=p['joint_growth_first_five']<=.2: raise DomainError('supported growth')
    if type(p['revenue_multipliers']) is not list or len(p['revenue_multipliers'])!=5: raise DomainError('multipliers shape')
    for row in p['revenue_multipliers']:
        if type(row) is not list or len(row)!=3: raise DomainError('multipliers shape')
        for v in row:
            number(v,'revenue_multipliers')
            if not 0<v<=2: raise DomainError('multipliers')
    if not 0<=p['cash_buffer_ratio']<=.4 or not 0<=p['research_ratio']<=.2 or not 0<=p['other_operating_cost_ratio']<=.2: raise DomainError('operating ratio')

def operating_path(p,e,years):
    """Profit, capital and reinvestment; same base required in every scenario."""
    own=1-p['minority_asset_fraction']; ppe=p['ppe0_full']*own; nwc=p['nwc0_full']*own
    jcap=p['joint_capital0']; out=[]; rev=None; jprofit=None
    for t in range(1,years+1):
        i=min(t-1,4)
        if t<=5:
            rev=[p['initial_revenue'][j]*(1+p['growth_first_five'][j])**(t-1)*p['revenue_multipliers'][t-1][j] for j in range(3)]
            jprofit=p['joint_profit_y1']*(1+p['joint_growth_first_five'])**(t-1)
            jgrow=p['joint_growth_first_five']
            capex=(p['maintenance_capex'][i]+p['growth_capex'][i])*own
            da=p['depreciation'][i]*own
        else:
            # Five years of fade, not maturity at Y5. Same margins persist thereafter.
            weight=max(0,(10-t)/5)
            rates=[e['g']+(v-e['g'])*weight for v in p['growth_first_five']]
            rev=[rev[j]*(1+rates[j]) for j in range(3)]
            jgrow=e['g']+(p['joint_growth_first_five']-e['g'])*weight
            jprofit*=1+jgrow
            # Maintain actual Y5 PPE/revenue intensity as growth fades.
            target=out[4]['ppe']/out[4]['revenue']*sum(rev)
            da=out[4]['da']*sum(rev)/out[4]['revenue']
            capex=da+target-ppe
        revenue=sum(rev)
        # Physical productive assets cannot become negative. Shrinkage may reduce
        # investment, but an unmodelled asset sale is not negative gross capex.
        for label,value in [('revenue',revenue),('capex',capex),('depreciation',da),('ppe_after_investment',ppe+capex-da)]:
            if not math.isfinite(value) or value < 0: raise DomainError('dynamic physical state: '+label+' year '+str(t))
        gross=rev[0]*p['instrument_margin'][i]+rev[1]*p['material_margin'][i]+rev[2]*p['other_margin']
        ebit=gross-revenue*(p['sales_ratio'][i]+p['admin_ratio'][i]+p['research_ratio']+p['other_operating_cost_ratio'])
        tax=max(0,ebit)*p['tax_rate']
        minority=p['minority_profit_y1']*revenue/sum(p['initial_revenue'])
        nopat=ebit-tax-minority
        new_nwc=revenue*p['nwc_ratio'][i]*own
        delta_nwc=new_nwc-nwc; nwc=new_nwc
        ppe+=capex-da
        required_cash=revenue*p['cash_buffer_ratio']*own
        delta_jcap=jcap*jgrow; jcap+=delta_jcap
        if not math.isfinite(jcap) or jcap<0: raise DomainError('dynamic joint capital year '+str(t))
        out.append(dict(year=t,revenue=revenue,instrument_revenue=rev[0],material_revenue=rev[1],gross_profit=gross,
            ebit=ebit,core_common_nopat=nopat,minority_profit=minority,capex=capex,da=da,nwc=nwc,delta_nwc=delta_nwc,ppe=ppe,
            required_cash=required_cash,operating_capital=ppe+nwc+required_cash,
            core_cash_before_buffer=nopat+da-capex-delta_nwc,joint_profit=jprofit,joint_capital=jcap,joint_reinvestment=delta_jcap))
    return out

def simulate(p,e):
    validate(p,e)
    # Longest release15 + three settlement years + two tests of terminal steady flow.
    horizon=e['release_year']+3+3*max(p['sub_delay_years'],p['joint_extra_delay_years']) if p.get('release_policy',True) else 10
    rows=operating_path(p,e,horizon+2)
    parent=p['parent_cash0']; sub=p['cash0']-p['minority_cash0']-parent
    plegal=p['parent_legal0']; slegal=p['sub_legal0']; debt=p['debt0']
    asset=p['financial_asset0']; blocked=0.; jsurplus=0.
    sub_queue=[]; joint_queue=[(1,p['joint_receivable0'])]
    records=[]; frac=p['parent_operating_fraction']; eps=1e-7
    for r in rows:
        t=r['year']; release=t>=e['release_year'] and p.get('release_policy',True); pc0=parent; sc0=sub; d0=debt; block0=blocked; a0=asset
        slegal0=slegal; plegal0=plegal
        shock=loss=recovery=0.
        if t==1 and p['freeze_amount']:
            shock=p['freeze_amount']; loss=shock*p['freeze_loss_fraction']; blocked=shock-loss; parent-=shock
        if t==p['freeze_release_year'] and blocked:
            recovery=blocked; parent+=recovery; blocked=0.
        pint=max(parent,0)*p['cash_yield_net']; sint=max(sub,0)*p['cash_yield_net']; fincome=asset*p['financial_asset_yield']
        interest=debt*p['borrowing_rate']
        sale=asset if release else 0.
        if sale: asset=0.
        retire=p['retirement0'] if t==1 else 0.
        internal=p['internal_net_payment_y1'] if t==1 else 0.
        parent+=r['core_cash_before_buffer']*frac+pint+fincome+sale-interest-retire-internal
        sub+=r['core_cash_before_buffer']*(1-frac)+sint+internal
        # JV earnings, declaration and cash are three separate quantities.
        jsurplus+=r['joint_profit']-r['joint_reinvestment']
        if jsurplus < -eps:
            return {'feasible':False,'failure':{'year':t,'reason':'joint required capital exceeds retained cash; no unbudgeted JV funding','shortfall':-jsurplus},'records':records}
        jdecl=max(0,jsurplus) if release else min(max(0,jsurplus),max(0,r['joint_profit']*p['joint_payout']))
        jsurplus-=jdecl
        jd=p['joint_extra_delay_years']
        joint_queue += [(t+jd,jdecl*p['joint_cash_same_year']),(t+jd+1,jdecl*(1-p['joint_cash_same_year']))]
        jcash=sum(v for due,v in joint_queue if due<=t); joint_queue=[(due,v) for due,v in joint_queue if due>t]
        parent+=jcash
        sfloor=r['required_cash']*(1-p['parent_buffer_fraction']); pfloor=r['required_cash']*p['parent_buffer_fraction']
        sub_profit=r['core_common_nopat']*(1-frac)+sint
        slegal+=sub_profit
        pending=sum(v for due,v in sub_queue)
        starget=max(0,sub-sfloor-pending) if release else max(0,sub_profit*p['sub_payout'])
        sdecl=min(max(0,slegal),starget); slegal-=sdecl
        sub_queue.append((t+p['sub_delay_years'],sdecl))
        due=sum(v for date,v in sub_queue if date<=t)
        scash=min(due,max(0,sub-sfloor)); sub-=scash; parent+=scash
        remaining=scash; nq=[]
        for date,v in sorted(sub_queue):
            paid=min(v,remaining) if date<=t else 0; remaining-=paid
            if v-paid>eps: nq.append((date,v-paid))
        sub_queue=nq
        # Funding precedes shareholder payouts. Parent may legally fund subsidiaries;
        # no arbitrary subsidiary sweep or loan-offset right is assumed.
        support=max(0,sfloor-sub); parent-=support; sub+=support
        draw=max(0,pfloor-parent)/(1-p['borrowing_rate']/2)
        if debt+draw>p['borrowing_limit']+eps:
            return {'feasible':False,'failure':{'year':t,'reason':'external funding cap','required_new_debt':draw,'existing_debt':debt,'limit':p['borrowing_limit']},'records':records}
        draw_interest=draw*p['borrowing_rate']/2
        parent+=draw-draw_interest; debt+=draw; interest+=draw_interest
        repay=min(debt,max(0,parent-pfloor)); parent-=repay; debt-=repay
        # Cost-method sub dividend declaration is parent legal profit; equity-method
        # JV earnings, not JV cash collection, are parent legal profit.
        parent_profit=r['core_common_nopat']*frac+pint+fincome-interest+sdecl+r['joint_profit']-loss
        common_profit=r['core_common_nopat']+pint+sint+fincome-interest+r['joint_profit']-loss
        plegal+=parent_profit
        target=max(0,parent-pfloor) if release else max(0,common_profit*p['common_payout'])
        payout=min(target,max(0,plegal),max(0,parent-pfloor)); parent-=payout; plegal-=payout
        # Individual and consolidated cash conservation, external creditor movements.
        expected=pc0+sc0+r['core_cash_before_buffer']+pint+sint+fincome+sale-interest-retire-shock+recovery+jcash+draw-repay-payout
        if abs(parent+sub-expected)>eps: raise ArithmeticError('cash conservation')
        if abs(plegal-(plegal0+parent_profit-payout))>eps or abs(slegal-(slegal0+sub_profit-sdecl))>eps: raise ArithmeticError('legal profit conservation')
        if parent<pfloor-eps or sub<sfloor-eps or payout<0 or debt< -eps: raise ArithmeticError('funding floor')
        if plegal< -eps or slegal< -eps:
            # Negative legal reserves are possible from losses; block payouts, do not
            # manufacture profit. This branch only rejects paying against deficits.
            if (plegal< -eps and payout>eps) or (slegal< -eps and sdecl>eps): raise ArithmeticError('illegal dividend')
        rec={**r,'parent_cash_open':pc0,'sub_cash_open':sc0,'parent_cash':parent,'sub_cash':sub,'own_cash':parent+sub,
            'parent_cash_floor':pfloor,'sub_cash_floor':sfloor,'common_profit':common_profit,'parent_legal_profit':parent_profit,
            'parent_legal_reserve':plegal,'sub_legal_reserve':slegal,'sub_declared':sdecl,'sub_paid':scash,'sub_dividend_receivable':sum(v for _,v in sub_queue),
            'joint_declared':jdecl,'joint_paid':jcash,'joint_dividend_receivable':sum(v for _,v in joint_queue),'joint_extra_retained_cash':jsurplus,
            'cash_interest':pint+sint,'financial_income':fincome,'financial_asset':asset,'financial_principal_released':sale,
            'interest_cost':interest,'new_borrowing':draw,'debt_repaid':repay,'debt_end':debt,'retirement_paid':retire,
            'internal_net_cash_payment':internal,'parent_capital_support_to_sub':support,'internal_receivable_disclosed_balance_not_nettable':p['internal_receivable0'],
            'frozen_principal_removed':shock,'credit_loss':loss,'frozen_recovery':recovery,'frozen_asset_end':blocked,
            'ordinary_or_special_common_cash':payout,'distribution_per_share':payout/p['shares']}
        records.append(rec)
    # No unresolved debt/frozen asset/financial principal is silently erased at terminal.
    n=horizon; last=records[n-1]; nxt=records[n]; nxt2=records[n+1]
    unsettled=last['debt_end']+last['frozen_asset_end']+(last['financial_asset'] if p.get('release_policy',True) else 0)
    if unsettled>1e-6: return {'feasible':False,'failure':{'reason':'unsettled terminal financing/assets','amount':unsettled},'records':records}
    permanent_terms=None
    if p.get('release_policy',True):
        if not math.isclose(nxt2['ordinary_or_special_common_cash'],nxt['ordinary_or_special_common_cash']*(1+e['g']),abs_tol=1e-6,rel_tol=1e-7):
            return {'feasible':False,'failure':{'reason':'nonsteady terminal actual payout','next':nxt['ordinary_or_special_common_cash'],'following':nxt2['ordinary_or_special_common_cash']},'records':records}
        terminal=nxt['ordinary_or_special_common_cash']/(e['ke']-e['g'])
    else:
        # Explicit permanent low-payout governance path. Surplus financial principal
        # is NEVER swept or added at par. Its interest feedback alone funds dividends.
        # C_t=a*C_(t-1)+K1*(1+g)^(t-1)+H; D_t=payout*(B_t+y*C_(t-1)+F).
        # This solves the actual cash-stock recurrence rather than discarding stock.
        if p['sub_delay_years'] or p['joint_extra_delay_years'] or any(r['new_borrowing']>1e-8 or r['parent_capital_support_to_sub']>1e-8 for r in records):
            return {'feasible':False,'failure':{'reason':'permanent-policy analytic branch requires unconstrained normal legal cash path'},'records':records}
        payout=p['common_payout']; y=p['cash_yield_net']; F=last['financial_asset']*p['financial_asset_yield']
        B=nxt['core_common_nopat']+nxt['joint_profit']; K=nxt['core_cash_before_buffer']+nxt['joint_paid']-payout*B
        H=(1-payout)*F; a=1+(1-payout)*y
        if e['ke']<=a-1: raise DomainError('permanent retention discount does not converge')
        S=(last['own_cash']+K/(e['ke']-e['g'])+H/e['ke'])/(1+e['ke']-a)
        terminal=payout*(B/(e['ke']-e['g'])+F/e['ke']+y*S)
        permanent_terms=dict(a=a,B_next=B,K_next=K,H=H,cash_stock_discounted_sum=S,financial_income=F,principal_release=0)

    pv_cash=sum(x['ordinary_or_special_common_cash']/(1+e['ke'])**x['year'] for x in records[:n])
    pv_terminal=terminal/(1+e['ke'])**n
    y5=sum(x['ordinary_or_special_common_cash']/(1+e['ke'])**(x['year']-5) for x in records[5:n])+terminal/(1+e['ke'])**(n-5)
    pv5=sum(x['ordinary_or_special_common_cash']/(1+e['ke'])**x['year'] for x in records[:5])
    if not math.isclose(pv5+y5/(1+e['ke'])**5,pv_cash+pv_terminal,rel_tol=1e-12): raise ArithmeticError('Y5/current bridge')
    return dict(feasible=True,endpoint=e,terminal_year=n,permanent_retention_terms=permanent_terms,current_equity_value=pv_cash+pv_terminal,current_value_per_share=(pv_cash+pv_terminal)/p['shares'],
        year5_equity_value=y5,year5_value_per_share=y5/p['shares'],first_five_distributions_per_share=[x['distribution_per_share'] for x in records[:5]],
        first_five_distribution_pv=pv5,year5_terminal_pv=y5/(1+e['ke'])**5,year5_terminal_fraction=(y5/(1+e['ke'])**5)/(pv_cash+pv_terminal),
        far_terminal_value=terminal,far_terminal_pv=pv_terminal,far_terminal_pv_fraction=pv_terminal/(pv_cash+pv_terminal),records=records)

def auxiliary(p,e,base):
    """Normalized owner-earnings capitalization, NOT main DDM averaged with it.
    Retains Y1 earning power; capital needs from Y1 physical/NWC/cash/JV stock.
    Deduct remaining Caijia construction separately (excluded from maintenance).
    Cash/portfolio income excluded from normalized earnings before principal bridge.
    """
    r=base['records'][0]; norm=r['core_common_nopat']+r['joint_profit']; capital=r['operating_capital']+r['joint_capital']
    roic=norm/capital; multiple=(1-e['g']/roic)/(e['ke']-e['g'])
    franchise=norm*multiple+r['required_cash']*p['cash_yield_net']/(e['ke']-e['g'])
    cash_surplus=p['cash0']-p['minority_cash0']-r['required_cash']
    n=e['release_year']; cash_recovery=cash_surplus*((1+p['cash_yield_net'])/(1+e['ke']))**n
    financial_recovery=sum(p['financial_asset0']*p['financial_asset_yield']/(1+e['ke'])**t for t in range(1,n+1))+p['financial_asset0']/(1+e['ke'])**n
    construction=362.88*(1-.4899)*(1-p['minority_asset_fraction'])
    project_pv=construction*.55/(1+e['ke'])+construction*.45/(1+e['ke'])**2
    # The steady multiple already funds g*NWC; separately fund the larger initial normalization.
    wc_normalization_pv=max(0,r['delta_nwc']-e['g']*r['nwc'])/(1+e['ke'])
    bridge=cash_recovery+financial_recovery+p['joint_receivable0']/(1+e['ke'])-p['debt0']-p['retirement0']-project_pv-wc_normalization_pv
    return dict(normalized_profit=norm,required_capital=capital,roic_proxy=roic,earnings_multiple=multiple,franchise=franchise,
      delayed_cash_principal_and_yield=cash_recovery,portfolio_cash_pv=financial_recovery,remaining_project_pv=project_pv,
      working_capital_normalization_pv=wc_normalization_pv,equity_bridge=bridge,value_per_share=(franchise+bridge)/p['shares'])

def run_all(p):
    core={k:simulate(p,e) for k,e in p['core_endpoints'].items()}
    aux={k:auxiliary(p,e,core[k]) for k,e in p['core_endpoints'].items() if core[k]['feasible']}
    scenarios={}
    for name,patch in p['scenarios'].items():
        q=copy.deepcopy(p);q.update(patch)
        e={'ke':.10,'g':.0175,'release_year':12}
        if name=='structural': e.update(g=.005)
        scenarios[name]=simulate(q,e)
    sensitivities={}
    mid={'ke':.10,'g':.0175,'release_year':12}
    for name,patch,epatch in [
      ('discount_11_percent',{}, {'ke':.11}),('instrument_margin_minus_1pp',{'instrument_margin':[.35]*5},{}),
      ('parent_cash_1800',{'parent_cash0':1800},{}),('sub_initial_legal_reserve_zero',{'sub_legal0':0},{}),
      ('minority_cash_69_189',{'minority_cash0':69.189},{}),('minority_cash_zero',{'minority_cash0':0},{}),
      ('cash_buffer_20pct',{'cash_buffer_ratio':.20},{}),('nwc_15pct',{'nwc_ratio':[.15]*5},{}),
      ('no_core_growth',{'growth_first_five':[0,0,0]},{}),('later_release_15',{}, {'release_year':15})]:
        q=copy.deepcopy(p);q.update(patch);e={**mid,**epatch}; sensitivities[name]=simulate(q,e)
    # Canonical full literal rows are preserved, not only endpoints.
    return {'unit':p['unit'],'information_cutoff':p['information_cutoff'],'shares':p['shares'],'core':core,'auxiliary':aux,'scenarios':scenarios,'diagnostic_sensitivities':sensitivities}

if __name__=='__main__':
    inputs=json.loads('{\n  "unit": "CNY million except rates and per-share CNY; shares in million",\n  "information_cutoff": "2026-10-30T18:10:00Z",\n  "shares": 511.539166,\n  "cash0": 2620.91242928,\n  "parent_cash0": 2050,\n  "minority_cash0": 20,\n  "minority_asset_fraction": 0.014,\n  "parent_legal0": 2835.98285542,\n  "sub_legal0": 300,\n  "debt0": 33.02453558,\n  "retirement0": 18.045,\n  "nwc0_full": 812.79639317,\n  "ppe0_full": 1135.30811064,\n  "joint_capital0": 326.82771557,\n  "joint_receivable0": 20.43036743,\n  "financial_asset0": 211.805089422,\n  "financial_asset_yield": 0.025,\n  "cash_yield_net": 0.008,\n  "borrowing_rate": 0.05,\n  "borrowing_limit": 500,\n  "parent_operating_fraction": 0.65,\n  "parent_buffer_fraction": 0.75,\n  "internal_receivable0": 737.40114573,\n  "initial_revenue": [\n    5850,\n    1450,\n    60\n  ],\n  "growth_first_five": [\n    0.04,\n    0.06,\n    0.0\n  ],\n  "instrument_margin": [\n    0.36,\n    0.36,\n    0.36,\n    0.36,\n    0.36\n  ],\n  "material_margin": [\n    0.205,\n    0.205,\n    0.205,\n    0.205,\n    0.205\n  ],\n  "other_margin": 0.5,\n  "sales_ratio": [\n    0.126,\n    0.125,\n    0.124,\n    0.123,\n    0.122\n  ],\n  "admin_ratio": [\n    0.0525,\n    0.052,\n    0.0515,\n    0.0505,\n    0.05\n  ],\n  "research_ratio": 0.069,\n  "other_operating_cost_ratio": 0.0135,\n  "tax_rate": 0.12,\n  "minority_profit_y1": 9,\n  "nwc_ratio": [\n    0.12,\n    0.12,\n    0.12,\n    0.12,\n    0.12\n  ],\n  "cash_buffer_ratio": 0.16,\n  "maintenance_capex": [\n    110,\n    112,\n    114,\n    116,\n    118\n  ],\n  "growth_capex": [\n    120,\n    98,\n    66,\n    64,\n    72\n  ],\n  "depreciation": [\n    120,\n    125,\n    130,\n    135,\n    140\n  ],\n  "joint_profit_y1": 80,\n  "joint_growth_first_five": 0.03,\n  "joint_payout": 0.6,\n  "joint_cash_same_year": 0.6,\n  "joint_extra_delay_years": 0,\n  "sub_payout": 0.7,\n  "sub_delay_years": 0,\n  "common_payout": 0.4,\n  "internal_net_payment_y1": 0,\n  "freeze_amount": 0,\n  "freeze_loss_fraction": 0,\n  "freeze_release_year": 3,\n  "revenue_multipliers": [\n    [\n      1,\n      1,\n      1\n    ],\n    [\n      1,\n      1,\n      1\n    ],\n    [\n      1,\n      1,\n      1\n    ],\n    [\n      1,\n      1,\n      1\n    ],\n    [\n      1,\n      1,\n      1\n    ]\n  ],\n  "core_endpoints": {\n    "low": {\n      "ke": 0.105,\n      "g": 0.015,\n      "release_year": 15\n    },\n    "high": {\n      "ke": 0.095,\n      "g": 0.02,\n      "release_year": 10\n    }\n  },\n  "scenarios": {\n    "cyclical": {\n      "revenue_multipliers": [\n        [\n          0.92,\n          0.96,\n          1\n        ],\n        [\n          0.93,\n          0.98,\n          1\n        ],\n        [\n          0.98,\n          1,\n          1\n        ],\n        [\n          1,\n          1,\n          1\n        ],\n        [\n          1,\n          1,\n          1\n        ]\n      ],\n      "instrument_margin": [\n        0.35,\n        0.35,\n        0.355,\n        0.36,\n        0.36\n      ],\n      "nwc_ratio": [\n        0.15,\n        0.15,\n        0.135,\n        0.12,\n        0.12\n      ],\n      "growth_capex": [\n        110,\n        95,\n        66,\n        64,\n        72\n      ]\n    },\n    "structural": {\n      "growth_first_five": [\n        0,\n        0.03,\n        0\n      ],\n      "instrument_margin": [\n        0.34,\n        0.33,\n        0.32,\n        0.32,\n        0.32\n      ],\n      "material_margin": [\n        0.19,\n        0.19,\n        0.19,\n        0.19,\n        0.19\n      ],\n      "sales_ratio": [\n        0.126,\n        0.126,\n        0.126,\n        0.126,\n        0.126\n      ],\n      "admin_ratio": [\n        0.0525,\n        0.0525,\n        0.0525,\n        0.0525,\n        0.0525\n      ],\n      "nwc_ratio": [\n        0.17,\n        0.17,\n        0.17,\n        0.17,\n        0.17\n      ],\n      "growth_capex": [\n        100,\n        85,\n        25,\n        25,\n        25\n      ],\n      "joint_profit_y1": 40,\n      "joint_growth_first_five": 0\n    },\n    "upside": {\n      "growth_first_five": [\n        0.06,\n        0.08,\n        0\n      ],\n      "instrument_margin": [\n        0.365,\n        0.37,\n        0.37,\n        0.37,\n        0.37\n      ],\n      "growth_capex": [\n        200,\n        198,\n        166,\n        144,\n        112\n      ],\n      "joint_profit_y1": 85\n    },\n    "finance_company_freeze": {\n      "freeze_amount": 1673.90585876,\n      "freeze_loss_fraction": 0.25,\n      "freeze_release_year": 3\n    },\n    "parent_upstream_delay": {\n      "parent_cash0": 1800,\n      "sub_delay_years": 2,\n      "joint_extra_delay_years": 1,\n      "internal_net_payment_y1": 200\n    },\n    "permanent_40pct_retention": {\n      "release_policy": false\n    }\n  },\n  "provenance": {\n    "factual_opening": "Q3 consolidated CCE/debt/equity/JV/financial assets; H1 latest parent legal retained profit and intra-group receivables. Restricted 117.612573m already belongs in NWC, not spendable CCE. financial_asset0 is Q3 trading+other noncurrent financial assets 249.18303151m times 85%; other-equity 1.266m excluded as immaterial (no dividend assigned).",\n    "nwc0_formula": "Q3 current assets 8004.38988508 - money2738.52500202 - tradefin1.43290031 - JVdivAR20.43036743 -(current liabilities4570.20186383-shortdebt14.21572202-currentdebt7.16834692)+restricted117.61257274 =812.79639317. All operating accruals/contract advances/bills remain; no assumption of legal internal netting.",\n    "ppe0_formula": "Investment property+PPE+CIP+ROU+intangibles+long prepaid+other noncurrent operating assets =1135.30811064; DTA and noncurrent investments excluded.",\n    "minority": "Profit 9m annualizes Q3 6.742m; 1.4% operating-asset fraction approximates 69.189m minority equity /5092.187m group equity. Minority opening cash20m estimated; sensitivity0..69.189m. No full minority equity deducted again.",\n    "parent_estimates": "Q3 parent statement unavailable. Parent cash2050m (range1800..2250), direct share65%, cash floor75%, sub legal reserves300m are forecasts, not Q3 facts. H1 parent CCE1871m/group2419.6m; FY2025 ratio85.5%. Sub reserves lower than major subsidiaries\' combined net equity; zero-reserve sensitivity included.",\n    "release": "Before release-year common payout40%, sub70%, JV60%; release-year10/15 assumes gradual maturing capital discipline, securities monetization and lawful return of extra cash. Not a commitment. Cash/financial income stops or shrinks after principal payment. Operating growth fades years6..10 to terminal1.5..2%, then required NWC/cash/PPE/JV capital grow at g. No perpetual reversion to historical peak.",\n    "cost_of_equity": "10y ChinaBond official2026-10-30 1.65%; Damodaran Jan5,2026 China ERP5.14%. Analyst adds2.7..3.7pp for business cashflow/Chinese industrial-equity estimation uncertainty to rounded9.5..10.5%, not a stock-price-derived beta or personal hurdle. Explicit finance-company loss is separate conditional stress, not base haircut on deposit principal."\n  },\n  "release_policy": true\n}\n')
    print(json.dumps(run_all(inputs),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))

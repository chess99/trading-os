#!/usr/bin/env python3
"""Moutai Q3 research v2: conditional 4-commercial-entity + finance cash/rights model.
CNY billion / original shares billion / annual saleable wine capacity thousand tonnes.
This is a budget, not reconstructed undisclosed legal-entity financial statements.
Standard library only. No inherited market price or securities quote input.
"""
import copy,json,sys
CUTOFF='2026-10-30T11:00:00Z'
A={'shares': 1.250081601, 'cash': 49.92681376981, 'interbank': 156.05645575074, 'loans': 0.40926645687, 'time_deposits': 1.0, 'bonds': 3.51231673436, 'external_deposits': 17.27230794465, 'inventory': 61.39082096446, 'ar': 1.03532367128, 'ap': 3.0274341941, 'advance': 2.08448574475, 'other_operating_liabilities': 15.16246218487, 'lease': 0.26211768401, 'net_tax_asset': 6.67676951661, 'fund_fv': 4.01628133611, 'fund_tax_basis': 3.79028618149, 'fund_uncalled': 6.0, 'associate': 0.14641586357, 'capital': 33.82251311204, 'other_current_assets': 0.23744759938, 'group_net_assets': 280.42161702285, 'nci': 9.21687648122, 'parent_h1_re': 107.64656535582, 'parent_reserve': 49.25142960871, 'old_trade_claim': 9.84629367836, 'old_trade_by_debtor': [6.93393334, 1.87622273814, 1.03613760022], 'prior_ytd_revenue': 128.45370765586, 'ltm_revenue': 171.35513850797, 'h1_internal_profit': 22.33779550547, 'h1_internal_profit_dta': 5.58444887637, 'h1_parent_other_net_dta': 0.60763517208, 'parent_subsidiary_investment_cost': 1.81053558755, 'parent_capital_surplus': 0.00091576218, 'parent_equity_q3_consolidated': 271.20474054163, 'h1_total_nci': 10.84275775486, 'h1_sales_nci': 4.42256335417}
B={'method': 'volume_price_capital', 'main_volume': 51.0, 'series_volume': 42.0, 'main_price': 3.02, 'series_price': 0.59, 'volume_growth': [0.03, 0.025, 0.02, 0.015, 0.01], 'price_growth': [0.0, 0.01, 0.015, 0.015, 0.015], 'mature_volume_growth': 0.01, 'mature_price_growth': 0.015, 'unit_inflation': 0.015, 'main_production_cost': 0.17, 'series_production_cost': 0.075, 'main_finish_cost': 0.02, 'series_finish_cost': 0.06, 'production_yield': 1.0, 'main_capacity': 58.47316, 'series_capacity': 57.65057, 'capacity_growth': 0.012, 'mature_capacity_growth': 0.01, 'main_supply_lag': 5, 'series_supply_lag': 3, 'opening_main_release': [52.0, 53.0, 54.0, 55.0, 56.0], 'opening_series_release': [43.0, 44.0, 45.0], 'inventory_years_main': 5.0, 'inventory_years_series': 3.0, 'inventory_buffer': 1.0, 'project_capex': [5.0, 5.0, 5.0, 5.0, 4.41349], 'opex_ratio': 0.064, 'royalty': 0.015, 'excise_and_other_tax': 0.1586, 'corp_tax': 0.25, 'depreciation': 0.071, 'maintenance_factor': 1.0, 'receivable_days': 2.0, 'payable_days': 60.0, 'advance_ratio': 0.012, 'main_parent_profit_share': 0.4, 'sales_profit_share': 0.55, 'sub_payout': 0.9, 'parent_payout': 0.8, 'parent_cash_floor': 8.0, 'sales_cash_floor': 2.0, 'other_cash_floor': 1.0, 'parent_cash': 110.0, 'sales_cash': 52.0, 'parent_cash_shift': 0.0, 'parent_re_shift': 0.0, 'sales_re': 52.762529624399995, 'finance_equity': 12.2, 'finance_capital_floor': 0.0, 'finance_rwa_ratio': 0.36, 'finance_general_reserve_ratio': 0.015, 'finance_payout': 0.7, 'finance_yield': 0.018, 'finance_tax': 0.4, 'internal_deposit_rate': 0.008, 'bank_yield': 0.008, 'external_deposit_rate': 0.01, 'finance_admin': 0.12, 'credit_cost': 0.0002, 'external_deposit_growth': 0.0, 'initial_internal_deposits': [80.0, 50.0, 10.0, 0.5], 'deposit_sweep': [0.65, 0.85, 0.5, 0.5], 'finance_freeze_years': 0, 'freeze_fraction': 0.0, 'finance_haircut': 0.0, 'fund_growth': 0.05, 'fund_exit': 7, 'fund_recovery': 1.0, 'fund_calls': [3.0, 3.0], 'old_trade_collection_years': 2, 'upstream_delay': 0, 'k': 0.085, 'aux_ebitda': 110.0, 'aux_revenue': 171.35513850797, 'aux_growth': 0.01, 'demand_loss': 0.0, 'loss_years': 0, 'extra_fixed_cost': 0.0, 'inventory_impairment': 0.0, 'other_nci_cash': 0.15, 'export_cash': 2.53613760022, 'export_equity': 1.5, 'export_profit_share': 0.0015, 'other_nci_ebit_share': 0.0004, 'export_cash_floor': 0.1, 'parent_continue_10pct_reserve': True, 'release_surplus': True, 'release_fraction': 0.1, 'release_start': 2, 'finance_capital_margin': 1.2, 'finance_derisk_cost': 0.005, 'finance_derisk_max_fraction': 0.5, 'finance_safe_yield': 0.006, 'finance_admin_mode': 'assets', 'finance_liquid_fraction': 0.4, 'supply_carry_fraction': 0.0, 'capital_return_start': 0, 'capital_return_interval': 5, 'capital_return_fraction': 0.5, 'finance_close_year': 0, 'finance_close_cost_rate': 0.002, 'finance_parent_cost': 1.275, 'parent_use_h1_re_floor': False, 'internal_profit_opening': 22.33779550547, 'markup_allocation': [0.85, 0.14, 0.01], 'internal_profit_release_years': 3.0, 'parent_other_dta_cap': 0.60763517208, 'parent_payout_basis': 'consolidated_attributable_profit', 'finance_safe_destination': 'conditional withdrawable central-bank settlement balances; zero RWA budget, not government-bond investment quota', 'finance_asset_liquidation_assumption': 'annual pro-rata redeemability subject to specified freeze and conversion costs; not disclosed maturity ladder'}

def allocate(re,profit,res,cap,continue_ten=False):
    taxable_profit=max(0.,profit+min(0.,re))
    added=.1*taxable_profit if continue_ten else min(max(0.,cap*.5-res),.1*taxable_profit)
    return re+profit-added,res+added,added

def run(overrides=None,years=240):
    p=copy.deepcopy(B);p.update(overrides or {});a=A
    gross=sum(a[k] for k in ['cash','interbank','loans','time_deposits','bonds'])
    available=gross-a['external_deposits']-p['finance_equity']-p['other_nci_cash']
    cash=[p['parent_cash']+p['parent_cash_shift'],p['sales_cash']-p['parent_cash_shift'],available-p['parent_cash']-p['sales_cash']-p['export_cash'],p['export_cash']]
    capitals=[a['shares'],.01,.2,.008];reserves=[a['parent_reserve'],.005,.1,.004]
    sales_equity=(a['nci']-.49*p['finance_equity']-.30*p['export_equity']-p['other_nci_cash'])/.05
    other_equity=20.3
    subsidiary_common_equity=.95*sales_equity+other_equity+.70*p['export_equity']+.51*p['finance_equity']
    internal_dta=p['internal_profit_opening']*.25
    parent_equity=a['parent_equity_q3_consolidated']-subsidiary_common_equity+a['parent_subsidiary_investment_cost']+p['internal_profit_opening']-internal_dta
    parent_re_budget=(a['parent_h1_re'] if p['parent_use_h1_re_floor'] else parent_equity-a['shares']-a['parent_reserve']-a['parent_capital_surplus'])+p['parent_re_shift']
    if p.get('parent_re_override') is not None:parent_re_budget=p['parent_re_override']
    assert 0<=internal_dta<=a['net_tax_asset'], 'opening deferred tax budget must fit actual net DTA'
    equities=[parent_equity,sales_equity,other_equity,p['export_equity']]
    q=[]
    for i in range(4):
        dep=min(p['initial_internal_deposits'][i],max(0,cash[i]*.8)) if p['initial_internal_deposits'][i]>cash[i] else p['initial_internal_deposits'][i]
        q.append({'bank':cash[i]-dep,'deposit':dep,'re':[parent_re_budget,p['sales_re'],20.,p['export_equity']-.012][i],'reserve':reserves[i],'capital':capitals[i],'unpaid':0.})
        q[i]['other_equity']=equities[i]-q[i]['capital']-q[i]['reserve']-q[i]['re']
        q[i]['noncash_net_assets']=equities[i]-cash[i]+(a['old_trade_by_debtor'][i-1] if i else -sum(a['old_trade_by_debtor'])-a['parent_subsidiary_investment_cost'])
    f={'equity':p['finance_equity'],'capital':2.5,'deposits_external':a['external_deposits'],'reserve':1.25,'general_risk_reserve':1.061529724,'re':p['finance_equity']-2.5-1.25-1.061529724,'assets':sum(x['deposit'] for x in q)+a['external_deposits']+p['finance_equity'],'safe_fraction':0.,'closed':False,'unpaid_external_deposits':0.}
    state={'capital':a['capital'],'inventory':a['inventory'],'ar':a['ar'],'ap':a['ap'],'advance':a['advance'],'lease':a['lease'],'taxasset':a['net_tax_asset'],'other_liabilities':a['other_operating_liabilities'],'fund_value':a['fund_fv'],'fund_book':a['fund_fv'],'fund_tax_basis':p.get('fund_tax_basis_override',a['fund_tax_basis']),'old_trade_by_debtor':list(a['old_trade_by_debtor']),'other_current_assets':a['other_current_assets'],'associate':a['associate'],'finance_parent_investment_cost':p['finance_parent_cost'],'supply_carry':[0.,0.],'internal_profit_elimination':p['internal_profit_opening'],'internal_profit_dta':internal_dta,'parent_other_dta':min(p['parent_other_dta_cap'],a['net_tax_asset']-internal_dta),'unallocated_other_dta':a['net_tax_asset']-internal_dta-min(p['parent_other_dta_cap'],a['net_tax_asset']-internal_dta),'parent_subsidiary_investment_cost':a['parent_subsidiary_investment_cost']}
    volume=[p['main_volume'],p['series_volume']];prices=[p['main_price'],p['series_price']];capacity=[p['main_capacity'],p['series_capacity']];release=[list(p['opening_main_release']),list(p['opening_series_release'])]
    initial_finance_assets=f['assets']
    rows=[];pv=0.;feasible=True;failure=None
    def snapshot():
        nci=.05*(q[1]['capital']+q[1]['reserve']+q[1]['re']+q[1]['other_equity'])+.30*(q[3]['capital']+q[3]['reserve']+q[3]['re']+q[3]['other_equity'])+.49*f['equity']+p['other_nci_cash']
        return dict(copy.deepcopy(state),commercial=copy.deepcopy(q),finance=copy.deepcopy(f),nci_equity=nci)
    initial=snapshot()
    def liquid(i,t):
        freeze=p['freeze_fraction'] if t<=p['finance_freeze_years'] and not f['closed'] else 0.
        return q[i]['bank']+q[i]['deposit']*(1-freeze) if f['equity']>=0 else q[i]['bank']
    def pay(i,requested,t):
        paid=min(max(0.,requested),liquid(i,t));bank=min(q[i]['bank'],paid);q[i]['bank']-=bank;q[i]['deposit']-=paid-bank
        return paid,max(0.,requested-paid)
    for t in range(1,years+1):
        opening=snapshot()
        if not feasible:
            rows.append({'year':t,'status':'unresolved_claims_retained','opening':opening,'closing':copy.deepcopy(opening),'dps':0.,'discounted':0.,'cumulative_realized_pv':pv,'failure':failure});continue
        if t>1:
            vg=p['volume_growth'][t-2] if t<=6 else p['mature_volume_growth'];pg=p['price_growth'][t-2] if t<=6 else p['mature_price_growth']
            volume=[v*(1+vg) for v in volume];prices=[v*(1+pg) for v in prices];capacity=[v*(1+(p['capacity_growth'] if t<=5 else p['mature_capacity_growth'])) for v in capacity]
        inflation=(1+p['unit_inflation'])**(t-1);impair=opening['inventory']*p['inventory_impairment'] if t==1 else 0.;surviving=opening['inventory']-impair
        depreciation=state['capital']*p['depreciation']*p['maintenance_factor'];project=p['project_capex'][t-1] if t<=len(p['project_capex']) else 0.
        growth=(1+(0. if project>0 else (p['capacity_growth'] if t<=5 else p['mature_capacity_growth'])))*(1+p['unit_inflation'])-1
        capex=depreciation+state['capital']*growth+project+(.4 if t==1 else 0.)
        if p['method']=='volume_price_capital':
            fresh=[release[j].pop(0)*p['production_yield']*(1-p['inventory_impairment'] if t<=p['main_supply_lag'] else 1.) for j in range(2)]
            offer=[fresh[j]+state['supply_carry'][j] for j in range(2)]
            demand=[v*(1-p['demand_loss'] if t<=p['loss_years'] else 1.) for v in volume];sold=[min(demand[j],offer[j]) for j in range(2)]
            carry=[min(max(0,offer[j]-sold[j]),volume[j]*p['supply_carry_fraction']) for j in range(2)]
            for j in range(2):release[j].append(capacity[j])
            revenue=sum(sold[j]*prices[j] for j in range(2));cogs=[sold[j]*(p['main_production_cost'] if j==0 else p['series_production_cost'])*inflation for j in range(2)]
            finish=(sold[0]*p['main_finish_cost']+sold[1]*p['series_finish_cost'])*inflation
            budget=[min(capacity[j],demand[j]*(1+p['mature_volume_growth'])**(p['main_supply_lag'] if j==0 else p['series_supply_lag'])) for j in range(2)]
            fixed=a['inventory']-51.*.17*5-42.*.075*3
            required=(budget[0]*p['main_production_cost']*p['inventory_years_main']+budget[1]*p['series_production_cost']*p['inventory_years_series']+fixed*(1+p['mature_volume_growth'])**(t-1)+carry[0]*p['main_production_cost']+carry[1]*p['series_production_cost'])*inflation*p['inventory_buffer']
            inventory=max(required,surviving-sum(cogs));production_cash=sum(cogs)+inventory-surviving
            ebitda=revenue*(1-p['opex_ratio']-p['royalty']-p['excise_and_other_tax'])-sum(cogs)-finish-p['extra_fixed_cost']*inflation
            newap=(production_cash+finish)*p['payable_days']/365
        else:
            scale=(1+p['aux_growth'])**(t-1);revenue=p['aux_revenue']*scale;ebitda=p['aux_ebitda']*scale-p['extra_fixed_cost']*inflation
            inventory=a['inventory']*scale*p['inventory_buffer'];capex=depreciation+state['capital']*p['aux_growth']+project+(.4 if t==1 else 0.);newap=revenue*.1*p['payable_days']/365
            fresh=offer=demand=sold=budget=cogs=carry=None;finish=production_cash=None;required=inventory
        desired_revenue=sum(demand[j]*prices[j] for j in range(2)) if demand is not None else revenue
        target_internal_profit=p['internal_profit_opening']*desired_revenue/a['ltm_revenue']
        max_realized_margin=p['internal_profit_opening']/p['internal_profit_release_years']*min(1.,revenue/a['ltm_revenue'])
        new_internal_profit=max(target_internal_profit,state['internal_profit_elimination']-max_realized_margin)
        delta_internal_profit=new_internal_profit-state['internal_profit_elimination']
        ebit=ebitda-depreciation;ar=revenue*p['receivable_days']/365;advance=revenue*p['advance_ratio']
        dwc=inventory-surviving+ar-state['ar']-(newap-state['ap'])-(advance-state['advance'])
        oldpaid=min(state['other_liabilities'],a['other_operating_liabilities']/3);leasepaid=min(state['lease'],a['lease']/3)
        state['other_liabilities']-=oldpaid;state['lease']-=leasepaid
        intdep=[x['deposit']*p['internal_deposit_rate'] if not f['closed'] else 0. for x in q];intbank=[x['bank']*p['bank_yield'] for x in q]
        finance_dividend=finance_capital_return=finance_liquidation_income=0.;derisk=derisk_cost=0.;fadd=riskadd=0.;external_change=0.;reg_required=target_required=0.
        fprofit=fgross=fpbt=ftax=fexpense=fcredit=0.;liquidity_ratio=1.
        if not f['closed']:
            fgross=f['assets']*((1-f['safe_fraction'])*p['finance_yield']+f['safe_fraction']*p['finance_safe_yield'])
            fexpense=f['deposits_external']*p['external_deposit_rate']+p['finance_admin']*(inflation if p['finance_admin_mode']=='fixed_inflation' else f['assets']/initial_finance_assets)
            fcredit=f['assets']*(p['credit_cost']*(1-f['safe_fraction'])+(p['finance_haircut'] if t==1 else 0.))
            fpbt=fgross-sum(intdep)-fexpense-fcredit;ftax=max(0,fpbt)*p['finance_tax'];fprofit=fpbt-ftax
            f['equity']+=fprofit
            provisional_assets=f['assets']+fprofit+sum(intdep)
            external_change=f['deposits_external']*p['external_deposit_growth'] if f['equity']>=0 else 0.;f['deposits_external']+=external_change;provisional_assets+=external_change
            safe_assets=max(0.,provisional_assets*f['safe_fraction']);risky=max(0.,provisional_assets-safe_assets)
            reg_required=.105*p['finance_rwa_ratio']*risky
            deposit_liabilities=provisional_assets-f['equity']
            liquidity_shortfall=.25*deposit_liabilities-(safe_assets+p['finance_liquid_fraction']*risky)
            if f['equity']>=0 and (f['equity']+1e-9<reg_required or liquidity_shortfall>1e-9):
                denominator=.105*p['finance_rwa_ratio']-p['finance_derisk_cost']
                capital_request=max(0.,reg_required-f['equity'])/denominator if denominator>0 else float('inf')
                liquidity_request=max(0.,liquidity_shortfall)/(1-p['finance_derisk_cost']-p['finance_liquid_fraction']) if 1-p['finance_derisk_cost']>p['finance_liquid_fraction'] else float('inf')
                request=max(capital_request,liquidity_request)
                derisk=min(risky*p['finance_derisk_max_fraction'],request)
                derisk_cost=derisk*p['finance_derisk_cost'];provisional_assets-=derisk_cost;f['equity']-=derisk_cost;fprofit-=derisk_cost;safe_assets+=derisk*(1-p['finance_derisk_cost']);risky-=derisk
            f['safe_fraction']=safe_assets/provisional_assets if provisional_assets>0 else 0.;reg_required=.105*p['finance_rwa_ratio']*max(0.,risky)
            liquidity_ratio=(safe_assets+p['finance_liquid_fraction']*risky)/deposit_liabilities if deposit_liabilities>0 else 1.
            if f['equity']<0 or f['equity']+1e-8<reg_required or liquidity_ratio<.25-1e-10:
                feasible=False;failure={'year':t,'entity':'finance','reason':'regulatory_capital_remediation_unresolved' if f['equity']>=0 else 'negative_equity_recovery_unresolved','equity':f['equity'],'required_regulatory_capital':reg_required,'claims_not_discharged':True,'not_automatic_bankruptcy':True}
            f['re'],f['reserve'],fadd=allocate(f['re'],fprofit,f['reserve'],f['capital'])
            riskadd=min(max(0,f['re']),max(0,provisional_assets*p['finance_general_reserve_ratio']-f['general_risk_reserve']));f['general_risk_reserve']+=riskadd;f['re']-=riskadd
            qtarget=.105*p['finance_rwa_ratio']*(1-f['safe_fraction'])*p['finance_capital_margin']
            target_required=max(p['finance_capital_floor'],qtarget*provisional_assets)
            liquid_coeff=f['safe_fraction']+(1-f['safe_fraction'])*p['finance_liquid_fraction']
            max_by_liquidity=max(0.,provisional_assets-.25*(provisional_assets-f['equity'])/liquid_coeff) if liquid_coeff>0 else 0.
            max_by_target=min(max(0,f['equity']-p['finance_capital_floor']),max(0,(f['equity']-qtarget*provisional_assets)/(1-qtarget)),max_by_liquidity)
            earnings_target=max(0,fprofit)*p['finance_payout']
            if p['release_surplus'] and t>=p['release_start']:earnings_target+=max(0,min(f['re'],max_by_target)-earnings_target)*p['release_fraction']
            finance_dividend=min(max(0,f['re']),max_by_target,earnings_target) if feasible and t>p['finance_freeze_years'] else 0.
            f['re']-=finance_dividend;f['equity']-=finance_dividend
        call=p['fund_calls'][t-1] if t<=len(p['fund_calls']) else 0.;state['fund_value']=state['fund_value']*(1+p['fund_growth'])+call;state['fund_book']+=call;state['fund_tax_basis']+=call
        fund_receipt=fund_gain=fund_tax=0.
        if t==p['fund_exit']:
            sale=state['fund_value']*p['fund_recovery'];fund_tax=max(0,sale-state['fund_tax_basis'])*.25;fund_receipt=sale-fund_tax;fund_gain=sale-state['fund_book']-fund_tax
            state['fund_value']=state['fund_book']=state['fund_tax_basis']=0.
        assoc=state['associate'] if t==5 else 0.;state['associate']-=assoc;other=state['other_current_assets'] if t==2 else 0.;state['other_current_assets']-=other
        ratios=[p['main_parent_profit_share'],p['sales_profit_share'],1-p['main_parent_profit_share']-p['sales_profit_share']-p['export_profit_share'],p['export_profit_share']]
        profits=[];cashflows=[];taxes=[];resadds=[];taxcredits=[];delta_internal_dta=0.
        for i in range(4):
            pre=ebit*ratios[i]+intdep[i]+intbank[i]-(a['lease']*.025 if i==0 and t<=3 else 0.)
            if i==0:pre+=delta_internal_profit
            tax=max(0,pre)*p['corp_tax'];profit=pre-tax;credit=min(state['parent_other_dta'],max(0,tax)*.5,p['parent_other_dta_cap']/10) if i==0 else 0.;state['parent_other_dta']-=credit
            if i==0:
                desired_dta=new_internal_profit*.25
                delta_internal_dta=min(max(0.,desired_dta-state['internal_profit_dta']),tax) if desired_dta>=state['internal_profit_dta'] else desired_dta-state['internal_profit_dta']
                state['internal_profit_dta']+=delta_internal_dta
                state['taxasset']=state['internal_profit_dta']+state['parent_other_dta']+state['unallocated_other_dta']
            flow=profit+credit-intdep[i];q[i]['deposit']+=intdep[i]
            if i==0:flow+=depreciation-dwc-capex-oldpaid-leasepaid-call+fund_receipt+assoc+other;profit+=fund_gain-impair
            else:
                markup=delta_internal_profit*p['markup_allocation'][i-1];flow-=markup;q[i]['noncash_net_assets']+=markup
            other_minor=max(0,ebit)*p['other_nci_ebit_share'] if i==2 else 0.;flow-=other_minor;profit-=other_minor
            if flow>=0:q[i]['bank']+=flow
            else:
                _,unpaid=pay(i,-flow,t);q[i]['unpaid']+=unpaid
                if unpaid>1e-8 and feasible:feasible=False;failure={'year':t,'entity':i,'reason':'mandatory_cash_obligations_not_funded','unpaid':unpaid,'claims_not_discharged':True}
            if i==0:q[i]['re']+=profit;added=0.
            else:q[i]['re'],q[i]['reserve'],added=allocate(q[i]['re'],profit,q[i]['reserve'],q[i]['capital'])
            profits.append(profit);cashflows.append(flow);taxes.append(tax);taxcredits.append(credit);resadds.append(added)
        q[0]['noncash_net_assets']+=profits[0]-cashflows[0]-intdep[0]
        state['internal_profit_elimination']=new_internal_profit
        tradepaid=[]
        for j,i in enumerate([1,2,3]):
            requested=min(state['old_trade_by_debtor'][j],a['old_trade_by_debtor'][j]/p['old_trade_collection_years']) if feasible else 0.
            paid,_=pay(i,requested,t);state['old_trade_by_debtor'][j]-=paid;q[0]['bank']+=paid;tradepaid.append(paid)
        scale=revenue/(p['aux_revenue'] if p['method']=='normalized_earnings' else p['main_volume']*p['main_price']+p['series_volume']*p['series_price'])
        basefloors=[p['parent_cash_floor'],p['sales_cash_floor'],p['other_cash_floor'],p['export_cash_floor']]
        floors=[x*max(1.,scale) for x in basefloors]
        futurecalls=sum(p['fund_calls'][t:]);nextproject=p['project_capex'][t] if t<len(p['project_capex']) else 0.
        floors[0]+=state['other_liabilities']+state['lease']+futurecalls+nextproject
        for j,i in enumerate([1,2,3]):floors[i]+=state['old_trade_by_debtor'][j]
        upcash=upincome=0.;minority=finance_dividend*.49;subdiv=[];subregular=[];subexcess=[]
        for i,ownership in [(1,.95),(2,1.),(3,.70)]:
            capacity_div=min(max(0,q[i]['re']),max(0,liquid(i,t)-floors[i])) if feasible and t>p['upstream_delay'] else 0.
            regular=capacity_div*p['sub_payout'];extra=max(0,capacity_div-regular)*p['release_fraction'] if p['release_surplus'] and t>=p['release_start'] else 0.
            paid,_=pay(i,regular+extra,t);q[i]['re']-=paid;receipt=paid*ownership;q[0]['bank']+=receipt;upcash+=receipt;upincome+=receipt;minority+=paid-receipt;subdiv.append(paid);subregular.append(regular);subexcess.append(extra)
        q[0]['bank']+=finance_dividend*.51;upcash+=finance_dividend*.51;upincome+=finance_dividend*.51
        # Optional separately labelled orderly finance-company exit; never presumed for a failed company.
        finance_close_cost=0.;closed_external_repayment=0.;closed_internal_repayments=[0.]*4
        if not f['closed'] and t==p['finance_close_year'] and feasible and t>p['finance_freeze_years']:
            closing_assets=sum(x['deposit'] for x in q)+f['deposits_external']+f['equity'];finance_close_cost=closing_assets*p['finance_close_cost_rate']
            if f['equity']>=finance_close_cost:
                f['equity']-=finance_close_cost;f['re']-=finance_close_cost;fprofit-=finance_close_cost
                for i in range(4):closed_internal_repayments[i]=q[i]['deposit'];q[i]['bank']+=q[i]['deposit'];q[i]['deposit']=0.
                closed_external_repayment=f['deposits_external'];finance_capital_return=f['equity'];cashreceipt=.51*finance_capital_return
                finance_liquidation_income=cashreceipt-state['finance_parent_investment_cost'];state['parent_subsidiary_investment_cost']-=state['finance_parent_investment_cost'];state['finance_parent_investment_cost']=0.
                q[0]['bank']+=cashreceipt;upcash+=cashreceipt;upincome+=finance_liquidation_income;minority+=.49*finance_capital_return
                f={k:0. for k in f};f['closed']=True;f['safe_fraction']=0.
            else:
                feasible=False;failure={'year':t,'entity':'finance','reason':'orderly_exit_cost_unfunded','claims_not_discharged':True}
        # Parent reserve is computed ONCE from total current own profit + genuine upstream income.
        parent_profit=profits[0]+upincome
        parent_re,parent_res,parent_add=allocate(opening['commercial'][0]['re'],parent_profit,opening['commercial'][0]['reserve'],a['shares'],p['parent_continue_10pct_reserve'])
        q[0]['re']=parent_re;q[0]['reserve']=parent_res;resadds[0]=parent_add
        lawful=min(max(0,q[0]['re']),max(0,liquid(0,t)-floors[0])) if feasible else 0.
        common_profit=sum(profits)+.51*fprofit-.05*profits[1]-.30*profits[3]-delta_internal_profit+delta_internal_dta
        ordinary_basis=common_profit if p['parent_payout_basis']=='consolidated_attributable_profit' else parent_profit-parent_add
        ordinary=min(lawful,max(0,ordinary_basis)*p['parent_payout']);special=max(0,lawful-ordinary)*p['release_fraction'] if p['release_surplus'] and t>=p['release_start'] else 0.
        pdiv,_=pay(0,ordinary+special,t);q[0]['re']-=pdiv
        capital_return=0.;capital_return_creditor_buffer=0.
        if feasible and p['capital_return_start'] and t>=p['capital_return_start'] and (t-p['capital_return_start'])%p['capital_return_interval']==0:
            # Explicit OPTIONAL prior-approved capitalization + proportional reduction. No ordinary dividend from reserve.
            capital_return_creditor_buffer=floors[0]+newap+advance+capex
            room=min(max(0,liquid(0,t)-capital_return_creditor_buffer),max(0,q[0]['reserve']-.25*q[0]['capital'])*p['capital_return_fraction']) if q[0]['re']>=0 else 0.
            capital_return,_=pay(0,room,t);q[0]['reserve']-=capital_return
        sweeps=[]
        for i in range(4):
            candidate=max(0,q[i]['bank']-floors[i])*p['deposit_sweep'][i] if feasible and not f['closed'] and t>p['finance_freeze_years'] else 0.
            coeff=.105*p['finance_rwa_ratio']*(1-f['safe_fraction'])*p['finance_capital_margin']
            current_assets=sum(x['deposit'] for x in q)+f['deposits_external']+f['equity']
            accept=max(0,f['equity']/coeff-current_assets) if coeff>0 else candidate
            liquid_coeff=f['safe_fraction']+(1-f['safe_fraction'])*p['finance_liquid_fraction']
            liquidity_accept=max(0.,(liquid_coeff*current_assets-.25*(current_assets-f['equity']))/(.25-liquid_coeff)) if liquid_coeff<.25 else candidate
            sweep=min(candidate,accept,liquidity_accept);q[i]['bank']-=sweep;q[i]['deposit']+=sweep;sweeps.append(sweep)
        if not f['closed']:
            f['assets']=sum(x['deposit'] for x in q)+f['deposits_external']+f['equity']
            closing_rwa=f['assets']*(1-f['safe_fraction'])*p['finance_rwa_ratio']
            closing_liquidity=(f['safe_fraction']+(1-f['safe_fraction'])*p['finance_liquid_fraction'])*f['assets']/(f['assets']-f['equity']) if f['assets']>f['equity'] else 1.
            if feasible and (f['equity']+1e-8<.105*closing_rwa or closing_liquidity<.25-1e-10):feasible=False;failure={'year':t,'entity':'finance','reason':'closing_regulatory_budget_not_restored','claims_not_discharged':True}
        else:closing_rwa=0.
        state.update({'capital':state['capital']+capex-depreciation,'inventory':inventory,'ar':ar,'ap':newap,'advance':advance,'supply_carry':carry if carry else [0.,0.]})
        dps=(pdiv+capital_return)/a['shares'];discount=dps/(1+p['k'])**t;pv+=discount
        nci_profit=.05*profits[1]+.30*profits[3]+.49*fprofit+max(0,ebit)*p['other_nci_ebit_share']
        nci_paid=minority+max(0,ebit)*p['other_nci_ebit_share']
        entity_equity=[x['capital']+x['reserve']+x['re']+x['other_equity'] for x in q]
        entity_asset_equity=[q[i]['bank']+q[i]['deposit']+q[i]['noncash_net_assets']-q[i]['unpaid']+(sum(state['old_trade_by_debtor'])+state['parent_subsidiary_investment_cost'] if i==0 else -state['old_trade_by_debtor'][i-1]) for i in range(4)]
        group_from_entities=sum(entity_equity)+f['equity']+p['other_nci_cash']-state['parent_subsidiary_investment_cost']-state['internal_profit_elimination']+state['internal_profit_dta']
        group_from_assets=sum(x['bank'] for x in q)+f['assets']-f['deposits_external']+p['other_nci_cash']+state['capital']+state['inventory']+state['ar']-state['ap']-state['advance']-state['lease']+state['taxasset']-state['other_liabilities']+state['fund_book']+state['associate']+state['other_current_assets']-sum(x['unpaid'] for x in q)
        roles=[{'bank_plus_deposit':x['bank']+x['deposit'],'available_now':liquid(i,t),'operating_and_known_obligations_buffer':floors[i],'legal_re':x['re'],'statutory_reserve':x['reserve'],'lawful_but_policy_retained':max(0,min(x['re'],liquid(i,t)-floors[i])),'cash_above_buffer_without_RE':max(0,x['bank']+x['deposit']-floors[i]-max(0,x['re']))} for i,x in enumerate(q)]
        row={'year':t,'status':'ongoing' if feasible else 'unresolved_claims_retained','opening':opening,'operating':{'method':p['method'],'demand':demand,'sold':sold,'unit_revenue':prices if sold else None,'fresh_mature_capacity':fresh,'available_with_carry':offer,'carry':carry,'supply_queue':copy.deepcopy(release) if sold else None,'capacity':capacity if sold else None,'production_budget':budget,'production_cash':production_cash,'inventory_required':required,'inventory_impairment':impair,'revenue':revenue,'vintage_cash_cogs':cogs,'finishing_cash':finish,'ebitda':ebitda,'depreciation':depreciation,'ebit':ebit,'capex':capex,'project_capex':project,'delta_wc':dwc},'finance':{'gross_income':fgross,'pbt_before_derisk':fpbt,'tax':ftax,'expense':fexpense,'credit_loss':fcredit,'profit_after_derisk_and_close':fprofit,'internal_deposit_interest':intdep,'derisk_asset_face':derisk,'derisk_cash_loss':derisk_cost,'regulatory_capital_required_after_repair':reg_required,'target_capital_before_dividend':target_required,'statutory_reserve_add':fadd,'general_reserve_add':riskadd,'external_deposit_change':external_change,'dividend':finance_dividend,'capital_return':finance_capital_return,'liquidation_parent_income':finance_liquidation_income,'close_cost':finance_close_cost,'external_deposits_repaid_on_close':closed_external_repayment,'internal_deposits_repaid_on_close':closed_internal_repayments,'closing_rwa':closing_rwa,'liquidity_ratio_after_repair':liquidity_ratio,'closing_liquidity_ratio':((f['safe_fraction']+(1-f['safe_fraction'])*p['finance_liquid_fraction'])*f['assets']/(f['assets']-f['equity']) if not f['closed'] and f['assets']>f['equity'] else 1.)},'commercial_profit':profits,'commercial_tax':taxes,'commercial_tax_credit':taxcredits,'commercial_cashflow':cashflows,'bank_interest':intbank,'reserve_add':resadds,'common_attributable_profit':common_profit,'internal_profit_change':delta_internal_profit,'internal_dta_change':delta_internal_dta,'internal_markup_inventory_by_entity':[delta_internal_profit*v for v in p['markup_allocation']],'old_liabilities_paid':oldpaid,'lease_paid':leasepaid,'fund_call':call,'fund_return':fund_receipt,'fund_gain':fund_gain,'fund_tax':fund_tax,'associate_receipt':assoc,'other_current_assets_receipt':other,'old_trade_paid_by_debtor':tradepaid,'upstream_cash':upcash,'upstream_income':upincome,'subsidiary_dividends':subdiv,'subsidiary_regular':subregular,'subsidiary_excess':subexcess,'minority_distributions':minority,'other_minor_distributions':max(0,ebit)*p['other_nci_ebit_share'],'parent_regular_dividend':ordinary,'parent_excess_dividend':special,'parent_total_dividend':pdiv,'parent_approved_capital_return':capital_return,'capital_return_creditor_buffer':capital_return_creditor_buffer,'new_internal_deposits':sweeps,'cash_roles':roles,'equity_bridge':{'entity_equity':entity_equity,'entity_net_assets':entity_asset_equity,'consolidated_equity_from_legal_budgets':group_from_entities,'consolidated_equity_from_external_assets':group_from_assets,'nci_profit':nci_profit,'nci_distributions':nci_paid,'nci_opening':opening['nci_equity'],'nci_closing':snapshot()['nci_equity']},'dps':dps,'discounted':discount,'cumulative_realized_pv':pv,'closing':snapshot(),'failure':failure}
        assert all(x['bank']>=-1e-7 and x['deposit']>=-1e-7 for x in q)
        assert all(abs(entity_equity[i]-entity_asset_equity[i])<1e-7*max(1,abs(entity_equity[i])) for i in range(4)),('legal balance',t,entity_equity,entity_asset_equity)
        assert abs(group_from_entities-group_from_assets)<1e-7*max(1,abs(group_from_assets)),('group bridge',t,group_from_entities,group_from_assets)
        assert abs(opening['nci_equity']+nci_profit-nci_paid-snapshot()['nci_equity'])<1e-7*max(1,abs(snapshot()['nci_equity'])),('NCI',t)
        rows.append(row)
    first5=sum(x['discounted'] for x in rows[:5]);terminal=(pv-first5)*(1+p['k'])**5
    return {'parameters':p,'years':years,'initial':initial,'feasible':feasible,'failure':failure,'value_per_share':pv if feasible else None,'realized_distribution_pv':pv,'dps_first5':[x['dps'] for x in rows[:5]],'year5_same_path_continuation':terminal if feasible else None,'rows':rows}


def scenarios():
    return {'base': {}, 'core_low': {'main_volume': 50.0, 'series_volume': 40.0, 'main_price': 2.9, 'series_price': 0.55, 'volume_growth': [0.01, 0.01, 0.01, 0.01, 0.01], 'k': 0.095, 'opex_ratio': 0.068}, 'core_high': {'main_volume': 52.5, 'series_volume': 43.0, 'main_price': 3.16, 'series_price': 0.62, 'volume_growth': [0.035, 0.03, 0.025, 0.02, 0.015], 'k': 0.08}, 'aux_low': {'method': 'normalized_earnings', 'aux_ebitda': 103.0, 'aux_growth': 0.0, 'k': 0.095}, 'aux_base': {'method': 'normalized_earnings'}, 'aux_high': {'method': 'normalized_earnings', 'aux_ebitda': 116.0, 'aux_growth': 0.015, 'k': 0.08}, 'cyclical_demand': {'demand_loss': 0.2, 'loss_years': 3, 'main_price': 2.8, 'series_price': 0.5}, 'structural_stuck_capacity': {'main_volume': 42.0, 'series_volume': 33.0, 'main_price': 2.5, 'series_price': 0.45, 'volume_growth': [-0.02, -0.02, 0.0, 0.0, 0.0], 'mature_volume_growth': 0.0, 'mature_price_growth': 0.01, 'unit_inflation': 0.01, 'k': 0.11}, 'structural_flexible_capacity': {'main_volume': 42.0, 'series_volume': 33.0, 'main_price': 2.5, 'series_price': 0.45, 'volume_growth': [-0.02, -0.02, 0.0, 0.0, 0.0], 'mature_volume_growth': 0.0, 'mature_price_growth': 0.01, 'unit_inflation': 0.01, 'capacity_growth': 0.0, 'mature_capacity_growth': 0.0, 'k': 0.11}, 'price_minus10pct': {'main_price': 2.718, 'series_price': 0.531}, 'cost_plus20pct': {'main_production_cost': 0.204, 'series_production_cost': 0.09, 'main_finish_cost': 0.024, 'series_finish_cost': 0.072}, 'supply_yield90pct': {'production_yield': 0.9}, 'maintenance_double': {'maintenance_factor': 2.0}, 'royalty3pct': {'royalty': 0.03}, 'excise_plus3pp': {'excise_and_other_tax': 0.1886}, 'ar30days_no_advance': {'receivable_days': 30.0, 'advance_ratio': 0.0}, 'finance_yield1pct': {'finance_yield': 0.01}, 'finance_tax25pct': {'finance_tax': 0.25}, 'finance_loss5pct': {'finance_haircut': 0.05}, 'finance_loss20pct': {'finance_haircut': 0.2}, 'finance_freeze3years': {'finance_freeze_years': 3, 'freeze_fraction': 1.0}, 'finance_freeze8years': {'finance_freeze_years': 8, 'freeze_fraction': 1.0}, 'deposits_out50pct': {'external_deposit_growth': -0.5}, 'parent_cash_minus30': {'parent_cash_shift': -30.0}, 'parent_cash_plus30': {'parent_cash_shift': 30.0}, 'parent_distributable_buffer_minus120': {'parent_re_shift': -120.0}, 'sales_re_zero': {'sales_re': 0.0}, 'parent_re_zero': {'parent_re_override':0.}, 'parent_legal_loss_buffer200': {'parent_re_override':-200.}, 'upstream_delay5': {'upstream_delay': 5}, 'payout60pct': {'parent_payout': 0.6}, 'payout95pct': {'parent_payout': 0.95}, 'sub_payout50pct': {'sub_payout': 0.5}, 'fund_loss50pct': {'fund_recovery': 0.5}, 'fund_exit15': {'fund_exit': 15}, 'fund_tax_basis_upper4bn':{'fund_tax_basis_override':4.},'fund_uncalled_already_paid_bound':{'fund_calls':[]},'fund_return_zero': {'fund_growth': 0.0}, 'fund_calls_immediate': {'fund_calls': [6.0]}, 'slow_old_trade': {'old_trade_collection_years': 10}, 'k_plus1pp': {'k': 0.095}, 'inventory_buffer30pct': {'inventory_buffer': 1.3}, 'series_age5years': {'inventory_years_series': 5.0}, 'legacy_supply_minus15pct': {'opening_main_release': [44.2, 45.05, 45.9, 46.75, 47.6], 'opening_series_release': [36.55, 37.4, 38.25]}, 'finance_rwa60pct': {'finance_rwa_ratio': 0.6}, 'projects_half': {'project_capex': [2.5, 2.5, 2.5, 2.5, 2.206745]}, 'projects_double': {'project_capex': [10.0, 10.0, 10.0, 10.0, 8.82698]}, 'inventory_quality_loss30pct': {'inventory_impairment': 0.3}, 'channel_price_credit_pressure': {'main_price': 2.5, 'series_price': 0.45, 'demand_loss': 0.2, 'loss_years': 3, 'receivable_days': 30.0, 'advance_ratio': 0.0}, 'severe_no_sales_freeze': {'demand_loss': 1.0, 'loss_years': 999, 'extra_fixed_cost': 20.0, 'finance_freeze_years': 999, 'freeze_fraction': 1.0}, 'finance_buffer10bn': {'finance_capital_floor': 10.0}, 'finance_buffer16bn': {'finance_capital_floor': 16.0}, 'immediate_full_lawful_release':{'release_start':1,'release_fraction':1.},'three_year_delay_full_release':{'release_start':4,'release_fraction':1.},'parent_h1_capacity_floor':{'parent_use_h1_re_floor':True},'other_tax_assets_no_credit':{'parent_other_dta_cap':0.},'intercompany_profit_15bn':{'internal_profit_opening':15.},'intercompany_profit_25bn':{'internal_profit_opening':25.},'old_payout_policy_no_excess_release': {'release_surplus': False}, 'legal_minimum_reserve_only': {'parent_continue_10pct_reserve': False}, 'release_excess_after5': {'release_start': 6}, 'release_excess_half': {'release_fraction': 0.5}, 'bounded_unsold_recovery20pct': {'supply_carry_fraction': 0.2}, 'cyclical_with_recovery20pct': {'demand_loss': 0.2, 'loss_years': 3, 'main_price': 2.8, 'series_price': 0.5, 'supply_carry_fraction': 0.2}, 'finance_loss5_no_derisk': {'finance_haircut': 0.05, 'finance_derisk_max_fraction': 0.0}, 'finance_loss5_derisk_highcost': {'finance_haircut': 0.05, 'finance_derisk_cost': 0.02}, 'finance_fixed_cost_inflates_forever':{'finance_admin_mode':'fixed_inflation'},'finance_low_liquid_assets10pct':{'finance_liquid_fraction':.1},'finance_loss5_low_liquid_assets':{'finance_haircut':.05,'finance_liquid_fraction':.1},'finance_approved_exit20': {'finance_close_year': 20}, 'finance_approved_exit40': {'finance_close_year': 40}, 'approved_parent_capital_return10': {'capital_return_start': 10}, 'approved_parent_capital_return20': {'capital_return_start': 20}, 'approved_combined_capital_return': {'capital_return_start': 10, 'finance_close_year': 20}, 'export_profit_share_double': {'export_profit_share': 0.003}, 'export_cash_half': {'export_cash': 1.26806880011}, 'annual_parent_loss_positive_upstream': {'main_parent_profit_share': -0.1, 'sales_profit_share': 1.05}}

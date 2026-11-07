#!/usr/bin/env python3
"""CN:603979 2026Q3. Stdlib only; bCNY, kt, USD/t. No market-price input.
Economic pools are NOT invented legal entities. Published legal capital only at parent.
Defaults output beside this file; every annual state and sensitivity is retained.
"""
import json, math, copy, pathlib, argparse, hashlib, gzip, base64
YEARS=30
SHARES=0.623794527+0.495804/11.12
OPEN_DEBT=1.25227476935+1.05483721952+1.44422037925+1.99977+.01873595414+.29869844836-.495804
OPEN_CASH=6.07462912271+.800-.030
BASE=dict(copper=11000.,fx=7.,cost=1.,capex=1.,delay=0,service_margin=.16,service_growth=.06,r=.115,g=.02,credit=8.5,wc_days=0,permit=True,upstream=.85,loss_of_priority=False,volume=1.,windfall_threshold=11250.,parent_cash=1.3,lubambe_loan=4.2,phosphate_limit=13000.,stored_release=.25,terminal_delay=2)
SPECS={
 'Dikulushi':dict(q=[12,7,1],own=.90,cost=4500,tax=.30,royalty=.038,wht=.10,opening_wc=.14,basis=.20,build=[],close=.08,maint=450),
 'Lonshi':dict(q=[50,50,45,50,65,80,85,85,80,70,65,55,40,30,20],own=.95,cost=3900,tax=.30,royalty=.038,wht=.10,opening_wc=.60,basis=2.5,build=[1.15,1.25,1.05,.50],close=.28,maint=550),
 'Lubambe':dict(q=[29,32,32.5,32.5,32.5,32.5,32.5,32.5,32.5,32.5,30,25],own=.80,cost=6500,tax=.30,royalty=.065,wht=0.,opening_wc=.28,basis=.75,build=[.22],close=.21,maint=500),
 'Alacran':dict(q=[0,0,12,25]+[27]*11+[27.5],own=.975,cost=4900,tax=.35,royalty=.04,wht=.20,opening_wc=.03,basis=.50,build=[1.50,1.35,.20],close=.1582,maint=500),
 'Phosphate':dict(q=[300,300]+[800]*15+[400],own=.90,cost=520,tax=.25,royalty=.04,wht=0.,opening_wc=.06,basis=.85,build=[.14,.135],close=.06,maint=80)
}
# Cu totals 20,870,376,361.5 kt. Phosphate 13 Mt requires resource-to-reserve conversion.
def pv(v,r): return sum(x/(1+r)**(i+1) for i,x in enumerate(v))
def tax_bill(ebit,loss,rate,minimum=0.):
    taxable=max(0.,ebit-loss); new_loss=max(0.,loss-ebit)
    return max(minimum,taxable*rate),new_loss

def initial():
    return dict(cash=OPEN_CASH,debt=OPEN_DEBT,parent_cash=BASE['parent_cash'],parent_re=.623*0+2.64544928507-.4117+.15,parent_reserve=.36055660399,parent_registered=.623776176,parent_loan=4.02555196452,parent_div_receivable=.23054008965,service_revenue=7.30,service_wc=2.92,service_ppe=1.9,service_cash=.584,zccm=.70627091921,old_lubambe_loan=4.2,emr_contingent=.18127773598,retained_nci_cash=.030,source_profit_budget=0.,pools={k:dict(wc=v['opening_wc'],tax_loss=0.,tax_payable=0.,basis=v['basis'],funding_loan=0.,remaining=sum(v['q']),depleted=False,closed=False) for k,v in SPECS.items()})

def mine(k,t,p,s):
    spec=SPECS[k]; st=s['pools'][k]; idx=t-1-(p['delay'] if k in ('Alacran','Lonshi') else 0)
    q=spec['q'][idx] if 0<=idx<len(spec['q']) else 0.
    if k=='Lonshi' and idx<0: q=50. # existing west is not shut while east delayed
    if k=='Lubambe' and not p['permit'] and t>7:q=0.
    if k=='Phosphate':q=min(q,max(0,p['phosphate_limit']-(sum(spec['q'])-st['remaining'])))
    q=min(q*p['volume'],st['remaining']); st['remaining']-=q
    end=(idx>=len(spec['q']) or (k=='Lubambe' and not p['permit'] and t>7))
    inflation=1.02**(t-1); price=(1000. if k=='Phosphate' else p['copper']*p['fx'])* (1.02**max(0,t-5))
    unitcost=spec['cost']*(1 if k=='Phosphate' else p['fx'])*inflation*p['cost']
    revenue=q*price/1e6; cost=q*unitcost/1e6
    royalty=revenue*spec['royalty']; maintenance=q*spec['maint']*(1 if k=='Phosphate' else p['fx'])*inflation/1e6
    bi=t-1; construction=(spec['build'][bi] if bi<len(spec['build']) else 0)*p['capex']*p['fx']/7.
    if p['delay'] and k in ('Alacran','Lonshi') and t<=p['delay']: construction+=.08*p['delay']
    depreciation=min(st['basis']+construction,(st['basis']+construction)*q/max(q+st['remaining'],1e-12)) if q else 0.
    st['basis']+=construction+maintenance-depreciation
    ebit=revenue-cost-royalty-depreciation
    windfall=(max(0,p['copper']*1.02**max(0,t-5)-p['windfall_threshold'])*q*p['fx']/1e6*.50) if k in ('Lonshi','Dikulushi') else 0.
    # Excess-profit levy is an explicit valuation reserve, not a legal tax opinion.
    tax,st['tax_loss']=tax_bill(ebit,st['tax_loss'],spec['tax'],revenue*.01 if k in ('Lonshi','Dikulushi') else 0.)
    assessed=tax+windfall; cash_tax=.8*assessed+st['tax_payable']; st['tax_payable']=.2*assessed
    oldwc=st['wc']; ar=revenue*(45+p['wc_days'])/365; inventory=cost*75/365; ap=cost*35/365
    target=ar+inventory-ap
    if q==0 and not end:target=oldwc
    if k=='Phosphate' and q==0 and sum(spec['q'])-st['remaining']>=p['phosphate_limit']:end=True
    if end: target=0.
    # First-year opening stock is explicit; last-year sales stock settles next year.
    st['wc']=target; dwc=target-oldwc
    close=spec['close']*inflation if end and not st['closed'] else 0.
    if end:st['closed']=True
    fcf=revenue-cost-royalty-cash_tax-construction-maintenance-dwc-close
    zccm_payment=0.; old_loan_return=0.; advanced=0.; priority_return=0.
    if fcf<0:
        advanced=-fcf; st['funding_loan']+=advanced; common=fcf; minority_cash=0.
    else:
        priority_return=min(fcf,st['funding_loan']) if not p['loss_of_priority'] else 0.
        st['funding_loan']-=priority_return; residual=fcf-priority_return
        if k=='Lubambe' and residual>0 and s['zccm']+s['old_lubambe_loan']>0:
            repaid=min(residual,s['zccm']+s['old_lubambe_loan']); zccm_payment=repaid*s['zccm']/(s['zccm']+s['old_lubambe_loan']); old_loan_return=repaid-zccm_payment
            s['zccm']-=zccm_payment;s['old_lubambe_loan']-=old_loan_return;residual-=repaid
        minority_cash=residual*(1-spec['own']);common=priority_return+old_loan_return+residual*spec['own']
    # Only dividend-like residual, not loan principal, bears withholding reserve.
    withholding=max(0,common-priority_return-old_loan_return)*spec['wht']
    common-=withholding
    return dict(name=k,quantity=q,remaining_recoverable=st['remaining'],revenue=revenue,cash_cost=cost,royalty=royalty,ebit=ebit,depreciation=depreciation,tax_assessed=assessed,cash_tax=cash_tax,tax_payable=st['tax_payable'],tax_loss=st['tax_loss'],construction=construction,maintenance=maintenance,opening_nwc=oldwc,ar=ar,inventory=inventory,ap=ap,closing_nwc=target,change_nwc=dwc,closure=close,unlevered_cash=fcf,shareholder_advance=advanced,priority_loan_return=priority_return,outstanding_new_shareholder_loan=st['funding_loan'],old_lubambe_loan_return=old_loan_return,zccm_repayment=zccm_payment,minority_cash=minority_cash,minority_profit=(ebit-assessed)*(1-spec['own']),withholding=withholding,common_cash=common)

def annual(t,p,s):
    opening=copy.deepcopy(s); oldrev=s['service_revenue']; growth=p['service_growth'] if t<=5 else (.04 if t<=10 else p['g'])
    rev=oldrev*(1+growth);ebit=rev*p['service_margin'];depr=rev*.05
    capex=depr+(rev-oldrev)*.25
    # Remaining equipment programme is minimum, not a second additive capital bill.
    capex=max(capex,.7857223/3 if t<=3 else 0.)
    wc=rev*(.40+p['wc_days']/365);dwc=wc-s['service_wc'];s['service_wc']=wc;s['service_revenue']=rev;s['service_ppe']+=capex-depr
    service_fcf=ebit*.75+depr-capex-dwc
    mines=[mine(k,t,p,s) for k in SPECS]
    terra=-.20 if t==1 else (-.08 if t==2 else (.03 if t==3 else 0.)) # shutdown/work-out, not owned mineral perpetuity
    buyback=.35 if t==1 else 0.
    contingency=min(s['emr_contingent'],.065 if p['copper']>8818 and t<=3 else 0.);s['emr_contingent']-=contingency
    bond_principal=min(s['debt'],1.99977) if t<=5 else 0.
    bond_coupon=[.003,.006,.010,.015,0.][t-1]*bond_principal if t<=5 else 0.
    interest=max(0,s['debt']-bond_principal)*.052+bond_coupon
    # No group-level instantaneous interest tax refund; local tax below EBIT already charged.
    operation=service_fcf+sum(m['common_cash'] for m in mines)+terra
    free=operation-interest-buyback-contingency-.08
    s['cash']+=free
    liquidity=1.20+rev*.08
    due=1.10 if t==1 else (.65 if t in (2,3) else (2.2397424 if t==5 else .30))
    bond_floor=1.99977 if t<5 else 0.
    due=min(due,max(0,s['debt']-bond_floor))
    redemption_premium=.2399724 if t==5 else 0.
    s['cash']-=redemption_premium
    draw=max(0,liquidity+due-s['cash']);capacity=max(0,p['credit']-s['debt'])
    feasible=draw<=capacity+1e-9
    funded=min(draw,capacity);s['debt']+=funded;s['cash']+=funded
    pay=min(due,max(0,s['cash']-liquidity));s['debt']-=pay;s['cash']-=pay
    if pay+1e-8<due:feasible=False
    extra=min(max(0,s['debt']-bond_floor),max(0,s['cash']-liquidity)*(.50 if t<=5 else .80));s['debt']-=extra;s['cash']-=extra
    # Parent opening funds reside inside group cash. Internal upstream transfers do not add group cash.
    # Cash upstream budget first settles disclosed parent receivables, then declarations with one-year cash lag.
    s['parent_cash']-=.08
    ordinary_capacity=max(0,operation)*p['upstream']
    opening_foreign_surplus=max(0,opening['cash']-opening['parent_cash']-(1.20+opening['service_revenue']*.08-.25))
    stored_capacity=opening_foreign_surplus*p['stored_release'] if t>5 else 0.
    foreign_capacity=ordinary_capacity+stored_capacity
    upstream=min(foreign_capacity,max(0,s['cash']-s['parent_cash']-(liquidity-.25)),s['parent_div_receivable']+s['parent_loan'])
    receivable_settle=min(upstream,s['parent_div_receivable']);s['parent_div_receivable']-=receivable_settle
    rest=upstream-receivable_settle;loan_return=min(rest,s['parent_loan']);s['parent_loan']-=loan_return
    dividend_cash=receivable_settle
    # New declarations capped by positive source profits; uncollected declarations retained as receivables.
    source_profit=ebit*.75+sum((m['ebit']-m['tax_assessed'])*SPECS[m['name']]['own'] for m in mines)
    s['source_profit_budget']+=source_profit
    declared=min(max(0,s['source_profit_budget']),foreign_capacity)
    s['source_profit_budget']-=declared
    # Current cash dividend amount is already within actual operating cash; declaration also supplies legal P&L.
    s['parent_div_receivable']+=declared
    parent_profit=declared-.08
    old_re=s['parent_re']; loss_makeup=min(max(0,-old_re),max(0,parent_profit))
    reserve=min(max(0,parent_profit-loss_makeup)*.10,max(0,.5*s['parent_registered']-s['parent_reserve']))
    s['parent_reserve']+=reserve;s['parent_re']+=parent_profit-reserve
    s['parent_cash']+=upstream
    # Parent central expense also leaves group; no double addition of domestic upstream.
    desired=[.60,.70,.80,1.00,1.20][t-1]*SHARES if t<=5 else max(0,s['cash']-liquidity)*.90
    distribution=min(desired,max(0,s['cash']-liquidity),max(0,s['parent_cash']-.25),max(0,s['parent_re'])) if feasible else 0.
    s['cash']-=distribution;s['parent_cash']-=distribution;s['parent_re']-=distribution
    # Parent cash cannot exceed all common cash. Excess retained subsidiary cash is not automatically parent cash.
    if s['parent_cash']>s['cash']+1e-8 or s['parent_cash']<.25-1e-8 or s['cash']<liquidity-1e-8: feasible=False
    ending=copy.deepcopy(s)
    return dict(year=t,calendar_year=2026+t,parameters=copy.deepcopy(p),opening=opening,service=dict(revenue=rev,ebit=ebit,tax=ebit*.25,depreciation=depr,capex=capex,change_nwc=dwc,nwc=wc,ppe=s['service_ppe'],fcf=service_fcf,roic=ebit*.75/max(.01,opening['service_ppe']+opening['service_wc'])),mines=mines,terra=terra,common_operating_cash=operation,interest=interest,bond_coupon=bond_coupon,bank_interest=interest-bond_coupon,buyback=buyback,redemption_premium=redemption_premium,emr_contingent_payment=contingency,borrow=funded,scheduled_debt_repayment=pay,extra_debt_repayment=extra,liquidity_floor=liquidity,ordinary_upstream_capacity=ordinary_capacity,opening_foreign_surplus=opening_foreign_surplus,stored_release_capacity=stored_capacity,upstream_cash=upstream,parent_receivable_cash=receivable_settle,parent_loan_principal_return=loan_return,parent_dividend_cash=dividend_cash,parent_dividend_declared=declared,parent_profit=parent_profit,parent_reserve_allocation=reserve,parent_loss_makeup=loss_makeup,distribution=distribution,distribution_per_share=distribution/SHARES,feasible=feasible,ending=ending,cash_conservation_error=s['cash']-(opening['cash']+free+funded-pay-extra-distribution-redemption_premium))

def run(p,start=None,start_year=1,prefix=None):
    s=copy.deepcopy(start) if start else initial();s['parent_cash']=p['parent_cash'] if not start else s['parent_cash']
    if not start:s['old_lubambe_loan']=p['lubambe_loan']
    rows=copy.deepcopy(prefix or []);failure=None
    for t in range(start_year,YEARS+1):
        row=annual(t,p,s);rows.append(row)
        if not row['feasible']:failure=f'year_{t}_finite_finance_or_parent_cash';break
    if failure:return dict(status='infeasible',failure=failure,parameters=p,years=rows,pv_per_share=None,terminal_year5_per_share=None,terminal_year30=None,distributions_per_share_30_years=[r['distribution_per_share'] for r in rows]+[0.]*(YEARS-len(rows)),paid_distributions_before_stop=[r['distribution_per_share'] for r in rows],unpaid_debt=s['debt']+s['zccm'],state=s)
    # Mature service continuation only. Its perpetuity retains incremental WC, PPE and cash.
    rev=s['service_revenue'];nextrev=rev*(1+p['g']);nextfcf=nextrev*p['service_margin']*.75-(nextrev-rev)*(.25+.40+.08)-.08*(1+p['g'])
    stock_factor=p['stored_release']/(p['r']+p['stored_release']) if p['stored_release']>0 else 0.
    flow_factor=(min(1.,p['upstream'])+(1-min(1.,p['upstream']))*stock_factor)/(1+p['r'])**p['terminal_delay']
    operating_tv=nextfcf/(p['r']-p['g'])*flow_factor
    excess=max(0,s['cash']-(1.20+rev*.08));realizable=min(excess,max(0,s['parent_re'])+max(0,s['source_profit_budget'])+s['parent_div_receivable']+s['parent_loan'])
    obligations=s['debt']+s['zccm']+s['emr_contingent']+sum(x['tax_payable'] for x in s['pools'].values())
    terminal=operating_tv+realizable*stock_factor/(1+p['r'])**p['terminal_delay']-obligations
    ds=[r['distribution'] for r in rows];value=pv(ds,p['r'])+terminal/(1+p['r'])**YEARS
    tv5=sum(r['distribution']/(1+p['r'])**(r['year']-5) for r in rows if r['year']>5)+terminal/(1+p['r'])**25
    return dict(status='feasible',failure=None,parameters=p,years=rows,pv_per_share=value/SHARES,terminal_year5_per_share=tv5/SHARES,distributions_per_share_30_years=[r['distribution_per_share'] for r in rows],terminal_year30=dict(operating_service=operating_tv,undelayed_service_value=nextfcf/(p['r']-p['g']),excess_cash=excess,realizable_excess_cash=realizable,realization_delay_years=p['terminal_delay'],stock_release_rate=p['stored_release'],stock_realization_factor=stock_factor,continuing_flow_factor=flow_factor,realized_cash_value=realizable*stock_factor/(1+p['r'])**p['terminal_delay'],retained_unrealizable_cash=excess-realizable,obligations=obligations,equity=terminal),unpaid_debt=obligations,state=s)

def produce():
    variants={'core_low':dict(copper=10500,service_margin=.15,r=.12),'base':{},'core_high':dict(copper=11500,service_margin=.17,r=.11),'cyclical_weak':dict(copper=8500,cost=1.05,service_growth=.02),'structural_adverse':dict(copper=7500,cost=1.20,service_margin=.11,service_growth=0.,credit=6.,permit=False),'optimistic':dict(copper=12500,service_margin=.18,cost=.95,service_growth=.08),'copper_minus_1000':dict(copper=10000),'copper_plus_1000':dict(copper=12000),'cost_plus_10pct':dict(cost=1.1),'capex_plus_20pct':dict(capex=1.2),'delay_two_years':dict(delay=2),'wc_plus_60_days':dict(wc_days=60),'fx_6_3':dict(fx=6.3),'fx_7_7':dict(fx=7.7),'upstream_half':dict(upstream=.425),'permanent_transfer_restriction':dict(upstream=.425,stored_release=.125),'stored_release_disabled':dict(stored_release=0.),'stored_release_half':dict(stored_release=.125),'terminal_delay_0':dict(terminal_delay=0),'terminal_delay_8':dict(terminal_delay=8),'parent_cash_minus_0_5':dict(parent_cash=.8),'priority_unavailable':dict(loss_of_priority=True),'permit_not_renewed':dict(permit=False),'credit_closed':dict(credit=OPEN_DEBT),'windfall_threshold_10000':dict(windfall_threshold=10000.),'phosphate_only_current_reserves':dict(phosphate_limit=3140.),'lubambe_old_loan_zero':dict(lubambe_loan=0.),'lubambe_old_loan_6bn':dict(lubambe_loan=6.)}
    paths={k:run(dict(BASE,**v)) for k,v in variants.items()}
    for path in paths.values():
        if path['status']=='feasible':
            r=path['parameters']['r'];asset_pv=sum((y['common_operating_cash']-.08-y['emr_contingent_payment']-y['buyback']-y['redemption_premium'])/(1+r)**y['year'] for y in path['years'])
            operating_tail=path['terminal_year30']['undelayed_service_value']/(1+r)**YEARS
            path['auxiliary_asset_cash_method']=dict(operating_cash_pv=asset_pv,service_tail_pv=operating_tail,opening_common_cash=OPEN_CASH,financial_debt_excluding_project_zccm=OPEN_DEBT,equity_per_share=(asset_pv+operating_tail+OPEN_CASH-OPEN_DEBT)/SHARES,meaning='unlevered asset cash discounted at equity hurdle, debt settled now, no parent remittance lag; upper cross-check not final distributable-holder value')
        else:path['auxiliary_asset_cash_method']=None
    base=paths['base'];conditional={}
    if base['status']=='feasible':
        state=base['years'][4]['ending'];prefix=base['years'][:5]
        for k in ('core_low','core_high'):conditional[k]=run(dict(BASE,**variants[k]),state,6,prefix)
    return dict(schema_version=1,symbol='CN:603979',period='2026-Q3',money_unit='billion_CNY',quantity_unit='kt',shares_billion=SHARES,opening=initial(),definitions={'parent_registered':'2025 charter registered RMB623,776,176, not issued shares','pools':'economic project budgets, not invented subsidiary statutory profit ledgers','dividends':'actual external common dividends only; buyback for incentives excluded','year1':'next full annual cash period 2027; Q4 2026 bridge held flat as valuation simplification','mine_nwc':'AR plus inventory minus AP; opening funded stock and final recovery explicit','tax':'country statutory rates plus conservative reserves; no instantaneous refunds','terminal':'only service perpetuity; all finite mines zero residual resource value'},sources={'q3':'https://static.cninfo.com.cn/finalpage/2026-10-27/1225625368.PDF','h1':'https://static.cninfo.com.cn/finalpage/2026-08-26/1225502889.PDF','annual':'https://static.cninfo.com.cn/finalpage/2026-04-28/1225201125.PDF','lonshi_fs':'https://static.cninfo.com.cn/finalpage/2025-01-20/1222373969.PDF'},scenarios=paths,conditional_year5=conditional,return_model={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':'2026-10-26T23:00:00Z','base_case_distributions_per_share':[r['distribution_per_share'] for r in base['years'][:5]],'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':conditional.get('core_low',{}).get('terminal_year5_per_share'),'high':conditional.get('core_high',{}).get('terminal_year5_per_share')}}})

def self_test():
    result=produce();checks=0
    assert tax_bill(-.3,0,.3)==(0,.3);assert abs(tax_bill(.5,.3,.3)[0]-.06)<1e-12;checks+=1
    for path in list(result['scenarios'].values())+list(result['conditional_year5'].values()):
        for row in path['years']:
            assert abs(row['cash_conservation_error'])<1e-8
            if row['feasible']:assert row['ending']['cash']>=row['liquidity_floor']-1e-8 and row['ending']['parent_cash']>=.25-1e-8
            for mine_row in row['mines']:
                assert abs(mine_row['change_nwc']-(mine_row['closing_nwc']-mine_row['opening_nwc']))<1e-8
                assert abs(mine_row['common_cash']+mine_row['minority_cash']+mine_row['zccm_repayment']+mine_row['withholding']-mine_row['unlevered_cash'])<1e-8
        if path['status']=='infeasible':
            assert path['pv_per_share'] is None and path['terminal_year5_per_share'] is None and path['terminal_year30'] is None
            assert all(d==0 for d in path['distributions_per_share_30_years'][len(path['years']):])
        checks+=1
    base=result['scenarios']['base'];prefix=base['years'][:5]
    for path in result['conditional_year5'].values():assert path['years'][:5]==prefix
    checks+=1
    for name,spec in SPECS.items():
        rows=[m for y in base['years'] for m in y['mines'] if m['name']==name]
        assert abs(sum(v['change_nwc'] for v in rows)+spec['opening_wc'])<1e-8
        assert abs(sum(v['quantity'] for v in rows)-sum(spec['q']))<1e-8
        assert rows[-1]['tax_payable']==0 and rows[-1]['closing_nwc']==0
        checks+=1
    st=initial();st['parent_re']=-10;row=annual(1,BASE,st);assert row['distribution']==0 and row['parent_reserve_allocation']==0;checks+=1
    st=initial();st['cash']=.1;st['parent_cash']=.05;row=annual(1,dict(BASE,credit=0),st);assert not row['feasible'] and row['distribution']==0;checks+=1
    st=initial();st['pools']['Dikulushi']['wc']=.47;row=mine('Dikulushi',4,BASE,st);assert abs(row['change_nwc']+.47)<1e-8;checks+=1
    assert abs(base['years'][0]['bond_coupon']-1.99977*.003)<1e-10
    assert all(y['ending']['debt']>=1.99977-1e-8 for y in prefix[:4]);assert prefix[4]['bond_coupon']==0;checks+=1
    for label in ['base','upstream_half','permanent_transfer_restriction','stored_release_disabled','terminal_delay_8']:
        path=result['scenarios'][label];p=path['parameters'];tail=path['terminal_year30'];factor=p['stored_release']/(p['r']+p['stored_release'])
        assert abs(tail['realized_cash_value']-tail['realizable_excess_cash']*factor/(1+p['r'])**p['terminal_delay'])<1e-8
        for y in path['years']:assert y['upstream_cash']<=y['ordinary_upstream_capacity']+y['stored_release_capacity']+1e-8
        checks+=1
    return dict(ok=True,assertion_groups=checks,scenarios=len(result['scenarios']),conditional_paths=len(result['conditional_year5']))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path);ap.add_argument('--expand',action='store_true');ap.add_argument('--self-test',action='store_true');args=ap.parse_args()
    if args.self_test:
        print(json.dumps(self_test()));return
    result=produce();path=args.output or pathlib.Path(__file__).resolve().with_name('2026-Q3-output.json')
    raw=json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    delivered=result if args.expand else dict(schema_version=1,symbol='CN:603979',period='2026-Q3',encoding='gzip+base64',uncompressed_sha256=hashlib.sha256(raw).hexdigest(),uncompressed_bytes=len(raw),return_model=result['return_model'],scenario_summary={k:{'status':v['status'],'pv_per_share':v['pv_per_share'],'terminal_year5_per_share':v['terminal_year5_per_share']} for k,v in result['scenarios'].items()},payload=base64.b64encode(gzip.compress(raw,mtime=0)).decode())
    path.write_text(json.dumps(delivered,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:{'status':v['status'],'pv':v['pv_per_share'],'failure':v['failure']} for k,v in result['scenarios'].items()},ensure_ascii=False))
if __name__=='__main__':main()

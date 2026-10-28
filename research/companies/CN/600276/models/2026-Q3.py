#!/usr/bin/env python3
"""Hengrui 2026-Q3: standalone economic/payment-budget model.
Amounts: CNY billion; shares: billion. Stdlib only. No security prices.
Assumptions are explicit below.
Default: write 2026-Q3-output.json beside this script; --output overrides.
Actual cash excludes internal designation of necessary cash as an outflow.
Statutory capacity is a forecast budget, not a legal opinion/approval.
"""
import argparse, copy, json, math
from pathlib import Path

CUTOFF='2026-10-27T11:26:39+00:00'
SHARES=6.638199874

def ramp(a,b,n=10): return [a+(b-a)*i/(n-1) for i in range(n)]

def params():
    return dict(name='base',k=.095,g=.025,tail_end=50,shares=SHARES,
        products=[13.5,5.6,10.0],growth=[[.08,.10,.10,.09,.08,.07,.06,.05,.04,.035],[.32,.28,.24,.20,.17,.14,.11,.09,.07,.05],[-.14,-.10,-.06,-.03,0,0,0,0,0,0]],
        gross=[.88,.88,.80],sales=ramp(.30,.27),admin=ramp(.085,.07),rd=ramp(.34,.28),other=.02,
        signed_near=[3.325,1.225,0,0,0,0,0,0,0,0],milestones=[.3,.5,.8,1.2,1.7,2,2.2,2.4,2.5,2.6],new_deals=[1.5,1.7,1.9,2.1,2.3,2.4,2.5,2.6,2.7,2.8],royalties=[0,0,.05,.15,.35,.4,.6,.8,1.1,1.4],
        old_license_release=[1.5,1.4,1,.74180621168,0,0,0,0,0,0],license_cost=.02,
        tax=.14,cash_yield=.02,debt_rate=.025,cash=42.79513257843-.0480091,debt=.42164947982,
        accrued_interest=43.4467695428-42.79513257843-.01269087819,restricted_deposit=.01269087819,
        accrued_receipt_year=1,deposit_release_year=3,opening_claim_parent_share=.90,normalize_after_year3=False,
        asset_net=3.11921733098-.26377476848-.52289751618,asset_parent_share=.8,
        fixed=9.,capex=ramp(2.5,3.4),depreciation_ratio=.028,nwc=7.4,nwc_ratio=.25,required_cash=5.82,required_cash_ratio=.20,
        payout=[.20,.20,.22,.24,.25,.28,.31,.34,.37,.40],parent_cash=32.,parent_retained=35.80101067811,parent_registered=6.637199874,parent_reserve=3.33952951742,
        parent_cash_share=.80,parent_profit_share=.85,parent_financial_share=.90,debt_parent_share=.90,parent_funding=[1.5]*10,parent_extra_payment=[0.]*10,parent_floor=8.,
        advances=7.06733668818,tail_parent_cash_share=.85,tail_parent_profit_share=.85,
        subsidiary_loss_buffer=5.,upstream_friction=.02,upstream_enabled=True,upstream_start=11,
        release_window=15,release_after_window=5,employee_payment=1.4261151,employee_receipt=.71305755,employee_non_cash=.23768585,
        sources=[dict(name='苏州盛迪亚生物医药有限公司',registered=.1,weight=2/3),dict(name='上海恒瑞医药有限公司',registered=.072,weight=1/3)])

def retained_step(retained,reserve,profit,registered):
    """Later losses always reduce retained capacity. No presumed reserve release.
    10% of current profit AFTER covering past retained deficit, capped at 50% capital.
    Existing undistributed retained is not erased by zero growth.
    """
    covered=max(0.,-retained)
    accrual=min(max(0.,registered*.5-reserve),max(0.,profit-covered)*.1)
    return retained+profit-accrual,reserve+accrual,accrual

def simulate(p):
    p=copy.deepcopy(p); cash=p['cash']; pc=p['parent_cash']; pr=p['parent_retained']; reserve=p['parent_reserve']
    debt=p['debt']; advances=p['advances']; fixed=p['fixed']; nwc=p['nwc']; req=p['required_cash']; prod=list(p['products'])
    pools=[dict(s,retained=-p['subsidiary_loss_buffer']*s['weight'],reserve=0.) for s in p['sources']]
    rows=[]; initial_asset=p['asset_net']; asset_left=initial_asset; debt_initial=debt; advance_repay_budget=None
    for y in range(1,p['tail_end']+1):
        cash0,pc0,pr0,res0,debt0,req0,nwc0,fixed0,advance0=cash,pc,pr,reserve,debt,req,nwc,fixed,advances
        if y<=10:
            i=y-1; prod=[v*(1+p['growth'][j][i]) for j,v in enumerate(prod)]; product=sum(prod)
            license_cash=sum(p[key][i] for key in ('signed_near','milestones','new_deals','royalties'))
            release=p['old_license_release'][i]
            # Future new-license cash is recognized contemporaneously in this budget;
            # separately release opening contract liability, without receiving cash twice.
            license_revenue=license_cash+release
            ebit=sum(v*m for v,m in zip(prod,p['gross']))-product*(p['sales'][i]+p['admin'][i]+p['rd'][i]+p['other'])+license_revenue-license_cash*p['license_cost']
            dep=product*p['depreciation_ratio']; capex=p['capex'][i]
            if p['normalize_after_year3'] and y>3: capex=dep+p['g']*fixed
            newnwc=product*p['nwc_ratio']; newreq=product*p['required_cash_ratio']
            cash_share=p['parent_cash_share']; profit_share=p['parent_profit_share']
            finance_parent_share=p['parent_financial_share']; funding=p['parent_funding'][i]; extra=p['parent_extra_payment'][i]
            corporate=(-p['employee_payment'] if y==1 else p['employee_receipt'] if y==2 else 0.)+(p['employee_non_cash'] if y<=3 else 0.)
            sale=0.; principal=0.; repayment=0.
        else:
            if y==11:
                anchor=rows[9]; advance_repay_budget=advances/p['release_window']
            q=(1+p['g'])**(y-10)
            product=anchor['product_revenue']*q; prod=[v*(1+p['g']) for v in prod]
            license_cash=anchor['license_cash']*q; license_revenue=license_cash; release=0.
            ebit=anchor['ebit']*q
            dep=product*p['depreciation_ratio']; capex=dep+p['g']*fixed
            newnwc=product*p['nwc_ratio']; newreq=product*p['required_cash_ratio']
            cash_share=p['tail_parent_cash_share']; profit_share=p['tail_parent_profit_share']
            # Actual starting mother cash earns only its own finance income.
            finance_parent_share=pc/cash if cash>0 else cash_share
            funding=extra=corporate=0.
            sale=min(asset_left,initial_asset/p['release_window']); asset_left-=sale
            principal=min(debt,debt_initial/p['release_window']); repayment=0.
        tax=max(ebit,0.)*p['tax']; nopat=ebit-tax
        fin=(cash*p['cash_yield']-debt*p['debt_rate'])*(1-p['tax'])
        pfin=(pc*p['cash_yield']-debt*p['debt_parent_share']*p['debt_rate'])*(1-p['tax'])
        necessary_income=req*p['cash_yield']*(1-p['tax'])
        # Full R&D already expensed in EBIT; no second R&D cash subtraction.
        op_cash=nopat+dep-capex-(newnwc-nwc)+license_cash-license_revenue
        business_fcf=op_cash+necessary_income-(newreq-req)
        if y>10 and business_fcf < -1e-9:
            raise ValueError('Negative continuing operating cash: explicit financing/restructuring/exit path required, not zero terminal value')
        # Opening accrued interest and guarantees are separate non-cash claims.
        # Settlement creates bank cash, not current profit; it earns interest only next year.
        claim_receipt=(p['accrued_interest'] if y==p['accrued_receipt_year'] else 0.)+(p['restricted_deposit'] if y==p['deposit_release_year'] else 0.)
        parent_claim_receipt=claim_receipt*p['opening_claim_parent_share']
        # No subtraction of delta necessary cash from actual bank balances.
        cash += op_cash+fin+corporate+sale-principal+claim_receipt
        pc += op_cash*cash_share+pfin+corporate+sale*p['asset_parent_share']-principal*p['debt_parent_share']-funding-extra+parent_claim_receipt
        advances += funding+extra
        # Employee receipt/noncash addback does not invent legal profit.
        parent_profit=nopat*profit_share+pfin
        pr,reserve,parent_accrual=retained_step(pr,reserve,parent_profit,p['parent_registered'])
        source_profit=nopat*(1-profit_share)+(fin-pfin)
        source_rows=[]
        for s in pools:
            opening=s['retained']; opening_reserve=s['reserve']
            prof=source_profit*s['weight']
            s['retained'],s['reserve'],accrual=retained_step(opening,opening_reserve,prof,s['registered'])
            source_rows.append(dict(name=s['name'],registered=s['registered'],weight=s['weight'],opening_retained=opening,profit=prof,opening_reserve=opening_reserve,reserve_accrual=accrual,reserve=s['reserve'],retained_before_distribution=s['retained']))
        req=newreq; nwc=newnwc; fixed+=capex-dep; debt-=principal
        if cash < req-1e-8 or pc< -1e-8:
            raise ValueError('Funding infeasible: group operating reserve or mother actual cash exhausted; no implicit financing')
        if y>10:
            # Only cash outside parent above its own share of necessary cash can repay.
            outside_available=max(0.,cash-pc-req*(1-cash_share))
            repayment=min(advances,advance_repay_budget,outside_available)
            pc+=repayment; advances-=repayment
        upstream=0.; friction=0.
        if p['upstream_enabled'] and y>=p['upstream_start']:
            outside_available=max(0.,cash-pc-req*(1-cash_share))
            for s,sr in zip(pools,source_rows):
                gross=min(max(0.,s['retained']),outside_available*s['weight'])
                s['retained']-=gross; loss=gross*p['upstream_friction']; net=gross-loss
                # Same period declaration/receipt budget, no pre-existing receivable counted again.
                pc+=net; pr+=net; cash-=loss; upstream+=gross; friction+=loss
                sr['gross_distribution']=gross
        for s,sr in zip(pools,source_rows):
            sr.setdefault('gross_distribution',0.);sr['closing_retained']=s['retained']
        economic_profit=nopat+fin
        if y<=10:
            request=max(0.,economic_profit)*p['payout'][y-1]
            release_request=0.
        else:
            # Initial recovery window then CONTINUING rolling request, not a cliff.
            available=max(0.,cash-req)
            remaining=max(1,p['release_window']-(y-11)) if y<=10+p['release_window'] else p['release_after_window']
            release_request=available/remaining
            sustainable=max(0.,business_fcf+fin-necessary_income-friction)
            request=sustainable+release_request
        parent_budget=max(0.,pc-max(p['parent_floor'],req*cash_share))
        legal_budget=max(0.,pr)
        group_budget=max(0.,cash-req)
        dividend=min(request,parent_budget,legal_budget,group_budget)
        pc-=dividend;cash-=dividend;pr-=dividend
        assert pc<=cash+1e-7,('mother_cash_exceeds_group',y,pc,cash)
        assert cash>=req-1e-7 and pc>=-1e-7 and debt>=-1e-7
        assert reserve<=max(p['parent_reserve'],p['parent_registered']*.5)+1e-8
        row=dict(year=y,product_revenue=product,products=prod[:],license_cash=license_cash,license_revenue=license_revenue,opening_license_release=release,ebit=ebit,tax=tax,nopat=nopat,physical_depreciation=dep,capex=capex,nwc=nwc,nwc_change=nwc-nwc0,fixed_assets=fixed,required_cash=req,required_cash_change=req-req0,necessary_cash_income=necessary_income,operating_cash_before_finance=op_cash,business_fcf=business_fcf,opening_cash=cash0,opening_parent_cash=pc0,opening_claim_receipt=claim_receipt,parent_opening_claim_receipt=parent_claim_receipt,opening_accrued_interest_remaining=p['accrued_interest'] if y<p['accrued_receipt_year'] else 0.,opening_restricted_deposit_remaining=p['restricted_deposit'] if y<p['deposit_release_year'] else 0.,finance_income=fin,parent_finance_income=pfin,corporate_cash_adjustment=corporate,asset_realization=sale,debt_repayment=principal,debt=debt,parent_funding=funding,parent_extra_payment=extra,advances=advances,advance_repayment=repayment,source_profits=source_profit,sources=source_rows,upstream_gross=upstream,upstream_friction=friction,parent_profit=parent_profit,parent_reserve_accrual=parent_accrual,parent_reserve=reserve,parent_retained=pr,parent_cash=pc,group_cash=cash,release_request=release_request,dividend_request=request,dividend=dividend,dividend_per_share=dividend/p['shares'],legal_budget=legal_budget,parent_cash_budget=parent_budget,group_cash_budget=group_budget,cash_share=cash_share,profit_share=profit_share,finance_parent_share=finance_parent_share)
        # Conservation tests cover actual cash ledger, not only valuation identities.
        expected=cash0+op_cash+fin+corporate+sale-principal-friction-dividend+claim_receipt
        pexpected=pc0+op_cash*cash_share+pfin+corporate+sale*p['asset_parent_share']-principal*p['debt_parent_share']-funding-extra+repayment+upstream-friction-dividend+parent_claim_receipt
        assert math.isclose(cash,expected,rel_tol=1e-12,abs_tol=1e-8)
        assert math.isclose(pc,pexpected,rel_tol=1e-12,abs_tol=1e-8)
        rows.append(row)
    k,g=p['k'],p['g']; assert k>g>=0
    # Close only continuing payment at the final horizon, never add group cash at par.
    tail_value=rows[-1]['dividend']*(1+g)/(k-g)
    pv_distributions=sum(r['dividend']/(1+k)**r['year'] for r in rows)
    pv_terminal=tail_value/(1+k)**p['tail_end']; equity=pv_distributions+pv_terminal
    future5=sum(r['dividend']/(1+k)**(r['year']-5) for r in rows if r['year']>5)+tail_value/(1+k)**(p['tail_end']-5)
    after10=sum(r['dividend']/(1+k)**(r['year']-10) for r in rows if r['year']>10)+tail_value/(1+k)**(p['tail_end']-10)
    result=dict(name=p['name'],parameters=p,rows=rows,value_per_share=equity/p['shares'],equity_value=equity,year5_terminal_per_share=future5/p['shares'],year10_remaining_equity=after10,terminal_pv_fraction=pv_terminal/equity,post_year10_pv_fraction=after10/(1+k)**10/equity,final_tail_value=tail_value,final_extra_cash=max(0.,cash-req),base_case_distributions_per_share=[r['dividend_per_share'] for r in rows[:5]])
    if p['name']=='structural_adverse': result['cash_recovery_boundary']=cash_boundary(result)
    return result

def cash_boundary(r):
    """Conditional economic boundary; not a legal permission or liquidation forecast.
    Beginning with final zero-growth balance, vary realization year of this same lot.
    Remove net income already capitalized; do not recover operating necessary cash.
    """
    p=r['parameters'];z=r['rows'][-1]; ps=p['tail_parent_cash_share']
    parent_needed=z['required_cash']*ps; outside_needed=z['required_cash']*(1-ps)
    parent_extra=max(0.,z['parent_cash']-parent_needed)
    outside_extra=max(0.,z['group_cash']-z['parent_cash']-outside_needed)
    net=parent_extra+outside_extra*(1-p['upstream_friction'])
    annual_income=net*p['cash_yield']*(1-p['tax'])
    cases=[]
    for y in (15,25,40):
        for fraction in (.25,.5,1.):
            receipt=net*fraction; lost=annual_income*fraction
            delta=(receipt-lost/p['k'])/(1+p['k'])**y/p['shares']
            cases.append(dict(realization_year=y,recovery_fraction=fraction,net_receipt=receipt,annual_income_removed=lost,value_delta_per_share=delta,conditional_value_per_share=r['value_per_share']+delta))
    return dict(kind='information_boundary_not_legal_or_liquidation_forecast',business_damage_and_recovery_restriction_independent=True,conditions='Future verification of ownership, distributable legal capacity or other lawful return, creditor protection, taxes and approvals; none asserted to exist.',group_cash=z['group_cash'],required_cash=z['required_cash'],parent_cash=z['parent_cash'],parent_required=parent_needed,parent_extra=parent_extra,nonparent_cash=z['group_cash']-z['parent_cash'],nonparent_required=outside_needed,nonparent_extra=outside_extra,extra_principal=parent_extra+outside_extra,net_recoverable_lot=net,annual_net_income_from_lot=annual_income,cases=cases)

def all_parameters():
    b=params();cases={'base':b}
    def case(name):
        p=copy.deepcopy(b);p['name']=name;cases[name]=p;return p
    p=case('core_low');p.update(k=.1025,g=.02);p['growth'][1]=[x-.02 for x in b['growth'][1]];p['sales']=[x+.003 for x in b['sales']];p['rd']=[x+.005 for x in b['rd']]
    p=case('core_high');p.update(k=.09,g=.025);p['growth'][1]=[x+.02 for x in b['growth'][1]];p['sales']=[x-.003 for x in b['sales']];p['rd']=[x-.005 for x in b['rd']]
    p=case('cyclical_weak');p['growth'][0]=[.02,.04,.07,.12,.11]+b['growth'][0][5:];p['growth'][1]=[.15,.18,.20,.25,.22]+b['growth'][1][5:];p['nwc_ratio']=.30;p['sales']=[x+.01 if i<3 else x for i,x in enumerate(b['sales'])];p['signed_near']=[1.225,3.325]+[0]*8;p['capex']=[2.2,2.2,2.4,3.1,3.3,3.4,3.5,3.5,3.6,3.6]
    p=case('structural_adverse');p.update(k=.11,g=0.,gross=[.82,.83,.73],tail_parent_cash_share=.70,tail_parent_profit_share=.70,nwc_ratio=.30,parent_floor=8.);p['growth']=[[-.04]*3+[0.]*7,[.10,.08,.06,.04,.03,.02,.01,0,0,0],[-.20,-.15,-.10,-.07,-.05,0,0,0,0,0]];p['sales']=ramp(.29,.25);p['admin']=ramp(.085,.075);p['rd']=ramp(.30,.26);p['new_deals']=[x*.35 for x in b['new_deals']];p['milestones']=[x*.40 for x in b['milestones']];p['royalties']=[x*.25 for x in b['royalties']];p['capex']=ramp(1.8,1.4)
    p=case('optimistic');p.update(k=.09,g=.03);p['growth'][0]=[x+.025 for x in b['growth'][0]];p['growth'][1]=[x+.05 for x in b['growth'][1]];p['sales']=ramp(.30,.25);p['rd']=ramp(.34,.27);p['capex']=[x*1.2 for x in b['capex']];p['new_deals']=[x*1.3 for x in b['new_deals']];p['milestones']=[x*1.25 for x in b['milestones']];p['parent_funding']=[2.]*10
    p=case('parent_cash_stress');p.update(parent_cash=20.,parent_cash_share=.60,parent_profit_share=.70,tail_parent_cash_share=.85,tail_parent_profit_share=.85,upstream_start=16);p['parent_extra_payment']=[2.]*5+[0.]*5
    return cases

def sensitivities():
    b=params();d={}
    def put(name,**kw):
        p=copy.deepcopy(b);p.update(kw);p['name']=name;d[name]=p;return p
    for v in (-.01,.01):
        p=put('non_oncology_growth_'+str(v));p['growth'][1]=[x+v for x in b['growth'][1]]
    for v in (-.005,.005): put('research_ratio_'+str(v),rd=[x+v for x in b['rd']])
    put('opening_claim_delayed',accrued_receipt_year=3,deposit_release_year=5);put('opening_claim_all_restricted',accrued_interest=0.,restricted_deposit=b['accrued_interest']+b['restricted_deposit'],deposit_release_year=5);
    put('tax_25pct',tax=.25);put('cash_yield_zero',cash_yield=0.);put('required_cash_double',required_cash=11.64,required_cash_ratio=.4)
    put('no_new_licenses',new_deals=[0.]*10);put('k_plus_100bp',k=.105);put('k_minus_100bp',k=.085)
    put('employee_no_cash',employee_receipt=0.);put('tail_70_years',tail_end=70);put('subsidiary_loss_buffer_zero',subsidiary_loss_buffer=0.);put('subsidiary_loss_buffer_double',subsidiary_loss_buffer=10.)
    put('upstream_friction_10pct',upstream_friction=.10);put('no_future_upstream',upstream_enabled=False);put('return_terminal_low',k=.105,g=.02);put('return_terminal_high',k=.09,g=.025)
    return d

def auxiliary(r):
    """Normalize Y3 economics into a mature earnings-capitalization crosscheck.
    No old deferred revenue in recurring earnings, no arbitrary market multiple.
    Keep actual Y1-3 distributions and SAME full source/payment asset ledger.
    """
    p=r['parameters']; y3=r['rows'][2]; out={}
    for name,g in [('normalized_low',.02),('normalized_high',.025)]:
        q=copy.deepcopy(p);q.update(name=name,g=g,normalize_after_year3=True)
        for j in range(3):q['growth'][j]=p['growth'][j][:3]+[g]*7
        for key in ('sales','admin','rd'):q[key]=p[key][:3]+[p[key][2]]*7
        for key in ('signed_near','milestones','new_deals','royalties'):
            q[key]=p[key][:3]+[p[key][2]*(1+g)**(y-3) for y in range(4,11)]
        rr=simulate(q); ebit=y3['ebit']-y3['opening_license_release']
        capital=y3['fixed_assets']+y3['nwc']+y3['required_cash']
        normal_nopat=ebit*(1-p['tax'])
        cash4=normal_nopat*(1+g)+y3['required_cash']*p['cash_yield']*(1-p['tax'])-g*capital
        # Earnings-capitalization benchmark at t3; necessary cash yield is included,
        # extra financial assets/debt are NOT independently added to holder value.
        multiple=cash4/(p['k']-g)/ebit
        first3=sum(z['dividend']/(1+p['k'])**z['year'] for z in rr['rows'][:3])
        remaining=(rr['equity_value']-first3)*(1+p['k'])**3
        out[name]=dict(result=rr,recurring_ebit_year3=ebit,old_deferred_revenue_excluded=y3['opening_license_release'],normal_capital_year3=capital,normal_nopat_year3=normal_nopat,incremental_roic_proxy=normal_nopat/capital,normal_operating_cash_year4=cash4,earnings_capitalization_multiple=multiple,operating_annuity_value_at_year3=cash4/(p['k']-g),first_three_actual_dividends_pv=first3,remaining_equity_after_payment_constraints_at_year3=remaining,value_per_share=rr['value_per_share'])
    return dict(method='normalized_Y3_full_RnD_earnings_capitalization_with_actual_payment_bridge',cases=out,low=min(x['value_per_share'] for x in out.values()),high=max(x['value_per_share'] for x in out.values()),limitation='Mature product/authorization mix from Y4 versus continued innovation ramp in main case. Same actual-payment, mother/sub legal-budget and financial-principal ledger. Two methods share assumptions, not independent commercial evidence; no unconditional net-asset addback.')

def literal_tests():
    results=[]
    for required in (10.,15.,5.):
        p=params();p.update(name='literal',accrued_interest=0.,restricted_deposit=0.,cash=100.,parent_cash=100.,parent_retained=1000.,parent_registered=1.,parent_reserve=.5,products=[10.,0.,0.],growth=[[0.]*10]*3,gross=[1.,1.,1.],sales=[0.]*10,admin=[0.]*10,rd=[0.]*10,other=0.,signed_near=[0.]*10,milestones=[0.]*10,new_deals=[0.]*10,royalties=[0.]*10,old_license_release=[0.]*10,license_cost=0.,tax=0.,cash_yield=.02,debt=0.,asset_net=0.,fixed=0.,capex=[0.]*10,depreciation_ratio=0.,nwc=0.,nwc_ratio=0.,required_cash=10.,required_cash_ratio=required/10,payout=[0.]*10,parent_cash_share=1.,parent_profit_share=1.,parent_financial_share=1.,debt_parent_share=1.,parent_funding=[0.]*10,parent_extra_payment=[0.]*10,parent_floor=0.,advances=0.,tail_parent_cash_share=1.,tail_parent_profit_share=1.,employee_payment=0.,employee_receipt=0.,employee_non_cash=0.,g=0.,subsidiary_loss_buffer=0.)
        r=simulate(p);first=r['rows'][0]
        assert abs(first['group_cash']-112.)<1e-10 and abs(first['parent_cash']-112.)<1e-10
        assert all(abs(z['group_cash']-z['parent_cash'])<1e-8 for z in r['rows'])
        results.append(dict(required=required,expected=112.,group=first['group_cash'],parent=first['parent_cash']))
    # Reserve threshold and POST-distribution loss must both be enforced.
    retained,res,acc=retained_step(-2.,0.,3.,.1)
    assert abs(acc-.05)<1e-12 and abs(retained-.95)<1e-12
    retained-=.90
    retained,res,acc=retained_step(retained,res,-.20,.1)
    assert abs(retained+.15)<1e-12 and acc==0.
    retained,res,acc=retained_step(retained,res,.10,.1)
    assert retained<0 and acc==0
    return dict(cash_source_cases=results,later_loss_capacity_test='passed',statutory_reserve_cap_test='passed')

def build():
    scenarios={n:simulate(p) for n,p in all_parameters().items()}; sens={n:simulate(p) for n,p in sensitivities().items()}
    convergence={}
    for n,p in all_parameters().items():
        a=copy.deepcopy(p);a['tail_end']=70;b=copy.deepcopy(p);b['tail_end']=110
        r70,r110=simulate(a),simulate(b)
        convergence[n]=dict(value_y50=scenarios[n]['value_per_share'],value_y70=r70['value_per_share'],value_y110=r110['value_per_share'],delta_110_minus_50=r110['value_per_share']-scenarios[n]['value_per_share'],extra_cash_y50=scenarios[n]['final_extra_cash'],extra_cash_y110=r110['final_extra_cash'])
    base=scenarios['base'];term=[sens[n]['year5_terminal_per_share'] for n in ('return_terminal_low','return_terminal_high')]
    return dict(schema_version=1,symbol='CN:600276',period='2026-Q3',information_cutoff=CUTOFF,units='CNY billion except per-share CNY',results=scenarios,sensitivities=sens,tail_convergence=convergence,auxiliary=auxiliary(base),literal_tests=literal_tests(),return_model=dict(schema_version=1,method='annual_common_equity_irr_v1',currency='CNY',model_as_of=CUTOFF,base_case_distributions_per_share=[round(x,4) for x in base['base_case_distributions_per_share']],base_case_terminal_equity_value_range_per_share={'year_5':dict(low=round(min(term),2),high=round(max(term),2))}))

def main():
    a=argparse.ArgumentParser();a.add_argument('--output',type=Path,default=Path(__file__).resolve().with_name('2026-Q3-output.json'));args=a.parse_args()
    out=build();args.output.write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(args.output),'scenarios':{n:r['value_per_share'] for n,r in out['results'].items()},'return_model':out['return_model']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()

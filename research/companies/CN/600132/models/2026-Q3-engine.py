#!/usr/bin/env python3
"""CN600132 independent author model. CNY billion, million kl, billion shares.
No files, third party packages, prices, imported inputs or wall-clock dependence.
Legal reserve, entity budgets and intra-group dividends are forecasts, not certified accounts.
"""
import json,math,sys
SHARES=.483971198
ASOF='2026-10-30T06:54:00+00:00'
PARAMS={
 'base':{},'core_low':{'r':.095},'core_high':{'r':.085},
 'earnings_crosscheck':{'method':'earnings'},
 'cycle':{'cycle':True},'structural':{'structural':True},'upside':{'upside':True},
 'price_minus_3pct':{'price_mult':.97},'royalty_plus_1pct':{'royalty_add':.01},
 'capex_plus_025':{'extra_capex':.25},'low_legal_reserve':{'opening_re':0.0},
 'upstream_delay':{'delay':1},'full_deposit_runoff':{'deposit_runoff':True},
 'associate_no_exit':{'associate_exit':False},'tax_no_extension':{},
 'tax_extension':{'tax_extend':True},'restricted_delay':{'restricted_year':10},
 'liquidity_failure':{'opening_cash':.1,'shock':5.0},
 'lower_nci_3pct':{'minor':.03},'no_october_draw':{'oct_draw':0.0},
 'cash_buffer_15':{'buffer':1.5},'legal_reserve_delayed':{'reserve_cap':.425,'reserve_open':0},
 'deposit_claim_addback':{'deposit_extra_claim':.2970776444},'payout_slow':{'release_rate':.03},'associate_tax_basis_zero':{'associate_basis':0.},'associate_tax_basis_high':{'associate_basis':.12332542929},'financial_holder_lower':{'financial_lower':True}
}

def distribution(cash,re,reserve,cap,profit,minimum,rate=1.0,ceiling=float('inf')):
    """After losses are absorbed, transfer 10% available profit until 50% capital cap.
    cash is before dividend; profit excludes capital recovery; no pooled parent tax shield.
    """
    old_re=re
    re+=profit
    transfer=min(max(0,re),max(0,cap-reserve),max(0,profit+min(0,old_re))*.1)
    reserve+=transfer;re-=transfer
    paid=min(max(0,cash-minimum),max(0,re),max(0,ceiling))*rate
    return cash-paid,re-paid,reserve,paid,transfer

def run(name='base',n=220,override=None):
    p={'r':.09,'method':'volume','price_mult':1.,'royalty_add':0.,'extra_capex':0.,'opening_re':1.8,'delay':0,'associate_exit':True,'restricted_year':3,'minor':.01,'oct_draw':.34516302821,'buffer':1.,'reserve_cap':.425,'reserve_open':.425,'release_rate':.10,'associate_basis':.0114081,'financial_lower':False,**PARAMS.get(name,{}),**(override or {})}
    # Q3 consolidated cash=2.89516302821; source reconciliation and Oct working-capital budget.
    cash=p.get('opening_cash',2.89516302821-p['oct_draw']-.02-.00795815076)
    parent_cash=.02;parent_re=.80582677149;parent_reserve=.241985599
    re=p['opening_re'];reserve=p['reserve_open'];loan=0.;parent_div_receivable=0.
    volume=2.8;price=4800*p['price_mult'];last_rev=13.84
    fixed=4.9;deposits=1.04424142415;allowance=.2970776444;lease=.12024859583
    pension=.08735144659;parent_pension=.053016124;parent_creditors=.07333647892;construction_payable=.20545710942;fund=.50005012521;restricted=.00795815076
    associate=.12332542929;associate_basis=p['associate_basis'];other_equity=.01361546362
    # Deferred assets substantially rotate with rebates/contract liabilities. No added DTA principal:
    # normal cash tax includes ordinary reversal/new origination; separate runoff uses cash deductibility.
    dta=.91187030397;dtl=.00497222420;provision=.10193309855
    rows=[];pv=0.;pv_after5=0.;status='feasible';loss_pool_w=0.;loss_pool_o=0.;entity_losses={}
    west_names=['新疆乌苏','乌苏库尔勒','乌苏伊宁','乌苏阿克苏','乌苏乌苏','昆明华狮']
    normal_names=['湖南','广东','宁夏西夏','江苏','佛山','云南工贸','其他独立盈利法人预算']
    for y in range(1,n+1):
        begin={'cash':cash,'parent_cash':parent_cash,'re':re,'parent_re':parent_re,'reserve':reserve,'lease':lease,'deposits':deposits,'fund':fund,'associate':associate,'restricted':restricted,'other_equity':other_equity,'fixed':fixed,'pension':pension,'parent_pension':parent_pension,'parent_creditors':parent_creditors,'construction_payable':construction_payable,'dta':dta,'dtl':dtl,'provision':provision,'parent_div_receivable':parent_div_receivable,'loan':loan}
        gvol=[0.,.005,.01,.005,.0][y-1] if y<=5 else (0. if y<=10 else -.002)
        gp=.01 if y<=10 else .012
        if p.get('cycle') and y<=3: gvol=[-.08,.015,.04][y-1]
        if p.get('structural'): gvol=-.025 if y<=10 else -.01;gp=.005
        if p.get('upside') and y<=5:gvol=.015;gp=.015
        volume*=1+gvol
        if y>1:price*=1+gp
        revenue=volume*price/1000+.4*(1.01**(y-1))
        if p['method']=='earnings':revenue=13.9*(1.012**(y-1))
        inflation=1.01**(y-1)
        production=revenue*(.47+(min(y-1,4)*-.001))
        jiawei_purchase=.5704 if y<=2 else (.5704/6 if y==3 else 0.)
        replacement_purchase=.5-jiawei_purchase*.5/.5704
        production+=jiawei_purchase+replacement_purchase-.5704
        excise=revenue*.062
        marketing=revenue*(.153-min(y-1,4)*.0005)
        royalty=revenue*(.017+p['royalty_add'])
        overhead=revenue*.034;rd=revenue*.001;credit_loss=revenue*.002
        if p.get('structural'): marketing+=revenue*.015;production+=revenue*.02
        ebitda=revenue-production-excise-marketing-royalty-overhead-rd-credit_loss
        depreciation=fixed*.115
        # Independent earnings entry is AFTER cash rent; add rent once below to construct EBITDA.
        # Operating lease cash fully expensed in both methods, not added to enterprise bridge.
        lease_interest=lease*.04;lease_principal=min(lease,.048*inflation)
        lease_new=lease_principal+lease*.01;lease=lease+lease_new-lease_principal
        lease_expense=lease_principal+lease_interest
        if p['method']=='earnings':ebitda=2.86*(1.012**(y-1))+depreciation+lease_expense
        ebit=ebitda-depreciation-lease_expense
        jiawei_purchase=.5704 if y<=2 else (.5704*2/12 if y==3 else 0.)
        jiawei_volume=.1426 if y<=2 else (.1426*2/12 if y==3 else 0.)
        # gross package procurement is already within production; associated cash distribution is separate.
        associate_profit=.045 if y<=2 else (.045/6 if y==3 else .004*inflation)
        if not associate:associate_profit=0.
        associate_dividend=associate_profit
        associate_exit=0.;associate_exit_profit=0.;associate_exit_tax_gain=0.
        if y==3 and p['associate_exit']:
            associate_exit=associate*.8*.98
            associate_exit_profit=associate_exit-associate
            associate_exit_tax_gain=associate_exit-associate_basis
            # loss does not create tax refund; deductible only against same holder's taxable income below.
            associate=0.
        other_dividend=other_equity*.025
        other_exit=other_exit_gain=0.
        if y==5:
            other_exit=other_equity*.98;other_exit_gain=other_exit-.001;other_equity=0.
        fund_income=fund*.015
        fund_return=fund if y==1 else 0.;fund-=fund_return
        restricted_income=restricted*.01
        restricted_release=restricted if y==p['restricted_year'] else 0.;restricted-=restricted_release
        internal_loan_interest=loan*.03
        interest=cash*.012+internal_loan_interest
        # Forecast earnings allocated to actual tax-rate groups, never cross-offset operating losses.
        west_profit=ebit*.10;ordinary_profit=ebit*.90+fund_income+restricted_income+interest+other_exit_gain+associate_exit_tax_gain
        tax_w=.15 if y<=4 or p.get('tax_extend') else .25
        entity_tax_pools=[]
        entries=[(name,ebit/60,tax_w) for name in west_names]+[(name,ebit*.1,.25) for name in normal_names]+[('嘉士伯重庆直接经营及金融持有',ebit*.2+fund_income+restricted_income+interest+other_exit_gain+associate_exit_tax_gain,.25)]
        financial_taxable=fund_income+restricted_income+interest+other_exit_gain
        if p['financial_lower']:
            entries[-2]=(entries[-2][0],entries[-2][1]+financial_taxable,.25)
            entries[-1]=(entries[-1][0],entries[-1][1]-financial_taxable,.25)
        lower_financial_tax=0.
        for entity,earning,rate in entries:
            oldloss=entity_losses.get(entity,0.);paid=max(0,earning-oldloss)*rate;entity_losses[entity]=max(0,oldloss-earning)
            if p['financial_lower'] and entity==normal_names[-1]:lower_financial_tax=paid-max(0,earning-financial_taxable-oldloss)*rate
            entity_tax_pools.append({'entity':entity,'pretax_profit_budget':earning,'rate':rate,'opening_own_loss':oldloss,'closing_own_loss':entity_losses[entity],'tax':paid})
        west_tax=sum(t['tax'] for t in entity_tax_pools[:6]);ordinary_tax=sum(t['tax'] for t in entity_tax_pools[6:])
        loss_pool_w=sum(entity_losses[k] for k in west_names);loss_pool_o=sum(entity_losses[k] for k in normal_names)+entity_losses['嘉士伯重庆直接经营及金融持有']
        tax=west_tax+ordinary_tax
        # Existing DTA and DTL continue with operating scale: growing temporary differences consume cash.
        pension_payment=min(pension,.008735144659);pension-=pension_payment
        pension_tax_credit=pension_payment*.15
        new_dta=.91187030397*revenue/13.84-(.08735144659-pension)*.15;new_dtl=.00497222420*revenue/13.84
        tax_timing=(new_dta-dta)-(new_dtl-dtl);cash_tax=tax+tax_timing
        if cash_tax<0:raise AssertionError('cash tax refund not supported')
        dta=new_dta;dtl=new_dtl
        net_profit=ebit+fund_income+restricted_income+interest+associate_profit+other_dividend+other_exit_gain+associate_exit_profit-tax
        capex=max(0,depreciation+max(0,revenue-last_rev)*.20+min(0,revenue-last_rev)*.35)+p['extra_capex']*inflation
        if y==3:capex+=.05 # replacement sourcing after contract expiry: line conversion budget
        if p['method']=='earnings':capex=.58*(1.012**(y-1))+p['extra_capex']*inflation
        fixed+=capex-depreciation
        # Operational NWC excludes deposits, deferred tax, and financial assets. Negative NWC grows modestly.
        nwc_change=-.08*(revenue-last_rev)
        deposit_refund=deposits*.20;deposit_new=deposit_refund+deposits*(revenue/last_rev-1)
        if p.get('deposit_runoff') and y<=3:deposit_new=0.
        deposit_new=max(0,deposit_new);deposits+=deposit_new-deposit_refund
        allowance=min(allowance,deposits*.2845) # accounting memorandum only: never reduces face or payout.
        extra_claim=p.get('deposit_extra_claim',0) if y==1 else 0.
        # Pension original liability settled; tax credit is already in deferred-tax movement.
        provision_use=min(provision,.05) if y<=3 else 0.;provision-=provision_use
        # Fulfilment costs are within production. Existing net provision release is noncash profit addback.
        net_profit+=provision_use
        op_cash=ebit+depreciation+interest+fund_income+restricted_income-cash_tax-nwc_change+deposit_new-deposit_refund-pension_payment-extra_claim
        fcf=op_cash-capex+associate_dividend+other_dividend
        construction_paid=construction_payable if y==1 else 0.;construction_payable-=construction_paid
        cash+=fcf+fund_return+restricted_release+associate_exit+other_exit-construction_paid
        if p.get('shock') and y==1:cash-=p['shock']
        cash_before_distributions=cash
        # Jiawei is directly held by Carlsberg Chongqing: NEVER nested minority.
        # 80% operating allocation matches the named lower-entity tax budgets; 20% direct.
        lower_operating_tax=sum(t['tax'] for t in entity_tax_pools[:-1])-lower_financial_tax
        lower_operating_cash=.8*(ebit+depreciation-capex-nwc_change+deposit_new-deposit_refund-pension_payment-extra_claim-construction_paid-tax_timing)-lower_operating_tax
        lower_operating_profit=.8*(ebit+provision_use)-lower_operating_tax
        # Unknown fund/restricted/bank-equity holder budget: direct in base; explicit lower-holder alternative.
        unknown_financial_profit=fund_income+restricted_income+interest+other_dividend+other_exit_gain
        unknown_financial_cash=unknown_financial_profit+fund_return+restricted_release+other_exit-other_exit_gain
        lower_financial_cash=(unknown_financial_cash-lower_financial_tax) if p['financial_lower'] else 0.
        lower_financial_profit=(unknown_financial_profit-lower_financial_tax) if p['financial_lower'] else 0.
        minor=max(0,lower_operating_cash+lower_financial_cash)*p['minor']
        cash-=minor
        lower_minor_profit=(lower_operating_profit+lower_financial_profit)*p['minor']
        legal_profit=net_profit-lower_minor_profit
        minimum=p['buffer']*revenue/13.84
        if cash<0:
            status='funding_failed';rows.append({'year':y,'status':status,'cash_shortfall':-cash,'before':begin,'revenue':revenue,'ebit':ebit,'cash_tax':cash_tax,'capex':capex});break
        cash,re,reserve,sub_div,transfer=distribution(cash,re,reserve,p['reserve_cap'],legal_profit,minimum,ceiling=max(0,legal_profit)*.95+max(0,cash-minimum)*p['release_rate'])
        mother_declared=sub_div*.5142;main_minor=sub_div*.4858
        # Delayed declaration creates a genuine parent receivable and subsidiary cash payable, not extra profit.
        received=parent_div_receivable if p['delay'] else mother_declared
        parent_div_receivable=mother_declared if p['delay'] else 0.
        parent_cost=.057*(revenue/13.84 if p.get('structural') else inflation);parent_interest=parent_cash*.01
        parent_pension_paid=min(parent_pension,.0053016124);parent_pension-=parent_pension_paid
        parent_creditors_paid=parent_creditors if y==1 else 0.;parent_creditors-=parent_creditors_paid
        parent_interest-=internal_loan_interest
        # Parent standalone expenses cannot create subsidiary tax shields. Exempt domestic dividend; no refund.
        parent_tax=max(0,parent_interest-parent_cost)*.25
        parent_profit=mother_declared+parent_interest-parent_cost-parent_tax
        parent_cash+=received+parent_interest-parent_cost-parent_tax-parent_pension_paid-parent_creditors_paid
        # Same-group short bridge only if covered by already declared receivable; face remains tracked.
        loan_new=max(0,.01-parent_cash) if parent_div_receivable>0 else 0.
        if loan_new>cash-minimum:loan_new=max(0,cash-minimum)
        cash-=loan_new;parent_cash+=loan_new;loan+=loan_new
        loan_repaid=min(loan,max(0,parent_cash-.02));loan-=loan_repaid;parent_cash-=loan_repaid;cash+=loan_repaid
        if parent_cash<0:
            status='funding_failed';rows.append({'year':y,'status':status,'parent_cash_shortfall':-parent_cash,'before':begin,'revenue':revenue});break
        parent_cash,parent_re,parent_reserve,common_div,parent_transfer=distribution(parent_cash,parent_re,parent_reserve,.241985599,parent_profit,.02)
        effective_group_cash=cash+parent_cash+parent_div_receivable # accrued sub payable is separately escrowed
        group_cash_before=begin['cash']+begin['parent_cash']+begin['parent_div_receivable']
        external_net=fcf+fund_return+restricted_release+associate_exit+other_exit-construction_paid-minor-main_minor+parent_interest-parent_cost-parent_tax-common_div-parent_pension_paid-parent_creditors_paid
        residual=effective_group_cash-group_cash_before-external_net
        if abs(residual)>1e-7*max(1,effective_group_cash):raise AssertionError(('cash conservation',y,residual))
        if min(cash,parent_cash)<-1e-9:raise AssertionError('negative funded cash')
        value=common_div/SHARES/(1+p['r'])**y;pv+=value
        if y>5:pv_after5+=value
        row=dict(year=y,status='feasible',before=begin,volume=volume,price=price,revenue=revenue,production=production,excise=excise,marketing=marketing,royalty=royalty,overhead=overhead,rd=rd,credit_loss=credit_loss,ebitda=ebitda,depreciation=depreciation,lease_expense=lease_expense,lease_interest=lease_interest,lease_principal=lease_principal,lease_new=lease_new,lease=lease,ebit=ebit,jiawei_purchase_in_production=jiawei_purchase,jiawei_volume=jiawei_volume,associate_profit=associate_profit,associate_dividend=associate_dividend,associate_exit=associate_exit,associate_exit_profit=associate_exit_profit,associate_exit_tax_gain=associate_exit_tax_gain,associate_book_basis_open=begin['associate'],associate_tax_basis_open=associate_basis if begin['associate'] else 0.,associate=associate,associate_tax_basis=associate_basis if associate else 0.,other_dividend=other_dividend,other_exit=other_exit,other_exit_gain=other_exit_gain,other_equity=other_equity,fund_income=fund_income,fund_return=fund_return,fund=fund,restricted_income=restricted_income,restricted_release=restricted_release,restricted=restricted,interest=interest,west_profit=west_profit,ordinary_profit=ordinary_profit,entity_tax_pools=entity_tax_pools,west_tax=west_tax,ordinary_tax=ordinary_tax,loss_pool_w=loss_pool_w,loss_pool_o=loss_pool_o,tax=tax,tax_timing=tax_timing,cash_tax=cash_tax,dta=dta,dtl=dtl,net_profit=net_profit,capex=capex,fixed=fixed,nwc_change=nwc_change,deposits=deposits,deposit_refund=deposit_refund,deposit_new=deposit_new,deposit_allowance_memo=allowance,extra_claim=extra_claim,pension_payment=pension_payment,pension_tax_credit=pension_tax_credit,pension=pension,parent_pension=parent_pension,parent_pension_paid=parent_pension_paid,parent_creditors_paid=parent_creditors_paid,parent_creditors=parent_creditors,construction_paid=construction_paid,construction_payable=construction_payable,replacement_purchase_in_production=replacement_purchase,internal_loan_interest=internal_loan_interest,provision_use=provision_use,provision=provision,op_cash=op_cash,fcf=fcf,cash_before_distributions=cash_before_distributions,lower_operating_cash=lower_operating_cash,lower_operating_profit=lower_operating_profit,lower_financial_cash=lower_financial_cash,lower_financial_profit=lower_financial_profit,lower_financial_tax=lower_financial_tax,lower_minor_profit=lower_minor_profit,lower_minor_paid=minor,main_minor_paid=main_minor,legal_profit=legal_profit,reserve_transfer=transfer,reserve=reserve,sub_re=re,sub_dividend=sub_div,mother_declared=mother_declared,mother_received=received,parent_div_receivable=parent_div_receivable,parent_cost=parent_cost,parent_interest=parent_interest,parent_tax=parent_tax,parent_profit=parent_profit,parent_reserve_transfer=parent_transfer,parent_re=parent_re,parent_reserve=parent_reserve,parent_cash=parent_cash,sub_cash=cash,minimum_cash=minimum,internal_loan_face=loan,internal_loan_new=loan_new,internal_loan_repaid=loan_repaid,common_dividend=common_div,common_dps=common_div/SHARES,shares=SHARES,group_cash=effective_group_cash,cash_residual=residual,discount_rate=p['r'],common_pv=value,cumulative_pv=pv,operating_return=ebit-tax,listed_investment_cost=1.71410396878,listed_investment_impairment=.01903761007)
        rows.append(row);last_rev=revenue
    return {'name':name,'parameters':p,'years_requested':n,'status':status,'rows':rows,'value_per_share':pv if status=='feasible' else None,'future_y5_per_share':pv_after5*(1+p['r'])**5 if status=='feasible' else None,'dps_5':[x.get('common_dps') for x in rows[:5]] if status=='feasible' else None,'tail_common_pv_last_year':rows[-1].get('common_pv')}

def main():
    tests={}
    # Actual production function hand cases and counterexample; not tautological external identities.
    got=distribution(12,2,0,1,4,3)
    assert got==(6.4,0.0,.4,5.6,.4);tests['reserve_hand_case']=list(got)
    got=distribution(12,-5,0,1,4,3)
    assert got==(12,-1,0,0.,0);tests['loss_absorption_counterexample']=list(got)
    got=distribution(1,100,0,0,0,0)
    assert got==(0,99,0,1,0);tests['profit_not_cash']=list(got)
    cases=[run(k) for k in PARAMS]
    tails=[run('base',n) for n in (80,140,300)]
    assert cases[17]['status']=='funding_failed'
    assert abs(tails[-1]['value_per_share']-cases[0]['value_per_share'])<.0001
    print(json.dumps({'identity':{'symbol':'CN:600132','period':'2026-Q3','cutoff':ASOF,'units':'CNY billion; million kl; CNY/share','shares':SHARES},'production_tests':tests,'cases':cases,'tail_extensions':tails},ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()

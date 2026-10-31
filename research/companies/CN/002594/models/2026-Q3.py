#!/usr/bin/env python3
"""BYD common-owner conditional budget, CNY bn. Standalone stdlib deterministic JSON.
Actual opening amounts: Q3 balance sheet except explicitly labelled H1/budget estimates.
Forecast clusters are economic cash-location budgets, not audited legal-entity accounts.
"""
import json

SHARES=9.117197565
AS_OF='2026-10-29T17:00:00+00:00'

def reserve_and_distribution(retained, reserve, profit, capital, requested, cash, minimum):
    """Production legal waterfall: cover losses before reserve; never distribute principal as income."""
    cover=min(max(-retained,0.),max(profit,0.))
    transfer=min(max(capital*.5-reserve,0.),max(profit-cover,0.)*.1)
    balance=retained+profit-transfer
    paid=min(max(balance,0.),max(cash-minimum,0.),max(requested,0.))
    return balance-paid,reserve+transfer,paid,transfer,cover

def opening():
    return dict(cash=29.781533,debt=115.637201,perpetual=17.2,perpetual_book=17.080815,perpetual_interest_payable=.119185,parent_capital_reserve=92.837687,fixed=422.267164,tax_basis=451.502900,
       dta=13.758434,depreciation_dta=6.312805,ppa=2.328289,dtl=1.380716,liquid=40.735441,term=27.558955,
       equity_portfolio=16.255084,associate=22.885172,loan_face=17.207881,loan_allowance=1.5,writtenoff_face=0.,
       restricted=2.06325,commitment=.904067,parent_liquid=6.970914,parent_term=5.389951,parent_equity_portfolio=7.721381,parent_associate=15.,parent_cash=2.,parent_retained=.598253,parent_reserve=2.101579,
       old_dividend_receivable=17.315101,intercompany_face=58.484377,intercompany_allowance=.058484,
       sub_retained=60.,sub_reserve=5.,group_retained=135.207559,nci_equity=12.745717,
       working_capital=[221.577509,56.472621,10.678295,58.410523,172.705053,78.863362,92.946398,101.855743,37.349867,29.758389])

def modeled_net_assets(s):
    return (s['cash']+s['fixed']+sum(s['working_capital'][:4])-sum(s['working_capital'][4:])+
      sum(s[k] for k in ['liquid','term','equity_portfolio','associate','loan_face','restricted','dta','depreciation_dta'])-
      sum(s[k] for k in ['loan_allowance','dtl','debt','perpetual_book','perpetual_interest_payable']))

def step(s,y,volumes,scenario,discount,margin):
    r=dict(year=y,opening_cash=s['cash'],opening_parent_cash=s['parent_cash'])
    v=list(volumes)
    if y>1:
        growth=(.02,.15,.05,.04) if y<=5 else (.01,.07,.03,.025) if y<=10 else (.005,.025,.02,.015) if y<=20 else (0.,)*4
        if scenario=='structural': growth=(-.025,.02,0.,0.) if y<=10 else (0.,)*4
        v=[a*(1+b) for a,b in zip(v,growth)]
    domestic,export,other,electronics=v[0]*105,v[1]*155,v[2],v[3]
    revenue=domestic+export+other+electronics
    if scenario=='capital': revenue=800*1.06**min(y,5)*1.04**max(0,min(y-5,5))*1.015**max(0,min(y-10,10))
    dm,em,om,lm=.045+margin,.08+margin,.06,.015+min(y-1,4)*.0025
    if scenario=='cycle' and y<=3: dm-=.018;em-=.015;revenue*=.9
    if scenario=='structural':dm,em,lm=.005,.025,.005
    if scenario=='upside':dm+=.01;em+=.015
    if y>10:
        fade=min((y-10)/10,1)
        dm,em=dm*(1-fade)+.035*fade,em*(1-fade)+.055*fade
        if scenario=='structural': dm,em=.005,.02
    EBIT=(domestic*dm+export*em+other*om+electronics*lm)*revenue/(domestic+export+other+electronics)
    if scenario=='capital': EBIT=(s['fixed']+max(0,sum(s['working_capital'][:4])-sum(s['working_capital'][4:])))*(.105+min(y-1,4)*.003)
    dep=s['fixed']*.18;taxdep=s['tax_basis']*.16
    target=revenue*(.55 if scenario=='structural' else .52)
    investment=dep+max(-dep*.1,(target-s['fixed'])*.35)
    end={key:s[key] for key in opening()};end['fixed']+=investment-dep;end['tax_basis']+=investment-taxdep
    ratios=[.20,.08,.015,.05,.20,.085,.10,.10,.045,.035]
    if scenario=='structural':ratios=[.28,.11,.015,.05,.15,.04,.07,.08,.06,.035]
    if scenario=='cycle' and y<=3:ratios[0:2]=[.27,.10]
    end['working_capital']=[a+.3*(revenue*b-a) for a,b in zip(s['working_capital'],ratios)]
    nwc=sum(end['working_capital'][:4])-sum(end['working_capital'][4:]);dnwc=nwc-sum(s['working_capital'][:4])+sum(s['working_capital'][4:])
    interest=s['debt']*(.055 if scenario=='structural' else .035);coupon=s['perpetual']*.06
    parent_fi=s['parent_cash']*.015+s['parent_liquid']*.02+s['parent_term']*.02+s['parent_equity_portfolio']*.025+s['parent_associate']*.035
    prior_interest_settled=min(s['perpetual_interest_payable'],coupon)
    end['perpetual_interest_payable']-=prior_interest_settled
    equity_coupon=coupon-prior_interest_settled
    perpetual_expense=equity_coupon if scenario=='perpetual_debt_classification' else 0.;equity_coupon-=perpetual_expense
    fi=sum(s[k]*yield_ for k,yield_ in [('liquid',.02),('term',.02),('equity_portfolio',.025),('associate',.035),('loan_face',.055),('restricted',.02),('cash',.015)])
    principal=s['loan_face']*.2;default=min(s['loan_face']-principal,s['loan_face']*.015);recovery=default*.4
    loss=default-recovery;used_allowance=min(s['loan_allowance'],loss)
    end['loan_face']-=principal+default;end['loan_allowance']-=used_allowance
    allowance_recovery=end['loan_allowance']*principal/s['loan_face'] if s['loan_face'] else 0.
    end['loan_allowance']-=allowance_recovery;end['writtenoff_face']+=loss
    realized_loss=loss-used_allowance-allowance_recovery;proceeds=principal+recovery
    liquid_sale=s['liquid']/(4-y) if y<=3 else 0.
    term_sale=s['term'] if y==3 else 0.
    equity_sale=s['equity_portfolio'] if y==10 else 0.;taxable_gain=max(s['equity_portfolio']-12,0.) if y==10 else 0.
    associate_sale=s['associate'] if y==15 else 0.
    parent_principal=0.
    for pk,gk,sale in [('parent_liquid','liquid',liquid_sale),('parent_term','term',term_sale),('parent_equity_portfolio','equity_portfolio',equity_sale),('parent_associate','associate',associate_sale)]:
        allocated=s[pk]/s[gk]*sale if s[gk] else 0.
        end[pk]-=allocated;parent_principal+=allocated
    for key,sale in [('liquid',liquid_sale),('term',term_sale),('equity_portfolio',equity_sale),('associate',associate_sale)]:end[key]-=sale
    associate_addition=s['commitment'] if y==1 else 0.
    end['associate']+=associate_addition;end['commitment']-=associate_addition
    taxable=EBIT+dep-taxdep+fi-interest-1.5+4+taxable_gain-realized_loss
    coupon_tax_deduction=coupon if scenario=='perpetual_tax_deductible' else 0.
    taxable-=coupon_tax_deduction
    parent_taxable=parent_fi-1.5-interest*.47+taxable_gain*(7.721381/16.255084)-coupon_tax_deduction
    parent_tax=max(parent_taxable,0.)*.20
    sub_taxable=taxable-parent_taxable
    credit=min(s['dta'],max(sub_taxable,0)*.20*.25)
    end['dta']-=credit;cash_tax=parent_tax+max(sub_taxable,0)*.20-credit
    end['ppa']=max(0,s['ppa']-2.328289/5)
    end['dtl']=max(0,s['dtl']-min(s['ppa'],2.328289/5)*(.383811/2.328289))
    if y==10:end['dtl']=0.
    end['depreciation_dta']=max(end['tax_basis']-(end['fixed']-end['ppa']),0.)*.20
    deferred=end['dtl']-s['dtl']-(end['depreciation_dta']-s['depreciation_dta'])
    tax_expense=cash_tax+credit+deferred
    ni=EBIT+fi-interest-1.5+4-realized_loss-tax_expense-perpetual_expense
    fcf=EBIT+fi-interest-1.5+4-cash_tax+dep-investment-dnwc+proceeds+liquid_sale+term_sale+equity_sale+associate_sale-associate_addition-coupon
    end['cash']+=fcf
    nci=(electronics*lm*.8)*.3424+((domestic*dm+other*om)*.8)*.0012
    ncid=min(max(end['cash']-revenue*.035,0.),max(nci,0.)*(.5 if y<=5 else 1.))
    end['cash']-=ncid;end['nci_equity']+=nci-ncid
    minimum=revenue*.035
    scheduled_maturity=min(end['debt'],95.) if scenario=='no_refinance' and y==1 else end['debt']*(32.163067/115.637201)
    rollover=0. if scenario=='no_refinance' else scheduled_maturity
    maturity=scheduled_maturity-rollover
    end['cash']-=maturity;end['debt']-=maturity
    draw=max(minimum-end['cash'],0.)
    r.update(revenue=revenue,ebit=EBIT,domestic_volume_million=v[0],export_volume_million=v[1],domestic_revenue=domestic,export_revenue=export,other_auto_revenue=other,electronics_revenue=electronics,
      rd_cash=revenue*.065,rd_capital=revenue*.008,depreciation=dep,tax_depreciation=taxdep,capex=investment,
      maintenance_capex=dep,growth_capex=investment-dep,nwc=nwc,delta_nwc=dnwc,interest=interest,perpetual_coupon=coupon,
      financial_income=fi,cash_tax=cash_tax,tax_expense=tax_expense,net_income=ni,fcf_before_common=fcf,
      nci_profit=nci,nci_dividend=ncid,financial_principal_received=proceeds,loan_face_default=default,
      loan_face_recovery=recovery,loan_loss=loss,loan_allowance_used=used_allowance,loan_allowance_released=allowance_recovery,legal_loan_face=end['loan_face']+end['writtenoff_face'],liquid_sale=liquid_sale,
      term_sale=term_sale,equity_sale=equity_sale,equity_tax_gain=taxable_gain,associate_sale=associate_sale,associate_addition=associate_addition,
      dta_credit_used=credit,forced_maturity_paid=maturity,finance_needed=draw,scheduled_debt_maturity=scheduled_maturity,gross_debt_rollover_budget=rollover,gross_debt_repayment_budget=scheduled_maturity,parent_maturity_cash=maturity*.47,parent_financial_income=parent_fi,parent_financial_principal=parent_principal,parent_cash_tax=parent_tax,parent_taxable=parent_taxable,subsidiary_taxable=sub_taxable,perpetual_tax_deduction=coupon_tax_deduction,perpetual_equity_distribution=equity_coupon,perpetual_current_interest_expense=perpetual_expense,perpetual_prior_interest_settled=prior_interest_settled)
    if end['debt']+draw>145.637201+1e-8 or (scenario=='no_refinance' and draw>0):
        r.update(end);r.update(distribution=None,pv=None,infeasible=True)
        return r,v,{'year':y,'cash_before_funding':end['cash'],'required_funding':draw}
    end['debt']+=draw;end['cash']+=draw
    repayment=min(end['debt'],max(end['cash']-minimum,0.)*.25) if y>5 else 0.
    end['debt']-=repayment;end['cash']-=repayment
    redemption=min(end['perpetual'],max(end['cash']-minimum,0.)*.20) if y>5 else 0.
    book_redemption=s['perpetual_book']*redemption/s['perpetual'] if s['perpetual'] else 0.
    capital_gap=redemption-book_redemption
    end['perpetual_book']-=book_redemption;end['parent_capital_reserve']-=capital_gap
    end['perpetual']-=redemption;end['cash']-=redemption
    parent_cost=1.5+interest*.47+coupon
    end['parent_cash']+=parent_fi-parent_tax+parent_principal+draw*.47-parent_cost-(repayment+maturity)*.47-redemption
    sub_spare=max(end['cash']-end['parent_cash']-(minimum-1.5),0.)
    receipt=0. if scenario=='receipts_delay' and y<=5 else min(end['old_dividend_receivable'],sub_spare*.12);end['old_dividend_receivable']-=receipt
    internal_repay=0. if scenario=='receipts_delay' and y<=5 else min(end['intercompany_face'],max(sub_spare-receipt,0.)*.15);end['intercompany_face']-=internal_repay
    release=s['intercompany_allowance']*internal_repay/s['intercompany_face'] if s['intercompany_face'] else 0.
    end['intercompany_allowance']-=release
    subprofit=ni-nci+1.5+interest*.47-parent_fi+parent_tax+perpetual_expense
    # Actual subsidiary paid-in capitals/reserves differ; 24bn capacity aggregate is an explicitly constrained budget.
    subret,subreserve,_,subaddition,subcover=reserve_and_distribution(s['sub_retained'],s['sub_reserve'],subprofit,24,0,0,0)
    upstream=min(max(sub_spare-receipt-internal_repay,0.)*.65,max(subret,0.)*.30,
      max(subprofit,0.)*(.20 if y<=5 else .50 if y<=10 else .90)+(max(subret,0.)*.05 if y>10 else 0.))
    if scenario=='upstream_delay':upstream*=.5
    if scenario=='upstream_fast':
        upstream=min(max(sub_spare-receipt-internal_repay,0.)*.80,max(subret,0.)*.40,max(subprofit,0.)*(.30 if y<=5 else .70 if y<=10 else 1.)+(max(subret,0.)*.05 if y>10 else 0.))
    end['sub_retained']=subret-upstream;end['sub_reserve']=subreserve
    withholding=upstream*.25*.05;end['cash']-=withholding
    pprofit=upstream-withholding-1.5-interest*.47+parent_fi-parent_tax+release-perpetual_expense
    end['parent_cash']+=receipt+internal_repay+upstream-withholding
    if end['parent_cash'] < -1e-8:
        r.update(end);r.update(distribution=None,pv=None,infeasible=True)
        return r,v,{'year':y,'parent_cash':end['parent_cash'],'group_cash':end['cash'],'reason':'parent funding gap'}
    desired=max(ni-nci-equity_coupon,0.)*(.10 if y<=5 else .55 if y<=10 else 1.)+(max(end['cash']-minimum,0.)*.10 if y>10 else 0.)
    desired=min(desired,max(end['cash']-minimum,0.))
    pret,preserve,_,paddition,pcover=reserve_and_distribution(s['parent_retained'],s['parent_reserve'],pprofit,SHARES,0,end['parent_cash'],1.5)
    pret-=equity_coupon
    D=min(max(pret,0.),max(end['parent_cash']-1.5,0.),desired)
    pret-=D
    end['parent_retained']=pret;end['parent_reserve']=preserve;end['parent_cash']-=D;end['cash']-=D
    end['group_retained']+=ni-nci-equity_coupon-D
    r.update(end)
    r.update(draw=draw,debt_repaid=repayment,perpetual_redeemed=redemption,old_dividend_received=receipt,
       intercompany_repayment=internal_repay,intercompany_allowance_release=release,sub_profit=subprofit,
       sub_reserve_added=subaddition,sub_loss_covered=subcover,new_upstream=upstream,withholding=withholding,
       parent_profit=pprofit,parent_reserve_added=paddition,parent_loss_covered=pcover,distribution=D,
       per_share=D/SHARES,pv=D/SHARES/(1+discount)**y,subs_cash=end['cash']-end['parent_cash'],minimum_group_cash=minimum,foreign_capex_budget=investment*.20,domestic_and_electronics_capex_budget=investment*.80,foreign_upstream_gross=upstream*.25,domestic_upstream=upstream*.75,
       gross_debt_rollover_budget=rollover,gross_debt_repayment_budget=scheduled_maturity+repayment,parent_debt_cash=(maturity+repayment-draw)*.47,perpetual_book_redeemed=book_redemption,perpetual_capital_adjustment=capital_gap,
       short_debt_budget=end['debt']*(32.163067/115.637201),long_debt_budget=end['debt']*(1-32.163067/115.637201),modeled_net_assets=modeled_net_assets(end))
    # Cash and book-net-assets are different identities, both checked every year.
    r['cash_residual']=end['cash']-(s['cash']+fcf-ncid+draw-maturity-repayment-redemption-withholding-D)
    r['net_asset_residual']=modeled_net_assets(end)-modeled_net_assets(s)-(ni-D-ncid-equity_coupon-withholding-capital_gap)
    assert abs(r['cash_residual'])<1e-7
    assert abs(r['net_asset_residual'])<1e-6,(y,r['net_asset_residual'])
    assert end['parent_cash']>=-1e-8 and r['subs_cash']>=-1e-8
    assert D<=max(s['parent_retained']+pprofit-paddition,0)+1e-8
    assert D<=max(s['parent_retained']+pprofit-paddition-equity_coupon,0)+1e-8
    assert abs(s['debt']-maturity+draw-repayment-end['debt'])<1e-8
    assert abs(end['parent_cash']-(s['parent_cash']+parent_fi-parent_tax+parent_principal+draw*.47-parent_cost-(repayment+maturity)*.47-redemption+receipt+internal_repay+upstream-withholding-D))<1e-7
    for pk,gk in [('parent_liquid','liquid'),('parent_term','term'),('parent_equity_portfolio','equity_portfolio'),('parent_associate','associate')]:assert -1e-8<=end[pk]<=end[gk]+1e-8
    assert end['intercompany_face']>=-1e-8 and end['loan_face']>=-1e-8
    return r,v,None

def run(kind='base',rate=.10,margin=0,years=250,opening_override=None):
    state=opening();state.update(opening_override or {});v=[3.,1.9,80.,160.];rows=[];failure=None
    for year in range(1,years+1):
        state,v,failure=step(state,year,v,kind,rate,margin)
        rows.append(state)
        if failure:break
    successful=[r for r in rows if r.get('distribution') is not None]
    value=sum(r['pv'] for r in successful) if not failure else None
    terminal=sum(r['distribution']/SHARES/(1+rate)**(r['year']-5) for r in successful if r['year']>5) if not failure else None
    return dict(kind=kind,rate=rate,margin=margin,years=years,states=rows,failure=failure,value=value,terminal_y5=terminal,
      distributions=[r['per_share'] for r in successful[:5]],tail_pv_after_y5=(sum(r['pv'] for r in successful if r['year']>5) if not failure else None),
      residual_pv_upper_budget=(rows[-1]['modeled_net_assets']+rows[-1]['distribution']/rate)/SHARES/(1+rate)**years if not failure else None)

def main():
    results={k:run(k) for k in ['base','capital','cycle','structural','upside','upstream_delay','no_refinance']}
    results['core_low']=run('base',.105,-.002);results['core_high']=run('base',.095,.002)
    results['holder_low']=run('base',.105);results['holder_high']=run('base',.095)
    results['tail_extension']=run('base',.10,0,500)
    results['zero_old_sub_reserve']=run('base',opening_override={'sub_retained':0.,'sub_reserve':0.})
    results['receipts_delay']=run('receipts_delay')
    results['upstream_fast']=run('upstream_fast')
    results['perpetual_tax_deductible']=run('perpetual_tax_deductible')
    results['perpetual_debt_classification']=run('perpetual_debt_classification')
    return dict(as_of=AS_OF,units='CNY billion / billion shares',shares=SHARES,opening=opening(),results=results)
if __name__=='__main__': print(json.dumps(main(),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))

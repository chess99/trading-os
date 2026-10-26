#!/usr/bin/env python3
"""EZVIZ 2026Q3. stdlib only. Units CNY million; shares million.
Y1..Y15 rolling years following 2026-10-26, latest balance 2026-09-30.
One economic trajectory per scenario; capital-cost cases reference it losslessly.
"""
import json, math, copy
from pathlib import Path
INPUT={
 'as_of':'2026-10-26T10:00:00+00:00','shares':787.5,
 'segments':['camera','entry','other_hardware','consumer_cloud','developer_cloud'],
 'year1_revenue':[3500.,1300.,500.,600.,850.],
 'growth_2_5':[.05,.13,.03,.08,.15], 'gross_margin':[.42,.49,.25,.72,.72],
 'sales_ratio':.165,'rd_ratio':.145,'admin_ratio':.04,'tax_surcharge_ratio':.01,
 'credit_inventory_loss_ratio':.005,'fx_friction_ratio':.004,'recurring_refund_ratio':.009,
 'cash_tax':.12,'terminal_g':.02,'fade_end_year':15,
 'cost_of_equity':[.105,.095], 'central_cost':.10,
 'group_cash':3968.35261672,'parent_cash':2314.40609369,
 'cash_min_ratio':.10,'parent_cash_min_share':.60,
 'parent_book_equity_budget':4353.21684739,'parent_sub_investment':154.82123591,
 'parent_retained':397.18677070,'parent_reserve':173.85715231,'parent_registered_capital':787.5,
 'subs_retained_budget':1000.,'subs_reserve_budget':30.,'subs_registered_capital_budget':150.,
 'intercompany_loan':1555.79576224,'internal_loan_rate':.03,'parent_internal_tax':.25,'subs_internal_tax':.15,'scheduled_loan_repayment':200.,'dedicated_release_year':3,'distribution_release_start_year':6,'projection_years':61,'intercompany_loan_ceiling':1800.,
 'parent_trade_payable_subs':1346.34428378,'parent_trade_receivable_subs':401.04683020,
 'parent_own_operating_profit_y1':120.,'parent_da_share':.25,'parent_capex_share':.25,'parent_wc_share':.70,
 'sub_upstream_fraction':.70, 'payout_1_5':.55,'payout_later':.80,
 'net_cash_yield':.01, 'debt_cost':.04, 'external_debt_start':21., 'external_debt_limit':500.,
 'lease_and_trustee_obligation':12.46136551,
 'capital_payable_budget':493.40713005,'unbooked_capital_commitment':9.121,
 'capital_pay_schedule':[.60,.40], 'dedicated_cash_start':526.4,
 'book_equity_start':6091.70646697, 'net_ppe_start':2454.79436444,
 'starting_revenue_ttm':6259.14558695, 'da_y1':190.,'maintenance_to_da':1.,
 'growth_capex_ratio_1_5':.15,'growth_capex_ratio_later':.25,'marginal_wc_ratio':.30,
 'inventory_release':[150.,100.],
 'other_financial_asset':5.24429857,
 'parent_q3_bridge_note':'Parent H1 cash 2402.07726144 less entire group H1-to-Q3 cash decrease87.67116775. Parent retained unchanged H1; no unverified Q3 parent profit credited.',
 'entity_note':'Wholly-owned subsidiary pool: opening statutory retained budget1000 of consolidated1999.7707 less latest parent397.1868 residual1602.5839. Remaining602.5839 excludes uncertain Q3 parent profit, intra-group unrealized margins and inaccessible foreign balances. Historical subsidiary dividends200/300m in2024/25 constrain payment ability. Reserve30m budget capped75m. These are conditional estimates, not undisclosed standalone accounts.',
 'capital_payable_note':'Q3 lacks split; full H1 unpaid engineering balance retained as budget despite Q3capex29.962m, so may overstate remaining old payment by at most that payment absent new liabilities; never deducted again in equity bridge.',
}
HISTORY=[
 {'year':2021,'revenue':4237.93565270,'cost':2743.46814887,'net_profit':452.12250601,'recurring_net_profit':398.02577263,'ocf':289.04237968,'cash_capex':377.31521328,'roe':.3888,'rd_ratio':.1157},
 {'year':2022,'revenue':4306.31377813,'cost':2738.09115191,'net_profit':333.48921442,'recurring_net_profit':296.05378543,'ocf':735.55804345,'cash_capex':337.10969302,'roe':.2023,'rd_ratio':.14},
 {'year':2023,'revenue':4841.06562027,'cost':2784.90297430,'net_profit':563.15933935,'recurring_net_profit':553.31412536,'ocf':969.52160482,'cash_capex':790.64149225,'roe':.1116,'rd_ratio':.1509},
 {'year':2024,'revenue':5441.93993951,'cost':3151.70677018,'net_profit':503.92773105,'recurring_net_profit':483.41831342,'ocf':548.38819376,'cash_capex':612.01365300,'roe':.0941,'rd_ratio':.1495},
 {'year':2025,'revenue':5901.16084027,'cost':3293.98066710,'net_profit':566.57694798,'recurring_net_profit':523.70224097,'ocf':1120.37131554,'cash_capex':299.69364736,'roe':.1009,'rd_ratio':.1461}]
ACTUAL_2026={'q1':{'revenue':1412.82506786,'net_profit':182.64844093,'recurring_net_profit':178.20165653,'ocf':-168.11144114},'h1':{'revenue':3007.09084754,'cost':1495.29456660,'net_profit':409.61917966,'recurring_net_profit':400.23472310,'ocf':-59.59486464,'cash_capex':46.48864070,'group_cash':4056.02378447,'parent_cash':2402.07726144,'parent_net_profit':48.64241951,'parent_retained':397.18677070},'q3_ytd':{'revenue':4650.85514641,'cost':2348.36229348,'net_profit':615.95687594,'recurring_net_profit':604.72188965,'ocf':-135.25007656,'cash_capex':76.45062542,'assets':9723.94743074,'liabilities':3632.24096377,'equity':6091.70646697,'inventory':1676.58352426,'receivables':1280.21970007,'cash_equivalents':3968.35261672,'cash_financing':-298.17759553,'cash_investing':-71.47087171,'cash_fx':-9.20635206,'net_change_cash':-514.10489586}}
SCENARIOS={
 'base':{},
 'cyclical':{'revenue_shock':[-.12,-.06,0.],'gm_shock':[-.035,-.02,0.],'inventory_release':[0.,50.,200.],'extra_wc':[250.,100.,-350.]},
 'structural':{'growth_mult':.35,'permanent_gm_shock':-.055,'cash_tax':.15,'wc_ratio':.42,'growth_capex_later':.35,'terminal_g':.01,'inventory_release':[0.,0.],'extra_wc':[300.,100.,0.],'parent_profit_factor':.55},
 'optimistic':{'growth_mult':1.25,'permanent_gm_shock':.012,'cash_tax':.12,'wc_ratio':.30,'inventory_release':[175.,125.]},
 'margin_minus_1pp':{'permanent_gm_shock':-.01},
 'tax_17pct':{'cash_tax':.17},
 'cloud_growth_half':{'cloud_growth_factor':.5},
 'upstream_delay':{'upstream_delay_years':2},
 'parent_extra_settlement':{'parent_settlement':[300.,0.,0.]},
 'no_inventory_release':{'inventory_release':[0.,0.]},
 'maintenance_125pct':{'maintenance_to_da':1.25},
 'zero_opening_sub_retained':{'opening_sub_retained':0.},
 'maximum_opening_sub_retained':{'opening_sub_retained':1602.58389599},
 'upstream_70pct_forever':{'future_upstream_cap':.70},
 'funding_failure':{'revenue_shock':[-.50,-.40,-.30],'gm_shock':[-.25,-.20,-.15],'extra_wc':[5000.]},
}
def statutory(retained,reserve,capital,profit):
    """Losses first; 10% only post-loss profit and only to 50% capital ceiling."""
    post=retained+profit
    covered=max(0.,min(profit,post))
    appropr=min(.1*covered,max(0.,.5*capital-reserve))
    return post-appropr,reserve+appropr,appropr

def operating(prev, year, p, s):
    g=p['terminal_g'] if 'terminal_g' not in s else s['terminal_g']
    if year==1: rev=list(p['year1_revenue'])
    else:
        rev=[]
        for j,(v,initial_growth) in enumerate(zip(prev['segment_unshocked'],p['growth_2_5'])):
            gg=initial_growth*s.get('growth_mult',1.)*(s.get('cloud_growth_factor',1.) if j>=3 else 1.)
            if year>5: gg=g+(gg-g)*max(0.,(p['fade_end_year']-year)/(p['fade_end_year']-5))
            rev.append(v*(1+gg))
    unshocked=rev[:]
    shock=(s.get('revenue_shock',[])+[0.]*year)[year-1]
    rev=[v*(1+shock) for v in rev]
    gmshock=s.get('permanent_gm_shock',0.)+(s.get('gm_shock',[])+[0.]*year)[year-1]
    gp=sum(v*(m+gmshock) for v,m in zip(rev,p['gross_margin']))
    total=sum(rev)
    expense_ratio=sum(p[x] for x in ['sales_ratio','rd_ratio','admin_ratio','tax_surcharge_ratio','credit_inventory_loss_ratio','fx_friction_ratio'])-p['recurring_refund_ratio']
    ebit=gp-total*expense_ratio
    tax=max(0.,ebit)*s.get('cash_tax',p['cash_tax'])
    nopat=ebit-tax
    oldrev=prev['revenue'] if year>1 else p['starting_revenue_ttm']
    dr=total-oldrev
    da=p['da_y1']*total/sum(p['year1_revenue'])
    maintenance=da*s.get('maintenance_to_da',p['maintenance_to_da'])
    growth_ratio=p['growth_capex_ratio_1_5'] if year<=5 else s.get('growth_capex_later',p['growth_capex_ratio_later'])
    growth_capex=max(dr,0.)*growth_ratio
    commitment=p['unbooked_capital_commitment'] if year==1 else 0.
    capex=maintenance+growth_capex+commitment
    release=(s.get('inventory_release',p['inventory_release'])+[0.]*year)[year-1]
    extra=(s.get('extra_wc',[])+[0.]*year)[year-1]
    dwc=dr*s.get('wc_ratio',p['marginal_wc_ratio'])-release+extra
    oldpay=p['capital_payable_budget']*p['capital_pay_schedule'][year-1] if year<=2 else 0.
    oldcashmin=prev['cash_min'] if year>1 else p['cash_min_ratio']*p['starting_revenue_ttm']
    cashmin=p['cash_min_ratio']*total
    fcf=nopat+da-capex-dwc-oldpay
    return {'year':year,'segment_unshocked':unshocked,'segment_revenue':rev,'revenue':total,'gross_profit':gp,'ebit':ebit,'cash_tax':tax,'nopat':nopat,'da':da,'maintenance':maintenance,'growth_capex':growth_capex,'new_commitment_capex':commitment,'capex':capex,'dwc':dwc,'inventory_release':release,'old_capital_payment':oldpay,'cash_min':cashmin,'operating_cash_interest':oldcashmin*p['net_cash_yield'],'economic_fcf':fcf-(cashmin-oldcashmin)+oldcashmin*p['net_cash_yield'],'cash_fcf':fcf}

def trajectory(p,s,years=None):
    years=p['projection_years'] if years is None else years
    pc=p['parent_cash']; sc=p['group_cash']-pc
    pre=p['parent_retained']; prs=p['parent_reserve']; sre=s.get('opening_sub_retained',p['subs_retained_budget']); srs=p['subs_reserve_budget']
    peq=p['parent_book_equity_budget']; seq=p['book_equity_start']-peq+p['parent_sub_investment']
    debt=p['external_debt_start']; loan=p['intercompany_loan']; eq=p['book_equity_start']; prev={}; rows=[]
    ppe=p['net_ppe_start']; remaining_capital=p['capital_payable_budget']; net_other=eq-p['group_cash']+debt+p['lease_and_trustee_obligation']+remaining_capital-ppe
    for y in range(1,years+1):
        r=operating(prev,y,p,s); opening_cash=pc+sc; opening_eq=eq; opening_debt=debt; opening_loan=loan
        pi=max(pc,0.)*p['net_cash_yield']; si=max(sc,0.)*p['net_cash_yield']; interest=debt*p['debt_cost']
        parentop=p['parent_own_operating_profit_y1']*r['revenue']/sum(p['year1_revenue'])*s.get('parent_profit_factor',1.)
        # Losses first fall at parent until direct margin is exhausted, then the subs pool.
        if r['nopat']<parentop: parentop=min(parentop,r['nopat']*.20)
        subop=r['nopat']-parentop
        loan_interest=loan*p['internal_loan_rate']
        parent_loan_net=loan_interest*(1-p['parent_internal_tax'])
        sub_loan_net=loan_interest-min(loan_interest,max(subop,0.)/(1-p['subs_internal_tax']))*p['subs_internal_tax']
        loan_tax_wedge=sub_loan_net-parent_loan_net
        financial_asset_collection=p['other_financial_asset'] if y==1 else 0.
        settlement=(s.get('parent_settlement',[])+[0.]*y)[y-1]
        parentcf=parentop+pi+parent_loan_net+financial_asset_collection+p['parent_da_share']*r['da']-p['parent_capex_share']*(r['capex']+r['old_capital_payment'])-p['parent_wc_share']*r['dwc']-settlement
        subcf=r['cash_fcf']+pi+si-interest-loan_tax_wedge+financial_asset_collection-parentcf
        pc+=parentcf; sc+=subcf
        # Internal ordinary trades maintain disclosed gross claims (no legal netting); extra settlement goes to subs.
        # Loan is a payable of subs, not equity, so statutory capital and reserve ceiling never change.
        pmin=r['cash_min']*p['parent_cash_min_share']+p['lease_and_trustee_obligation']; smin=r['cash_min']*(1-p['parent_cash_min_share'])
        dedicated=max(0.,p['dedicated_cash_start']-sum(x['old_capital_payment'] for x in rows)-r['old_capital_payment']-p['unbooked_capital_commitment'])
        if y>=p['dedicated_release_year']: dedicated=0.
        funding_smin=smin+dedicated
        newloan=0.; repayment=0.; external=0.
        if sc<funding_smin:
            newloan=min(funding_smin-sc,max(0.,pc-pmin),max(0.,p['intercompany_loan_ceiling']-loan)); pc-=newloan; sc+=newloan; loan+=newloan
        if pc<pmin and loan>0:
            repayment=min(pmin-pc,loan,max(0.,sc-funding_smin)); pc+=repayment; sc-=repayment; loan-=repayment
        if pc<pmin or sc<funding_smin:
            need=max(0.,pmin-pc)+max(0.,funding_smin-sc)
            external=min(need,p['external_debt_limit']-debt)
            pcadd=min(external,max(0.,pmin-pc)); pc+=pcadd; sc+=external-pcadd; debt+=external
            if need-external>1e-7:
                return {'feasible':False,'failure_year':y,'unfunded_cash_even_zero_dividend':need-external,'debt':debt,'rows':rows,'failed_operating_row':r}
        # Scheduled repayment of real intra-group debt: cash transfer only, no parent profit.
        planned_repay=min(p['scheduled_loan_repayment'],loan,max(0.,sc-funding_smin))
        pc+=planned_repay; sc-=planned_repay; loan-=planned_repay; repayment+=planned_repay
        snet=subop+si-interest-sub_loan_net
        sre,srs,sa=statutory(sre,srs,p['subs_registered_capital_budget'],snet)
        upstream_desired=max(snet,0.)*p['sub_upstream_fraction'] if y>s.get('upstream_delay_years',0) else 0.
        if y>=p['distribution_release_start_year'] and y>s.get('upstream_delay_years',0):
            upstream_desired=max(sre,0.) if 'future_upstream_cap' not in s else max(snet,0.)*s['future_upstream_cap']

        # Whole dedicated balance reserved at subsidiary pool: conservative location assumption.
        upstream=min(upstream_desired,max(sre,0.),max(0.,sc-smin-dedicated))
        sre-=upstream; sc-=upstream; pc+=upstream
        pnet=parentop+pi+parent_loan_net+upstream
        pre,prs,pa=statutory(pre,prs,p['parent_registered_capital'],pnet)
        ni=r['nopat']+pi+si-interest-loan_tax_wedge
        ordinary_desired=max(ni,0.)*p['payout_1_5']
        if y>=p['distribution_release_start_year']:
            prior_min=prev['cash_min'] if y>1 else p['cash_min_ratio']*p['starting_revenue_ttm']
            ordinary_desired=max(0.,r['cash_fcf']-(r['cash_min']-prior_min)+pi+si-interest-loan_tax_wedge)
        ordinary_dividend=min(ordinary_desired,max(pre,0.),max(0.,pc-pmin))
        pre-=ordinary_dividend; pc-=ordinary_dividend
        # Exactly the remaining same statutory ledger, not a second allowance based on the same profit.
        additional_dividend=0.
        if y>=p['distribution_release_start_year']:
            additional_dividend=min(max(pre,0.),max(0.,pc-pmin))
            pre-=additional_dividend; pc-=additional_dividend
        desired=ordinary_desired
        dividend=ordinary_dividend+additional_dividend
        # Repay remaining subsidiary cash debt; no new borrowing finances shareholder dividends.
        repay=min(debt,max(0.,sc-smin-dedicated)); sc-=repay; debt-=repay
        eq+=ni-dividend
        peq+=pnet-dividend; seq+=snet-upstream
        assert abs(peq+seq-p['parent_sub_investment']-eq)<1e-6
        ppe+=r['capex']-r['da']; remaining_capital-=r['old_capital_payment']; net_other+=r['dwc']-financial_asset_collection
        residual=(pc+sc)-debt-p['lease_and_trustee_obligation']-remaining_capital+ppe+net_other-eq
        cashres=(pc+sc)-(opening_cash+r['cash_fcf']+pi+si-interest-loan_tax_wedge+financial_asset_collection+external-repay-dividend)
        assert abs(residual)<1e-6 and abs(cashres)<1e-6
        assert pre>=-1e-7 or dividend==0
        assert sre>=-1e-7 or upstream==0
        assert dividend<=max(0,pre+dividend)+1e-8 and pc>=pmin-1e-6 and sc>=funding_smin-1e-6
        r.update({'parent_book_equity_budget':peq,'subs_book_equity_budget':seq,'parent_sub_investment':p['parent_sub_investment'],'parent_operating_profit':parentop,'subs_operating_profit':subop,'parent_cash_interest':pi,'subs_cash_interest':si,'debt_interest':interest,'parent_net_profit_with_new_dividend':pnet,'subs_net_profit':snet,'group_net_profit':ni,'ordinary_dividend':ordinary_dividend,'additional_principal_release_dividend':additional_dividend,'internal_loan_interest_gross':loan_interest,'parent_internal_loan_interest_after_tax':parent_loan_net,'subs_internal_loan_cost_after_tax':sub_loan_net,'internal_interest_tax_wedge':loan_tax_wedge,'financial_asset_collection_no_profit':financial_asset_collection,'upstream_dividend_declared_and_collected':upstream,'old_dividend_receivable_collection':0.,'parent_reserve_addition':pa,'subs_reserve_addition':sa,'parent_retained':pre,'parent_reserve':prs,'subs_retained_budget':sre,'subs_reserve_budget':srs,'parent_cash':pc,'subs_cash':sc,'group_cash':pc+sc,'cash_dividend':dividend,'distribution_per_share':dividend/p['shares'],'desired_distribution':desired,'dividend_cut':desired-ordinary_dividend,'new_internal_loan':newloan,'internal_loan_repayment':repayment,'internal_loan_balance':loan,'external_borrowing':external,'debt_repaid':repay,'external_debt':debt,'dedicated_cash_remaining':dedicated,'capital_payable_remaining':remaining_capital,'net_ppe':ppe,'net_other_operating_assets':net_other,'book_equity':eq,'cash_reconciliation_error':cashres,'equity_reconciliation_error':residual,'shares':p['shares'],'parent_trade_net_extra_payment':settlement})
        rows.append(r); prev=r
    return {'feasible':True,'rows':rows}

def value(p,t,k,s):
    if not t['feasible']: return None
    rows=t['rows'];r5=rows[4];g=s.get('terminal_g',p['terminal_g']); end=len(rows)-1
    # Mature legal cash chain is closed: loans gone, reserves capped, no extra principal,
    # cash at operating minimum plus provision for contractual obligation. Only that
    # constant liability-matching cash interest is non-growing.
    constant=p['lease_and_trustee_obligation']*p['net_cash_yield']
    tailready=all(abs(r['additional_principal_release_dividend'])<1e-6 and r['external_debt']<1e-6 and r['internal_loan_balance']<1e-6 and abs(r['group_cash']-r['cash_min']-p['lease_and_trustee_obligation'])<1e-5 and r['dividend_cut']<1e-6 for r in rows[-5:])
    # A persistently constrained upstream policy is diagnosed, never silently capitalized.
    if not tailready:
        return {'unresolved_terminal_constraint':True,'discounted_actual_distributions_lower_bound_per_share':sum(r['cash_dividend']/(1+k)**r['year'] for r in rows)/p['shares'],'undistributed_end_cash':rows[-1]['group_cash'],'ending_parent_retained':rows[-1]['parent_retained'],'ending_subs_retained':rows[-1]['subs_retained_budget']}
    for a,b in zip(rows[-4:],rows[-5:-1]):
        assert abs((a['cash_dividend']-constant)/(b['cash_dividend']-constant)-(1+g))<1e-9
    terminal=(rows[-1]['cash_dividend']-constant)/(k-g)+constant/k
    pv5=sum(r['cash_dividend']/(1+k)**(r['year']-5) for r in rows[5:-1])+terminal/(1+k)**(end-5)
    pvdiv=sum(r['cash_dividend']/(1+k)**r['year'] for r in rows[:5])
    total=pvdiv+pv5/(1+k)**5
    # Financial-property comparator: same operating state, but ignores release timing.
    fade=p['fade_end_year']
    op5=sum(rows[y-1]['economic_fcf']/(1+k)**(y-5) for y in range(6,fade+1))+rows[fade]['economic_fcf']/(k-g)/(1+k)**(fade-5)
    fin5=r5['group_cash']-r5['cash_min']-r5['external_debt']-p['lease_and_trustee_obligation']-r5['capital_payable_remaining']
    property_value=(pvdiv+(op5+fin5)/(1+k)**5)/p['shares']
    ep=(rows[0]['nopat']+rows[0]['da']-rows[0]['maintenance']+p['cash_min_ratio']*p['starting_revenue_ttm']*p['net_cash_yield'])/k
    cash0=p['group_cash']-p['cash_min_ratio']*p['starting_revenue_ttm']-p['external_debt_start']-p['lease_and_trustee_obligation']+p['other_financial_asset']-p['capital_payable_budget']-p['unbooked_capital_commitment']
    release=[{'year':r['year'],'additional_dividend':r['additional_principal_release_dividend'],'parent_retained_after_all_dividends':r['parent_retained'],'subs_retained_after_upstream':r['subs_retained_budget'],'cash_excess_after_distributions':r['group_cash']-r['cash_min']-p['lease_and_trustee_obligation']} for r in rows[5:] if r['additional_principal_release_dividend']>1e-6]
    return {'cost_of_equity':k,'value_per_share':total/p['shares'],'terminal_year5_per_share':pv5/p['shares'],'pv_year1_5_dividends':pvdiv,'pv_tv5':pv5/(1+k)**5,'tv5_contribution':(total-pvdiv)/total,'actual_distributions_pv_after_year15':(sum(r['cash_dividend']/(1+k)**r['year'] for r in rows[15:-1])+terminal/(1+k)**end),'mature_earnings_power_per_share':(ep+cash0)/p['shares'],'earnings_power_operating_value':ep,'earnings_power_financial_bridge':cash0,'property_comparator_value_per_share':property_value,'property_comparator_tv5_per_share':(op5+fin5)/p['shares'],'property_comparator_net_financial_year5':fin5,'principal_release_years':release,'all_financial_excess_released_by_year':max([z['year'] for z in release],default=5),'tail_start_year':end+1,'terminal_cash_closed':tailready,'remaining_gross_cash_matched_to_obligation':p['lease_and_trustee_obligation'],'net_unreleased_financial_principal':0.}

def tests():
    # Formal statutory function hand cases: recover loss first, reserve cap, loss carry.
    assert statutory(-20.,5.,100.,30.)==(9.,6.,1.)
    assert statutory(0.,49.,100.,30.)==(29.,50.,1.)
    assert statutory(-20.,0.,100.,10.)==(-10.,0.,0.)
    # Formal operating chain: gross100, expenses0, tax0, flat revenue, DA10/capex10 =>100FCF.
    p=copy.deepcopy(INPUT); p.update(year1_revenue=[100,0,0,0,0],gross_margin=[1,0,0,0,0],starting_revenue_ttm=100.,cash_tax=0.,net_cash_yield=0.,da_y1=10.,capital_payable_budget=0.,unbooked_capital_commitment=0.,inventory_release=[0,0])
    for k in ['sales_ratio','rd_ratio','admin_ratio','tax_surcharge_ratio','credit_inventory_loss_ratio','fx_friction_ratio','recurring_refund_ratio']:p[k]=0.
    o=operating({},1,p,{})
    assert o['nopat']==100. and o['cash_fcf']==100. and o['economic_fcf']==100.
    # Formal end-to-end entity/cash chain: parent40, sub60, 10% reserves,
    # sub pays42; parent82 legally keeps73.8 and distributes55; group NI100, cash245.
    p.update(group_cash=200.,parent_cash=100.,parent_retained=0.,parent_reserve=0.,parent_registered_capital=100.,subs_retained_budget=0.,subs_reserve_budget=0.,subs_registered_capital_budget=100.,parent_own_operating_profit_y1=40.,net_cash_yield=0.,external_debt_start=0.,lease_and_trustee_obligation=0.,dedicated_cash_start=0.,book_equity_start=300.,net_ppe_start=100.,intercompany_loan=0.,other_financial_asset=0.,internal_loan_rate=0.)
    z=trajectory(p,{},1)['rows'][0]
    for field,expected in {'group_net_profit':100.,'group_cash':245.,'cash_dividend':55.,'upstream_dividend_declared_and_collected':42.,'parent_retained':18.8,'subs_retained_budget':12.,'parent_reserve':8.2,'subs_reserve_budget':6.}.items():
        assert abs(z[field]-expected)<1e-8,(field,z[field])
    # Same legal ledger hand case: sub54, parent94 less reserve9.4 =>84.6;
    # ordinary request100 must use the same84.6 allowance before any extra release.
    p['distribution_release_start_year']=1
    z=trajectory(p,{},1)['rows'][0]
    # The ordinary request becomes100; it consumes all84.6, leaving zero extra.
    assert abs(z['cash_dividend']-84.6)<1e-8 and z['additional_principal_release_dividend']==0.
    assert abs(z['parent_retained'])<1e-8 and abs(z['group_cash']-215.4)<1e-8
    p['distribution_release_start_year']=6
    p.update(intercompany_loan=100.,internal_loan_rate=.03,group_cash=2000.,parent_cash=1000.)
    z=trajectory(p,{},1)['rows'][0]
    assert abs(z['internal_loan_interest_gross']-3.)<1e-8
    assert abs(z['internal_interest_tax_wedge']-.3)<1e-8
    assert abs(z['group_net_profit']-99.7)<1e-8 and z['internal_loan_balance']==0.
    assert abs(z['cash_dividend']-54.835)<1e-8
    # Exact steady perpetuity closure vs explicit 200 annual terms (not valuation trajectory duplication).
    k=.10;g=.02; cf=100.; finite=sum(cf*(1+g)**(i-1)/(1+k)**i for i in range(1,201))
    tail=cf*(1+g)**200/(k-g)/(1+k)**200
    assert abs(finite+tail-cf/(k-g))<1e-8
    steady=trajectory(INPUT,{},17)['rows']
    assert abs(steady[16]['economic_fcf']/steady[15]['economic_fcf']-1.02)<1e-12
    for a,b in zip(steady[15:],steady[14:]):
        delta=a['revenue']-b['revenue']
        assert abs(a['capex']-a['da']+a['dwc']+a['cash_min']-b['cash_min']-.65*delta)<1e-8
    return {'statutory_loss_and_cap_hand_cases':'passed','formal_operating_hand_case':'passed','formal_full_entity_hand_case':'passed','same_legal_ledger_and_loan_tax_hand_cases':'passed','steady_reinvestment_perpetuity_closure':'passed'}

def main():
    out={'units':'CNY million except per-share CNY, shares million','inputs':INPUT,'historical_financials':HISTORY,'actual_2026':ACTUAL_2026,'scenario_overrides':SCENARIOS,'tests':tests(),'scenarios':{}}
    for name,s in SCENARIOS.items():
        t=trajectory(INPUT,s); vals=[value(INPUT,t,k,s) for k in INPUT['cost_of_equity']]
        out['scenarios'][name]={'trajectory':t,'valuation_endpoints':vals,'central':value(INPUT,t,INPUT['central_cost'],s)}
    assert not out['scenarios']['funding_failure']['trajectory']['feasible']
    # Independent diagnostics no future principal or internal dividends credited to group earnings.
    p=INPUT; b=out['scenarios']['base']; r=b['trajectory']['rows']
    out['base_return_model']={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':p['as_of'],'base_case_distributions_per_share':[round(x['distribution_per_share'],6) for x in r[:5]],'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':round(b['valuation_endpoints'][0]['terminal_year5_per_share'],4),'high':round(b['valuation_endpoints'][1]['terminal_year5_per_share'],4)}}}
    out['base_incremental_return_Y1_Y5']=(r[4]['nopat']-r[0]['nopat'])/((r[4]['net_ppe']+r[4]['net_other_operating_assets']+r[4]['cash_min'])-(r[0]['net_ppe']+r[0]['net_other_operating_assets']+r[0]['cash_min']))
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')
    print(json.dumps({n: {'feasible':x['trajectory']['feasible'],'value':x['central']} for n,x in out['scenarios'].items()},ensure_ascii=False,indent=2))
if __name__=='__main__':main()

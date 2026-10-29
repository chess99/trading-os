#!/usr/bin/env python3
"""APT medical 2026Q3. stdlib, self-contained, all currency CNY millions.
No price/IRR input. Report evidence and budgets are separate; legal stocks below are
aggregate budgeting proxies, never representations of undisclosed subsidiary ledgers.
"""
import copy,json,math
ASOF='2026-10-29T00:00:00+00:00'
NAMES=['parent','apt','shanghai','yiweidi','haoying']
DIRECT=[1.,1.,1.,.533859,.119048]
FUND=[0.,0.,0.,.192207,.515774]
OWN=[a+b for a,b in zip(DIRECT,FUND)] # economic residual BEFORE fund priority, not look-through capital percentage
SHARES=141.529162
TREASURY=2.301876
# Actual H1 financials, Q3 budget opening parent/major sub legal stocks; total cash Q3 actual.
def initial(parent_re=90.,apt_re=2000.,loan=800.):
    cash=[160.,1430.,140.,50.,9.03133583]
    # sum equals Q3 cash+trading securities; no second add-on of financial principal.
    fixed=[210.,530.,500.,45.,25.]
    wc=[30.,410.,15.,25.,7.]
    re=[parent_re,apt_re,-790.,30.,-30.]
    reserve=[53.22155367,5.,0.,10.,0.]
    cap=[141.529162,10.,26.548213,40.13537,2.1]
    s={'year':0,'entities':{},'internal_debt':loan,'dividend_receivable':0.,
       'restricted_cash':18.44325524,'lease_debt':11.99033801,
       'portfolio_book':184.25972308,
       'sub_investment_cost':{'apt':54.301306,'shanghai':1369.429922,'yiweidi':79.97148,'haoying':15.,'fund':35.,'other':2.75882454},'support_claims':{n:0. for n in NAMES[1:]},'support_allowances':{n:0. for n in NAMES[1:]},'support_net_recoverable':{n:0. for n in NAMES[1:]},'sub_investment_allowances':{n:0. for n in NAMES[1:]},'fund':{'cash':0.,'retained':0.,'other_lp_principal':49.,'preferred_due':0.,'parent_capital':35.,'closed':False,'investment_cost':{'yiweidi':20.,'haoying':64.},'investment_allowances':{'yiweidi':0.,'haoying':0.}},'shares':SHARES,'treasury':TREASURY,'inventory_book':549.97637012,'parent_share_premium':1419.84990158,
       'direct_fractions':DIRECT[:],'fund_fractions':FUND[:],'cumulative_dividend_ps':0.,'product_revenues':[1610.,730.,550.,50.,134.50211962],
       'aux_profit':980.,'aux_capital':1797.,'calendar_revenues':{'2025':2583.92732109,'2026':3200.},
       'construction_remaining':550.,'operating_accruals_stock':275.76719316,'cumulative_external_finance':0.,'sbc_accumulated':0.,'cumulative_vested':0.}
    for i,n in enumerate(NAMES):s['entities'][n]={'cash':cash[i],'fixed':fixed[i],'wc':wc[i],'retained':re[i],'reserve':reserve[i],'registered_capital':cap[i],'returnable_paid_in_budget':[0.,45.,1350.,80.,15.][i],'support_debt':0.,'external_debt':31. if n=='haoying' else 0.,'closed':False,'settlement_status':'operating','liquidation_net_assets':None}
    return s

def reserve_profit(e,profit):
    # Loss offset BEFORE reserve appropriation. No reserve withdrawal in budget.
    taxable=max(0.,profit+min(0.,e['retained']))
    appropriation=min(max(0.,.5*e['registered_capital']-e['reserve']),.1*taxable)
    e['retained']+=profit-appropriation;e['reserve']+=appropriation
    return appropriation

def legal_payment(e,wanted,buffer):
    paid=max(0.,min(wanted,e['retained'],e['cash']-buffer))
    e['cash']-=paid;e['retained']-=paid
    return paid

def growth_rates(year,c):
    g=[.15,.22,.18,.10,.00]
    factor=(1-.10*(year-1)) if year<=5 else .6*max(0.,(16-year)/11)
    g=[x*factor for x in g]
    if c.get('structural'):
        g=[.04,.02,.05,.02,0.] if year<=5 else [x*max(0.,(16-year)/10) for x in [.04,.02,.05,.02,0.]]
    if c.get('optimistic'):g=[x*1.15 for x in g]
    if c.get('cycle') and year<=2:g=[-.04,0.,-.03,-.03,-.05]
    if c.get('cycle') and year in (3,4):g=[x+0.04 for x in g]
    return [x*c.get('growth_scale',1.) for x in g]

def operating(s,c):
    y=s['year']+1
    if 'manual_operating' in c:
        z=c['manual_operating'];return z[0],z[1],z[2],z[3],{'hand_fixture':True}
    if c.get('engine')=='historical_return':
        rate=max(0.,.55*(16-y)/15) if y<=15 else 0.
        roic=c.get('incremental_roic',.30)
        invest=s['aux_profit']*rate
        erosion=.01 if y>5 and y<=20 else 0.
        profit=s['aux_profit']*(1-erosion)+invest*roic
        s['aux_profit']=profit;s['aux_capital']+=invest
        r=profit/.32
        fixed_target=s['aux_capital']*.8;wc_target=s['aux_capital']*.2
        detail={'normalized_profit_start':c.get('normal_profit',980.),'reinvestment_fraction':rate,'incremental_roic':roic,'growth_investment':invest,'erosion':erosion}
    else:
        s['product_revenues']=[v*(1+g) for v,g in zip(s['product_revenues'],growth_rates(y,c))]
        r=sum(s['product_revenues'])
        margin=.342-.042*min(1.,max(0.,y-3)/17)
        if c.get('structural'):margin=.26-.035*min(1.,y/10)
        if c.get('cycle') and y<=2:margin-=.045
        if c.get('optimistic'):margin+=.008
        margin+=c.get('margin_delta',0.)
        profit=r*margin
        # PPE incl intangibles; existing building capacity and land already in opening.
        fixed_target=max(1310.,r*.34*c.get('capital_scale',1.))
        wc_target=r*.16*c.get('capital_scale',1.)
        detail={'products':s['product_revenues'][:],'tax_after_margin':margin,'rd_fraction':.135,'sales_fraction_budget':.16,'tax_rate_budget':.15}
    s['calendar_revenues'][str(2026+y)]=r # fiscal approximation explicitly budgeted
    # Separate legal profit engines anchored in actual H1; main group profit reconciled by residual Apt.
    parent=r*.030
    sh=-60.*max(0.,(6-y)/5) if y<=5 else r*.012*min(1.,(y-5)/5)
    yi=-8.*max(0.,(4-y)/3) if y<=3 else r*.004
    hao=-20.*max(0.,(6-y)/5) if y<=5 else r*.002
    if c.get('structural'):
        sh=-65.*max(0.,(6-y)/5) if y<=5 else r*.004
        yi=-10. if y<=3 else r*.001
        hao=-22. if y<=2 else 0.
    p=[parent,profit-parent-sh-yi-hao,sh,yi,hao]
    return r,p,fixed_target,wc_target,detail

def step(s,c):
    s=copy.deepcopy(s);y=s['year']+1
    direct=s['direct_fractions'];via=s['fund_fractions'];ownership=[a+b for a,b in zip(direct,via)]
    opening_cash=sum(e['cash'] for e in s['entities'].values())+s['fund']['cash']
    r,profits,ft,wt,detail=operating(s,c)
    construction=min(s['construction_remaining'],[200.,200.][y-1] if y<=2 else s['construction_remaining'])
    s['construction_remaining']-=construction
    weights=[.12,.60,.24,.03,.01]
    ledger={'year':y,'revenue':r,'operating':detail,'entities':{},'construction':construction}
    external_in=external_out=0.;group_profit=sum(profits);group_capex=0.;group_dep=0.;group_dwc=0.
    sbc=[11.4069,7.0285,4.4162,1.008][y-1] if y<=4 else 0.
    # Budget gross grant expense; reverse when forecast original award expires unmet.
    if y==5:sbc=-s['sbc_accumulated']*max(0.,1-s['cumulative_vested']/1.780501)
    if 'manual_operating' in c:sbc=0.
    s['sbc_accumulated']+=sbc
    group_sbc=0.
    # Interest on actual opening liquid principal, not separately capitalized.
    for i,n in enumerate(NAMES):
        e=s['entities'][n]
        if e['closed']:profits[i]=0.
        interest=max(0.,e['cash'])*c.get('cash_yield',.012) # after tax cash yield budget
        entity_sbc=sbc*weights[i]
        profit=profits[i]+interest-entity_sbc
        dep=e['fixed']*.08
        target=ft*weights[i]
        growth=(detail['growth_investment']*.8*weights[i]) if c.get('engine')=='historical_return' else max(0.,target-e['fixed'])
        # All committed construction is paid, capitalized and depreciated; not thrown into terminal.
        capex=dep+growth+construction*([.1,.2,.7,0.,0.][i])
        if e['closed']:dep=0.;capex=0.
        wcnew=(e['wc']+detail['growth_investment']*.2*weights[i]) if c.get('engine')=='historical_return' else wt*weights[i]
        if e['closed']:wcnew=0.
        dwc=wcnew-e['wc']
        e['cash']+=profit+entity_sbc+dep-capex-dwc
        e['fixed']+=capex-dep;e['wc']=wcnew
        app=reserve_profit(e,profit)
        group_profit+=interest-entity_sbc;group_sbc+=entity_sbc;group_capex+=capex;group_dep+=dep;group_dwc+=dwc
        ledger['entities'][n]={'operating_profit':profits[i],'interest':interest,'legal_profit_pre_upstream':profit,'noncash_sbc':entity_sbc,'depreciation':dep,'capex':capex,'delta_wc':dwc,'reserve_appropriation':app}
    parent=s['entities']['parent'];apt=s['entities']['apt']
    # Lending interest internal: no new group profit/cash.
    int_interest=s['internal_debt']*.027
    parent['cash']-=int_interest;parent['retained']-=int_interest
    apt['cash']+=int_interest;reserve_profit(apt,int_interest)
    ledger['internal_interest']=int_interest
    # External debt belongs to Haoying, not the listed parent; no disclosed guarantee.
    hao=s['entities']['haoying'];debtpay=hao['external_debt'] if y==1 else 0.
    debtinterest=hao['external_debt']*.027
    hao['cash']-=debtpay+debtinterest;hao['retained']-=debtinterest;hao['external_debt']-=debtpay
    external_out+=debtpay+debtinterest
    leasepay=min(s['lease_debt'],4.);parent['cash']-=leasepay;s['lease_debt']-=leasepay;external_out+=leasepay
    # New support is a separately documented, zero-interest senior-to-equity shareholder loan budget.
    # Neither a guarantee nor a previously signed loan agreement is claimed.
    support_interest=0.
    for n in NAMES[1:]:
        e=s['entities'][n];fee=s['support_claims'][n]*c.get('support_interest',0.)
        e['cash']-=fee;e['retained']-=fee;parent['cash']+=fee;reserve_profit(parent,fee);support_interest+=fee
    # Fund other-LP fixed preferred return accrues ONLY in the fund, not as parent cash expense.
    fund=s['fund'];pref=fund['other_lp_principal']*c.get('fund_preferred_rate',.05) if not fund['closed'] else 0.
    fund['preferred_due']+=pref;fund['retained']-=pref
    ledger['fund_preferred_accrual']=pref
    ledger['support_interest']=support_interest
    # Equity holdings realized gradually years6-8, historical disposals demonstrate realizability.
    port=0.;port_gain=0.
    portfolio_income=s['portfolio_book']*.10 if y<=8 else 0.
    portfolio_dividend=portfolio_income*.4
    s['portfolio_book']+=portfolio_income-portfolio_dividend
    apt['cash']+=portfolio_dividend;reserve_profit(apt,portfolio_income);external_in+=portfolio_dividend
    ledger['portfolio_equity_income']=portfolio_income;ledger['portfolio_dividend_cash']=portfolio_dividend
    if y in (6,7,8):
        book=s['portfolio_book']/(9-y);port=book*c.get('portfolio_recovery',1.);port_gain=port-book
        s['portfolio_book']-=book;apt['cash']+=port;reserve_profit(apt,port_gain)
        external_in+=port
    ledger.update({'debt_paid':debtpay,'debt_interest':debtinterest,'lease_paid':leasepay,'portfolio_proceeds':port,'portfolio_gain':port_gain})
    # Settle last year's dividend receivable: NO investment income again.
    receipt=s['dividend_receivable'];apt['cash']-=receipt;parent['cash']+=receipt;s['dividend_receivable']=0.
    ledger['prior_dividend_receipt']=receipt
    # Internal debt repayment in cash before new dividend; restores Apt cash, does not create income.
    repay=min(s['internal_debt'],max(0.,parent['cash']-r*.012),100.)
    parent['cash']-=repay;apt['cash']+=repay;s['internal_debt']-=repay
    # First upstream declarations can be legally set off against intercompany balance by budgeted resolutions.
    # Operational cash buffers continuously scale with activity, not a perpetual arbitrary lock-up.
    buffer=[r*.012,r*.045,r*.008,r*.003,r*.001]
    if y<=c.get('upstream_delay',0):up_ratio=0.
    else:up_ratio=.65 if y<=5 else min(1.,.65+.07*(y-5))
    upstream=[];minor_paid=0.;investment_income=0.;injections=0.;impairment=0.
    support_ledger=[];cost_ledger=[];capital_returns=[]
    # Finance cash shortfalls at their actual legal obligor; a claim mirrors every support debt.
    for i,n in enumerate(NAMES[1:],1):
        e=s['entities'][n];need=max(0.,buffer[i]-e['cash']) if not e['closed'] else 0.
        parent['cash']-=need;e['cash']+=need;injections+=need
        if c.get('support_gift',False):
            # Explicit adverse governance counterfactual: gratuitous cash support, no claim or extra ownership.
            parent['retained']-=need;reserve_profit(e,need)
        else:s['support_claims'][n]+=need;e['support_debt']+=need
        support_ledger.append({'entity':n,'advanced':need,'claim_created':0. if c.get('support_gift') else need})
    # Real liquidation: cash obligations, outside senior debt, support claim, then equity.
    if c.get('structural') and y==3:
        e=s['entities']['haoying'];proceeds=.25*e['fixed']+.5*e['wc'];obligation=20.
        impairment_exit=e['fixed']+e['wc']-proceeds;e['cash']+=proceeds-obligation;e['retained']-=impairment_exit+obligation
        group_profit-=impairment_exit+obligation;group_capex-=proceeds;external_out+=obligation
        if e['cash']<0.:
            emergency=-e['cash'];parent['cash']-=emergency;e['cash']+=emergency;s['support_claims']['haoying']+=emergency;e['support_debt']+=emergency;injections+=emergency
        recovered=min(e['cash'],s['support_claims']['haoying']);e['cash']-=recovered;parent['cash']+=recovered
        written=s['support_claims']['haoying']-recovered;parent['retained']-=written
        s['support_claims']['haoying']=written;e['support_debt']=written;s['support_allowances']['haoying']=written
        equity_cash=e['cash'];parent_receipt=equity_cash*direct[4];fund_receipt=equity_cash*via[4]
        parent['cash']+=parent_receipt;fund['cash']+=fund_receipt;minor_paid+=equity_cash*(1-ownership[4])
        pcost=s['sub_investment_cost']['haoying'];fcost=fund['investment_cost']['haoying']
        reserve_profit(parent,parent_receipt-pcost);fund['retained']+=fund_receipt-fcost
        s['sub_investment_allowances']['haoying']=pcost;fund['investment_allowances']['haoying']=fcost
        ledger['haoying_exit']={'proceeds':proceeds,'obligation':obligation,'impairment':impairment_exit,'support_recovered':recovered,'support_written_off':written,'parent_equity_cash':parent_receipt,'parent_equity_cost_written_off':pcost,'fund_equity_cash':fund_receipt,'fund_equity_cost_written_off':fcost,'outside_equity_cash':equity_cash*(1-ownership[4]),'uncollected_support_gross_face':written,'support_allowance':written,'net_support_recoverable':0.,'legal_debt_extinguished':False,'entity_legally_dissolved':False}
        for k in ['cash','fixed','wc']:e[k]=0.
        e['closed']=True;e['settlement_status']='operations_ceased_unsettled';e['liquidation_net_assets']=-e['support_debt']-e['external_debt']
    # Support loans repay before dividends/capital. Principal never creates mother investment income.
    for i,n in enumerate(NAMES[1:],1):
        e=s['entities'][n]
        debt_repay=min(s['support_claims'][n],max(0.,e['cash']-buffer[i]-(s['dividend_receivable'] if n=='apt' else 0.)))
        e['cash']-=debt_repay;parent['cash']+=debt_repay;s['support_claims'][n]-=debt_repay;e['support_debt']-=debt_repay
        support_ledger[i-1]['repaid']=debt_repay
        if e['closed']:continue
        wanted=max(0.,e['cash']-buffer[i])*up_ratio
        if n=='apt':
            offset=min(s['internal_debt'],max(0.,e['retained']),100.) if up_ratio else 0.
            e['retained']-=offset;s['internal_debt']-=offset;investment_income+=offset
        else:offset=0.
        available=max(0.,e['cash']-buffer[i]-(s['restricted_cash'] if n=='apt' else 0.))
        declared=min(wanted,available,max(0.,e['retained']))
        if n=='apt' and c.get('receipt_lag'):
            e['retained']-=declared;s['dividend_receivable']=declared;investment_income+=declared;paid=0.
        else:
            paid=legal_payment(e,declared,buffer[i]+(s['restricted_cash'] if n=='apt' else 0.))
            parent['cash']+=paid*direct[i];investment_income+=paid*direct[i]
            fund['cash']+=paid*via[i];fund['retained']+=paid*via[i];minor_paid+=paid*(1-ownership[i])
        upstream.append({'entity':n,'declared':declared,'paid':paid,'offset':offset,'direct_fraction':direct[i],'fund_fraction':via[i]})
    reserve_profit(parent,investment_income)
    # Cost testing is entity-specific. A Shanghai loss cannot consume Apt/Haoying acquisition basis.
    for i,n in enumerate(NAMES[1:],1):
        if s['entities'][n]['closed']:continue
        loss=max(0.,-profits[i]);direct_loss=min(s['sub_investment_cost'][n],loss*direct[i]);s['sub_investment_cost'][n]-=direct_loss;parent['retained']-=direct_loss;impairment+=direct_loss
        fund_loss=min(fund['investment_cost'].get(n,0.),loss*via[i])
        if n in fund['investment_cost']:fund['investment_cost'][n]-=fund_loss;fund['retained']-=fund_loss
        cost_ledger.append({'entity':n,'parent_impairment':direct_loss,'fund_impairment':fund_loss})
    if y>c.get('capital_return_start',10):
        for i,n in enumerate(NAMES[1:],1):
            e=s['entities'][n]
            returned=min(max(0.,e['cash']-buffer[i])*.25,e['returnable_paid_in_budget']*.25) if e['retained']>=-1e-8 and e['support_debt']<1e-8 and not e['closed'] else 0.
            pcost=fcost=gain=0.
            if returned:
                ratio=returned/e['returnable_paid_in_budget'];e['registered_capital']=max(1.,e['registered_capital']*(1-ratio));e['returnable_paid_in_budget']-=returned;e['cash']-=returned
                direct_cash=returned*direct[i];indirect=returned*via[i];parent['cash']+=direct_cash;fund['cash']+=indirect;minor_paid+=returned*(1-ownership[i])
                pcost=min(s['sub_investment_cost'][n],direct_cash);s['sub_investment_cost'][n]-=pcost;gain=direct_cash-pcost;reserve_profit(parent,gain)
                fcost=min(fund['investment_cost'].get(n,0.),indirect)
                if n in fund['investment_cost']:fund['investment_cost'][n]-=fcost
                fund['retained']+=indirect-fcost
            capital_returns.append({'entity':n,'cash':returned,'parent_cost_recovery':pcost,'fund_cost_recovery':fcost,'parent_gain':gain})
    # Fund has a finite legal/economic exit budget, independent of valuation horizon.
    # Parent may acquire the remaining investee stakes at discounted net tangible assets; no claim face-value guarantee.
    fund_exit=None
    if y==c.get('fund_exit_year',20) and not fund['closed']:
        acquisitions=[]
        for i,n in [(3,'yiweidi'),(4,'haoying')]:
            e=s['entities'][n]
            nav=max(0.,e['cash']+e['fixed']+e['wc']-e['support_debt']-e['external_debt'])
            price=nav*via[i]*c.get('fund_exit_asset_recovery',.8)
            buyer_capacity=max(0.,parent['cash']-buffer[0]);buyer_fee=price*.01 if not c.get('fund_external_buyer') else 0.
            if not c.get('fund_external_buyer'):
                if price+buyer_fee>buyer_capacity:raise ValueError('No independent parent acquisition capacity')
                parent['cash']-=price+buyer_fee;s['sub_investment_cost'][n]+=price+buyer_fee;external_out+=buyer_fee
            else:external_in+=price
            fund['cash']+=price
            gross_basis=fund['investment_cost'][n];prior_allowance=fund['investment_allowances'][n];basis=gross_basis-prior_allowance;sell_fee=price*.02;gain_tax=max(0.,price-basis)*.15
            fund['cash']-=sell_fee+gain_tax;fund['retained']+=price-basis-sell_fee-gain_tax;external_out+=sell_fee+gain_tax;fund['investment_cost'][n]=0.;fund['investment_allowances'][n]=0.
            acquisitions.append({'entity':n,'acquired_fraction':via[i],'asset_value_before_recovery':nav,'price':price,'fund_basis':basis,'fund_gross_basis':gross_basis,'fund_prior_allowance':prior_allowance,'buyer_cash_capacity':buyer_capacity,'buyer_fee':buyer_fee,'seller_fee':sell_fee,'gain_tax':gain_tax,'external_buyer':bool(c.get('fund_external_buyer'))})
            if not c.get('fund_external_buyer'):direct[i]+=via[i]
            via[i]=0.
        fund_exit={'acquisitions':acquisitions,'limited_recourse_budget_not_contract_fact':True}
    # One actual two-layer waterfall: outside LP fixed coupon -> principal at maturity -> mother basis -> residual.
    preferred_paid=min(fund['cash'],fund['preferred_due']);fund['cash']-=preferred_paid;fund['preferred_due']-=preferred_paid
    lp_principal=min(fund['cash'],fund['other_lp_principal']) if y>=c.get('fund_maturity',10) else 0.
    fund['cash']-=lp_principal;fund['other_lp_principal']-=lp_principal;minor_paid+=preferred_paid+lp_principal
    mother_capital=min(fund['cash'],fund['parent_capital']) if y>=c.get('fund_maturity',10) and fund['other_lp_principal']<1e-9 and fund['preferred_due']<1e-9 else 0.
    fund['cash']-=mother_capital;fund['parent_capital']-=mother_capital;parent['cash']+=mother_capital
    mother_basis=min(s['sub_investment_cost']['fund'],mother_capital);s['sub_investment_cost']['fund']-=mother_basis;reserve_profit(parent,mother_capital-mother_basis)
    fund_profit=max(0.,min(fund['cash'],fund['retained'])) if fund['preferred_due']<1e-9 and (y<c.get('fund_maturity',10) or fund['other_lp_principal']<1e-9) else 0.
    fund['cash']-=fund_profit;fund['retained']-=fund_profit;parent['cash']+=fund_profit;reserve_profit(parent,fund_profit);investment_income+=fund_profit
    if fund_exit is not None:
        # Final liquidation cash follows the same priority, then remaining capital/claims absorb real losses.
        residual_cash=fund['cash'];parent['cash']+=residual_cash;fund['cash']=0.
        unrecovered_parent_basis=s['sub_investment_cost']['fund'];reserve_profit(parent,residual_cash-unrecovered_parent_basis);s['sub_investment_cost']['fund']=0.
        fund_exit.update({'unpaid_other_principal_loss':fund['other_lp_principal'],'unpaid_preferred_loss':fund['preferred_due'],'parent_capital_loss':fund['parent_capital'],'parent_basis_loss':unrecovered_parent_basis,'residual_parent_cash':residual_cash,'closing_retained_before_liquidation':fund['retained']})
        fund.update({'other_lp_principal':0.,'preferred_due':0.,'parent_capital':0.,'retained':0.,'closed':True})
        ledger['fund_exit']=fund_exit
    ledger['fund_waterfall']={'preferred_paid':preferred_paid,'other_principal_paid':lp_principal,'parent_capital_return':mother_capital,'parent_cost_recovery':mother_basis,'parent_residual_profit':fund_profit,'direct_ownership_not_reapplied':True}
    new_internal_loan=max(0.,buffer[0]-parent['cash'])
    if new_internal_loan:
        if apt['cash']-s['dividend_receivable']-new_internal_loan < buffer[1]:raise ValueError('No subsidiary bridge capacity year '+str(y))
        apt['cash']-=new_internal_loan;parent['cash']+=new_internal_loan;s['internal_debt']+=new_internal_loan
    ledger['new_internal_loan']=new_internal_loan
    ledger['capital_returns']=capital_returns;ledger['support_ledger']=support_ledger;ledger['cost_ledger']=cost_ledger
    # Stock incentives: observed actual dates/thresholds, inventory used first, no fresh shares double counted.
    vest=0.;exercise=0.;a_factor=0.;b_ok=False
    rev=s['calendar_revenues'];base=2583.92732109
    if y in (2,3,4) and c.get('vest_budget',True):
        if y==2:
            performance=(rev['2026']+rev['2027'])/base-2
            a_factor=1. if performance>=.7429 else (.75 if performance>=.64 else 0.)
            b_ok=rev['2026']/base>=1.2 and rev['2027']/base>=1.44
            vest=.836791*.5*a_factor+.943710*.4*b_ok
        if y==3:
            b_ok=rev['2028']/base>=1.728;vest=.943710*.3*b_ok
        if y==4:
            performance=(rev['2028']+rev['2029'])/base-2
            a_factor=1. if performance>=2.1497 else (.75 if performance>=1.8016 else 0.)
            b_ok=rev['2029']/base>=2.0736
            vest=.836791*.5*a_factor+.943710*.3*b_ok
        # Exercise is scenario budget, not claim future employee election is certain.
        from_t=min(s['treasury'],vest)
        inventory_release=s['inventory_book']*from_t/s['treasury'] if s['treasury'] else 0.
        s['inventory_book']-=inventory_release;s['treasury']-=from_t;s['shares']+=vest-from_t
        exercise=vest*max(0.,240.-s['cumulative_dividend_ps'])
        parent['cash']+=exercise;external_in+=exercise
        s['parent_share_premium']+=exercise-inventory_release-(vest-from_t)
        parent['registered_capital']+=vest-from_t
    # Unawarded reserve not automatically paid; unused inventory cancellation budget in year3.
    cancelled=0.
    if y==3:
        cancelled=s['treasury'];s['shares']-=cancelled;s['treasury']=0.
        parent['registered_capital']-=cancelled;s['parent_share_premium']-=s['inventory_book']-cancelled;s['inventory_book']=0.
    s['cumulative_vested']+=vest
    participating=s['shares']-s['treasury']
    # Ordinary dividend policy gradual maturation: current ~17%; discretionary surpluses distributed as capacity matures.
    desired_ratio=min(1.,.20+.07*(y-1))
    ordinary_profit=sum(p*o for p,o in zip(profits,ownership))-pref
    wanted=max(0.,ordinary_profit)*desired_ratio
    if y>10:wanted=max(wanted,parent['cash']-buffer[0])
    dist=legal_payment(parent,wanted,buffer[0])
    # No automatic emergency external finance: adjust payout first; fail clearly if operation cannot fund itself.
    if parent['cash'] < -1e-7:raise ValueError('Parent financing infeasible year '+str(y))
    dividendps=dist/participating;s['cumulative_dividend_ps']+=dividendps
    if y==2:s['restricted_cash']=0. # performance guarantees release upon project completion; not loss
    s['year']=y
    closing_cash=sum(e['cash'] for e in s['entities'].values())+s['fund']['cash']
    # cash ledger includes all real outside flows; internal settlements cancel.
    expected=opening_cash+group_profit+group_sbc+group_dep-group_capex-group_dwc+external_in-external_out-minor_paid-dist
    # exit accounting loss was included in group profit, undo noncash impairment, no extra double expense.
    if 'haoying_exit' in ledger:expected+=ledger['haoying_exit']['impairment']+ledger['haoying_exit']['obligation']
    if abs(expected-closing_cash)>1e-6:raise AssertionError(('cash',y,expected,closing_cash))
    for n in NAMES[1:]:
        s['support_net_recoverable'][n]=s['support_claims'][n]-s['support_allowances'][n]
        assert abs(s['support_claims'][n]-s['entities'][n]['support_debt'])<1e-7
        assert 0.<=s['support_allowances'][n]<=s['support_claims'][n]+1e-8
        assert 0.<=s['sub_investment_allowances'][n]<=s['sub_investment_cost'][n]+1e-8
    for e in s['entities'].values():
        assert e['cash']>=-1e-7 and e['reserve']>=-1e-7 and e['fixed']>=-1e-7
    ledger.update({'ordinary_operating_profit':ordinary_profit,'group_profit_plus_interest':group_profit,'noncash_sbc':group_sbc,'capex':group_capex,'depreciation':group_dep,'delta_wc':group_dwc,'upstream':upstream,'new_parent_investment_income':investment_income,'capital_injections':injections,'parent_sub_cost_impairment':impairment,'interloan_cash_repayment':repay,'minority_dividends':minor_paid,'vested_million':vest,'exercise_cash':exercise,'unawarded_reserve_not_assumed':.419499,'cancelled_inventory':cancelled,'participating_shares':participating,'dividend':dist,'dividend_per_share':dividendps,'cash_conservation_error':closing_cash-expected,'state':copy.deepcopy(s)})
    return s,ledger

def run(c,n=180,start=None):
    s=copy.deepcopy(start) if start is not None else initial(c.get('parent_re',90.),c.get('apt_re',2000.),c.get('interloan',800.))
    if start is None:
        s['fund']['other_lp_principal']=c.get('fund_other_principal',49.)
        s['construction_remaining']=c.get('construction_budget',550.)
    if start is None and c.get('engine')=='historical_return':s['aux_profit']=c.get('normal_profit',980.)
    rows=[];pv=0.;r=c.get('discount',.10)
    for t in range(1,n+1):
        s,row=step(s,c);rows.append(row);pv+=row['dividend_per_share']/(1+r)**t
    return {'parameters':c,'start_state':start,'years':n,'value_per_share':pv,'rows':rows,'last_state':s,'pv_after_year5':sum(x['dividend_per_share']/(1+r)**(i+1) for i,x in enumerate(rows) if i>=5)}

def flattened_numbers(x,p=''):
    out={}
    if isinstance(x,dict):
        for k,v in x.items():
            if k in ('calendar_revenues','cumulative_dividend_ps','year'):continue
            out.update(flattened_numbers(v,p+'/'+k))
    elif isinstance(x,list):
        for i,v in enumerate(x):out.update(flattened_numbers(v,p+'/'+str(i)))
    elif isinstance(x,(int,float)) and not isinstance(x,bool):out[p]=x
    return out

def handtests():
    h=initial();h.update({'restricted_cash':0.,'lease_debt':0.,'internal_debt':0.,'portfolio_book':0.,'construction_remaining':0.,'shares':1.,'treasury':0.,'inventory_book':0.})
    h['fund'].update({'other_lp_principal':0.,'parent_capital':0.})
    for n in NAMES:h['entities'][n].update({'cash':0.,'fixed':0.,'wc':0.,'retained':0.,'reserve':0.,'registered_capital':0.,'external_debt':0.})
    h['entities']['parent'].update({'cash':100.,'registered_capital':100.})
    hc={'manual_operating':[0.,[10.,0.,0.,0.,0.],0.,0.],'cash_yield':0.,'vest_budget':False}
    hz,hr=step(h,hc)
    assert hr['dividend']==2. and hz['entities']['parent']['cash']==108. and hz['entities']['parent']['retained']==7. and hz['entities']['parent']['reserve']==1.
    h['entities']['parent']['retained']=-50.;hz2,hr2=step(h,hc);assert hr2['dividend']==0. and hz2['entities']['parent']['cash']==110. and hz2['entities']['parent']['retained']==-40.
    h['entities']['parent']['retained']=0.;hc['manual_operating']=[0.,[10.,0.,0.,0.,-5.],0.,0.]
    hz3,hr3=step(h,hc)
    assert hz3['support_claims']['haoying']==5. and hz3['entities']['haoying']['support_debt']==5.
    assert hz3['entities']['parent']['cash']==103.634822 # profit10-support5-dividend1.365178
    # Error rejection: an attempted claim erasure fails the same production invariant in next step.
    broken=copy.deepcopy(hz3);broken['support_claims']['haoying']=0.
    rejected=False
    try:step(broken,hc)
    except AssertionError:rejected=True
    assert rejected
    debtcase=copy.deepcopy(h);debtcase['entities']['haoying']['external_debt']=31.
    dc={'manual_operating':[0.,[0.,0.,0.,0.,0.],0.,0.],'cash_yield':0.,'vest_budget':False}
    dz,dr=step(debtcase,dc)
    assert abs(dz['support_claims']['haoying']-31.837)<1e-9 and abs(dz['entities']['parent']['retained'])<1e-9
    assert abs(dz['entities']['haoying']['retained']+.837)<1e-9
    fundcase=copy.deepcopy(h);fundcase['fund'].update({'cash':100.,'retained':100.,'other_lp_principal':49.,'parent_capital':35.})
    fz,fr=step(fundcase,dict(dc,fund_maturity=1))
    assert abs(fr['fund_waterfall']['parent_residual_profit']-13.55)<1e-9
    assert abs(fz['entities']['parent']['cash']-148.55)<1e-9
    assert fr['fund_waterfall']['other_principal_paid']==49. and fr['fund_waterfall']['parent_capital_return']==35.
    zero={'cash':1e6,'retained':0.,'reserve':1e6,'registered_capital':1e6};assert legal_payment(zero,100.,0.)==0.
    return {'pure_parent':{'dividend':hr['dividend'],'cash':108.,'retained':7.,'reserve':1.},'loss_counterexample':{'dividend':hr2['dividend'],'cash':110.,'retained':-40.},'support_claim_created':5.,'claim_erasure_rejected':rejected,'wrong_debtor_counterexample':{'haoying_external_debt_paid':31.,'haoying_interest':.837,'parent_claim':31.837,'parent_interest_expense':0.},'fund_hand_example':{'outside_coupon':2.45,'outside_principal':49.,'parent_capital':35.,'parent_residual_profit':13.55,'parent_receipt':48.55},'illegal_retained_payment_rejected':True}

def main():
    paths={
      'base':{'discount':.10},
      'core_low':{'discount':.105,'margin_delta':-.01,'growth_scale':.95},
      'core_high':{'discount':.095,'margin_delta':.005,'growth_scale':1.05},
      'cycle':{'discount':.10,'cycle':True},
      'structural':{'discount':.105,'structural':True,'capital_scale':1.15,'portfolio_recovery':.6},
      'optimistic':{'discount':.095,'optimistic':True},
      'legal_delay':{'discount':.10,'upstream_delay':3,'receipt_lag':True,'parent_re':55.58810726,'apt_re':1000.},
      'no_vest':{'discount':.10,'vest_budget':False},
      'legal_capacity_high':{'discount':.10,'parent_re':120.,'apt_re':2500.,'interloan':900.},
      'legal_capacity_low':{'discount':.10,'parent_re':55.58810726,'apt_re':1000.,'interloan':700.},
      'capital_return_delayed':{'discount':.10,'capital_return_start':20},
      'portfolio_loss':{'discount':.10,'portfolio_recovery':.5},
      'fund_preferred_low':{'discount':.10,'fund_preferred_rate':.02,'fund_maturity':8},
      'fund_preferred_high':{'discount':.10,'fund_preferred_rate':.08,'fund_maturity':15},
      'support_gift':{'discount':.10,'support_gift':True},
      'support_interest':{'discount':.10,'support_interest':.03},
      'fund_exit_low':{'discount':.10,'fund_exit_asset_recovery':.5,'fund_exit_year':15},
      'fund_exit_high':{'discount':.10,'fund_exit_asset_recovery':1.,'fund_exit_year':30},
      'fund_no_acquisition':{'discount':.10,'fund_exit_year':9999},
      'fund_external_exit':{'discount':.10,'fund_external_buyer':True,'fund_exit_asset_recovery':.2},
      'structural_external_exit':{'discount':.105,'structural':True,'capital_scale':1.15,'portfolio_recovery':.6,'fund_external_buyer':True,'fund_exit_asset_recovery':.2},
      'construction_low':{'discount':.10,'construction_budget':450.},
      'construction_high':{'discount':.10,'construction_budget':650.},
      'capital_pressure':{'discount':.10,'capital_scale':1.3},
      'margin_minus_2pt':{'discount':.10,'margin_delta':-.02},
      'aux_low':{'discount':.105,'engine':'historical_return','incremental_roic':.35,'normal_profit':950.},
      'aux_high':{'discount':.095,'engine':'historical_return','incremental_roic':.45,'normal_profit':1030.}}
    full={};convergence={};extensions={}
    for name,c in paths.items():
        try:
            runs=[run(c,n) for n in (120,180,240)]
            full[name]=runs[-1];extensions[name]={'120':runs[0],'180':runs[1]}
            a,b=flattened_numbers(runs[1]['last_state']),flattened_numbers(runs[2]['last_state'])
            dif={k:abs(a[k]-b[k]) for k in a}
            convergence[name]={'horizons':[120,180,240],'values':[x['value_per_share'] for x in runs],'actual_extended_runs':True,'all_stock_differences_180_240':dif,'max_stock_difference':max(dif.values()),'annual_terminal_distributions':[x['rows'][-1]['dividend_per_share'] for x in runs]}
        except ValueError as e:full[name]={'infeasible':str(e),'parameters':c}
    base=full['base'];y5=base['rows'][4]['state']
    terminals={}
    for name,c in {'low':paths['core_low'],'high':paths['core_high']}.items():
        terminals[name]=run(c,240,start=y5)
    summary={k:({a:v[a] for a in ['value_per_share','pv_after_year5']} if 'rows' in v else v) for k,v in full.items()}
    result={'as_of':ASOF,'units':'CNY million except per share; shares million','summary':summary,'tests':handtests(),'convergence':convergence,'extension_runs':extensions,'paths':full,'year5_common_state':y5,'year5_terminal_continuations':terminals,'holder':{'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':ASOF,'base_case_distributions_per_share':[round(x['dividend_per_share'],6) for x in base['rows'][:5]],'base_case_terminal_equity_value_range_per_share':{'year_5':{k:round(v['value_per_share'],2) for k,v in terminals.items()}}}}
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()

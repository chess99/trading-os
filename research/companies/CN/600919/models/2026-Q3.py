"""Bank of Jiangsu economic common-equity model. Python stdlib; deterministic stdout.
CNY billion except per-share RMB and shares in billions. No external input files.
The entity-level budgets are forecasts, not unpublished regulatory measurements.
"""
import json, copy, math
SHARES=18.351324463
ASOF='2026-10-29T20:31:43+00:00'
FACTS={'assets':5605.845442,'common_equity':281.568810,'minority':12.811966,'preferred_book':19.977830,'preferred_face':20.,'old_perpetual':60.,'new_perpetual':20.,'CET1':288.110523,'CET1_deduction':.108653,'AT1':80.864546,'T2':39.185051,'credit_RWA':3030.341186,'market_RWA':56.188881,'operational_RWA':164.196028,'RWA':3250.726095,'shares':SHARES,'deferred_tax_assets':13.074875}

def lawful_profit(re,profit,statutory,reserve_target,risk_reserve,risk_target,continue_statutory=False):
    """Losses are restored before appropriations; no dividend from capital/reserve itself."""
    restored=max(0.,profit-max(0.,-re))
    appropriation=.10*restored if continue_statutory or statutory<reserve_target else 0.
    risk=max(0.,risk_target-risk_reserve)
    return re+profit-appropriation-risk,statutory+appropriation,risk_reserve+risk,appropriation,risk

def equity_valuation(opening_equity, rows, discount_rate, shares=SHARES):
    """Actual production cash/clean-surplus valuation chain, also callable with hand fixtures."""
    pv=ri=tail5=first5=0.
    prior=opening_equity
    for row in rows:
        y=row['year'];d=row['dividend'];profit=row['common_profit'];end=row['E']
        assert abs(end-(prior+profit-d))<max(1e-7,abs(end)*1e-12)
        pv+=d/(1+discount_rate)**y/shares
        ri+=(profit-discount_rate*prior)/(1+discount_rate)**y/shares
        if y<=5:first5+=d/(1+discount_rate)**y/shares
        else:tail5+=d/(1+discount_rate)**(y-5)/shares
        prior=end
    return dict(value=pv,RI_value=opening_equity/shares+ri,Y5=tail5,first_five_PV=first5,tail_after_five_PV=pv-first5,residual_book_PV=prior/(1+discount_rate)**len(rows)/shares)

def initial():
    loan=2132.626717+647.175111
    liquid=562.160558
    residual=5605.845442-(loan-70.043322+1728.195205+504.366965+liquid)
    consumer=6.004291+.530+.75*.710464
    # FY run-rate Q3 legal entity split, reconciled to actual consolidated NCI. Not disclosed Q3 solo accounts.
    leasing=(12.811966-.3868*consumer)/.4875
    wealth=5.715268+.75*.883385
    subs=[]
    for n,e,o,c,re,stat,risk,a in zip(['leasing','wealth','consumer'],[leasing,wealth,consumer],[.5125,1.,.6132],[2.46,2.,3.059513],[8.,3.,1.5],[3.,1.5,2.365],[3.,.5,.4],[160.,7.5,75.]):
        subs.append(dict(name=n,E=e,ownership=o,cost=c,RE=re,statutory=stat,risk=risk,assets=a,cash=a*.05))
    E=281.568810
    pe=E-sum(x['E']*x['ownership'] for x in subs)+sum(x['cost'] for x in subs)
    return dict(corporate_bill=2132.626717,retail=647.175111,debt=1728.195205,trading=504.366965,cash=liquid+20,other=residual,deposits=2990.309946,allowance=70.043322,offbalance=520.597345,market_rwa=56.188881,op_rwa=164.196028,fee=4.5,other_liabilities=112.101488,dta=13.074875,E=E,NCI=12.811966,preferred=19.977830,perpetual=80.,parent_E=pe,parent_RE=81.,parent_statutory=24.295024,parent_risk=63.964641,parent_pending=0.,parent_liquidity_offset=0.,subs=subs)

def simulate(name='base',years=250,rate=.11,method='spread',overrides=None):
    p=dict(tail_loss=.0085,tail_loan_yield=.033,tail_cost=.26,group_buffer=.0925,parent_buffer=.09,first_loss=.0085,shock=0.,dta_haircut=0.,deposit_flight=0.,solo_fraction=.935,sub_return_scale=1.,parent_RE=81.,rwa_extra=0.,growth_shift=0.,holding_shift=0.,disposal_scale=1.,liquidity_maturity=.35,upstream_delay=False,holding_front_shift=0.,disposal_front_scale=1.)
    if name=='low':p.update(tail_loss=.009,tail_loan_yield=.0327,tail_cost=.265,group_buffer=.095,parent_buffer=.0925,holding_shift=-.001,disposal_scale=.5)
    if name=='high':p.update(tail_loss=.008,tail_loan_yield=.0333,tail_cost=.255,holding_shift=.001,disposal_scale=1.5)
    if name=='cycle':p.update(first_loss=.012,shock=-.001)
    if name=='structural':p.update(tail_loss=.012,tail_loan_yield=.029,tail_cost=.29,first_loss=.012,shock=-.002,group_buffer=.10,parent_buffer=.0975,dta_haircut=.25,sub_return_scale=.65,growth_shift=-.025)
    if name=='funding_failure':p.update(deposit_flight=.20)
    if overrides:p.update(overrides)
    s=initial();s['parent_RE']=p['parent_RE'];rows=[];E0=s['E'];pv=0.;ri=0.;tail5=0.;pv5=0.;failure=None
    scale=3030.341186/(.95*(s['corporate_bill']+s['retail'])+.3*s['debt']+.5*s['trading']+.5*s['offbalance'])
    for y in range(1,years+1):
        z=copy.deepcopy(s);f=min((y-1)/14,1);oldassets=sum(s[k] for k in ['corporate_bill','retail','debt','trading','cash','other'])-s['allowance']
        oldwh=oldassets-s['E']-s['NCI']-s['preferred']-s['perpetual']-s['deposits']-s['other_liabilities']
        gc=.08*(1-f)+.02*f+p['growth_shift']*(1-f);gb=.06*(1-f)+.02*f;gd=.075*(1-f)+.02*f
        for key,g in [('corporate_bill',gc),('retail',.02),('debt',gb),('trading',.02),('other',.02),('deposits',gd),('offbalance',gc),('op_rwa',.05*(1-f)+.02*f),('market_rwa',.02),('other_liabilities',.02),('dta',.02)]:z[key]=s[key]*(1+g)
        z['deposits']-=s['deposits']*p['deposit_flight'] if y==1 else 0.
        z['cash']=(s['cash']-20 if y==1 else s['cash'])*1.02
        # Deposit run-off first consumes accessible liquid assets above operating needs, then funding capacity.
        parent_ratio=467.813988/507.551548
        old_parent_basket=(s['cash']-20 if y==1 else s['cash'])*parent_ratio+(20 if y==1 else 0)-s['parent_pending']-s['parent_liquidity_offset']
        old_restricted=(157.873587+24.838062+.415473+.055)*s['deposits']/3026.974216+1.02**(y-1)
        immediate=min(max(0.,old_parent_basket-old_restricted),34.906878*(s['cash']-20 if y==1 else s['cash'])/507.551548+(20 if y==1 else 0))
        # Use the SAME period-end restrictions and maturity window as the payment constraint.
        # Retain priority and operating cash before releasing assets; do not advance future sub dividends.
        release_maturity=p['liquidity_maturity'] if y<=2 else .35
        end_restricted=(157.873587+24.838062+.415473+.055)*z['deposits']/3026.974216+1.02**y
        release_reserve_addition=max(0.,end_restricted-old_restricted)
        release_coupon=1.701 if y<3 else 1.701+(2.4-1.701)*min((y-2)/4,1)
        if y==1:release_coupon+=.772
        release_priority=release_coupon+(20 if y==1 else 0)
        accessible=max(0.,immediate+release_maturity*max(0.,old_parent_basket-old_restricted-immediate)-release_reserve_addition-.015*z['deposits']-release_priority)
        deposit_runoff=s['deposits']*p['deposit_flight'] if y==1 else 0.
        liquid_asset_release=min(deposit_runoff,accessible)
        z['cash']-=liquid_asset_release
        z['parent_liquidity_offset']=s['parent_liquidity_offset']*1.02+liquid_asset_release*(1-parent_ratio)
        loan0=s['corporate_bill']+s['retail'];loan1=z['corporate_bill']+z['retail'];avgloan=(loan0+loan1)/2
        tail_weight=max(0.,(y-5)/10);tail_weight=min(tail_weight,1.)
        writeoff_rate=p['first_loss'] if y<=3 else .0085+(p['tail_loss']-.0085)*tail_weight
        writeoffs=avgloan*writeoff_rate
        z['allowance']=.025*loan1
        provision=z['allowance']-s['allowance']+writeoffs
        finloss=.0005*(s['debt']+z['debt'])/2
        assets=sum(z[k] for k in ['corporate_bill','retail','debt','trading','cash','other'])-z['allowance']
        wh_budget=assets-s['E']-s['NCI']-80-z['deposits']-z['other_liabilities']
        ly=.0378*(1-f)+.033*f+(p['tail_loan_yield']-.033)*tail_weight+(p['shock'] if (name=='structural' or y<=3) else 0)
        dy=.024*(1-f)+.022*f;dc=.013*(1-f)+.011*f;wc=.0165*(1-f)+.015*f
        interest=avgloan*ly+(s['debt']+z['debt'])/2*dy+((s['cash']-20 if y==1 else s['cash'])+z['cash'])/2*.014
        funding=(s['deposits']+z['deposits'])/2*dc+(oldwh+wh_budget)/2*wc
        nii=interest-funding
        holding_income=(s['trading']+z['trading'])/2*(.015-.001*f+p['holding_shift']*tail_weight+p['holding_front_shift'])
        disposal_income=(2.-f)*1.02**y*(1+(p['disposal_scale']-1)*tail_weight)*p['disposal_front_scale']
        # Expected FV mark gains and gross derivative/metal gains are zero; disposal budget is NET of hedges.
        finincome=holding_income+disposal_income
        z['fee']=s['fee']*(1+.04*(1-f)+.02*f)
        revenue=nii+finincome+z['fee']
        opex=revenue*(.245+.015*f+(p['tail_cost']-.26)*tail_weight)
        pbt=revenue-opex-revenue*.011-provision-finloss
        segments=None
        if method=='segment':
            # Independent earnings entry: H1 annualised pretax segment yields haircut for Q4 costs, repricing, no trading windfall.
            avcorp=(s['corporate_bill']+z['corporate_bill'])/2
            avret=(s['retail']+z['retail'])/2
            avtreasury=(s['debt']+z['debt']+s['trading']+z['trading']+s['cash']+z['cash']-(20 if y==1 else 0))/2
            segments=[avcorp*(.0112-.002*f),avret*(.005-.0008*f),avtreasury*(.0062-.001*f)]
            pbt=sum(segments)-(writeoff_rate-.0085)*avgloan
            # For the independent segment case reconcile observed gross revenue to its allocated economic costs.
            opex=revenue-revenue*.011-provision-finloss-pbt
        impairment=s['dta']*p['dta_haircut'] if y==1 else 0.
        z['dta']-=impairment;z['other']-=impairment;assets-=impairment
        tax=max(0.,pbt*.18);net=pbt-tax-impairment
        coupon=1.701 if y<3 else 1.701+(2.4-1.701)*min((y-2)/4,1)
        if y==1:coupon+=.772
        upstream=nciprofit=ncidiv=subprofit=unscaled_subprofit=0.;subrows=[]
        for k,(a,b) in enumerate(zip(s['subs'],z['subs'])):
            ret=([.135,.14,.10][k]*(1-f)+[.10,.10,.085][k]*f)*p['sub_return_scale']
            profit=a['E']*ret
            unscaled_subprofit+=a['E']*([.135,.14,.10][k]*(1-f)+[.10,.10,.085][k]*f)
            subprofit+=profit;nciprofit+=profit*(1-a['ownership'])
            b['RE'],b['statutory'],b['risk'],st,rk=lawful_profit(a['RE'],profit,a['statutory'],[3,1.5,2.365][k],a['risk'],a['risk']*1.02)
            needed=a['E']*(1+.06*(1-f)+.02*f)
            div=max(0.,min(b['RE'],a['E']+profit-needed,.8*max(0.,profit)))
            b['RE']-=div;b['E']=a['E']+profit-div
            ag=.06*(1-f)+.02*f;b['assets']=a['assets']*(1+ag);b['cash']=b['assets']*.05
            debt0=a['assets']-a['E'];debt1=b['assets']-b['E']
            sub_cash_residual=b['cash']-a['cash']-(profit-div+(debt1-debt0)-((b['assets']-b['cash'])-(a['assets']-a['cash'])))
            upstream+=div*a['ownership'];ncidiv+=div*(1-a['ownership'])
            subrows.append(dict(name=a['name'],profit=profit,dividend=div,parent_dividend=div*a['ownership'],minority_dividend=div*(1-a['ownership']),E=b['E'],RE=b['RE'],statutory=b['statutory'],risk_reserve=b['risk'],assets=b['assets'],debt=debt1,cash=b['cash'],economic_capital=needed,capital_ratio=b['E']/b['assets'],cash_residual=sub_cash_residual,ownership=a['ownership'],parent_cost=a['cost']))
        subs_incremental_loss=unscaled_subprofit-subprofit
        net-=subs_incremental_loss
        parentprofit=net-subprofit+upstream
        z['parent_RE'],z['parent_statutory'],z['parent_risk'],pst,prk=lawful_profit(s['parent_RE'],parentprofit,s['parent_statutory'],SHARES*.5,s['parent_risk'],.015*(loan1+z['debt']+z['trading']),y<=5)
        redemption_cost=.02217 if y==1 else 0.
        z['parent_RE']-=coupon+redemption_cost
        z['parent_E']=s['parent_E']+parentprofit-coupon-redemption_cost
        profit_common=net-nciprofit-coupon-redemption_cost
        z['E']=s['E']+profit_common;z['NCI']=s['NCI']+nciprofit-ncidiv
        credit=scale*(.95*loan1+.3*z['debt']+.5*z['trading']+.5*z['offbalance'])*(1+p['rwa_extra'])
        rwa=credit+z['market_rwa']+z['op_rwa']
        eligible=(288.110523-281.568810+.108653)*z['NCI']/12.811966
        atminor=.886716*z['NCI']/12.811966
        t2=min(.0125*credit,z['allowance']*.55)+z['NCI']*.14
        gtarget=.0886+(.0925-.0886)*min(y/3,1)+(p['group_buffer']-.0925)*tail_weight
        ptarget=.086+(.09-.086)*min(y/3,1)+(p['parent_buffer']-.09)*tail_weight
        capital_need=max(gtarget*rwa-eligible+.108653,.105*rwa-80-atminor-eligible+.108653,.1225*rwa-80-atminor-t2-eligible+.108653)
        solorwa=rwa*p['solo_fraction'];cost=sum(a['cost'] for a in z['subs'])
        parent_need=max(ptarget*solorwa,.1025*solorwa-80,.12*solorwa-80-t2*.9)+cost+.108653
        wanted=.32*max(0.,net-nciprofit-coupon) if y<=5 else max(0.,z['E']-capital_need)
        # Parent payment window: restricted balances retained, no cash from legal reserve or unreceived dividends.
        pending=upstream if p['upstream_delay'] else 0.
        upstream_received=(s['parent_pending'] if p['upstream_delay'] else upstream)
        z['parent_pending']=pending
        restricted=(157.873587+24.838062+.415473+.055)*z['deposits']/3026.974216+1.02**y
        maturity_fraction=p['liquidity_maturity'] if y<=2 else .35
        maturities=max(0.,old_parent_basket-old_restricted-immediate)*maturity_fraction
        reserve_addition=max(0.,restricted-old_restricted)
        available=immediate+maturities+upstream_received-reserve_addition-liquid_asset_release
        parent_minimum=.015*z['deposits']
        priority_payment=coupon+(20 if y==1 else 0)
        liquidity_cap=max(0.,available-parent_minimum-priority_payment)
        parent_assets_pre=assets-sum(a['assets'] for a in z['subs'])+cost
        old_parent_assets_pre=oldassets-sum(a['assets'] for a in s['subs'])+cost
        old_parent_wholesale_pre=old_parent_assets_pre-s['parent_E']-80-s['preferred']-s['deposits']-s['other_liabilities']
        parent_wholesale_before_D=parent_assets_pre-z['parent_E']-80-z['deposits']-z['other_liabilities']
        parent_funding_dividend_cap=max(0.,min(1.12*old_parent_wholesale_pre,.5*parent_assets_pre)-parent_wholesale_before_D)
        group_wholesale_before_D=assets-z['E']-z['NCI']-80-z['deposits']-z['other_liabilities']
        group_funding_dividend_cap=max(0.,min(1.12*oldwh,.5*assets)-group_wholesale_before_D)
        div=max(0.,min(wanted,z['E']-capital_need,z['parent_E']-parent_need,z['parent_RE'],liquidity_cap,parent_funding_dividend_cap,group_funding_dividend_cap))
        # Do not pay ordinary shareholders while preference/perpetual coupons are unsupported.
        if z['parent_RE']<0:div=0.
        wh_pre_div=assets-z['E']-z['NCI']-80-z['deposits']-z['other_liabilities']
        if wh_pre_div/max(oldwh,1)>1.12 or wh_pre_div/assets>.50:div=0.
        z['E']-=div;z['parent_E']-=div;z['parent_RE']-=div;z['preferred']=0.;z['perpetual']=80.
        wholesale=assets-z['E']-z['NCI']-80-z['deposits']-z['other_liabilities']
        cet=z['E']+eligible-.108653;tier1=cet+80+atminor;total=tier1+t2
        solo_cet=z['parent_E']-cost-.108653
        leverage=tier1/(assets+.98*z['offbalance'])
        # Economic liquidity projection: calibrate starting HQLA/30-day outflows, not a certified future LCR.
        hqla=526.383390*(.5*(z['cash']/(562.160558))+.5*(z['debt']/1728.195205))
        outflow=308.917861*(.6*z['deposits']/2990.309946+.4*wholesale/(5231.486836-2990.309946-112.101488))
        # Full annual consolidated cash waterfall; credit charges restored only once, actual principal writeoffs retained.
        sources=net+provision+finloss+impairment+(z['deposits']-s['deposits'])+(wholesale-oldwh)+(z['other_liabilities']-s['other_liabilities'])
        applications=(loan1-loan0+writeoffs)+(z['debt']-s['debt']+finloss)+(z['trading']-s['trading'])+(z['other']-s['other']+impairment)+coupon+div+ncidiv+(20 if y==1 else 0)
        cash_residual=z['cash']-s['cash']-(sources-applications)
        clean_residual=z['E']-(s['E']+profit_common-div)
        entity_residual=z['E']-(z['parent_E']+sum(a['E']*a['ownership'] for a in z['subs'])-cost)
        # Annual solo balance/flow budget. Investments are carried at cost; pending subsidiary payments
        # are receivables, not parent cash. These economic allocations are not published solo regulatory accounts.
        parent_assets=assets-sum(a['assets'] for a in z['subs'])+cost
        old_parent_assets=oldassets-sum(a['assets'] for a in s['subs'])+cost
        parent_cash=z['cash']*parent_ratio-pending-z['parent_liquidity_offset']
        old_parent_cash=old_parent_basket
        parent_wholesale=parent_assets-z['parent_E']-80-z['deposits']-z['other_liabilities']
        old_parent_wholesale=old_parent_assets-s['parent_E']-80-s['preferred']-s['deposits']-s['other_liabilities']
        # Net asset deployment excludes subsidiary dividend receivables; no double subtraction of cash delay.
        parent_net_asset_deployment=(parent_assets-parent_cash-pending)-(old_parent_assets-old_parent_cash-s['parent_pending'])
        parent_noncash_credit=(10.081179/12.048152)*(provision+finloss+impairment) # H1 parent/group credit-charge allocation budget
        parent_cash_earnings=parentprofit-upstream+upstream_received+parent_noncash_credit
        parent_cash_sources=parent_cash_earnings+(z['deposits']-s['deposits'])+(parent_wholesale-old_parent_wholesale)+(z['other_liabilities']-s['other_liabilities'])
        parent_cash_uses=parent_net_asset_deployment+parent_noncash_credit+priority_payment+div
        parent_cash_residual=parent_cash-old_parent_cash-(parent_cash_sources-parent_cash_uses)
        assert abs(parent_cash_residual)<max(1e-7,assets*1e-12),(name,y,parent_cash_residual)
        parent_free_stock=parent_cash-restricted
        parent_funding_capacity_ok=parent_wholesale/max(old_parent_wholesale,1)<=1.12 and parent_wholesale/parent_assets<=.5
        # Retained pending amounts remain in subsidiaries, with matching payable; group cash unchanged.
        for sub,a,b in zip(subrows,s['subs'],z['subs']):
            prior_pending=a.get('pending_parent',0.)
            current_pending=sub['parent_dividend'] if p['upstream_delay'] else 0.
            received=prior_pending if p['upstream_delay'] else sub['parent_dividend']
            b['pending_parent']=current_pending
            sub['parent_dividend_received']=received
            sub['parent_payable']=current_pending
            sub['cash_including_parent_payable']=sub['cash']+current_pending
            sub['assets_including_parent_payable']=sub['assets']+current_pending
            sub['debt_including_parent_payable']=sub['debt']+current_pending
            old_cash=a['cash']+prior_pending
            paid=sub['minority_dividend']+received
            sub['actual_cash_residual']=(sub['cash']+current_pending)-old_cash-(sub['profit']-paid+(sub['debt']-(a['assets']-a['E']))-((sub['assets']-sub['cash'])-(a['assets']-a['cash'])))
            assert abs(sub['actual_cash_residual'])<max(1e-7,assets*1e-12)
        
        for v in [cash_residual,clean_residual,entity_residual]:
            assert abs(v)<max(1e-7,assets*1e-12),(name,y,v)
        hard=[]
        if cet/rwa<.0775 or solo_cet/solorwa<.0775:hard.append('CET1 below disclosed minimum+buffers assuming CCyB0; solo is model budget')
        if tier1/rwa<.0875 or total/rwa<.1075:hard.append('tier1/total capital insufficient')
        if leverage<.04125:hard.append('leverage insufficient')
        if wholesale<0 or wholesale/max(oldwh,1)>1.12 or wholesale/assets>.50:hard.append('wholesale funding exceeds 12% annual or 50% asset economic capacity')
        if hqla/outflow<1.:hard.append('economic liquidity coverage below 100%')
        if z['parent_RE']<0 and coupon>0:hard.append('priority coupon not supported by parent distributable profits')
        if not parent_funding_capacity_ok:hard.append('parent annual wholesale funding exceeds economic capacity')
        if available-parent_minimum-priority_payment < -1e-8:hard.append('parent payment-window funds insufficient for priority payments after operating buffer')
        if parent_free_stock<parent_minimum:hard.append('parent unencumbered liquidity stock below economic operating reserve')
        if any(a['E']<0 or a['cash']<0 for a in z['subs']):hard.append('subsidiary insolvent or cash negative')
        df=(1+rate)**y;pv+=div/df/SHARES;ri+=(profit_common-rate*s['E'])/df/SHARES
        if y<=5:pv5+=div/df/SHARES
        else:tail5+=div/(1+rate)**(y-5)/SHARES
        row=dict(year=y,common_shares=SHARES,opening_E=s['E'],E=z['E'],parent_E=z['parent_E'],parent_RE=z['parent_RE'],parent_statutory=z['parent_statutory'],parent_risk=z['parent_risk'],parent_profit=parentprofit,parent_upstream=upstream,net=net,common_profit=profit_common,NCI=z['NCI'],minority_profit=nciprofit,minority_distribution=ncidiv,dividend=div,D=div/SHARES,coupon=coupon,preferred_face_repaid=20 if y==1 else 0,preferred_book=z['preferred'],perpetual_face=80.,perpetual_redemption=0.,new_AT1_issuance=0.,T2=t2,T2_bond_face=0.,T2_bond_amortization=0.,eligible_minority_CET1=eligible,eligible_minority_AT1=atminor,CET1=cet,tier1=tier1,total_capital=total,RWA=rwa,credit_RWA=credit,market_RWA=z['market_rwa'],operational_RWA=z['op_rwa'],group_CET1_ratio=cet/rwa,group_tier1_ratio=tier1/rwa,group_total_ratio=total/rwa,solo_RWA_budget=solorwa,solo_CET1_budget=solo_cet,solo_CET1_ratio_budget=solo_cet/solorwa,common_capital_required=capital_need,parent_capital_required=parent_need,capital_shortfall_budget=max(0.,capital_need-z['E']),parent_shortfall_budget=max(0.,parent_need-z['parent_E']),assets=assets,corporate_bill=z['corporate_bill'],retail=z['retail'],debt_assets=z['debt'],trading_assets=z['trading'],cash=z['cash'],other_assets=z['other'],deposits=z['deposits'],wholesale=wholesale,wholesale_growth=wholesale/oldwh-1,other_liabilities=z['other_liabilities'],offbalance=z['offbalance'],allowance=z['allowance'],writeoffs=writeoffs,credit_loss=provision+finloss,loan_provision=provision,financial_credit_loss=finloss,interest_income=interest,interest_cost=funding,NII=nii,investment_income=finincome,holding_income=holding_income,net_disposal_income=disposal_income,expected_FV_gain=0.,net_fee=z['fee'],revenue=revenue,opex=opex,pretax_profit=pbt,tax_expense=tax,DTA=z['dta'],DTA_impairment=impairment,current_tax_budget=tax+z['dta']-s['dta']+impairment,loan_yield=ly,deposit_cost=dc,wholesale_cost=wc,leverage=leverage,HQLA_budget=hqla,outflows_budget=outflow,LCR_budget=hqla/outflow,subsidiaries=subrows,segments=segments,parent_funding_dividend_cap=parent_funding_dividend_cap,group_funding_dividend_cap=group_funding_dividend_cap,parent_cash=parent_cash,parent_restricted=restricted,parent_free_liquidity=parent_free_stock,parent_immediate_liquidity=immediate,parent_maturities=maturities,parent_liquidity_available=available,parent_liquidity_minimum=parent_minimum,parent_liquidity_dividend_cap=liquidity_cap,parent_priority_payment=priority_payment,parent_upstream_received=upstream_received,parent_pending_dividends=pending,parent_assets=parent_assets,parent_wholesale=parent_wholesale,parent_wholesale_growth=parent_wholesale/old_parent_wholesale-1,parent_cash_sources=parent_cash_sources,parent_cash_uses=parent_cash_uses,parent_net_asset_deployment=parent_net_asset_deployment,parent_cash_earnings=parent_cash_earnings,parent_noncash_credit=parent_noncash_credit,parent_cash_residual=parent_cash_residual,deposit_runoff=deposit_runoff,liquid_asset_release=liquid_asset_release,cash_sources=sources,cash_applications=applications,cash_residual=cash_residual,clean_surplus_residual=clean_residual,entity_residual=entity_residual,PV=pv,RI_value=E0/SHARES+ri,hard_failures=hard)
        rows.append(row);s=z
        if hard:
            failure={'year':y,'conditions':hard,'required_new_authority_or_financing':'No equity issue or assumed emergency approval modeled; conditional path has no reliable ordinary-share valuation.'};break
    v=equity_valuation(E0,rows,rate)
    pv,ri,tail5,pv5,residual=v['value'],v['RI_value']-E0/SHARES,v['Y5'],v['first_five_PV'],v['residual_book_PV']
    return dict(name=name,method=method,as_of=ASOF,discount_rate=rate,parameters=p,years_requested=years,years_executed=len(rows),failure=failure,value=None if failure else pv,Y5=None if failure else tail5,RI_value=None if failure else E0/SHARES+ri,residual_book_PV=residual,first_five_PV=pv5,tail_after_five_PV=pv-pv5,final_state=s,rows=rows)

def main():
    out={'facts':FACTS,'as_of':ASOF,'initial_state':initial(),'models':{}}
    for n,r,m in [('base',.11,'spread'),('low',.115,'spread'),('high',.105,'spread'),('cycle',.11,'spread'),('structural',.11,'spread'),('funding_failure',.11,'spread'),('economic_capital',.11,'segment')]:out['models'][n]=simulate(n,250,r,m)
    out['extension500']=simulate('base',500,.11)
    out['sensitivities']={
        'solo_rwa_fraction_97':simulate('solo97',250,.11,overrides={'solo_fraction':.97}),
        'CCyB_or_buffer_plus_50bp':simulate('buffer50',250,.11,overrides={'group_buffer':.0975,'parent_buffer':.095}),
        'subs_return_minus25':simulate('subs25',250,.11,overrides={'sub_return_scale':.75}),
        'parent_RE_minus20bn':simulate('parentre',250,.11,overrides={'parent_RE':61.}),
        'credit_RWA_plus10pct':simulate('rwa10',250,.11,overrides={'rwa_extra':.10}),
        'financial_income_weaker':simulate('financialweak',250,.11,overrides={'holding_front_shift':-.002,'disposal_front_scale':0.}),
        'parent_liquidity_delay':simulate('parentliquidity',250,.11,overrides={'liquidity_maturity':.10,'upstream_delay':True})}
    out['liquidity_boundaries']={
        'flight5':simulate('flight5',250,.11,overrides={'deposit_flight':.05}),
        'flight10':simulate('flight10',250,.11,overrides={'deposit_flight':.10}),
        'flight20':simulate('flight20',250,.11,overrides={'deposit_flight':.20}),
        'flight5_maturity10_delay':simulate('flight5joint',250,.11,overrides={'deposit_flight':.05,'liquidity_maturity':.10,'upstream_delay':True})}
    print(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Midea 2026Q3. Standalone stdlib. All ledger amounts CNY billion; shares billion.
Synthetic S/N pools are economic budgets, NOT claimed separate statutory entities.
No quote is read. Complete annual states, no terminal cash sweep or principal shortcut.
"""
import copy,json,math,sys
ASOF='2026-10-30T02:30:00Z'
FACT={
 'revenue9m':367.364936,'parent_profit9m':41.393371,'adjusted_profit9m':28.787970,
 'cfo9m':40.187380,'cfo_h1':37.552090,'capex9m':5.052583,
 'group_cash':110.398412,'parent_cash':36.872537,'parent_re':13.142013,
 'parent_reserve':10.702928,'parent_sub_cost_h1':115.521479,'parent_invest_q3':121.271228,
 'parent_other_receivable_book':26.723175,'parent_other_payable_face':206.807040,
 'group_re':179.973507,'nci_equity':12.885327,'group_bank':65.047826,
 'parent_bank':25.434242,'lease':3.450692,'usd_bond_book':3.095389,
 'cb_face_each_h1_fx':7.490375,'cb2027_book_proxy':7.269104,'cb2033_book':6.520208,
 'registered_rounded':7.629934,'treasury_sep':.187650463,'cancel_treasury_sep':.123010307,
 'oct_buy_shares':.015332700,'oct_buy_cash':1.286159934,
 'clou_fraction':.2263,'clou_h1_equity':.24418,'clou_h1_parent_equity':.19501,
 'clou_h1_loss':-.21900396463,'clou_investment_cost_fy':1.672332,
 'h1_household_entity_due':24.9795587,'h1_household_entity_cost':5.952766,
 'h1_parent_sub_dividends':4.303943,'fy_parent_sub_dividends':29.620368,
}
DEFAULT={
 'method':'segments','k':.085,'terminal_g':.015,'growth_scale':1.,'margin_shift':0.,
 'revenue_initial':[180.,130.,42.,25.,33.,49.],
 'margin':[.12,.105,.135,.08,.025,.035],
 'growth':[.025,.055,.07,.045,.04,.03],
 'capital_ratio':[.25,.35,.32,.30,.38,.30],
 'tax':.20,'financial_tax':.25,'cash_yield':.018,'deposit_yield':.025,
 'cash_floor':80.,'parent_floor':5.,'capital_extra':1.2,
 'parent_cost':.8,'pool_re':158.,'pool_reserve':12.,'pool_reserve_cap':20.,
 'pool_claim':206.7,'pool_receivable_face':26.742270,'pool_receivable_allowance':.019095,
 'settlement_years':12,'upstream_payout':.90,'upstream_reserve_release':.06,
 'parent_payout':.75,'late_payout':.95,'extra_cash_release':.08,
 'fixed_realization_years':12,'trade_realization_years':8,'trade_price_factor':1.,
 'trade_tax_basis_fraction':.5,'repatriation_leakage':.005,
 'minority_profit_fraction':.018,'minority_cash':3.,'minority_payout':.70,
 'bank_rate':.03,'debt_repay_years':12,'no_rollover':False,
 'credit_capacity':20.,'fx_shock':0.,'receivable_impairment':0.,
 'working_capital_shock':0.,'cyclical':False,'structural':False,
 'option_shares':.012354138,'option_cash_per_share':41.44,
 'employee_treasury_release':.064640156,'legacy_sbc_addback':.90,
 'cb_convert':False,'cb_dilution_multiplier':1.,'cb_long_pay_year':3,'cb_fx_multiplier':1.,
 'clou_ordinary_distribution':True,'clou_nested_attribution':.19501/.24418,'clou_support':2.,'clou_coupon':.027,'clou_pay_after':3,'clou_redeem_after':12,
 'clou_never_redeem':False,'clou_never_coupon':False,'clou_growth':.05,
 'clou_margin_end':.04,'clou_bank':3.7685,'clou_bank_rate':.05,'clou_credit_cap':4.,'clou_exit_recovery_order':'pro_rata','clou_coupon_cash_tax':0.,'clou_exit_gain_tax':.25,'clou_exit_dividend_exempt':True,'clou_equity_basis_factor':1.,'clou_perpetual_basis_factor':1.,
 'secondary_nopat':34.5,'secondary_roic':.18,'secondary_growth':.04,
}
NAMES=['domestic_home','overseas_home','building','industrial','robotics','other_ex_clou_finance']
def reserve_step(re,rs,profit,cap):
    # Prior loss is repaired before statutory appropriation.
    add=min(max(0.,cap-rs),.1*max(0.,profit-max(0.,-re)))
    return re+profit-add,rs+add,add

def distribute(re,cash,floor,target):
    d=max(0.,min(max(0.,re),max(0.,cash-floor),max(0.,target)))
    return re-d,cash-d,d

def financial_step(a,year,p):
    """Opening assets earn yield; end-year amortization/disposal. Tax basis and DTL distinct."""
    op=copy.deepcopy(a); cash=0.;profit=0.;detail={}
    for name,rate,years in [('fixed',p['deposit_yield'],p['fixed_realization_years']),('loans',.045,10),('trade',.015,p['trade_realization_years']),('associate',.08,15),('derivative',0.,1),('fvoci',.015,8)]:
        z=a[name];old=z['book'];basis=z['tax_basis'];dtl=z['dtl']
        income=old*rate;income_tax=income*p['financial_tax'] if name in ('fixed','loans') else 0.
        # Linear remaining maturity is a portfolio reinvestment/runoff budget, not instrument maturity.
        fraction=1./max(1,years-year+1) if year<=years else 1.
        sold=old*fraction;basis_used=basis*fraction;dtl_used=dtl*fraction
        proceeds=sold*(p['trade_price_factor'] if name in ('trade','fvoci') else 1.)
        sale_tax=max(0.,proceeds-basis_used)*p['financial_tax'] if name in ('trade','associate','fvoci') else 0.
        tax_expense=sale_tax-dtl_used
        sale_profit=0. if name=='fvoci' else proceeds-sold-tax_expense
        oci_removed=z.get('oci',0.)*fraction
        oci_adjustment=(proceeds-sold)-tax_expense if name=='fvoci' else 0.
        nonrecycling_transfer=oci_removed+oci_adjustment if name=='fvoci' else 0.
        cash+=income-income_tax+proceeds-sale_tax;profit+=income-income_tax+sale_profit
        z['book']-=sold;z['tax_basis']-=basis_used;z['dtl']-=dtl_used
        if name=='fvoci':z['oci']-=oci_removed
        detail[name]={'opening_book':old,'opening_tax_basis':basis,'income':income,'income_tax':income_tax,'book_removed':sold,'tax_basis_removed':basis_used,'proceeds':proceeds,'cash_tax':sale_tax,'dtl_released':dtl_used,'opening_oci':op[name].get('oci',0.),'oci_removed':oci_removed,'oci_value_adjustment':oci_adjustment,'nonrecycling_oci_to_re':nonrecycling_transfer,'accounting_profit':income-income_tax+sale_profit,'end':copy.deepcopy(z)}
    return cash,profit,detail

def asset(book,kind,p):
    basis=book*(p['trade_tax_basis_fraction'] if kind in ('trade','fvoci') else 1.)
    return {'book':book,'tax_basis':basis,'dtl':(book-basis)*p['financial_tax'],'oci':(book-basis)*(1-p['financial_tax']) if kind=='fvoci' else 0.}

def initial(p):
    totalfixed=140.+56.052069-1.75
    pfixed=67.510140+31.577646-.5
    totaltrade=19.468614+2.494492; ptrade=4.871430+.182187
    assetsP={k:asset(v,k,p) for k,v in dict(fixed=pfixed,trade=ptrade,loans=0.,associate=3.765986,derivative=.167382,fvoci=0.).items()}
    assetsS={k:asset(v,k,p) for k,v in dict(fixed=totalfixed-pfixed,trade=totaltrade-ptrade,loans=12.856978+.438971,associate=4.851407-3.765986,derivative=3.748339-.849345-.564707-.167382,fvoci=.029622).items()}
    return dict(P={'cash':FACT['parent_cash']-FACT['oct_buy_cash'],'re':FACT['parent_re'],'reserve':FACT['parent_reserve'],'assets':assetsP,'bank':FACT['parent_bank'],'internal_payable':p['pool_claim'],'internal_receivable':p['pool_receivable_face'],'allowance':p['pool_receivable_allowance'],'sub_investment_cost':115.521479,'perpetual_cost':0.,'perpetual_tax_basis':0.,'clou_equity_book':FACT['clou_investment_cost_fy'],'clou_equity_tax_basis':FACT['clou_investment_cost_fy']*p['clou_equity_basis_factor'],'clou_equity_oci':0.,'perpetual_oci':0.,'perpetual_coupon_receivable':0.,'external_other_due':FACT['parent_other_payable_face']-p['pool_claim']},
      S={'cash':FACT['group_cash']-FACT['parent_cash']-p['minority_cash']-.5,'re':p['pool_re'],'reserve':p['pool_reserve'],'assets':assetsS,'bank':FACT['group_bank']-FACT['parent_bank']-p['clou_bank'],'lease':FACT['lease'],'usd':FACT['usd_bond_book'],'cb_short':FACT['cb2027_book_proxy'],'cb_long':FACT['cb2033_book'],'internal_receivable':p['pool_claim'],'internal_payable':p['pool_receivable_face'],'operating_capital':100.,'emergency_debt':0.},
      C={'cash':.5,'re':-4.17883996602,'reserve':.13450588355,'operating_capital':p['clou_bank']+FACT['clou_h1_equity']-.5,'bank':p['clou_bank'],'perpetual':0.,'coupon_arrears':0.,'revenue':4.36956,'alive':True},
      N={'cash':p['minority_cash'],'re':8.,'capital':FACT['nci_equity']-(1-FACT['clou_fraction']*p['clou_nested_attribution'])*FACT['clou_h1_equity']-p['minority_cash']},
      registered=FACT['registered_rounded'],treasury=FACT['treasury_sep']+FACT['oct_buy_shares'],revenue=list(p['revenue_initial']),secondary_nopat=p['secondary_nopat'],cum_holder=0.)

def clou_step(C,P,year,p,scale):
    P.setdefault('perpetual_tax_basis',P['perpetual_cost']*p['clou_perpetual_basis_factor'])
    P.setdefault('clou_equity_book',FACT['clou_investment_cost_fy']);P.setdefault('clou_equity_tax_basis',FACT['clou_investment_cost_fy']*p['clou_equity_basis_factor'])
    P.setdefault('clou_equity_oci',0.);P.setdefault('perpetual_oci',0.)
    old=copy.deepcopy(C);profitP=0.
    f={k:0. for k in ['support','bank_repayment_from_support','revenue','margin','investment','bank_interest','profit','reserve_add','coupon_due','coupon_paid','redemption','new_external_borrowing','ordinary_dividend','majority_dividend','liquidation_proceeds','disposal_book_loss','parent_guarantee_cash','parent_investment_writeoff','parent_perpetual_writeoff','cash_interest','scheduled_bank_repayment','coupon_cash_tax','perpetual_principal_tax','perpetual_basis_removed','liquidation_coupon_paid','liquidation_coupon_tax','perpetual_principal_return','perpetual_principal_loss','unpaid_coupon_extinguished_on_completed_liquidation','equity_gross_proceeds','equity_exempt_distribution','equity_capital_proceeds','equity_taxable_gain','equity_cash_tax','equity_basis_removed','equity_book_removed','equity_net_cash','perpetual_claim_principal','perpetual_claim_interest','perpetual_claim_recovery_ratio','ordinary_residual_gross','nested_minority_exit_cash','clou_outside_owner_exit_cash','parent_exit_oci_reclassification']}
    if not C['alive']:
        f['closed']=True
        return f,0.
    support=p['clou_support'] if year==1 else 0.;P['cash']-=support;P['perpetual_cost']+=support;P['perpetual_tax_basis']+=support*p['clou_perpetual_basis_factor'];C['cash']+=support;C['perpetual']+=support
    cbankrep=min(C['bank'],support);C['bank']-=cbankrep;C['cash']-=cbankrep
    crev=C['revenue']*(1+(p['clou_growth'] if year<=5 else p['terminal_g']));cinvest=max(0.,crev-C['revenue'])*.30;C['revenue']=crev
    cmargin=-.075+(p['clou_margin_end']+.075)*min(1.,(year-1)/5)
    if p['structural']:cmargin=-.02
    cinterest=old['bank']*p['clou_bank_rate']
    c_cash_interest=old['cash']*p['cash_yield']
    cpretax=crev*cmargin-cinterest+c_cash_interest;cprofit=cpretax-max(cpretax,0.)*.25
    C['cash']+=cprofit-cinvest;C['operating_capital']+=cinvest
    C['re'],C['reserve'],creserve=reserve_step(C['re'],C['reserve'],cprofit,.836275304)
    cscheduled=min(C['bank'],max(0.,C['cash']-.5*scale)*.5);C['cash']-=cscheduled;C['bank']-=cscheduled
    coupon_due=old['perpetual']*p['clou_coupon'];C['coupon_arrears']+=coupon_due
    coupon=0.
    if year>=p['clou_pay_after'] and not p['clou_never_coupon']:
        coupon=max(0.,min(C['coupon_arrears'],C['cash']-.3*scale))
    C['cash']-=coupon;C['re']-=coupon;C['coupon_arrears']-=coupon;coupon_tax=coupon*p['clou_coupon_cash_tax'];P['cash']+=coupon-coupon_tax;profitP+=coupon-coupon_tax
    redeemed=0.
    if year>=max(3,p['clou_redeem_after']) and year%2==1 and not p['clou_never_redeem'] and C['coupon_arrears']<1e-10:
        redeemed=C['perpetual'] if C['cash']-.5*scale>=C['perpetual'] else 0.
    basis_removed=P['perpetual_tax_basis']*redeemed/P['perpetual_cost'] if P['perpetual_cost'] else 0.
    principal_tax=max(0.,redeemed-basis_removed)*p['clou_exit_gain_tax']
    C['cash']-=redeemed;C['perpetual']-=redeemed;P['cash']+=redeemed-principal_tax;P['perpetual_cost']-=redeemed;P['perpetual_tax_basis']-=basis_removed;profitP-=principal_tax
    cborrow=max(0.,min(p['clou_credit_cap']-C['bank'],.3*scale-C['cash']));C['cash']+=cborrow;C['bank']+=cborrow
    C['re'],C['cash'],cdiv=distribute(C['re'],C['cash'],.5*scale,0. if not p['clou_ordinary_distribution'] else (.65 if year<=5 else .95)*max(cprofit-coupon,0.)+(.05*max(0.,C['cash']-.5*scale) if year>5 else 0.))
    majority_cdiv=cdiv*FACT['clou_fraction']*p['clou_nested_attribution'];P['cash']+=majority_cdiv;profitP+=majority_cdiv
    f.update(support=support,bank_repayment_from_support=cbankrep,revenue=crev,margin=cmargin,investment=cinvest,bank_interest=cinterest,profit=cprofit,reserve_add=creserve,coupon_due=coupon_due,coupon_paid=coupon,redemption=redeemed,new_external_borrowing=cborrow,ordinary_dividend=cdiv,majority_dividend=majority_cdiv,nested_minority_dividend=cdiv*(1-p['clou_nested_attribution']),clou_outside_owner_dividend=cdiv*p['clou_nested_attribution']*(1-FACT['clou_fraction']),closed=False,coupon_cash_tax=coupon_tax,perpetual_principal_tax=principal_tax,perpetual_basis_removed=basis_removed,cash_interest=c_cash_interest,scheduled_bank_repayment=cscheduled)
    if C['cash']<0:
        # Explicit conditional wind-down, not ongoing unfunded growth. 60% realisation, no tax refund.
        proceeds=.60*C['operating_capital'];bookloss=C['operating_capital']-proceeds
        C['cash']+=proceeds;C['operating_capital']=0.;C['re']-=bookloss
        # Stress assumption of full bank support, NOT assertion of subsidiary-specific disclosed guarantee.
        guarantee=max(0.,C['bank']-C['cash']);P['cash']-=guarantee;profitP-=guarantee;C['cash']+=guarantee
        C['cash']-=C['bank'];C['bank']=0.
        # Contract puts principal AND unpaid interest after ordinary creditors and before equity.
        # Within that common rank, proportional recovery is the disclosed budget, not a legal priority claim.
        claim_principal=C['perpetual'];claim_interest=C['coupon_arrears'];total_claim=claim_principal+claim_interest
        available=max(0.,C['cash']);ratio=min(1.,available/total_claim) if total_claim else 1.
        if p['clou_exit_recovery_order']=='pro_rata':perp_return=claim_principal*ratio;exit_coupon=claim_interest*ratio
        elif p['clou_exit_recovery_order']=='principal_first':
            perp_return=min(claim_principal,available);exit_coupon=min(claim_interest,max(0.,available-perp_return))
        elif p['clou_exit_recovery_order']=='interest_first':
            exit_coupon=min(claim_interest,available);perp_return=min(claim_principal,max(0.,available-exit_coupon))
        else:raise ValueError('unknown hypothetical recovery order')
        C['cash']-=perp_return+exit_coupon;C['re']-=exit_coupon
        exit_coupon_tax=exit_coupon*p['clou_coupon_cash_tax']
        oldcost=P['perpetual_cost'];oldbasis=P['perpetual_tax_basis']
        exit_principal_tax=max(0.,perp_return-oldbasis)*p['clou_exit_gain_tax']
        P['cash']+=perp_return+exit_coupon-exit_coupon_tax-exit_principal_tax
        perp_loss=oldcost-perp_return;profitP+=exit_coupon-exit_coupon_tax-perp_loss-exit_principal_tax
        P['perpetual_cost']=0.;P['perpetual_tax_basis']=0.;C['perpetual']=0.
        unpaid_interest=claim_interest-exit_coupon;C['coupon_arrears']=0.
        # The unrecognised, indefinitely deferred coupon has no opening parent RE/basis asset to write down twice.
        residual=max(0.,C['cash']);attribution=FACT['clou_fraction']*p['clou_nested_attribution']
        equityreturn=residual*attribution
        exempt=min(equityreturn,max(0.,C['re'])*attribution) if p['clou_exit_dividend_exempt'] else 0.
        capital_proceeds=equityreturn-exempt;equity_basis=P['clou_equity_tax_basis'];invcost=P['clou_equity_book']
        taxable_gain=max(0.,capital_proceeds-equity_basis);equity_tax=taxable_gain*p['clou_exit_gain_tax']
        P['cash']+=equityreturn-equity_tax;P['sub_investment_cost']-=invcost
        profitP+=equityreturn-invcost-equity_tax
        # Actual direct holding is cost-method, not a hypothetical recyclable OCI asset.
        assert P['clou_equity_oci']==0. and P['perpetual_oci']==0.,'unsupported OCI type: must classify before disposal'
        oci=0.
        P['clou_equity_oci']=0.;P['perpetual_oci']=0.;P['clou_equity_book']=0.;P['clou_equity_tax_basis']=0.
        C['cash']=0.;C['alive']=False;C['re']=0.;C['reserve']=0.;C['revenue']=0.
        f.update(liquidation_proceeds=proceeds,disposal_book_loss=bookloss,parent_guarantee_cash=guarantee,
          parent_investment_writeoff=invcost-equityreturn,parent_perpetual_writeoff=perp_loss,closed=True,
          liquidation_coupon_paid=exit_coupon,liquidation_coupon_tax=exit_coupon_tax,
          perpetual_principal_return=perp_return,perpetual_principal_loss=perp_loss,
          perpetual_principal_tax=principal_tax+exit_principal_tax,perpetual_basis_removed=basis_removed+oldbasis,
          unpaid_coupon_extinguished_on_completed_liquidation=unpaid_interest,
          perpetual_claim_principal=claim_principal,perpetual_claim_interest=claim_interest,perpetual_claim_recovery_ratio=ratio,
          equity_gross_proceeds=equityreturn,equity_exempt_distribution=exempt,equity_capital_proceeds=capital_proceeds,
          equity_taxable_gain=taxable_gain,equity_cash_tax=equity_tax,equity_basis_removed=equity_basis,equity_book_removed=invcost,
          equity_net_cash=equityreturn-equity_tax,ordinary_residual_gross=residual,
          nested_minority_exit_cash=residual*(1-p['clou_nested_attribution']),
          clou_outside_owner_exit_cash=residual*p['clou_nested_attribution']*(1-FACT['clou_fraction']),
          parent_exit_oci_reclassification=oci)
    return f,profitP

def step(state,year,p):
    st=copy.deepcopy(state);P,S,C,N=(st[x] for x in ('P','S','C','N'));op=state
    flows={};seg=[];gterminal=p['terminal_g']
    gross_ebit=0.;investment=0.;revenue=0.
    for i,name in enumerate(NAMES):
        g=p['growth'][i]*p['growth_scale'] if year<=5 else p['growth'][i]*p['growth_scale']+(gterminal-p['growth'][i]*p['growth_scale'])*min(1.,(year-5)/10)
        margin=p['margin'][i]+p['margin_shift']
        if p['cyclical'] and year<=3:g-= [.10,.05,.015][year-1];margin-= [.018,.01,.003][year-1]
        if p['structural']:
            g=min(g,.005);margin-=.025 if i<2 else .015
        old=st['revenue'][i];rv=old*(1+g);st['revenue'][i]=rv
        inv=max(0.,rv-old)*p['capital_ratio'][i] # contraction doesn't conjure immediate liquidation cash
        ebit=rv*margin;gross_ebit+=ebit;investment+=inv;revenue+=rv
        seg.append({'name':name,'opening_revenue':old,'growth':g,'revenue':rv,'margin':margin,'ebit':ebit,'growth_capital':inv})
    committed_floor=8.192824/2 if year<=2 else 0.
    investment=max(investment,committed_floor)
    nopat=gross_ebit*(1-p['tax'])
    if p['method']=='reinvestment':
        g=p['secondary_growth']*p['growth_scale'] if year<=5 else p['secondary_growth']*p['growth_scale']+(gterminal-p['secondary_growth']*p['growth_scale'])*min(1.,(year-5)/10)
        if p['structural']:g=.005
        old=st['secondary_nopat'];nopat=old*(1+g);st['secondary_nopat']=nopat
        investment=max(committed_floor,max(0.,nopat-old)/p['secondary_roic']);gross_ebit=nopat/(1-p['tax'])
    scale=revenue/sum(p['revenue_initial']);floorP=p['parent_floor']*scale;floorS=(p['cash_floor']-p['parent_floor']-p['minority_cash']-.5)*scale
    finPC,finPP,fp=financial_step(P['assets'],year,p);finSC,finSP,fs=financial_step(S['assets'],year,p)
    p_interest=op['P']['cash']*p['cash_yield']*(1-p['financial_tax']);s_interest=op['S']['cash']*p['cash_yield']*(1-p['financial_tax'])
    p_binterest=op['P']['bank']*p['bank_rate'];s_binterest=(op['S']['bank']+op['S']['emergency_debt'])*p['bank_rate']
    lease_exp=op['S']['lease']*.03
    s_interest_tax_shield=(s_binterest+lease_exp)*p['tax'] if nopat>0 else 0.
    usd_interest=op['S']['usd']*.0288
    P['cash']+=finPC+p_interest-p_binterest-p['parent_cost']*scale
    p_profit=finPP+p_interest-p_binterest-p['parent_cost']*scale
    # NCI economic portfolio separate from cash legally owed by the parent pool (wholly-owned treasury sources).
    nprofit=nopat*p['minority_profit_fraction'];ninvest=investment*p['minority_profit_fraction']
    ninterest=op['N']['cash']*p['cash_yield']*(1-p['financial_tax'])
    N['cash']+=nprofit+ninterest-ninvest;N['capital']+=ninvest;N['re']+=nprofit+ninterest
    N['re'],N['cash'],ndiv=distribute(N['re'],N['cash'],p['minority_cash']*scale,p['minority_payout']*(nprofit+ninterest))
    extra=p['capital_extra']*scale;shock=p['working_capital_shock'] if year==1 else 0.
    # SBC is an existing noncash expense; already-bought employee treasury is released below. No new repurchase assumed.
    sbc=p['legacy_sbc_addback'] if year<=4 else 0.
    majority_nopat=nopat-nprofit
    S['cash']+=majority_nopat+finSC+s_interest-s_binterest-lease_exp+s_interest_tax_shield-usd_interest-investment+ninvest-extra+ sbc-shock
    s_profit=majority_nopat+finSP+s_interest-s_binterest-lease_exp+s_interest_tax_shield-usd_interest
    S['operating_capital']+=investment-ninvest+extra+shock
    # Opening derivative positions are realised once above; a future unhedged FX stress is an incremental cash AND earnings loss.
    fx=p['fx_shock'] if year==1 else 0.;S['cash']-=fx;s_profit-=fx
    cflow,c_parent_profit=clou_step(C,P,year,p,scale);p_profit+=c_parent_profit
    cprofit=cflow['profit']
    # Intercompany claim collection and payment are separate executed cash movements; never profit from principal.
    wantPS=min(P['internal_payable'],p['pool_claim']/p['settlement_years'])
    payPS=max(0.,min(wantPS,P['cash']-floorP));P['cash']-=payPS;S['cash']+=payPS;P['internal_payable']-=payPS;S['internal_receivable']-=payPS
    wantSP=min(S['internal_payable'],p['pool_receivable_face']/p['settlement_years'])
    paySP=max(0.,min(wantSP,S['cash']-floorS));S['cash']-=paySP;P['cash']+=paySP;S['internal_payable']-=paySP;P['internal_receivable']-=paySP
    allowance_release=op['P']['allowance']*(paySP/op['P']['internal_receivable']) if op['P']['internal_receivable'] else 0.
    P['allowance']-=allowance_release;p_profit+=allowance_release
    impairment=0.
    if year==1 and p['receivable_impairment']:
        impairment=P['internal_receivable']*p['receivable_impairment'];P['allowance']+=impairment;p_profit-=impairment
        # Accounting impairment doesn't extinguish borrower face; no consolidated incremental cash loss.
    # Callable obligations: principal cash and debt book; conversion mutually exclusive.
    cb_cash=0.;cb_shares=0.;cb_expense=0.
    for key,payyear,face,strike in [('cb_short',1,FACT['cb_face_each_h1_fx'],91.82),('cb_long',p['cb_long_pay_year'],FACT['cb_face_each_h1_fx']*(1.0615 if p['cb_long_pay_year']==3 else (1.1046 if p['cb_long_pay_year']==5 else 1.1495)),109.78)]:
        opening=op['S'][key]
        if opening<=0.:continue
        target=face*p['cb_fx_multiplier'];remaining=payyear-year+1
        # Effective accretion reaches exact contractual redemption cash, starting from disclosed/proxy carrying amount.
        expense=opening*((target/opening)**(1./max(remaining,1))-1.)
        S[key]+=expense;cb_expense+=expense;s_profit-=expense
        if year==payyear:
            if p['cb_convert']:
                issued=8.624/strike*p['cb_dilution_multiplier'];cb_shares+=issued;st['registered']+=issued
            else:cb_cash+=target;S['cash']-=target
            S[key]=0.
    usdpaid=S['usd'] if year==1 else 0.;S['usd']-=usdpaid;S['cash']-=usdpaid
    # Normal annual refinancing; no blanket first-year acceleration except clearly labelled stress.
    prep=min(P['bank'],FACT['parent_bank']/p['debt_repay_years'])
    srep=min(S['bank'],(FACT['group_bank']-FACT['parent_bank']-p['clou_bank'])/p['debt_repay_years'])
    if p['no_rollover'] and year==1:prep=P['bank'];srep=S['bank']
    if not (p['no_rollover'] and year==1):
        prep=max(0.,min(prep,P['cash']-floorP));srep=max(0.,min(srep,S['cash']-floorS))
    P['cash']-=prep;P['bank']-=prep;S['cash']-=srep;S['bank']-=srep
    leasepaid=min(S['lease'],FACT['lease']/10);S['cash']-=leasepaid;S['lease']-=leasepaid
    # No secret new equity: finite emergency bank capacity and feasibility flag; payout clips first.
    emergency=max(0.,min(p['credit_capacity']-S['emergency_debt'],floorS-S['cash']));S['cash']+=emergency;S['emergency_debt']+=emergency
    erpay=max(0.,min(S['emergency_debt'],S['cash']-floorS));S['cash']-=erpay;S['emergency_debt']-=erpay
    p_fvoci_transfer=sum(z['nonrecycling_oci_to_re'] for z in fp.values());s_fvoci_transfer=sum(z['nonrecycling_oci_to_re'] for z in fs.values())
    P['re']+=p_fvoci_transfer;S['re']+=s_fvoci_transfer
    S['re'],S['reserve'],sreserve=reserve_step(S['re'],S['reserve'],s_profit,p['pool_reserve_cap'])
    target_up=max(0.,s_profit)*p['upstream_payout']+p['upstream_reserve_release']*max(0.,op['S']['re']-20.*scale)
    S['re'],S['cash'],up=distribute(S['re'],S['cash'],floorS,target_up)
    leak=up*p['repatriation_leakage'];P['cash']+=up-leak;p_profit+=up-leak
    # Parent already has statutory reserve well above 50% registered capital; capital actions tracked separately.
    P['re'],P['reserve'],preserve=reserve_step(P['re'],P['reserve'],p_profit,.5*st['registered'])
    options=p['option_shares'] if year==1 else 0.;optioncash=options*p['option_cash_per_share'];P['cash']+=optioncash;st['registered']+=options
    release=min(st['treasury'],p['employee_treasury_release']/4) if year<=4 else 0.;st['treasury']-=release
    cancelled=FACT['cancel_treasury_sep']+FACT['oct_buy_shares'] if year==1 else 0.;st['registered']-=cancelled;st['treasury']-=cancelled
    otherpaid=P['external_other_due'];P['cash']-=otherpaid;P['external_other_due']=0.
    # Distribution policy anchored to normal ordinary economics, not upstream declaration timing alone.
    normal_owner=majority_nopat+cprofit*FACT['clou_fraction']*p['clou_nested_attribution']+cflow['coupon_paid']*(1-FACT['clou_fraction']*p['clou_nested_attribution'])-cflow['coupon_cash_tax']-cflow['perpetual_principal_tax']+finPP+finSP+p_interest+s_interest-p_binterest-s_binterest-lease_exp+s_interest_tax_shield-usd_interest-p['parent_cost']*scale-cb_expense
    target=max(0.,normal_owner)*(p['parent_payout'] if year<=5 else p['late_payout'])
    if year>5:target+=p['extra_cash_release']*max(0.,P['cash']-floorP-P['internal_payable'])
    P['re'],P['cash'],holder=distribute(P['re'],P['cash'],floorP,target)
    shares=st['registered']-st['treasury'];dps=holder/shares;st['cum_holder']+=holder
    feasible=min(P['cash'],S['cash'],C['cash'],N['cash'])>=-1e-8
    flows.update(year=year,segments=seg,nopat=nopat,majority_nopat=majority_nopat,nci_profit=nprofit,nci_investment=ninvest,nci_cash_distribution=ndiv,capital_growth=investment,capital_commitment_minimum=committed_floor,capital_extra=extra,working_capital_shock=shock,sbc_cash_addback=sbc,fx_cash_loss=fx,revenue=revenue,floorP=floorP,floorS=floorS,financialP=fp,financialS=fs,p_cash_interest=p_interest,s_cash_interest=s_interest,p_bank_interest=p_binterest,s_bank_interest=s_binterest,lease_interest=lease_exp,sub_interest_tax_shield=s_interest_tax_shield,usd_interest=usd_interest,p_accounting_profit=p_profit,s_accounting_profit=s_profit,p_fvoci_transfer=p_fvoci_transfer,s_fvoci_transfer=s_fvoci_transfer,p_stat_reserve_add=preserve,s_stat_reserve_add=sreserve,clou=cflow,parent_to_sub_principal=payPS,sub_to_parent_principal=paySP,allowance_release=allowance_release,parent_receivable_impairment=impairment,cb_cash=cb_cash,cb_conversion_shares=cb_shares,cb_book_accretion=cb_expense,usd_cash=usdpaid,parent_bank_repay=prep,sub_bank_repay=srep,lease_repay=leasepaid,emergency_borrow=emergency,emergency_repay=erpay,upstream_declared_and_paid=up,upstream_tax=leak,parent_external_other_paid=otherpaid,option_shares=options,option_cash=optioncash,employee_treasury_released=release,treasury_cancelled=cancelled,normal_owner_profit=normal_owner,holder_target=target,holder_cash=holder,shares=shares,dps=dps,feasible=feasible,end=st)
    return st,flows

def project(overrides=None,horizon=320,start=None,startyear=1):
    p=copy.deepcopy(DEFAULT);p.update(overrides or {});st=initial(p) if start is None else copy.deepcopy(start);init=copy.deepcopy(st);rows=[];pv=0.
    for y in range(startyear,horizon+1):
        st,row=step(st,y,p);rows.append(row);pv+=row['dps']/(1+p['k'])**(y-startyear+1)
    return {'assumptions':p,'initial':init,'years':rows,'pv_per_share':pv,'all_feasible':all(x['feasible'] for x in rows),'unrealised_end_state':st,'tail_not_added':True}

def build():
    cases={'base':{},'core_low':{'margin_shift':-.0025,'growth_scale':.85,'k':.09},'core_high':{'margin_shift':.0025,'growth_scale':1.1,'k':.08},'secondary':{'method':'reinvestment'},'cycle':{'cyclical':True,'working_capital_shock':8.},'structural':{'structural':True,'working_capital_shock':15.,'clou_margin_end':-.02},'upside':{'growth_scale':1.35,'margin_shift':.006},'k_plus_100bp':{'k':.095},'operating_margin_minus_1pp':{'margin_shift':-.01},'capital_intensity_plus50':{'capital_ratio':[x*1.5 for x in DEFAULT['capital_ratio']]},'upstream_slow':{'upstream_payout':.60,'upstream_reserve_release':.025,'settlement_years':24},'legal_reserve_capacity_low':{'pool_re':80.},'liquidity_floor_high':{'cash_floor':110.},'financial_principal_haircut':{'trade_price_factor':.5},'no_clou_approval':{'clou_support':0.},'clou_defer_forever':{'clou_never_coupon':True,'clou_never_redeem':True},'clou_late_recovery':{'clou_pay_after':12,'clou_redeem_after':25},'cb_conversion':{'cb_convert':True,'cb_dilution_multiplier':1.10},'cb_2033_redemption':{'cb_long_pay_year':7},'no_bank_rollover':{'no_rollover':True,'working_capital_shock':20.},'parent_receivable_markdown':{'receivable_impairment':.25},'unhedged_fx_loss':{'fx_shock':3.},'minority_share_higher':{'minority_profit_fraction':.03},'options_upper_bound':{'option_shares':.028849231},'clou_nested_low':{'clou_nested_attribution':.65},'clou_nested_high':{'clou_nested_attribution':.95},'clou_no_ordinary_distribution':{'clou_ordinary_distribution':False},'clou_coupon_tax25':{'clou_coupon_cash_tax':.25},'clou_exit_gain_exempt':{'clou_exit_gain_tax':0.},'clou_low_tax_basis':{'clou_equity_basis_factor':.5,'clou_perpetual_basis_factor':.5},'clou_exit_no_exempt_distribution':{'clou_exit_dividend_exempt':False}}
    allcases={name:project(a) for name,a in cases.items()}
    b=allcases['base'];ds=[x['dps'] for x in b['years'][:5]]
    y5=b['years'][4]['end'];low=project({'k':.09},start=y5,startyear=6);high=project({'k':.08},start=y5,startyear=6)
    # Independent Y5 state continuation; future discount variation only, all actual first five cash fixed.
    holder={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':ASOF,'base_case_distributions_per_share':ds,'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':low['pv_per_share'],'high':high['pv_per_share']}}}
    convergence={str(n):sum(r['dps']/(1+DEFAULT['k'])**r['year'] for r in b['years'][:n]) for n in (120,180,240,320)}
    return {'schema':'midea_complete_economic_ledger_v1','information_cutoff':ASOF,'units':'CNY billion and billion shares; per_share CNY','facts':FACT,'value_range':{'low':round(allcases['core_low']['pv_per_share'],2),'high':round(allcases['core_high']['pv_per_share'],2),'currency':'CNY'},'holder':holder,'convergence':convergence,'cases':allcases,'year5_low':low,'year5_high':high}
if __name__=='__main__':
    json.dump(build(),sys.stdout,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False);sys.stdout.write('\n')

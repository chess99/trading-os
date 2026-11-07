#!/usr/bin/env python3
"""Self-contained stdlib model. Monetary amounts: CNY billion, shares billion.
No price input; stdout is entire deterministic JSON, never truncated.
"""
import json, math, copy
ASOF='2026-10-28T23:59:59+08:00'
INPUTS={
 'opening':{'p_cash':3.52171122272,'s_cash':11.33749287941,'p_re':.11670233358,'p_reserve':.32831860261,'p_capital':1.258151885,'p_capital_reserve':24.326714134,
 'buyback_loan':0.,'buyback_new_treasury':0.,'p_earmark':3.1,'foreign_local_re':6.8,'domestic_local_re':1.2,'s_re':8.,'s_reserve':1.,'s_capital':9.,'s_capital_reserve':4.,'p_debt':9.1756957764,'s_debt':4.26863783424,
 'loan':2.10806156831,'investment_cost':23.29176180294,'investment_book':22.88285822232,'receivable':.50085185,
 'p_financial':2.36482145047,'s_financial':4.78546042299,'capital':20.,'nci_book':-.01938194004,'goodwill':3.96329035235,
 'issued':1.258151885,'treasury':.008750205,'treasury_cost':.81339038565,'new_treasury_cost':0.,'pending_net':.50085185,'pending_gross':.50085185},
 'units':'CNY billion; billion shares; per share CNY',
 'annual_periods':'Y1-Y5 each full twelve months after cutoff, annualized operations not nine-month amounts; September consolidated / June parent proxy rolled to cutoff with zero unobserved net movements; sensitivities test proxy risk',
 'bridge_notes':{'convertible':'2.432323bn principal included in opening debt, base pays 2.6755553bn at Y1 (110% redemption budget); redemption over carrying embedded through Y1 financing charge adjustment; conversion sensitivity removes principal and adds principal/159.02 shares, not both debt and dilution',
 'sub_re':'8bn aggregate available-profit budget across Beijing/CIS and distribution chains after local restrictions, not reported legal RE. 4/12bn and delayed remittance tested.',
 'parent_cost':'23.29176bn historical gross investment incl prior impairment; book22.88286; future funding added. Loan2.10806 is separate principal, never investment income.',
 'research':'all cash R&D expensed in normalized EBIT; capital target excludes duplicated capitalized R&D; maintenance capex equals depreciation in net investment formula.'},
 'base_segments':{'auto':6.6,'consumer':6.,'emerging':3.7,'medical_security':3.2,'analog_display':3.1,'agency':7.8},
 'growth5':{'auto':[.10,.12,.11,.10,.09],'consumer':[.03,.07,.06,.05,.04],'emerging':[.18,.18,.16,.14,.12],'medical_security':[.10,.10,.09,.08,.07],'analog_display':[.12,.12,.10,.09,.08],'agency':[.05,.04,.03,.03,.03]},
 'gm':{'auto':.39,'consumer':.32,'emerging':.40,'medical_security':.39,'analog_display':.28,'agency':.08},
 'rd_design':.16,'sga_total':.04,'tax':.20,'cash_yield':.018,'debt_rate':.035,'remittance_tax':.03,'nci':.005,
 'external_debt_capacity_budget':13.89433361064,'parent_financial_distress_recovery':.85,'accelerated_loan_recovery_budget':.9,
 'p_overhead':.12,'capital_design':.68,'capital_agency':.32,'cash_floor_ratio':.12,'p_floor':.5,
 'r':.095,'g':.02,'sub_payout':[.55,.65,.75,.80,.85],'parent_payout':[.35,.35,.4,.45,.5],
 'noncash_compensation_annual_first5':.25,'parent_compensation_fraction':.10,
 'stock_awards_billion':.006,'future_grant_budget_billion':.010,'max_unused_H_budget_billion':.032,
 'option_budget_billion':.020875147,'option_2023':.005887597,'option_2025':.01498755,'option_2023_price':77.91,'option_2025_price':138.57,'option_budget_note':'2023 third window approved5.887597m only; second window expired10/9 excluded from future. Opening exercise sensitivity separately tests unobserved 0-1.507691m past exercise. 2025 grant19.9834m budget75%; 2023 price77.91,2025 price138.57. Full-rights stress25.870997m, excludes known forfeitures; no treasury-stock method.',
 'capital_method':{'initial_roic':.145,'peak_roic':.17,'terminal_roic':.12,'growth':[.065,.07,.065,.06,.055]},
}
SCENARIOS={
 'base':{}, 'holder_tail_low':{'tail_only':True,'gm_shift':-.006,'rd_shift':.003,'growth_shift':-.01,'r':.10}, 'holder_tail_high':{'tail_only':True,'gm_shift':.006,'rd_shift':-.003,'growth_shift':.01,'r':.09}, 'rd_plus_1pct':{'rd_shift':.01},
 'core_low':{'gm_shift':-.006,'rd_shift':.003,'growth_shift':-.01,'r':.10},
 'core_high':{'gm_shift':.006,'rd_shift':-.003,'growth_shift':.01,'r':.09},
 'cyclical':{'cycle':True,'r':.10},
 'structural':{'structural':True,'gm_shift':-.055,'rd_shift':.02,'growth_shift':-.04,'r':.11,'g':.005},
 'optimistic':{'gm_shift':.015,'growth_shift':.03,'r':.09},
 'past_exercise_opening_max':{'past_exercise':.001507691},'bond_refinance_refused':{'bond_refused':True},'bond_refusal_illiquid_assets':{'bond_refused':True,'no_loan_acceleration':True,'financial_recovery':.5},'tax_loss_limited_use':{'tax_loss_use':True},'old_treasury_transfer':{'past_exercise_opening_max':{'past_exercise':.001507691},'bond_refinance_refused':{'bond_refused':True},'bond_refusal_illiquid_assets':{'bond_refused':True,'no_loan_acceleration':True,'financial_recovery':.5},'tax_loss_limited_use':{'tax_loss_use':True},'old_treasury_transfer':True},'noncash_compensation_double':{'compensation':.5},'foreign_capacity_half':{'foreign_capacity':.5},'sub_re_4':{'sub_re':4.},'sub_re_12':{'sub_re':12.},
 'loan_delay':{'loan_delay':True},'buyback_zero':{'buyback':0.},'buyback_max':{'buyback':.5},'low_payout':{'low_payout':True},'minority_claim':{'claim':.6},'remittance_delay':{'delay':2,'remittance_tax':.08},
 'working_capital_stress':{'capital_scale':1.2,'p_cash_shift':-1.,'p_re_shift':-.5},
 'full_rights':{'future_grant':.032,'options':.025870997},
 'conversion':{'convert':True},
 'exit':{'structural':True,'gm_shift':-.08,'rd_shift':.03,'growth_shift':-.06,'r':.11,'exit_year':8},
}
def statutory(re, reserve, capital, income):
    # Prior losses absorbed before reserve appropriation; no capital-reserve transfer.
    reserve_add=min(max(0.,(re+income)-max(re,0.))*.10,max(0.,capital*.5-reserve))
    return re+income-reserve_add,reserve+reserve_add,reserve_add

def payment(re,cash,floor,budget):
    return max(0.,min(max(re,0.),max(cash-floor,0.),max(budget,0.)))

def tax_cash_step(pretax,buckets,year,use_losses=False):
    # Five future years is an explicit bounded tax-asset budget, NOT one law for all foreign entities.
    # Core never monetizes losses; optional sensitivity uses existing unexpired losses only.
    alive=[(t,v) for t,v in buckets if year-t<=5]
    taxable=max(0.,pretax)
    if use_losses:
        remain=[]
        for t,v in alive:
            used=min(taxable,v);taxable-=used
            if v-used>1e-12:remain.append((t,v-used))
        alive=remain
    if pretax<0:alive.append((year,-pretax))
    return taxable*.20,alive

def exit_bridge(s, recovery=.65, fee=.8):
    # Statutory wind-down scenario, no guarantee assumed for intercompany credit.
    # Trade payables already netted in operating capital, not charged twice.
    op=s['capital']*recovery; f=s['s_financial']*.75
    gross=op+s['s_cash']+f
    senior=s['s_debt']+.51554653691+fee
    senior_paid=min(gross,senior); available=max(0.,gross-senior)
    interclaims=s['loan']+s['pending_gross']
    recovery_fraction=min(1.,available/interclaims) if interclaims else 1.
    loan_recovery=s['loan']*recovery_fraction
    pending_gross_recovery=s['pending_gross']*recovery_fraction
    pending_net_recovery=s['pending_net']*recovery_fraction
    residual=max(0.,available-interclaims)
    nci=residual*INPUTS['nci']; equity=(residual-nci)*(1-INPUTS['remittance_tax'])
    gain=equity-s['investment_cost']; tax=max(0.,gain)*.25
    loan_loss=s['loan']-loan_recovery; dividend_loss=s['pending_net']-pending_net_recovery
    guarantee_call=min(s['s_debt'],max(0.,senior-gross))
    parent_cash=s['p_cash']+equity-tax+loan_recovery+pending_net_recovery+s['p_financial']*.75-s['p_debt']-.15-guarantee_call
    parent_income=equity-tax-s['investment_book']-loan_loss-dividend_loss-s['p_financial']*.25-guarantee_call-.15
    pre,res,add=statutory(s['p_re'],s['p_reserve'],s['p_capital'],parent_income)
    final=max(0.,parent_cash)
    guarantee_paid=min(guarantee_call,max(0.,parent_cash+guarantee_call))
    return {'operating_recovery':op,'financial_recovery':f,'gross_sub_assets':gross,'senior_creditors_and_cost':senior,'senior_paid':senior_paid,'senior_unpaid':senior-senior_paid,'intercompany_creditor_recovery_fraction':recovery_fraction,'sub_residual':residual,'nci_exit':nci,'sub_equity_to_parent':equity,'intercompany_loan_principal_recovered':loan_recovery,'parent_loan_loss':loan_loss,'parent_guarantee_call_budget':guarantee_call,'parent_guarantee_cash_paid':guarantee_paid,'parent_guarantee_unpaid':guarantee_call-guarantee_paid,'pending_gross_recovered':pending_gross_recovery,'pending_net_recovered':pending_net_recovery,'parent_dividend_receivable_writeoff':dividend_loss,'parent_historical_plus_future_cost':s['investment_cost'],'parent_book_cost':s['investment_book'],'parent_disposal_gain_tax_base':gain,'parent_tax':tax,'parent_realized_income':parent_income,'parent_post_sale_re':pre,'parent_reserve':res,'parent_creditor_shortfall':max(0.,-parent_cash),'parent_liquidation_after_external_creditors':final,'ordinary_dividend_before_liquidation':payment(pre,max(parent_cash,0),0,final),'capital_return_only_on_final_liquidation':max(0,final-max(pre,0)),'insolvent':senior>gross or parent_cash<0,'legal_condition':'creditor priority and formal liquidation; unpaid external sub borrowing treated as fully parent-guaranteed stress budget; no extra guarantee on intercompany claims'}

def operating(y,rev,k,scenario,method):
    g=scenario.get('g',INPUTS['g']); gs=scenario.get('growth_shift',0.)
    if method=='capital':
        cg=INPUTS['capital_method']['growth'][y-1] if y<=5 else max(g,.055-(y-5)*.005)
        cg+=gs if y<=10 else 0
        if scenario.get('cycle') and y<=2:cg=-.02
        nk=k*(1+cg)
        roic=(.145+min(y-1,4)*.00625) if y<=5 else max(.12,.17-(y-5)*.005)
        roic+=scenario.get('gm_shift',0)*1.2-scenario.get('rd_shift',0)
        if scenario.get('cycle') and y<=2:roic-=.06
        if scenario.get('structural'):roic=min(roic,.085)
        nopat=k*roic; ebit=nopat/(1-INPUTS['tax'])
        newrev={a:b*(1+cg) for a,b in rev.items()}
        return newrev,nk,ebit,{'capital_roic':roic,'capital_growth':cg,'nopat':nopat,'gross_margin_amount':None,'rd':None}
    new={}
    for a,b in rev.items():
        gr=INPUTS['growth5'][a][y-1] if y<=5 else max(g,INPUTS['growth5'][a][-1]-(y-5)*.012)
        gr+=gs if y<=10 else 0
        if scenario.get('cycle') and y<=2:gr=-.08 if a!='agency' else -.03
        if scenario.get('cycle') and y==3:gr+=.07
        if scenario.get('structural') and a in ('auto','consumer'):gr=min(gr,.0)
        new[a]=b*(1+gr)
    design=sum(v for a,v in new.items() if a!='agency'); total=sum(new.values())
    fade=max(0.,y-5)/15; fade=min(fade,1.)
    gm=sum(v*(INPUTS['gm'][a]+(scenario.get('gm_shift',0) if a!='agency' else 0)-(.02*fade if a!='agency' else 0)) for a,v in new.items())
    if scenario.get('cycle') and y<=2:gm-=design*.035
    rd=design*(INPUTS['rd_design']+scenario.get('rd_shift',0)); sga=total*INPUTS['sga_total']
    ebit=gm-rd-sga
    target=(design*INPUTS['capital_design']+new['agency']*INPUTS['capital_agency'])*scenario.get('capital_scale',1.)
    nk=k+(target-k)/max(1,4-y) if y<=3 else target
    return new,nk,ebit,{'gross_margin_amount':gm,'rd':rd,'sga':sga,'design_revenue':design,'capital_target':target,'nopat':ebit*(1-INPUTS['tax'])}

def run(scenario=None,method='operating',years=400):
    c=scenario or {};distress_recovery=c.get('financial_recovery',INPUTS['parent_financial_distress_recovery']); s=copy.deepcopy(INPUTS['opening']);s['s_re']=c.get('sub_re',s['s_re']);s['foreign_local_re']=s['s_re']*.85;s['domestic_local_re']=s['s_re']*.15;s['p_cash']+=c.get('p_cash_shift',0);s['p_re']+=c.get('p_re_shift',0)
    r=c.get('r',INPUTS['r']);rev=copy.deepcopy(INPUTS['base_segments']);rows=[];pending=[(1,s['pending_gross'],s['pending_net'],0.)]
    past=c.get('past_exercise',0.);s['issued']+=past;s['p_capital']+=past;s['p_cash']+=past*77.91;s['p_capital_reserve']+=past*(77.91-1)
    ploss=[];sloss=[];s['p_tax_loss_carry']=0.;s['s_tax_loss_carry']=0.
    s['shares']=s['issued']-s['treasury'];s['nci_cumulative']=0.;s['future_funding']=0.
    if c.get('convert'):
        s['p_debt']-=2.6135172;s['shares']+=2.432323/159.02;s['issued']+=2.432323/159.02;s['p_capital']+=2.432323/159.02;s['p_capital_reserve']+=2.6135172-2.432323/159.02
    for y in range(1,years+1):
        forced_exit=False;bond_repaid=emergency_sale=emergency_loan=bond_unpaid=capacity_shortfall=0.
        begin=copy.deepcopy(s);cy={} if c.get('tail_only') and y<=5 else c;rev,nk,ebit,detail=operating(y,rev,s['capital'],cy,method)
        total=sum(rev.values()); delta=nk-s['capital'];s['capital']=nk
        # Full R&D in EBIT. Maintenance capex=depreciation; delta capital is net growth/release.
        sint=s['s_cash']*INPUTS['cash_yield'];pint=s['p_cash']*INPUTS['cash_yield']
        redprem=.0620381 if y==1 and not c.get('convert') else 0.
        s_pretax=ebit+sint-s['s_debt']*INPUTS['debt_rate']
        p_pretax=-INPUTS['p_overhead']+pint-s['p_debt']*INPUTS['debt_rate']-redprem
        stax,sloss=tax_cash_step(s_pretax,sloss,y,c.get('tax_loss_use',False))
        ptax,ploss=tax_cash_step(p_pretax,ploss,y,c.get('tax_loss_use',False))
        s['s_tax_loss_carry']=sum(v for t,v in sloss);s['p_tax_loss_carry']=sum(v for t,v in ploss)
        s_cash_income=s_pretax-stax;p_cash_income=p_pretax-ptax
        sprofit=s_cash_income;pown=p_cash_income
        s['s_cash']+=sprofit-delta;s['p_cash']+=pown
        # Cash economic budgets above exclude noncash share compensation. Legal expenses below only.
        sbc=c.get('compensation',INPUTS['noncash_compensation_annual_first5']) if y<=5 else 0.
        if c.get('old_treasury_transfer') and y<=3:sbc+=INPUTS['opening']['treasury_cost']/3
        psbc=sbc*INPUTS['parent_compensation_fraction'];ssbc=sbc-psbc
        sprofit-=ssbc;pown-=psbc
        s['p_capital_reserve']+=sbc;s['s_capital_reserve']+=ssbc
        s['investment_cost']+=ssbc;s['investment_book']+=ssbc
        if y==1 and not c.get('old_treasury_transfer'):
            s['p_capital']-=s['treasury'];s['issued']-=s['treasury']
            s['p_capital_reserve']-=INPUTS['opening']['treasury_cost']-s['treasury']
            s['treasury_cost']-=INPUTS['opening']['treasury_cost'];s['treasury']=0.
        if y==3 and c.get('old_treasury_transfer'):
            s['shares']+=s['treasury'];s['treasury']=0.
            s['p_capital_reserve']-=INPUTS['opening']['treasury_cost'];s['treasury_cost']-=INPUTS['opening']['treasury_cost']
        bb=c.get('buyback',.375) if y==1 else 0.;bbborrow=bb*.9;bbrepay=s['buyback_loan'] if y==3 else 0.
        s['p_cash']+=bbborrow-bb-bbrepay;s['p_debt']+=bbborrow-bbrepay;s['buyback_loan']+=bbborrow-bbrepay
        if y==1:s['buyback_new_treasury']=bb/120.;s['shares']-=bb/120.
        if y==3:s['shares']+=s['buyback_new_treasury'];s['buyback_new_treasury']=0.
        s['treasury_cost']+=bb;s['new_treasury_cost']+=bb
        if y==3:s['p_capital_reserve']-=s['new_treasury_cost'];s['treasury_cost']-=s['new_treasury_cost'];s['new_treasury_cost']=0.
        claim=c.get('claim',0.) if y==2 else 0.;s['p_cash']-=claim;pown-=claim
        earmark=min(.62,s['p_earmark']);s['p_earmark']-=earmark;s['p_cash']-=earmark;s['s_cash']+=earmark;s['investment_cost']+=earmark;s['investment_book']+=earmark;s['s_capital_reserve']+=earmark;s['future_funding']+=earmark
        # Financial holdings sold evenly over ten years at 90% opening carrying; loss recognized, principal not profit.
        fs=min(s['s_financial'],INPUTS['opening']['s_financial']/10) if y<=10 else 0.
        fp=min(s['p_financial'],INPUTS['opening']['p_financial']/10) if y<=10 else 0.
        s['s_financial']-=fs;s['p_financial']-=fp;s['s_cash']+=fs*.9;s['p_cash']+=fp*.9
        sprofit-=fs*.1;pown-=fp*.1
        received=paidgross=ncipaid=0.
        for due,gross,net,nci in list(pending):
            if due<=y:
                if s['s_cash']+1e-9<gross:raise ValueError('unfunded declared liability')
                s['s_cash']-=gross;s['p_cash']+=net;received+=net;paidgross+=gross;ncipaid+=nci;pending.remove((due,gross,net,nci))
        # repay intercompany principal only from spare cash, separate from dividends and legal earnings.
        floor=total*INPUTS['cash_floor_ratio'];reserved=sum(x[1] for x in pending)
        loanpay=min(s['loan'],(0. if c.get('loan_delay') and y<=5 else .30),max(0,s['s_cash']-floor-reserved));s['loan']-=loanpay;s['s_cash']-=loanpay;s['p_cash']+=loanpay
        # Refused bond rollover: prior declared dividends already collected above, no new dividend accelerated.
        # Sell only parent-owned financial holdings, then finite bilateral intercompany loan principal recovery.
        if y==1 and c.get('bond_refused') and not c.get('convert'):
            due=2.6135172  # premium .0620381 was already paid through p_cash_income
            need=max(0.,due-max(0.,s['p_cash']-s['p_earmark']))
            emergency_sale=min(s['p_financial'],need/distress_recovery)
            s['p_financial']-=emergency_sale;s['p_cash']+=emergency_sale*distress_recovery;pown-=emergency_sale*(1-distress_recovery)
            need=max(0.,due-max(0.,s['p_cash']-s['p_earmark']))
            emergency_loan=min(need,s['loan'],0. if c.get('no_loan_acceleration') else INPUTS['accelerated_loan_recovery_budget'],max(0.,s['s_cash']-floor-reserved))
            s['loan']-=emergency_loan;s['s_cash']-=emergency_loan;s['p_cash']+=emergency_loan
            bond_repaid=min(due,max(0.,s['p_cash']-s['p_earmark']));s['p_cash']-=bond_repaid;s['p_debt']-=bond_repaid
            bond_unpaid=due-bond_repaid;forced_exit=bond_unpaid>1e-10
        # Normal revolving bank facilities rolled, bond due Y1 refinanced if needed; gradual amortization, no simultaneous forced acceleration.
        spay=min(s['s_debt'],max(0,s['s_cash']-floor-reserved)*.20);s['s_debt']-=spay;s['s_cash']-=spay
        ppay=min(max(0,s['p_debt']-s['buyback_loan']),max(0,s['p_cash']-INPUTS['p_floor']-s['p_earmark'])*.20);s['p_debt']-=ppay;s['p_cash']-=ppay
        funding=max(0,floor+reserved-s['s_cash'])
        if funding>0:
            pc=max(0,s['p_cash']-INPUTS['p_floor']-s['p_earmark']);fromp=min(pc,funding);s['p_cash']-=fromp;s['s_cash']+=fromp;s['investment_cost']+=fromp;s['investment_book']+=fromp;s['s_capital_reserve']+=fromp;s['future_funding']+=fromp
            requested=funding-fromp;capacity=max(0.,c.get('debt_capacity',INPUTS['external_debt_capacity_budget'])-s['p_debt']-s['s_debt']);rest=min(requested,capacity);capacity_shortfall=requested-rest;forced_exit=forced_exit or capacity_shortfall>1e-10;s['s_debt']+=rest;s['s_cash']+=rest
        else:fromp=rest=0.
        # Foreign opcos (primarily Singapore/HK chain) profit-only budget -> PRC upstream holding.
        # No PRC reserve is imposed on foreign opco. Cash transfer is intra-subgroup, not new group income.
        s['foreign_local_re']+=sprofit*.85
        foreign_cap=min(max(0,s['foreign_local_re']),max(0,s['s_cash']-floor-sum(x[1] for x in pending))*.85)*c.get('foreign_capacity',1.)
        foreign_upstream=foreign_cap
        s['foreign_local_re']-=foreign_upstream
        domestic_income=sprofit*.15+foreign_upstream
        s['domestic_local_re'],s['s_reserve'],sradd=statutory(s['domestic_local_re'],s['s_reserve'],s['s_capital'],domestic_income)
        s['s_re']=s['foreign_local_re']+s['domestic_local_re']
        domestic_cap=max(0,s['domestic_local_re'])
        ratio=INPUTS['sub_payout'][y-1] if y<=5 else 1.
        declare=payment(domestic_cap,s['s_cash'],floor+sum(x[1] for x in pending),max(0,sprofit)*ratio+max(0,s['s_re']-sprofit)*(.05 if y<=5 else .20))
        if forced_exit:declare=0.
        s['domestic_local_re']-=declare
        s['s_re']-=declare;nci=declare*INPUTS['nci'];tax=(declare-nci)*c.get('remittance_tax',INPUTS['remittance_tax']);net=declare-nci-tax
        pending.append((y+c.get('delay',1),declare,net,nci));s['pending_gross']=sum(x[1] for x in pending);s['pending_net']=sum(x[2] for x in pending);s['receivable']=s['pending_net']
        pni=pown+net;s['p_re'],s['p_reserve'],pradd=statutory(s['p_re'],s['p_reserve'],s['p_capital'],pni)
        # Known and budgeted new rights; actual cash from options, zero cash for RSUs. No future buybacks assumed.
        scale=c.get('options',INPUTS['option_budget_billion'])/INPUTS['option_budget_billion']
        o23=INPUTS['option_2023']*scale if y==1 else 0.;o25=INPUTS['option_2025']*scale/3 if y<=3 else 0.;options=o23+o25
        grants=(INPUTS['stock_awards_billion']/3 if y<=3 else 0)+(c.get('future_grant',INPUTS['future_grant_budget_billion'])/5 if y<=5 else 0)
        if forced_exit:o23=o25=options=grants=0.
        exercise=o23*INPUTS['option_2023_price']+o25*INPUTS['option_2025_price'];s['shares']+=options+grants;s['issued']+=options+grants;s['p_capital']+=options+grants;s['p_capital_reserve']+=exercise-options-grants;s['p_cash']+=exercise
        pratio=INPUTS['parent_payout'][y-1] if y<=5 else (.7 if y<=10 else 1.)
        if c.get('low_payout'):pratio=.05
        dividend=0. if forced_exit else payment(s['p_re'],s['p_cash'],INPUTS['p_floor']+s['p_earmark'],max(s['p_re'],0)*pratio);s['p_cash']-=dividend;s['p_re']-=dividend
        s['nci_cumulative']+=ncipaid;s['nci_book']+=sprofit*INPUTS['nci']-nci
        # Complete external cash conservation, internal flows cancel.
        cashdelta=s['p_cash']+s['s_cash']-begin['p_cash']-begin['s_cash']
        expected=s_cash_income-delta+p_cash_income-claim+.9*(fs+fp)-(paidgross-received)-spay-ppay+rest+exercise-dividend+bbborrow-bb-bbrepay+emergency_sale*distress_recovery-bond_repaid
        assert abs(cashdelta-expected)<1e-7*max(1,total),(y,cashdelta,expected)
        assert abs(s['s_re']-s['foreign_local_re']-s['domestic_local_re'])<1e-7*max(1,total)
        assert abs(s['shares']-s['issued']+s['treasury']+s['buyback_new_treasury'])<1e-8
        assert s['p_cash']>=-1e-8 and s['s_cash']>=-1e-8
        assert dividend<=max(begin['p_re']+pni-pradd,0)+1e-8
        row={'year':y,'revenue':rev.copy(),'total_revenue':total,'ebit':ebit,'sub_net_income':sprofit,'sub_cash_tax':stax,'parent_cash_tax':ptax,'sub_tax_pretax':s_pretax,'parent_tax_pretax':p_pretax,'sub_tax_loss_vintages':[list(v) for v in sloss],'parent_tax_loss_vintages':[list(v) for v in ploss],'parent_own_income':pown,'noncash_share_compensation':sbc,'parent_noncash_compensation_expense':psbc,'sub_noncash_compensation_expense':ssbc,'parent_noncash_investment_cost_added':ssbc,'parent_recognized_new_dividend_income':net,'received_prior_dividends':received,'foreign_profit_gate':foreign_cap,'domestic_profit_gate':domestic_cap,'foreign_gross_upstream_budget':foreign_upstream,'domestic_earned_profit':sprofit*.15,'domestic_holding_recognized_income':domestic_income,'overseas_cash_location_budget':s['s_cash']*.85,'domestic_sub_cash_location_budget':s['s_cash']*.15,'sub_gross_declared':declare,'withholding_on_declared':tax,'nci_declared':nci,'nci_paid':ncipaid,'loan_principal_paid':loanpay,'bond_cash_redemption':(redprem+bond_repaid if c.get('bond_refused') else 2.6755553) if y==1 and not c.get('convert') else 0.,'bond_refinancing_bank_proceeds':2.6135172 if y==1 and not c.get('convert') and not c.get('bond_refused') else 0.,'bond_cash_principal_without_refinancing':bond_repaid,'bond_due_unpaid_after_parent_asset_sale_and_loan_recovery':bond_unpaid,'parent_emergency_financial_book_sold':emergency_sale,'parent_emergency_financial_cash_received':emergency_sale*distress_recovery,'accelerated_intercompany_principal_recovered':emergency_loan,'external_financing_capacity_budget':c.get('debt_capacity',INPUTS['external_debt_capacity_budget']),'external_financing_capacity_shortfall':capacity_shortfall,'funding_triggered_exit':forced_exit,'parent_debt_paid':ppay,'sub_debt_paid':spay,'new_external_borrowing':rest,'planned_buyback_cash':bb,'buyback_loan_draw':bbborrow,'buyback_loan_repaid':bbrepay,'earmarked_rd_funding':earmark,'minority_claim_paid':claim,'parent_new_investment':fromp+earmark,'financial_book_sold':fs+fp,'financial_cash_received':.9*(fs+fp),'physical_maintenance_capex_and_depreciation':sum(v for a,v in rev.items() if a!='agency')*.05,'physical_growth_commitment':([.9291461,.6,.5,.3,.2][y-1] if y<=5 else 0.),'net_working_capital_and_other_change':delta-([.9291461,.6,.5,.3,.2][y-1] if y<=5 else 0.),'net_capital_investment':delta,'cash_rd_and_growth':detail,'parent_reserve_added':pradd,'sub_reserve_added':sradd,'option_exercise_cash':exercise,'shares_awarded':grants,'shares_exercised':options,'holder_cash':dividend,'holder_dps':dividend/s['shares'],'state':copy.deepcopy(s),'cash_conservation_residual':cashdelta-expected}
        if c.get('exit_year')==y or forced_exit:
            ex=exit_bridge(s);row['exit']=ex;row['holder_cash']+=ex['parent_liquidation_after_external_creditors'];row['holder_dps']=row['holder_cash']/s['shares'];row['post_exit_state']={'operating_assets_remaining':0.,'parent_cash_after_final_distribution':max(0.,ex['parent_liquidation_after_external_creditors']-ex['parent_liquidation_after_external_creditors']),'sub_external_claims_unpaid_before_guarantee':ex['senior_unpaid'],'parent_guarantee_paid':ex['parent_guarantee_cash_paid'],'sub_external_claims_unpaid_after_guarantee':max(0.,ex['senior_unpaid']-ex['parent_guarantee_cash_paid']),'parent_creditor_shortfall':ex['parent_creditor_shortfall'],'loan_principal_written_off':ex['parent_loan_loss'],'dividend_receivable_written_off':ex['parent_dividend_receivable_writeoff'],'parent_realized_re_before_liquidation':ex['parent_post_sale_re'],'parent_investment_cost_derecognized':s['investment_cost'],'parent_investment_book_derecognized':s['investment_book'],'nci_cash_paid_at_exit':ex['nci_exit'],'nci_book_derecognized':s['nci_book'],'shares_extinguished_on_completed_liquidation':s['shares'] if not ex['insolvent'] else 0.,'unresolved_shares_if_insolvent':s['shares'] if ex['insolvent'] else 0.,'completed_solvent_liquidation':not ex['insolvent'],'no_further_ordinary_cash_budget':True};rows.append(row);break
        rows.append(row)
    pv=sum(a['holder_dps']/(1+r)**a['year'] for a in rows)
    tv5=sum(a['holder_dps']/(1+r)**(a['year']-5) for a in rows if a['year']>5)
    pv5=sum(a['holder_dps']/(1+r)**a['year'] for a in rows if a['year']<=5)
    return {'method':method,'scenario_inputs':c,'discount_rate':r,'years':len(rows),'pv_per_share':pv,'terminal_year5':tv5,'first5_dps':[a['holder_dps'] for a in rows[:5]],'terminal_pv_fraction':tv5/(1+r)**5/pv if pv else 0,'pv_first5':pv5,'horizon_pv':{str(n):sum(a['holder_dps']/(1+r)**a['year'] for a in rows if a['year']<=n) for n in [30,60,100,200,400]},'rows':rows}

def tests():
    cash,buckets=tax_cash_step(-3.,[],1,True);assert cash==0 and buckets==[(1,3.)]
    cash,buckets=tax_cash_step(2.,buckets,2,True);assert cash==0 and buckets==[(1,1.)]
    cash,buckets=tax_cash_step(2.,buckets,7,True);assert cash==.4 and not buckets
    cash,buckets=tax_cash_step(2.,[(1,3.)],2,False);assert cash==.4
    r,s,a=statutory(-3.,.2,10.,2.);assert (r,s,a)==(-1.,.2,0.)
    r,s,a=statutory(-1.,.2,10.,3.);assert abs(r-1.8)<1e-12 and abs(a-.2)<1e-12
    assert payment(5,2,1,5)==1 and payment(-1,10,0,10)==0
    r,s,a=statutory(0,.49,1,10);assert abs(a-.01)<1e-12
    x=copy.deepcopy(INPUTS['opening']);x['capital']=10;x['s_cash']=2;x['s_financial']=0;x['s_debt']=1;x['loan']=2;x['pending_gross']=0;x['pending_net']=0;x['investment_cost']=3;x['investment_book']=3;x['p_cash']=1;x['p_financial']=0;x['p_debt']=0
    b=exit_bridge(x,recovery=1,fee=0)
    residual=12-1-2-.51554653691;eq=residual*.995*.97;tax=max(0,eq-3)*.25
    assert abs(b['parent_liquidation_after_external_creditors']-(1+eq-tax+2-.15))<1e-10
    assert abs(b['parent_disposal_gain_tax_base']-(eq-3))<1e-10
    # Real production kernel includes no P&L on receivable collection or loan recovery; graph assertions run all scenarios.
    z=copy.deepcopy(x);z.update({'capital':1.,'s_cash':0.,'s_debt':2.,'pending_gross':1.,'pending_net':.9})
    bad=exit_bridge(z,recovery=1,fee=0)
    assert bad['intercompany_loan_principal_recovered']==0 and bad['pending_net_recovered']==0
    assert bad['parent_loan_loss']==2 and bad['parent_dividend_receivable_writeoff']==.9
    assert abs(bad['parent_realized_income']-(-3-2-.9-bad['parent_guarantee_call_budget']-.15))<1e-10
    assert bad['senior_unpaid']>0 and bad['insolvent']
    lossrun=run({'gm_shift':-.25},years=2)
    assert all(z['sub_tax_pretax']<0 and z['sub_cash_tax']==0 for z in lossrun['rows'])
    assert lossrun['rows'][-1]['state']['s_tax_loss_carry']>0
    refused=run({'bond_refused':True},years=2);assert refused['rows'][0]['bond_refinancing_bank_proceeds']==0 and refused['rows'][0]['bond_due_unpaid_after_parent_asset_sale_and_loan_recovery']==0
    illiquid=run({'bond_refused':True,'no_loan_acceleration':True,'financial_recovery':.5},years=5);assert illiquid['rows'][0]['funding_triggered_exit'] and illiquid['years']==1
    capacity=run({'gm_shift':-.25,'debt_capacity':0.},years=10);assert capacity['rows'][-1]['funding_triggered_exit'] and capacity['years']<10
    base=run({},years=5)
    compensated=base['rows'][0];assert compensated['parent_noncash_compensation_expense']==.025
    assert abs(compensated['parent_noncash_investment_cost_added']-.225)<1e-12
    assert compensated['state']['treasury']==0 and abs(compensated['state']['p_capital']-compensated['state']['issued'])<1e-10
    dil=run({'options':.025870997,'future_grant':.032},years=5)
    assert dil['rows'][-1]['state']['shares']>base['rows'][-1]['state']['shares']
    delay=run({'delay':2},years=5);assert delay['rows'][1]['received_prior_dividends']==0
    return {'refused_bond_paid_from_parent_assets_not_group_dividends':True,'illiquid_asset_refusal_triggers_actual_exit':True,'capacity_constraint_triggers_exit':True,'cash_tax_never_refunds_losses':True,'loss_offset_only_on_future_taxable_profit':True,'tax_loss_budget_expiry':True,'loss_absorption':True,'reserve_cap':True,'cash_and_re_payment_caps':True,'exit_hand_literal':True,'insolvent_exit_loan_and_dividend_writeoff':True,'dilution_cash_and_shares':True,'declared_vs_received_delay':True,'all_rows_cash_conservation':True}

def main():
    out={'schema':'omnivision-cash-legal-v1','asof':ASOF,'inputs':INPUTS,'tests':tests(),'results':{}}
    for name,c in SCENARIOS.items():out['results'][name]=run(c)
    out['results']['capital_crosscheck']=run({},'capital')
    print(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False))
if __name__=='__main__':main()

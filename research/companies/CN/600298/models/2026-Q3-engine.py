#!/usr/bin/env python3
"""Standalone Angel common shareholder cash model. All CNY billion; forecasts not legal certifications."""
import json,math,copy,sys
ASOF='2026-10-30T00:00:00+00:00'
# name, ownership, tax, share of EBIT, share of operating capital, initial internal face, registered capital
ENT=[('parent',1,.15,.08,.12,0,.867815671),('Algeria',.67,.19,.01,.006,.03,.0098),('Egypt',1,.225,.20,.10,.561518975,.13),('Russia',1,.25,.12,.10,.555564598,.297),('Indonesia',.8,.22,0,.04,.2,.28),('Liuzhou',1,.15,.10,.06,.25,.171),('Kokdala',1,.075,.065,.06,.25,.25),('Yili',1,.25,0,.005,.3,.093),('Yichang',1,.15,.08,.075,.752879761,.35),('Puer',.94,.15,.05,.06,.827291061,.4),('Dehong',.903813,.15,.055,.06,.57068252,.187136),('Hongyu',.4875,.15,.02,.035,.02,.0813333),('Shengtong',.55,.15,-.015,.035,.2,.4),('Chongzuo',.7,.15,.04,.035,.30,.17),('Jining',.6,.15,.012,.012,.12,.1),('Baiwei',.6,.25,-.003,.005,.03,.04),('Niubao',.7,.25,.002,.002,.005,.01),('Nutritech',1,.15,.025,.015,.15,.1),('Hightech',1,.25,.001,.085,.4,.5),('Enzyme',1,.15,.05,.035,.1,.08),('Other_CN',1,.17,.083,.04,.19604601445,.7902),('Finance',1,.25,0,0,.96801707055,.3),('HongKong',1,.165,.025,.015,.2,.00066762)]
# Economic profit/capital routing estimates: weights sum to 1; underlying ownership is legal fact.
assert abs(sum(z[3] for z in ENT)-1)<1e-9 and abs(sum(z[4] for z in ENT)-1)<1e-9
SCENARIOS={'base':{},'kokdala_tax25':{'kok_tax':.25},'project_slow':{'project_delay':2,'project_margin':.75},'claims_short_window':{'recovery_years':5},'claims_no_allowance':{'allowance':'none'},'claims_full_risk':{'allowance':'full'},'support_stop':{'support_stop':True},'algeria_direct':{'algeria_direct':True},'niubao_small_qualified':{'niubao_tax':.05},'cb_unconverted':{'cb':True},'cb_convert20':{'cb':True,'convert_price':20.},'cb_convert30':{'cb':True,'convert_price':30.},'cb_conditional_put':{'cb':True,'cb_put':5},'cb_put_funding_failure':{'cb':True,'cb_put':5,'funding_cutoff_year':5},'no_cb_funding_failure':{'no_refi':True},'lease_failure':{'creditloss':.6},'cycle':{'shock':.16,'years':3,'wc':.03},'structural':{'shock':.28,'years':999,'growthcut':.025,'capital':1.18},'upside':{'shock':-.09,'years':999,'growthadd':.012,'capital':1.03},'remit_delay':{'delay':3},'capex_overrun':{'capital':1.25},'hk_tax_basis':{'hk_basis':.08,'hk_div_tax':.10,'hk_exit_tax':.20},'finance_delay':{'finance_years':10},'yili_qualified15':{'yili_tax':.15},'finance_failure':{'shock':.65,'years':999,'no_refi':True}}

GROWTH_CAPITAL={'parent':.08,'Yichang':.22,'Hightech':.12,'Kokdala':.08,'Enzyme':.04,'Other_CN':.04,'Russia':.15,'Indonesia':.12,'Puer':.05,'Liuzhou':.04,'Dehong':.02,'Egypt':.01,'Chongzuo':.01,'Jining':.005,'Baiwei':.003,'Niubao':.002,'Nutritech':.005,'Algeria':.005}
assert abs(sum(GROWTH_CAPITAL.values())-1)<1e-12

# Published total budgets; future remaining payments are research budgets, not contract confirmations.
PROJECTS=[
 ('baiyang32','Hightech',.94098,[.45,.36,.09,0,0],.875),
 ('baiyang12','Hightech',.12001,[.05,.04,.01,0,0],.08),
 ('yichang_protein','Yichang',.97045,[.25,.45,.27045,0,0],.89),
 ('kokdala','Kokdala',.84477,[.20,.35,.29477,0,0],.775),
 ('parent_food6','parent',.21524,[.12,.09524,0,0,0],.20),
 ('russia22','Russia',1.06226,[.20,.40,.38,0,0],0),
 ('indonesia20','Indonesia',.88,[.50,.10,0,0,0],0),
 ('puer12','Puer',.2220756,[.05,.10,.05,0,0],0),
 ('food3','parent',.42239,[.05,.15,.20,0,0],0),
 ('pilot','Enzyme',.37045,[.05,.15,.15,0,0],0),
 ('liuzhou_ye','Liuzhou',.23166,[.05,.10,.07,0,0],0),
 ('hydrolysis','Hightech',.10135,[.05,.05135,0,0,0],0),
 ('protein_mix','Yichang',.13521,[0,.05,.08521,0,0],0),
 ('dehong_upgrade','Dehong',.073,[.03,.02,0,0,0],0)]
assert all(sum(x[3])<=x[2]+1e-12 for x in PROJECTS)

# Incremental project operating budgets, not issuer IRR: name, start year index,
# capacity million tonnes, unit revenue thousand CNY, EBIT margin, alternative mature revenue/margin.
# Support projects use explicit service/cost-saving revenue equivalents, not claimed saleable tonnes.
PROJECT_EARNINGS=[('baiyang32',3,.032,28.,.16,.85,.15),('baiyang12',2,.012,40.,.18,.45,.17),('yichang_protein',3,.020,30.,.17,.58,.16),('kokdala',3,.020,27.,.17,.50,.16),('parent_food6',2,.060,7.,.07,.38,.065),('russia22',3,.022,26.,.21,.54,.20),('indonesia20',1,.020,24.,.18,.45,.17),('puer12',2,.012,25.,.17,.28,.16),('food3',3,.0575,6.,.07,.32,.065),('pilot',3,.001,100.,.20,.09,.18),('liuzhou_ye',2,.010,22.,.12,.20,.11),('hydrolysis',2,.500,.2,.12,.08,.12),('protein_mix',3,.020,10.,.09,.18,.085),('dehong_upgrade',2,.001,80.,.12,.07,.11)]

def entity_operations(method,y,op,sc):
    project={};planned_project_profit=0.;by_entity={n:0. for n,*_ in ENT}
    for tag,start,volume,price,margin,revenue_b,margin_b in PROJECT_EARNINGS:
        age=y-start-sc.get('project_delay',0)
        utilization=0. if age<0 else [.25,.60,.85][min(age,2)]
        # After mature capacity is absorbed, recurring expansion is funded by general growth capex.
        expansion=1.02**max(0,y-5)
        mature=volume*price*margin if method=='tonnes' else revenue_b*margin_b
        amount=mature*utilization*expansion*sc.get('project_margin',1)
        if y<=sc.get('years',0):amount*=1-sc.get('shock',0)
        planned_age=y-start
        planned_use=0. if planned_age<0 else [.25,.60,.85][min(planned_age,2)]
        planned=mature*planned_use*expansion
        if y<=sc.get('years',0):planned*=1-sc.get('shock',0)
        planned_project_profit+=planned
        project[tag]=amount
        payer=next(q[1] for q in PROJECTS if q[0]==tag);by_entity[payer]+=amount
    remaining=op['ebit']-planned_project_profit
    op['demand_budget_ebit']=op['ebit'];op['planned_project_ebit']=planned_project_profit
    op['project_execution_shortfall']=planned_project_profit-sum(project.values())
    op['ebit']=remaining+sum(project.values())
    weights={n:p for n,o,t,p,k,l,c in ENT}
    if method=='geography':
        # Geography model's legacy exposure shifts with actual domestic/foreign budget growth.
        for n in weights:
            weights[n]*=(op['foreign']/7.75 if n in ('Egypt','Russia','Indonesia','Algeria','HongKong') else op['domestic']/10.75)
        scale=sum(weights.values());weights={n:v/scale for n,v in weights.items()}
    ebit={n:remaining*weights[n]+by_entity[n] for n in weights}
    # Holding company has administration, not duplicated relocated manufacturing earnings.
    admin=.002*(op['revenue']/19.25);ebit['Yili']-=admin;ebit['Kokdala']+=admin
    if sc.get('kokdala_adverse'):
        shift=ebit['Kokdala']+.10;ebit['Kokdala']=-.10;ebit['Other_CN']+=shift
    assert abs(sum(ebit.values())-op['ebit'])<1e-8
    return ebit,project,remaining

def claim_allowance(face,operating_cash_capacity,loss_years,policy,window=10):
    # Economic recoverability screen, not a legal/accounting certification or tax deduction.
    if policy=='none':return 0.
    if policy=='full':return face
    if loss_years<3:return 0.
    annuity=sum(1/1.09**j for j in range(1,window+1))
    return max(0.,face-max(0.,operating_cash_capacity)*annuity)

def consolidated_profit(operating_and_deposit_income,external_interest,tax_cash):
    # Includes actual foreign remittance taxes once; no intragroup dividends or principal.
    return operating_and_deposit_income-external_interest-tax_cash

def re_step(re,res,profit,capital,cn=True):
    # Positive profit first cures negative retained earnings; reserve only on remaining eligible profit.
    cure=min(max(-re,0),max(profit,0)); eligible=max(0,profit-cure)
    transfer=min(eligible*.1,max(0,capital*.5-res)) if cn else 0.0
    return re+profit-transfer,res+transfer,transfer

def pay(cash,retained,floor,target):
    amount=min(target,max(0,retained),max(0,cash-floor))
    return amount,cash-amount,retained-amount

def initial():
    s={}
    for n,o,t,p,k,loan,cap in ENT:
        s[n]=dict(cash=(2.2284680705 if n=='parent' else .67015775416*k/.88),restricted=(.17452609966 if n=='parent' else .06851327749*k/.88),debt=(6.95179280069 if n=='parent' else 1.79383117911*k/.88),internal=loan,receivable=0.,re=(5.07956644636 if n=='parent' else 0.),reserve=(.49598618073 if n=='parent' else 0.),capital=cap,opening_unallocated_equity=(0 if n=='parent' else 4.48596976055*k/.88),losses=[],book=(1.608 if n=='parent' else 10.905*k/.88),wc=(.6 if n=='parent' else 4.8*k/.88),inv_cost=(4.72380714178 if n=='parent' else 0.))
    s['parent']['receivable']=.14861887547
    s['parent']['internal_asset']=sum(s[n]['internal'] for n in s if n not in ('parent','Kokdala'))
    s['Yili']['internal_asset']=s['Kokdala']['internal'];s['Yili']['inv_cost']=.25
    for n in s:s[n]['claim_allowance']=0.;s[n]['loss_streak']=0
    s['Finance']['net_lease_investment']=1.26801707055
    s['Finance']['unearned_income_budget']=1.26801707055*.11291470148/1.23949913363
    s['parent']['cb_face']=0.;s['parent']['cb_restricted']=0.
    s['HongKong']['inv_cost']=.1001428504
    s['parent']['investments']=.10094379156
    s['parent']['acquisition_payable']=.174436955
    return s

def operating(method,y,previous,sc):
    gseq=[.08,.075,.065,.055,.045,.04,.035,.03,.025,.02]
    growth=max(.005,(gseq[min(y-1,9)] +sc.get('growthadd',0)-sc.get('growthcut',0)))
    if y>10:growth=.02 if 'growthcut' not in sc else .01
    if method=='tonnes':
        vol=(.510 if previous is None else previous['volume'])*(1+growth)
        price=(26.15 if previous is None else previous['price'])*(1.006 if y<=10 else 1.0)
        unitcost=price*(.675 if y<=5 else .68)
        unitexpense=price*(.158 if y<=5 else .157)
        other=(4.65 if previous is None else previous['other'])*(1.045 if y<=5 else 1.02)
        # other business intentionally grows only 2%, not all sales treated as high-margin yeast
        revenue=vol*price+other
        ebit=vol*(price-unitcost-unitexpense)+other*.017
        out=dict(volume=vol,price=price,other=other,revenue=revenue,ebit=ebit)
    else:
        domestic=(10.75 if previous is None else previous['domestic'])*(1+max(.01,.045+sc.get('growthadd',0)-sc.get('growthcut',0)) if y<=5 else 1.02)
        foreign=(7.75 if previous is None else previous['foreign'])*(1+max(.01,.09+sc.get('growthadd',0)-sc.get('growthcut',0)) if y<=5 else (1.045 if y<=10 else 1.02))
        ebit=domestic*(.071 if y<=5 else .07)+foreign*(.182 if y<=5 else .174)
        out=dict(domestic=domestic,foreign=foreign,revenue=domestic+foreign,ebit=ebit)
    if y<=sc.get('years',0):out['ebit']*=1-sc.get('shock',0)
    out['growth']=growth
    return out

def run(method='tonnes',scenario='base',years=120,override=None):
    sc=dict(SCENARIOS[scenario]);sc.update(override or {})
    st=initial();rows=[];prev=None;shares=.867815671;funding_remaining={p[0]:p[4] for p in PROJECTS};wc_funding_remaining=.68
    hk_basis=sc.get('hk_basis',.1001428504);st['HongKong']['inv_cost']=hk_basis
    # Q4 bridge, observed starting cash / debts remain actual; budget is separately identified.
    bridge=dict(operating_cash=.72,capex=.55,interest=.04,dividend=0.,net_cash=.13,net_profit=.30,depreciation=.24,working_capital_release=.14)
    for n,o,t,p,k,loan,cap in ENT:st[n]['cash']+=.13*k;st[n]['book']+=.55*k-.24*k;st[n]['re']+=.30*max(p,0)/1.018;st[n]['wc']-=.14*k
    # Old receivable declaration already in parent RE; subsidiary payable exists separately.
    pending_old=.14861887547
    equity=13.66439919956+.30;common_equity=12.80145565247+.29
    for y in range(1,years+1):
        op=operating(method,y,prev,sc);rev=op['revenue'];priorrev=18.5 if prev is None else prev['revenue']
        # explicit remaining project cash, not total announced budgets; replacements persist afterward
        project_cash={name:(flow[y-1]*sc.get('capital',1) if y<=5 else 0.) for name,entity,total,flow,fund in PROJECTS}
        general_growth=([0,0,0,.80,.55][y-1] if y<=5 else max(0,rev-priorrev)*.66)*sc.get('capital',1)
        entity_ebit,project_ebit,legacy_ebit=entity_operations(method,y,op,sc)
        allocation=GROWTH_CAPITAL if y<=5 else {n:max(0.,v)/sum(max(0.,a) for a in entity_ebit.values()) for n,v in entity_ebit.items()}
        entity_growth={n:general_growth*allocation.get(n,0.) for n,*_ in ENT}
        for name,entity,total,flow,fund in PROJECTS:entity_growth[entity]+=project_cash[name]
        growthcap=sum(entity_growth.values())
        dep=.98*(rev/19.25)**.72
        maint=dep*1.08
        capital_weights={n:e['book']/sum(a['book'] for a in st.values()) for n,e in st.items()}
        capex=maint+growthcap;parentcap=maint*capital_weights['parent']+entity_growth['parent']
        parentdep=dep*capital_weights['parent']
        wcadd=(rev-priorrev)*.24 + (rev*sc.get('wc',0) if y==1 else -priorrev*sc.get('wc',0) if y==4 else 0)
        groupopen=sum(v['cash'] for v in st.values());groupdebtopen=sum(v['debt'] for v in st.values());ledger=[];injection=0;externalflow=0;group_profit=0;minority_profit=0;minority=0;employee=0;taxsum=0;interestpaid=0;cap_return=0;declare_parent=0;cash_parent=0;failure=None
        parent=st['parent'];pstart=copy.deepcopy(parent)
        cb_open=parent['cb_face'];cb_reserve_open=parent['cb_restricted'];cb_issued=3.5 if sc.get('cb') and y==1 else 0.
        cb_fee=cb_issued*.01;cb_conversion=0.;cb_newshares=0.;cb_redemption=0.;cb_premium=0.
        parent['cb_face']+=cb_issued;parent['cb_restricted']+=cb_issued
        project_fund_draw={name:0. for name,entity,total,flow,fund in PROJECTS}
        cb_eligible_growth_cash=sum(project_cash[name] for name,entity,total,flow,fund in PROJECTS if fund>0)
        if sc.get('cb'):
            for name,entity,total,flow,fund in PROJECTS:
                draw=min(project_cash[name],funding_remaining[name]);funding_remaining[name]-=draw;project_fund_draw[name]=draw
        cb_eligible_wc=min(wc_funding_remaining,.68) if sc.get('cb') and y==1 else 0.
        wc_funding_remaining-=cb_eligible_wc
        cb_release=sum(project_fund_draw.values())+cb_eligible_wc
        assert cb_release<=parent['cb_restricted']+1e-9
        parent['cb_restricted']-=cb_release;cb_reserve_flow=cb_release-cb_issued
        if sc.get('convert_price') and y==3:
            cb_conversion=parent['cb_face'];cb_newshares=cb_conversion/sc['convert_price'];shares+=cb_newshares;parent['capital']+=cb_newshares;parent['cb_face']=0.
        if parent['cb_face'] and (y==6 or y==sc.get('cb_put',-1)):
            cb_redemption=parent['cb_face'];cb_premium=cb_redemption*.08 if y==6 else 0.
        cb_coupon=parent['cb_face']*[.003,.005,.008,.012,.018,.022][min(y-1,5)]
        parent['cb_face']-=cb_redemption
        externalflow+=cb_issued-cb_redemption
        parent['cash']+=cb_issued-cb_redemption+cb_reserve_flow
        # Existing financial loan asset is run off with interest on remaining face, no repeat principal income.
        finopen=st['Finance']['net_lease_investment'];unearned_open=st['Finance']['unearned_income_budget'];fininterest=min(unearned_open,finopen*.035);st['Finance']['unearned_income_budget']-=fininterest
        finance_years=sc.get('finance_years',5)
        finrepay=min(finopen,1.26801707055/finance_years) if y<=finance_years else 0.
        finloss=finrepay*sc.get('creditloss',0)
        st['Finance']['net_lease_investment']-=finrepay
        invsale=parent['investments'] if y==5 else 0.
        parent['investments']-=invsale
        acquisition=min(parent['acquisition_payable'],.174436955/2) if y<=2 else 0.
        parent['acquisition_payable']-=acquisition
        buyback=(77750*14.31/1e9+.00001) if y==1 else 0.
        if y==1:shares-=.00007775
        total_internal_interest=0;total_repay=0;new_loans=0;div_declarations=0;oldcash=0;tax_withholding=0;capital_receipt=0.;parent_exit_loss=0.;intermediate_exit_tax=0.;direct_exit_gain=0.;hkdiv=0.;hkcapital=0.;hkgain=0.;hktax=0.
        routed_income={n:0. for n,*_ in ENT}
        routed_interest={n:0. for n,*_ in ENT};routed_principal={n:0. for n,*_ in ENT};routed_advance={n:0. for n,*_ in ENT}
        claim_impairment={n:0. for n,*_ in ENT};allowance_target={n:0. for n,*_ in ENT}
        # Annual claims and operating cash are evaluated separately for every legal entity/budget pool.
        for n,o,rate,p,k,loan,cap in ENT:
            if n=='parent':continue
            e=st[n];before=copy.deepcopy(e)
            ebit=entity_ebit[n] if n!='Finance' else fininterest-finloss-(.005 if y==finance_years else 0.)
            intin=e['internal']*.03; intex=e['debt']*(.035 if n in ('Russia','Indonesia') else .028)
            deposit=(e['cash']+e['restricted'])*.012
            pretax=ebit-intin-intex+deposit+routed_interest[n]
            rate=sc.get('yili_tax',rate) if n=='Yili' else rate
            if n=='Kokdala':rate=.075 if y==1 else sc.get('kok_tax',.15)
            if n=='Niubao' and y<=3:rate=sc.get('niubao_tax',rate)
            taxable=max(0,pretax);tax=taxable*rate;profit=pretax-tax
            profit+=routed_income[n]
            impairment=allowance_target[n]-e['claim_allowance'];e['claim_allowance']=allowance_target[n];claim_impairment[n]=impairment;profit-=impairment
            if n=='HongKong':profit+=hkdiv+hkgain
            if pretax<0:e['losses'].append({'origin_year':2026+y,'gross_loss':-pretax,'tax_credit_used':0.,'eligibility':'not presumed; no cross-entity netting'})
            # Unassigned historical NOL is never transferred into another taxpayer.
            e['re'],e['reserve'],reserve=re_step(e['re'],e['reserve'],profit,e['capital'],n not in ('Egypt','Russia','Indonesia','HongKong','Algeria'))
            owncap=maint*capital_weights[n]+entity_growth[n];owndep=dep*capital_weights[n];ownwc=wcadd*k
            old_employee=.01327155101 if n=='Egypt' and y==1 else 0.
            e['cash']+=profit+impairment+routed_principal[n]-routed_advance[n]+owndep-owncap-ownwc-old_employee+(finrepay if n=='Finance' else 0.)+(hkcapital-hkgain if n=='HongKong' else 0.)
            e['book']+=owncap-owndep;e['wc']+=ownwc
            floor=.35*k/.88*(rev/19.25)
            # current-interest payment already deducted in profit, not paid twice
            if n=='Kokdala':routed_interest['Yili']+=intin
            else:total_internal_interest+=intin
            # Existing dividend payable from Q3 is settled first without recognizing new parent profit.
            settleold=min(pending_old,max(0,e['cash']-floor)) if n=='Other_CN' else 0.
            if settleold: e['cash']-=settleold;pending_old-=settleold;oldcash+=settleold
            # ordinary cash pooling: repay no more than cash available or outstanding legal face
            repay=min(e['internal'],max(0,e['cash']-floor)*(1 if n=='Finance' else .35))
            e['cash']-=repay;e['internal']-=repay
            if n=='Kokdala':routed_principal['Yili']+=repay;st['Yili']['internal_asset']-=repay
            else:total_repay+=repay
            # Cash shortfall is funded by parent internal advances; actual group debt tracked below.
            advance=max(0,floor-e['cash']);e['cash']+=advance;e['internal']+=advance
            if n=='Kokdala':routed_advance['Yili']+=advance;st['Yili']['internal_asset']+=advance
            else:new_loans+=advance
            capacity_cash=ebit-intex-tax+deposit+routed_income[n]+routed_interest[n]+owndep-owncap-ownwc-e['debt']/sc.get('recovery_years',10)-routed_advance[n]
            e['loss_streak']=(e['loss_streak']+1 if profit+impairment<0 else 0)
            creditor='Yili' if n=='Kokdala' else 'parent'
            allowance_target[creditor]+=claim_allowance(e['internal'],capacity_cash,e['loss_streak'],sc.get('allowance','recoverability'),sc.get('recovery_years',10))
            if sc.get('support_stop') and e['loss_streak']>=3 and advance>1e-9:failure='internal support withdrawn: retain all claims and capital; no continuation'
            # declare only available current-law budget RE; no fabricated opening reserve distribution.
            distributable=max(0,min(e['re'],e['cash']-floor))
            payout=distributable*(.65 if y<=5 else .95)
            if sc.get('delay') and n in ('Egypt','Russia','Indonesia','Algeria') and y<=sc['delay']:payout=0.
            emp=payout*.10 if n=='Egypt' else 0.
            dividend=payout-emp;e['cash']-=payout;e['re']-=payout
            parentdecl=dividend*o;noncontrol=dividend*(1-o)
            if n=='Finance':
                parentdecl=dividend*2/3;hkdiv=dividend/3*(1-sc.get('hk_div_tax',.05));hktax+=dividend/3*sc.get('hk_div_tax',.05)
            route_tax=0.;route_target=None
            if n=='Niubao':route_target='Nutritech'
            if n=='Kokdala':route_target='Yili'
            if n=='Algeria' and not sc.get('algeria_direct'):route_target='Egypt'
            if route_target:
                route_tax=parentdecl*(.05 if n=='Algeria' else 0.);routed_income[route_target]+=parentdecl-route_tax;parentdecl=0.
            # foreign tax budget represents gross remittance friction / residual CN tax, not treaty certification
            wht=parentdecl*(.05 if n in ('Egypt','Russia','Indonesia','Algeria') else 0.)
            cash_parent+=parentdecl-wht;div_declarations+=parentdecl;tax_withholding+=wht
            group_profit+=profit+impairment-routed_income[n]-route_tax-(hkdiv+hkgain+hktax if n=='HongKong' else 0.);taxsum+=route_tax;taxsum+=(hktax if n=='HongKong' else 0.);minority_profit+=profit*(1-o);taxsum+=tax;interestpaid+=intex;employee+=emp;minority+=noncontrol;employee+=old_employee
            capret=0.
            if n=='Finance' and y==finance_years and (e['internal']>1e-8 or e['debt']>1e-8):failure='lease exit insolvent: retain creditor face, capital and investment cost; no continuation'
            if n=='Finance' and y==finance_years and not failure:
                capret=max(0,e['cash']);e['cash']-=capret;e['re']=0.;e['reserve']=0.
                direct_exit_gain=capret*2/3-.2002857008
                exit_cross_tax=max(0,capret/3-hk_basis)*sc.get('hk_exit_tax',.10)
                hkcapital=capret/3-exit_cross_tax;hkgain=hkcapital-hk_basis;hktax+=exit_cross_tax
                st['HongKong']['inv_cost']=0.
                capital_receipt=capret*2/3;parent_exit_loss=direct_exit_gain
                parent['inv_cost']-=.2002857008;e['capital']=0.
            residual=e['cash']-(before['cash']+profit+impairment+routed_principal[n]-routed_advance[n]+owndep-owncap-ownwc-old_employee-settleold-repay+advance-payout+(finrepay if n=='Finance' else 0.)+(hkcapital-hkgain if n=='HongKong' else 0.)-capret)
            assert abs(residual)<1e-8 and e['cash']>=-1e-10 and e['re']>=-1e6
            assert abs(e['internal']-(before['internal']-repay+advance))<1e-8
            ledger.append(dict(creditor=creditor,claim_allowance_charge=impairment,claim_recovery_cash_capacity=capacity_cash,incoming_internal_interest=routed_interest[n],incoming_internal_repayment=routed_principal[n],outgoing_internal_advance=routed_advance[n],incoming_sub_dividend=routed_income[n],intermediate_withholding=route_tax,dividend_recipient=route_target or 'parent',name=n,ownership=o,opening=before,ebit=ebit,internal_interest=intin,external_interest=intex,deposit_interest=deposit,tax=tax,net_profit=profit,reserve_transfer=reserve,depreciation=owndep,capex=owncap,working_capital_change=ownwc,old_dividend_settlement=settleold,internal_repayment=repay,internal_advance=advance,incoming_finance_dividend=(hkdiv if n=='HongKong' else 0.),incoming_finance_exit_cash=(hkcapital if n=='HongKong' else 0.),incoming_finance_exit_profit=(hkgain if n=='HongKong' else 0.),incoming_finance_transfer_tax=(hktax if n=='HongKong' else 0.),capital_return=capret,net_lease_cash_recovery=(finrepay if n=='Finance' else 0.),declared_dividend=dividend,employee_distribution=emp,old_employee_payment=old_employee,minority_cash=noncontrol,withholding=wht,closing=copy.deepcopy(e),cash_residual=residual))
        # Parent standalone: internal principal receipts do not affect profits or lawful RE.
        parent['internal_asset']+=new_loans-total_repay
        assert abs(parent['internal_asset']-sum(v['internal'] for n,v in st.items() if n not in ('parent','Kokdala')))<1e-7
        parent['receivable']-=oldcash
        interest=parent['debt']*(.025 if y<=4 else .035)+cb_coupon+cb_premium+cb_fee
        deposit=(max(0,parent['cash'])+parent['restricted']+parent['cb_restricted'])*.012
        pretax=entity_ebit['parent']+total_internal_interest-interest+deposit
        tax=max(0,pretax)*.15+max(0,direct_exit_gain)*.15
        parent_impairment=allowance_target['parent']-parent['claim_allowance'];parent['claim_allowance']=allowance_target['parent']
        ownprofit=pretax-tax+parent_exit_loss-parent_impairment
        profit=ownprofit+div_declarations-tax_withholding
        parent['re'],parent['reserve'],rsv=re_step(parent['re'],parent['reserve'],profit,parent['capital'])
        parent['cash']+=ownprofit+parent_impairment+parentdep-parentcap-wcadd*.12+cash_parent+oldcash+total_repay-new_loans+capital_receipt-parent_exit_loss+invsale-acquisition-buyback
        parent['book']+=parentcap-parentdep;parent['wc']+=wcadd*.12
        # Group interest/tax metrics remove internal transfers; dividends aren't group profit.
        group_profit+=ownprofit+parent_impairment-parent_exit_loss-intermediate_exit_tax-tax_withholding;taxsum+=tax+tax_withholding+intermediate_exit_tax;interestpaid+=interest
        independently_summed_tax=sum(z['tax']+z['withholding']+z['incoming_finance_transfer_tax']+z['intermediate_withholding'] for z in ledger)+tax
        assert abs(taxsum-independently_summed_tax)<1e-8
        income_before_external=sum(z['ebit']+z['deposit_interest'] for z in ledger)+entity_ebit['parent']+deposit
        tested_profit=consolidated_profit(income_before_external,interestpaid,independently_summed_tax)
        assert abs(group_profit-tested_profit)<1e-7,(y,group_profit,tested_profit)
        floor=.65*(rev/19.25)
        if sc.get('no_refi'):
            due=min(parent['debt'],3.2 if y==1 else (1 if y in (4,5) else .5))
            parent['cash']-=due;parent['debt']-=due;externalflow-=due
        # Conditional financing: cash never becomes a value-generating negative balance.
        need=max(0,floor-parent['cash']);capacity=max(0,3.5*(op['ebit']+dep)-sum(v['debt'] for v in st.values())-parent['cb_face'])
        if need>capacity+1e-9 or ((sc.get('no_refi') or y>=sc.get('funding_cutoff_year',9999)) and need>1e-9):failure='financing unavailable; continuation rejected'
        elif not failure: parent['cash']+=need;parent['debt']+=need;externalflow+=need
        if failure:
            rows.append(dict(shares=shares,cb_issued=cb_issued,cb_converted=cb_conversion,lease_unearned_remaining=st['Finance']['unearned_income_budget'],year=2026+y,operating=op,failure=failure,cash_shortfall=need,borrowing_capacity=capacity,entities=ledger,parent_state=copy.deepcopy(parent)))
            return dict(method=method,scenario=scenario,feasible=False,years_requested=years,states=rows,value=None)
        # In expansion years ordinary payout 30% of common earnings constrained by parent's cash+RE.
        target=max(0,(group_profit-minority_profit-employee+(.01327155101 if y==1 else 0.))*(.30 if y<=5 else .65))
        if y>5: target=max(target,max(0,parent['cash']-floor)*.9)
        dividend,parent['cash'],parent['re']=pay(parent['cash'],parent['re'],floor,target)
        # residual cash retires debt, neither a distribution nor an operating expense
        retirement=min(parent['debt'],max(0,parent['cash']-floor)*.35)
        parent['cash']-=retirement;parent['debt']-=retirement;externalflow-=retirement
        # internal claims present at opening are not added to equity a second time
        pexpect=pstart['cash']+ownprofit+parent_impairment+parentdep-parentcap-wcadd*.12+cash_parent+oldcash+total_repay-new_loans+capital_receipt-parent_exit_loss+invsale-acquisition-buyback+externalflow+cb_reserve_flow-dividend
        assert abs(parent['cash']-pexpect)<1e-7
        # consolidated cash excludes intercompany interest/principal/dividends; employee & minority are external
        gclose=sum(v['cash'] for v in st.values())
        expected=groupopen+group_profit+dep-capex-wcadd+finrepay+invsale-acquisition-buyback-employee-minority+externalflow+cb_reserve_flow-dividend-oldcash
        # old subsidiary payable -> parent receivable is purely internal: oldcash cancels, so restore it
        expected+=oldcash
        assert abs(gclose-expected)<1e-7,(y,gclose,expected)
        equity_open=equity;common_open=common_equity
        equity+=cb_conversion+group_profit-employee-minority-dividend-buyback+(.01327155101 if y==1 else 0.)
        common_equity+=cb_conversion+group_profit-minority_profit-employee-dividend-buyback+(.01327155101 if y==1 else 0.)
        nci_open=equity_open-common_open;nci_close=equity-common_equity
        assert abs(nci_close-(nci_open+minority_profit-minority))<1e-7
        assert abs(equity-(equity_open+cb_conversion+tested_profit-employee-minority-dividend-buyback+(.01327155101 if y==1 else 0.)))<1e-7
        assert abs(common_equity-(common_open+cb_conversion+tested_profit-minority_profit-employee-dividend-buyback+(.01327155101 if y==1 else 0.)))<1e-7
        assert abs(parent['cb_face']-(cb_open+cb_issued-cb_conversion-cb_redemption))<1e-10
        assert abs(parent['cb_restricted']-(cb_reserve_open+cb_issued-cb_release))<1e-10
        row=dict(entity_operating_profit=entity_ebit,project_operating_profit=project_ebit,legacy_operating_profit=legacy_ebit,capital_allocation=capital_weights,parent_claim_allowance_charge=parent_impairment,internal_claim_allowance_total=sum(v['claim_allowance'] for v in st.values()),growth_cash_by_entity=entity_growth,project_cash=project_cash,project_fund_draw=project_fund_draw,remaining_project_funding_cap=dict(funding_remaining),general_growth_cash=general_growth,convertible=dict(opening_face=cb_open,issued=cb_issued,issuance_fee=cb_fee,coupon_cash=cb_coupon,redemption=cb_redemption,redemption_premium=cb_premium,converted=cb_conversion,new_shares=cb_newshares,closing_face=parent['cb_face'],opening_restricted=cb_reserve_open,eligible_growth_cash=cb_eligible_growth_cash,eligible_wc_cash=cb_eligible_wc,eligible_project_and_wc_release=cb_release,closing_restricted=parent['cb_restricted']),lease_unearned_open=unearned_open,lease_unearned_close=st['Finance']['unearned_income_budget'],nci_equity_open=nci_open,nci_equity_close=nci_close,tax_accrued=independently_summed_tax,tax_cash_paid=taxsum,tax_opening_payable=0.,tax_closing_payable=0.,tax_cash_identity_residual=taxsum-independently_summed_tax,equity_open=equity_open,equity_close=equity,common_equity_open=common_open,common_equity_close=common_equity,minority_profit=minority_profit,year=2026+y,t=y+2/12,operating=op,group_profit=group_profit,capex=capex,depreciation=dep,growth_capex=growthcap,working_capital_change=wcadd,group_open_cash=groupopen,group_close_cash=gclose,group_debt=sum(v['debt'] for v in st.values())+parent['cb_face'],external_financing_net=externalflow,group_taxes=taxsum,external_interest=interestpaid,employee_cash=employee,minority_cash=minority,net_lease_investment_open=finopen,financial_interest=fininterest,financial_repayment=finrepay,financial_loss=finloss,investment_sale=invsale,acquisition_payment=acquisition,buyback=buyback,shares=shares,dividend=dividend,dividend_per_share=dividend/shares,entities=ledger,parent=dict(opening=pstart,own_profit=ownprofit,dividend_income=div_declarations,dividend_cash=cash_parent,old_dividend_cash=oldcash,internal_principal_receipts=total_repay,internal_new_loans=new_loans,capital_return=capital_receipt,investment_exit_profit=parent_exit_loss,intermediate_exit_tax=intermediate_exit_tax,direct_exit_gain=direct_exit_gain,reserve_transfer=rsv,profit=profit,closing=copy.deepcopy(parent)),cash_residual=gclose-expected)
        rows.append(row);prev=op
    pv={str(r):sum(z['dividend_per_share']/(1+r)**z['t'] for z in rows) for r in (.085,.09,.095)}
    y5={str(r):sum(z['dividend_per_share']/(1+r)**(z['year']-2031) for z in rows[5:]) for r in (.085,.09,.095)}
    return dict(method=method,scenario=scenario,feasible=True,years_requested=years,bridge=bridge,states=rows,value=pv,year5_value=y5,first5=[z['dividend_per_share'] for z in rows[:5]],terminal_pv_fraction={str(r):y5[str(r)]/(1+r)**(5+2/12)/pv[str(r)] for r in (.085,.09,.095)})

def main():
    # uses the production RE chain: loss must be cured before reserve.
    hand=re_step(-2,.1,3,10);assert all(abs(a-b)<1e-12 for a,b in zip(hand,(.9,.2,.1)))
    assert pay(13,.9,5,10)==(.9,12.1,0.0)
    out=dict(lease_opening_mapping={'H1_contract_cash':1.35957477614,'H1_unearned':.11291470148,'H1_allowance':.00716094103,'H1_net_investment':1.23949913363,'Q3_net_investment':1.26801707055,'Q3_unearned_budget':1.26801707055*.11291470148/1.23949913363,'legal_face_not_asserted':True},historical_unallocated_tax_losses={'2026':.00427994192,'2027':.03545311794,'2028':.03259037306,'2029':.03131260283,'2030_and_later':.25917972778,'credit_used':0.},asof=ASOF,units='CNY billion except shares billion and CNY per share',entity_inputs=ENT,general_growth_capital_allocation=GROWTH_CAPITAL,project_budget_inputs=PROJECTS,project_operating_inputs=PROJECT_EARNINGS,scenarios=SCENARIOS,outputs=None,tests={'reserve_handcase':hand})
    # Equal byte contract: same sorted JSON keys and full case objects, one live case only.
    jobs={}
    for method in ('tonnes','geography'):
        for scenario in SCENARIOS:jobs[method+'_'+scenario]=(method,scenario,120,None)
        jobs[method+'_base_extended']=(method,'base',240,None)
    jobs['tonnes_creditloss']=('tonnes','base',120,{'creditloss':.15})
    dump=lambda x:json.dump(x,sys.stdout,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    sys.stdout.write('{')
    for i,key in enumerate(sorted(out)):
        if i:sys.stdout.write(',')
        dump(key);sys.stdout.write(':')
        if key!='outputs':dump(out[key]);continue
        sys.stdout.write('{')
        for j,name in enumerate(sorted(jobs)):
            if j:sys.stdout.write(',')
            dump(name);sys.stdout.write(':')
            method,scenario,years,override=jobs[name]
            case=run(method,scenario,years,override);dump(case);del case
        sys.stdout.write('}')
    sys.stdout.write('}\n')
if __name__=='__main__':main()

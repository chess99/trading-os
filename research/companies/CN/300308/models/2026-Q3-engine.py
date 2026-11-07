#!/usr/bin/env python3
"""Independent 300308 owner-cash model. CNY billion, shares billion. No inputs/files/network.
Forecast anniversaries after 2026-10-29; source balances 2026-09-30 rolled for known October dividend.
Entity aggregates D/O are explicit economic budgets, not statutory company statements.
"""
import json,math,copy
CUT='2026-10-29T21:50:00+00:00'
N0=(1177909641-5653063)/1e9
OPT=14746970/1e9
C0=53.48946712097-1.0330493416
ASSET=2.27964230279+3.00426510110+1.08388243662
BASE={'name':'base','method':'volume_mix','margin_shift':0.,'demand':1.,'capital':.50,'issue_factor':1.,'exit_year':999,'exit_mode':'none','tax_remit':.05,'o_margin_shift':0.,'funding':True,'cash_shift':0.,'initial_DO_loan':0.,'initial_D_RE':25.,'strategic_recovery':1.,'stage2_year':1,'redemption_payer':'P','cash_roll_extra':0.,'unlocated_O':.5,'portfolio_shift':0.,'portfolio_delay':0,'portfolio_recovery':1.,'basis_factor':1.,'ipo_transfer_start':1,'contract_timing':'postyear','restrict_overseas_fv':False,'other_receivable_nonop':False,'equipment_advance':.17865321763}

def reserve(re,profit,res,cap):
    total=re+profit
    addition=min(max(0.,total-max(re,0.))*.10,max(0.,cap-res))
    return total-addition,res+addition,addition

def operating(y,c,last):
    qty=[47,56,65,73,80];asp=[2450,2600,2650,2700,2700]
    if y<=5:
        if c['method']=='volume_mix': r=qty[y-1]*asp[y-1]/1000.+.8+.05*(y-1)
        else:
            # independent end-market entry: annual AI infra $bn x optical share x company participation x FX + nonAI
            cap=[760,900,1030,1150,1260][y-1];share=[.060,.065,.070,.075,.080][y-1]
            participation=[.32,.32,.315,.305,.295][y-1]
            r=cap*share*participation*7+4
        r*=c['demand']
        gm=[.45,.43,.41,.385,.365][y-1]+c['margin_shift']
        expense=[.070,.075,.080,.085,.090][y-1]
    else:
        g=max(.02,.10-.016*(y-6));r=last*(1+g)
        gm=max(.31,.365-.011*(y-5))+c['margin_shift'];expense=.09
    if c['name']=='core_low':
        r*=([.96,.94,.92,.90,.88][y-1] if y<=5 else 1.)
        gm=([.44,.415,.39,.36,.335][y-1] if y<=5 else max(.29,.335-.009*(y-5)))
        expense+=.005
    elif c['name']=='core_high':
        r*=([1.03,1.06,1.09,1.12,1.15][y-1] if y<=5 else 1.)
        gm=([.46,.45,.43,.405,.385][y-1] if y<=5 else max(.34,.385-.009*(y-5)))
    if c['method']=='customer_spend':
        pretax_roic=[.72,.66,.61,.56,.52][y-1] if y<=5 else max(.39,.52-.026*(y-5))
        gm=expense+pretax_roic*c['capital']
    if c['name']=='cycle':
        if y<=2:r*= [.78,.82][y-1];gm-=.05
        elif y<=4:r*= [.92,.98][y-3];gm-=.02
    if c['name'] in ('structural','contract_inyear_structural','funding_failure'):
        if y>=2:r*=.78 if y==2 else (.96 if y<=5 else 1.0);gm=min(gm,.24)
        expense=max(expense,.12)
    return r,gm,expense

def working_capital_state(y,c,revenue,core):
    # Gross operating amounts; no off-balance contractual AP/AR knobs.
    if y==0:
        items={'receivables':17.48815136839,'inventory':23.87770202848,'prepayments':1.56698549908,'other_assets':1.75079420738-(.28398638655 if c['other_receivable_nonop'] else 0.),'payables':14.66305633718,'tax_salary':2.20162543783,'contract_liabilities':.01128812651,'other_operating_liabilities':.01738320685,'long_material_prepayment':1.95402617149-c['equipment_advance']}
        pools={q:{k:v*weight for k,v in items.items()} for q,weight in [('D',.25),('O',.75)]}
    else:
        pools={}
        for q,weight,ar,ap,pre,other,tax,contract in [('D',.25,.05,.06,.004,.004,.008,.00001),('O',.75,.17*.97,.15*.97,.012,.012,.014,.0001)]:
            z={'receivables':revenue*ar,'payables':revenue*ap,'prepayments':revenue*pre,'other_assets':revenue*other,'tax_salary':revenue*tax,'contract_liabilities':revenue*contract}
            z['inventory']=core*weight-z['receivables']-z['prepayments']-z['other_assets']+z['payables']+z['tax_salary']+z['contract_liabilities']
            z['other_operating_liabilities']=.01738320685/100*revenue*weight
            z['long_material_prepayment']=(1.95402617149-.17865321763)/100*revenue*weight
            z['inventory']+=z['other_operating_liabilities']-z['long_material_prepayment']
            pools[q]=z
        profile=([1.,1.,.5,0.][y-1] if y<=4 else 0.) if c['name']=='overseas_trade_credit' else (([1.,1.,1.,.5,0.][y-1] if y<=5 else 0.) if c['name']=='supplier_credit_withdrawal' else 0.)
        credit=(.12 if c['name']=='overseas_trade_credit' else -.08)*revenue*.97*profile
        pools['O']['payables']+=credit
    for q,z in pools.items():
        z['gross_assets']=sum(z[k] for k in ('receivables','inventory','prepayments','other_assets','long_material_prepayment'))
        z['gross_liabilities']=sum(z[k] for k in ('payables','tax_salary','contract_liabilities','other_operating_liabilities'))
        z['net_wc']=z['gross_assets']-z['gross_liabilities']
        assert min(z.values())>=-1e-10,(y,q,z)
    return pools

def overseas_profit_holdback(assets,c):
    # Conditional Singapore eligibility sensitivity, not a general cash-realization rule.
    if not c['restrict_overseas_fv']:return 0.
    return sum(max(0.,a['book']-a['opening_reference_cost']) for a in assets if a['owner']=='O' and a['kind']!='associate')

def portfolio_start(c):
    # Confirmed parent blocks: H1 parent associates + paid Zhongshi stake; parent other financial assets.
    confirmed={'associate':.10986498862+1.747448473,'fund':.60820460056*(.71978903860/.93788963417),'private':.60820460056*(.21810059557/.93788963417),'trading':0.}
    totals={'associate':3.0042651011,'trading':2.27964230279,'fund':1.08388243662*(.71978903860/.93788963417),'private':1.08388243662*(.21810059557/.93788963417)}
    terms={'associate':(.055,.10,12,.96),'trading':(.04,.25,4,.90),'fund':(.06,.25,8,.90),'private':(.06,.25,12,.90)}
    out=[]
    for typ,total in totals.items():
        for owner,book in [('P',confirmed[typ]),('D',(total-confirmed[typ])*(1-c['unlocated_O'])),('O',(total-confirmed[typ])*c['unlocated_O'])]:
            rate,payout,end,basis=terms[typ]
            taxcost=(1.747448473+.10986498862*.96*c['basis_factor']) if typ=='associate' and owner=='P' else book*basis*c['basis_factor']
            if book:out.append({'kind':typ,'owner':owner,'book':book,'basis':taxcost,'opening_reference_cost':book,'return_rate':rate+c['portfolio_shift'],'payout':payout,'exit_year':end+c['portfolio_delay'],'recovery':c['portfolio_recovery']})
    return out

def portfolio_step(assets,y,c):
    bookprofit={k:0. for k in ('P','D','O')};legal=dict(bookprofit);cash=dict(bookprofit);detail=[]
    # Separate financial strategic projects, not benefits already embedded in module EBIT.
    strategic_spend=1.58 if 3<=y<=7 else 0.
    if strategic_spend:
        assets.append({'kind':'strategic','owner':'P','book':strategic_spend,'basis':strategic_spend,'opening_reference_cost':strategic_spend,'return_rate':.08+c['portfolio_shift'],'payout':.25,'exit_year':15+c['portfolio_delay'],'recovery':c['strategic_recovery']})
        cash['P']-=strategic_spend
    for a in assets:
        opening=a['book'];owner=a['owner']
        if opening<=0:continue
        profit=opening*a['return_rate'];distribution=max(0.,profit)*a['payout']
        # Book income is after investee tax; qualifying domestic cash distributions assumed exempt.
        divtax=(.17 if owner=='O' else .25) if a['kind']=='fund' else (.05 if owner=='O' else 0.)
        withhold=distribution*divtax
        a['book']+=profit-distribution
        bookprofit[owner]+=profit-withhold;legal[owner]+=distribution-withhold;cash[owner]+=distribution-withhold
        sale=fee=tax=0.
        if y==a['exit_year']:
            sale=a['book']*a['recovery'];fee=sale*(.01 if a['kind']=='trading' else .02)
            tax=max(0.,sale-fee-a['basis'])*(.17 if owner=='O' else .25)
            cash[owner]+=sale-fee-tax
            bookprofit[owner]+=sale-fee-a['book']-tax
            legal[owner]+=sale-fee-a['opening_reference_cost']-tax
            a['book']=0.
        detail.append(dict(a,opening_book=opening,book_income=profit,cash_dividend=distribution,withholding=withhold,exit_gross=sale,exit_fee=fee,exit_tax=tax))
    balances={k:sum(a['book'] for a in assets if a['owner']==k) for k in ('P','D','O')}
    return bookprofit,legal,cash,balances,detail,strategic_spend

def contract_dividend(reference,eligible_profit_budget,fcf_budget,retained_availability_budget,cash_available,operating_reserve,policy):
    netcash=reference['cash']-reference['interest_debt']-max(0.,reference['payable']-reference['receivable'])
    outflow=max(0.,-fcf_budget)
    lower=max(.20*max(0.,eligible_profit_budget),.25*max(0.,netcash-outflow))
    capacity=min(max(0.,retained_availability_budget),max(0.,cash_available-operating_reserve))
    declare=capacity+1e-10>=lower
    paid=min(capacity,max(policy,lower)) if declare else 0.
    return {'reference':reference,'net_cash':netcash,'next_12m_fcf':fcf_budget,'next_12m_outflow':outflow,'minimum_if_declared':lower,'distribution_capacity':capacity,'declared':declare,'paid':paid,'reason':None if declare else 'minimum_exceeds_profit_or_operating_cash_capacity'}

def overseas_forward(y,c,revenue,fixed,core,gross,cash,loan,assets):
    nr,ng,ne=operating(y+1,c,revenue);depreciation=fixed*.12
    cap=max(depreciation*.65,nr*c['capital']*.4-fixed+depreciation)
    nextcore=max(nr*c['capital']*.6,core*.70)
    futuregross=working_capital_state(y+1,c,nr,nextcore)
    dw=futuregross['O']['net_wc']-gross['O']['net_wc']
    pretax=min(nr*(ng-ne)*.70,nr*.97*(min(.145,.10+.01125*y)+c['o_margin_shift']))
    tax=min(.17,.15+.01*y)
    _,_,money,_,_,_=portfolio_step(copy.deepcopy(assets),y+1,c)
    return pretax*(1-tax)+cash*.02*(1-tax)-loan*.03*(1-tax)+money['O']+depreciation*.50-cap*.50-dw,.02*(1-tax)

def run(c,T=180,terms=None):
    # Group cash exact; location is deliberately a budget sensitivity, not inferred legal access.
    cash={'P':41.+c['cash_shift']-c['cash_roll_extra'],'D':7.-c['cash_shift'],'O':C0-48.}
    re={'P':.0083,'D':c['initial_D_RE'],'O':4.};sr={'P':.50474934023,'D':2.5,'O':0.}
    loanPD=.173;loanDP=5.9503354;loanDO=c['initial_DO_loan'];olddiv=1.645
    invcost=14.60825582072;invallow=.03446700615;assets=portfolio_start(c);assetbook={k:sum(a['book'] for a in assets if a['owner']==k) for k in ('P','D','O')};fin=assetbook['P'];finbasis=0.
    stock=N0;own=87821368/132445184;finminor=23739112/132445184;warrants=False;claim=5.06300063538;claim_base=claim
    debt=1.85616607235;capdue=4.0;fixed=20.021;last=100.
    gross=working_capital_state(0,c,last,0.);wc=sum(z['net_wc'] for z in gross.values());corewc=wc;opening_gross=copy.deepcopy(gross)
    nonop_receivable={q:(.28398638655*w if c['other_receivable_nonop'] else 0.) for q,w in [('D',.25),('O',.75)]};prior_holdback=0.;capital_advance=c['equipment_advance']
    ipo={'rd':18.4,'capacity':13.5,'supply':5.2,'strategic':7.9};restriction=45.;strategic=0.;contract_prior=None;rows=[];feasible=True;fail=None
    prior_equity={'P':cash['P']+invcost-invallow+fin+strategic+loanPD+olddiv-loanDP,'D':cash['D']+assetbook['D']+fixed*.5+capital_advance*.5+gross['D']['net_wc']+nonop_receivable['D']+loanDP+loanDO-loanPD-debt-capdue-olddiv,'O':cash['O']+assetbook['O']+fixed*.5+capital_advance*.5+gross['O']['net_wc']+nonop_receivable['O']-loanDO}
    for y in range(1,T+1):
        opening=copy.deepcopy(cash);op_re=copy.deepcopy(re);old_loans=(loanPD,loanDP,loanDO)
        r,gm,expense=operating(y,c,last)
        # Gross margin includes depreciation; depreciation is added back only in cash flow.
        dep=fixed*.12;ebit=r*(gm-expense)
        target_fixed=r*c['capital']*.4
        gross_capex=max(dep*.65,target_fixed-fixed+dep)
        advance_used=min(capital_advance,gross_capex);capital_advance-=advance_used
        capex=gross_capex-advance_used
        fixed1=fixed+gross_capex-dep
        target_wc=r*c['capital']*.6;corewc1=max(target_wc,corewc*.70)
        gross1=working_capital_state(y,c,r,corewc1);wc1=sum(z['net_wc'] for z in gross1.values());dwc=wc1-wc
        wc_flow={q:gross1[q]['net_wc']-gross[q]['net_wc'] for q in ('D','O')}
        nr_collected={q:(nonop_receivable[q] if y==2 else 0.) for q in ('D','O')}
        for q in ('D','O'):cash[q]+=nr_collected[q];nonop_receivable[q]-=nr_collected[q]
        ocapshare=.50;owcshare=.75
        o_pretax=min(ebit*.70,r*.97*(min(.145,.10+.01125*(y-1))+c['o_margin_shift']))
        # Domestic/foreign transfer allocation changes local taxes, not total EBIT.
        d_pretax=ebit-o_pretax
        td=.16;to=min(.17,.15+.01*(y-1))
        opD=d_pretax*(1-td);opO=o_pretax*(1-to)
        pbook,plegal,pcash,assetbook,pdetails,strategic_spend=portfolio_step(assets,y,c)
        strategic=sum(a['book'] for a in assets if a['kind']=='strategic');fin=assetbook['P']-strategic
        interest_debt=debt*.027;repay=min(debt,.95)
        finance={k:opening[k]*.02*(1-({'P':.25,'D':td,'O':to}[k])) for k in cash}
        # Intercompany interest paid on legal face balances; no allowance eliminates face.
        ipd=loanPD*.03;idp=loanDP*.03;ido=loanDO*.03
        internal_tax=(td-.25)*ipd+(.25-td)*idp+(to-td)*ido
        npD=opD+pbook['D']+finance['D']+(idp+ido-ipd)*(1-td)-interest_debt
        npO=opO+pbook['O']+finance['O']-ido*(1-to)
        npP=pbook['P']+finance['P']+(ipd-idp)*.75-.15
        cfoD=npD-pbook['D']+pcash['D']+dep*(1-ocapshare)-wc_flow['D']
        cfoO=npO-pbook['O']+pcash['O']+dep*ocapshare-wc_flow['O']
        paycap=min(capdue,2.)
        cash['D']+=cfoD-capex*(1-ocapshare)-repay-paycap
        cash['O']+=cfoO-capex*ocapshare
        cash['P']+=npP-pbook['P']+pcash['P']
        debt-=repay;capdue-=paycap
        tranche_parent=0.;tranche_minority=0.
        if y==c['stage2_year']:
            tranche_parent=3061223*32.16*7/1e9;tranche_minority=(346267+1118348)*32.16*7/1e9
            cash['P']-=tranche_parent;cash['O']+=tranche_parent+tranche_minority;invcost+=tranche_parent
            own=90882591/136971022;finminor=24857460/136971022
            claim_base+=1118348*32.16*7/1e9;claim=claim_base
        # Exchange/warrant budget occurs at end-year after trading, before distribution.
        warrant_cash=0.;issued=0.;fees=0.;settlement=0.;acquired=0.;taxexit=0.
        if y==c['exit_year'] and c['exit_mode']=='exchange':
            w=6712155/(136971022 if y>=c['stage2_year'] else 132445184) # current issued-sub shares; pending tranche not presumed complete
            warrant_cash=6712155*32.16*7/1e9
            cash['O']+=warrant_cash
            own/=1+w;finminor/=1+w;warrants=True
            if terms:
                acquired=finminor;settlement=terms['stake_value'];issued=settlement/(terms['parent_price']*c['issue_factor'])
                stock+=issued;own+=acquired;finminor=0.;claim=0.
                invcost+=settlement;fees=settlement*.005;cash['P']-=fees;npP-=fees
        elif y==c['exit_year'] and c['exit_mode']=='redeem':
            # Disclosed PV rolled at upper contract rate is a stress proxy, not legal face quotation.
            settlement=claim_base*1.08**y;acquired=finminor
            if c['redemption_payer']=='O':
                cash['O']-=settlement;before=own;own=own/(1-finminor);acquired=own-before
            else:
                cash['P']-=settlement;own+=acquired;invcost+=settlement
            finminor=0.;claim=0.
        elif claim>0:claim=claim_base # unresolved conditional liability retained; no invented discharge
        # Fund or repay internal support; intercompany balance is not a group cash source.
        p_to_d=min(loanDP,max(0.,cash['P']-2.),2.)
        cash['P']-=p_to_d;cash['D']+=p_to_d;loanDP-=p_to_d
        d_to_p=min(loanPD,max(0.,cash['D']-r*.02))
        cash['D']-=d_to_p;cash['P']+=d_to_p;loanPD-=d_to_p
        old_collect=min(olddiv,max(0.,cash['D']-r*.02))
        cash['D']-=old_collect;cash['P']+=old_collect;olddiv-=old_collect
        o_to_d=min(loanDO,max(0.,cash['O']-r*.025),max(0.,npO)*.65)
        cash['O']-=o_to_d;cash['D']+=o_to_d;loanDO-=o_to_d
        supportD=0.;supportO=0.
        for k,floor in [('D',r*.02),('O',r*.025)]:
            need=max(0.,floor-cash[k]);available=max(0.,cash['P']-2.) if c['funding'] else 0.
            pay=min(need,available);cash['P']-=pay;cash[k]+=pay
            if k=='D':loanPD+=pay;supportD=pay
            else:loanPD+=pay;loanDO+=pay;supportO=pay # via wholly-owned domestic treasury, corresponding receivable
            if need>pay+1e-8:
                feasible=False;fail={'year':y,'entity':k,'shortfall':need-pay};break
        if not feasible:
            # Stop: no negative-cash continuation or fictitious equity rescue.
            rows.append({'year':y,'failed':fail,'cash':cash});break
        # Future awards are not free: full known dilution plus cash at budget weighted exercise price.
        opt=OPT*[.4,.35,.20,.05][y-1] if y<=4 else 0.
        optcash=opt*((6220690-759850)*36.16+759850*35.16+(8526280-1100000)*52.10+1100000*53.10)/14746970;stock+=opt;cash['P']+=optcash
        # IPO source tracking: actual parent loans reimburse budgeted eligible cash expenditures.
        ipo_transfers={'D':0.,'O':0.};ipo_consumed={'rd':0.,'capacity':0.,'supply':0.,'strategic':strategic_spend}
        ipo['strategic']=max(0.,ipo['strategic']-strategic_spend)
        eligible={'rd':r*.03,'capacity':capex,'supply':sum(max(0.,v) for v in wc_flow.values())}
        if y>=c['ipo_transfer_start']:
            for category in ('rd','capacity','supply'):
                use=min(ipo[category],eligible[category],max(0.,cash['P']-2.))
                offshore=(max(0.,wc_flow['O'])/max(1e-30,eligible['supply'])) if category=='supply' else .50
                cash['P']-=use;cash['D']+=use*(1-offshore);cash['O']+=use*offshore
                loanPD+=use;loanDO+=use*offshore
                ipo_transfers['D']+=use*(1-offshore);ipo_transfers['O']+=use*offshore
                ipo[category]-=use;ipo_consumed[category]=use
        restriction=sum(ipo.values())
        realization=taxexit=0. # exits are fully included in pcash/pbook, never repeated
        fgain=0.;strategic_sale=sum(z['exit_gross'] for z in pdetails if z['kind']=='strategic');strategic_tax=sum(z['exit_tax'] for z in pdetails if z['kind']=='strategic')
        holdback=overseas_profit_holdback(assets,c);contract_profit=npO-(holdback-prior_holdback)
        re['D'],sr['D'],resD=reserve(re['D'],npD,sr['D'],5.)
        re['O']+=npO;resO=0.
        available_O=max(0.,re['O']-holdback)
        ddiv=min(max(0.,re['D']),max(0.,cash['D']-r*.02),max(0.,npD)*(.4 if y<=5 else min(.95,.4+.055*(y-5)))+max(0.,cash['D']-r*.04)*(.0 if y<=5 else .15))
        o_target=max(0.,npO)*(.20 if y<=5 else min(.80,.20+.06*(y-5)))
        # Cash year y=3 (2029) first covers the FY2028 declared dividend. Audited annual state
        # is represented by the previous budget closing state; approved next-FY FCF is current flow.
        contract=None
        if c['contract_timing']=='inyear' and y>=2:
            reference={'cash':cash['O'],'interest_debt':loanDO,'receivable':gross1['O']['receivables'],'payable':gross1['O']['payables'],'distributable_profit':contract_profit,'budget_year':2026+y}
            forward,interest_slope=overseas_forward(y,c,r,fixed1,corewc1,gross1,cash['O'],loanDO,assets)
            guess=0.
            for _ in range(16):
                contract=contract_dividend(reference,contract_profit,forward-interest_slope*guess,available_O,cash['O'],r*.025,o_target)
                guess=contract['paid']
            odiv=guess
        elif y>=3:
            next_fcf=cfoO-capex*ocapshare
            contract=contract_dividend(contract_prior,contract_prior['distributable_profit'],next_fcf,available_O,cash['O'],r*.025,o_target)
            odiv=contract['paid']
        else:odiv=min(available_O,max(0.,cash['O']-r*.025),o_target)
        cash['D']-=ddiv;cash['O']-=odiv;re['D']-=ddiv;re['O']-=odiv
        dminor=ddiv*.005;ominor=odiv*(1-own)
        upstream=ddiv-dminor+odiv*own*(1-c['tax_remit']);remittax=odiv*own*c['tax_remit']
        cash['P']+=upstream;npP+=upstream
        re['P'],sr['P'],resP=reserve(re['P'],npP,sr['P'],(stock+5653063/1e9)*.5)
        desired=(opD*.995+opO*own)*([.15,.175,.20,.225,.25][y-1] if y<=5 else min(.85,.25+.06*(y-5)))
        if y>5:desired+=max(0.,cash['P']-restriction-2.)*.15
        div=min(max(0.,re['P']),max(0.,cash['P']-restriction-2.),max(0.,desired))
        cash['P']-=div;re['P']-=div
        groupfcf=opD+opO+dep-capex-dwc
        delta=sum(cash.values())-sum(opening.values())
        external=groupfcf+sum(finance.values())+internal_tax-.15-interest_debt-repay-paycap+warrant_cash+tranche_minority+optcash+sum(pcash.values())+sum(nr_collected.values())-fees-(settlement if c['exit_mode']=='redeem' and y==c['exit_year'] else 0.)-div-dminor-ominor-remittax
        assert abs(delta-external)<1e-7*max(1.,abs(external)),(y,delta,external)
        assert min(cash.values())>=-1e-8
        row={'year':y,'revenue':r,'gross_margin':gm,'expense_ratio':expense,'ebit':ebit,'domestic_pretax':d_pretax,'overseas_pretax':o_pretax,'op_profit_D':opD,'op_profit_O':opO,'tax_D':td,'tax_O':to,'depreciation':dep,'capex':capex,'gross_capex':gross_capex,'capital_advance_remaining':capital_advance,'capital_advance_applied':advance_used,'maintenance_capex':dep*.65,'growth_capex':gross_capex-dep*.65,'wc':wc1,'delta_wc':dwc,'fixed':fixed1,'fcf':groupfcf,'cash_open':opening,'cash':copy.deepcopy(cash),'retained':copy.deepcopy(re),'reserves':copy.deepcopy(sr),'profits':{'D':npD,'O':npO,'P':npP},'dividend_D':ddiv,'dividend_O':odiv,'upstream':upstream,'dividend':div,'dps':div/stock,'shares':stock,'registered_shares':stock+5653063/1e9,'treasury_shares':5653063/1e9,'minority_cash':dminor+ominor,'overseas_ownership':own,'financial_minority':finminor,'redemption_accounting_proxy':claim,'contract_cash_proxy_low':claim*1.04**y,'contract_cash_proxy_high':claim*1.08**y,'debt':debt,'capex_payable':capdue,'parent_investment_cost':invcost,'parent_investment_allowance':invallow,'loan_P_to_D_face':loanPD,'loan_D_to_P_face':loanDP,'loan_D_to_O_face':loanDO,'loan_allowance':0.,'old_dividend_receivable':olddiv,'old_dividend_collected':old_collect,'capital_support_D':supportD,'capital_support_O_via_D':supportO,'ipo_use_reserve':restriction,'nonoperating_asset':fin,'portfolio_by_owner':dict(assetbook),'portfolio_detail':pdetails,'portfolio_book_income':pbook,'portfolio_realized_income_proxy':plegal,'portfolio_cash':pcash,'ipo_budget_remaining':dict(ipo),'ipo_loan_transfers':ipo_transfers,'ipo_consumed':ipo_consumed,'overseas_dividend_contract':contract,'strategic_asset':strategic,'strategic_spend':strategic_spend,'strategic_sale':strategic_sale,'strategic_tax':strategic_tax,'finance_income':finance,'internal_interest_tax_cash_effect':internal_tax,'stage2_parent_cash':tranche_parent,'stage2_minority_cash':tranche_minority,'warrant_cash':warrant_cash,'option_cash':optcash,'new_shares':issued+opt,'exit_consideration':settlement,'acquired_O_share':acquired,'redemption_payer':c['redemption_payer'],'exit_fees':fees,'exit_tax':taxexit,'remittance_tax':remittax,'cash_conservation_residual':delta-external}
        equity={'P':cash['P']+invcost-invallow+fin+strategic+loanPD+olddiv-loanDP,'D':cash['D']+assetbook['D']+fixed1*.5+capital_advance*.5+gross1['D']['net_wc']+nonop_receivable['D']+loanDP+loanDO-loanPD-debt-capdue-olddiv,'O':cash['O']+assetbook['O']+fixed1*.5+capital_advance*.5+gross1['O']['net_wc']+nonop_receivable['O']-loanDO}
        er={'P':equity['P']-prior_equity['P']-(npP-div+optcash+(settlement if acquired and c['exit_mode']=='exchange' else 0.)), 'D':equity['D']-prior_equity['D']-(npD-ddiv), 'O':equity['O']-prior_equity['O']-(npO-odiv+warrant_cash+tranche_parent+tranche_minority-(settlement if c['exit_mode']=='redeem' and c['redemption_payer']=='O' else 0.))}
        assert max(abs(z) for z in er.values())<1e-7*max(1.,sum(equity.values())),(y,er)
        row['entity_net_assets_excluding_conditional_put']=equity;row['entity_equity_reconciliation']=er
        row['economic_common_group_net_assets']=equity['P'] # parent standalone; operating subsidiaries are cost-method, not added again
        prior_equity=equity
        contract_prior={'cash':cash['O'],'interest_debt':loanDO,'receivable':gross1['O']['receivables'],'payable':gross1['O']['payables'],'distributable_profit':contract_profit,'budget_year':2026+y}
        row['overseas_contract_closing_state']=dict(contract_prior)
        row.update({'gross_working_capital':copy.deepcopy(gross1),'opening_gross_working_capital':copy.deepcopy(gross),'core_wc':corewc1,'wc_cash_movement':dict(wc_flow),'nonoperating_receivable':dict(nonop_receivable),'nonoperating_receivable_collected':nr_collected,'overseas_profit_holdback':holdback,'overseas_contract_profit':contract_profit,'overseas_book_profit':npO,'accounting_retained':copy.deepcopy(re),'distribution_retained_capacity':{'P':max(0.,re['P']),'D':max(0.,re['D']),'O':max(0.,re['O']-holdback)}})
        prior_holdback=holdback;corewc=corewc1;gross=gross1
        rows.append(row);fixed=fixed1;wc=wc1;last=r
    return {'config':c,'feasible':feasible,'failure':fail,'terms':terms,'annual':rows}

def continuation(rows,year,r,field='dps'):
    return sum(a.get(field,0.)/(1+r)**(a['year']-year) for a in rows if a['year']>year)

def terms_for(c,T):
    pre=run(c,T,None)
    if not pre['feasible']:return None,pre
    t=c['exit_year'];s=pre['annual'][t-1]
    ov=continuation(pre['annual'],t,.105,'dividend_O')
    pv=continuation(pre['annual'],t,.105,'dps')
    return {'stake_value':ov*s['financial_minority'],'parent_price':pv,'overseas_all_equity':ov,'reference_rate':.105},pre

def value(c,T):
    terms,pre=terms_for(c,T) if c['exit_mode']=='exchange' else (None,None)
    out=run(c,T,terms)
    if out['feasible']:
        out['value']={str(r):continuation(out['annual'],0,r) for r in [.10,.105,.11]}
        out['terminal5']={str(r):continuation(out['annual'],5,r) for r in [.10,.105,.11]}
        out['five_dps']=[a['dps'] for a in out['annual'][:5]]
        out['tail5_pv_fraction']=out['terminal5']['0.105']/1.105**5/out['value']['0.105']
    else:out['value']=None
    if pre is not None:out['pricing_counterfactual']=pre
    return out

def exit_waterfall(gross,cost,fee_rate,tax_rate,loan_face,allowance):
    fee=gross*fee_rate
    gain=gross-fee-cost
    tax=max(gain,0.)*tax_rate
    # loan face is repaid separately; allowance reversal is not new external cash.
    return {'gross_equity_proceeds':gross,'cost':cost,'fee':fee,'tax':tax,'accounting_gain':gain-tax,'loan_face_received':loan_face,'allowance_reversed':allowance,'cash_received':gross-fee-tax+loan_face}

def parent_sale_state(case):
    a=case['annual'][4]
    gross=continuation(case['annual'],5,.105,'upstream')
    f=exit_waterfall(gross,a['parent_investment_cost'],.02,.25,a['loan_P_to_D_face'],a['loan_allowance'])
    # Tax basis is gross cost; book allowance reversal is not an additional cash inflow.
    f['accounting_gain']+=a['parent_investment_allowance']
    cash=a['cash']['P']+f['cash_received']-a['loan_D_to_P_face']
    re,sr,addition=reserve(a['retained']['P'],f['accounting_gain']+a['loan_allowance'],a['reserves']['P'],a['registered_shares']*.5)
    retained_guarantee=a['contract_cash_proxy_high']
    dividend=min(max(0.,re),max(0.,cash-2.-retained_guarantee))
    post_equity=cash+a['nonoperating_asset']+a['strategic_asset']
    prior=a['entity_net_assets_excluding_conditional_put']['P']
    residual=post_equity-prior-f['accounting_gain']
    assert abs(residual)<1e-7*max(1.,abs(post_equity))
    return {'sale':f,'starting_parent_cash':a['cash']['P'],'debt_face_repaid':a['loan_D_to_P_face'],'post_settlement_cash_before_distribution':cash,'retained_guarantee_cash_budget':retained_guarantee,'post_sale_investment_cost':0.,'post_sale_loan_face':0.,'post_sale_retained_before_distribution':re,'post_sale_reserve':sr,'exit_distribution':dividend,'post_distribution_cash':cash-dividend,'post_distribution_retained':re-dividend,'post_sale_net_assets_before_distribution':post_equity,'equity_reconciliation':residual}

def main():
    configs=[]
    for name,kw in [('base',{}),('core_low',{'capital':.55,'o_margin_shift':.01}),('core_high',{'capital':.48,'o_margin_shift':-.005}),('demand_entry',{'method':'customer_spend'}),('cycle',{}),('structural',{'capital':.70,'exit_mode':'redeem','exit_year':5}),('bull',{'demand':1.15,'margin_shift':.025}),('issue_discount',{'issue_factor':.75,'exit_mode':'exchange','exit_year':3}),('issue_premium',{'issue_factor':1.25,'exit_mode':'exchange','exit_year':3}),('fair_exchange',{'exit_mode':'exchange','exit_year':3}),('cash_location',{'cash_shift':-10.}),('legacy_intercompany',{'initial_DO_loan':13.1}),('low_domestic_reserves',{'initial_D_RE':5.}),('strategic_loss',{'strategic_recovery':.5}),('portfolio_weak',{'portfolio_shift':-.04,'portfolio_recovery':.7}),('portfolio_strong',{'portfolio_shift':.025,'portfolio_recovery':1.1}),('portfolio_delayed',{'portfolio_delay':5}),('portfolio_all_unknown_O',{'unlocated_O':1.}),('portfolio_all_unknown_D',{'unlocated_O':0.}),('portfolio_taxbasis_low',{'basis_factor':.8}),('ipo_funding_delayed',{'ipo_transfer_start':6}),('overseas_trade_credit',{}),('supplier_credit_withdrawal',{}),('overseas_profit_restriction',{'restrict_overseas_fv':True}),('other_receivable_nonoperating',{'other_receivable_nonop':True}),('prepayment_all_material',{'equipment_advance':0.}),('prepayment_all_equipment',{'equipment_advance':1.95402617149}),('contract_inyear',{'contract_timing':'inyear'}),('contract_inyear_structural',{'contract_timing':'inyear','capital':.70,'exit_mode':'redeem','exit_year':5}),('contract_no_ipo',{'exit_mode':'redeem','exit_year':5,'redemption_payer':'O'}),('late_put',{'exit_mode':'redeem','exit_year':43,'redemption_payer':'O'}),('unclosed_tranche',{'stage2_year':999}),('dividend_timing',{'cash_roll_extra':1.3314978936+.07521-1.0330493416}),('tax_remittance',{'tax_remit':.10}),('call_liquidity',{'exit_mode':'redeem','exit_year':3}),('funding_failure',{'capital':1.50,'funding':False,'exit_mode':'redeem','exit_year':2})]:
        c=dict(BASE);c.update(kw);c['name']=name;configs.append(c)
    output={'as_of':CUT,'units':'CNY billion/shares billion','known_start':{'cash':C0,'shares':N0,'portfolio':ASSET},'cases':{c['name']:value(c,180) for c in configs}}
    output['tail_extension']={str(t):value(dict(BASE),t) for t in (240,300)}
    # Formal production-chain handcase: reserve must first repair losses.
    assert reserve(-3,5,0,10)==(1.8,.2,.2)
    assert reserve(-3,2,0,10)==(-1,0,0)
    assert continuation([{'year':1,'dps':11},{'year':2,'dps':12.1}],0,.1)==20.
    waterfall=exit_waterfall(20,14,.05,.25,3,1)
    assert waterfall['cash_received']==20.75 and waterfall['accounting_gain']==3.75
    assert contract_dividend({'cash':10.,'interest_debt':2.,'payable':4.,'receivable':1.},8.,-1.,20.,10.,1.,0.)['paid']==1.6
    assert contract_dividend({'cash':10.,'interest_debt':2.,'payable':4.,'receivable':1.},0.,2.,20.,10.,1.,0.)['paid']==1.25
    hold=portfolio_step([{'kind':'associate','owner':'P','book':10.,'basis':10.,'opening_reference_cost':10.,'return_rate':.1,'payout':.2,'exit_year':3,'recovery':1.}],1,dict(BASE))
    assert hold[0]['P']==1. and hold[1]['P']==.2 and hold[2]['P']==.2 and hold[3]['P']==10.8
    salecheck=portfolio_step([{'kind':'associate','owner':'P','book':10.,'basis':8.,'opening_reference_cost':10.,'return_rate':0.,'payout':.2,'exit_year':1,'recovery':1.}],1,dict(BASE))
    assert abs(salecheck[1]['P']+.65)<1e-12 and abs(salecheck[2]['P']-9.35)<1e-12
    accountcheck=reserve(0.,hold[0]['P'],0.,10.)
    assert accountcheck==(.9,.1,.1)
    output['handcases']={'loss_repair':reserve(-3,5,0,10),'still_loss':reserve(-3,2,0,10),'discount_two_years':20.,'investment_exit':waterfall,'contract_negative_fcf':1.6,'contract_positive_fcf':1.25,'portfolio_taxbasis_separation':{'legal_gain':salecheck[1]['P'],'cash':salecheck[2]['P']},'equity_income_retained':{'income':hold[0]['P'],'cash':hold[2]['P'],'retained':accountcheck[0],'reserve':accountcheck[1]},'portfolio_hold':{'book_profit':1.,'legal_income':.2,'cash':.2,'closing_book':10.8}}
    output['conditional_parent_exit']={n:parent_sale_state(o) for n,o in output['cases'].items() if o['feasible']}
    print(json.dumps(output,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()

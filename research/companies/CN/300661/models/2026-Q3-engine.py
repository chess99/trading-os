#!/usr/bin/env python3
"""SG Micro 2026Q3 standalone economic budget. CNY million; million shares.
No input files or network. All annual states retained. Budget, not legal opinion.
"""
import json, math, sys, copy
ASOF='2026-10-30T03:54:00+00:00'

def reserve(re, res, profit, cap):
    after=re+profit
    eligible=max(0.0,after)-max(0.0,re)
    addition=min(max(0.0,cap*.5-res),max(0.0,eligible)*.1)
    return after-addition,res+addition,addition

def deferred_contracts(shift=0):
    """Original full put right is 50m/10%; book allocation is NOT cash allocation.
    H1 aggregate buckets are retained as a forward timing budget. Q3 entity book
    split uses H1 disclosed book proportions, not a claimed Q3 legal subledger.
    """
    timeline={2+shift:87.85685,4+shift:109.999429,6+shift:5.76473597}
    parent_book=191.93659398*145.75902890/190.61918886
    entries=[]
    for ident,face,book in [('purchase',153.62101497,parent_book),('original_put_10pct',50.,191.93659398-parent_book)]:
        schedule={year:amount*face/203.62101497 for year,amount in timeline.items()}
        lower,upper=0.,.5
        for _ in range(100):
            rate=(lower+upper)/2
            if sum(amount/(1+rate)**year for year,amount in schedule.items())>book:lower=rate
            else:upper=rate
        entries.append(dict(id=ident,original_face=face,initial_book=book,face=face,book=book,basis=book,
                            interest_total=0.,eir=(lower+upper)/2,schedule=schedule))
    return entries,timeline


def operating(method,years,scenario):
    rows=[]; sig=2650.;power=3550.;other=100.;units=13000.;asp=.485;cost=.232
    head=1570.;comp=.64; nonlabor=350.;acqrev=340.
    prior=5401.74317963
    for y in range(1,years+1):
        if y>1:
            gs=max(.02,.18-.02*(y-2)) if y<=10 else max(.02,.07-.005*(y-10))
            gp=max(.02,.14-.012*(y-2)) if y<=10 else max(.02,.04-.002*(y-10))
            sig*=1+gs;power*=1+gp;other*=1.06 if y<6 else 1.02
            vg=max(.035,.19-.016*(y-2)) if y<=10 else max(.035,.062-.0027*(y-10))
            units*=1+vg if y<=20 else 1.02
            if y<=20:asp*=.985;cost*=.986
            head*=1+max(.02,.12-.01*(y-2));comp*=1.025 if y<=20 else 1.;nonlabor*=1+max(.02,.12-.01*(y-2))
            acqrev*=1+(max(.02,.20-.015*(y-2)) if y<=12 else .02)
        if method=='products':
            revenue=sig+power+other
            margin_sig=.5711-.001*min(y-1,15);margin_power=.4797-.0004*min(y-1,15)
            gross=sig*margin_sig+power*margin_power+other*.5
            rd=revenue*(.225-.0005*min(y-1,10));sga=revenue*(.089-.0006*min(y-1,15))
        else:
            revenue=units*asp;gross=units*(asp-cost)
            # Independent engineer/head-cost entrance through year 20; mature cost elasticity follows revenue.
            rd=head*comp+nonlabor if y<=20 else rows[-1]['rd_unshocked']*(revenue/prior)
            sga=revenue*(.087-.0003*min(y-1,15))
        rd0=rd;shock=1.;gp_cut=0.;extra_rd=0.
        if scenario=='cycle':
            shock={1:.78,2:.84,3:.94}.get(y,1.);gp_cut={1:.035,2:.025,3:.01}.get(y,0.)
        if scenario=='structural':
            shock=max(.60,.85-.015*(y-1)) if y<=18 else .60;gp_cut=.07;extra_rd=.015
        if scenario=='upside':shock=1.08 if y<=5 else 1.12;gp_cut=-.015
        if scenario=='supplier':shock=.72 if y<=2 else (.92 if y<=5 else 1.);gp_cut=.08 if y<=2 else .02
        rev=revenue*shock
        # Fixed R&D retained in cyclic weakness, no instant layoff cost benefit.
        gp=gross*shock-rev*gp_cut
        rd+=rev*extra_rd
        imp=rev*(.03-.0005*min(y-1,10))
        if scenario=='cycle' and y<=2:imp+=rev*.02
        if scenario=='structural':imp+=rev*.015
        taxadd=rev*.0025
        ebit=gp-rd-sga*max(.85,shock)-imp-taxadd
        if scenario=='parent_loss' and y<=3:ebit-=900
        if scenario=='funding_failure' and y<=4:ebit-=1800
        rows.append(dict(year=y,revenue=rev,signal_revenue=sig if method=='products' else None,
          power_revenue=power if method=='products' else None,units_m=units if method=='units' else None,
          asp=asp if method=='units' else None,unit_cost=cost if method=='units' else None,
          engineer_count=head if method=='units' else None,gross_profit=gp,rd=rd,rd_unshocked=rd0,sga=sga*max(.85,shock),
          inventory_loss=imp,ebit=ebit,acq_revenue=acqrev,acq_ebit=acqrev*(.105+.002*min(y-1,8)),
          growth=rev/prior-1))
        prior=revenue
    return rows

def entity(name,cash,re,rs,cap,own,cost,loan=0,allowance=0,loss=0):
    return dict(name=name,cash=cash,re=re,reserve=rs,capital=cap,ownership=own,parent_cost=cost,
                loan_face=loan,loan_allowance=allowance,tax_loss=loss,nwc=0.,fixed=0.,nci_equity=0.,parent_tax_cost=cost)

def run(method='products',scenario='base',years=480,rate=.095,override=None):
    o=override or {}; ops=operating(method,years,scenario)
    E=[entity('parent',4615.72682727,3300.,291.43073790,687.150701,1,0),
       entity('HK',260.,520.,0,.01023029,1,76.65387057),
       entity('wholly_owned_RD_budget',140.,-550.,0,450.,1,718.47613954,107.92176369,.714,600.),
       entity('Hangzhou_Shenan',35.,-120.,0,16.,.56,20.,0,0,170.),
       entity('Ganrui_Microtrans',45.,-100.,0,3.3217,.6899,164.1422,36.42563014,5.92314,160.),
       entity('Shanghai_Yicun',20.,-60.,0,5.697427,.7754,96.96472505,0,0,146.36815933),
       entity('Shanghai_Pingsheng',0.,-199.91436872,0,2.45,1,16.41436872,183.5,183.5,183.5),
       entity('Shanghai_Shenxiling',0.,0.,0,60.,.582878,0)]
    p=E[0];p['cash']*=o.get('parent_cash_factor',1.)
    if scenario=='low_cash':p['cash']=80.
    if scenario=='funding_failure':p['cash']=10.
    p['re']=o.get('parent_RE',p['re'])
    if scenario=='parent_loss':p['re']=-2000.
    if scenario=='sub_loss':
        for e in E[1:]:e['re']-=400.
    capex_due=o.get('opening_capex_due',29.32911473);invest_due=o.get('opening_invest_due',5.1);prior_div_due=o.get('opening_prior_dividend',0.)
    long_wages=o.get('opening_long_wages',19.02141520)
    # Q3 line-by-line bridge: capex/acquisition/dividend liabilities excluded here and paid once separately.
    nwc0=1658.09247641+(63.06481458-55.)+203.40065236-339.84104963-9.94701088-(51.80404454-capex_due-invest_due-prior_div_due)-99.25284285
    fix0=718.18692860+31.42730207+92.25349313+185.74221299;weights=[.78,.08,.10,.01,.02,.01,0,0]
    for e,w in zip(E,weights):e['nwc']=nwc0*w;e['fixed']=fix0*w
    for e in E:
        e['tax_loss']*=o.get('tax_loss_factor',1.)
        e['tax_lots']=[[k,e['tax_loss']/10.] for k in range(1,11)] if e['tax_loss'] else []
    nci0=42.81209153
    for e,f in zip(E[3:6],[.40,.35,.25]):e['nci_equity']=nci0*f
    bank=2363.93303207;bankbasis=o.get('bank_basis',2330.);deposit=223.07850384+o.get('long_deposit',236.18379665)
    depositbasis=deposit-7.;restricted=49.06543743;p['cash']-=restricted
    associate=579.18809142;associate_basis=o.get('associate_basis',450.)
    venture=235.98568520;venture_basis=o.get('venture_basis',180.)
    newfund=0.;newfundbasis=0.;strategic=0.;strategicbasis=0.
    debt=401.11369774+88.41599142+11.59092013;acqdebt=0.
    deferred_face=203.62101497;deferred_book=191.93659398
    contracts,payment_schedule=deferred_contracts(o.get('deferred_delay',0));deferred_basis=191.93659398;deferred_interest_total=0.
    ganrui_weight=124.14825204/(124.14825204+19.93475373)
    settlement_fraction=0.;purchase_fraction=0.;put_parent=o.get('put_parent_settlement',False)
    shares=687.150701+o.get('postperiod_extra_shares',0.);p['capital']+=o.get('postperiod_extra_shares',0.);treasury=0.;option_remaining=24.993541
    ipo_total=5224.38*.8686;ipo_remaining=ipo_total;ipo_used=0.
    acq_done=False;external_support=0.;failed=None;rows=[];totalpv=0.;dps=[];pv5=0.;prev_rev=5401.74317963
    nci_paid_total=0.;new_capital_total=0.;legacy_nci=0.
    for op in ops:
        y=op['year'];opening=copy.deepcopy(E);openingcash=sum(e['cash'] for e in E)
        balance_before=dict(bank=bank,deposit=deposit,restricted=restricted,associate=associate,venture=venture,
             newfund=newfund,strategic=strategic,debt=debt,acqdebt=acqdebt,deferred_face=deferred_face,deferred_book=deferred_book,shares=shares,
             options=option_remaining,ipo_remaining=ipo_remaining,deferred_basis=deferred_basis,long_wages=long_wages,capex_due=capex_due,invest_due=invest_due,prior_div_due=prior_div_due)
        balance_before['deferred_contracts']=[{k:c[k] for k in ['id','original_face','initial_book','face','book','basis','interest_total','eir']} for c in contracts]
        flows=[dict(op_profit=0.,tax=0.,net_income=0.,reserve_add=0.,reinvest=0.,interest=0.,financial_profit=0.,
           declared=0.,received=0.,dividend=0.,nci_paid=0.,loan_new=0.,loan_repaid=0.,support=0.,capital_purchase=0.,deferred_interest=0.,nci_income=0.,nci_acquired=0.) for e in E]
        # Non-operating proceeds and income separate. Initial cash already includes IPO and past receipts.
        fincash=0.;finprofit=0.;fintax=0.;acqin=0.;purchase=0.;fundcalls=0.;fundfees=0.;debtin=0.;debtout=0.;deferpay=0.;exercise_cash=0.
        portfolio=[]
        cash_yield=max(0,p['cash'])*.015*(1-.15)
        fincash+=cash_yield;finprofit+=cash_yield
        by=bank*.016;bank+=by;finprofit+=by
        if y==1:
            tax=max(0,bank-bankbasis)*.15;fincash+=bank-tax;fintax+=tax
            # Existing unrealized gain is already in opening retained earnings. Only tax and new yield affect current profit.
            portfolio.append(dict(asset='bank',proceeds=bank,basis=bankbasis,tax=tax,recognized_new_profit=by-tax))
            bank=0.;bankbasis=0.
        dy=deposit*.018;deposit+=dy;finprofit+=dy
        if y in (1,2,3):
            part=deposit/(4-y);basispart=depositbasis/(4-y);tax=max(0,part-basispart)*.15
            fincash+=part-tax;fintax+=tax;deposit-=part;depositbasis-=basispart
            portfolio.append(dict(asset='deposit',proceeds=part,basis=basispart,tax=tax))
        ry=restricted*.015;restricted+=ry;finprofit+=ry
        if y<=3:
            rel=restricted/(4-y);fincash+=rel;restricted-=rel
        # Associates: only cash dividend included, held economic asset continues until documented-budget exit.
        ay=associate*.035;fincash+=ay;finprofit+=ay
        if y==o.get('investment_exit_year',10):
            proceeds=associate*o.get('exit_multiple',1.15);fee=proceeds*.01;tax=max(0,proceeds-fee-associate_basis)*.15
            fincash+=proceeds-fee-tax;finprofit+=proceeds-fee-associate-tax
            portfolio.append(dict(asset='associate',proceeds=proceeds,fee=fee,basis=associate_basis,tax=tax,book=associate))
            associate=0.;associate_basis=0.
        if y==o.get('investment_exit_year',10):
            proceeds=venture*o.get('exit_multiple',1.15);fee=proceeds*.02;tax=max(0,proceeds-fee-venture_basis)*.15
            fincash+=proceeds-fee-tax;finprofit+=proceeds-fee-venture-tax
            portfolio.append(dict(asset='venture',proceeds=proceeds,fee=fee,basis=venture_basis,tax=tax,book=venture))
            venture=0.;venture_basis=0.
        if y<=2 and scenario!='fund_cancelled':fundcalls=100.;newfund+=100.;newfundbasis+=100.
        if newfund:
            fundfees=4. if y<=5 else newfundbasis*.02
            newfund=max(0,newfund-fundfees)
        if y==o.get('fund_exit_year',9):
            proceeds=newfund*o.get('fund_multiple',1.35);fee=proceeds*.02;tax=max(0,proceeds-fee-newfundbasis)*.15
            fincash+=proceeds-fee-tax;finprofit+=proceeds-fee-newfund-tax
            portfolio.append(dict(asset='newfund',proceeds=proceeds,fee=fee,basis=newfundbasis,tax=tax,book=newfund))
            newfund=0.;newfundbasis=0.
        # Remaining IPO strategic budget after announced acquisition: invest in identifiable financial assets, not free magic spend.
        strategic_call=100. if y in (2,3,4) else 0.
        strategic+=strategic_call;strategicbasis+=strategic_call
        if y==12:
            proceeds=strategic*1.1;tax=max(0,proceeds-strategicbasis)*.15;fincash+=proceeds-tax
            finprofit+=proceeds-strategic-tax;portfolio.append(dict(asset='strategic',proceeds=proceeds,basis=strategicbasis,tax=tax))
            strategic=0.;strategicbasis=0.
        p['cash']+=fincash-fundcalls-strategic_call
        # Fund fee reduces NAV and reported investment income, not a second cash expense at parent.
        finprofit-=fundfees+fintax
        # Signed transaction is a forward budget, not falsely reported as completed on cutoff.
        if y==1 and scenario!='deal_cancelled':
            purchase=832.698626
            debtin=0. if scenario in ('no_acq_loan','funding_failure') else 582.889038
            acqdebt+=debtin;p['cash']+=debtin-purchase;E[7]['parent_cost']+=purchase
            # Target cash/net assets not separately disclosed; budget 60 cash, 240 working/fixed capital, residual other assets.
            E[7]['cash']=o.get('target_cash',60.);acqin=E[7]['cash'];E[7]['nwc']=190.;E[7]['fixed']=50.
            E[7]['re']=o.get('target_RE',100.);E[7]['reserve']=10.;E[7]['nci_equity']=347.8944*(1-.582878)
            acq_done=True;E[7]['parent_tax_cost']+=purchase
        # Two legal rights, two amortized-cost schedules; contractual cash is never
        # allocated by book weights. No extra cash interest beyond the nominal face.
        opening_fraction=settlement_fraction
        contract_rows=[]
        for j,c in enumerate(contracts):
            opening_face,opening_book,opening_basis=c['face'],c['book'],c['basis']
            cash=c['schedule'].get(y,0.)
            charge=opening_book*c['eir'] if y<=max(payment_schedule) else 0.
            cost=cash/(1+c['eir'])**y if cash else 0.
            c['face']-=cash;c['book']+=charge-cash;c['basis']-=cost;c['interest_total']+=charge
            if y==max(payment_schedule):
                assert max(abs(c[k]) for k in ['face','book','basis'])<1e-8
                c['face']=c['book']=c['basis']=0. # proven floating point normalization only
            payer=0 if j==0 or put_parent else 3
            E[payer]['cash']-=cash;flows[payer]['deferred_interest']+=charge
            contract_rows.append(dict(id=c['id'],original_face=c['original_face'],initial_book=c['initial_book'],payer=E[payer]['name'],
                opening_face=opening_face,opening_book=opening_book,opening_basis=opening_basis,
                cash_paid=cash,interest=charge,principal_cost=cost,financing_cash=cash-cost,
                closing_face=c['face'],closing_book=c['book'],closing_basis=c['basis'],interest_total=c['interest_total'],eir=c['eir'],
                tax_deduction_eligible=bool(o.get('deferred_tax_deductible',0.)),payer_budget_tax_rate=.12 if y<=5 else .15))
        parent_part,put_part=[r['cash_paid'] for r in contract_rows]
        deferpay=parent_part+put_part;accretion=sum(r['interest'] for r in contract_rows)
        principal_cost=sum(r['principal_cost'] for r in contract_rows);finance_paid=deferpay-principal_cost
        opening_book_total=sum(r['opening_book'] for r in contract_rows)
        eir=accretion/opening_book_total if opening_book_total else 0. # weighted current-year budget rate only
        deferred_face=sum(c['face'] for c in contracts);deferred_book=sum(c['book'] for c in contracts)
        deferred_basis=sum(c['basis'] for c in contracts);deferred_interest_total=sum(c['interest_total'] for c in contracts)
        parent_acc=flows[0]['deferred_interest'];put_acc=flows[3]['deferred_interest']
        purchase_fraction=1-contracts[0]['face']/153.62101497
        settlement_fraction=1-contracts[1]['face']/50.
        for i,w in [(4,ganrui_weight),(5,1-ganrui_weight)]:
            add=contract_rows[0]['principal_cost']*w
            E[i]['parent_cost']+=add;E[i]['parent_tax_cost']+=add;flows[i]['capital_purchase']=add
        if put_parent:
            add=contract_rows[1]['principal_cost']
            E[3]['parent_cost']+=add;E[3]['parent_tax_cost']+=add;flows[3]['capital_purchase']=add
        # Opening accrued wages: cash settlement only; expense was recognized before cutoff.
        wage_pay=long_wages/(5-y) if y in (2,3,4) else 0.
        long_wages-=wage_pay;p['cash']-=wage_pay
        capex_pay=capex_due if y==1 else 0.;investment_tail=invest_due if y==1 else 0.;prior_div_pay=prior_div_due if y==1 else 0.
        p['cash']-=capex_pay+investment_tail+prior_div_pay
        capex_due-=capex_pay;invest_due-=investment_tail;prior_div_due-=prior_div_pay
        debtinterest=debt*.03+acqdebt*.033+parent_acc
        if y<=3:oldpay=debt/(4-y)
        else:oldpay=0.
        acqpay=min(acqdebt,582.889038/7.) if 2<=y<=8 else 0.
        debtout=oldpay+acqpay;debt-=oldpay;acqdebt-=acqpay;p['cash']-=debtout
        # Reported outstanding instruments retained, exercise is explicit stress budget; no hidden treasury shrink.
        newshares=0.
        if scenario=='full_exercise' and y<=4:
            newshares=24.993541/4.;exercise_cash=newshares*57.8;shares+=newshares;option_remaining-=newshares;p['cash']+=exercise_cash;p['capital']+=newshares
        elif y==4:option_remaining=0. # contractual expiry budget; no cash/RE gain
        # Ordinary-share buyback is an explicit counterexample only, cash and shares together.
        repurchase=0.;cancelled=0.
        if scenario=='buyback' and y==3:
            repurchase=120.;treasury+=3.;p['cash']-=repurchase
        if scenario=='buyback' and y==4:cancelled=treasury;shares-=treasury;p['capital']-=treasury;treasury=0.
        # Assign consolidated operating profits to economic legal-entity budgets, eliminating internal services.
        eb=op['ebit'];hk=eb*.18
        wprofit=op['revenue']*min(.009,-.008+.003*(y-1))
        sa=op['revenue']*min(.003,-.002+.001*(y-1));gr=op['revenue']*.0025;yc=op['revenue']*.002
        profit=[eb-hk-wprofit-sa-gr-yc,hk,wprofit,sa,gr,yc,0.,op['acq_ebit'] if acq_done else 0.]
        if scenario=='sub_loss' and y<=5:
            # Move real extra costs to subsidiaries, no offsetting fictitious parent profit.
            for i in (2,3,4,5):profit[i]-=60.
        for i in range(1,8):
            flows[i]['financial_profit']=max(0,E[i]['cash'])*.015
            profit[i]+=flows[i]['financial_profit']
        profit[0]+=finprofit-debtinterest
        profit[3]-=put_acc;flows[3]['interest']=put_acc
        flows[0]['financial_profit']=finprofit;flows[0]['interest']=debtinterest
        wc_ratio=o.get('wc_ratio',.25)
        if scenario=='cycle' and y<=2:wc_ratio+=.07
        if scenario in ('structural','supplier'):wc_ratio+=.06
        target_nwc=op['revenue']*wc_ratio;target_fixed=op['revenue']*(.20-.001*min(y-1,20))
        reinvest_total=0.;tax_total=0.;cashprofit_total=0.
        for i,(e,w) in enumerate(zip(E,weights)):
            if i==7 and not acq_done:continue
            f=flows[i];f['op_profit']=profit[i]-f['financial_profit']+f['interest']
            pre=profit[i];taxable=pre-(finprofit if i==0 else 0.)+f['deferred_interest']*(1-o.get('deferred_tax_deductible',0.))
            expired=sum(a for expiry,a in e['tax_lots'] if expiry<y)
            e['tax_lots']=[pair for pair in e['tax_lots'] if pair[0]>=y]
            left=max(0.,taxable);used=0.
            for pair in e['tax_lots']:
                take=min(pair[1],left);pair[1]-=take;left-=take;used+=take
            if taxable<0:e['tax_lots'].append([y+5,-taxable])
            e['tax_loss']=sum(a for expiry,a in e['tax_lots'])
            f['tax_loss_expired']=expired;f['tax_loss_used']=used
            # Future domestic R&D additional deduction/expired tax losses not presumed fully usable: budget rate 12% ->15%.
            taxrate=0. if i==1 else (.12 if y<=5 else .15)
            tax=max(0,taxable-used)*taxrate
            ni=pre-tax;f['tax']=tax;f['net_income']=ni;tax_total+=tax;cashprofit_total+=ni
            e['re'],e['reserve'],f['reserve_add']=reserve(e['re'],e['reserve'],ni,e['capital'])
            if i==7:
                nw=op['acq_revenue']*.42;fx=op['acq_revenue']*.16
            else:nw=target_nwc*w;fx=target_fixed*w
            rein=(nw-e['nwc'])+(fx-e['fixed']);f['reinvest']=rein;reinvest_total+=rein
            f['depreciation']=op['revenue']*.03*w+(op['acq_revenue']*.035 if i==7 else 0)
            f['capex']=fx-e['fixed']+f['depreciation'];f['delta_nwc']=nw-e['nwc']
            e['nwc']=nw;e['fixed']=fx
            # Parent financial cash already booked separately; current interest cash and unrealized-income exclusions.
            operatingcash=ni-rein
            operatingcash+=f['deferred_interest']
            if i==0:operatingcash-=finprofit
            e['cash']+=operatingcash
            f['operating_cash']=operatingcash
        for i,e in enumerate(E[1:],1):
            f=flows[i];inc=f['net_income']*(1-e['ownership']);f['nci_income']=inc;e['nci_equity']+=inc
        if deferpay:
            for i,initial in [(4,.6899),(5,.7754)]:
                e=E[i];old=e['ownership'];new=initial+(1-initial)*purchase_fraction
                bought=e['nci_equity']*(new-old)/(1-old) if old<1 else 0.
                e['nci_equity']-=bought;e['ownership']=new;flows[i]['nci_acquired']=bought
            e=E[3];old=e['ownership']
            if put_parent:
                new=.56+.1*settlement_fraction;bought=e['nci_equity']*(new-old)/(1-old)
            else:
                new=.56/(1-.1*settlement_fraction)
                bought=e['nci_equity']*(.1*(settlement_fraction-opening_fraction))/(.44-.1*opening_fraction)
                e['capital']=16.*(1-.1*settlement_fraction)
            e['ownership']=new;e['nci_equity']-=bought;flows[3]['nci_acquired']=bought
        # Existing share exercise receivable is principal already recognized in equity, not new income or shares.
        receivable=55. if y==1 else 0.;p['cash']+=receivable
        # Parent support is actual intercompany debt; no group cash creation. Pingsheng face survives full allowance.
        hk_received=0.;nci_paid=0.;hk_tax=0.;loan_repaid=0.;loan_new=0.;nci_income=0.
        for i,e in enumerate(E[1:],1):
            f=flows[i]
            floor=(op['acq_revenue']*.06 if i==7 and acq_done else op['revenue']*.07*weights[i])
            if i==6:floor=0.
            gap=max(0,floor-e['cash'])
            if gap:
                e['cash']+=gap;p['cash']-=gap;e['loan_face']+=gap;f['loan_new']=gap;loan_new+=gap
            available=max(0,e['cash']-floor)
            rep=min(available*.5,e['loan_face']) if i!=6 else 0.
            if scenario=='loan_delay' and y<=5:rep=0.
            if i==6 and scenario=='pingsheng_recovery' and y==5:
                # External IP/workout realization sensitivity, net of costs; not assumed in baseline.
                e['cash']+=30.;e['re']+=30.;rep=30.;f['workout_external']=30.
            if rep:
                e['cash']-=rep;p['cash']+=rep;e['loan_face']-=rep
                recovered=min(rep,e['loan_allowance']);e['loan_allowance']-=recovered
                p['re']+=recovered;f['allowance_reversal_parent']=recovered
                f['loan_repaid']=rep;loan_repaid+=rep
            available=max(0,e['cash']-floor)
            d=min(available,max(0,e['re']))*.65
            if scenario=='upstream_delay' and y<=5:d=0.
            if i==6:d=0.
            e['cash']-=d;e['re']-=d;f['dividend']=d
            owned=d*e['ownership'];nci=d-owned
            remtax=owned*.15 if i==1 else 0.
            p['cash']+=owned-remtax
            # Declaration and same-year receipt budget shown separately; not two P&L gains.
            p['re'],p['reserve'],radd=reserve(p['re'],p['reserve'],owned-remtax,p['capital'])
            flows[0]['reserve_add']+=radd;flows[0]['declared']+=owned;flows[0]['received']+=owned-remtax
            f['nci_paid']=nci;f['upstream_tax']=remtax;hk_tax+=remtax;nci_paid+=nci
            nci_inc=f['nci_income'];nci_income+=nci_inc;e['nci_equity']-=nci
        # IPO source tags: total R&D/SG&A is already in P&L and cash, so tags are never a second expense.
        earmark_rd=min(op['rd'],ipo_total*.60/5.) if y<=5 else 0.
        earmark_sg=min(op['sga'],ipo_total*.06/5.) if y<=5 else 0.
        earmark_wc=min(max(0,reinvest_total),ipo_total*.08/5.) if y<=5 else 0.
        tagged=min(ipo_remaining,earmark_rd+earmark_sg+earmark_wc+purchase+strategic_call)
        ipo_remaining-=tagged;ipo_used+=tagged
        # Payment decision respects both cash and retained earnings after losses/reserve.
        parent_floor=op['revenue']*.07*.78+ipo_remaining
        if p['cash']<0:
            failed=dict(year=y,shortfall=-p['cash'],reason='No authorized incremental funding; future distributions and value invalid')
            rows.append(dict(year=y,operating=op,opening=opening,opening_financial=balance_before,entities=copy.deepcopy(E),flows=flows,failed=failed,
              financial=dict(bank=bank,bank_basis=bankbasis,deposit=deposit,deposit_basis=depositbasis,restricted=restricted,
                associate=associate,associate_basis=associate_basis,venture=venture,venture_basis=venture_basis,
                newfund=newfund,newfund_basis=newfundbasis,strategic=strategic,strategic_basis=strategicbasis,
                debt=debt,acqdebt=acqdebt,deferred_face=deferred_face,deferred_book=deferred_book,deferred_basis=deferred_basis,deferred_eir=eir,deferred_interest_total=deferred_interest_total,deferred_parent_face=contracts[0]['face']+(contracts[1]['face'] if put_parent else 0.),deferred_put_face=0. if put_parent else contracts[1]['face'],deferred_contracts=copy.deepcopy(contract_rows),
                deferred_parent_book=contracts[0]['book']+(contracts[1]['book'] if put_parent else 0.),deferred_put_book=0. if put_parent else contracts[1]['book'],
                long_wages=long_wages,capex_due=capex_due,invest_due=invest_due,prior_div_due=prior_div_due,shares=shares,treasury=treasury,
                options=option_remaining,ipo_remaining=ipo_remaining,ipo_used=ipo_used,
                parent_investment_cost=sum(e['parent_cost'] for e in E[1:]),internal_face=sum(e['loan_face'] for e in E[1:]),internal_allowance=sum(e['loan_allowance'] for e in E[1:])),
              capital_flows=dict(acquisition=purchase,target_cash=acqin,new_debt=debtin,debt_repaid=debtout,deferred_paid=deferpay,deferred_interest=accretion,deferred_principal_cost=principal_cost,deferred_finance_paid=finance_paid,
                parent_deferred_paid=parent_part+(put_part if put_parent else 0.),subsidiary_put_paid=0. if put_parent else put_part,
                opening_wages_paid=wage_pay,opening_capex_paid=capex_pay,opening_investment_tail_paid=investment_tail,prior_dividend_paid=prior_div_pay,
                exercise_cash=exercise_cash,new_shares=newshares,buyback_cash=repurchase,cancelled=cancelled,receivable_principal=receivable,
                fund_call=fundcalls,strategic_call=strategic_call,fund_NAV_fee=fundfees,financial_cash=fincash,financial_profit=finprofit,portfolio=portfolio),
              group=dict(cash=sum(e['cash'] for e in E),operating_income=sum(f['op_profit'] for f in flows),tax=tax_total,upstream_tax=hk_tax,
                reinvest=reinvest_total,nci_income=nci_income,nci_paid=nci_paid,internal_repaid=loan_repaid,internal_new=loan_new),
              holder=dict(distribution=0.,dps=0.,shares=shares-treasury,pv=None,cumulative_pv=None,parent_cash_floor=parent_floor,legal_budget_capacity=0.)))
            break
        payout=.20+.025*min(y-1,4) if y<=5 else min(1.,.30+.07*(y-5))
        common_income=max(0,flows[0]['net_income']+flows[0]['declared']-hk_tax)
        # For first five years cash dividend based on earnings and known 2025 actual dividend (~22.7% NP).
        desired=common_income*payout if y<=5 else max(0,p['cash']-parent_floor)*payout
        if scenario=='slow_distribution' and y>5:desired*=.45
        available=min(max(0,p['cash']-parent_floor),max(0,p['re']))
        distribution=min(desired,available);p['cash']-=distribution;p['re']-=distribution
        outstanding=shares-treasury
        dd=distribution/outstanding;dps.append(dd);pv=dd/(1+rate)**y;totalpv+=pv
        if y<=5:pv5+=pv
        nci_paid_total+=nci_paid
        endcash=sum(e['cash'] for e in E)
        workout=30. if scenario=='pingsheng_recovery' and y==5 else 0.
        # Complete cash conservation includes target cash only on entry; transfers cancel.
        expected=openingcash+fincash-fundcalls-strategic_call+debtin-purchase+acqin-deferpay-wage_pay-capex_pay-investment_tail-prior_div_pay-debtout+exercise_cash-repurchase+sum(f.get('operating_cash',0) for f in flows)+receivable-hk_tax-nci_paid-distribution+workout
        residual=endcash-expected
        assert abs(residual)<1e-6*max(1,abs(expected)),(y,residual)
        assert all(e['cash']>=-1e-7 for e in E),(y,'negative entity cash')
        assert distribution<=available+1e-7
        assert min(debt,acqdebt,deferred_face,bank,deposit,restricted)>=-1e-6
        state=dict(bank=bank,bank_basis=bankbasis,deposit=deposit,deposit_basis=depositbasis,restricted=restricted,
          associate=associate,associate_basis=associate_basis,venture=venture,venture_basis=venture_basis,newfund=newfund,newfund_basis=newfundbasis,
          strategic=strategic,strategic_basis=strategicbasis,debt=debt,acqdebt=acqdebt,deferred_face=deferred_face,deferred_book=deferred_book,
          deferred_basis=deferred_basis,deferred_eir=eir,deferred_interest_total=deferred_interest_total,deferred_parent_face=contracts[0]['face']+(contracts[1]['face'] if put_parent else 0.),deferred_put_face=0. if put_parent else contracts[1]['face'],deferred_contracts=copy.deepcopy(contract_rows),
          deferred_parent_book=contracts[0]['book']+(contracts[1]['book'] if put_parent else 0.),deferred_put_book=0. if put_parent else contracts[1]['book'],
          long_wages=long_wages,capex_due=capex_due,invest_due=invest_due,prior_div_due=prior_div_due,shares=shares,treasury=treasury,options=option_remaining,ipo_remaining=ipo_remaining,ipo_used=ipo_used,
          parent_investment_cost=sum(e['parent_cost'] for e in E[1:]),internal_face=sum(e['loan_face'] for e in E[1:]),internal_allowance=sum(e['loan_allowance'] for e in E[1:]))
        rows.append(dict(year=y,operating=op,opening=opening,opening_financial=balance_before,flows=flows,entities=copy.deepcopy(E),financial=state,
            capital_flows=dict(acquisition=purchase,target_cash=acqin,new_debt=debtin,debt_repaid=debtout,deferred_paid=deferpay,deferred_interest=accretion,deferred_principal_cost=principal_cost,deferred_finance_paid=finance_paid,
                parent_deferred_paid=parent_part+(put_part if put_parent else 0.),subsidiary_put_paid=0. if put_parent else put_part,
                opening_wages_paid=wage_pay,opening_capex_paid=capex_pay,opening_investment_tail_paid=investment_tail,prior_dividend_paid=prior_div_pay,
              exercise_cash=exercise_cash,new_shares=newshares,buyback_cash=repurchase,cancelled=cancelled,receivable_principal=receivable,
              fund_call=fundcalls,strategic_call=strategic_call,fund_NAV_fee=fundfees,financial_cash=fincash,financial_profit=finprofit,portfolio=portfolio),
            group=dict(cash=endcash,operating_income=sum(f['op_profit'] for f in flows),tax=tax_total,upstream_tax=hk_tax,reinvest=reinvest_total,
                cash_identity_residual=residual,nci_income=nci_income,nci_paid=nci_paid,internal_repaid=loan_repaid,internal_new=loan_new),
            holder=dict(distribution=distribution,dps=dd,shares=outstanding,pv=pv,cumulative_pv=totalpv,parent_cash_floor=parent_floor,legal_budget_capacity=available)))
        prev_rev=op['revenue']
    if failed:return dict(method=method,scenario=scenario,rate=rate,years=years,feasible=False,failure=failed,value=None,terminal_year5=None,rows=rows)
    tail5=(totalpv-pv5)*(1+rate)**5
    return dict(method=method,scenario=scenario,rate=rate,years=years,feasible=True,value=totalpv,terminal_year5=tail5,
        first5=dps[:5],tail_PV_share=(totalpv-pv5)/totalpv,rows=rows,
        end=dict(cash=sum(e['cash'] for e in E),RE_parent=p['re'],nominal_internal_face=sum(e['loan_face'] for e in E),
          nominal_nci=sum(e['nci_equity'] for e in E),last_dps=dps[-1],last_PV=dps[-1]/(1+rate)**years,
          undistributed_cash_PV=sum(e['cash'] for e in E)/shares/(1+rate)**years))

def main():
    out={'asof':ASOF,'units':'CNY million and million shares; dps CNY','legal_status':'economic budget, not certification','models':[]}
    for method,scenario,r,ov in [
      ('products','base',.095,{}),('products','base',.10,{}),('products','base',.09,{}),('units','base',.095,{}),
      ('products','cycle',.095,{}),('products','structural',.10,{}),('products','upside',.09,{}),
      ('products','supplier',.10,{}),('products','no_acq_loan',.095,{}),('products','deal_cancelled',.095,{}),
      ('products','fund_cancelled',.095,{}),('products','low_cash',.095,{}),('products','funding_failure',.095,{}),('products','parent_loss',.095,{}),
      ('products','sub_loss',.095,{}),('products','upstream_delay',.095,{}),('products','loan_delay',.095,{}),
      ('products','pingsheng_recovery',.095,{}),('products','full_exercise',.095,{}),('products','buyback',.095,{}),
      ('products','slow_distribution',.095,{}),('products','base',.095,{'wc_ratio':.32}),
      ('products','base',.095,{'associate_basis':200.,'venture_basis':100.,'bank_basis':2260.}),
      ('products','base',.095,{'investment_exit_year':18,'fund_exit_year':13,'exit_multiple':.65,'fund_multiple':.7}),
      ('products','base',.095,{'target_RE':-200.,'target_cash':10.}),
      ('products','base',.095,{'long_deposit':0.}),('products','base',.095,{'parent_RE':100.}),('products','base',.095,{'tax_loss_factor':0.}),('products','base',.095,{'postperiod_extra_shares':.8}),
      ('products','base',.095,{'deferred_tax_deductible':1.}),('products','base',.095,{'put_parent_settlement':True}),
      ('products','base',.095,{'deferred_delay':1}),('products','base',.095,{'opening_capex_due':0.,'opening_invest_due':0.}),
      ('products','base',.095,{'opening_prior_dividend':6.29266440}),('products','base',.095,{'opening_long_wages':38.04283040}),
      ('products','base',.095,{'put_parent_settlement':True,'deferred_delay':1}),
      ('products','base',.095,{'put_parent_settlement':True,'deferred_tax_deductible':1.})]:
        z=run(method,scenario,480,r,ov);z['overrides']=ov;out['models'].append(z)
    # Actual extended paths, all states retained; no geometric-terminal plug.
    out['convergence']=[run('products','base',n,.095) for n in (240,960)]
    json.dump(out,sys.stdout,ensure_ascii=False,separators=(',',':'),sort_keys=True,allow_nan=False);sys.stdout.write('\n')
if __name__=='__main__':main()

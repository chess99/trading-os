"""CN:300693, 2026-Q3. Stdlib-only, CNY million except shares (million) and CNY/share.
Annual years are rolling budgets after 2026-10-26. Long continuation is quadrature,
not a forecast of named distant years. No market price, IRR or trading threshold.
"""
import copy,json,math,gzip,base64,hashlib,sys
from pathlib import Path
P={
 'registration_delay_years':0, 'support_registered_fraction':1., # forecast cash/debt contribution versus legally effective registered face
 'parent_voluntary_reserve_until':15, # existing business/capital-allocation fade ends at15; reassess to optional stop thereafter
 'parent_voluntary_reserve_continues':True, # FY25 actual continued despite already above half; governance forecast, not statutory mandate
 'revenue0':[1050.,1040.,1670.,270.,90.],
 'growth5':[[.22,.20,.12,.06,.05],[.18,.17,.10,.06,.04],[.15,.14,.09,.05,.04],[.12,.12,.08,.05,.03],[.10,.10,.07,.04,.03]],
 'gross5':[[.59,.34,.30,.31,.30],[.58,.335,.295,.31,.30],[.57,.33,.29,.31,.30],[.56,.325,.285,.31,.30],[.55,.32,.28,.31,.30]],
 'gross_mature':[.50,.27,.25,.28,.28], 'opex5':[.245,.241,.238,.235,.232], 'opex_mature':.225,
 'tax':.15, 'legacy_tax':False,'entity_tax_rates':[.15,.25,.25,.25,.25,.25,.25],
 'foreign_cash_budget':51.91445336,'foreign_release_year':3,'foreign_effective_tax_budget':.25,'foreign_transfer_friction':.01,
 'finite_sub_capital_from':20,'finite_sub_capital_fee':.01,'finite_sub_capital_annual_cap':10.,
 'investment_book0':[22.0744,0.,0.,0.,0.,0.,0.], 'investment_tax_basis_budget':[20.26747658,0.,0.,0.,0.,0.,0.],
 'investment_dtl0':[.27103851,0.,0.,0.,0.,0.,0.], 'investment_realize_year':10,'investment_recovery':.8,'investment_fee':.03,
 'mother_preferential_until':None,'tax_loss_years':5,'opening_tax_losses':[0.]*7,
 'tax_note':'H126p112 mother15%, six domestic subsidiaries default25% absent disclosed special qualification. Mother ongoing renewal is forecast, failure atY1/Y4/Y10 tested. No cross-entity tax losses; only model-generated own taxable losses roll for5years, no assumed opening tax asset. SBC not deducted for cash tax.','wc_ratio':.14,'wc0':400.,'fixed0':820.,'depreciation_ratio':.025,'capex_ratio':.035,
 'committed_capex':[80.,40.,0.,0.,0.], 'long_g':.02,'fade_end':15,'capital_allocation_fade_end':15,
 'cash0':[422.50624451,25.,20.,15.,10.,10.,12.], 'excluded_minor_cash':0.,
 'term0':[610.,0.,0.,0.,0.,28.88201449,0.], 'maturity_year':3,
 'debt0':[100.06944556,0.,0.,0.,0.,0.,0.], 'lease0':12.34619662,
 'legal0':[1600.,3.,-21.6641,-23.2001,-1.2582,0.,-36.],
 'reserve0':[210.59477448,.5,0.,0.,0.,0.,0.], 'capital0':[312.795823,5.,180.,50.,5.,60.,50.],
 'loan0':[142.00445104,158.00074483,0.,31.83073359,111.,0.],
 'cash_floor_weights':[.72,.05,.06,.045,.025,.075,.025], 'cash_floor_ratio':.10,
 'reinvest_weights':[.60,.05,.10,.08,.02,.14,.01],
 'subs_profit5':[[.005,-.003,-.025,.015,-.010,-.002],[.008,.002,-.012,.018,-.005,0.],[.012,.010,0.,.020,.005,.003],[.016,.018,.020,.023,.020,.006],[.020,.025,.040,.025,.030,.010]],
 'subs_profit_mature':[.02,.025,.04,.025,.03,.01], 'ownership':[1.,1.,1.,1.,1.,1.,.5],
 'deposit_yield':.018,'debt_rate':.04,'loan_rate':.03,'loan_limit_additional':500.,'external_limit':320.,'equity_support_limit':250.,
 'payout5':.45,'special_start':3,
 'new_shares':[.84864,.84864,1.13152,0.,0.], 'initial_shares':312.042673, 'sbc_path':[25.,14.,5.76330317,0.,0.], 'conversion_year':0,'conversion_limit':0.,'grant_price':31.06,
 'book0':2290.14471334,'discount_low':.11,'discount_high':.10,
 'margin_shock':0.,'shock_start':1,'cash_parent_shift':0.,'maturity_haircut':0.,
 'name':'base','notes':'经营路径相同；核心两端只变股权成本。研究预算，不是公司承诺。'
}
NAMES=['深圳市盛弘电气股份有限公司','惠州盛弘电气有限公司','苏州盛弘技术有限公司','深圳市盛弘新能源设备有限公司','西安盛弘电气有限公司','陕西盛弘电气有限公司','深圳市盛弘艾苏娜能源科技有限公司']

def tax_rates(p,year):
    rates=p.get('entity_tax_rates',[p['tax']]*7)[:]
    until=p.get('mother_preferential_until')
    if until is not None and year>until:rates[0]=.25
    return rates

def tax_at_base(base,rate,available_loss=0.):
    return max(0.,base-max(available_loss,0.))*rate

def entity_tax_bridge(pre_cash_operating,sbc,cash,term,debt,loan,p,year,loss_buckets):
    rates=tax_rates(p,year);n=7
    opening_losses=[];updated=[];tax_used=[];new_loss=[]
    op=[];fin=[];external=[];taxes=[];pre_bases=[];op_tax=[];deposit_tax=[];external_shield=[]
    iparent=0.;ishield=[0.]*6
    interest=[v*p['loan_rate'] for v in loan]
    for i in range(n):
        # Tax ledger is distinct from statutory retained profits / accounting losses.
        buckets=[list(z) for z in loss_buckets[i] if z[0]>=year]
        loss=sum(z[1] for z in buckets);opening_losses.append(loss)
        operating=pre_cash_operating[i]
        dep=(cash[i]+term[i])*p['deposit_yield'];ext=debt[i]*p['debt_rate']
        own=operating+dep-ext
        inter=sum(interest) if i==0 else -interest[i-1]
        base=own+inter;rate=rates[i]
        t0=tax_at_base(operating,rate,loss);t1=tax_at_base(operating+dep,rate,loss);t2=tax_at_base(own,rate,loss);t3=tax_at_base(base,rate,loss)
        op.append(operating-t0-(sbc if i==0 else 0.));fin.append(dep-(t1-t0));external.append(ext-(t1-t2))
        op_tax.append(t0);deposit_tax.append(t1-t0);external_shield.append(t1-t2)
        if i==0:iparent=t3-t2
        else:ishield[i-1]=t2-t3
        taxes.append(t3);pre_bases.append(base)
        used=min(max(base,0.),loss);tax_used.append(used)
        remaining=used
        for z in buckets:
            take=min(z[1],remaining);z[1]-=take;remaining-=take
        generated=max(0.,-base);new_loss.append(generated)
        if p.get('tax_loss_years',5)>0 and generated>0:buckets.append([year+p['tax_loss_years'],generated])
        updated.append([z for z in buckets if z[1]>1e-10])
    assert all(t>=-1e-10 for t in taxes)
    # Cash taxes have no negative refund; loan tax is based on each actual borrower.
    return dict(operating_profits=op,deposit_income=fin,external_interest=external,
       internal_parent_tax=iparent,internal_sub_shield=ishield,entity_tax_rates=rates,
       entity_cash_taxes=taxes,entity_cash_taxable_before_losses=pre_bases,
       entity_operating_cash_taxes=op_tax,entity_deposit_cash_taxes=deposit_tax,
       entity_external_interest_shields=external_shield,opening_tax_losses=opening_losses,
       tax_losses_used=tax_used,generated_tax_losses=new_loss,tax_loss_buckets=updated)


def annual_business(p,y,rev,wc,fixed):
    if y<=5:
        growth=p['growth5'][y-1]; gross=p['gross5'][y-1]; opex=p['opex5'][y-1]
    else:
        a=min((y-5)/(p['fade_end']-5),1.)
        growth=[v+(p['long_g']-v)*a for v in p['growth5'][-1]]
        gross=[v+(m-v)*a for v,m in zip(p['gross5'][-1],p['gross_mature'])]
        opex=p['opex5'][-1]+(p['opex_mature']-p['opex5'][-1])*a
    gross=[g+(p['margin_shock'] if y>=p['shock_start'] else 0.) for g in gross]
    newrev=[a*(1+b) for a,b in zip(rev,growth)]; sales=sum(newrev)
    gp=sum(a*b for a,b in zip(newrev,gross)); ebit_before_sbc=gp-sales*opex
    sbc=p.get('sbc_path',[0.]*5)[y-1] if y<=5 else 0.
    ebit=ebit_before_sbc-sbc
    nopat=(ebit_before_sbc*(1-p['tax']) if ebit_before_sbc>0 else ebit_before_sbc)-sbc # no cash tax credit for a loss
    if not p.get('legacy_tax',False):
        sw=p['subs_profit5'][y-1] if y<=5 else p['subs_profit_mature'];weights=[1-sum(sw)]+sw
        rates=tax_rates(p,y);nopat=sum(ebit_before_sbc*w-max(0.,ebit_before_sbc*w)*rates[i] for i,w in enumerate(weights))-sbc
    newwc=sales*p['wc_ratio']; da=sales*p['depreciation_ratio']
    # Stable growth supports the same fixed asset intensity, no unsupported capex discount.
    if y<=5: capex=sales*p['capex_ratio']+p['committed_capex'][y-1]
    else: capex=da+max(sales-sum(rev),0)*p['fixed_terminal_ratio']
    newfixed=fixed+capex-da
    return dict(revenue=newrev,sales=sales,growth=growth,gross_margins=gross,gross_profit=gp,opex=sales*opex,
       ebit_before_sbc=ebit_before_sbc,ebit=ebit,nopat=nopat,wc=newwc,delta_wc=newwc-wc,da=da,capex=capex,fixed=newfixed,
       sbc=sbc,fcf=nopat+sbc+da-capex-(newwc-wc),reinvestment=capex-da+newwc-wc)

def legal_add(balance,reserve,capital,profit,voluntary_continues=False):
    before=balance; balance+=profit
    profit_after_loss=max(balance-max(before,0.),0.)
    provision=profit_after_loss*.10 if voluntary_continues else min(profit_after_loss*.10,max(capital*.5-reserve,0.))
    return balance-provision,reserve+provision,provision

def payment(cash,legal,reserve,capital,profit,floor,target):
    """Shared actual payment gate; used by both live simulation and hand cases."""
    legal,reserve,appropriation=legal_add(legal,reserve,capital,profit)
    paid=min(max(target,0.),max(legal,0.),max(cash-floor,0.))
    return cash-paid,legal-paid,reserve,paid,appropriation

def investment_realization(p,year):
    # Listed holder's existing investment carrying share, NOT investee gross assets.
    # Q3 unidentified new11.5m uses mother-settlement economic budget, not asserted title.
    book=p.get('investment_book0',[0.]*7)
    if p.get('legacy_tax',False) or year!=p.get('investment_realize_year',10):
        return dict(cash=[0.]*7,profit=[0.]*7,tax=[0.]*7,book_released=[0.]*7,fee=[0.]*7)
    basis=p['investment_tax_basis_budget'];dtl=p['investment_dtl0'];rates=tax_rates(p,year)
    gross=[v*p['investment_recovery'] for v in book];fee=[v*p['investment_fee'] for v in gross]
    # No instantaneous refund from disposal losses or unspecified opening tax credits.
    taxes=[max(gross[i]-fee[i]-basis[i],0.)*rates[i] for i in range(7)]
    cash=[gross[i]-fee[i]-taxes[i] for i in range(7)]
    profit=[cash[i]-book[i]+dtl[i] for i in range(7)]
    return dict(cash=cash,profit=profit,tax=taxes,book_released=book[:],fee=fee)

def finite_capital_budget(cash,floor,legal,reserve,capital,profit,ownership,parent_basis,rate,annual_cap,fee_rate):
    # Pro-rata redemption at forecast net-asset price, not cash limited to par value.
    # Only surplus beyond both operating liquidity and immediately distributable profit.
    after,_,_=legal_add(legal,reserve,capital,profit)
    excess=max(cash-floor-max(after,0.),0.)
    nav=capital+reserve+legal+profit
    gross=min(excess/(1+fee_rate),max(nav,0.)*.25,annual_cap)
    if gross<.01 or nav<=0 or capital<=.01:return None
    fraction=gross/nav;face=capital*fraction;fee=gross*fee_rate
    parent=gross*ownership;basis=parent_basis*fraction
    tax=parent*rate # conservative full-receipt tax budget, not asserted statutory tax basis
    return dict(gross=gross,fraction=fraction,face=face,fee=fee,parent=parent,
       minority=gross-parent,basis=basis,mother_gain=parent-basis,tax=tax,
       sub_capital_premium_charge=gross-face,available_excess=excess,forecast_nav_before=nav)

def simulate(p,horizon=240):
    p=copy.deepcopy(p); rev=p['revenue0'][:];wc=p['wc0'];fixed=p['fixed0'];cash=p['cash0'][:]
    cash[0]-=p['cash_parent_shift']; cash[1]+=p['cash_parent_shift']
    term=p['term0'][:];debt=p['debt0'][:];legal=p['legal0'][:];reserve=p['reserve0'][:];capital=p['capital0'][:]
    loan=p['loan0'][:];pending=[0.]*6;shares=p['initial_shares'];book=p['book0'];rows=[]
    added_loans=0.;equity_support=0.;borrowed=0.;cumulative_dps=0.; p['fixed_terminal_ratio']=.20
    def move(i,j,a):
        assert a>=-1e-7
        cash[i]-=a;cash[j]+=a
    tax_loss_buckets=[([[p.get('opening_tax_loss_expiry',p['tax_loss_years']),a]] if a>0 else []) for a in p.get('opening_tax_losses',[0.]*7)]
    foreign_cash=p.get('foreign_cash_budget',0.) if not p.get('legacy_tax',False) else 0.
    parent_investment_basis={5:53.43073375,6:16.10284915};sub_units={5:1.,6:1.}
    registration_queue={}
    def register_contribution(year,i,amount,face_share=1.):
        registered_amount=amount*face_share
        due=year+p.get('registration_delay_years',0)
        if due==year:capital[i]+=registered_amount
        else:registration_queue.setdefault(due,[0.]*7)[i]+=registered_amount
    for y in range(1,horizon+1):
        for i,amount in enumerate(registration_queue.pop(y,[0.]*7)):capital[i]+=amount
        before_cash=sum(cash)+sum(term);prevbook=book;prevshares=shares;prev_legal=legal[:];prev_reserve=reserve[:]
        b=annual_business(p,y,rev,wc,fixed);rev=b['revenue'];wc=b['wc'];fixed=b['fixed'];sales=b['sales']
        if y==5: p['fixed_terminal_ratio']=fixed/sales
        foreign_tax_adjustment=foreign_transfer_cost=0.
        foreign_cash_open=foreign_cash
        if foreign_cash>0:
            if y>=p.get('foreign_release_year',3):
                foreign_transfer_cost=foreign_cash*p.get('foreign_transfer_friction',.01);foreign_cash=0.
            else:
                foreign_tax_adjustment=foreign_cash*p['deposit_yield']*(p['foreign_effective_tax_budget']-tax_rates(p,y)[0])
                foreign_cash*=1+p['deposit_yield']*(1-p['foreign_effective_tax_budget'])
        floors=[sales*p['cash_floor_ratio']*w for w in p['cash_floor_weights']]
        floors[0]+=foreign_cash # explicitly unavailable foreign economic location budget, not mother physically owned cash
        if y<=p.get('unlocated_cash_unavailable_years',0):floors[0]+=22.50624451 # availability budget, not a foreign legal reserve pool
        conversion=[0.]*6
        if y==p['conversion_year']:
            remaining=p['conversion_limit']
            for i in [5,2,3,1,4]:
                cv=min(remaining,loan[i-1]);loan[i-1]-=cv;register_contribution(y,i,cv,p.get('support_registered_fraction',1.));conversion[i-1]=cv;remaining-=cv
        sw=p['subs_profit5'][y-1] if y<=5 else p['subs_profit_mature']
        pre_cash_op=[b['ebit_before_sbc']*(1-sum(sw))]+[b['ebit_before_sbc']*w for w in sw]
        tax_detail={}
        if p.get('legacy_tax',False):
            fin=[(cash[i]+term[i])*p['deposit_yield']*(1-p['tax']) for i in range(7)]
            extint=[d*p['debt_rate']*(1-p['tax']) for d in debt]
            lp=[l*p['loan_rate'] for l in loan]
            sw=p['subs_profit5'][y-1] if y<=5 else p['subs_profit_mature']
            op_profit=[b['nopat']*(1-sum(sw))]+[b['nopat']*w for w in sw]
            profits=[op_profit[i]+fin[i]-extint[i] for i in range(7)]
            internal_parent_tax=sum(lp)*p['tax']
            internal_sub_shield=[min(lp[i-1],max(op_profit[i]+fin[i]-extint[i],0.)/(1-p['tax']))*p['tax'] if legal[i]>=0. else 0. for i in range(1,7)]
            internal_tax=internal_parent_tax-sum(internal_sub_shield)
            profits[0]+=sum(lp)-internal_parent_tax
            for i in range(1,7): profits[i]-=lp[i-1]-internal_sub_shield[i-1]
        else:
            tax_detail=entity_tax_bridge(pre_cash_op,b['sbc'],cash,term,debt,loan,p,y,tax_loss_buckets)
            tax_loss_buckets=tax_detail['tax_loss_buckets']
            op_profit=tax_detail['operating_profits'];fin=tax_detail['deposit_income'][:];extint=tax_detail['external_interest']
            fin[0]-=foreign_tax_adjustment
            lp=[l*p['loan_rate'] for l in loan]
            internal_parent_tax=tax_detail['internal_parent_tax'];internal_sub_shield=tax_detail['internal_sub_shield']
            internal_tax=internal_parent_tax-sum(internal_sub_shield)
            profits=[op_profit[i]+fin[i]-extint[i] for i in range(7)]
            profits[0]+=sum(lp)-internal_parent_tax
            for i in range(1,7):profits[i]-=lp[i-1]-internal_sub_shield[i-1]
            b['nopat']=sum(op_profit);b['fcf']=b['nopat']+b['sbc']-b['reinvestment']
        investment_event=investment_realization(p,y)
        for i in range(7):profits[i]+=investment_event['profit'][i]
        profits[0]-=foreign_transfer_cost
        # Internal interest moves actual cash; only each taxpayer's own current taxable
        # profit and separately tracked tax-loss vintages determine current tax.
        # Statutory retained losses never substitute for tax-return loss balances.
        a=min(max((y-5)/(p['capital_allocation_fade_end']-5),0.),1.)
        mature_weights=[1-sum(p['subs_profit_mature'])]+p['subs_profit_mature']
        investment_weights=[w*(1-a)+z*a for w,z in zip(p['reinvest_weights'],mature_weights)]
        for i in range(7): cash[i]+=op_profit[i]-b['reinvestment']*investment_weights[i]+fin[i]-extint[i]
        cash[0]+=b['sbc']-internal_parent_tax-foreign_transfer_cost
        for i in range(1,7):cash[i]+=internal_sub_shield[i-1]
        for i in range(7):cash[i]+=investment_event['cash'][i]
        received=pending[:]
        # Declared last year, received this year; do not book new parent legal income.
        for i in range(1,7): move(i,0,received[i-1])
        pending=[0.]*6
        matured=[0.]*7; impairment=0.
        if y==p['maturity_year']:
            for i in range(7):
                matured[i]=term[i]*(1-p['maturity_haircut']); impairment+=term[i]*p['maturity_haircut']
                profits[i]-=term[i]*p['maturity_haircut'];cash[i]+=matured[i];term[i]=0.
        # Known initial debt amortizes in Y1; any capped contingency borrowing paid in Y2/3.
        principal=[debt[i] if y in (1,3) else 0. for i in range(7)]
        lease=p['lease0'] if y==1 else 0.;cash[0]-=lease
        performance_proxy=576. if y==1 else (rows[-1]['common_profit']+rows[-1]['sbc'] if rows else 0.)
        targets=[561.62,673.94,808.73];triggers=[514.82,566.30,622.93]
        vest=(1. if performance_proxy>=targets[y-1] else .6 if performance_proxy>=triggers[y-1] else 0.) if y<=3 else 0.
        issue=p['new_shares'][y-1]*vest if y<=5 else 0.
        issue_price=max(p['grant_price']-cumulative_dps,0.)
        proceeds=issue*issue_price;shares+=issue;register_contribution(y,0,issue);cash[0]+=proceeds
        # All subsidiaries must cover operating liquidity, internal interest and due debt
        # before declaring new cash. Support is a named loan, never unidentified cash.
        support=[0.]*6;equity_injections=[0.]*6;repaid=[0.]*6;external=[0.]*7
        for i in range(1,7):
            need=max(floors[i]+principal[i]+lp[i-1]-cash[i],0.)
            # Bridge against disclosed deposits is capped, explicitly costly, and
            # remains debt until cash repayment. No unlimited credit plug.
            parent_gap=max(need+floors[0]+principal[0]-cash[0],0.)
            draw=min(parent_gap,max(p['external_limit']-borrowed,0.))
            cash[0]+=draw;debt[0]+=draw;borrowed+=draw;external[0]+=draw
            capacity=max(min(sum(p['loan0'])+p['loan_limit_additional']-sum(loan),cash[0]-floors[0]-principal[0]),0.)
            lend=min(need,capacity);move(0,i,lend);loan[i-1]+=lend;support[i-1]=lend;added_loans+=lend
            remaining=max(floors[i]+principal[i]+lp[i-1]-cash[i],0.)
            eq=min(remaining,max(p['equity_support_limit']-equity_support,0.),max(cash[0]-floors[0]-principal[0],0.)) if p['ownership'][i]==1 else 0.
            move(0,i,eq);register_contribution(y,i,eq,p.get('support_registered_fraction',1.));equity_support+=eq;equity_injections[i-1]=eq
            if cash[i]+1e-7<floors[i]+principal[i]+lp[i-1]:
                return dict(feasible=False,failure_year=y,failure_entity=NAMES[i],failure='zero-dividend funding deficit',rows=rows,inputs=p,failed_state={'cash':cash[:],'legal':legal[:],'debt':debt[:],'loans':loan[:],'capital':capital[:],'business':b},unfunded=floors[i]+principal[i]+lp[i-1]-cash[i])
            move(i,0,lp[i-1])
        for i in range(7):
            need=max(floors[i]+principal[i]-cash[i],0.)
            avail=max(p['external_limit']-borrowed,0.) if i==0 else 0.
            draw=min(need,avail);cash[i]+=draw;debt[i]+=draw;borrowed+=draw;external[i]+=draw
            if cash[i]+1e-7<floors[i]+principal[i]:
                return dict(feasible=False,failure_year=y,failure_entity=NAMES[i],failure='zero-dividend funding deficit',rows=rows,inputs=p,failed_state={'cash':cash[:],'legal':legal[:],'debt':debt[:],'loans':loan[:],'capital':capital[:],'business':b},unfunded=floors[i]+principal[i]-cash[i])
            cash[i]-=principal[i];debt[i]-=principal[i]
        # Repay pre-existing shareholder loans before distributing profits; never a new
        # parent profit. Some major balances represent operating advances; budget settlement
        # is limited by each debtor's available cash, not legal consolidation set-off.
        for i in range(1,7):
            a=min(max(cash[i]-floors[i],0.),loan[i-1]);move(i,0,a);loan[i-1]-=a;repaid[i-1]=a
        finite_capital_events=[];finite_capital_external=0.
        for i in [5,6]:parent_investment_basis[i]+=equity_injections[i-1]+conversion[i-1]
        # Zero-growth structural branch has no growth use for accumulated reserve cash.
        # Use a finite mature capital-allocation forecast; no forced business liquidation.
        if not p.get('legacy_tax',False) and p.get('finite_sub_capital_enabled',False) and y>=p.get('finite_sub_capital_from',20):
            for i in [5,6]:
                if loan[i-1]>1e-8:continue
                e=finite_capital_budget(cash[i],floors[i],legal[i],reserve[i],capital[i],profits[i],p['ownership'][i],parent_investment_basis[i],tax_rates(p,y)[0],p['finite_sub_capital_annual_cap'],p['finite_sub_capital_fee'])
                if e is None:continue
                cash[i]-=e['gross']+e['fee'];cash[0]+=e['parent']-e['tax']
                capital[i]-=e['face'];legal[i]-=e['sub_capital_premium_charge']
                profits[i]-=e['fee'];profits[0]-=e['tax']
                # Separate cost-method disposal gain only in mother standalone legal ledger.
                cont=p.get('parent_voluntary_reserve_continues',False) and (p.get('parent_voluntary_reserve_until') is None or y<=p['parent_voluntary_reserve_until'])
                legal[0],reserve[0],_=legal_add(legal[0],reserve[0],capital[0],e['mother_gain'],cont)
                parent_investment_basis[i]-=e['basis'];sub_units[i]*=1-e['fraction']
                finite_capital_external+=e['minority']+e['fee']+e['tax']
                finite_capital_events.append(dict(entity=NAMES[i],year=y,**e,units_after=sub_units[i],registered_after=capital[i],ownership_after=p['ownership'][i],parent_basis_after=parent_investment_basis[i]))
        voluntary=p.get('parent_voluntary_reserve_continues',False) and (p.get('parent_voluntary_reserve_until') is None or y<=p['parent_voluntary_reserve_until'])
        provision=[0.]*7
        for i in range(7): legal[i],reserve[i],provision[i]=legal_add(legal[i],reserve[i],capital[i],profits[i],i==0 and voluntary)
        declared=[0.]*6;minority_paid=0.
        for i in range(1,7):
            # A full-year dividend delay is an explicit budget. Reserve the declaration
            # in cash, and do not count it as parent receipt until next annual step.
            a=min(max(legal[i],0.),max(cash[i]-floors[i],0.))
            if y<=5: a*=.45
            parent_part=a*p['ownership'][i]; minority=a-parent_part
            cash[i]-=minority;minority_paid+=minority;legal[i]-=a
            declared[i-1]=parent_part;pending[i-1]=parent_part
        # Parent records declared investment income now, before receipt next year.
        legal[0],reserve[0],extra=legal_add(legal[0],reserve[0],capital[0],sum(declared),voluntary);provision[0]+=extra
        totalprofit=sum(profits);minority_profit=profits[-1]*.5
        common_profit=totalprofit-minority_profit
        ordinary_target=max(common_profit,0.)*(p['payout5'] if y<=5 else 1.)
        # Ordinary distribution consumes legal profit first. The subsequent sweep is
        # actual cash, subject to remaining statutory earnings, liquidity and debt.
        cash[0],legal[0],reserve[0],ordinary,_=payment(cash[0],legal[0],reserve[0],capital[0],0.,floors[0],ordinary_target)
        special=0.
        if y>=p['special_start']:
            # During first 5 years only matured original deposits are released; after 5
            # all genuinely redundant cash can be returned. No parallel cash add-back.
            target=sum(matured) if y<=5 else max(cash[0]-floors[0],0.)
            special=min(target,max(legal[0],0.),max(cash[0]-floors[0],0.));cash[0]-=special;legal[0]-=special
        paid=ordinary+special;dps=paid/shares;cumulative_dps+=dps
        book=prevbook+common_profit+b['sbc']+proceeds-paid
        expected=before_cash+b['fcf']+sum(fin)-sum(extint)-impairment-internal_tax+proceeds+sum(external)-sum(principal)-lease-paid-minority_paid+sum(investment_event['cash'])-finite_capital_external-foreign_transfer_cost
        error=sum(cash)+sum(term)-expected
        assert abs(error)<1e-6*max(1,sales/10000),error
        assert min(cash+term+debt+loan)>=-1e-6
        assert all(cash[i]+1e-6>=floors[i]+(pending[i-1] if i else 0.) for i in range(7))
        assert all(reserve[i]>=prev_reserve[i]-1e-8 for i in range(7))
        rows.append(dict(year=y,finite_capital_events=finite_capital_events,investment_realization=investment_event,foreign_cash_open=foreign_cash_open,foreign_cash_unavailable=foreign_cash,foreign_cash_tax_adjustment=foreign_tax_adjustment,foreign_transfer_cost=foreign_transfer_cost,entity_tax_details=tax_detail,entity_pre_tax_cash_operating=pre_cash_op,**b,common_profit=common_profit,group_profit=totalprofit,
          entity_operating_profits=op_profit,reinvestment_weights=investment_weights,entity_statutory_own_profits=profits,cash=cash[:],deposits=term[:],
          deposit_income=fin,deposit_matured=matured,debt=debt[:],external_interest=extint,
          capital=capital[:],registered_capital_end=capital[:],registration_pending=[sum(v[i] for v in registration_queue.values()) for i in range(7)],legal=legal[:],reserve=reserve[:],reserve_provision=provision,liquidity_floors=floors,
          parent_dividend_receivable=pending[:],subs_declared=declared,subs_cash_received=received,
          internal_loans=loan[:],internal_loan_interest=lp,internal_interest_parent_cash_tax=internal_parent_tax,internal_interest_sub_cash_tax_shield=internal_sub_shield,internal_support=support,internal_equity_injections=equity_injections,internal_debt_to_equity=conversion,internal_repayment=repaid,
          external_draw=external,debt_principal=principal,lease_principal=lease,minority_profit=minority_profit,
          minority_paid=minority_paid,ordinary=ordinary,special=special,distribution=paid,distribution_per_share=dps,
          shares=shares,new_shares=issue,vesting_fraction=vest,performance_proxy=performance_proxy,issue_price=issue_price,issue_proceeds=proceeds,common_book=book,
          book_per_share=book/shares,opening_book_per_share=prevbook/prevshares,cash_identity_error=error))
    return dict(feasible=True,rows=rows,inputs=p,entities=NAMES,excluded_minor_cash=p['excluded_minor_cash'],
       omitted_cash_note='合并现金514.50624451百万元完整纳入，母422.50624451/六子92为资金位置预算；原未定位残差22.50624451不再冒称少数而永久归零，十年不可用缓冲另测。',
       shareholder_support_used=added_loans,equity_support_used=equity_support,external_draw_total=borrowed)

def prepare_award_budget(p):
    p=copy.deepcopy(p)
    if sum(p['new_shares'])==0:
        p['sbc_path']=[-15.67174636,0.,0.,0.,0.]
        p['award_note']='全部失效，冲回截至Q3约15.672百万元已认费用；不是额外现金收益。'
        return p
    for _ in range(6):
        trial=simulate(p,5)
        if not trial['feasible']:return p
        vest=[a['vesting_fraction'] for a in trial['rows'][:3]]
        total=60.43504953*sum(a*b for a,b in zip([.3,.3,.4],vest))
        remaining=total-15.67174636
        shape=[25.,14.,5.76330317]
        target=[remaining*w/sum(shape) for w in shape]+[0.,0.]
        if max(abs(a-b) for a,b in zip(p['sbc_path'],target))<1e-10:break
        p['sbc_path']=target
    p['award_note']='预期归属比例决定最终股份费用总额；扣已确认部分后分摊未来费用，未达标份额不持续保留全部费用。'
    p['expected_vesting']=vest;p['expected_total_award_cost']=total
    return p

def value(run,r):
    if not run['feasible']: return None
    rows=run['rows'];dpv=sum(a['distribution_per_share']/(1+r)**a['year'] for a in rows)
    tv=sum(a['distribution_per_share']/(1+r)**(a['year']-5) for a in rows if a['year']>5)
    near=sum(a['distribution_per_share']/(1+r)**a['year'] for a in rows[:5])
    ri=run['inputs']['book0']/run['inputs']['initial_shares']
    residual_rows=[]
    for a in rows:
        residual=a['book_per_share']-a['opening_book_per_share']+a['distribution_per_share']-r*a['opening_book_per_share']
        ri+=residual/(1+r)**a['year'];residual_rows.append(residual)
    terminal_book=rows[-1]['book_per_share']/(1+r)**rows[-1]['year']
    assert abs(ri-terminal_book-dpv)<1e-8
    tail_bound=abs(rows[-1]['distribution_per_share'])*(1.02)/(r-.02)/(1+r)**rows[-1]['year']
    return dict(discount=r,per_share=dpv,year5_terminal_per_share=tv,first5_pv=near,
       terminal_pv_fraction=(dpv-near)/dpv,residual_income_value=ri,
       residual_income_per_year=residual_rows,terminal_book_pv=terminal_book,tail_upper_diagnostic=tail_bound)

def configs():
    d={'base':copy.deepcopy(P)}
    for tag,change in [('foreign_tax9',{'foreign_effective_tax_budget':.09}),('foreign_tax27_98',{'foreign_effective_tax_budget':.2798}),('foreign_release_Y1',{'foreign_release_year':1}),('foreign_release_Y5_fee3',{'foreign_release_year':5,'foreign_transfer_friction':.03})]:
        q=copy.deepcopy(P);q.update(name=tag,**change);d[tag]=q
    for tag,change in [('investments_no_realization_boundary',{'investment_recovery':0.}),('investments_Y5_par',{'investment_realize_year':5,'investment_recovery':1.}),('investments_Y15_half',{'investment_realize_year':15,'investment_recovery':.5}),('investments_Y10_120pct',{'investment_recovery':1.2})]:
        q=copy.deepcopy(P);q.update(name=tag,**change);d[tag]=q
    for until in [0,3,9]:
        q=copy.deepcopy(P);q.update(name='mother_tax25_from_Y'+str(until+1),mother_preferential_until=until);d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='no_generated_tax_loss_credit',tax_loss_years=0);d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='entity_tax_all25_boundary',entity_tax_rates=[.25]*7);d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='unlocated_cash_unavailable_10y',unlocated_cash_unavailable_years=10);d[q['name']]=q
    for until in [5,10,20,None]:
        q=copy.deepcopy(P);q.update(name='voluntary_continue_'+str(until),parent_voluntary_reserve_until=until);d[q['name']]=q
    for lag in [1,2]:
        q=copy.deepcopy(P);q.update(name='registration_delay_'+str(lag)+'y',registration_delay_years=lag);d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='support_half_registered_half_premium',support_registered_fraction=.5);d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='parent_optional_stop_at_half',parent_voluntary_reserve_continues=False);d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='cyclical_weak',notes='Y1-2库存/项目延迟，Y3开始恢复，Y5仍低于基准。',wc_ratio=.18)
    q['growth5']=[[-.05,-.15,-.08,-.12,0.],[.05,.05,.03,0.,.02],[.20,.20,.14,.08,.04],[.14,.14,.10,.06,.03],[.11,.11,.08,.05,.03]]
    q['gross5']=[[g-.03 for g in row] if j<2 else row for j,row in enumerate(q['gross5'])];q['committed_capex']=[80.,40.,0.,0.,0.];d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='structural_adverse',notes='Y1起充电/PCS永久商品化，工业接口优势减弱，无自动均值回归。',wc_ratio=.20,foreign_release_year=1,opex_mature=.235,conversion_year=3,conversion_limit=250.)
    q['growth5']=[[.08,.02,.02,-.05,.02],[.06,.02,.02,0.,.02],[.05,.02,.02,.02,.02],[.04,.02,.02,.02,.02],[.03,.02,.02,.02,.02]]
    q['gross5']=[[.51,.25,.23,.27,.28]]*5;q['gross_mature']=[.47,.23,.22,.26,.27];q['opex5']=[.245,.242,.24,.238,.235];q['capex_ratio']=.03;d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='optimistic',notes='Y1起工业/海外份额提升，仍保留资本和远期竞争衰减。',wc_ratio=.15)
    q['growth5']=[[g+.04 for g in a] for a in q['growth5']];q['gross5']=[[a[0]+.01,a[1]+.02,*a[2:]] for a in q['gross5']];q['committed_capex']=[120.,60.,20.,0.,0.];d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='margin_minus_2pp',margin_shock=-.02,shock_start=2,notes='Y2起所有分部毛利率永久减2点，其余商业假设冻结；整链诊断敏感性。');d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='wc_plus_5pp',wc_ratio=.19,notes='Y1起净营运资本占收入永久+5点；经营/资金/分配全链重算。');d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='deposit_delay',maturity_year=5,notes='原定Y3本金释放延后至Y5，期间利息和现金/法定利润继续滚动。');d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='parent_cash_shift',cash_parent_shift=100.,notes='初始母公司现金少1亿元，改放惠州；同一集团现金，资金必须通过还款或宣派到账。');d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='no_exercise',new_shares=[0.]*5,sbc_path=[0.]*5,notes='Y1起激励全部失效：无认款无新增股份，未归属费用不再承担；经营费用其他部分不变。');d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='funding_failure',wc_ratio=.75,external_limit=0.,loan_limit_additional=0.,equity_support_limit=0.,notes='Y1极端回款冻结：即使零分配仍现金不足，必须不可行且不输出价值。');d[q['name']]=q
    q=copy.deepcopy(d['structural_adverse']);q.update(name='structural_foreign_not_accelerated',foreign_release_year=3);d[q['name']]=q
    q=copy.deepcopy(d['structural_adverse']);q.update(name='structural_zero_growth',long_g=0.,finite_sub_capital_enabled=True);d[q['name']]=q
    return d

def earnings_power_crosscheck(base):
    # Economic alternative, not a different multiple applied to an unfunded tail.
    # Same end-Y5 state, then immediate 2% growth and mature segment economics.
    p=copy.deepcopy(base['inputs']);p.update(name='earnings_power_crosscheck',fade_end=6,capital_allocation_fade_end=6,
       gross_mature=[.52,.29,.26,.29,.29],opex_mature=.23,
       notes='第二法：第6年立即成熟，工业52/PCS29/充电26/检测29/其他29%毛利，2%增长；按必要再投资资本化盈利能力，法律和金融过渡用同一实际支付预算桥接。')
    run=simulate(p);assert run['feasible']
    for k in ['cash','legal','reserve','debt','shares','common_book','revenue','fixed','wc']:
        assert run['rows'][4][k]==base['rows'][4][k]
    s5,s6=run['rows'][4:6];shares=s6['shares'];ownership=p['ownership']
    capacity=sum((s6['entity_operating_profits'][i]-s6['reinvestment']*s6['reinvestment_weights'][i]
       -(s6['liquidity_floors'][i]-s5['liquidity_floors'][i])
       +s5['liquidity_floors'][i]*p['deposit_yield']*(1-(p['tax'] if p.get('legacy_tax',False) else tax_rates(p,6)[i])))*ownership[i] for i in range(7))/shares
    run['earnings_power_capacity_per_share']=capacity;run['method_results']={}
    for label,r in [('low',.11),('high',.10)]:
        operating=capacity/(r-p['long_g'])
        bridge=sum((a['distribution_per_share']-capacity*(1+p['long_g'])**(a['year']-6))/(1+r)**(a['year']-5) for a in run['rows'][5:])
        first=sum(a['distribution_per_share']/(1+r)**a['year'] for a in run['rows'][:5])
        result=first+(operating+bridge)/(1+r)**5
        direct=value(run,r)['per_share']
        assert abs(result-direct)<.00001
        run['method_results'][label]={'normalised_operating_capitalisation_at_y5':operating,
          'actual_legal_financial_bridge_at_y5':bridge,'per_share':result,'year5_terminal':operating+bridge,
          'normalised_nopat_y6':s6['nopat'],'necessary_reinvestment_y6':s6['reinvestment'],
          'liquidity_increment_y6':sum(s6['liquidity_floors'])-sum(s5['liquidity_floors']),
          'first5_pv':first,'full_budget_check':direct}
    return run

def self_tests():
    # Real payment gate: cash12, legal-3, profit10, reserve0, capital10: loss absorbed,
    # reserve .7, legal6.3; liquidity floor2, target20 => dividend6.3, cash5.7.
    assert legal_add(0.,5.,20.,10.)==(9.,6.,1.) # registered20 paid10: still appropriate1
    assert legal_add(0.,6.,10.,10.,True)==(9.,7.,1.) # eligible stop does not mean compulsory stop
    assert legal_add(0.,6.,10.,10.,False)==(10.,6.,0.)
    a=payment(12.,-3.,0.,10.,10.,2.,20.)
    assert all(abs(x-y)<1e-10 for x,y in zip(a,[5.7,0.,.7,6.3,.7]))
    # Ordinary cash consumes profits; principal cannot reuse same 6.3 statutory budget.
    b=payment(a[0]+100,a[1],a[2],10.,0.,2.,100.)
    assert b[3]==0. and b[0]==105.7
    c=payment(10.,-20.,0.,10.,5.,0.,10.);assert c[3]==0. and c[1]==-15.
    # Same business function, manually: sales100, 20% gross, opex10%, tax0,
    # da2, capex3, no growth/working capital change => profit10, FCF9.
    p=copy.deepcopy(P);p['legacy_tax']=True;p.update(growth5=[[0.]*5]*5,gross5=[[.2]*5]*5,opex5=[.1]*5,tax=0.,wc_ratio=.1,
       depreciation_ratio=.02,capex_ratio=.03,committed_capex=[0.]*5,sbc_path=[0.]*5)
    z=annual_business(p,1,[100.,0.,0.,0.,0.],10.,20.)
    assert z['nopat']==10. and z['fcf']==9.
    p.update(parent_voluntary_reserve_continues=False,revenue0=[100.,0.,0.,0.,0.],cash0=[10.]+[0.]*6,term0=[0.]*7,debt0=[0.]*7,lease0=0.,legal0=[100.]+[0.]*6,reserve0=[1.]+[0.]*6,capital0=[2.]+[0.]*6,loan0=[0.]*6,cash_floor_ratio=0.,deposit_yield=0.,new_shares=[0.]*5,subs_profit5=[[0.]*6]*5,subs_profit_mature=[0.]*6,reinvest_weights=[1.]+[0.]*6,wc0=10.,fixed0=20.,payout5=.5,special_start=99)
    trial=simulate(p,1);row=trial['rows'][0]
    assert trial['feasible'] and abs(row['distribution']-5.)<1e-9 and abs(row['cash'][0]-14.)<1e-9 and abs(row['legal'][0]-105.)<1e-9
    taxcase=copy.deepcopy(p);taxcase.update(gross5=[[.1]*5]*5,capex_ratio=0.,depreciation_ratio=0.,cash0=[10.,1.,0.,0.,0.,0.,0.],loan0=[10.,0.,0.,0.,0.,0.],legal0=[100.,-2.,0.,0.,0.,0.,0.],tax=.15,loan_rate=.03)
    taxrow=simulate(taxcase,1)['rows'][0]
    assert abs(taxrow['internal_interest_parent_cash_tax']-.045)<1e-12
    assert sum(taxrow['internal_interest_sub_cash_tax_shield'])==0.
    assert abs(sum(taxrow['cash'])-10.955)<1e-9
    return {'internal_interest_cash_tax_hand_case':{'parent_cash_tax':taxrow['internal_interest_parent_cash_tax'],'subs_shield':sum(taxrow['internal_interest_sub_cash_tax_shield']),'ending_group_cash':sum(taxrow['cash'])},'full_simulator_hand_case':{'distribution':row['distribution'],'cash':row['cash'][0],'legal':row['legal'][0]},'payment_gate_hand_case':list(a),'no_double_legal_principal':b[3],'loss_carry':c[1],'business_hand_case_fcf':z['fcf']}

def make():
    out={'symbol':'CN:300693','period':'2026-Q3','as_of':'2026-10-26','unit':'CNY million; shares million; per-share CNY',
       'entity_parameters_are_budgets_not_disclosed_Q3_legal_accounts':True,'tests':self_tests(),'scenarios':{}}
    for name,p in configs().items():
        p=prepare_award_budget(p);run=simulate(p);run['low']=value(run,p['discount_low']);run['high']=value(run,p['discount_high']);out['scenarios'][name]=run
    base=out['scenarios']['base'];assert base['feasible']
    out['earnings_power_crosscheck']=earnings_power_crosscheck(base)
    longer=simulate(prepare_award_budget(P),320);out['convergence']={}
    for r in [.10,.11]:
        a=value(base,r);b=value(longer,r);out['convergence'][str(r)]={'horizon240':a['per_share'],'horizon320':b['per_share'],'difference':b['per_share']-a['per_share']}
        assert abs(b['per_share']-a['per_share'])<.00001
    assert not out['scenarios']['funding_failure']['feasible']
    out['value_range']={'low':round(base['low']['per_share'],2),'high':round(base['high']['per_share'],2),'currency':'CNY'}
    out['return_model']={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':'2026-10-26T09:30:00+00:00',
       'base_case_distributions_per_share':[x['distribution_per_share'] for x in base['rows'][:5]],
       'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':base['low']['year5_terminal_per_share'],'high':base['high']['year5_terminal_per_share']}}}
    return out

def canonical_bytes(o):
 return json.dumps(o,ensure_ascii=False,separators=(',',':')).encode('utf-8')

def pack_output(o):
 def summary(x):
  if isinstance(x,dict):return {k:summary(v) for k,v in x.items() if k not in ('rows','tail_rows')}
  if isinstance(x,list):return [summary(v) for v in x]
  return x
 raw=canonical_bytes(o);p=summary(o)
 p['_complete_output']={'encoding':'gzip-mtime0-base64-json-utf8','expanded_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'schema':'Complete 34 scenarios, every annual entity tax, legal capital, cash, financing, share, investment and capital-realization field, auxiliary economics and convergence. Outer object is a readable summary, not the annual detail. CNY million and shares million; per-share CNY.','expand_command':'python 2026-Q3.py --expand 2026-Q3-output.json expanded.json','data':base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode('ascii')}
 assert expand_output(p)==o
 return p

def expand_output(o):
 a=o['_complete_output'];raw=gzip.decompress(base64.b64decode(a['data']))
 assert len(raw)==a['expanded_bytes'] and hashlib.sha256(raw).hexdigest()==a['sha256']
 return json.loads(raw)

if __name__=='__main__':
 if len(sys.argv)==4 and sys.argv[1]=='--expand':
  src=json.loads(Path(sys.argv[2]).read_text());Path(sys.argv[3]).write_bytes(canonical_bytes(expand_output(src)))
 else:
  o=make();Path(__file__).with_name('2026-Q3-output.json').write_bytes(canonical_bytes(pack_output(o)));print(o['value_range'])

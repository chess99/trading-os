#!/usr/bin/env python3
"""NARI 2026Q3 owner cash model. stdlib only; CNY billion, shares billion.
All source-level forecasts and opening unreported legal balances are economic
budgets, not representations of undisclosed legal-entity accounts.
"""
import json, math, copy
ASOF='2026-10-28T21:00:00+08:00'
SHARES=8.031756156 # already issued including treasury; full regrant dilution
SOURCE_URLS={
 'Q3':'https://static.cninfo.com.cn/finalpage/2026-10-29/1225635689.PDF',
 'H1':'https://static.cninfo.com.cn/finalpage/2026-08-27/1225508099.PDF',
 'FY25':'https://static.cninfo.com.cn/finalpage/2026-04-30/1225257886.PDF',
 'buyback':'https://static.cninfo.com.cn/finalpage/2026-10-29/1225635679.PDF',
 'dividend':'https://static.cninfo.com.cn/finalpage/2026-09-22/1225575117.PDF'}
# Earnings are after source-specific tax, excluding all financial asset returns.
# A source may contain several legal persons: legal profit ceilings are explicit
# budgets tested below, never an assertion that their profits legally offset.
SOURCES=[
 dict(name='control',owner=1.,profit=1.8,cash=2.,floor=.7,re=6.0,reserve=.5,capital=1.5,weight=.22,tax=.13,legal=.85),
 dict(name='information',owner=1.,profit=1.1,cash=1.,floor=.4,re=2.,reserve=.4,capital=1.5,weight=.13,tax=.13,legal=.85),
 dict(name='relay_group',owner=.87,profit=3.6,cash=4.5,floor=1.2,re=5.0,reserve=.4,capital=1.2,weight=.36,tax=.11,legal=.80),
 dict(name='other_profitable',owner=.95,profit=2.8,cash=.4,floor=.3,re=8.0,reserve=.4,capital=2.0,weight=.24,tax=.15,legal=.75),
 dict(name='semiconductor',owner=.6539,profit=-.09,cash=.12,floor=.1,re=-.8,reserve=0.,capital=.8667189,weight=.05,tax=.15,legal=1.)]
# H1 receivable 2.0619bn =20.619亿元; not 20.619bn. Q3 settled amount unknown.
# Remaining 0.8bn is a timing budget only and already recognized in opening RE.
OLD_RECEIVABLE=.8
PARENT=dict(name='listed_parent',cash=11.9801975,floor=1.5,re=.85,reserve=3.06223541013,capital=8.031756156)
# Aggregate liquidity 20.0001975 after October incremental buyback; current
# term deposits 2.58bn, other non-current deposits 4.55bn are Q3 estimates.
CASES={
 'base':dict(r=.09,g=.075,margin=1.,wc=.25,extra_wc=.6,up=.82,h=.08,tax_add=0.),
 'core_low':dict(r=.095,g=.065,margin=.98,wc=.28,extra_wc=.8,up=.80,h=.07,tax_add=0.),
 'core_high':dict(r=.085,g=.085,margin=1.02,wc=.23,extra_wc=.4,up=.85,h=.09,tax_add=0.),
 'cycle':dict(r=.09,g=.075,margin=1.,wc=.30,extra_wc=2.5,up=.75,h=.06,tax_add=0.,cycle=True),
 'structural':dict(r=.10,g=.025,margin=.77,wc=.36,extra_wc=2.,up=.7,h=.06,tax_add=.015,structural=True),
 'optimistic':dict(r=.085,g=.105,margin=1.06,wc=.21,extra_wc=.2,up=.88,h=.1,tax_add=0.),
 'margin_minus_1pct':dict(r=.09,g=.075,margin=1.-.77/9.21,wc=.25,extra_wc=.6,up=.82,h=.08,tax_add=0.),
 'cash_conversion_slow':dict(r=.09,g=.075,margin=1.,wc=.35,extra_wc=2.6,up=.65,h=.08,tax_add=0.),
 'legal_half':dict(r=.09,g=.075,margin=1.,wc=.25,extra_wc=.6,up=.82,h=.08,tax_add=0.,legal_mult=.5),
 'cash_open_minus_1bn':dict(r=.09,g=.075,margin=1.,wc=.25,extra_wc=.6,up=.82,h=.08,tax_add=0.,cash_shift=-1.),
 'parent_supports_all':dict(r=.09,g=.075,margin=1.,wc=.25,extra_wc=.6,up=.82,h=.08,tax_add=0.,full_support=True),
 'parent_extra_payment':dict(r=.09,g=.075,margin=1.,wc=.25,extra_wc=.6,up=.82,h=.08,tax_add=0.,parent_payment=1.),
 'finance_yield_zero':dict(r=.09,g=.075,margin=1.,wc=.25,extra_wc=.6,up=.82,h=.08,tax_add=0.,yield_net=0.),
}
def legal_step(re,reserve,capital,profit,wanted):
    """Loss-first: a positive year first cures pre-existing accumulated loss.
    Appropriation 10% only of post-loss profit, capped at half legal capital.
    RE remains negative if losses remain. No group loss pooling.
    """
    cure=min(max(profit,0.),max(-re,0.))
    distributable_new=max(profit-cure,0.)
    addition=min(.1*distributable_new,max(.5*capital-reserve,0.))
    legal=max(re+profit-addition,0.)
    dividend=min(max(wanted,0.),legal)
    return dict(re=re+profit-addition-dividend,reserve=reserve+addition,
                loss_cured=cure,reserve_added=addition,ceiling=legal,dividend=dividend)
def cash_step(cash,opcash,interest,capex,wc,debt,repay,injection,receipt,dividend):
    end=cash+opcash+interest-capex-wc+debt-repay+injection+receipt-dividend
    return end

def investment_step(book,addition,capital_return,close=False,impairment=0.):
    basis=book+addition
    loss=basis-capital_return if close else min(impairment,basis)
    return (0. if close else basis-loss),loss

def per_share(cash,issued,treasury=0.,regrant=True):
    denominator=issued if regrant else issued-treasury
    assert denominator>0
    return cash/denominator

def run(c, horizon=60):
    fullinputs=copy.deepcopy(c)
    ss=copy.deepcopy(SOURCES); p=copy.deepcopy(PARENT)
    p['cash']+=c.get('cash_shift',0.)
    # Distinct internal settlement obligation; never automatically net against RE.
    # H1 parent other payables exceeds consolidated by ~19bn, but composition
    # and maturity not published. 17bn budget claims, not proven pooling contract.
    claims={'control':7.,'information':3.,'relay_group':5.,'other_profitable':2.,'semiconductor':0.}
    liability=sum(claims.values()); recv=OLD_RECEIVABLE
    debt=.37330786866; revenue=77.; previous_revenue=74.; scale=1.
    semi_basis=.56001927137+fullinputs.get('semi_basis_delta',0.) # H1 p228 actual; Q3 movement unreported
    semi_netnoncash=.2328327-.12 # H1 net assets less starting cash budget; ALL liabilities already netted
    annual=[]; y=c.get('yield_net',.015); group_re=34.95795264214
    for t in range(1,horizon+1):
        c=fullinputs.get('first_five',fullinputs) if t<=5 else fullinputs
        basis_open=semi_basis; investment_loss=0.;semi_added=0.;capital_return=0.
        opening=sum(s['cash'] for s in ss)+p['cash']
        oldscale=scale
        growth=(c['g'] if t<=5 else c['g']*(20-t)/15 if t<=20 else 0.)
        if t>1: scale*=1+growth; revenue=77.*scale
        # Rolling 12-month year1; source earnings anchor has Q4 seasonality,
        # not 9M*4/3. Temporary slump recovers in years3-4, not instantly.
        cyclefactor=([.82,.88,.96,1.][t-1] if c.get('cycle') and t<=4 else 1.)
        # Additional working capital is a permanent new level, not an annual tax.
        dnwc=max(revenue-previous_revenue,0.)*c['wc']+(c['extra_wc'] if t==1 else 0.)
        if c.get('cycle') and t==4: dnwc-=1.5 # bounded delayed collection recovery
        if t>20: dnwc=0.
        capex=(2.3*scale if t<=10 else (1.35+(2.3-1.35)*(20-t)/10)*scale if t<=20 else 1.35*scale)
        da=1.35*scale
        if '_aux' in c:
            ab=c['_aux'][min(t-1,len(c['_aux'])-1)];scale=ab['earnings']/c['_aux'][0]['earnings'];revenue=ab['revenue'];capex=ab['capex'];da=ab['da'];dnwc=ab['wc']
        floor_scale=scale
        h=(c['h'] if t<=5 else c['h']+(0.2-c['h'])*(min(t,20)-5)/15)
        # Source earnings and cash remain separate from mother statutory profit.
        srcrows=[]; upstream=0.; cash_up=0.; support=0.; minority_d=0.; minority_in=0.; total_profit=0.; total_yield=0.; total_cap=0.; total_da=0.; total_wc=0.; settletotal=0.; old_paid=0.
        for s in ss:
            name=s['name']; start=s['cash']; own=s['owner']; floor=s['floor']*floor_scale;source_open_re=s['re']
            profit=s['profit']*scale*c['margin']*cyclefactor
            if '_aux' in c and name!='semiconductor':
                profit=s['profit']/8.692*(ab['earnings']+.30*scale)
            if name=='semiconductor':
                # Independent loss entity. Base ramp no positive dividends until
                # accumulated loss is cured. Structural winds down by year8.
                seq=[-.09,-.06,-.04,-.02,0.,.015,.025,.03]
                profit=(seq[min(t-1,7)]*scale if not c.get('structural') else (-.10 if t<8 else -.15 if t==8 else 0.))
            pretax=profit/(1-s['tax']) if profit>0 else profit
            tax=max(pretax,0.)*(s['tax']+c['tax_add'])
            profit=pretax-tax
            interest=start*y
            capital_exp=capex*s['weight']; depreciation=da*s['weight']; wc=dnwc*s['weight']
            exit_year=c.get('exit_year',8 if c.get('structural') else 12)
            liquidation=(name=='semiconductor' and t==exit_year)
            closed=(name=='semiconductor' and t>exit_year)
            noncash_disposal=0.;netbook_open=semi_netnoncash if name=='semiconductor' else 0.;net_recovery=0.;closure=0.
            if name=='semiconductor' and t>=exit_year:
                capital_exp=0.;depreciation=0.;wc=0.;floor=0.
                closure=c.get('exit_closure',.1+c.get('exit_net_cost',.05)) if liquidation else 0.
                net_recovery=(semi_netnoncash*c['exit_book_recovery'] if 'exit_book_recovery' in c else c.get('exit_net_recovery',.1)) if liquidation else 0.
                profit=net_recovery-closure if liquidation else 0. # NET of all noncash liabilities, not gross assets
                noncash_disposal=semi_netnoncash if liquidation else 0.
                interest=0. if closed else interest
                pretax=profit;tax=0.
            # Existing credit is repaid once; capital support preserves liquidity.
            repay=0. # centrally funded debt retirement below; no fictional entity allocation
            pre=cash_step(start,profit+depreciation,interest,capital_exp,wc,0.,repay,0.,0.,0.)
            injection=max(floor-pre,0.)
            parent_fraction=own if c.get('minority_subscribes') else 1.
            support+=injection*parent_fraction;minority_in+=injection*(1-parent_fraction)
            pre+=injection
            if name=='semiconductor':
                semi_added=injection*parent_fraction;semi_basis+=semi_added
                semi_netnoncash+=capital_exp-depreciation+wc
                if liquidation: semi_netnoncash=0.
            # 40% of owned declaration may settle genuine intercompany claims.
            # Such settlement needs bilateral legal authorization, modeled not fact.
            can_settle=claims[name]/max(own,1e-20)
            wanted=(c['up']*max(profit,0.)+h*max(pre-floor,0.)) if t<=20 else profit+interest+h*max(start-floor,0.)
            eligibility=1.-(1.-s['legal']*c.get('legal_mult',1.))*max(0.,(20-t)/19)
            wanted*=eligibility
            sbc=.09 if name=='other_profitable' and t<=3 else 0.
            legalprofit=profit+interest-sbc-noncash_disposal
            max_payable=max(pre-floor,0.)+can_settle
            leg=legal_step(s['re'],s['reserve'],s['capital'],legalprofit,min(wanted,max_payable))
            declaration=leg['dividend'];setoff=min(.4*declaration*own,claims[name]) if t<=20 else 0.
            cash_div=declaration-setoff
            if cash_div>max(pre-floor,0.):
                # Reduce actual policy first, then recompute legal state.
                declaration=max(pre-floor,0.)+setoff
                leg=legal_step(s['re'],s['reserve'],s['capital'],legalprofit,declaration)
                declaration=leg['dividend'];setoff=min(.4*declaration*own,claims[name]) if t<=20 else 0.;cash_div=declaration-setoff
                # A second strict cap prevents setoff fraction circularity.
                if cash_div>max(pre-floor,0.):
                    declaration=max(pre-floor,0.)/(1-.4*own) if t<=20 and claims[name]>.4*declaration*own else max(pre-floor,0.)+min(claims[name],.4*declaration*own)
                    leg=legal_step(s['re'],s['reserve'],s['capital'],legalprofit,declaration);declaration=leg['dividend'];setoff=min(.4*declaration*own,claims[name]) if t<=20 else 0.;cash_div=declaration-setoff
            if liquidation:
                declaration=max(pre,0.);cash_div=declaration;setoff=0.
                leg=legal_step(s['re'],s['reserve'],s['capital'],legalprofit,0.)
            if liquidation:
                capital_return=declaration*own
                semi_basis,investment_loss=investment_step(semi_basis,0.,capital_return,close=True) # noncash loss; no tax shield
            s['cash']=pre-cash_div;s['re']=leg['re'];s['reserve']=leg['reserve']
            claims[name]-=setoff;liability-=setoff;settletotal+=setoff
            upstream+=(0. if liquidation else declaration*own);cash_up+=declaration*own-setoff
            minority_d+=declaration*(1-own)
            # Previously declared subsidiary dividend: cash only, no new profit.
            paid=0.
            if name=='relay_group' and t<=2:
                paid=min(recv,max(s['cash']-floor,0.),OLD_RECEIVABLE/2);s['cash']-=paid;recv-=paid;old_paid+=paid
            total_profit+=profit;total_yield+=interest;total_cap+=capital_exp;total_da+=depreciation;total_wc+=wc
            assert s['cash']>=floor-1e-8,(name,t,s['cash'],floor)
            assert abs(s['cash']-(start+profit+depreciation+interest-capital_exp-wc-repay+injection-cash_div-paid))<1e-8
            srcrows.append(dict(name=name,owner=own,liquidation=liquidation,closed=closed,source_anchor='H1 p29,196-197; normalized future budget',cash_open=start,re_open=source_open_re,pretax=pretax,tax=tax,operating_profit=profit,financial_income=interest,financial_income_gross=interest/.85,financial_tax_budget=interest/.85*.15,noncash_share_compensation=sbc,legal_profit_budget=legalprofit,capex=capital_exp,da=depreciation,delta_wc=wc,required_cash=floor,debt_repaid=repay,equity_injection=injection,minority_capital=injection*(1-parent_fraction),declaration=declaration,owned_new_income=0. if liquidation else declaration*own,owned_capital_return=declaration*own if liquidation else 0.,liquidation_net_asset_recovery=net_recovery,liquidation_cost=closure,noncash_disposal_book_charge=noncash_disposal,net_noncash_book_open=netbook_open,net_noncash_book_close=semi_netnoncash if name=='semiconductor' else 0.,cash_to_parent=declaration*own-setoff,intercompany_setoff=setoff,old_dividend_paid=paid,external_minority_dividend=declaration*(1-own),cash_close=s['cash'],**{k:v for k,v in leg.items() if k!='dividend'}))
        startp=p['cash']; parent_op=-.30*scale*(1.4 if c.get('structural') else 1.)-(.01119923606 if t==1 else 0.)
        parent_interest=startp*y
        # Parent fixed assets already in consolidated capex allocations above;
        # allocate .25bn cash directly and deduct same amount from other source
        # budgets? Instead parent service Op includes maintenance net cash cost;
        # all DA/capex stays in sources; parent op is net of own maintenance.
        repurchase=.3506679732 if t==1 else 0. # min authorized remaining cash
        if c.get('structural') and t==1: repurchase=.8506679732
        # Current claims payment shock is a real transfer, not group loss.
        payment=c.get('parent_payment',0.) if t==1 else 0.
        if payment:
            q=min(payment,claims['control']);claims['control']-=q;liability-=q;ss[0]['cash']+=q;srcrows[0]['cash_close']+=q;srcrows[0]['extra_intercompany_receipt']=q
        parent_pre=cash_step(startp,parent_op,parent_interest,repurchase,0.,0.,debt if t==1 else 0.,-support-payment,cash_up+old_paid,0.)
        parent_floor=p['floor']*scale
        early_impairment=semi_basis if c.get('semi_early_impairment') and t==1 else 0.
        semi_basis,impairment_loss=investment_step(semi_basis,0.,0.,impairment=early_impairment)
        investment_loss+=impairment_loss
        legalprofit=parent_op+parent_interest+upstream-investment_loss
        group_re+=sum((r['operating_profit']-r['noncash_share_compensation']-r['noncash_disposal_book_charge']+r['financial_income'])*r['owner'] for r in srcrows)+parent_op+parent_interest
        # 60% of recurring owned operating profit; increasing toward full
        # cash generation. Excess-cash distribution is gradual and legal-limited.
        recurring=sum(r['operating_profit']*r['owner'] for r in srcrows)+parent_op
        payout=.60 if t<=5 else .60+.40*(min(t,20)-5)/15
        wanted=(payout*max(recurring,0.)+h*max(parent_pre-parent_floor,0.)) if t<=20 else legalprofit-support+h*max(startp-parent_floor,0.)
        affordable=max(parent_pre-parent_floor,0.)
        leg=legal_step(p['re'],p['reserve'],p['capital'],legalprofit,min(wanted,affordable,max(group_re,0.)))
        distribution=leg['dividend'];p['cash']=parent_pre-distribution;p['re']=leg['re'];p['reserve']=leg['reserve'];group_re-=distribution
        assert p['cash']>=parent_floor-1e-8,(t,p['cash'],parent_floor)
        closing=sum(s['cash'] for s in ss)+p['cash']
        expected=opening+total_profit+parent_op+total_yield+parent_interest+total_da-total_cap-total_wc-(debt if t==1 else 0)+minority_in-minority_d-repurchase-distribution
        assert abs(closing-expected)<1e-7,(t,closing,expected)
        assert abs(sum(claims.values())-liability)<1e-7
        annual.append(dict(year=t,revenue=revenue,scale=scale,group_cash_open=opening,group_operating_profit=total_profit+parent_op,group_financial_yield=total_yield+parent_interest,group_capex=total_cap,group_da=total_da,group_delta_wc=total_wc,source_records=srcrows,parent=dict(semi_investment_basis_open=basis_open,semi_investment_addition=semi_added,semi_capital_return=capital_return,semi_investment_loss=investment_loss,semi_early_impairment=early_impairment,semi_investment_basis_close=semi_basis,cash_open=startp,own_profit=parent_op,financial_income=parent_interest,financial_income_gross=parent_interest/.85,financial_tax_budget=parent_interest/.85*.15,new_declared_income=upstream,new_cash_received=cash_up,old_receivable_collected=old_paid,old_receivable_remaining=recv,intercompany_setoff=settletotal,intercompany_liability=liability,extra_intercompany_payment=payment,source_capital_support=support,central_debt_repaid=debt if t==1 else 0.,buyback_cash=repurchase,legal_profit=legalprofit,cash_available=affordable,cash_close=p['cash'],required_cash=parent_floor,**leg),group_cash_close=closing,group_re=group_re,shares=SHARES,distribution=distribution,dps=per_share(distribution,SHARES)))
        previous_revenue=revenue
    # Exact steady tail once growth/investment/reserves/receivables settle.
    # Forecast eligibility converges by year20; legal loss/reserve/cash constraints
    # remain active each year. Tail is admitted only after exact transition tests.
    last=annual[-1]; floor=sum(a['required_cash']*a['owner'] for a in last['source_records'])+p['floor']*scale
    excess=sum((a['cash_close']-a['required_cash'])*a['owner'] for a in last['source_records'])+p['cash']-p['floor']*scale
    stable=sum(row['operating_profit']*row['owner'] for row in last['source_records'])+last['parent']['own_profit']+y*floor
    # Upstream scheduling converges over twenty years. Cash and legal balances
    # continue unchanged into the steady state; principal is never spot-added.
    tail=stable/c['r']+(y+.2)*excess/(c['r']+.2)
    if True:
        previous_excess=sum((s['cash_close']-s['required_cash'])*s['owner'] for s in annual[-2]['source_records'])+annual[-2]['parent']['cash_close']-annual[-2]['parent']['required_cash']
        assert abs(excess-.8*previous_excess)<1e-7,('tail_not_converged',excess,previous_excess)
        assert abs(last['distribution']-(stable+(y+.2)*previous_excess))<1e-7,('tail_distribution',last['distribution'],stable+(y+.2)*previous_excess)
    pv=sum(a['dps']/(1+c['r'])**a['year'] for a in annual)+tail/SHARES/(1+c['r'])**horizon
    tv5=sum(a['dps']/(1+c['r'])**(a['year']-5) for a in annual if a['year']>5)+tail/SHARES/(1+c['r'])**(horizon-5)
    return dict(inputs=fullinputs,value=pv,d=[a['dps'] for a in annual[:5]],tv5=tv5,terminal5_pv_share=tv5/(1+c['r'])**5/pv,annual=annual,tail=dict(year=horizon,stable_owned_cash_profit=stable,necessary_cash=floor,excess_cash=excess,value=tail,discounted_value_per_share=tail/SHARES/(1+c['r'])**horizon),cash_conservation=True)

def auxiliary():
    """Independent segment earning power / reinvestment franchise, then exactly
    the same source ownership, statutory reserves, cash and holder bridge.
    No market multiple, RI identity or controller-level immediate cash extraction.
    """
    ans={}
    for label,margins,r,roic in [('low',[.155,.115,.065,.09],.095,.14),('high',[.165,.13,.08,.10],.085,.16)]:
        rev=[35.5,12.5,25.,3.0]
        earnings=sum(a*b for a,b in zip(rev,margins))
        opening_earnings=earnings;revenue=sum(rev);budgets=[]
        for t in range(1,61):
            reinvest=.30*earnings if t<=10 else .30*earnings*(20-t)/10 if t<=20 else 0.
            # Independent total net growth capital; half fixed, half working.
            gap=.75*(max(0,20-t)/19) # mature engineering maintenance gap fades
            budgets.append(dict(year=t,earnings=earnings,reinvestment=reinvest,revenue=revenue,capex=1.35+gap+.5*reinvest,da=1.35,wc=.5*reinvest))
            earnings+=reinvest*roic;revenue=sum(rev)*earnings/opening_earnings
        c=dict(r=r,g=0.,margin=1.,wc=0.,extra_wc=0.,up=.82,h=.08,tax_add=0.,_aux=budgets)
        result=run(c)
        ans[label]=dict(value=result['value'],normal_earnings=opening_earnings,segment_revenues=rev,owner_aftertax_segment_margins=margins,maintenance_gap_initial=.75,roic=roic,discount=r,model=result)
    return ans

def tests():
    # Calls production functions. Independent literal hand examples.
    a=legal_step(-5.,0.,10.,3.,99.);assert a['dividend']==0 and a['reserve']==0 and a['re']==-2
    b=legal_step(-5.,0.,10.,8.,99.);assert abs(b['reserve']-.3)<1e-12 and abs(b['dividend']-2.7)<1e-12 and abs(b['re'])<1e-12
    z=legal_step(1.,4.8,10.,10.,99.);assert abs(z['reserve_added']-.2)<1e-12 and abs(z['dividend']-10.8)<1e-12
    assert cash_step(10.,4.,.2,2.,1.,3.,2.,0.,1.,5.)==8.2
    assert abs(legal_step(0,0,10,0,9)['ceiling'])<1e-12 # old receivable cannot create profit
    # Treasury is not cancellation: full regrant dilutes to issued count.
    assert per_share(12.,10.,2.,False)==1.5
    assert per_share(12.,10.,2.,True)==1.2
    assert abs((8.031756156-.051749523)-7.980006633)<1e-12
    ib,il=investment_step(.56,.20,.10,True);assert ib==0. and abs(il-.66)<1e-12
    ib,il=investment_step(.56,.20,0.,impairment=.30);assert abs(ib-.46)<1e-12 and il==.30
    # No second cash deduction: return is receipt; historic .20 support was paid earlier.
    assert cash_step(1.,0.,0.,0.,0.,0.,0.,0.,.10,0.)==1.1
    return dict(investment_disposal=True,investment_impairment=True,loss_first=True,reserve_cap=True,cash_debt=True,old_receivable=True,shares=True)

def main():
    CASES['minority_subscribes']=dict(CASES['base'],minority_subscribes=True)
    CASES['semi_exit_later']=dict(CASES['base'],exit_year=20,exit_net_cost=.20)
    CASES['semi_zero_net_recovery']=dict(CASES['base'],exit_net_recovery=0.)
    CASES['semi_full_netbook_recovery']=dict(CASES['base'],exit_book_recovery=1.)
    CASES['semi_basis_plus_02bn']=dict(CASES['base'],semi_basis_delta=.2)
    CASES['semi_early_impairment']=dict(CASES['base'],semi_early_impairment=True)
    CASES['holder_terminal_low']=dict(CASES['core_low'],first_five=CASES['base'])
    CASES['holder_terminal_high']=dict(CASES['core_high'],first_five=CASES['base'])
    results={k:run(v) for k,v in CASES.items()}
    assert results['holder_terminal_low']['d']==results['base']['d']==results['holder_terminal_high']['d']
    aux=auxiliary()
    convergence={}
    for key,initial in list(results.items())+[(f'aux_{k}',v['model']) for k,v in aux.items()]:
        inp=initial['inputs']; extensions=[]
        for n in (100,160):
            extended=run(inp,n)
            assert abs(extended['value']-initial['value'])<1e-8,(key,n,extended['value'],initial['value'])
            assert abs(extended['tv5']-initial['tv5'])<1e-8
            extensions.append(dict(horizon=n,value=extended['value'],tv5=extended['tv5'],tail=extended['tail'],last_distribution=extended['annual'][-1]['distribution'],last_group_operating_profit=extended['annual'][-1]['group_operating_profit'],last_group_cash=extended['annual'][-1]['group_cash_close'],last_parent=extended['annual'][-1]['parent'],last_source_records=extended['annual'][-1]['source_records']))
        a,b=extensions
        for field in ('last_distribution','last_group_operating_profit','last_group_cash'):
            assert abs(a[field]-b[field])<1e-6,(key,field,a[field],b[field])
        for field in ('re','reserve','cash_close'):
            assert abs(a['last_parent'][field]-b['last_parent'][field])<1e-6,(key,'parent',field)
            for sa,sb in zip(a['last_source_records'],b['last_source_records']):
                assert abs(sa[field]-sb[field])<1e-6,(key,sa['name'],field,sa[field],sb[field])
        convergence[key]=extensions
    print(json.dumps(dict(asof=ASOF,units='CNY bn / shares bn / per share CNY',sources=SOURCE_URLS,initial_sources=SOURCES,initial_parent=PARENT,tests=tests(),primary=results,auxiliary=aux,convergence=convergence),ensure_ascii=False,sort_keys=True,indent=2))
if __name__=='__main__':main()

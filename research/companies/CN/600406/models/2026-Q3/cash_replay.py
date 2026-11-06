"""当前资本现金与权益计算核；经营输入由同次实际计算生成。"""

import copy, math, json, hashlib

from bridge_common import EconomicFailure, CacheMissing, require, freeze_equal

SHARES=8.031756156

SOURCES=[
 dict(name='control',owner=1.,profit=1.8,cash=2.,floor=.7,re=6.0,reserve=.5,capital=1.5,weight=.22,tax=.13,legal=.85),
 dict(name='information',owner=1.,profit=1.1,cash=1.,floor=.4,re=2.,reserve=.4,capital=1.5,weight=.13,tax=.13,legal=.85),
 dict(name='relay_group',owner=.87,profit=3.6,cash=4.5,floor=1.2,re=5.0,reserve=.4,capital=1.2,weight=.36,tax=.11,legal=.80),
 dict(name='other_profitable',owner=.95,profit=2.8,cash=.4,floor=.3,re=8.0,reserve=.4,capital=2.0,weight=.24,tax=.15,legal=.75),
 dict(name='semiconductor',owner=.6539,profit=-.09,cash=.12,floor=.1,re=-.8,reserve=0.,capital=.8667189,weight=.05,tax=.15,legal=1.)]

OLD_RECEIVABLE=.8

PARENT=dict(name='listed_parent',cash=11.9801975,floor=1.5,re=.85,reserve=3.06223541013,capital=8.031756156)

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

def run(c, frozen_rows, *, paid_delta=0.05008263040, refund_extra=0.0):
    horizon=len(frozen_rows)
    require(horizon>=21, "NARI tail needs saved complete horizon")
    fullinputs=copy.deepcopy(c)
    ss=copy.deepcopy(SOURCES); p=copy.deepcopy(PARENT)
    p['cash']+=c.get('cash_shift',0.)-paid_delta
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
        frozen=frozen_rows[t-1]
        require(frozen['year']==t, 'NARI noncontiguous cache')
        scale=frozen['scale'];revenue=frozen['revenue'];floor_scale=scale
        h=(c['h'] if t<=5 else c['h']+(0.2-c['h'])*(min(t,20)-5)/15)
        # Source earnings and cash remain separate from mother statutory profit.
        srcrows=[]; upstream=0.; cash_up=0.; support=0.; minority_d=0.; minority_in=0.; total_profit=0.; total_yield=0.; total_cap=0.; total_da=0.; total_wc=0.; settletotal=0.; old_paid=0.
        for s in ss:
            name=s['name']; start=s['cash']; own=s['owner']; floor=s['floor']*floor_scale;source_open_re=s['re']
            fr=next(x for x in frozen['source_records'] if x['name']==name)
            profit=fr['operating_profit'];pretax=fr['pretax'];tax=fr['tax']
            interest=start*y
            capital_exp=fr['capex'];depreciation=fr['da'];wc=fr['delta_wc']
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
            require(s['cash']>=floor-1e-8,'source_cash_floor_unfunded',economic=True,state={'name':name,'year':t,'cash':s['cash'],'floor':floor,'rows':annual})
            assert abs(s['cash']-(start+profit+depreciation+interest-capital_exp-wc-repay+injection-cash_div-paid))<1e-8
            srcrows.append(dict(name=name,owner=own,liquidation=liquidation,closed=closed,source_anchor='H1 p29,196-197; normalized future budget',cash_open=start,re_open=source_open_re,pretax=pretax,tax=tax,operating_profit=profit,financial_income=interest,financial_income_gross=interest/.85,financial_tax_budget=interest/.85*.15,noncash_share_compensation=sbc,legal_profit_budget=legalprofit,capex=capital_exp,da=depreciation,delta_wc=wc,required_cash=floor,debt_repaid=repay,equity_injection=injection,minority_capital=injection*(1-parent_fraction),declaration=declaration,owned_new_income=0. if liquidation else declaration*own,owned_capital_return=declaration*own if liquidation else 0.,liquidation_net_asset_recovery=net_recovery,liquidation_cost=closure,noncash_disposal_book_charge=noncash_disposal,net_noncash_book_open=netbook_open,net_noncash_book_close=semi_netnoncash if name=='semiconductor' else 0.,cash_to_parent=declaration*own-setoff,intercompany_setoff=setoff,old_dividend_paid=paid,external_minority_dividend=declaration*(1-own),cash_close=s['cash'],**{k:v for k,v in leg.items() if k!='dividend'}))
        startp=p['cash']; parent_op=frozen['parent']['own_profit']
        parent_interest=startp*y
        # Parent fixed assets already in consolidated capex allocations above;
        # allocate .25bn cash directly and deduct same amount from other source
        # budgets? Instead parent service Op includes maintenance net cash cost;
        # all DA/capex stays in sources; parent op is net of own maintenance.
        repurchase=.3506679732-paid_delta+refund_extra if t==1 else 0. # min authorized remaining cash
        if c.get('structural') and t==1: repurchase=.8506679732-paid_delta+refund_extra
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
        require(p['cash']>=parent_floor-1e-8,'parent_cash_floor_unfunded',economic=True,state={'year':t,'parent':p,'floor':parent_floor,'rows':annual})
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

def replay(saved, *, paid_delta=0.05008263040, refund_extra=0.0):
    return run(copy.deepcopy(saved['inputs']), saved['annual'], paid_delta=paid_delta, refund_extra=refund_extra)

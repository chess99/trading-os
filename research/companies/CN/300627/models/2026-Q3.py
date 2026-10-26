"""CN:300627 Huace Navigation, CNY million. Stdlib only.
Rolling years from 2026-10-26. Long years are numerical integration, not forecasts.
First block is the frozen legacy counterfactual only. Corrected simulate below uses parent law and economic source budgets.
"""
import copy,json,math
from pathlib import Path
P={
 'sales':[3600,4000,4400,4800,5200], 'margin':[.13,.15,.16,.165,.17],
 'terminal_growth':.02,'terminal_margin':.145,'fade_end':15,
 'wc_ratio':.39,'fixed_ratio':.20,'opening_wc':1430.,'opening_fixed':686.,
 'tax':.15,'cash_yield':.018,'debt_rate':.035,'payout':.50,
 'opening_cash':[1800.,200.,200.], 'opening_debt':[105.006481,17.225,17.225],
 'opening_legal':[1700.,0.,0.], 'opening_reserve':[370.058427,0.,0.],
 'capital':[793.970662,50.,200.], 'weights':[.85,.075,.075],
 'cash_weights':[.85,.075,.075], 'floor_weights':[.75,.10,.15], 'floor_ratio':.12,
 'new_shares':[.60312,0.,0.,0.,0.], 'exercise_prices':[16.8,26.63,26.63,0,0],
 'sbc_addback':[0.,0.,0.,0.,0.], 'sbc_expense':[0.,0.,0.,0.,0.],
 'opening_shares':793.970662,'opening_equity':4445.085799,
 'opening_intercompany':[137.30797819,354.63494228], 'debt_limit':[200.,50.,50.],
 'upstream_start':2,'special_start':10,'fund_call':62.5,'locked_deposits':[450.,0.,0.],'extra_wc':0.,'extra_wc_start':1,
 'entity_names':['上海华测导航技术股份有限公司','上海双微导航技术有限公司','武汉华测卫星技术有限公司'],
 'nonmodelled_assets':134.035546,'nonmodelled_asset_return':0.,
 'annual_minority':.002,'opening_ringfenced_minorities':12.22431,
}
def legal_add(balance,reserve,capital,profit):
    """Losses carried forward; only profit above prior loss can fund reserve."""
    gain=max(profit-max(-balance,0),0)
    allocation=min(.1*gain,max(.5*capital-reserve,0))
    return balance+profit-allocation,reserve+allocation,allocation

def simulate(p,n=350):
    p=copy.deepcopy(p); cash=p['opening_cash'][:]; debt=p['opening_debt'][:]
    legal=p['opening_legal'][:]; reserve=p['opening_reserve'][:]; capital=p['capital'][:]
    loans=p['opening_intercompany'][:]; shares=p['opening_shares'];equity=p['opening_equity']
    wc=p['opening_wc'];fixed=p['opening_fixed'];sales=p['sales'][0];rows=[]
    for y in range(1,n+1):
        locked=p['locked_deposits'][:] if y==1 else [0.,0.,0.]
        prior_cash=cash[:];prior_legal=legal[:];prior_equity=equity;prior_shares=shares
        if y<=5: sales=p['sales'][y-1];margin=p['margin'][y-1]
        else:
            fade=min((y-5)/(p['fade_end']-5),1.)
            growth=(p['sales'][4]/p['sales'][3]-1)*(1-fade)+p['terminal_growth']*fade
            sales*=1+growth;margin=p['margin'][4]*(1-fade)+p['terminal_margin']*fade
        new_wc=sales*p['wc_ratio']+(p['extra_wc'] if y>=p['extra_wc_start'] else 0.)
        new_fixed=sales*p['fixed_ratio']; da=fixed*.12;capex=da+new_fixed-fixed
        if capex<0: capex=0.;new_fixed=fixed-da
        dwc=new_wc-wc; net_reinvestment=capex-da+dwc
        cash_ebit=sales*margin; sbc=(p['sbc_expense'][y-1] if y<=5 else 0.)
        accounting_ebit=cash_ebit-sbc
        nopat=accounting_ebit*(1-p['tax'])
        addback=p['sbc_addback'][y-1] if y<=5 else 0.
        # Tax benefit is not assumed for share awards. SBC addback therefore net of no tax shield.
        operating_cf=cash_ebit*(1-p['tax'])-net_reinvestment
        financial=[c*p['cash_yield']*(1-p['tax']) for c in cash]
        interest=[d*p['debt_rate']*(1-p['tax']) for d in debt]
        minority=max(cash_ebit*(1-p['tax']),0)*p['annual_minority']
        profits=[nopat*w+financial[i]-interest[i] for i,w in enumerate(p['weights'])]
        profits[0]-=minority+sbc*p['tax'] # no tax shield for SBC
        ni=sum(profits)
        for i in range(3):
            cash_weight=p['cash_weights'][i] if y<=5 else p['weights'][i]
            cash[i]+=operating_cf*cash_weight+financial[i]-interest[i]
        fund_call=p['fund_call'] if y==1 else 0.
        cash[0]-=minority+fund_call
        issued=p['new_shares'][y-1] if y<=5 else 0.;proceeds=issued*(p['exercise_prices'][y-1] if y<=5 else 0)
        shares+=issued;capital[0]+=issued;cash[0]+=proceeds
        allocations=[]
        for i in range(3):
            legal[i],reserve[i],a=legal_add(legal[i],reserve[i],capital[i],profits[i]);allocations.append(a)
        floor=[sales*p['floor_ratio']*w+locked[i] for i,w in enumerate(p['floor_weights'])]
        principal=[min(d,p['opening_debt'][i]/3) if y<=3 else 0 for i,d in enumerate(debt)]
        newloans=[0.,0.];newborrow=[0.,0.,0.]
        # No shareholder cash injection with unidentified ownership: internal funding is a recorded loan.
        for i in (1,2):
            need=max(floor[i]+principal[i]-cash[i],0)
            give=min(need,max(cash[0]-floor[0]-principal[0],0))
            cash[0]-=give;cash[i]+=give;loans[i-1]+=give;newloans[i-1]=give
        for i in range(3):
            need=max(floor[i]+principal[i]-cash[i],0)
            borrow=min(need,max(p['debt_limit'][i]-debt[i],0));cash[i]+=borrow;debt[i]+=borrow;newborrow[i]=borrow
            if cash[i]+1e-8<principal[i]: raise ValueError('Zero dividend still cannot pay debt/operations: year %d entity %d'%(y,i))
            cash[i]-=principal[i];debt[i]-=principal[i]
            if cash[i]+1e-7<floor[i]:raise ValueError('Zero dividend cannot fund minimum operating liquidity')
        repay=[];declared=[];received=[]
        for i in (1,2):
            pay=min(loans[i-1],max(cash[i]-floor[i],0));loans[i-1]-=pay;cash[i]-=pay;cash[0]+=pay;repay.append(pay)
            # New dividends declared and paid in same annual budget. Opening dividend receivables = zero.
            div=min(max(legal[i],0),max(cash[i]-floor[i],0)) if y>=p['upstream_start'] else 0.
            legal[i]-=div;cash[i]-=div;cash[0]+=div
            legal[0],reserve[0],a=legal_add(legal[0],reserve[0],capital[0],div);allocations[0]+=a
            declared.append(div);received.append(div)
        target=max(ni,0)*p['payout'] if y<=5 else max(ni+max(addback,0)-max(net_reinvestment,0),0)
        ordinary=min(target,max(cash[0]-floor[0],0),max(legal[0],0))
        cash[0]-=ordinary;legal[0]-=ordinary
        # Additional retained financial principal is released only AFTER ordinary dividends consume legal profit.
        special=min(max(cash[0]-floor[0],0),max(legal[0],0)) if y>=p['special_start'] else 0.
        cash[0]-=special;legal[0]-=special;dist=ordinary+special
        equity+=ni+addback+proceeds-dist # equity-settled charge credit also increases capital reserve
        expected=sum(prior_cash)+operating_cf+sum(financial)-sum(interest)-minority-fund_call+proceeds+sum(newborrow)-sum(principal)-dist
        assert abs(sum(cash)-expected)<max(1e-6,abs(expected)*1e-12)
        assert min(cash+debt+loans)>=-1e-7
        assert all(reserve[i]<=capital[i]*.5+1e-7 for i in range(3))
        bps=equity/shares;prior_bps=prior_equity/prior_shares
        # Shareholder clean-surplus earnings include stock issue dilution, not whole-group profit alone.
        owner_earnings=(ni+addback+proceeds-prior_bps*issued)/shares
        assert abs(bps-prior_bps-owner_earnings+dist/shares)<1e-8
        rows.append(dict(year=y,sales=sales,margin=margin,cash_ebit=cash_ebit,accounting_ebit=accounting_ebit,
          net_profit=ni,sbc_expense=sbc,sbc_addback=addback,minority_cash=minority,da=da,capex=capex,
          working_capital=new_wc,fixed_assets=new_fixed,net_reinvestment=net_reinvestment,operating_cf=operating_cf,
          shares=shares,issued_shares=issued,issue_proceeds=proceeds,equity=equity,bps=bps,prior_bps=prior_bps,
          owner_earnings=owner_earnings,cash=cash[:],debt=debt[:],legal=legal[:],reserve=reserve[:],capital=capital[:],
          legal_profit_operating_financial=profits,legal_profit_upstream=[sum(declared),0.,0.],
          reserve_allocation=allocations,financial_income=financial,debt_interest=interest,principal=principal,
          new_borrowing=newborrow,intercompany_new_loans=newloans,intercompany_loans=loans[:],
          intercompany_principal_repaid=repay,subs_declared=declared,subs_received=received,old_dividend_receipts=0.,
          locked_deposits=locked,fund_call=fund_call,fund_parent_equity_injection_to_ningbo= fund_call,fund_ningbo_cash_paid_to_partnership=fund_call,fund_vehicle_capital_budget=100.+p['fund_call'],nonmodelled_investment_assets=p['nonmodelled_assets']+p['fund_call'],cash_floor=floor,ordinary=ordinary,special=special,distribution=dist,dps=dist/shares))
        wc=new_wc;fixed=new_fixed
    return rows

def value(rows,r,start=0):
    return sum(z['dps']/(1+r)**(z['year']-start) for z in rows if z['year']>start)
def residual_income(rows,r,start=0):
    b=rows[start]['prior_bps']
    return b+sum((z['owner_earnings']-r*z['prior_bps'])/(1+r)**(z['year']-start) for z in rows if z['year']>start)-rows[-1]['bps']/(1+r)**(len(rows)-start)
def case(p,n=350):
    rows=simulate(p,n);v={}
    for r in (.105,.10,.095):
        k=str(r);v[k]={'value':value(rows,r),'tv5':value(rows,r,5),'residual_income':residual_income(rows,r),
          'tv5_share_pv':value(rows,r,5)/(1+r)**5/value(rows,r)}
        assert abs(v[k]['value']-v[k]['residual_income'])<1e-7
    return {'parameters':p,'valuations':v,'rows':rows}
legacy_simulate=simulate
legacy_P=copy.deepcopy(P)

# Corrected cash sources: parent / domestic-source budget / other-source budget.
# The latter two are NOT legal entities. No synthetic registered capital or statutory pool.
P.update(source_names=['listed_parent','domestic_upstream_budget','other_upstream_budget'],
    parent_registered=793.970662,parent_statutory=327.13892023,
    parent_discretionary=0., voluntary_reserve_rate=0.,
    investment_recovery_year=10,investment_recovery_ratio=.8,investment_exit_cost=.02,
    upstream_lag=2,upstream_friction=.01,tax_renewal=True,
    tax_failure_year=1,old_dividend_receivable=0.,old_dividend_receipt_year=1,
    old_principal_recovery_year=1,exit_year=None,exit_cost=20.,exit_asset_recovery=.7)

def tax_cash(profit,rate):
    # No immediate refund and no cross-source loss offset. No unverified deferred asset.
    return max(profit,0.)*rate

class SettlementError(ValueError):
    """Uncompleted transaction. Snapshot preserves creditors and uncancelled equity."""
    def __init__(self,message,**state):
        super().__init__(message);self.state=state

def capital_recovery(cost,gross,fees,rate,ownership=1.):
    if min(cost,gross,fees)<0 or not 0<=ownership<=1:raise ValueError('invalid recovery inputs')
    # Fees are payable even when they exceed disposal proceeds. A negative cash
    # result must be funded by the holder; never silently forgive the shortfall.
    proceeds=(gross-fees)*ownership
    gain=(gross-fees-cost)*ownership
    tax=tax_cash(gain,rate)
    return {'principal':min(cost*ownership,max(proceeds,0.)),'accounting_gain':gain,
            'tax':tax,'net_cash':proceeds-tax}

def reduce_capital(cash,debt,costs,registered,shares,amount):
    if min(cash,debt,costs,registered,shares,amount)<0 or amount>=registered:
        raise ValueError('invalid continuing-company capital reduction; full exit uses liquidation')
    if cash-debt-costs < amount-1e-9:
        raise SettlementError('capital return creditors/fees not covered',cash=cash,debt=debt,
          unpaid_fees=costs,registered=registered,shares=shares,capital_return=0.)
    fraction=amount/registered
    # Debt is protected, not extinguished, by this continuing-company action.
    return cash-costs-amount,registered-amount,shares*(1-fraction)

def simulate(p,n=350):
    p=copy.deepcopy(p); cash=p['opening_cash'][:]; debt=p['opening_debt'][:]
    parent_legal=p['opening_legal'][0]; reserve=p['parent_statutory']; discretion=p['parent_discretionary']
    registered=p['parent_registered']; shares=p['opening_shares']; equity=p['opening_equity']
    loans=p['opening_intercompany'][:]; wc=p['opening_wc']; fixed=p['opening_fixed']; sales=p['sales'][0]
    queues=[[],[]]; cumulative_earnings=[0.,0.]; remitted=[0.,0.]; rows=[]
    investment=p['nonmodelled_assets']; receivable=p['old_dividend_receivable'];holder_units=1.
    for y in range(1,n+1):
        before=sum(cash); prior_equity=equity;prior_shares=shares;prior_bps=equity/shares*holder_units;prior_unit_bps=equity/shares;prior_units=holder_units
        if y<=5:sales=p['sales'][y-1];margin=p['margin'][y-1]
        else:
            fade=min((y-5)/(p['fade_end']-5),1.)
            sales*=1+(p['sales'][4]/p['sales'][3]-1)*(1-fade)+p['terminal_growth']*fade
            margin=p['margin'][4]*(1-fade)+p['terminal_margin']*fade
        new_wc=sales*p['wc_ratio']+(p['extra_wc'] if y>=p['extra_wc_start'] else 0.)
        da=fixed*.12; capex=max(da+sales*p['fixed_ratio']-fixed,0.);new_fixed=fixed+capex-da
        reinvest=capex-da+new_wc-wc; ebit=sales*margin
        sbc=p['sbc_expense'][y-1] if y<=5 else 0.
        addback=p['sbc_addback'][y-1] if y<=5 else 0.
        taxrate=p['tax'] if p['tax_renewal'] or y<p['tax_failure_year'] else .25
        financial=[c*p['cash_yield'] for c in cash];interest=[d*p['debt_rate'] for d in debt]
        pretax=[ebit*w+financial[i]-interest[i] for i,w in enumerate(p['weights'])]
        taxes=[tax_cash(a,taxrate) for a in pretax]
        profits=[a-taxes[i]-sbc*p['weights'][i] for i,a in enumerate(pretax)]
        minority=max(ebit-tax_cash(ebit,taxrate),0)*p['annual_minority']; profits[0]-=minority
        operating_cf=ebit-tax_cash(ebit,taxrate)-reinvest
        for i in range(3):
            cw=p['cash_weights'][i] if y<=5 else p['weights'][i]
            # Economic allocation shares sum to one; source-specific taxes and minority retained.
            cash[i]+=ebit*p['weights'][i]-reinvest*cw+financial[i]-interest[i]-taxes[i]
        cash[0]-=minority
        fund_call=p['fund_call'] if y==1 else 0.;cash[0]-=fund_call;investment+=fund_call
        recovered={'principal':0.,'accounting_gain':0.,'tax':0.,'net_cash':0.}
        if y==p['investment_recovery_year']:
            gross=investment*p['investment_recovery_ratio']
            recovered=capital_recovery(investment,gross,gross*p['investment_exit_cost'],taxrate)
            if cash[0]+recovered['net_cash']<0:
                raise SettlementError('investment exit fees unpaid',cash=cash[:],debt=debt[:],
                  unpaid_fees=-(cash[0]+recovered['net_cash']),registered=registered,shares=shares,
                  investment=investment,capital_return=0.)
            cash[0]+=recovered['net_cash'];profits[0]+=recovered['accounting_gain']-recovered['tax'];investment=0.
        old_receipt=receivable if y==p['old_dividend_receipt_year'] else 0.
        receivable-=old_receipt;cash[0]+=old_receipt # never added to earnings / statutory profit
        issued=p['new_shares'][y-1] if y<=5 else 0.;proceeds=issued*(p['exercise_prices'][y-1] if y<=5 else 0.)
        shares+=issued;registered+=issued;cash[0]+=proceeds
        capital_cost=p.get('capital_return_cost',0.) if p.get('capital_return_year')==y else 0.
        if capital_cost<0:raise ValueError('negative capital return fee')
        if cash[0]<capital_cost:
            raise SettlementError('capital return fees unpaid',cash=cash[:],debt=debt[:],
              unpaid_fees=capital_cost,registered=registered,shares=shares,capital_return=0.)
        cash[0]-=capital_cost;profits[0]-=capital_cost # no unverified immediate tax refund
        prior_parent_legal=parent_legal
        parent_legal,reserve,allocation=legal_add(parent_legal,reserve,registered,profits[0])
        optional=max(profits[0]-max(-prior_parent_legal,0)-allocation,0)*p['voluntary_reserve_rate']
        parent_legal-=optional;discretion+=optional
        for j in range(2):
            cumulative_earnings[j]+=profits[j+1];queues[j].append([y,profits[j+1]])
        locked=p['locked_deposits'] if y==1 else [0.,0.,0.]
        floor=[sales*p['floor_ratio']*w+locked[i] for i,w in enumerate(p['floor_weights'])]
        principal=[min(d,p['opening_debt'][i]/3) if y<=3 else 0. for i,d in enumerate(debt)]
        newloans=[0.,0.];borrow=[0.,0.,0.]
        for i in (1,2):
            need=max(floor[i]+principal[i]-cash[i],0.)
            give=min(need,max(cash[0]-floor[0]-principal[0],0.))
            cash[0]-=give;cash[i]+=give;loans[i-1]+=give;newloans[i-1]=give
        for i in range(3):
            borrow[i]=min(max(floor[i]+principal[i]-cash[i],0),max(p['debt_limit'][i]-debt[i],0))
            cash[i]+=borrow[i];debt[i]+=borrow[i];cash[i]-=principal[i];debt[i]-=principal[i]
            if cash[i]<floor[i]-1e-7:
                raise SettlementError('zero dividend cannot fund operations/creditors year '+str(y),
                  cash=cash[:],debt=debt[:],unpaid_fees=0.,registered=registered,shares=shares,
                  capital_return=0.,cash_shortfall=floor[i]-cash[i])
        repayments=[];upstream=[];frictions=[];capacity=[]
        for i in (1,2):
            j=i-1;pay=min(loans[j],max(cash[i]-floor[i],0)) if y>=p['old_principal_recovery_year'] else 0.
            loans[j]-=pay;cash[i]-=pay;cash[0]+=pay;repayments.append(pay)
            # Mature earnings are an economic remittability BUDGET, not a pooled legal surplus.
            effective_lag=(p.get('upstream_lag_after_recovery',2) if y>=p.get('upstream_lag_recovery_year',10**9) else p['upstream_lag'])
            matured=sum(v for t,v in queues[j] if t<=y-effective_lag)
            cap=max(min(matured,cumulative_earnings[j])-remitted[j],0.)
            div=min(cap,max(cash[i]-floor[i],0.)) if y>=p['upstream_start'] else 0.
            friction=div*p['upstream_friction'];cash[i]-=div;cash[0]+=div-friction;remitted[j]+=div
            parent_legal,reserve,a=legal_add(parent_legal,reserve,registered,div-friction);allocation+=a
            upstream.append(div);frictions.append(friction);capacity.append(cap)
        ni=sum(profits)-sum(frictions)
        target=max(ni,0)*p['payout'] if y<=5 else max(ni+max(addback,0)-max(reinvest,0),0.)
        ordinary=min(target,max(cash[0]-floor[0],0),max(parent_legal,0))
        if p['exit_year']==y:ordinary=0.
        cash[0]-=ordinary;parent_legal-=ordinary
        special=min(max(cash[0]-floor[0],0),max(parent_legal,0)) if y>=p['special_start'] else 0.
        if p['exit_year']==y:special=0.
        cash[0]-=special;parent_legal-=special;dist=ordinary+special
        pre_reduction_shares=shares
        capital_return=0.
        if p.get('capital_return_year')==y:
            capital_return=p['capital_return_amount']
            if p['exit_year']==y:raise ValueError('choose capital reduction or liquidation, not both')
            try:
                cash[0],registered,shares=reduce_capital(cash[0],sum(debt)+floor[0],0.,registered,shares,capital_return)
            except SettlementError as e:
                e.state.update(debt=debt[:],protected_operating_cash=floor[0],paid_fees=capital_cost,
                  parent_legal=parent_legal,equity_before_distribution=prior_equity+ni+addback+proceeds,
                  proposed_capital_return=capital_return)
                raise
            holder_units*=shares/pre_reduction_shares
            dist+=capital_return
        exit_detail=None
        if p['exit_year']==y:
            # Conditional economic orderly exit, NOT a claim that group assets
            # are a single legal liquidation estate. Source taxes cannot offset losses.
            asset_book=new_wc+new_fixed
            disposal=asset_book*p['exit_asset_recovery']
            inv=capital_recovery(investment,investment*p['investment_recovery_ratio'],
              investment*p['investment_recovery_ratio']*p['investment_exit_cost'],taxrate)
            gain=disposal-asset_book-p['exit_cost']
            exit_taxes=[tax_cash(gain*w,taxrate) for w in p['weights']]
            available=sum(cash)+disposal+inv['net_cash']+receivable
            exitcash=available-p['exit_cost']-sum(exit_taxes)-sum(debt)
            if exitcash<0:
                # Do not set debt, registered capital or shares to zero on failure.
                raise SettlementError('exit creditors/fees unpaid',cash=cash[:],debt=debt[:],
                  unpaid_debt=max(sum(debt)-available,0.),
                  unpaid_fees=max(p['exit_cost']+sum(exit_taxes)-max(available-sum(debt),0.),0.),
                  registered=registered,shares=shares,capital_return=capital_return,
                  exit_distribution=0.,asset_book=asset_book,investment=investment)
            exit_profit=gain-sum(exit_taxes)+inv['accounting_gain']-inv['tax']
            ni+=exit_profit
            parent_legal+=gain*p['weights'][0]-exit_taxes[0]+inv['accounting_gain']-inv['tax']
            exit_detail=dict(disposal=disposal,asset_book=asset_book,fees=p['exit_cost'],
              taxes=exit_taxes,investment=inv,receivable=receivable,debt_paid=sum(debt),
              net_cash=exitcash,accounting_profit=exit_profit)
            dist+=exitcash;cash=[0.,0.,0.];debt=[0.,0.,0.];investment=0.;receivable=0.
        equity+=ni+addback+proceeds-dist
        expected=before+ebit-reinvest+sum(financial)-sum(interest)-sum(taxes)-minority-fund_call+recovered['net_cash']+old_receipt+proceeds+sum(borrow)-sum(principal)-sum(frictions)-ordinary-special-capital_return-capital_cost
        if p['exit_year']!=y:assert abs(sum(cash)-expected)<max(1e-6,abs(expected)*1e-12)
        assert min(cash+debt+loans)>=-1e-7
        earnings=(ni+addback+proceeds-prior_unit_bps*issued)/pre_reduction_shares*prior_units
        holder_dps=dist/pre_reduction_shares*prior_units
        assert abs(equity/shares*holder_units-prior_bps-earnings+holder_dps)<1e-8
        rows.append(dict(year=y,sales=sales,margin=margin,ebit=ebit,pretax=pretax,taxes=taxes,taxrate=taxrate,
          net_profit=ni,source_profits=profits,minority_cash=minority,financial_income=financial,debt_interest=interest,
          da=da,capex=capex,working_capital=new_wc,fixed_assets=new_fixed,net_reinvestment=reinvest,operating_cf=operating_cf,
          cash=cash[:],debt=debt[:],cash_floor=floor,principal=principal,new_borrowing=borrow,
          intercompany_new_loans=newloans,intercompany_loans=loans[:],intercompany_principal_repaid=repayments,
          parent_legal=parent_legal,parent_statutory=reserve,parent_discretionary=discretion,reserve_allocation=allocation,
          parent_registered_budget=registered,source_cumulative_earnings=cumulative_earnings[:],source_remitted=remitted[:],
          source_matured_capacity=capacity,subs_declared_budget=upstream,upstream_friction=frictions,
          old_dividend_receipts=old_receipt,old_dividend_receivable=receivable,
          investment_asset=investment,investment_recovery=recovered,fund_call=fund_call,
          shares=shares,issued_shares=issued,issue_proceeds=proceeds,equity=equity,bps=equity/shares*holder_units,prior_bps=prior_bps,holder_units=holder_units,capital_return=capital_return,
          owner_earnings=earnings,ordinary=ordinary,special=special,distribution=dist,dps=holder_dps,
          capital_return_cost=capital_cost,exit_detail=exit_detail))
        if p['exit_year']==y:break
        wc=new_wc;fixed=new_fixed
    return rows

def corrected_tests():
    checks={}
    checks['registered_not_paid']=legal_add(0,5,20,10)==(9,6,1)
    checks['loss_first']=legal_add(-10,0,100,30)==(18,2,2)
    checks['full_reserve']=legal_add(0,10,20,10)==(10,10,0)
    checks['new_registered']=legal_add(0,10,40,10)==(9,11,1)
    checks['no_loss_refund']=tax_cash(-100,.25)==0
    q=copy.deepcopy(P);q.update(sales=[100]*5,margin=[.2]*5,wc_ratio=0.,fixed_ratio=0.,opening_wc=0.,opening_fixed=0.,tax=0.,cash_yield=0.,debt_rate=0.,opening_cash=[0.,0.,0.],opening_debt=[0.,0.,0.],opening_legal=[0.,0.,0.],parent_statutory=0.,parent_registered=0.,weights=[1.,0.,0.],cash_weights=[1.,0.,0.],floor_ratio=0.,new_shares=[0.]*5,opening_shares=10.,opening_equity=0.,opening_intercompany=[0.,0.],annual_minority=0.,payout=1.,fund_call=0.,locked_deposits=[0.,0.,0.],nonmodelled_assets=0.)
    a=simulate(q,5);manual=2*sum(1/1.1**i for i in range(1,6))
    checks['formal_function_annuity']=abs(value(a,.1)-manual)<1e-10
    z=copy.deepcopy(q);z.update(old_dividend_receivable=10.)
    b=simulate(z,1)[0];checks['old_receipt_not_profit']=b['net_profit']==20 and b['parent_legal']==0 and b['cash'][0]==10
    z=copy.deepcopy(q);z.update(margin=[-1]*5,debt_limit=[0.,0.,0.])
    try:simulate(z,1);checks['zero_dividend_failure']=False
    except ValueError:checks['zero_dividend_failure']=True
    rec=capital_recovery(100,100,5,.25,.6)
    checks['cost_recovery_not_profit']=rec=={'principal':57.,'accounting_gain':-3.,'tax':0.,'net_cash':57.}
    checks['capital_reduction_shares']=reduce_capital(200,50,10,100,10,40)==(150,60,6)
    try:reduce_capital(20,30,0,100,10,10);checks['unpaid_exit_fails']=False
    except ValueError:checks['unpaid_exit_fails']=True
    z=copy.deepcopy(q);z.update(opening_cash=[100.,0.,0.],opening_debt=[80.,0.,0.],exit_year=1,exit_cost=200.)
    try:simulate(z,1);checks['formal_simulate_unpaid_exit_fails']=False
    except ValueError:checks['formal_simulate_unpaid_exit_fails']=True
    z=copy.deepcopy(q);z.update(opening_cash=[100.,0.,0.],opening_debt=[20.,0.,0.],exit_year=1,exit_cost=5.)
    end=simulate(z,1)[0]
    checks['formal_simulate_exit_after_creditors']=abs(end['distribution']-95.)<1e-9
    z=copy.deepcopy(q);z.update(margin=[0.]*5,opening_cash=[100.,0.,0.],opening_equity=100.,parent_registered=100.,capital_return_year=1,capital_return_amount=40.)
    capitalcase=simulate(z,1)[0]
    checks['formal_profit_zero_capital_return']=capitalcase['net_profit']==0 and capitalcase['parent_legal']==0 and capitalcase['shares']==6 and capitalcase['dps']==4 and capitalcase['holder_units']==.6
    assert all(checks.values()),checks
    return {'checks':checks,'annuity_literal':manual,'capital_recovery_case':rec}

def boundary_tests():
    q=copy.deepcopy(P)
    q.update(sales=[100.]*5,margin=[0.]*5,wc_ratio=0.,fixed_ratio=0.,opening_wc=0.,opening_fixed=0.,
      tax=.25,cash_yield=0.,debt_rate=0.,opening_cash=[100.,0.,0.],opening_debt=[0.,0.,0.],
      opening_legal=[0.,0.,0.],parent_statutory=0.,parent_registered=100.,weights=[1.,0.,0.],
      cash_weights=[1.,0.,0.],floor_ratio=0.,new_shares=[0.]*5,opening_shares=10.,opening_equity=100.,
      opening_intercompany=[0.,0.],annual_minority=0.,payout=0.,fund_call=0.,
      locked_deposits=[0.,0.,0.],nonmodelled_assets=0.,debt_limit=[0.,0.,0.])
    checks={};samples={}
    def test(name,changes,expect):
        p=copy.deepcopy(q);p.update(changes);row=simulate(p,1)[0]
        for key,want in expect.items():
            got=row[key]
            assert abs(got-want)<1e-8,(name,key,got,want)
        checks[name]=True;samples[name]=row
    test('fee_cash_legal_equity_shares',dict(capital_return_year=1,capital_return_amount=40.,capital_return_cost=10.),
      dict(net_profit=-10.,parent_legal=-10.,equity=50.,shares=6.,holder_units=.6,dps=4.,bps=5.))
    assert samples['fee_cash_legal_equity_shares']['cash']==[50.,0.,0.]
    test('fee_precedes_legal_reserve_no_unverified_tax_shield',dict(margin=[.2]*5,capital_return_year=1,capital_return_amount=40.,capital_return_cost=10.),
      dict(net_profit=5.,parent_legal=4.5,parent_statutory=.5,equity=65.,shares=6.))
    test('opening_wc_release_not_profit',dict(opening_wc=10.,opening_equity=110.),dict(net_profit=0.,equity=110.,net_reinvestment=-10.))
    assert samples['opening_wc_release_not_profit']['cash']==[110.,0.,0.]
    test('investment_fee_exceeds_gross_funded',dict(opening_cash=[20.,0.,0.],opening_equity=120.,nonmodelled_assets=100.,investment_recovery_year=1,investment_recovery_ratio=.05,investment_exit_cost=2.),
      dict(net_profit=-105.,parent_legal=-105.,equity=15.))
    assert samples['investment_fee_exceeds_gross_funded']['cash']==[15.,0.,0.]
    test('exit_wc_debt_fee',dict(opening_wc=10.,opening_debt=[20.,0.,0.],opening_equity=90.,exit_year=1,exit_cost=5.),dict(distribution=85.,net_profit=-5.,equity=0.))
    test('exit_positive_gain_cash_tax',dict(opening_fixed=100.,fixed_ratio=1.,opening_cash=[200.,0.,0.],opening_equity=300.,exit_year=1,exit_asset_recovery=1.5,exit_cost=10.),
      dict(distribution=330.,net_profit=30.,equity=0.))
    for name,changes in {
      'recovery_fee_shortfall':dict(opening_cash=[0.,0.,0.],nonmodelled_assets=100.,investment_recovery_year=1,investment_recovery_ratio=.05,investment_exit_cost=2.),
      'capital_return_creditor_shortfall':dict(opening_debt=[80.,0.,0.],capital_return_year=1,capital_return_amount=40.,capital_return_cost=10.),
      'exit_fee_shortfall':dict(exit_year=1,exit_cost=200.)}.items():
        p=copy.deepcopy(q);p.update(changes)
        try:simulate(p,1)
        except SettlementError as e:
            assert e.state['shares']==10. and e.state['registered']==100.
            assert e.state.get('exit_distribution',0.)==0.
            checks[name]=True;samples[name]=e.state
        else:raise AssertionError(name)
    rec=capital_recovery(100.,5.,10.,.25,.6)
    assert rec==dict(principal=0.,accounting_gain=-63.,tax=0.,net_cash=-3.)
    checks['ownership_fee_shortfall_no_refund']=True;samples['ownership_fee_shortfall_no_refund']=rec
    assert reduce_capital(200.,50.,10.,100.,10.,40.)==(150.,60.,6.)
    try:reduce_capital(20.,30.,10.,100.,10.,5.)
    except SettlementError as e:
        assert e.state==dict(cash=20.,debt=30.,unpaid_fees=10.,registered=100.,shares=10.,capital_return=0.)
        checks['function_failed_debt_fee_equity_preserved']=True;samples['function_failed_debt_fee_equity_preserved']=e.state
    else:raise AssertionError('failed settlement')
    return dict(checks=checks,samples=samples)

def parameters():
    d={'base':copy.deepcopy(P)}
    variants={
      'cyclical':dict(sales=[3100,3300,3900,4500,5000],margin=[.07,.10,.14,.16,.17],extra_wc=200.),
      'structural':dict(sales=[3400,3500,3600,3700,3800],margin=[.08,.085,.09,.09,.09],terminal_margin=.08,terminal_growth=.01,wc_ratio=.48,fixed_ratio=.24),
      'upside':dict(sales=[3800,4400,5100,5800,6500],margin=[.145,.17,.18,.19,.19],terminal_margin=.16,wc_ratio=.37,fixed_ratio=.21),
      'normalized_earnings_power_year3':dict(sales=[3600,4000,4400,4488,4577.76],margin=[.13,.15,.16,.16,.16],terminal_margin=.16),
      'terminal_margin_minus2pt_from_year6':dict(terminal_margin=.125),
      'receivable_delay_300_from_year1':dict(extra_wc=300.),
      'parent_cash_upstream_delay':dict(upstream_start=6,upstream_lag=5,weights=[.65,.175,.175],cash_weights=[.60,.20,.20]),
      'upstream_delay_recovers_year15':dict(upstream_start=6,upstream_lag=5,weights=[.65,.175,.175],cash_weights=[.60,.20,.20],upstream_lag_recovery_year=15,upstream_lag_after_recovery=2),
      'retained_principal_release_year15':dict(special_start=15,investment_recovery_year=15),
      'all_rights_exercise_conditional_diagnostic':dict(new_shares=[12.,7.,6.67055,0.,0.],exercise_prices=[16.5,25.5,24.9,0.,0.]),
      'tax_preference_not_renewed':dict(tax_renewal=False),
      'investment_recovery_full':dict(investment_recovery_ratio=1.),
      'investment_recovery_half':dict(investment_recovery_ratio=.5),
      'upstream_friction_5pct':dict(upstream_friction=.05),
      'voluntary_reserve_10pct':dict(voluntary_reserve_rate=.1),
      'registered_change_delayed':dict(parent_registered=786.892451),
      'minority_2pct':dict(annual_minority=.02)}
    for name,changes in variants.items():q=copy.deepcopy(P);q.update(changes);d[name]=q
    return d

def main():
    import gzip,hashlib,sys,base64
    root=Path(__file__).parent
    if '--expand' in sys.argv:
        pos=sys.argv.index('--expand')
        target=Path(sys.argv[pos+1]) if len(sys.argv)>pos+1 else root/'2026-Q3-output.full.json'
        packed=root/'2026-Q3-output.json'
        if target.resolve()==packed.resolve():raise ValueError('expanded target must not overwrite the packed output')
        wrapper=json.loads(packed.read_text(encoding='utf-8'))
        if wrapper['format']!='gzip-base64-json-v1':raise ValueError('unsupported packed output format')
        compressed=base64.b64decode(wrapper['payload_base64'],validate=True)
        raw=gzip.decompress(compressed)
        if hashlib.sha256(raw).hexdigest()!=wrapper['payload_sha256'] or len(raw)!=wrapper['payload_bytes']:
            raise ValueError('full output integrity mismatch')
        target.write_bytes(raw);print(target);return
    out={'unit':'CNY million, million shares; per share CNY','method':'Parent legal account plus economic upstream capacity budgets (NOT synthetic legal entities)','manual_tests':corrected_tests(),'boundary_tests':boundary_tests(),'cases':{}}
    for name,p in parameters().items():out['cases'][name]=case(p)
    # Same growth, margin, capital needs, financing and ownership as legacy; isolate accounting/method changes.
    bridge=[]
    for name,p in parameters().items():
        if name not in ['base','cyclical','structural','upside','terminal_margin_minus2pt_from_year6','receivable_delay_300_from_year1','parent_cash_upstream_delay','retained_principal_release_year15']:continue
        old=legacy_simulate(p);new=out['cases'][name]['rows']
        accounting_only=copy.deepcopy(p);accounting_only.update(investment_recovery_year=10000,upstream_friction=0.)
        stage=simulate(accounting_only)
        bridge.append({'case':name,'old_pv':value(old,.1),'new_pv':value(new,.1),'old_tv5':value(old,.1,5),'new_tv5':value(new,.1,5),
          'all_discount_rates':{str(r):{'old_pv':value(old,r),'old_tv5':value(old,r,5),'new_pv':value(new,r),'new_tv5':value(new,r,5),'method_only_pv':value(stage,r),'new_recovery_and_friction_increment':value(new,r)-value(stage,r)} for r in [.095,.10,.105]},
          'method_only_rows':stage,
          'old_dps':[x['dps'] for x in old[:5]],'new_dps':[x['dps'] for x in new[:5]],'old_rows':old,
          'annual_effect':[{'year':a['year'],'cash_delta':[b['cash'][i]-a['cash'][i] for i in range(3)],'parent_legal_delta':b['parent_legal']-a['legal'][0],'dps_delta':b['dps']-a['dps']} for a,b in zip(old,new)]})
    out['same_economic_budget_bridge']=bridge
    # New investment recovery assumption is separately removed; don't mislabel forecast uplift as legal correction.
    z=copy.deepcopy(P);z.update(investment_recovery_year=10000,upstream_friction=0.)
    out['bridge_without_new_recovery_or_friction_assumptions']=case(z)
    long=simulate(P,450);base=out['cases']['base'];low=out['cases']['retained_principal_release_year15']
    out['long_integration_rows']=long
    out['all_case_tail_checks']={name:{'pv_350':value(c['rows'],.095),'pv_450':value(simulate(c['parameters'],450),.095),'last_cash_above_floor':[a-b for a,b in zip(c['rows'][-1]['cash'],c['rows'][-1]['cash_floor'])],'investment_remaining':c['rows'][-1]['investment_asset'],'max_new_debt':max(sum(z['new_borrowing']) for z in c['rows']),'min_parent_legal':min(z['parent_legal'] for z in c['rows'])} for name,c in out['cases'].items()}
    assert all(abs(v['pv_450']-v['pv_350'])<1e-7 for v in out['all_case_tail_checks'].values())
    out['integration_check']={str(r):value(long,r)-value(base['rows'],r) for r in [.095,.105]}
    out['core']={'low':round(low['valuations']['0.105']['value'],2),'high':round(base['valuations']['0.095']['value'],2),
      'dps':[round(x['dps'],6) for x in base['rows'][:5]],'tv5_low':round(low['valuations']['0.105']['tv5'],2),'tv5_high':round(base['valuations']['0.095']['tv5'],2)}
    raw=(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
    compressed=gzip.compress(raw,mtime=0)
    summary={'core':out['core'],'manual_tests':out['manual_tests'],'integration_check':out['integration_check'],
      'cases':{k:{'value10':v['valuations']['0.1']['value'],'dps':[x['dps'] for x in v['rows'][:5]],'tv5':v['valuations']['0.1']['tv5'],'max_debt':max(sum(x['debt']) for x in v['rows'])} for k,v in out['cases'].items()},
      'output_uncompressed_sha256':hashlib.sha256(raw).hexdigest(),'uncompressed_bytes':len(raw),'gzip_bytes':len(compressed)}
    wrapper={
      'format':'gzip-base64-json-v1','schema_version':1,
      'description':'华测导航2026-Q3：可读摘要与完整无损年度输出。payload解码后保留全部18情景、350年行、450年尾期、桥和测试，不删除或重算字段。',
      'summary':summary,
      'schema':{'payload_encoding':'base64(gzip(canonical UTF-8 JSON)); gzip mtime=0',
        'canonicalization':'json.dumps(ensure_ascii=False, sort_keys=True, separators=(comma,colon)) plus LF',
        'cases':'18 complete paths; each parameters, valuations and 350 annual rows',
        'long_integration_rows':'450 annual base rows',
        'all_case_tail_checks':'all 18 paths 350/450 valuation convergence',
        'same_economic_budget_bridge':'8 historical comparison paths with full old/method-only rows and annual effects',
        'manual_tests':'original same-function manual cases',
        'boundary_tests':'11 same-function fee, tax, creditor, initial working-capital and equity-state cases',
        'expand':'python 2026-Q3.py --expand [target]; default 2026-Q3-output.full.json'},
      'payload_sha256':hashlib.sha256(raw).hexdigest(),'payload_bytes':len(raw),
      'gzip_sha256':hashlib.sha256(compressed).hexdigest(),'gzip_bytes':len(compressed),
      'payload_base64':base64.b64encode(compressed).decode('ascii')}
    root.joinpath('2026-Q3-output.json').write_text(json.dumps(wrapper,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    root.joinpath('summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary['core']))
if __name__=='__main__':main()

#!/usr/bin/env python3
"""CN002315 owner cash model. CNY million / million shares. stdlib only.
Entity allocations are explicit budget assumptions, not unpublished subsidiary accounts.
No quotation or IRR. Year 1 is next twelve months after 2026-10-26.
"""
import json, math, copy, gzip, base64, hashlib, sys
from pathlib import Path
ASOF='2026-10-26T16:45:00+08:00'
N0=413.375586
# Financial asset bridge: CA is not cash. Reserve cash includes customer settlement excluded at outset.
BRIDGE={'cash_equivalents':727.782733,'customer_money_excluded':223.0,'noncash_deposits':713.668442,'cd_after_CA':1561.298925,'trading_assets':192.062255,'treasury':50.045760,'equities':792.818599,'other_financial':4.000974,'loans':31.117926,'associates':57.237025,'restricted_excluded':12.325576,'existing_tax_and_legacy_obligations_excluded':55.0}
# Accountable allocation budget: all group financial resources allocated, no unsupported cash upstream.
TOTAL=sum(BRIDGE[k] for k in ('cash_equivalents','noncash_deposits','cd_after_CA','trading_assets','treasury','equities','other_financial','loans','associates'))-223-12.325576-55
P_DEP=2100.; P_EQ=620.; L_DEP=220.; P_ASSOC=49.17621371; S_EQ=172.818599+57.237025+4.000974-P_ASSOC
S_DEP=TOTAL-500.-4.782733-P_DEP-P_EQ-L_DEP-S_EQ-P_ASSOC
SCENARIOS={
 'base':dict(mic=[1990,2150,2320,2490,2640],ai=[105,130,155,178,200],other=[230,235,240,245,250],margin=[.313,.319,.324,.328,.330],cl=[.68,.68,.68,.67,.66],subs=[-25,-18,-10,-5,0],tax=.15,cap=.018,after_growth=.06,stable=.025,exercise=True),
 'cyclical':dict(mic=[1800,1810,1950,2130,2300],ai=[90,100,115,135,155],other=[210,210,220,230,240],margin=[.275,.270,.295,.310,.320],cl=[.64,.62,.64,.65,.65],subs=[-40,-35,-20,-10,-5],tax=.17,cap=.018,after_growth=.05,stable=.02,exercise=False),
 'structural':dict(mic=[1750,1550,1400,1280,1200],ai=[80,65,55,50,45],other=[200,180,165,150,140],margin=[.23,.18,.14,.12,.10],cl=[.58,.50,.44,.40,.38],subs=[-50,-45,-35,-25,-15],tax=.20,cap=.022,after_growth=-.02,stable=0.,exercise=False),
 'optimistic':dict(mic=[2070,2340,2630,2920,3210],ai=[120,165,220,285,350],other=[240,255,270,285,300],margin=[.32,.335,.345,.355,.36],cl=[.70,.71,.71,.70,.69],subs=[-20,-10,0,8,15],tax=.15,cap=.021,after_growth=.07,stable=.03,exercise=True)}

def legal_profit(old,profit,reserve,capital,continue_reserve=False):
    # Loss carryforward never reset. Reserve only on profit after fully covering old losses.
    eligible=max(0.,profit+min(old,0.))
    provision=.10*eligible if continue_reserve else min(.10*eligible,max(0.,.5*capital-reserve))
    return old+profit-provision,reserve+provision,provision

def cash_year(st,revenue,margin,tax,capex,da,wc,minimum,financial_interest=0.,mature=0.,sale=0.,sale_book=0.,borrow_limit=0.,desired=0.,receipt=0.,declared_income=0.,support=0.,new_equity=0.,capital_increase=0.,financial_cash=None,noncash_charge=0.,continue_reserve=False,corporate_action_cost=0.):
    """Same formal earnings->capital->cash->legal distribution chain used by every case."""
    o=copy.deepcopy(st); oldcash=st['cash']; olddebt=st['debt']
    interest_cost=olddebt*.05
    operating_ebit=revenue*margin
    pretax=operating_ebit+financial_interest-interest_cost
    tax_paid=max(0.,pretax)*tax+max(0.,sale-sale_book)*.25
    # Realized investment gain/loss counted once; receipt of old dividend not new earnings.
    profit=pretax-tax_paid+(sale-sale_book)+declared_income-noncash_charge-corporate_action_cost
    if st['capital'] is None:
      # S is an economic remittance hurdle, never a statutory company pool.
      re,reserve,provision=st['re']+profit,0.,0.
    else:re,reserve,provision=legal_profit(st['re'],profit,st['reserve'],st['capital']+capital_increase,continue_reserve)
    financial_cash=financial_interest if financial_cash is None else financial_cash
    operating_cash=operating_ebit+financial_cash-interest_cost-tax_paid+da-capex-(wc-st['wc'])-corporate_action_cost
    available=oldcash+operating_cash+mature+sale+receipt+new_equity-support
    debt_draw=min(max(0.,minimum-available),max(0.,borrow_limit-olddebt))
    available+=debt_draw
    if available < minimum-1e-7: raise ValueError('financing infeasible even with zero dividend')
    repay=min(max(0.,available-minimum),olddebt+debt_draw)
    available-=repay
    payout=max(0.,min(desired,re,available-minimum))
    o.update(cash=available-payout,debt=olddebt+debt_draw-repay,re=re-payout,reserve=reserve,wc=wc,capital=(st['capital']+capital_increase if st['capital'] is not None else None))
    assert o['cash']>=-1e-7 and o['re']>=min(re,0.)-1e-7
    cash_error=o['cash']-(oldcash+operating_cash+mature+sale+receipt+new_equity-support+debt_draw-repay-payout)
    assert abs(cash_error)<1e-7
    return o,dict(corporate_action_cost=corporate_action_cost,ebit=operating_ebit,profit=profit,tax=tax_paid,interest_cost=interest_cost,financial_interest=financial_interest,financial_cash=financial_cash,ocf_after_capex=operating_cash,delta_wc=wc-st['wc'],minimum=minimum,maturity=mature,sale=sale,receipt=receipt,declared_income=declared_income,support=support,equity_cash=(new_equity if st['capital'] is not None else None),funding_cash=new_equity,debt_draw=debt_draw,repayment=repay,distribution=payout,cash=o['cash'],debt=o['debt'],capacity_budget=o['re'],reserve_budget=(o['reserve'] if o['capital'] is not None else None),registered_capital_budget=o['capital'],actual_legal_retained=None,actual_statutory_reserve=None,scope=('economic_remittance_budget_not_legal_person' if o['capital'] is None else 'named_legal_person_forecast_budget'),reserve_charge=provision,cash_error=cash_error)


# Consolidated source-informed operating funding envelope, allocated to P for
# cash budgeting only. NOT a disclosed Q3 statutory parent balance.
OPENING_OPERATING_ASSETS={'bills':16.46805266,'accounts':11.13009779,'prepayments':6.42775631,'other_receivables_ex_interest':14.85441390-.35618504,'inventory':2.82887070,'current_maturing_commissions':105.02844406,'other_current_assets':20.59768442,'long_commissions_H1_proxy':24.84393786}
OPENING_ORDINARY_CREDITORS={'trade_payables':54.12300168,'payroll':57.38578862,'taxes':56.43644598,'rent_advances':.91897749,'other_current_tax':5.31752236}
OPENING_NOA=sum(OPENING_OPERATING_ASSETS.values())-sum(OPENING_ORDINARY_CREDITORS.values())
NORMALIZED_OPENING_NOA=.045*2134.324686
LEGACY_HEADROOM=55.-43.79557263

def initial(opening_noa=OPENING_NOA):
    return dict(P=dict(cash=500.,debt=1.5,re=1300.,reserve=186.36459629,capital=N0,wc=-(1229.590007+258.957197)+opening_noa),
      S=dict(cash=4.782733,debt=0.,re=-650.,reserve=0.,capital=None,wc=0.),
      L=dict(cash=0.,debt=0.,re=0.,reserve=0.,capital=200.,wc=0.))

def public_states(states):
    return {k:{'cash':v['cash'],'debt':v['debt'],'working_capital_budget':v['wc'],
      'distribution_capacity_budget':v['re'],'reserve_budget':v['reserve'] if k!='S' else None,
      'registered_capital_budget':v['capital'],'actual_Q3_statutory_reserve':None,
      'actual_Q3_legal_retained':None,'actual_Q3_paid_in_capital':None,
      'scope':'multi_jurisdiction_economic_hurdle_not_legal_person' if k=='S' else 'named_legal_person_forecast_budget'} for k,v in states.items()}

def run(name='base',stable=None,delay=0,margin_shift=0.,parent_cash_shift=0.,sub_upstream=True,sub_loss=-650.,deposit_shift=0.,opening_re=1300.,max_year=80,impairment_fraction=1.,remittance_factor=.65,loan_remittance_factor=.9987,continue_reserve=False,register_lag=0,l_opening_capacity=0.,l_opening_reserve=0.,asset_recovery=True,asset_recovery_delay=0,recovery_friction=.10,recovery_basis_ratio=1.,recovery_tax_basis_ratio=1.,parent_capital_recovery=True,parent_premium_budget=1000.,parent_capital_start=12,parent_capital_fee=.02,parent_min_nominal=100.,loan_exit_year=None,loan_exit_fee=.10,opening_noa=OPENING_NOA):
    assert 0<=remittance_factor<=1 and register_lag in (0,1)
    pending_registration=0.;holder_share_factor=1.;premium_budget=parent_premium_budget;loan_exited=False
    c=copy.deepcopy(SCENARIOS[name]); stable=c['stable'] if stable is None else stable
    states=initial(opening_noa);states['L']['re']=l_opening_capacity;states['L']['reserve']=l_opening_reserve;states['S']['re']=sub_loss;states['P']['re']=opening_re;states['P']['cash']+=parent_cash_shift;states['S']['cash']-=parent_cash_shift
    if min(v['cash'] for v in states.values())<0:raise ValueError('invalid allocation')
    deposits={'P':P_DEP+deposit_shift,'S':S_DEP-deposit_shift,'L':L_DEP}; eq={'P':P_EQ,'S':S_EQ};accrued={'P':0.,'S':0.,'L':0.};N=N0;cum_dps=0.;rows=[];receivable=0.;s_receivable=0.;loan_receivable=0.; cumulative_subscription=0.; incremental_investment_book=0.;parent_associate=P_ASSOC;capital_receivable=0.;recovered=False;financial_carveout_cost_budget=max(0,S_DEP+S_EQ+4.782733-20)*remittance_factor*recovery_basis_ratio
    for y in range(1,max_year+1):
      group_cash_open=sum(v['cash'] for v in states.values());group_receivable_open=receivable+capital_receivable
      if y<=5:mic=c['mic'][y-1];ai=c['ai'][y-1];other=c['other'][y-1];m=c['margin'][y-1]+margin_shift;cl=c['cl'][y-1];subprofit=c['subs'][y-1]
      else:
        gy=stable+(c['after_growth']-stable)*max(0.,(10-y)/5)
        mic*=1+gy;ai*=1+gy;other*=1+gy
        # Post-year5 cash budgets retain each scenario's competitive economics.
        subprofit=(c['subs'][-1] if name=='structural' else max(c['subs'][-1],4.))*((1+stable)**(y-5))
      rev=mic+ai+other; prevN=N
      # Existing awards only; conditions modeled, new annual talent cost already in operating margin.
      ex=0.
      if c['exercise']:
        ex=10.329613 if y==1 else (8.156226 if y==2 else 0.)
      strike=max(0.,20.84-cum_dps);eqcash=ex*strike;N+=ex;premium_budget+=max(0,eqcash-ex)
      parent_rev=rev-other
      wc=-cl*parent_rev+.07*parent_rev-.025*parent_rev
      minimum=.30*cl*parent_rev+.12*parent_rev
      capex=c['cap']*parent_rev;da=.017*parent_rev
      # Contract source fees and recurring stock-equivalent compensation embedded in margin.
      maturityP=600. if y==1+delay else (500. if y in (2+delay,3+delay,4+delay) else 0.)
      maturityP=min(deposits['P'],maturityP)
      maturityS=deposits['S'] if y==1+delay else 0.
      maturityL=deposits['L'] if y==1 else 0.
      # Interest accrued on beginning deposits; paid only pro rata as principal matures.
      p_interest=.018*(states['P']['cash']+deposits['P'])+(.025*eq['P'])
      s_interest=.015*(states['S']['cash']+deposits['S'])
      l_interest=.018*(states['L']['cash']+deposits['L'])
      interest_cash={}
      for ent,rate,mat in [('P',.018,maturityP),('S',.015,maturityS),('L',.018,maturityL)]:
        accrued[ent]+=rate*deposits[ent]
        paid=accrued[ent]*mat/deposits[ent] if deposits[ent] else 0.
        accrued[ent]-=paid
        interest_cash[ent]=rate*states[ent]['cash']+paid
      interest_cash['P']+=.025*eq['P']
      psale=.90*eq['P'] if y==8+delay else 0.;pbook=eq['P'] if psale else 0.
      assoc_sale=.65*parent_associate if y==10+delay else 0.;assoc_book=parent_associate if assoc_sale else 0.;psale+=assoc_sale;pbook+=assoc_book
      ssale=.65*eq['S'] if y==10+delay else 0.;sbook=eq['S'] if ssale else 0.
      # S is a segregated non-financial subsidiary budget envelope, NOT published entity accounts.
      # Segregated loss-repair equity subscription budget, not an intercompany loan.
      # No fictitious entity issuance, registration or dilution is inferred. Support is
      # an economic necessary-funding allowance; actual contract/equity routing remains conditional.
      # Newly funded operating losses are budgeted as unrecoverable incremental cost-method
      # investment impairment, no tax credit. This is NOT a disclosed statutory charge.
      # Zero impairment is tested; existing investment carrying cost not written off again.
      smin=20.;s_cash_pre=states['S']['cash']+subprofit+interest_cash['S']-max(0.,subprofit+s_interest)*.20+maturityS+ssale
      support=max(0.,-subprofit,smin-s_cash_pre)
      if support>60.:raise ValueError('subsidiary support budget infeasible')
      cumulative_subscription+=support
      incremental_investment_book+=support
      impairment=impairment_fraction*min(support,max(0.,-subprofit))
      incremental_investment_book-=impairment
      s_remittance_factor=remittance_factor # economic realizability/attribution haircut, NOT legal equity share
      states['S'],sr=cash_year(states['S'],1.,subprofit,.20,0.,0.,0.,smin,s_interest,maturityS,ssale,sbook,borrow_limit=0.,desired=0.,new_equity=support,capital_increase=0.,financial_cash=interest_cash['S'])
      # Economic realization of financial-asset surplus; not a fictional capital
      # reduction of S. Actual legal routes/individual capacities unknown: use an
      # explicit attributable realizability discount and transaction costs, bounded
      # by disclosed real parent investment costs. No registered capital invented.
      recovery_gross=recovery_net=recovery_profit=recovery_fee=recovery_tax=0.
      if asset_recovery and not recovered and y>=10+delay+asset_recovery_delay:
        recovery_gross=max(0.,states['S']['cash']-smin)
        attributable=recovery_gross*remittance_factor;recovery_fee=attributable*recovery_friction
        net=attributable-recovery_fee
        taxbasis=financial_carveout_cost_budget*recovery_tax_basis_ratio
        recovery_tax=max(net-taxbasis,0)*.25
        recovery_net=net-recovery_tax;recovery_profit=net-financial_carveout_cost_budget-recovery_tax
        states['S']['cash']-=recovery_gross;sr['cash']=states['S']['cash'];recovered=True
      # Subsequent operating cash, unlike principal, is a new budget dividend.
      # No cross-company statutory loss pool or 650m pseudo legal gate is used.
      economic_dividend=max(0.,states['S']['cash']-smin) if sub_upstream and recovered else 0.
      states['S']['cash']-=economic_dividend;states['S']['re']-=economic_dividend
      sr['cash']=states['S']['cash'];sr['capacity_budget']=states['S']['re'];sr['distribution']=economic_dividend
      sr['economic_realization_gross']=recovery_gross;sr['economic_realization_parent_net']=recovery_net
      sr['economic_realization_parent_profit']=recovery_profit;sr['economic_realization_fee']=recovery_fee;sr['economic_realization_tax']=recovery_tax
      sr['parent_cost_budget_released']=financial_carveout_cost_budget if recovery_gross else 0.
      sr['realization_route']='conditional financial investment carve-out/disposal and remittance budget across identified legal entities; no synthetic registration'
      # Small-loan subsidiary: 99.87% parent ownership; real capital retained, dividends from earned profit.
      # No assumption of regulatory-capital cancellation or return of original principal.
      lmin=0. if loan_exited else 220.;lpre=max(0.,l_interest*.75)
      ldesired=max(0,states['L']['cash']+interest_cash['L']-l_interest*.25+maturityL-lmin) if y>=10 else .8*lpre
      states['L'],lr=cash_year(states['L'],0.,0.,.25,0.,0.,0.,lmin,l_interest,maturityL,borrow_limit=0.,desired=ldesired,financial_cash=interest_cash['L'],continue_reserve=continue_reserve)
      loan_exit_gross=loan_exit_net=loan_exit_profit=loan_exit_tax=0.
      if loan_exit_year==y:
        # Alternative disposal of the named regulated business, not simultaneous
        # liquidation proceeds plus its continuing yield. Costs/approval discount
        # and parent disclosed investment carrying cost applied separately.
        loan_exit_gross=states['L']['cash'];proceeds=loan_exit_gross*loan_remittance_factor*(1-loan_exit_fee)
        loan_exit_tax=max(proceeds-205.15818722,0)*.25
        loan_exit_net=proceeds-loan_exit_tax;loan_exit_profit=loan_exit_net-205.15818722
        states['L'].update(cash=0.,re=0.,reserve=0.,capital=0.);lr.update(cash=0.,capacity_budget=0.,reserve_budget=0.,registered_capital_budget=0.);loan_exited=True
        recovery_gross+=loan_exit_gross;recovery_net+=loan_exit_net;recovery_profit+=loan_exit_profit
      lr['exit_gross_cash']=loan_exit_gross;lr['exit_parent_net']=loan_exit_net;lr['exit_parent_profit']=loan_exit_profit;lr['exit_cash_tax']=loan_exit_tax
      lr['continuing_parent_rights_after_exit_budget']=0. if loan_exited else loan_remittance_factor
      declared=lr['distribution']*loan_remittance_factor+sr['distribution']*s_remittance_factor
      received=receivable;receivable=declared
      capital_received=capital_receivable;capital_receivable=recovery_net
      # Parent recognizes declaration now, actual cash is received one year later.
      owner_profit_est=max(0.,parent_rev*m*(1-c['tax'])+p_interest*(1-c['tax'])+subprofit+declared)
      ordinary=.80*owner_profit_est
      # Financial principal is NOT swept into TV. Additional distributions begin year6, capped
      # at 20% of annual sales and constrained by parent accumulated statutory profit and cash.
      special_cap=.20*parent_rev if y>=6+delay else 0.
      desired=ordinary+special_cap
      registration_this_year=ex if register_lag==0 else pending_registration
      pending_registration=ex if register_lag else 0.
      parent_opening=copy.deepcopy(states['P']);pre_cancel_N=N;pre_cancel_holder_factor=holder_share_factor
      states['P'],pr=cash_year(states['P'],parent_rev,m,c['tax'],capex,da,wc,minimum,p_interest,maturityP,psale,pbook,borrow_limit=100.,desired=desired,receipt=received+capital_received,declared_income=declared+recovery_profit,support=support,new_equity=eqcash,capital_increase=registration_this_year,financial_cash=interest_cash['P'],noncash_charge=impairment,continue_reserve=continue_reserve)
      # Conditional pro-rata redemption of real listed-parent nominal shares and
      # contributed-capital budget; preserve all net customer funding, not merely
      # the smaller operating cash floor. Investor's share count shrinks pro rata.
      capital_payment=capital_fee=cancel_fraction=0.
      creditor_cash_protection=max(minimum,max(0.,-wc))
      if parent_capital_recovery and y>=parent_capital_start and (y-parent_capital_start)%5==0:
        contributed=states['P']['capital']+premium_budget
        max_cancel=max(0.,1-parent_min_nominal/states['P']['capital'])
        capital_payment=min(max(0,states['P']['cash']-creditor_cash_protection)/(1+parent_capital_fee),contributed*max_cancel)
        if capital_payment>1e-8:
          capital_fee=capital_payment*parent_capital_fee
          states['P'],pr=cash_year(parent_opening,parent_rev,m,c['tax'],capex,da,wc,minimum,p_interest,maturityP,psale,pbook,borrow_limit=100.,desired=desired,receipt=received+capital_received,declared_income=declared+recovery_profit,support=support,new_equity=eqcash,capital_increase=registration_this_year,financial_cash=interest_cash['P'],noncash_charge=impairment,continue_reserve=continue_reserve,corporate_action_cost=capital_fee)
          cancel_fraction=capital_payment/contributed
          states['P']['cash']-=capital_payment;states['P']['capital']*=1-cancel_fraction
          N*=1-cancel_fraction;holder_share_factor*=1-cancel_fraction;premium_budget*=1-cancel_fraction
          pr['cash']=states['P']['cash'];pr['registered_capital_budget']=states['P']['capital']
          assert states['P']['cash']>=creditor_cash_protection-1e-7
      pr['capital_payment']=capital_payment;pr['capital_reduction_fee']=capital_fee;pr['nominal_shares_cancelled']=pre_cancel_N-N
      pr['creditor_cash_protection_for_capital_action']=creditor_cash_protection
      pr['contributed_premium_budget_remaining']=premium_budget

      deposits['P']-=maturityP;deposits['S']-=maturityS;deposits['L']-=maturityL
      if psale-assoc_sale:eq['P']=0.
      if assoc_sale:parent_associate=0.
      if ssale:eq['S']=0.
      pr['ordinary_actual']=min(ordinary,pr['distribution'])
      pr['extra_actual']=pr['distribution']-pr['ordinary_actual']
      assert pr['extra_actual']<=max(0.,pr['capacity_budget']+pr['distribution']-pr['ordinary_actual'])+1e-8
      dps=(pr['distribution']+capital_payment)/pre_cancel_N*pre_cancel_holder_factor;cum_dps+=dps
      # Entity-level conservation; parent support and subsidiary receipt cancel exactly.
      assert abs(sr['funding_cash']-pr['support'])<1e-8
      assert abs(pr['receipt']-((rows[-1]['dividend_receivable']+rows[-1]['capital_recovery_receivable']) if rows else 0.))<1e-8
      group_cash_close=sum(v['cash'] for v in states.values())
      external_cash=sum(q['ocf_after_capex']+q['maturity']+q['sale']+q['debt_draw']-q['repayment'] for q in (pr,sr,lr))+eqcash-pr['distribution']-capital_payment-sr['distribution']*(1-remittance_factor)-lr['distribution']*(1-loan_remittance_factor)-(recovery_gross-recovery_net)-(receivable+capital_receivable-group_receivable_open)
      group_cash_error=group_cash_close-group_cash_open-external_cash
      assert abs(group_cash_error)<1e-7,(y,group_cash_error)
      rows.append(dict(group_cash_conservation_error=group_cash_error,holder_share_factor=holder_share_factor,pre_cancel_holder_factor=pre_cancel_holder_factor,pre_cancel_shares=pre_cancel_N,capital_recovery_receivable=capital_receivable,parent_associate_book=parent_associate,parent_associate_sale=assoc_sale,parent_associate_book_released=assoc_book,financial_carveout_cost_budget=financial_carveout_cost_budget,year=y,revenue=rev,mic=mic,ai=ai,other=other,parent_revenue=parent_rev,margin=m,cl=cl,capex=capex,da=da,shares=N,exercise=ex,exercise_price=strike,dps=dps,subsidiary_support_scope='economic_necessary_funding_no_legal_form_inferred',S_legal_ownership=None,S_economic_remittance_factor=s_remittance_factor,S_non_parent_or_realization_friction_cash=sr['distribution']*(1-s_remittance_factor),L_economic_remittance_factor=loan_remittance_factor,cumulative_S_funding_budget=cumulative_subscription,pending_parent_registration_budget=pending_registration,P_incremental_funding_unrecovered_budget=incremental_investment_book,P_budget_investment_impairment=impairment,ordinary_budget=ordinary,special_cap=special_cap,P=pr,S=sr,L=lr,deposit_remaining=copy.deepcopy(deposits),equity_remaining=copy.deepcopy(eq),dividend_receivable=receivable,deposit_interest_receivable=copy.deepcopy(accrued),states=public_states(states)))
    return rows

def pv(rows,r,g,start=0):
    # First five-year distributions identical at both core endpoints. Future terminal at y5
    # is computed from the same fifth-year balances, with growth only changed after that date.
    cash=sum(x['dps']/(1+r)**(x['year']-start) for x in rows if x['year']>start)
    tail=rows[-1]['dps']*(1+g)/(r-g)/(1+r)**(rows[-1]['year']-start)
    return dict(value=cash+tail,tail=tail,cash=cash)

def tests():
    st=dict(cash=10.,debt=0.,re=-2.,reserve=0.,capital=100.,wc=0.)
    # Hand result: EBIT20 tax4, NI16, loss cover2, reserve1.4, legal12.6;
    # cash =10+16+2-3-1=24; min5; desired20 -> D12.6; cash11.4.
    s,x=cash_year(st,100.,.2,.2,3.,2.,1.,5.,desired=20.)
    assert abs(x['distribution']-12.6)<1e-9 and abs(s['cash']-11.4)<1e-9
    # Prior dividend receipt is cash only: no new income or statutory capacity.
    s,x=cash_year(dict(st,cash=5.,re=-20.),0.,0.,.2,0.,0.,0.,0.,receipt=7.,desired=7.)
    assert s['re']==-20 and s['cash']==12 and x['distribution']==0
    # Finite financing failure even with dividend zero.
    try:cash_year(dict(st,cash=1.),100.,-1.,.2,0.,0.,0.,0.,borrow_limit=20.)
    except ValueError:pass
    else:raise AssertionError('must fail insolvent path')
    # Interest enters earnings/cash exactly once.
    s,x=cash_year(dict(st,re=0.),0.,0.,.25,0.,0.,0.,0.,financial_interest=4.,desired=0.)
    assert abs(s['cash']-13.)<1e-9 and abs(x['profit']-3.)<1e-9
    s,x=cash_year(dict(st,re=0.),0.,0.,.25,0.,0.,0.,0.,financial_interest=4.,financial_cash=0.,desired=0.)
    assert abs(s['cash']-9.)<1e-9 and abs(x['profit']-3.)<1e-9
    s,x=cash_year(s,0.,0.,.25,0.,0.,0.,0.,financial_interest=0.,financial_cash=4.,desired=0.)
    assert abs(s['cash']-13.)<1e-9 and x['profit']==0.
    # Equity subscription must raise capital/reserve ceiling, not earnings.
    ss,xx=cash_year(dict(st,cash=100.,re=0.,reserve=50.),100.,1.,0.,0.,0.,0.,0.,new_equity=100.,capital_increase=100.)
    assert ss['capital']==200. and ss['reserve']==60. and xx['profit']==100. and ss['cash']==300.
    return ['equity_subscription_changes_reserve_ceiling','deferred_interest_not_double_profit','formal_chain_hand_example','old_dividend_no_new_profit','finite_financing_failure','interest_once','all_entity_cash_conservation']

def independent_verify(rows,r,g,claimed,start=0):
    # Independent direct loop on frozen scalar output; does not call run/pv/cash_year.
    z=0.
    for row in rows:
      if row['year']>start:z+=row['dps']*math.exp(-(row['year']-start)*math.log(1+r))
    z+=rows[-1]['dps']*(1+g)/(r-g)*math.exp(-(len(rows)-start)*math.log(1+r))
    assert abs(z-claimed)<1e-8
    # Independently reconstruct all first-year main parameters and payment constraints.
    q=rows[0];rev=1990+105;ebit=rev*.313;fin=.018*(500+2100)+.025*620;tax=(ebit+fin-.075)*.15
    ni=ebit+fin-.075-tax+q['L']['distribution']*.9987-25
    rsv=min(.1*ni,.5*q['shares']-186.36459629)
    re=1300+ni-rsv
    cash=500+ebit+(.018*500+.025*620+.018*600)-.075-tax+.017*rev-.018*rev-(q['P']['delta_wc'])+600+10.329613*20.84-q['P']['support']
    repay=min(cash-q['P']['minimum'],1.5)
    d=min(q['ordinary_budget'],re,cash-repay-q['P']['minimum'])
    assert abs(d-q['P']['distribution'])<1e-7
    return z

def independently_rebuild(r,g):
    """Second implementation from literal source/budget inputs; no formal model calls or rows.
    Rebuild P/S/L earnings, accrual/receipt, capital, borrowing, legal profit, dilution, all 80 years.
    This is deliberately verbose and uses scalar accounts to expose cross-entity mistakes.
    """
    pc,sc,lc=500.,4.782733,0.; pd,sd,ld=2100.,160.867732,220.
    pe,se=620.,234.056598; pa=sa=la=0.; debt=1.5
    pre,pres=1300.,186.36459629; sre,sres=-650.,0.; s_capital=None; lre,lres=0.,0.
    shares=413.375586; old_wc=-1488.547204+27.64133653
    outstanding_dividend=0.; accumulated_dps=0.; payments=[]; rebuilt=[]
    for year in range(1,81):
      if year<=5:
        mic=[1990.,2150.,2320.,2490.,2640.][year-1]
        ai=[105.,130.,155.,178.,200.][year-1]
        other=[230.,235.,240.,245.,250.][year-1]
        margin=[.313,.319,.324,.328,.330][year-1]
        prepaid=[.68,.68,.68,.67,.66][year-1]
        subsidiary_profit=[-25.,-18.,-10.,-5.,0.][year-1]
      else:
        growth=g+(.06-g)*max(0.,(10-year)/5)
        mic=mic*(1+growth);ai=ai*(1+growth);other=other*(1+growth)
        subsidiary_profit=4.*(1+g)**(year-5)
      turnover=mic+ai
      issued=(10.329613 if year==1 else 8.156226 if year==2 else 0.)
      subscription=issued*max(0.,20.84-accumulated_dps);shares+=issued
      pm=min(pd,600. if year==1 else 500. if year in (2,3,4) else 0.)
      sm=sd if year==1 else 0.;lm=ld if year==1 else 0.
      p_fin=pc*.018+pd*.018+pe*.025;s_fin=sc*.015+sd*.015;l_fin=lc*.018+ld*.018
      pa+=pd*.018;sa+=sd*.015;la+=ld*.018
      p_coupon=pa*pm/pd if pd else 0.;s_coupon=sa*sm/sd if sd else 0.;l_coupon=la*lm/ld if ld else 0.
      pa-=p_coupon;sa-=s_coupon;la-=l_coupon
      p_fin_cash=pc*.018+pe*.025+p_coupon;s_fin_cash=sc*.015+s_coupon;l_fin_cash=lc*.018+l_coupon
      pp=pe*.90 if year==8 else 0.;pb=pe if year==8 else 0.
      sp=se*.65 if year==10 else 0.;sb=se if year==10 else 0.
      s_tax=max(0.,subsidiary_profit+s_fin)*.20+max(0.,sp-sb)*.25
      s_income=subsidiary_profit+s_fin-s_tax+sp-sb
      s_potential=sc+subsidiary_profit+s_fin_cash-s_tax+sm+sp
      parent_support=max(0.,-subsidiary_profit,20.-s_potential)
      assert parent_support<=60.
      sc=s_potential+parent_support
      s_capital=None # no synthetic registration
      s_reserve=0. # economic remittance hurdle, not a legal reserve
      sre+=s_income-s_reserve;sres+=s_reserve
      # No S upstream; no positive/negative sub income can be pooled into P statutory balance.
      l_tax=l_fin*.25;l_income=l_fin-l_tax
      l_reserve=min(.1*max(0.,l_income+min(lre,0.)),max(0.,100.-lres))
      lre+=l_income-l_reserve;lres+=l_reserve
      l_before=lc+l_fin_cash-l_tax+lm
      ld_cash=min(.8*l_income,max(0.,lre),max(0.,l_before-220.))
      lc=l_before-ld_cash;lre-=ld_cash
      declaration=ld_cash*.9987
      ebit=turnover*margin;debt_interest=debt*.05
      income_tax=max(0.,ebit+p_fin-debt_interest)*.15+max(0.,pp-pb)*.25
      p_income=ebit+p_fin-debt_interest-income_tax+(pp-pb)+declaration-max(0.,-subsidiary_profit)
      p_reserve=min(.1*max(0.,p_income+min(pre,0.)),max(0.,.5*shares-pres))
      pre+=p_income-p_reserve;pres+=p_reserve
      new_wc=(-prepaid+.045)*turnover
      required=(.3*prepaid+.12)*turnover
      available=pc+ebit+p_fin_cash-debt_interest-income_tax+.017*turnover-.018*turnover-new_wc+old_wc+pm+pp+outstanding_dividend+subscription-parent_support
      draw=min(max(0.,required-available),max(0.,100.-debt));available+=draw
      assert available>=required-1e-7
      repaid=min(max(0.,available-required),debt+draw);available-=repaid;debt+=draw-repaid
      normal=.8*max(0.,ebit*.85+p_fin*.85+subsidiary_profit+declaration)
      extra=.2*turnover if year>=6 else 0.
      distribution=max(0.,min(normal+extra,pre,available-required))
      pre-=distribution;pc=available-distribution
      per_share=distribution/shares;payments.append(per_share);accumulated_dps+=per_share
      outstanding_dividend=declaration;old_wc=new_wc
      pd-=pm;sd-=sm;ld-=lm
      if year==8:pe=0.
      if year==10:se=0.
      rebuilt.append(dict(year=year,P_cash=pc,S_cash=sc,L_cash=lc,P_retained=pre,S_retained=sre,S_capital=s_capital,S_reserve=sres,L_retained=lre,shares=shares,dividend=per_share))
    current=sum(payment*math.pow(1+r,-i) for i,payment in enumerate(payments,1))
    current+=payments[-1]*(1+g)/(r-g)*math.pow(1+r,-80)
    future=sum(payments[i-1]*math.pow(1+r,-(i-5)) for i in range(6,81))
    future+=payments[-1]*(1+g)/(r-g)*math.pow(1+r,-75)
    return {'current':current,'TV5':future,'first5':rebuilt[:5],'last':rebuilt[-1],'annual_trace':rebuilt}

def pack_traces(obj,key=None):
    if key in ('annual_trace','base_annual_trace') and isinstance(obj,list):
        raw=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        return {'encoding':'gzip-mtime0-base64-json-utf8','sha256':hashlib.sha256(raw).hexdigest(),'years':len(obj),'data':base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode('ascii')}
    if isinstance(obj,dict):return {k:pack_traces(v,k) for k,v in obj.items()}
    if isinstance(obj,list):return [pack_traces(v) for v in obj]
    return obj

def expand_traces(obj):
    if isinstance(obj,dict) and '_lossless_manifest' in obj:
        manifest=obj['_lossless_manifest']
        result={k:expand_traces(v) for k,v in obj.items() if k!='_lossless_manifest'}
        raw=json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        assert hashlib.sha256(raw).hexdigest()==manifest['canonical_full_sha256'],'full output SHA256 mismatch'
        return dict(result,_lossless_manifest=manifest)
    if isinstance(obj,dict) and obj.get('encoding')=='gzip-mtime0-base64-json-utf8':
        raw=gzip.decompress(base64.b64decode(obj['data']))
        assert hashlib.sha256(raw).hexdigest()==obj['sha256'],'annual trace SHA256 mismatch'
        return json.loads(raw.decode('utf-8'))
    if isinstance(obj,dict):return {k:expand_traces(v) for k,v in obj.items()}
    if isinstance(obj,list):return [expand_traces(v) for v in obj]
    return obj

def main():
    out={'asof':ASOF,'units':'CNY million; shares million','account_schema':{'P':'焦点科技股份有限公司 mainland parent; opening H1 statutory186.36459629, Q3 registered N0 budget; future register time explicitly forecast','L':'南京市焦点互联网科技小额贷款有限公司 mainland registered200; group99.87 direct97.5 indirect2.37. Actual retained/reserve unknown; future-only budget, capital220 is prudential economic retention not registration','S':'Multi-jurisdiction economic operating/funding/remittance envelope, NOT corporation. No legal capital, no PRC reserve, no invented dilution. -650 is historical economic-loss diagnostic only, never legal remittance gate. Financial principal realizability from Y10 separate from recurring cash; factor65% attribution/realization budget, not ownership. Carve-out cost allocation is budget bounded by mother real investment costs, not registered/paid capital.0/100 and fees/delay/tax basis bounds retained.','capacity_budget':'Forecast economic or named-company distribution capacity, never asserted reported legal retained','reserve_budget':'Incremental/working reserve budget; S zero means no artificial statutory charge, NOT actual legal reserve zero','support':'Parent necessary-funding allowance; legal issuance/loan agreement not identified. No registered capital or ownership created','parent_capital_action':'Conditional pro-rata listed-parent capital cancellation from Y12 every5years, never dividend profit. 1000m contributed-premium budget below H1mother total capital reserve1236.479828m, not certified paid tax basis. Keep nominal>=100m and protect full net customer prepayment float; fee reduces profit/cash; original holders own proportionately fewer shares. No denominator windfall.','policy':'Registered50% permits stopping; core elects stop, continued10% sensitivity computed. Paid subscriptions never set threshold.','legacy_sensitivity_names':'S_upstream_after_legal_recovery and S_loss_zero retained only for old/new comparison; now economic remittance hurdle sensitivity, NOT legal recovery'},'financial_bridge':BRIDGE,'net_financial_assets_budget':TOTAL,'sub_deposits_budget':S_DEP,'tests':tests(),'scenarios':{}}
    for name,c in SCENARIOS.items():
      if name=='base': endpoints=[(.105,.02),(.095,.03)]
      elif name=='structural':endpoints=[(.13,0.),(.115,0.)]
      elif name=='cyclical':endpoints=[(.115,.015),(.105,.025)]
      else:endpoints=[(.10,.025),(.09,.035)]
      vals=[]
      # The first five years do not depend on long-run g.
      for r,g in endpoints:
        rows=run(name,stable=g);v=pv(rows,r,g);tv=pv(rows,r,g,5)
        if name=='base': independent_verify(rows,r,g,v['value'])
        vals.append(dict(r=r,g=g,current=v['value'],year5=tv['value'],year5_pv_share=tv['value']/(1+r)**5/v['value'],year80_tail=v['tail'],first5=rows[:5],release_years=rows[5:16],last=rows[-1],annual_trace=rows))
      assert [x['dps'] for x in vals[0]['first5']]==[x['dps'] for x in vals[1]['first5']]
      out['scenarios'][name]=vals
    b=out['scenarios']['base'];out['core_value']={'low':round(b[0]['current'],2),'high':round(b[1]['current'],2)}
    out['return_model']={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':ASOF,'base_case_distributions_per_share':[x['dps'] for x in b[0]['first5']],'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':b[0]['year5'],'high':b[1]['year5']}}}
    # Auxiliary: exact non-overlapping decomposition of holder cash. Capitalize only
    # recurring OPERATING ordinary distribution; price all other actual cash through
    # the same entity/legal bridge. No extra face-value asset add-on or arbitrary delay.
    rr=run('base',stable=.025)
    ordinary_operating=[]; residual=[]
    for row in rr:
      y=row['year']; sub=[-25,-18,-10,-5,0][y-1] if y<=5 else 4*1.025**(y-5)
      op=.8*max(0.,row['P']['ebit']*.85+sub)/row['pre_cancel_shares']*row['pre_cancel_holder_factor']
      ordinary_operating.append(op);residual.append(row['dps']-op)
    residual_pv=sum(v/1.10**i for i,v in enumerate(residual,1))+residual[-1]*1.025/.075/1.10**80
    operating_pv=sum(v/1.10**i for i,v in enumerate(ordinary_operating,1))+ordinary_operating[-1]*1.025/.075/1.10**80
    assert abs(residual_pv+operating_pv-pv(rr,.10,.025)['value'])<1e-8
    normal_op_distribution=.8*(2095*.313*.85-25)
    out['auxiliary']={'normal_operating_distribution':normal_op_distribution,'other_actual_distribution_pv':residual_pv,'operating_distribution_pv':operating_pv,'low':normal_op_distribution*18/431.861425+residual_pv,'high':normal_op_distribution*22/431.861425+residual_pv,'note':'18-22x only operating ordinary dividend; all remaining actual payments valued through legal bridge, no independent excess-cash addition'}
    out['independent_full_rebuild']={'method':'Fresh external literal-budget-rebuild.py, no production inputs imported; retained separately with annual state comparisons'}
    # Historical inline rebuild is retained below as source history but not used for this new path.
    out['sensitivity']={}
    for label,kw in [('opening_frozen_normalized',{'opening_noa':NORMALIZED_OPENING_NOA}),('opening_all_legacy_overlap_credit',{'opening_noa':OPENING_NOA+LEGACY_HEADROOM}),('opening_ex_other_receivables',{'opening_noa':OPENING_NOA-OPENING_OPERATING_ASSETS['other_receivables_ex_interest']}),('loan_exit20',{'loan_exit_year':20}),('loan_exit40',{'loan_exit_year':40}),('loan_exit20_direct_only',{'loan_exit_year':20,'loan_remittance_factor':.975}),('parent_no_capital_return',{'parent_capital_recovery':False}),('parent_premium_zero',{'parent_premium_budget':0.}),('parent_return_start20',{'parent_capital_start':20}),('parent_return_fee10',{'parent_capital_fee':.10}),('no_asset_recovery',{'asset_recovery':False}),('asset_recovery_delay5',{'asset_recovery_delay':5}),('recovery_friction25',{'recovery_friction':.25}),('recovery_zero_tax_basis',{'recovery_tax_basis_ratio':0.}),('recovery_full_disclosed_cost',{'recovery_basis_ratio':974.76695646/214.8450520385}),('recovery_book_cost_2x',{'recovery_basis_ratio':2.}),('no_budget_investment_impairment',{'impairment_fraction':0.}),('release_delay_3',{'delay':3}),('release_delay_5',{'delay':5}),('margin_minus_1pt',{'margin_shift':-.01}),('no_S_upstream',{'sub_upstream':False}),('S_upstream_after_legal_recovery',{'sub_upstream':True}),('S_loss_zero',{'sub_loss':0.,'sub_upstream':True}),('parent_principal_minus_300',{'deposit_shift':-300.}),('parent_retained_minus_300',{'opening_re':1000.}),('S_realizability_0',{'sub_upstream':True,'sub_loss':0.,'remittance_factor':0.}),('S_realizability_100',{'sub_upstream':True,'sub_loss':0.,'remittance_factor':1.}),('L_direct_only975',{'loan_remittance_factor':.975}),('continue_reserves',{'continue_reserve':True}),('parent_registration_delay1',{'register_lag':1}),('L_old_loss10',{'l_opening_capacity':-10.}),('L_reserve_already_full',{'l_opening_reserve':100.})]:
      try:
        rr=run('base',stable=.025,**kw);v=pv(rr,.10,.025);out['sensitivity'][label]={'value':v['value'],'D':[round(z['dps'],6) for z in rr[:5]],'TV5':pv(rr,.10,.025,5)['value'],'annual_trace':rr}
      except ValueError as e:out['sensitivity'][label]={'infeasible':str(e)}
    out['opening_operating_funding']={'scope':'consolidated economic funding envelope allocated to P; not statutory parent balances','assets':OPENING_OPERATING_ASSETS,'ordinary_creditors':OPENING_ORDINARY_CREDITORS,'net_operating_assets':OPENING_NOA,'previous_normalized':NORMALIZED_OPENING_NOA,'transition_funding':NORMALIZED_OPENING_NOA-OPENING_NOA,'legacy_headroom_max_overlap_credit':LEGACY_HEADROOM,'excluded_doublecount_items':['customer settlement223 separately excluded from financial resources','contract float1488.547204 separately modeled','legacy55 including DTL43.79557263 and residual allowance','financial debt1.5 independently repaid','leases8.980182 included in recurring rental margin'],'uncertainties':['long commission H1 proxy; same financial carveout retained','other receivables and taxes composition unavailable Q3','no Q3 parent attribution; consolidated cash budget only']}
    out['base_annual_trace']=run('base',stable=.025)
    # Dominant discount-rate sensitivity independently reconstructed from unchanged cash path.
    rr=run('base',stable=.025);v=pv(rr,.11,.025);independent_verify(rr,.11,.025,v['value']);out['sensitivity']['discount_11pct']={**v,'annual_trace':rr}
    out['tail_convergence']=[]
    for r,g in [(.105,.02),(.095,.03),(.10,.025)]:
      for horizon in (80,120,160):
        path=run('base',stable=g,max_year=horizon); val=pv(path,r,g)
        out['tail_convergence'].append(dict(r=r,g=g,horizon=horizon,value=val['value'],tail_pv=val['tail'],last_dps_growth=path[-1]['dps']/path[-2]['dps']-1,last_parent_capacity_budget=path[-1]['P']['capacity_budget'],annual_trace=path))
    out['unpaid_subsidiary_financial_assets_ceiling']=[]
    for year in (5,10,80):
      z=out['base_annual_trace'][year-1]
      ss=z['S']['cash']+z['deposit_remaining']['S']+z['equity_remaining']['S']+z['deposit_interest_receivable']['S']-z['S']['debt']
      ll=z['L']['cash']+z['deposit_remaining']['L']+z['deposit_interest_receivable']['L']-z['L']['debt']
      ceiling=(ss+ll*.9987)/z['shares'] # gross100% ceiling only; no invented consolidated ownership
      out['unpaid_subsidiary_financial_assets_ceiling'].append(dict(year=year,S_financial_assets=ss,L_financial_assets=ll,S_economic_recovery_balance=z['S']['capacity_budget'],S_registered_capital=z['states']['S']['registered_capital_budget'],S_legal_ownership=None,gross_assets_per_share_upper_bound=ceiling,gross_assets_per_share_lower_bound=ll*.9987/z['shares'],discounted_gross_assets_ceiling=ceiling/1.10**year,note='Inventory ceiling only, NOT incremental valuation: before operating liabilities, tax, liquidation costs, approvals and legal loss cover; L earnings already valued, liquidation would remove future earnings. S envelope does not authorize cross-entity pooling.'))
    raw_full=json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    packed=pack_traces(out)
    packed['_lossless_manifest']={'schema':'recursive annual trace envelopes; all fields preserved','canonical_full_sha256':hashlib.sha256(raw_full).hexdigest(),'canonical_bytes':len(raw_full),'canonicalization':'utf8 JSON ensure_ascii=False sort_keys=True separators comma colon; manifest excluded','expansion':'python 2026-Q3.py --expand 2026-Q3-output.json'}
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(packed,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'core':out['core_value'],'return_model':out['return_model'],'auxiliary':out['auxiliary'],'sensitivities':{k:{a:b for a,b in v.items() if a!='annual_trace'} for k,v in out['sensitivity'].items()}},ensure_ascii=False,indent=2))
if __name__=='__main__':
    if '--expand' in sys.argv:
        i=sys.argv.index('--expand');p=Path(sys.argv[i+1]) if len(sys.argv)>i+1 else Path(__file__).with_name('2026-Q3-output.json')
        print(json.dumps(expand_traces(json.loads(p.read_text())),ensure_ascii=False,indent=2))
    else:main()

#!/usr/bin/env python3
"""Standalone economic budget; billion CNY, billion shares, million pigs.
Not a certification of legal upstream permissions. No prices or input files.
"""
import json, math, sys, copy
ASOF='2026-10-29T20:00:00+00:00'

def initial():
    cash=20.07045877616; assets=175.77226000297; debt=81.73194012594 # financial carrying amounts incl leases/long payable
    eq=77.53404082286; cb=9.880 # Q3 amortized carrying budget; face known, repay at 107%
    return dict(cash=cash,restricted=2.81784941523,restricted_operating=1.08434152701,restricted_financing=1.53350788822,restricted_unresolved=.2,parent_restricted=2.81784941523*(2.17157235279/2.91744722625),portfolio=2.24522097172,investment=1.08440749322,
      fixed=94.60360395119+1.97267568030+1.28733784227,bio=7.30976627055,rou=3.38829681871,
      working=assets-cash-2.81784941523-2.24522097172-1.08440749322-97.86361747376-7.30976627055-3.38829681871,
      bank=debt-cb-3.94988132569,cb=cb,lease=3.94988132569,op_liab=assets-eq-debt,common=77.51789205519,minority=.01614876767,
      group_re=47.67526614244,other_equity=1.01713369505,shares=5.701357721,registered=5.772996144,
      parent_cash=10.67709310039,parent_re=9.93534560896,parent_reserve=2.82919055676,
      sub_re=37.73992053348,sub_reserve=0.,ic_receivable=55.886267322,ic_payable=56.85749810193,
      parent_invest_cost=94.51884521005,parent_bank=50.73317752492,parent_lease=.14717622223,finance_used=0.)

def assumptions(y,case,entry):
    qty=[76.,77.,78.,78.,78.][min(y-1,4)]
    price=[12.,13.2,14.,13.4,12.6][y-1] if y<=5 else [13.,13.5,13.2,12.5,12.8][(y-6)%5]
    cost=9.70 if y==1 else 9.65
    slaughter=[.75,.90,1.05,1.15,1.2][min(y-1,4)]
    expansion=.8 if y<=5 else 0.
    if case in ('core_low','core_high'):
        k=-1 if case=='core_low' else 1
        if y>=2:price+=k*.15
        cost-=k*.05
    if case=='weak' and y<=2:
        price=[10.5,11.3][y-1];expansion=0.;qty=[74.,75.][y-1];cost+=.15
    if case=='structural':price=11.;cost+=.5;qty=72.;expansion=0.;slaughter=.5
    if case=='upside':price+=.6;slaughter+=.35
    if case=='cost_up':cost+=.5
    if case=='cycle7' and y>5:price=[12.8,13.2,13.5,13.2,12.8,12.5,12.7][(y-6)%7]
    if case=='slow_recovery':
        if y<=5:price=[11.6,12.,12.6,13.2,13.6][y-1];qty=[74.,74.,75.,76.,77.][y-1];cost+=.15;expansion=0. if y<=2 else .8
        else:price=[13.3,13.6,13.4,13.,12.4,12.3,12.8][(y-6)%7]
    if case=='industry_efficiency':price-=.4;cost-=.1;qty=80.;expansion=1.6 if y<=5 else 0.
    if case=='maintenance_up':expansion+=1.5 # repairs expensed separately below, no invented added capacity
    # Independent capital-productivity entry: capacity cash surplus, not a transform of primary EBIT.
    # 76-78m head operating capacity, normal net operating capital ~132bn, normal 11%-14% EBIT yield.
    ebit2=[3.5,13.5,19.,16.5,11.][min(y-1,4)] if y<=5 else [14.,18.,16.,10.,12.][(y-6)%5]
    return qty,price,cost,slaughter,expansion,ebit2

def step(s,y,case='base',entry='unit',custom=None):
    s=copy.deepcopy(s);o=copy.deepcopy(s);q,p,c,sl,growth,ebit2=assumptions(y,case,entry)
    da_fixed=s['fixed']/7.;da_bio=s['bio']*.28;da_rou=.8;da=da_fixed+da_bio+da_rou
    kg=q*.125
    ebitda=kg*(p-c)+sl-.5 # cash farming cost excludes financing, DD&A and group HQ expense
    if entry=='capital':ebitda=ebit2+da
    repair=1.5 if case=='maintenance_up' else 0.
    if repair:growth-=repair;ebitda-=repair
    if custom:ebitda=custom.get('ebitda',ebitda);growth=custom.get('growth',growth)
    cap_fixed=da_fixed+growth;bio_gross=s['bio']*.4;bio_retire=bio_gross*.3;bio_net=bio_gross-bio_retire
    # physical renewal at net residual proceeds; no extra profit from retired animals
    working_target=initial()['working']*(q/76.) # recomputed in EVERY forecast year, including post-Y5 capacity changes
    dw=working_target-s['working'];s['working']=working_target
    s['fixed']+=cap_fixed-da_fixed;s['bio']+=bio_net-da_bio
    lease_principal=1.99143568794 if y==1 else .8;lease_new=.8;s['rou']+=lease_new-da_rou
    s['lease']+=lease_new-lease_principal
    interest=o['bank']*.035+o['lease']*.035
    cb_pay=9.5429474*1.07 if y==1 else 0.
    cb_charge=cb_pay-s['cb'] if y==1 else 0.
    # CB face plus embedded last coupon/premium; no second coupon charge
    # Separate ongoing procurement collateral, financing collateral and unresolved releases.
    # Amount allocations are budgets: observed FY restricted balance anchors ongoing needs, not a legal split.
    op_floor=1.08434152701;unresolved0=.2;resolve_rate=.2;resolve_start=3
    if case=='restricted_high':op_floor=1.8;unresolved0=.4;resolve_rate=.1;resolve_start=5
    if case=='restricted_low':op_floor=.7;unresolved0=.1;resolve_rate=.3;resolve_start=2
    if case=='restricted_delay':resolve_rate=.1;resolve_start=5
    # Reallocate opening bucket definitions before calculating the first year's runoff; total remains actual.
    if y==1:
        o['restricted_operating']=op_floor;o['restricted_unresolved']=unresolved0
        o['restricted_financing']=2.81784941523-op_floor-unresolved0
    target_op=op_floor*q/76.*c/9.70
    target_fin=(2.81784941523-op_floor-unresolved0)*o['bank']/67.90205880025
    target_unresolved=o['restricted_unresolved']*(1.-resolve_rate if y>=resolve_start else 1.)
    s['restricted_operating']=target_op;s['restricted_financing']=target_fin;s['restricted_unresolved']=target_unresolved
    s['restricted']=target_op+target_fin+target_unresolved
    restricted_release=o['restricted']-s['restricted']
    parent_restricted_ratio=2.17157235279/2.91744722625 # H1 parent/group restricted proxy, not a Q3 legal statement
    parent_restricted_release=restricted_release*parent_restricted_ratio
    s['parent_restricted']=s['restricted']*parent_restricted_ratio
    restricted_income=o['restricted']*.015
    restricted_tax=restricted_income*.25 # conservative taxable interest, no cash tax refund assumed
    finance_income=(restricted_income+s['portfolio']*.025+s['investment']*.04+s['cash']*.01)
    tax=max(0.,sl-.15)*.25+.15+restricted_tax # loss-making farm exempt; taxable profitable subsidiaries do not offset group losses
    investment_sale=s['investment'] if y==10 else 0.
    investment_sale_cost=investment_sale*.02
    ni=ebitda-da-interest-cb_charge+finance_income-tax-investment_sale_cost
    minority_income=ni*.00021
    common_income=ni-minority_income
    # liquid financial portfolio redeemed once at book; external equity investment stays productive at 4%
    redeem=s['portfolio'] if y==1 else 0.;s['portfolio']-=redeem
    fcfe=ni+da-cap_fixed-bio_net-lease_principal-dw
    s['cash']+=fcfe+redeem+investment_sale-cb_pay+cb_charge+restricted_release
    s['investment']-=investment_sale
    s['cb']=0. if y==1 else s['cb']
    # Actual maturity need separated from net debt budget. Normal annual bank rollover is assumed, not legal commitment.
    maturity=min(s['bank'],62. if y==1 else s['bank']*.75)
    rollover=maturity
    if case=='rollover_failure' and y==1:rollover=.5*maturity
    contractual_net=maturity-rollover
    s['bank']-=contractual_net;s['cash']-=contractual_net
    if case=='convert' and y==1:
        s['cash']+=cb_pay;s['shares']+=9.5429474/43.32;s['registered']+=9.5429474/43.32
        ni+=cb_charge;common_income+=cb_charge;s['common']+=o['cb'];cb_pay=0.;cb_charge=0.
    # initial CB equity component moves to ordinary capital, not profits; included once in common equity already
    if y==1:s['other_equity']=0.
    need=max(0.,12.-s['cash'])
    limit=12. if case!='no_new_finance' else 0.
    issue=min(need,max(0.,limit-s['finance_used']))
    s['finance_used']+=issue;s['bank']+=issue;s['cash']+=issue
    failure=s['cash']<12.-1e-8
    if failure:
        return o,dict(year=y,feasible=False,attempted_cash=s['cash'],attempted_bank=s['bank'],reason='cash reserve cannot be funded after contractual/refinancing budget',funding_gap=12.-s['cash'],bank_maturity=maturity,rollover=rollover,new_finance=issue,ending_state=o),False
    # Preserve cycle buffer, repay discretionary debt only from surplus; no artificial acceleration on weak paths
    repay=min(s['bank'],max(0.,s['cash']-18.)*(.65 if y<=10 else 1.))
    s['bank']-=repay;s['cash']-=repay
    # entity cash cost and interest allocations, not a factual Q3 parent statement
    parent_ratio=o['parent_bank']/o['bank'] if o['bank'] else 0.
    parent_interest=o['parent_bank']*.035+o['parent_lease']*.035
    parent_lease_ratio=o['parent_lease']/o['lease'] if o['lease'] else 0.
    s['parent_lease']+=(lease_new-lease_principal)*parent_lease_ratio
    parent_fin_income=o['parent_cash']*.01+o['parent_restricted']*.015+(.2*.025 if y==1 else 0.)
    parent_restricted_tax=o['parent_restricted']*.015*.25
    parent_expense=.5+parent_interest+cb_charge-parent_fin_income+parent_restricted_tax
    s['parent_bank']=max(0.,o['parent_bank']+(issue-repay-contractual_net)*parent_ratio)
    sub_income=common_income+parent_expense
    sr0=s['sub_re'];s['sub_re']+=sub_income
    statutory=min(max(0.,sub_income-max(0.,-sr0))*.1,max(0.,47.259422605025-s['sub_reserve']))
    s['sub_re']-=statutory;s['sub_reserve']+=statutory
    parent_financing=(issue-repay-contractual_net)*parent_ratio-cb_pay+cb_charge-(lease_principal-.8)*parent_lease_ratio
    parent_portfolio_redemption=.2 if y==1 else 0.
    pc=s['parent_cash']-parent_expense+parent_financing+parent_portfolio_redemption+parent_restricted_release
    sub_cash=s['cash']-pc
    # genuine group distributions first five years conservative 40% profit; debt-free mature business sweeps cash
    desired=0. if y==1 else max(0.,common_income)*.4 if y<=10 else max(0.,s['cash']-18.)
    desired=min(desired,max(0.,s['cash']-12.))
    upstream=min(max(0.,s['sub_re']),max(0.,sub_cash-5.),max(0.,desired+6.-pc))
    if case=='upstream_delay' and y<=3:upstream*=.2
    s['sub_re']-=upstream;pc+=upstream;sub_cash-=upstream
    parent_profit=upstream-parent_expense
    pr0=s['parent_re'];s['parent_re']+=parent_profit
    reserve=min(max(0.,parent_profit-max(0.,-pr0))*.1,max(0.,s['registered']*.5-s['parent_reserve']))
    s['parent_re']-=reserve;s['parent_reserve']+=reserve
    # Gross legal intercompany balances never silently netted. Settlement uses actual cash and reduces each claim.
    # Ordinary budget settles 2bn each direction annually, cash neutral. Additional loans preserve entity buffers.
    gross_receive=min(2.,s['ic_receivable'],max(0.,sub_cash-5.))
    pc+=gross_receive;sub_cash-=gross_receive;s['ic_receivable']-=gross_receive
    gross_pay=min(2.,s['ic_payable'],max(0.,pc-3.))
    pc-=gross_pay;sub_cash+=gross_pay;s['ic_payable']-=gross_pay
    support=0.
    if pc<3.:
        support=min(3.-pc,max(0.,sub_cash-5.))
        pc+=support;sub_cash-=support;s['ic_payable']+=support
    elif sub_cash<5.:
        support=-min(5.-sub_cash,max(0.,pc-3.))
        pc+=support;sub_cash-=support;s['ic_receivable']-=support
    # additional principal repayment from child to parent can support dividends but NEVER legal income
    collect=min(s['ic_receivable'],max(0.,sub_cash-5.),max(0.,desired+3.-pc))
    s['ic_receivable']-=collect;pc+=collect;sub_cash-=collect
    dividend=min(desired,max(0.,s['parent_re']),max(0.,pc-3.))
    pc-=dividend;s['parent_re']-=dividend;s['cash']-=dividend;s['parent_cash']=pc
    md=min(max(0.,minority_income),max(0.,s['cash']-12.),max(0.,sub_cash-5.))
    s['cash']-=md;sub_cash-=md
    s['common']+=common_income-dividend;s['minority']+=minority_income-md;s['group_re']+=common_income-dividend
    # conversion is a capital transaction; share accounting asserted separately below
    assets=sum(s[k] for k in ('cash','restricted','portfolio','investment','fixed','bio','rou','working'))
    liabilities=s['bank']+s['cb']+s['lease']+s['op_liab']
    equity=s['common']+s['minority']
    cash_error=s['cash']-(o['cash']+fcfe+redeem+investment_sale+restricted_release-(9.5429474*1.07 if y==1 else 0.)+(9.5429474*1.07-o['cb'] if y==1 else 0.)-contractual_net+issue-repay-dividend-md+(9.5429474*1.07 if case=='convert' and y==1 else 0.))
    assert abs(assets-liabilities-equity)<1e-7,(case,y,assets-liabilities-equity)
    assert abs(cash_error)<1e-7
    assert abs(pc+sub_cash-s['cash'])<1e-7
    assert min(s['cash']-12.,pc-3.,sub_cash-5.)>-1e-7,(case,y,pc,sub_cash)
    assert s['parent_re']>=-1000 # negative RE permitted; distributions cannot exploit it
    row=dict(year=y,feasible=True,qty_million=q,weight_kg=125.,pig_price=p,cash_unit_cost=c,slaughter_cash=sl,
      ebitda=ebitda,da_fixed=da_fixed,da_bio=da_bio,da_rou=da_rou,ebit=ebitda-da,interest=interest,cb_charge=cb_charge,
      finance_income=finance_income,restricted_income=restricted_income,restricted_tax=restricted_tax,restricted_release=restricted_release,parent_restricted_release=parent_restricted_release,parent_restricted_tax=parent_restricted_tax,tax=tax,net_income=ni,common_income=common_income,capex_fixed=cap_fixed,
      maintenance_fixed=da_fixed,expansion=growth,bio_gross=bio_gross,bio_disposal_cash=bio_retire,bio_net=bio_net,
      lease_new=lease_new,lease_principal=lease_principal,delta_working=dw,fcfe_before_finance=fcfe,
      portfolio_redemption=redeem,investment_sale=investment_sale,investment_sale_cost=investment_sale_cost,investment_sale_tax=0.,cb_face=9.5429474 if y==1 else 0.,cb_cash_interest_premium=.668006318 if y==1 and case!='convert' else 0.,cb_repayment=cb_pay,bank_maturity=maturity,rollover=rollover,new_finance=issue,
      discretionary_bank_repayment=repay,parent_expense=parent_expense,parent_interest=parent_interest,parent_fin_income=parent_fin_income,parent_financing=parent_financing,sub_income=sub_income,sub_statutory=statutory,
      upstream_declared=upstream,upstream_paid=upstream,parent_profit=parent_profit,parent_statutory=reserve,
      gross_ic_principal_received=gross_receive,gross_ic_principal_paid=gross_pay,new_ic_support_to_parent=support,ic_principal_collected=collect,
      common_dividend=dividend,dps=dividend/s['shares'],minority_dividend=md,sub_cash=sub_cash,
      assets=assets,liabilities=liabilities,equity=equity,cash_error=cash_error,ending_state=s)
    return s,row,True

def simulate(case='base',entry='unit',years=240,rate=.105,override=None):
    s=initial()
    if override:s.update(override)
    rows=[]
    for y in range(1,years+1):
        s,row,ok=step(s,y,case,entry);rows.append(row)
        if not ok:return dict(case=case,entry=entry,feasible=False,rows=rows,current_value=None,terminal_y5=None,rate=rate)
    pv=sum(r['dps']/(1+rate)**r['year'] for r in rows)
    tv=sum(r['dps']/(1+rate)**(r['year']-5) for r in rows if r['year']>5)
    return dict(case=case,entry=entry,feasible=True,rows=rows,current_value=pv,terminal_y5=tv,rate=rate,
      dps5=[r['dps'] for r in rows[:5]],pv_after5=sum(r['dps']/(1+rate)**r['year'] for r in rows[5:]),final_state=s)

def main():
    runs=[simulate('core_low',rate=.11),simulate('base'),simulate('core_high',rate=.10),simulate(entry='capital'),
      *[simulate(c) for c in ('weak','structural','upside','cost_up','maintenance_up','rollover_failure','no_new_finance','upstream_delay','convert')],
      simulate('base',override={'sub_re':0.}),simulate('base',override={'parent_cash':5.67709310039}),simulate('base',rate=.10),simulate('base',rate=.11),*[simulate('base',years=n) for n in (120,360,720)],*[simulate(c) for c in ('cycle7','slow_recovery','industry_efficiency','restricted_high','restricted_low','restricted_delay')]]
    print(json.dumps(dict(model_as_of=ASOF,units='CNY billion; shares billion; pigs million',opening=initial(),runs=runs),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()

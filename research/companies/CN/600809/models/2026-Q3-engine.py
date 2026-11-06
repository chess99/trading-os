#!/usr/bin/env python3
"""山西汾酒独立普通股模型。stdlib；金额十亿元，股数十亿股；stdout为完整JSON。
现金口径含银行定期存款，区分受限额度。现金租金已在经营利润中扣除，租赁债不再扣企业价值。
母公司/销售子公司预测为预算，不冒称Q3未披露的法定报表。
"""
import json, math, copy
SHARES=1.219964222
CUT='2026-10-28T14:00:00+00:00'
FACTS={
 'q3_revenue':7.33751121118,'nine_month_revenue':28.38189901952,'nine_month_common_profit':8.33789004539,
 'q3_common_profit':1.89857647128,'cash':6.86847813114,'other_current_assets':21.29221120543,
 'h1_tax_assets_in_other_current':.22091848888,'h1_pledged_deposits':2.56907206675,
 'nci_equity':.54238221870,'common_equity':39.99380201652,
 'lease_noncurrent':2.03656935837,'lease_current':.19888137064,'rou_asset':2.44378588632,
 'inventory':14.36194890964,'contract_liabilities':5.61268116815,
 'parent_h1_RE':24.12178236925,'parent_h1_reserve':.610057186,'parent_sharecapital':1.219964222,
 'parent_capital_surplus':1.02000463311,'parent_h1_dividend_receivable':0,
 'sales_h1_netassets':14.3694136,'sales_h1_assets':27.6084059,'sales_capital':.08,
 'sales_h1_profit':3.1636348,'sales_parent_investment_cost':.3840384,
 'parent_all_investment_cost':2.83671321956,'dividend_already_paid':8.00296529632,
 'parent_h1_trade_receivable_net':4.43960999776,'parent_h1_other_payables_ex_div':19.8199020933,
 'FY2025_parent_cost_method_income':5.0051,'FY2025_parent_investment_cash_receipts':.44604250742,
 'h1_parent_cash':8.85436345185,'h1_parent_deposits_and_tax_assets':25.60234947274}
BASE={
 'inside':[13.5,13.7,14,14.3,14.5], 'outside':[19.3,19.3,20.1,21.2,22], 'other':[.5,.55,.6,.65,.7],
 'net_operating_margin':[.275,.28,.285,.29,.292], # after cash rent, normal tax and NCI; no financial income
 'capex':[2.5,2.8,2.6,2,1.5], 'da':[.5,.6,.7,.8,.85],
 'wc_extra':[.7,.6,.2,.1,0], # prepayment runoff and ageing stock; does not count contract cash as distributable again
 'long_growth':.015,'transition_growth':[.035,.03,.025,.02,.015],
 'long_margin':.29,'interest_aftertax':.009,'rent_cash':.40,
 'internal_ar_settlement':1.0,'pool_repayment':1.0,'upstream_delay':0,
 'initial_liquid_delta':0,'parent_cash_delta':0,'extra_parent_payment':0,
 'payout_release_start':6,'opening_parent_RE_override':None,'nci_cash_buffer_multiple':1.0,'opening_sub_RE_override':None,'description':'省内稳定、省外两年整理后低个位数扩展；资本预算完成而非立即变现酒龄库存。'}

def legal_step(re,reserve,capital,profit,request,available):
    """同一生产分配函数：先补累计亏损，再提10%法定公积至资本50%，最后受现金限制分配。"""
    distributable_profit=max(0,profit-max(0,-re))
    appropriation=min(max(0,capital*.5-reserve),.1*distributable_profit)
    before=re+profit-appropriation
    dividend=max(0,min(request,max(0,before),max(0,available)))
    return {'re':before-dividend,'reserve':reserve+appropriation,'appropriation':appropriation,
            'dividend':dividend,'pre_distribution_RE':before,'cash_limit':max(0,available)}

def opening(p):
    # Q3定期存款分项未公开：沿H1税类资产差额估计，另做±1bn检验；绝不把其他流动资产全部当现金。
    liquid=FACTS['cash']+FACTS['other_current_assets']-FACTS['h1_tax_assets_in_other_current']-FACTS['nci_equity']*p['nci_cash_buffer_multiple']+p['initial_liquid_delta']
    # 全额留出NCI账面权益作为非普通股现金隔离，经营利润亦已扣NCI；不在终值再次扣。
    parent=liquid-.9+p['parent_cash_delta']
    return dict(cash=liquid,parent_cash=parent,sub_cash=liquid-parent,
       parent_re=(FACTS['parent_h1_RE'] if p['opening_parent_RE_override'] is None else p['opening_parent_RE_override']),parent_reserve=FACTS['parent_h1_reserve'],
       sub_re=(FACTS['sales_h1_netassets']-.08-.04 if p['opening_sub_RE_override'] is None else p['opening_sub_RE_override']),sub_reserve=.04,
       sub_capital=.08,parent_capital=SHARES,parent_capital_surplus=FACTS['parent_capital_surplus'],
       equity=FACTS['common_equity']+p['initial_liquid_delta'],
       net_operating_capital=FACTS['common_equity']-liquid+p['initial_liquid_delta'],
       lease=FACTS['lease_noncurrent']+FACTS['lease_current'],rou=FACTS['rou_asset'],
       trade_receivable=FACTS['parent_h1_trade_receivable_net'],pool_payable=18.0,
       dividend_receivable=0,dividend_payable=0,sub_investment_cost=FACTS['parent_all_investment_cost'],
       due=[],revenue=34.17573992158,previous_profit=9.0,
       pledged=FACTS['h1_pledged_deposits'],financial_debt=0,shares=SHARES)

def annual(state,year,p):
    s=copy.deepcopy(state); old=copy.deepcopy(state)
    if year<=5:
        inside,outside,other=[p[k][year-1] for k in ('inside','outside','other')]
        revenue=inside+outside+other; margin=p['net_operating_margin'][year-1]
        capex=p['capex'][year-1]; da=p['da'][year-1];extra=p['wc_extra'][year-1]
    else:
        growth=p['transition_growth'][year-6] if year<=10 else p['long_growth']
        revenue=old['revenue']*(1+growth)
        outside=revenue*p['outside'][-1]/sum(p[k][-1] for k in ('inside','outside','other'))
        inside=revenue*p['inside'][-1]/sum(p[k][-1] for k in ('inside','outside','other'));other=revenue-inside-outside
        margin=p['long_margin']+(p['net_operating_margin'][-1]-p['long_margin'])*max(0,(10-year)/5)
        da=.85*(revenue/sum(p[k][-1] for k in ('inside','outside','other')))
        capex=da+.20*max(0,revenue-old['revenue']);extra=0
    delta_wc=.15*(revenue-old['revenue'])+extra
    rent=p['rent_cash']*(revenue/33.3)
    # Margin base assumes .40bn rent at 33.3bn revenue; every alternate rent changes profits AND cash.
    op_profit=revenue*margin-(rent-.40*(revenue/33.3))*.75
    financial_income=old['cash']*p['interest_aftertax']
    profit=op_profit+financial_income
    fcf=profit+da-capex-delta_wc
    parent_profit_own=op_profit*.52+financial_income*.95
    sub_profit=profit-parent_profit_own
    parent_fcf=parent_profit_own+da*.95-capex*.95-delta_wc*.70
    sub_fcf=fcf-parent_fcf
    s['parent_cash']+=parent_fcf;s['sub_cash']+=sub_fcf
    cash_floor=max(3.0,.15*revenue)
    parent_floor=.7*cash_floor;sub_floor=.3*cash_floor
    # 应收货款和往来借款分别结算，非合并净额自动法律抵销。
    ar_collection=min(s['trade_receivable'],p['internal_ar_settlement'],max(0,s['sub_cash']))
    s['parent_cash']+=ar_collection;s['sub_cash']-=ar_collection;s['trade_receivable']-=ar_collection
    repayment=min(s['pool_payable'],p['pool_repayment']+(p['extra_parent_payment'] if year==1 else 0),max(0,s['parent_cash']-parent_floor))
    s['parent_cash']-=repayment;s['sub_cash']+=repayment;s['pool_payable']-=repayment
    ordinary_target=.65*max(0,old['previous_profit']) if year<=5 else .85*max(0,profit)
    # 尾期释放是经济收敛预算而非公司法律承诺；在每一法定/现金上限内执行。
    release=max(0,(old['cash']-cash_floor))*.20 if year>=p['payout_release_start'] else 0
    if year>10:ordinary_target=max(0,fcf-.15*(revenue-old['revenue']))
    target=ordinary_target+release
    sub_target=.70*max(0,sub_profit) if year<=5 else max(0,sub_profit)+.20*max(0,old['sub_re'])
    # 宣派还须具备现金来源：已宣派未付金额逐元预留，防止永久滚动无资金的应付股利。
    # 母先偿还真实既有资金池借款，子再宣派；不是合并净额自动抵销。
    prefund=min(s['pool_payable'],max(0,sub_target+s['dividend_payable']+sub_floor-s['sub_cash']),
                max(0,s['parent_cash']-parent_floor))
    s['pool_payable']-=prefund;s['parent_cash']-=prefund;s['sub_cash']+=prefund
    sub_cash_capacity=max(0,s['sub_cash']-sub_floor-s['dividend_payable'])
    sr=legal_step(s['sub_re'],s['sub_reserve'],s['sub_capital'],sub_profit,sub_target,sub_cash_capacity)
    declared=sr['dividend'];s['sub_re']=sr['re'];s['sub_reserve']=sr['reserve']
    s['due'].append([year+p['upstream_delay'],declared]);s['dividend_receivable']+=declared;s['dividend_payable']+=declared
    due_now=sum(v for t,v in s['due'] if t<=year)
    topup=min(s['pool_payable'],max(0,due_now+sub_floor-s['sub_cash']),max(0,s['parent_cash']-parent_floor))
    s['pool_payable']-=topup;s['parent_cash']-=topup;s['sub_cash']+=topup
    received=min(due_now,max(0,s['sub_cash']-sub_floor))
    left=received;remaining=[]
    for t,v in s['due']:
        pay=min(v,left) if t<=year else 0;left-=pay
        if v-pay>1e-10:remaining.append([t,v-pay])
    s['due']=remaining;s['parent_cash']+=received;s['sub_cash']-=received
    s['dividend_receivable']-=received;s['dividend_payable']-=received
    parent_profit=parent_profit_own+declared
    s['pledged']=.075*revenue # normal bills/deposit collateral rolls; retained inside minimum cash, not lost permanently
    available=min(s['parent_cash']-parent_floor,s['parent_cash']-s['pledged'],s['parent_cash']+s['sub_cash']-cash_floor)
    pr=legal_step(s['parent_re'],s['parent_reserve'],s['parent_capital'],parent_profit,target,available)
    paid=pr['dividend'];s['parent_re']=pr['re'];s['parent_reserve']=pr['reserve'];s['parent_cash']-=paid
    # 现金租赁成本已经包含在利润及FCF；以下只展开债务状态，不重复从FCF扣。
    lease_interest=old['lease']*.03
    lease_principal=min(old['lease'],max(0,rent-lease_interest))
    lease_new=0 if year<=6 else max(0,FACTS['lease_noncurrent']*(revenue/33.3)-(old['lease']-lease_principal))
    s['lease']=old['lease']-lease_principal+lease_new;s['rou']=max(0,old['rou']-lease_principal)+lease_new
    s['cash']=s['parent_cash']+s['sub_cash'];s['equity']+=profit-paid
    s['net_operating_capital']+=capex-da+delta_wc;s['previous_profit']=profit;s['revenue']=revenue
    assert abs(s['cash']-(old['cash']+fcf-paid))<1e-7+1e-12*abs(s['cash'])
    assert abs(s['equity']-(s['cash']+s['net_operating_capital']))<1e-6+1e-12*abs(s['equity'])
    assert abs(s['dividend_receivable']-s['dividend_payable'])<1e-8
    assert abs(s['dividend_receivable']-sum(v for _,v in s['due']))<1e-7+1e-12*abs(s['dividend_receivable'])
    assert min(s['parent_cash'],s['sub_cash'],s['parent_reserve'],s['sub_reserve'],s['lease'],s['pool_payable'])>=-1e-8
    assert paid<=max(0,pr['pre_distribution_RE'])+1e-8
    assert paid<=max(0,available)+1e-8
    assert s['parent_capital_surplus']==old['parent_capital_surplus']
    assert s['sub_cash']-sub_floor-s['dividend_payable']>=-1e-7-1e-12*abs(s['sub_cash'])
    assert all(t>year for t,v in s['due'] if v>1e-8) # 无逾期未付，只允许已预留现金的未来日期股利
    row=dict(year=year,opening=old,revenue_inside=inside,revenue_outside=outside,revenue_other=other,
      revenue=revenue,net_operating_margin=margin,operating_common_profit_after_rent=op_profit,
      financial_income=financial_income,common_profit=profit,owned_asset_depreciation=da,capex_cash=capex,
      delta_working_capital=delta_wc,common_free_cash=fcf,parent_profit_own=parent_profit_own,sub_profit=sub_profit,
      parent_fcf_before_internal=parent_fcf,sub_fcf_before_internal=sub_fcf,
      gross_current_internal_sales_budget=.67*revenue,old_trade_receivable_collected=ar_collection,
      old_pool_liability_repaid=repayment+prefund+topup,sub_declaration_cash_capacity=sub_cash_capacity,sub_dividend_declared=declared,sub_dividend_received=received,
      parent_legal_profit=parent_profit,parent_reserve_added=pr['appropriation'],sub_reserve_added=sr['appropriation'],
      holder_requested=target,holder_cash=paid,holder_per_share=paid/s['shares'],
      holder_limited_by_legal=max(0,target-max(0,pr['pre_distribution_RE'])),
      holder_limited_by_cash=max(0,target-max(0,available)),required_cash=cash_floor,required_cash_including_declared_dividends=cash_floor+s['dividend_payable'],
      rent_cash_already_in_profit=rent,lease_interest_within_rent=lease_interest,
      lease_principal_within_rent=lease_principal,new_lease_noncash=lease_new,
      debt_draw=0,debt_repayment=0,share_issuance=0,buyback_cash=0,closing=s)
    return s,row

def run(p,years=960):
    s=opening(p);rows=[]
    for t in range(1,years+1):s,row=annual(s,t,p);rows.append(row)
    return rows

def valuation(rows,r,g,start=0):
    # Terminal dividend at the recursion horizon derives actual converged cash/operating/legal state.
    last=rows[-1];tail=last['holder_cash']*(1+g)/(r-g)
    n=len(rows)-start
    dividends_pv=sum(x['holder_cash']/(1+r)**(x['year']-start) for x in rows[start:])
    tail_pv=tail/(1+r)**n
    return {'equity_value':dividends_pv+tail_pv,'per_share':(dividends_pv+tail_pv)/SHARES,
      'dividends_pv':dividends_pv,'terminal_year':rows[-1]['year'],'terminal_at_horizon':tail,'terminal_pv':tail_pv,
      'terminal_share':tail_pv/(dividends_pv+tail_pv),'rate':r,'growth':g,'valuation_year':start}

def scenarios():
    specs={'base':copy.deepcopy(BASE)}
    def add(n,changes):p=copy.deepcopy(BASE);p.update(changes);specs[n]=p
    add('cyclical_weak',dict(outside=[17.0,17.3,18.3,20.0,21.5],inside=[13,13,13.5,14,14.4],net_operating_margin=[.245,.25,.265,.28,.29],wc_extra=[1.2,.8,.4,.1,0],description='省外去库存延长至第三年，费用不同比收缩；保留产能预算及品牌长期恢复机制。'))
    add('structural_damage',dict(outside=[17,16,15.5,15.3,15.2],inside=[13,12.8,12.7,12.6,12.5],other=[.4]*5,net_operating_margin=[.24,.225,.215,.21,.21],capex=[2.5,2.5,2.2,1.7,1.2],wc_extra=[1.1,.7,.3,.2,.1],transition_growth=[0]*5,long_growth=0,long_margin=.21,description='省外渠道失效和中高价带竞争永久化；2030已形成投入仍结算，后续扩张放慢；零长期增长。'))
    add('optimistic',dict(outside=[20.5,22,24,26,28],inside=[13.6,14,14.5,15,15.5],net_operating_margin=[.29,.30,.305,.31,.31],capex=[2.8,3,3,2.4,2],wc_extra=[.5,.5,.3,.2,.1],long_margin=.305,long_growth=.02,transition_growth=[.045,.04,.035,.025,.02],description='省外终端复购和青花结构恢复需额外兑现；加大资本及酒龄存货配套，不只是升倍数。'))
    add('cash_settlement_stress',dict(upstream_delay=2,parent_cash_delta=-2,extra_parent_payment=3,description='母现金初始少2bn、第一年额外偿还资金池3bn，子宣派两年后支付；不改变集团需求但重算母法定利润/现金与股利。'))
    add('rent_cost_stress',dict(rent_cash=.65,description='新租赁现金成本0.65bn替代0.40bn；利润、资金、法定利润、尾期全部传导；非已知合同额。'))
    add('capital_overrun',dict(capex=[3.3,3.6,3.4,2.4,1.8],description='建设与支付额追加3.1bn，收益不变；增长也可能毁损价值。'))
    add('deposit_classification_low',dict(initial_liquid_delta=-1,description='Q3其他流动资产中额外1bn非金融资产；不重复扣租债。'))
    add('low_legal_cash_capacity',dict(opening_sub_RE_override=4.27482408,opening_parent_RE_override=21.0,parent_cash_delta=-6.0,upstream_delay=2,nci_cash_buffer_multiple=2.0,description='子初始RE取近似值30%、母RE210亿元、母现金少60亿元、上划延迟2年、少数现金隔离取账面权益2倍；联合不利预算非已知损失。'))
    add('high_legal_cash_capacity',dict(opening_sub_RE_override=14.2494136,opening_parent_RE_override=26.0,parent_cash_delta=.5,upstream_delay=0,nci_cash_buffer_multiple=0,description='母RE260亿元/现金多5亿元，少数不另隔离金融现金；对应经济现金归属的较宽边界，不是事实。'))
    add('zero_initial_sub_RE',dict(opening_sub_RE_override=0,description='子公司初始可分RE取零的极端法律容量诊断，普通股资产并未被核销；只分未来新利润。'))
    add('nci_cash_zero',dict(nci_cash_buffer_multiple=0,description='少数现金隔离为零的单因素上界代理；经营利润仍扣少数份额。'))
    add('nci_cash_double_book',dict(nci_cash_buffer_multiple=2.0,description='少数现金隔离采用两倍账面权益的单因素不利代理，非严格现金归属上限。'))
    add('slow_capital_release',dict(payout_release_start=16,description='额外现金释放推迟十年；不是永锁，逐年检验现金和法定约束。'))
    out={}
    for n,p in specs.items():
        rows=run(p);out[n]={'assumptions':p,'rows':rows,'value_9pct':valuation(rows,.09,p['long_growth']),
          'value_95pct':valuation(rows,.095,p['long_growth']),'value_10pct':valuation(rows,.10,p['long_growth'])}
    return out

def liquidation_fixture():
    # Genuine use of the same loss-first production legal engine, with investment cost/loan/cash separately bridged.
    # Completely specified synthetic subsidiary: assets cash2+stock8+plant10+loan_to_parent4=24; external debt6; netassets18.
    assets=24.;debt=6.;book_equity=18.;sale_cash=2+8*.5+10*.6;collection=4.;closure_cost=1.
    liquidation_equity=sale_cash+collection-debt-closure_cost # 9
    investment_cost=12.;parent_loan_receivable=3.;loan_recovery=1.
    # This latter loan is a DIFFERENT subsidiary already insolvent, no entry in the first 24 assets.
    parent_cash_open=30.;parent_pool_payable=4.
    parent_cash_after_pool=parent_cash_open-parent_pool_payable
    cash_received=liquidation_equity+loan_recovery
    loss=(liquidation_equity-investment_cost)+(loan_recovery-parent_loan_receivable)
    parent=legal_step(10.,2.,10.,loss,100.,parent_cash_after_pool+cash_received)
    closing_cash=parent_cash_after_pool+cash_received-parent['dividend']
    assert liquidation_equity==9 and loss==-5 and parent['dividend']==5 and closing_cash==31
    assert abs(book_equity-(assets-debt))<1e-12
    return dict(assets=assets,external_debt=debt,book_equity=book_equity,asset_sale_cash=sale_cash,
      parent_pool_repayment=collection,closure_cash=closure_cost,subsidiary_liquidation_equity=liquidation_equity,
      mother_investment_cost=investment_cost,other_failed_sub_loan_cost=parent_loan_receivable,
      other_failed_sub_loan_recovery=loan_recovery,parent_legal_loss=loss,parent=parent,
      closing_cash=closing_cash,note='合成fixture非汾酒清算估值；投资成本损失/贷款损失减少RE，不二次扣现金；资本/公积不作为普通分红。')

def tests():
    # Formal production engine called with hand-calculable inputs, not stand-alone tautologies.
    a=legal_step(-4,0,10,3,100,100);assert a['dividend']==0 and a['re']==-1 and a['appropriation']==0
    b=legal_step(-4,0,10,10,100,100);assert abs(b['appropriation']-.6)<1e-10 and abs(b['dividend']-5.4)<1e-10
    c=legal_step(0,4.8,10,10,100,100);assert abs(c['appropriation']-.2)<1e-10 and abs(c['dividend']-9.8)<1e-10
    capital_loss=legal_step(0,5,10,-3,100,100);assert capital_loss['dividend']==0 and capital_loss['re']==-3 and capital_loss['reserve']==5
    d=legal_step(0,5,10,10,100,3);assert d['dividend']==3 and d['re']==7 and d['reserve']==5
    q=copy.deepcopy(BASE);q['upstream_delay']=2
    r=run(q,4)
    assert r[0]['sub_dividend_received']==0 and r[0]['sub_dividend_declared']>0
    assert r[2]['sub_dividend_received']>0
    # DCF formula via formal valuation function: cash distributions of1 each, terminal D6=1 at r10,g0 -> value10.
    toy=[dict(year=i,holder_cash=1) for i in range(1,6)]
    assert abs(valuation(toy,.10,0)['equity_value']-10)<1e-10
    return dict(capital_protection=capital_loss,loss_first=a,reserve_after_loss=b,reserve_cap=c,cash_cap=d,delayed_receipts_test=True,
                formal_valuation_annuity_test=10,liquidation=liquidation_fixture())

def control_boundary():
    # Separately normalized business earning power, not fitted to DDM. Cash-rent basis; no financial income in profit.
    cases=[]
    for name,inside,outside,other,margin,r,g,roic in [
        ('low',13.5,20.0,.5,.275,.10,.01,.25),('high',14.0,22.0,.6,.29,.09,.015,.30)]:
        revenue=inside+outside+other;earnings=revenue*margin
        reinvest=g/roic;multiple=(1-reinvest)/(r-g)
        initial=opening(BASE)['cash'];necessary=.15*revenue
        # Already committed growth payments beyond maintenance paid from surplus before steady earning-power valuation.
        unfinished_net_growth=8.0
        excess=initial-necessary-unfinished_net_growth
        business=earnings*multiple
        cases.append(dict(name=name,revenue=revenue,op_common_earnings_after_cash_rent=earnings,
          rate=r,growth=g,incremental_ROIC=roic,reinvestment_share=reinvest,justified_multiple=multiple,
          current_common_liquid=initial,necessary_cash=necessary,remaining_growth_cash=unfinished_net_growth,
          excess_cash=excess,lease_debt_additional_deduction=0,value=(business+excess)/SHARES))
    return cases

def ri_value(rows,r,g):
    # Residual income is a separate equity-book valuation chain, including actual dividends and book changes.
    # Net operating/cash common equity excludes the separately buffered minority assets.
    initial=rows[0]['opening']['equity']
    residual=sum((z['common_profit']-r*z['opening']['equity'])/(1+r)**z['year'] for z in rows)
    terminal=rows[-1]['holder_cash']*(1+g)/(r-g)
    continuation=(terminal-rows[-1]['closing']['equity'])/(1+r)**len(rows)
    total=initial+residual+continuation
    assert abs(total-valuation(rows,r,g)['equity_value'])<1e-7
    return dict(opening_common_equity=initial,residual_income_pv=residual,
       terminal_common_equity=terminal,closing_book_equity=rows[-1]['closing']['equity'],
       continuation_residual_pv=continuation,value_per_share=total/SHARES,rate=r,growth=g)

def formal_auxiliary():
    paths=[]
    for label,r,g,inside,outside,other,margin,terminal_margin in [
      ('low',.10,.01,[13.5]*5,[19.8,20,20,20,20],[.5]*5,[.275]*5,.275),
      ('high',.09,.015,[13.5,13.7,13.8,13.9,14],[19.8,20.5,21,21.5,22],[.5,.5,.6,.6,.6],[.275,.28,.285,.29,.29],.29)]:
        p=copy.deepcopy(BASE);p.update(inside=inside,outside=outside,other=other,
          net_operating_margin=margin,long_margin=terminal_margin,long_growth=g,
          transition_growth=[g]*5,description='独立正常化盈利能力路径；沿同一实际母子付款和必要资本桥，剩余收益折现。')
        rows=run(p)
        paths.append(dict(name=label,assumptions=p,rows=rows,valuation=ri_value(rows,r,g),
          convergence=convergence(rows,r,g)))
    return paths

def convergence(rows,r,g):
    horizons=[60,120,240,480,960]
    values=[dict(year=n,**valuation(rows[:n],r,g)) for n in horizons if n<=len(rows)]
    keys=['cash','parent_cash','sub_cash','parent_re','sub_re','parent_reserve','sub_reserve',
      'parent_capital','sub_capital','parent_capital_surplus','equity','net_operating_capital',
      'lease','rou','trade_receivable','pool_payable','dividend_receivable','dividend_payable',
      'sub_investment_cost','pledged','financial_debt','shares']
    fixed={'parent_reserve','sub_reserve','parent_capital','sub_capital','parent_capital_surplus',
      'sub_investment_cost','shares'}
    comparison=[]
    for a,b in [(60,120),(120,240),(240,480),(480,960)]:
        if b>len(rows):continue
        old=rows[a-1];new=rows[b-1];fields={}
        for k in keys+['required_cash','required_cash_including_declared_dividends']:
            av=old[k] if k.startswith('required_cash') else old['closing'][k]
            bv=new[k] if k.startswith('required_cash') else new['closing'][k]
            normalized_old=av/old['revenue'];normalized_new=bv/new['revenue']
            expected=av if k in fixed else av*(1+g)**(b-a)
            fields[k]=dict(old=av,new=bv,absolute_change=bv-av,expected_under_declared_scaling=expected,
              absolute_scaling_residual=bv-expected,relative_scaling_residual=(bv-expected)/max(1,abs(expected)),
              old_per_revenue=normalized_old,new_per_revenue=normalized_new,
              absolute_ratio_change=normalized_new-normalized_old,
              scaling_rule='nominal_constant' if k in fixed else 'growth_plus_possible_fixed_offset')
        # Complete state, including overdue-dividend maturity queue, is retained in every row.
        comparison.append(dict(from_year=a,to_year=b,fields=fields,
          holder_dividend_growth_error=new['holder_cash']/rows[b-2]['holder_cash']-(1+g),
          parent_legal_limit=new['holder_limited_by_legal'],parent_cash_limit=new['holder_limited_by_cash']))
    # Full state convergence permits an economically explicit fixed historical-capital offset.
    # x_t = a * revenue_t + b; a is the growing capital intensity and b the old nominal stock.
    affine=[]
    for n in horizons:
        if n>len(rows):continue
        cur,prev=rows[n-1],rows[n-2];fit={}
        for k in keys+['required_cash','required_cash_including_declared_dividends']:
            curx=cur[k] if k.startswith('required_cash') else cur['closing'][k]
            prevx=prev[k] if k.startswith('required_cash') else prev['closing'][k]
            if g and k not in fixed:
                coefficient=(curx-prevx)/(cur['revenue']-prev['revenue'])
                offset=curx-coefficient*cur['revenue']
            else:coefficient=0.;offset=curx
            fit[k]=dict(growing_intensity=coefficient,nominal_fixed_offset=offset,
              absolute_one_year_change=curx-prevx,relative_one_year_change=(curx-prevx)/max(1,abs(prevx)))
        affine.append(dict(year=n,fields=fit))
    affine_deltas=[]
    for a,b in zip(affine,affine[1:]):
        f={}
        for k,v in b['fields'].items():
            av=a['fields'][k]
            f[k]={'intensity_absolute_change':v['growing_intensity']-av['growing_intensity'],
              'fixed_offset_absolute_change':v['nominal_fixed_offset']-av['nominal_fixed_offset'],
              'fixed_offset_relative_change':(v['nominal_fixed_offset']-av['nominal_fixed_offset'])/max(1,abs(av['nominal_fixed_offset']))}
        affine_deltas.append(dict(from_year=a['year'],to_year=b['year'],fields=f))
    final=values[-1]['per_share']
    if len(rows)>=960:
        assert abs(values[-1]['per_share']-values[-2]['per_share'])<1e-8
        assert max(abs(v['intensity_absolute_change']) for v in affine_deltas[-1]['fields'].values())<1e-9
        assert max(abs(v['fixed_offset_absolute_change']) for v in affine_deltas[-1]['fields'].values())<1e-3 # billion CNY; separately disclose absolute floating precision
    return dict(horizon_values=values,absolute_PV_changes=[values[i]['per_share']-values[i-1]['per_share'] for i in range(1,len(values))],
      relative_PV_changes=[(values[i]['per_share']-values[i-1]['per_share'])/max(1,abs(values[i]['per_share'])) for i in range(1,len(values))],
      state_comparisons=comparison,affine_state_fits=affine,affine_state_fit_changes=affine_deltas,
      statement='完整状态绝对差与营收尺度差均报告；固定资本与存量净经营资本常数项不假装同比例消失，延长实际现金递推检验其估值影响。')

def main():
    sc=scenarios();
    for z in sc.values():z['convergence']=convergence(z['rows'],.095,z['assumptions']['long_growth'])
    base=sc['base'];rows=base['rows']
    # Exact same full Y5 state is used for both future terminal endpoints; no recomputation with alternate first-five-year assumptions.
    tv={'low':valuation(rows,.10,BASE['long_growth'],5)['per_share'],'high':valuation(rows,.09,BASE['long_growth'],5)['per_share']}
    value={'low':base['value_10pct']['per_share'],'high':base['value_9pct']['per_share']}
    result={'schema':'fenjiu-independent-economic-common-equity-v1','unit':'CNY billion; shares billion',
      'information_cutoff':CUT,'facts':FACTS,'tests':tests(),'scenarios':sc,'control_earning_power_boundary':control_boundary(),'formal_auxiliary_residual_income':formal_auxiliary(),
      'core_value_exact':value,'core_value_rounded':{'low':round(value['low']),'high':round(value['high'])},
      'return_model':{'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':CUT,
        'base_case_distributions_per_share':[round(x['holder_per_share'],6) for x in rows[:5]],
        'base_case_terminal_equity_value_range_per_share':{'year_5':{k:round(v,6) for k,v in tv.items()}}},
      'year5_full_shared_state':rows[4]['closing'],
      'five_year_identity':{str(r):sum(x['holder_cash']/(1+r)**x['year'] for x in rows[:5])/SHARES+valuation(rows,r,.015,5)['per_share']/(1+r)**5 for r in (.09,.10)},
      'tail_convergence':{'penultimate_year':rows[-2]['year'],'last_year':rows[-1]['year'],'penultimate_distribution':rows[-2]['holder_cash'],'last_distribution':rows[-1]['holder_cash'],
        'ratio':rows[-1]['holder_cash']/rows[-2]['holder_cash'],'target':1.015,
        'legal_slack':rows[-1]['closing']['parent_re'],'cash_floor':rows[-1]['required_cash']}}
    for r,k in [(.09,'high'),(.10,'low')]:assert abs(result['five_year_identity'][str(r)]-value[k])<1e-9
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()

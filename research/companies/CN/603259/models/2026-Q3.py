#!/usr/bin/env python3
"""CN:603259 2026-Q3. Python standard library only. Monetary unit CNY billion.
Run: python 2026-Q3.py --out directory. Outputs are deterministic and standalone.
No network, prices, external templates, or other companies' model inputs.
"""
import argparse,copy,json,math,pathlib,sys
ASOF='2026-10-26T22:21:00+00:00'
BASE=dict(revenue0=61.45,growth=[.14,.12,.10,.09,.08,.07,.06,.05,.04,.03]+[.025]*10,
 margins=[.40,.395,.39,.385,.38,.37,.36,.345,.33,.32]+[.32]*10,tax=.20,minority=.008,
 capex=[9,9.5,10,10.5,11],nwc_ratio=.30,nwc0=18.435,fixed0=32.032,daratio=.062,
 roic=.18,rate=.10,terminal_growth=.025,shares=3.034904066,
 liquid0=(37.13398285321+16.34323390369-7.60788472996-.60874924152),locked0=7.60788472996,
 financial0=9.46125728685,financial_recovery=.80,maturing0=2.46276916798,maturing_recovery=.95,
 debt0=8.52518110633,equity0=96.84524897981,parent_cash0=8.98937759,parent_profit0=3.33548544813,
 parent_reserve0=1.4918785775,parent_registered=3.034904066,receivable0=4.31167951917,
 upstream=.55,upstream_eligible=.85,upstream_delay=1,upstream_leak=.025,parent_cost=.40,
 policy_start=1,payout=.35,liquidity_ratio=.10,financial_yield=.016,asset_release_delay=2,asset_release_cost=.02,
 tail_strategy='budgeted_upstream',realization_delay=1,realization_cost=.025,issue_year=0,issue_proceeds=0,issue_shares=0,internal_payment=0,cyber_cost=0,exit_year=0,
 exit_fixed_recovery=.45,exit_nwc_recovery=.80,exit_cost=5,extra_exit_claim=0,
 scenario='base',effective_years=[],affected='集团经营；无锡上市母公司付款；境外为经济预算非逐法人法定账',changed=[],frozen=['起点资产与既有股本，除明示融资','所有财务以人民币计量'])

def after_tax_profit(profit,tax):
    """No immediate refund or cross-entity offset for a loss without evidenced current recoverability.
    Negative EBIT is an economic loss diagnostic, not an established legal tax-loss balance.
    Future use is unknown and has zero recognized value in this model.
    """
    return profit*(1-tax) if profit>0 else profit

def allocation(cash,profit,request,reserve,registered,current_profit=None):
    """Actual parent legal calculation: losses first; reserve uses REGISTERED capital.
    profit includes signed opening undistributed balance, not just positive current income.
    """
    appropriable=max(0,min(profit,current_profit)) if current_profit is not None else max(0,profit)
    add=min(max(0,registered*.5-reserve),appropriable*.10)
    reserve+=add; profit-=add
    pay=min(max(0,cash),max(0,profit),max(0,request))
    return pay,profit-pay,reserve,add

def settle_exit(cash,assets,debt,cost,tax,minority,other_claims=0):
    gross=cash+assets; senior=debt+cost+tax+minority+other_claims
    return dict(gross=gross,senior=senior,common=max(0,gross-senior),unpaid=max(0,senior-gross),feasible=gross>=senior)

def run(p):
    p=copy.deepcopy(p);rev=p['revenue0'];nwc=p['nwc0'];fixed=p['fixed0'];cash=p['liquid0'];locked=p['locked0'];fin=p['financial0'];mature=p['maturing0'];debt=p['debt0'];equity=p['equity0'];shares=p['shares'];registered=p['parent_registered']
    pcash=p['parent_cash0'];ret=p['parent_profit0'];reserve=p['parent_reserve0'];receivable=p['receivable0'];declared={0:receivable};rows=[];dead=False
    for y in range(1,21):
        opening=dict(cash=cash,parent_cash=pcash,locked=locked,financial=fin,maturing=mature,debt=debt,equity=equity,shares=shares,parent_profit=ret,parent_reserve=reserve,receivable=receivable,fixed=fixed,nwc=nwc,parent_registered=registered)
        growth=p['growth'][y-1];revnew=rev*(1+growth);margin=p['margins'][y-1];ebit=revnew*margin
        nopat=after_tax_profit(ebit,p['tax'])*(1-p['minority'])
        da=revnew*p['daratio'];nwcnew=revnew*p['nwc_ratio'];dnwc=nwcnew-nwc
        if y<=5: capex=p['capex'][y-1]
        else: capex=da+max(0,nopat*growth/(1+growth)/p['roic']-dnwc)
        # No pretending a contraction instantly liquidates installed fixed assets.
        fixednew=fixed+capex-da
        gross_interest=debt*.045
        interest=(gross_interest*(1-p['tax']) if ebit>=gross_interest else gross_interest-max(0,ebit)*p['tax'])
        financial_income=cash*p['financial_yield'];parent_fin=pcash*p['financial_yield']
        cyber=p['cyber_cost'] if y in (1,2) else 0
        op_common=nopat-interest-cyber;fcfe=op_common+da-capex-dnwc
        cash+=fcfe+financial_income;pcash+=parent_fin-p['parent_cost']
        # Parent costs are already inside EBIT: transfer their cash effect back to subsidiaries to avoid double count.
        unlock=p['locked0']/2 if y<=2 else 0;locked-=unlock;cash+=unlock
        mature_gross=mature*p['maturing_recovery'] if y==2 else 0;mature_loss=(mature-mature_gross) if y==2 else 0
        if y==2:cash+=mature_gross;mature=0
        sale_gross=fin*.86 if y==3 else 0;sale_friction=fin*(.86-p['financial_recovery']) if y==3 else 0
        sale_net=sale_gross-sale_friction;sale_loss=(fin-sale_net) if y==3 else 0
        if y==3:cash+=sale_net;fin=0
        debt_due=debt if y==1 else 0;debtpay=min(debt_due,max(0,cash));cash-=debtpay;debt-=debtpay;unpaid_debt_due=debt_due-debtpay
        parent_debtpay=min(2.2994,debtpay);pcash-=parent_debtpay
        issue_cash=p['issue_proceeds'] if y==p['issue_year'] else 0;issue_shares=p['issue_shares'] if issue_cash else 0
        cash+=issue_cash;pcash+=issue_cash;shares+=issue_shares;registered+=issue_shares # RMB1 nominal per newly issued share, not issue proceeds
        internal=p['internal_payment'] if y==1 else 0;pcash-=internal
        # Six identified PRC dividend debtors support starting AR; future source budget follows new common profit.
        active=y>=p['policy_start']
        upstream=p['upstream'] if active else BASE['upstream']
        eligible=p['upstream_eligible'] if active else BASE['upstream_eligible']
        delay=p['upstream_delay'] if active else BASE['upstream_delay']
        declaration=max(0,op_common)*upstream*eligible
        declared[y]=declaration;ret+=declaration+parent_fin-p['parent_cost']
        due_keys=[k for k in declared if k<=y-delay]
        payable=sum(declared[k] for k in due_keys)
        # Delay zero still collects existing old AR only once in year one.
        # Existing receivable is already included by due_keys; no second recognition.
        sub_available=max(0,cash-pcash-revnew*p['liquidity_ratio'])
        gross_up=min(payable,sub_available)
        # unpaid due amounts remain tracked and are attempted in following year
        remaining=gross_up
        for k in sorted(due_keys):
            collected=min(declared[k],remaining);declared[k]-=collected;remaining-=collected
        leakage=gross_up*p['upstream_leak'];net_up=gross_up-leakage;pcash+=net_up;cash-=leakage;ret-=leakage
        receivable+=declaration-gross_up
        request=max(0,op_common)*p['payout'];group_available=max(0,cash-revnew*p['liquidity_ratio'])
        # Parent legal retained balance is distinct from actual available money and group cash.
        pay,ret,reserve,reserve_add=allocation(min(max(0,pcash-1),group_available),ret,request,reserve,registered,declaration+parent_fin-p['parent_cost']-leakage)
        pcash-=pay;cash-=pay
        ni=op_common+financial_income-sale_loss-mature_loss-leakage
        equity+=ni-pay+issue_cash
        r=dict(year=y,calendar_label=f'Y{y}',revenue=revnew,growth=growth,ebit_margin=margin,ebit=ebit,nopat_common=nopat,
          tax_expense_budget=max(0,ebit)*p['tax'],interest_tax_shield=gross_interest-interest,current_tax_refund=0,negative_ebit_not_monetized=max(0,-ebit),interest=interest,financial_income=financial_income,op_common=op_common,depreciation=da,capex=capex,nwc=nwcnew,
          delta_nwc=dnwc,fixed=fixednew,fcfe=fcfe,unlock=unlock,asset_sale_gross=sale_gross,asset_sale_friction=sale_friction,
          asset_sale_net=sale_net,maturing_receipt=mature_gross,asset_loss=sale_loss+mature_loss,debt_payment=debtpay,
          parent_debt_payment=parent_debtpay,issue_cash=issue_cash,issue_shares=issue_shares,internal_payment=internal,
          parent_declaration=declaration,parent_gross_receipt=gross_up,parent_net_receipt=net_up,upstream_leakage=leakage,
          parent_receivable=receivable,parent_financial_income=parent_fin,parent_cost=p['parent_cost'],parent_profit=ret,
          parent_registered=registered,parent_reserve=reserve,parent_reserve_add=reserve_add,parent_cash=pcash,requested_dividend=request,
          dividend=pay,dps=pay/shares,principal_return=0,cash=cash,locked=locked,financial=fin,maturing=mature,debt=debt,
          equity=equity,shares=shares,net_income=ni,opening=opening,liquidity_need=revnew*p['liquidity_ratio'],liquidity_increment=(revnew-rev)*p['liquidity_ratio'],economic_extractable_fcfe=fcfe-(revnew-rev)*p['liquidity_ratio'],unpaid_debt_due=unpaid_debt_due,feasible=cash>=0 and pcash>=0 and unpaid_debt_due<=1e-9)
        assert abs(cash-(opening['cash']+fcfe+financial_income+unlock+sale_net+mature_gross-debtpay+issue_cash-leakage-pay))<1e-8
        assert abs(equity-(opening['equity']+ni-pay+issue_cash))<1e-8
        assert abs(pcash-(opening['parent_cash']+parent_fin-p['parent_cost']-parent_debtpay+issue_cash-internal+net_up-pay))<1e-8
        assert abs(receivable-(opening['receivable']+declaration-gross_up))<1e-8
        assert pay<=max(0,opening['parent_profit']+declaration+parent_fin-p['parent_cost'])+1e-8
        rows.append(r);rev=revnew;fixed=fixednew;nwc=nwcnew
        if p['exit_year']==y:
            assets=fixed*p['exit_fixed_recovery']+nwc*p['exit_nwc_recovery']+locked+fin*p['financial_recovery']+mature*p['maturing_recovery']
            e=settle_exit(cash,assets,debt,p['exit_cost'],max(0,assets-fixed-nwc-locked-fin-mature)*.25,0,p['extra_exit_claim'])
            r['before_exit_feasible']=r['feasible'];r['exit']=e;r['exit_common_dps']=e['common']/shares;r['feasible']=r['feasible'] and e['feasible'];dead=True;break
        if not r['feasible']:
            r['funding_failure']=dict(unpaid_debt_due=unpaid_debt_due,unfunded_group_operating_cash=max(0,-cash),unfunded_parent_cash=max(0,-pcash),overlap_note='parent and group deficits are not additive; diagnostic cash is unfunded, not a completed payment')
            dead=True;break
    feasible=all(r['feasible'] for r in rows)
    def terminal(t,rate):
        if not feasible:return None
        if dead:
            if p['exit_year']<=t:return 0
            return sum(z['dividend']/z['shares']/(1+rate)**(z['year']-t) for z in rows[t:])+rows[-1]['exit_common_dps']/(1+rate)**(len(rows)-t)
        rr=rows[t-1]
        end=rows[-1];g=p['terminal_growth']
        if p['tail_strategy']=='budgeted_upstream':
            steady=end['nopat_common']*(1+g)*(1-g/p['roic']-p['upstream']*p['upstream_eligible']*p['upstream_leak'])-end['revenue']*g*p['liquidity_ratio']
            operating=sum((z['economic_extractable_fcfe']-z['upstream_leakage'])/(1+rate)**(z['year']-t) for z in rows[t:])+steady/(rate-g)/(1+rate)**(len(rows)-t)
        elif p['tail_strategy']=='uniform_realization':
            steady=(end['nopat_common']*(1+g)*(1-g/p['roic'])-end['revenue']*g*p['liquidity_ratio'])*(1-p['realization_cost'])
            operating=(sum(z['economic_extractable_fcfe']*(1-p['realization_cost'])/(1+rate)**(z['year']-t) for z in rows[t:])+steady/(rate-g)/(1+rate)**(len(rows)-t))/(1+rate)**p['realization_delay']
        else:raise ValueError('unknown tail strategy')
        # Necessary liquidity remains employed in the business. Surplus is an economic recovery budget,
        # not an assertion that every subsidiary can dividend book capital on demand.
        surplus=max(0,rr['cash']-rr['liquidity_need'])
        financial_value=(surplus*(1-p['asset_release_cost'])+rr['locked']+rr['financial']*p['financial_recovery']+rr['maturing']*p['maturing_recovery'])/(1+rate)**max(p['asset_release_delay'],p['upstream_delay'])
        return (operating+financial_value-rr['debt'])/rr['shares']
    rates=[p['rate']+.005,p['rate']-.005]
    tv=[terminal(5,k) for k in rates]
    current=[];tvparts=[]
    for k,t in zip(rates,tv):
        if t is None:current.append(None);tvparts.append(None);continue
        d=sum(r['dps']/(1+k)**r['year'] for r in rows[:5]);v=d+t/(1+k)**5
        current.append(v);tvparts.append((t/(1+k)**5)/v if v else 0)
    if feasible and dead and p['exit_year']<=5:
        current=[sum(r['dps']/(1+k)**r['year'] for r in rows)+rows[-1]['exit_common_dps']/(1+k)**len(rows) for k in rates]
    # Independent earnings-power/franchise method: current normalized economics, no reuse of DCF future revenue or capex.
    # Current revenue x normalized EBIT(35-37%) x tax/minority, replacement upkeep=depreciation.
    # Ten years finite excess growth franchise: 5% reinvestment-driven income growth, 18-20% return on new capital.
    aux=[]
    for k,em,rr in [(rates[0],.35,.18),(rates[1],.37,.20)]:
        income=after_tax_profit(p['revenue0']*em,p['tax'])*(1-p['minority'])
        epv=income/k
        franchise=sum((income*((1.05)**j-(1.05)**(j-1))*(1/k-1/rr)-p['revenue0']*((1.05)**j-(1.05)**(j-1))*p['liquidity_ratio'])/(1+k)**j for j in range(1,11))
        financial=(p['liquid0']+p['locked0']-p['revenue0']*.10+p['financial0']*p['financial_recovery']+p['maturing0']*.95-p['debt0'])*.98/(1+k)**2
        if p['tail_strategy']=='uniform_realization':
            av=(epv+franchise)*(1-p['realization_cost'])/(1+k)**p['realization_delay']
        else:
            fee=p['upstream']*p['upstream_eligible']*p['upstream_leak']
            fee_pv=income*fee/k+sum(income*((1.05)**j-(1.05)**(j-1))*fee/k/(1+k)**j for j in range(1,11))
            av=epv+franchise-fee_pv
        aux.append((av+financial)/p['shares'])
    return dict(parameters=p,annual=rows,current_value=(current if feasible else None),terminal_year5=(tv if feasible else None),terminal_pv_share=(tvparts if feasible else None),distributions=[x['dps'] for x in rows[:5]],auxiliary_value=(aux if feasible else None),auxiliary_scope='baseline_normalization_only_not_this_scenario_forecast',feasible=feasible,forecast_distributions_before_hypothetical_failure=([dict(year=x['year'],dps=x['dps']) for x in rows if x['feasible'] or x.get('before_exit_feasible',False)] if not feasible else []),valuation_status=('complete_economic_realization_budget' if feasible else 'infeasible_no_complete_equity_value'))

def scenarios():
    cases={};cases['base']=run(BASE)
    def add(name,**kw):
        p=copy.deepcopy(BASE);p.update(kw);p['scenario']=name;p['changed']=list(kw);cases[name]=run(p)
    add('cyclical',growth=[-.08,.02,.18,.15,.10,.07,.06,.05,.04,.03]+[.025]*10,margins=[.31,.33,.36,.38,.38,.37,.36,.345,.33,.32]+[.32]*10,capex=[8.5,8,9,10,11],nwc_ratio=.34,effective_years=list(range(1,21)),affected='临床订单延后和商业化去库存；境内外经营实体与母公司上划')
    add('structural',growth=[-.15,-.15,-.05,0,.02]+[.02]*15,margins=[.30,.23,.21,.20,.20]+[.20]*15,capex=[8,7,5,4,4],nwc_ratio=.36,roic=.10,terminal_growth=.015,upstream=.35,upstream_eligible=.65,upstream_delay=2,effective_years=list(range(1,21)),affected='条件性美国客户迁移30-40%并非法律全面停业，商业化中国/海外产能共同降利用率')
    add('upside',growth=[.20,.18,.15,.12,.10,.08,.07,.06,.04,.03]+[.025]*10,margins=[.42,.42,.41,.40,.39,.38,.37,.35,.34,.33]+[.33]*10,capex=[10,11,12,12,12],nwc_ratio=.29,roic=.20,effective_years=list(range(1,11)),affected='小分子和TIDES规模兑现；合全相关98.9%普通股权益已经在少数预算中处理')
    add('upstream_delay_3',upstream_delay=3,effective_years=list(range(1,21)),affected='母公司六家直接分红来源与境外中间层，现金滞后三年，不撤销已确认利润')
    add('old_losses_budget',upstream_eligible=.40,tail_strategy='uniform_realization',realization_delay=3,realization_cost=.05,effective_years=list(range(1,21)),affected='未披露海外逐法人旧亏损/税基，只有40%新利润可形成宣派预算；经济现金实现另延迟三年并付5%费用')
    add('parent_settlement',internal_payment=3,effective_years=[1],affected='母公司集团资金池额外净还款30亿元，集团现金不减少')
    add('capital_intensity',capex=[12,13,14,15,16],nwc_ratio=.36,roic=.13,effective_years=list(range(1,21)),affected='全球冗余产能及库存融资，保持销量路径，增加投资且降低终态资本效率')
    add('margin_minus_3pt',margins=[x-.03 for x in BASE['margins']],effective_years=list(range(1,21)),affected='全部经营业务单位利润诊断，不是完整政策情景')
    add('cyber',cyber_cost=1,margins=[.39,.385]+BASE['margins'][2:],effective_years=[1,2],affected='DEL生物学与客户索赔条件压力，非已确认10亿元损失')
    add('financial_recovery_50',financial_recovery=.50,asset_release_delay=5,effective_years=[3,5],affected='非经营投资回收及跨境分配延迟，不计投资收益第二份价值')
    add('equity_financing',issue_year=2,issue_proceeds=10,issue_shares=.10,effective_years=[2],affected='纯融资诊断：资金100亿元换1亿新股，非公司计划或证券报价')
    add('finite_exit_10',exit_year=10,effective_years=[10],affected='集团第10年停止经营，资产折收并先付退出成本债税；非核心情景')
    add('failed_exit_3',exit_year=3,extra_exit_claim=200,effective_years=[3],affected='反例：额外高级索赔2000亿元，必须保留未偿且禁止正普通股清算分配')
    add('late_policy_year3',policy_start=3,growth=BASE['growth'][:2]+[-.20,-.12,0]+[.015]*15,margins=BASE['margins'][:2]+[.25,.20,.20]+[.20]*15,capex=[9,9.5,7,5,4],roic=.10,terminal_growth=.015,upstream=.40,upstream_delay=2,effective_years=list(range(3,21)),affected='仅第3年起条件性限制扩大并发生客户迁移，前两年经营预测不改')
    add('cost_of_capital_plus_1pt',rate=.11,effective_years=list(range(1,21)),affected='仅资本成本诊断，经营和现金不变')
    add('financing_then_exit',issue_year=2,issue_proceeds=10,issue_shares=.10,exit_year=10,effective_years=[2,10],affected='融资后有限退出组合，退出分母必须包含新增股本')
    return cases

def tests():
    # Literal examples are sent through production legal and waterfall functions.
    assert allocation(100,-5,80,0,100)==(0,-5,0,0)
    assert allocation(100,20,80,45,100)==(18,0,47,2)
    assert allocation(3,20,80,50,100)==(3,17,50,0)
    assert settle_exit(5,10,8,2,1,1)['common']==3
    e=settle_exit(1,2,8,2,1,1);assert not e['feasible'] and e['unpaid']==9 and e['common']==0
    p=copy.deepcopy(BASE);p.update(parent_profit0=-50,parent_cash0=0,upstream=0,financial_yield=0,parent_cost=0,debt0=0)
    r=run(p);assert all(x['dividend']==0 for x in r['annual']) and abs(r['annual'][0]['parent_profit']+50+r['annual'][0]['upstream_leakage'])<1e-10
    p=copy.deepcopy(BASE);p.update(upstream=0,upstream_delay=1,parent_cost=0,financial_yield=0,payout=0,debt0=0)
    r=run(p);assert abs(r['annual'][0]['parent_gross_receipt']-BASE['receivable0'])<1e-8
    assert abs(r['annual'][0]['parent_profit']-(BASE['parent_profit0']-r['annual'][0]['parent_reserve_add']-r['annual'][0]['upstream_leakage']))<1e-10
    p=copy.deepcopy(BASE);p.update(capex=[1000]*5)
    fail=run(p);assert not fail['feasible'] and len(fail['annual'])==1 and fail['current_value'] is None and fail['terminal_year5'] is None and fail['annual'][0]['unpaid_debt_due']>0
    p=copy.deepcopy(BASE);p.update(issue_year=2,issue_proceeds=10,issue_shares=.1)
    funded=run(p);assert abs(funded['annual'][1]['parent_registered']-3.134904066)<1e-10 and abs(funded['annual'][1]['parent_reserve']-1.567452033)<1e-10
    assert after_tax_profit(-10,.20)==-10 and after_tax_profit(10,.20)==8
    p=copy.deepcopy(BASE);p['margins']=[-.10]+p['margins'][1:];loss_case=run(p)
    lr=loss_case['annual'][0];assert loss_case['feasible'] and lr['cash']>0 and lr['ebit']<0
    assert abs(lr['nopat_common']-lr['ebit']*.992)<1e-10 and lr['tax_expense_budget']==0 and lr['current_tax_refund']==0 and lr['interest_tax_shield']==0
    assert loss_case['annual'][1]['tax_expense_budget']>0 # no undocumented cross-entity or later offset
    return {'actual_function_counterexamples':11,'negative_ebit_cash_feasible_test':loss_case,'nonexit_failure_test':fail,'cash_equity_receivable_assertions':'all annual rows all scenarios','no_price_inputs':True}

# Embedded reader prose is below; all numerical tables are generated from model output.
REPORT_TEMPLATE='# 药明康德（CN:603259）：商业化兑现很强，跨境可复制性仍是价值的关键\n\n信息截止：2026-10-26\n\n金额除每股数据外为人民币亿元；报告期为2026年第三季度，预测年度为资料截止后的周年预算。\n\n## 一句话结论\n\n**药明康德具备长期拥有的商业基础，核心在于把早期分子服务转成可靠、规模化的商业生产；本期现金增长验证了这条路径，但没有消除客户迁移和资本回报下降的风险。** 核心合理价值区间为@VALUE@元。采纳的路径保留未来五年两位数附近的平均收入增长，同时让经营利润率与新增资本回报逐步下降。最危险的反证是全球药品需求继续增长，公司却因地域限制、客户双供或数据事件失去高价值后期订单。\n\n这里不对报告时点证券价格作判断，也不主张已识别可靠市场错价。持续覆盖意味着值得继续研究其商业和普通股现金，不构成交易指令。\n\n## 客户真正购买的是工艺连续性，收益集中在成功分子的后端\n\n试剂、溶剂、科研人才和设备进入发现、测试、工艺开发及GMP生产体系，再交付给药企的研发、注册与采购部门，最终由临床疗效、药品批准、支付和患者需求决定批量。客户拥有药物知识产权和终端定价权；药明取得的是研发效率、质量可靠性和制造成本带来的服务报酬。公司不承担全部新药研发成本，也没有自动取得药物商业成功的全部利润。\n\n2026年前三季度化学业务收入393.62亿元，同比增长51.52%，占持续经营收入86.4%；其中小分子D&M收入235.8亿元、增长65.6%，TIDES收入115.2亿元、增长46.9%。测试业务39.11亿元、增长31.97%，生物学21.88亿元、增长12.35%。小分子商业化项目103个、III期94个，前三季度两类合计增加23个；R到D转化314个，D&M新增分子1,089个。[Q3]\n\n这些数据支持“客户产品成功、原有产能释放和工艺复用共同提高收益”的解释。研发早期的新化合物数量主要衡量引流和交付活动；3,863个D&M项目中3,264个仍处临床前或I期，不能把每个项目赋予相同成功率和收入。商业化项目数也没有公开单项目销售、批次、独供程度或合约期限，因此收入预测从已实现业务和新增产能预算出发，不由管线数量直接乘出。\n\n后端项目更难替换：新供应商需要完成技术转移、分析方法、质量验证、注册变更和爬坡。这种摩擦有利于已有分子延续，却不能保证新分子始终进入同一供应商。2025年前五客户收入占48.11%，前五供应商采购占11.25%，显示客户一侧更有集中议价权。面对大客户，供应可靠性重要，但客户同样有动力双供和自建。[FY] 我更相信公司能够保留显著制造优势，同时接受利润份额被客户和新增海外成本逐步分享。因此五年收入继续增长，EBIT率从40%降至38%，第十年降至32%；没有另外加上“龙头溢价”。\n\n## 行业增长真实，新增供给和客户价格压力也真实\n\n全球宏观环境不支持把本期38.6%的增速当作常态。IMF十月预测2026/2027全球实际增长3.1%/3.4%；这对创新药的影响主要通过融资、药企预算、物流能源成本与汇率传递，而非GDP直接决定药明收入。[IMF] 本期财务费用3.29亿元，虽然利息收入7.83亿元高于利息费用1.63亿元，汇率及其他项目仍使财务费用为正。人民币收益不应假设海外收入完全自然对冲。\n\n创新药研发没有停止。FDA公布2025年CDER批准46个新药，这是行业供给持续形成的证据，不是药明获单或临床成功率的证明。[FDA] 礼来2026Q2收入增长48%，销量增长60%而实现价格下降13%，研发投入增长14%；其新增美国制造投入又提示客户可能把部分规模利润留在内部。[Lilly] 没有公开合同把上述产品与药明订单逐项对应，故这里只用于验证终端量增、定价和自建三种力量并存。\n\n竞争者Bachem的2026H1收入增长4.3%、EBIT率16.6%，商业API收入下降21%，临床开发收入增长35.4%；Building K开始商业GMP生产，全年计划投资3.5—4亿瑞郎。[Bachem] 这不是可直接横比的药明利润率基准：产品、阶段、会计与规模不同。它有区分力的含义是，新产能投放和临床管线扩展可以与商业交付波动、爬坡费用同时出现。药明的海外布局有客户价值，但将带来地域冗余和新增竞争，资本回报应逐步收敛。\n\n| 领先指标 | 最新观察 | 传导与改判条件 |\n|---|---|---|\n| 持续经营订单 | 767.4亿元，同比+36.4%；H1为664.3亿元 | 支撑近期排产；若应收库存增长快于兑现收入，减少未来现金而非资本化全部订单 |\n| 后期/商业化分子 | 103个商业化、94个III期 | 既有方法与设施复用；连续迁出和双供降价会降低利润率及优势寿命 |\n| TIDES交付 | 9M收入115.2亿元，全年公司预计约+47% | 支持近端增速；客户项目失败和自建会降低新产能利用率 |\n| 早期服务 | 生物学+12.35%、测试+31.97% | 引流未停，但早期扩量不保证商业成功；关注客户续约和质量 |\n| 竞争产能与客户自建 | Bachem新设施投产、礼来继续扩产 | 提高未来供给和议价压力，进入长期利润率及18%增量资本回报 |\n| 现金兑现与投入 | CFO171.93亿元、购建50.82亿元、存货125.93亿元 | 支持经营改善，同时要求维持真实资本与周转预算 |\n\n## 美国政策：经营压力已经出现，法律作用范围仍需逐层区分\n\n2026年6月公布的1260H名单确实列有WuXi AppTec Co., Ltd.。1260H本身首先是识别与报告制度，不是一般资产冻结或全面私人交易禁令；其他法条引用名单才形成具体后果。法院原文第4—5页说明，2024财年NDAA第805条自2026年6月30日起限制国防部与列名公司新订、续订或延长货物、服务或技术采购合同；另有国防部特定游说代表安排、2026财年国土安全部采购、能源部支持及特定联邦研发项目限制。各条款对象不同，不能扩大成美国全部私人药企不得采购。[1260H][Court]\n\n8月7日哥伦比亚特区联邦地区法院准予初步禁令，判决理由第35页说明限制被告执行、实施或以其他方式落实这次对药明康德的认定；第33—34页拒绝当时提出的待上诉暂缓请求。该救济针对本次认定，不是永久撤销全部法律，也不影响其他实体，且不阻止基于充分新证据重新认定。8月9日发行人公告交叉确认获得初步禁令。[Court][Injunction] 截止时点已检查发行人后续公告及可公开取得的官方裁判，未取得新的暂缓或替代裁判；完整后续案卷及独立命令文书未全部取得，因此不作“诉讼终结”或“名单永久移除”的断言。\n\nBIOSECURE相关规定已于2025年12月18日成为Public Law 119-60第851节，适用于规定范围的联邦采购、履约及贷款/拨款资金。原文设OMB认定、指引与FAR修订程序，OMB初始清单法定期限为2026年12月18日，1260H及生技活动是其中一类认定条件，不能仅从六月列名跳过OMB及实施步骤；并按主体类别安排FAR修订后60/90日生效，特定既有协议有五年过渡，不是所有私人商业采购同时归零。[Law] 2026年10月22日Treasury公布、10月26日Federal Register刊载的COINS实施规则仍为NPRM，拟扩大特定美国对外投资限制，不能把拟议生技范围当作已经生效的普遍服务禁令。[Treasury][COINS]\n\n商业后果可能先于最终法律后果。法院理由记载客户和供应商已经取消或迁移部分关系，这些材料部分来自公司和专家宣誓证言，并非全行业独立销量统计。它们足以否定“禁令暂缓就毫无经济损伤”，但不能推导全部美国收入必然流失。核心保留现有项目交付，长期降速；结构压力假设部分美国客户迁移、毛利下滑、重复产能及上划延迟共同发生。药明生物、药明合联是不同上市主体；本报告只把药明合联作为公司持有的联营投资，不把相邻公司的收入和管线合并进药明康德。\n\n## 财务质量：扣非与现金同向改善，但处置收益不能年金化\n\n| 期间 | 收入 | 归母净利 | 扣非归母 | CFO | 现金购建 | CFO减购建 |\n|---|---:|---:|---:|---:|---:|---:|\n| 2019 | 128.72 | 18.55 | 19.14 | 29.16 | — | — |\n| 2020 | 165.35 | 29.60 | 23.85 | 39.74 | — | — |\n| 2021 | 229.02 | 50.97 | 40.64 | 45.89 | 69.36 | -23.47 |\n| 2023 | 403.41 | 96.07 | 97.48 | 133.87 | — | — |\n| 2024 | 392.41 | 94.50 | 99.88 | 124.07 | 40.03 | 84.03 |\n| 2025 | 454.56 | 191.51 | 132.41 | 172.03 | 55.38 | 116.65 |\n| 2026H1 | 288.97 | 110.80 | 105.72 | 96.99 | 29.62 | 67.38 |\n| 2026Q3单季 | 166.40 | 83.18 | 59.05 | 74.94 | 21.20 | 53.74 |\n| 2026年前三季度 | 455.37 | 193.98 | 164.77 | 171.93 | 50.82 | 121.11 |\n\n历史范围涵盖2019—2026，表内未填的购建及2022全年不以二手估计补齐；历史业务出售、疫情订单与新增能力使跨期结构不同，不据总收入复合增长率推导恒定份额。Q3收入、利润和CFO为季报直接披露；购建及自由现金由9M减H1拆分。Q3同比收入+38.01%、扣非+49.85%，累计扣非+73.03%；不能把累计增长当作单季增速。[Q3][H1][FY][FY2021]\n\n9M营业成本208.57亿元，毛利246.81亿元、毛利率54.20%；销售/管理/研发费用分别6.24/25.10/9.23亿元。营业利润240.70亿元含投资收益39.71亿元和公允收益1.64亿元；非流动处置损益31.08亿元主要来自药明合联股权出售。扣非164.77亿元比归母193.98亿元更接近经营，但仍需剔除金融收益、正常化汇率与资本开支。模型没有直接年化任一EPS。[Q3]\n\n8月出售药明合联5,352.4万股的公告成交额为39.20亿港元，公告预估税前利润31.43亿元；季报已承接本次交易和处置结果。这里使用期末资产余额，不再另加公告成交款，更不把一次性利润永久资本化。[Sale][Q3] 其他金融投资和仍持有的联营权益统一从经营现金中剥离，以净回收预算计价。\n\n9月末应收账款98.18亿元、存货125.93亿元、合同资产6.44亿元，年初分别72.63/89.93/4.70亿元；合同负债41.38亿元、应付账款33.41亿元部分提供周转支持。经营现金/归母为88.6%、经营现金/扣非为104.3%；利润改善确有现金，但扩张仍吸收应收与存货。固定资产189.28亿元、在建95.33亿元，后者比年初增加36.57亿元。2026公司购建指引80—85亿元，明显高于9M已付50.82亿元，预测不能假设下半年后投入停止。[Q3]\n\n9M加权ROE为22.42%；2025年报告ROE28.56%、扣非ROE19.74%。非经营处置、转股扩大资本与期内时点都会影响该比率，不能用报告ROE直接证明新建海外产能可赚同等回报；模型另设18%增量资本回报并施加13%及10%的资本压力。[Q3][FY]\n\n本次正常化2026收入取公司指引610—619亿元中点614.5亿元，只作为经营规模起点。首年收入700.53亿元，普通股税后经营利润222.38亿元。五年购建90/95/100/105/110亿元，折旧按收入6.2%（H1固定折旧17.59亿元、其他摊销约1.59亿元提供量级），先保留约40—60亿元年度维护更新，再承担成长投入。税费预算仅对正经营利润计提；若出现经营亏损，在没有可核当期抵扣或退款依据时不即时确认20%税收利益，亏损时也不即时确认债务利息税盾，正利润不足时税盾限于正经营利润预算；不把集团不同法人之间的亏损相互抵销。未来可利用亏损的法域、税基和期限未知，模型保留负经营利润记录但不给未知税利益计价；辅助盈利法遵守同一原则。研发在EBIT中持续费用化，不另资本化；股权薪酬的未来滚动预算按现金等价费用保留，不以非现金加回制造自由现金。\n\n五年营运资本按收入30%预算，起点184.35亿元；这是一项经营净周转预算而非某一资产负债表科目。五年后增长投入按增量税后经营利润/18%资本回报推算，再扣已计的营运资本增量，剩余作为实物成长投资。对应Y1至Y5普通经营利润增量84.01亿元，固定资本加净周转增量约281.17亿元，端点增量回报约29.9%；同一期间配对，但这是预测诊断，不能倒过来证明项目必然高回报。更长期18%回报低于过渡期，反映已建能力释放结束及海外冗余。\n\n## 资本、真实主体和股东现金：合并有钱不等于付款母公司有利润\n\n9月股本月报为A股2,473,280,246股、H股561,623,820股，合计3,034,904,066股；A股回购账户9,701,231股、H股库存20,148,900股，当前外部股份合计3,005,053,935股。67.8亿元美元结算零息可转债已于9月23日前全转，Q3债表也不再有该债；发行所得69.44亿元早在现金流中，不能再加一次资金或同时扣原债。[Shares][Conversion][Q3]\n\n模型采用30.34904066亿股完全稀释口径，从首年起视现有库存全部可能形成外部权益，不享受未实施注销的分母收益。A股员工计划来源于已回购股份，资金来自长期激励基金；9月29日股东会已通过员工计划及相关授权，但批准不等于全部过户完成；本报告不把这种内部薪酬安排当作新的外部融资现金。[EGM]既有回购成本已反映在期末现金中，未来未授权回购不预设。[Employee] 分红预算占普通经营利润35%，不是把FCFE或公开市场回购认作持续持有人的收款。未来融资诊断按每股人民币1元面值同时增加注册资本，法定公积50%目标随之上调；100亿元融资发行1亿股时，新增公积目标为0.5亿元而不是把全部融资溢价当注册资本。\n\n| 法人/法域 | 核实的控制与最终权益 | 现金路径含义 |\n|---|---|---|\n| 无锡药明康德新药开发股份有限公司，中国内地 | A/H共同发行母公司 | H1营业收入为零，依赖子公司宣派及资金管理；持有人分红由此支付 |\n| 药明康德（上海）医药研发有限公司，中国内地 | 直接100%，注册145.32亿元 | H1母公司应收其股利33.93亿元，是实际已确认来源，不是新增现金 |\n| 上海合全药业股份有限公司及常州合全、合全药业香港等 | 集团权益98.90%，并非全部100% | 重要少数权益1.10%；母子内部贸易收入不可相加估值 |\n| 常州合全生命科学有限公司，中国内地 | 集团间接100% | 注册资本13.10183亿元是工商资本，不代表现金实缴或可派储备 |\n| WuXi AppTec (HongKong) Limited，香港 | 直接100% | 与合全药业香港有限公司是不同主体；不能把两者现金混作母公司可用 |\n| STA Pharmaceutical USA, Co.、STA Pharmaceutical Singapore PTE. LTD. | 依H1集团表为相应间接权益 | 海外经营需各自税费、资金和法律测试，业务分部或在建工程不是法律分配池 |\n\nH1母公司未分配利润48.42亿元、盈余公积14.9188亿元、现金及交易金融136.03亿元、应收股利43.12亿元；母公司实际收到投资收益现金59.26亿元，其中收回旧应收不能重复形成新利润。应收股利六个实际债务人是药明康德（上海）医药研发、苏州、天津、上海药明、成都与武汉公司。[H1] 各法人注册资本的币种和单位必须分别阅读；本报告不把注册资本与资产净值等同，也不以合全分部的累计盈利代替每家海外法人的法定储备。\n\n本次母公司预算起点采用H1未分配利润扣已经支付中期分配15.0649亿元，余33.3549亿元，未擅自补入未披露Q3单体利润。母现金用H1现金等价物94.9471亿元加交易金融10.0116亿元、减中期现金15.0649亿元，约89.8938亿元；不是声称Q3披露了这项单体余额。集团9月现金与交易金融534.77亿元中，现金等价物差额76.08亿元按两年释放预算处理，而非全部判作永久受限；另扣现存少数权益6.09亿元的经济回收份额。上市母公司对应债务约22.994亿元、集团银行及租赁等合计85.25亿元，基准第一年清偿属于净现金充裕下的财务预算，不是声称这些全在一年到期。\n\n内地利润分配须先弥补旧亏损，再提法定公积；50%门槛以注册资本计，母公司转股后的法定公积缺口约0.2557亿元。模型逐年将新增宣派形成母公司投资收益、收款形成现金，旧应收回收只增加现金；实际分配同时受母利润、母现金和集团必要流动性约束。[CompanyLaw] 子公司未来宣派采用普通经营利润55%再乘85%可上划份额，现金滞后一年，并计2.5%税费/摩擦。85%是对未公开逐法人亏损、留存、跨境税基的经济预算，不是逐法人审计盈余；其合理性由H1真实宣派和收现、合全盈利、已核控制关系约束。H1仍有20.85亿元可抵扣亏损未确认递延所得税资产，其中15.02亿元在2031年及以后到期，证明并非每家经营实体都可按合并盈利派息；税务亏损并不等于法定会计旧亏损，也不能从该合计反推85%的精确合法比例。上划摩擦同时减少集团现金、集团权益及母公司利润预算。母公司日常费用每年4亿元已含在集团经营利润内，只在母现金预算分开定位一次。\n\n集团资金池不能法律抵销。H1母公司其他应付款110.50亿元，其他应收含合全物流5亿元资金池拆借；正常续作和集团内结算保留，不把合并抵销视为无需还款。额外母公司净还款30亿元压力只在母子之间移转现金，会压低首年分配而不凭空减少集团资产。上划延迟三年、仅40%利润可上划等情景实际重新计算母公司的现金、未分配利润和分配。仅降低宣派比例主要改变近端付款和留存位置，不能宣传成对全部未来经济权益的永久法律封锁；因此40%场景还将Y6以后现金兑现延长至三年、实现费用提高至5%，真正检验跨境及旧亏损对经济权益的影响。\n\n期末长期股权加其他非流动金融资产94.61亿元，基准第三年按账面86%毛回收、6%费用和税负预算，净80%；一年内到期非流动资产24.63亿元按第二年95%回收。H1后者包括大额存单与处置应收，Q3未逐笔细分，所以这不是每笔法定到期和税基的精确推断。处置的本金回收与利润分开，不靠投资收益加倍计价。\n\n## 估值：高质量现金流仍需要完整的再投资成本\n\n核心合理价值区间：@VALUE@ 元\n\n方法一（主方法）为未来五年实际普通股分配，加第五年末剩余经营现金价值和金融净资产。Y6—Y20逐年预测，之后稳态增长2.5%；长期EBIT32%，新增资本回报18%，该回报口径的资本只包括经营固定资本与非现金净周转，不含另行保留的经营现金。非现金净周转预算为收入30%，必要现金另为收入10%；它们是研究口径，不冒充季报逐项净额。Y6起固定投入由18%回报反推，扣除已计入非现金净周转后求得购建；随后从可提取现金再扣必要现金增加额。永续端同样扣终态收入×2.5%×10%的新增现金占用，避免只保留第五年流动性却免费使用未来增长的现金。总现金账并不再次扣掉这项内部留存，而是将其从可提取份额隔离。核心同一经营路径用9.5%—10.5%人民币普通股资本成本形成端点。拆分看，采用2.5%长期人民币低风险名义机会成本预算（不是当日债券报价）、约5.14%股票风险补偿参考，再加1.86%—2.86%公司风险调整；5.14%来自Damodaran于2026年1月公布的中国风险估计，只是风险量级参考，不是本公司可直接套用的实测资本成本。[ERP] 客户集中、跨境政策和资本冗余解释额外调整，净现金则限制融资风险；长期名义增长2.5%也不代表公司永远跑赢药企预算。\n\n五年后的余下经营现金按周年末折现，经营金融收益不资本化。这里有明确的方法边界：前五年的D逐年通过母公司利润、实收与现金限制；Y6以后则估计普通股对剩余经营的经济权益，不继续把85%上划预算当作逐法人永久法定证明。核心路径对未来扣完再投资与新增必要现金的FCFE，减去预算实际宣派对应的2.5%上划摩擦；终态按55%宣派、85%可上划份额对应费用延续。没有对每一元未立即分配的永续经营现金再统一施加一年延迟；已形成的经济权益主要依靠以后可分配利润及合理资本实现兑现，不依赖在市场上按估值出售证券。核心可实现性的积极依据是：六家已确认起点分红债务人主要位于境内，H1有59.26亿元实际收现、43.12亿元股利应收，母公司本身保有较大现金；经营路径持续产生税后利润，并非全部价值依赖尚未获准的海外本金退回。这仍不证明每家海外实体都具备足额法定储备，不能把合并现金全部视作当日可派。2.5%是混合税费及手续预算，不是境内分红法定统一税率。一次H1错期观察不足以证明所有未来经营现金必须统一延迟一年，因此“全部净可提现金2.5%、延迟一年”只保留为独立经济实现敏感；该敏感替代预算上划费用，不同时扣两者。另设零费用/零延迟和5%/三年边界。金融资产自身处置成本已在回收比例内，后续资本实现费用只覆盖另一环节，不重复同一次资产出售税。第五年净金融现金扣必要运营资金后，按98%经济回收、延迟两年折现；必要流动性仍服务经营，不强迫现金归零。该回收可以来自以后依法增加利润分配、投资变现或经批准的资本返还，不把本金当作当期可分配利润，也不声称已取得跨境资本退回批准。对于具体税基和上划时点的未知，50%非经营投资回收及五年资产释放延迟另作压力，不使用伪精确法律储备池。\n\n基准第五年每股终值@TV@元；终值现值占当前价值@TVSHARE@。这说明判断仍主要取决于五年后经营寿命、长期资本回报和现金归属，不能把近期扣非高增长视为足够的估值证明。第五年金融现金为@CASH5@亿元，已经逐笔扣除前五年实际分配、债务、投资和上划摩擦。\n\n方法二（辅助法）独立采用当前614.5亿元规模、35%—37%正常化EBIT率、20%税率和0.8%少数利润扣除，维护更新等于折旧。先将无增长利润按股权成本资本化；再只计十年、每年5%新增利润的有限增长价值，每期新增利润价值为“新增利润/资本成本−新增利润/18%—20%新增资本回报”，按发生时点折现；有限增长同时另扣新增10%收入现金占用，避免将18%不含现金资本回报误作全资本回报。该方法独立从正常化利润中扣55%×85%×2.5%的预算上划费用，并对十年增长形成的永久盈利增加同口径费用现值；不统一延迟整份经营权益，再加同一归属的金融资产净回收。这种盈利能力/有限特许法不复用主法未来收入或逐年资本开支，也不使用市场倍数，所得@AUX@元。其低于主法，主要因为只给5%增量、采用更快正常化的当前利润率；两法仍共享行业税费和归属假设，不能互相证明客户订单预测。\n\n## 经营情景与现金后果\n\n周期弱情景从第一年开始：临床订单延期和商业化去库存使前两年收入-8%/+2%、EBIT31%/33%，营运资金升至收入34%，随后依靠客户项目交付和现有认证恢复。结构不利从第一年开始：假设一部分美国客户永久迁出，收入连续下降15%/15%/5%，长期EBIT20%、新增回报10%，海外与境内产能同时承受冗余；没有把法律标签机械解释成全部收入消失。另设第三年才开始的政策压力，前两年经营和母公司付款参数保留基准，再切换迁移和上划节奏。\n\n较乐观路径需要现有商业化及TIDES进一步兑现，前五年增速20/18/15/12/10%，同时投入100—120亿元年度购建；后期仍降速，不把市场空间当作免费成长。资本强度压力保留销量但增加购建、周转和长期资本消耗，展示业绩仍增长而价值下降的可能。\n\n| 情景/诊断 | 当前经济价值，元/股 | 现金状态 |\n|---|---:|---|\n@SCENARIOS@\n\n前三种分别对应上述完整经营路径，其余多数为隔离诊断。“第十年退出”是假设第十年结束经营、固定资产45%、净周转80%回收并先支付50亿元退出费用及全部债税的经济边界，不是清算底。“退出索赔失败”另加2,000亿元高级索赔，是检验失败路径的反例：该路径的完整估值与终值均为空，未偿高级权利仍保留并停止预测。输出另列的失败前现金是未来假设路径中可能收到的分配，不是研究截止日已经历史收到的现金，也不是清算估值。非退出期间如经营或母公司现金不足、到期债未能清偿，同样停止并保留未付款及资金缺口，不把负现金继续滚成可行估值。融资诊断同时增加100亿元现金和1亿股份，没有只享受资金而忘记分母。\n\n## 基准持有人回报模型输入\n\n未来五年一股持续持有人实际现金预算为 **@D@ 元**；第五年末每股普通股终值 **@TV@ 元**。已支付2026中期分红不再次列入；没有把公开市场回购和留存现金列作持有人现金。本报告不冻结随行情变化的IRR。\n\n| 年 | 收入 | 普通税后经营利润 | 购建 | 增量周转 | FCFE | 实际分配 | 期末金融现金 | 母宣派确认 | 母收现毛额 | 母未分配利润 | 母现金 | 每股分配元 |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n@TABLE@\n\n普通税后经营利润不含金融收益；FCFE扣税后债务利息、全部购建、周转和条件性损失。净金融现金单列利息净收入、金融资产回收、还债和分配。年度输出另列必要现金增量和可提取FCFE；现金占用仍是集团资产，不在总现金守恒中重复作为费用或投资支出。母宣派只是内部利润归属，集团不新增一份利润；母收现毛额与税费摩擦另计。五年不是竞争优势的终点，独立第三年终值未予估计。\n\n统一经济实现敏感按“2.5%费用/一年延迟”“零费用/零延迟”“5%费用/三年延迟”排列，分别为@REALIZATION@。它们只检验实现方式，不改变业务收入或资本回报。完整20年、全情景的[可重算现金模型](../models/2026-Q3.py)与[年度输出](../models/2026-Q3-output.json)对应本公司本周期；输出包含现金、股本、应收股利、权益和退出未偿余额。\n\n## 前次假设复盘\n\n| 前次假设 | 本期实际 | 判断变化 | 估值影响 |\n|---|---|---|---|\n| H1基础年收入595亿元、首年636亿元 | 公司Q3收入与现金继续兑现，全年指引610—619亿元 | 近期经营规模上修，首年700.53亿元；长期仍降速 | 增加近端现金，但新增购建与周转同时上升 |\n| 8月底仍有可转债待转，股数为备考 | 9月23日全部转股，9月末A/H股本30.34904066亿股 | 使用已完成实际资本结构，不再假设现金赎回 | 既有融资只计一次，不再重复债务扣减 |\n| XDC出售与剩余投资采用8月交易外推 | Q3合并余额已含处置，非经营资产现有账面重新核对 | 不把已实现出售再加到期末现金；残余以回收范围处理 | 降低由外部成交外推全部资产的依赖 |\n| 未来每股分配3.00/3.35/3.70/4.05/4.40元 | 新增母公司宣派时间和逐年现金预算重新建立 | 改为约35%经营利润且受实际付款约束，取消固定分红先验 | 近期分配改变，留存仍在终值中一次计价 |\n| 五年后直接设终态回报 | Bachem爬坡与全球产能扩展继续；Q3业务规模上升 | 延长显式经营至20年，逐年衰减及再投资 | 区分收入上修和估值方法变化，不以区间重叠证明旧模型正确 |\n\n## 风险与改判条件\n\n能够容忍的是有明确恢复机制的项目延后、爬坡费用与回款错期：它们需要由订单完成、产品销量、应收库存回转和现金重新兑现来验证。无法容忍的是终端需求强、公司投入持续增加而高价值项目长期迁出；这将同时削弱增长、利润率与资本回报，应按结构路径处理，而非等利润均值回归。\n\n8月DEL平台网络安全事件已由公司公告确认；公司称系统正常且当时未发现公开或滥用证据，这是当时公司自述，不是长期无索赔保证。[DEL] 若客户知识产权、数据完整性或监管资格发生实质损失，生物学业务当前收入占比不能限定对集团引流信誉的影响。两年各10亿元损失及利润率下降仅为压力量级，不是已确认负债。\n\n2025年报披露公司无控股股东，实际控制人为通过一致行动协议共同控制的Ge Li（李革）、张朝晖和刘晓钟，年末合计控制16.6972%表决权；不应把董事长个人与全部最终控制权混同。[FY] H1对子公司担保余额10.19亿元、占净资产1.22%，是已披露的集团融资支持，不能描述成对实际控制人个人担保。[H1] 治理观察重点是资金用途而非单看分红增长。H1母公司为控股平台，集团投资收益、回购、员工激励、海外建设和子公司往来同时存在；现有现金若被长期低回报扩产或关联资金占用吞噬，普通股价值会下降。H1未披露控股股东占用或为其关联方担保不等于未来风险为零。海外逐法人税基、亏损和实收资本、订单取消权、具名客户采购份额仍是主要认识边界；它们以明确预算和压力反映，不能用复杂但未经核实的法人表掩盖。\n\n## 来源\n\n[Q3] [2026年第三季度报告](https://static.cninfo.com.cn/finalpage/2026-10-27/1225624435.PDF)，董事会2026-10-26，目录名义10-27；实际10-26已可公开取得，15页、未经审计，发行人及三表均核对。文件名日期不改变实际已披露事实，首次检索时间不当作精确发布时间。\n\n[H1] [2026年半年度报告](https://static.cninfo.com.cn/finalpage/2026-08-04/1225455027.PDF)，199页；[FY] [2025年年度报告](https://static.cninfo.com.cn/finalpage/2026-03-24/1225025225.PDF)；[FY2021] [2021年年度报告](https://static.cninfo.com.cn/finalpage/2022-03-24/1212651601.PDF)。\n\n[Shares] [截至2026年9月30日证券变动月报](https://officialsite-static.wuxiapptec.com/upload/Monthly_Return_of_Equity_Issuer_on_Movements_in_Securities_for_the_Month_Ended_30_September_2026_b83e355d45.pdf)，10-07；[Conversion] [2027年到期可转债已全部转股公告](https://officialsite-static.wuxiapptec.com/upload/FULL_CONVERSION_AND_WITHDRAWAL_OF_LISTING_OF_THE_RMB_6_780_000_000_U_S_DOLLAR_SETTLED_ZERO_COUPON_CONVERTIBLE_BONDS_DUE_2027_d3fe6b8888.pdf)，09-23。\n\n[Sale] [出售部分股票资产公告](https://static.cninfo.com.cn/finalpage/2026-08-28/1225520321.PDF)，08-28；[Employee] [A股员工持股计划草案](https://static.cninfo.com.cn/finalpage/2026-08-04/1225455035.PDF)，08-04，草案不作已过户证明；[DEL] [DEL网络安全事件自愿公告](https://static.cninfo.com.cn/finalpage/2026-08-25/1225500481.PDF)，08-25。\n\n[1260H] [国防部2026年名单及理由](https://public-inspection.federalregister.gov/2026-11571.pdf)，06-10；[Court] [地区法院2026-08-07裁判理由全文](https://www.govinfo.gov/content/pkg/USCOURTS-dcd-1_26-cv-02069/pdf/USCOURTS-dcd-1_26-cv-02069-0.pdf)，35页，案号26-2069；[Injunction] [公司获初步禁令公告](https://officialsite-static.wuxiapptec.com/upload/ANNOUNCEMENT_FOR_PRELIMINARY_INJUNCTION_2e0a0bc090.pdf)，08-09。\n\n[Law] [Public Law 119-60，第851节](https://www.govinfo.gov/content/pkg/PLAW-119publ60/pdf/PLAW-119publ60.pdf)，2025-12-18；[Treasury] [美国财政部OISP实施页面](https://home.treasury.gov/policy-issues/international/outbound-investment-program)；[COINS] [10月26日刊载的拟议规则](https://www.federalregister.gov/documents/2026/10/26/2026-21786/outbound-investment-security-program-regulations)。\n\n[IMF] [2026年10月世界经济展望](https://www.imf.org/en/Publications/WEO/Issues/2026/10/13/world-economic-outlook-october-2026)；[FDA] [2025新药批准](https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2025)；[Lilly] [礼来2026Q2财报](https://investor.lilly.com/news-releases/news-release-details/lilly-reports-second-quarter-2026-financial-results-raises-full)，08-05；[Bachem] [2026H1正式业绩公告](https://www.bachem.com/articles/news/ad-hoc/bachem-confirms-growth-and-expects-a-strong-second-half-2026/)，07-30。\n\n[CompanyLaw] [中华人民共和国公司法](https://www.samr.gov.cn/xyjgs/flfg/art/2024/art_d4e84936a8a744f8928ac7aec7594345.html)，2023年修订、2024年施行，利润分配及减资条款。各来源性质与日期不同，公司指引和研究预算均不视为已实现事实。\n\n[ERP] [Damodaran国家风险补偿表](https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ctryprem.html)，2026-01-05，学术估计，用途限资本成本量级参考。\n\n[EGM] [2026年第一次临时股东会决议](https://static.cninfo.com.cn/finalpage/2026-09-30/1225587771.PDF)，9月29日审议、9月30日公告；[Board] [董事会接受转股申请决议](https://static.cninfo.com.cn/finalpage/2026-09-22/1225573839.PDF)。\n'
SOURCES=['https://static.cninfo.com.cn/finalpage/2026-09-30/1225587771.PDF','https://static.cninfo.com.cn/finalpage/2026-09-22/1225573839.PDF','https://static.cninfo.com.cn/finalpage/2026-10-27/1225624435.PDF', 'https://static.cninfo.com.cn/finalpage/2026-08-04/1225455027.PDF', 'https://static.cninfo.com.cn/finalpage/2026-03-24/1225025225.PDF', 'https://static.cninfo.com.cn/finalpage/2022-03-24/1212651601.PDF', 'https://officialsite-static.wuxiapptec.com/upload/Monthly_Return_of_Equity_Issuer_on_Movements_in_Securities_for_the_Month_Ended_30_September_2026_b83e355d45.pdf', 'https://officialsite-static.wuxiapptec.com/upload/FULL_CONVERSION_AND_WITHDRAWAL_OF_LISTING_OF_THE_RMB_6_780_000_000_U_S_DOLLAR_SETTLED_ZERO_COUPON_CONVERTIBLE_BONDS_DUE_2027_d3fe6b8888.pdf', 'https://static.cninfo.com.cn/finalpage/2026-08-28/1225520321.PDF', 'https://static.cninfo.com.cn/finalpage/2026-08-04/1225455035.PDF', 'https://static.cninfo.com.cn/finalpage/2026-08-25/1225500481.PDF', 'https://public-inspection.federalregister.gov/2026-11571.pdf', 'https://www.govinfo.gov/content/pkg/USCOURTS-dcd-1_26-cv-02069/pdf/USCOURTS-dcd-1_26-cv-02069-0.pdf', 'https://officialsite-static.wuxiapptec.com/upload/ANNOUNCEMENT_FOR_PRELIMINARY_INJUNCTION_2e0a0bc090.pdf', 'https://www.govinfo.gov/content/pkg/PLAW-119publ60/pdf/PLAW-119publ60.pdf', 'https://home.treasury.gov/policy-issues/international/outbound-investment-program', 'https://www.federalregister.gov/documents/2026/10/26/2026-21786/outbound-investment-security-program-regulations', 'https://www.imf.org/en/Publications/WEO/Issues/2026/10/13/world-economic-outlook-october-2026', 'https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2025', 'https://investor.lilly.com/news-releases/news-release-details/lilly-reports-second-quarter-2026-financial-results-raises-full', 'https://www.bachem.com/articles/news/ad-hoc/bachem-confirms-growth-and-expects-a-strong-second-half-2026/', 'https://www.samr.gov.cn/xyjgs/flfg/art/2024/art_d4e84936a8a744f8928ac7aec7594345.html', 'https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ctryprem.html']

def report(s):
    b=s['base'];lo,hi=[round(x,1) for x in b['current_value']];tv=[round(x,2) for x in b['terminal_year5']]
    table='\n'.join('|'+str(r['year'])+'|'+ '|'.join(f'{r[k]*10:.2f}' for k in ['revenue','nopat_common','capex','delta_nwc','fcfe','dividend','cash','parent_declaration','parent_gross_receipt','parent_profit','parent_cash'])+f"|{r['dps']:.4f}|" for r in b['annual'][:5])
    names=dict(cyclical='周期性弱',structural='结构性不利',upside='较乐观',upstream_delay_3='上划延迟三年',old_losses_budget='旧亏损预算加大',parent_settlement='母资金池额外还款',capital_intensity='资本强度上升',margin_minus_3pt='经营利润率低3个百分点',cyber='DEL损失压力',financial_recovery_50='金融回收50%并延迟',equity_financing='外部融资稀释',finite_exit_10='第十年退出',failed_exit_3='退出索赔失败',late_policy_year3='第三年才发生迁移',cost_of_capital_plus_1pt='资本成本高1个百分点',financing_then_exit='融资后退出组合')
    st='\n'.join(f"|{names.get(n,n)}|{('—，无法完成估值' if not z['feasible'] else format(z['current_value'][0],'.2f')+'—'+format(z['current_value'][1],'.2f'))}|{'可行' if z['feasible'] else '失败，未偿权利保留'}|" for n,z in s.items() if n!='base')
    diag=[]
    for delay,cost in [(1,.025),(0,0),(3,.05)]:
        pp=copy.deepcopy(BASE);pp.update(tail_strategy='uniform_realization',realization_delay=delay,realization_cost=cost);diag.append(run(pp)['current_value'])
    realization='；'.join('—'.join(format(x,'.2f') for x in pair)+'元' for pair in diag)
    return REPORT_TEMPLATE.replace('@REALIZATION@',realization).replace('@VALUE@',f'{lo}—{hi}').replace('@TV@',f'{tv[0]}—{tv[1]}').replace('@D@',' / '.join(f'{x:.4f}' for x in b['distributions'])).replace('@TABLE@',table).replace('@SCENARIOS@',st).replace('@AUX@','—'.join(f'{x:.2f}' for x in b['auxiliary_value'])).replace('@TVSHARE@','—'.join(f'{x*100:.1f}%' for x in b['terminal_pv_share'])).replace('@CASH5@',f"{b['annual'][4]['cash']*10:.2f}")

def build():
    validation=tests();s=scenarios();b=s['base'];md=report(s)
    realization_diagnostics={}
    for label,delay,cost in [('uniform_one_year_2p5percent',1,.025),('frictionless_upper_diagnostic',0,0),('three_year_five_percent',3,.05)]:
        p=copy.deepcopy(BASE);p.update(tail_strategy='uniform_realization',realization_delay=delay,realization_cost=cost,scenario=label,effective_years=list(range(6,21)),affected='仅经济实现费用及延迟，非法律分红能力变化');realization_diagnostics[label]=run(p)
    result=dict(symbol='CN:603259',name='药明康德',outcome='covered',report_period='2026-Q3',information_cutoff=ASOF,
      summary='小分子商业化与TIDES交付已形成真实现金优势；长期价值取决于迁移壁垒能否抵御客户双供、地域限制与海外资本冗余。',
      key_logic=['商业化小分子和TIDES规模兑现支持未来增长，但长期利润率与新增资本回报衰减。','母公司无营业收入；法定利润、宣派应收和实际上划分别约束股东现金。','可转债已全转，现有金融本金与经营现金分离且不重复资本化处置收益。'],
      risks=['美国客户集中及条件性采购/投资约束推动永久迁移','新增产能资本回报下降和客户药品商业化失败','子公司旧亏损、跨境税及上划延迟','DEL数据事件与科研人才流失'],
      value_range=dict(low=round(b['current_value'][0],1),high=round(b['current_value'][1],1),currency='CNY'),
      valuation_note='主法为五年实际分配加第五年独立经营现金终值与净资产回收；20年经营显式衰减、资本成本9.5%—10.5%、稳态增长2.5%、非现金经营资本增量ROIC18%，另扣新增必要现金；剩余经营现金扣预算上划费用，额外净资产98%两年实现，统一费用及延迟另作压力；辅助为独立正常化盈利及十年有限增长特许价值。无报价与市场错价判断。',
      return_model=dict(schema_version=1,method='annual_common_equity_irr_v1',currency='CNY',model_as_of=ASOF,
          base_case_distributions_per_share=[round(x,4) for x in b['distributions']],base_case_terminal_equity_value_range_per_share=dict(year_5=dict(low=round(b['terminal_year5'][0],2),high=round(b['terminal_year5'][1],2)))),
      return_model_note='五年周年预算非承诺；普通股现金排除公开市场回购。完全稀释30.34904066亿股含现有库存可能转予员工，现有债全转不重复扣债。第五年余下经营FCFE加未分配净金融资产按两年98%回收预算计价；母公司法定利润与实收现金分别约束，海外逐法人法定储备未知，前五年采用可兑现上划比例及延迟压力；Y6后为经济权益实现预算，并非永久逐法人分红账，扣新增必要现金及预算上划摩擦；全部经营现金统一2.5%及一年延迟为单独敏感。',source_urls=SOURCES,report_markdown=md)
    return dict(schema='cn603259-q3-economic-model-v1',units='CNY billion except per-share CNY, shares billion',as_of=ASOF,summary={'value_range':result['value_range'],'return_model':result['return_model']},scenarios=s,economic_realization_diagnostics=realization_diagnostics,validation=validation,result=result,
      limitations=['经济上划预算不是海外逐法人法定可分配利润证明','独立Document24命令与完整后续案卷未取得；Document25及公司公告已核','无具名客户合同、成功率、单项目毛利或订单取消权数据'])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default=str(pathlib.Path(__file__).resolve().parent));ap.add_argument('--expand',action='store_true');a=ap.parse_args();o=pathlib.Path(a.out);o.mkdir(parents=True,exist_ok=True);z=build()
    (o/'2026-Q3-output.json').write_text(json.dumps(z,ensure_ascii=False,indent=2)+'\n')
    (o/'2026-Q3.md').write_text(z['result']['report_markdown'])
    (o/'result.json').write_text(json.dumps(z['result'],ensure_ascii=False,indent=2)+'\n')
    (o/'candidate.json').write_text(json.dumps(dict(task_id='f50bbb47f29e5c26219e232e',at=ASOF,result=z['result']),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(z['summary'],ensure_ascii=False))
if __name__=='__main__':main()

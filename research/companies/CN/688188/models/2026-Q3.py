#!/usr/bin/env python3
"""CN:688188 2026-Q3. RMB million, million shares; standard-library only.
Annual periods end on successive anniversaries of 2026-10-26. Four real operating-company reserve accounts; indirect ownership routes are
economic cash-transmission channels, not fictitious Company Law reserve pools. No market price.
"""
import json, math, pathlib, argparse, copy, gzip, base64, hashlib
ROOT=pathlib.Path(__file__).resolve().parent
SCENARIOS={
 'base':dict(g=[.15,.14,.12,.10,.08,.065,.05,.04,.03,.02],m0=.46,mt=.40,r=.09,roi=.60,rt=.25,release=.15,up_start=3),
 'core_low':dict(g=[.13,.12,.10,.09,.07,.055,.045,.035,.025,.02],m0=.45,mt=.39,r=.095,roi=.55,rt=.25,release=.10,up_start=3),
 'core_high':dict(g=[.17,.15,.13,.11,.09,.07,.055,.04,.03,.02],m0=.47,mt=.41,r=.085,roi=.65,rt=.28,release=.20,up_start=3),
 'cyclical':dict(cycle=True,g=[-.10,.02,.20,.15,.10,.07,.05,.04,.03,.02],m0=.38,mt=.40,r=.09,roi=.60,rt=.25,release=.15,up_start=4),
 'structural':dict(g=[-.12,-.08,0,.02,.02,.02,.02,.02,.02,.02],m0=.32,mt=.25,r=.105,roi=.25,rt=.15,release=.10,up_start=5),
 'optimistic':dict(g=[.22,.20,.18,.15,.12,.09,.07,.05,.03,.02],m0=.48,mt=.43,r=.085,roi=.70,rt=.30,release=.20,up_start=3)
}

def settle(cash, retained, reserve, capital, profit, noncash, investment, floor, desired, debt, limit, extra=0):
    """Production cash/legal waterfall; losses restored BEFORE reserve accrual.
    desired includes ordinary + release; only a single legal allowance exists.
    extra is capital subscription, never legal income. Prior payables/receipts
    are settled before this call and never become profit here.
    """
    after=retained+profit
    appropriation=min(max(after,0)*.10,max(profit,0)*.10,max(capital*.50-reserve,0))
    legal=after-appropriation
    liquid=cash+profit+noncash-investment+extra
    draw=min(max(floor-liquid,0),max(limit-debt,0)); liquid+=draw; debt+=draw
    failure=max(floor-liquid,0)
    repay=min(debt,max(liquid-floor,0)); liquid-=repay; debt-=repay
    d=min(max(desired,0),max(legal,0),max(liquid-floor,0)) if failure<1e-8 else 0.
    return dict(cash=liquid-d,retained=legal-d,reserve=reserve+appropriation,dividend=d,legal_before=legal,appropriation=appropriation,draw=draw,repay=repay,debt=debt,funding_failure=failure)

def proportional_capital_return(cash,capital,shares,holding_units,capital_surplus,amount,cancel_fraction,friction,floor):
    """Conditional pro-rata approved capital reduction; not a dividend or accounting profit.
    Price=amount/(shares*cancel_fraction), can exceed face; transaction costs debit equity.
    Creditors/solvency approval is a scenario precondition, not inferred from cash alone.
    """
    assert 0<cancel_fraction<1 and amount>=0 and friction>=0
    face=capital*cancel_fraction;cost=amount*friction
    assert amount>=face and capital_surplus>=amount-face+cost
    assert cash-floor>=amount+cost
    receipt_per_original_share=holding_units*amount/shares
    return dict(cash=cash-amount-cost,capital=capital-face,shares=shares*(1-cancel_fraction),holding_units=holding_units*(1-cancel_fraction),capital_surplus=capital_surplus-(amount-face)-cost,receipt_per_original_share=receipt_per_original_share,capital_face_cancelled=face,capital_return=amount,friction=cost,cancellation_price=amount/(shares*cancel_fraction),legal_profit_created=0.)

def run(s,n=600,records=True):
    p=copy.deepcopy(s); p.setdefault('release_restricted_year',8); names=['parent','bochu_nc','boci','precision']; ownership=[1,1,.9275,.946964]
    # H1 parent actual cash+trading assets 4323.784810; Q3 aggregate 5730.572263.
    # Q3 legal-entity allocation is a budget, NOT a disclosed Q3 standalone sheet.
    cash=[4500.,806.0990022124001,380.,25.0034]; re=[1881.95245753,200.,300.,-1.9109]
    res=[144.3649635,0.,0.,0.]; cap=[405.984426,60.,32.,55.]
    debt=[28.99906365,0.,0.,0.]; payable=[236.03437363,0.,0.,0.]; receivable=[0.,0.,0.,0.]
    if p.get('no_opening_sub_earnings'): re[1:3]=[0.,0.]
    if p.get('parent_cash_shift'): cash[0]-=p['parent_cash_shift'];cash[1]+=p['parent_cash_shift']
    invcap=[400.,270.,200.,30.]; shares=405.984426; rev=2500.; lastprofit=1150.
    intercompany=[0.,0.]
    channel_queue={}; prior_forward=[0.,0.]; transit_cash=[0.,0.]
    registration_queue={}
    registration_delay=int(p.get('registration_delay',0))
    if registration_delay:
        cap[0]=405.557343
        registration_queue[1+registration_delay]=405.984426-405.557343
    restricted=[999.4403,24.984,0.,11.2534]
    precision_op=-4.; holding_units=1.; capital_surplus=2872.37790885
    pv=tv=0.; rows=[]; maxfail=0.; cum_minor=0.; d5=[]
    for y in range(1,n+1):
        cap[0]+=registration_queue.pop(y,0.)
        growth=p['g'][min(y-1,9)] if y<=10 else p.get('tail_g',.02)
        if p.get('prefix_base') and y<=5: growth=SCENARIOS['base']['g'][y-1]
        previous_rev=rev; rev*=1+growth
        margin=p['m0']+(p['mt']-p['m0'])*min((y-1)/9,1)
        if p.get('prefix_base'):
            margin=(.46+(.40-.46)*min((y-1)/9,1)) if y<=5 else (.46+(.40-.46)*4/9)+(p['mt']-(.46+(.40-.46)*4/9))*min((y-5)/5,1)
        if p.get('cycle') or s==SCENARIOS['cyclical']:
            if y<=3: margin=[.38,.41,.44][y-1]
        op=rev*margin
        iroic=p['roi']+(p['rt']-p['roi'])*min((y-1)/9,1)
        if p.get('prefix_base') and y<=5: iroic=.60+(.25-.60)*min((y-1)/9,1)
        project=(698.8312/3+.15*max(rev-previous_rev,0)) if y<=3 else .15*max(rev-previous_rev,0)
        # NET investment; maintenance capex and depreciation each 2% sales cancel.
        investment=max(max(op-lastprofit,0)/iroic,project)+p.get('extra_capital',0)*(1 if y<=3 else 0)
        if growth<0: investment+=.06*(rev-previous_rev) # inventory/receivable release, not all capital
        sbc=[50.,35.,20.,5.][y-1] if y<=4 else 0.
        newshares=([1+3.5314*.30,3.5314*.30+.8039/3,3.5314*.40+.8039/3,.8039/3][y-1] if y<=4 else 0.)
        if p.get('no_issue'): newshares=0
        proceeds=(35.+3.5314*.30*50.7 if y==1 else newshares*50.7) if y<=4 and not p.get('no_issue') else 0.
        shares+=newshares; capital_surplus+=proceeds-newshares
        if registration_delay:registration_queue[y+registration_delay]=registration_queue.get(y+registration_delay,0.)+newshares
        else:cap[0]+=newshares
        start_cash=cash.copy(); start_res=res.copy(); start_re=re.copy(); start_debt=debt.copy(); start_pay=payable.copy()
        # Direct Precision 75%; indirect 19.6964% and Boci 92.75% are
        # separately governed pass-through routes. No partnership 50% pool.
        channel_in=[payable[3]*.196964,payable[2]*.9275]
        channel_out=prior_forward.copy()
        transit_cash=[transit_cash[i]+channel_in[i]-channel_out[i] for i in range(2)]
        assert min(transit_cash)>-1e-7
        old_received=[payable[1]+payable[3]*.75+channel_out[0],channel_out[1],0.,0.]
        channel_forward=channel_queue.pop(y,[0.,0.])
        minor_paid=payable[2]*(1-.9275)+payable[3]*(1-.946964)
        old_common=payable[0]
        for i in range(4): cash[i]+=old_received[i]-payable[i]
        receivable=[0.,0.,0.,0.]; payable=[0.,0.,0.,0.]
        # May/June 2026 approval adds Precision to the original mother/NC project
        # perimeter. Boci funds growth itself. Existing paid capital is NOT new cash.
        # Principal AND return on restricted funds retain the use restriction.
        restricted_open=restricted.copy()
        eligible_spend=([754.9289/3,104.984/3,0.,17./3] if y<=3 else [0.,0.,0.,0.])
        qualified_spend=eligible_spend.copy()
        restricted_transfer=[0.,0.,0.,0.]
        if y<=3:
            a1=max(qualified_spend[1]-restricted[1],0)
            intercompany[0]+=a1
            assert intercompany[0]<=80+1e-8, "approved project loan limit"
            internal_flow=[-a1,a1,0.,0.]
            restricted_transfer=[-a1,a1,0.,0.]
        else:
            r1=min(intercompany[0],intercompany[0]/max(9-y,1),max(cash[1]-restricted[1]*(1+p.get('yield',.02))-rev*.04-investment*.34,0))
            intercompany[0]-=r1
            internal_flow=[r1,-r1,0.,0.]
            restricted_transfer=[r1,0.,0.,0.] # returned project loan remains restricted at mother
        for i in range(4):cash[i]+=internal_flow[i]
        # Opening payments/transfers happen first; construction and operating
        # cash occur at year end. Restricted interest uses the SAME cash date.
        restricted_interest_base=[restricted_open[i]+restricted_transfer[i] for i in range(4)]
        restricted_income=[v*p.get('yield',.02) for v in restricted_interest_base]
        qualified_spend[3]=min(eligible_spend[3],restricted_interest_base[3]+restricted_income[3])
        for i in range(4):
            restricted[i]=restricted_interest_base[i]+restricted_income[i]-qualified_spend[i]
            assert restricted[i]>=-1e-8
        conditional_authorised_release=[0.,0.,0.,0.]
        if p.get('release_restricted_year')==y:
            conditional_authorised_release=restricted.copy();restricted=[0.,0.,0.,0.]
        # Operating settlement stress: delayed receivable is an intra-group
        # asset/liability, reversed next year, no second group cost.
        transfer=p.get('settlement_delay',0)*(1 if y==1 else -1 if y==2 else 0)
        cash[0]-=transfer; cash[1]+=transfer
        interest_base=cash.copy()
        fin=[max(interest_base[i],0)*p.get('yield',.02)-start_debt[i]*.04 for i in range(4)]
        precision_op=([-4.,0.,2.,4.,6.][y-1] if y<=5 else precision_op*(1+growth))
        operational=[op*(.779-p.get('unmapped_profit_haircut',0.)),op*.12-precision_op,op*.10,precision_op]
        ownprofit=[operational[i]+fin[i]-sbc*([.8,.1,.1,0.][i]) for i in range(4)]
        investments=([608.8312/3+(investment-698.8312/3)*.35,80/3+(investment-698.8312/3)*.34,(investment-698.8312/3)*.30,10./3+(investment-698.8312/3)*.01] if y<=3 else [investment*.35,investment*.34,investment*.30,investment*.01])
        floors=[rev*.06+restricted[0],rev*.04+restricted[1],rev*.025+restricted[2],rev*.001+restricted[3]]
        declarations=[0.,0.,0.,0.]; legalprofit=ownprofit.copy(); node=[None]*4
        for i in [3,2,1,0]:
            if i==0:legalprofit[i]+=declarations[1]+declarations[3]*.75+channel_forward[0]
            if i==1:legalprofit[i]+=channel_forward[1]
            # Investment income at declaration, NOT at receipt. Sub payables are
            # funded and earmarked at declaration; payment settles next year.
            investment_income=legalprofit[i]-ownprofit[i]
            noncash=sbc*([.8,.1,.1,0.][i])-investment_income
            liquid_before=cash[i]+legalprofit[i]+noncash-investments[i]+(proceeds if i==0 else 0)
            ordinary=(max(sum(ownprofit[j]*(ownership[j]) for j in range(4)),0)*.55 if i==0 else max(ownprofit[i],0)*.65)
            if i>0 and y<p.get('up_start',3): ordinary=0.
            if y>5:
                ordinary=max(ownprofit[i]+investment_income-investments[i],0)
            release=(p.get('release',.15)*max(liquid_before-floors[i]-ordinary,0)) if y>5 else 0.
            if p.get('no_upstream') and i>0: ordinary=release=0.
            desired=ordinary+release
            if p.get('zero_distributions'):desired=0.
            z=settle(cash[i],re[i],res[i],cap[i],legalprofit[i],noncash,investments[i],floors[i],desired,debt[i],[200.,100.,50.,10.][i],proceeds if i==0 else 0)
            d=z['dividend']; declarations[i]=d
            if i in (2,3):
                route=0 if i==3 else 1
                amount=d*(.196964 if i==3 else .9275)
                lag=int(p.get('indirect_route_delay',1))
                if lag==0:channel_forward[route]+=amount
                else:channel_queue.setdefault(y+lag,[0.,0.])[route]+=amount
            if i>0:
                # settle() subtracts d as though paid; restore earmarked cash
                # and create next-period payable. RE stays reduced now.
                z['cash']+=d; payable[i]=d; receivable[1 if i==2 else 0]+=d*ownership[i]
            cash[i],re[i],res[i],debt[i]=z['cash'],z['retained'],z['reserve'],z['debt']
            invcap[i]+=investments[i]
            expected=start_cash[i]+old_received[i]-start_pay[i]+internal_flow[i]+(-transfer if i==0 else transfer if i==1 else 0)+ownprofit[i]+sbc*([.8,.1,.1,0.][i])-investments[i]+(proceeds if i==0 else 0)+z['draw']-z['repay']-(d if i==0 else 0)
            assert abs(cash[i]-expected)<max(1e-6,abs(cash[i])*1e-12)
            assert re[i]>=-1e-8 or d==0
            assert res[i]<=max(start_res[i],cap[i]*.5)+1e-8 # capital reduction need not destroy existing reserve
            assert d<=max(z['legal_before'],0)+1e-8
            maxfail=max(maxfail,z['funding_failure'])
            node[i]=dict(name=names[i],restricted_open=restricted_open[i],financial_interest_base=interest_base[i],restricted_interest_base=restricted_interest_base[i],restricted_financial_income=restricted_income[i],restricted_transfer=restricted_transfer[i],eligible_project_spending=eligible_spend[i],qualified_project_spending=qualified_spend[i],project_spending_from_own_funds=eligible_spend[i]-qualified_spend[i],restricted_close=restricted[i],conditional_authorised_release=conditional_authorised_release[i],internal_project_cash_flow=internal_flow[i],intercompany_loan_receivable=(intercompany[0] if i==0 else intercompany[1] if i==1 else 0),intercompany_loan_payable=(intercompany[0] if i==1 else intercompany[1] if i==2 else 0),cash_open=start_cash[i],cash_close=cash[i],retained_open=start_re[i],retained_close=re[i],reserve=res[i],registered_capital_budget=cap[i],own_profit=ownprofit[i],declared_investment_income=investment_income,prior_dividend_received=old_received[i],prior_payable_paid=start_pay[i],new_declaration=d,ordinary_requested=ordinary,release_requested=release,legal_profit_before_distribution=z['legal_before'],reserve_appropriation=z['appropriation'],investment=investments[i],noncash_compensation=sbc*([.8,.1,.1,0.][i]),financial_income=fin[i],liquidity_floor=floors[i],debt_close=debt[i],debt_draw=z['draw'],debt_repaid=z['repay'],funding_failure=z['funding_failure'],dividend_payable=payable[i],dividend_receivable=receivable[i],invested_capital=invcap[i],capital_inflow=proceeds if i==0 else 0)
        receivable=[declarations[1]+declarations[3]*.75+channel_forward[0],channel_forward[1],0.,0.]
        for i in range(4):node[i]['dividend_receivable']=receivable[i]
        prior_forward=channel_forward.copy()
        dist=holding_units*declarations[0]/shares+(old_common/405.557343 if y==1 else 0)
        capital_event=None
        if y==p.get('capital_return_year',0):
            capital_event=proportional_capital_return(cash[0],cap[0],shares,holding_units,capital_surplus,p['capital_return_amount'],p['capital_cancel_fraction'],p.get('capital_return_friction',.01),floors[0])
            cash[0]=capital_event['cash'];cap[0]=capital_event['capital'];shares=capital_event['shares'];holding_units=capital_event['holding_units'];capital_surplus=capital_event['capital_surplus'];dist+=capital_event['receipt_per_original_share']
            node[0]['cash_close']=cash[0];node[0]['registered_capital_budget']=cap[0]
        # Capital return changes cash/equity/shares, never reserve or legal profit.

        pv+=dist/(1+p['r'])**y
        if y>5: tv+=dist/(1+p['r'])**(y-5)
        if y<=5:d5.append(dist)
        cum_minor+=minor_paid
        if records:rows.append(dict(capital_return_event=capital_event,original_share_holding_units=holding_units,mother_capital_surplus_budget=capital_surplus,unregistered_paid_share_face=sum(registration_queue.values()),indirect_channel_cash=transit_cash.copy(),indirect_channel_received=channel_in,indirect_channel_paid=channel_out,indirect_forward_declared=channel_forward.copy(),year=y,revenue=rev,operating_cash_net_margin=margin,operating_cash_profit=op,net_investment=investment,incremental_roic=iroic,maintenance_capex=rev*.02,depreciation=rev*.02,shares=shares,new_shares=newshares,capital_inflow=proceeds,minority_cash_paid=minor_paid,ordinary_shareholder_cash=declarations[0],old_dividend_paid=old_common,distribution_per_share=dist,nodes=node))
        lastprofit=op
        if maxfail>1e-7:break
    return dict(pv=pv if maxfail<1e-7 else None,terminal_year5=tv if maxfail<1e-7 else None,distributions=d5,terminal_pv_share=((tv/(1+p['r'])**5)/pv if maxfail<1e-7 else None),stopped_at_year=y,maximum_funding_failure=maxfail,feasible=maxfail<1e-7,rows=rows)

def auxiliary():
    # Independent normalised segment earning-power SOTP. No production cash
    # forecast, growth array, margins or capital accumulation is imported.
    result=[]
    for revenues,margins,multiples in [([1450.,600.,70.,450.],[.45,.48,.40,.16],[17.,17.,15.,10.]),([1600.,700.,90.,550.],[.50,.52,.45,.20],[20.,20.,18.,12.])]:
        profits=[r*m for r,m in zip(revenues,margins)]
        operation=sum(p*k for p,k in zip(profits,multiples))*(1-.00725)
        finance=5730.5722629-236.03437363-1035.6777-400.-28.99906365-48.34594101
        finance_pv=sum((finance/10)/(1.09**y) for y in range(1,11))
        shares=411.319726
        result.append(dict(normalised_segment_sales=revenues,segment_cash_net_margins=margins,segment_profits=profits,earnings_multiples=multiples,operating_equity_value=operation,net_financial_bridge=finance,financial_release_pv=finance_pv,shares=shares,pv=(operation+finance_pv)/shares))
    return result

def tests():
    cr=proportional_capital_return(20.,10.,10.,1.,20.,8.,.2,.05,2.)
    assert cr['cash']==11.6 and cr['capital']==8. and cr['shares']==8. and cr['holding_units']==.8 and cr['receipt_per_original_share']==.8 and cr['legal_profit_created']==0.
    assert cr['cancellation_price']==4. # face1 is not the mandatory return price
    registered_not_paid=settle(100,0,5,20,10,0,0,0,100,0,0)
    assert registered_not_paid['appropriation']==1 # paid10 cannot cap statutory reserve
    a=settle(100,20,5,10,10,0,0,10,50,0,0)
    assert a['dividend']==30 and a['cash']==80 and a['retained']==0 # reserve cap already met
    b=settle(10,-20,0,100,30,0,0,0,100,0,0)
    assert b['appropriation']==1 and b['dividend']==9 and b['cash']==31
    c=settle(10,-20,0,100,10,0,0,0,100,0,0)
    assert c['appropriation']==0 and c['dividend']==0 and c['retained']==-10
    d=settle(0,100,0,100,0,0,100,20,0,0,30)
    assert d['funding_failure']==90 and d['dividend']==0
    e=settle(50,0,0,100,0,0,0,0,50,0,0) # old dividend receipt is cash only
    assert e['dividend']==0
    f=settle(100,10,0,100,0,0,0,0,80,0,0)
    assert f['dividend']==10 # ordinary + principal share ONE legal budget
    failed=run(dict(SCENARIOS['base'],extra_capital=1000000.,zero_distributions=True),5,True)
    assert not failed['feasible'] and failed['pv'] is None and failed['terminal_year5'] is None
    assert len(failed['rows'])==1 and all(n['new_declaration']==0 for n in failed['rows'][0]['nodes'])
    return dict(profit_zero_capital_return=cr,full_run_zero_dividend_capital_failure=failed,capped_reserve=a,loss_recovery=b,unrecovered_loss=c,zero_dividend_failure=d,old_receivable=e,shared_legal_budget=f)

def decode_rows(packed,schema):
    """Pure lossless table decoder: no model parameters or external state."""
    result=[]
    for values in packed:
        row=dict(zip(schema['row_columns'],values))
        row['nodes']=[dict(zip(schema['node_columns'],n)) for n in row['nodes']]
        result.append(row)
    return result

def canonical(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()

def expand_output(envelope):
    """Pure decoder, no production inputs: verifies canonical annual-table SHA."""
    out=copy.deepcopy(envelope)
    if 'annual_tables' not in out:return out
    payload=out.pop('annual_tables')
    raw=gzip.decompress(base64.b64decode(payload['data']))
    assert hashlib.sha256(raw).hexdigest()==payload['expanded_sha256']
    tables=json.loads(raw)
    assert canonical(tables)==raw
    for group,cases in tables.items():
        for key,rows in cases.items():out[group][key]['rows']=rows
    return out

def build():
    out={'symbol':'CN:688188','period':'2026-Q3','currency_unit':'CNY million','share_unit':'million','as_of':'2026-10-26T11:00:00+00:00','scenarios':{},'sensitivities':{},'production_hand_tests':tests(),'auxiliary':auxiliary()}
    out['project_completion_policy']={'release_year_budget':8,'evidence':'H1募投专项PDF41-42预计2028年12月可使用；2026-014 PDF12贷款至实施完成、允许续期；历史2023/2025结项补流支持有限实现路径，不是未来批准事实','mechanics':'不增加现金或法定利润，解除用途下限后仍按主体分配、少数和在途时序支付；Y8为模型项目贷款回收完毕的保守结项预算，Y10/15延期敏感'}
    out['input_evidence']={'units': 'CNY million', 'mother_statutory_reserve': {'value': 144.3649635, 'status': '事实：母权益表与法定明细交叉勾稽，不是直接拿合并余额代母', 'source_url': 'https://static.cninfo.com.cn/finalpage/2026-04-10/1225091045.PDF', 'pdf_pages': [138, 220], 'h1_confirmation_url': 'https://static.cninfo.com.cn/finalpage/2026-08-18/1225477071.PDF', 'h1_pdf_pages': [65, 76, 77, 145]}, 'bochu_nc_reserve': {'value': 0, 'status': '未披露逐户余额；有限保守预算，至注册60的一半30停止'}, 'boci_reserve': {'value': 0, 'status': '未披露逐户余额；有限保守预算，至注册32的一半16停止'}, 'precision_reserve': {'value': 0, 'status': '2026年4月新设且H1亏损的事实约束推断，不是独立储备余额表披露', 'registered_capital': 55, 'direct_parent_investment': 41.25, 'direct_ownership': 0.75, 'indirect_effective_ownership': 0.196964}, 'registered_capital_timing': 'H1 PDF79公司概况明确注册405.557343百万元；母Q3起始405.984426及未来新股份面值是预计登记预算，0.427083差额注册时序未独立核。缴款额与溢价不全部增加注册资本。', 'opening_retained': '母H1已知2117.98683116减宣派236.03437363=1881.95245753；数控200/波刺300为预算，精密-1.9109为H1新设损失期初代理。', 'indirect_routes': '平台是经济转款渠道，核心额外一年转宣派；0/2年边界。不对合伙应用公司法公积、不赋额外存量资产价值。', 'residual_entities': '其他小额公司未逐法人映射，未来经营贡献归入经营预算；不将四账户代表为全集团已审法定账。'}
    for k,p in SCENARIOS.items():out['scenarios'][k]=run(p)
    out['holder_conditionals']={k:run(dict(SCENARIOS[k],prefix_base=True,release=.15)) for k in ['core_low','core_high']}
    for label,change in {'registration_delay_1y':{'registration_delay':1},'registration_delay_2y':{'registration_delay':2},'unmapped_profit_haircut_2pct':{'unmapped_profit_haircut':.02},'unmapped_profit_haircut_3pct':{'unmapped_profit_haircut':.03},'indirect_route_same_year':{'indirect_route_delay':0},'indirect_route_delay_2y':{'indirect_route_delay':2},'r_plus_1pp':{'r':.10},'r_minus_1pp':{'r':.08},'long_margin_minus_5pp':{'mt':.35},'incremental_return_15pct':{'roi':.35,'rt':.15},'no_subsidiary_upstream':{'no_upstream':True},'no_extra_principal_release':{'release':0},'collection_delay_200m':{'settlement_delay':200},'projects_plus_300m':{'extra_capital':100},'financial_yield_1pct':{'yield':.01},'tail_growth_0pct':{'tail_g':0},'zero_sub_opening_legal_profit':{'no_opening_sub_earnings':True},'parent_cash_500m_lower':{'parent_cash_shift':500},'project_completion_release_delay_y10':{'release_restricted_year':10},'project_completion_release_delay_y15':{'release_restricted_year':15},'restricted_never_released_extreme':{'release_restricted_year':0},'capital_return_y10_300m':{'capital_return_year':10,'capital_return_amount':300.,'capital_cancel_fraction':.10},'capital_return_y20_300m':{'capital_return_year':20,'capital_return_amount':300.,'capital_cancel_fraction':.10},'capital_return_y10_600m':{'capital_return_year':10,'capital_return_amount':600.,'capital_cancel_fraction':.20}}.items():
        out['sensitivities'][label]=run(dict(SCENARIOS['base'],**change))
    out['convergence']={}
    for k,p in SCENARIOS.items():
        seq={}
        for horizon in [300,600,900,1200]:
            z=run(p,horizon,True)
            seq[str(horizon)]={"pv":z['pv'],"terminal_year5":z['terminal_year5'],"last_full_state":z['rows'][-1]}
        out['convergence'][k]=seq
    for k in ['core_low','core_high']:
        assert out['holder_conditionals'][k]['rows'][:5]==out['scenarios']['base']['rows'][:5], 'holder first-five full states differ'
    out['holder_first_five_full_states_equal']=True
    # Lossless columnar JSON removes repeated field names but retains every
    # annual/entity scalar (including all tail years and every sensitivity).
    example=out['scenarios']['base']['rows'][0]
    out['table_schema']={'row_columns':list(example),'node_columns':list(example['nodes'][0])}
    for group in ['scenarios','sensitivities','holder_conditionals']:
        for case in out[group].values():
            packed=[]
            for row in case['rows']:
                nodes=[[node[k] for k in out['table_schema']['node_columns']] for node in row['nodes']]
                packed.append([nodes if col=='nodes' else row[col] for col in out['table_schema']['row_columns']])
            assert decode_rows(packed,out['table_schema'])==case['rows']
            assert decode_rows(json.loads(json.dumps(packed,allow_nan=False)),out['table_schema'])==case['rows']
            case['rows']=packed
    out['columnar_full_field_roundtrip_verified']=True

    original=copy.deepcopy(out)
    tables={group:{key:case.pop('rows') for key,case in out[group].items()} for group in ['scenarios','sensitivities','holder_conditionals']}
    raw=canonical(tables)
    out['annual_tables']={'encoding':'gzip-mtime0-base64-canonical-json','expanded_sha256':hashlib.sha256(raw).hexdigest(),'expanded_bytes':len(raw),'data':base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode()}
    assert expand_output(out)==original
    assert expand_output(json.loads(canonical(out)))==original
    return out
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',default=str(ROOT/'2026-Q3-output.json'));ap.add_argument('--expand',help='Purely expand an existing output; no model execution');a=ap.parse_args()
    if a.expand:
        pathlib.Path(a.output).write_bytes(canonical(expand_output(json.loads(pathlib.Path(a.expand).read_text())))+b'\n');raise SystemExit(0)
    result=build();pathlib.Path(a.output).write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
    print(json.dumps({k:{j:v[j] for j in ['pv','terminal_year5','distributions','feasible']} for k,v in result['scenarios'].items()},ensure_ascii=False,indent=2))

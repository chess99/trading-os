#!/usr/bin/env python3
"""CN:688188 2026-Q3. RMB million, million shares; standard-library only.
Annual periods end on successive anniversaries of 2026-10-26. Four explicit
legal payout nodes; residual small holding entities conservatively absorbed in the
sales-node operating budget, not separately capitalised. No market price.
"""
import json, math, pathlib, argparse, copy, gzip, base64, hashlib
ROOT=pathlib.Path(__file__).resolve().parent
SCENARIOS={
 'base':dict(g=[.15,.14,.12,.10,.08,.065,.05,.04,.03,.02],m0=.46,mt=.40,r=.09,roi=.60,rt=.25,release=.15,up_start=3),
 'core_low':dict(g=[.13,.12,.10,.09,.07,.055,.045,.035,.025,.02],m0=.45,mt=.39,r=.095,roi=.55,rt=.25,release=.10,up_start=3),
 'core_high':dict(g=[.17,.15,.13,.11,.09,.07,.055,.04,.03,.02],m0=.47,mt=.41,r=.085,roi=.65,rt=.28,release=.20,up_start=3),
 'cyclical':dict(g=[-.10,.02,.20,.15,.10,.07,.05,.04,.03,.02],m0=.38,mt=.40,r=.09,roi=.60,rt=.25,release=.15,up_start=4),
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

def run(s,n=600,records=True):
    p=copy.deepcopy(s); names=['parent','bochu_nc','boci','precision']; ownership=[1,1,.9275,.946964]
    # H1 parent actual cash+trading assets 4323.784810; Q3 aggregate 5730.572263.
    # Q3 legal-entity allocation is a budget, NOT a disclosed Q3 standalone sheet.
    cash=[4500.,806.0990022124001,380.,25.0034]; re=[1881.95245753,200.,300.,-1.9109]
    res=[144.3649635,0.,0.,0.]; cap=[405.984426,60.,32.,55.]
    debt=[28.99906365,0.,0.,0.]; payable=[236.03437363,0.,0.,0.]; receivable=[0.,0.,0.,0.]
    if p.get('no_opening_sub_earnings'): re[1:3]=[0.,0.]
    if p.get('parent_cash_shift'): cash[0]-=p['parent_cash_shift'];cash[1]+=p['parent_cash_shift']
    invcap=[400.,270.,200.,30.]; shares=405.984426; rev=2500.; lastprofit=1150.
    intercompany=[0.,0.]
    restricted=[999.4403,24.984,0.,11.2534]
    precision_op=-4.
    pv=tv=0.; rows=[]; maxfail=0.; cum_minor=0.; d5=[]
    for y in range(1,n+1):
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
        shares+=newshares; cap[0]+=newshares
        start_cash=cash.copy(); start_re=re.copy(); start_debt=debt.copy(); start_pay=payable.copy()
        old_received=[payable[1]+payable[3]*.946964,payable[2]*.9275,0.,0.]
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
        operational=[op*.779,op*.12-precision_op,op*.10,precision_op]
        ownprofit=[operational[i]+fin[i]-sbc*([.8,.1,.1,0.][i]) for i in range(4)]
        investments=([608.8312/3+(investment-698.8312/3)*.35,80/3+(investment-698.8312/3)*.34,(investment-698.8312/3)*.30,10./3+(investment-698.8312/3)*.01] if y<=3 else [investment*.35,investment*.34,investment*.30,investment*.01])
        floors=[rev*.06+restricted[0],rev*.04+restricted[1],rev*.025+restricted[2],rev*.001+restricted[3]]
        declarations=[0.,0.,0.,0.]; legalprofit=ownprofit.copy(); node=[None]*4
        for i in [3,2,1,0]:
            if i==0:legalprofit[i]+=declarations[1]+declarations[3]*.946964
            if i==1:legalprofit[i]+=declarations[2]*.9275
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
            if i>0:
                # settle() subtracts d as though paid; restore earmarked cash
                # and create next-period payable. RE stays reduced now.
                z['cash']+=d; payable[i]=d; receivable[1 if i==2 else 0]+=d*ownership[i]
            cash[i],re[i],res[i],debt[i]=z['cash'],z['retained'],z['reserve'],z['debt']
            invcap[i]+=investments[i]
            expected=start_cash[i]+old_received[i]-start_pay[i]+internal_flow[i]+(-transfer if i==0 else transfer if i==1 else 0)+ownprofit[i]+sbc*([.8,.1,.1,0.][i])-investments[i]+(proceeds if i==0 else 0)+z['draw']-z['repay']-(d if i==0 else 0)
            assert abs(cash[i]-expected)<max(1e-6,abs(cash[i])*1e-12)
            assert re[i]>=-1e-8 or d==0
            assert res[i]<=cap[i]*.5+1e-8
            assert d<=max(z['legal_before'],0)+1e-8
            maxfail=max(maxfail,z['funding_failure'])
            node[i]=dict(name=names[i],restricted_open=restricted_open[i],financial_interest_base=interest_base[i],restricted_interest_base=restricted_interest_base[i],restricted_financial_income=restricted_income[i],restricted_transfer=restricted_transfer[i],eligible_project_spending=eligible_spend[i],qualified_project_spending=qualified_spend[i],project_spending_from_own_funds=eligible_spend[i]-qualified_spend[i],restricted_close=restricted[i],conditional_authorised_release=conditional_authorised_release[i],internal_project_cash_flow=internal_flow[i],intercompany_loan_receivable=(intercompany[0] if i==0 else intercompany[1] if i==1 else 0),intercompany_loan_payable=(intercompany[0] if i==1 else intercompany[1] if i==2 else 0),cash_open=start_cash[i],cash_close=cash[i],retained_open=start_re[i],retained_close=re[i],reserve=res[i],paid_in_capital=cap[i],own_profit=ownprofit[i],declared_investment_income=investment_income,prior_dividend_received=old_received[i],prior_payable_paid=start_pay[i],new_declaration=d,ordinary_requested=ordinary,release_requested=release,legal_profit_before_distribution=z['legal_before'],reserve_appropriation=z['appropriation'],investment=investments[i],noncash_compensation=sbc*([.8,.1,.1,0.][i]),financial_income=fin[i],liquidity_floor=floors[i],debt_close=debt[i],debt_draw=z['draw'],debt_repaid=z['repay'],funding_failure=z['funding_failure'],dividend_payable=payable[i],dividend_receivable=receivable[i],invested_capital=invcap[i],capital_inflow=proceeds if i==0 else 0)
        dist=declarations[0]/shares+(old_common/405.557343 if y==1 else 0)
        pv+=dist/(1+p['r'])**y
        if y>5: tv+=dist/(1+p['r'])**(y-5)
        if y<=5:d5.append(dist)
        cum_minor+=minor_paid
        if records:rows.append(dict(year=y,revenue=rev,operating_cash_net_margin=margin,operating_cash_profit=op,net_investment=investment,incremental_roic=iroic,maintenance_capex=rev*.02,depreciation=rev*.02,shares=shares,new_shares=newshares,capital_inflow=proceeds,minority_cash_paid=minor_paid,ordinary_shareholder_cash=declarations[0],old_dividend_paid=old_common,distribution_per_share=dist,nodes=node))
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
    return dict(full_run_zero_dividend_capital_failure=failed,capped_reserve=a,loss_recovery=b,unrecovered_loss=c,zero_dividend_failure=d,old_receivable=e,shared_legal_budget=f)

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
    for k,p in SCENARIOS.items():out['scenarios'][k]=run(p)
    out['holder_conditionals']={k:run(dict(SCENARIOS[k],prefix_base=True,release=.15)) for k in ['core_low','core_high']}
    for label,change in {'r_plus_1pp':{'r':.10},'r_minus_1pp':{'r':.08},'long_margin_minus_5pp':{'mt':.35},'incremental_return_15pct':{'roi':.35,'rt':.15},'no_subsidiary_upstream':{'no_upstream':True},'no_extra_principal_release':{'release':0},'collection_delay_200m':{'settlement_delay':200},'projects_plus_300m':{'extra_capital':100},'financial_yield_1pct':{'yield':.01},'tail_growth_0pct':{'tail_g':0},'zero_sub_opening_legal_profit':{'no_opening_sub_earnings':True},'parent_cash_500m_lower':{'parent_cash_shift':500},'conditional_approved_restricted_release_y8':{'release_restricted_year':8}}.items():
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

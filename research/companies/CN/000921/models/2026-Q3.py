#!/usr/bin/env python3
"""海信家电2026Q3，人民币十亿元；慢恢复与逐年金融释放的核心持有人模型；原证、研究假设与敏感性分开。
实际分红受资金及法定利润双约束；历史现金分项冲突保留，不反改原表。
"""
import json, math
from pathlib import Path
SHARES=1.384861171 # 保持已发行全部股数，未执行注销不提前享受
OWN=.492

def pv_flows(flows,r):
    return sum(x/(1+r)**(i+1) for i,x in enumerate(flows))

def treasury_value(principal,rate,yield_rate,delay,release_years):
    """利息每年支付；本金delay年后等额release_years年回收；None=不回收本金。
    仅是治理/期限单因素诊断，未声称已授权特别分红。"""
    if release_years is None:
        return principal*yield_rate/rate
    balance=principal; flows=[]
    for year in range(1,delay+release_years+1):
        interest=balance*yield_rate
        release=principal/release_years if year>delay else 0
        balance-=release; flows.append(interest+release)
    assert abs(balance)<1e-8
    return pv_flows(flows,rate)

def operating_dcf(np_b,np_other,investment_b,investment_other,r=.10,g=.015,roi=.14):
    """已经按实际权益归属；其他为归母净数，不能再次扣三电少数。
    np剔除金融收益，投资为DA后净固定/营运追加，借款税后成本超过金融收益率的净利差已入其他税后利润。
    TV再投资与g/ROI相容；不自动计入金融本金。"""
    cf=[OWN*(p-i)+q-j for p,q,i,j in zip(np_b,np_other,investment_b,investment_other)]
    n=len(cf)
    np_next=(OWN*np_b[-1]+np_other[-1])*(1+g)
    terminal_cf=np_next*(1-g/roi)
    tv=terminal_cf/(r-g)
    pv=pv_flows(cf,r)+tv/(1+r)**n
    return dict(common_profit=[OWN*p+q for p,q in zip(np_b,np_other)],common_fcfe=cf,operating_value=pv,operating_terminal=tv,terminal_pv_share=tv/(1+r)**n/pv)

def parent_budget(np_b,np_other,dividend_ps,initial_cash=1.5,initial_legal=6.03298055478,y=.015):
    """辅助诊断普通分红候选的付款约束；海信博世70%和其他50%宣派且当年到账是条件。
    初始现金1.5为H1余额扣已宣股息及缓冲后的量级，非已核Q3母公司余额。
    不把应收股利收回再次计为利润；不以该诊断发布return_model。"""
    cash=initial_cash; legal=initial_legal; rows=[]
    for i,(p,q,d) in enumerate(zip(np_b,np_other,dividend_ps)):
        up=OWN*p*.7+max(q,0)*.5
        income=up+cash*y
        desired=d*SHARES
        actual=max(0,min(desired,cash+income,legal+income))
        before=cash;cash+=income-actual;legal+=income-actual
        assert abs(before+income-actual-cash)<1e-10
        assert cash>=-1e-10 and legal>=-1e-10
        rows.append(dict(year=2027+i,upstream_declared_and_received=up,parent_profit=income,desired_dividend=desired,actual_dividend=actual,parent_cash=cash,parent_legal_profit=legal,constrained=actual<desired-1e-10))
    return rows

PATHS={
 'partial_recovery':dict(np_b=[2.3,2.4,2.5,2.6,2.7],np_other=[.35,.45,.6,.7,.8],investment_b=[.45]*5,investment_other=[.5,.45,.4,.35,.35]),
 'cyclical_delay':dict(np_b=[1.9,2.1,2.3,2.5,2.7],np_other=[.1,.2,.4,.6,.8],investment_b=[.55,.55,.5,.45,.45],investment_other=[.6,.55,.45,.4,.35]),
 'structural_loss':dict(np_b=[2.0,1.8,1.6,1.5,1.4],np_other=[.1,0,-.1,-.1,.2],investment_b=[.55]*5,investment_other=[.6,.55,.5,.6,.35]),
 'better_execution':dict(np_b=[2.5,2.7,2.9,3.1,3.3],np_other=[.5,.65,.8,1.,1.2],investment_b=[.55]*5,investment_other=[.6,.6,.55,.5,.5])}

def owner_run(inputs, common_finance=21., bosch_finance=8., release=.03, r=.10, g=.015, years=200, other_legal=6., parent_start=1.5, parent_legal=6.03298055478,exit_other=False,bosch_legal=5.5,yield_rate=.015):
    # C为扣外债/必要经营资金后的净金融等效余额；负债正常续作的税后净利差已入其他经营NP。
    # 博世bucket为全额；R为其他业务已扣少数的权益组合，三电不承担上划预算。
    cb=bosch_finance; cr=common_finance-OWN*cb-parent_start; cp=parent_start
    lb=bosch_legal;lr=other_legal;lp=parent_legal
    assert min(cb,cr,cp)>=0
    rows=[]; distributions=[]; cap_b=cap_r=0; reserve_b=reserve_r=reserve_p=0
    for t in range(1,years+1):
        if t<=5:
            nb=inputs['np_b'][t-1];nr=inputs['np_other'][t-1]
            ib=inputs['investment_b'][t-1];ir=inputs['investment_other'][t-1]+(1. if exit_other and t==5 else 0)
        else:
            nb=inputs['np_b'][-1]*(1+g)**(t-5);nr=inputs['np_other'][-1]*(1+g)**(t-5)
            ib=nb*g/.14+(0.15 if g==0 else 0);ir=max(nr,0)*g/.14+(0.2 if g==0 else 0)
            if exit_other:nr=0;ir=0
        cap_b+=ib;cap_r+=ir
        old=(cb,cr,cp);interest_b=cb*yield_rate;interest_r=cr*yield_rate;interest_p=cp*yield_rate
        pb=nb+interest_b;pr=nr+interest_r
        # 未逐主体证明公积已达上限：每年正利润保守提10%，亏损全额结转。
        # 即使尚有未弥补亏损也提取正利润的10%，且不假设未来达到上限停止；因此偏保守。
        rb=max(pb,0)*.10;rr=max(pr,0)*.10
        reserve_b+=rb;reserve_r+=rr
        cb+=pb-ib;cr+=pr-ir;lb+=pb-rb;lr+=pr-rr
        # 资金不足时停止新增分配；负cash属于融资不可行，不能默许无偿注资。
        if min(cb,cr)<-1e-9:
            return {'feasible':False,'failure_year':2026+t,'reason':'subsidiary net liquidity exhausted','rows':rows}
        if t<=5:
            desired_b=max(0,.7*nb);desired_r=max(0,.5*nr)
        else:
            # 仅逐年释放余额2%-4%，同时派出当年经营净现金与金融利息；没有第五年全部释放。
            ramp=min(1.,.6+.08*(t-5))
            desired_b=max(0,nb-ib)*ramp+interest_b+release*ramp*old[0]
            desired_r=max(0,nr-ir)*ramp+interest_r+release*ramp*old[1]
        db=max(0,min(desired_b,cb,lb));dr=max(0,min(desired_r,cr,lr))
        cb-=db;cr-=dr;lb-=db;lr-=dr
        up=OWN*db+dr
        # 子股利不二次提取；母自有金融正收益仍保守提10%，不影响现金守恒。
        rp=max(interest_p,0)*.10;reserve_p+=rp
        cp+=up+interest_p;lp+=up+interest_p-rp
        desired=([.65,.75,.85,.95,1.05][t-1]*SHARES if t<=5 else up+interest_p+release*min(1.,.6+.08*(t-5))*old[2])
        d=max(0,min(desired,cp,lp));cp-=d;lp-=d
        start=OWN*old[0]+old[1]+old[2];end=OWN*cb+cr+cp
        assert abs(start+OWN*(pb-ib)+(pr-ir)+interest_p-d-end)<1e-8
        assert min(cb,cr,cp)>-1e-8
        assert not (lb < -1e-8 and db > 1e-8)
        assert not (lr < -1e-8 and dr > 1e-8)
        assert not (lp < -1e-8 and d > 1e-8)
        distributions.append(d)
        rows.append(dict(year=2026+t,bosch_reserve_addition=rb,other_reserve_addition=rr,parent_reserve_addition=rp,bosch_cumulative_reserve=reserve_b,other_cumulative_reserve=reserve_r,parent_cumulative_reserve=reserve_p,bosch_operating_np=nb,other_common_operating_np=nr,bosch_net_investment=ib,other_net_investment=ir,bosch_declared_dividend=db,external_bosch_dividend=(1-OWN)*db,other_upstream=dr,parent_cash=cp,parent_legal=lp,bosch_cash=cb,other_common_cash=cr,bosch_legal=lb,other_legal=lr,common_net_finance=end,common_dividend=d,dividend_per_share=d/SHARES,dividend_capped=d<desired-1e-10))
    pv=pv_flows(distributions,r)/SHARES
    tv=sum(distributions[t-1]/(1+r)**(t-5) for t in range(6,years+1))/SHARES
    return dict(feasible=True,value_per_share=pv,terminal_year5=tv,distributions_first5=[d/SHARES for d in distributions[:5]],terminal_pv_share=(tv/(1+r)**5/pv if pv else 0),rows=rows,tail_note='200年后剩余现金与经营现值未加，误差以再跑300年检验')

def run():
    out={'status':'owner_cash_model','information_cutoff':'2026-10-26T14:00:00+08:00','unit':'CNY billion, per_share CNY','value_range':None,'return_model':None,'shares_billion':SHARES,'paths':{}}
    for key,inputs in PATHS.items():
        structural=key=='structural_loss'
        op=operating_dcf(**inputs,r=.11 if structural else .10,g=0 if structural else .015,roi=.10 if structural else .14)
        op['parent_budget']=parent_budget(inputs['np_b'],inputs['np_other'],[.65,.75,.85,.95,1.05])
        op['operating_value_per_share']=op['operating_value']/SHARES
        # 资本化仅诊断盈利持续性。9-12倍由10%成本/0-1.5%增速/必要再投约束，不取同业均值。
        op['earnings_power_operating_per_share']=[(pv_flows(op['common_fcfe'],.11 if structural else .10)+op['common_profit'][-1]*pe/(1+(.11 if structural else .10))**5)/SHARES for pe in [9,12]]
        out['paths'][key]=op
    out['treasury_sensitivity']={}
    for principal in [12.,20.]:
        out['treasury_sensitivity'][str(principal)]={}
        for label,delay,years in [('interest_only',0,None),('release_6_25',5,20),('release_11_30',10,20)]:
            out['treasury_sensitivity'][str(principal)][label]=treasury_value(principal,.10,.015,delay,years)/SHARES
    # 正式计算函数的可手算特例
    assert abs(pv_flows([11,12.1],.1)-20)<1e-10
    assert abs(treasury_value(100,.10,0,0,1)-100/1.1)<1e-10
    assert abs(treasury_value(100,.10,.02,0,None)-20)<1e-10
    # 当利润恒定、零再投、零增长、首期现金同于永续时，DCF=全年普通利润/r。
    v=operating_dcf([1]*5,[0]*5,[0]*5,[0]*5,r=.1,g=0)
    assert abs(v['operating_value']-.492/.1)<1e-10
    budget=parent_budget([0],[0],[1],initial_cash=.5,initial_legal=.2,y=0)
    assert abs(budget[0]['actual_dividend']-.2)<1e-10
    assert abs(budget[0]['parent_cash']-.3)<1e-10
    base=PATHS['partial_recovery']
    owner={}
    for name,params in {'low':dict(common_finance=19,bosch_finance=12,release=.02,r=.105),'center':dict(common_finance=21,bosch_finance=8,release=.03,r=.10),'high':dict(common_finance=23,bosch_finance=4,release=.04,r=.095)}.items():
        owner[name]=owner_run(base,**params)
        assert owner[name]['feasible']
        extended=owner_run(base,years=300,**params)
        assert abs(extended['value_per_share']-owner[name]['value_per_share'])<.0001
    out['value_range']={'low':round(owner['low']['value_per_share'],2),'high':round(owner['high']['value_per_share'],2),'currency':'CNY'}
    # 回报模型固定中点的同一资金、法定留存和分配路径，仅重估折现率。
    return_terminal={label:owner_run(base,common_finance=21,bosch_finance=8,release=.03,r=rate) for label,rate in [('low',.105),('high',.095)]}
    out['return_terminal_fixed_center']={label:dict(terminal_year5=v['terminal_year5'],discount_rate=.105 if label=='low' else .095) for label,v in return_terminal.items()}
    out['return_model']={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':out['information_cutoff'],'base_case_distributions_per_share':[round(d,4) for d in owner['center']['distributions_first5']],'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':round(return_terminal['low']['terminal_year5'],2),'high':round(return_terminal['high']['terminal_year5'],2)}}}
    out['auxiliary_total_range']=[owner['center']['value_per_share']+p-out['paths']['partial_recovery']['operating_value_per_share'] for p in out['paths']['partial_recovery']['earnings_power_operating_per_share']]
    out['finance_bridge']={'gross_financial_assets_estimate':35.5,'restricted':1.16,'operating_buffer':4.5,'external_interest_debt':4.4,'other_cash_obligations':.6,'group_net_finance':24.84,'bosch_total_net_finance_low_high':[4,12],'other_minority_net_debt_adjustment':.6,'common_net_finance_derived':[24.84-.508*12+.6,24.84-.508*4+.6],'common_net_finance_model':[19,23],'parent_cash_bridge':[3.56801452721,-1.75184938132,-.03080368884,-.2,-.08],'parent_statutory_profit_bridge':[7.06649564879,.71833428731,-1.75184938132]}
    out['owner_model']=owner
    out['owner_scenarios']={name:owner_run(inp,common_finance=21,bosch_finance=8,release=.03,r=.11 if name=='structural_loss' else .10,g=0 if name=='structural_loss' else .015,exit_other=False) for name,inp in PATHS.items()}
    out['owner_sensitivity']={
      'no_principal_release':owner_run(base,release=0),
      'other_legal_zero':owner_run(base,other_legal=0),
      'both_subsidiary_legal_zero':owner_run(base,other_legal=0,bosch_legal=0),
      'parent_cash_minus_1bn':owner_run(base,parent_start=.5),
      'working_capital_extra_3bn':owner_run(base,common_finance=18)}
    # 同一完整函数手算：首年无经营/利息无法隔离因固定收益，利用零资金与零利润零分配应全零。
    zero=dict(np_b=[0]*5,np_other=[0]*5,investment_b=[0]*5,investment_other=[0]*5)
    z=owner_run(zero,common_finance=0,bosch_finance=0,parent_start=0,parent_legal=0,other_legal=0,years=5)
    assert z['value_per_share']==0 and z['distributions_first5']==[0]*5
    # 单年正常经营B=1,R=0,C=0：B上划.7，其中母.3444，实际全部付出；B现金.3，归母末现金.1476。
    simple=dict(np_b=[1],np_other=[0],investment_b=[0],investment_other=[0])
    z=owner_run(simple,common_finance=0,bosch_finance=0,parent_start=0,parent_legal=0,other_legal=0,years=1)
    assert abs(z['rows'][0]['common_dividend']-.3444)<1e-10
    assert abs(z['rows'][0]['common_net_finance']-.1476)<1e-10
    loss=dict(np_b=[-1,.5,1],np_other=[0]*3,investment_b=[0]*3,investment_other=[0]*3)
    z=owner_run(loss,common_finance=.984,bosch_finance=2,parent_start=0,parent_legal=0,other_legal=0,bosch_legal=0,years=3,yield_rate=0)
    # 法定利润-1 -> -.55 -> .35（分配前）；第二年恢复盈利但亏损未填平，不能分红。
    assert abs(z['rows'][0]['bosch_legal']+1)<1e-10
    assert abs(z['rows'][1]['bosch_legal']+.55)<1e-10
    assert [row['bosch_declared_dividend'] for row in z['rows'][:2]]==[0,0]
    assert abs(z['rows'][2]['bosch_declared_dividend']-.35)<1e-10
    assert abs(z['rows'][2]['bosch_cash']-2.15)<1e-10
    assert abs(z['rows'][2]['common_dividend']-.1722)<1e-10
    out['statutory_loss_test']=z
    out['tests']='positive profits reserve 10%, full losses carried forward, actual-function loss recovery test; analytic function cases, owner cash conservation, legal constraints and 200/300-year convergence passed'
    return out
if __name__=='__main__':
    data=run();Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(data,ensure_ascii=False,indent=2));print(json.dumps(data,ensure_ascii=False,indent=2))

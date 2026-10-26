#!/usr/bin/env python3
"""卫星化学独立研究。stdlib only; 金额亿元、股数亿股；非价格/IRR模型。
经营船租现金化，利息仅对非船租金融本金计一次。税/法定储备/现金分开。
主体预算是公开合并总量与已披露持股链约束的研究分配，不是公司分部指引。
"""
import json, math, copy
from pathlib import Path
SHARES=33.68645690
# Q3现有银行长期17.4623；当期到期17.8906中船租沿H1估17.2369，余0.6538。
# 应付票据51.2530为贴现融资；短期金属租借按其他流动负债扣1亿税估29.3038；长期1.9177。
DEBT=17.4622684964+(17.890628146-17.236864745)+51.2530244+29.303815726+1.9177433628
FREE_CASH=128.1150078051
RESTRICTED=142.1546221072-FREE_CASH
SECURITIES=9.118
INVESTMENT=23.0780722239
MINORITY=.118577
ENTITIES=['L','I','E','H','O','P']
BASE={
 'revenue':[580,600,630,655,675],
 'before_rent_ebit':[132,138,148,158,163],
 'rent':[30,32,34,35,36],
 'da':[28,29,31,33,35],
 'maintenance':[30,31,33,35,37],
 'project':[26,22,13.29,0,0],
 'ongoing_growth':[5,6,8,10,12],
 'working_capital':[4,4,5,5,5],
 'old_capital_payables':[12,10.64941641,0,0,0],
 'payout':[.65,.75,.85,.95,1.05],
 'rate':.033,'cash_yield':.01,'upstream_delay':0,
 'profit_scale':[1]*5,'capex_scale':[1]*5,
 'max_new_debt':40,'parent_limit':12,'extra_rent':[0]*5,
 'extra_working_capital':[0]*5,'freeze_distributions':False
}
WEIGHTS={'L':.70,'E':.13,'H':.10,'O':.02,'P':.05,'I':0}
CAPWEIGHTS={'L':.65,'E':.10,'H':.10,'O':0,'P':.15,'I':0}
# Parent 0.902亿自由现金来自最新母表；他主体分配是假设。O保留20亿进口结算缓冲。
CASH0={'L':70,'I':0,'E':20,'H':10,'O':FREE_CASH-100-.9016081171,'P':.9016081171}
FLOOR={'L':7,'I':0,'E':1.5,'H':1,'O':20,'P':.5}
DEBT0={'L':DEBT*.48,'I':0,'E':DEBT*.24,'H':DEBT*.20,'O':DEBT*.02,'P':DEBT*.06}
# 不借用未披露子公司旧利润支持普通派息；由预测盈利先弥补亏损后提10%储备。
RESERVE_ROOM={'L':28,'I':22.4,'E':15.975,'H':6,'O':.522345,'P':SHARES*.5-9.2269774471}
PROFITS0={'L':0,'I':0,'E':0,'H':0,'O':0,'P':9.0996638532}
# 80%产业发展、20%平湖的预算路由；海外->卫星能源->母体。
ROUTE={'L':[('I',.8),('H',.2)],'I':[('P',1)],'E':[('P',1)],'H':[('P',1)],'O':[('E',1)]}

def close(a,b): return abs(a-b)<1e-8*max(1,abs(a),abs(b))
def legal_profit(balance, profit, reserve_room=float('inf')):
    """只有填补累计亏损后的新增正利润提公积；母子境内股利免税不重复集团税。"""
    eligible=max(0.,profit-max(0.,-balance)) if profit>0 else 0.
    reserve=min(.1*eligible,max(0,reserve_room))
    return balance+profit-reserve,reserve

def operating_cash(ebit,interest,da,maintenance,growth,wc,tax=.15,minority=0,legal_adjustment=0):
    # EBIT为完整现金船租后的经营利润，金融本金不在此函数扣。
    taxable=ebit+legal_adjustment-interest
    tax_paid=max(0,taxable)*tax # 不凭亏损产生现金退税
    net=taxable-tax_paid-minority
    cash=net-legal_adjustment+da-maintenance-growth-wc
    return {'net_profit':net,'tax':tax_paid,'cash':cash,'interest':interest}

def simulate(config):
    c=copy.deepcopy(config);cash=copy.deepcopy(CASH0);debt=copy.deepcopy(DEBT0)
    legal=copy.deepcopy(PROFITS0); reserves={k:0. for k in ENTITIES}; pending=[]
    rows=[];borrowed=0.;new_by={k:0. for k in ENTITIES}
    def declare(src,amount,year,delay):
        amount=min(max(0,amount),max(0,legal[src]),max(0,cash[src]-FLOOR[src]))
        if amount<=0:return 0.
        legal[src]-=amount
        # 法定宣派已确认接收方投资收益；现金仍归付款主体，锁定不可再宣派。
        cash[src]-=amount
        for dest,w in ROUTE[src]:
            v=amount*w;legal[dest],r=legal_profit(legal[dest],v,RESERVE_ROOM[dest]-reserves[dest]);reserves[dest]+=r
            pending.append({'src':src,'dest':dest,'due':year+delay,'cash':v})
        return amount
    for t in range(5):
        opening=sum(cash.values())+sum(p['cash'] for p in pending)
        opening_debt=sum(debt.values());flows={};ordinary=0.; declared={k:0. for k in ENTITIES}
        erent=c['rent'][t]+c['extra_rent'][t]
        ebit=c['before_rent_ebit'][t]*c['profit_scale'][t]-erent
        maint=c['maintenance'][t]*c['capex_scale'][t]
        growth=(c['project'][t]+c['ongoing_growth'][t])*c['capex_scale'][t]
        wc=c['working_capital'][t]+c['extra_working_capital'][t]
        total_oper=0.;total_net=0.;total_tax=0.;total_interest=0.;funding=0.
        for k in ENTITIES:
            w=WEIGHTS[k]; cap=CAPWEIGHTS[k]
            interest=debt[k]*c['rate']
            # 金融收益按期初可动用现金计，受限本金不以收益冒充本金价值。
            income=max(0,cash[k]-FLOOR[k])*c['cash_yield']
            f=operating_cash(ebit*w+income,interest,c['da'][t]*cap,maint*cap,growth*cap,wc*w,
                             .17 if k=='O' else .15, .02 if k=='H' else 0., .5*w)
            cash[k]+=f['cash'];legal[k],res=legal_profit(legal[k],f['net_profit'],RESERVE_ROOM[k]-reserves[k]);reserves[k]+=res
            cap_payment=c['old_capital_payables'][t]*cap
            cash[k]-=cap_payment
            total_oper+=f['cash'];total_net+=f['net_profit'];total_tax+=f['tax'];total_interest+=interest
            flows[k]={**f,'old_capital_payment':cap_payment,'cash_after_operations':cash[k]}
        # 有限融资先保证各主体经营必需现金；未获公开承诺的授信是预算而非确定事实。
        for k in ENTITIES:
            need=max(0,FLOOR[k]-cash[k])
            capacity=min(c['max_new_debt']-borrowed,(c['parent_limit']-new_by[k]) if k=='P' else c['max_new_debt']-borrowed)
            loan=min(need,max(0,capacity))
            cash[k]+=loan;debt[k]+=loan;borrowed+=loan;new_by[k]+=loan;funding+=loan
            if cash[k]<-1e-8 or cash[k]+1e-8<FLOOR[k]:
                return {'feasible':False,'failed_year':t+1,'failed_entity':k,'shortfall':max(0,FLOOR[k]-cash[k]),'distributions_suspended':True,'rows':rows,'cash':cash,'debt':debt}
        # 仅法定分配能力与剩余现金都通过才宣派；C2 80/20先经控股主体，海外先经能源。
        delay=c['upstream_delay']
        for k in ['L','O','I','E','H']:
            receipts=[p for p in pending if p['dest']==k and p['due']<=t]
            for p in receipts:cash[k]+=p['cash'];pending.remove(p)
            # 普通上划预算最高净利润55%；旧投资收益收现不增利润（宣派时已记）。
            cap=.55*max(0,flows[k]['net_profit']) if k in ['L','O'] else max(0,cash[k]-FLOOR[k])
            declared[k]=declare(k,cap,t,delay)
        receipts=[p for p in pending if p['dest']=='P' and p['due']<=t]
        for p in receipts:cash['P']+=p['cash'];pending.remove(p)
        want=0 if c['freeze_distributions'] else c['payout'][t]*SHARES
        ordinary=min(want,max(0,legal['P']),max(0,cash['P']-FLOOR['P']))
        legal['P']-=ordinary;cash['P']-=ordinary
        ending=sum(cash.values())+sum(p['cash'] for p in pending)
        assert close(ending,opening+total_oper-sum(c['old_capital_payables'][t]*CAPWEIGHTS[k] for k in ENTITIES)+funding-ordinary)
        assert close(sum(debt.values()),opening_debt+funding)
        assert all(v>=-1e-8 for v in cash.values())
        rows.append({'year':t+1,'revenue':c['revenue'][t],'ebit_before_rent':c['before_rent_ebit'][t]*c['profit_scale'][t],
            'rent':erent,'ebit':ebit,'nopat':ebit*.85,'nonlease_interest':total_interest,'tax':total_tax,'net_profit':total_net,
            'da':c['da'][t],'maintenance':maint,'growth':growth,'working_capital':wc,'old_capital_payments':c['old_capital_payables'][t],
            'cash_generated':total_oper,'new_debt':funding,'ordinary_dividend':ordinary,'dps':ordinary/SHARES,
            'cash_by_entity':copy.deepcopy(cash),'debt_by_entity':copy.deepcopy(debt),'legal_by_entity':copy.deepcopy(legal),
            'reserves_by_entity':copy.deepcopy(reserves),'upstream_declared':declared,'pending_dividends':copy.deepcopy(pending),'flows':flows,
            'total_cash':ending,'total_debt':sum(debt.values())})
    return {'feasible':True,'rows':rows,'cash':cash,'debt':debt,'legal':legal,'pending':pending,'reserves':reserves,'config':c}

def release_financial_assets(result,ke,years=3,blocked_years=0):
    """第五年金融本金实际分批宣派到账再支付。无虚构新利润；未能分派残额保留。
受限保证金保持配对融资不提前释放，仅给第五年以后配对借款清偿时的净额价值。
本函数可分现金不包括受限金/证券，证券单独在最后一年到期释放，子公司留存利润约束。
"""
    cash=copy.deepcopy(result['cash']);legal=copy.deepcopy(result['legal']);pending=copy.deepcopy(result['pending'])
    reserves=copy.deepcopy(result['reserves'])
    release=[];pv=0.;sec=SECURITIES
    initial_total=sum(cash.values())+sum(p['cash'] for p in pending)+sec
    cumulative_paid=0
    target={k:max(0,cash[k]-FLOOR[k]) for k in ENTITIES}
    for t in range(1,years+blocked_years+1):
        paid=0.;declared={k:0. for k in ENTITIES}
        if t>blocked_years:
            left=years+blocked_years-t+1
            # 到期的证券本金不确认新利润；现金只增加本金，利润仍受既有legal约束。
            if t==years+blocked_years:cash['E']+=sec;sec=0
            for k in ['L','O','I','E','H']:
                # 外部普通利润不在释放本金桥另算：只释放已经存在的合法储备。
                amount=min(max(0,cash[k]-FLOOR[k])/left,max(0,legal[k]))
                cash[k]-=amount;legal[k]-=amount;declared[k]=amount
                for dst,w in ROUTE[k]:
                    v=amount*w;cash[dst]+=v;legal[dst],added=legal_profit(legal[dst],v,RESERVE_ROOM[dst]-reserves[dst]);reserves[dst]+=added
            # 之前已宣派未到账本金按实际延期付款，不再次确认投资利润。
            mature=[p for p in pending if p['due']<=4+t]
            for p in mature:cash[p['dest']]+=p['cash'];pending.remove(p)
            paid=min(max(0,cash['P']-FLOOR['P']),max(0,legal['P']))
            cash['P']-=paid;legal['P']-=paid
            pv+=paid/(1+ke)**t
        cumulative_paid+=paid
        assert close(sum(cash.values())+sum(p['cash'] for p in pending)+sec+cumulative_paid,initial_total)
        assert all(v>=-1e-8 for v in cash.values())
        release.append({'post_year5_year':t,'declared':declared,'actual_common_payment':paid,'cash':copy.deepcopy(cash),'legal':copy.deepcopy(legal)})
    residual=sum(max(0,cash[k]-FLOOR[k]) for k in ENTITIES)+sum(x['cash'] for x in pending)+sec
    # 未派本金不消失，但未能证明法律可分配，不计入本次价值；保留余额及可追溯潜在价值。
    return {'pv_at_year5':pv,'undistributed_principal':residual,'rows':release,'security_remaining':sec}

def valuation(result,ke,wacc,g,roic,release_years=3,blocked_years=0):
    if not result['feasible']:return {'feasible':False}
    rows=result['rows'];r=rows[-1]
    nopat=r['ebit']*.85
    fcff6=nopat*(1+g)*(1-g/roic)
    ev5=fcff6/(wacc-g)
    release=release_financial_assets(result,ke,release_years,blocked_years)
    # 受限金14.039与同额融资匹配，既不分红又不算损失；净债仅扣D-R。
    debt_net=r['total_debt']-RESTRICTED
    inv=INVESTMENT # 经营EBIT剔除权益法收益，单列资本价值，未假定五年收到该本金。
    tv=(ev5-debt_net+inv-MINORITY+release['pv_at_year5'])/SHARES
    dpv=sum(row['dps']/(1+ke)**(i+1) for i,row in enumerate(rows))
    tvpv=tv/(1+ke)**5
    # 辅助FCFF法。起点自由现金及证券减最低经营资金；旧应付资本在期内实际支付，不另重复扣。
    fcff=[x['nopat']+x['da']-x['maintenance']-x['growth']-x['working_capital']-x['old_capital_payments'] for x in rows]
    aux=(sum(x/(1+wacc)**(i+1) for i,x in enumerate(fcff))+ev5/(1+wacc)**5+FREE_CASH+SECURITIES-sum(FLOOR.values())+RESTRICTED-DEBT+INVESTMENT-MINORITY)/SHARES
    return {'feasible':True,'ke':ke,'wacc':wacc,'growth':g,'incremental_roic':roic,'fcff6':fcff6,'ev_year5':ev5,
      'financial_release':release,'terminal_equity_per_share':tv,'value_per_share':dpv+tvpv,'dividend_pv':dpv,'terminal_pv_share':tvpv/(dpv+tvpv),'auxiliary_fcff_value':aux,'fcff':fcff}

def tests():
    # 送入正式经营现金函数：EBIT10,interest2,tax25%,DA3,maint4,growth2,WC1 => net6/cash2。
    f=operating_cash(10,2,3,4,2,1,.25);assert close(f['net_profit'],6) and close(f['cash'],2)
    adj=operating_cash(10,2,3,4,2,1,.25,0,2);assert close(adj['net_profit'],7.5) and close(adj['cash'],1.5)
    a,r=legal_profit(-5,8);assert close(a,2.7) and close(r,.3)
    a,r=legal_profit(-5,3);assert close(a,-2) and close(r,0)
    z=copy.deepcopy(BASE);z.update(profit_scale=[0]*5,max_new_debt=0,parent_limit=0,freeze_distributions=True,extra_working_capital=[200]*5)
    failed=simulate(z);assert not failed['feasible'] and failed['distributions_suspended']
    return {'formal_cash_hand_case':f,'loss_first_reserve_test':'pass','zero_dividend_finite_financing_failure':failed,'entity_cash_conservation':'asserted_each_year'}

def independent_recompute(result,v):
    # 仅折现算术复核，读取正式余额，不是原参数独立全链。全链见independent-full-chain.py。
    r=result['rows'][-1];k=v['ke'];w=v['wacc'];g=v['growth'];ic=v['incremental_roic']
    op=(r['ebit']*.85)*(1+g)*(1-g/ic)/(w-g)
    cashpv=0
    for row in v['financial_release']['rows']:cashpv+=row['actual_common_payment']/(1+k)**row['post_year5_year']
    eq=(op-r['total_debt']+RESTRICTED+INVESTMENT-MINORITY+cashpv)/SHARES
    pv=eq/(1+k)**5
    for i,row in enumerate(result['rows']):pv+=row['ordinary_dividend']/SHARES/(1+k)**(i+1)
    assert close(pv,v['value_per_share'])
    # 支配参数：仅Y6起持续EBIT降低10亿，Y1–5主体余额不变；局部解析诊断非全链情景。
    effect=-10*.85*(1+g)*(1-g/ic)/(w-g)/SHARES/(1+k)**5
    direct_alt=((op-10*.85*(1+g)*(1-g/ic)/(w-g))-r['total_debt']+RESTRICTED+INVESTMENT-MINORITY+cashpv)/SHARES/(1+k)**5+sum(row['ordinary_dividend']/SHARES/(1+k)**(i+1) for i,row in enumerate(result['rows']))
    assert close(direct_alt-pv,effect)
    return {'independent_value':pv,'permanent_ebit_minus_10_partial_value_change':effect,'alternate_value':direct_alt}

def main():
    scenarios={'base':copy.deepcopy(BASE)}
    weak=copy.deepcopy(BASE);weak.update(profit_scale=[.78,.80,.90,1,1],capex_scale=[1,1,1.05,1.05,1.05],extra_working_capital=[8,3,-4,-3,0],upstream_delay=1)
    scenarios['cyclical']=weak
    structural=copy.deepcopy(BASE);structural.update(profit_scale=[.65,.65,.62,.60,.60],capex_scale=[1.1]*5,extra_rent=[5]*5,extra_working_capital=[8,3,2,2,2],rate=.045,upstream_delay=1)
    scenarios['structural_unmitigated']=structural
    recovery=copy.deepcopy(structural);recovery.update(profit_scale=[.65,.65,.60,.58,.58],project=[15,18,18,10.29,0],ongoing_growth=[0,0,2,3,3],freeze_distributions=True)
    scenarios['structural']=recovery
    bull=copy.deepcopy(BASE);bull.update(profit_scale=[1.08,1.10,1.12,1.15,1.15],capex_scale=[1.05,1.05,1.1,1.1,1.1],extra_working_capital=[2]*5)
    scenarios['upside']=bull
    results={n:simulate(c) for n,c in scenarios.items()}
    params={'low':(.11,.099,.015,.10),'high':(.10,.092,.02,.12)}
    vals={n:{ep:valuation(res,*p) for ep,p in params.items()} for n,res in results.items()}
    vals['structural']={ep:valuation(results['structural'],p[0],p[1],.005,.08) for ep,p in params.items()}
    independent={ep:independent_recompute(results['base'],v) for ep,v in vals['base'].items()}
    # 真正延迟本金宣派到账支付，不只改折现倍数；3/5年延期仍保留未派本金。
    delayed={str(y):{ep:valuation(results['base'],*p,release_years=3,blocked_years=y) for ep,p in params.items()} for y in [3,5]}
    upstream={}
    for y in [3,5]:
        c=copy.deepcopy(BASE);c['upstream_delay']=y;res=simulate(c)
        upstream[str(y)]={'simulation':res,'values':{ep:valuation(res,*p) for ep,p in params.items()}}
    out={'units':'亿元; shares亿股; CNY per share','shares':SHARES,'opening':{'nonlease_debt':DEBT,'unrestricted_cash':FREE_CASH,'restricted':RESTRICTED,'securities':SECURITIES,'investments':INVESTMENT,'minority':MINORITY,'entity_cash':CASH0,'capital_payables':22.64941641},
        'assumptions':BASE,'scenarios':results,'valuations':vals,'financial_principal_delays':delayed,'upstream_delays':upstream,'tests':tests(),'independent_recomputation':independent,
        'return_model':{'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':'2026-10-26T08:00:00+00:00','base_case_distributions_per_share':[round(r['dps'],8) for r in results['base']['rows']],
          'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':round(vals['base']['low']['terminal_equity_per_share'],6),'high':round(vals['base']['high']['terminal_equity_per_share'],6)}}}}
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'base':[{'y':x['year'],'ebit':x['ebit'],'np':x['net_profit'],'cf':x['cash_generated'],'dps':x['dps'],'cash':x['total_cash'],'debt':x['total_debt']} for x in results['base']['rows']], 'values':{n:{p:(v.get('value_per_share'),v.get('terminal_equity_per_share')) for p,v in vs.items()} for n,vs in vals.items()}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()

"""伟明环保：分部运营、资本、项目融资、少数和母现金。标准库、无网络。"""
from pathlib import Path
import json
from copy import deepcopy
P=Path(__file__).parent
S=20.32406318
D=[.30,.30,.40,.45,.50]
JULY_COUPON=14.7662*.015
START_CASH=18.133-JULY_COUPON
DEBT_JUNE=(748129549.25+849900534.98+4319273896.15+1516452898.46+11813413.60+620267454.06)/1e8
DEBT_START=DEBT_JUNE-.209362735
DEBT_FINAL=DEBT_START-15.1645289846+12

def pv(xs,k): return sum(c/(1+k)**t for t,c in enumerate(xs,1))
def operating(rev,margin,overhead,da,tax,maintenance,growth,wc):
    ebit=rev*margin-overhead
    nopat=ebit-max(ebit,0)*tax
    return dict(revenue=rev,ebit=ebit,nopat=nopat,da=da,maintenance=maintenance,growth=growth,wc=wc,fcff=nopat+da-maintenance-growth-wc)

def overseas(kwh=300,util=.90,cost=170,k=.12):
    # 3,000吨/日，0.2美元/度，项目总投24.14亿元，债70%，资本30%。
    cap=24.14;loan=cap*.7;equity=cap*.3; a=equity*.3
    rows=[]
    for t in range(1,31):
        tons=3000*365*util
        revenue=tons*kwh*.2*(24.14/3.5)/1e8
        cashcost=tons*cost/1e8+.15
        interest=loan*.045
        principal=cap*.7/15 if t<=15 else 0
        tax=max(0,revenue-cashcost-cap/30-interest)*.22
        cash=revenue-cashcost-tax-.35-interest-principal
        # 现金不足按普通股经济比例追加；A优先权是已宣派时优先，未捏造无限保证。
        a_distribution=min(max(cash,0),max(a*.05,max(cash,0)*.3))
        common=(cash-a_distribution)*.79 if cash>=0 else cash*.553
        rows.append(dict(year=t,revenue=revenue,interest=interest,principal=principal,project_cash=cash,a_dividend=a_distribution,common_cash=common))
        loan=max(0,loan-principal)
    assert abs(loan)<1e-8
    # Y3开始运营；Y5是运营第3年末，此后尚余27年。
    tv=pv([r['common_cash'] for r in rows[3:]],k)
    return dict(capital=equity*.553,rows=rows,tv5=tv,post_construction_value=pv([r['common_cash'] for r in rows],k),net_npv_at_t0=-equity*.553/2/(1+k)-equity*.553/2/(1+k)**2+pv([0,0]+[r['common_cash'] for r in rows],k))

OV=overseas()
rows=[]; cash=START_CASH; parent=1.344-JULY_COUPON; minority=19.8118415765
for i in range(5):
    electric_volume=39.5+.8*i
    electric_price=.55-.006*i
    disposal_ten_thousand_tons=1400+25*i
    disposal_fee=85
    other_revenue=[3.175,3.2,3.25,3.3,3.35][i]
    domrev=electric_volume*electric_price+disposal_ten_thousand_tons*disposal_fee/10000+other_revenue
    # 毛利推导：成本=现金生产成本+特许摊销；现金成本含人工及环保处置。
    dc=[8.2,8.5,8.8,9.1,9.4][i];da=6.0
    dom=operating(domrev,1-(dc+da)/domrev,2.8,da,.20,2.6+.1*i,[4,3,2,1.5,1.5][i],[.8,.6,.4,.3,.3][i])
    eq=operating([16,17,18,19,20][i],[.32,.32,.32,.32,.32][i],1.4,.3,.20,.3,[.6,.5,.4,.4,.4][i],[.7,.4,.3,.3,.3][i])
    mat=operating([12,15,18,20,21][i],[.06,.08,.10,.11,.12][i],.65,1.2,.22,.8,[2,1,.5,.3,.3][i],[.7,.6,.6,.4,.2][i])
    # 少数损益基于H1年化1.166亿元，随材料税后经营利润变化；子公司付息已在集团税盾后利息列。
    mprofit=1.166+.37*max(0,mat['nopat']-.1)
    mdiv=mprofit*.30
    minority+=mprofit-mdiv
    netinterest=[2.3+14.7662*.018*.8,2.3,2.6,2.6,2.6][i] #现金利息约3.1亿元减税盾，含资本化利息。
    financial=cash*.015
    jvdiv=[0,0,.2,.3,.4][i]
    ovcontrib=OV['capital']/2 if i<2 else 0
    ovcash=OV['rows'][i-2]['common_cash'] if i>=2 else 0
    fcff=dom['fcff']+eq['fcff']+mat['fcff']
    fcfe=fcff-netinterest-mdiv+financial+jvdiv-ovcontrib+ovcash
    payout=D[i]*S
    financing=12-16.243 if i==1 else 0
    begin=cash;cash+=fcfe-payout+financing
    # 子公司上划为主；母本体经营0.2、母层付息0.5，资本支付在母层实际发生。
    upstream=[10.5,10.5,11,11.5,12][i]
    other_net=.2-[.25+14.7662*.018,.25,.5,.5,.5][i]
    parent+=upstream+other_net-ovcontrib-payout+financing
    profit_budget=upstream-.5 #现金上划对应未来正常宣派，非已确认应收股利再确认。
    rows.append(dict(year=i+1,domestic_drivers=dict(electric_volume=electric_volume,electric_price=electric_price,disposal_ten_thousand_tons=disposal_ten_thousand_tons,disposal_fee=disposal_fee,other=other_revenue),domestic=dom,equipment=eq,materials=mat,fcff=fcff,after_tax_interest=netinterest,minority_profit=mprofit,minority_distribution=mdiv,minority_equity=minority,financial_income=financial,jv_distribution=jvdiv,overseas_contribution=ovcontrib,overseas_distribution=ovcash,fcfe=fcfe,common_distribution=payout,finance_net=financing,financial_pool=cash,parent_upstream=upstream,parent_cash=parent,parent_profit=profit_budget))
    assert abs(cash-(begin+fcfe-payout+financing))<1e-10
    assert cash>=parent>=0

def terminal(side,domcash_factor=1,life_delta=0,minority_factor=1):
    if side=='low':
        revenue,production,overhead,tax,maint=41*.513+1500*85/10000+3.2,10,3,.20,3.5
        rate,life,decay=.085,15,.01
        equipment=operating(17,.30,1.4,.3,.20,.3,.3,.1)
        material=operating(21,.10,.65,1.2,.22,1.2,.4,.1)
        ek,mk,ok=.103,.123,.13
        ov=overseas(280,.85,180,ok)
        jv=8.132*.85
    else:
        revenue,production,overhead,tax,maint=43.5*.53+1550*85/10000+3.27,9.5,2.9,.18,3
        rate,life,decay=.073,18,.005
        equipment=operating(19,.32,1.4,.3,.20,.3,.3,.1)
        material=operating(23,.13,.65,1.2,.22,1.2,.4,.1)
        ek,mk,ok=.09,.11,.115
        ov=overseas(320,.90,160,ok)
        jv=8.132*1.15
    life+=life_delta
    dom=operating(revenue,1-(production+6)/revenue,overhead,6,tax,maint,0,.3)
    dcf=[dom['fcff']*domcash_factor*(1-decay)**t for t in range(life)]
    dv=pv(dcf,rate)
    ev=equipment['fcff']/ek
    mv=material['fcff']/mk
    # 联营无新增出资，无未兑现股利年金化；用净资产范围代表收益/回收约束，扣已取出股利。
    jv_value=jv-sum(r['jv_distribution'] for r in rows)
    debt=DEBT_FINAL
    minority_value=rows[-1]['minority_equity']*minority_factor
    equity=dv+ev+mv+ov['tv5']+cash+jv_value-debt-minority_value
    k=.112 if side=='low' else .098
    tv=equity/S
    value=pv(D,k)+tv/(1+k)**5
    return dict(domestic_cash=dom['fcff'],domestic_cashflows=dcf,domestic_rate=rate,domestic_value=dv,equipment_cash=equipment['fcff'],equipment_value=ev,materials_cash=material['fcff'],materials_value=mv,overseas_value=ov['tv5'],jv_value=jv_value,financial_pool=cash,debt=debt,minority_value=minority_value,equity=equity,tv5=tv,equity_rate=k,value=value,terminal_share=(tv/(1+k)**5)/value)
ends={s:terminal(s) for s in ['low','high']}
sens={s:dict(domestic_cash_minus20=terminal(s,.8)['value'],life_minus3=terminal(s,life_delta=-3)['value'],minority_plus20=terminal(s,minority_factor=1.2)['value']) for s in ends}
parentstress=[]
for i,r in enumerate(rows): parentstress.append(r['parent_cash']-.1*sum(x['parent_upstream'] for x in rows[:i+1]))
# 辅助：当前正常化分部资产价值；独立现值时点，扣未完成的产能资本，项目投入与收益相配。
aux={}
for label in ['low','high']:
    t=ends[label];k=t['equity_rate'];dr=t['domestic_rate']
    years=20 if label=='low' else 23
    decay=.01 if label=='low' else .005
    dc=[t['domestic_cash']*(1-decay)**i for i in range(years)]
    domestic=pv(dc,dr)
    growth=[r['domestic']['growth']+r['equipment']['growth']+r['materials']['growth'] for r in rows]
    growth_pv=pv(growth,dr)
    ov=overseas(280,.85,180,.13) if label=='low' else overseas(320,.9,160,.115)
    jv=8.132*(.85 if label=='low' else 1.15)
    equity=domestic+t['equipment_value']+t['materials_value']+ov['net_npv_at_t0']+jv+START_CASH-DEBT_START-19.8118415765-growth_pv
    aux[label]=dict(domestic=domestic,equipment=t['equipment_value'],materials=t['materials_value'],overseas_net=ov['net_npv_at_t0'],jv=jv,cash=START_CASH,debt=DEBT_START,minority=19.8118415765,growth_capex_pv=growth_pv,value=equity/S)
# 特例与守恒：1期PV、零现金、母分配不高于集团资金、项目还本、存量少数+留存。
assert pv([11],.1)==10
assert pv([0,0],.1)==0
assert abs(minority-(19.8118415765+sum(r['minority_profit']-r['minority_distribution'] for r in rows)))<1e-9
assert abs(cash-(START_CASH+sum(r['fcfe']-r['common_distribution']+r['finance_net'] for r in rows)))<1e-9
recipes=[]
for s,t in ends.items():
    recipes.append(dict(label=s+'国内核心经营端点',type='pv',cashflows=[dict(t=i,amount=v) for i,v in enumerate(t['domestic_cashflows'],1)],terminal=dict(t=len(t['domestic_cashflows']),amount=0),rate=t['domestic_rate'],net_adjustment=0,shares=1,expected_per_share=t['domestic_value']))
    recipes.append(dict(label=s+'普通股端点',type='pv',cashflows=[dict(t=i,amount=v) for i,v in enumerate(D,1)],terminal=dict(t=5,amount=t['tv5']),rate=t['equity_rate'],net_adjustment=0,shares=1,expected_per_share=t['value']))
    st=terminal(s,.8)
    recipes.append(dict(label=s+'国内现金降20%敏感性',type='pv',cashflows=[dict(t=i,amount=v) for i,v in enumerate(D,1)],terminal=dict(t=5,amount=st['tv5']),rate=t['equity_rate'],net_adjustment=0,shares=1,expected_per_share=st['value']))
out=dict(debt_bridge=dict(june=DEBT_JUNE,paid_coupon=JULY_COUPON,start_cash=START_CASH,start_debt=DEBT_START,final_debt=DEBT_FINAL),units='亿元、亿股；每股人民币元',shares=S,distributions=D,annual=rows,overseas=OV,terminal=ends,sensitivities=sens,parent_upstream_minus10_cash=parentstress,auxiliary=aux,recipes=recipes)
(P/'2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(terminal=ends,annual_summary=[{k:r[k] for k in ['year','fcff','fcfe','financial_pool','parent_cash','minority_equity']} for r in rows],sensitivity=sens,parent_stress=parentstress,overseas_tv=OV['tv5']),ensure_ascii=False,indent=2))

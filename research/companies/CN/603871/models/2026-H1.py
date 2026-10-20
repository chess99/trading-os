"""嘉友国际2026-H1；单位亿元/亿股，标准库，无网络。"""
import json
from pathlib import Path
S=13.68008658
D=[.38,.38,.40,.42,.45]
OPEN=19.1773-.0998-.1805-1.5118
OTHER=1.5+.2103+.1605+.0096
DEBT=4.6421+.2333

def pv(c,r): return sum(v/(1+r)**(i+1) for i,v in enumerate(c))
def ann(r,n): return pv([1]*n,r)
PARAM={
 'low':dict(core=7.5,port=2.7,new=3.2,cap=23,r=.12,g=.01),
 'base':dict(core=7.75,port=2.8,new=3.4,cap=22,r=.115,g=.0125),
 'high':dict(core=8,port=2.9,new=3.6,cap=21,r=.11,g=.015),
}
def calc(p, dividends=D):
    r=p['r']; cash=OPEN; rows=[]
    caps=[p['cap']*v/22 for v in [6,6,5,3,2]]
    ramp=[0,.3,.8,1.8,2.8]
    for i in range(5):
        year=i+1; mature=p['core']*1.02**year
        associate=.55
        new=ramp[i]*p['new']/3.4
        op=mature+associate+p['port']+new-.35
        div=dividends[i]*S
        principal=(DEBT+1.3) if year==5 else 0
        obligations=OTHER if year==1 else 0
        before=cash; cash+=op-caps[i]-div-principal-obligations
        rows.append(dict(year=year,opening_cash=before,mature_cash=mature,associate_cash=associate,port_cash=p['port'],new_cash=new,interest=.35,operating_after_interest=op,capex=caps[i],dividend=div,principal=principal,other=obligations,closing_cash=cash))
        assert abs(cash-(before+op-caps[i]-div-principal-obligations))<1e-9
        assert cash>=8, '不能覆盖8亿元经营储备'
    # 第五年清偿全部有息本金，终值按无债经营现金计价，避免利息与本金双扣。
    terminal_core=rows[-1]['mature_cash']*(1+p['g'])/(r-p['g'])
    terminal_associate=.55*ann(r,7)
    terminal_old_port=p['port']*ann(r,13)
    terminal_new=p['new']*ann(r,15)
    terminal_excess=cash-8
    terminal=terminal_core+terminal_associate+terminal_old_port+terminal_new+terminal_excess
    value=(pv([z['dividend'] for z in rows],r)+terminal/(1+r)**5)/S
    # 方法二：成熟业务10.5/11/11.5倍现金，港口及新建项目采用有限期现金，扣完整投入。
    mult=10.5 if p['r']==.12 else (11.5 if p['r']==.11 else 11)
    oldpv=p['port']*ann(r,18)
    newpv=pv([z['new_cash'] for z in rows],r)+terminal_new/(1+r)**5
    financial=OPEN-8-OTHER/(1+r)-pv([.35]*5,r)-(DEBT+1.3)/(1+r)**5
    m2=(p['core']*mult+.55*ann(r,12)+oldpv+newpv-pv(caps,r)+financial)/S
    return dict(parameters=p,rows=rows,terminal=dict(core=terminal_core,associate=terminal_associate,old_port=terminal_old_port,new_projects=terminal_new,excess_cash=terminal_excess,total=terminal,per_share=terminal/S),value=value,terminal_pv_share=(terminal/(1+r)**5)/(value*S),method2=m2,method2_components=dict(mature=p['core']*mult,associate=.55*ann(r,12),old_port=oldpv,new_project_cash=newpv,capex_pv=pv(caps,r),financial=financial))

out={k:calc(v) for k,v in PARAM.items()}
b=out['base']; sensitivities={}
for name,mods in [('new_project_cash_zero',{'new':0}),('new_project_cash_half',{'new':1.7}),('extra_capex_6',{'cap':28}),('port_90_to_80',{'port':2.8*8/9}),('trade_margin_down_4ppt',{'core':7.75-48*.04*.82}),('logistics_margin_down_3ppt',{'core':7.75-28*.03*.82})]:
    try:
        v=calc({**PARAM['base'],**mods}); sensitivities[name]={'value':v['value'],'delta':v['value']-b['value'],'min_cash':min(x['closing_cash'] for x in v['rows'])}
    except AssertionError:
        # 压力时不伪造融资：允许降低分配以守住储备，另明确原分配预算失败。
        v=calc({**PARAM['base'],**mods},[.25]*5); sensitivities[name]={'value':v['value'],'delta':v['value']-b['value'],'distribution_reduced_to':.25,'min_cash':min(x['closing_cash'] for x in v['rows'])}
# 母公司支付层：内部流转不是集团新增现金。
parent_cash=6.8016341944; retained=4.419577389
parent=[]
for i,d in enumerate(D):
    receivable=2.262100961 if i==0 else 0
    new_sub_declared=3.5; new_assoc=.5; own_profit=2.5; reserve=.25
    upstream=[2,2,1,0,0][i]
    profit_add=own_profit+new_sub_declared+new_assoc-reserve
    retained+=profit_add-d*S
    assoc_cash=.55-.262100961 if i==0 else new_assoc
    parent_cash+=2.3+new_sub_declared+assoc_cash+receivable-upstream-d*S-(4.4646350251 if i==4 else 0)
    parent.append({'year':i+1,'new_sub_declared_and_received':3.5,'new_associate_declared':.5,'new_associate_received':assoc_cash,'old_receivable_received':receivable,'own_after_tax_profit':own_profit,'own_operating_cash':2.3,'statutory_reserve':reserve,'additional_outbound_funding':upstream,'dividend':d*S,'ending_retained_profit':retained,'ending_cash':parent_cash})
    assert retained>=0 and parent_cash>=1.5
assert pv([1,1],0)==2
assert abs(ann(.1,1)-1/1.1)<1e-10
assert abs(OPEN-(19.1773-.0998-.1805-1.5118))<1e-10
# 经济所有权与金融本金：逐项清偿，不把期末净资产当第二份价值。
structural=calc(dict(core=4.8,port=1.8,new=1.7,cap=28,r=.14,g=0),[0]*5)
result={'structural':structural,'shares':S,'distributions_per_share':D,'opening_common_cash':OPEN,'opening_operating_reserve':8,'cases':out,'sensitivities':sensitivities,'parent_budget':parent,'parent_delay_test':{'two_billion_receivable_delay_year1_cash':parent[0]['ending_cash']-2,'one_year_3_5_subsidiary_receipt_delay_year1_cash':parent[0]['ending_cash']-3.5,'additional_net_payment_2_year1_cash':parent[0]['ending_cash']-2},'project_total_commitment_CNY_at_7':(185011444.72+62150000+68516310+50991220)*7/1e8,'associate_half_cash_value_delta':(.275*5+.275*ann(.115,7))/(1.115**5)/S,'preferred_3_to_6pct_five_year_pv_per_share':1.3*.03*ann(.115,5)/S}
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:{'value':v['value'],'method2':v['method2'],'terminal':v['terminal']['per_share'],'min_cash':min(x['closing_cash'] for x in v['rows'])} for k,v in out.items()},ensure_ascii=False,indent=2))
print(json.dumps({'sensitivities':sensitivities,'parent':parent,'delay':result['parent_delay_test']},ensure_ascii=False,indent=2))

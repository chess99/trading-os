import json
from pathlib import Path
S=8.24808488
ELIG=S-.02249766
D=[.50,.55,.60,.65,.72]
START=22.4108-9.2609-3-1.0080-.2027
PSTART=7.7369

def run(gm_shift=0,wc=.30,cap_mult=1,first_scale=1,growth_shift=0,extra=0):
    cash,pcash,re=START,PSTART,54.9512
    rev,prev=130*first_scale,122.10
    rows=[]
    for i,g in enumerate([0,.08,.07,.06,.05]):
        if i:rev*=1+g+growth_shift
        shift=gm_shift[i] if isinstance(gm_shift,list) else gm_shift
        gm=27.21/130+shift
        op=rev*(gm-.08)*.85
        pop=rev*.99*(.204+shift-.08)*.85
        maintenance=3+.2*i
        growth=[7,7,6,4,4][i]*cap_mult+(extra if i==0 else 0)
        dwc=(rev-prev)*wc
        reserve=(rev-prev)*.02
        fcf=op-growth-dwc-reserve
        pfcf=pop-growth-(dwc+reserve)*.99
        interest=max(cash,0)*.012
        pinter=max(pcash,0)*.012
        bridge_interest=.10 if i==0 else 0
        div=D[i]*ELIG
        old,oldp=cash,pcash
        cash+=fcf+interest-bridge_interest-div
        pcash+=pfcf+pinter-bridge_interest-div
        re+=pop+pinter-bridge_interest-div
        assert abs(cash-old-(fcf+interest-bridge_interest-div))<1e-9
        assert abs(pcash-oldp-(pfcf+pinter-bridge_interest-div))<1e-9
        rows.append(dict(year=i+1,revenue=rev,operating_profit=op,parent_operating_profit=pop,maintenance=maintenance,depreciation=maintenance,growth_capital=growth,total_capital=maintenance+growth,incremental_wc=dwc,incremental_operating_reserve=reserve,fcf=fcf,dividend_total=div,cash_interest=interest,cash_end=cash,parent_cash_end=pcash,parent_retained_earnings=re))
        prev=rev
    tv=[(rows[-1]['operating_profit']*m+cash)/S for m in [14,20]]
    pv=[sum(d/1.09**t for t,d in enumerate(D,1))+v/1.09**5 for v in tv]
    return dict(rows=rows,terminal=tv,pv=pv,min_group_cash=min(x['cash_end'] for x in rows),min_parent_cash=min(x['parent_cash_end'] for x in rows),executable=min(x['cash_end'] for x in rows)>=0 and min(x['parent_cash_end'] for x in rows)>=0)
base=run()
# 独立常识特例：零增长、无再投资、期初无现金时，永续分配的资本化值等于利润/资本成本。
assert abs(sum(1/1.1**t for t in range(1,6))+(1/.1)/1.1**5-10)<1e-10
assert len(base['rows'])==5 and base['executable']
assert abs(START-8.9392)<1e-8
# 经营利润不含金融利息；终值仅加分红后的现金；总股数不减未注销库存。
out={'units':'金额亿元，股数亿股，每股元','shares':S,'dividend_eligible_shares':ELIG,'initial_cash':START,'base':base,'cyclical_weak':run(gm_shift=[-.025,-.0125,0,0,0],wc=.40),'margin_minus_1pp':run(gm_shift=-.01),'growth_capital_plus_30pct':run(cap_mult=1.3),'beihai_extra_17':run(extra=17),'structural_weak':run(gm_shift=-.04,wc=.45,cap_mult=1.2,first_scale=.9,growth_shift=-.04),'strong':run(gm_shift=.007,wc=.25,first_scale=1.04,growth_shift=.01),'core_value_range':[round(base['pv'][0],1),round(base['pv'][1],1)],'return_model_distributions':D,'terminal_range':[round(x,1) for x in base['terminal']]}
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k in ['core_value_range','terminal_range']},ensure_ascii=False))

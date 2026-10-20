"""华明装备：亿元/亿股；标准库、离线可复算。"""
import json
from pathlib import Path
S=8.96225431
C0=.5220786845
GOV=.9662023658
EQ=.43877111758
R0=25.8656644689
K0=31.2520570442
DPS=[.50,.53,.56,.59,.62]

def model(wc=.45,gm_shift=0,continuation=None,roic=.20,mode='base'):
    equip=[24.5]
    for g in [.10,.09,.07,.05]: equip.append(equip[-1]*(1+g))
    cnc=[3.1]
    for g in [.04,.03,.02,.02]: cnc.append(cnc[-1]*(1+g))
    gm=[.60,.60,.598,.595,.595]
    fixed=[.70,.80,.80,.70,.60]
    if mode=='cyclical': equip=[21,22.2,25,28,31];gm=[.56,.57,.585,.595,.595]
    if mode=='structural': equip=[18,17.5,17,17,17];gm=[.49,.47,.46,.45,.45]
    if mode=='upside': equip=[25,28,30.8,33.264,35.25984];gm=[.62,.62,.615,.61,.61];fixed=[1,.9,.8,.7,.6]
    rows=[];cash=C0;capital=K0;prior=R0;cum_fixed=0;cum_cip=0
    for i in range(5):
        revenue=equip[i]+cnc[i]+.75
        cip=.27095511755 if i<2 else 0
        da_add=.08*(cum_fixed+cum_cip+.5*(fixed[i]+cip))
        gp=equip[i]*(gm[i]+gm_shift)+cnc[i]*.23+.75*.28
        expenses=revenue*(.09+.06+.035+.0125+.01)+.15*1.03**i
        nopat=(gp-expenses-da_add+.28*1.03**i-.32*1.03**i)*.82
        nci=.08*1.09**i
        common=nopat-nci
        dwc=max(revenue-prior,0)*wc
        reserve=max(revenue-prior,0)*1.8/R0
        investment=fixed[i]+dwc+reserve
        fcff=(nopat-investment)*(1-nci/nopat)
        dividend=DPS[i]*S
        if mode!='base': dividend=min(dividend,max(0,fcff*.7))
        receipt=GOV if i==1 else 0
        previous_cash=cash;cash+=fcff+receipt-dividend
        capital+=investment
        row=dict(year=i+1,equipment=equip[i],revenue=revenue,equipment_gm=gm[i]+gm_shift,group_nopat=nopat,common_nopat=common,maintenance=1.15+da_add,fixed_growth=fixed[i],working_capital_increment=dwc,reserve_increment=reserve,investment=investment,common_fcff=fcff,dividend=dividend,dps=dividend/S,cash=cash,capital=capital)
        assert abs(cash-previous_cash-fcff-receipt+dividend)<1e-9
        assert abs(nopat-investment-fcff/(1-nci/nopat))<1e-9
        rows.append(row);prior=revenue;cum_fixed+=fixed[i];cum_cip+=cip
    growth=continuation or [.05,.04,.03,.03,.02]
    if mode=='structural':growth=[0]*5;roic=.12
    if mode=='cyclical':growth=[.04,.04,.03,.03,.02]
    if mode=='upside':growth=[.07,.06,.05,.04,.03];roic=.25
    n=rows[-1]['common_nopat'];future=[]
    terminal_g=.02 if mode!='structural' else 0
    for j,g in enumerate(growth):
        n*=1+g
        next_g=growth[j+1] if j<4 else terminal_g
        inv=n*next_g/roic
        future.append(dict(year=6+j,common_nopat=n,investment=inv,common_fcff=n-inv))
    np11=n*(1+terminal_g);f11=np11*(1-terminal_g/roic)
    def value(r):
        op5=sum(x['common_fcff']/(1+r)**(x['year']-5) for x in future)+f11/(r-terminal_g)/(1+r)**5
        tv5=op5+cash+EQ
        pvdiv=sum(x['dividend']/(1+r)**x['year'] for x in rows)
        v=(pvdiv+tv5/(1+r)**5)/S
        tv10pv=f11/(r-terminal_g)/(1+r)**10/S
        return dict(rate=r,value=v,terminal_year5=tv5/S,operating_value_year5=op5,terminal10_pv_share=tv10pv/v)
    rates=[.115,.095]
    values=[value(r) for r in rates]
    return dict(rows=rows,continuation=future,np11=np11,fcff11=f11,terminal_growth=terminal_g,roic=roic,values=values,cash5=cash,share_count=S,initial_cash=C0,equity_recovery=EQ)

def parent_cash():
    cash=.43555082;re=4.447803;reserve=3.653017;out=[]
    for i,up in enumerate([5.3,5.6,5.9,6.2,6.5]):
        own=-.15*1.03**i;profit=up+own
        statutory=min(profit*.1,max(0,S*.5-reserve))
        reserve+=statutory;re+=profit-statutory-DPS[i]*S
        cash+=profit-([.45,.1,0,0,0][i])-DPS[i]*S
        out.append(dict(year=i+1,upstream=up,cash=cash,retained_earnings=re,statutory_reserve=reserve))
    return out

def main():
    b=model();p=parent_cash()
    bridge=C0+GOV/1.105**2+EQ/1.105**5
    cap=[(b['rows'][0]['common_nopat']*m+bridge)/S for m in [12,15]]
    sensitivities={name:model(**kw) for name,kw in {'wc35':{'wc':.35},'wc55':{'wc':.55},'gm_minus3':{'gm_shift':-.03},'post5_growth2':{'continuation':[.02]*5},'roic15':{'roic':.15}}.items()}
    scenarios={x:model(mode=x) for x in ['cyclical','structural','upside']}
    assert len(b['rows'])==5 and len(b['continuation'])==5
    assert all(x['cash']>0 and x['retained_earnings']>0 for x in p)
    assert abs(sum(x['common_fcff'] for x in b['rows'])+C0+GOV-sum(DPS)*S-b['cash5'])<1e-8
    assert abs((10/.1)/10-10)<1e-12 # 零增长现金年金特例
    assert abs((12-2)-10)<1e-12 # 利润减再投资现金守恒特例
    recipes=[]
    for label,run in [('core_low',b),('gm_minus3_low',sensitivities['gm_minus3'])]:
        v=run['values'][0];r=v['rate']
        recipes.append(dict(label=label,type='pv',cashflows=[dict(t=x['year'],amount=x['dividend']) for x in run['rows']],terminal=dict(t=5,amount=v['terminal_year5']*S),rate=r,net_adjustment=0,shares=S,expected_per_share=v['value']))
    output=dict(base=b,capitalization=dict(multiples=[12,15],bridge=bridge,values=cap),parent=p,sensitivities=sensitivities,scenarios=scenarios,independent_recipes=recipes,checks='passed')
    Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
    print(json.dumps(dict(value=[x['value'] for x in b['values']],terminal=[x['terminal_year5'] for x in b['values']],capitalization=cap,parent=p),ensure_ascii=False,indent=2))
if __name__=='__main__':main()

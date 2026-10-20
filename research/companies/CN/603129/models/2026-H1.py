"""春风动力；金额亿元，股数亿股。仅标准库，无网络。"""
import json
from pathlib import Path
S=1.64854391
D=[4.5,5,5.5,6,6.5]
P=[20.5,22,23.5,25,27]
DA=[3,3.5,4,4.5,5]
CAP=[18,16,12,9,9]
WC=[8,6,4,3,3]
RESOURCE=123.0840-.9327+1.8345+2.4080

def pv(flows,r):return sum(x/(1+r)**(i+1) for i,x in enumerate(flows))
def case(p5=27,r=.0975,roi=.14,reserve=35,yield_cash=.015,gs=(.07,.06,.05,.04,.03),extra_cap=0,shock=None,converted=True,debt_coupon=.03):
    shares=S if converted else (153482763+2357300)/1e8
    debt=0 if converted else 21.78763
    c=RESOURCE-reserve; rows=[]
    for i in range(5):
        p=P[i]*p5/27-(shock[i] if shock else 0)
        fin=c*yield_cash
        cap=CAP[i]+(extra_cap if i==0 else 0)
        f=p+DA[i]-cap-WC[i]-debt*debt_coupon
        end=c+fin+f-D[i]*shares
        assert abs(end-c-fin-f+D[i]*shares)<1e-9
        rows.append(dict(year=i+1,profit=p,da=DA[i],capex=cap,wc=WC[i],financial_income=fin,fcf=f,distribution=D[i]*shares,cash_open=c,cash_close=end))
        c=end
    p=p5; tail=[]
    for y,g in enumerate(gs,6):
        n=p*(1+g); reinvest=(n-p)/roi; cf=n-reinvest
        assert abs(n-cf-reinvest)<1e-9
        tail.append(dict(year=y,growth=g,profit=n,net_reinvestment=reinvest,fcf=cf));p=n
    g=.03;n=p*(1+g);reinvest=(n-p)/roi;tv10=(n-reinvest)/(r-g)
    op5=pv([x['fcf'] for x in tail],r)+tv10/(1+r)**5
    tv5=(op5+c-debt)/shares
    value=pv(D,r)+tv5/(1+r)**5
    return dict(shares=shares,debt=debt,debt_coupon=debt_coupon if debt else 0,p5=p5,rate=r,incremental_return=roi,reserve=reserve,cash_yield=yield_cash,years=rows,tail=tail,terminal_profit=n,terminal_reinvestment=reinvest,operating_tv10=tv10,operating_value5=op5,implied_multiple5=op5/p5,cash5=c,terminal_per_share=tv5,value_per_share=value,terminal_pv_fraction=tv5/(1+r)**5/value)

def run():
    low=case(26,.105,.12,40);high=case(28,.09,.16,30);base=case()
    out={'unit':'亿元/亿股/元每股','shares':S,'resource':RESOURCE,'distributions':D,'low':low,'base':base,'high':high,
      'sensitivity':{'return10':case(27,.0975,.10,35),'return18':case(27,.0975,.18,35),'no_growth_transition':case(gs=(.03,)*5),'extra_cap20':case(extra_cap=20),'cash_yield_zero':case(yield_cash=0),
      'cyclical':case(shock=[5,3,0,0,0]),'structural':case(20,.11,.09,40,gs=(.01,.01,.02,.02,.03)),'optimistic':case(32,.09,.18,30,gs=(.09,.08,.06,.05,.03))},
      'matched_incremental_return':(27-20.5)/(sum(CAP[1:])-sum(DA[1:])+sum(WC[1:])),
      'maintenance_proxy_incremental_return':(27-20.5)/(sum(CAP[1:])-2.54*4+sum(WC[1:])),
      'no_conversion_low_coupon0':case(26,.105,.12,40,converted=False,debt_coupon=0),
      'no_conversion_low_coupon3':case(26,.105,.12,40,converted=False,debt_coupon=.03),
      'auxiliary_low':pv(D,.105)+((26*11+low['cash5'])/S)/(1.105**5),'auxiliary_high':pv(D,.09)+((28*15+high['cash5'])/S)/(1.09**5)}
    assert pv([1,1],0)==2
    assert abs(pv([10,10],.1)+100/1.1**2-100)<1e-9
    assert len(D)==5 and min(x['cash_close'] for x in low['years'])>0
    assert abs(sum(x['distribution'] for x in base['years'])-sum(D)*S)<1e-9
    assert case(extra_cap=20)['cash5']<base['cash5']
    assert low['value_per_share']<high['value_per_share']
    Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:out[k]['value_per_share'] for k in ['low','base','high']},ensure_ascii=False))
if __name__=='__main__':run()

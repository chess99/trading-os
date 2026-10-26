"""Independent reconstruction from frozen raw parameters, no model import.
Covers every year 1-41, both core endpoints and TV5, margin -2pp,
working capital +5pp; excludes other scenario numeric verification.
"""
import json,pathlib,math
D=pathlib.Path(__file__).resolve().parent

def rebuild(margin_cut=0.,wc_ratio=.32):
    cash=[.4,.22,.17,.15,.16111696734];debt=[1.8,3,1.6,1,2.09499814993]
    retained=[3.87016577999,0,0,0,-.5];reserves=[.3333703975,0,0,0,0];capital=[.681166595,.78,.78,.101,1.5]
    wp=[.18,.32,.18,.22,.1];wk=[.08,.40,.22,.12,.18];ww=[.2,.3,.2,.18,.12]
    rev=32.66683675642;wc=10.564;shares=.681166595;outputs=[]
    def profit(e,amount):
        contribution=max(0,amount+min(0,retained[e]))
        add=min(max(0,capital[e]/2-reserves[e]),contribution/10)
        retained[e]+=amount-add;reserves[e]+=add
    for year in range(1,42):
        old=rev
        if year<6:
            rev=[40,47,53,58,62][year-1];m=[.20,.195,.19,.185,.18][year-1]-margin_cut;capex=[8,6,5,4.8,4.8][year-1]
        else:
            rev*=1+([.07,.06,.05,.04,.03][year-6] if year<11 else .02)
            m=.18-margin_cut+(.15-.18)*min(1,(year-5)/5)
            capex=rev*.055+(rev-old)*.65
        dwc=rev*wc_ratio-wc;wc=rev*wc_ratio;floor=[rev*.035*w for w in ww];income=0
        for e in range(5):
            pretax=rev*m*wp[e]-.04*debt[e]+cash[e]*.015
            tax=max(0,pretax)*.17
            minority=rev*m*.83*.0013 if e==0 else 0
            net=pretax-tax-minority;income+=net
            cash[e]+=net+(rev*.055-capex)*wk[e]-dwc*ww[e]
            profit(e,net)
        if year==3:
            gain=.08418882463-.0304783237
            cash[0]+=.08418882463-.25*gain
            profit(0,gain*.75)
        for e in range(5):
            repay=min(debt[e],max(0,cash[e]-floor[e])*(.25 if year<6 else 1))
            cash[e]-=repay;debt[e]-=repay
        for e,target in [(3,4),(1,0),(2,0),(4,0)]:
            remittance=min(max(0,retained[e]),max(0,cash[e]-floor[e]))
            retained[e]-=remittance;cash[e]-=remittance;cash[target]+=remittance;profit(target,remittance)
        for e in [1,2,3,4]:
            injection=max(0,floor[e]-cash[e]);cash[0]-=injection;cash[e]+=injection;capital[e]+=injection
            if e==3:capital[4]+=injection
        target=income*.30 if year<6 else max(0,cash[0]-floor[0])
        credit=min(max(0,18-sum(debt)),max(0,floor[0]+min(max(0,target),max(0,retained[0]))-cash[0]));debt[0]+=credit;cash[0]+=credit
        assert cash[0]+1e-8>=floor[0]
        requested=income*.30 if year<6 else max(0,cash[0]-floor[0])
        payout=min(max(0,requested),max(0,retained[0]),max(0,cash[0]-floor[0]))
        cash[0]-=payout;retained[0]-=payout
        outputs.append({'year':year,'revenue':rev,'net_profit':income,'total_cash':sum(cash),'total_debt':sum(debt),'distribution_per_share':payout/shares,'entity_cash':cash[:],'entity_debt':debt[:],'entity_retained':retained[:]})
    values={}
    for name,rate in [('low',.105),('high',.09)]:
        div=[x['distribution_per_share'] for x in outputs]
        tail=div[40]/(rate-.02)
        # Full reconstruction, not a sum of official output amounts.
        current=sum(div[t-1]/(1+rate)**t for t in range(1,41))+tail/(1+rate)**40
        tv5=sum(div[t-1]/(1+rate)**(t-5) for t in range(6,41))+tail/(1+rate)**35
        values[name]={'value_per_share':current,'terminal_year5_per_share':tv5}
    return {'years':outputs,'values':values}


import pytest, runpy
ROOT=pathlib.Path(__file__).resolve().parents[1]/'research/companies/CN/002916/models'
@pytest.mark.parametrize('name,args',[('base',{}),('margin_minus_2pp_from_year1',{'margin_cut':.02}),('wc_plus_5pp_from_year1',{'wc_ratio':.37})])
def test_shennan_independent_raw_chain(name,args):
 reference=json.loads((ROOT/'2026-Q3-output.json').read_text());calc=rebuild(**args)
 for a,b in zip(calc['years'],reference['scenarios'][name]['years']):
  for k in ['revenue','net_profit','total_cash','total_debt','distribution_per_share']:assert a[k]==pytest.approx(b[k],abs=1e-8)
  for i in range(5):
   for x,y in [('entity_cash','closing_cash'),('entity_debt','closing_debt'),('entity_retained','closing_legal_retained')]:assert a[x][i]==pytest.approx(b['entities'][i][y],abs=1e-8)
 for edge in ['low','high']:
  for metric in ['value_per_share','terminal_year5_per_share']:assert calc['values'][edge][metric]==pytest.approx(reference['valuations'][name][edge][metric],abs=1e-8)

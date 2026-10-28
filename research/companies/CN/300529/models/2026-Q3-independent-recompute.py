"""Independent Decimal literal calculation: no production import or inputs read. Output compared only after calculation."""
from decimal import Decimal as D,getcontext
from pathlib import Path
import json
getcontext().prec=40
P=Path(__file__).resolve().parent

def calc(low=False,sales='.20',acquire=True):
 z=D(0);pc=D('22.9691089761');sc=D('28.3407847082')-pc;pl=D('25.4579677382');pr=D('4.03855193');bank=D('2.289288817');prev=D('21.6');capital=D(19);sl=D(-1);sr=D('.1');rows=[];dv=[]
 ks=['3.6','4','4.4','4.8','5.2'] if low else ['4','4.7','5.4','6.1','6.8'];ls=['13.7','13.8','14','14.2','14.4'] if low else ['14.5','15','15.5','16','16.5'];os=['3.2','3.5','3.8','4','4.2'] if low else ['3.5','3.8','4.1','4.4','4.7']
 tax=D('.83') if low else D('.84');discount=D('1.105') if low else D('1.1')
 for i,(k,l,o,cx,da) in enumerate(zip(ks,ls,os,['2.5','2.1','1.8','1.9','2'],['1.45','1.5','1.55','1.6','1.65'])):
  k,l,o,cx,da=map(D,(k,l,o,cx,da));rev=k+l+o;gp=k*D('.74' if low else '.76')+l*D('.81' if low else '.82')+o*D('.50' if low else '.52');ebit=gp-rev*(D(sales)+D('.19'));n=ebit*tax;pn=n*D('1.05');sn=-n*D('.05');wc=(rev-prev)*D('.12')
  interest=bank*D('.035')*tax;rep=min(bank,D('.45') if i==0 else D('.5'));bank-=rep;pi=pc*D('.015');si=sc*D('.015');bond=D('10.9981212') if i==0 else z;acq=D('.17592') if i==0 and acquire else z;mi=z if acquire else D('.02')
  pb=pc+pn+pi+D('.9')*(da-cx-wc)-D('.15')*(interest+rep)-bond-acq;sb=sc+sn+si+D('.1')*(da-cx-wc)-D('.85')*(interest+rep)-mi
  inj=max(z,D('.5')-sb)+(D('.0828') if i==0 and acquire else z);pb-=inj;sb+=inj;lp=pn+pi-interest*D('.15')-(D('.3') if i==0 else z)
  add=min(max(z,D('7.98605275')/2-pr),max(z,lp+min(z,pl))/10);paid=min(max(z,(n+pi+si-interest-mi)*D('.6')),max(z,pl+lp-add),max(z,pb-2));pl+=lp-add-paid;pr+=add
  sp=sn+si-interest*D('.85')-mi;sa=min(max(z,D('1.5')-sr),max(z,sp+min(z,sl))/10);sl+=sp-sa;sr+=sa
  pc=pb-paid;sc=sb;prev=rev;capital+=cx-da+wc;dv.append(paid)
  rows.append({k:float(v) for k,v in dict(revenue=rev,gross_profit=gp,ebit=ebit,nopat=n,mother_nopat=pn,subsidiary_nopat=sn,depreciation=da,capex=cx,working_capital_increase=wc,bank_interest=interest,bank_repayment=rep,bank_end=bank,bond_redemption=bond,financial_income=pi+si,acquisition=acq,minority_cash=mi,injection=inj,upstream=z,mother_legal_profit=lp,mother_retained=pl,mother_reserve=pr,reserve_addition=add,subsidiary_retained=sl,mother_cash=pc,subsidiary_cash=sc,group_cash=pc+sc,distribution=paid,distribution_per_share=paid/D('7.74362581'),operating_capital=capital).items()})
 tail=z;tailrows=[]
 for j in range(5):
  start=D('.025') if low else D('.04');gr=start+(D('.02')-start)*D(j)/4;prior=n;n*=1+gr;ri=max(z,n-prior)/D('.16' if low else '.18');fcf=n-ri;tail+=fcf/discount**(j+1);tailrows.append(dict(nopat=float(n),reinvestment=float(ri),fcf=float(fcf)))
 stable=n*D('1.02');perp=stable*(1-D('.02')/D('.16' if low else '.18'))/(discount-1-D('.02'))/discount**5;tail+=perp;minority=z if acquire else D('.02')/(discount-1);netcash=pc+sc-D('2.5')-bank;tv=tail+netcash+D('1.3066241057')-minority;dpv=sum(v/discount**(i+1) for i,v in enumerate(dv));value=(dpv+tv/discount**5)/D('7.74362581')
 apv=dv[0]/discount+dv[1]/discount**2;bridge=D(str(rows[1]['group_cash']))-D('2.5')-D(str(rows[1]['bank_end']))+D('1.3066241057')-minority;aux=[(apv+(D(str(rows[2]['nopat']))*m+bridge)/discount**2)/D('7.74362581') for m in (14,18)]
 return dict(years=rows,tail_years=tailrows,current_value=float(value),terminal_year5_per_share=float(tv/D('7.74362581')),terminal_operation=float(tail),terminal_net_cash=float(netcash),terminal_minority=float(minority),terminal_total_pv_fraction=float(tv/discount**5/(dpv+tv/discount**5)),auxiliary_value_range=list(map(float,aux)))
results={}
for name,low,sale,acq in [('core_low',True,'.21',True),('base',False,'.20',True),('sell_plus_2pp',False,'.22',True),('no_acquisition',False,'.20',False)]:
 results[name]=calc(low,sale,acq)
actual=json.loads((P/'2026-Q3-output.json').read_text());checks={}
for name,ind in results.items():
 pro=actual['cases'].get(name,actual['diagnostics'].get(name));errors=[]
 for seq in ['years','tail_years']:
  assert len(ind[seq])==len(pro[seq])
  for i,row in enumerate(ind[seq]):
   for key,v in row.items():errors.append(abs(v-pro[seq][i][key]))
 for key in ['current_value','terminal_year5_per_share','terminal_operation','terminal_net_cash','terminal_minority','terminal_total_pv_fraction']:errors.append(abs(ind[key]-pro[key]))
 errors.extend(abs(a-b) for a,b in zip(ind['auxiliary_value_range'],pro['auxiliary_value_range']));assert max(errors)<1e-8,(name,max(errors));checks[name]={'max_absolute_error':max(errors),'independent_full_chain':ind}
print(json.dumps(checks,sort_keys=True,ensure_ascii=False,indent=2))

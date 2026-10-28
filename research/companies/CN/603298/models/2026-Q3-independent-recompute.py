#!/usr/bin/env python3
# Literal-input reconstruction. Production only loaded AFTER independent calculations.
import json
from pathlib import Path

def independently_build(rate,terminal_return,margin_cut=0,convert_price=0):
 stock=13.09812049;sales=195.;growth=(.08,.08,.07,.06,.05,.05,.04,.04,.03,.03);margins=(.105,.107,.109,.110,.110,.109,.108,.107,.106,.105)
 cash=23.1382402887;debt=11.0611623667;associate_funds=0.;book=127.2457586051;assoc_book=32.5847711792;operating_capital=book-assoc_book-cash+debt;assoc_necessary=assoc_book
 parent=17.;retained=75.5688992677;reserve=6.549060245;registered=13.09812049;premium=17.6109299678;earmarked=0.;divs=[];trace=[]
 for index in range(10):
  year=index+1;sales*=1+growth[index];before_rd=sales*(margins[index]-margin_cut);weight=(.4,.4,.2,0,0,0,0,0,0,0)[index];rd=2.3218*weight;earnings=before_rd-rd;plant=16.527918*weight;wc=5.700282*weight;normal=.03*sales;free=earnings-normal-plant-wc
  associate=4.2*1.03**index;previous=4.2*1.03**(index-1);investment=(associate-previous)/.12;associate_interest=associate_funds*.01;upstream=(.2,.3,.5,.8,1.2)[index] if index<5 else associate*.4
  associate_funds+=associate+associate_interest-investment-upstream;assoc_necessary+=investment;assoc_book+=associate+associate_interest-upstream
  borrowing=22.59 if year==1 else 0;payment=22.59 if year==6 and not convert_price else 0;fees=.2 if year==1 else 0;converted=22.59 if year==3 and convert_price else 0
  if converted:
   added=converted/convert_price;stock+=added;registered+=added;premium+=converted-added
  interest=.025*(debt+borrowing-converted);bond_interest=.025*max(0,debt+borrowing-converted-11.0611623667);earmarked=max(0,earmarked+borrowing-22.59*weight);cash_interest=.01*cash
  dividend=stock*(.65,.70,.75,.80,.85)[index] if index<5 else .45*(earnings+associate)
  own_cash=.75*before_rd-.002*sales-rd;own_capex=.012*sales+plant;subdiv=min(.25*.25*before_rd,max(0,free-(own_cash-own_capex-wc)));parent_interest=4.973078389*.025+bond_interest
  parent_before=parent+own_cash-own_capex-wc+subdiv+upstream+borrowing-payment-fees-parent_interest
  parent_profit=.75*before_rd-rd+subdiv+(associate+associate_interest)*(263187909.88/263212746.76)-parent_interest-fees
  allocation=.1*max(0,parent_profit+min(0,retained)) if reserve<.5*registered else 0;legal=retained+parent_profit-allocation;reserve+=allocation
  group_before=cash+free+upstream+cash_interest-interest+borrowing-payment-fees;sinking=22.59*year/6 if year<6 and not convert_price else 0
  dividend=max(0,min(dividend,group_before-sinking-earmarked,parent_before-8-sinking-earmarked,legal));retained=legal-dividend;parent=parent_before-dividend
  cash=group_before-dividend;debt+=borrowing-payment-converted;book+=earnings+associate+associate_interest+cash_interest-interest-fees-dividend+converted;operating_capital+=normal+plant+wc
  assert abs(book-operating_capital-assoc_book-cash+debt)<1e-7
  divs.append(dividend/stock);trace.append(dict(year=year,cash=cash,debt=debt,book=book,dividend=dividend,parent_cash=parent,retained=retained,statutory=reserve,registered=registered,premium=premium,earmarked=earmarked))
 q=1/(1+rate);n=10;annuity=q*(1-q**n)/(1-q);weighted=q*(1-(n+1)*q**n+n*q**(n+1))/(1-q)**2
 def financial(principal):return principal*((.1+.011)*annuity-.001*weighted)
 continuing=(before_rd*1.025*(1-.025/terminal_return)+associate*1.025*(1-.025/.12))/(rate-.025)
 ending=(continuing+financial(associate_funds)+financial(cash-debt))/stock
 return dict(current=sum(divs[i]*q**(i+1) for i in range(10))+ending*q**10,year5=sum(divs[i]*q**(i-4) for i in range(5,10))+ending*q**5,trace=trace)
out={}
for label,r,roi,cut in [('core_low',.105,.095,0),('core_high',.095,.115,0),('base',.10,.105,0),('sensitivity_discount_plus_1pct',.11,.105,0),('sensitivity_margin_minus_1pct',.10,.105,.01)]:out[label]=independently_build(r,roi,cut)
out['conversion_30']=independently_build(.10,.105,0,30)
out['method2']={}
for key,r,roi,ar in [('low',.105,.105,.115),('high',.095,.115,.105)]:
 g=.025;manufacturing=21.5*(1-g/roi)/(r-g);associate=4.2*(1-g/.12)/(ar-g)
 cash_pv=sum((12.077077922*.1+12.077077922*(1-(y-1)/10)*.01)/(1+r)**y for y in range(1,11));project=9.82/(1+r)+9.82/(1+r)**2+4.91/(1+r)**3
 out['method2'][key]=(manufacturing/(1+r)**2+associate/(1+ar)**2+cash_pv-project-.2)/13.09812049
# Production is comparison target only, never an independent calculation input.
prod=json.loads(Path(__file__).with_name('2026-Q3-output.json').read_text())
for label,v in out.items():
 if label=='method2':continue
 ref=prod['conversion_sensitivity'][1] if label=='conversion_30' else prod[label]
 assert abs(v['current']-ref['current_value_per_share'])<1e-8
 assert abs(v['year5']-ref['year5_value_per_share'])<1e-8
 for i in range(10):
  for literal,production in [('cash','cash'),('book','common_book'),('dividend','distribution'),('parent_cash','parent_cash_budget'),('retained','parent_legal_reserve_budget'),('statutory','parent_statutory_reserve'),('registered','parent_registered_capital'),('premium','parent_capital_premium'),('earmarked','earmarked_project_cash')]:assert abs(v['trace'][i][literal]-ref['rows'][i][production])<1e-7,(label,i,literal)
for key in ['low','high']:assert abs(out['method2'][key]-prod['method2'][key])<1e-8
out['status']='literal endpoints, dominant parameters, conversion, distribution and conservation passed'
Path(__file__).with_name('independent-rebuild-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(out['status'])

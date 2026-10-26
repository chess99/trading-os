import json
# All financial amounts CNY billion, shares billion. Inputs independent of historical report.
SHARES0=4.65-0.010945162 # existing Q3 cancellation-designated treasury shares; other treasury treated dilutive
BUYBACK=20-3.303 # minimum announced programme, remainder, research assumption executed Year1
BUYBACK_P=300 # execution assumption, not a price trigger
SHARES5=SHARES0-BUYBACK/BUYBACK_P
cash=369.813786; liquid=62.779978; debt=39.897579+16.871100+76.354823+52.737747+4.064886
# reserve 90 includes restricted/term monies, settlement needs and provision liquidity; no forfeiture assumed.
reserve=90; minority_financial=15
derivative_net=0.629346-1.646355
legacy_longpay=1.632147
financial=cash+liquid+derivative_net-debt-reserve-minority_financial-legacy_longpay
other_financial=(13.148849+11.824729)*.8
bridge=financial+other_financial
volumes=[1100,1270,1440,1600,1760]
unit=[.065,.063,.062,.061,.060]
associates_other=[6.5,7,7.5,9,9.5]
profit=[v*u+a for v,u,a in zip(volumes,unit,associates_other)]
reinvestment=[42,44,45,46,47]
dps=[8.5,9.5,10.5,12,13]
fcf=[p-i for p,i in zip(profit,reinvestment)]
for g,roic in zip([.06,.05,.04,.03,.03],[.16,.15,.14,.13,.12]):
 p=profit[-1]*(1+g); profit.append(p); reinvestment.append((p-profit[-2])/roic); fcf.append(p-reinvestment[-1])
# Synthetic attributable operating value: profit excludes net financing income; debt netted once in bridge.
def capacity_dcf(r=.095,g=.025,scale=1.,extra_reinvestment=0):
 f=[x*scale-(extra_reinvestment if i<5 else 0) for i,x in enumerate(fcf)]
 terminal_profit=profit[-1]*scale*(1+g)
 terminal_fcf=terminal_profit*(1-g/.12)
 terminal=terminal_fcf/(r-g)
 op=sum(x/(1+r)**(i+1) for i,x in enumerate(f))+terminal/(1+r)**10
 # Remaining programme paid year1, then remaining shares; approximate annual bucket at t1.
 equity=op+bridge-BUYBACK/(1+r)
 return {'r':r,'g':g,'equity':equity,'per_share':equity/SHARES5,'terminal_pv_share_of_operating':terminal/(1+r)**10/op,'operating':op}
# Holder cash conservation; excess financial assets earn 2% net; separate from operating profit.
financial5=financial
rows=[]
for i in range(5):
 opening=financial5; earnings=opening*.02; bb=BUYBACK if i==0 else 0; dividend=dps[i]*SHARES5
 financial5=opening+earnings+fcf[i]-dividend-bb
 assert abs(financial5-opening-earnings-fcf[i]+dividend+bb)<1e-8
 rows.append(dict(year=i+1,volume=volumes[i],operating_profit=profit[i],reinvestment=reinvestment[i],owner_cash=fcf[i],dividend=dividend,dps=dps[i],opening_financial=opening,financial_income=earnings,buyback=bb,closing_financial=financial5))
def terminal5(r,g):
 # Year5 valuation separately uses years6-10 and post-year10 steady state; distribution already removed in bridge.
 tail=sum(fcf[i]/(1+r)**(i-4) for i in range(5,10))
 tail+=profit[-1]*(1+g)*(1-g/.12)/(r-g)/(1+r)**5
 return (tail+financial5+other_financial)/SHARES5
# Actual allocation path is the adopted current-value path, including low-yield retention.
def dcf(r=.095,g=.025,scale=1.,extra_reinvestment=0,cycle=False,buyback=BUYBACK,shares=SHARES5):
 f=[x*scale-(extra_reinvestment if i<5 else 0) for i,x in enumerate(fcf)]
 if cycle: f[0]-=20; f[1]-=15
 fin=financial
 for i in range(5): fin=fin*1.02+f[i]-dps[i]*shares-(buyback if i==0 else 0)
 tailcash=sum(f[i]/(1+r)**(i-4) for i in range(5,10))
 terminal=profit[-1]*scale*(1+g)*(1-g/.12)/(r-g)
 terminal_pv=terminal/(1+r)**10
 remaining=(tailcash+terminal/(1+r)**5+fin+other_financial)/shares
 per_share=sum(dps[i]/(1+r)**(i+1) for i in range(5))+remaining/(1+r)**5
 return dict(r=r,g=g,per_share=per_share,equity=per_share*shares,financial5=fin,terminal5=remaining,year5_terminal_pv_fraction=remaining/(1+r)**5/per_share,post_year10_pv_fraction=terminal_pv/(per_share*shares))
def justified_pe(r):
 # EPS1 is denominator; years1-5 payout50%, 10% growth financed at incremental20%.
 # After year5 g3%, ROIC12%, payout75%.
 return sum(1.1**t*.5/(1+r)**(t+1) for t in range(5))+1.1**4*1.03*.75/(r-.03)/(1+r)**5
out={'shares0':SHARES0,'shares5':SHARES5,'debt':debt,'derivative_net':derivative_net,'legacy_longpay':legacy_longpay,'financial':financial,'other_financial':other_financial,'bridge':bridge,'profit':profit,'reinvestment':reinvestment,'fcf':fcf,'base_rows':rows,'dcf_low':dcf(.10,.02),'dcf_high':dcf(.09,.03),'dcf_mid':dcf(),'terminal5_low':terminal5(.10,.02),'terminal5_high':terminal5(.09,.03),'pe_low_multiple':justified_pe(.10),'pe_high_multiple':justified_pe(.09),'pe_aux_low':(profit[0]*justified_pe(.10)+bridge-BUYBACK)/SHARES5,'pe_aux_high':(profit[0]*justified_pe(.09)+bridge-BUYBACK)/SHARES5,'economic_capacity_low':capacity_dcf(.10,.02),'economic_capacity_high':capacity_dcf(.09,.03),'sensitivity_discount_plus1pp':dcf(.105,.025),'sensitivity_extra_reinvestment10':dcf(extra_reinvestment=10),'sensitivity_operating_cash_minus10pct':dcf(scale=.9),'structural':dcf(.105,.015,scale=.70,extra_reinvestment=10),'optimistic':dcf(.09,.03,scale=1.15),'cycle_2yr_delay_value':None,'no_further_buyback_mid':dcf(buyback=0,shares=SHARES0)['per_share'],'financial5':financial5,'other_financial_terminal':other_financial}
# Cyclical disruption reduces first two owner cash by 20/15bn and restores base year3; liquidity can fund.
out['cycle_2yr_delay_value']=dcf(cycle=True)['per_share']
out['holder_pv_low']=sum(dps[i]/1.1**(i+1) for i in range(5))+out['terminal5_low']/1.1**5
out['holder_pv_high']=sum(dps[i]/1.09**(i+1) for i in range(5))+out['terminal5_high']/1.09**5
out['incremental_return_y1_y5']=(profit[4]-profit[0])/sum(reinvestment[1:5])
assert len(dps)==5
assert abs(SHARES0-SHARES5-BUYBACK/BUYBACK_P)<1e-10

print(json.dumps(out,ensure_ascii=False,indent=2))

"""Independent literal reconstruction. No production imports, parameters or computed rows as inputs."""
import json,gzip,math,base64
from pathlib import Path
P=dict(sales=[3600,4000,4400,4800,5200],margin=[.13,.15,.16,.165,.17],terminal_growth=.02,terminal_margin=.145,fade_end=15,wc_ratio=.39,fixed_ratio=.20,opening_wc=1430.,opening_fixed=686.,tax=.15,cash_yield=.018,debt_rate=.035,payout=.5,opening_cash=[1800.,200.,200.],opening_debt=[105.006481,17.225,17.225],opening_legal=1700.,parent_statutory=327.13892023,parent_registered=793.970662,weights=[.85,.075,.075],cash_weights=[.85,.075,.075],floor_weights=[.75,.10,.15],floor_ratio=.12,new_shares=[.60312,0.,0.,0.,0.],exercise_prices=[16.8,26.63,26.63,0,0],opening_shares=793.970662,opening_equity=4445.085799,opening_intercompany=[137.30797819,354.63494228],debt_limit=[200.,50.,50.],upstream_start=2,special_start=10,fund_call=62.5,locked_deposits=[450.,0.,0.],extra_wc=0.,extra_wc_start=1,nonmodelled_assets=134.035546,annual_minority=.002,investment_recovery_year=10,investment_recovery_ratio=.8,investment_exit_cost=.02,upstream_lag=2,upstream_friction=.01,tax_renewal=True,tax_failure_year=1,voluntary_reserve_rate=0.)
VAR={
'base':{},'cyclical':dict(sales=[3100,3300,3900,4500,5000],margin=[.07,.10,.14,.16,.17],extra_wc=200.),
'structural':dict(sales=[3400,3500,3600,3700,3800],margin=[.08,.085,.09,.09,.09],terminal_margin=.08,terminal_growth=.01,wc_ratio=.48,fixed_ratio=.24),
'upside':dict(sales=[3800,4400,5100,5800,6500],margin=[.145,.17,.18,.19,.19],terminal_margin=.16,wc_ratio=.37,fixed_ratio=.21),
'normalized_earnings_power_year3':dict(sales=[3600,4000,4400,4488,4577.76],margin=[.13,.15,.16,.16,.16],terminal_margin=.16),
 'terminal_margin_minus2pt_from_year6':dict(terminal_margin=.125),'receivable_delay_300_from_year1':dict(extra_wc=300.),
 'parent_cash_upstream_delay':dict(upstream_start=6,upstream_lag=5,weights=[.65,.175,.175],cash_weights=[.60,.20,.20]),
 'upstream_delay_recovers_year15':dict(upstream_start=6,upstream_lag=5,weights=[.65,.175,.175],cash_weights=[.60,.20,.20],upstream_lag_recovery_year=15,upstream_lag_after_recovery=2),
 'retained_principal_release_year15':dict(special_start=15,investment_recovery_year=15),
 'all_rights_exercise_conditional_diagnostic':dict(new_shares=[12.,7.,6.67055,0.,0.],exercise_prices=[16.5,25.5,24.9,0.,0.]),
 'tax_preference_not_renewed':dict(tax_renewal=False),'investment_recovery_full':dict(investment_recovery_ratio=1.),
 'investment_recovery_half':dict(investment_recovery_ratio=.5),'upstream_friction_5pct':dict(upstream_friction=.05),
 'voluntary_reserve_10pct':dict(voluntary_reserve_rate=.1),'registered_change_delayed':dict(parent_registered=786.892451),
 'minority_2pct':dict(annual_minority=.02)}

def rebuild(change,n=350):
 p=P|change
 c=list(p['opening_cash']);d=list(p['opening_debt']);loan=list(p['opening_intercompany']);wc=1430.;fa=686.;reg=p['parent_registered'];st=p['parent_statutory'];opt=0.;l=1700.;shares=793.970662;equity=4445.085799;asset=134.035546
 hist=[[],[]];cum=[0.,0.];sent=[0.,0.];out=[];revenue=0.
 for t in range(1,n+1):
  oldshares=shares;oldbps=equity/shares
  if t<6:revenue=p['sales'][t-1];m=p['margin'][t-1]
  else:
   a=min(1.,(t-5)/10);revenue*=1+(p['sales'][4]/p['sales'][3]-1)*(1-a)+p['terminal_growth']*a;m=p['margin'][4]*(1-a)+p['terminal_margin']*a
  nextwc=revenue*p['wc_ratio']+(p['extra_wc'] if t>=p['extra_wc_start'] else 0.)
  depreciation=.12*fa;spend=max(depreciation+revenue*p['fixed_ratio']-fa,0.);nextfa=fa+spend-depreciation
  inv=spend-depreciation+nextwc-wc;ebit=revenue*m
  rate=p['tax'] if p['tax_renewal'] or t<p['tax_failure_year'] else .25
  yieldcash=[x*.018 for x in c];interest=[x*.035 for x in d]
  pre=[ebit*p['weights'][i]+yieldcash[i]-interest[i] for i in range(3)]
  tax=[max(x,0)*rate for x in pre];earn=[pre[i]-tax[i] for i in range(3)]
  nci=max(ebit-max(ebit,0)*rate,0)*p['annual_minority'];earn[0]-=nci
  cw=p['cash_weights'] if t<6 else p['weights']
  c=[c[i]+ebit*p['weights'][i]-inv*cw[i]+yieldcash[i]-interest[i]-tax[i] for i in range(3)];c[0]-=nci
  call=62.5 if t==1 else 0;c[0]-=call;asset+=call
  if t==p['investment_recovery_year']:
   net=asset*p['investment_recovery_ratio']*(1-.02);gain=net-asset;selltax=max(gain,0)*rate
   c[0]+=net-selltax;earn[0]+=gain-selltax;asset=0.
  issued=p['new_shares'][t-1] if t<6 else 0;received=issued*p['exercise_prices'][t-1] if t<6 else 0
  shares+=issued;reg+=issued;c[0]+=received
  priorl=l
  al=min(.1*max(earn[0]-max(-l,0),0),max(reg*.5-st,0));l+=earn[0]-al;st+=al
  extra=max(earn[0]-max(-priorl,0)-al,0)*p['voluntary_reserve_rate'];l-=extra;opt+=extra
  for j in range(2):hist[j].append(earn[j+1]);cum[j]+=earn[j+1]
  floor=[revenue*.12*w+(p['locked_deposits'][i] if t==1 else 0) for i,w in enumerate(p['floor_weights'])]
  repay=[min(d[i],p['opening_debt'][i]/3) if t<4 else 0 for i in range(3)]
  new=[0.,0.,0.];il=[0.,0.]
  for i in [1,2]:
   transfer=min(max(floor[i]+repay[i]-c[i],0),max(c[0]-floor[0]-repay[0],0));c[0]-=transfer;c[i]+=transfer;loan[i-1]+=transfer;il[i-1]=transfer
  for i in range(3):
   new[i]=min(max(floor[i]+repay[i]-c[i],0),max(p['debt_limit'][i]-d[i],0));c[i]+=new[i]-repay[i];d[i]+=new[i]-repay[i]
   assert c[i]>=floor[i]-1e-7
  upstream=[];cost=[];pr=[];cap=[]
  for j in range(2):
   i=j+1;payment=min(loan[j],max(c[i]-floor[i],0));c[i]-=payment;c[0]+=payment;loan[j]-=payment;pr.append(payment)
   lag=p.get('upstream_lag_after_recovery',2) if t>=p.get('upstream_lag_recovery_year',10**9) else p['upstream_lag'];mature=sum(hist[j][:max(t-lag,0)]);capacity=max(min(mature,cum[j])-sent[j],0);cap.append(capacity)
   rem=min(capacity,max(c[i]-floor[i],0)) if t>=p['upstream_start'] else 0;fee=rem*p['upstream_friction'];sent[j]+=rem;c[i]-=rem;c[0]+=rem-fee
   gain=rem-fee;take=min(.1*max(gain-max(-l,0),0),max(.5*reg-st,0));l+=gain-take;st+=take;al+=take;upstream.append(rem);cost.append(fee)
  profit=sum(earn)-sum(cost);target=max(profit,0)*.5 if t<6 else max(profit-max(inv,0),0)
  dividend=min(target,max(c[0]-floor[0],0),max(l,0));c[0]-=dividend;l-=dividend
  special=min(max(c[0]-floor[0],0),max(l,0)) if t>=p['special_start'] else 0;c[0]-=special;l-=special
  total=dividend+special;equity+=profit+received-total
  out.append(dict(year=t,sales=revenue,margin=m,ebit=ebit,taxes=tax,net_profit=profit,cash=c[:],debt=d[:],parent_legal=l,parent_statutory=st,parent_discretionary=opt,parent_registered_budget=reg,reserve_allocation=al,source_cumulative_earnings=cum[:],source_remitted=sent[:],source_matured_capacity=cap,subs_declared_budget=upstream,upstream_friction=cost,intercompany_loans=loan[:],intercompany_principal_repaid=pr,investment_asset=asset,shares=shares,equity=equity,working_capital=nextwc,fixed_assets=nextfa,capex=spend,net_reinvestment=inv,dps=total/shares))
  wc=nextwc;fa=nextfa
 return out

def main():
 root=Path(__file__).parent;prod=json.loads(gzip.decompress(base64.b64decode(json.loads(root.joinpath('2026-Q3-output.json').read_text())['payload_base64'])));result={};maximum=0.
 for name,changes in VAR.items():
  rows=rebuild(changes);expected=prod['cases'][name]['rows'];err=0.
  tail=rebuild(changes,450)
  assert abs(sum(z['dps']/1.095**z['year'] for z in tail)-prod['all_case_tail_checks'][name]['pv_450'])<1e-8
  for row,want in zip(rows,expected):
   for key,x in row.items():
    y=want[key];pairs=zip(x,y) if isinstance(x,list) else [(x,y)]
    for a,b in pairs:
     delta=abs(a-b);err=max(err,delta);assert delta<max(1e-6,abs(b)*1e-11),(name,row['year'],key,a,b)
  vals={}
  for r in [.095,.10,.105]:
   pv=sum(x['dps']/(1+r)**x['year'] for x in rows);tv=sum(x['dps']/(1+r)**(x['year']-5) for x in rows[5:]);vals[str(r)]={'pv':pv,'tv5':tv}
   assert abs(pv-prod['cases'][name]['valuations'][str(r)]['value'])<1e-8
  result[name]={'rows':rows,'valuations':vals,'max_absolute_difference':err};maximum=max(maximum,err)
 long=rebuild({},450)
 for a,b in zip(long,prod['long_integration_rows']):
  assert abs(a['dps']-b['dps'])<1e-7
 raw=(json.dumps({'independent_literal_all_years':result,'long_450':long},ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
 root.joinpath('independent-all-years.json.gz').write_bytes(gzip.compress(raw,mtime=0))
 root.joinpath('independent-summary.json').write_text(json.dumps({'cases':len(result),'years_per_case':350,'fields':list(long[0]),'max_absolute_difference':maximum,'long_years':450,'status':'all annual fields independently reconstructed within tolerance'},indent=2)+'\n')
 print('PASS',len(result),'x350 plus450 maxdiff',maximum)
if __name__=='__main__':main()

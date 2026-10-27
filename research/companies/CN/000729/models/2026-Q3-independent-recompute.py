import json,sys
from pathlib import Path
def independent_literal_check(p,o):
 A=6.27917245316+.42382745678+1.31109376145+p['long_deposit']-.28185393410-.47302271150-.10007011013-p['old_cap_payable']-p['minority_finance']
 C=p['parent_cash'];T=p['parent_term'];Z=A-C-T;L=p['parent_retained'];B=0.;H=0.;Q=0.;loan=0.;owing=0.;schedule={};AR=p['old_dividend_receivable'];ds=[];last_op=0.;revenue=0.;loss=p['source_loss_budget']
 for year in range(1,len(o['rows'])+1):
  ix=min(year-1,4)
  if year<6:revenue=p['revenues'][ix]
  else:revenue*=1+(p['years6to10_growth'][year-6] if year<11 else p['g'])
  margin=p['margins'][ix];OP=revenue*margin*(1-p['tax'])*(1-p['minority'])
  DA=p['da'][ix] if year<6 else p['da'][4]*revenue/p['revenues'][4]
  MC=p['maintenance'][ix] if year<6 else DA
  GC=p['growth_cap'][ix] if year<6 else max(0,OP-last_op)/p['roic']
  WC=p['nwc'][ix] if year<6 else 0.
  AC=p['associate_cash']*(1+p['g'])**(year-1)
  CF=OP+DA-MC-GC-WC+AC;allocation=.5 if year<6 else .2;CFP=OP*p['parent_share']+(DA-MC-GC-WC)*allocation+AC
  IP=max(0,C+T-p['parent_floor'])*p['deposit_net_yield'];IS=max(0,Z-p['sub_floor'])*p['deposit_net_yield']
  idx=year-p['maturity_delay']-1
  maturity=min(T,[1.3,2.,2.,1.7][idx]) if idx in range(4) else 0.
  receipt=min(AR,.71988416907) if year==1+p['old_receipt_delay'] else 0.
  transfer=(p['own_net_payments'][ix] if year<6 else 0.)+(p['extra_internal_net_payment'] if year==1 else 0.)
  PF=p['parent_floor']*revenue/p['revenues'][0];SF=p['sub_floor']*revenue/p['revenues'][0]
  SP=OP*(1-p['parent_share'])+IS;held=.1*SP if year<6 else 0.;released=H if year==6 else 0.
  used=min(loss,max(0,SP)*p['loss_affected_profit_share']);loss-=used
  eligible=B+SP-held+released-used;before=Z+CF-CFP+IS+transfer-receipt
  fraction=1/max(1,p['release_end']-year+1) if year>=p['release_start'] else 0.
  wanted=(p['sub_decl'] if year<6 else .9)*SP+max(0,before-SF)*fraction
  declare=max(0,min(wanted,eligible,before-SF-Q))
  when=year+p['upstream_delay'];schedule[when]=schedule.get(when,0)+declare;owing+=schedule.get(year,0)
  remit=min(owing,max(0,before-SF));owing-=remit;Q+=declare-remit;B=eligible-declare;H+=held-released
  interest=loan*.05;Cbefore=C+CFP+IP+maturity+remit+receipt-transfer-interest
  borrow=max(0,PF-Cbefore);Cbefore+=borrow;repay=min(loan,max(0,Cbefore-PF));Cbefore-=repay;loan+=borrow-repay
  legal=L+OP*p['parent_share']+IP+declare+AC-interest
  T-=maturity;Z=before-remit;total=Cbefore+T+Z
  desired=p['dividend_ps'][ix]*2.818539341 if year<6 else max(0,CF+IP+IS)+max(0,total-PF-SF-max(0,CF+IP+IS))*fraction
  D=max(0,min(desired,legal,Cbefore-PF));D=0. if D<1e-12 else D
  C=Cbefore-D;L=legal-D;AR-=receipt;A+=CF+IP+IS-D-interest+borrow-repay;last_op=OP;ds.append(D)
  checks={'revenue':revenue,'fcf':CF,'parent_fcf':CFP,'sub_declaration':declare,'sub_cash_remittance':remit,'distribution':D,'parent_cash_end':C,'parent_term_end':T,'sub_cash_end':Z,'parent_retained_end':L,'sub_distributable_budget_end':B,'dividends_receivable_end':Q,'financial_assets_end':A,'bank_debt_end':loan,'source_loss_end':loss,'source_loss_offset':used}
  for key,value in checks.items():assert abs(value-o['rows'][year-1][key])<1e-8,(year,key,value,o['rows'][year-1][key])
 discount=p['rate'];offset=p['deposit_net_yield']*(p['parent_floor']+p['sub_floor']);tail=(ds[-1]+offset)*(1+p['g'])/(discount-p['g'])-offset/discount;n=len(ds)
 pv=sum(c/(1+discount)**(i+1) for i,c in enumerate(ds))+tail/(1+discount)**n
 tv=sum(ds[i]/(1+discount)**(i-4) for i in range(5,n))+tail/(1+discount)**(n-5)
 assert abs(pv/2.818539341-o['value_per_share'])<1e-10
 assert abs(tv/2.818539341-o['terminal_year5_per_share'])<1e-10
 raw_initial=6.27917245316+.42382745678+1.31109376145+p['long_deposit']-.28185393410-.47302271150-.10007011013-p['old_cap_payable']-p['minority_finance']
 cash1=p['revenues'][0]*p['margins'][0]*(1-p['tax'])*(1-p['minority'])*(1-p['g']/p['roic'])-(p['parent_floor']+p['sub_floor'])*p['g']+p['associate_cash']
 npv=cash1/(p['rate']-p['g']);balance=max(0,raw_initial-p['parent_floor']-p['sub_floor']);fpv=0.
 for y in range(1,p['release_end']+1):
  balance+=balance*p['deposit_net_yield']
  pay=0. if y<p['release_start'] else balance/(p['release_end']+1-y)
  balance-=pay;fpv+=pay/(1+p['rate'])**y
 assert abs((npv+fpv)/2.818539341-o['auxiliary_value'])<1e-10
 return dict(years_checked=n,all_cash_decisions_recomputed=True,independent_of_production_helpers=True,pv_independent=pv/2.818539341,terminal5_independent=tv/2.818539341)

if __name__=='__main__':
 o=json.loads((Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('2026-Q3-output.json')).read_text())
 for k,v in o['scenarios'].items():
  print(k, independent_literal_check(v['inputs'],v))

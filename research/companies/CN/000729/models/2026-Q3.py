"""燕京啤酒2026Q3，原截止事实重建。十亿元/十亿股。未来均为经济预算，非法律容量认证。
单文件标准库。python 2026-Q3.py [output.json]。"""
import json,copy,sys
from pathlib import Path
S=2.818539341
BASE=dict(rate=.09,g=.02,tax=.20,minority=.15,deposit_net_yield=.015,
 long_deposit=3.134,minority_finance=.90,old_cap_payable=.15,
 revenues=[16.5,17.16,17.8464,18.381792,18.8413368],margins=[.17,.173,.176,.178,.18],da=[.66,.69,.72,.75,.78],
 maintenance=[.70,.73,.76,.79,.82],growth_cap=[.45,.40,.35,.30,.30],nwc=[.10]*5,
 dividend_ps=[.30,.33,.36,.39,.42],roic=.12,parent_share=.15,sub_decl=.55,
 parent_cash=.37262339115,parent_term=7.0,parent_retained=9.36159910644,
 source_loss_budget=0.,loss_affected_profit_share=.40,associate_cash=.004,old_dividend_receivable=.71988416907,maturity_delay=0,old_receipt_delay=0,
 upstream_delay=0,extra_internal_net_payment=0.,credit_limit=1.2,release_start=6,release_end=15,
 years6to10_growth=[.045,.04,.035,.03,.025],parent_floor=.30,sub_floor=2.20,own_net_payments=[.3,.0,.0,.0,.0])
FACTS=dict(cash=6.27917245316,trading=.42382745678,current_deposit=1.31109376145,
 other_noncurrent=3.81387803421,oct_dividend=.28185393410,bank=.47302271150,old_dividends=.10007011013,shares=S)
def initial(p):
 return FACTS['cash']+FACTS['trading']+FACTS['current_deposit']+p['long_deposit']-FACTS['oct_dividend']-FACTS['bank']-FACTS['old_dividends']-p['old_cap_payable']-p['minority_finance']
def run(p,N=120):
 pc,pt,pr=p['parent_cash'],p['parent_term'],p['parent_retained']
 sc=initial(p)-pc-pt;sr=0.;ar=p['old_dividend_receivable'];declared_pending=0.
 rows=[];prior_nopat=None;bank_debt=0.;held_source_buffer=0.;due={};matured_unpaid=0.;source_loss=p['source_loss_budget']
 for y in range(1,N+1):
  j=min(y,5)-1
  rev=p['revenues'][j] if y<=5 else rows[-1]['revenue']*(1+(p['years6to10_growth'][y-6] if y<=10 else p['g']))
  margin=p['margins'][j] if y<=5 else p['margins'][-1]
  ebit=rev*margin;tax=max(ebit,0)*p['tax'];group_nopat=ebit-tax
  minority=group_nopat*p['minority'];op=group_nopat-minority
  da=p['da'][j] if y<=5 else p['da'][-1]*rev/p['revenues'][-1]
  maintenance=p['maintenance'][j] if y<=5 else da
  growth=p['growth_cap'][j] if y<=5 else max(0,op-prior_nopat)/p['roic']
  wc=p['nwc'][j] if y<=5 else 0.
  cap=maintenance+growth;assoc=p['associate_cash']*(1+p['g'])**(y-1);fcf=op+da-cap-wc+assoc
  capital_parent_share=.50 if y<=5 else .20
  pfcf=p['parent_share']*op+capital_parent_share*(da-cap-wc)+assoc;sfcf=fcf-pfcf
  pi=max(0,pc+pt-p['parent_floor'])*p['deposit_net_yield'];si=max(0,sc-p['sub_floor'])*p['deposit_net_yield']
  mature=[1.3,2.,2.,1.7][y-1-p['maturity_delay']] if 1<=y-p['maturity_delay']<=4 else 0.
  mature=min(pt,mature);pt_new=pt-mature
  old_receipt=min(ar,.71988416907) if y==1+p['old_receipt_delay'] else 0.
  settle=(p['own_net_payments'][j] if y<=5 else 0.)+(p['extra_internal_net_payment'] if y==1 else 0.)
  scale=rev/p['revenues'][0];pf=p['parent_floor']*scale;sf=p['sub_floor']*scale
  sn=op*(1-p['parent_share'])+si
  buffer_add=.10*max(sn,0) if y<=5 else 0.
  buffer_release=held_source_buffer if y==6 else 0.
  loss_offset=min(source_loss,max(0,sn)*p['loss_affected_profit_share'])
  source_earnings=sr+sn-buffer_add+buffer_release-loss_offset
  source_pre=sc+sfcf+si+settle-old_receipt
  release_fraction=(1/max(1,p['release_end']-y+1)) if y>=p['release_start'] else 0.
  desired_up=(p['sub_decl'] if y<=5 else .90)*max(sn,0)+release_fraction*max(0,source_pre-sf)
  declared=max(0,min(desired_up,source_earnings,source_pre-sf-declared_pending))
  due[y+p['upstream_delay']]=due.get(y+p['upstream_delay'],0.)+declared
  matured_unpaid+=due.get(y,0.)
  cash_up=min(matured_unpaid,max(0,source_pre-sf));matured_unpaid-=cash_up
  pending_new=declared_pending+declared-cash_up;sr_new=source_earnings-declared;sc_new=source_pre-cash_up
  parent_profit=op*p['parent_share']+pi+declared+assoc
  legal=pr+parent_profit
  interest=bank_debt*.05
  pc_pre=pc+pfcf+pi+mature+cash_up+old_receipt-settle-interest
  borrowing=max(0,pf-pc_pre)
  if bank_debt+borrowing>p['credit_limit']+1e-10:raise ValueError('Unfunded parent liquidity: year=%s gap=%.12f' % (y,bank_debt+borrowing-p['credit_limit']))
  if borrowing>0:pc_pre+=borrowing
  repayment=min(bank_debt,max(0,pc_pre-pf));pc_pre-=repayment
  bank_new=bank_debt+borrowing-repayment;legal-=interest
  common_before=pc_pre+pt_new+sc_new
  target=(p['dividend_ps'][j]*S if y<=5 else max(0,fcf+pi+si)+(max(0,common_before-(pf+sf)-max(0,fcf+pi+si))*release_fraction))
  d=max(0,min(target,legal,pc_pre-pf))
  if d<1e-12:d=0.
  pc_new=pc_pre-d;pr_new=legal-d
  residual=(pc_new+pt_new+sc_new)-(pc+pt+sc+fcf+pi+si-d-interest+borrowing-repayment)
  assert abs(residual)<1e-8,(y,residual)
  assert min(pc_new,sc_new,pt_new,pr_new,sr_new,pending_new)>=-1e-8
  rows.append(dict(year=y,revenue=rev,margin=margin,group_ebit=ebit,cash_tax=tax,group_nopat=group_nopat,minority_profit=minority,common_operating_profit=op,da=da,maintenance=maintenance,growth_capital=growth,working_capital=wc,associate_cash=assoc,fcf=fcf,parent_fcf=pfcf,sub_fcf=sfcf,parent_cash_open=pc,parent_term_open=pt,sub_cash_open=sc,parent_financial_income=pi,sub_financial_income=si,maturity=mature,old_receipt=old_receipt,internal_receipts=1.0,internal_payments=1.0+settle,net_internal=settle,sub_profit_budget=sn,source_loss_open=source_loss,source_loss_offset=loss_offset,source_loss_end=source_loss-loss_offset,source_buffer_added=buffer_add,source_buffer_released=buffer_release,sub_distributable_budget_open=sr,sub_eligible_budget=source_earnings,sub_declaration=declared,sub_cash_remittance=cash_up,dividends_receivable_end=pending_new,sub_distributable_budget_end=sr_new,parent_profit_budget=parent_profit,parent_retained_open=pr,parent_retained_end=pr_new,parent_cash_end=pc_new,parent_term_end=pt_new,sub_cash_end=sc_new,financial_assets_end=pc_new+pt_new+sc_new,desired_distribution=target,distribution=d,distribution_ps=d/S,bank_debt_open=bank_debt,bank_debt_end=bank_new,interest=interest,external_financing=borrowing,debt_repayment=repayment,cash_residual=residual,parent_floor=pf,sub_floor=sf))
  pc,pt,sc,pr,sr,ar,declared_pending=pc_new,pt_new,sc_new,pr_new,sr_new,ar-old_receipt,pending_new
  prior_nopat=op;bank_debt=bank_new;held_source_buffer+=buffer_add-buffer_release;source_loss-=loss_offset
 assert bank_debt<1e-8
 r,g=p['rate'],p['g'];constant=p['deposit_net_yield']*(p['parent_floor']+p['sub_floor'])
 tail=(rows[-1]['distribution']+constant)*(1+g)/(r-g)-constant/r
 pv=sum(x['distribution']/(1+r)**x['year'] for x in rows)+tail/(1+r)**N
 terminal5=sum(x['distribution']/(1+r)**(x['year']-5) for x in rows[5:])+tail/(1+r)**(N-5)
 terminal_share=(tail/(1+r)**N)/pv
 operating_buffer=p['parent_floor']+p['sub_floor']
 normalized_operating_cash=rows[0]['common_operating_profit']*(1-g/p['roic'])-operating_buffer*g+p['associate_cash']
 normalized_operating_pv=normalized_operating_cash/(r-g)
 extra=max(0,initial(p)-operating_buffer);extra0=extra;finance_pv=0.;finance_rows=[]
 for y in range(1,p['release_end']+1):
  opening=extra;income=opening*p['deposit_net_yield'];available=opening+income
  payment=available/(p['release_end']-y+1) if y>=p['release_start'] else 0.
  extra=available-payment;finance_pv+=payment/(1+r)**y
  finance_rows.append(dict(year=y,opening=opening,net_income=income,distribution=payment,closing=extra))
 assert abs(extra)<1e-10
 auxiliary=(normalized_operating_pv+finance_pv)/S
 auxiliary_details=dict(method='current_normalized_cash_capitalization_plus_realized_finance_pv',first_cash=normalized_operating_cash,opening_operating_buffer=operating_buffer,first_buffer_growth=operating_buffer*g,operating_pv=normalized_operating_pv,extra_finance_opening=extra0,finance_pv=finance_pv,finance_rows=finance_rows)
 return dict(value_per_share=pv/S,terminal_year5_per_share=terminal5/S,distributions_ps=[x['distribution_ps'] for x in rows[:5]],terminal_tail_pv_share=terminal_share,year5_terminal_pv_share=(terminal5/(1+r)**5)/pv,auxiliary_value=auxiliary,auxiliary_details=auxiliary_details,initial_financial_assets=initial(p),rows=rows,tail=tail)
def hand_test():
 p=copy.deepcopy(BASE);p.update(revenues=[10]*5,margins=[.2]*5,tax=.25,minority=.2,da=[0]*5,maintenance=[0]*5,growth_cap=[0]*5,nwc=[0]*5,dividend_ps=[.5/S]*5,parent_share=.5,associate_cash=0.,sub_decl=1.,deposit_net_yield=0.,parent_cash=10.,parent_term=0.,old_dividend_receivable=0.,own_net_payments=[0]*5,parent_floor=0.,sub_floor=0.)
 p['long_deposit']+=20-initial(p)
 z=run(p,1)['rows'][0]
 assert abs(z['fcf']-1.2)<1e-12 and abs(z['distribution']-.5)<1e-12
 assert abs(z['financial_assets_end']-20.7)<1e-12 and abs(z['sub_declaration']-.54)<1e-12
 return dict(fcf=1.2,dividend=.5,end_finance=20.7,source_declaration=.54,passed=True)
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
def main():
 paths={}
 low=copy.deepcopy(BASE);low.update(rate=.095,long_deposit=3.0,minority_finance=1.15,roic=.10)
 high=copy.deepcopy(BASE);high.update(rate=.085,long_deposit=3.35,minority_finance=.65,roic=.14)
 paths.update(core_low=low,base=copy.deepcopy(BASE),core_high=high)
 cyc=copy.deepcopy(BASE);cyc.update(revenues=[15.5,16.3,17.8464,18.381792,18.8413368],margins=[.15,.16,.176,.178,.18],nwc=[.25,.20,-.15,.1,.1]);paths['cyclical']=cyc
 bear=copy.deepcopy(BASE);bear.update(revenues=[14.5,14.2,14.2,14.2,14.2],margins=[.14,.13,.13,.13,.13],tax=.25,g=0.,roic=.09,rate=.105,years6to10_growth=[0]*5,maintenance=[.8]*5,growth_cap=[.3,.3,.2,.1,.1],nwc=[.2,.1,0,0,0],dividend_ps=[.20]*5,sub_decl=.45);paths['structural']=bear
 bull=copy.deepcopy(BASE);bull.update(revenues=[17.0,18.02,19.1012,20.05626,20.85851],margins=[.18,.185,.19,.19,.19],growth_cap=[.65,.60,.55,.45,.40],nwc=[.15]*5,roic=.15);paths['upside']=bull
 delay=copy.deepcopy(BASE);delay.update(maturity_delay=2,old_receipt_delay=2,upstream_delay=2,extra_internal_net_payment=1.0);paths['liquidity_delay']=delay
 tax=copy.deepcopy(BASE);tax['tax']=.25;paths['tax25']=tax
 margin=copy.deepcopy(BASE);margin['margins']=[m-.01 for m in BASE['margins']];paths['margin_minus_1pp']=margin
 slow=copy.deepcopy(BASE);slow.update(release_start=11,release_end=20);paths['slower_principal_return']=slow
 loss=copy.deepcopy(BASE);loss['source_loss_budget']=1.23268854706;paths['source_loss_recovery']=loss
 ncil=copy.deepcopy(BASE);ncil['minority_finance']=0.;paths['minority_finance_zero_bound']=ncil
 ncih=copy.deepcopy(BASE);ncih['minority_finance']=1.8;paths['minority_finance_high_bound']=ncih
 result=dict(units='CNY billion; shares billion; per share CNY',facts=FACTS,source_budget_status='未来母子宣派/利润/到期均为情景预算，不证明未披露法人法定容量；旧应收收现不再确认利润。',hand_test=hand_test(),scenarios={})
 for k,p in paths.items():
  o=run(p);tail_check=run(p,121);assert abs(o['value_per_share']-tail_check['value_per_share'])<1e-7;o['tail_horizon_difference']=abs(o['value_per_share']-tail_check['value_per_share']);o['inputs']=p;o['independent_check']=independent_literal_check(p,o);result['scenarios'][k]=o
 unfunded=copy.deepcopy(delay);unfunded['credit_limit']=0.
 try:run(unfunded);raise AssertionError('expected funding failure')
 except ValueError as e:result['no_credit_liquidity_stress']=dict(feasible=False,reason=str(e),note='无授信证明；该压力需融资或重新协商往来付款，不沿用未付股息/终值。')
 target=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('2026-Q3-output.json')
 target.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
 print(json.dumps({k:{a:v[a] for a in ['value_per_share','terminal_year5_per_share','distributions_ps','auxiliary_value']} for k,v in result['scenarios'].items()},ensure_ascii=False,indent=2))
if __name__=='__main__':main()

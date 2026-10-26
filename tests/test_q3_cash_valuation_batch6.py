"""从冻结原始事实/预算重建，不导入正式模型；正式输出只在末尾作比较。
三现金账户P/J/O，法定利润各自滚动；Decimal。金额百万元。
"""
from decimal import Decimal as D, getcontext
import json
from pathlib import Path
getcontext().prec=38
Z=D(0);ONE=D(1);OWN=D('.51');SH=D('635.588289')
# 原始三表/附注现金边界，不从正式模型结果读取任何预测输入。
SOURCE={'cash':'283.26693590','trading':'422.54048033','current_noncurrent':'935.17586633','receivable_excluded':'5.82521356','other_noncurrent':'1283.83120596','prepaid_capital':'52.41057010',
 'j_old_parent_debt':'163.214080','j_external_minority':'156.785920','group_affiliated_debt':'50','bank_debt':'7.78537867','lease':'2.26369971','investment':'94.77226667'}
FACT={k:D(v) for k,v in SOURCE.items()}
CASH0=FACT['cash']+FACT['trading']+FACT['current_noncurrent']-FACT['receivable_excluded']+FACT['other_noncurrent']-FACT['prepaid_capital']
# 研究预算，与来源事实分列，全部冻结于此。
BUDGET={'p_profit':'580','n_profit':'240','j_profit':'20','internal_other_to_p':'400','n_cash':'70','j_cash':'20',
 'p_legal':'2200','j_legal':'100','other_legal':'550','p_statutory_reserve':'356.393488','j_statutory_reserve':'20','other_statutory_reserve':'80',
 'j_new_loan':'300','internal_interest_after_tax':'.03','financial_yield_after_tax':'.015','fund_call':'24'}
B={k:D(v) for k,v in BUDGET.items()}
GROWTH=list(map(D,['0','.025','.03','.03','.025']))
PCAP=list(map(D,['120','120','110','105','105']))
JCAP=list(map(D,['40','35','30','25','20']))
NCAP=list(map(D,['150','140','125','115','115']))
WC=list(map(D,['15','15','16','17','17']))
DPS=list(map(D,['.95','1','1.05','1.1','1.15']))
CAP={'p':SH,'j':D('122.45'),'o':D('277.55')}
def accrue_legal(re,res,profit,capital):
 # Accumulated accounting deficit only. A loss year with positive retained profits is not a separate loss pool.
 profit_after_old_deficit=profit-max(Z,-re)
 statutory_add=min(max(Z,capital/2-res),max(Z,profit_after_old_deficit)/10)
 return re+profit-statutory_add,res+statutory_add,statutory_add

def five_years(sub_start=3):
 cash={'p':CASH0-B['n_cash'],'j':B['j_cash'],'o':B['n_cash']-B['j_cash']}
 re={'p':B['p_legal'],'j':B['j_legal'],'o':B['other_legal']}
 res={'p':B['p_statutory_reserve'],'j':B['j_statutory_reserve'],'o':B['other_statutory_reserve']}
 op={'p':B['p_profit'],'j':B['j_profit'],'o':B['n_profit']-B['j_profit']}
 loan=Z; rows=[]
 total_external=FACT['group_affiliated_debt']+FACT['bank_debt']+FACT['lease']
 for k in range(5):
  y=k+1;opening=sum(cash.values());op={a:b*(1+GROWTH[k]) for a,b in op.items()}
  if y==1:
   # Mother repays only the actual budget creditor O; J receives its own new loan.
   cash['p']-=B['internal_other_to_p'];cash['o']+=B['internal_other_to_p']
   cash['j']-=FACT['j_old_parent_debt'];cash['p']+=FACT['j_old_parent_debt']
   cash['j']+=B['j_new_loan'];cash['p']-=B['j_new_loan'];loan+=B['j_new_loan']
  ip=cash['p']*B['financial_yield_after_tax']
  # Frozen budget places external N financial yield at O, not at restricted J.
  ino=(cash['j']+cash['o'])*B['financial_yield_after_tax']
  jint=loan*B['internal_interest_after_tax']
  principal_o=(FACT['bank_debt']+FACT['lease']) if y==1 else (FACT['group_affiliated_debt'] if y==2 else Z)
  principal_j=FACT['j_external_minority'] if y==1 else Z
  extint=total_external*D('.03') if y==1 else (FACT['group_affiliated_debt']*D('.03') if y==2 else Z)
  # Build each entity's operating cash independently, not by reading group prediction rows.
  fcfp=op['p']+90-PCAP[k]-WC[k]*D('.6')
  fcfj=op['j']+40-JCAP[k]
  fcfo=op['o']+35-(NCAP[k]-JCAP[k])-WC[k]*D('.4')
  profit={'p':op['p']+ip+jint,'j':op['j']-jint,'o':op['o']+ino-extint}
  for entity in re:re[entity],res[entity],_=accrue_legal(re[entity],res[entity],profit[entity],CAP[entity])
  cash['p']+=fcfp+ip+jint-(B['fund_call'] if y==1 else Z)
  cash['j']+=fcfj-jint-principal_j
  cash['o']+=fcfo+ino-extint-principal_o
  topup=max(Z,20-cash['j'])
  assert loan+topup<=450 and cash['p']-topup>=900
  cash['p']-=topup;cash['j']+=topup;loan+=topup
  sub_div=max(Z,min(D('.65')*(profit['j']+profit['o']),cash['o']-150,re['o'])) if y>=sub_start else Z
  cash['o']-=sub_div;re['o']-=sub_div;cash['p']+=OWN*sub_div;re['p']+=OWN*sub_div
  ordinary=max(Z,min(DPS[k]*SH,cash['p']-900,re['p']))
  cash['p']-=ordinary;re['p']-=ordinary
  assert ordinary==DPS[k]*SH
  assert min(cash.values())>=0 and min(re.values())>=0
  expected=opening+fcfp+fcfj+fcfo+ip+ino-extint-principal_o-principal_j-(B['fund_call'] if y==1 else Z)-ordinary-(1-OWN)*sub_div
  assert abs(sum(cash.values())-expected)<D('1e-28')
  rows.append({'year':y,'cash':dict(cash),'legal':dict(re),'reserve':dict(res),'operating_profit':dict(op),'fcf':{'p':fcfp,'j':fcfj,'o':fcfo},'loan':loan,'internal_interest':jint,'topup':topup,'sub_dividend':sub_div,'ordinary':ordinary,'ordinary_per_share':ordinary/SH,'external_principal':principal_o+principal_j,'external_interest':extint,'financial_interest':ip+ino})
 return rows

def post_fifth(last,rate,growth,roi,wait=1):
 # Three entities retain independent ownership and legal capacity beyond Y5.
 cash={'p':last['cash']['p']-300,'j':last['cash']['j']-20,'o':last['cash']['o']-130}
 re=dict(last['legal']);res=dict(last['reserve']);op=dict(last['operating_profit']);debt=last['loan']
 rows=[];v=Z
 for t in range(1,81):
  opening=sum(cash.values());interest={e:c*D('.015') for e,c in cash.items()}
  for e in cash:cash[e]+=interest[e];op[e]*=1+growth
  loan_interest=debt*D('.03');j_fcf=op['j']*(1-growth/roi)
  debt_service=min(j_fcf,debt+loan_interest)
  assert debt_service>=loan_interest
  debt-=debt_service-loan_interest
  cash['p']+=debt_service
  profit={'p':op['p']+interest['p']+loan_interest,'j':op['j']-loan_interest+interest['j'],'o':op['o']+interest['o']}
  for e in re:re[e],res[e],_=accrue_legal(re[e],res[e],profit[e],CAP[e])
  normal={'p':op['p']*(1-growth/roi),'o':op['o']*(1-growth/roi),'j':max(Z,j_fcf-debt_service)}
  for e in re:
   assert re[e]>=normal[e], 'Operating terminal cannot pay assumed normal dividend'
   re[e]-=normal[e]
  sub_normal_receipt=OWN*(normal['j']+normal['o'])
  re['p']+=sub_normal_receipt;re['p']-=sub_normal_receipt
  j_old_repaid=Z;divo=Z;divj=Z
  if t>=wait:
   j_old_repaid=min(cash['j'],debt);cash['j']-=j_old_repaid;debt-=j_old_repaid;cash['p']+=j_old_repaid
   divo=max(Z,min(cash['o'],re['o']));cash['o']-=divo;re['o']-=divo
   if debt<D('1e-28'):divj=max(Z,min(cash['j'],re['j']))
   cash['j']-=divj;re['j']-=divj
   cash['p']+=OWN*(divo+divj);re['p']+=OWN*(divo+divj)
  recovered=FACT['investment']+B['fund_call'] if t==max(3,wait) else Z
  cash['p']+=recovered
  ordinary=max(Z,min(cash['p'],re['p'])) if t>=wait else Z
  cash['p']-=ordinary;re['p']-=ordinary
  incremental=ordinary-OWN*debt_service
  v+=incremental/(1+rate)**t
  expected=opening+sum(interest.values())+debt_service+recovered-ordinary-(1-OWN)*(divo+divj)
  assert abs(sum(cash.values())-expected)<D('1e-25')
  assert min(cash.values())>=-D('1e-25') and min(re.values())>=0
  rows.append({'year_after_five':t,'cash':dict(cash),'legal':dict(re),'reserve':dict(res),'op':dict(op),'normal':normal,'normal_sub_receipt_and_passthrough':sub_normal_receipt,'debt_service':debt_service,'internal_interest':loan_interest,'debt':debt,'j_existing_repaid':j_old_repaid,'divo':divo,'divj':divj,'ordinary_financial':ordinary,'baseline_j_operating_cash_removed':OWN*debt_service,'incremental_financial':incremental,'investment_recovery':recovered})
  if t>=max(3,wait) and debt<D('1e-25') and sum(cash.values())<D('1e-25'):
   for e in re:assert re[e]>=max(Z,CAP[e]/2-res[e])
   break
 else:raise AssertionError('Unreleased financial cash or loan after year80')
 return v,rows

def rebuilt(rate,growth,roi,sub_start=3,wait=1):
 rate,growth,roi=map(D,[rate,growth,roi])
 years=five_years(sub_start);last=years[-1]
 common_profit=last['operating_profit']['p']+OWN*(last['operating_profit']['j']+last['operating_profit']['o'])
 operating_value=common_profit*(1+growth)*(1-growth/roi)/(rate-growth)
 financial_value,tail=post_fifth(last,rate,growth,roi,wait)
 terminal=(operating_value+financial_value)/SH
 current=sum(row['ordinary_per_share']/(1+rate)**row['year'] for row in years)+terminal/(1+rate)**5
 return {'value':current,'terminal_per_share':terminal,'terminal_operating':operating_value,'terminal_financial':financial_value,'rows':years,'tail':tail}


import pytest
ROOT=Path(__file__).resolve().parents[1]/'research/companies/CN'
# 江中完整纠正及独立复算移至 test_q3_jiangzhong_final.py。

def tebao_recalc(ghscale=1.,r=.115):
    a={'hbv': [3250, 3350, 3350, 3300, 3200, 3100, 3000, 2900, 2800, 2700], 'gh': [800, 1050, 1300, 1500, 1650, 1800, 1930, 2050, 2150, 2220], 'other': [320, 350, 380, 400, 420, 440, 455, 465, 470, 470], 'new': [0, 0, 0, 100, 300, 450, 600, 700, 750, 780], 'rd': [500, 540, 580, 620, 650, 680, 700, 710, 710, 710], 'milestones': [80, 100, 160, 150, 120, 100, 80, 60, 50, 50], 'capex': [520, 470, 400, 330, 300, 300, 300, 300, 300, 300], 'da': [145, 165, 185, 210, 235, 255, 275, 290, 300, 300], 'gross': [0.887, 0.883, 0.878, 0.873, 0.868, 0.863, 0.858, 0.853, 0.85, 0.85], 'sell': [0.355, 0.35, 0.345, 0.34, 0.335, 0.335, 0.335, 0.335, 0.335, 0.335], 'admin': [0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085], 'donation': [0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018, 0.018], 'research_sub': [90, 100, 110, 120, 130, 135, 140, 140, 140, 140], 'nwc_ratio': 0.34, 'nwc_open': 1471.73526582, 'tail_decay': -0.02, 'bank_limit': 1100.0, 'bank_rate': 0.035, 'yield': 0.012, 'payout': 0.3, 'b_payout': 0.6, 'old_settlement_years': 4, 'initial_cash': {'P': 2005.2855085, 'B': 195.0, 'R': 40.0}, 'initial_retained': {'P': 1950.0, 'B': 600.0, 'R': -100.0}, 'delay': 1, 'fund_recovery_year': 8, 'fund_recovery': 161.65239399, 'convert': False, 'zero_dividend': False, 'revenue_multiplier': 1.0, 'gh_multiplier': 1.0, 'shift_parent_to_sub': 0.0, 'reserve_extra': 0.0}
    N=(408189480-10821089+4334528)/1e6
    P,B,R=2005.2855085,195.,40.;uP,uB,uR=1950.,600.,-100.;sP=205.43661109
    debt=795.74141896;old=320.;last_nwc=1471.73526582;earmark=1400.;declared=0.;D=[]
    rows=[]
    for t in range(1,251):
        ix=min(t-1,9); f=.98**max(0,t-10)
        h=a['hbv'][ix]*f;g=a['gh'][ix]*f*ghscale;o=a['other'][ix]*f;n=a['new'][ix]*f;revenue=h+g+o+n
        research=a['research_sub'][ix]*f;cap=a['capex'][ix]*f;da=a['da'][ix]*f
        ebit=revenue*(a['gross'][ix]-a['sell'][ix]-.085-.018)-(a['rd'][ix]+a['milestones'][ix])*f-.08*n
        be=.8*(h+g)*(.06 if t==1 else .045 if t==2 else .03);pe=ebit-be+research
        bi=debt*.035;coupon=1533.266*[.001,.003,.006,.01,.015][t-1] if t<6 else 0
        premium=122.66128 if t==6 else 0
        pp=(pe+P*.012-bi-coupon-premium)*.85;bp=(be+B*.012)*.85;rp=-research+R*.012
        change=revenue*.34-last_nwc;last_nwc=revenue*.34
        P+=pp+.9*(da-cap)-change+premium
        B+=bp+.05*(da-cap);R+=rp+.05*(da-cap)
        if t==1:P+=4.334528*38.57
        repayment=min(debt,150) if 2<=t<=7 else 0;P-=repayment;debt-=repayment
        if t==6:P-=1655.92728
        if t==2:P-=31.49177387
        if t==8:P+=161.65239399
        settle=min(old,80);old-=settle;P-=settle;B+=settle
        P+=declared;B-=declared
        support=max(0,20*f-R);R+=support;P-=support
        earmark=max(0,earmark-.65*cap-.2*a['rd'][ix]*f)
        floor=max(250*.98**max(0,t-20),revenue*.1)+earmark
        assert P>=floor # these paths do not draw loans; independently checked
        add=min(max(0,(408.18948+4.334528)*.5-sP),max(0,pp+min(0,uP))*.1);sP+=add;uP+=pp-add;uB+=bp;uR+=rp
        target=.6*max(0,bp)+(.25*max(0,B-30*f) if 5<t<=20 else 0)
        if t>=25:target=max(0,B-30*f)
        declared=min(target,max(0,B-30*f),max(0,uB));uB-=declared;uP+=declared
        targetp=.3*max(0,pp+bp+rp) if t<=5 else .7*max(0,pp+bp+rp)+.25*max(0,P-floor)
        if 20<t<23:targetp=.7*max(0,pp+bp+rp)
        if t>=23:targetp=max(0,P-floor)
        dividend=min(targetp,max(0,P-floor),max(0,uP))
        P-=dividend;uP-=dividend;D.append(dividend/N)
        fcfe=pe*.85+be*.85-research+da-cap-change
        rows.append([P,B,R,dividend/N,fcfe])
    v=sum(d/(1+r)**t for t,d in enumerate(D,1))
    tv=sum(D[t-1]/(1+r)**(t-5) for t in range(6,251))
    return {'value':v,'tv5':tv,'dps':D[:5],'rows':rows}

@pytest.mark.parametrize('rate,gh,key',[(.115,1.,'low'),(.10,1.,'high'),(.1075,.8,'gh_minus20')])
def test_tebao_independent_250year_legal_cash(rate,gh,key):
 out=json.loads((ROOT/'688278/models/2026-Q3-output.json').read_text())
 value=tebao_recalc(gh,rate)
 expected=out['valuations']['base'][key] if gh==1 else out['sensitivities'][key]['value']
 assert value['value']==pytest.approx(expected['value'],abs=1e-8)
 assert value['tv5']==pytest.approx(expected['tv5'],abs=1e-8)
 rows=out['runs']['base']['rows'] if gh==1 else out['sensitivities'][key]['model']['rows']
 for a,b in zip(value['rows'],rows):
  for i,k in enumerate(['P','B','R']):assert a[i]==pytest.approx(b['cash_close'][k],abs=1e-7)
 assert len(rows)==250

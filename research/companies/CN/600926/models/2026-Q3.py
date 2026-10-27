#!/usr/bin/env python3
"""杭州银行普通股模型。单位十亿元、十亿股；--table NAME 展开年表。无外部依赖。"""
import json, math, pathlib, sys
B0=144.102147; PB0=138.667354; R0=1504.078374; S=7.249002548
D0=.320167; PD0=1.298238; PR=.993603962
CASES={
 'base':dict(k=.10,nim=.0139,endnim=.0135,loancc=.005,nonloancc=.0002,commitcc=.0005,cost=.29,tax=.16,at1rate=.028,g=.04),
 'core_low':dict(k=.105,nim=.0137,endnim=.0133,loancc=.0055,nonloancc=.0003,commitcc=.0006,cost=.295,tax=.17,at1rate=.03,g=.04),
 'core_high':dict(k=.095,nim=.0141,endnim=.0137,loancc=.0045,nonloancc=.0001,commitcc=.0004,cost=.285,tax=.15,at1rate=.026,g=.04),
 'cycle':dict(k=.10,nim=.0139,endnim=.0135,loancc=.005,nonloancc=.0002,commitcc=.0005,cost=.29,tax=.16,at1rate=.028,g=.04),
 'structural':dict(k=.115,nim=.0123,endnim=.0118,loancc=.009,nonloancc=.0008,commitcc=.0015,cost=.32,tax=.16,at1rate=.04,g=.025),
 'upside':dict(k=.095,nim=.0145,endnim=.0142,loancc=.004,nonloancc=.0001,commitcc=.0003,cost=.28,tax=.15,at1rate=.025,g=.045),
}

def pv(divs, terminal, k):
 return sum(d/(1+k)**(i+1) for i,d in enumerate(divs))+terminal/(1+k)**len(divs)

def run(name,c,years=120):
 b,pb,r,u=B0,PB0,R0,58.880589
 rows=[]
 for t in range(1,years+1):
  g=([.08,.08,.07,.065,.06][t-1] if t<=5 else (.06+(c['g']-.06)*min((t-5)/10,1)))
  nim=c['nim']+(c['endnim']-c['nim'])*min((t-1)/14,1)
  cc=c['loancc']; ncc=c['nonloancc']; cmcc=c['commitcc']; at=c['at1rate']; cost=c['cost']
  if name=='cycle' and t<=3:
   nim-= [.0015,.001,.0005][t-1]; cc+=[.006,.004,.002][t-1]; ncc+=.0005; at+=.006; g=min(g,.04)
  if name=='structural': g=min(g,.04)
  group_target=.096; parent_target=.092
  if name=='structural': group_target=.102; parent_target=.098
  # 无股权增发；约束不足时先减分红、再减资产增长。正常存款与债务续作成本在息差中。
  def economics(growth):
   rn=r*(1+growth); avg=(r+rn)/2
   ea=avg*1.50; loans=avg*.78; nonloan=avg*.72; commits=avg*.30
   nii=ea*nim; fee=avg*.0030; other=avg*.0031
   rev=nii+fee+other; expenses=rev*cost; losses=loans*cc+nonloan*ncc+commits*cmcc
   tax=max(0,(rev-expenses-losses-avg*.00025))*c['tax']
   # 按RWA同比例维持AT1，含续作及新增成本；本金全为其他权益，不计普通股净资产。
   at1=(r+rn)/2*(30/R0); coupon=at1*at
   excess=max(0,b-(group_target+D0/R0)*r)
   excess_income=.02*excess
   group_before_at1=rev-expenses-losses-avg*.00025-tax+excess_income
   profit=group_before_at1-coupon
   parent_profit=.962*group_before_at1-coupon
   subprofit=profit-parent_profit
   subbook=b-pb
   subneed=.004*rn
   upstream=0 if t<=5 else max(0,min(subbook+subprofit-subneed,subprofit-(subneed-.004*r)+.2*max(0,subbook-.004*r)))
   # 下列准备为经济分配预算，而非逐年精确法定认定；均为权益内部划转。
   reserve=max(0,parent_profit)*.10+max(0,rn-r)*.78*.015
   legal=max(0,u+parent_profit+upstream-reserve)
   gc=max(0,b+profit-(D0/R0)*rn-group_target*rn)
   pc=max(0,pb+parent_profit+upstream-(PD0/R0)*rn-parent_target*PR*rn)
   rawg=b+profit-(D0/R0)*rn-group_target*rn
   rawp=pb+parent_profit+upstream-(PD0/R0)*rn-parent_target*PR*rn
   return locals()
  x=economics(g)
  if min(x['rawg'],x['rawp'])<0:
   lo=-.10; hi=g
   for _ in range(70):
    mid=(lo+hi)/2; xx=economics(mid)
    if min(xx['rawg'],xx['rawp'])>=0: lo=mid
    else: hi=mid
   g=lo; x=economics(g)
  rn=x['rn']; profit=x['profit']; pp=x['parent_profit']; up=x['upstream']
  if t<=5: desired=max(0,profit)*[.30,.30,.32,.35,.38][t-1]
  else:
   # 增长降速后普通资本超额按20%每年逐步返还；无尾期集中清空。
   required=(group_target+D0/R0)*r
   desired=max(0,profit-(group_target+D0/R0)*(rn-r)+.2*max(0,b-required))
  # 保留母行流动性：年度分红不超过期初合格优质流动资产的5%，余款留存。
  liquidity_limit=.05*(470.061919/R0)*r
  div=min(desired,x['gc'],x['pc'],x['legal'],liquidity_limit)
  bn=b+profit-div; pbn=pb+pp+up-div; un=u+pp+up-x['reserve']-div
  cet=bn-D0/R0*rn; pcet=pbn-PD0/R0*rn
  assert abs(bn-b-profit+div)<1e-8*max(1,bn)
  assert abs((bn-pbn)-(b-pb)-(profit-pp)+up)<1e-8*max(1,bn)
  assert cet/rn>=group_target-1e-10 and pcet/(PR*rn)>=parent_target-1e-10
  assert div>=0 and un>=-1e-9
  tier1=(cet+rn*30/R0)/rn; total=(cet+rn*(30+20+17.452983)/R0)/rn
  assert tier1>=.085 and total>=.105
  # 总资产/存款随RWA扩展，其他负债占比固定；剩余同业及债券融资为配平项。
  A0=2530.394819; DEP0=1543.748157; OTH0=23.0; CASH0=159.486803
  a0=A0/R0*r; a1=A0/R0*rn; dep0=DEP0/R0*r; dep1=DEP0/R0*rn
  ot0=OTH0/R0*r; ot1=OTH0/R0*rn; at0=30/R0*r; at1=30/R0*rn
  wh0=a0-b-at0-dep0-ot0; wh1=a1-bn-at1-dep1-ot1
  cash0=CASH0/R0*r; cash1=CASH0/R0*rn
  cash_sources=profit+(dep1-dep0)+(ot1-ot0)+(wh1-wh0)+(at1-at0)
  cash_uses=div+(a1-cash1)-(a0-cash0)
  assert abs(cash_sources-cash_uses-(cash1-cash0))<1e-8*max(1,a1)
  assert wh1>0
  pa0=2517.445024/R0*r; pa1=2517.445024/R0*rn
  pwh0=pa0-pb-at0-dep0-ot0; pwh1=pa1-pbn-at1-dep1-ot1
  pcash_sources=pp+up+(dep1-dep0)+(ot1-ot0)+(pwh1-pwh0)+(at1-at0)
  pcash_uses=div+(pa1-cash1)-(pa0-cash0)
  assert abs(pcash_sources-pcash_uses-(cash1-cash0))<1e-8*max(1,pa1)
  assert pwh1>0
  rows.append(dict(year=t,parent_cash_sources=pcash_sources,parent_cash_uses=pcash_uses,parent_cash_change=cash1-cash0,parent_wholesale_and_bonds=pwh1,tier1_ratio=tier1,total_capital_ratio=total,tier2_end=rn*20/R0,tier2_net_funding=(rn-r)*20/R0,excess_capital= x['excess'],excess_income=x['excess_income'],total_assets=a1,deposits=dep1,wholesale_and_bonds=wh1,wholesale_net_funding=wh1-wh0,deposit_net_funding=dep1-dep0,cash_equivalents_end=cash1,cash_sources=cash_sources,cash_uses=cash_uses,cash_change=cash1-cash0,rwa_begin=r,rwa_end=rn,rwa_growth=g,nim=nim,loan_cc=cc,nonloan_cc=ncc,commit_cc=cmcc,cost_income=cost,tax_rate=c['tax'],at1_coupon_rate=at,
   revenue=x['rev'],nii=x['nii'],fee=x['fee'],other=x['other'],expenses=x['expenses'],credit_losses=x['losses'],tax=x['tax'],at1_coupon=x['coupon'],at1_end=rn*30/R0,at1_net_funding=(rn-r)*30/R0,
   book_begin=b,book_end=bn,parent_book_begin=pb,parent_book_end=pbn,common_profit=profit,parent_profit=pp,sub_upstream=up,parent_legal_reserve_budget=x['reserve'],parent_undistributed_end=un,
   common_dividend=div,dps=div/S,eps=profit/S,roe=profit/b,payout=div/profit if profit else 0,cet1_ratio=cet/rn,parent_cet1_ratio=pcet/(PR*rn),liquidity_limit=liquidity_limit,shares=S,new_common_shares=0,new_common_funding=0))
  b,pb,r,u=bn,pbn,rn,un
 # 已稳定的最后一年后使用稳态g；账面增长与分红逐年已收敛。
 last=rows[-1]; g=c['g']; k=c['k']
 assert abs(last['rwa_growth']-g)<1e-9
 assert abs(last['book_end']/last['book_begin']-1-g)<1e-7
 tv=last['common_dividend']*(1+g)/(k-g)
 value=pv([a['common_dividend'] for a in rows],tv,k)/S
 ri=B0+sum((a['common_profit']-k*a['book_begin'])/(1+k)**a['year'] for a in rows)+(tv-last['book_end'])/(1+k)**years
 assert abs(value-ri/S)<1e-8
 term5=pv([a['common_dividend'] for a in rows[5:]],tv,k)/S
 term15=pv([a['common_dividend'] for a in rows[15:]],tv,k)/S
 # year 5价值是继续经营分配，不将今天价值复制至未来。
 return dict(parameters=c,value=value,residual_income_value=ri/S,terminal_year5=term5,terminal_year15=term15,terminal15_present_value_share=(term15/(1+k)**15)/value,tail120_present_value_share=(tv/S/(1+k)**years)/value,distributions=[a['dps'] for a in rows[:5]],rows=rows)

def main():
 # 手算特例进入正式pv链：100本金、10%收益全派，五年后仍值100。
 assert abs(pv([10]*5,100,.1)-100)<1e-10
 out={name:run(name,c) for name,c in CASES.items()}
 sens=dict(CASES['base']);sens['k']=.11
 out['cost_plus_100bp']=run('base',sens)
 for lab,k in [('base_terminal_low',.105),('base_terminal_high',.095)]:
  cc=dict(CASES['base']);cc['k']=k;out[lab]=run('base',cc)
 out['meta']=dict(unit='CNY billion; billion shares',opening_date='2026-09-30',valuation_date='2026-10-27',shares=S,book=B0,parent_book=PB0,rwa=R0,rounding_note='Q3 statement shares shown in thousand; exact H1 unchanged shares used',policy='No market prices. 120-year readable annual states retained; --table NAME prints any scenario.')
 path=pathlib.Path(__file__).resolve().with_name('2026-Q3-output.json')
 path.write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
 if len(sys.argv)>2 and sys.argv[1]=='--table':
  print('year rwa book profit dividend CET1 parentCET1')
  for a in out[sys.argv[2]]['rows']: print(a['year'],*(round(a[k],6) for k in ['rwa_end','book_end','common_profit','common_dividend','cet1_ratio','parent_cet1_ratio']))
 else: print(json.dumps({k:{a:v[a] for a in ['value','terminal_year5','distributions']} for k,v in out.items() if k!='meta'},ensure_ascii=False,indent=2))
if __name__=='__main__': main()

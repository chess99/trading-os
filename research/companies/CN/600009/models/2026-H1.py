"""上海机场普通股经济现金模型；亿元/亿股；标准库，无网络。"""
import json
from pathlib import Path
S=24.8831304
R0=[59.89,22.06,18.30,33.22]
REVS=[[62,20,21,33.5],[64.2,22,22.7,34],[66.4,24,24.3,34.5],[68.6,25.5,25.8,35],[70.8,27,27.3,35.5]]
M=[.55,.75,.30,.35] # 新增收入的税后现金贡献率，扣变动成本；固定成本另扣
MAINT=[15,15.3,15.6,15.9,16.2]
GROW=[2,2.5,3,3,3]
LEASE=[20,21,22,23,24]
ASSOC=[5,5.2,5.4,5.6,5.8]
NCI=[3,3.2,3.5,3.8,4.1] # 少数经济现金份额，非实际派息
D=[.53,.56,.59,.62,.65]
OBL=3.1633987888
B0=156.67+15.22+1.99-50-20.12-8-OBL

def run(revs=REVS,extra_lease=0,cost_step=.8,nci=NCI,terminal_roi=None):
 rows=[]; B=B0
 for i,rr in enumerate(revs):
  contrib=[(a-b)*m for a,b,m in zip(rr,R0,M)]
  # 2025 CFO59.82，去金融收入2及营运资金有利贡献2，保留成熟经营现金55.82
  cfo=55.82+sum(contrib)-cost_step*(i+1)
  before=cfo-MAINT[i]-LEASE[i]-extra_lease+ASSOC[i]-nci[i]
  cf=before-GROW[i]
  old=B; B=B*1.01+cf-D[i]*S
  rows.append(dict(year=i+1,revenue=rr,incremental_cash_by_segment=contrib,operating_cash_ex_finance=cfo,maintenance=MAINT[i],growth_capex=GROW[i],lease=LEASE[i]+extra_lease,associate_cash=ASSOC[i],minority_economic_cash=nci[i],pre_growth_common_cash=before,common_cash=cf,dividend_per_share=D[i],opening_financial_bridge=old,financial_return=old*.01,closing_financial_bridge=B))
 endpoints=[]
 for r,g,roi in [(.105,.01,.10),(.09,.02,.12)]:
  if terminal_roi is not None: roi=terminal_roi
  # 终态维护后的业主收益，g/ROIC用于新增成长资本；显性GROW不再另扣
  u=rows[-1]['pre_growth_common_cash']*(1+g)
  grow=u*g/roi; f6=u-grow; tv=f6/(r-g)
  pv=sum(x['common_cash']/(1+r)**x['year'] for x in rows)
  ep=dict(rate=r,growth=g,incremental_return=roi,year6_pre_growth_cash=u,year6_growth_capex=grow,year6_common_cash=f6,operating_terminal=tv,pv_explicit=pv,pv_terminal=tv/(1+r)**5,value_per_share=(pv+tv/(1+r)**5+B0)/S,TV5_per_share=(tv+B)/S)
  ep['terminal_share_of_total']=ep['pv_terminal']/(pv+ep['pv_terminal']+B0)
  endpoints.append(ep)
 return dict(rows=rows,endpoints=endpoints)

def main():
 base=run(); stress=run(extra_lease=2); no_recovery=run([[x[0],20,x[2],x[3]] for x in REVS]); weak=run(cost_step=1.6)
 for row in base['rows']:
  assert abs(row['closing_financial_bridge']-row['opening_financial_bridge']-row['financial_return']-row['common_cash']+row['dividend_per_share']*S)<1e-9
  assert abs(row['pre_growth_common_cash']-row['growth_capex']-row['common_cash'])<1e-9
 for ep in base['endpoints']:
  assert abs(ep['year6_pre_growth_cash']-ep['year6_growth_capex']-ep['year6_common_cash'])<1e-9
 # g=0特例，无新增成长资本，经营终值为维护后现金/r。
 u=base['rows'][-1]['pre_growth_common_cash']; assert u*(1-0/.1)/.1==u/.1
 out=dict(shares=S,initial_bridge=B0,bridge_inputs=dict(cash=156.67,trading_assets=15.22,other_financial_recovery=1.99,operating_cash_reserve=50,financial_debt=20.12,nci_financial_cash_allocation=8,declared_unpaid_nci_dividend=OBL),base=base,sensitivity_extra_lease_2=stress,sensitivity_commercial_stays_20=no_recovery,sensitivity_cost_step_1_6=weak,sensitivity_terminal_return_8=run(terminal_roi=.08),auxiliary=[(24*11.5+B0)/S,(28*14+B0)/S])
 Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print(json.dumps({'base':base['endpoints'],'bridge':B0,'rows':base['rows'],'auxiliary':out['auxiliary'],'lease_sensitivity':[x['value_per_share'] for x in stress['endpoints']],'commercial_sensitivity':[x['value_per_share'] for x in no_recovery['endpoints']],'cost_sensitivity':[x['value_per_share'] for x in weak['endpoints']]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()

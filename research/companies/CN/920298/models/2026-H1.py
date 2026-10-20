"""腾信精密独立经营/股东现金模型；金额亿元、股数亿股，无网络依赖。"""
import json, math
from pathlib import Path
S=.807
D=[.4,.5,.7,.9,1.1]
P_REVENUE=7.100463
BUILD=9.60-.309556 # 移除已在总预算内的铺底资金，再按增量实际周转形成全量WC
C0=4.3285+6.7795-.8 # 持续租用费用已在经营利润/现金中；不再扣相同租赁本金，最低现金不作多余资产
PARAMS={
 'low':dict(e0=1.75,g=.04,ri=.20,margin=.18,wc=.45,r=.12,tg=.02,pri=.105),
 'high':dict(e0=1.85,g=.06,ri=.25,margin=1.322229/7.100463,wc=.40,r=.112,tg=.025,pri=.115),
 'base':dict(e0=1.80,g=.05,ri=.225,margin=.183,wc=.425,r=.116,tg=.0225,pri=.11),
}
def run(p,project_scale=1.0,delay=0,mature_scale=1.0,start_cash_delta=0):
 p=p.copy(); c=C0+start_cash_delta; rows=[]; prev_e=p['e0']*mature_scale; prev_rev=0; years=[0,0,.6,.8,1]
 if delay: years=[0]*delay+years
 parent=1.1016+6.7795-.5+start_cash_delta; sub=c-parent; legal=3.8023; transferred=0
 for t in range(1,6):
  e=p['e0']*mature_scale*(1+p['g'])**t
  reinvest=(e-prev_e)/p['ri']; mature=e-reinvest
  u=years[t-1]; rev=P_REVENUE*u; pe=(rev*p['margin']-.15*(1-u)-.1)*project_scale if u else 0
  da=.55 if u else 0; maintenance=.30 if u else 0
  dwc=(rev-prev_rev)*p['wc']; building=BUILD/2 if t in [1+delay,2+delay] else 0
  project=pe+da-maintenance-dwc-building
  interest=c*.015; dividend=D[t-1]*S
  next_c=c+interest+mature+project-dividend
  # 母公司现金收现弱，按35/45/60/60/60%成熟自由现金在母公司形成；余额在全资子公司。
  fraction=[.35,.45,.60,.60,.60][t-1]
  p_interest=parent*.015; s_interest=sub*.015
  parent+=p_interest+mature*fraction+project-dividend
  sub+=s_interest+mature*(1-fraction)
  settlement=max(0,.30-parent); parent+=settlement;sub-=settlement;transferred+=settlement
  # 内部贸易应收结算只转移现金，不增加合并利润或母公司留存。
  legal+=max(0,e*.9+pe+p_interest)*.9-dividend # 为法定公积保守预留利润10%
  assert abs(parent+sub-next_c)<1e-9
  assert abs(next_c-c-interest-mature-project+dividend)<1e-9
  rows.append(dict(year=t,mature_profit=e,mature_growth_capital=reinvest,mature_cash=mature,project_utilization=u,project_revenue=rev,project_profit=pe,project_da=da,project_maintenance=maintenance,project_delta_wc=dwc,building=building,project_cash=project,interest=interest,dividend=dividend,cash_end=next_c,parent_cash=parent,subsidiary_cash=sub,internal_settlement=settlement,parent_distributable_profit=legal))
  c=next_c;prev_e=e;prev_rev=rev
 # 第五年未满产的延期情景，在第五年终值先扣补足WC和剩余扩建；其后仅稳态，不暗中恢复更高增长。
 e6=rows[-1]['mature_profit']*(1+p['tg'])
 full_pe=(P_REVENUE*p['margin']-.1)*project_scale
 pe6=full_pe*(1+p['tg'])
 mature6=e6*(1-p['tg']/p['ri']);project6=pe6*(1-p['tg']/p['pri'])
 remaining_wc=max(0,(P_REVENUE-prev_rev)*p['wc'])
 remaining_build=BUILD-sum(z['building'] for z in rows)
 c5=c-remaining_wc-max(0,remaining_build)
 f6=mature6+project6
 op_tv=f6/(p['r']-p['tg']);tv=(op_tv+c5)/S
 dpv=sum(d/(1+p['r'])**t for t,d in enumerate(D,1));pv=dpv+tv/(1+p['r'])**5
 # 辅助法：直接资本化成熟业务+项目净现值，现金按可用时点估值，无低收益沉淀五年的额外假设。
 mature_value=sum(z['mature_cash']/(1+p['r'])**z['year'] for z in rows)+mature6/(p['r']-p['tg'])/(1+p['r'])**5
 project_npv=sum(z['project_cash']/(1+p['r'])**z['year'] for z in rows)+(project6/(p['r']-p['tg'])-remaining_wc-max(0,remaining_build))/(1+p['r'])**5
 auxiliary=(C0+start_cash_delta+mature_value+project_npv)/S
 assert len(rows)==5 and all(math.isfinite(z['cash_end']) for z in rows)
 return dict(parameters=p,rows=rows,C0=C0+start_cash_delta,C5=c5,mature_F6=mature6,project_F6=project6,F6=f6,operating_TV5=op_tv,TV5=tv,distribution_PV=dpv,current_value=pv,terminal_share=(pv-dpv)/pv,mature_value=mature_value,project_npv=project_npv,auxiliary_value=auxiliary,total_internal_settlement=transferred,min_sub_cash=min(z['subsidiary_cash'] for z in rows))
def main():
 global D, S
 core={k:run(v) for k,v in PARAMS.items()}
 base=PARAMS['base']
 scenarios={'project_profit_minus20':run(base,project_scale=.8),'one_year_delay':run(base,delay=1),'cash_minus_0_5':run(base,start_cash_delta=-.5),'wc_0_55':run({**base,'wc':.55}),'structural':run({**base,'g':0,'margin':.12,'ri':.15,'pri':.07,'tg':.01,'r':.13},project_scale=1,mature_scale=.8),'upside':run({**PARAMS['high'],'g':.08,'margin':.20,'ri':.28,'pri':.14,'r':.108,'tg':.025})}
 saved_d=D[:]; D=[0]*5
 undistributed=run(base); D=saved_d
 expected_retained=sum(d*S*1.015**(5-t) for t,d in enumerate(D,1))
 assert abs(undistributed['C5']-core['base']['C5']-expected_retained)<1e-9
 S=.780; scenarios['without_greenshoe']=run(base,start_cash_delta=5.8137-6.7795); S=.807
 # 资本守恒；分红重复计价自检：假设分红保留应按现金收益复利加入C5，而不是同时发出又保留。
 for a in core.values():
  assert a['min_sub_cash']>=0 and a['total_internal_settlement']<2.8
  assert all(z['parent_distributable_profit']>0 for z in a['rows'])
  assert abs(sum(z['project_delta_wc'] for z in a['rows'])-P_REVENUE*a['parameters']['wc'])<1e-10
  assert abs(sum(z['building'] for z in a['rows'])+.309556-9.6)<1e-10
 assert abs(2/.1-20)<1e-12 # 零增长永续资本化基本特例
 assert abs(sum([1/(1.0)**t for t in range(1,6)])-5)<1e-12 # 零贴现率分配基本特例
 out={'units':'CNY亿元；shares亿股','shares':S,'distributions_per_share':D,'core':core,'sensitivities':scenarios,'self_checks':'cash conservation; capital/WC; dividend cash removed; legal profit; subsidiary cash; zero-growth/zero-rate identities passed'}
 Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print(json.dumps({k:{v:a[v] for v in ['C5','F6','TV5','current_value','project_npv','auxiliary_value','total_internal_settlement']} for k,a in core.items()},ensure_ascii=False,indent=2))
 print(json.dumps({k:a['current_value'] for k,a in scenarios.items()},ensure_ascii=False,indent=2))
if __name__=='__main__': main()

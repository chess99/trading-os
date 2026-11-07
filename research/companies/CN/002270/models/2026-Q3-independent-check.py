"""独立Decimal复算，不导入正式模型。输入同源，现金/法律状态及现值重新实现。"""
from decimal import Decimal as D, getcontext
from pathlib import Path
import json,copy
getcontext().prec=40
P=Path(__file__).resolve().parent
WORK = P.parent / '.work'
WORK.mkdir(parents=True, exist_ok=True)
RAW=json.loads((P/'2026-Q3-inputs.json').read_text(encoding='utf-8'))
def dec(z):
 if isinstance(z,(int,float)):return D(str(z))
 if isinstance(z,list):return [dec(v) for v in z]
 if isinstance(z,dict):return {k:dec(v) for k,v in z.items()}
 return z

def independent(raw,mode):
 a=dec(copy.deepcopy(raw));margin=a['electric_nopat_margin'];capital=a['growth_capital_per_incremental_sales'];rate=a['discount_base']
 if mode=='core_low':margin=[v-D('.01') for v in margin];capital=D('1.25');rate=D('.105')
 if mode=='core_high':margin=[v+D('.005') for v in margin];capital=D('1.0');rate=D('.09')
 if mode=='margin_down_1pp':margin=[v-D('.01') for v in margin]
 c=a['cash_20260930']-a['paid_oct_dividend']-a['repurchase_paid_oct'];debt=sum(a[k] for k in ['short_bank_debt','long_bank_debt','current_long_bank_debt'])
 pc=a['parent_cash_budget'];ret=a['parent_retained_start'];law=a['parent_statutory_reserve_credit'];old=a['parent_old_dividend_receivable']
 domestic=a['base_revenue_2026']['domestic_electric'];export=a['base_revenue_2026']['export_electric'];cnc=a['base_revenue_2026']['cnc'];other=a['base_revenue_2026']['solar_other'];ds=[]; audit=[]
 for i in range(10):
  prior_sales=domestic+export+cnc
  domestic*=1+a['growth']['domestic'][i];export*=1+a['growth']['export'][i];cnc*=1+a['growth']['cnc'][i]
  hq=a['hq_cash_cost_2026']*(1+a['hq_growth'])**(i+1)
  grant=a['annual_incentive_charge']*((1+a['hq_growth'])**(i-4) if i>=5 else 1)
  electric=(domestic+export)*margin[i]-grant
  manufacturing=electric+cnc*a['cnc_nopat_margin']-hq
  solar=other*a['solar_other_nopat_margin'];income=manufacturing+solar
  principal=min(debt,a['bank_repayment'][i]);end_debt=debt-principal
  borrowing_cost=(debt+end_debt)/2*a['bank_interest']*(1-a['cash_tax'])
  interest=max(D(0),c-a['minimum_group_cash']*(1+a['cash_floor_growth'])**i)*a['cash_yield']*(1-a['cash_tax'])
  profit=income-borrowing_cost+interest
  investment=max(D(0),domestic+export+cnc-prior_sales)*capital
  free=income+(grant if i<5 else 0)+a['solar_annual_depreciation']-other*a['solar_maintenance_rate']-investment-(a['solar_completion_capex'] if i==0 else 0)-borrowing_cost+interest-principal
  buy=a['repurchase_total_budget']-a['repurchase_paid_oct']+a['repurchase_fees'] if i==0 else D(0)
  settlement=a['parent_net_other_settlement'][i];gov=a['government_receivable_collection'][i];asset=a['equity_asset_collection'][i]
  before=c+free-buy+gov+asset-settlement
  floor=a['minimum_group_cash']*(1+a['cash_floor_growth'])**(i+1)
  declared=max(D(0),electric)*(a['upstream_ratio_first5'] if i<5 else a['upstream_ratio_next5'])
  pl=declared-hq
  reserve=min(max(D(0),pl)*D('.1'),max(D(0),a['parent_share_capital']/2-law));law+=reserve
  room=max(D(0),ret+pl-reserve)
  parent_before=pc-hq-buy-settlement+gov
  can_transfer=max(D(0),before-parent_before-(floor-a['parent_cash_floor']))
  collected=min(old,a['old_dividend_collection'][i],can_transfer);old-=collected
  new_cash=min(declared,can_transfer-collected)
  desired=max(D(0),profit)*(a['payout_first5'] if i<5 else a['payout_next5'])
  dividend=max(D(0),min(desired,before-floor,parent_before+collected+new_cash-a['parent_cash_floor'],room))
  pc=parent_before+collected+new_cash-dividend;ret+=pl-reserve-dividend;c=before-dividend;debt=end_debt
  assert c>=floor and pc>=a['parent_cash_floor'] and ret>=0
  ds.append(dividend);audit.append({'cash':float(c),'parent_cash':float(pc),'retained':float(ret),'dividend':float(dividend)})
 r=rate;g=a['stable_growth'];return_on_cap=a['stable_incremental_roic']
 manufacturing_future=manufacturing*(1+g)*(1-g/return_on_cap)/(r-g)
 solar_cash=other*(a['solar_other_nopat_margin']-a['solar_maintenance_rate'])+a['solar_annual_depreciation'];remaining=int(a['solar_remaining_years'])-10
 solar_value=sum(solar_cash/(1+r)**t for t in range(1,remaining+1))+a['solar_final_recovery']/(1+r)**remaining
 extra=c-floor;legal=ret;release=None
 for t in range(1,51):
  np=manufacturing*(1+g)**t
  legal+=np+(solar if t<=remaining else 0)-np*(1-g/return_on_cap)-(solar_cash if t<=remaining else 0)
  if t>=int(a['cash_release_delay']) and legal>=extra:release=t;break
 assert release is not None
 tv=manufacturing_future+solar_value+extra/(1+r)**release
 current=(sum(ds[j]*(1+r)**(9-j) for j in range(10))+tv)/(1+r)**10/a['shares']
 at5=(sum(ds[j]*(1+r)**(9-j) for j in range(5,10))+tv)/(1+r)**5/a['shares']
 return {'current_per_share':float(current),'terminal_year5_per_share':float(at5),'first5_distributions':[float(v/a['shares']) for v in ds[:5]],'cash_legal_rows':audit,'release_after_year10':release}

formal=json.loads((WORK / '2026-Q3-diagnostics.json').read_text(encoding='utf-8'))
results={}
for mode in ['base','core_low','core_high','margin_down_1pp']:
 z=independent(RAW,mode);target=formal['scenarios'][mode]['value']
 for key in ['current_per_share','terminal_year5_per_share']:
  assert abs(z[key]-target[key])<1e-9,(mode,key,z[key],target[key])
 for j,row in enumerate(z['cash_legal_rows']):
  if mode=='base':
   f=formal['base_rows'][j]
   for k,a in [('cash','cash_end'),('parent_cash','parent_cash_end'),('retained','parent_retained'),('dividend','dividend')]:assert abs(row[k]-f[a])<1e-8
 results[mode]=z
results['margin_1pp_change']=results['margin_down_1pp']['current_per_share']-results['base']['current_per_share']
# 手算通过正式函数执行，并用独立闭式年金算式对照。
import importlib.util
spec=importlib.util.spec_from_file_location('huaming_formal',P/'2026-Q3.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
closed_form=(1-(1.1)**-5)/.1+10*(1.1)**-5
assert abs(m.holder_value([1]*5,10,.1)-closed_form)<1e-12
results['formal_chain_hand_example']={'formal':m.holder_value([1]*5,10,.1),'independent_closed_form':closed_form,'proof':'五期1元年金现值3.790786769；第五年10元折现6.209213231；合计10元。'}
(WORK / '2026-Q3-independent-check.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
base=results['base'];low=results['core_low']['current_per_share'];high=results['core_high']['current_per_share']
lo_input=copy.deepcopy(RAW);lo_input['discount_base']=.105
hi_input=copy.deepcopy(RAW);hi_input['discount_base']=.09
verified_model={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':RAW['information_cutoff'],'base_case_distributions_per_share':[round(v,8) for v in base['first5_distributions']],'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':round(independent(lo_input,'base')['terminal_year5_per_share'],8),'high':round(independent(hi_input,'base')['terminal_year5_per_share'],8)}}}
print(json.dumps({'schema':'trading_os_research_result_v1','symbol':'CN:002270','report_period':'2026-Q3','information_cutoff':RAW['information_cutoff'],'value_range':{'low':round(low,2),'high':round(high,2),'currency':'CNY'},'return_model':verified_model,'notes':['独立Decimal重算基准、两个核心端点、经营率低1个百分点及持有人输入；不导入正式金融计算。','正式holder_value函数手算特例与独立闭式公式均为10。']},ensure_ascii=False))

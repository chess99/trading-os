#!/usr/bin/env python3
"""CN:601100 江苏恒立液压股份有限公司 2026-Q3. Stdlib economic budgets, CNY bn.
No market prices, legal certification or synthetic legal reserve pools.
python 2026-Q3.py [--output DIR] regenerates all consumer output.
"""
import argparse,copy,csv,hashlib,json,pathlib
SYMBOL='CN:601100'; NAME='江苏恒立液压股份有限公司'; SHARES=1.340820992
ASOF='2026-10-26T21:30:00+00:00'
OPEN={
 'cash':10.33092840291-.40224629760-.034,'financial_asset':.08681219824+.01143425646+.005,
 'minority_treasury_excluded':.034,
 'debt':.84856631642+.06007119166+.00242858311+.00883052235,
 'old_dividend_claim':2.02082578357-.40224629760,
 'parent_cash':8.10542576480-.40224629760,
 'parent_profit_stock':4.08385921873-.40224629760,
 'ppe':4.98827067350+.44871970863+.43784484828+.67188350070+.02839592490+.01125857972,
 'ar':2.23430074187,'notes':.58182107169+.83028693761,'inventory':2.69748081825,
 'prepayments':.27768215146,'other_operating_assets':.09211311015+.02525905317+.14138326782,
 'trade_payable':1.22494841720-.13770439850+.07647627381,
 'engineering_payable':.13770439850,'customer_advance':.38795154858,
 'salary_tax':.29502120044+.23520068678,
 'other_operating_liability':2.07074735477-2.02082578357+.38655871954,
 'revenue':13.6,'minority_share':.1714,'minority_book':.05990220453,
}
OPEN['nwc']=sum(OPEN[x] for x in ['ar','notes','inventory','prepayments','other_operating_assets'])-sum(OPEN[x] for x in ['trade_payable','customer_advance','salary_tax','other_operating_liability'])
BASE={'growth':[.10,.10,.09,.08,.07,.06,.05,.045,.035,.03],
 'margin':[.25,.255,.26,.26,.26,.255,.25,.245,.24,.24],
 'mexico_ebit':[-.12,-.07,0,.04,.08,.10,.12,.14,.16,.18],
 'linear_ebit':[0,.02,.04,.08,.12,.15,.18,.20,.22,.24],
 'tax':.16,'capex_ratio':[.10,.10,.09,.085,.08,.075,.07,.065,.06,.06],
 'da_ratio':.045,'nwc_ratio':OPEN['nwc']/13.6,'minimum_cash_ratio':.12,
 'r':.095,'g':.02,'terminal_roic':.15,'terminal_multiple':15.0,
 'payout':.40,'special_years':[10],'release_fraction':.50,
 'initial_locked_cash':1.11257408292,'cash_yield':.018,'interest':.04,'debt_limit':2.0,'upstream_fraction':.50,
 'upstream_lag':0,'parent_operating_share':.27,'tech_profit_share':.65,
 'treasury_haircut':0.,'cash_release_year':2,'operating_loss':0.,'extra_wc':0.,
 'extra_cost':0.,'tax_rate_change_year':1,'shock_year':1,'project_future_extra':0.,
 'parent_extra_settlement':0.,'description':'基准：液压跨产品复制和已有海外产能爬坡；线性驱动仅有限贡献'}

def cases():
 d={}
 def add(k,**kw):
  d[k]=copy.deepcopy(BASE);d[k].update(kw)
 add('base')
 add('core_low',r=.10,terminal_roic=.14,terminal_multiple=14.,description='同一核心经营路径；资本成本10%、稳定增量回报14%')
 add('core_high',r=.09,terminal_roic=.16,terminal_multiple=16.,description='同一核心经营路径；资本成本9%、稳定增量回报16%')
 add('cyclical',mexico_ebit=[-.18,-.15,-.08,0,.04,.07,.10,.12,.14,.16],linear_ebit=[-.03,-.03,0,.02,.04,.08,.12,.16,.20,.22],growth=[-.12,-.04,.12,.12,.09,.07,.06,.05,.04,.03],margin=[.19,.18,.23,.25,.26,.255,.25,.245,.24,.24],extra_wc=.5,description='Y1–2主机厂去库和墨西哥爬坡延迟，库存现金Y3恢复，保留服务研发')
 add('structural',mexico_ebit=[-.15]*10,linear_ebit=[-.03]*10,growth=[-.08,0,.03,.03,.03,.02,.02,.02,.02,.02],margin=[.17,.15,.15,.15,.15,.15,.15,.15,.15,.15],nwc_ratio=.38,capex_ratio=[.09]*10,terminal_roic=.09,g=.01,terminal_multiple=10.,extra_cost=.25,description='Y1起主机厂双供议价、海外成本和新产品低利用率永久恶化；不回归旧利润率，Y1–3重组员工费用')
 add('upside',mexico_ebit=[-.06,.02,.10,.18,.25,.30,.35,.40,.45,.50],linear_ebit=[.03,.08,.15,.25,.35,.45,.55,.65,.75,.85],growth=[.16,.14,.12,.11,.09,.08,.065,.05,.04,.03],margin=[.26,.275,.28,.28,.28,.275,.27,.26,.25,.25],capex_ratio=[.12,.115,.11,.10,.095,.085,.075,.07,.065,.06],terminal_roic=.17,description='海外客户复用与线性批量兑现，扩产和周转现金同步增加')
 add('release_early',special_years=[5,10],description='诊断：Y5开始返还过剩金融资产，需董事会及股东会批准')
 add('deposit_delay',initial_locked_cash=7.15817885196,cash_release_year=3,description='诊断：全部H1非等价物直到Y3可用，分配受流动性约束并重算')
 add('collection_delay',extra_wc=1.5,description='诊断：Y1–2额外应收15亿元，Y3收回，不虚增利润')
 add('permanent_wc',nwc_ratio=.42,description='诊断：净营运资本永久提高至42%，终值同步提高必要资本')
 add('treasury_loss',treasury_haircut=.8,description='诊断：Y1外汇掉期及金融本金净损失8亿元，非重复费用')
 add('upstream_lag',upstream_lag=2,description='诊断：恒立科技新股利延迟两年到账；确认和到账分离')
 add('no_upstream10',upstream_fraction=0.,description='诊断：未来十年不宣派新子公司股利，母公司现金/利润约束重算；Y11恢复正常上划，沉淀金融本金Y12实现')
 add('parent_settlement',parent_extra_settlement=1.,description='诊断：Y1母公司向子公司多结算10亿元往来，集团现金不变')
 add('tax25',tax=.25,description='诊断：Y1起有效现金税率25%，所有利润、分配和终值重算')
 add('project_overrun',project_future_extra=1.,description='诊断：Y1–2新增建设超支各5亿元，非已付在建重复扣费')
 add('funding_failure',growth=[-.40]*10,margin=[-.30]*10,operating_loss=1.,debt_limit=.5,description='正式生产链反例：持续亏损、保留员工和债务义务，有限融资后不可行，禁止给TV')
 return d

def step_cash(cash,op_cash,capex,claim,interest,debt,limit,minimum):
 """One production financing function; no zero-clamp of unpaid obligations."""
 before=cash+op_cash-capex-claim-interest
 draw=min(max(minimum-before,0.),max(limit-debt,0.))
 repay=min(max(before-minimum,0.),debt)
 return {'before_financing':before,'draw':draw,'repay':repay,'cash':before+draw-repay,'debt':debt+draw-repay,'shortfall':max(minimum-before-draw,0.)}

def run(p,opening=None,years=10):
 o=copy.deepcopy(OPEN if opening is None else opening)
 revenue=o['revenue'];nwc=o['nwc'];capital=o['ppe'];cash=o['cash'];debt=o['debt'];parent_cash=o['parent_cash'];profit_stock=o['parent_profit_stock'];queue=[];out=[]
 locked=p['initial_locked_cash'] # H1 disclosed security deposits, temporary not permanent loss; Q3 composition unreported
 # Parent pool uses disclosed separate-company profits, not consolidated retained earnings.
 feasible=True
 for t in range(1,years+1):
  revenue*=1+p['growth'][t-1]
  ebit=revenue*p['margin'][t-1]-p['operating_loss']-(p['extra_cost'] if t<=3 else 0)
  mexico_loss=min(p['mexico_ebit'][t-1],0.)
  tax=max(ebit-mexico_loss,0)*p['tax'] # no instant cross-border tax credit for identified Mexico losses
  nopat=ebit-tax
  nwc_end=revenue*p['nwc_ratio']+(p['extra_wc'] if t<=2 else 0)
  dwc=nwc_end-nwc;da=revenue*p['da_ratio'];capex=revenue*p['capex_ratio'][t-1]+(p['project_future_extra']/2 if t<=2 else 0)
  engineering=o['engineering_payable'] if t==1 else 0.
  old_claim=o['old_dividend_claim'] if t==1 else 0.
  treasury_loss=p['treasury_haircut'] if t==1 else 0.
  asset_sale=o['financial_asset'] if t==p['cash_release_year'] else 0.
  asset_sale_tax=max(asset_sale-(.01143425646+.005),0)*.15 # small investments recover book cost; trading gain taxed, not deposit principal
  treasury_income=max(cash,0)*p['cash_yield']*(1-.15)
  interest=debt*p['interest'] # tax deduction deliberately not assumed for all foreign borrowers
  # Shanghai Lixin is 82.86% owned, other listed subsidiaries 100% total economic ownership.
  lixin_profit=(.00357642109/.1714/0.75)*(revenue/13.6)*max(p['margin'][t-1],0)/.25
  lixin_capital_delta=(capex-da+dwc)*.0192 # implied 100% Lixin book (.0599022/.1714) / group equity; capital allocation estimate
  minority_fcfe=p['minority_share']*(lixin_profit-lixin_capital_delta) if 'minority_share' in p else o['minority_share']*(lixin_profit-lixin_capital_delta)
  fcf=nopat+da-capex-dwc-minority_fcfe
  minimum=revenue*p['minimum_cash_ratio']
  # Restricted deposits release at Y2; not spent before then. Treasury principal remains an asset.
  lock_end=locked if t<p['cash_release_year'] else 0.
  financing=step_cash(cash,nopat+da-dwc-minority_fcfe+treasury_income+asset_sale-asset_sale_tax-treasury_loss,capex+engineering,old_claim,interest,debt,p['debt_limit'],minimum+lock_end)
  cash_pre=financing['cash'];debt_end=financing['debt'];feasible=feasible and financing['shortfall']<1e-9
  tech_profit=nopat*p['tech_profit_share']
  tech_fcf=max(0.,(nopat+da-capex-dwc)*p['tech_profit_share'])
  declaration=min(max(tech_profit,0.)*p['upstream_fraction'],tech_fcf)
  queue.append((t+p['upstream_lag'],declaration))
  receipt=sum(a for due,a in queue if due==t)
  receivable=sum(a for due,a in queue if due>t)
  # Internal dividends increase only parent's accounting income, never group income.
  parent_op_profit=nopat*p['parent_operating_share']
  parent_profit=parent_op_profit+declaration+treasury_income*.79-treasury_loss*.79-interest*.08
  profit_pre=profit_stock+parent_profit
  parent_flow=(nopat+da-capex-dwc)*p['parent_operating_share']+receipt+treasury_income*.79-interest*.08+(asset_sale-asset_sale_tax)*.79-treasury_loss*.79
  internal_settlement=p['parent_extra_settlement'] if t==1 else 0.
  parent_pre=parent_cash+parent_flow-old_claim-engineering*.27-internal_settlement+financing['draw']-financing['repay']
  parent_minimum=minimum*.5+lock_end*.79
  planned=max(nopat-o['minority_share']*lixin_profit,0)*p['payout']
  if t in p['special_years']:
   planned+=max(cash_pre-minimum-lock_end-planned,0)*p['release_fraction']
  distribution=min(planned,max(cash_pre-minimum-lock_end,0),max(parent_pre-parent_minimum,0),max(profit_pre,0)) if feasible else 0.
  cash_end=cash_pre-distribution;parent_end=parent_pre-distribution;profit_end=profit_pre-distribution
  if parent_end<0:feasible=False
  capital_end=capital+capex-da
  row=dict(year=t,year_end=f'{2026+t}-10-26',revenue=revenue,ebit=ebit,cash_tax=tax,nopat=nopat,depreciation=da,capex=capex,engineering_old_claim_paid=engineering,nwc_open=nwc,nwc_end=nwc_end,delta_nwc=dwc,operating_capital_end=capital_end+nwc_end+minimum,fcf_common=fcf,lixin_profit_100pct=lixin_profit,lixin_capital_delta_100pct=lixin_capital_delta,minority_fcfe=minority_fcfe,cash_open=cash,treasury_income_net=treasury_income,financial_principal_released=asset_sale,financial_realization_tax=asset_sale_tax,treasury_loss=treasury_loss,old_dividend_claim_paid=old_claim,interest=interest,debt_open=debt,debt_draw=financing['draw'],debt_repaid=financing['repay'],debt_end=debt_end,financing_shortfall=financing['shortfall'],minimum_operating_cash=minimum,locked_cash_end=lock_end,cash_before_distribution=cash_pre,planned_distribution=planned,distribution=distribution,dps=distribution/SHARES,cash_end=cash_end,parent_cash_open=parent_cash,parent_operating_profit=parent_op_profit,tech_profit_budget=tech_profit,tech_cash_available_budget=tech_fcf,tech_dividend_declared=declaration,tech_dividend_received=receipt,parent_dividend_receivable_end=receivable,parent_profit=parent_profit,parent_profit_stock_open=profit_stock,parent_profit_stock_end=profit_end,parent_flow=parent_flow,parent_internal_settlement=internal_settlement,parent_cash_before_distribution=parent_pre,parent_minimum_cash=parent_minimum,parent_cash_end=parent_end,feasible=feasible)
  assert abs(cash_end-(cash+nopat+da-dwc-minority_fcfe+treasury_income+asset_sale-asset_sale_tax-treasury_loss-capex-engineering-old_claim-interest+financing['draw']-financing['repay']-distribution))<1e-7
  assert abs(parent_end-(parent_cash+parent_flow-old_claim-engineering*.27-internal_settlement+financing['draw']-financing['repay']-distribution))<1e-7
  row['mexico_ebit_included']=p['mexico_ebit'][t-1]
  row['linear_ebit_included']=p['linear_ebit'][t-1]
  row['other_ebit_residual']=ebit-row['mexico_ebit_included']-row['linear_ebit_included']
  for key in ['ar','notes','inventory','prepayments','other_operating_assets','trade_payable','customer_advance','salary_tax','other_operating_liability']:
   row['wc_'+key]=o[key]*revenue/o['revenue']
  row['wc_ar']+=nwc_end-o['nwc']*revenue/o['revenue']
  out.append(row);nwc=nwc_end;capital=capital_end;cash=cash_end;debt=debt_end;parent_cash=parent_end;profit_stock=profit_end
 terminal=None;value=None;value2=None;tv5=None;tv52=None;terminal_fraction=None;terminal_bridge=None
 if feasible:
  last=out[-1];next_nopat=(last['nopat']-o['minority_share']*last['lixin_profit_100pct'])*(1+p['g'])
  # Sustainable incremental return bounded by actual cash and working-capital intensity.
  roic=min(p['terminal_roic'],max(.001,(last['nopat']-o['minority_share']*last['lixin_profit_100pct'])/max(last['operating_capital_end'],1e-15)))
  growth_reinvestment=next_nopat*p['g']/roic
  physical_reinvestment=last['revenue']*(1+p['g'])*(p['capex_ratio'][-1]-p['da_ratio'])+p['g']*(last['nwc_end']+last['minimum_operating_cash'])
  sustainable=next_nopat-max(growth_reinvestment,physical_reinvestment)
  if sustainable<0 or p['r']<=p['g']:
   feasible=False
  else:
   excess=cash-last['minimum_operating_cash']-debt
   # no-new-upstream is a persistent remittance constraint, not automatic unrestricted TV.
   remittance_factor=1. # blocked ten-year scenario resumes in Y11, not a perpetual cash trap
   continuing=sustainable/(p['r']-p['g'])*remittance_factor
   # Excess cash has a finite two-year realization budget, with 2% cost/tax friction.
   treasury_value=excess*.98/(1+p['r'])**2
   terminal=continuing+treasury_value
   terminal2=next_nopat*p['terminal_multiple']*remittance_factor+treasury_value
   divpv=sum(x['distribution']/(1+p['r'])**x['year'] for x in out)
   value=(divpv+terminal/(1+p['r'])**years)/SHARES
   value2=(divpv+terminal2/(1+p['r'])**years)/SHARES
   tv5=(sum(x['distribution']/(1+p['r'])**(x['year']-5) for x in out if x['year']>5)+terminal/(1+p['r'])**(years-5))/SHARES
   tv52=(sum(x['distribution']/(1+p['r'])**(x['year']-5) for x in out if x['year']>5)+terminal2/(1+p['r'])**(years-5))/SHARES
   terminal_fraction=terminal/(1+p['r'])**years/(value*SHARES)
   terminal_bridge=dict(year=years,next_common_nopat=next_nopat,effective_roic=roic,growth_reinvestment=growth_reinvestment,physical_reinvestment=physical_reinvestment,sustainable_common_cash=sustainable,continuing_value=continuing,excess_cash_before_friction=excess,excess_realization_year=years+2,excess_realization_friction=.02,treasury_value=treasury_value,earnings_continuing_value=next_nopat*p['terminal_multiple'],parent_profit_stock=profit_stock,release_condition='恒立科技及其他全资法人累计合法可分利润在Y11–12宣派到账；普通金融收益正常纳税；未假设资本返还或注销营业实体')
 return {'parameters':p,'annual':out,'feasible':feasible,'value_dcf_per_share':value,'value_earnings_crosscheck_per_share':value2,'d1_d5':[x['dps'] for x in out[:5]],'year5_terminal_dcf_per_share':tv5,'year5_terminal_crosscheck_per_share':tv52,'year10_terminal_total':terminal,'terminal_pv_fraction':terminal_fraction,'terminal_bridge':terminal_bridge}

def all_output():
 return {'symbol':SYMBOL,'name':NAME,'report_period':'2026-Q3','model_as_of':ASOF,'currency':'CNY','amount_unit':'CNY billion; per share CNY','shares_billion':SHARES,'opening':OPEN,'economic_not_legal_certification':True,'cases':{k:run(v) for k,v in cases().items()}}

def write(dest):
 dest.mkdir(parents=True,exist_ok=True);obj=all_output();data=(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();(dest/'2026-Q3-output.json').write_bytes(data)
 with (dest/'2026-Q3-years.csv').open('w',newline='') as f:
  rows=[{'scenario':k,**r} for k,v in obj['cases'].items() for r in v['annual']];w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 summary={k:{a:v[a] for a in ['feasible','value_dcf_per_share','value_earnings_crosscheck_per_share','d1_d5','year5_terminal_dcf_per_share','terminal_pv_fraction']} for k,v in obj['cases'].items()}
 (dest/'2026-Q3-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'symbol':SYMBOL,'output_sha256':hashlib.sha256(data).hexdigest(),'cases':len(summary)},ensure_ascii=False))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--output',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parent);write(a.parse_args().output)

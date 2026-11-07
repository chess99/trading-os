"""思源电气2026Q3：十亿元/十亿股。实际分配逐年滚动；不存在现价输入。
Y1-Y15为截止后年度现金预算，营业预测以相邻公历年度代表，非公司承诺。
"""
import json,copy,gzip,base64,hashlib,sys
from pathlib import Path
SHARES=.795034532
# H1母公司权益变动表pp51-52：已宣派股利先冲未分配利润，7月付款不二扣。
MOTHER_LEGAL_BRIDGE={'opening_2025':6.85349635421,'h1_net_profit':1.96832846134,'h1_declared_dividend':.54771576213,'h1_closing':8.27410905342,'additional_post_h1_declared':0.}
MOTHER_LEGAL0=MOTHER_LEGAL_BRIDGE['opening_2025']+MOTHER_LEGAL_BRIDGE['h1_net_profit']-MOTHER_LEGAL_BRIDGE['h1_declared_dividend']-MOTHER_LEGAL_BRIDGE['additional_post_h1_declared']
OPENING={'cash':3.76409683288,'trading':4.25769347219,'debt_investment':.30507739726,'other_financial':.12922305852,
'restricted':.33799333991,'operating_cash':2.5,'borrowings_and_leases':.95979383065,'minority_financial':.15}
EXCESS=sum(OPENING[k] for k in ['cash','trading','debt_investment','other_financial'])-sum(OPENING[k] for k in ['restricted','operating_cash','borrowings_and_leases','minority_financial'])
BASE={'revenue0':26.5,'profit0':3.5,'growth':[.17,.15,.12,.10,.08,.07,.06,.05,.04,.03]+[.03]*5,
'margins':[.132,.134,.135,.135,.135,.134,.133,.132,.131,.13]+[.13]*5,
'capital_intensity':.45,'terminal_roic':.18,'g':.03,'payout':[.20]*5+[.25,.30,.40,.50,.60,.70,.80,1.,1.,1.],
'cash_yield':.015,'mother_direct_profit':.20,'upstream_rate':[.40]*5+[.50,.60,.70,.80,.90]+[1.]*5,
'arrival':[.80]*5+[.85,.90,.95,1.,1.]+[1.]*5,'mother_cash0':2.,'mother_legal0':MOTHER_LEGAL0,
'sub_legal0':0.,'receivable0':0.,'wc_shocks':[0.]*15,'parent_payments':[0.]*15,'r':.095,'excess0':EXCESS,
'shares':SHARES,'extra_borrowing_rate':.05,'option_exercise':True,'special_release_start':11,'special_release_end':15,
'effective':'Y1起合并经营主体和付款母公司。Y6起分红率/上划率渐升；Y11-Y15合法储备支持特别分配，Y13起正常分配经济现金。'}

# Registered capital is not mother investment cost or latest option share count.
BASE.update(mother_registered0=.777642620,mother_paid0=.786762975,mother_statutory0=.388821310,
 source_buffer_rate=.10,source_buffer_until=10,source_buffer_tail=0.,release_rate=.10,
 illiquid_book=.12922305852,mother_illiquid_book=.10261164646,illiquid_net=.80,illiquid_year=10,
 deposit_book=.30507739726,deposit_face=.30,deposit_year=2,deposit_net_yield=.0175*.75,
 new_energy_subscription=.4,subscription_year=1,subscription_capex_year=1,horizon=400,
 debt_limit=2.,liquidity_loan_limit=1.,extra_net_tax_rate=0.,register_options=True,
 economic_source_haircut=0.)

def legal_step(retained,profit,rate,registered=None,reserve=0.):
 eligible=max(0.,profit-max(0.,-retained));add=eligible*rate
 if registered is not None:add=min(add,max(0.,registered*.5-reserve))
 return retained+profit-add,add

def operate(p,years=None):
 years=years or len(p['growth']);rev=p['revenue0'];prevprofit=p['profit0'];prevcore=rev*p['margins'][0]
 # Noncash principal is not distributable cash at t0. Subscription .4 remains mother earmark until paid.
 cash0=p['excess0']-p['deposit_book']-p['illiquid_book']
 mother=p['mother_cash0']+p['new_energy_subscription'];sub=cash0-mother
 ml=p['mother_legal0'];sl=p['sub_legal0'];ar=p['receivable0'];debt=0.;rows=[];ic=13.
 reserve=p['mother_statutory0'];registered=p['mother_registered0'];paidcap=p['mother_paid0']
 earmark=p['new_energy_subscription'];project_cash=0.;project_capital=.2;project_paid=None;deposit=p['deposit_book'];deposit_accrual=0.;loan=0.
 for i in range(years):
  y=i+1;g=p['growth'][i] if i<len(p['growth']) else p['g'];margin=p['margins'][i] if i<len(p['margins']) else p['margins'][-1]
  oldrev=rev;rev*=1+g;capital_core=rev*margin;core=rev*(margin-p['extra_net_tax_rate'])
  shares=(.788772032 if i==0 else SHARES) if p['option_exercise'] else p['shares']
  subscription=(.002009057*43.8 if i==0 else (.0062625*(43.8-rows[0]['dps']) if i==1 else 0.)) if p['option_exercise'] else 0.
  # Future registry catch-up and option registration are a dated budget, not already completed disclosure.
  if p['register_options']:registered=shares
  paidcap=shares
  mi=mother*p.get('mother_cash_yield',p['cash_yield']);si=sub*p.get('source_cash_yield',p['cash_yield'])-debt*p['extra_borrowing_rate']
  deposit_income=p['deposit_face']*p['deposit_net_yield'] if deposit else 0.;deposit_accrual+=deposit_income
  profit=core+mi+si+deposit_income
  shock=p['wc_shocks'][i] if i<len(p['wc_shocks']) else 0.
  reinvest=(max(0.,rev-oldrev)*p['capital_intensity'] if i<10 else max(0.,capital_core-prevcore)/p['terminal_roic'])+shock
  ic+=reinvest;fcfe=profit-reinvest
  direct=p['mother_direct_profit']*((1+p['g'])**max(0,y-15))
  mother_net=direct+mi-.10*reinvest;sub_net=core-direct+si-.90*reinvest
  settlement=p['parent_payments'][i] if i<len(p['parent_payments']) else 0.
  mc=mother+mother_net+subscription-settlement;sc=sub+sub_net+settlement
  source_cost=max(0.,core-direct)*p['economic_source_haircut'];sc-=source_cost;profit-=source_cost;fcfe-=source_cost
  newcapital=0.;project_spent=0.
  if y==p['subscription_year']:
   newcapital=earmark;mc-=newcapital;sc+=newcapital;project_cash+=newcapital;earmark=0.;project_capital=.6;project_paid=newcapital
  # This is part of the existing 90% source investment, not a second group outflow.
  if y>=p['subscription_capex_year']:
   project_spent=min(project_cash,max(0.,.90*reinvest));project_cash-=project_spent
  net_realization=0.;mother_guard=source_guard=0.;deposit_cash=0.
  if y==p['deposit_year']:
   deposit_cash=deposit+deposit_accrual;mc+=deposit_cash;deposit=0.;deposit_accrual=0.
  if y==p['illiquid_year']:
   mb=min(p['mother_illiquid_book'],p['illiquid_book']);sb=p['illiquid_book']-mb
   mc+=mb*p['illiquid_net'];sc+=sb*p['illiquid_net'];net_realization=p['illiquid_book']*p['illiquid_net']
   mother_guard=mb*(1-p['illiquid_net']);source_guard=sb*(1-p['illiquid_net'])
  # Source is a conditional after-loss economic budget, NOT common legal reserves.
  rate=p['source_buffer_rate'] if y<=p['source_buffer_until'] else p['source_buffer_tail']
  sl,buffer=legal_step(sl,core-direct+si-source_cost-source_guard,rate)
  old_paid=min(ar,max(0.,sc-project_cash));sc-=old_paid;mc+=old_paid;ar-=old_paid
  ordinary_rate=p['upstream_rate'][i] if i<len(p['upstream_rate']) else p['upstream_rate'][-1]
  arrival=p['arrival'][i] if i<len(p['arrival']) else p['arrival'][-1]
  special=p['special_release_start']<=y<=p['special_release_end'];remaining=max(1,p['special_release_end']-y+1)
  release=(1/remaining if special else (p['release_rate'] if y>p['special_release_end'] else 0.))
  ordinary_up=max(0.,sub_net-source_cost)*ordinary_rate
  special_up=max(0.,sc-project_cash-ar-ordinary_up)*release
  declared=min(ordinary_up+special_up,max(0.,sl),max(0.,sc-project_cash-ar));newpaid=declared*arrival
  sc-=newpaid;mc+=newpaid;ar+=declared-newpaid;sl-=declared
  ml,addition=legal_step(ml,direct+mi+deposit_income+declared-mother_guard,.10,registered,reserve);reserve+=addition
  # Temporary funding is explicit, capped and recorded; intercompany loan is not dividend profit.
  internal=0.
  if sc<project_cash:
   internal=min(project_cash-sc,max(0.,mc-earmark),max(0.,p['liquidity_loan_limit']-loan));mc-=internal;sc+=internal;loan+=internal
  repay_internal=min(loan,max(0.,sc-project_cash-ar));sc-=repay_internal;mc+=repay_internal;loan-=repay_internal
  finance=max(0.,project_cash-sc)+max(0.,earmark-mc)
  if debt+finance>p['debt_limit']+1e-9:raise ValueError('unfunded finite borrowing capacity')
  top=max(0.,earmark-mc);mc+=top;sc+=finance-top;debt+=finance
  repay=min(debt,max(0.,mc-earmark)+max(0.,sc-project_cash-ar));take=min(repay,max(0.,mc-earmark));mc-=take;sc-=repay-take;debt-=repay
  payout=p['payout'][i] if i<len(p['payout']) else p['payout'][-1]
  requested=max(0.,prevprofit*payout) if payout<1 else max(0.,fcfe)
  special_requested=max(0.,mc+sc-earmark-project_cash-requested-debt)*release
  div=min(requested+special_requested,max(0.,mc-earmark),max(0.,ml),max(0.,mc+sc-earmark-project_cash-debt))
  mother=mc-div;sub=sc;ml-=div;cash=mother+sub
  oldcash=rows[-1]['cash'] if rows else cash0
  # Deposit income was accrued off-cash, then paid once at maturity. Net investments similarly not new profit.
  assert abs(cash-oldcash-(fcfe-deposit_income)-subscription-finance+repay+div-net_realization-deposit_cash)<1e-7
  assert min(mother,sub,reserve)>=-1e-8
  rows.append(dict(year=2027+i,year_index=y,revenue=rev,core_profit=core,financial_income=mi+si+deposit_income,profit=profit,reinvest=reinvest,fcfe=fcfe,
   regular_requested=requested,special_requested=special_requested,requested_dividend=requested+special_requested,dividend=div,dps=div/shares,shares=shares,cash=cash,debt=debt,finance=finance,debt_repaid=repay,
   option_subscription=subscription,mother_cash=mother,subsidiary_cash=sub,mother_legal_profit_reserve=ml,source_earnings_budget=sl,source_profit_buffer=buffer,
   declared_upstream=declared,upstream_received=old_paid+newpaid,upstream_receivable=ar,mother_operating_net_cash=mother_net,
   parent_settlement=settlement,internal_liquidity_transfer=internal,internal_loan_repaid=repay_internal,internal_loan=loan,invested_capital=ic,
   mother_registered=registered,mother_paid=paidcap,mother_statutory=reserve,mother_statutory_add=addition,
   new_energy_capital_transfer=newcapital,new_energy_registered_budget=project_capital,new_energy_incremental_cash_paid_budget=project_paid,new_energy_capex_in_existing_group_investment=project_spent,project_restricted_cash=project_cash,mother_subscription_earmark=earmark,
   deposit_cash=deposit_cash,deposit_accrual_income=deposit_income,illiquid_net_realization=net_realization,mother_realization_guard=mother_guard,source_realization_guard=source_guard,economic_realization_book_loss=mother_guard+source_guard,source_cash_friction=source_cost))
  prevprofit=profit;prevcore=capital_core
 return rows

def principal_review(p,rows):
 records={};source={};mother={}
 def add(name,amount,at_source):
  records[name]=dict(net_principal=amount,paid=0.,last_year=None);mother[name]=0. if at_source else amount
  if at_source:source[name]=amount
 cash0=p['excess0']-p['deposit_book']-p['illiquid_book']
 add('mother_opening_free',p['mother_cash0'],False)
 add('source_opening_free',cash0-p['mother_cash0']-p['new_energy_subscription'],True)
 for row in rows:
  if row['deposit_cash']:add('mother_deposit_book',p['deposit_book'],False)
  if row['illiquid_net_realization']:
   mb=min(p['mother_illiquid_book'],p['illiquid_book']);add('mother_noncore_net',mb*p['illiquid_net'],False);add('source_noncore_net',(p['illiquid_book']-mb)*p['illiquid_net'],True)
  up=row['upstream_received']+row['internal_loan_repaid']
  for name in source:
   take=min(up,source[name]);source[name]-=take;mother[name]+=take;up-=take
  paid=row['dividend']
  for name in mother:
   take=min(paid,mother[name]);mother[name]-=take;paid-=take
   if take>1e-12:records[name]['paid']+=take;records[name]['last_year']=row['year_index']
 for v in records.values():v['unpaid']=v['net_principal']-v['paid']
 cohorts={}
 for checkpoint in [5,20,80,160]:
  at=rows[checkpoint-1];m=max(0.,at['mother_cash']-at['mother_subscription_earmark']);src=max(0.,at['subsidiary_cash']-at['project_restricted_cash']);left=src;pending=m;paid=0.;last=None
  for r in rows[checkpoint:]:
   take=min(left,r['upstream_received']+r['internal_loan_repaid']);left-=take;pending+=take;take=min(pending,r['dividend']);pending-=take;paid+=take
   if take>1e-12:last=r['year_index']
  cohorts[str(checkpoint)]=dict(mother_free=m,source_free=src,paid=paid,last_year=last,unpaid=left+pending)
 return dict(initial_financial_principal=records,later_cash_cohorts=cohorts,note='FIFO attribution to actual common payments only, no added value. New-energy .4 transferred and spent within required operating investment, not an additional idle financial asset. No internal liquidity loans used in published paths.')

def value(p):
 a=operate(p,p['horizon']);r=p['r']
 tail=sum(x['dps']/(1+r)**(i-4) for i,x in enumerate(a) if i>=5)
 pvdiv=sum(x['dps']/(1+r)**(i+1) for i,x in enumerate(a[:5]));present=pvdiv+tail/(1+r)**5
 return {'value_per_share':present,'terminal_per_share':tail,'terminal_pv_share':(tail/(1+r)**5)/present,
 'perpetuity_pv_share':None,'mature_next_cash':a[15]['fcfe'],
 'distributions_per_share':[x['dps'] for x in a[:5]],'rows':a[:15],'tail_rows':a[15:],
 'principal_realization':principal_review(p,a),
 'terminal_method':'actual all future common payments; no terminal balance sweep or automatic group FCFE perpetuity'}

def residual(p,terminal_roe):
 # A deliberately different capitalisation of total retained equity, using actual cash distributions and matched equity issuance.
 a=operate(p);book=17.56710050226;initial=book;r=p['r'];pv=0.
 for i,x in enumerate(a[:10]):
  loss=x['economic_realization_book_loss'];pv+=(x['profit']-loss-r*book+x['option_subscription'])/(1+r)**(i+1);book+=x['profit']-loss-x['dividend']+x['option_subscription']
 terminal=book*(terminal_roe-r)/(r-p['g'])
 return {'value_per_share':(initial+pv+terminal/(1+r)**10)/p['shares']+sum((x['dps']-x['dividend']/p['shares'])/(1+r)**(i+1) for i,x in enumerate(a[:10])),'opening_common_book':initial,'closing_book':book,'terminal_roe':terminal_roe,'mature_payout':1-p['g']/terminal_roe}

def permanent_low_payout(p):
 z=copy.deepcopy(p);z['payout']=[.20]*15;z['upstream_rate']=[.4]*15;z['arrival']=[.8]*15
 z['special_release_start']=1000;z['special_release_end']=1001
 return value(z)

def production_tests():
 p=copy.deepcopy(BASE);p.update(revenue0=1.,profit0=1.,growth=[0.]*15,margins=[1.]*15,capital_intensity=0.,g=0.,payout=[1.]*15,upstream_rate=[0.]*15,arrival=[1.]*15,mother_direct_profit=1.,cash_yield=0.,excess0=0.,mother_cash0=0.,new_energy_subscription=0.,deposit_book=0.,deposit_face=0.,illiquid_book=0.,mother_illiquid_book=0.,option_exercise=False,shares=1.,mother_registered0=1.,mother_paid0=1.,mother_statutory0=.5,mother_legal0=0.,source_buffer_rate=0.,special_release_start=1000,special_release_end=1001,r=.1)
 v=value(p);assert abs(v['value_per_share']-10)<1e-10
 p.update(revenue0=10.,profit0=10.,mother_direct_profit=10.,shares=10.,mother_registered0=20.,mother_paid0=10.,mother_statutory0=5.,register_options=False)
 row=operate(p,1)[0];assert row['mother_statutory_add']==1 and row['dividend']==9
 retained=0.;reserve=5.;trace=[]
 for profit in [-.5,.3,.3]:
  retained,add=legal_step(retained,profit,.1,20.,reserve);reserve+=add;pay=max(0.,retained);retained-=pay;trace.append(dict(profit=profit,reserve_added=add,distribution=pay,retained=retained))
 assert [round(q['distribution'],8) for q in trace]==[0.,0.,.09]
 return dict(actual_perpetuity=v['value_per_share'],registered20_paid10_reserve5_profit10=row,loss_recovery_same_production_legal_function=trace)

def make():
 low=copy.deepcopy(BASE);low['r']=.10;high=copy.deepcopy(BASE);high['r']=.09
 weak=copy.deepcopy(BASE);weak.update(growth=[.03,.07,.18,.14,.10,.07,.06,.05,.04,.03]+[.03]*5,margins=[.11,.12,.13,.135,.135,.134,.133,.132,.131,.13]+[.13]*5,wc_shocks=[1.8,0.,-.9,-.9]+[0.]*11,parent_payments=[.8]+[0.]*14,arrival=[.5,.5]+BASE['arrival'][2:],effective='Y1-Y2交付及回款延迟，母公司额外结算8亿元；Y3-Y4释放18亿元周转占用；成熟回报、股数和后期分配政策冻结。')
 bad=copy.deepcopy(BASE);bad.update(growth=[.08,.06,.04,.03,.03,.03,.03,.03,.03,.03]+[.02]*5,margins=[.11,.10,.095]+[.09]*12,capital_intensity=.65,terminal_roic=.11,g=.02,wc_shocks=[2.5]+[0.]*14,parent_payments=[1.5]+[0.]*14,upstream_rate=[.25]*5+BASE['upstream_rate'][5:],arrival=[.5]*5+BASE['arrival'][5:],option_exercise=False,shares=.786762975,effective='Y1起核心设备价格/客户结构永久恶化，集团25亿元新增周转占用不回转；付款母公司额外结算15亿元；前五年上划下降、尚未执行的期权假设最终不行权，股数和认款同时取消（不表示已成就资格被撤销）；后期分配目标冻结，实际分配自动受约束。')
 good=copy.deepcopy(BASE);good.update(growth=[.22,.20,.17,.14,.11,.09,.07,.05,.04,.03]+[.03]*5,margins=[.14,.145,.15,.15,.15,.145,.14,.135,.132,.13]+[.13]*5,capital_intensity=.48,effective='Y1起海外高压设备销量/净价兑现，更多扩产同步占款；母子付款和后期分配规则冻结。')
 delayed=copy.deepcopy(BASE)
 delayed['growth'] += [.03]*5;delayed['margins'] += [.13]*5;delayed['payout'] += [1.]*5;delayed['upstream_rate'] += [1.]*5;delayed['arrival'] += [1.]*5;delayed['wc_shocks'] += [0.]*5;delayed['parent_payments'] += [0.]*5
 delayed.update(special_release_start=16,special_release_end=20,effective='Y11起母公司为海外资金调回及未来收购保留额外现金，特别分配从Y11-15整体延后到Y16-20；收入、利润率、必要资本、常规分红及上划规则冻结；现金按1.5%赚取收入并逐期进入实际分配。')
 result={'units':'CNY billion; billion shares','information_cutoff':'2026-10-26T00:00:00+08:00','opening_bridge':OPENING,'mother_legal_opening_bridge':MOTHER_LEGAL_BRIDGE,'excess0':EXCESS,'inputs':BASE,
 'core_low':value(low),'core_high':value(high),'base':value(BASE),'scenarios':{k:{'inputs':p,'output':value(p)} for k,p in [('cyclical_weak',weak),('structural_adverse',bad),('optimistic',good),('delayed_release',delayed)]},
 'auxiliary_residual_income':{'low':residual(low,.12),'high':residual(high,.14)}}
 sens=copy.deepcopy(BASE);sens['capital_intensity']=.60;result['sensitivity_capital_060']=value(sens)['value_per_share']
 result['permanent_20pct_payout_diagnostic']=permanent_low_payout(BASE)
 result['capital_governance']={}
 for key,updates in {'source_net_financial_yield1pct':dict(source_cash_yield=.01),'mother_net_financial_yield1pct':dict(mother_cash_yield=.01),'net_financial_yield0_5pct':dict(cash_yield=.005),'source_buffer_zero':dict(source_buffer_rate=0.),'source_buffer_forever':dict(source_buffer_tail=.1),'source_50pct_forever':dict(upstream_rate=[.4]*5+[.5]*10),'special_release_none_but_10pct_later':dict(special_release_start=16,special_release_end=15),'release_delayed25':dict(special_release_start=21,special_release_end=25),'net_tax_plus_1pp':dict(extra_net_tax_rate=.01),'source_cash_friction_2pct_profit':dict(economic_source_haircut=.02),'noncore_net50pct':dict(illiquid_net=.5),'noncore_year15':dict(illiquid_year=15),'deposit_year5':dict(deposit_year=5),'old_dividend_still_pending':dict(receivable0=.7929904,mother_cash0=2.-.7929904),'all_minority_equity_financial_boundary':dict(excess0=EXCESS-(.444661809-.15)),'capital_payment_year2':dict(subscription_year=2,subscription_capex_year=2),'mother_legal_zero':dict(mother_legal0=0.),'mother_statutory_zero_boundary':dict(mother_statutory0=0.),'mother_statutory_group_amount_boundary':dict(mother_statutory0=.33309767575),'horizon500':dict(horizon=500)}.items():
  q=copy.deepcopy(BASE);q.update(updates);result['capital_governance'][key]=value(q)
 q=copy.deepcopy(bad);q['deposit_year']=5;result['capital_governance']['structural_deposit_year5']=value(q)
 result['production_tests']=production_tests()
 return result

def canonical_bytes(o):
 return json.dumps(o,ensure_ascii=False,separators=(',',':')).encode('utf-8')

def pack_output(o):
 def summary(x):
  if isinstance(x,dict):return {k:summary(v) for k,v in x.items() if k not in ('rows','tail_rows')}
  if isinstance(x,list):return [summary(v) for v in x]
  return x
 raw=canonical_bytes(o);p=summary(o)
 p['_complete_output']={'encoding':'gzip-mtime0-base64-json-utf8','expanded_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'schema':'Complete original object including rows (Y1-15), tail_rows (Y16 onward), every year, economic field, scenario and diagnostic. Other top-level fields are readable summaries, not full annual traces. Monetary units CNY billion except per-share and indicated units.','expand_command':'python 2026-Q3.py --expand 2026-Q3-output.json expanded.json','data':base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode('ascii')}
 assert expand_output(p)==o
 return p

def expand_output(o):
 a=o['_complete_output'];raw=gzip.decompress(base64.b64decode(a['data']))
 assert len(raw)==a['expanded_bytes'] and hashlib.sha256(raw).hexdigest()==a['sha256']
 return json.loads(raw)

if __name__=='__main__':
 if len(sys.argv)==4 and sys.argv[1]=='--expand':
  src=json.loads(Path(sys.argv[2]).read_text());Path(sys.argv[3]).write_bytes(canonical_bytes(expand_output(src)))
 else:
  o=make();Path(__file__).with_name('2026-Q3-output.json').write_bytes(canonical_bytes(pack_output(o)));print({k:round(o[k]['value_per_share'],4) for k in ['core_low','core_high','base']})

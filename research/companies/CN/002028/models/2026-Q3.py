"""思源电气2026Q3：十亿元/十亿股。实际分配逐年滚动；不存在现价输入。
Y1-Y15为截止后年度现金预算，营业预测以相邻公历年度代表，非公司承诺。
"""
import json,copy
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

def operate(p):
 rev=p['revenue0'];prevprofit=p['profit0'];prevcore=rev*p['margins'][0]
 mother=p['mother_cash0'];sub=p['excess0']-mother;ml=p['mother_legal0'];sl=p['sub_legal0'];ar=p['receivable0'];debt=0.;rows=[];ic=13.
 for i,(g,margin) in enumerate(zip(p['growth'],p['margins'])):
  y=i+1; oldrev=rev;rev*=1+g;core=rev*margin
  shares=(.788772032 if i==0 else SHARES) if p['option_exercise'] else p['shares']
  mi=mother*p['cash_yield'];si=sub*p['cash_yield']-debt*p['extra_borrowing_rate'];profit=core+mi+si
  reinvest=(max(0.,rev-oldrev)*p['capital_intensity'] if i<10 else max(0.,core-prevcore)/p['terminal_roic'])+p['wc_shocks'][i]
  ic+=reinvest;fcfe=profit-reinvest
  subscription=(.002009057*43.8 if i==0 else (.0062625*(43.8-rows[0]['dps']) if i==1 else 0.)) if p['option_exercise'] else 0.
  direct=p['mother_direct_profit'];mother_net=direct+mi-.10*reinvest;sub_net=core-direct+si-.90*reinvest
  mc_before=mother+mother_net+subscription-p['parent_payments'][i]
  sc_before=sub+sub_net+p['parent_payments'][i] # specified parent-to-sub settlement; not an external group cost
  ml_before=ml+.90*max(0.,direct+mi);sl_before=sl+.90*max(0.,core-direct+si)
  # Internal liquidity loan precedes outside funding; neither creates earnings.
  transfer=0.
  if sc_before<0:
   transfer=min(-sc_before,max(0.,mc_before));mc_before-=transfer;sc_before+=transfer
  if mc_before<0:
   back=min(-mc_before,max(0.,sc_before-ar));mc_before+=back;sc_before-=back;transfer-=back
  finance=max(0.,-sc_before)+max(0.,-mc_before)
  if finance>2.: raise ValueError('unfunded outside-financing need exceeds bounded facility')
  if sc_before<0:sc_before=0.
  if mc_before<0:mc_before=0.
  debt+=finance
  # Existing declared dividend receivable is paid first: no new mother profit.
  old_paid=min(ar,max(0.,sc_before));sc_before-=old_paid;mc_before+=old_paid;ar-=old_paid
  special_phase=p['special_release_start']<=y<=p['special_release_end']
  remaining=max(1,p['special_release_end']-y+1)
  ordinary_up=max(0.,sub_net)*p['upstream_rate'][i]
  special_up=max(0.,sc_before-ar-ordinary_up)/remaining if special_phase else 0.
  declared=min(ordinary_up+special_up,max(0.,sl_before),max(0.,sc_before-ar))
  paid=declared*p['arrival'][i];sc_before-=paid;mc_before+=paid;ar+=declared-paid
  sl=sl_before-declared;ml_before+=declared # new dividend income once only, no reserve deduction on intercompany exempt income
  requested=max(0.,prevprofit*p['payout'][i]) if p['payout'][i]<1 else max(0.,fcfe)
  special_requested=max(0.,mc_before+sc_before-requested-debt)/remaining if special_phase else 0.
  target=requested+special_requested
  div=min(target,max(0.,mc_before),max(0.,ml_before),max(0.,mc_before+sc_before-debt))
  mother=mc_before-div;sub=sc_before;ml=ml_before-div;cash=mother+sub
  oldcash=rows[-1]['cash'] if rows else p['excess0']
  assert abs(cash-oldcash-fcfe-subscription-finance+div)<1e-8
  assert min(mother,sub,ml,sl)>=-1e-8
  rows.append(dict(year=2027+i,year_index=y,revenue=rev,core_profit=core,financial_income=mi+si,profit=profit,reinvest=reinvest,fcfe=fcfe,
   regular_requested=requested,special_requested=special_requested,requested_dividend=target,dividend=div,dps=div/shares,shares=shares,cash=cash,debt=debt,finance=finance,
   option_subscription=subscription,mother_cash=mother,subsidiary_cash=sub,mother_legal_profit_reserve=ml,subsidiary_common_legal_reserve=sl,
   declared_upstream=declared,upstream_received=old_paid+paid,upstream_receivable=ar,mother_operating_net_cash=mother_net,
   parent_settlement=p['parent_payments'][i],internal_liquidity_transfer=transfer,invested_capital=ic))
  prevprofit=profit;prevcore=core
 return rows

def value(p):
 a=operate(p);r=p['r'];n=len(a);g=p['g']
 # Mature distribution is generated through the same capital requirement; residual financial assets must have actually been paid.
 if a[-1]['cash']>1e-7 or a[-1]['debt']>1e-7 or a[-1]['upstream_receivable']>1e-7:
  raise ValueError('terminal financial principal not fully resolved; do not silently add it')
 mature_cash=a[-1]['core_profit']*(1+g)*(1-g/p['terminal_roic'])
 perpetuity=mature_cash/(r-g)
 tail=sum(x['dps']/(1+r)**(i-4) for i,x in enumerate(a) if i>=5)+perpetuity/p['shares']/(1+r)**(n-5)
 pvdiv=sum(x['dps']/(1+r)**(i+1) for i,x in enumerate(a[:5]));present=pvdiv+tail/(1+r)**5
 return {'value_per_share':present,'terminal_per_share':tail,'terminal_pv_share':(tail/(1+r)**5)/present,
 'perpetuity_pv_share':perpetuity/p['shares']/(1+r)**n/present,'mature_next_cash':mature_cash,
 'distributions_per_share':[x['dps'] for x in a[:5]],'rows':a}

def residual(p,terminal_roe):
 # A deliberately different capitalisation of total retained equity, using actual cash distributions and matched equity issuance.
 a=operate(p);book=17.56710050226;initial=book;r=p['r'];pv=0.
 for i,x in enumerate(a[:10]):
  pv+=(x['profit']-r*book+x['option_subscription'])/(1+r)**(i+1);book+=x['profit']-x['dividend']+x['option_subscription']
 terminal=book*(terminal_roe-r)/(r-p['g'])
 return {'value_per_share':(initial+pv+terminal/(1+r)**10)/p['shares']+sum((x['dps']-x['dividend']/p['shares'])/(1+r)**(i+1) for i,x in enumerate(a[:10])),'opening_common_book':initial,'closing_book':book,'terminal_roe':terminal_roe,'mature_payout':1-p['g']/terminal_roe}

def permanent_low_payout(p):
 # Diagnostic alternative: no policy change, no special dividends. Mature cash reinvested at1.5%; actual distributions only.
 z=copy.deepcopy(p);z['growth']+= [p['g']]*385;z['margins']+=[p['margins'][-1]]*385
 z['payout']=[.20]*400;z['upstream_rate']=[.4]*400;z['arrival']=[.8]*400;z['wc_shocks']+=[0.]*385;z['parent_payments']+=[0.]*385
 z['special_release_start']=1000;z['special_release_end']=1001
 a=operate(z)
 return sum(x['dps']/(1+p['r'])**(i+1) for i,x in enumerate(a))

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
 return result
if __name__=='__main__':
 o=make();Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(o,ensure_ascii=False,indent=2));print({k:round(o[k]['value_per_share'],4) for k in ['core_low','core_high','base']})

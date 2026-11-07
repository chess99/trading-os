#!/usr/bin/env python3
"""双汇2026Q3重建快照。标准库、自足输入；不能证明与已丢失旧包字节一致。金额十亿元。"""
import json,copy,pathlib,math
SHARES=3.464661213
ASOF='2026-10-27T21:05:30+00:00'
INITIAL_ASSETS=16.27
INITIAL_DEBT=12.98
OPERATING_CASH=2
REGULATORY_CASH=.65
CASES={
'base':dict(vol=[1.40,1.425,1.45,1.475,1.50],unit=[4400,4420,4440,4460,4480],slaughter=[.30,.34,.38,.42,.46],other=[-.40,-.35,-.30,-.25,-.20],capex=[1.9]*5,da=[1.6]*5,wc=[.20]*5,r=.09,g=.01,roic=.15,payout=.80,rate=.022,up=.88,delay=.15,settle=[.5,.25,.1,0,0],redemption=[0]*5),
'core_low':dict(vol=[1.38,1.40,1.42,1.44,1.46],unit=[4250,4270,4290,4310,4330],slaughter=[.25,.28,.31,.34,.37],other=[-.45,-.40,-.35,-.30,-.25],capex=[2.0]*5,da=[1.6]*5,wc=[.25]*5,r=.095,g=.005,roic=.13,payout=.80,rate=.025,up=.85,delay=.20,settle=[.7,.3,.1,0,0],redemption=[0]*5),
'core_high':dict(vol=[1.42,1.45,1.48,1.51,1.54],unit=[4500,4520,4540,4560,4580],slaughter=[.35,.40,.45,.50,.55],other=[-.35,-.30,-.25,-.20,-.15],capex=[1.9]*5,da=[1.6]*5,wc=[.20]*5,r=.085,g=.015,roic=.18,payout=.80,rate=.020,up=.90,delay=.10,settle=[.3,.1,0,0,0],redemption=[0]*5),
'cycle':dict(vol=[1.33,1.36,1.42,1.46,1.50],unit=[4000,4150,4350,4430,4480],slaughter=[-.10,.10,.25,.35,.46],other=[-.65,-.55,-.40,-.30,-.20],capex=[1.85,1.85,1.9,1.9,1.9],da=[1.6]*5,wc=[.70,.20,-.30,.1,.2],r=.095,g=.01,roic=.15,payout=.75,rate=.032,up=.80,delay=.30,settle=[1,.5,.2,0,0],redemption=[2,0,0,0,0]),
'structural':dict(terminal_maintenance_gap=.20,vol=[1.30,1.25,1.21,1.18,1.16],unit=[3900,3650,3450,3350,3300],slaughter=[0,-.1,-.1,0,0],other=[-.70,-.70,-.65,-.60,-.55],capex=[2,1.9,1.85,1.8,1.8],da=[1.6]*5,wc=[.8,.3,.1,0,0],r=.105,g=0,roic=.10,payout=.60,rate=.04,up=.70,delay=.40,settle=[1.5,.7,.3,.2,.2],redemption=[3,1,0,0,0]),
'upside':dict(vol=[1.46,1.52,1.58,1.64,1.70],unit=[4600,4650,4700,4750,4800],slaughter=[.45,.55,.65,.75,.85],other=[-.25,-.15,-.05,0,0],capex=[2.1]*5,da=[1.6,1.65,1.7,1.75,1.8],wc=[.25]*5,r=.08,g=.02,roic=.20,payout=.80,rate=.02,up=.90,delay=.10,settle=[.3,.1,0,0,0],redemption=[0]*5)}
def production(c,opening=INITIAL_ASSETS,debt0=INITIAL_DEBT,parent0=4.92685,legal0=4.30024,receivable0=1.104697,reserve0=1.831906632,registered_capital=SHARES,parent_debt0=5.104,minority_net_financial=.10):
 assets=opening-max(minority_net_financial,0);debt=debt0+min(minority_net_financial,0)
 parent,legal,receivable,reserve,parent_debt=parent0,legal0,receivable0,reserve0,parent_debt0
 rows=[]
 for i in range(5):
  meat=c['vol'][i]*c['unit'][i]/1000
  minority_financial_result=max(minority_net_financial,0)*.015+min(minority_net_financial,0)*c['rate']*.75
  minority_operating=.04-minority_financial_result
  op=meat*.75+c['slaughter'][i]*(.85 if c['slaughter'][i]>=0 else 1)+c['other'][i]-minority_operating
  interest=debt*c['rate']*.75;financial=max(assets-OPERATING_CASH,0)*.015
  profit=op+financial-interest
  fcf=profit+c['da'][i]-c['capex'][i]-c['wc'][i]-.04
  declaration=max(profit,0)*c['up']
  receipt=receivable+(1-c['delay'])*declaration
  new_receivable=c['delay']*declaration
  parent_interest=parent_debt*c['rate']*.75
  parent_financial_income=parent*.0142
  parent_operating=.25*c['vol'][i]/1.4
  direct=c.get('parent_direct_profit',[None]*5)[i]
  if direct is None:direct=parent_operating+parent_financial_income-parent_interest
  # 子公司宣派增加母体投资收益，旧应收到账不再增加利润；直接损益不截断负值。
  parent_income=declaration+direct
  profit_after_loss=max(0,parent_income+min(legal,0))
  reserve_transfer=min(max(0,registered_capital*.5-reserve),profit_after_loss*.10)
  legal_available=legal+parent_income-reserve_transfer
  reserve_new=reserve+reserve_transfer
  repayment=c['redemption'][i]
  parent_repayment=min(parent_debt,repayment*c.get('parent_repayment_share',.4))
  parent_before=parent+receipt+direct-.30-c['settle'][i]-parent_repayment
  group_before=assets+fcf-repayment
  target=max(profit,0)*c['payout']
  div=max(0,min(target,legal_available,parent_before-1.5,group_before-OPERATING_CASH-REGULATORY_CASH))
  a1=group_before-div;p1=parent_before-div;l1=legal_available-div;d1=debt-repayment;pd1=parent_debt-parent_repayment
  assert min(a1,p1,d1,pd1)>-1e-9
  assert abs(a1-assets-fcf+repayment+div)<1e-8
  assert abs(receivable+declaration-receipt-new_receivable)<1e-8
  assert abs(l1-legal-parent_income+reserve_transfer+div)<1e-8
  row=dict(year=i+1,meat_ebit=meat,minority_operating_profit=minority_operating,minority_financial_result=minority_financial_result,operating_common_nopat=op,financial_income=financial,interest=interest,common_profit=profit,da=c['da'][i],capex=c['capex'][i],wc=c['wc'][i],fcfe=fcf,dividend=div,dps=div/SHARES,assets=a1,debt=d1,parent_cash=p1,parent_profit=parent_income,parent_legal=l1,parent_statutory_reserve=reserve_new,parent_reserve_transfer=reserve_transfer,parent_direct_profit=direct,parent_debt=pd1,parent_interest=parent_interest,parent_financial_income=parent_financial_income,parent_operating_profit=parent_operating,parent_debt_repaid=parent_repayment,subsidiary_debt_repaid=repayment-parent_repayment,subs_declared=declaration,subs_received=receipt,dividend_receivable=new_receivable,net_internal_settlement=c['settle'][i],debt_repaid=repayment)
  rows.append(row)
  assets,debt,parent,legal,receivable,reserve,parent_debt=a1,d1,p1,l1,new_receivable,reserve_new,pd1
 r,g=c['r'],c['g'];gap=c.get('terminal_maintenance_gap',.05)
 terminal_cash=rows[-1]['operating_common_nopat']*(1+g)*(1-g/c['roic'])-gap-.04
 terminal_operating=terminal_cash/(r-g)
 years=c.get('reg_recovery',10)
 reserve_value=REGULATORY_CASH/(1+r)**years+sum(REGULATORY_CASH*.015/(1+r)**j for j in range(1,years+1))
 terminal_financial=assets-debt-OPERATING_CASH-REGULATORY_CASH+reserve_value
 terminal=(terminal_operating+terminal_financial)/SHARES
 pvdiv=sum(x['dividend']/(1+r)**x['year'] for x in rows)/SHARES;pvtv=terminal/(1+r)**5
 auxiliary=((rows[0]['operating_common_nopat']-gap-.04)/r+opening-minority_net_financial-debt0-OPERATING_CASH-REGULATORY_CASH+reserve_value)/SHARES
 return dict(rows=rows,current_value=pvdiv+pvtv,terminal_value=terminal,pv_dividends=pvdiv,terminal_pv_share=pvtv/(pvdiv+pvtv),terminal_operating=terminal_operating,terminal_financial_bridge=terminal_financial,regulatory_principal_value=reserve_value,auxiliary_no_growth_value=auxiliary)
def production_tests():
 c=copy.deepcopy(CASES['base']);c.update(vol=[1]*5,unit=[1000]*5,slaughter=[0]*5,other=[0]*5,da=[0]*5,capex=[0]*5,wc=[0]*5,payout=0,rate=0,up=0,settle=[0]*5,redemption=[0]*5)
 k=dict(opening=2.65,debt0=0,minority_net_financial=0,parent_debt0=0)
 z=production(c,**k)
 assert abs(z['rows'][0]['common_profit']-.71975)<1e-12
 assert abs(z['rows'][0]['fcfe']-.67975)<1e-12
 assert abs(z['rows'][0]['assets']-3.32975)<1e-12
 c.update(parent_direct_profit=[-.4,.2,.4,0,0],payout=1)
 z=production(c,**k,parent0=10,legal0=-.1,receivable0=0,reserve0=0,registered_capital=2)
 assert abs(z['rows'][0]['parent_legal']+.5)<1e-12
 assert abs(z['rows'][1]['parent_legal']+.3)<1e-12
 assert z['rows'][0]['dividend']==z['rows'][1]['dividend']==0
 assert abs(z['rows'][2]['parent_reserve_transfer']-.01)<1e-12
 assert abs(z['rows'][2]['dividend']-.09)<1e-12
 c['parent_direct_profit']=[.4,0,0,0,0]
 z=production(c,**k,parent0=10,legal0=0,receivable0=0,reserve0=.99,registered_capital=2)
 assert abs(z['rows'][0]['parent_reserve_transfer']-.01)<1e-12
 assert abs(z['rows'][0]['parent_statutory_reserve']-1)<1e-12
 assert abs(z['rows'][0]['dividend']-.39)<1e-12
 c=copy.deepcopy(CASES['base']);c['payout']=0;z=production(c)
 c['redemption']=[1,0,0,0,0];q=production(c)
 assert abs(z['rows'][0]['parent_cash']-q['rows'][0]['parent_cash']-.4)<1e-12
 assert abs(q['rows'][0]['parent_debt']-4.704)<1e-12
 assert abs(q['rows'][1]['parent_interest']-4.704*.022*.75)<1e-12
 # 少数净债本金与利息两者同时剥离；基准会计净利润不因所有者拆分改变。
 a=production(CASES['base'],minority_net_financial=-.1);b=production(CASES['base'],minority_net_financial=0)
 assert abs(a['rows'][0]['debt']-(INITIAL_DEBT-.1))<1e-12
 assert abs(a['rows'][0]['interest']-(INITIAL_DEBT-.1)*.022*.75)<1e-12
 assert abs(a['rows'][0]['common_profit']-b['rows'][0]['common_profit'])<1e-12
 return {'cash_hand_case':'passed .75-.04+.65*.015-.04=.67975; cash2.65->3.32975','legal_loss_to_profit':'capital2 retained-.1->-.5->-.3; then profit.4 reserve.01 dividend.09 passed','legal_reserve_cap':'capital2 reserve.99->1; transfer.01 dividend.39 passed','parent_repayment':'group repayment1 -> parent repayment.4; debt4.704 and next interest4.704*.022*.75 passed','minority_net_debt':'principal and interest removed, operating minority reconciles total net profit passed'}
def independent_literal(data):
 """不调用production，重新literal递推全部正式经营路径。"""
 checks=[]
 paths=list(data['inputs'].items())
 altered=dict(data['inputs']['base']);altered['unit']=[x-500 for x in altered['unit']]
 paths.append(('unit_minus_500',altered))
 for name,c in paths:
  a=16.17;b=12.98;pc=4.92685;lr=4.30024;ar=1.104697;reserve=1.831906632;pb=5.104;pv=0
  for n in range(5):
   e=c['vol'][n]*c['unit'][n]*.001*.75+c['slaughter'][n]*(.85 if c['slaughter'][n]>=0 else 1)+c['other'][n]-.0385
   profit=e+(a-2)*.015-b*c['rate']*.75
   free=profit+c['da'][n]-c['capex'][n]-c['wc'][n]-.04
   declare=max(0,profit)*c['up'];recv=ar+declare*(1-c['delay']);ar=declare*c['delay']
   pcost=pb*c['rate']*.75;direct=.25*c['vol'][n]/1.4+pc*.0142-pcost
   prep=min(pb,c['redemption'][n]*.4)
   income=declare+direct
   levy=min(max(0,3.464661213*.5-reserve),max(0,income+min(lr,0))*.1)
   reserve+=levy;lr+=income-levy
   pc+=recv+direct-.3-c['settle'][n]-prep
   a+=free-c['redemption'][n];b-=c['redemption'][n];pb-=prep
   paid=max(0,min(max(0,profit)*c['payout'],lr,pc-1.5,a-2.65))
   pc-=paid;lr-=paid;a-=paid;pv+=paid/(1+c['r'])**(n+1)
   reference=data['sensitivities'][name] if name=='unit_minus_500' else data['outputs'][name]
   ref=reference['rows'][n]
   for key,val in [('common_profit',profit),('fcfe',free),('assets',a),('debt',b),('parent_cash',pc),('parent_legal',lr),('dividend',paid),('dividend_receivable',ar),('parent_statutory_reserve',reserve),('parent_reserve_transfer',levy),('parent_debt',pb),('parent_debt_repaid',prep),('parent_interest',pcost)]:
    assert math.isclose(val,ref[key],rel_tol=1e-12,abs_tol=1e-11),(name,n,key)
  r=c['r'];g=c['g'];gap=c.get('terminal_maintenance_gap',.05)
  op=(e*(1+g)*(1-g/c['roic'])-gap-.04)/(r-g)
  reg=.65/(1+r)**10+.00975*(1-(1+r)**-10)/r
  tv=(op+a-b-2.65+reg)/3.464661213;value=pv/3.464661213+tv/(1+r)**5
  assert abs(tv-reference['terminal_value'])<1e-10
  assert abs(value-reference['current_value'])<1e-10
  checks.append(dict(case=name,value=value,terminal=tv,status='passed'))
 assert abs(data['outputs']['base']['rows'][0]['common_profit']-data['sensitivities']['unit_minus_500']['rows'][0]['common_profit']-.525)<1e-10
 return dict(method='independent literal, no production call',cases=checks,dominant_parameter='吨利-500元首年利润-5.25亿元 passed')

OTHER_BRIDGE = dict(units='亿元',h1_segment=-2.0600095931,q3_ytd_segment=-2.571494,h1_interest_income=.9868257102,h1_interest_cost=.0066312074,h1_fee_cost=.0040604963,q3_ytd_interest_income=1.4439667585,q3_ytd_interest_cost=.0100967645,q3_ytd_fee_cost=.0068661228)
def other_bridge():
 b=dict(OTHER_BRIDGE)
 for key in ['h1','q3_ytd']:
  b[key+'_net_financial']=b[key+'_interest_income']-b[key+'_interest_cost']-b[key+'_fee_cost']
  b[key+'_residual']=b[key+'_segment']-b[key+'_net_financial']
 b['q3_only_residual']=b['q3_ytd_residual']-b['h1_residual']
 b['h1_annualized']=b['h1_residual']*2
 b['q3_ytd_annualized']=b['q3_ytd_residual']*4/3
 b['q3_only_annualized']=b['q3_only_residual']*4
 b['base_year1_budget']=CASES['base']['other'][0]*10
 b['repair_vs_ytd']=b['base_year1_budget']-b['q3_ytd_annualized']
 b['scope']='合并已抵销净金融收支代理；未辨金融运营费用留在剩余亏损；负值无即时税盾；非精确税后分部对账'
 return b

def generate():
 outputs={k:production(c) for k,c in CASES.items()};sens={}
 changes={'unit_minus_500':{'unit':[x-500 for x in CASES['base']['unit']]},'capex_plus_03':{'capex':[2.2]*5},'parent_delay_80pct':{'delay':.8,'up':.7,'settle':[1.5,.7,.3,.2,.2]},'no_roll_5bn':{'redemption':[5,0,0,0,0],'rate':.04},'reg_immediate':{'reg_recovery':0},'reg_20years':{'reg_recovery':20}}
 for name,change in changes.items():
  c=copy.deepcopy(CASES['base']);c.update(change);sens[name]=production(c)
 sens['financial_assets_minus_08']=production(CASES['base'],opening=15.47)
 c=copy.deepcopy(CASES['base']);c.update(changes['parent_delay_80pct']);sens['parent_opening_and_delay']=production(c,parent0=2,legal0=2.5)
 sens['minority_net_debt_01']=production(CASES['base'],minority_net_financial=-.1)
 sens['minority_financial_02']=production(CASES['base'],minority_net_financial=.2)
 tr=[]
 for r,g,ic in [(.095,.005,.13),(.085,.015,.18)]:
  c=copy.deepcopy(CASES['base']);c.update(r=r,g=g,roic=ic);tr.append(production(c)['terminal_value'])
 data=dict(snapshot_kind='new reconstruction; historical byte identity unproven',asof=ASOF,units='十亿元；销量百万吨；吨利润元；股数十亿股',inputs=CASES,other_business_bridge=other_bridge(),outputs=outputs,sensitivities=sens,base_terminal_range=tr,checks=production_tests())
 return data

REPORT_TEMPLATE='# 双汇发展：加工肉利润池仍在，食品安全与现金期限决定拥有质量\n\n信息截止：2026-10-27 21:05:30 UTC\n\n## 一句话结论\n\n双汇的包装肉制品仍有值得长期拥有和跟踪的品牌、规模加工与全国分销优势，但食品安全处罚暴露了采购、检验和管理责任的缺口，降低了对单位利润长期稳定的确信。基准采纳温和销量增长、持续合规投入和配套业务逐步减亏，核心合理价值为@@LOW@@—@@HIGH@@元/股，维持持续覆盖。未使用证券行情，不评价当前价格吸引力，也未识别到有直接证据支持的非共识错价。最大认知风险是把一次罚款误当全部损失，忽略消费者信任和渠道利润归属的永久变化。\n\n## 值得拥有的是肉制品利润，而非屠宰吨数\n\n产业链是生猪、禽肉、进口分割肉及包装供应商→双汇屠宰分割、肉制品加工与冷链→经销商、商超、便利店、零食和餐饮渠道→家庭和外食消费者。低客单、稳定规格及易购买帮助形成复购；经销商需要供货稳定与周转。工厂规模能分摊采购和制造成本，密集渠道可复用配送与货架，但消费者更换品牌成本很低，安全信任必须持续维护。\n\n前三季肉制品分部外部收入188.10亿元、营业利润49.66亿元；屠宰分部外部收入165.56亿元，含内部交易收入189.42亿元，营业利润仅1.99亿元；其他业务亏损2.57亿元。分部利润已扣正常费用和减值，不是毛利；44.93亿元内部交易已经抵销。2025肉制品利润64.46亿元占分部合计66.96亿元绝大部分，说明优势集中于加工品牌，不应把整条纵向产业链都按消费品牌回报定价。[S1，p10；S3，p255]\n\nH1包装肉外销69.91万吨、同比+9.12%，收入120.64亿元，推算吨收入17,256元、税前分部吨利4,503元；2025全年136.11万吨、吨利4,736元。半年与全年受季节和产品结构影响，不能据此精确推出同款降价，但现有证据不足以支持永久提升吨利润。包装肉成本中直接材料占74.28%，低猪价收益可以被渠道降价、营销费用和零售议价分走。[S2，pp19—21；S3，p27]\n\nH1经销商22,799家，主要先款后货，前五经销商占收入6.22%，降低单一客户风险。经销毛利率24.14%、直销6.60%混合产品和客户结构，不能解释为任何新增经销业务都更优。2025年末重划渠道分类，H1已重列同期。公司200多万吨肉制品产能相对销量存在复用空间，但地区、产品和班次不同，不能当作精确利用率。[S2，pp19—22；S3]\n\n采纳的长期解释是成熟品牌在低增长总量环境中保持利润池，新品与渠道复用带来小幅增长。基准首年销量140万吨、吨利4,400元，五年150万吨、4,480元；不要求重获高峰吨利，也不把上半年放量永久化。最强相反解释是销量靠促销和渠道让利买来，食安问题进一步破坏信任。那会同时减少销量、单位利润并增加合规成本，需要一条永久损伤路径而非只扣罚款。\n\n## 原料周期与食品安全必须分开理解\n\n国家统计局前三季猪肉产量4,508万吨、+3.2%，生猪出栏53,739万头、+1.4%，三季度末存栏42,533万头、-2.6%；生猪生产者价格前三季同比-22.1%。供给增加和价格下降可以同时利好新采购、压低生鲜售价并损害旧库存；不同统计口径不能直接相减得到双汇价差。[S8]\n\n双汇总肉外销量273.10万吨、+9.74%，营业收入却-3.85%，反映价格和品类结构共同变化，尚未证明终端消费同步增长。前三季资产减值5.02亿元，较同期2.49亿元大增；H1生鲜猪产品库存14万吨、同比+48.31%，包括进口肉，不能等同自产屠宰头数。[S1，pp3—5；S2，p21]\n\n竞争反证是龙大2026H1屠宰242.83万头、屠宰收入30.23亿元，全集团收入37.99亿元、扣非亏损1.46亿元。其B端结构、融资和治理不同，不能与双汇净利率直接排名，但屠宰规模及完整产业链并不保证股东利润，集中度提升也可能让利给终端客户。[S7，经营及财务章节]\n\n10月10日处罚公告确认望奎子公司有关肉品兽药残留不合格、检验人员及静养制度问题；母公司被指出食品安全总监、内部抽检规范执行及致歉数据表达缺陷。公司披露全年归母影响6,380.66万元。管理层个人罚款不作为上市公司支出；Q3营业外支出1.02亿元、相关预计义务已增加，未来不重复扣整个罚款。未付金额未逐项披露，首年2亿元营运支出预算中包含0—0.74亿元潜在结算，其余用于经营周转。[S1，pp4—5；S6]\n\n公司公告判断生产经营正常、不触及重大违法强制退市，这不能证明品牌信用已经修复。六项整改包括供应商审核、检测升级、静养管理、专业人员、追溯及培训；长期执行尚待检验。基准降低初期单位利润并保持维护投入；结构情景让量价永久受损。可容忍一次库存错配和已纠正处罚，不能容忍跨工厂控制反复失败、复购走弱却靠费用维持出货。\n\n|领先观察|最新可得事实|模型后果与盲区|\n|---|---|---|\n|肉制品量和单位利润|H1量+9.12%、吨分部利4,503元；Q3肉制品分部利润18.18亿元由累计减H1得到|Q3没有单独销量，不虚构Q3吨利；首年采用4,400元|\n|库存与减值|9月底存货66.99亿元，比年初+11.52亿元，减值5.02亿元|弱周期首年额外占用7亿元、第三年回收3亿元，不假定所有库存无损回转|\n|供应周期|全国猪肉增产3.2%，生猪生产者价下降22.1%|加工成本缓冲与养殖/旧库存损失并存|\n|渠道回款|合同负债23.09亿元、较年初+2.56%，应收账款4.34亿元|先款后货机制仍在，但同SKU净价、经销库存和终端动销未公开|\n|食安整改|处罚和六项措施已披露|维护投入不按低现金资本支出永续化；结构路径直接压利润池|\n|融资及上划|短借125.48亿元；H1母体应收股利11.05亿元|实际分配受母体现金、法定利润及到账限制|\n\n## 财务质量：利润韧性不等于新增资本有高回报\n\n以下亿元；收入不含财务公司利息收入，CFO为合并经营现金流，全年与本期累计分列。[S1—S5]\n\n|期间|营业收入|归母利润|扣非归母|CFO|加权ROE|\n|---|---:|---:|---:|---:|---:|\n|2020全年|738.63|62.56|57.75|88.22|32.93%|\n|2021全年|666.82|48.66|44.34|60.34|21.80%|\n|2022全年|625.76|56.21|52.17|75.65|25.43%|\n|2023全年|598.93|50.53|47.32|33.88|23.83%|\n|2024全年|595.61|49.89|48.13|84.16|23.81%|\n|2025全年|592.74|51.05|49.39|73.52|24.10%|\n|2026H1|280.86|23.06|22.86|16.17|10.68%|\n|2026前三季|428.10|36.42|36.65|34.14|16.83%|\n\n2020—2022采用2022年报同列数据，2023—2025采用2025年报。收入多年下降、利润大致稳定支持加工利润韧性，不支持高增长叙事。2021、2022现金资本支出39.33、35.49亿元，合计74.82亿元，2025盈利仍低于2020。利润受周期影响，不能把利润差简单除资本支出认作项目ROIC；分部资产不单列，也不具备精确分部ROIC。高ROE同时受高派息和低留存权益影响。\n\nQ3单季收入147.25亿元、归母13.37亿元、扣非13.78亿元，同比-8.59%、-18.27%、-13.84%。单季CFO为34.1352−16.1694=17.9659亿元，对照2025Q3的30.8126亿元下降41.69%，不是把累计-43.06%直接当单季。前三季毛利率19.67%，同期18.18%，但销售费用18.04亿元、约+15.19%，减值和配套亏损吃掉部分原料红利。[S1—S3]\n\n前三季CFO34.14减现金资本支出6.94为27.19亿元，尚未扣租赁与少数分配，低于归母36.42亿元。公司解释本期库存占款11.52亿元、同期释放13.81亿元，方向反转25.33亿元接近CFO下降25.82亿元，量级有支撑；但不应全部加回成永久自由现金。\n\n2025资本支出9亿元低于折旧摊销约16.30亿元；2026预算投资13亿元，九个月实际6.94亿元。过去预建能力、工程付款时点与技改周期不同，不能用低支出证明未来无需更新。基准普通股归属非租DA16亿元、投入19亿元（维护约16.5、成长约2.5）、营运2亿元、租赁本金与ROU折旧净差0.4亿元，都是研究预算，不是假称公司已批准19亿元。既有产能承担主要销量增量，同时持续净投资。第1至第5年经营利润增约7.6亿元，对应四年净固定及营运投入约20亿元，约38%的端点比率包含闲置能力利用和减亏，非项目已实现回报；长期新增资本回报降为15%。\n\n## 普通股归属与金融本金：不能只看合并余额\n\nQ3总股本34.64661213亿股，无库存股、优先股或永续权益列示；模型没有回购、增发或转股假设。少数权益2.20亿元、前三季少数利润0.285亿元。年度少数净利润预算0.4亿元分为经营0.385与金融收益0.015亿元；后者对应估计少数净金融本金1亿元×1.5%。先从合并金融资产剥1亿元，再只扣少数经营利润，避免同一收益双扣；终值不另减全部少数净资产。净资本也按普通股归属预算，非全资扩张需要重新分配资本。[S1，pp13—15]\n\n9月底货币资金68.48亿元、现金等价物62.04亿元，差额不能当即时分红；交易金融资产4.01亿元，其他流动79.24亿元、其他非流动16.54亿元。H1其他流动中不可提前支取定存64.07亿元、短债投资30.92亿元，余项包括留抵税等。Q3未重列细项，因此其中金融部分取74亿元、长期存单16.2亿元，加现金及交易金融资产，合并本金**162.7亿元为估计**，不是披露的精确金融总额。普通股先扣少数1亿元；本金误估8亿元的价值敏感性约0.16元/股。[S1，pp4、11—12；S2，p133]\n\n融资与金融负债129.8亿元预算由短借125.48、长借2.08、一年内到期非流动0.92、外部吸收存款1.30亿元取整。独立租赁负债1.89亿元不再重复扣，因为租现金已进经营支付链；一年内到期项可能混有租赁，全部误分的量级约0.03元/股。普通备付现金20亿元约相当于两周采购和经营支出，支持在营业务价值，不再另加为可抽走现金。监管/受限资金另取6.5亿元，接近货币资金与现金等价物差额及H1准备金量级，不声称法律最低额恰好如此。\n\nH1财务公司全资，净资产23.95亿元、净利润0.798亿元，资本充足率32.42%、流动性比例35.87%。单体106.57亿元存款大部分集团内部，不能再次加外债；单体权益与利润不能加到合并价值。母公司在财务公司32.26亿元存款是母体资产，但集团内部抵销，不能作第三笔现金。监管缓冲支持正常运转，不保证母体可无限提取。[S9]\n\n重要非全资子公司原表如下，单位亿元；持股比例不等于精确金融本金归属。[S2，pp186—187]\n\n|主体|总资产|总负债|流动资产|少数比例|披露少数权益|\n|---|---:|---:|---:|---:|---:|\n|望奎|3.3534|1.7963|2.0983|25%|0.3893|\n|阜新肉类|3.1184|0.3847|1.9323|20%|0.5467|\n|宝泉岭|1.7872|0.2014|0.8466|25%|0.3964|\n|生物工程|5.3182|3.6572|1.6782|4.62%|0.3256|\n\n前三家资产减负债再乘少数比例可勾稽。生物工程资产负债差×4.62%约0.0767亿元，不能勾稽0.3256亿元，可能涉及主体层级/穿透口径，不能强行使用同一分母。四家流动资产直接比例粗加权约1.20亿元，只是量级线索、不是净金融资产或硬上限，另有小型非全资企业。故采用少数净金融1亿元预算，测试净债1亿元至净资产2亿元；负值端剥除少数债务及其真实模型融资成本，不能用存款收益替代债息。对基准现值影响不足0.05元，但不声称归属已得到审计确认。\n\n存款到期按流动部分一年内、长期存单未来三年内分批处理，正常续贷为基准而非全部短债集中提前偿还。基准融资利率2.2%、金融税后收益1.5%；周期和结构路径分别净偿还20亿元、40亿元并提高利率。预算40%由母体偿还，接近H1母体融资占集团比例；其余由子公司承担。母体本金付款、余额与下年利息同步递推，没有凭空新增内部借款填洞。50亿元不续作压力中，母体承担20亿元、子公司30亿元。逐月到期细项未公开，年度有资金不保证每月没有流动性错配。\n\n金融本金并未永久锁死：前五年未派现金计入金融资产并产生收益；第五年经营终值剥离金融收益和融资利息，另加分配后金融资产减债务及必要经营现金。受限6.5亿元按十年回收本金、期间1.5%现金收益估值，只是经济实现预算，不是监管批准；立即与二十年回收边界对当前价值差不足0.09元。若监管要求永久改变或实际退出，需要重估回收，而非机械延后。\n\n### 母体法定利润与实际现金是两道不同门槛\n\n最后公开母表为H1：现金等价物49.27亿元、应收股利11.05亿元、未分配利润43亿元；H1净利润26.40亿元、投资收益25.07亿元，取得投资收益现金14.70亿元、CFO负17.81亿元。投资收益收现不等于全部本期子公司股利；旧应收回款只增加现金，不再次增加法定利润。应付票据70.93亿元、应收账款12.49亿元体现贸易结算，合并抵销不等于法律可自动抵销。[S2，pp66—74]\n\nQ3没有母表，以下以H1余额为锚的**经济付款预算，不是10月法定余额证明**。基准子公司新宣派为归母利润88%，15%延迟一年到账，首年另外收回旧应收11.05亿元。母体直接经营利润起点2.5亿元/年随肉量缓增，按期初现金1.42%计利息收益，减自身融资成本，量级参考H1母净利润减投资收益1.33亿元及单列利息收支。内部收益仅是主体间分布，不增加集团合并收益。母融资51.04亿元由H1短借46.93、一年内到期4.02、长期0.0876亿元估计，并非Q3母体已知数。\n\n母表法定盈余公积18.3191亿元，附注62明确为法定公积，超过注册资本34.6466亿元的50%（17.3233亿元）。基准不继续凭空提取。模型让母体负损益完整消耗留存，未来利润先弥补期初亏损，再按适用利润10%提公积、以距注册资本50%的缺口为预算上限；不假定任意公积或已获动用公积弥亏决议。资本及公积变化须重新核验。[S2，p164；S10]\n\n母体现金投入及周转每年3亿元，既有往来首三年额外净付5/2.5/1亿元，其余贸易正常滚动，不把70.93亿元票据全额提前清偿。母体现金至少15亿元，约半个月H1经营支出；实际股利取目标派息、集团可用资金、母体现金及法定可分利润的最小值。子公司宣派量从约39.03增45.89亿元有多年真实分红作方向证据，仍非未来各家董事会承诺。80%到账延迟、上划降70%并提高付款时，第二年每股分配降至约0.68元；再把母体期初现金降到20亿元、留存降25亿元，首年降至约0.18元。滞留现金仍在集团内，不冒充股东已收分红。\n\n## 估值：温和修复为核心，永久损伤单列\n\n主法是实际股利折现，加第五年末独立经营状态与分配后金融权益桥；辅助是首年正常经营现金零增长资本化并加相容金融桥。核心资本成本8.5%—9.5%、基准9%，反映成熟食品需求和低净金融杠杆，同时承担食安、关联控制与单位利润风险；不是账户回报门槛。\n\n核心合理价值区间：@@LOW@@—@@HIGH@@ 元。\n\n低端首年138万吨/吨利4,250元，五年146万吨/4,330元，屠宰税前2.5→3.7亿元、其他税后亏损4.5→2.5亿元，每年投入20亿元、营运2.5亿元，折现9.5%、长期增长0.5%、新增资本回报13%。高端首年142万吨/4,500元，五年154万吨/4,580元，屠宰3.5→5.5亿元、其他亏损3.5→1.5亿元，投入19亿元、营运2亿元，折现8.5%、长期增长1.5%、回报18%。两端都保留品牌与温和增长，不包含永久衰退或新品超常成功。\n\n基准归母首年约44.35、第五年52.15亿元，未将Q3乘四：140万吨×4,400元=肉制品税前61.6亿元，按25%税得46.2；加屠宰3亿元×85%、其他亏损4亿元，扣少数经营0.385亿元，再加普通股金融收益减借款成本。屠宰15%有效税是免税初加工与应税进口混合预算，不把所有屠宰收益免税；亏损配套不假定即时税盾。\n\n终值经营现金=第五年普通股经营利润×(1+g)×(1−g/新增资本回报)−维护高于折旧差额0.5亿元−租赁净差0.4亿元；结构情景维护差额2亿元。增长有资本代价，金融收益与债息从经营终值剥离，另桥接本金。基准终值现值贡献@@TV_WEIGHT@@，远期量价及治理假设支配结果，小数位仅供复算。\n\n辅助零增长法核心两端@@AUX_LOW@@—@@AUX_HIGH@@元、基准@@AUX_BASE@@元，低于主法基准@@BASE_VALUE@@元，因未计五年产能复用及配套减亏。两法共享利润原证，不互相证明品牌假设。结构情景辅助冻结首年，忽略此后进一步衰退，明显高于完整路径，不能机械平均。\n\n@@SCENARIO_TABLE@@\n\n周期路径从第1年冲击库存及养殖，但保留肉制品品牌，销量133→150万吨、吨利4,000→4,480；首年营运占用7亿元、第三年回收3亿元，融资成本3.2%、上划80%、延迟30%，偿债20亿元。结构路径量130→116万吨、吨利3,900→3,300，配套亏损7→5.5亿元不恢复，长期零增长，融资4%、上划70%、延迟40%，首两年偿债30/10亿元。乐观路径需要新品复购与渠道经济实际兑现，量146→170万吨、吨利4,600→4,800、屠宰4.5→8.5亿元、配套盈亏平衡，每年投入21亿元、营运2.5亿元，长期2%增长配20%资本回报。\n\n所有路径实际重算投入、利润、融资、少数归属、母体付款和终值，股数保持不变，不用增发维持分红。吨利减少500元使首年归母减少5.25亿元、当前价值约少1.84元；每年投入加3亿元只隔离五年支出、不凭空创造终值利润，不能替代永久资本强度上升的完整结构路径。\n\n### “其他”先剥金融：原表到经营预算的桥\n\n“其他分部”原表包含金融服务，不能将其亏损直接加上模型金融收益。以下均为亿元，以合并利润表已抵销内部交易的金融服务利息收入减利息支出及手续费支出作可辨净金融收支代理；不使用含内部业务的财务公司单体净利润，也不把普通财务费用中的存款利息重复加进这个代理。[S2，合并利润表及pp209—210；S1，合并利润表及p10]\n\n|可复算口径|2026H1|前三季|单Q3（差额）|\n|---|---:|---:|---:|\n|原表其他分部营业利润|−2.060010|−2.571494|−0.511484|\n|金融服务利息收入|0.986826|1.443967|0.457141|\n|金融利息及手续费支出|0.010692|0.016963|0.006271|\n|可辨净金融收支|0.976134|1.427004|0.450870|\n|原其他减上述金融收支|−3.036144|−3.998498|−0.962354|\n|机械全年化亏损量级（非预测）|−6.072287|−5.331331|−3.849417|\n\n这不是精确非金融分部税后对账：未单独披露的金融人员、管理、信用及合规成本仍保留在剩余亏损中，不宣称全部费用已可识别剥离；金融外部本金的未来1.5%税后回报只代表净利息税后预算，不再另加财务公司净利润或原表金融净收入，未辨费用不会因模型拆分被消失。集团普通外债融资成本另由债务余额×融资利率×75%计算，不把合并表金融服务对外吸收存款的历史利息支出再扣一遍。金融净收支代理仅为预测锚，不能当作精确法律主体利润。\n\n模型other是上述剥可辨金融收入后、保留未辨费用的经营现金收益预算，负值不乘75%，不确认即时亏损税盾。基准首年−4亿元接近单Q3亏损机械全年化−3.85亿元，但相对前三季全年化−5.33亿元仍要求约1.33亿元修复，相对H1全年化−6.07亿元要求约2.07亿元；因此不是把现状中性外推。单Q3较H1的亏损收窄支持修复方向，但季节性、减值和产品结构使它不能证明全年可维持。选择−4而非−3.85保留小幅余量，不改变19亿元投入及维护预算，不靠删减食品安全费用达成；第五年−2亿元另外要求四年累计2亿元减亏，主要依赖禽养殖和配套利用率改善，并非已落实项目回报。\n\n核心首年亏损−4.5至−3.5亿元仍是偏修复区间，不覆盖全部现状风险；周期首年−6.5亿元、结构首年−7亿元且五年仍−5.5亿元，覆盖H1量级未改善及治理成本继续上升。后续若单季剥金融亏损无法保持约1亿元附近，或改善只来自未持续的减值/税收益，应取消基准减亏而采用较弱路径。上述桥决定预算可解释性，不承诺任何税务抵扣。\n\n## 前次假设复盘\n\n|前次假设|本期实际|判断变化|估值影响|\n|---|---|---|---|\n|食品安全为低频尾部风险|10月正式处罚指出采购、检测和管理缺口，归母影响0.638066亿元|新事实提升风险优先级；一次支出与信用损伤分开|保留合规资本、初期吨利更审慎，结构路径量价永久下移|\n|屠宰税后4.5逐步升6.5亿元、配套减亏|前三季屠宰营业利润1.99亿元、其他亏损2.57亿元|旧恢复幅度偏乐观，是经营预测变化而非会计纠错|基准屠宰税前3→4.6亿元，初年归母44.35低于旧49亿元|\n|D从1.20元起，可用现金43.70亿元起|前三季CFO34.14、资本支出6.94亿元；短借较年初增加28.27亿元|历史派息不能代替母体到账，需要实际付款约束|首年每股@@DPS_FIRST@@元，延迟时自动下调，不把FCFE全当股东收到|\n|保持现有金融资本，主要以净金融收益计值|新增长期存单7.2亿元，金融细项与Q3母表缺失|本金实现、少数归属与母债必须显式表达|本金单列、收益从经营终值移除，不无故永远锁死资产|\n\nH1已记录Q2利润与现金压力，本期Q3归母和扣非再下滑是对“出货修复自然变成利润”的继续反证。以后必须同时看到单位利润、库存周转与渠道回款，不能每期吸收较差结果后宣布原假设正确。价值变化包含新事实、屠宰预测与本金方法，不全部归因于一季基本面。\n\n## 基准持有人回报模型输入\n\n未来五个完整周年至2027—2031年10月27日，按年末现金分配预算；2026年4月已付不计未来，H1不派中期不等于未来全年为零。各年未获董事会承诺，个人税费未计，不使用现价固化IRR。\n\n@@BASE_TABLE@@\n\n五年每股现金分配：**@@DPS@@元**。相同基准经营和分配后资产下，第五年末用资本成本8.5%—9.5%、长期增长0.5%—1.5%、新增资本回报13%—18%，独立终值为**@@TV_LOW@@—@@TV_HIGH@@元/股**；没有把当前区间复制成终值，也没有把不同经营情景的终值拼作基准接口。\n\n第五年普通股金融资产约@@END_ASSETS@@亿元，融资/金融负债129.80亿元，减经营备付20亿元及受限本金6.5亿元，加受限本金实现价值约@@REG_VALUE@@亿元，金融权益桥约@@FIN_BRIDGE@@亿元。每年已付股利从现金中扣除，未付内部应收不额外加集团价值。完全稀释股数34.64661213亿不变，未独立研究三年终值，故不作插值。\n\n[下载可复算模型](../models/2026-Q3-model.py)。年度全量经营、主体现金、债务与法定利润预算、情景和敏感性均可复算；预测小数不表示经济确定性。\n\n## 风险与改判条件\n\n首位是安全与诚信：重复跨工厂违规、重要客户退出、复购及净价持续走弱，将使品牌利润从周期修复变为永久衰退。第二是低回报扩张：屠宰、禽养殖持续要库存与设备却不能产生相应现金，应取消配套减亏预期。第三是资金归属：关联采购运输让价值转向上市体系之外，或子公司上划受限、母体仍维持高分红，将损害普通股本金。\n\n罗特克斯持股70.33%，前三季向其体系进口采购36.71亿元、关联运输13.16亿元并有商标许可。整合供给和集中控制可提高执行效率，也削弱外部股东对资本配置的约束；未获得足够独立成交样本验证所有关联定价，不能把交易金额本身判为违法。[S1，pp6—9] 公司2025审计标准无保留，存货跌价是关键审计事项；H1和Q3未经审计，不能把审计历史代替本期信用核验。\n\n短期库存和分红延迟可容忍，条件是客户仍选择产品、错配能在资金范围内出清。即使收入增长，若利润捕获、回款和新增资本回报长期恶化，拥有理由仍会削弱。持续覆盖依据是加工利润来源可识别且尚有韧性，不是对管理质量无条件背书。\n\n## 来源与资料边界\n\n- [S1 双汇2026第三季度报告](https://static.cninfo.com.cn/finalpage/2026-10-28/1225628424.PDF)，18页，9月30日报表、未经审计；公告标示10月28日，全文已于10月27日公开取得。\n- [S2 双汇2026半年度报告](https://static.cninfo.com.cn/finalpage/2026-08-29/1225524169.PDF)，8月29日，母表pp66—74、金融资产p133、法定公积p164、非全资pp186—187、分部p210。\n- [S3 双汇2025年度报告](https://static.cninfo.com.cn/finalpage/2026-03-25/1225028113.PDF)，3月25日，历史数据、投资预算、折旧和分部。\n- [S4 双汇2022年度报告](https://static.cninfo.com.cn/finalpage/2023-03-29/1216242470.PDF)，2023年3月29日，2020—2022序列及现金资本支出。\n- [S5 双汇2021年度报告](https://static.cninfo.com.cn/finalpage/2022-03-29/1212707745.PDF)，2022年3月29日，交验2020—2021及列报变化。\n- [S6 双汇行政处罚公告](https://static.cninfo.com.cn/finalpage/2026-10-10/1225599972.PDF)，10月10日，6页，企业与个人责任分开。\n- [S7 龙大2026半年度报告全文](https://static.cninfo.com.cn/finalpage/2026-08-29/1225528489.PDF)，8月29日，业务与财务原表，仅作竞争反证。\n- [S8 国家统计局前三季度经济运行](https://www.stats.gov.cn/sj/zxfbhjd/202610/t20261019_1965618.html)，10月19日，畜牧及生产者价格表。\n- [S9 双汇财务公司H1风险评估](https://static.cninfo.com.cn/finalpage/2026-08-29/1225524171.PDF)，8月29日披露、正文8月27日，监管及母体存款。\n- [S10 公司法第210条，税务总局法规库](https://fgk.chinatax.gov.cn/zcfgk/c100009/c5233383/content.html)，2023年修订、2024年7月施行，先弥亏与法定公积机制。\n\n原证可支持量级估值，不支持逐月母体可派资金的法律确认。最大盲区是整改后复购、同SKU终端动销、Q3母表和金融到期明细，已通过较谨慎单位利润、主体资金约束及本金敏感性影响判断。\n'

def deliver(data):
 import inspect
 p=pathlib.Path(__file__).resolve().parent;b=data['outputs']['base'];rows=b['rows']
 lo=round(data['outputs']['core_low']['current_value'],2);hi=round(data['outputs']['core_high']['current_value'],2)
 tv=[round(x,2) for x in data['base_terminal_range']];dps=[round(x['dps'],4) for x in rows]
 table=['|基准预算，亿元（销量另列）|第1年|第2年|第3年|第4年|第5年|','|---|---:|---:|---:|---:|---:|']
 fields=[('肉制品销量，万吨',None),('归母利润','common_profit'),('经营后普通股现金','fcfe'),('实际现金股利','dividend'),('母体期末现金','parent_cash'),('母体期末可分利润','parent_legal'),('母体法定公积','parent_statutory_reserve'),('母体融资余额','parent_debt'),('母体偿债','parent_debt_repaid'),('母体税后利息','parent_interest'),('子公司宣派','subs_declared'),('子公司到账','subs_received'),('应收股利','dividend_receivable')]
 for title,key in fields:
  vals=[x*100 for x in CASES['base']['vol']] if key is None else [x[key]*10 for x in rows]
  table.append('|'+title+'|'+'|'.join(f'{v:.2f}' for v in vals)+'|')
 st=['|路径|当前价值元/股|第五年终值元/股|终值现值贡献|','|---|---:|---:|---:|']
 names={'base':'基准','core_low':'核心低端','core_high':'核心高端','cycle':'周期性弱','structural':'结构性不利','upside':'较乐观'}
 for k,x in data['outputs'].items():st.append(f"|{names[k]}|{x['current_value']:.2f}|{x['terminal_value']:.2f}|{x['terminal_pv_share']:.1%}|")
 values={'LOW':f'{lo:.2f}','HIGH':f'{hi:.2f}','BASE_VALUE':f"{b['current_value']:.2f}",'TV_WEIGHT':f"{b['terminal_pv_share']:.1%}",'AUX_LOW':f"{data['outputs']['core_low']['auxiliary_no_growth_value']:.2f}",'AUX_HIGH':f"{data['outputs']['core_high']['auxiliary_no_growth_value']:.2f}",'AUX_BASE':f"{b['auxiliary_no_growth_value']:.2f}",'DPS_FIRST':f'{dps[0]:.4f}','DPS':'、'.join(f'{x:.4f}' for x in dps),'TV_LOW':f'{tv[0]:.2f}','TV_HIGH':f'{tv[1]:.2f}','END_ASSETS':f"{rows[-1]['assets']*10:.2f}",'REG_VALUE':f"{b['regulatory_principal_value']*10:.2f}",'FIN_BRIDGE':f"{b['terminal_financial_bridge']*10:.2f}",'BASE_TABLE':'\n'.join(table),'SCENARIO_TABLE':'\n'.join(st)}
 report=REPORT_TEMPLATE
 for key,val in values.items():report=report.replace('@@'+key+'@@',val)
 assert '@@' not in report
 urls=['https://static.cninfo.com.cn/finalpage/2026-10-28/1225628424.PDF','https://static.cninfo.com.cn/finalpage/2026-08-29/1225524169.PDF','https://static.cninfo.com.cn/finalpage/2026-03-25/1225028113.PDF','https://static.cninfo.com.cn/finalpage/2023-03-29/1216242470.PDF','https://static.cninfo.com.cn/finalpage/2022-03-29/1212707745.PDF','https://static.cninfo.com.cn/finalpage/2026-10-10/1225599972.PDF','https://static.cninfo.com.cn/finalpage/2026-08-29/1225528489.PDF','https://www.stats.gov.cn/sj/zxfbhjd/202610/t20261019_1965618.html','https://static.cninfo.com.cn/finalpage/2026-08-29/1225524171.PDF','https://fgk.chinatax.gov.cn/zcfgk/c100009/c5233383/content.html']
 result=dict(symbol='CN:000895',name='双汇发展',outcome='covered',report_period='2026-Q3',information_cutoff=ASOF,summary=f'加工肉的品牌与分销利润池仍有长期价值，食品安全、屠宰薄利和资金期限降低确定性；采纳温和量价增长及持续合规投入，核心合理价值{lo:.2f}—{hi:.2f}元，持续覆盖。未使用证券行情。',key_logic=['经济利润集中于肉制品，屠宰规模增长不等于新增资本获得相同回报。','行政处罚的一次支出与品牌/治理永久损伤分开建模，保持维护投入。','母体亏损、公积、偿债、子公司宣派和到账逐年联动；少数金融本金及收益拆分，分配后现金进入终值。'],risks=['重复食安或诚信问题破坏复购及单位利润。','库存减值与低回报配套投资持续吸收现金。','关联交易、金融期限或上划受限影响普通股利益；Q3母表及期限细项尚缺。'],value_range={'low':lo,'high':hi,'currency':'CNY'},valuation_note=f'主法为实际股利折现加独立第五年经营与金融权益桥，核心采用温和修复路径合理量价/投入范围，不混入结构与乐观情景。资本成本8.5%—9.5%、长期增长0.5%—1.5%、增量回报13%—18%；辅助零增长法{values["AUX_LOW"]}—{values["AUX_HIGH"]}元。',return_model={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':ASOF,'base_case_distributions_per_share':dps,'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':tv[0],'high':tv[1]}}},return_model_note=f'五个完整周年的实际分红为经济预算，非决议承诺。同一基准经营与已分配后金融资产下第五年终值{tv[0]:.2f}—{tv[1]:.2f}元；终值经营现金剥离金融收益和债息，再加归普通股本金净桥。34.64661213亿完全稀释股数不变，无回购增发假设。母体H1余额仅为预算锚；保留负损益、先弥亏、法定公积及偿债主体限制，不把合并现金当即刻可分。',source_urls=urls,report_markdown=report)
 candidate={'task_id':'6bcfa6d662e803ff7e5eeb71','at':'2026-10-27T21:05:31+00:00','result':result}
 check=independent_literal(data)
 (p/'candidate.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n')
 (p/'2026-Q3-output.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 (p/'independent_check.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n')
 (p/'model_tables.md').write_text('\n'.join(st)+'\n\n'+'\n'.join(table)+'\n')
 (p/'reports').mkdir(exist_ok=True);(p/'models').mkdir(exist_ok=True)
 (p/'reports'/'2026-Q3.md').write_text(report);(p/'report.md').write_text(report)
 dest=p/'models'/'2026-Q3-model.py'
 if dest.resolve()!=pathlib.Path(__file__).resolve():dest.write_text(pathlib.Path(__file__).read_text())
 checker='import json, math, pathlib\n'+inspect.getsource(independent_literal)+"\np=pathlib.Path(__file__).resolve().parent\nr=independent_literal(json.loads((p/'2026-Q3-output.json').read_text()))\n(p/'independent_check.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\\n')\nprint(json.dumps(r,ensure_ascii=False,indent=2))\n"
 (p/'independent_literal_check.py').write_text(checker)
 print(json.dumps({'value_range':result['value_range'],'return_model':result['return_model'],'checks':data['checks']},ensure_ascii=False,indent=2))
if __name__=='__main__':deliver(generate())

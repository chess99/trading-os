#!/usr/bin/env python3
"""卫星化学2026Q3；stdlib；亿元/亿股。六经济预算桶不是六个法律主体。
仅母公司维护单体利润/法定公积；子公司使用分开亏损的经济上划预算，不伪称法律余额。
所有尾期新增金融余款逐批保留，未来利润容量、实际收现、支付分别计算。
"""
import json,copy,math,gzip,base64,hashlib,argparse
from pathlib import Path
S=33.68645690
D=17.4622684964+(17.890628146-17.236864745)+51.2530244+29.303815726+1.9177433628
C=128.1150078051; R=142.1546221072-C; SEC=9.118; INV=23.0780722239
K=['L','I','E','H','O','P']; W=dict(zip(K,[.70,0,.13,.10,.02,.05])); CW=dict(zip(K,[.65,0,.10,.10,0,.15]))
C0=dict(zip(K,[70,0,20,10,C-100-.9016081171,.9016081171])); D0=dict(zip(K,[D*.48,0,D*.24,D*.20,D*.02,D*.06])); F=dict(zip(K,[7,0,1.5,1,20,.5]))
BASE={'revenue':[580,600,630,655,675],'ebit_pre':[132,138,148,158,163],'rent':[30,32,34,35,36],'da':[28,29,31,33,35],'maintenance':[30,31,33,35,37],'project':[26,22,13.29,0,0],'growth':[5,6,8,10,12],'wc':[4,4,5,5,5],'old_pay':[12,10.64941641,0,0,0],'payout':[.65,.75,.85,.95,1.05],'scale':[1]*5,'capscale':[1]*5,'extra_rent':[0]*5,'extra_wc':[0]*5,'rate':.033,'yield':.01,'max_debt':40,'parent_limit':12,'delay':0,'freeze':False,'availability':.95,'overseas_tax':.21,'overseas_remit_friction':.05,'initial_capacity':0.,'tax_cn':.15,'investment_sale':.90,'investment_tax_basis':INV*.90,'release_block':0,'tail_ebit_delta':0.,'parent_governance_reserve':False,'parent_legacy':9.0996638532,'settle_restricted':True,'early_remit_ratio':1.,'special_window':3,'parent_statutory_initial':9.2269774471,'security_year':1,'investment_yield':.04,'security_yield':.01,'book_adjustment':.5}
PARAM={'low':{'ke':.11,'wacc':.099,'g':.015,'roic':.10},'high':{'ke':.10,'wacc':.092,'g':.02,'roic':.12}}
def near(x,y):return abs(x-y)<1e-7*max(1,abs(x),abs(y))
def parent_profit(balance,profit,registered,statutory,paid_in=None,voluntary=0,continue_reserve=False):
    eligible=max(0,profit-max(0,-balance))
    room=max(0,registered*.5-statutory)
    transfer=.1*eligible if continue_reserve else min(.1*eligible,room)
    return balance+profit-transfer,statutory+transfer,transfer

def economic_profit(capacity,loss,profit,availability):
    """经济预算而非法人法律余额。未分配利润原值加损益后再乘可实现率。
    亏损先冲现有容量对应利润，只有未覆盖余亏留待将来；不重复扣。
    资本回收现金不传入profit，只有处置净会计损益传入。
    """
    assert 0 < availability <= 1 and capacity >= -1e-8 and loss >= -1e-8
    balance=capacity/availability-loss+profit
    return max(0.,balance)*availability,max(0.,-balance)

def flow(ebit,interest,da,maintenance,growth,wc,tax,minority=0,book_adjustment=0):
    taxable=ebit-interest+book_adjustment; taxes=max(0,taxable)*tax
    profit=taxable-taxes-minority
    return {'profit':profit,'tax':taxes,'cash':profit-book_adjustment+da-maintenance-growth-wc,'interest':interest}

def receive_old_receivable(cash,legal,amount):
    return cash+amount,legal

def equity_sale(proceeds,book_cost,tax_basis,tax_rate,cost=0):
    tax=max(0,proceeds-tax_basis-cost)*tax_rate
    return {'cash':proceeds-cost-tax,'accounting_gain':proceeds-book_cost-cost-tax,'taxable_gain':max(0,proceeds-tax_basis-cost),'tax':tax,'book_cost':book_cost,'tax_basis':tax_basis}

def capitalise(registered,paid_in,shares,capital_reserve,amount,cash):
    assert 0<=amount<=capital_reserve and registered>0
    return {'registered':registered+amount,'paid_in':paid_in+amount,'shares':shares*(registered+amount)/registered,'capital_reserve':capital_reserve-amount,'cash':cash}

def capital_return(registered,paid_in,shares,amount,ownership,fee):
    assert 0<=amount<=paid_in and 0<=ownership<=1
    ratio=amount/paid_in if paid_in else 0
    return {'registered':registered*(1-ratio),'paid_in':paid_in-amount,'shares':shares*(1-ratio),'original_holder_cash':amount*ownership-fee,'profit':-fee}

class Lots:
    def __init__(self): self.items={k:[] for k in K};self.history=[]
    def add(self,k,amount,year,tag):
        if amount>1e-9:self.items[k].append({'born':year,'tag':tag,'amount':amount})
    def take(self,k,amount,year,purpose):
        out=[];left=amount
        while left>1e-8 and self.items[k]:
            v=self.items[k][0];n=min(left,v['amount']);out.append({**v,'amount':n});v['amount']-=n;left-=n
            self.history.append({'born':v['born'],'tag':v['tag'],'from':k,'year':year,'amount':n,'purpose':purpose})
            if v['amount']<1e-8:self.items[k].pop(0)
        assert left<1e-5,(k,amount,left)
        return out
    def transfer(self,src,dst,amount,year,friction=0):
        batch=self.take(src,amount,year,'upstream')
        return [{'born':v['born'],'tag':v['tag'],'amount':v['amount']*(1-friction)} for v in batch]

def run(c,p,n=400,trace=True):
    c=copy.deepcopy(c);cash=copy.deepcopy(C0);debt=copy.deepcopy(D0);new={k:0. for k in K}
    capacity={k:c['initial_capacity']*W[k] for k in K if k!='P'}
    losses={k:0. for k in K if k!='P'}
    legal=c['parent_legacy'];reserve=c['parent_statutory_initial'];pending=[];rows=[];lots=Lots();pv=0.;dpv5=0.;tv5=0.;old_floor=copy.deepcopy(F)
    for k in K:lots.add(k,max(0,cash[k]-F[k]),0,'opening_financial')
    sec=SEC;investment=INV;borrowed=0.;max_age=0
    for y in range(1,n+1):
        t=min(y-1,4);growthfactor=(1+p['g'])**max(0,y-5)
        floor={k:F[k]*growthfactor for k in K};fd=sum(floor.values())-sum(old_floor.values())
        eb=c['ebit_pre'][t]*c['scale'][t]-c['rent'][t]-c['extra_rent'][t]
        if y>5:eb=(eb+c['tail_ebit_delta'])*growthfactor
        rent=(c['rent'][t]+c['extra_rent'][t])*growthfactor
        da=c['da'][t]*growthfactor;maint=c['maintenance'][t]*c['capscale'][t]*growthfactor
        if y<=5:grow=(c['project'][t]+c['growth'][t])*c['capscale'][t];wc=c['wc'][t]+c['extra_wc'][t];pay=c['old_pay'][t]
        else:
            reinvest=max(0,eb*(1-c['tax_cn']))*p['g']/p['roic']
            grow=reinvest*.6;wc=reinvest*.4-fd;pay=0
        opening=sum(cash.values())+sum(v['amount'] for v in pending)
        opening_debt=sum(debt.values());debt_repaid=0.
        if y==8 and c['settle_restricted']:
            for k in K:
                rep=min(debt[k],R*D0[k]/D);debt[k]-=rep;debt_repaid+=rep
        totalcf=0.;totalnp=0.;total_tax=0.;total_interest=0.;fin=0.;fric=0.;sale_cash=0.;sale_book=0.;decl={k:0. for k in K};flows={}
        # floor增长由显式再投资预算的一部分支持，不能与贸易营运资本重复扣。
        for k in K:
            delta=floor[k]-old_floor[k]
            if delta>0:lots.take(k,min(delta,max(0,cash[k]-old_floor[k])),y,'necessary_operating_capital')
            inc=max(0,cash[k]-floor[k])*c['yield']
            if k=='E':inc+=sec*c['security_yield']+investment*c['investment_yield']
            tax=c['overseas_tax'] if k=='O' else c['tax_cn']
            f=flow(eb*W[k]+inc,debt[k]*c['rate'],da*CW[k],maint*CW[k],grow*CW[k],wc*W[k],tax,.02*growthfactor if k=='H' else 0,c['book_adjustment']*W[k]*growthfactor)
            q=f['cash']-pay*CW[k];cash[k]+=q
            if q>0:lots.add(k,q,y,'future_financial')
            else:lots.take(k,min(-q,sum(v['amount'] for v in lots.items[k])),y,'operating_use')
            if k=='P':legal,reserve,_=parent_profit(legal,f['profit'],S,reserve,continue_reserve=c['parent_governance_reserve'])
            else:
                # 不跨桶抵亏。不称这些数为法人法定利润；95%是可实现股利预算。
                capacity[k],losses[k]=economic_profit(capacity[k],losses[k],f['profit'],c['availability'])
            totalcf+=f['cash'];totalnp+=f['profit'];total_tax+=f['tax'];total_interest+=f['interest'];flows[k]=f
        if y==c['security_year']:
            cash['E']+=sec;lots.add('E',sec,0,'opening_security');sale_cash+=sec;sec=0
        if y==10:
            sale=equity_sale(INV*c['investment_sale'],INV,c['investment_tax_basis'],.25)
            cash['E']+=sale['cash'];lots.add('E',sale['cash'],0,'opening_equity_investment');sale_cash+=sale['cash'];sale_book=sale['accounting_gain'];investment=0
            # 处置利润/亏损与现金分别进入经济股利预算，亏损不能凭空抵其他桶。
            capacity['E'],losses['E']=economic_profit(capacity['E'],losses['E'],sale_book,c['availability'])
        # 已宣派现金锁定，旧应收到账不增母利润。
        mature=[x for x in pending if x['due']<=y]
        for x in mature:
            cash['P'],legal=receive_old_receivable(cash['P'],legal,x['amount']);lots.items['P'].extend(x['lots']);pending.remove(x)
        # 经营资金不足优先使用本期可实现上划；不能因此凭空制造集团资金。
        if y>c['release_block']:
            for k in K:
                if k=='P':continue
                available=max(0,cash[k]-floor[k]);limit=capacity[k]
                if y<=5 and k in ['L','O']:limit=min(limit,c['early_remit_ratio']*max(0,flows[k]['profit']))
                amount=min(available,limit)
                haircut=c['overseas_remit_friction'] if k=='O' else 0
                if amount:
                    packed=lots.transfer(k,'P',amount,y,haircut);cash[k]-=amount;capacity[k]-=amount
                    net=amount*(1-haircut);fric+=amount-net;decl[k]=amount
                    legal,reserve,_=parent_profit(legal,net,S,reserve,continue_reserve=c['parent_governance_reserve'])
                    if c['delay']==0:cash['P']+=net;lots.items['P'].extend(packed)
                    else:pending.append({'src':k,'due':y+c['delay'],'amount':net,'lots':packed})
        for k in K:
            lot_excess=sum(v['amount'] for v in lots.items[k])-max(0,cash[k]-floor[k])
            if lot_excess>1e-8:lots.take(k,lot_excess,y,'restore_operating_floor')
            need=max(0,floor[k]-cash[k]);allow=max(0,min(c['max_debt']-borrowed,c['parent_limit']-new[k] if k=='P' else c['max_debt']-borrowed));loan=min(need,allow)
            cash[k]+=loan;debt[k]+=loan;new[k]+=loan;borrowed+=loan;fin+=loan
            # loan仅填经营底线不成为金融可分配批次。
            if cash[k]<floor[k]-1e-7:
                return {'feasible':False,'failed_year':y,'failed_bucket':k,'shortfall':floor[k]-cash[k],'rows':rows,'distributions_suspended':True}
        desired=0 if c['freeze'] and y<=5 else (c['payout'][t]*S if y<=5 else max(0,cash['P']-floor['P']))
        if y>5 and y<=5+c['special_window']:desired/=5+c['special_window']-y+1
        paid=min(desired,max(0,legal),max(0,cash['P']-floor['P']))
        lots.take('P',paid,y,'shareholder_cash');cash['P']-=paid;legal-=paid
        end=sum(cash.values())+sum(v['amount'] for v in pending)
        assert near(end,opening+totalcf-pay+fin+sale_cash-fric-paid),(y,end,opening+totalcf-pay+fin+sale_cash-fric-paid)
        assert near(sum(debt.values()),opening_debt+fin-debt_repaid)
        for k in K:assert abs(sum(v['amount'] for v in lots.items[k])-max(0,cash[k]-floor[k]))<1e-6*max(1,abs(cash[k])),(y,k,sum(v['amount'] for v in lots.items[k]),cash[k]-floor[k])
        disc=paid/S/(1+p['ke'])**y;pv+=disc
        if y<=5:dpv5+=disc
        else:tv5+=disc*(1+p['ke'])**5
        ages=[y-v['born'] for k in K for v in lots.items[k] if v['amount']>1e-7]+[y-v['born'] for x in pending for v in x['lots'] if v['amount']>1e-7]
        max_age=max(max_age,max(ages,default=0))
        row={'year':y,'ebit':eb,'rent':rent,'da':da,'maintenance':maint,'growth':grow,'trade_wc':wc,'cash_floor_addition':fd,'old_capital_payment':pay,'profit':totalnp,'cash_generated':totalcf,'tax':total_tax,'interest':total_interest,'debt_added':fin,'restricted_debt_repaid':debt_repaid,'remittance_friction':fric,'sale_cash':sale_cash,'sale_book_gain':sale_book,'dividend':paid,'dps':paid/S,'cash':copy.deepcopy(cash),'debt':copy.deepcopy(debt),'parent_legal_profit':legal,'parent_statutory_reserve':reserve,'economic_capacity_not_legal':copy.deepcopy(capacity),'unrecovered_budget_losses':copy.deepcopy(losses),'declared':decl,'pending_cash':sum(v['amount'] for v in pending),'cash_floor':floor,'financial_lots':copy.deepcopy(lots.items) if trace else None,'flows':flows}
        rows.append(row);old_floor=floor
    # 不补一个终端倍数；长数值尾部通过400/800年收敛校验，全部仍在账的批次明列。
    return {'feasible':True,'value_per_share':pv,'dividend_pv_first5':dpv5,'terminal_equity_per_share':tv5,'terminal_pv_share':(pv-dpv5)/pv if pv else 0,'dps':[r['dps'] for r in rows[:5]],'rows':rows,'remaining_financial_lots':lots.items,'pending':pending,'max_financial_age':max_age,'cash':cash,'debt':debt,'lot_events':lots.history if trace else [],'n':n,'parameters':p,'config':c}

def disposal(asset_cash,noncash_assets,asset_haircut,all_external_liabilities,exit_cost,tax_basis,ownership,parent_book_cost,parent_tax_basis,tax=.25):
    proceeds=asset_cash+noncash_assets*(1-asset_haircut)
    asset_gain=max(0,proceeds-tax_basis-exit_cost);asset_tax=asset_gain*tax
    after_cost=proceeds-exit_cost-asset_tax
    creditor_paid=min(max(0,after_cost),all_external_liabilities)
    equity=max(0,after_cost-all_external_liabilities)
    owner_proceeds=equity*ownership
    parent=equity_sale(owner_proceeds,parent_book_cost,parent_tax_basis,tax)
    return {'feasible':after_cost>=all_external_liabilities-1e-8,'exit_fees_shortfall':max(0,exit_cost+asset_tax-proceeds),'gross_realization':proceeds,'noncash_haircut':noncash_assets*asset_haircut,'asset_tax':asset_tax,'creditor_paid':creditor_paid,'creditor_shortfall':max(0,all_external_liabilities-after_cost),'gross_equity':equity,'minority_cash':equity*(1-ownership),'parent':parent,'common_cash':max(0,parent['cash'])}

def cases():
    out={'base':copy.deepcopy(BASE)}
    x=copy.deepcopy(BASE);x.update(scale=[.78,.80,.90,1,1],capscale=[1,1,1.05,1.05,1.05],extra_wc=[8,3,-4,-3,0],delay=1);out['cyclical']=x
    x=copy.deepcopy(BASE);x.update(scale=[.65,.65,.62,.60,.60],capscale=[1.1]*5,extra_rent=[5]*5,extra_wc=[8,3,2,2,2],rate=.045,delay=1);out['structural_unmitigated']=x
    x=copy.deepcopy(x);x.update(scale=[.65,.65,.60,.58,.58],project=[15,18,18,10.29,0],growth=[0,0,2,3,3],freeze=True);out['structural']=x
    x=copy.deepcopy(BASE);x.update(scale=[1.08,1.10,1.12,1.15,1.15],capscale=[1.05,1.05,1.1,1.1,1.1],extra_wc=[2]*5);out['upside']=x
    for name,updates in {'delay3':{'delay':3},'delay5':{'delay':5},'zero_parent_legacy':{'parent_legacy':0},'availability80':{'availability':.80},'availability100':{'availability':1.},'overseas_friction30':{'overseas_remit_friction':.30},'tax25':{'tax_cn':.25},'investment_zero_tax_basis':{'investment_tax_basis':0},'block5':{'release_block':5},'tail_ebit_minus10':{'tail_ebit_delta':-10},'continue_parent_reserve':{'parent_governance_reserve':True},'special_window8':{'special_window':8},'parent_statutory_zero':{'parent_statutory_initial':0},'book_adjustment_minus5':{'book_adjustment':-5.},'book_adjustment_plus5':{'book_adjustment':5.}}.items():
        c=copy.deepcopy(BASE);c.update(updates);out[name]=c
    return out

def tests():
    # 正式run调用的同一函数：正利润/负经营利润/处置损失/未来弥亏。
    c,l=economic_profit(9.5,0,-4,.95);assert near(c,5.7) and l==0
    c,l=economic_profit(c,l,-9,.95);assert c==0 and near(l,3)
    c,l=economic_profit(c,l,2,.95);assert c==0 and near(l,1)
    c,l=economic_profit(c,l,5,.95);assert near(c,3.8) and l==0
    sale=equity_sale(18,20,18,.25)
    assert sale['cash']==18 and sale['accounting_gain']==-2
    c,l=economic_profit(9.5,0,sale['accounting_gain'],.95)
    assert near(c,7.6) and l==0 # 18本金未成为新利润
    c,l=economic_profit(c,l,3,.95);assert near(c,10.45) and l==0
    # 累计亏损不会留下虚假的可宣派额度；两个比例均走生产函数。
    for rate in [.8,.95,1.]:
        c,l=0.,0.
        for profit in [20,-30,5,13.0419]:c,l=economic_profit(c,l,profit,rate)
        assert near(c,8.0419*rate) and l==0
    assert parent_profit(0,10,20,5,paid_in=10)==(9.,6.,1.)
    assert parent_profit(-5,8,20,5)==(2.7,5.3,.30000000000000004)
    assert parent_profit(0,10,20,10)==(10,10,0)
    conv=capitalise(20,10,10,10,10,3);assert conv=={'registered':30,'paid_in':20,'shares':15,'capital_reserve':0,'cash':3}
    assert parent_profit(0,10,conv['registered'],10)==(9,11,1)
    a=flow(-10,2,3,4,0,0,.25);assert a['tax']==0
    a=flow(10,2,3,4,2,1,.25);assert a['profit']==6 and a['cash']==2
    cash,old_legal=receive_old_receivable(1,8,9);assert old_legal==8. and cash==10. # receipt branch in run has no parent_profit call
    a=capital_return(20,10,10,4,.8,.2);assert near(a['shares'],6) and near(a['original_holder_cash'],3) and a['profit']==-.2
    a=equity_sale(10,8,3,.25,1);assert a['tax']==1.5 and a['cash']==7.5 and a['accounting_gain']==-.5
    a=disposal(2,8,.5,7,.5,10,.8,3,2);assert a['common_cash']==0 and a['creditor_paid']==5.5 and not a['feasible']
    a=disposal(0,0,0,0,5,0,1,0,0);assert not a['feasible'] and a['exit_fees_shortfall']==5
    a=disposal(2,8,0,4,.5,10,.8,3,2);assert near(a['minority_cash'],1.1) and near(a['parent']['tax'],.6)
    c=copy.deepcopy(BASE);c.update(scale=[0]*5,max_debt=0,parent_limit=0,freeze=True,extra_wc=[200]*5)
    assert not run(c,PARAM['low'],10,False)['feasible']
    # run级集成：先盈利再连续负经营利润，锁住前四年上划后才宣派。
    stress=copy.deepcopy(BASE);stress.update(scale=[1,.05,.05,1,1],release_block=4,max_debt=400,parent_limit=400,freeze=True)
    rr=run(stress,PARAM['low'],5,False);assert rr['feasible']
    for k in K[:-1]:
        profits=sum(row['flows'][k]['profit'] for row in rr['rows'])
        declared=sum(row['declared'][k] for row in rr['rows'])
        assert declared<=max(0,profits)*stress['availability']+1e-8
    # 前一年利润留在账、次年零租前营业利润后即宣派；旧公式曾超累计利润。
    loss_now=copy.deepcopy(BASE);loss_now.update(scale=[1,0,0,1,1],release_block=1,max_debt=400,parent_limit=400,freeze=True)
    rr=run(loss_now,PARAM['low'],2,False);assert rr['feasible']
    for k in K[:-1]:
        cumulative=sum(row['flows'][k]['profit'] for row in rr['rows'])
        assert sum(row['declared'][k] for row in rr['rows'])<=max(0,cumulative)*loss_now['availability']+1e-8
    rr=run(BASE,PARAM['low'],11,False)
    year10=rr['rows'][9];previous=rr['rows'][8]
    expected=max(0,previous['economic_capacity_not_legal']['E']/BASE['availability']-previous['unrecovered_budget_losses']['E']+year10['flows']['E']['profit']+year10['sale_book_gain'])*BASE['availability']
    assert near(year10['declared']['E'],expected)
    return {'run_negative_profit_sequence':'pass','run_same_year_disposal':'pass','loss_offsets_existing_capacity':'pass','loss_recovery_no_double_deduction':'pass','disposal_loss_same_period':'pass','principal_not_profit':'pass','cumulative_profit_capacity_bound':'pass','registered_not_paid_in':'pass','prior_loss_first':'pass','statutory_cap':'pass','registered_conversion':'pass','negative_tax_no_refund':'pass','operating_hand_case':'pass','old_receivable_no_new_profit':'pass','pro_rata_capital_return_shares':'pass','book_vs_tax_basis':'pass','all_creditors_before_equity':'pass','minority_once':'pass','zero_dividend_insufficient_funding':'pass'}

def auxiliary(result,p):
    # 独立企业现金法：无金融收益；利息不进FCFF，期初仅扣一次非船租金融债。
    if not result['feasible']:return None
    c=result['config'];present=0.
    for row in result['rows']:
        e=row['ebit'];y=row['year'];factor=(1+p['g'])**max(0,y-5)
        taxes=sum(max(0,e*W[k]+c['book_adjustment']*W[k]*factor)*(c['overseas_tax'] if k=='O' else c['tax_cn']) for k in K)
        fcff=e-taxes-.02*factor+row['da']-row['maintenance']-row['growth']-row['trade_wc']-row['cash_floor_addition']-row['old_capital_payment']
        present+=fcff/(1+p['wacc'])**y
    sale=equity_sale(INV*c['investment_sale'],INV,c['investment_tax_basis'],.25)
    bridge=C-sum(F.values())+R-D+SEC/(1+p['wacc'])**c['security_year']+sum(SEC*c['security_yield']*(1-c['tax_cn'])/(1+p['wacc'])**y for y in range(1,c['security_year']+1))+sum(INV*c['investment_yield']*(1-c['tax_cn'])/(1+p['wacc'])**y for y in range(1,11))+sale['cash']/(1+p['wacc'])**10
    return {'value_per_share':(present+bridge)/S,'operating_pv':present,'asset_debt_bridge':bridge,'no_cash_income_or_minority_double_add':True}

def cohort_checks(results):
    checks={}
    for name,eps in results.items():
        for ep,r in eps.items():
            if not r['feasible']:continue
            # 最后20年新生余额允许尚在付款流程，早于此的每个批次必须已退出金融池。
            remaining=[v for arr in r['remaining_financial_lots'].values() for v in arr]+[v for x in r['pending'] for v in x['lots']]
            old=[v for v in remaining if v['born']<=r['n']-20 and v['amount']>1e-6]
            assert not old,(name,ep,old)
            births={v['born'] for v in r['lot_events'] if v['tag']=='future_financial'}
            assert set(range(1,r['n']-20)).issubset(births)
            shareholder=[x for x in r['lot_events'] if x['purpose']=='shareholder_cash']
            paid_initial=sum(x['amount'] for x in shareholder if x['born']==0)
            checks[name+'_'+ep]={'all_future_birth_years_checked':r['n']-20,'old_unsettled_batches':len(old),'maximum_observed_financial_age':r['max_financial_age'],'opening_financial_cash_reaching_shareholder':paid_initial,'last_20_years_remaining_not_written_off':remaining}
    return checks

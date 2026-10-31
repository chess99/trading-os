"""Self contained CNY billion budget, no prices; legal-entity allocations are estimates."""
import json,math,copy
SHARES=.5286
NAMES=['parent','gujing_sales_and_wholly_owned','huanghelou_51','other_60','glass_9769','construction_52']
OWN=[1,1,.51,.60,.9769,.52]
COST=[0,.33815990343,.816,.44992,.08526745306,.00572]
# Remaining small investments included in full-owned cost; sum matches mother subsidiary investments.
COST[1]=1.69407990343-sum(COST[2:])
EQ=[21.6,0,1.7,.600000311725,.1,.04]
EQ[1]=26.08140320036+sum(COST)-sum(EQ)
CASH=[7.3,2.85,.5,.3,.15,0]
CASH[-1]=11.23525974456-sum(CASH)
LOCK=[0,.36,.10,.03,0,.00820670699]
RE=[14.6,2,.5,.13,.03,.01]
REG=[.5286,.2,.4,.3,.0887103,.011]
RES=[.2643,.06,.12,.04,.025,.003]
DEBT=[0,0,.3,.12,0,.053099487]
PAY=[.85,.025,.08,.03,.005,.01]
ALLOC=[.76,.17,.035,.02,.01,.005]
INVEST=[.82,.03,.08,.04,.02,.01]
FLOOR=[1.15,.65,.18,.09,.03,.02]
IC=[0,0,.0722061,.4203452,0,0]
# Product entry volumes in thousand tonnes and net CNY thousand per tonne, gives billion.
CASES={
'base':{'vol':[58,31,17],'price':[205,52,88],'growth':[0,.025,.03,.025,.02],'gm':.797,'sell':.34,'admin':.073,'rd':.005,'levy':.17,'r':.105,'tailg':.015},
'core_low':{'vol':[57,31,17],'price':[203,52,88],'growth':[0,.02,.025,.02,.015],'gm':.794,'sell':.345,'admin':.074,'rd':.005,'levy':.17,'r':.11,'tailg':.0125},
'core_high':{'vol':[59,31,17],'price':[207,52,88],'growth':[0,.03,.035,.03,.025],'gm':.800,'sell':.335,'admin':.072,'rd':.005,'levy':.17,'r':.10,'tailg':.0175},
'cyclical':{'vol':[53,30,16],'price':[200,51,86],'growth':[0,.01,.06,.05,.03],'gm':.79,'sell':.35,'admin':.078,'rd':.005,'levy':.17,'r':.105,'tailg':.015},
'structural':{'vol':[48,30,14],'price':[180,48,80],'growth':[0,-.02,-.01,0,0],'gm':.76,'sell':.36,'admin':.085,'rd':.005,'levy':.175,'r':.115,'tailg':0},
'upside':{'vol':[61,32,18],'price':[211,53,90],'growth':[0,.04,.045,.04,.03],'gm':.81,'sell':.32,'admin':.07,'rd':.005,'levy':.17,'r':.10,'tailg':.02},
'channel_entry':{'regions':[13.65,.83,.62,.03],'growth':[0,.022,.025,.022,.018],'gm':.795,'sell':.342,'admin':.075,'rd':.005,'levy':.17,'r':.105,'tailg':.015},
}

def legal_step(s,profit,cashprofit,investment,debtpay,projectpay,unlock,restricted_income,desired,minimum,reserve_cap,ic_in=0,ic_out=0):
    """Production primitive, called for each legal node in each official state."""
    z=dict(s); old=dict(s)
    z['locked']+=restricted_income
    release=min(z['locked'],max(0,unlock)); z['locked']-=release
    z['cash']+=cashprofit-investment-debtpay-projectpay+release+ic_in-ic_out
    z['ic_receivable']=s.get('ic_receivable',0)-ic_in;z['ic_payable']=s.get('ic_payable',0)-ic_out
    z['debt']-=debtpay; z['payable']-=projectpay; z['capital']+=investment
    available=max(0,s['re']+profit)
    appropr=min(max(0,reserve_cap-s['reserve']),.1*max(0,profit-max(0,-s['re'])))
    z['reserve']+=appropr; z['re']+=profit-appropr; z['equity']+=profit
    dividend=min(max(0,desired),max(0,z['cash']-minimum),max(0,z['re']))
    z['cash']-=dividend;z['re']-=dividend;z['equity']-=dividend
    if z['cash'] < -1e-8:raise ValueError('financing failure, negative cash forbidden')
    residual=z['cash']+z['locked']+z['capital']+z['investment_cost']+z['ic_receivable']-z['ic_payable']-z['debt']-z['payable']-z['equity']
    assert abs(residual)<max(1e-7,abs(z['equity'])*1e-10),(residual,z)
    return z,{'profit':profit,'cash_profit':cashprofit,'net_investment':investment,'debt_paid':debtpay,'project_paid':projectpay,'restricted_income':restricted_income,'release':release,'ic_collection':ic_in,'ic_repayment':ic_out,'reserve_added':appropr,'dividend':dividend,'cash_residual':z['cash']-(old['cash']+cashprofit-investment-debtpay-projectpay+release+ic_in-ic_out-dividend),'equity_residual':z['equity']-(old['equity']+profit-dividend),'balance_residual':residual}

def run(name='base',years=240,overrides=None):
    p=copy.deepcopy(CASES[name]);p.update(overrides or {})
    revenue=sum(p['regions']) if 'regions' in p else sum(v*q/1000 for v,q in zip(p['vol'],p['price']))+.20
    startrev=revenue; states=[]; nodes=[]
    for i,n in enumerate(NAMES):
        cash=CASH[i]+(.42225290186+p.get('other_financial',.1) if i==0 else 0)
        locked=LOCK[i]; eq=EQ[i];debt=DEBT[i];pay=PAY[i]+(.000813225465 if i==0 else 0)
        cost=sum(COST) if i==0 else 0
        icasset=sum(IC) if i==0 else 0;icliab=IC[i]
        nodes.append(dict(name=n,cash=cash,locked=locked,capital=eq+debt+pay+icliab-cash-locked-cost-icasset,ic_receivable=icasset,ic_payable=icliab,investment_cost=cost,debt=debt,payable=pay,equity=eq,re=RE[i],reserve=RES[i]))
    if p.get('minority_cash_shift'):
        a=p['minority_cash_shift'];nodes[0]['cash']-=a;nodes[0]['capital']+=a;nodes[2]['cash']+=a;nodes[2]['capital']-=a
    group0=sum(x['equity'] for x in nodes)-sum(COST)
    common0=nodes[0]['equity']+sum(OWN[i]*nodes[i]['equity']-COST[i] for i in range(1,6))
    pv=0; pvpost5=0; residualpv=0; dividends=[]; prevrev=revenue; prevcommon=common0; prevgroup=group0
    for t in range(1,years+1):
        if t>1:
            g=p['growth'][t-1] if t<=5 else (p['growth'][4]+(p['tailg']-p['growth'][4])*min(1,(t-5)/10))
            revenue*=1+g
        factor=revenue/startrev
        # Recovery retains elevated promotion. Cyclical branch normalises expense by Y5, not structural.
        sell=p['sell']; gm=p['gm']; admin=p['admin']
        if name=='cyclical':
            f=min(1,max(0,(t-1)/4));sell+=f*(.34-.35);gm+=f*(.797-.79);admin+=f*(.073-.078)
        ebit=revenue*(gm-sell-admin-p['rd']-p['levy'])-.012*factor
        # First five years include completion investments and slow inventory accumulation; afterwards capital tracks sales.
        growcap=([.45,.40,.35,.25,.15][t-1] if t<=5 else max(0,revenue-prevrev)*.45)
        wc=([.26,.24,.20,.18,.16][t-1] if t<=5 else (revenue-prevrev)*.50)
        if name=='structural':wc+=.15*factor if t<=5 else 0
        if p.get('extra_capital'):growcap+=p['extra_capital']*factor
        if p.get('channel_refund') and t==1:wc+=p['channel_refund']
        maintenance=.92*factor; annual=[]; parentup=0;nci=0; ownprofits=[];iccollected=0;icinterest=0
        # Children first. No recognition of unreceived distributions. Same-year remittance budget explicitly conditional.
        for i in list(range(1,6))+[0]:
            s=nodes[i]; op=ebit*ALLOC[i]; debtinterest=s['debt']*.04
            icpaid=min(s['ic_payable'],IC[i]/5) if not (p.get('ic_delay') and t<=p['ic_delay']) else 0
            iccharge=(min(.42,s['ic_payable'])*.03 if i==3 else 0)
            if i==0:op+=icinterest
            else:op-=iccharge
            fin=s['cash']*.02; restricted=s['locked']*.02*.75
            operating_tax=max(0,op-debtinterest)*.25
            ownprofit=op-debtinterest-operating_tax+fin*.75+restricted
            profit=ownprofit+(parentup if i==0 else 0)
            cashprofit=profit-restricted
            debtpaid=min(s['debt'],DEBT[i]/5)
            projectpaid=min(s['payable'],(PAY[i]+(.000813225465 if i==0 else 0))/3)
            # Locked principal/earnings remain locked through two periods; 25% released Y3, rest Y4.
            unlock=(s['locked']*.25 if t==3 else s['locked']+restricted if t==4 else 0)
            if p.get('lock_years') and t<=p['lock_years']:unlock=0
            if p.get('lock_years') and t==p['lock_years']+1:unlock=s['locked']+restricted
            netinvestment=(growcap+wc)*INVEST[i]
            floor=FLOOR[i]*factor
            if i==0:
                desired=SHARES*[2.8,2.9,3.1,3.3,3.5][t-1] if t<=5 else max(0,profit)*.9+max(0,s['cash']-floor)*.20
            else:desired=max(0,profit)*(.65 if t<=5 else .95)+max(0,s['cash']-floor)*(.06 if t<=5 else .20)
            if p.get('no_upstream') and i>0 and t<=p['no_upstream']:desired=0
            icpaid=min(icpaid,max(0,s['cash']+cashprofit-netinvestment-debtpaid-projectpaid+unlock-floor))
            z,flow=legal_step(s,profit,cashprofit,netinvestment,debtpaid,projectpaid,unlock,restricted,desired,floor,REG[i]/2,iccollected if i==0 else 0,icpaid)
            nodes[i]=z;flow.update(name=NAMES[i],own_profit=ownprofit,financial_income_after_tax=fin*.75+restricted,operating_tax=operating_tax,ownership=OWN[i],maintenance=maintenance*INVEST[i],depreciation=maintenance*INVEST[i])
            if i>0:
                parentup+=flow['dividend']*OWN[i];nci+=flow['dividend']*(1-OWN[i]);iccollected+=icpaid;icinterest+=iccharge
            annual.append(flow);ownprofits.append((i,ownprofit))
        d=annual[-1]['dividend'];dividends.append(d/SHARES)
        group=sum(x['equity'] for x in nodes)-sum(COST)
        common=nodes[0]['equity']+sum(OWN[i]*nodes[i]['equity']-COST[i] for i in range(1,6))
        gp=sum(v for i,v in ownprofits);cp=sum(v*OWN[i] for i,v in ownprofits)
        gres=group-(prevgroup+gp-d-nci);cres=common-(prevcommon+cp-d)
        assert abs(gres)<max(1e-7,group*1e-10) and abs(cres)<max(1e-7,common*1e-10)
        discount=(1+p['r'])**t; residual=(cp-p['r']*prevcommon)/discount;residualpv+=residual;pv+=d/discount
        if t>5:pvpost5+=d/discount
        state={'year':t,'revenue':revenue,'ebit_ex_financial':ebit,'net_capital':growcap+wc,'maintenance':maintenance,'upstream':parentup,'common_dividend':d,'minority_dividend':nci,'group_profit':gp,'common_profit':cp,'common_equity':common,'group_equity':group,'common_equity_residual':cres,'group_equity_residual':gres,'cash':sum(x['cash'] for x in nodes),'locked':sum(x['locked'] for x in nodes),'dividend_pv':d/discount,'residual_income_pv':residual,'cumulative_pv':pv,'nodes':copy.deepcopy(nodes),'flows':annual,'normalized':{'cash_to_revenue':sum(x['cash'] for x in nodes)/revenue,'common_equity_to_revenue':common/revenue,'dividend_to_revenue':d/revenue}}
        states.append(state);prevgroup=group;prevcommon=common;prevrev=revenue
    return {'case':name,'years':years,'assumptions':p,'initial_common_equity':common0,'initial_group_equity':group0,'value_per_share':pv/SHARES,'post5_pv_share':pvpost5/pv,'year5_equity_value_per_share':pvpost5*(1+p['r'])**5/SHARES,'distributions':dividends[:5],'residual_income_value_per_share':(common0+residualpv-common/(1+p['r'])**years)/SHARES,'last_pv':states[-1]['dividend_pv']/SHARES,'states':states}

def main():
    out={k:run(k) for k in CASES}
    for k,o in [('ic_collection_delayed',{'ic_delay':5}),('holder_low',{'r':.11}),('holder_high',{'r':.10}),('other_financial_zero',{'other_financial':0}),('other_financial_upper',{'other_financial':.23}),('margin_minus_1pct',{'sell':.35}),('minority_cash_shift',{'minority_cash_shift':1}),('restricted_ten_years',{'lock_years':10}),('upstream_delayed',{'no_upstream':5}),('channel_refund',{'channel_refund':1.0}),('completion_overrun',{'extra_capital':.1})]:out[k]=run('base',overrides=o)
    out['tail_extension']=run('base',480)
    print(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()

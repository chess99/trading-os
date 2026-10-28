"""独立literal重建；不导入生产文件、不以生产inputs为输入。"""
import json, pathlib, copy
ROOT=pathlib.Path(__file__).resolve().parent

def literal(name):
    D=[1640,1870,2080,2245,2400,2520,2620,2700,2750,2800];R=[180,240,310,390,470,540,600,650,690,720];J=[80,96,110,121,131,138,144,150,155,160]
    M=[.33,.33,.325,.32,.315,.30,.285,.27,.26,.25];N=[.25,.26,.27,.28,.28,.27,.26,.25,.24,.23];Q=[.15,.15,.15,.15,.15,.14,.135,.13,.125,.12]
    w=[.12]*10;build=[250,160,80]+[0]*7;k=.105;g=.025;roic=.15;c=.34;part=.9;payout=.5;fin_fraction=.25;include_reserve=name in ['reserve_conditional_grant','upside_reserve_granted','maximum_grant_business_stress']
    balances=[1550,269.86597613,30];loans=[0,3.17227943,4.47555138]
    if name=='low':k,g,roic=.11,.02,.14
    if name=='high':k,g,roic=.10,.025,.16
    if name=='cyclical':
        factors=[.8,.85,.95]+[1]*7;penalty=[.05,.03,.01]+[0]*7
        D=[x*y for x,y in zip(D,factors)];R=[x*y for x,y in zip(R,factors)];J=[x*y for x,y in zip(J,factors)]
        M=[x-y for x,y in zip(M,penalty)];N=[x-y for x,y in zip(N,penalty)];Q=[x-y for x,y in zip(Q,penalty)];w=[.16,.16,.14]+[.12]*7;build=[150,160,130,50]+[0]*6
    if name=='structural':D=[1300,1350]+[1400]*8;R=[140,160,180,200,210,220,230,230,230,230];M=[.18]*10;N=[.16]*10;Q=[.10]*10;w=[.18]*10;g=.01;roic=.1
    if name in ['upside','upside_reserve_granted']:D=[x*1.15 for x in D];R=[x*1.15 for x in R];M=[x+.02 for x in M];N=[x+.02 for x in N]
    if name=='maximum_grant_business_stress':D=[x*2 for x in D];R=[x*2 for x in R];J=[x*2 for x in J]
    if name=='margin_minus_3pp':M=[x-.03 for x in M];N=[x-.03 for x in N]
    if name=='demand_minus_20pct':D=[x*.8 for x in D];R=[x*.8 for x in R]
    if name=='capital_50pct':c=.5
    if name=='parent_profit_60pct':part=.6;balances=[1250,569.86597613,30]
    if name=='financial_gate_none':fin_fraction=0
    if name=='financial_gate_all':fin_fraction=1
    if name=='deposit_excluded':balances[0]-=160
    if name=='no_other_debt':loans[1]=0
    if name=='all_other_payables_debt':loans[1]=5.05557835
    if name=='cost_of_equity9':k=.09
    if name=='cost_of_equity12':k=.12
    if name=='payout25':payout=.25
    if name=='roic_equals_cost':roic=.105
    if name=='extra_project100':build[0]+=100
    capital_surplus=[887.31127393,0,0]
    grants=[]; outcomes={}
    for reserve in [False,True]:
        total_shares=.2475 if reserve else .99
        total_cost=15.856825 if reserve else 63.4273
        opening=0 if reserve else 7.34999118
        for i,weight in enumerate([.33,.33,.34]):
            grants.append({'id':('reserve' if reserve else 'first')+'-'+str(i+1),'enabled':not reserve or include_reserve,'end':i+2,'test':i+1,'cost':total_cost*weight,'start':opening*weight,'recognized':opening*weight,'old_ratio':1,'shares':total_shares*weight})
    if name in ['sbc_opening_first_only','sbc_opening_last_only']:
        which=0 if name=='sbc_opening_first_only' else 2
        for i,pool in enumerate(grants[:3]):pool['start']=pool['recognized']=7.34999118 if i==which else 0
    owners=[1,1,.55];working=[125.548648416,13.949849824,10];profits=[568.42422395,100,20];reserves=[118.75012332,10,5];stock=400.01;extra=121.4283;dps_sofar=0;capacity=2024.63587552;old_run=None;rows=[]
    for j in range(10):
        sales=D[j]+R[j];core_profit=D[j]*M[j]+R[j]*N[j]
        revenues=[sales*part,sales*(1-part),J[j]];op=[core_profit*part,core_profit*(1-part),J[j]*Q[j]]
        fixed_increment=c*max(0,sales-capacity);capacity=max(capacity,sales)
        invest=[build[j]+part*fixed_increment,(1-part)*fixed_increment,c*max(0,J[j]-(J[j-1] if j else J[j]))]
        needs=[x*.08 for x in revenues];new_wc=[x*w[j] for x in revenues];dw=[new_wc[z]-working[z] for z in range(3)];working=new_wc[:]
        cash_profit=[op[z]+balances[z]*.015-loans[z]*.05 for z in range(3)]
        minority=.363757149*1.1**(j+1)
        recurring=sum(op[z]*owners[z] for z in range(3))+sum(balances[z]*.015*owners[z] for z in range(3))*fin_fraction-sum(loans[z]*.05*owners[z] for z in range(3))-minority
        if j<3:
            growth=max((sales+J[j])/1700-1,recurring/(593.4+7-.2-.2)-1)
            lower=[.2,.4,.6][j];upper=[.5,1,1.5][j]
            outcomes[j+1]=0 if growth<lower-1e-12 else min(1,.6+.4*(growth-lower)/(upper-lower))
        issuance=0;expense=0;reversal=0;pool_results=[]
        for grant in grants:
            rate=outcomes.get(grant['test'],1) if grant['enabled'] else 0
            service=grant['start']/grant['cost']+(1-grant['start']/grant['cost'])*min(j+1,grant['end'])/grant['end'] if grant['enabled'] else 0
            target=grant['cost']*rate*service
            before=grant['recognized'];adjusted=before*rate/grant['old_ratio'] if grant['old_ratio'] else 0
            catchup=adjusted-before;newservice=target-adjusted
            exp=max(catchup,0)+max(newservice,0);rev=max(-catchup,0)+max(-newservice,0)
            newshares=grant['shares']*rate if grant['enabled'] and j+1==grant['end'] else 0
            expense+=exp;reversal+=rev;issuance+=newshares
            pool_results.append(dict(pool=grant['id'],active=grant['enabled'],ratio=rate,service_fraction=service,previous_recognized=before,expense=exp,reversal=rev,cumulative_recognized=target,issued_shares=newshares,max_shares=grant['shares']))
            grant['recognized']=target;grant['old_ratio']=rate
        cashin=issuance*max(59.275-dps_sofar,1.000001);stock+=issuance
        provision=[];acct=[]
        for z in range(3):
            profit=cash_profit[z]-(expense-reversal if z==0 else 0)
            acct.append(profit);loss=max(-profits[z],0);newreserve=min(max(profit-loss,0)*.1,max([stock,50,20][z]*.5-reserves[z],0));provision.append(newreserve)
            profits[z]+=profit-newreserve;reserves[z]+=newreserve;balances[z]+=cash_profit[z]-dw[z]-invest[z]
        capital_surplus[0]+=cashin-issuance+expense-reversal
        balances[0]+=cashin;extra=max(extra-fixed_increment,0)
        blocked=sum(build[j+1:])+(90.93+83.9647)*max(2-j,0)/3+extra
        mincash=[needs[0]+blocked,needs[1],needs[2]]
        for z in range(3):
            repayment=min(loans[z],max(balances[z]-mincash[z],0));loans[z]-=repayment;balances[z]-=repayment
            borrow=max(mincash[z]-balances[z],0);loans[z]+=borrow;balances[z]+=borrow
        common_profit=sum(x*y for x,y in zip(cash_profit,owners))-minority;div=min(max(common_profit*payout,0),max(profits[0],0),max(balances[0]-mincash[0],0));balances[0]-=div;profits[0]-=div;dps=div/stock;dps_sofar+=dps
        run=sum(x*y for x,y in zip(needs,owners));dr=0 if old_run is None else run-old_run;old_run=run
        fc=sum((op[z]-dw[z]-invest[z])*owners[z] for z in range(3))
        rows.append(dict(sbc_pools=pool_results,sbc_expense=expense,sbc_reversal=reversal,contract_recurring_profit_ex_sbc=recurring,capital_surplus=capital_surplus[:],cash=balances[:],debt=loans[:],noncash_wc=working[:],legal_retained=profits[:],legal_reserve=reserves[:],accounting_profit=acct,statutory_provision=provision,shares=stock,distribution=div,dps=dps,common_owner_fcfe=fc-dr,required_cash=needs,restricted_parent_cash=blocked,issued_shares=issuance,issue_proceeds=cashin,nopat=op))
    b5=sum((rows[4]['cash'][z]-rows[4]['debt'][z]-rows[4]['required_cash'][z])*owners[z] for z in range(3))-3.63757149*1.1**5-rows[4]['restricted_parent_cash']+rows[4]['restricted_parent_cash']*.015/k
    tail=sum(x*y for x,y in zip(rows[-1]['nopat'],owners))*(1+g)*(1-g/roic)/(k-g)
    future=sum(rows[j]['common_owner_fcfe']/(1+k)**(j-4) for j in range(5,10))+tail/(1+k)**5
    terminal=(future+b5)/rows[4]['shares'];dpv=sum(rows[j]['dps']/(1+k)**(j+1) for j in range(5))
    aux=(D[4]*M[-1]+R[4]*N[-1]+J[4]*Q[-1]*.55)*(1+g)*(1-g/roic)/(k-g)
    return {'years':rows,'value':dpv+terminal/(1+k)**5,'terminal5':terminal,'auxiliary_value':dpv+(aux+b5)/rows[4]['shares']/(1+k)**5}

names=['base','low','high','sbc_opening_first_only','sbc_opening_last_only','maximum_grant_business_stress','cyclical','structural','upside','margin_minus_3pp','demand_minus_20pct','capital_50pct','parent_profit_60pct','reserve_not_granted','reserve_conditional_grant','upside_reserve_granted','financial_gate_none','financial_gate_all','deposit_excluded','no_other_debt','all_other_payables_debt','cost_of_equity9','cost_of_equity12','payout25','roic_equals_cost','extra_project100']
independent={n:literal(n) for n in names}
# Only now load observed production output, never its model or inputs.
production=json.loads((ROOT/'2026-Q3-output.json').read_text())['scenarios']
errors=[]
def compare(a,b,path):
    if isinstance(a,dict):
        for k in a:compare(a[k],b[k],path+'/'+k)
    elif isinstance(a,list):
        for i,v in enumerate(a):compare(v,b[i],path+'/'+str(i))
    elif isinstance(a,(str,bool)):
        assert a==b,(path,a,b)
    else:
        e=abs(a-b);errors.append(e)
        assert e<1e-8,(path,a,b,e)
for n in names:compare(independent[n],production[n],n)
print(json.dumps({'independent_results':independent,'max_absolute_difference':max(errors),'numbers_compared':len(errors),'no_production_import':True},ensure_ascii=False,indent=2,sort_keys=True))

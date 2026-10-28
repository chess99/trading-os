"""新快照独立Decimal复算；仅读输出作比较，不导入生产脚本/其assumptions。"""
from decimal import Decimal as D,getcontext
from pathlib import Path
import json
getcontext().prec=40
ROOT=Path(__file__).parent
actual=json.loads((ROOT/'2026-Q3-output.json').read_text())
def seq(s):return list(map(D,s.split()))
def independent(kind='base',r='.105',price='1',delay=0,extra=0,release='.2',early=False,zero=False,principal='0',arb=False):
    main=seq('7.2 7.8 8.4 8.8 9 9.1 9.1 8.5 4.675 3.74 2.992 2.3936 1.91488 1.531904')
    other=seq('.5 .7 .9 1 1.1 1.15 1.2 1.2 1.1 1 .85 .7 .55 .4')
    rd=seq('.65 .75 .85 .95 1 1 1 .95 .8 .65 .5 .4 .3 .2');lic=seq('.1 .15 .2 .2 .2 .15 .15 .1 .05 .03 0 0 0 0')
    cap=seq('.12 .15 .18 .2 .2 .15 .12 .1 .08 .07 .06 .05 .04 .03');dep=seq('.08 .09 .1 .11 .12 .12 .12 .12 .1 .09 .08 .07 .06 .05')
    sale=seq('.36 .35 .34 .34 .34 .34 .35 .36 .4 .4 .4 .4 .4 .4')
    if kind=='cyclical':
        for i,m in enumerate(seq('.85 .9 .97')):main[i]*=m;other[i]*=m
        sale[:2]=seq('.39 .38')
    if kind=='structural':
        for i in range(14):
            main[i]*=D('.7')*D('.93')**i;other[i]*=D('.65');sale[i]=D('.42')
            if i>=3:rd[i]*=D('.75')
    if kind=='optimistic':
        mods=seq('1 1.1 1.18 1.25 1.3 1.3 1.3 1.3 1.15 1.15 1.15 1.15 1.15 1.15')
        for i in range(14):main[i]*=mods[i];other[i]*=D('1.25');rd[i]*=D('1.2');lic[i]*=D('1.5');cap[i]*=D('1.2')
    for j in range(1,extra+1):
        main.append(D('1.531904')*D('.8')**j);other.append(D('.4')*D('.75')**j);rd.append(D('.2')*D('.8')**j);lic.append(D(0));cap.append(D('.03')*D('.8')**j);dep.append(D('.05')*D('.8')**j);sale.append(D('.4'))
    c=D('3.53070676363');s=D('.19637183653');locked=D('4.27760262553')-D(principal);u=D('3.24853945402');v=D(0);reserve=D(0);pending=D(0);wc=D('-.35816603907');rows=[]
    for i in range(len(main)):
        received=pending;c+=pending;s-=pending
        mat=min(locked,(D('4.27760262553')-D(principal))/3) if delay<=i<delay+3 else D(0);locked-=mat;c+=mat
        fi=(c+locked)*D('.015');si=s*D('.015')
        rev=main[i]*D(price)+other[i];cogs=main[i]*D(price)*D('.04')+other[i]*D('.30');sales=rev*sale[i];admin=rev*D('.025')+D('.03');sur=rev*D('.013')
        pre=rev-cogs-sales-admin-sur-rd[i]-lic[i]-dep[i];op=pre-max(D(0),pre)*D('.15')
        loss=D('.23316379655') if arb and i==0 else D(0)
        old=D('.01880004734') if arb and i==0 else D(0)
        pp=op*D('.8')+fi-loss;sp=op*D('.2')+si
        sa=min(max(D(0),D('.1225')-reserve),max(D(0),sp+min(D(0),v))*D('.1'));reserve+=sa;v+=sp-sa
        newwc=rev*(D('.10') if kind=='cyclical' and i<2 else D('.06'));change=newwc-wc;fcf=op+dep[i]-cap[i]-change;wc=newwc
        c+=fcf*D('.8')+fi-loss-old*D('.2');s+=fcf*D('.2')+si+old*D('.2')
        settlement=(D('1.118') if i==0 else D(0)) if early else ([D('.4'),D('.4'),D('.318')][i] if i<3 else D(0))
        c-=settlement;s+=settlement;buy=D('.13070676363') if i==0 else D(0);c-=buy
        assert c>=D('.65') # 全生产路径无需融资，不掩盖失败
        pending=min(max(D(0),v),max(D(0),s-D('.15')))/2 if i>=5 else D(0);v-=pending;pp+=pending;u+=pp
        target=max(D(0),op*(D('.25') if i<5 else D('.7')))+(max(D(0),c-D('.65'))*D(release) if i>=5 else D(0))
        div=min(target,max(D(0),u),max(D(0),c-D('.65')));c-=div;u-=div
        rows.append(dict(nwc_cash_change=change,shared_nwc_cash_change=change-old,parent_old_claim_paid_from_nwc=old,parent_total_claim_cash=old+loss,parent_oneoff_loss=loss,group_cash_after_oneoff=fcf-loss,revenue=rev,main_revenue=main[i]*D(price),other_revenue=other[i],cogs=cogs,sales=sales,admin=admin,surcharge=sur,rd=rd[i],license=lic[i],dep=dep[i],capex=cap[i],pretax=pre,op=op,nwc=wc,fcf=fcf,parent_profit=pp,subs_profit=sp,parent_retained=u,subs_retained=v,parent_reserve=D('.225'),subs_reserve=reserve,parent_reserve_add=D(0),subs_reserve_add=sa,parent_cash=c,subs_cash=s,deposits=locked,debt=D(0),interest=D(0),financial_income=fi+si,settlement=settlement,buyback=buy,sub_declared=pending,sub_received=received,dividend_receivable=pending,dividend=div,dps=div/D('.45'),financial_net=c+s+locked,target_dividend=target))
    end=c+s+locked+wc+D('.15')+(D(0) if zero else D('.24210563687'));discount=1+D(r)
    value=(sum(z['dividend']/discount**(i+1) for i,z in enumerate(rows))+end/discount**len(rows))/D('.45')
    tv=(sum(z['dividend']/discount**(i-4) for i,z in enumerate(rows) if i>=5)+end/discount**(len(rows)-5))/D('.45')
    return rows,value,tv,end
checks=[]
def verify(label,observed,**args):
    rows,val,tv,end=independent(**args);diff=[]
    assert len(rows)==len(observed['years'])
    for a,b in zip(rows,observed['years']):
        for k,v in a.items():diff.append(abs(v-D(str(b[k]))))
    for a,k in [(val,'value'),(tv,'terminal5'),(end,'exit')]:diff.append(abs(a-D(str(observed[k]))))
    assert max(diff)<D('1e-9'),(label,max(diff))
    checks.append(dict(label=label,year_count=len(rows),value=str(val),max_abs_error=str(max(diff))))
for k,v in actual['cases'].items():verify(k,v,kind=k)
verify('core_low',actual['core_low'],r='.115',price='.97');verify('core_high',actual['core_high'],r='.095',price='1.03')
for k,args in {'price_minus10':{'price':'.9'},'deposit_delay3':{'delay':3},'discount_plus1':{'r':'.115'},'finite_tail2045':{'extra':5},'no_extra_release':{'release':'0'},'internal_pay_early':{'early':True},'equity_zero':{'zero':True},'principal_minus100m':{'principal':'.1'},'arbitration_loss':{'arb':True}}.items():verify(k,actual['sensitivities'][k],**args)
aux=[]
for idx,(cash,rate) in enumerate([('3','.115'),('3.4','.095')]):
    prior=D('-.35816603907');pv=D(0);r=D(rate)
    for t in range(1,15):
        fade=D(1) if t<=8 else D('.75')**(t-8);wc=D('.462')*fade;change=wc-prior;flow=D(cash)*fade-change;prior=wc;pv+=flow/(1+r)**t
        for k,v in [('nwc',wc),('nwc_change',change),('cash',flow)]:assert abs(v-D(str(actual['auxiliary'][idx]['years'][t-1][k])))<D('1e-9')
    exitcash=prior+D('.15')+D('.24210563687');opening=D('1.12214593170')+D('2.67422590483')+D('.48101753424')+D('3.90268976167')-D('.10610467038')-D('.2')
    val=(opening+pv+exitcash/(1+r)**14)/D('.45');assert abs(val-D(str(actual['auxiliary'][idx]['value'])))<D('1e-9');aux.append(str(val))
legal=[]
for loss,label in [(D(0),'sub_profit_reserve'),(D(-1),'sub_profit_loss_then_collection')]:
    u=loss;res=D(0);v=D(0);pending=D(0);cash=D(0)
    for i in range(7):
        cash+=pending;v+=1;decl=v/2 if i>=5 else D(0);v-=decl;add=min(D(5)-res,max(D(0),decl+min(D(0),u))/10);res+=add;u+=decl-add;pending=decl
        obs=actual['hand_tests'][label]['years'][i]
        for k,value in [('parent_profit',decl),('parent_retained',u),('parent_reserve',res),('parent_cash',cash)]:assert abs(D(str(obs[k]))-value)<D('1e-9')
    legal.append(dict(label=label,last_retained=str(u),reserve=str(res),cash=str(cash)))
assert abs(D(str(actual['hand_tests']['cash']['value']))-D(12)/D('1.1'))<D('1e-9')
assert abs(D(str(actual['hand_tests']['loss']['years'][0]['dividend']))-D('.9'))<D('1e-9')
assert abs(D(str(actual['hand_tests']['mother_only_oneoff']['value']))-D('10.5')/D('1.1'))<D('1e-9')
assert actual['hand_tests']['mother_only_oneoff']['years'][0]['subs_profit']==0
print(json.dumps(dict(status='PASS',method='independent literal Decimal; no production import/assumptions',checks=checks,auxiliary=aux,legal_chain=legal),ensure_ascii=False,indent=2))

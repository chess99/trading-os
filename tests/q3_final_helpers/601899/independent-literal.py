
def read_full_output(path):
    import gzip,base64,hashlib
    obj=json.loads(path.read_text())
    if obj.get('schema')=='zijin-full-output-gzip-base64-v1':
        packed=base64.b64decode(obj['payload_base64'],validate=True)
        assert hashlib.sha256(packed).hexdigest()==obj['gzip_sha256']
        raw=gzip.decompress(packed)
        assert len(raw)==obj['expanded_bytes'] and hashlib.sha256(raw).hexdigest()==obj['expanded_sha256']
        return json.loads(raw)
    return obj

"""Independently coded literal-budget reconstruction. Does not import production code.
Literal units: bn CNY, kt copper/lithium, tonnes gold. Only compares output at end.
"""
import json,math
from pathlib import Path
# metal, ownership, q1..q5, recoverable, life, cost,DA,maintenance,cap1..5
DATA='''cu|.5816|300,330,350,350,350|17000|40|31000|5000|6000|1.2,.8,.6,.4,.4
cu|1|180,190,200,200,195|2300|14|24000|4500|6000|1,1,1,.6,.5
cu|.63|125,135,145,150,150|5000|24|39000|6000|7500|1,1,1,.8,.5
cu|.67|115,110,100,85,70|500|6|34000|4000|5000|.2,.2,.1,.1,0
cu|1|108,115,120,125,125|2500|30|30000|5000|6000|1,1.2,1,.8,.5
cu|1|85,80,70,60,50|450|8|29000|4000|5000|.1,.1,.1,0,0
cu|.5359|38,65,76,76,76|1800|25|33000|5000|6500|1,.3,.2,.2,.2
cu|.76|80,85,90,90,90|1300|18|34000|5000|6500|.7,.8,.8,.6,.4
cu|.396|350,420,480,500,500|14500|35|44000|9000|10000|6,4,3,2,2
cu|1|0,0,0,20,70|2300|30|36000|6000|7000|2,2.5,2.5,1.5,.5
au|.5897|8.8,9,9,9,9|130|15|265|35|55|.2,.2,.2,.2,.2
au|.85|8,9,10,10,10|177|22|400|50|80|.6,.7,.7,.4,.3
au|.8075|8,8.5,9,9,9|145|22|350|45|70|.5,.7,.7,.4,.3
au|.85|8,8,8,8,8|94|14|430|55|80|.3,.3,.3,.3,.3
au|.85|7,8,9,10,10|76|16|310|40|65|.5,.6,.6,.3,.2
au|.595|6,6,6,6,6|62|12|280|35|60|.2,.3,.3,.2,.1
au|.85|5,5.5,6,6,6|75|20|320|50|75|.4,.4,.4,.3,.2
au|.8388361627233438|46,47,49,50,50|780|22|290|40|65|2,2.5,2.5,2,1.5
au|.2126938|15,16,17,18,18|210|18|400|45|75|.8,.9,.9,.7,.5
li|.63|25,30,35,40,40|1800|30|55000|7000|9000|.5,.5,.4,.3,.2
li|1|25,30,35,40,40|1500|30|50000|7000|9000|.5,.5,.4,.3,.2
li|1|40,45,50,50,50|1000|25|60000|6000|9000|.4,.4,.3,.3,.2
li|.549|30,55,75,90,100|2800|30|55000|7000|10000|2,1.5,1,.5,.4
li|.262|14,15,15,15,15|400|25|30000|3000|5000|.1,.1,.1,.1,.1'''
def rebuild(gold,copper,lithium,rate,cashfactor,debtfactor,assetfactor):
    annual=[[0.,0.] for _ in range(40)]
    ends=[];weights=[]
    for index,line in enumerate(DATA.splitlines()):
        metal,own,qty,stock,life,cost,da,maint,cap=line.split('|')
        own=float(own);qty=list(map(float,qty.split(',')));stock=float(stock)*(.85 if metal=='li' else 1);life=int(life)
        cost=float(cost);da=float(da);maint=float(maint);cap=list(map(float,cap.split(',')))
        weights.append(own*qty[0]*{'cu':.08,'au':.85,'li':.09}[metal] if index not in (8,18) else 0.)
        invested=0.;last=-1
        delivery_remaining=(240000-213807.41)*.0000311034768
        for j in range(40):
            planned=(qty[j] if j<5 else qty[4]*.995**(j-4)) if j<life else 0
            q=min(stock,planned);stock-=q;factor=1.015**j/(1000 if metal=='au' else 1000000)
            sales=q*{'au':gold,'cu':copper,'li':lithium}[metal]*factor
            earnings=sales*.945-q*cost*factor*1.003**j
            profit=earnings*(.76 if earnings>0 else 1)
            flow=profit+q*(da-maint)*factor-(cap[j] if j<5 else 0)-(sales*.015 if j<5 else 0)
            if j<5:invested+=sales*.015
            if q>0:last=j
            if index==18:
                wassa=q*.35;first=min(wassa,delivery_remaining/.105)
                sold1=first*.105;delivery_remaining=max(0,delivery_remaining-sold1)
                sold2=(wassa-first)*.055
                stream=(sold1*.8+sold2*.7)*gold*1.015**j/1000*(.2585*.62*.9)
                profit-=stream/own;flow-=stream/own
            annual[j][0]+=profit*own;annual[j][1]+=flow*own
        ends.append(last)
        annual[last][0]-=invested*.02*own
        annual[last][1]+=invested*.98*own
    # Independent literal opening portfolio bridge, already attributable balances.
    group=(35.3254895292,16.844962462114985,5.010779109515934,47.27217902060259)
    def settle(amounts,year,weight=1.):
        inv,rec,credit,liability=amounts
        loss=(inv*.05+rec*.02+credit*.20)*weight
        annual[year][0]-=loss
        annual[year][1]+=(inv+rec+credit-liability)*weight-loss
    for index,w in enumerate(weights):
        if w: settle(group,ends[index],.7*w/sum(weights))
    settle(group,25,.3)
    settle((.6288861469275758,.15574424361424324,.02699845689234232,.47584137329385756-.03951398919*.2585*.8228),ends[18])
    settle((2.013821964,2.135512764,3.192315588,2.046334752),ends[8])
    for j in range(40):
        f=1.015**j;s=1 if j<5 else max(0,(25-j)/21)
        other=(8+min(j,4)*.5)*f*s;overhead=7.5*f*(1 if j<5 else max(.15,(40-j)/36))
        annual[j][0]+=other-overhead;annual[j][1]+=other-overhead-(1.8 if j<5 else .6)*f*s
    parentdebt=10.326890067+22.075727251+20.929911054+43.254379669
    total=35.207599259+27.941847860+41.904209712+64.633685387+.222222739-.012086635
    cb=24.4972
    joint=(.907076+.916897+.315435+.075532+.066728-.129481+2.744807)*.495*7-9.284632475
    sc=(76.776449446-6.119465016)*cashfactor-10.006048855-.310902731*29.82*.88+(6.033056952-.251781916-.535727062-(.152391571-.03824932403)-.13372439190)*.2585+.310902731*29.82*.88*.2585
    pc=6.119465016;pd=parentdebt;sd=(total-parentdebt-21.5)*debtfactor+cb+joint
    assets=((13.141995727+15.006467342+2.694675079)*.8+3.242001754+1.175240077+(4.741664751+.440994803)*.262+.388460245+.288414821+.141983058-.7-(3.333987700-1.425577447))*assetfactor
    re=14.622428427;sr=1.316465612;shares=26.616998241;reg=2.6616998241;closure=8*1.015**39
    dist=[];trace=[]
    for j,(profit,cf) in enumerate(annual):
        t=j+1;minimum=15 if t<=5 else max(15,closure+sum(max(0,-x[1]) for x in annual[t:]))
        interest_parent=pd*.033;interest_sub=max(0,sd-cb)*(.033+joint/((total-parentdebt-21.5)*debtfactor+joint)*.042)+(.139972 if cb>10.5 else 0)
        group_profit=profit-interest_parent-interest_sub+(pc+sc)*.015
        direct=min(2,max(0,profit*.06));sp=profit-direct-interest_sub+sc*.015
        pp=direct-interest_parent+pc*.015
        sc+=cf-direct-interest_sub+sc*.015;pc+=pp
        allowance=max(0,sp)*.65;extra=max(0,sc-minimum-sd-allowance)*.65 if t>5 and t%3==0 else 0
        gross=min(allowance+extra,max(0,sc-minimum));net=gross*.97
        sc-=gross;pc+=net;pp+=net
        if t==1:pc+=.077474592*18.56+.0262*10.70
        if t==3:sd-=13.9972;cb-=13.9972;pd+=13.9972;sc+=assets*.97;group_profit-=assets*.03;assets=0
        if t==5:sd-=10.5;cb-=10.5;pd+=10.5
        reserve_add=min(max(0,reg*.5-sr),max(0,pp-max(0,-re))*.1)
        re+=pp-reserve_add;sr+=reserve_add
        desired=max(0,group_profit-gross*.03)*(.35 if t<=5 else .7)
        if extra>0 and pd+sd<1e-8:desired+=extra*.97
        cap=min(10,max(0,190-pd-sd));a=max(0,3-pc);b=max(0,minimum-sc)
        assert a+b<=cap+1e-8
        pc+=a;pd+=a;sc+=b;sd+=b
        allowed=max(0,pc-3)+cap-a-b if t<=5 else max(0,pc-3-pd/(41-t))
        d=min(desired,max(0,re-2),allowed);borrow=max(0,d+3-pc)
        pd+=borrow;pc+=borrow-d;re-=d
        pay=min(max(0,sd-cb),max(0,sc-minimum));sd-=pay;sc-=pay
        pay=min(pd,max(0,pc-3));pd-=pay;pc-=pay
        dist.append(d/shares);trace.append([pc,sc,pd,sd,re,sr])
    residual=max(0,pc+sc-pd-sd-closure);assert pc+sc-pd-sd-closure>=0
    dist += [0,residual/shares]
    pv=sum(x/(1+rate)**(i+1) for i,x in enumerate(dist))
    tv=sum(x/(1+rate)**(i-4) for i,x in enumerate(dist) if i>=5)
    return dict(current=pv,terminal_year5=tv,five_year_dps=dist[:5],annual=annual,trace=trace)
if __name__=='__main__':
    p=Path(__file__).parent;actual=read_full_output(p/'2026-Q3-output.json')['cases'];checks={}
    for name,args in [('base',(850,80000,90000,.095,.78,.75,1)),('core_low',(810,77000,85000,.10,.74,.79,.95)),('core_high',(890,83000,95000,.09,.82,.71,1.05)),('gold_minus_100',(750,80000,90000,.095,.78,.75,1))]:
        r=rebuild(*args);a=actual[name];errors=[abs(r[k]-a['values'][k]) for k in ['current','terminal_year5']]
        for j in range(40):
            errors.extend(abs(r['trace'][j][i]-a['financing'][j][key]) for i,key in enumerate(['parent_cash','sub_cash','parent_debt','sub_debt','parent_re','statutory_reserve_budget']))
            errors.extend([abs(r['annual'][j][0]-a['operations'][j]['profit']),abs(r['annual'][j][1]-a['operations'][j]['fcf'])])
        assert max(errors)<1e-8,(name,max(errors));checks[name]={'max_absolute_error':max(errors),'current':r['current'],'tv5':r['terminal_year5'],'five_year_dps':r['five_year_dps']}
    (p/'independent-literal-output.json').write_text(json.dumps(checks,indent=2));print(json.dumps(checks,indent=2))

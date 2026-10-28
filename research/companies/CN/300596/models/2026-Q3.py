#!/usr/bin/env python3
"""利安隆经济预算，亿元；stdout 是完整确定性 JSON，未读取行情/外部文件。"""
import json, copy
S=2.29619667
F=dict(cash=20.1010664173,parent_cash=8.4999897194,debt=39.8918366226,parent_debt=18.50420146,retained=3.7588349652,reserve=1.0337783199,capital=S,nci=1.3748068389,book=51.5550381579,nonop=.4545495239)
B=dict(anti=[58,62.5,67,71,75,78,81,84,87,90],lube=[15,16.5,18,19.5,21,22,23,24,25,26],new=[.7,1,1.4,1.8,2.2,2.5,2.8,3.1,3.4,3.7],am=[.12,.122,.124,.125,.125,.124,.123,.122,.121,.12],lm=[.095,.10,.105,.11,.115,.116,.117,.118,.119,.12],ne=[-.4,-.35,-.2,0,.1,.15,.2,.25,.3,.35],da=[4.2,4.6,4.9,5.2,5.4,5.5,5.6,5.7,5.8,5.9],maintenance=[3.3,3.5,3.7,3.9,4.1,4.2,4.3,4.4,4.5,4.6],growth=[5.4,4,2,1.4,1.3,1.3,1.3,1.3,1.3,1.3],extra_wc=[.5,.3]+[0]*8,up=[1.5,1.8,2.1,2.5,3,3.4,3.8,4.2,4.6,5],ownprofit=[.1,.15,.2,.25,.3,.35,.4,.45,.5,.55],owncash=[0,.1,.15,.2,.25,.3,.35,.4,.45,.5],fund=[2,1.5,.8,.5]+[.4]*6,settle=[-1,-.5]+[0]*8,dps=[.45,.5,.6,.7,.8,.9,1,1.1,1.2,1.3],minority=[-.12,-.1,-.05,0,.02,.04,.06,.08,.1,.12],repay=[0,0,.5,1,1.5,2,2.5,3,3,3],buyout=[0,.6]+[0]*8,acquisition=[.4955815529]+[0]*9,nci_retire=[0,.054]+[0]*8,rate=.032,tax=.17,wc=.22,prior_sales=67,g=.02,roic=.11,yield_rate=.01,pc_floor=3,sc_floor=7,sc_repay_floor=9,child_scale=[1]*10)
# 三家全资成熟子公司的未分配利润/公积缺单体完整表：期初两者均以零作预算，非事实。
CHILD=[('中卫',1.25,1.4990559776,.50),('凯亚',.36,1.3426936172,13/30),('科润',.106875,.4223655154,1/15)]
def legal(retained,reserve,capital,profit):
    add=min(.1*max(profit-max(-retained,0),0),max(.5*capital-reserve,0))
    return retained+profit-add,reserve+add,add

def run(p,f=None):
    f=copy.deepcopy(F if f is None else f); p=copy.deepcopy(p)
    pc=f['parent_cash']; sc=f['cash']-pc; pd=f['parent_debt']; sd=f['debt']-pd
    pr=f['retained']; reserve=f['reserve']; nci=f['nci']; book=f['book']; prev=p['prior_sales']
    child=[dict(name=n,capital=c,profit0=np,weight=w,retained=0.,reserve=0.) for n,c,np,w in CHILD]
    for j,c in enumerate(child):
        c['retained']=p.get('child_opening_retained',[0,0,0])[j]
    rows=[]; internal_loan=0.0
    for i in range(10):
        internal_loan+=p['fund'][i]
        cash0=pc+sc; debt0=pd+sd; pc0=pc;sc0=sc;pd0=pd;sd0=sd
        sales=p['anti'][i]+p['lube'][i]+p['new'][i]
        ebit=p['anti'][i]*p['am'][i]+p['lube'][i]*p['lm'][i]+p['ne'][i]; nopat=ebit*(1-p['tax'])
        pi=pd*p['rate']*(1-p['tax']); si=sd*p['rate']*(1-p['tax'])
        fin=max(cash0-p['pc_floor']-p['sc_floor'],0)*p['yield_rate']
        wc=p['wc']*(sales-prev)+p['extra_wc'][i]
        capex=p['maintenance'][i]+p['growth'][i]
        supplier=capex-p['buyout'][i]-p['acquisition'][i]
        assert supplier>=-1e-9
        free=nopat+p['da'][i]-capex-wc-pi-si+fin
        ref=f['parent_debt']*.032*(1-p['tax'])
        ownprofit=p['ownprofit'][i]+ref-pi; owncash=p['owncash'][i]+ref-pi
        sub_pre=sc+free-owncash+p['fund'][i]-p['settle'][i]
        childdetail=[]; proposed=[]
        for c in child:
            profit=c['profit0']*(p['anti'][i]/58)*p['child_scale'][i]
            r,z,a=legal(c['retained'],c['reserve'],c['capital'],profit)
            proposed.append(max(0,min(p['up'][i]*c['weight'],r)))
            childdetail.append(dict(name=c['name'],opening_retained=c['retained'],statutory_profit=profit,reserve_add=a,reserve=z,pre_distribution_retained=r))
        up=min(sum(proposed),max(sub_pre-p['sc_floor'],0),max(.45*nopat,0))
        for c,d,v in zip(child,childdetail,proposed):
            d['paid_dividend']=v*up/sum(proposed) if sum(proposed)>0 else 0
            c['retained']=d['pre_distribution_retained']-d['paid_dividend'];c['reserve']=d['reserve'];d['closing_retained']=c['retained']
            assert d['paid_dividend']<=max(d['pre_distribution_retained'],0)+1e-9
        statutory=ownprofit+up; prepr,reserve,ra=legal(pr,reserve,f['capital'],statutory)
        prep=pc+owncash+up-p['fund'][i]+p['settle'][i]; pres=sub_pre-up
        ndiv=max(p['minority'][i],0)*.2
        div=max(0,min(p['dps'][i]*S,max(prepr,0),max(prep-p['pc_floor'],0),max(cash0+free-ndiv-p['pc_floor']-p['sc_floor'],0)))
        pn=max(p['pc_floor']-(prep-div),0);sn=max(p['sc_floor']-(pres-ndiv),0)
        pp=min(pd,p['repay'][i],max(prep-div-p['pc_floor'],0));sp=min(sd,max(pres-ndiv-p['sc_repay_floor'],0))
        pc=prep-div+pn-pp;sc=pres-ndiv+sn-sp;pd=pd+pn-pp;sd=sd+sn-sp;pr=prepr-div
        # 母公司2029年8亿元债到期；其余年初债50%滚续为预算，不冒充逐笔到期事实。
        maturity=min(pd0,.5*max(pd0-(8 if i<3 else 0),0)+(8 if i==2 else 0))
        pgross=max(pp,maturity);pborrow=pgross-pp+pn;sgross=max(sp,.5*sd0);sborrow=sgross-sp+sn
        premium=max(p['buyout'][i]-p['nci_retire'][i],0)
        nci_premium=premium*.4882  # 回购主体创聚的少数股东承担其对应净资产减额，条件经济预算
        nci+=p['minority'][i]-ndiv-p['nci_retire'][i]-nci_premium
        commonprofit=nopat-pi-si+fin-p['minority'][i]
        book+=commonprofit-div-premium+nci_premium
        assert abs(pc-(pc0+owncash+up-p['fund'][i]+p['settle'][i]-div+pborrow-pgross))<1e-8
        assert abs(sc-(sc0+free-owncash+p['fund'][i]-p['settle'][i]-up-ndiv+sborrow-sgross))<1e-8
        assert abs(pc+sc-(cash0+free-div-ndiv+pn+sn-pp-sp))<1e-8
        assert abs(pd+sd-(debt0+pborrow+sborrow-pgross-sgross))<1e-8
        assert pc>=p['pc_floor']-1e-8 and sc>=p['sc_floor']-1e-8
        assert pn+sn<12, '年度新增融资预算不可行'
        if prepr<0: assert div==0
        rows.append(dict(year=i+1,sales=sales,ebit=ebit,nopat=nopat,da=p['da'][i],maintenance=p['maintenance'][i],growth=p['growth'][i],cash_investment=capex,supplier_payment=supplier,acquisition_payment=p['acquisition'][i],government_buyout=p['buyout'][i],nci_buyout_premium_share=nci_premium,wc=wc,parent_interest_aftertax=pi,sub_interest_aftertax=si,financial_cash_income=fin,group_free_cash=free,parent_own_profit=ownprofit,parent_own_cash=owncash,parent_project_funding=p['fund'][i],parent_internal_loan_receivable=internal_loan,sub_internal_loan_payable=internal_loan,parent_trade_net_receipt=p['settle'][i],child_legal=childdetail,upstream_declared_and_received=up,parent_statutory_profit=statutory,parent_reserve_add=ra,parent_reserve=reserve,parent_retained=pr,common_distribution=div,dps=div/S,nci_dividend=ndiv,parent_cash=pc,subsidiary_cash=sc,parent_debt=pd,subsidiary_debt=sd,parent_net_new=pn,sub_net_new=sn,parent_net_repay=pp,sub_net_repay=sp,parent_gross_borrowing=pborrow,parent_gross_repayment=pgross,sub_gross_borrowing=sborrow,sub_gross_repayment=sgross,group_cash=pc+sc,group_debt=pd+sd,nci_book=nci,nci_profit=p['minority'][i],common_book=book))
        prev=sales
    return rows

def price(rows,p,k,f=None,delay=0):
    f=F if f is None else f;r=rows[-1];g=p['g'];floor=p['pc_floor']+p['sc_floor']
    operating=r['nopat']*(1+g)*(1-g/p['roic'])/(k-g)
    excess=max(r['group_cash']-floor,0)/(1+k)**delay
    nci=max(r['nci_book'],max(r['nci_profit'],0)*(1+g)/(k-g))
    terminal=operating+excess+f['nonop']-r['group_debt']-nci
    pvdiv=sum(r['common_distribution']/(1+k)**r['year'] for r in rows)
    tv5=(sum(r['common_distribution']/(1+k)**(r['year']-5) for r in rows[5:])+terminal/(1+k)**5)/S
    q=rows[4];auxend=q['nopat']/k+max(q['group_cash']-floor,0)+f['nonop']-q['group_debt']-max(q['nci_book'],max(q['nci_profit'],0)/k)
    aux=(sum(r['common_distribution']/(1+k)**r['year'] for r in rows[:5])+auxend/(1+k)**5)/S
    return dict(k=k,value=(pvdiv+terminal/(1+k)**10)/S,terminal_year5=tv5,terminal_year10=terminal/S,terminal_operating=operating,terminal_excess_cash=excess,terminal_debt=r['group_debt'],terminal_nci=nci,terminal_pv_fraction=(terminal/(1+k)**10)/(pvdiv+terminal/(1+k)**10),auxiliary_value=aux)

def cases():
    out={'base':copy.deepcopy(B)}
    c=copy.deepcopy(B);c['rate']=.042
    for i in range(3):
        c['anti'][i]*=[.88,.90,.96][i];c['lube'][i]*=[.88,.90,.96][i];c['am'][i]-=.015;c['lm'][i]-=.015;c['ne'][i]-=.1;c['minority'][i]-=.04;c['extra_wc'][i]+=.3;c['up'][i]*=.65;c['ownprofit'][i]-=.1;c['owncash'][i]-=.1;c['settle'][i]-=.3;c['child_scale'][i]=.75
    out['cyclical']=c
    c=copy.deepcopy(B);c.update(rate=.045,g=.01,roic=.08)
    for i in range(10):
        c['anti'][i]=54*1.025**i;c['lube'][i]=14*1.03**i;c['new'][i]=.5+.1*i;c['am'][i]=.09;c['lm'][i]=.07;c['ne'][i]=-.4 if i<3 else -.2;c['up'][i]*=.55;c['ownprofit'][i]-=.1;c['owncash'][i]-=.1;c['fund'][i]*=.8;c['growth'][i]=[5.4,4,1,.7,.6,.6,.6,.6,.6,.6][i];c['extra_wc'][i]+=.2;c['minority'][i]=-.12 if i<3 else -.08;c['child_scale'][i]=.6
    out['structural']=c
    c=copy.deepcopy(B);c.update(g=.025,roic=.13)
    for i in range(10):
        c['anti'][i]*=1.03+.007*i;c['lube'][i]*=1.04+.01*i;c['am'][i]+=.007;c['lm'][i]+=.015;c['ne'][i]+=.04*i;c['growth'][i]+=.4;c['up'][i]*=1.15;c['dps'][i]*=1.1;c['minority'][i]+=.02*i;c['child_scale'][i]=1.10
    out['optimistic']=c
    for delta in [-.01,.01]:
        c=copy.deepcopy(B);c['am']=[x+delta for x in c['am']];out['anti_margin_'+str(delta)]=c
    c=copy.deepcopy(B);c['up']=[x*.5 for x in c['up']];c['settle'][1]-=2;out['upstream_delay_and_settlement']=c
    for extra in [1.5,4]:
        c=copy.deepcopy(B);c['growth'][1]+=extra;c['buyout'][1]+=extra;c['fund'][1]+=extra;out['buyout_extra_'+str(extra)]=c
    c=copy.deepcopy(B);c['nci_retire']=[0]*10;out['buyout_no_nci_retirement']=c
    return out

def handtests():
    p=copy.deepcopy(B)
    for key,v in p.items():
        if isinstance(v,list):p[key]=[0]*10
    p.update(rate=0,tax=1,wc=0,prior_sales=0,g=0,yield_rate=.01)
    f=dict(F,cash=12,parent_cash=5,debt=0,parent_debt=0,retained=10,reserve=2,nci=0,nonop=0)
    p['dps'][0]=1/S;r=run(p,f)[0]
    assert abs(r['group_cash']-11.02)<1e-10 and abs(r['parent_cash']-4)<1e-10
    p['dps'][0]=0;p['repay'][0]=1;f.update(debt=1,parent_debt=1);r=run(p,f)[0]
    assert abs(r['parent_cash']-4)<1e-10 and r['parent_debt']==0 and abs(r['group_cash']-11.02)<1e-10
    f.update(retained=-1,reserve=0,debt=0,parent_debt=0);p['ownprofit'][0]=2;r=run(p,f)[0]
    assert abs(r['parent_reserve_add']-.1)<1e-10 and abs(r['parent_retained']-.9)<1e-10
    p['ownprofit'][0]=.5;r=run(p,f)[0];assert r['parent_reserve_add']==0 and r['parent_retained']==-.5 and r['dps']==0
    # 同一法定函数用于生产子公司及母公司，历史亏损先弥补。
    assert legal(-1,0,10,2)==(.9,.1,.1)
    cp=copy.deepcopy(p);cp['child_opening_retained']=[-1,0,0];cp['anti'][0]=58;cp['child_scale'][0]=2/1.4990559776
    ch=run(cp,f)[0]['child_legal'][0]
    assert abs(ch['reserve_add']-.1)<1e-10 and abs(ch['closing_retained']-.9)<1e-10
    p['tax']=0;p['ne']=[1]*10;p['ownprofit']=[0]*10;p['owncash']=[1]*10;p['dps']=[1/S]*10;p['yield_rate']=0;p['pc_floor']=5;p['sc_floor']=5;p['sc_repay_floor']=5
    f.update(cash=10,parent_cash=5,retained=20,reserve=2);rows=run(p,f);v=price(rows,p,.1,f)
    assert abs(v['value']-10/S)<1e-10
    return {'production_nonzero_cash':{'cash_start':12,'financial_income':.02,'distribution':1,'cash_end':11.02},'production_parent_principal':{'parent_cash_start':5,'repayment':1,'parent_cash_end':4,'debt_end':0},'production_loss_cure':{'retained_start':-1,'profit':2,'reserve_add':.1,'retained_end':.9},'production_child_loss_cure':{'opening_retained':-1,'statutory_profit':2,'reserve_add':.1,'closing_retained':.9},'production_unrepaired_loss':{'profit':.5,'retained_end':-.5,'dividend':0},'production_perpetuity':{'annual_distribution':1,'k':.1,'value':10/S},'passed':True}

def main():
    result={'units':'亿元；每股元；股数亿股','shares':S,'facts':F,'child_budget':CHILD,'handtests':handtests(),'scenarios':{}}
    for name,p in cases().items():
        r=run(p);result['scenarios'][name]={'inputs':p,'rows':r,'valuation':[price(r,p,k) for k in [.11,.10]]}
    r=result['scenarios']['base']['rows'];result['terminal_cash_delay_3_years']=[price(r,B,k,delay=3) for k in [.11,.10]]
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Independent literal reconstruction. Does NOT import/run production model.
Hard-coded base economic inputs; independently evolves all three entities for ten years,
then checks production JSON field-by-field and both 5Y/10Y valuation chains.
"""
import json, math
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from pathlib import Path
D=json.loads((Path(__file__).parent/'2026-Q3-output.json').read_text())
checks=[]
def eq(a,b,label):
    if isinstance(a,list):
        for j,(x,y) in enumerate(zip(a,b)):eq(x,y,label+str(j))
        return
    assert abs(a-b)<1e-7*max(1,abs(a),abs(b)),(label,a,b)
    checks.append(label)
for scenario,conversion in [('base',0),('full_convert_y1',1),('full_convert_y3',3),('internal_loan_4pct',0)]:
    pc,oc,sc=650.,119.0341064,0.
    pe,oe=231.6170843,240.
    pr,orr,sr=835.81490092,40.,0.
    ps,os,ss=119.46981799,0.,0.
    cp=48.5;cap_p=313.916240; shares=313.916240;bond=694.694;bank=120.;lease=24.82907446
    loan=0.;equity=0.;wc=475.97031164;swc=0.;fix=922.08027908;sfix=0.
    rev=[1750,2000,2200,2400,2550,2700,2820,2920,3020,3100]
    margins=[.27,.28,.285,.28,.275,.27,.265,.26,.255,.25]
    cap=[350,300,250,180,150,190,200,210,220,230];dep=[90,110,130,145,155,170,180,190,200,210]
    svr=[0,162,324,459,540,550,560,570,580,590];sve=[-8,40.5,97.2,146.88,172.8,176,179.2,182.4,185.6,188.8]
    svc=[270,180,15,20,30,45,45,45,45,45];svd=[0,22.5,45,45,45,45,45,45,45,45]
    own=[];groupdiv=[];fcfs=[];incomes=[];debts=[];opening=[]
    for t in range(10):
        irate=.04 if scenario=='internal_loan_4pct' else 0.
        inter=loan*irate;ptax=inter*.15;vat=inter*.06
        y=t+1;start=pc+oc+sc+pe+oe;opening.append(start)
        if y==conversion:shares+=bond/cp;cap_p+=bond/cp;bond=0.
        coup=bond*[.001,.003,.006,.01,.015,0,0,0,0,0][t]
        redemption=bond*1.1 if y==6 else 0.
        if redemption:bond=0.
        bi=bank*.045;bp=bank if y==3 else 0.;bank-=bp
        li=lease*.04;lp=min(lease,24.82907446/5);lease-=lp
        pi,oi,si=pc*.017,oc*.017,sc*.015
        pei,oei=pe*.0136,oe*.0136
        pc+=pi;oc+=oi;sc+=si;pe+=pei;oe+=oei
        op=rev[t]*margins[t]*.85
        newwc=rev[t]*.35;dw=newwc-wc;wc=newwc
        sebit=sve[t]-svd[t];sp=sebit-max(sebit,0)*.25
        deductible=min(inter+vat,2*equity*irate*1.06,max(sebit,0));shield=deductible*.25
        newswc=svr[t]*150/540;ds=newswc-swc;swc=newswc
        fix+=cap[t]-dep[t];sfix+=svc[t]-svd[t]
        tax_timing=44.39580994/5 if y<=5 else 0.
        fcf=op+dep[t]-cap[t]-dw+sp+svd[t]-svc[t]-ds-tax_timing+shield-ptax-vat
        usep=min(pe,max(cap[t]-dep[t],0)*.6)
        useo=min(max(oe-(78 if y<3 else 0),0),max(cap[t]-dep[t],0)*.4)
        pe-=usep;oe-=useo
        pc+=usep+op*.65+dep[t]*.6-cap[t]*.6-dw*.75-coup-redemption-lp*.65-li*.65
        oc+=useo+op*.35+dep[t]*.4-cap[t]*.4-dw*.25-bi-bp-lp*.35-li*.35
        pc-=tax_timing*.65;oc-=tax_timing*.35
        pc+=inter-ptax;sc+=-inter-vat+shield
        sc+=sp+svd[t]-svc[t]-ds
        inj=min(max(20-sc,0),max(150-equity,0));equity+=inj;pc-=inj;sc+=inj
        adv=max(20-sc,0);loan+=adv;pc-=adv;sc+=adv
        repay=min(loan,max(sc-20,0));loan-=repay;sc-=repay;pc+=repay
        oldprofit=op*.35+oi+oei-bi-li*.35;scprofit=sp+si-inter-vat+shield
        oldrepair=min(max(-orr,0),max(oldprofit,0));screpair=min(max(-sr,0),max(scprofit,0))
        oldreserve=min(max(295-os,0),max(oldprofit-oldrepair,0)*.1)
        screserve=min(max(75-ss,0),max(scprofit-screpair,0)*.1)
        orr+=oldprofit-oldreserve;os+=oldreserve;sr+=scprofit-screserve;ss+=screserve
        oldup=min(max(orr,0)*.6,max(oc-40,0));scup=min(max(sr,0)*.5,max(sc-20,0)) if loan<1e-8 else 0.
        oc-=oldup;orr-=oldup;sc-=scup;sr-=scup;pc+=oldup+scup
        amort=(23 if y<=5 else (11.89443669 if y==6 else 0)) if not conversion or y<conversion else 0.
        pp=inter-ptax+op*.65+pi+pei-coup-amort-li*.65+oldup+scup
        prepair=min(max(-pr,0),max(pp,0));preserve=min(max(cap_p*.5-ps,0),max(pp-prepair,0)*.1)
        pr+=pp-preserve;ps+=preserve
        div=min(max(op+sp,0)*(.35 if y<=2 else .45),max(pr,0),max(pc-80,0));pc-=div;pr-=div
        close=pc+oc+sc+pe+oe;inc=pi+oi+si+pei+oei;debt=coup+redemption+bi+bp+lp+li
        row=D['cases'][scenario]['years'][t]
        independently=dict(internal_interest=inter,parent_interest_tax=ptax,sc_interest_deduction=deductible,sc_interest_tax_shield=shield,internal_vat=vat,internal_tax_effect=shield-ptax-vat,revenue=rev[t],ebit=rev[t]*margins[t],nopat=op,fcff=fcf,wc=wc,delta_wc=dw,sc_revenue=svr[t],sc_ebit=sebit,sc_nopat=sp,sc_wc=swc,sc_delta_wc=ds,fixed=fix,sc_fixed=sfix,capital_employed=fix+sfix+wc+swc+133.97321219,opening_financial=start,closing_financial=close,financial_interest=inc,earmark_use=[usep,useo],closing_earmark=[pe,oe],closing_free=[pc,oc,sc],coupon=coup,cb_redeemed=redemption,cb_face_remaining=bond,bank_repaid=bp,bank_remaining=bank,lease_repaid=lp,lease_remaining=lease,lease_interest=li,debt_cash=debt,sc_equity_injection=inj,sc_equity_paid=equity,sc_loan_advance=adv,sc_loan_repaid=repay,sc_loan_remaining=loan,statutory_profit=[pp,oldprofit,scprofit],legal_re=[pr,orr,sr],legal_reserve=[ps,os,ss],reserve_added=[preserve,oldreserve,screserve],loss_repair=[prepair,oldrepair,screpair],upstream_old=oldup,upstream_sc=scup,dividend=div,dps=div/shares,shares=shares)
        for k,v in independently.items():eq(v,row[k],f'{scenario}.Y{y}.{k}')
        eq(close,start+fcf+inc-debt-div,'cash-identity')
        cp=max(.01,float((Decimal(str(cp))-Decimal(str(div/shares))).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))) if bond else cp
        own.append(div/shares);groupdiv.append(div);fcfs.append(fcf);incomes.append(inc);debts.append(debt)
    terminal_profit=(op+sp)*1.02;ev=terminal_profit*(1-.02/.16)/(.10-.02);equity10=ev+close+52.89378643
    pv=sum(v/1.115**(j+1) for j,v in enumerate(own))+equity10/shares/1.115**10
    tv5=(sum(groupdiv[j]/1.115**(j-4) for j in range(5,10))+equity10/1.115**5)/shares
    actual=D['cases'][scenario]
    eq(ev,actual['terminal_ev'],scenario+'.EV10');eq(pv,actual['value_per_share'],scenario+'.value');eq(tv5,actual['terminal5_per_share'],scenario+'.TV5')
    eq(sum(own[j]/1.115**(j+1) for j in range(5))+tv5/1.115**5,pv,scenario+'.5Y-chain')
    bridge=1240.6511907+sum((fcfs[j]+incomes[j]-debts[j]-.115*opening[j])/1.115**(j+1) for j in range(10))+(ev+52.89378643)/1.115**10
    eq(bridge,actual['aggregate_value'],scenario+'.FCFF-bridge')
    if scenario=='base':literal_base=dict(dps=own[:],terminal=equity10/shares)
# Every scenario's production ledger, capital rolls and valuation identities checked from explicit rows.
for name,c in D['cases'].items():
    r=c['inputs']['discount'];last=c['years'][-1];prev=c['financial_initial']
    for row in c['years']:
        eq(row['closing_financial'],prev+row['fcff']+row['financial_interest']-row['debt_cash']-row['dividend'],name+'.all-scenario-cash')
        assert all(x>=-1e-7 for x in row['closing_free']),name
        assert not (row['converted_face'] and row['cb_redeemed'])
        prev=row['closing_financial']
    ev=(last['nopat']+last['sc_nopat'])*(1+c['inputs']['terminal_g'])*(1-c['inputs']['terminal_g']/c['inputs']['terminal_roic'])/(c['inputs']['terminal_rate']-c['inputs']['terminal_g'])
    eq(ev,c['terminal_ev'],name+'.terminal-independent')
    eq(c['value_per_share'],c['five_year_identity'],name+'.5Y-10Y')
# Independent dominant discount sensitivity from literal base cash stream, not production valuation helper.
b=D['cases']['base'];r=.135
dominant=sum(x/(1+r)**(i+1) for i,x in enumerate(literal_base['dps']))+literal_base['terminal']/(1+r)**10
expected=next(x['value_per_share'] for x in D['dominance_sensitivities'] if x['name']=='discount_plus_2pt')
eq(dominant,expected,'dominant_discount_plus_2pt')
# Contractual debt book removal and dated put, independently calculated.
for name,c in D['cases'].items():
    book=637.26896331
    for row in c['years']:
        eq(row['cb_book_open'],book,name+'.book-open')
        book+=row['cb_accretion']-row['cb_book_conversion']-row['cb_book_redeemed']
        eq(row['cb_book_close'],book,name+'.book-close')
p=D['cases']['conditional_put_y4']['years'][3]
days=(date(2030,10,27)-date(2030,1,8)).days
accrued=694.694*.015*days/365
net=637.26896331+4*23-694.694-accrued
for k,v in {'put_accrual_days':292,'put_accrued_interest':accrued,'cb_redeemed':694.694+accrued,'cb_derecognition_net':net,'cb_derecognition_tax':net*.15,'cb_book_close':0.}.items():eq(p[k],v,'dated-put.'+k)
eq(D['cases']['full_convert_y3']['years'][2]['conversion_price_at_year_start'],47.51,'rounded-conversion-price')
# Genuine first production handcase expected values, hard-coded independent arithmetic.
h=D['production_handcase']['years'][0]
for k,v in dict(revenue=100,nopat=16,delta_wc=5,existing_fcff=4,sc_fcff=-12,fcff=-8,financial_interest=2.176,coupon=.01,bank_interest=.225,lease_interest=.2,lease_repaid=1,debt_cash=1.435,sc_equity_injection=10,sc_loan_advance=4,upstream_old=6.10662,dividend=4.9,closing_financial=127.841).items():eq(h[k],v,'handcase.'+k)
print(json.dumps(dict(status='PASS',numeric_checks=len(checks),literal_scenarios=['base','full_convert_y1','full_convert_y3','internal_loan_4pct'],all_scenario_ledger_checks=len(D['cases']),imports_production=False,handcase_nonzero=True),indent=2))

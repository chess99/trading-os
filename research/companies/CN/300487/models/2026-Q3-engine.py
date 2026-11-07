#!/usr/bin/env python3
"""Standalone stdlib economic model; CNY100m except shares (100m) and per share CNY.
All prospective allocations are research budgets, NOT entity statutory forecasts.
No price inputs. Run from any cwd: python /path/2026-Q3.py > output.json
"""
import json, math, copy
S=5.08590859 # 509140859 issued less 550000 treasury
FACE=5.455263
ASOF='2026-10-28T11:01:36+00:00'
# Annualized H1 segment sizes are only allocation weights; total anchored to TTM30.2888.
WEIGHTS=[8.084164,7.40496,3.185874,4.253918,4.001118,.630690]
TTM=(2785832825.02+2176453423.64-1933406991.48)/1e8
INIT=[TTM*x/sum(WEIGHTS) for x in WEIGHTS]
NAMES=['life_science','water_ultrapure','metal_material','other_material','systems','service_other']

def cash_step(opening,operating,interest,reinvest,coupon,principal,other,recovery):
    return opening+operating+interest-reinvest-coupon-principal-other+recovery

def legal(retained,reserve,capital,profit):
    # Losses first offset by subsequent profits; no reserve on profit that merely fills loss.
    eligible=max(0,profit+min(0,retained))
    addition=min(.10*eligible,max(0,.5*capital-reserve))
    return retained+profit-addition,reserve+addition,addition

def pay(retained,reserve,capital,profit,cash,minimum,target):
    retained,reserve,addition=legal(retained,reserve,capital,profit)
    dividend=max(0,min(target,max(0,retained),max(0,cash-minimum)))
    return retained-dividend,reserve,cash-dividend,dividend,addition

PARAMS={
'core_low':dict(k=.105,g=.025,roic=.18,growth=[.16,.055,.05,.07,.025,.03],margins=[.355,.295,.29,.25,.19,.20]),
'core_high':dict(k=.095,g=.03,roic=.22,growth=[.20,.075,.065,.09,.04,.04],margins=[.385,.315,.31,.27,.21,.23]),
'cyclical':dict(k=.11,g=.02,roic=.16,growth=[.16,.055,.05,.07,.025,.03],margins=[.355,.295,.29,.25,.19,.20]),
'structural':dict(k=.12,g=.01,roic=.10,growth=[.05,.02,0,.02,0,0],margins=[.23,.22,.20,.18,.12,.14]),
'upside':dict(k=.095,g=.035,roic=.24,growth=[.24,.10,.08,.11,.06,.04],margins=[.40,.33,.32,.28,.22,.24])}

def run(p,kind='core_low',convert=False,normal=False,release=.20,delay=False,horizon=200,overseas_share=.13,remittance_rate=.05,risk_loss=.06):
    p=copy.deepcopy(p); shares=S+(FACE/59.09 if convert else 0)
    rev=INIT[:]; prev_rev=sum(rev); pm=22.0; sm=29.0926431881-pm
    # H1 known parent legal retained less Sep paid dividend, no invented Q3 statutory profit.
    pr=12.8392613104; pres=2.7616994379
    dc=sm-1.5; oc=1.5; dr=orr=0.0; dres=ores=0.0; risk_retained=-.10
    domestic_share=.45-overseas_share
    # Subsidiary capital/reserves are an aggregate conservative budget, NOT reported legal amounts.
    cap_sub=8.0; bank=.4703542275; rows=[]; pv=0.0; tv5=0.0
    finance_yield=.0125; op_capital=25.0
    for t in range(1,horizon+1):
        sm=dc+oc;oldcash=pm+sm
        if normal:
            rates=[p['g']]*6
            # Independent normalized segment sizes and net operating margins, not core forecasts.
            if t==1: rev=[8.6,8.0,3.5,5.0,4.5,1.0]; prev_rev=sum(rev)/(1+p['g'])
            else: rev=[v*(1+p['g']) for v in rev]
            margins=[.35,.29,.27,.24,.18,.18]
        else:
            fade=min(1,max(0,(t-1)/9))
            rates=[x*(1-fade)+p['g']*fade for x in p['growth']]
            if kind=='cyclical' and t<=2: rates=[-.12,-.08,-.20,-.10,-.30,-.10] if t==1 else [0,.01,-.05,0,-.10,0]
            if kind=='structural' and t<=2: rates=[-.15]*6
            rev=[v*(1+r) for v,r in zip(rev,rates)]
            margins=p['margins'][:]
            if kind=='cyclical' and t<=2:margins=[m-.065 for m in margins]
        revenue=sum(rev); earnings=sum(v*m for v,m in zip(rev,margins))-.01 # common NOPAT, excludes interest/investments
        # Margins already include R&D, normal FX friction, depreciation, tax, and losses.
        dep=revenue*.05
        nwc_rate=.32 if kind not in ('cyclical','structural') else (.39 if kind=='structural' else (.40 if t<=2 else .34))
        old_nwc=prev_rev*(.32 if t==1 else last_nwc_rate)
        dnwc=revenue*nwc_rate-old_nwc
        construction=[5.7,4.4,2.0,.7,.5][t-1] if t<=5 else 0
        if normal: growth_total=max(0,earnings*p['g']/p['roic']); capex=dep+growth_total-dnwc+construction
        elif t<=5:capex=dep+construction
        else:
            # Gradual normalization; total investment covers both fixed and working capital.
            g_eff=max(p['g'],revenue/prev_rev-1)
            capex=dep+max(0,earnings*g_eff/p['roic'])-dnwc
        capex=max(dep*.7,capex)
        reinvest=capex-dep+dnwc; op_capital+=reinvest
        fcf=earnings-reinvest
        interest_p=pm*finance_yield; interest_d=dc*finance_yield;interest_o=oc*finance_yield;interest_s=interest_d+interest_o
        loss_cost=risk_loss if t<=5 else (.05 if t==6 else 0)
        risk_retained-=loss_cost
        coupon=0 if convert else (FACE*.018 if t==1 else FACE*.025 if t==2 else 0)
        redemption=FACE*1.15 if t==3 and not convert else 0
        repay_bank=bank if t==1 else 0
        # An extra 0.8 settlement of pre-existing payables in year 1, not a new earnings expense.
        settlement=.8 if t==1 else 0
        # Non-operating investments 2.7885232 recover 80% over years8-12; gains excluded from NOPAT.
        investment_recovery=2.7885231992*.8/5 if 8<=t<=12 else 0
        investment_loss=2.7885231992*.2 if t==1 else 0
        pp=earnings*.55+interest_p-coupon-(FACE*.15 if t==3 and not convert else 0)-investment_loss
        dp=earnings*domestic_share+interest_d
        op=earnings*overseas_share+interest_o
        # Parent separately funds a non-distributing loss/exit budget. No legal offset against either positive pool.
        pcash=earnings*.55+interest_p-reinvest*.65-coupon-redemption-repay_bank-settlement+investment_recovery-loss_cost
        dcash=earnings*domestic_share+interest_d-reinvest*.35*(domestic_share/.45)
        ocash=earnings*overseas_share+interest_o-reinvest*.35*(overseas_share/.45)
        pm=cash_step(pm,earnings*.55,interest_p,reinvest*.65,coupon,redemption+repay_bank,settlement+loss_cost,investment_recovery)
        dc+=dcash;oc+=ocash
        minp=revenue*.065; mind=revenue*.045*(domestic_share/.45);mino=revenue*.045*(overseas_share/.45)
        dsupport=max(0,mind-dc);osupport=max(0,mino-oc);support=dsupport+osupport
        pm-=support;dc+=dsupport;oc+=osupport
        dt=max(0,dcash)*.90+(release*max(0,dc-mind) if t>=6 else 0)
        ot=max(0,ocash)*.90+(release*max(0,oc-mino) if t>=6 else 0)
        if delay and t<=3:dt=ot=0
        dr,dres,dc,du,dares=pay(dr,dres,6.0,dp,dc,mind,dt)
        # Overseas 10% retention / capital2 is a conservative cash & distributability budget,
        # not a claim foreign law follows China's statutory reserve law.
        orr,ores,oc,ou,oares=pay(orr,ores,2.0,op,oc,mino,ot)
        remittance_tax=ou*remittance_rate
        upstream=du+ou-remittance_tax
        pm+=upstream;pp+=upstream-loss_cost
        sm=dc+oc;sr=dr+orr;sres=dres+ores;sadd=dares+oares
        dtarget=([.40,.45,.50,.55,.60][t-1]*shares if t<=5 else max(0,pcash+upstream)+release*max(0,pm-minp))
        if kind=='cyclical' and t<=2:dtarget=0
        if kind=='structural' and t<=5:dtarget=0
        pr,pres,pm,div,padd=pay(pr,pres,5.09140859+(FACE/59.09 if convert else 0),pp,pm,minp,dtarget)
        # No unreported external funding plugs. Negative cash renders path impossible.
        if min(pm,sm)<-1e-8:raise ValueError('Unfunded path')
        expected=oldcash+fcf+interest_p+interest_s-coupon-redemption-repay_bank-settlement+investment_recovery-div-loss_cost-remittance_tax
        assert abs(pm+sm-expected)<1e-7*max(1,abs(expected))
        dps=div/shares; pv+=dps/(1+p['k'])**t
        if t>5:tv5+=dps/(1+p['k'])**(t-5)
        rows.append(dict(year=t,revenue=revenue,segment_revenue=dict(zip(NAMES,rev)),common_operating_profit=earnings,
          depreciation=dep,capex=capex,delta_working_capital=dnwc,reinvestment=reinvest,fcf=fcf,
          parent_cash=pm,subsidiary_cash=sm,parent_legal_retained_budget=pr,subsidiary_legal_retained_budget=sr,
          parent_reserve=pres,subsidiary_reserve_budget=sres,parent_reserve_add=padd,sub_reserve_add=sadd,
          subsidiary_upstream=upstream,parent_profit_budget=pp,subsidiary_profit_budget=dp+op,intragroup_support=support,
          domestic_profit_budget=dp,overseas_profit_budget=op,domestic_cash=dc,overseas_cash=oc,
          domestic_retained_budget=dr,overseas_retained_budget=orr,domestic_upstream=du,overseas_gross_upstream=ou,
          overseas_remittance_tax=remittance_tax,risk_loss_cash=loss_cost,risk_retained_budget=risk_retained,risk_dividend=0,risk_closed=t>=6,
          coupon=coupon,redemption=redemption,bank_repayment=repay_bank,settlement=settlement,
          investment_recovery=investment_recovery,finance_income=interest_p+interest_s,dividend=div,dps=dps,shares=shares,
          cash_conservation_error=pm+sm-expected,operating_capital=op_capital))
        prev_rev=revenue;last_nwc_rate=nwc_rate
    # Explicit distributions model principal recovery through Y200; homogeneous continuation thereafter.
    # At that point growth, operating return, legal buffer and cash policy have converged.
    tail=rows[-1]['dps']*(1+p['g'])/(p['k']-p['g'])
    pv+=tail/(1+p['k'])**horizon;tv5+=tail/(1+p['k'])**(horizon-5)
    return dict(parameters=p,kind=kind,convert=convert,normalization_method=normal,release=release,delay=delay,
        value=pv,terminal_year5=tv5,distribution5=[r['dps'] for r in rows[:5]],
        terminal_pv_share=tv5/(1+p['k'])**5/pv,remote_tail_pv=tail/(1+p['k'])**horizon,horizon=horizon,overseas_share=overseas_share,remittance_rate=remittance_rate,risk_loss=risk_loss,rows=rows)

def tests():
    # All calls use the exact legal/pay chain used above.
    a=pay(-2,0,10,-1,10,0,9);assert a==(-3,0,10,0,0)
    b=pay(a[0],a[1],10,4,a[2]+4,0,9)
    assert all(abs(x-y)<1e-12 for x,y in zip(b,(0,.1,13.1,.9,.1)))
    c=pay(0,4.95,10,2,10,0,9);assert abs(c[4]-.05)<1e-12 and abs(c[3]-1.95)<1e-12
    d=pay(10,5,10,2,1,.5,9);assert d[3]==.5 and d[2]==.5 and d[0]==11.5
    assert abs(cash_step(10,2,.1,3,.2,4,.5,.6)-5.0)<1e-12
    return dict(debt_cash_hand_case=5.0,loss_then_profit={'first':a,'second':b},reserve_cap=c,cash_cap=d)

def main():
    out={'units':'CNY100m except per-share CNY','as_of':ASOF,'observed_ttm_revenue':TTM,'initial_segment_allocation_estimate':dict(zip(NAMES,INIT)), 'tests':tests(),'cases':{}}
    for name,p in PARAMS.items():out['cases'][name]=run(p,name)
    for name in ('core_low','core_high'):
        p=PARAMS[name]
        out['cases'][name+'_conversion']=run(p,name,convert=True)
        out['cases'][name+'_normalization']=run(p,name,normal=True)
        q=copy.deepcopy(p);q['roic']=.12;out['cases'][name+'_roic12']=run(q,name)
        out['cases'][name+'_slow_release']=run(p,name,release=.10,delay=True)
    for name in ('core_low','core_high'):
        out['cases'][name+'_overseas_loss_stress']=run(PARAMS[name],name,overseas_share=.20,remittance_rate=.10,risk_loss=.15)
        out['cases'][name+'_overseas_low_friction']=run(PARAMS[name],name,overseas_share=.05,remittance_rate=.02,risk_loss=.01)
    out['tail_convergence']={}
    for name,original in list(out['cases'].items()):
        p=original['parameters']
        runs=[run(p,original['kind'],convert=original['convert'],normal=original['normalization_method'],release=original['release'],delay=original['delay'],horizon=h,overseas_share=original['overseas_share'],remittance_rate=original['remittance_rate'],risk_loss=original['risk_loss']) for h in (160,200,240)]
        values=[v['value'] for v in runs]
        assert max(values)-min(values)<.001
        checks=[]
        for v in runs:
            last,prev=v['rows'][-1],v['rows'][-2]
            ratios={key:last[key]/prev[key]-1 for key in ('revenue','common_operating_profit','parent_cash','subsidiary_cash','domestic_cash','overseas_cash','dividend','parent_profit_budget','subsidiary_profit_budget')}
            for key,growth in ratios.items():assert abs(growth-p['g'])<1e-5,(name,key,growth)
            assert abs(last['parent_reserve']-prev['parent_reserve'])<1e-10
            assert abs(last['subsidiary_reserve_budget']-prev['subsidiary_reserve_budget'])<1e-10
            assert last['parent_legal_retained_budget']>=last['dividend'] and last['risk_dividend']==0
            assert abs((last['parent_cash']+last['subsidiary_cash'])/last['revenue']-.11)<1e-8
            checks.append(dict(horizon=v['horizon'],value=v['value'],terminal=v['terminal_year5'],growth_checks=ratios,
                parent_cash=last['parent_cash'],subsidiary_cash=last['subsidiary_cash'],cash_to_revenue=.11,
                parent_retained=last['parent_legal_retained_budget'],subsidiary_retained=last['subsidiary_legal_retained_budget'],
                parent_reserve=last['parent_reserve'],sub_reserve=last['subsidiary_reserve_budget'],dividend=last['dividend'],remote_tail_pv=v['remote_tail_pv']))
        out['tail_convergence'][name]=dict(value_spread=max(values)-min(values),checks=checks)
    print(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False))
if __name__=='__main__':main()

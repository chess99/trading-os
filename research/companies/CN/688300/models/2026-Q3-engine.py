#!/usr/bin/env python3
"""联瑞新材，独立经济预算，CNY million; shares million. Stdlib only.
No market prices. stdout is complete deterministic JSON. Ten rolling years from 2026-10-27.
Entity allocations and future statutory profits are budgets, NOT disclosed legal accounts.
"""
import copy,json,math
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
SHARES=313.916240
FACE=694.694
ACTIVE=1240.65119070
OPERATING_CASH=133.97321219
WC0=475.97031164
FIXED0=922.08027908

def base():
    return dict(name='base',internal_loan_rate=0.,internal_loan_vat=.06,cb_initial_book=637.26896331,sc_parent_preparation=False,affiliate_asset=52.89378643,initial_deferred_tax=44.39580994,extra_settlement=0.,revenue=[1750,2000,2200,2400,2550,2700,2820,2920,3020,3100],margin=[.27,.28,.285,.28,.275,.27,.265,.26,.255,.25],capex=[350,300,250,180,150,190,200,210,220,230],da=[90,110,130,145,155,170,180,190,200,210],wc=.35,tax=.15,sc_revenue=[0,162,324,459,540,550,560,570,580,590],sc_ebitda=[-8,40.5,97.2,146.88,172.8,176,179.2,182.4,185.6,188.8],sc_capex=[270,180,15,20,30,45,45,45,45,45],sc_da=[0,22.5,45,45,45,45,45,45,45,45],sc_wc=150/540,sc_tax=.25,sc_impair=[0]*10,sc_recovery=[0]*10,sc_equity=150,phase2=False,convert_year=0,put_year=0,terminal_g=.02,terminal_roic=.16,terminal_rate=.10,discount=.115,financial_yield=.02,distribution=.45,restricted_old=240.,restricted_parent=231.6170843,long_lock=78.,free_parent=650.,free_old=119.0341064,initial_wc=WC0,initial_fixed=FIXED0,initial_op_cash=OPERATING_CASH,initial_parent_re=835.81490092,initial_parent_reserve=119.46981799,initial_old_re=40.,initial_old_reserve=0.,parent_capital=SHARES,old_capital=590.,face=FACE,bank=120.,lease=24.82907446,shares=SHARES,conversion_price=48.50,cash_floors=[80,40,20],reserve_rate=.10)

def legal(re,reserve,capital,profit,rate):
    # statutory loss repair before new reserve; no dividend of capital or premium
    repair=min(max(-re,0),max(profit,0))
    eligible=max(profit-repair,0)
    add=min(max(capital*.5-reserve,0),eligible*rate)
    return re+profit-add,reserve+add,add,repair

def simulate(p):
    p=copy.deepcopy(p)
    free=[p['free_parent'],p['free_old'],0.]
    earmark=[p['restricted_parent'],p['restricted_old']]
    re=[p['initial_parent_re'],p['initial_old_re'],0.]
    reserve=[p['initial_parent_reserve'],p['initial_old_reserve'],0.]
    capital=[p['parent_capital'],p['old_capital'],p['sc_equity']]
    bank=p['bank']; lease=p['lease']; face=p['face']; loan=0.; equity_paid=0.
    cb_book=p['cb_initial_book']*p['face']/FACE
    sc_loss=0.; oldwc=p['initial_wc']; scwc=0.; fixed=p['initial_fixed']; scfixed=0.
    shares=p['shares'];conversion_price=p['conversion_price'];parent_project_impairment=0.; init=sum(free)+sum(earmark); rows=[]
    for i in range(10):
        y=i+1; opening=sum(free)+sum(earmark); opening_by=free[:]; opening_ear=earmark[:]
        book_open=cb_book;book_conversion=0.;book_redeemed=0.
        converted=face if y==p['convert_year'] else 0.
        if converted:
            newshares=face/conversion_price; shares+=newshares; capital[0]+=newshares;face=0.;book_conversion=cb_book;cb_book=0.
        else:newshares=0.
        coupon=face*[.001,.003,.006,.01,.015,0,0,0,0,0][i]
        accretion=(23 if y<=5 else (11.89443669 if y==6 else 0))*p['face']/FACE if face else 0.
        cb_book+=accretion
        put_date=date(2026+y,10,27) if y==p['put_year'] else None
        accrual_start=date(2026+y,1,8) if put_date else None
        put_days=(put_date-accrual_start).days if put_date else 0
        put_accrual=face*.015*put_days/365 if put_date else 0.
        redemption_face=face if (y==6 or put_date) else 0.
        redeem=face*1.10 if y==6 else (face+put_accrual if put_date else 0.)
        derecognition_gain=cb_book-redemption_face if put_date else 0.
        derecognition_net=derecognition_gain-put_accrual
        derecognition_tax=max(derecognition_net,0)*p['tax']
        if redeem:book_redeemed=cb_book;cb_book=0.;face=0.
        internal_interest=loan*p['internal_loan_rate']
        internal_vat=internal_interest*p['internal_loan_vat']
        parent_interest_tax=internal_interest*p['tax']
        bankinterest=bank*.045; bankpay=bank if y==3 else 0.;bank-=bankpay
        leasepay=min(lease,p['lease']/5);lease-=leasepay
        leaseinterest=(lease+leasepay)*.04
        financial_interest=[free[0]*p['financial_yield']*(1-p['tax']),free[1]*p['financial_yield']*(1-p['tax']),free[2]*p['financial_yield']*(1-p['sc_tax'])]
        ear_interest=[e*.016*(1-p['tax']) for e in earmark]
        for j in range(3):free[j]+=financial_interest[j]
        for j in range(2):earmark[j]+=ear_interest[j]
        rev=p['revenue'][i];ebit=rev*p['margin'][i];nopat=ebit*(1-p['tax'])
        nwc=rev*p['wc'];dw=nwc-oldwc;oldwc=nwc
        sc_rev=p['sc_revenue'][i];sc_ebit=p['sc_ebitda'][i]-p['sc_da'][i]
        # Conservative no current tax shield on start-up losses; loss pool disclosed but not monetized.
        sc_tax=max(sc_ebit,0)*p['sc_tax'];sc_nopat=sc_ebit-sc_tax
        sc_loss+=min(sc_ebit,0)
        sc_interest_deduction=min(internal_interest+internal_vat,2*equity_paid*p['internal_loan_rate']*(1+p['internal_loan_vat']),max(sc_ebit,0))
        sc_interest_tax_shield=sc_interest_deduction*p['sc_tax']
        internal_tax_effect=sc_interest_tax_shield-parent_interest_tax-internal_vat
        sw=sc_rev*p['sc_wc'];dsw=sw-scwc;scwc=sw
        fixed+=p['capex'][i]-p['da'][i]
        scfixed+=p['sc_capex'][i]-p['sc_da'][i]-p['sc_impair'][i]-p['sc_recovery'][i]
        oldfcf=nopat+p['da'][i]-p['capex'][i]-dw
        scfcf=sc_nopat+p['sc_da'][i]-p['sc_capex'][i]-dsw+p['sc_recovery'][i]
        tax_timing=p['initial_deferred_tax']/5 if y<=5 else 0.
        extra_settlement=p['extra_settlement'] if y==1 else 0.
        fcff=oldfcf+scfcf-tax_timing-extra_settlement+internal_tax_effect-derecognition_tax
        # Existing maintenance approximates D&A; earmarks only existing eligible growth, not Sichuan.
        eligible=max(p['capex'][i]-p['da'][i],0)
        used=[]
        for j,share in enumerate([.60,.40]):
            lock=p['long_lock'] if j==1 and y<3 else 0.
            use=min(max(earmark[j]-lock,0),eligible*share)
            earmark[j]-=use;free[j]+=use;used.append(use)
        free[0]+=nopat*.65+p['da'][i]*.60-p['capex'][i]*.60-dw*.75-coupon-redeem-leasepay*.65-leaseinterest*.65
        free[1]+=nopat*.35+p['da'][i]*.40-p['capex'][i]*.40-dw*.25-bankinterest-bankpay-leasepay*.35-leaseinterest*.35
        free[0]-=tax_timing*.65+extra_settlement
        free[1]-=tax_timing*.35
        free[0]+=internal_interest-parent_interest_tax-derecognition_tax
        free[2]+=-internal_interest-internal_vat+sc_interest_tax_shield
        if p['sc_parent_preparation']:free[0]+=scfcf
        else:free[2]+=scfcf
        # Equity subscriptions are internal. Any excess project funding is parent intercompany loan.
        equity_injection=min(max(-free[2]+p['cash_floors'][2],0),max(p['sc_equity']-equity_paid,0)) if any(p['sc_capex']) else 0.
        free[0]-=equity_injection;free[2]+=equity_injection;equity_paid+=equity_injection
        advance=max(p['cash_floors'][2]-free[2],0) if (not p['sc_parent_preparation'] and (equity_paid or sc_rev or any(p['sc_capex']) or any(p['sc_ebitda']))) else 0.
        free[0]-=advance;free[2]+=advance;loan+=advance
        repay=min(loan,max(free[2]-p['cash_floors'][2],0));free[2]-=repay;free[0]+=repay;loan-=repay
        # Subsidiary statutory profits exclude intra-group loan repayment. Impairment noncash.
        subprofit=nopat*.35+financial_interest[1]+ear_interest[1]-bankinterest-leaseinterest*.35
        scprofit=0. if p['sc_parent_preparation'] else sc_nopat+financial_interest[2]-p['sc_impair'][i]-internal_interest-internal_vat+sc_interest_tax_shield
        re[1],reserve[1],res_old,repair_old=legal(re[1],reserve[1],capital[1],subprofit,p['reserve_rate'])
        re[2],reserve[2],res_sc,repair_sc=legal(re[2],reserve[2],capital[2],scprofit,p['reserve_rate'])
        upstream_old=min(max(re[1],0)*.60,max(free[1]-p['cash_floors'][1],0))
        upstream_sc=min(max(re[2],0)*.50,max(free[2]-p['cash_floors'][2],0)) if loan<1e-8 else 0.
        for j,up in [(1,upstream_old),(2,upstream_sc)]:free[j]-=up;re[j]-=up;free[0]+=up
        project_impairment=max(max(-re[2],0)-parent_project_impairment,0) if any(p['sc_impair'][:y]) else 0.
        parent_project_impairment+=project_impairment
        parentprofit=internal_interest-parent_interest_tax+derecognition_net-derecognition_tax+(sc_nopat if p['sc_parent_preparation'] else 0)-project_impairment+nopat*.65+financial_interest[0]+ear_interest[0]-coupon-accretion-leaseinterest*.65+upstream_old+upstream_sc
        re[0],reserve[0],res_parent,repair_parent=legal(re[0],reserve[0],capital[0],parentprofit,p['reserve_rate'])
        desired=max(nopat+sc_nopat,0)*(min(p['distribution'],.35) if y<=2 else p['distribution'])
        dividend=min(desired,max(re[0],0),max(free[0]-p['cash_floors'][0],0))
        free[0]-=dividend;re[0]-=dividend
        # Contractual cash-dividend adjustment; conversion assumed at beginning of year.
        conversion_price_after=max(.01,float((Decimal(str(conversion_price))-Decimal(str(dividend/shares))).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP))) if face else conversion_price
        # No silent external borrowing. Negative cash makes scenario financing-infeasible.
        closing=sum(free)+sum(earmark)
        debtcash=coupon+redeem+bankinterest+bankpay+leasepay+leaseinterest
        interest=sum(financial_interest)+sum(ear_interest)
        error=closing-(opening+fcff+interest-debtcash-dividend)
        assert abs(error)<1e-7,(p['name'],y,error)
        rows.append(dict(year=y,cb_book_open=book_open,cb_accretion=accretion,cb_book_conversion=book_conversion,cb_book_redeemed=book_redeemed,cb_book_close=cb_book,put_date=put_date.isoformat() if put_date else None,put_accrual_start=accrual_start.isoformat() if accrual_start else None,put_accrual_days=put_days,put_accrued_interest=put_accrual,cb_derecognition_gain=derecognition_gain,cb_derecognition_net=derecognition_net,cb_derecognition_tax=derecognition_tax,internal_interest=internal_interest,internal_vat=internal_vat,internal_interest_cash_paid=internal_interest+internal_vat,parent_interest_tax=parent_interest_tax,sc_interest_deduction=sc_interest_deduction,sc_interest_tax_shield=sc_interest_tax_shield,internal_tax_effect=internal_tax_effect,revenue=rev,ebit=ebit,nopat=nopat,capex=p['capex'][i],da=p['da'][i],wc=nwc,delta_wc=dw,existing_fcff=oldfcf,sc_revenue=sc_rev,sc_ebit=sc_ebit,sc_nopat=sc_nopat,sc_capex=p['sc_capex'][i],sc_da=p['sc_da'][i],sc_wc=sw,sc_delta_wc=dsw,sc_fcff=scfcf,fcff=fcff,tax_timing_payment=tax_timing,extra_settlement=extra_settlement,fixed=fixed,sc_fixed=scfixed,capital_employed=fixed+scfixed+nwc+sw+p['initial_op_cash'],opening_financial=opening,opening_free=opening_by,opening_earmark=opening_ear,financial_interest=interest,earmark_use=used,closing_earmark=earmark[:],closing_free=free[:],closing_financial=closing,bank_interest=bankinterest,bank_repaid=bankpay,bank_remaining=bank,coupon=coupon,cb_redeemed=redeem,cb_face_remaining=face,converted_face=converted,new_shares=newshares,lease_repaid=leasepay,lease_interest=leaseinterest,lease_remaining=lease,debt_cash=debtcash,sc_equity_injection=equity_injection,sc_equity_paid=equity_paid,sc_loan_advance=advance,sc_loan_repaid=repay,sc_loan_remaining=loan,statutory_profit=[parentprofit,subprofit,scprofit],legal_re=re[:],legal_reserve=reserve[:],reserve_added=[res_parent,res_old,res_sc],loss_repair=[repair_parent,repair_old,repair_sc],parent_project_impairment=project_impairment,conversion_price_at_year_start=conversion_price,conversion_price_after_dividend=conversion_price_after,registered_capital=capital[:],upstream_old=upstream_old,upstream_sc=upstream_sc,dividend=dividend,shares=shares,dps=dividend/shares,group_cash_error=error,minimum_entity_cash=min(free)))
        conversion_price=conversion_price_after
    r=p['discount'];g=p['terminal_g'];tr=p['terminal_rate'];roic=p['terminal_roic']
    last=rows[-1]; terminal_nopat=(last['nopat']+last['sc_nopat'])*(1+g)
    reinvest=terminal_nopat*g/roic
    terminal_fcff=terminal_nopat-reinvest
    terminal_ev=terminal_fcff/(tr-g)
    # Sale of equity includes retained financial principal ONCE, not a hypothetical statutory dividend.
    terminal_equity=terminal_ev+last['closing_financial']+p['affiliate_asset']-bank-lease-face*1.1
    pv_div=sum(x['dividend']/(1+r)**x['year'] for x in rows)
    pv_terminal=terminal_equity/(1+r)**10
    value=(pv_div+pv_terminal)/shares
    terminal5=(sum(x['dividend']/(1+r)**(x['year']-5) for x in rows[5:])+terminal_equity/(1+r)**5)/shares
    # Exact independently checkable FCFF-to-distribution identity for cash retention opportunity cost.
    pv_fcff=sum(x['fcff']/(1+r)**x['year'] for x in rows)
    pv_interest=sum(x['financial_interest']/(1+r)**x['year'] for x in rows)
    pv_debt=sum(x['debt_cash']/(1+r)**x['year'] for x in rows)
    retention=sum(r*x['opening_financial']/(1+r)**x['year'] for x in rows)
    bridge=init+pv_fcff+pv_interest-pv_debt-retention+(terminal_ev+p['affiliate_asset']-bank-lease-face*1.1)/(1+r)**10
    assert abs(bridge-(pv_div+pv_terminal))<1e-7
    # With early conversion, initial holder owns one unchanged share: use each actual yearly DPS.
    per_share=sum(x['dps']/(1+r)**x['year'] for x in rows)+terminal_equity/shares/(1+r)**10
    return dict(name=p['name'],inputs=p,years=rows,financial_initial=init,financing_feasible=all(x['minimum_entity_cash']>=-1e-7 for x in rows),value_per_share=per_share,aggregate_value=bridge,pv_dividends=pv_div,pv_terminal=pv_terminal,terminal_share=terminal_equity/shares,terminal5_per_share=terminal5,terminal_ev=terminal_ev,terminal_equity=terminal_equity,terminal_nopat=terminal_nopat,terminal_reinvestment=reinvest,terminal_fcff=terminal_fcff,terminal_pv_fraction=pv_terminal/(pv_div+pv_terminal),fcff_bridge=dict(initial_financial=init,pv_fcff=pv_fcff,pv_interest=pv_interest,pv_debt=pv_debt,pv_cash_retention_drag=retention,pv_enterprise=terminal_ev/(1+r)**10,pv_affiliate=p['affiliate_asset']/(1+r)**10,total=bridge),five_year_identity=sum(x['dps']/(1+r)**x['year'] for x in rows[:5])+terminal5/(1+r)**5)

def variants():
    b=base();out=[b]
    for name,r,tr,g in [('core_low',.12,.105,.02),('core_high',.11,.095,.025)]:
        p=copy.deepcopy(b);p.update(name=name,discount=r,terminal_rate=tr,terminal_g=g);out.append(p)
    p=copy.deepcopy(b);p.update(name='cycle',revenue=[1500,1650,1950,2250,2450,2600,2750,2870,2970,3050],margin=[.23,.24,.26,.27,.27,.265,.26,.255,.25,.245],wc=.39);out.append(p)
    p=copy.deepcopy(b);p.update(name='structural',revenue=[1600,1700,1800,1900,2000,2070,2130,2180,2230,2280],margin=[.24,.23,.22,.21,.20,.20,.20,.20,.20,.20],sc_revenue=[0,108,189,270,324,330,336,342,348,354],sc_ebitda=[-12,16.2,37.8,59.4,71.28,72.6,73.92,75.24,76.56,77.88],wc=.39,terminal_roic=.12,terminal_g=.01,terminal_rate=.115,discount=.13,distribution=.25);out.append(p)
    p=copy.deepcopy(b);p.update(name='upside',revenue=[1850,2200,2550,2850,3100,3350,3550,3720,3880,4000],margin=[.28,.29,.30,.30,.30,.295,.29,.285,.28,.275],sc_revenue=[0,216,432,594,648,680,720,760,800,840],sc_ebitda=[-6,64.8,151.2,213.84,233.28,244.8,259.2,273.6,288,302.4],sc_capex=[300,200,40,180,160,60,65,70,75,80],sc_da=[0,25,50,60,75,85,90,95,100,105],phase2=True,terminal_roic=.18,terminal_g=.025,discount=.11,terminal_rate=.095);out.append(p)
    p=copy.deepcopy(b);p['name']='project_delay'
    for k in ['sc_revenue','sc_ebitda','sc_capex','sc_da']:
        arr=p[k];p[k]=[0,0]+arr[:8]
    p['sc_ebitda'][0]=-3;p['sc_ebitda'][1]=-3;p['sc_capex'][0]=10;p['sc_capex'][2]-=10
    # Delay withhold cash: same parent policy; no special payout of the unspent project budget.
    out.append(p)
    p=copy.deepcopy(b);p.update(name='project_pending',sc_parent_preparation=True,sc_revenue=[0]*10,sc_ebitda=[-3,-3,-2,-2,-2,-2,-2,-2,-2,-2],sc_capex=[10]+[0]*9,sc_da=[0]*10,sc_equity=0,distribution=.35);out.append(p)
    p=copy.deepcopy(b);p.update(name='project_failure',sc_revenue=[0,108,60,0,0,0,0,0,0,0],sc_ebitda=[-8,10,-10,-8,0,0,0,0,0,0],sc_capex=[270,180,15,0,0,0,0,0,0,0],sc_da=[0,22.5,45,0,0,0,0,0,0,0],sc_recovery=[0,0,0,60,0,0,0,0,0,0],sc_impair=[0,0,337.5,0,0,0,0,0,0,0],distribution=.35);out.append(p)
    p=copy.deepcopy(b);p.update(name='full_convert_y1',convert_year=1);out.append(p)
    p=copy.deepcopy(b);p.update(name='full_convert_y3',convert_year=3);out.append(p)
    p=copy.deepcopy(b);p.update(name='conditional_put_y4',put_year=4,distribution=.30);out.append(p)
    p=copy.deepcopy(b);p.update(name='internal_loan_4pct',internal_loan_rate=.04);out.append(p)
    return out

def handcase():
    # Genuine production-path micro-case, nonzero operations, finance, tax/reserve, project funding.
    p=base();p.update(name='production_handcase',affiliate_asset=0.,initial_deferred_tax=0.,extra_settlement=0.,revenue=[100]*10,margin=[.20]*10,capex=[12]*10,da=[5]*10,wc=.30,tax=.20,sc_revenue=[0]*10,sc_ebitda=[-2]*10,sc_capex=[10]+[0]*9,sc_da=[0]*10,sc_wc=.25,sc_tax=.25,sc_equity=10,face=10,bank=5,lease=5,shares=10,parent_capital=10,old_capital=20,free_parent=100,free_old=20,restricted_parent=10,restricted_old=10,long_lock=0,initial_wc=25,initial_fixed=50,initial_op_cash=10,initial_parent_re=20,initial_parent_reserve=1,initial_old_re=5,initial_old_reserve=1,cash_floors=[5,3,2],financial_yield=.02)
    return simulate(p)

def main():
    cases={p['name']:simulate(p) for p in variants()}
    sensitivities=[]
    specs=[('legacy_margin_minus_3pt',{'margin':[x-.03 for x in base()['margin']]}),('legacy_wc_plus_5pt',{'wc':.40}),('sc_revenue_minus_25pct',{'sc_revenue':[x*.75 for x in base()['sc_revenue']],'sc_ebitda':[x*.75 if x>0 else x for x in base()['sc_ebitda']]}),('sc_capex_plus_30pct',{'sc_capex':[x*1.3 for x in base()['sc_capex']]}),('discount_plus_2pt',{'discount':.135}),('terminal_rate_plus_2pt',{'terminal_rate':.12}),('terminal_roic_12pct',{'terminal_roic':.12}),('long_cd_not_recoverable',{'free_parent':650-71.40080589,'restricted_old':162.,'long_lock':0.}),('existing_tax_25pct',{'tax':.25}),('parent_extra_settlement_150',{'extra_settlement':150.}),('affiliate_zero_recovery',{'affiliate_asset':0.})]
    for name,changes in specs:
        p=base();p.update(changes);p['name']=name;q=simulate(p);sensitivities.append(dict(name=name,value_per_share=q['value_per_share'],delta=q['value_per_share']-cases['base']['value_per_share'],financing_feasible=q['financing_feasible']))
    sensitivities.sort(key=lambda x:abs(x['delta']),reverse=True)
    b=cases['base'];last=b['years'][-1];aux=[]
    for multiple in [8.,10.]:
        enterprise=(last['ebit']+last['sc_ebit'])*multiple
        equity=enterprise+last['closing_financial']+b['inputs']['affiliate_asset']-last['bank_remaining']-last['lease_remaining']-last['cb_face_remaining']*1.1
        aux.append(dict(ev_ebit=multiple,terminal_ev=enterprise,terminal_equity=equity,value_per_share=(b['pv_dividends']+equity/(1+b['inputs']['discount'])**10)/last['shares']))
    result=dict(auxiliary_ev_ebit=aux,company='联瑞新材',ticker='CN:688300',report_period='2026-Q3',as_of='2026-10-27T22:00:00+00:00',units='CNY million; shares million; per-share CNY',model_basis='economic budgets; no market inputs; annual end-period timing; initial legal ledgers partly H1 proxy',cases=cases,dominance_sensitivities=sensitivities,production_handcase=handcase())
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False))
if __name__=='__main__':main()

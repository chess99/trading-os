#!/usr/bin/env python3
"""CN600426 independent 2026Q3, stdlib standalone. CNY billions, million tonnes.
All future legal distributions are budgets, not certifications. October paid dividend
already removed. Full states always emitted; no file inputs or market quotations.
"""
import json,math,copy
ASOF='2026-10-30T08:00:00+00:00'
SHARES=2.749943015
DEBT=(486992995.37+2445654902.26+8152674605.41+43959632.81)/1e9
OWN=.7

def opening():
    cash=2.74312477661-.71498518390
    subeq=2.65307897812/.3
    peq=35.75569533728-.71498518390-OWN*subeq+4.2
    s={'cash':.65,'restricted':.02815864713,'debt':7.4,'fixed':16.6,'wc':0.,'capital':6.,'premium':0.,'reserve':.25,'re':subeq-6.25,'eq':subeq,'payable':.2,'div_payable':0.,'tax_losses':[]}
    p={'cash':cash-.65,'restricted':.1,'debt':DEBT-7.4,'fixed':24.50091760343,'wc':0.,'capital':SHARES,'premium':1.61679736085,'reserve':1.06165999950,'re':0.,'eq':peq,'payable':.35,'div_receivable':0.,'investment_cost':4.2,'loan_face':2.27310126390,'loan_allowance':0.,'financial':.05001035616,'tax_losses':[]}
    p['re']=peq-p['capital']-p['premium']-p['reserve']
    s['wc']=subeq+s['debt']+p['loan_face']+s['payable']-s['cash']-s['fixed']
    p['wc']=peq+p['debt']+p['payable']-p['cash']-p['fixed']-p['investment_cost']-p['loan_face']-p['financial']
    return {'p':p,'s':s,'shares':SHARES}

def tax(profit,losses,rate,y):
    old=[list(a) for a in losses if y-a[0]<=(10 if rate==.15 else 5)]
    taxable=max(profit,0.)
    for a in old:
        use=min(taxable,a[1]);taxable-=use;a[1]-=use
    if profit<0:old.append([y,-profit])
    return taxable*rate,[a for a in old if a[1]>1e-12]

def retain(e,ni):
    # Current profit first covers opening accumulated losses, then statutory reserve.
    appropriation=min(.1*max(ni+min(e['re'],0.),0.),max(.5*e['capital']-e['reserve'],0.))
    e['reserve']+=appropriation;e['re']+=ni-appropriation;e['eq']+=ni
    return appropriation

def config(name):
    c=dict(name=name,method='products',spread=0.,raw=0.,price=0.,rate=.10,tax=.15,capmult=1.,lag=0,loan_delay=0,struct=False,cycle=False,optimistic=False,ceiling=14.,cash_split=.65)
    if name=='core_low': c.update(spread=-.01,rate=.105)
    if name=='core_high': c.update(spread=.01,rate=.095)
    if name=='capital_low': c.update(method='capital',spread=-.01,rate=.105)
    if name=='capital_high': c.update(method='capital',spread=.01,rate=.095)
    if name=='cycle':c.update(cycle=True,capmult=1.10)
    if name=='structural':c.update(struct=True,tax=.25,capmult=1.15,rate=.11)
    if name=='optimistic':c.update(optimistic=True,spread=.02,rate=.095)
    if name=='raw_plus10':c.update(raw=.10)
    if name=='upstream_delay':c.update(lag=1,loan_delay=3)
    if name=='tax25':c.update(tax=.25)
    if name=='ip_stress':c.update(ip_stress=True)
    if name=='capital_ip_stress':c.update(ip_stress=True,method='capital',spread=-.01,rate=.105)
    return c

def operations(y,c,st):
    n=min(y-1,4);infl=1.01**max(y-5,0)
    # Different segment baskets; material coefficients describe a basket exposure,
    # never claimed physical coal consumption or pure urea/DMF production.
    volume=[3.30*(1.025**n),5.50,.56,1.50]
    price=[5500.,1400.,4300.,2600.]
    margin=[.16,.315,.19,.315]
    raw=c['raw'];passprice=c['price'];volshock=1.
    if c['cycle'] and y<=2:raw+=.15 if y==1 else .08;passprice+=.055 if y==1 else .03;volshock=.94 if y==1 else .98
    if c['struct']:raw+=.06;passprice-=.025;volshock=.93
    if c['optimistic']:volume[0]*=1.04
    seg=[];gross=0.;rev=0.
    for i,(q,pr,m) in enumerate(zip(volume,price,margin)):
        m+=c['spread']*(1 if i==0 else .5)
        # FY direct-material share of COGS roughly 74-78%; 75% exposure retained.
        unitcost=pr*(1-m)*(1+.75*raw)
        r=q*volshock*pr*(1+passprice)/1000*infl
        gp=q*volshock*(pr*(1+passprice)-unitcost)/1000*infl
        seg.append(dict(volume_mton=q*volshock,price=pr*(1+passprice)*infl,unit_cogs=unitcost*infl,revenue=r,gross_profit=gp));rev+=r;gross+=gp
    otherrev=1.6*infl;othergp=.32*infl
    expense=(1.92+.025*n)*infl # R&D 1.10 to1.20, admin/sales/tax add .82
    ebit=gross+othergp-expense
    # Gas replacement: bounded efficiency benefit net of additional depreciation,
    # not 45.09万Nm3/h counted as external sales. Competitive erosion after Y10.
    efficiency=[.06,.12,.16,.18,.18][n]*infl
    fade=max(.88,1.-.008*max(y-10,0))
    ebit=(ebit+efficiency)*fade
    subweight=.29+.005*n
    es=(ebit-efficiency*fade)*subweight;ep=ebit-es
    # Site mapping within new-material basket: existing licensed Dezhou 100kt
    # budget, Jingzhou proprietary ramp 40/80/120/160/160kt; no extra group sales.
    # Allocate identified contribution to its actual entity, residual by site mix.
    project_unit_ebit=650.+5500.*c['spread']+5500.*passprice-4620.*.75*raw
    project_q=[.04,.08,.12,.16,.16][n]*(1.04 if c['optimistic'] else 1.)*volshock
    old_q=.10*(1.04 if c['optimistic'] else 1.)*volshock
    assignment=(project_q*(1-subweight)-old_q*subweight)*project_unit_ebit/1000*infl*fade
    es+=assignment;ep-=assignment
    if c['method']=='capital':
        # Independent operating入口: mature-site NOPAT / productive net operating
        # capital; budgets below are not derived from product model outputs.
        pcapital=26.5+[0.,.7,1.2,1.5,1.7][n]
        scap=17.0+[0.,.5,.9,1.1,1.3][n]
        pr=.115+c['spread']*.6;sr=.078+c['spread']*.4
        ep=pcapital*pr/.85*infl*fade;es=scap*sr/.85*infl*fade
    # Conditional proprietary Jingzhou melamine ramp: 40/80/120/160/160 kt.
    # Stress delays ramp two years and pays 60m one-off qualification/license
    # negotiation expense; not asserted contractual royalty or old settlement.
    ipgap=([.04,.08,.08,.08,.04][y-1] if y<=5 else 0.) if c.get('ip_stress') else 0.
    lost=ipgap*.650*infl*fade
    if c['method']=='capital':lost=ipgap/.16*.73378*(.078+c['spread']*.4)/.85*infl*fade
    license_cost=.06 if c.get('ip_stress') and y==1 else 0.
    es-=lost+license_cost
    if ipgap:
        seg[0]['volume_mton']-=ipgap
        seg[0]['revenue']-=ipgap*5.5*infl
        seg[0]['gross_profit']-=ipgap*.88*infl
        rev-=ipgap*5.5*infl;gross-=ipgap*.88*infl
        expense-=ipgap*.23*infl
    expense+=license_cost
    return ep,es,dict(ip_volume_gap_mton=ipgap,ip_operating_profit_lost=lost,ip_qualification_expense=license_cost,segments=seg,revenue=rev+otherrev,product_gross_profit=gross+othergp,operating_expense=expense,gas_efficiency_net=efficiency,competitive_fade=fade,entry=c['method'])

def run(c,years=120,initial=None,operating_override=None,first_year=1):
    st=copy.deepcopy(initial or opening());p=st['p'];s=st['s'];rows=[];pv=0.
    for y in range(first_year,first_year+years):
        start=copy.deepcopy(st);infl=1.01**max(y-5,0)
        # Settle previously declared dividends, never recognize profit twice.
        received=p['div_receivable'];s['cash']-=s['div_payable'];p['cash']+=received
        paid_nci=s['div_payable']*(1-OWN);p['div_receivable']=0.;s['div_payable']=0.
        injection=1. if y==1 and not c.get('hand') else 0.
        p['cash']-=OWN*injection;p['investment_cost']+=OWN*injection;s['cash']+=injection;s['capital']+=injection;s['eq']+=injection
        ep,es,op=operations(y,c,st) if operating_override is None else operating_override(y,st)
        da_total=[3.60,3.65,3.70,3.75,3.80][min(y-1,4)]*infl
        growth=[1.20,.85,.60,.40,.30][min(y-1,4)] if y<=5 else .01*(p['fixed']+s['fixed'])
        # maintenance includes replacement gas plant spending only once. Old-payable
        # settlement is cash-only, old asset already in fixed balance.
        maintenance=da_total*c['capmult'];cap_total=maintenance+growth
        cap_p=cap_total*.65;cap_s=cap_total*.35;dap=da_total*.62;das=da_total*.38
        # Timing risk: 350m remaining project spending delayed two years, not erased.
        shift=([-.175,-.175,.175,.175,0.][y-1] if y<=5 else 0.) if c.get('ip_stress') else 0.
        cap_s+=shift;cap_total+=shift
        retire=.10 if y==1 else 0. # net old equipment carrying amount budget
        wc_add=([.22,.18,.15,.12,.10][y-1] if y<=5 else .01*(p['wc']+s['wc']))
        wcp=wc_add*.65;wcs=wc_add*.35
        wcshift=([-.01,-.01,.01,.01,0.][y-1] if y<=5 else 0.) if c.get('ip_stress') else 0.
        wcs+=wcshift;wc_add+=wcshift
        # 0.55bn old equipment creditors: extinguish liability, no second expense.
        oldp=min(p['payable'],.245 if y==1 else .105);olds=min(s['payable'],.14 if y==1 else .06)
        if c.get('hand'):
            da_total=growth=maintenance=cap_total=cap_p=cap_s=dap=das=retire=wc_add=wcp=wcs=0.
        p['payable']-=oldp;s['payable']-=olds
        ip=p['debt']*.032;iss=s['debt']*.032;internal=p['loan_face']*.026
        fp=(p['cash']+p['financial'])*.015;fs=s['cash']*.015
        finredeem=p['financial'] if y==1 else 0.;p['financial']-=finredeem;p['cash']+=finredeem
        pretaxp=ep-ip+internal+fp-retire;pretaxs=es-iss-internal+fs
        tp,p['tax_losses']=tax(pretaxp,p['tax_losses'],c['tax'],y);ts,s['tax_losses']=tax(pretaxs,s['tax_losses'],c['tax'],y)
        nip=pretaxp-tp;nis=pretaxs-ts
        p['cash']+=nip+dap+retire-cap_p-wcp-oldp
        s['cash']+=nis+das-cap_s-wcs-olds
        p['fixed']+=cap_p-dap-retire;s['fixed']+=cap_s-das
        p['wc']+=wcp;s['wc']+=wcs
        # Necessary operating cash and restricted deposit grow with nominal scale;
        # interest earned on both. Surplus financial principal is not trapped.
        p['restricted']=.10*infl;s['restricted']=.02815864713*infl
        floorp=(.60*infl+p['restricted']);floors=(.40*infl+s['restricted'])
        if c.get('hand'):
            floorp=floors=0.;p['restricted']=s['restricted']=0.
        borrowed={};repaid={}
        for name,e,floor in [('p',p,floorp),('s',s,floors)]:
            need=max(floor-e['cash'],0.)
            if p['debt']+s['debt']+need>c['ceiling']*infl+1e-9:
                raise ValueError('Mandatory investment financing unavailable at year '+str(y))
            e['cash']+=need;e['debt']+=need;borrowed[name]=need
        # Principal goes through both entities, not earnings. No writeoff of claims.
        repayment=min(p['loan_face'],max(s['cash']-floors,0.)*.50) if y>c['loan_delay'] else 0.
        p['loan_face']-=repayment;p['cash']+=repayment;s['cash']-=repayment
        sub_prepaid=min(s['debt'],max(s['cash']-floors,0.)) if y>5 else 0.
        s['debt']-=sub_prepaid;s['cash']-=sub_prepaid
        reserves_s=retain(s,nis)
        # Subsidiary dividend follows capital service; future board consent budget.
        subdecl=min(max(s['re'],0.),max(s['cash']-floors,0.)*.35) if y<=5 else min(max(s['re'],0.),max(s['cash']-floors,0.))
        s['re']-=subdecl;s['eq']-=subdecl
        if c['lag']:
            s['div_payable']=subdecl;p['div_receivable']=subdecl*OWN
        else:
            s['cash']-=subdecl;p['cash']+=subdecl*OWN;paid_nci+=subdecl*(1-OWN)
        nip+=OWN*subdecl
        reserves_p=retain(p,nip)
        requested=SHARES*[.45,.48,.52,.56,.60][y-1] if y<=5 else max(p['cash']-floorp,0.)
        # Clear external debt with residual cash; don't repay debt from earmarked dividend payables.
        for name,e,floor,earmark in [('p',p,floorp,min(requested,max(p['re'],0.))),('s',s,floors,s['div_payable'])]:
            available=max(e['cash']-floor-earmark,0.)
            repayment_ext=min(e['debt'],available*(.75 if y<=5 else 1.))
            e['cash']-=repayment_ext;e['debt']-=repayment_ext;repaid[name]=repayment_ext+(sub_prepaid if name=='s' else 0.)
        if y>5:
            # debt-first all surplus; unlike first five-year dividend policy
            pay=min(p['debt'],max(p['cash']-floorp,0.));p['cash']-=pay;p['debt']-=pay;repaid['p']+=pay
        distribution=min(max(requested,.75*max(p['cash']-floorp,0.)),max(p['re'],0.),max(p['cash']-floorp,0.))
        p['cash']-=distribution;p['re']-=distribution;p['eq']-=distribution
        economic_eq=p['eq']+OWN*s['eq']-p['investment_cost']
        # Balance-sheet exact closures: net operating asset includes all opening
        # noncash net assets; all legal intercompany claims shown and eliminated once.
        pa=p['fixed']+p['wc']+p['cash']+p['financial']+p['loan_face']-p['loan_allowance']+p['investment_cost']+p['div_receivable']-p['debt']-p['payable']
        sa=s['fixed']+s['wc']+s['cash']-s['debt']-p['loan_face']-s['payable']-s['div_payable']
        groupassets=p['fixed']+s['fixed']+p['wc']+s['wc']+p['cash']+s['cash']+p['financial']-p['debt']-s['debt']-p['payable']-s['payable']-(1-OWN)*s['div_payable']
        errors={'parent_balance':pa-p['eq'],'sub_balance':sa-s['eq'],'common_equity':groupassets-(economic_eq+(1-OWN)*s['eq'])}
        expected= start['p']['cash']+start['s']['cash'] + (nip-OWN*subdecl)+nis+dap+das+retire-cap_total-wc_add-oldp-olds+(1-OWN)*injection+finredeem+sum(borrowed.values())-sum(repaid.values())-distribution-paid_nci
        errors['cash']=p['cash']+s['cash']-expected
        for k,v in errors.items():assert abs(v)<1e-7*max(1.,abs(groupassets)),(y,k,v)
        for e in [p,s]:assert e['cash']>=-1e-9 and e['debt']>=-1e-9
        pvflow=distribution/(1+c['rate'])**(y-first_year+1);pv+=pvflow
        rows.append(dict(year=y,opening=start,operations=op,ebit_parent=ep,ebit_sub=es,net_income_parent=nip,net_income_sub=nis,tax_parent=tp,tax_sub=ts,internal_interest=internal,external_interest_parent=ip,external_interest_sub=iss,financial_income_parent=fp,financial_income_sub=fs,da_parent=dap,da_sub=das,capex_parent=cap_p,capex_sub=cap_s,wc_add=wc_add,old_payable_paid=oldp+olds,old_equipment_loss=retire,sub_capital_injection=injection,internal_principal_paid=repayment,sub_dividend_declared=subdecl,parent_sub_dividend_received=received+(0 if c['lag'] else OWN*subdecl),minority_cash=paid_nci,reserve_parent=reserves_p,reserve_sub=reserves_s,borrowed=borrowed,repaid=repaid,distribution=distribution,dps=distribution/SHARES,pv_distribution=pvflow,pv_accumulated=pv,common_equity_book=economic_eq,minority_equity_book=(1-OWN)*s['eq'],closing=copy.deepcopy(st),closure_errors=errors))
    # Terminal continuation is residual beyond actual full-state recursion. No asset
    # liberation: last distribution grows 1%; horizon-extension proves negligible PV.
    residual=rows[-1]['distribution']*1.01/(c['rate']-.01)/(1+c['rate'])**years
    total=pv+residual
    y5=sum(r['distribution']/(1+c['rate'])**(r['year']-5) for r in rows[5:])+residual*(1+c['rate'])**5
    return dict(config=c,years=years,rows=rows,current_value_per_share=total/SHARES,year5_value_per_share=y5/SHARES,first5_dps=[r['dps'] for r in rows[:5]],beyond5_pv_share=(y5/(1+c['rate'])**5/total if total else None),residual_pv=residual,residual_fraction=(residual/total if total else None))

def main():
    names=['core_low','base','core_high','capital_low','capital_high','cycle','structural','optimistic','raw_plus10','upstream_delay','tax25','ip_stress','capital_ip_stress']
    result={'as_of':ASOF,'unit':'CNY billion except per-share and unit-product data','shares_billion':SHARES,'opening':opening(),'paths':{n:run(config(n)) for n in names}}
    result['tail_extensions']={n:run(config(n),180) for n in ['core_low','core_high','structural','upstream_delay','ip_stress','capital_ip_stress']}
    result['holder_terminal']={n:{str(h):run(config(n),h,initial=result['paths']['base']['rows'][4]['closing'],first_year=6) for h in [115,175]} for n in ['core_low','core_high']}
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()

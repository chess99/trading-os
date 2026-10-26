"""Independent literal operating/cash reconstruction. Does NOT import/run production.
Inputs transcribed explicitly; reads production OUTPUT only for final comparison.
Checks core-low and dominant +1000 copper case from raw operations to equity PV.
Money bn CNY, quantity kt. Own arrays/scalar recurrence intentionally not production functions.
"""
import json,gzip,base64,pathlib,math
ROOT=pathlib.Path(__file__).resolve().parent
UNITS=.623794527+.495804/11.12
# name, production, economic share, USD cash cost (phosphate RMB), CIT, levy,
# withholding, opening net WC, tax basis, remaining construction, closure, sustaining
INPUTS=[
 ('D',[12,7,1],.9,4500,.30,.038,.10,.14,.20,[],.08,450),
 ('L',[50,50,45,50,65,80,85,85,80,70,65,55,40,30,20],.95,3900,.30,.038,.10,.60,2.5,[1.15,1.25,1.05,.50],.28,550),
 ('U',[29,32]+[32.5]*8+[30,25],.80,6500,.30,.065,0,.28,.75,[.22],.21,500),
 ('A',[0,0,12,25]+[27]*11+[27.5],.975,4900,.35,.04,.20,.03,.50,[1.5,1.35,.20],.1582,500),
 ('P',[300,300]+[800]*15+[400],.90,520,.25,.04,0,.06,.85,[.14,.135],.06,80)]

def literal(copper,margin,discount):
    cash=6.07462912271+.800-.030
    debt=1.25227476935+1.05483721952+1.44422037925+1.99977+.01873595414+.29869844836-.495804
    pcash=1.3; retained=2.64544928507-.4117+.15; reserve=.36055660399
    loan=4.02555196452; dividend_receivable=.23054008965; source_profit_stock=0.
    service_sales=7.30; service_wc=2.92; fixed_assets=1.9
    zccm=.70627091921; acquired_loan=4.2; earnout=.18127773598
    projects={v[0]:{'remaining':sum(v[1]),'wc':v[7],'basis':v[8],'loss':0.,'tax_due':0.,'advance':0.,'closed':False} for v in INPUTS}
    answer=[];distributions=[]
    for year in range(1,31):
        oldcash=cash;oldparent=pcash;oldrev=service_sales
        growth=.06 if year<=5 else (.04 if year<=10 else .02)
        service_sales=oldrev*(1+growth)
        service_income=service_sales*margin*.75
        depreciation=service_sales*.05
        investment=max(depreciation+(service_sales-oldrev)*.25,.7857223/3 if year<=3 else 0)
        new_wc=.4*service_sales
        service_flow=service_income+depreciation-investment-(new_wc-service_wc)
        service_wc=new_wc;fixed_assets+=investment-depreciation
        mineflow=0.;mineprofit=0.;taxes=0.;construction=0.;working=0.;totalvolume=0.
        details={}
        for v in INPUTS:
            name,schedule,equity,unit_cost,rate,levy,wht,wc0,basis0,build,close,maint=v
            a=projects[name];tons=schedule[year-1] if year<=len(schedule) else 0.
            tons=min(tons,a['remaining']);a['remaining']-=tons
            finished=year>len(schedule);inflation=1.02**(year-1)
            fx=1 if name=='P' else 7.
            selling_price=(1000 if name=='P' else copper*7)*1.02**max(0,year-5)
            sales=tons*selling_price/1e6;running=tons*unit_cost*fx*inflation/1e6
            minerallevy=sales*levy;replacement=tons*maint*fx*inflation/1e6
            expansion=build[year-1] if year<=len(build) else 0.
            exhausted=(a['basis']+expansion)*tons/max(1e-12,tons+a['remaining']) if tons else 0.
            exhausted=min(exhausted,a['basis']+expansion)
            a['basis']+=expansion+replacement-exhausted
            taxable_income=sales-running-minerallevy-exhausted
            current_tax=max(0,taxable_income-a['loss'])*rate
            a['loss']=max(0,a['loss']-taxable_income)
            if name in ('D','L'):
                current_tax=max(current_tax,.01*sales)
                current_tax+=max(0,copper*1.02**max(0,year-5)-11250)*tons*7/1e6*.5
            paid_tax=a['tax_due']+.8*current_tax;a['tax_due']=.2*current_tax
            required_wc=sales*45/365+running*(75-35)/365
            if not tons and not finished:required_wc=a['wc']
            if finished:required_wc=0.
            wc_movement=required_wc-a['wc'];a['wc']=required_wc
            reclamation=close*inflation if finished and not a['closed'] else 0.
            a['closed']=a['closed'] or finished
            asset_cash=sales-running-minerallevy-paid_tax-replacement-expansion-wc_movement-reclamation
            if asset_cash<0:
                a['advance']-=asset_cash; common=asset_cash; minority=0.;external=0.;withheld=0.
            else:
                priority=min(asset_cash,a['advance']);a['advance']-=priority;left=asset_cash-priority
                external=0.;acquired_return=0.
                if name=='U' and left>0 and zccm+acquired_loan>0:
                    payment=min(left,zccm+acquired_loan)
                    external=payment*zccm/(zccm+acquired_loan);acquired_return=payment-external
                    zccm-=external;acquired_loan-=acquired_return;left-=payment
                minority=left*(1-equity);withheld=left*equity*wht
                common=priority+acquired_return+left*equity-withheld
            mineflow+=common;mineprofit+=(taxable_income-current_tax)*equity
            taxes+=paid_tax;construction+=expansion;working+=wc_movement;totalvolume+=tons
            details[name]=dict(quantity=tons,common_cash=common,cash_tax=paid_tax,change_nwc=wc_movement,construction=expansion)
        tera={1:-.20,2:-.08,3:.03}.get(year,0.)
        operating=service_flow+mineflow+tera
        acquisition_earnout=min(earnout,.065 if copper>8818 and year<=3 else 0.);earnout-=acquisition_earnout
        bond=min(debt,1.99977) if year<=5 else 0.
        coupons=[.003,.006,.01,.015,0.]
        financing_cost=(debt-bond)*.052+(bond*coupons[year-1] if year<=5 else 0.)
        treasury_purchase=.35 if year==1 else 0.
        cash+=operating-financing_cost-acquisition_earnout-treasury_purchase-.08
        minimum=1.20+service_sales*.08
        protected_bond=1.99977 if year<5 else 0.
        scheduled={1:1.10,2:.65,3:.65,5:2.2397424}.get(year,.30)
        scheduled=min(scheduled,max(0,debt-protected_bond))
        premium=.2399724 if year==5 else 0.;cash-=premium
        borrowing=max(0,minimum+scheduled-cash)
        assert borrowing<=max(0,8.5-debt)+1e-8
        debt+=borrowing;cash+=borrowing
        paid=min(scheduled,max(0,cash-minimum));debt-=paid;cash-=paid
        additional=min(max(0,debt-protected_bond),max(0,cash-minimum)*(.5 if year<=5 else .8))
        debt-=additional;cash-=additional
        pcash-=.08
        old_surplus=max(0,oldcash-oldparent-(1.2+oldrev*.08-.25))
        release=.25*old_surplus if year>5 else 0.
        transfer_capacity=max(0,operating)*.85+release
        transfer=min(transfer_capacity,max(0,cash-pcash-(minimum-.25)),dividend_receivable+loan)
        collected=min(transfer,dividend_receivable);dividend_receivable-=collected
        principal=min(transfer-collected,loan);loan-=principal
        source_profit_stock+=service_income+mineprofit
        declaration=min(max(0,source_profit_stock),transfer_capacity);source_profit_stock-=declaration
        dividend_receivable+=declaration
        parent_profit=declaration-.08
        makeup=min(max(0,-retained),max(0,parent_profit))
        legal_reserve=min(max(0,parent_profit-makeup)*.10,max(0,.5*.623776176-reserve))
        reserve+=legal_reserve;retained+=parent_profit-legal_reserve;pcash+=transfer
        planned=[.6,.7,.8,1,1.2][year-1]*UNITS if year<=5 else max(0,cash-minimum)*.90
        paid_to_holder=min(planned,max(0,cash-minimum),max(0,pcash-.25),max(0,retained))
        cash-=paid_to_holder;pcash-=paid_to_holder;retained-=paid_to_holder
        assert cash>=minimum-1e-8 and pcash>=.25-1e-8
        distributions.append(paid_to_holder)
        answer.append(dict(year=year,revenue=service_sales,service_fcf=service_flow,operation=operating,interest=financing_cost,tax=taxes,capex=construction,change_nwc=working,distribution=paid_to_holder,cash=cash,debt=debt,parent_cash=pcash,parent_re=retained,source_profit_budget=source_profit_stock,upstream=transfer,projects=details))
    nextrevenue=service_sales*1.02
    nextcash=nextrevenue*margin*.75-(nextrevenue-service_sales)*(.25+.40+.08)-.08*1.02
    stock_factor=.25/(discount+.25)
    flow_factor=(.85+.15*stock_factor)/(1+discount)**2
    ongoing=nextcash/(discount-.02)*flow_factor
    surplus=max(0,cash-(1.2+service_sales*.08))
    realisable=min(surplus,max(0,retained)+max(0,source_profit_stock)+dividend_receivable+loan)
    claims=debt+zccm+earnout+sum(a['tax_due'] for a in projects.values())
    terminal=ongoing+realisable*stock_factor/(1+discount)**2-claims
    value=sum(amount/(1+discount)**(i+1) for i,amount in enumerate(distributions))+terminal/(1+discount)**30
    return dict(years=answer,pv_per_share=value/UNITS,terminal_equity=terminal)

def read_output():
    obj=json.loads((ROOT/'2026-Q3-output.json').read_text())
    return json.loads(gzip.decompress(base64.b64decode(obj['payload']))) if 'payload' in obj else obj

def check():
    actual=read_output(); comparisons={}
    names={'D':'Dikulushi','L':'Lonshi','U':'Lubambe','A':'Alacran','P':'Phosphate'}
    for label,params in [('core_low',(10500,.15,.12)),('copper_plus_1000',(12000,.16,.115))]:
        independently=literal(*params);prod=actual['scenarios'][label];errors=[]
        def same(a,b):
            errors.append(abs(a-b));assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-8),(label,a,b)
        same(independently['pv_per_share'],prod['pv_per_share']);same(independently['terminal_equity'],prod['terminal_year30']['equity'])
        for a,b in zip(independently['years'],prod['years']):
            for key,target in [('revenue',b['service']['revenue']),('service_fcf',b['service']['fcf']),('operation',b['common_operating_cash']),('interest',b['interest']),('tax',sum(z['cash_tax'] for z in b['mines'])),('capex',sum(z['construction'] for z in b['mines'])),('change_nwc',sum(z['change_nwc'] for z in b['mines'])),('distribution',b['distribution']),('upstream',b['upstream_cash'])]:same(a[key],target)
            for key in ['cash','debt','parent_cash','parent_re','source_profit_budget']:same(a[key],b['ending'][key])
            for code,vals in a['projects'].items():
                project=next(z for z in b['mines'] if z['name']==names[code])
                for key,value in vals.items():same(value,project[key])
        comparisons[label]={'independent_pv':independently['pv_per_share'],'production_pv':prod['pv_per_share'],'compared_values':len(errors),'max_abs_error':max(errors),'literal_inputs':params,'years':independently['years']}
    (ROOT/'independent-literal-output.json').write_text(json.dumps(comparisons,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:{a:b for a,b in v.items() if a!='years'} for k,v in comparisons.items()},indent=2))
if __name__=='__main__':check()

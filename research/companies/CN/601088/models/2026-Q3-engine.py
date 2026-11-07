"""601088: finite economic remittance budget plus actual PRC parent distribution constraint.
CNY bn; no synthetic subsidiary registered capital/statutory profit pool.
All forecasts are budgets, not statements of individual subsidiaries' legal capacity.
Python stdlib only. Run in place; prints summary and emits complete deterministic JSON.
"""
import json,math,gzip,hashlib
from pathlib import Path
SHARES=21.689434304
REGISTERED=19.868519955 # September HKEX registered-capital disclosure, distinct from issued shares
P_RESERVE=11.433
INITIAL=dict(pc=45.426,sc=45.677,pd=52.8,sd=109.752,re=165.353,asset=65.,asset_cost=83.5,mineral=35.283)
# Real tax entities, annual EBIT budget inferred from H1 net income before financing adjustments.
# Residual is an economic tax-expense budget at 25%, never a tax-consolidation entity.
TAX_SOURCES=[('准格尔能源',1.252*2/.85,.15,.58),('宝日希勒能源',1.098*2/.75,.25,.57),('朔黄铁路',3.714*2/.75,.25,.53),('远海航运',.172*2/.75,.25,.51),('黄骅港务',.979*2/.75,.25,.70),('北电胜利能源',.815*2/.85,.15,.63),('神延煤炭',1.444*2/.85,.15,.41)]

def legal_step(re,reserve,registered,profit,voluntary=0):
    covered=min(max(-re,0),max(profit,0))
    levy=min(max(0,registered*.5-reserve),max(0,profit-covered)*.1)
    discretionary=max(0,profit-covered-levy)*voluntary
    return re+profit-levy-discretionary,reserve+levy,levy,discretionary

def tax_due(profit,rate):
    return max(0.,profit)*rate # no instant refund, no cross-entity loss utilization or unverified DTA

def parent_payment(cash,re,floor,desired):
    d=min(max(0,cash-floor),max(0,re),max(0,desired))
    return cash-d,re-d,d

def capital_return(cash,registered,shares,nominal_reduction,payment):
    if nominal_reduction<0 or nominal_reduction>registered or payment>cash or payment<0:raise ValueError('资本返还不可行')
    # Uniform cancellation, actual holder payment is per ORIGINAL share; no new profit.
    return dict(cash=cash-payment,registered=registered-nominal_reduction,shares=shares*(1-nominal_reduction/registered),payment_per_original_share=payment/shares)

def pv(xs,r,start=1):return sum(x/(1+r)**t for t,x in enumerate(xs,start))

def run(r=.08,capex_shift=0,coal_price_shift=0,life=40,scenario='base',upstream=.75,delay=3,interest_shift=0,recovery_year=10,ownership=.72,voluntary=0,old_law=False,legacy_tax=False,salvage=20.,exitcost=8.,tax_leakage=.5,shock=None,toy=None,upstream_haircut=.004,sale_loss_budget=18.5):
    pc,sc,pd,sd,re,asset,basis,mineral=(INITIAL[k] for k in ['pc','sc','pd','sd','re','asset','asset_cost','mineral'])
    if toy:
        upstream_haircut=0;life=toy['life'];pc=sc=pd=sd=asset=basis=mineral=0.;re=toy.get('opening_re',0);salvage=toy.get('salvage',0);exitcost=0;ownership=toy.get('ownership',1)
    reserve=P_RESERVE; rows=[]; pending=[]; source_cumulative=0.; source_paid=0.; treasury=0.; overdue=[]
    for y in range(1,life+1):
        scale=1 if y<=life-15 else max(0,(life-y)/15)
        growth=1+.005*min(y-1,5)
        factor=scale*growth*(.8 if scenario=='cycle' and y<=3 else 1)*(.72 if scenario=='structural' and y>=2 else 1)*(1.1 if scenario=='upside' and y>=3 else 1)
        if scenario=='structural':factor*=max(.3,1-.025*max(0,y-5))
        delta=coal_price_shift*.380*.91*scale # 9% resource tax sensitivity, H1 discloses 8-10%
        peb=28*factor+.3*delta;seb=64*factor+.7*delta
        cap=((57 if y<=3 else 52 if y<=5 else 46)+capex_shift)*scale
        if scenario=='cycle' and y<=3:cap-=4*scale
        if scenario=='structural':cap=max(34*scale,cap*.9)
        if scenario=='upside':cap+=(4 if y<=5 else 1)*scale
        pcap,scap=cap*.24,cap*.76;pda,sda=5.6*scale,29.4*scale
        mineralpay=min(mineral,7.0566) if y<=5 else 0;mineral-=mineralpay
        wc=scale if y<=5 else 0
        pri,sri=.025+interest_shift,.03+interest_shift
        ppretax=peb-pd*pri+pc*.015;spretax=seb-sd*sri+sc*.015
        taxrows=[]
        for name,eb,rate,own in TAX_SOURCES:
            budget=eb/64*spretax
            actual_rate=rate if y<=4 else (rate*.2+.25*.8 if y==5 else .25)
            taxrows.append(dict(name=name,pretax_budget=budget,rate=actual_rate,tax=tax_due(budget,actual_rate),ownership=own))
        residual=spretax-sum(z['pretax_budget'] for z in taxrows)
        taxrows.append(dict(name='未逐家拆分的其余子公司税款预算（不跨法人抵亏）',pretax_budget=residual,rate=.25,tax=tax_due(residual,.25)+tax_leakage*scale))
        ptax=tax_due(ppretax,.25);stax=sum(z['tax'] for z in taxrows)
        if legacy_tax:
            rate=.22 if y<=4 else .245 if y==5 else .25;ptax=ppretax*rate;stax=spretax*rate
        pni=ppretax-ptax;sni=spretax-stax
        invprofit=3. if asset else 0.;invcash=invprofit*.6
        sale=asset if y==recovery_year else 0.;sale_loss=-sale_loss_budget if sale else 0. # conditional profit-capacity haircut, NOT observed parent tax cost
        if sale:asset=0;basis=0
        pfcf=pni+pda-pcap-mineralpay*.15-wc*.3
        sfcf=sni+sda-scap-mineralpay*.85-wc*.7
        if toy:
            pni=toy.get('pni',0);sni=toy.get('sni',0);pda=toy.get('da',0);sda=0.;pcap=toy.get('capex',0);scap=0.;cap=pcap;mineralpay=wc=0.;scale=1.
            pfcf=toy.get('pfcf',pni+pda-pcap);sfcf=toy.get('sfcf',sni);invprofit=invcash=sale=sale_loss=0.;ptax=stax=0.
        pc0,sc0,pd0,sd0=pc,sc,pd,sd
        extra_p=extra_s=0.
        if shock and y==shock['year']:
            # Controlled external cash entitlement fixture, not a free-value core assumption.
            extra_p=shock.get('parent_cash',0);extra_s=shock.get('sub_cash',0)
            re+=shock.get('new_profit',0) # old receivable / principal do NOT create profit
        pc+=pfcf+invcash+sale+extra_p;sc+=sfcf+extra_s
        floorp=10*scale+exitcost*min(1,max(0,(y-(life-10))/5));floors=15*scale
        if toy:floorp=floors=0.
        pb=max(0,floorp-pc);sb=max(0,floors-sc)
        if pd+pb>100 or sd+sb>160:raise ValueError('经营缺口超过限定融资容量，路径不可行')
        pd+=pb;sd+=sb;pc+=pb;sc+=sb
        # Earnings capacity is an ECONOMIC forecast bound only; no statute or losses netting is asserted.
        source_cumulative+=sni*(.9 if old_law and sni>0 else 1)
        scheduled_s=sd/max(1,life-y) if y>life-15 else 0
        scheduled_p=pd/max(1,life-y) if y>life-15 else 0
        ordinary=min(max(0,sni)*upstream,max(0,source_cumulative-source_paid),max(0,sc-floors-scheduled_s))
        sc-=ordinary;source_paid+=ordinary
        received=ordinary*ownership*(1-upstream_haircut);pc+=received
        legalprofit=pni+invcash+received+sale_loss
        if old_law:re+=legalprofit-max(0,legalprofit)*.1;levy=max(0,legalprofit)*.1;disc=0
        else:re,reserve,levy,disc=legal_step(re,reserve,REGISTERED,legalprofit,voluntary)
        common=pni+sni*ownership+invprofit+sale_loss
        # No borrowing for dividends: capex and debt servicing precede all common cash.
        pc,re,div=parent_payment(pc,re,floorp+scheduled_p,max(0,common)*.70)
        pr=min(pd,max(0,pc-floorp));sr=min(sd,max(0,sc-floors))
        pd-=pr;sd-=sr;pc-=pr;sc-=sr
        # All NEW surplus vintages are reviewed every delay years, not just opening cash FIFO.
        sweep=0
        if y%delay==0 or y==life:
            sweep=min(max(0,sc-floors),max(0,source_cumulative-source_paid)) if sd<1e-9 else 0
            sc-=sweep;source_paid+=sweep;pc+=sweep*ownership*(1-upstream_haircut);received+=sweep*ownership*(1-upstream_haircut)
            if old_law:re+=sweep*ownership*(1-upstream_haircut)*.9
            else:
                re,reserve,l,d=legal_step(re,reserve,REGISTERED,sweep*ownership*(1-upstream_haircut),voluntary);levy+=l;disc+=d
            legalprofit+=sweep*ownership*(1-upstream_haircut)
        special=0
        if pd<1e-9:pc,re,special=parent_payment(pc,re,floorp,pc-floorp);div+=special
        # Resource maintenance is consumed in finite extraction; exhausted mines get no book-value floor.
        # Salable rail/port equipment and land rights at closure: gross20, sale costs5, tax25% of gross
        # (zero tax basis assumption: no unverified tax loss shield), restoration8 paid separately.
        liquidation=0;residualnet=0
        if y==life:
            residualnet=(salvage*.5)*(.24+.76*ownership)
            liquidation=pc-pd+ownership*(sc-sd)+asset+residualnet-exitcost
            if liquidation< -1e-8:raise ValueError('退出净款为负；须调整经营/债务或提前退出')
            cancelled=capital_return(max(0,liquidation),REGISTERED,SHARES,REGISTERED,max(0,liquidation))
            div+=max(0,liquidation);pc=sc=pd=sd=asset=0
            assert cancelled['shares']==0 and cancelled['registered']==0
        else:
            assert abs(pc-(pc0+pfcf+invcash+sale+extra_p+pb+received-div-pr))<1e-7
            assert abs(sc-(sc0+sfcf+extra_s+sb-ordinary-sweep-sr))<1e-7
        rows.append(dict(year=y,scale=scale,parent_ebit=peb,sub_ebit=seb,parent_ni=pni,sub_ni=sni,parent_tax=ptax,sub_tax=stax,tax_sources=taxrows,common_profit=common,parent_legal_profit=legalprofit,parent_legal_re=re,parent_statutory_reserve=reserve,statutory_addition=levy,discretionary_addition=disc,parent_fcf=pfcf,sub_fcf=sfcf,capex=cap,depreciation=pda+sda,mineral_payment=mineralpay,nwc=wc,parent_borrow=pb,sub_borrow=sb,parent_repayment=pr,sub_repayment=sr,sub_declared=ordinary+sweep,upstream_received=received,nci_dividend=(ordinary+sweep)*(1-ownership),economic_earned_capacity=source_cumulative-source_paid,parent_cash=pc,sub_cash=sc,parent_debt=pd,sub_debt=sd,financial_profit=invprofit,financial_cash=invcash,asset_sale=sale,asset_sale_loss=sale_loss,remaining_financial_assets=asset,dividend=div,dps=div/SHARES,liquidation=liquidation,residual_disposal_net=residualnet,shares_outstanding=0 if y==life else SHARES,upstream_friction=(ordinary+sweep)*ownership*upstream_haircut,extra_parent_cash=extra_p,extra_sub_cash=extra_s))
    flows=[z['dps'] for z in rows];value=pv(flows,r)
    return dict(value=value,distributions=flows[:5],year5_terminal=pv(flows[5:],r),terminal_pv_share=pv(flows[5:],r,6)/value,rows=rows,parameters=dict(r=r,capex_shift=capex_shift,coal_price_shift=coal_price_shift,life=life,scenario=scenario,upstream=upstream,delay=delay,interest_shift=interest_shift,recovery_year=recovery_year,ownership=ownership,voluntary=voluntary,old_law=old_law,legacy_tax=legacy_tax,salvage=salvage,exitcost=exitcost,tax_leakage=tax_leakage,shock=shock,upstream_haircut=upstream_haircut,sale_loss_budget=sale_loss_budget))

def fixtures():
    assert legal_step(0,5,20,10)[2]==1
    assert legal_step(-8,5,20,10)[2]==.2
    assert legal_step(0,10,20,10)[2]==0
    assert legal_step(0,10,30,10)[2]==1
    assert tax_due(-10,.25)==0
    reduction=capital_return(10,20,20,4,5)
    assert reduction==dict(cash=5,registered=16,shares=16.,payment_per_original_share=.25)
    assert parent_payment(5,-1,0,5)[2]==0
    assert parent_payment(12,10,2,100)==(2,0,10)
    # Exact production run hand case achieved by eliminating annual economy via fixture? handled below
    t=run(r=.1,toy=dict(life=2,pni=4,pfcf=10))
    manual=4/1.1+16/1.1**2
    assert abs(t['value']*SHARES-manual)<1e-10
    z=run(r=.1,toy=dict(life=2,pni=4,da=6,capex=6,salvage=20))
    assert abs(z['value']*SHARES-(4/1.1+14/1.1**2))<1e-10
    try:run(toy=dict(life=2,pni=-300,pfcf=-300))
    except ValueError:pass
    else:raise AssertionError('亏损融资上限未生效')
    old_cash=run(r=.1,toy=dict(life=2,pni=0,pfcf=10))
    new_cash=run(r=.1,toy=dict(life=2,pni=10,pfcf=10))
    assert old_cash['distributions'][0]==0 and abs(old_cash['value']*SHARES-20/1.1**2)<1e-10
    assert abs(new_cash['distributions'][0]*SHARES-10)<1e-10
    minority=run(r=.1,toy=dict(life=2,sni=4,sfcf=10,ownership=.6))
    assert abs(sum(minority['distributions'])*SHARES-12)<1e-10
    checks=[]
    for y in [20,38]:
        b=run();q=run(shock=dict(year=y,parent_cash=2,new_profit=0))
        incremental=sum(a['dividend']-c['dividend'] for a,c in zip(q['rows'],b['rows']))
        payments=[a['year'] for a,c in zip(q['rows'],b['rows']) if a['dividend']-c['dividend']>1e-8]
        assert incremental>=2-1e-7 and max(payments)<=40
        checks.append(dict(injection_year=y,amount=2,incremental_paid=incremental,payment_years=payments))
    # Nominal years80/160 after actual closure have no company, no new cash rights or perpetuity.
    return dict(law_tests=True,tax_loss_test=True,payment_hand_case=dict(actual=t['value']*SHARES,manual=manual,flows=[v*SHARES for v in t['distributions']]),zero_growth_maintenance_and_capital_recovery=dict(actual=z['value']*SHARES,manual=4/1.1+14/1.1**2),unfundable_loss_rejected=True,old_receivable_does_not_create_profit=True,capital_return_cancels_shares=True,minority_cash_and_principal_test=True,future_surplus_checks=checks,years80_160='40年完成清算，股份归零；80/160年无存续经营现金，有限矿寿测试使用20/38年。')

def build():
    specs={'base':{},'core_low':dict(r=.085,capex_shift=2),'core_high':dict(r=.075,capex_shift=-2),'holder_low':dict(r=.085),'holder_high':dict(r=.075),'cycle':dict(scenario='cycle'),'structural':dict(scenario='structural',life=30,recovery_year=10),'upside':dict(scenario='upside'),'coal_minus20':dict(coal_price_shift=-20),'capex_plus5':dict(capex_shift=5),'life30':dict(life=30),'rate9':dict(r=.09),'upstream50_delay5':dict(upstream=.5,delay=5),'interest_plus1pct':dict(interest_shift=.01),'financial_recovery40':dict(recovery_year=40),'sub_ownership68':dict(ownership=.68),'sub_ownership76':dict(ownership=.76),'no_salvage':dict(salvage=0),'exit_double':dict(exitcost=16),'sale_profit_capacity_no_loss':dict(sale_loss_budget=0),'sale_profit_capacity_full_book_loss':dict(sale_loss_budget=83.5),'crossborder_friction2pct':dict(upstream_haircut=.02),'tax_leakage2':dict(tax_leakage=2),'voluntary10':dict(voluntary=.1),'same_economy_old_law':dict(old_law=True),'same_economy_old_tax':dict(legacy_tax=True)}
    cases={k:run(**v) for k,v in specs.items()}
    oldlaw_comparison={k:run(**dict(v,old_law=True)) for k,v in specs.items() if k not in ['same_economy_old_law','same_economy_old_tax','voluntary10']}
    fcff=28*.75+5.6-46*.24+.72*(64*.75+29.4-46*.76)
    bridge=45.426+.72*45.677-52.8-.72*109.752+65-35.283*(.15+.85*.72)
    early=sum(((57 if y<=3 else 52)-46+1)*(.24+.76*.72)/1.08**y for y in range(1,6))
    method2={str(r):(fcff*sum((1+r)**-y for y in range(1,31))+bridge-early+((20*.5)*(.24+.76*.72)-8)/(1+r)**40)/SHARES for r in [.085,.08,.075]}
    return dict(units='人民币十亿元、十亿股；每股元',shares=SHARES,initial=INITIAL,cases=cases,oldlaw_comparison=oldlaw_comparison,method2=dict(fcff=fcff,bridge=bridge,early=early,values=method2),value_range=dict(low=round(cases['core_low']['value'],2),high=round(cases['core_high']['value'],2)),year5_terminal_range=dict(low=round(cases['holder_low']['year5_terminal'],2),high=round(cases['holder_high']['year5_terminal'],2)),fixtures=fixtures())
if __name__=='__main__':
    o=build();p=Path(__file__).parent;raw=(json.dumps(o,ensure_ascii=False,separators=(',',':'))+'\n').encode();(p/'2026-Q3-output.json').write_bytes(raw)
    (p/'2026-Q3-output.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    summary={k:o[k] for k in ['value_range','year5_terminal_range','method2','fixtures']};summary['cases']={k:dict(value=v['value'],distributions=v['distributions'],year5_terminal=v['year5_terminal']) for k,v in o['cases'].items()}
    (p/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))

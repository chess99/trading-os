#!/usr/bin/env python3
"""CN301498 2026Q3 reconstructed model, NOT byte-exact recovery.
Stdlib, self-contained. Money CNY 100 million; shares 100 million.
Historical-source cutoff 2026-10-27; reconstructed budgets require fresh audit.
python model.py --out DIR generates all numerical/model tables.
"""
from pathlib import Path
from copy import deepcopy
import argparse,json
SHARES=4.01133
CASH=13.1208052057+4.957272599+1.8638702753+.7
SHORT=12.5004688889
LONG=.340825
BASE={
 'revenue':[72,78,84.5,91,96.5], 'margin':[.07,.08,.09,.095,.10],
 'growthcap':[6,5.5,4.5,3,1], 'maintenance':[2.5,2.7,3,3.3,3.5],
 'da':[2.3,2.5,2.8,3.1,3.3], 'parentcap':[2.3,2.5,1.8,1,.7],
 'payout':[.2,.25,.3,.3,.35], 'fixed':[0,.65,0,0,0],
 'brandrev':[1,1.6,2.2,2.8,3.4], 'brandmargin':.05,
 'buyback':[.6636085757,0,0,0,0], 'subscription':[0]*5,
 'registered':[4.01133]*5, 'shares':SHARES,
 'cash':CASH, 'parentcash':11., 'parentretained':2.6796800999,
 'parentreserve':.9290301779, 'parentshort':7.5505157778,
 'wc_rate':.1, 'revenue_open':71.5612458114, 'tax':.25,
 'deposit':.015, 'interest':.038, 'parent_nopat_share':.45,
 'parent_da_share':.45, 'parent_wc_share':.4,
 'group_floor':5., 'parent_floor':1., 'sub_floor':3.,
 'full_nonrenewal':False, 'growth6_10':[.06,.055,.045,.035,.03],
 'marginal_roic':.15, 'steady_roic':.12, 'steady_g':.02,
 'maintenance_gap':.2, 'r':.105,
}

def statutory_profit(retained,earned,reserve,registered_capital):
    recovered=min(max(-retained,0),max(earned,0))
    appropriation=min(max(0,registered_capital*.5-reserve),max(earned-recovered,0)*.1)
    return retained+earned-appropriation,reserve+appropriation,appropriation

def brand_earnout(revenue,margin):
    return (1. if revenue>=5 else .5 if revenue>=3 else 0.) if margin>0 else 0.

def continuation(nopat,r,growth,roic,g,steady_roic,gap):
    assert r>g and roic>0 and steady_roic>0
    rows=[]; pv=0.
    for t,rate in enumerate(growth,1):
        new=nopat*(1+rate); invest=(new-nopat)/roic
        fcf=new-invest-gap; pv+=fcf/(1+r)**t
        rows.append({'year':t+5,'nopat':new,'growth':rate,'reinvestment':invest,'maintenance_gap':gap,'fcff':fcf})
        nopat=new
    steady=nopat*(1+g)*(1-g/steady_roic)-gap
    distant=steady/(r-g)/(1+r)**5
    return {'ev5':pv+distant,'explicit6_10_pv_at5':pv,'distant_pv_at5':distant,'year11_fcff':steady,'rows':rows}

def roll(spec):
    s=deepcopy(spec); cash=s['cash']; pc=s['parentcash']; retained=s['parentretained'];reserve=s['parentreserve']
    short=SHORT; ps=s['parentshort']; rev=s['revenue_open']; rows=[]
    cal28=.75*s['brandrev'][1]+.25*s['brandrev'][2]
    earnout=brand_earnout(cal28,s['brandmargin'])
    for i in range(5):
        opening=cash; po=pc; so=short; pso=ps
        revenue=s['revenue'][i]; nopat=revenue*s['margin'][i]*(1-s['tax'])
        netinterest=(opening*s['deposit']-(short+LONG)*s['interest'])*(1-s['tax'])
        ni=nopat+netinterest; wc=max(0,revenue-rev)*s['wc_rate']; da=s['da'][i]
        op=ni+da-wc
        own=nopat*s['parent_nopat_share']+(po*s['deposit']-ps*s['interest'])*(1-s['tax'])
        pop=own+da*s['parent_da_share']-wc*s['parent_wc_share']
        legal,reserve,allocation=statutory_profit(retained,own,reserve,s['registered'][i])
        cap=s['growthcap'][i]+s['maintenance'][i]; pcap=s['parentcap'][i]
        acquisition=s['fixed'][i]+(earnout if i==2 else 0.)
        buy=s['buyback'][i]; sub=s['subscription'][i]
        gpre=opening+op-cap-acquisition-buy+sub
        ppre=po+pop-pcap-acquisition-buy+sub
        repay=short
        if s['full_nonrenewal']:
            net=short
        elif i>=2:
            net=min(short,2.,max(0,gpre-7.))
        else: net=0.
        renewal=repay-net
        prep=ps; pnet=net*ps/short if short>0 else 0.; prenew=prep-pnet
        srep=repay-prep; srenew=renewal-prenew
        gpre-=net; ppre-=pnet; short-=net; ps-=pnet
        # Treasury support increases subsidiary cash but never parent profit or group cash.
        support=max(0,ppre-(gpre-s['sub_floor']))
        ppre-=support
        requested=max(0,ni)*s['payout'][i]
        dividend=max(0,min(requested,gpre-s['group_floor'],ppre-s['parent_floor'],max(0,legal)))
        cash=gpre-dividend; pc=ppre-dividend; retained=legal-dividend
        subclose=(opening-po)+(op-pop)-(cap-pcap)-srep+srenew+support
        # Acquisition/buyback/subscription all borne by parent; their net group/sub difference is zero.
        conservation=(opening+op-cap-acquisition-buy+sub-repay+renewal-dividend)-cash
        parentcheck=(po+pop-pcap-acquisition-buy+sub-prep+prenew-support-dividend)-pc
        assert abs(conservation)<1e-9 and abs(parentcheck)<1e-9
        assert abs(subclose-(cash-pc))<1e-9
        assert cash>=s['group_floor']-1e-9 and pc>=s['parent_floor']-1e-9 and subclose>=s['sub_floor']-1e-9, (i,cash,pc,subclose)
        rows.append(dict(year=i+1,period=f'{2026+i}-10/{2027+i}-09',revenue=revenue,margin=s['margin'][i],nopat=nopat,ni=ni,da=da,wc=wc,operating_cash=op,growth_capex=s['growthcap'][i],maintenance_capex=s['maintenance'][i],capex=cap,acquisition=acquisition,buyback=buy,subscription=sub,cash_open=opening,bank_debt_open=so+LONG,external_short_repayment=repay,external_short_renewal=renewal,net_short_repayment=net,dividend_requested=requested,dividend=dividend,dps=dividend/s['shares'],cash_close=cash,bank_debt_close=short+LONG,parent_cash_open=po,parent_own_profit=own,parent_operating_cash=pop,parent_capex=pcap,parent_short_open=pso,parent_short_repayment=prep,parent_short_renewal=prenew,parent_short_close=ps,parent_support_downstream=support,parent_cash_close=pc,parent_legal_before_distribution=legal,parent_retained_close=retained,parent_reserve=reserve,parent_appropriation=allocation,registered_capital=s['registered'][i],subsidiary_short_repayment=srep,subsidiary_short_renewal=srenew,subsidiary_cash_close=subclose,upstream_dividend=0.,nci_distribution=0.,conservation_error=conservation,parent_conservation_error=parentcheck))
        rev=revenue
    return {'assumptions':s,'npfg_calendar2028_revenue':cal28,'npfg_contingent':earnout,'rows':rows}

def value(result,r=None):
    s=result['assumptions']; r=s['r'] if r is None else r; end=result['rows'][-1]
    c=continuation(end['nopat'],r,s['growth6_10'],s['marginal_roic'],s['steady_g'],s['steady_roic'],s['maintenance_gap'])
    netcash=end['cash_close']-end['bank_debt_close']; terminal=(c['ev5']+netcash)/s['shares']
    divpv=sum(row['dps']/(1+r)**(i+1) for i,row in enumerate(result['rows']))
    terminalpv=terminal/(1+r)**5
    return dict(r=r,value_per_share=divpv+terminalpv,dividend_pv=divpv,terminal_pv=terminalpv,terminal_per_share=terminal,terminal_net_cash=netcash,terminal_pv_fraction=terminalpv/(divpv+terminalpv),distant_value_fraction=c['distant_pv_at5']/s['shares']/(1+r)**5/(divpv+terminalpv),continuation=c)

def scenarios():
    cases={'base':deepcopy(BASE)}
    def add(name,**kw): cases[name]=dict(deepcopy(BASE),**kw)
    add('margin_minus_1pp',margin=[x-.01 for x in BASE['margin']])
    add('full_short_debt_nonrenewal_rebuilt',full_nonrenewal=True,payout=[0,0,.1,.2,.25],r=.12,revenue=[65,66,70,75,81],margin=[.045,.05,.065,.08,.09],growthcap=[1.4,2,4,4,3],parentcap=[1.2,1.2,1.8,1.8,1.2],parent_floor=2.)
    add('parent_minus_4',parentcash=7.)
    add('q3_incremental_debt_all_parent',parentshort=11.0505157778)
    add('other_financial_cash_zero',cash=CASH-.7)
    add('continuation_roic12',marginal_roic=.12)
    add('continuation_roic18',marginal_roic=.18)
    add('all_awards_conditional',shares=4.027775,subscription=[.35,.1771994,0,0,0],registered=[4.01133,4.01955,4.027775,4.027775,4.027775])
    add('upfront60m_unpaid',fixed=[.6,.65,0,0,0])
    add('seller_event_fixed_early',fixed=[.65,0,0,0,0])
    # Incomplete retained scenario schedules are REBUILT budgets, never claimed identical to lost originals.
    add('cyclical_rebuilt',revenue=[69,73,79,85,91],margin=[.045,.06,.075,.085,.09],growthcap=[4,4,4,3,2],payout=[.1,.2,.25,.3,.3],r=.115,growth6_10=[.05,.045,.04,.03,.025])
    add('structural_rebuilt',revenue=[66,64,62,61,60],margin=[.035,.03,.025,.025,.025],growthcap=[3,.5,0,0,0],parentcap=[1.8,1.2,1.2,1.2,1.2],payout=[0]*5,brandmargin=-.02,r=.13,growth6_10=[0]*5,steady_g=0.,maintenance_gap=.3)
    add('upside_rebuilt',revenue=[76,86,98,110,121],margin=[.08,.095,.11,.12,.125],brandrev=[1.7,3.2,5.2,6.5,8.],brandmargin=.1,r=.10,growth6_10=[.08,.07,.06,.04,.03],marginal_roic=.18,steady_roic=.15)
    return cases

def manual_checks():
    a=statutory_profit(-10,8,0,100); b=statutory_profit(a[0],5,a[1],100)
    assert a==(-2,0,0) and all(abs(x-y)<1e-12 for x,y in zip(b,(2.7,.3,.3)))
    c=continuation(100,.1,[0]*5,.15,0,.12,0)['ev5']; d=continuation(100,.2,[0]*5,.15,0,.12,0)['ev5']
    assert abs(c-1000)<1e-9 and abs(d-500)<1e-9
    assert [brand_earnout(x,.1) for x in [2.99,3,4.99,5]]==[0,.5,.5,1]
    assert brand_earnout(10,0)==0
    return {'production_legal_loss_then_recovery':[a,b],'production_constant_cash_values':[c,d],'earnout_boundaries':'PASS'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default=str(Path(__file__).resolve().parent)); args=ap.parse_args(); out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    allresults={}
    for name,s in scenarios().items():
        result=roll(s);result['valuation']=value(result)
        if name=='base': result['low']=value(result,.115); result['high']=value(result,.10)
        allresults[name]=result
    payload={'status':'reconstructed_requires_fresh_independent_review','units':'CNY 100m; shares 100m; per-share CNY','historical_cutoff':'2026-10-27T13:00:00+00:00','manual_checks':manual_checks(),'scenarios':allresults}
    (out/'2026-Q3-output.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    lines=['# 重建模型全情景结果','金额亿元；每股元；不是原输出字节恢复。']
    for name,res in allresults.items():
        v=res['valuation'];lines += [f'\n## {name}',f"价值 {v['value_per_share']:.6f}；终值每股 {v['terminal_per_share']:.6f}；NPFG2028收入 {res['npfg_calendar2028_revenue']:.3f}；尾款 {res['npfg_contingent']:.3f}",'|年|收入|净利|资本开支|银行偿还|续开|股利|集团现金|集团债务|母现金|母债务|母未分配|子现金|','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for row in res['rows']:
            keys=['year','revenue','ni','capex','external_short_repayment','external_short_renewal','dividend','cash_close','bank_debt_close','parent_cash_close','parent_short_close','parent_retained_close','subsidiary_cash_close']
            lines.append('|'+ '|'.join(f'{row[k]:.6f}' for k in keys)+'|')
    (out/'model-tables.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({name:r['valuation']['value_per_share'] for name,r in allresults.items()},indent=2))
if __name__=='__main__':main()

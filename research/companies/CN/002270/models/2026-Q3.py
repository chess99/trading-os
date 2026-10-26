#!/usr/bin/env python3
"""CN:002270; CNY billion except per share. Deterministic legal/cash annual model.
Run from any cwd; writes next to this file. No external input/dependencies.
"""
import json, math, pathlib, copy, gzip, base64, hashlib, argparse
SHARES=.896225431
# Legal-subject budgets: actual ownership/capital, estimated standalone allocation.
SPECS=[('Guizhou',.20,.060,1.,'Shanghai'),('Zunyi',.06,.050,1.,'Shanghai'),('Russia',.02,.00113862286,.65,'Shanghai'),('Turkey',.02,.017401925,.9832,'Shanghai'),('CNC',0.,.092,1.,'Parent'),('SolarLeaf',0.,.133,1.,'SolarHolding'),('SolarHolding',0.,.387,1.,'Parent'),('ShanghaiHV',.15,.050,1.,'Shanghai'),('Shanghai',.55,.100,1.,'Parent')]

def legal_step(ur,reserve,capital,profit,rate=.1,cap_fraction=.5):
    recovery=min(max(-ur,0.),max(profit,0.))
    addition=min(max(capital*cap_fraction-reserve,0.),max(profit-recovery,0.)*rate)
    return ur+profit-addition,reserve+addition,addition

def payout(legal,cash,floor,target):
    return min(max(legal,0.),max(cash-floor,0.),max(target,0.))

def run(mode='base',discount=.10,years=600,margin_shift=0.,roic=.25,lag=.0,legal_zero=False,extra_payment=0.,issue=0.,debt_limit=.95,shanghai_weight=.55,parent_cash=.06,old_ar_delay=0):
    specs=[(n,(shanghai_weight if n=='Shanghai' else .15+.55-shanghai_weight if n=='ShanghaiHV' else w),cap,own,par) for n,w,cap,own,par in SPECS]
    cash0=.99942404399-.23301861206-.024998103-.00927546078
    nodes={}
    for name,w,cap,own,par in specs:
        nodes[name]=dict(cash=(cash0-parent_cash)*({'Shanghai':.78,'ShanghaiHV':.02,'CNC':.02,'SolarLeaf':.04,'SolarHolding':.02,'Guizhou':.04,'Zunyi':.02,'Russia':.04,'Turkey':.02}[name]),ur=0. if legal_zero else (.30 if name=='Shanghai' else .03),reserve=0.,capital=cap,debt=.23858193369 if name=='Shanghai' else (.55 if name=='SolarLeaf' else 0.),payable=.39698138794 if name=='Shanghai' else 0.,owner=own,parent=par,operating_capital=2.3*w if w else (.7*.45 if name=='CNC' else .7*.55 if name=='SolarLeaf' else 0.))
    nodes['Parent']=dict(cash=parent_cash,ur=.44478031239-.23301861206,reserve=.36530171861,capital=SHARES,debt=0.,payable=0.,owner=1.,parent=None)
    ar={n:0. for n in nodes};ar['Parent']=.39698138794
    rev=2.36;other=.34; shares=SHARES; rows=[]; feasible=True; fail=None; debt_cap=debt_limit; sponsor_used=0.; maturity={n:{} for n in nodes}
    for t in range(1,years+1):
        growth=[.09,.09,.08,.07,.06,.05,.04,.03,.025,.02][min(t-1,9)]
        if mode=='cyclical' and t<=3:growth=[-.15,.0,.18][t-1]
        if mode=='structural':growth=[-.22,-.08,0.,0.,.01][min(t-1,4)]
        if mode=='upside':growth=[.13,.12,.10,.09,.07,.06,.05,.04,.03,.02][min(t-1,9)]
        oldrev=rev; rev*=1+growth; oldother=other;other*=1+(.03 if t<6 else .02)
        margin=.34-.02*min(t,10)/10+margin_shift
        if mode=='cyclical' and t<=3:margin-=[.05,.03,.01][t-1]
        if mode=='structural':margin=.23+margin_shift
        if mode=='upside':margin+=.012
        ep=rev*margin; op=other*.055; hq=.02*((1.01 if mode=='structural' else 1.02)**(t-1))
        inc=max(rev-oldrev,0)*margin/(roic if t<=5 else min(roic,.18))
        if mode=='structural':inc+=rev*.015 # stranded capital, no immediate liquidation credit
        oinc=max(other-oldother,0)*.055/.12
        beginning={n:copy.deepcopy(s) for n,s in nodes.items()}; start_ar=ar.copy(); receipts={n:0. for n in nodes}; declarations={n:0. for n in nodes}; netprofit={n:0. for n in nodes}; detail={}; minor=0.; ext=0.; equity=0.
        if t==1 and issue:
            nodes['Parent']['cash']+=issue;nodes['Parent']['capital']+=issue/10; shares+=issue/10;equity=issue
        for name,w,cap,own,par in specs:
            s=nodes[name]; old=beginning[name]
            oper=ep*w if w else (op*.45 if name=='CNC' else op*.55 if name=='SolarLeaf' else 0.)
            investment=inc*w if w else (oinc*.45 if name=='CNC' else oinc*.55 if name=='SolarLeaf' else 0.)
            interest=s['cash']*.015-s['debt']*.045
            profit=oper+interest+declarations[name]
            # Subsidiary declaration income is not consolidated new earnings.
            s['cash']+=oper+interest-investment+receipts[name]
            s['operating_capital']+=investment
            s['ur'],s['reserve'],reserve_add=legal_step(s['ur'],s['reserve'],s['capital'],profit, .05 if name=='Turkey' else .1, .2 if name=='Turkey' else .5)
            principal=min(s['debt'],((.23858193369 if name=='Shanghai' else .55 if name=='SolarLeaf' else 0.)/8 if t<=8 else 0.)+maturity[name].pop(t,0.))
            s['cash']-=principal;s['debt']-=principal
            floor=rev*.085*w if w else other*.085*({'CNC':.45,'SolarLeaf':.55,'SolarHolding':0.}[name])
            old_paid=min(s['payable'], max(s['cash']-floor,0.)) if not (name=='Shanghai' and t<=old_ar_delay) else 0.
            s['payable']-=old_paid;s['cash']-=old_paid
            old_tax=old_paid*own*(.10 if name in ['Russia','Turkey'] else 0.)
            receipts[par]+=old_paid*own-old_tax;ar[par]-=old_paid*own-old_tax;minor+=old_paid*(1-own)
            if name=='CNC':
                receipts['Parent']-=old_paid*.1304;receipts['Shanghai']+=old_paid*.1304
                ar['Parent']+=old_paid*.1304;ar['Shanghai']-=old_paid*.1304
            # Ordinary and release dividends share ONE legal and cash cap.
            desired=max(oper*.78,0.)+max(s['cash']-floor-oper*.78,0.)*.20
            legal=max(s['ur'],0.)
            if name=='Turkey':legal=min(legal,(legal+.005*s['capital'])/1.1)
            declared=payout(legal,s['cash'],floor,desired)
            second=max(declared-.05*s['capital'],0.)*.1 if name=='Turkey' else 0.
            s['ur']-=second;s['second_reserve']=s.get('second_reserve',0.)+second
            paid=declared*(1-lag);s['ur']-=declared;s['cash']-=paid;s['payable']+=declared-paid
            tax=.10 if name in ['Russia','Turkey'] else 0.
            declarations[par]+=declared*own*(1-tax);receipts[par]+=paid*own*(1-tax);ar[par]+=(declared-paid)*own*(1-tax);minor+=paid*(1-own)
            foreign_tax=paid*own*tax+old_tax
            # CNC indirect 13.04% is routed through Shanghai, still 100% group-owned.
            if name=='CNC':
                for ledger,amount in [(declarations,declared),(receipts,paid)]:
                    ledger['Parent']-=amount*.1304;ledger['Shanghai']+=amount*.1304
                ar['Parent']-=(declared-paid)*.1304;ar['Shanghai']+=(declared-paid)*.1304
            detail_floor=floor
            netprofit[name]=oper+interest-foreign_tax
            detail[name]=dict(floor=floor,begin=old,operating_profit=oper,financial_income_net=interest,declared_income=declarations[name],profit=profit,reinvestment=investment,maintenance=rev*.04*w if w else other*.04*({'CNC':.45,'SolarLeaf':.55,'SolarHolding':0.}[name]),dep=rev*.04*w if w else other*.04*({'CNC':.45,'SolarLeaf':.55,'SolarHolding':0.}[name]),reserve_add=reserve_add,second_reserve_add=second,withholding_paid=foreign_tax,old_dividend_paid=old_paid,declared=declared,paid=paid,received=receipts[name],debt_repaid=principal,end=copy.deepcopy(s))
        p=nodes['Parent'];profit=declarations['Parent']-hq+p['cash']*.015-p['debt']*.045
        netprofit['Parent']=-hq+p['cash']*.015-p['debt']*.045
        parent_principal=min(p['debt'],maturity['Parent'].pop(t,0.))
        p['debt']-=parent_principal
        p['cash']+=receipts['Parent']+netprofit['Parent']-parent_principal
        # Sponsor solar debt amortization through the actual holding chain before dividends.
        need=max(detail['SolarLeaf']['floor']-nodes['SolarLeaf']['cash'],0.)
        injection=min(need,max(p['cash']-.03,0.),max(.70-sponsor_used,0.))
        p['cash']-=injection;nodes['SolarLeaf']['cash']+=injection
        nodes['SolarLeaf']['capital']+=injection;nodes['SolarHolding']['capital']+=injection
        sponsor_used+=injection
        detail['SolarLeaf']['capital_cash_in']=injection;detail['SolarHolding']['parent_equity_in_and_project_equity_out']=injection
        for name,w,cap,own,par in specs:
            ss=nodes[name]; floor=detail[name]['floor']
            borrowing=min(max(floor-ss['cash'],0.),max(debt_cap-sum(z['debt'] for z in nodes.values()),0.))
            if borrowing<1e-12*max(1.,floor):borrowing=0.
            ss['cash']+=borrowing;ss['debt']+=borrowing;ext+=borrowing
            if borrowing:
                for due in [t+1,t+2]:maturity[name][due]=maturity[name].get(due,0.)+borrowing/2
            detail[name]['borrowed']=borrowing;detail[name]['end']=copy.deepcopy(ss)
            if ss['cash']<floor-1e-10*max(1.,floor):feasible=False;fail={'year':t,'entity':name,'cash':ss['cash'],'required_cash':floor,'zero_D_failed':True}

        recovery=.07 if t==2 else (.04 if t==3 else 0.)
        p['cash']+=recovery
        buyback=.125001897 if t==1 else 0.
        payment=extra_payment if t==1 else (-extra_payment if t==3 else 0.)
        p['cash']-=buyback+payment
        p['ur'],p['reserve'],ra=legal_step(p['ur'],p['reserve'],p['capital'],profit)
        group_profit=sum(netprofit.values()); parent_floor=.03*(1.01 if mode=='structural' else 1.02)**(t-1)
        # No issue proceeds are automatically dividend profit.
        target=max(group_profit,0.)*.70 if t<=5 else max(p['cash']-parent_floor,0.)
        D=payout(p['ur'],p['cash'],parent_floor,target)
        p['ur']-=D;p['cash']-=D
        borrow=min(max(parent_floor-p['cash'],0.),max(debt_cap-sum(s['debt'] for s in nodes.values()),0.))
        if borrow<1e-12*max(1.,parent_floor):borrow=0.
        p['cash']+=borrow;p['debt']+=borrow;ext+=borrow
        if borrow:
            for due in [t+1,t+2]:maturity['Parent'][due]=maturity['Parent'].get(due,0.)+borrow/2
        if p['cash']<parent_floor-1e-10*max(1.,parent_floor):feasible=False;fail={'year':t,'entity':'Parent','cash':p['cash'],'required_cash':parent_floor,'zero_D_failed':True}
        detail['Parent']=dict(floor=parent_floor,debt_repaid=parent_principal,begin=beginning['Parent'],profit=profit,operating_profit=-hq,declared_income=declarations['Parent'],received=receipts['Parent'],reserve_add=ra,dividend=D,nonoperating_asset_recovery=recovery,solar_equity_out=injection,sponsor_used=sponsor_used,buyback=buyback,extra_settlement=payment,borrowed=borrow,equity_raised=equity,end=copy.deepcopy(p))
        b=sum(v['cash'] for v in beginning.values());e=sum(v['cash'] for v in nodes.values());rep=sum(d.get('debt_repaid',0) for d in detail.values())
        residual=e-(b+group_profit-inc-oinc-rep+ext+equity+recovery-D-minor-buyback-payment)
        assert abs(residual)<1e-6*max(1,e), (t,residual)
        assert all(s['reserve']<=s['capital']*.5+1e-9 and s['reserve']>=0 for s in nodes.values())
        assert all(s['cash']>=-1e-8 for s in nodes.values()) or not feasible
        for n,s in nodes.items():
            if n!='Parent': assert s['ur']>=-1e-9 or detail[n]['declared']==0
        rows.append(dict(year=t,electric_revenue=rev,other_revenue=other,margin=margin,group_profit=group_profit,reinvestment=inc+oinc,dividend=D,dps=D/shares,shares=shares,minority_paid=minor,financing=ext,equity=equity,ar_end=ar.copy(),new_debt_maturities=copy.deepcopy(maturity),cash_residual=residual,subjects=detail))
        if not feasible:break
    pv=sum(x['dps']/(1+discount)**x['year'] for x in rows) if feasible else None
    tv=sum(x['dps']/(1+discount)**(x['year']-5) for x in rows if x['year']>5) if feasible else None
    return dict(mode=mode,discount=discount,years=years,feasible=feasible,failure=fail,pv=pv,tv5=tv,first5=[x['dps'] for x in rows[:5]],tail_share=(sum(x['dps']/(1+discount)**x['year'] for x in rows if x['year']>10)/pv if feasible else None),rows=rows)

def tests():
    assert payout(3.,10.,2.,4.+5.)==3. # Ordinary+principal release share one legal cap
    assert payout(10.,3.,2.,9.)==1.
    assert payout(-1.,10.,0.,9.)==0.
    assert legal_step(-3.,0.,10.,2.)==(-1.,0.,0.)
    assert legal_step(-3.,0.,10.,5.)==(1.8,.2,.2)
    assert legal_step(4.,4.9,10.,10.)==(13.9,5.,.09999999999999964)
    # Actual production chain: known no income = no cash D, legal recovery tests above.
    z=run(years=1,extra_payment=10.)
    assert not z['feasible'] and z['failure']['zero_D_failed'] and z['rows'][0]['dividend']==0
    a=run(years=1,lag=1.)
    assert abs(a['rows'][0]['ar_end']['Parent']-(.39698138794+a['rows'][0]['subjects']['Parent']['declared_income']-a['rows'][0]['subjects']['Parent']['received']))<1e-10
    r=run(years=1)
    pre=r['rows'][0]['subjects']['Parent']['end']['cash']+r['rows'][0]['dividend']
    z=run(years=1,extra_payment=pre-.015,debt_limit=0.)
    assert not z['feasible'] and 0<z['failure']['cash']<z['failure']['required_cash'] and z['rows'][0]['dividend']==0
    f=run(years=4,extra_payment=pre+.02)
    assert any(x['financing']>.001 for x in f['rows'])
    assert f['rows'][1]['subjects']['Parent']['debt_repaid']>0 and f['rows'][2]['subjects']['Parent']['debt_repaid']>0
    return {'positive_cash_fixture':z['failure'],'new_debt_fixture':[{'year':r['year'],'borrowing':r['financing'],'parent_principal':r['subjects']['Parent']['debt_repaid']} for r in f['rows']],'positive_cash_below_floor':'pass','new_debt_actual_two_year_amortization':'pass','legal_loss_recovery':'pass','reserve_cap':'pass','zero_D_finance_failure':'pass','declaration_vs_cash':'pass'}

def expand_output(packed):
    """Pure lossless expansion; no files, mutations or economic recomputation."""
    x=copy.deepcopy(packed)
    compressed=x.pop('annual_data',None)
    if compressed is not None:
        payload=json.loads(gzip.decompress(base64.b64decode(compressed['payload_base64'])))
        for name,rows in payload.items():x['paths'][name]['rows']=rows
        x['subject_encoding']=compressed['subject_encoding']
    schemas=x.pop('subject_encoding')['schemas']
    def unpack(a):
        return {k:(unpack(v) if isinstance(v,list) else v) for k,v in zip(schemas[a[0]],a[1:])}
    for path in x['paths'].values():
        if isinstance(path['rows'],list):
            for row in path['rows']:
                row['subjects']={name:unpack(d) for name,d in row['subjects'].items()}
                if row.get('new_debt_maturities')=={'reference':'empty_by_subject'}:row['new_debt_maturities']={name:{} for name in row['subjects']}
            for i,row in enumerate(path['rows']):
                if i:
                    for name,d in row['subjects'].items():
                        if d.get('begin')=={'reference':'previous_end'}:d['begin']=copy.deepcopy(path['rows'][i-1]['subjects'][name]['end'])
    for path in x['paths'].values():
        if isinstance(path['rows'],dict):path['rows']=copy.deepcopy(x['paths'][path['rows']['reference']]['rows'])
    if compressed is not None:
        assert hashlib.sha256(canonical_json(x)).hexdigest()==compressed['expanded_canonical_sha256']
    return x

def canonical_json(x):
    return json.dumps(x,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode('utf-8')

def main():
    paths={n:run(mode=m,discount=r,**kw) for n,m,r,kw in [('base_low','base',.105,{}),('base_high','base',.09,{}),('base','base',.0975,{}),('cyclical','cyclical',.0975,{}),('structural','structural',.0975,{}),('upside','upside',.0975,{}),('margin_minus3','base',.0975,{'margin_shift':-.03}),('roic15','base',.0975,{'roic':.15}),('receipt_half','base',.0975,{'lag':.5}),('no_opening_sub_legal','base',.0975,{'legal_zero':True}),('parent_payment','base',.0975,{'extra_payment':.078}),('issue','base',.0975,{'issue':.5}),('upstream_manufacturing','base',.0975,{'shanghai_weight':.30}),('parent_cash_low','base',.0975,{'parent_cash':.02}),('old_receipt_year2','base',.0975,{'old_ar_delay':1})]}
    conv={}
    for n in [300,600,900]:
        conv[str(n)]={}
        for key,r in [('low',.105),('high',.09)]:
            z=run(discount=r,years=n);last=z['rows'][-1];sales=last['electric_revenue']+last['other_revenue'];ss=last['subjects']
            conv[str(n)][key]={'pv':z['pv'],'tv5':z['tv5'],'cash_to_sales':sum(v['end']['cash'] for v in ss.values())/sales,'capital_to_sales':sum(v['end'].get('operating_capital',0) for v in ss.values())/sales,'d_to_sales':last['dividend']/sales,'state_per_sales':{name:{k:v/sales for k,v in d['end'].items() if k in ['cash','ur','reserve','capital','debt','payable','operating_capital','second_reserve']} for name,d in ss.items()}}
    # Independent ECONOMIC method: mature earnings power + 8-year franchise runoff.
    # Uses no production payout or its forecast operating path.
    epv=[]
    for r,margin,decay in [(.105,.30,.75),(.09,.33,.85)]:
        sustainable=2.50*margin+.32*.04-.025 # separate normalized sales/aftertax margins
        maintenance_excess=.035 # replacement exceeds depreciation
        f=sustainable-maintenance_excess
        # Franchise: eight independent annual additions, persist then decay, fully paid after reinvestment.
        franchise=sum((.04*(1-decay**t)/(1-decay))*(1-.03/.20)/(1+r)**t for t in range(1,9))
        mature=f/r
        netbridge=.73213186815-.78858193369-.24-.125001897+.07/(1+r)**2+.04/(1+r)**3 # necessary cash and authorized repurchase
        epv.append((mature+franchise+netbridge)/SHARES)
    output={'symbol':'CN:002270','units':'CNY billion; shares billion; per share CNY','source_cutoff':'2026-10-26T11:31:00Z','paths':paths,'convergence':conv,'tests':tests(),'method2_epv':epv}
    p=pathlib.Path(__file__).resolve().parent/'2026-Q3-output.json';raw=copy.deepcopy(output)
    schemas=[]
    def pack(d):
        keys=list(d)
        if keys not in schemas:schemas.append(keys)
        return [schemas.index(keys),*[pack(v) if isinstance(v,dict) else v for v in d.values()]]
    for path in output['paths'].values():
        for i,row in enumerate(path['rows']):
            if i:
                for name,detail in row['subjects'].items():
                    assert detail['begin']==raw['paths'][next(k for k,v in output['paths'].items() if v is path)]['rows'][i-1]['subjects'][name]['end']
                    detail['begin']={'reference':'previous_end'}
            if not any(row['new_debt_maturities'].values()):row['new_debt_maturities']={'reference':'empty_by_subject'}
            row['subjects']={name:pack(detail) for name,detail in row['subjects'].items()}
    output['subject_encoding']={'format':'first array item is schema index; subsequent values follow schema keys; nested state objects use same format','schemas':schemas}
    for name in ['base_low','base_high']:
        assert raw['paths'][name]['rows']==raw['paths']['base']['rows']
        output['paths'][name]['rows']={'reference':'base'}
    assert expand_output(output)==raw, 'lossless expansion must equal every original field'
    trajectory={name:path.pop('rows') for name,path in output['paths'].items()}
    encoding=output.pop('subject_encoding')
    compressed=gzip.compress(canonical_json(trajectory),compresslevel=9,mtime=0)
    output['annual_data']={'encoding':'deterministic-gzip-base64-of-lossless-column-trajectories-v1','gzip_mtime':0,'subject_encoding':encoding,'expanded_canonical_json':'UTF-8; ensure_ascii=False; sort_keys=True; separators=(comma,colon); no trailing newline','expanded_canonical_sha256':hashlib.sha256(canonical_json(raw)).hexdigest(),'expand_command':'python 2026-Q3.py --expand expanded.json','payload_base64':base64.b64encode(compressed).decode('ascii')}
    assert expand_output(output)==raw, 'gzip/base64 roundtrip must preserve every raw field'
    p.write_bytes(canonical_json(output))
    print(json.dumps({k:{x:v[x] for x in ['pv','tv5','first5','feasible']} for k,v in paths.items()},ensure_ascii=False));print('EPV',epv,'convergence',conv)
if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Recompute CN:002270 model, or expand downloaded complete annual data with SHA verification.')
    parser.add_argument('--expand',metavar='OUTPUT_JSON',help='Write full human-readable-key annual object as canonical JSON to this path; reads adjacent 2026-Q3-output.json.')
    args=parser.parse_args()
    if args.expand:
        source=pathlib.Path(__file__).resolve().parent/'2026-Q3-output.json'
        full=expand_output(json.loads(source.read_text()))
        dest=pathlib.Path(args.expand);dest.write_bytes(canonical_json(full))
        print(str(dest)+' SHA256 '+hashlib.sha256(dest.read_bytes()).hexdigest())
    else:main()

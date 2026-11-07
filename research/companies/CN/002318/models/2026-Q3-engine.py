#!/usr/bin/env python3
"""CN:002318. CNY billion, year-end cash flows. No network/input dependency.
Model years are rolling twelve-month budgets after 2026-10-26, not FY guidance.
All future single-entity inputs are research budgets, NOT disclosed precision.
"""
import json, math, copy, gzip, base64, sys, hashlib
from pathlib import Path
SHARES=.977170720
IDS=['P','A','E','D','C','H','U']
# Parent: individual distributable account. Subsidiaries: economic remittance-capacity
# budgets anchored to named entities, NOT certified individual legal balances.
# Domestic subsidiary disclosed net assets include unknown capital/surplus reserves:
# do not infer opening distributable profits by subtracting registered capital.
# Core excludes ALL old domestic subsidiary surplus and allows a finite 10% future
# appropriation budget until 50% of disclosed registered capital. This is an upper
# incremental retention allowance, not a claim that actual opening reserve is zero.
# Foreign nodes use no PRC reserve rule; local approval/solvency and 5% friction
# remain conditional economic assumptions. No notional EUR conversion is used
# to create statutory capacity. No equity issuance. Conditional proportional D capital return starts Y13 from excess cash only; registered nominal units decline, ownership/listed shares unchanged.
# Ordinary and excess distributions consume the same budget and available cash.
OPEN={
'P':dict(cash=2.85,locked=.428,debt=1.85,capital=.97717072,reserve=.48858536,retained=4.06127034,fixed=2.70,wc=2.25,own=1,tax=.15,limit=2.15),
'A':dict(cash=.25,locked=0,debt=.4,capital=.389198642,reserve=0.,retained=0.,fixed=.82,wc=.45,own=.685,tax=.15,limit=.65),
'E':dict(cash=.28,locked=0,debt=.4,capital=None,reserve=0,retained=-.10,fixed=.50,wc=.50,own=1,tax=.30,limit=.70),
'D':dict(cash=.033,locked=0,debt=0,capital=.030950195,reserve=0.,retained=0.,fixed=.04,wc=.04,own=1,tax=.25,limit=.03),
'C':dict(cash=.02,locked=0,debt=.016,capital=.0115,reserve=0.,retained=0.,fixed=.035,wc=.015,own=1,tax=.25,limit=.05),
'H':dict(cash=0,locked=0,debt=0,capital=None,reserve=0,retained=0,fixed=0,wc=0,own=1,tax=0,limit=0),
'U':dict(cash=0,locked=0,debt=0,capital=None,reserve=0,retained=0,fixed=0,wc=0,own=1,tax=0,limit=0)}
BASE={
'P':{'rev':[6.6,7.2,7.8,8.3,8.7],'m':[.08,.09,.10,.105,.11],'k':[5.05,5.15,5.35,5.55,5.75],'mature':.095,'fixedshare':.56},
'A':{'rev':[1.4,1.48,1.56,1.63,1.7],'m':[.03,.035,.04,.045,.05],'k':[1.31,1.35,1.39,1.43,1.47],'mature':.045,'fixedshare':.65},
'E':{'rev':[1.3,1.5,1.65,1.8,1.9],'m':[0,.03,.05,.06,.07],'k':[1.08,1.12,1.16,1.20,1.24],'mature':.055,'fixedshare':.50},
'D':{'rev':[.20,.21,.22,.23,.24],'m':[.01,.015,.02,.025,.03],'k':[.082,.084,.086,.088,.090],'mature':.025,'fixedshare':.50},
'C':{'rev':[1.3,1.36,1.42,1.48,1.54],'m':[.003,.004,.005,.006,.007],'k':[.052,.054,.056,.058,.060],'mature':.006,'fixedshare':.70}}
SCENARIOS={
'core_low':dict(r=.105,margin=-.005,g=.02,growth=.03,kind='base'),
'holder_low':dict(r=.105,margin=-.005,g=.02,growth=.03,kind='base',freeze_first5=True),
'holder_high':dict(r=.095,margin=.005,g=.02,growth=.03,kind='base',freeze_first5=True),
'base':dict(r=.10,margin=0,g=.02,growth=.03,kind='base'),
'core_high':dict(r=.095,margin=.005,g=.02,growth=.03,kind='base'),
'cyclical':dict(r=.10,margin=0,g=.02,growth=.03,kind='cycle'),
'structural':dict(r=.11,margin=-.025,g=0,growth=0,kind='structure'),
'structural_dividend_only':dict(r=.11,margin=-.025,g=0,growth=0,kind='structure',capital_recovery=False),
'structural_recovery_delay20':dict(r=.11,margin=-.025,g=0,growth=0,kind='structure',recovery_start=20),
'structural_recovery_fee10':dict(r=.11,margin=-.025,g=0,growth=0,kind='structure',recovery_fee=.10),
'structural_zero_tax_basis':dict(r=.11,margin=-.025,g=0,growth=0,kind='structure',recovery_tax_basis_ratio=0.),
'upside':dict(r=.095,margin=.01,g=.025,growth=.04,kind='up'),
'margin_minus_1pct':dict(r=.10,margin=-.01,g=.02,growth=.03,kind='base'),
'capital_plus_15pct':dict(r=.10,margin=0,g=.02,growth=.03,kind='base',capital=1.15),
'upstream_delay':dict(r=.10,margin=0,g=.02,growth=.03,kind='base',pay=.3),
'locked_longer':dict(r=.10,margin=0,g=.02,growth=.03,kind='base',unlock=5),
'parent_cash_shift':dict(r=.10,margin=0,g=.02,growth=.03,kind='base',cashshift=.3),
'foreign_legal_loss':dict(r=.10,margin=0,g=.02,growth=.03,kind='base',foreignloss=.3),
'domestic_prior_loss_100m':dict(r=.10,margin=0,g=.02,growth=.03,kind='base',domestic_loss=.1),
'domestic_reserves_already_full':dict(r=.10,margin=0,g=.02,growth=.03,kind='base',domestic_full_reserve=True),
'no_refinance_zero_D':dict(r=.10,margin=0,g=.02,growth=.03,kind='cycle',no_refi=True,zero_D=True)}
def target(e,y,c):
    b=BASE[e];i=min(y,5)-1;rev=b['rev'][i];m=b['m'][i]+(0 if c.get('freeze_first5') and y<=5 else c['margin'])*(.1 if e=='C' else .5 if e in ['A','D'] else 1);k=b['k'][i]
    if y>5:
        scale=(1+c['growth'])**min(y-5,5)*(1+c['g'])**max(y-10,0)
        rev*=scale;k*=scale;m+=(b['mature']-b['m'][4])*min((y-5)/10,1)
    if c['kind']=='cycle':
        factor=[.82,.90,.96,1,1][i] if y<=5 else 1
        rev*=factor;m-=([.045,.025,.01,0,0][i] if y<=5 else 0)*(.1 if e=='C' else .5 if e in ['A','D'] else 1)
        k+=([.12,.15,.08,0,0][i] if y<=5 else 0)*(1 if e=='P' else .2)
    if c['kind']=='structure':
        rev*=.85; m-=.01 if e=='E' else 0
        # weaker turnover, no perpetual mean reversion: mature margins stay lower
        k*=1.08
    if c['kind']=='up': rev*=1.08; k*=1.05
    k*=c.get('capital',1)
    return rev,m,k*b['fixedshare'],k*(1-b['fixedshare'])
def legal_step(retained,reserve,registered,net,domestic):
    # only positive profit AFTER covering opening accumulated losses supports appropriation
    assess=max(0,net-max(0,-retained))
    appropriation=min(max(0,registered*.5-reserve),assess*.1) if domestic else 0
    return retained+net-appropriation,reserve+appropriation,appropriation

def capital_return_budget(available,registered,parent_investment_cost,requested,ownership=1.,friction=.02,parent_tax=.25,tax_basis_ratio=1.):
 # Partial proportional capital reduction of a named company, not an ordinary dividend.
 # Cost is parent's carrying cost of its interest; ownership unchanged when all owners reduce pro rata.
 gross=min(max(available,0.),max(requested,0.),max(registered,0.))
 allocated_cost=parent_investment_cost*gross/registered if registered else 0.
 parent_gross=gross*ownership;fee=parent_gross*friction;proceeds=parent_gross-fee
 disposal_profit=proceeds-allocated_cost
 # Tax basis is NOT the disclosed accounting carrying value. Core uses a conditional
 # paid-capital budget equal to registered capital; zero-basis sensitivity taxes all
 # net proceeds and assumes no dividend exemption. No loss produces an immediate refund.
 allocated_tax_basis=gross*ownership*tax_basis_ratio
 tax=max(proceeds-allocated_tax_basis,0.)*parent_tax
 return {'gross_capital_return':gross,'allocated_tax_basis_budget':allocated_tax_basis,'tax_basis_ratio_budget':tax_basis_ratio,'parent_cash':proceeds-tax,'parent_investment_cost_released':allocated_cost,'parent_profit':disposal_profit-tax,'parent_cash_tax':tax,'friction_cash':fee,'minority_cash':gross*(1-ownership),'registered_after':registered-gross,'parent_investment_cost_after':parent_investment_cost-allocated_cost,'ownership_after':ownership,'listed_shares_change':0.,'sub_capital_units_remaining_ratio':(registered-gross)/registered if registered else 0.}

def run(c,n=240,opening=None,overrides=None):
    ss=copy.deepcopy(OPEN if opening is None else opening)
    if c.get('cashshift'):
        ss['P']['cash']-=c['cashshift'];ss['E']['cash']+=c['cashshift']
    if c.get('foreignloss'):ss['E']['retained']-=c['foreignloss']
    if c.get('domestic_loss'):
        for e in ('A','D','C'):ss[e]['retained']-=c['domestic_loss']*{'A':.8,'D':.1,'C':.1}[e]
    if c.get('domestic_full_reserve'):
        for e in ('A','D','C'):ss[e]['reserve']=ss[e]['capital']/2
    for s in ss.values():s.update(receivable=0,payable=0)
    years=[];pv=tv=0.;failed=None;d_investment_cost=.04251307794
    for y in range(1,n+1):
        rows={};incoming={e:dict(declared=0,received=0,capital_profit=0,capital_received=0) for e in IDS};total_minority=0;capital_leakage=0
        for e in ['A','E','D','C','H','U','P']:
            s=ss[e];o=s.copy();op=e in BASE
            rev,m,f,w=target(e,y,c) if op else (0,0,0,0)
            if overrides is not None: rev,m,f,w=overrides.get(e,(0,0,o['fixed'],o['wc']))
            dep=o['fixed']*.075;capex=dep+f-o['fixed'];dw=w-o['wc']
            # Negative capex is actual sale at book value; no artificial depreciation/cash double count.
            ebit=rev*m;income=o['cash']*.015;interest=o['debt']*.03
            pre=ebit+income-interest;tax=max(0,pre)*s['tax'];noncash_awards=.165 if e=='P' and y<=3 and overrides is None else 0;net=pre-tax-noncash_awards
            inc=incoming[e];legal_income=net+inc['declared']+inc['capital_profit']
            u,res,appropriation=legal_step(o['retained'],o['reserve'],o['capital'],legal_income,e in ['P','A','D','C'])
            cfo=net+noncash_awards+dep-dw
            extra=(.2215+.0701+.10+.113127127) if e=='P' and y==1 and overrides is None else 0
            cash=o['cash']+cfo-capex-extra+inc['received']
            required=(rev*.07 if e=='P' else rev*(.01 if e=='C' else .05)) if op else 0
            locked=o['locked']
            # deposit pledge released only after the corresponding scheduled debt repayment
            repayment=min(o['debt'],max(0,cash-locked-required-o['payable'])*.65)
            if c.get('no_refi'):repayment=o['debt']
            cash-=repayment;debt=o['debt']-repayment
            if y>=c.get('unlock',2) and OPEN[e]['debt']-debt>=min(.428,o['locked']):locked=0
            if debt<1e-8:locked=0
            borrow=min(max(0,required+locked+o['payable']-cash),max(0,s['limit']-debt)) if not c.get('no_refi') else 0
            cash+=borrow;debt+=borrow
            oldpay=min(o['payable'],max(0,cash-locked-required));cash-=oldpay
            room=max(0,cash-locked-required)
            if e=='P':
                requested=([.25,.35,.45,.55,.60][y-1]*SHARES if y<=5 else max(0,net+inc['declared']))
                if y>=9:requested=room
                if c.get('zero_D'):requested=0
                d=min(requested,max(0,u),room);paid=d;new_ar=0
            else:
                requested=max(0,net+inc['declared'])*(.7 if op else 1)
                if y>=9:requested=room
                # declare only cash-supported dividends, with remaining cash segregated for next-year payout
                d=min(requested,max(0,u),room)
                fraction=c.get('pay',.8) if op else 1
                paid=d*fraction;new_ar=d-paid
            cash-=paid
            recovery=capital_return_budget(0,0,0,0)
            if e=='D' and c.get('capital_recovery',True) and y>=c.get('recovery_start',13) and (y-c.get('recovery_start',13))%5==0:
                # Exclude locked/required cash and both old and newly declared dividend payables.
                surplus=max(0,cash-locked-required-(o['payable']-oldpay+new_ar))
                recovery=capital_return_budget(surplus,s['capital'],d_investment_cost,surplus,ownership=s['own'],friction=c.get('recovery_fee',.02),parent_tax=ss['P']['tax'],tax_basis_ratio=c.get('recovery_tax_basis_ratio',1.))
                cash-=recovery['gross_capital_return'];s['capital']=recovery['registered_after'];d_investment_cost=recovery['parent_investment_cost_after']
                incoming['P']['received']+=recovery['parent_cash'];incoming['P']['capital_received']+=recovery['parent_cash'];incoming['P']['capital_profit']+=recovery['parent_profit']
                capital_leakage+=recovery['friction_cash']+recovery['parent_cash_tax']+recovery['minority_cash']
            s.update(cash=cash,locked=locked,debt=debt,reserve=res,retained=u-d,fixed=f,wc=w,payable=o['payable']-oldpay+new_ar)
            # Payable provision is unavailable for any subsequent dividends/financing repayment.
            # Cash minimum is checked INCLUDING existing unpaid dividend obligations.
            gap=max(0,required+locked+s['payable']-cash)
            if gap>1e-8 and failed is None:failed={'year':y,'entity':e,'gap_bn':gap,'zero_dividend':d==0}
            dest={'A':'P','E':'H','D':'P','C':'P','H':'U','U':'P'}.get(e)
            received=oldpay+paid
            leakage=.05 if e=='U' else 0
            if dest:
                share=s['own'];incoming[dest]['declared']+=d*share*(1-leakage)
                incoming[dest]['received']+=received*share*(1-leakage)
                total_minority+=received*(1-share)
                ss[dest]['receivable']+=d*share*(1-leakage)-received*share*(1-leakage)
            s['retained']=u-d
            assert debt<=s['limit']+1e-8
            assert d<=max(0,u)+1e-8 and paid<=room+1e-8
            assert s['retained']>=-1e-8 or d==0
            assert abs(cash-(o['cash']+cfo-capex-extra+inc['received']-repayment+borrow-oldpay-paid-recovery['gross_capital_return']))<1e-7*max(1,abs(cash))
            rows[e]=dict(capital_recovery=recovery,capital_return_received=inc['capital_received'],capital_disposal_profit=inc['capital_profit'],revenue=rev,ebit_margin=m,ebit=ebit,deposit_income=income,interest=interest,tax=tax,net_income=net,upstream_declared=inc['declared'],upstream_received=inc['received'],legal_income=legal_income,noncash_awards=noncash_awards,opening_retained=o['retained'],reserve_add=appropriation,reserve=res,registered_capital=s['capital'],distribution_capacity_budget_before_D=u,account_scope=('parent_forecast_from_individual_balance' if e=='P' else 'economic_remittance_capacity_budget'),actual_individual_statutory_reserve=None,actual_individual_legal_retained=None,reserve_state_kind=('registered_half_equivalent_full_status_not_disclosed_amount' if e=='P' else 'bounded_incremental_retention_budget_not_actual_reserve'),registered_capital_currency=('CNY' if e in ['P','A','D','C'] else 'EUR'),registered_capital_native=(25000 if e in ['E','H','U'] else s['capital']*1e9),declared_D=d,current_D_paid=paid,old_D_paid=oldpay,D_payable=s['payable'],D_receivable=s['receivable'],retained=s['retained'],cash_open=o['cash'],cash_end=cash,locked_end=locked,required_cash=required,fixed_open=o['fixed'],fixed_end=f,wc_open=o['wc'],wc_end=w,DA=dep,capex=capex,delta_wc=dw,CFO=cfo,old_obligations_and_buyback=extra,debt_open=o['debt'],gross_maturity=o['debt'],gross_rollover=o['debt']-repayment,repayment=repayment,new_debt=borrow,debt_end=debt,debt_ceiling=s['limit'],funding_gap=gap)
        group_before=sum(rows[e]['cash_open'] for e in IDS)
        group_after=sum(rows[e]['cash_end'] for e in IDS)
        external_flow=sum(rows[e]['CFO']-rows[e]['capex']-rows[e]['old_obligations_and_buyback']-rows[e]['repayment']+rows[e]['new_debt'] for e in IDS)-rows['P']['current_D_paid']-total_minority-.05*(rows['U']['current_D_paid']+rows['U']['old_D_paid'])-capital_leakage
        assert abs(group_after-group_before-external_flow)<1e-7*max(1,group_after)
        dist=rows['P']['current_D_paid']/SHARES
        np=sum(rows[e]['net_income']*ss[e]['own'] for e in BASE)-rows['U']['declared_D']*.05-capital_leakage
        consolidated=sum(rows[e]['revenue'] for e in BASE)-rows['C']['revenue']-.55*rows['A']['revenue']
        yr={'year':y,'shares_bn':SHARES,'entities':rows,'DPS':dist,'attributable_profit_bn':np,'group_revenue_proxy_bn':consolidated,'minority_cash_bn':total_minority,'cash_bn':sum(s['cash'] for s in ss.values()),'debt_bn':sum(s['debt'] for s in ss.values())}
        years.append(yr);pv+=dist/(1+c['r'])**y
        if y>5:tv+=dist/(1+c['r'])**(y-5)
        if failed:break
    return {'feasible':failed is None,'failure':failed,'PV':pv if failed is None else None,'TV5':tv if failed is None else None,'DPS5':[z['DPS'] for z in years[:5]],'years':years}
def pack(result):
    r=copy.deepcopy(result); yrs=r.pop('years')
    raw=json.dumps(yrs,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    r['annual_trace_sha256']=hashlib.sha256(raw).hexdigest()
    r['annual_trace_encoding']='gzip-mtime0-base64-json-utf8'
    r['annual_trace_years']=len(yrs)
    r['annual_trace_schema']={'unit':'CNY billion except native currency capital and per-share figures','content':'Complete annual records including every entity and variable registered capital; no fields omitted','decode':'base64 decode, gzip decompress, UTF-8 JSON array; python model --expand output.json'}
    r['annual_trace_gzip_base64']=base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode('ascii')
    return r

def expand(p):
    p=copy.deepcopy(p)
    if 'annual_trace_gzip_base64' in p:
        raw=p.pop('annual_trace_gzip_base64')
        p.pop('annual_trace_encoding');p.pop('annual_trace_years');p.pop('annual_trace_schema')
        decoded=gzip.decompress(base64.b64decode(raw))
        assert hashlib.sha256(decoded).hexdigest()==p.pop('annual_trace_sha256'), 'annual trace SHA256 mismatch'
        p['years']=json.loads(decoded.decode('utf-8'))
        return p
    names=p.pop('annual_columns');vals=p.pop('annual_values');cols=p.pop('entity_columns');ev=p.pop('entity_values')
    p['years']=[dict(zip(names,v)) for v in vals]
    for i,z in enumerate(p['years']):z['entities']={e:dict(zip(cols,ev[e][i])) for e in IDS}
    return p

def boundary():
    # Genuine production-chain test: all operating activity zero, parent starts cash 10 and U=1.
    o=copy.deepcopy(OPEN)
    for e,s in o.items():s.update(cash=0,locked=0,debt=0,capital=0,reserve=0,retained=0,fixed=0,wc=0,limit=0)
    o['P'].update(cash=10,retained=1,tax=.15)
    x=run(SCENARIOS['base'],1,opening=o,overrides={})['years'][0]['entities']['P']
    # interest .15 tax .0225, NP .1275; requested .25 * .97717072
    expected_D=.25*.97717072
    assert abs(x['cash_end']-(10+.1275-expected_D))<1e-12
    assert abs(x['retained']-(1+.1275-expected_D))<1e-12
    # Opening loss .5, net .6: reserve .01 not .06.
    assert legal_step(-.5,0,1,.6,True)==(.08999999999999998,.009999999999999998,.009999999999999998)
    o2=copy.deepcopy(o);o2['P'].update(cash=1,debt=.4,fixed=1,wc=.5)
    real=run(SCENARIOS['base'],1,opening=o2,overrides={'P':(2,.1,1.2,.6)})['years'][0]['entities']['P']
    assert abs(real['capex']-.275)<1e-12 and abs(real['repayment']-.4)<1e-12
    assert abs(real['cash_end']-(1+.17255-.2-.1-.4-expected_D))<1e-12
    return {'capital_debt_boundary':real,'cash_expected':10+.1275-expected_D,'cash_actual':x['cash_end'],'reserve_after_loss':legal_step(-.5,0,1,.6,True),'pass':True}
def secondary():
    # independent mature product volumes (kt), prices CNY thousand/t, EBIT margins;
    # no use of BASE revenues/margins, no dividend algebra.
    seg=[('seamless',65,62,.15),('welded',62,29,.06),('composite',24,65,.07),('fittings',10,65,.14),('other_alloy',1,550,.035)]
    ebit=sum(q*p/1000*m for _,q,p,m in seg)
    # current financial bridge: gross 3.433 minus all financing debt 2.666,
    # old obligations .3916, planned minimum remaining repurchase .113127127;
    # 31.5% minority for standalone alloy EBIT .045, valued at same multiple.
    bridge=3.433-2.666-.3916-.113127127
    vals=[(ebit*k-.045*k*.315+bridge)/SHARES for k in (10,12)]
    return {'segments':seg,'EBIT_bn':ebit,'EV_EBIT':[10,12],'bridge_bn':bridge,'PV_range':vals,'note':'current normalized capacity earnings cross-check, independent volume/mix; embeds maintenance and normal capex via EBIT and industrial multiples, weaker than explicit payout method'}
def main():
    out={'symbol':'CN:002318','units':'CNY billion except per share','shares_bn':SHARES,'opening_budget':OPEN,'account_schema':{'monetary_unit':'CNY billion unless native capital explicitly labelled','reserve':'Forecast state only: parent registered/2 equivalent of documented full status, subsidiaries accumulated bounded retention allowance; not actual statutory reserve','retained':'Parent future distributable-profit forecast; subsidiary economic remittance-capacity accumulator, not disclosed individual legal balance','foreign_capital':'CNY value null, EUR25000 native disclosure in rows; no PRC rule or placeholder FX','capital_return':'Only named 湖州乾诚不锈钢管制造有限公司 conditional proportional reduction; H1 registered30.950195m vs mother carrying42.51307794m. Actual paid/tax basis unknown; registered amount used as paid-capital/tax budget with zero-basis sensitivity. Excess excludes required/locked/payables; 2% costs and no loss refund. Ordinary dividend and capital return distinct, nominal units decline, ownership/listed shares unchanged','sources':'entity-audit.json has actual disclosures, null unknowns and exact table/page identity'},'business_budget':BASE,'scenarios':{},'boundary':boundary(),'secondary':secondary(),'convergence':{}}
    for name,c in SCENARIOS.items():
        r=run(c);p=pack(r);assert expand(p)==r
        out['scenarios'][name]={'assumptions':c,**p}
    for name in ['core_low','core_high','holder_low','holder_high']:
        out['convergence'][name]={str(n):{k:run(SCENARIOS[name],n)[k] for k in ['PV','TV5']} for n in (160,240,320)}
    for name in ['holder_low','holder_high']:
        h=expand({k:v for k,v in out['scenarios'][name].items() if k!='assumptions'})
        b=expand({k:v for k,v in out['scenarios']['base'].items() if k!='assumptions'})
        assert h['years'][:5]==b['years'][:5]
    out['holder_first_five_full_state_equal']=True
    out['lossless_expand_verified']=True
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')))
    print(json.dumps({k:{j:v[j] for j in ['feasible','failure','PV','TV5','DPS5']} for k,v in out['scenarios'].items()},indent=2))
if __name__=='__main__':
    if '--expand' in sys.argv:
        i=sys.argv.index('--expand');source=Path(sys.argv[i+1]) if len(sys.argv)>i+1 else Path(__file__).with_name('2026-Q3-output.json')
        data=json.loads(source.read_text())
        data['scenarios']={k:expand(v) for k,v in data['scenarios'].items()}
        print(json.dumps(data,ensure_ascii=False,indent=2))
    else:main()

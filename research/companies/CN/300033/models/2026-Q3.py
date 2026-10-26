#!/usr/bin/env python3
"""CN300033. CNY billion, shares billion. Standard library only; no live prices.
Individual company allocations are distribution budgets, not audited segment forecasts.
Annual periods end 2027-10-26 onward; far years are numerical integration only.
"""
import json, copy, math
from pathlib import Path
NAMES=['listed_parent','Hexin_Software','Intelligent_Technology','Zhifu_Software','Data_Development','Network_Technology','Hong_Kong','Hexin_downstream_distribution_budget']
SHARES=.75264
ASOF='2026-10-26T00:00:00+08:00'
PARAM={
 'revenue':[7.8,8.346,8.84676,9.3775656,9.84644388], 'margin':[.48]*5,
 'g_after5':.04,'g_long':.02,'margin_long':.42,'tax':.15,'discount':.10,
 'cash':[2.4,.325,1.45,.30,2.4,2.36567701089,.918,.325],
 'retained':[2.7,.35,.9,.2,1.2,1.1,.5,.35],
 'capital':[.75264,.03,.30,.01,.20766,.055,.4007804,.01],
 'reserve':[.36081535125,.015,.15,.005,.10383,.0275,.2003902,0.],
 'weights':[0.,.115,.27,.22,.16,.12,0.,.115],
 'parent_cost':.16,'cash_yield':.012,'loan_rate':.03,'external_rate':.05,'external_limit':.5,
 'liquidity_ratio':.12,'contract_ratio':3.09069063185/7.8,'working_ratio':.01,
 'capital_ratio':.20,'initial_fixed':1.70810491672,'initial_working':.078,
 'construction':[.18,.11,.06,0,0], 'normal_payout':.80,'upstream_payout':.80,'release_fraction':.20,
 'release_start':6,'upstream_lag':0,'parent_extra_cost':0.,'terminal_mode':'base',
 'receiver':[None,0,0,0,0,0,0,1], 'upstream_order':[7,1,2,3,4,5,6],
 'opening_distribution':0.,
 'notes':'Point cash allocation and subsidiary statutory retained are research budgets. Zero-reserve and delayed upstream cases bracket attribution uncertainty.'}

def legal_roll(retained,reserve,capital,profit):
    # Prior losses consumed first; capital injection changes the reserve ceiling through capital.
    old=retained; eligible=max(profit-max(-old,0),0)
    add=min(.10*eligible,max(.50*capital-reserve,0))
    return retained+profit-add,reserve+add,add

def annual_inputs(p,t,previous_revenue):
    if t<=5: rev=p['revenue'][t-1];margin=p['margin'][t-1]
    else:
        f=min((t-5)/10,1);g=p['g_after5']*(1-f)+p['g_long']*f
        rev=previous_revenue*(1+g)
        margin=p['margin'][-1]*(1-f)+p['margin_long']*f
    return rev,margin

def run(p,years=300,initial=None,start=1):
    p=copy.deepcopy(p);m=len(NAMES);w=p['weights']; rows=[]
    s=copy.deepcopy(initial) if initial else {'cash':p['cash'][:],'retained':p['retained'][:], 'reserve':p['reserve'][:], 'capital':p['capital'][:], 'loans':[0.]*m,'external':[0.]*m,'payable':[0.]*m,'rev':7.8,'fixed':p['initial_fixed'],'working':p['initial_working'],'contract':3.09069063185}
    for t in range(start,start+years):
        opening=copy.deepcopy(s);rev,margin=annual_inputs(p,t,s['rev'])
        operating=rev*margin*(1-p['tax']);parent_cost=p['parent_cost']*(rev/7.8)
        own=[-parent_cost-p['parent_extra_cost']]+[(operating+parent_cost)*w[i] for i in range(1,m)]
        interest=[x*p['cash_yield'] for x in s['cash']]
        financing=[s['external'][i]*p['external_rate'] for i in range(m)]
        interinterest=[0.]+[s['loans'][i]*p['loan_rate'] for i in range(1,m)];interinterest[0]=-sum(interinterest)
        profits=[own[i]+interest[i]-financing[i]-interinterest[i] for i in range(m)]
        fixed_target=p['initial_fixed']+p['capital_ratio']*(rev-7.8)+sum(p['construction'][:min(t,5)])
        fixed_target=max(fixed_target,.6);growth_capex=fixed_target-s['fixed']
        depreciation=rev*.02;capex=depreciation+growth_capex
        # Asset shrinkage requires realised disposal; limit disposal to depreciation, avoiding fictional sale proceeds.
        if capex<0: capex=0.;growth_capex=-depreciation;fixed_target=s['fixed']+growth_capex
        working=rev*p['working_ratio'];dworking=working-s['working']
        contract=rev*p['contract_ratio'];dcontract=contract-s['contract']
        reinvest=growth_capex+dworking
        cashflow=[profits[0]]+[profits[i]-reinvest*w[i]+dcontract*w[i] for i in range(1,m)]
        s['cash']=[s['cash'][i]+cashflow[i] for i in range(m)]
        # Prior declared dividends settle as cash only: no repeated income/profit at parent.
        settlements=[0.]*m
        for i in range(1,m):
            settlements[i]=s['payable'][i];s['cash'][i]-=settlements[i];s['cash'][p['receiver'][i]]+=settlements[i];s['payable'][i]=0.
        floors=[.3]+[(rev*p['liquidity_ratio']+contract)*w[i] for i in range(1,m)]
        newloans=[0.]*m;loanrepay=[0.]*m;external_new=[0.]*m;external_repaid=[0.]*m
        # Explicit shareholder loans, not anonymous liquidity. No assumed new equity or infinite finance.
        for i in range(1,m):
            need=max(floors[i]-s['cash'][i],0);lend=min(need,max(s['cash'][0]-floors[0],0))
            s['cash'][0]-=lend;s['cash'][i]+=lend;s['loans'][i]+=lend;newloans[i]=lend
        for i in range(1,m):
            need=max(floors[i]-s['cash'][i],0);borrow=min(need,max(p['external_limit']-sum(s['external']),0))
            s['cash'][i]+=borrow;s['external'][i]+=borrow;external_new[i]=borrow
            if s['cash'][i]<floors[i]-1e-8: raise ValueError('Unfunded even with zero dividends: '+NAMES[i]+' year '+str(t))
        for i in range(m):
            repay=min(max(s['cash'][i]-floors[i],0),s['external'][i]);s['cash'][i]-=repay;s['external'][i]-=repay;external_repaid[i]=repay
        for i in range(1,m):
            repay=min(max(s['cash'][i]-floors[i],0),s['loans'][i]);s['cash'][i]-=repay;s['cash'][0]+=repay;s['loans'][i]-=repay;loanrepay[i]=repay
        appropriations=[0.]*m;declared=[0.]*m;paid=[0.]*m;normal=[0.]*m;extra=[0.]*m
        statutory_profit=profits[:]
        for i in p['upstream_order']:
            s['retained'][i],s['reserve'][i],appropriations[i]=legal_roll(s['retained'][i],s['reserve'][i],s['capital'][i],statutory_profit[i])
            free=max(s['cash'][i]-floors[i],0)
            normal[i]=min(max(statutory_profit[i],0)*p['upstream_payout'],max(s['retained'][i],0),free)
            # Ordinary payment consumes both cash AND statutory profit before releasing old capital.
            extra[i]=min(max(s['retained'][i]-normal[i],0),max(free-normal[i],0)*p['release_fraction']) if t>=p['release_start'] else 0.
            declared[i]=normal[i]+extra[i];s['retained'][i]-=declared[i]
            statutory_profit[p['receiver'][i]]+=declared[i]
            if p['upstream_lag']:
                s['payable'][i]=declared[i]
            else:
                paid[i]=declared[i];s['cash'][i]-=paid[i];s['cash'][p['receiver'][i]]+=paid[i]
        need=max(floors[0]-s['cash'][0],0)
        borrow=min(need,max(p['external_limit']-sum(s['external']),0))
        s['cash'][0]+=borrow;s['external'][0]+=borrow;external_new[0]=borrow
        if s['cash'][0]<floors[0]-1e-8: raise ValueError('Unfunded parent even after legal upstream, year '+str(t))
        parent_profit=statutory_profit[0]
        s['retained'][0],s['reserve'][0],appropriations[0]=legal_roll(s['retained'][0],s['reserve'][0],s['capital'][0],parent_profit)
        group_profit=sum(profits)
        free=max(s['cash'][0]-floors[0],0)
        normal[0]=min(max(group_profit,0)*p['normal_payout'],max(s['retained'][0],0),free)
        extra[0]=min(max(s['retained'][0]-normal[0],0),max(free-normal[0],0)*p['release_fraction']) if t>=p['release_start'] else 0.
        dividend=normal[0]+extra[0];s['cash'][0]-=dividend;s['retained'][0]-=dividend
        s.update(rev=rev,fixed=fixed_target,working=working,contract=contract)
        assert min(s['cash'])>=-1e-8
        assert max(abs(s['cash'][i]-floors[i]) if s['cash'][i]<floors[i]-1e-7 else 0 for i in range(m))<1e-6
        cash_expected=sum(opening['cash'])+sum(cashflow)+sum(external_new)-sum(external_repaid)-dividend
        assert abs(sum(s['cash'])-cash_expected)<1e-5*max(1,sum(s['cash']))
        assert abs(sum(interinterest))<1e-10
        rows.append({'year':t,'period_end':str(2026+t)+'-10-26','revenue':rev,'ebit_margin':margin,'operating_nopat':operating,'financial_income':sum(interest),'external_interest':sum(financing),'group_profit':group_profit,'own_statutory_profit':profits,'total_entity_statutory_profit':statutory_profit,'parent_statutory_profit':parent_profit,'depreciation':depreciation,'capex':capex,'delta_working':dworking,'delta_contract':dcontract,'cashflow_before_financing':cashflow,'cash_floor':floors,'normal_distribution':normal,'extra_release':extra,'subs_declared':declared,'subs_paid_current':paid,'subs_prior_settlement':settlements,'reserve_add':appropriations,'new_shareholder_loans':newloans,'shareholder_loan_repayment':loanrepay,'external_new':external_new,'external_repaid':external_repaid,'equity_injection':[0.]*m,'dividend':dividend,'dividend_per_share':dividend/SHARES,'state':copy.deepcopy(s)})
    return rows

def valuation(rows,r,opening_distribution=0.):
    pv=(opening_distribution+sum(x['dividend']/(1+r)**x['year'] for x in rows))/SHARES
    d5=sum(x['dividend']/(1+r)**x['year'] for x in rows if x['year']<=5)/SHARES
    tv=sum(x['dividend']/(1+r)**(x['year']-5) for x in rows if x['year']>5)/SHARES
    return {'value':pv,'opening_distribution':opening_distribution,'pv_first5':d5,'tv5':tv,'tv5_pv_share':1-d5/pv,'last_cash':rows[-1]['state']['cash'],'last_retained':rows[-1]['state']['retained'],'last_external':rows[-1]['state']['external']}

def cases():
    low=copy.deepcopy(PARAM);low.update(discount=.105,g_after5=.03,g_long=.015,margin_long=.40)
    high=copy.deepcopy(PARAM);high.update(discount=.095,g_after5=.045,g_long=.025,margin_long=.44)
    cyc=copy.deepcopy(PARAM);cyc.update(revenue=[6.0,6.3,7.1,8.1,9.0],margin=[.32,.34,.40,.44,.46],g_after5=.04,margin_long=.42)
    structural=copy.deepcopy(PARAM);structural.update(revenue=[6.8,6.5,6.3,6.2,6.2],margin=[.35,.30,.27,.26,.26],g_after5=0.,g_long=0.,margin_long=.24,liquidity_ratio=.16)
    bull=copy.deepcopy(PARAM);bull.update(revenue=[8.5,9.52,10.5672,11.62392,12.6700728],margin=[.50,.51,.51,.50,.50],g_after5=.05,g_long=.025,margin_long=.45)
    zero=copy.deepcopy(PARAM);zero['retained']=[2.7,0,0,0,0,0,0,0]
    lag=copy.deepcopy(PARAM);lag['upstream_lag']=1;lag['release_start']=11
    stuck=copy.deepcopy(PARAM);stuck['upstream_payout']=.4;stuck['release_start']=11
    m=copy.deepcopy(PARAM);m['margin']=[x-.05 for x in m['margin']];m['margin_long']-=.05
    g=copy.deepcopy(PARAM);g['g_after5']=.02;g['g_long']=0.
    y=copy.deepcopy(PARAM);y['cash_yield']=0.
    heavy=copy.deepcopy(PARAM);heavy['capital_ratio']=.4;heavy['construction']=[.36,.22,.12,0,0]
    down0=copy.deepcopy(PARAM);down0['weights'][1]=.23;down0['weights'][7]=0.
    down100=copy.deepcopy(PARAM);down100['weights'][1]=0.;down100['weights'][7]=.23
    downold0=copy.deepcopy(PARAM);downold0['retained'][1]=.7;downold0['retained'][7]=0.
    downoldall=copy.deepcopy(PARAM);downoldall['retained'][1]=0.;downoldall['retained'][7]=.7
    offshore=copy.deepcopy(PARAM);offshore['opening_distribution']=offshore['cash'][6];offshore['retained'][0]-=offshore['opening_distribution']
    for field in ('cash','retained','reserve','capital'):offshore[field][6]=0.
    offshore['opening_event']='Conditional immediate solvent liquidation of offshore cash budget; all proceeds paid through parent using existing parent statutory retained; no tax/fees, upper bound only. Initial investment capital removed, not operating income.'
    return {'downstream_share0':down0,'downstream_share100':down100,'downstream_old_retained0':downold0,'downstream_old_retained_all':downoldall,'offshore_immediate_recovery_upper_bound':offshore,'base':PARAM,'core_low':low,'core_high':high,'cyclical_weak':cyc,'structural_adverse':structural,'optimistic':bull,'zero_sub_opening_retained':zero,'one_year_upstream_lag_release11':lag,'subs_upstream40_release11':stuck,'margin_minus5pp_fromY1':m,'growth_lower_fromY6':g,'zero_financial_yield_fromY1':y,'capital_double_fromY1':heavy}

def tests():
    # Exact hand-computable special case goes through the production engine.
    p=copy.deepcopy(PARAM);p.update(revenue=[10]*5,margin=[.1]*5,tax=0.,parent_cost=0.,cash_yield=0.,liquidity_ratio=0.,contract_ratio=0.,working_ratio=0.,capital_ratio=0.,construction=[0]*5,normal_payout=1.,upstream_payout=1.,release_start=999,weights=[0,1,0,0,0,0,0,0],cash=[.3,3.09069063185,0,0,0,0,0,0],retained=[0]*8,capital=[0]*8,reserve=[0]*8,initial_working=0.,external_limit=0.)
    # Initial contract is a cash liability: run from explicit zero-liability opening.
    s={'cash':[.3,0,0,0,0,0,0,0],'retained':[0]*8,'reserve':[0]*8,'capital':[0]*8,'loans':[0]*8,'external':[0]*8,'payable':[0]*8,'rev':10.,'fixed':p['initial_fixed'],'working':0.,'contract':0.}
    rr=run(p,years=1,initial=s);assert abs(rr[0]['dividend']-1)<1e-9
    assert abs(valuation(rr,.1)['value']-1/1.1/SHARES)<1e-9
    nested=copy.deepcopy(p);nested['weights']=[0,0,0,0,0,0,0,1]
    nr=run(nested,years=1,initial=s)[0]
    assert abs(nr['dividend']-1)<1e-9 and abs(nr['group_profit']-1)<1e-9
    assert nr['subs_declared'][7]==1 and nr['subs_declared'][1]==1
    assert legal_roll(-2,0,10,1)==(-1,0,0)
    assert legal_roll(-1,0,10,2)==(.9,.1,.1)
    assert abs(legal_roll(0,.36,.75264,1)[2]-.01632)<1e-9
    # Zero distributions do not repair an unfinanceable operating deficit.
    broken=copy.deepcopy(PARAM);broken.update(parent_extra_cost=50.,external_limit=0.,normal_payout=0.,release_fraction=0.)
    try: run(broken,1)
    except ValueError: pass
    else: raise AssertionError('Should reject insolvent path')
    return {'production_engine_hand_case':'profit=1; cash distribution=1; PV=1/1.1/0.75264','two_tier_dividend_hand_case':'downstream operating profit1 -> declared1 to Hexin -> declared1 to parent -> owner1, group profit remains1','continuous_loss_and_new_capital_reserve_ceiling':'pass','zero_distribution_insolvency':'rejected as required'}

def pack_output(output):
    """Lossless table encoding of annual-row keys only; nested state remains unchanged."""
    packed=copy.deepcopy(output)
    for case in packed['cases'].values():
        rows=case['annual_rows']
        columns=list(rows[0]) if rows else []
        assert all(list(row)==columns for row in rows)
        case['annual_rows']={'columns':columns,'values':[[row[col] for col in columns] for row in rows]}
    return packed

def expand_output(output):
    """Restore every case annual_rows to its original list of full field dictionaries."""
    expanded=copy.deepcopy(output)
    for case in expanded['cases'].values():
        table=case['annual_rows']
        if isinstance(table,dict):
            columns=table['columns']
            assert len(columns)==len(set(columns))
            assert all(len(row)==len(columns) for row in table['values'])
            case['annual_rows']=[dict(zip(columns,row)) for row in table['values']]
    return expanded

def main():
    output={'unit':'CNY billion; shares billion','shares':SHARES,'asof':ASOF,'entities':NAMES,'tests':tests(),'cases':{}}
    for name,p in cases().items():
        if p.get('opening_distribution',0)>0:
            assert abs(sum(PARAM['cash'])-sum(p['cash'])-p['opening_distribution'])<1e-9
            assert p['retained'][0]>=0 and abs(PARAM['retained'][0]-p['retained'][0]-p['opening_distribution'])<1e-9
            assert p['cash'][6]==p['capital'][6]==p['retained'][6]==p['reserve'][6]==0
        rr=run(p);out={'parameters':p,'valuation':valuation(rr,p['discount'],p.get('opening_distribution',0.)),'annual_rows':rr}
        out['convergence_200_300_400']={str(n):valuation(run(p,n),p['discount'],p.get('opening_distribution',0.))['value'] for n in (200,300,400)}
        out['integration_tail_bound_300_to400']=out['convergence_200_300_400']['400']-out['convergence_200_300_400']['300']
        output['cases'][name]=out
    # Same year-five operating and financial state across core endpoints.
    assert output['cases']['core_low']['annual_rows'][4]['state']==output['cases']['core_high']['annual_rows'][4]['state']
    output['offshore_cash_recovery_boundary']={'initial_principal':PARAM['cash'][6],'year5_cash':output['cases']['base']['annual_rows'][4]['state']['cash'][6],'year30_cash':output['cases']['base']['annual_rows'][29]['state']['cash'][6],'year300_undistributed_cash':output['cases']['base']['annual_rows'][-1]['state']['cash'][6],'immediate_net_value_increment_upper_bound':output['cases']['offshore_immediate_recovery_upper_bound']['valuation']['value']-output['cases']['base']['valuation']['value'],'not_an_extra_addon_to_core':True}
    output['core']={'value_range':{'low':round(output['cases']['core_low']['valuation']['value'],2),'high':round(output['cases']['core_high']['valuation']['value'],2),'currency':'CNY'},'distributions':[round(x['dividend_per_share'],6) for x in output['cases']['base']['annual_rows'][:5]],'tv5':{'low':round(output['cases']['core_low']['valuation']['tv5'],6),'high':round(output['cases']['core_high']['valuation']['tv5'],6)}}
    # Auxiliary operating earnings capitalization excludes ALL cash yield; add only legally paid extra release PV.
    aux={}
    for label,r,multiple in [('low',.105,16.),('high',.095,20.)]:
        rr=output['cases']['core_'+label]['annual_rows']
        # Controlled subtraction: re-run legal cash engine without opening excess cash.
        # This captures only the incremental owner distributions caused by existing cash,
        # not extra distributions of future operating profits already capitalized below.
        cashless=copy.deepcopy(output['cases']['core_'+label]['parameters'])
        cashless['cash']=[.3]+[(7.8*cashless['liquidity_ratio']+3.09069063185)*v for v in cashless['weights'][1:]]
        shadow=run(cashless)
        release=valuation(rr,r)['value']-valuation(shadow,r)['value']
        output['cases']['cash_attribution_shadow_'+label]={'parameters':cashless,'annual_rows':shadow,'valuation':valuation(shadow,r)}
        op=PARAM['revenue'][0]*.48*.85-(.2*(PARAM['revenue'][1]-PARAM['revenue'][0])+.01*(PARAM['revenue'][1]-PARAM['revenue'][0]))
        aux[label]={'operating_cash_earnings':op,'multiple':multiple,'opening_cash_incremental_legal_distribution_pv':release,'value':op*multiple/SHARES+release}
    output['auxiliary']=aux
    packed=pack_output(output)
    assert expand_output(packed)==output
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(packed,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps({'core':output['core'],'cases':{k:v['valuation']['value'] for k,v in output['cases'].items()},'auxiliary':aux},ensure_ascii=False,indent=2))
if __name__=='__main__': main()

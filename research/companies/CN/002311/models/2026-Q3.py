"""Haid 2026Q3. CNY billion; volumes million tonnes. Standard library only.
Every terminal value is a continuation of actual legal distributions; no cash add-back.
"""
import json, math
from pathlib import Path
from copy import deepcopy
P=dict(dom0=27.2,over0=4.3,dom1=28.5,over1=4.8,dom_growth=.05,over_growth=.15,dom_unit=105.,over_unit=220.,other=.30,animal=.20,dom_cap=450.,over_cap=1200.,mature_dom_cap=900.,mature_over_cap=1500.,cash_p=3.,cash_s=4.35,debt=3.,debt_cap=5.,ret_p=2.5,ret_s=6.,reserve_s=2.,paid_capital_s=5.,registered_growth_fraction=.30,reserve_limit_fraction=.50,intercompany_rate=.03,parent_tax=.25,sub_interest_tax_shield=.15,parent_reserve=.831874985,capital=22.67663922194,nci_equity=1.34309475243,common_equity=25.68354446951,nci=.05,interest=.035,yield_cash=.02,pmin=.8,smin=2.5,lag=.2,release=.25,legal_haircut=0.,unit_factor=1.,growth_factor=1.,capital_factor=1.,own=.75,years=65,g=.02,options=.002955818,shares=1.657062365,strike=26.91,zero_dividend=False)
class FundingError(Exception):pass

def step(st,x,p):
    """One legal cash/earnings cycle. Declare only after operations, investment and solvency."""
    s=deepcopy(st); op=x['op']; own=x['own']; reinv=x['reinv']; scale=x['scale']; t=x['t']
    p0,s0=s['cp'],s['cs']; debt0=s['debt']; rp0,rs0=s['rp'],s['rs']; pay0=s['payable']
    yi_p=p0*p['yield_cash']; yi_s=s0*p['yield_cash']; interest=debt0*p['interest']; ic_coupon=s['loan']*p['intercompany_rate']; ic_income_tax=ic_coupon*p['parent_tax']
    # Operating inputs are after-tax budgets: gross up only positive income to
    # bound incremental coupon deductibility. Prior tax losses get priority;
    # unused losses are carried without recording any deferred-tax asset/cash.
    tax_rate=p['sub_interest_tax_shield']
    before_coupon=op-own+yi_s-interest
    taxable_before_coupon=before_coupon/(1-tax_rate) if before_coupon>0 else before_coupon
    tax_loss_open=s.get('tax_loss_s',max(0,-rs0))
    taxable_capacity=max(0,taxable_before_coupon-tax_loss_open)
    ic_deductible=min(ic_coupon,taxable_capacity)
    ic_tax_shield=ic_deductible*tax_rate
    s['tax_loss_s']=max(0,tax_loss_open-taxable_before_coupon+ic_coupon)
    pn=own+yi_p+ic_coupon-ic_income_tax; sn=op-own+yi_s-interest-ic_coupon+ic_tax_shield
    s['rp']+=pn; s['rs']+=sn
    new_registered=max(0,.95*reinv)*p['registered_growth_fraction']
    s['paid_capital']+=new_registered
    provision=min(max(0,sn+min(rs0,0))*.1,max(p['reserve_limit_fraction']*s['paid_capital']-s['reserve'],0))
    s['rs']-=provision;s['reserve']+=provision
    s['capital']+=reinv
    # All group investment uses total consolidated profit, never only common profit.
    p_reinv=.05*reinv; s_reinv=.95*reinv
    s['cp']+=pn-p_reinv+(p['options']*p['strike'] if t==1 else 0)
    s['cs']+=sn-s_reinv
    parent_subscription=new_registered*(1-p['nci']);minority_subscription=new_registered*p['nci']
    s['cp']-=parent_subscription;s['cs']+=new_registered
    s['shares']+=p['options'] if t==1 else 0
    # Old receivable collections change cash, NOT this year's legal profit.
    old=pay0;s['cs']-=old;s['cp']+=old*(1-p['nci']);minor_old=old*p['nci'];s['payable']=0.
    pmin=p['pmin']*scale;smin=p['smin']*scale
    repay=min(s['loan'],max(0,s['cs']-smin));s['cs']-=repay;s['cp']+=repay;s['loan']-=repay
    debt_repay=min(s['debt'],.4 if t<=5 else max(0,s['cs']-smin)*.5)
    debt_repay=min(debt_repay,max(0,s['cs']-smin));s['cs']-=debt_repay;s['debt']-=debt_repay
    transfer=min(max(0,smin-s['cs']),max(0,s['cp']-pmin));s['cp']-=transfer;s['cs']+=transfer;s['loan']+=transfer
    newdebt=max(0,smin-s['cs']);
    if s['debt']+newdebt>p['debt_cap']+1e-9:raise FundingError(f"Y{t}: funding deficit {newdebt:.6f}, available facility {p['debt_cap']-s['debt']:.6f}")
    s['debt']+=newdebt;s['cs']+=newdebt
    if s['cp']<pmin-1e-9:raise FundingError(f"Y{t}: parent funding deficit {pmin-s['cp']:.6f}")
    # Feasible legal declaration is limited by both retained profits and current cash.
    sub_policy=[.35,.5,.65,.75,.85][t-1] if t<=5 else 1.
    excess=max(0,s['cs']-smin)
    proposed=max(0,sn)*sub_policy+p['release']*max(0,excess-max(sn,0))
    declaration=min(proposed,max(0,s['rs'])*(1-p['legal_haircut']),excess)
    paid=declaration*(1-p['lag']);s['payable']=declaration-paid;s['cs']-=paid;s['rs']-=declaration
    s['cp']+=paid*(1-p['nci']);s['rp']+=declaration*(1-p['nci'])
    parent_provision=min(max(0,pn+declaration*(1-p['nci'])+min(rp0,0))*.1,max(.5*(s['shares']+.000075557)-s['parent_reserve'],0))
    s['parent_reserve']+=parent_provision;s['rp']-=parent_provision
    group_np=pn+sn; common_np=pn+sn*(1-p['nci'])
    ordinary_target=max(0,common_np)*(.50 if t<=5 else .70)
    legal=min(max(0,s['rp']),max(0,s['rg']+common_np));money=max(0,s['cp']-pmin)
    ordinary=min(ordinary_target,legal,money)
    special=min(p['release']*max(0,money-ordinary),max(0,legal-ordinary),max(0,money-ordinary)) if t>5 else 0.
    if p['zero_dividend']:ordinary=special=0.
    dividend=ordinary+special;s['cp']-=dividend;s['rp']-=dividend;s['rg']+=common_np-dividend
    minority_paid=minor_old+paid*p['nci'];s['nci_equity']+=sn*p['nci']-declaration*p['nci']+minority_subscription
    s['common_equity']+=common_np-dividend+(p['options']*p['strike'] if t==1 else 0)
    total_change=s['cp']+s['cs']-p0-s0
    expected=group_np-reinv-debt_repay+newdebt-dividend-minority_paid+minority_subscription+(p['options']*p['strike'] if t==1 else 0)
    assert abs(total_change-expected)<1e-7
    # Balance-sheet identity is checked relative to opening calibration, including NCI payable.
    opening_gap=st['capital']+p0+s0-debt0-st['payable']*p['nci']-st['common_equity']-st['nci_equity']
    closing_gap=s['capital']+s['cp']+s['cs']-s['debt']-s['payable']*p['nci']-s['common_equity']-s['nci_equity']
    assert abs(closing_gap-opening_gap)<1e-7
    assert s['cp']>=pmin-1e-8 and s['cs']>=smin-1e-8
    assert declaration<=max(0,rs0+sn-provision)+1e-8
    assert dividend<=max(0,rp0+pn+declaration*(1-p['nci']))+1e-8
    row={**x,'group_net_profit':group_np,'common_profit':common_np,'minority_profit':sn*p['nci'],'parent_own_net':pn,'sub_net':sn,'cash_interest_parent':yi_p,'cash_interest_sub':yi_s,'debt_interest':interest,'reserve_add':provision,'sub_paid_capital':s['paid_capital'],'new_registered_capital':new_registered,'parent_subscription':parent_subscription,'minority_subscription':minority_subscription,'parent_reserve':s['parent_reserve'],'parent_reserve_add':parent_provision,'sub_taxable_before_coupon':taxable_before_coupon,'sub_tax_loss_open':tax_loss_open,'sub_tax_loss_close':s['tax_loss_s'],'sub_interest_deductible':ic_deductible,'intercompany_coupon':ic_coupon,'parent_tax_on_intercompany':ic_income_tax,'sub_interest_tax_shield':ic_tax_shield,'intercompany_tax_leakage':ic_income_tax-ic_tax_shield,'parent_reinvestment':p_reinv,'sub_reinvestment':s_reinv,'old_dividend_collected':old*(1-p['nci']),'new_sub_declared':declaration,'new_sub_paid':paid,'minority_paid':minority_paid,'debt_repaid':debt_repay,'new_debt':newdebt,'intercompany_advance':transfer,'intercompany_repaid':repay,'ordinary':ordinary,'special':special,'distribution':dividend,'distribution_per_share':dividend/s['shares'],'parent_cash':s['cp'],'sub_cash':s['cs'],'parent_legal_retained':s['rp'],'consolidated_legal_retained':s['rg'],'sub_legal_retained':s['rs'],'sub_reserve':s['reserve'],'declared_unpaid':s['payable'],'parent_dividend_receivable':s['payable']*(1-p['nci']),'intercompany_loan':s['loan'],'debt':s['debt'],'capital':s['capital'],'common_equity':s['common_equity'],'minority_equity':s['nci_equity'],'shares':s['shares'],'cash_identity_error':total_change-expected,'pmin':pmin,'smin':smin}
    return s,row

def run(p,kind='base'):
    s=dict(cp=p['cash_p'],cs=p['cash_s'],debt=p['debt'],rp=p['ret_p'],rs=p['ret_s'],reserve=p['reserve_s'],paid_capital=p['paid_capital_s'],parent_reserve=p['parent_reserve'],capital=p['capital'],rg=19.1646404088,payable=0.,loan=0.,shares=p['shares'],nci_equity=p['nci_equity'],common_equity=p['common_equity'])
    rows=[];d,o=p['dom0'],p['over0'];other=p['other'];animal=p['animal']
    for t in range(1,p['years']+2):
        dprev,oprev=d,o
        if t==1:d,o=p['dom1'],p['over1']
        else:
            fade=max(0,(12-t)/7) if t>5 else 1.
            d*=1+(p['g']+(p['dom_growth']-p['g'])*fade)*p['growth_factor']
            o*=1+(p['g']+(p['over_growth']-p['g'])*fade)*p['growth_factor']
        scale=(d+o)/(p['dom1']+p['over1']);unit=p['unit_factor'];loss=0.;shockcap=0.
        if kind=='cycle' and t<=3:unit*= [.80,.88,.96][t-1];loss=[-.6,-.3,0][t-1];shockcap=[1.,.3,-.8][t-1]
        if kind=='structural':unit*=.72;loss=-.3*scale;shockcap=.02*(d+o)
        if kind=='optimistic':unit*=1.10
        if kind=='funding_failure' and t==1:loss=-20.;shockcap=10.
        dc=p['dom_cap'] if t<=5 else p['mature_dom_cap'];oc=p['over_cap'] if t<=5 else p['mature_over_cap']
        oth=(other+animal)*scale+loss
        op=(d*p['dom_unit']+o*p['over_unit'])/1000*unit+oth
        reinv=((d-dprev)*dc+(o-oprev)*oc)/1000*p['capital_factor']+(other+animal)*max(0,scale-(rows[-1]['scale'] if rows else (p['dom0']+p['over0'])/(p['dom1']+p['over1'])))/.15+shockcap
        maintenance=2.2*scale
        x=dict(t=t,year=2026+t,dom_volume=d,over_volume=o,dom_unit_net=p['dom_unit']*unit,over_unit_net=p['over_unit']*unit,other_and_farming=oth,op=op,own=p['own']*scale,reinv=reinv,maintenance=maintenance,growth_fixed=.7*reinv,working_capital=.3*reinv,capex=maintenance+.7*reinv,scale=scale)
        s,row=step(s,x,p);rows.append(row)
    return rows

def value(rows,r,g=.02):
    n=len(rows)-1;tail=rows[-1]['distribution_per_share']/(r-g)
    pv=sum(z['distribution_per_share']/(1+r)**z['t'] for z in rows[:-1])+tail/(1+r)**n
    tv5=sum(z['distribution_per_share']/(1+r)**(z['t']-5) for z in rows[5:-1])+tail/(1+r)**(n-5)
    first=sum(z['distribution_per_share']/(1+r)**z['t'] for z in rows[:5])
    assert abs(pv-first-tv5/(1+r)**5)<1e-9
    return dict(pv=pv,tv5=tv5,tv5_pv_share=tv5/(1+r)**5/pv,tail_year=n,tail_value=tail,tail_pv_share=tail/(1+r)**n/pv)

def tests():
    # Actual function: no investment, borrowing or interest, parent earns 2, subsidiary 8.
    p=deepcopy(P);p.update(yield_cash=0.,interest=0.,nci=.25,lag=.2,options=0.,pmin=0.,smin=0.,release=0.)
    s=dict(cp=0.,cs=0.,debt=0.,rp=0.,rs=0.,reserve=0.,paid_capital=0.,parent_reserve=2.,capital=0.,payable=0.,loan=0.,shares=2.,nci_equity=1.,common_equity=4.,rg=4.)
    x=dict(t=1,op=10.,own=2.,reinv=0.,scale=1.)
    st,row=step(s,x,p)
    # 8*.35=2.8 declaration; 2.24 paid, parent gets1.68; group common earns8;
    # ordinary min(4,4.1,3.68)=3.68, parent ending0, sub5.76.
    assert abs(row['new_sub_declared']-2.8)<1e-12 and abs(row['distribution']-3.68)<1e-12
    assert abs(st['cp'])<1e-12 and abs(st['cs']-5.76)<1e-12 and abs(st['rp']-.42)<1e-12
    # Collect the old .56 payable; no new earnings => legal profit increases zero.
    p.update(lag=0.,zero_dividend=True);x.update(t=2,op=0.,own=0.)
    st2,row2=step(st,x,p)
    assert abs(row2['old_dividend_collected']-.42)<1e-12 and abs(st2['rp']-.42)<1e-12
    # Actual function: prior subsidiary legal losses must be offset before reserves.
    p=deepcopy(P);p.update(yield_cash=0.,interest=0.,nci=0.,lag=0.,options=0.,pmin=0.,smin=0.,release=0.,registered_growth_fraction=0.,zero_dividend=True)
    neg=dict(cp=0.,cs=0.,debt=0.,rp=0.,rs=-5.,reserve=0.,paid_capital=10.,parent_reserve=2.,capital=0.,payable=0.,loan=0.,shares=2.,nci_equity=0.,common_equity=0.,rg=10.)
    _,negative=step(neg,dict(t=1,op=8.,own=0.,reinv=0.,scale=1.),p)
    # Profit8 first fills historical loss5: statutory addition .3, not .8.
    assert abs(negative['reserve_add']-.3)<1e-12
    assert abs(negative['sub_legal_retained'])<1e-12 # declaration is capped at after-loss-and-reserve retained2.7
    # Actual cash function: internal loan coupon3%, parent tax25%, sub deduction15%.
    taxstate=deepcopy(neg);taxstate.update(cp=5.,cs=5.,rs=0.,loan=1.)
    _,taxrow=step(taxstate,dict(t=1,op=0.,own=0.,reinv=0.,scale=1.),p)
    assert abs(taxrow['intercompany_coupon']-.03)<1e-12
    assert abs(taxrow['group_net_profit']+.0075)<1e-12
    assert taxrow['sub_interest_tax_shield']==0 and abs(taxrow['sub_tax_loss_close']-.03)<1e-12
    # Positive after-tax income .0085 => pretax capacity .01, not coupon .03.
    _,partial=step(taxstate,dict(t=1,op=.0085,own=0.,reinv=0.,scale=1.),p)
    assert abs(partial['sub_interest_tax_shield']-.0015)<1e-12
    assert abs(partial['group_net_profit']-.0025)<1e-12
    # Sufficient profits: .085 after tax / .85 = .10 pretax; full .0045 shield.
    _,full=step(taxstate,dict(t=1,op=.085,own=0.,reinv=0.,scale=1.),p)
    assert abs(full['sub_interest_tax_shield']-.0045)<1e-12
    assert abs(full['group_net_profit']-.082)<1e-12
    # Existing tax loss .20 has priority: even profitable year receives no coupon refund.
    lossstate=deepcopy(taxstate);lossstate['tax_loss_s']=.20
    _,loss=step(lossstate,dict(t=1,op=.085,own=0.,reinv=0.,scale=1.),p)
    assert loss['sub_interest_tax_shield']==0
    assert abs(loss['sub_tax_loss_close']-.13)<1e-12
    assert abs(loss['group_net_profit']-.0775)<1e-12
    # Solvency: even canceling all ordinary/special dividends cannot fix catastrophic losses.
    p=deepcopy(P);p['zero_dividend']=True
    try:run(p,'funding_failure')
    except FundingError as e:failure=str(e)
    else:raise AssertionError('Zero dividend must still fail for exhausted funding')
    return dict(hand_case='pass',old_receivable_no_double_profit='pass',loss_offset_before_statutory_reserve='pass',intercompany_tax_asymmetry='pass',tax_shield_zero_profit='pass',tax_shield_partial_profit='pass',tax_shield_full_profit='pass',tax_shield_prior_loss='pass',zero_dividend_insolvency=failure)

def residual_income():
    # Independent economic view: clean-surplus book equity and excess ROE fade, not DCF cash inputs.
    # Broad historic ROE 11.77-20.88%; forward 15-17%, fade to capital cost in years11-20.
    result={}
    for name,roe0,cost in [('low',.15,.105),('high',.17,.095)]:
        b=25.68354446951+.002955818*26.91;initial=b;pv=b;rows=[]
        for t in range(1,21):
            roe=roe0 if t<=10 else roe0+(cost-roe0)*(t-10)/10
            earn=b*roe;dist=earn*(.5 if t<=10 else .7);ri=earn-cost*b
            pv+=ri/(1+cost)**t;rows.append(dict(t=t,book_open=b,roe=roe,profit=earn,distribution=dist,residual_income=ri,book_close=b+earn-dist));b+=earn-dist
        result[name]=dict(pv_per_share=pv/1.660018183,initial_book=initial,rows=rows,terminal_excess_return=0.)
    return result

def main():
    core=run(P);assert all(z['parent_reserve']>=.5*(z['shares']+.000075557)-1e-10 for z in core); scenarios={'base':dict(parameters=P,rows=core,low=value(core,.105),high=value(core,.095))}
    for kind in ['cycle','structural','optimistic']:
        p=deepcopy(P)
        if kind=='structural':p.update(dom_growth=.02,over_growth=.06,capital_factor=1.4,own=.55,release=.15)
        if kind=='optimistic':p.update(dom_growth=.06,over_growth=.18)
        rr=run(p,kind);scenarios[kind]=dict(parameters=p,rows=rr,value=value(rr,.10))
    sens={}
    for name,key,val in [('unit_minus10','unit_factor',.9),('capital_plus25','capital_factor',1.25),('remittance_lag50','lag',.5),('parent_legal_zero','ret_p',0.),('sub_legal_zero','ret_s',0.),('release10','release',.10),('initial_cash_minus2','cash_s',2.35),('zero_yield','yield_cash',0.),('no_initial_net_surplus','cash_s',3.30),('paid_capital_double','paid_capital_s',10.),('no_sub_interest_tax_credit','sub_interest_tax_shield',0.)]:
        p=deepcopy(P);p[key]=val;rr=run(p);sens[name]=dict(changed={key:val},rows=rr,low=value(rr,.105),high=value(rr,.095))
    # Tail law check: long-run payout growth must match the economic steady state.
    ratios=[core[i]['distribution_per_share']/core[i-1]['distribution_per_share']-1 for i in range(60,66)]
    assert max(abs(g-.02) for g in ratios)<.0001,ratios
    # Finite initial surplus recovery: strip all already-valued treasury yields on both paths.
    pa=deepcopy(P);pa['yield_cash']=0.;pb=deepcopy(pa);pb['cash_s']=3.30
    ra,rb=run(pa),run(pb)
    recovery={str(r):value(ra,r)['pv']-value(rb,r)['pv'] for r in [.095,.105]}
    recovery_bound=1.05*(1-P['nci'])/(P['shares']+P['options'])
    assert all(0<=z<=recovery_bound+1e-9 for z in recovery.values())
    convergence={}
    paths={k:(v['parameters'],k) for k,v in scenarios.items()}
    for name,key,val in [('unit_minus10','unit_factor',.9),('capital_plus25','capital_factor',1.25),('remittance_lag50','lag',.5),('release10','release',.1)]:
        p=deepcopy(P);p[key]=val;paths[name]=(p,'base')
    for name,(p,kind) in paths.items():
        runs={}
        for horizon in [65,85,105]:
            z=deepcopy(p);z['years']=horizon;rr=run(z,kind)
            runs[str(horizon)]=dict(rows=rr,low=value(rr,.105),high=value(rr,.095),last_growth=rr[-1]['distribution_per_share']/rr[-2]['distribution_per_share']-1)
        differences={side:{m:runs['65'][side][m]-runs['105'][side][m] for m in ['pv','tv5']} for side in ['low','high']}
        assert all(abs(q)<1e-3 for d in differences.values() for q in d.values()),(name,differences)
        assert all(abs(v['last_growth']-.02)<1e-4 for v in runs.values())
        convergence[name]=dict(full_extended_rows=runs['105']['rows'],horizons={h:{k:v for k,v in z.items() if k!='rows'} for h,z in runs.items()},delta_65_minus_105=differences,annual_data_rule='All years 1-106 retained once; horizons65/85 use exactly the same path prefix, not omitted annual economics')
    out=dict(horizon_convergence=convergence,initial_surplus_recovery_ex_interest=dict(incremental_pv_per_share=recovery,undiscounted_common_principal_bound=recovery_bound,initial_group_surplus=1.05),units='CNY billion; million tonnes; CNY/share',timing='Y1-Y5: next five annual payments, approximated end-year 2027-2031; no 2026Q4 cash dividend added',scenarios=scenarios,sensitivities=sens,independent_economic_view=residual_income(),tests=tests(),tail_growth_checks=ratios)
    target=Path(__file__).with_name('2026-Q3-output.json');target.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'),sort_keys=True)+'\n')
    print(json.dumps(dict(core_low=scenarios['base']['low'],core_high=scenarios['base']['high'],distributions=[z['distribution_per_share'] for z in core[:5]],scenarios={k:v.get('value') for k,v in scenarios.items() if k!='base'},ri={k:v['pv_per_share'] for k,v in out['independent_economic_view'].items()},tests=out['tests']),indent=2))
if __name__=='__main__':main()

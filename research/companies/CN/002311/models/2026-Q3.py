"""Haid: real parent statutory account + explicitly NON-LEGAL economic remittance budget.
CNY bn, million tonnes. Standard library. No look-through legal balances invented.
"""
import json, math
from pathlib import Path
from copy import deepcopy
P=dict(dom0=27.2,over0=4.3,dom1=28.5,over1=4.8,dom_growth=.05,over_growth=.15,dom_unit=105.,over_unit=220.,other=.30,animal=.20,dom_cap=450.,over_cap=1200.,mature_dom_cap=900.,mature_over_cap=1500.,cash_p=3.,cash_s=4.35,debt=3.,debt_cap=5.,ret_p=2.5,parent_reserve=.831874985,registered_parent=1.663749970,capital=22.67663922194,nci_equity=1.34309475243,common_equity=25.68354446951,nci=.05,interest=.035,yield_cash=.02,pmin=.8,smin=2.5,lag=.2,release=.25,unit_factor=1.,growth_factor=1.,capital_factor=1.,own=.75,years=105,g=.02,options=.002955818,shares=1.657062365,strike=26.91,zero_dividend=False,upstream_capacity=.90,remittance_friction=.03,foreign_tax_fade=.06,parent_tax=.15,intercompany_rate=.03,source_deductibility=0.,maintenance_factor=1.,upstream_policy_scale=1.)
class FundingError(Exception):pass

def legal_profit(open_retained,net_profit,registered,statutory,policy_extra=0):
    # PRC parent only. Registered, not paid capital or investment cost.
    legal_base=max(0,net_profit+min(open_retained,0))
    reserve=min(.1*legal_base,max(0,.5*registered-statutory))
    extra=min(max(0,policy_extra)*legal_base,max(0,open_retained+net_profit-reserve))
    return dict(retained=open_retained+net_profit-reserve-extra,statutory=statutory+reserve,reserve_add=reserve,voluntary_add=extra)

def exit_waterfall(gross_assets,asset_recovery,outside_creditors,parent_loan,ownership,cost_basis,new_investment,exit_cost,tax_rate,units):
    # Diagnostic realization contract: discounts GROSS assets, pays creditors at face,
    # then shareholder loan, then equity. No subtraction of net debt a second time.
    realized=gross_assets*asset_recovery
    fee_paid=min(max(0,realized),exit_cost)
    fee_shortfall=exit_cost-fee_paid
    available=max(0,realized-fee_paid)
    outside_paid=min(available,outside_creditors);available-=outside_paid
    loan_paid=min(available,parent_loan);available-=loan_paid
    equity_gross=available*ownership
    basis=cost_basis+new_investment
    gain=equity_gross-basis
    tax=max(0,gain)*tax_rate
    solvent=fee_shortfall<=1e-9 and outside_creditors-outside_paid<=1e-9
    return dict(feasible=solvent,exit_fee_paid=fee_paid,exit_fee_shortfall=fee_shortfall,gross_assets=gross_assets,realized=realized,outside_paid=outside_paid,outside_shortfall=outside_creditors-outside_paid,parent_loan_paid=loan_paid,equity_gross=equity_gross,minority=available*(1-ownership),tax=tax,investment_basis=basis,realized_gain=gain,capital_recovered=min(equity_gross,basis),parent_receipt=loan_paid+equity_gross-tax,units_cancelled=units if solvent else 0.,units_close=0. if solvent else units)

def step(st,x,p):
    s=deepcopy(st);t=x['t'];p0=s['cp'];s0=s['cs'];debt0=s['debt'];rp0=s['rp'];pay0=s['payable'];loan0=s['loan']
    yp=p0*p['yield_cash'];ys=s0*p['yield_cash'];interest=debt0*p['interest']
    coupon=loan0*p['intercompany_rate'];parent_tax=coupon*p['parent_tax']
    # No synthetic pooled tax loss / cross-entity interest tax credit.
    shield=min(coupon,max(0,x['op']-x['own']))*p['source_deductibility']
    pn=x['own']+yp+coupon-parent_tax
    sn=x['op']-x['own']+ys-interest-coupon+shield
    s['cp']+=pn-.05*x['reinv'];s['cs']+=sn-.95*x['reinv']
    s['capital']+=x['reinv'];option_cash=p['options']*p['strike'] if t==1 else 0.
    s['cp']+=option_cash;s['shares']+=p['options'] if t==1 else 0.
    s['registered']+=p['options'] if t==1 else 0. # conditional completed exercise AND registration; opening registration is evidenced upper bound, not claimed exact registry
    # Old net dividend receivable already earned; old collection does not enter pn.
    s['cs']-=pay0;s['cp']+=pay0*(1-p['nci']);minority_old=pay0*p['nci'];s['payable']=0.
    pmin=p['pmin']*x['scale'];smin=p['smin']*x['scale']
    repay=min(s['loan'],max(0,s['cs']-smin));s['cs']-=repay;s['cp']+=repay;s['loan']-=repay
    dr=min(s['debt'],.4 if t<=5 else max(0,s['cs']-smin)*.5,max(0,s['cs']-smin));s['debt']-=dr;s['cs']-=dr
    advance=min(max(0,smin-s['cs']),max(0,s['cp']-pmin));s['cp']-=advance;s['cs']+=advance;s['loan']+=advance
    newdebt=max(0,smin-s['cs'])
    if s['debt']+newdebt>p['debt_cap']+1e-9:raise FundingError(f'Y{t} source funding deficit {newdebt}; available {p["debt_cap"]-s["debt"]}')
    s['cs']+=newdebt;s['debt']+=newdebt
    if s['cp']<pmin-1e-9:raise FundingError(f'Y{t} parent funding deficit {pmin-s["cp"]}')
    excess=max(0,s['cs']-smin)
    policy=([.35,.5,.65,.75,.85][t-1] if t<=5 else 1.)*p['upstream_policy_scale']
    # This is an economic upstream CAPACITY/TIMING budget, NOT statutory profits,
    # reserve, registered capital or legal offsetting among subsidiaries.
    proposed=max(0,sn)*policy+p['release']*max(0,excess-max(sn,0))
    capacity=p['upstream_capacity']*max(sn,0)+p['release']*max(0,excess-max(sn,0))
    foreign_fraction=x['over_volume']*x['over_unit_net']/max(x['op']*1000,1e-6)
    foreign_fraction=max(0,min(1,foreign_fraction))
    friction_rate=p['remittance_friction']*foreign_fraction
    declaration=min(proposed,capacity,excess/(1+friction_rate))
    friction=declaration*friction_rate # assumed prepaid at declaration; not a statutory tax rate
    paid=declaration*(1-p['lag']);s['payable']=declaration-paid
    s['cs']-=paid+friction;s['cp']+=paid*(1-p['nci'])
    legal=legal_profit(rp0,pn+declaration*(1-p['nci']),s['registered'],s['reserve'])
    s['rp']=legal['retained'];s['reserve']=legal['statutory']
    group_profit=pn+sn-friction;common_profit=pn+(sn-friction)*(1-p['nci'])
    target=max(0,common_profit)*(.5 if t<=5 else .7)
    legal_capacity=max(0,min(s['rp'],s['rg']+common_profit));money=max(0,s['cp']-pmin)
    ordinary=min(target,legal_capacity,money)
    special=min(p['release']*max(0,money-ordinary),max(0,legal_capacity-ordinary)) if t>5 else 0.
    if p['zero_dividend']:ordinary=special=0.
    dividend=ordinary+special;s['cp']-=dividend;s['rp']-=dividend;s['rg']+=common_profit-dividend
    minority=minority_old+paid*p['nci']
    s['ce']+=common_profit-dividend+option_cash;s['me']+=(sn-friction)*p['nci']-declaration*p['nci']
    expected=group_profit-x['reinv']-dr+newdebt-dividend-minority+option_cash
    err=s['cp']+s['cs']-p0-s0-expected
    assert abs(err)<1e-7
    gap=s['capital']+s['cp']+s['cs']-s['debt']-s['payable']*p['nci']-s['ce']-s['me']
    assert abs(gap)<1e-6
    assert s['cp']>=pmin-1e-8 and s['cs']>=smin-1e-8
    assert s['rp']>=-1e-8 or dividend==0
    row={**x,'parent_own_profit':pn,'source_profit_budget':sn,'group_profit':group_profit,'common_profit':common_profit,'source_capacity_budget':capacity,'new_dividend_budget':declaration,'new_paid':paid,'old_received':pay0*(1-p['nci']),'foreign_remittance_friction':friction,'foreign_fraction':foreign_fraction,'parent_reserve_add':legal['reserve_add'],'parent_registered':s['registered'],'parent_statutory':s['reserve'],'parent_legal_retained':s['rp'],'parent_cash':s['cp'],'source_cash_budget':s['cs'],'parent_loan':s['loan'],'intercompany_coupon':coupon,'intercompany_parent_tax':parent_tax,'source_interest_tax_credit':shield,'intercompany_advance':advance,'intercompany_repaid':repay,'new_debt':newdebt,'debt_repaid':dr,'debt':s['debt'],'capital':s['capital'],'common_equity':s['ce'],'minority_equity':s['me'],'minority_paid':minority,'option_cash':option_cash,'ordinary':ordinary,'special':special,'distribution':dividend,'distribution_per_share':dividend/s['shares'],'shares':s['shares'],'pending_dividend':s['payable'],'cash_identity_error':err,'balance_error':gap,'pmin':pmin,'smin':smin,'state_close':deepcopy(s)}
    return s,row

def run(p,kind='base'):
    s=dict(cp=p['cash_p'],cs=p['cash_s'],debt=p['debt'],rp=p['ret_p'],reserve=p['parent_reserve'],registered=p['registered_parent'],capital=p['capital'],rg=19.1646404088,payable=0.,loan=0.,shares=p['shares'],ce=p['common_equity'],me=p['nci_equity'])
    # cash sensitivities are changes in realizability, not invented opening earnings.
    s['ce']+=(p['cash_p']+p['cash_s']-7.35)
    rows=[];d,o=p['dom0'],p['over0'];prior_scale=(d+o)/(p['dom1']+p['over1'])
    for t in range(1,p['years']+2):
        dp,oprev=d,o
        if t==1:d,o=p['dom1'],p['over1']
        else:
            fade=max(0,(12-t)/7) if t>5 else 1.
            d*=1+(p['g']+(p['dom_growth']-p['g'])*fade)*p['growth_factor'];o*=1+(p['g']+(p['over_growth']-p['g'])*fade)*p['growth_factor']
        scale=(d+o)/(p['dom1']+p['over1']);unit=p['unit_factor'];loss=0.;shock=0.
        if kind=='cycle' and t<=3:unit*=[.8,.88,.96][t-1];loss=[-.6,-.3,0][t-1];shock=[1.,.3,-.8][t-1]
        if kind=='structural':unit*=.72;loss=-.3*scale;shock=.02*(d+o)
        if kind=='optimistic':unit*=1.10
        if kind=='funding_failure' and t==1:loss=-20.;shock=10.
        dc=p['dom_cap'] if t<=5 else p['mature_dom_cap'];oc=p['over_cap'] if t<=5 else p['mature_over_cap']
        # Tax holidays are not perpetuated: 0 -> full extra haircut by Y10, budget not tax law.
        tax_fade=p['foreign_tax_fade']*min(1,max(0,t-3)/7)
        ou=p['over_unit']*unit*(1-tax_fade)
        oth=(p['other']+p['animal'])*scale+loss
        op=(d*p['dom_unit']*unit+o*ou)/1000+oth
        reinv=((d-dp)*dc+(o-oprev)*oc)/1000*p['capital_factor']+(p['other']+p['animal'])*max(0,scale-prior_scale)/.15+shock
        maintenance=2.2*scale*p['maintenance_factor'];extra_maintenance=2.2*scale*(p['maintenance_factor']-1)
        op-=extra_maintenance
        x=dict(t=t,year=2026+t,dom_volume=d,over_volume=o,dom_unit_net=p['dom_unit']*unit,over_unit_net=ou,foreign_tax_fade=tax_fade,other_and_farming=oth,op=op,own=p['own']*scale,reinv=reinv,maintenance=maintenance,extra_maintenance=extra_maintenance,growth_fixed=.7*reinv,working_capital=.3*reinv,capex=maintenance+.7*reinv,scale=scale)
        s,row=step(s,x,p);rows.append(row);prior_scale=scale
    return rows

def value(rows,r,g=.02):
    n=len(rows)-1;tail=rows[-1]['distribution_per_share']/(r-g)
    pv=sum(z['distribution_per_share']/(1+r)**z['t'] for z in rows[:-1])+tail/(1+r)**n
    tv5=sum(z['distribution_per_share']/(1+r)**(z['t']-5) for z in rows[5:-1])+tail/(1+r)**(n-5)
    assert abs(pv-sum(z['distribution_per_share']/(1+r)**z['t'] for z in rows[:5])-tv5/(1+r)**5)<1e-9
    return dict(pv=pv,tv5=tv5,tv5_pv_share=tv5/(1+r)**5/pv,tail_year=n,tail_pv_share=tail/(1+r)**n/pv)

def tests():
    # Literal expected figures exercise production functions.
    a=legal_profit(0,10,20,5);assert a['reserve_add']==1 and a['retained']==9
    assert abs(legal_profit(-5,8,20,0)['reserve_add']-.3)<1e-12
    assert legal_profit(0,10,20,10)['reserve_add']==0
    assert legal_profit(0,10,22,10)['reserve_add']==1
    # Registered20/paid10 are deliberately different: paid capital is not an argument.
    p=deepcopy(P);p.update(options=0,yield_cash=0,interest=0,remittance_friction=0,pmin=0,smin=0,nci=.25,release=0,zero_dividend=True)
    s=dict(cp=0.,cs=10.,debt=0.,rp=2.,reserve=2.,registered=2.,capital=0.,rg=20.,payable=2.,loan=0.,shares=2.,ce=9.5,me=0.)
    x=dict(t=2,op=0.,own=0.,reinv=0.,scale=1.,over_volume=0.,over_unit_net=0.)
    ss,rr=step(s,x,p);assert rr['old_received']==1.5 and ss['rp']==2 and ss['cp']==1.5
    # No cross-entity instantaneous refund even when source has negative earnings.
    s.update(cp=10.,cs=10.,payable=0.,loan=1.,ce=20.)
    x.update(op=-1.)
    ss,rr=step(s,x,p);assert rr['source_interest_tax_credit']==0 and abs(rr['intercompany_parent_tax']-.0045)<1e-12
    # Production exit waterfall: no legal profit, yet principal recoverable after real obligations.
    ex=exit_waterfall(100,.8,30,10,.6,20,5,4,.2,100)
    assert ex['outside_paid']==30 and ex['parent_loan_paid']==10
    assert abs(ex['equity_gross']-21.6)<1e-12 and ex['tax']==0
    assert abs(ex['parent_receipt']-31.6)<1e-12 and ex['units_close']==0
    gain=exit_waterfall(100,1,30,10,.6,20,5,4,.2,100)
    assert abs(gain['tax']-1.72)<1e-12 and abs(gain['parent_receipt']-41.88)<1e-12
    low=exit_waterfall(100,.2,30,10,.6,20,5,4,.2,100)
    assert low['outside_shortfall']==14 and low['parent_receipt']==0
    q=deepcopy(P);q['zero_dividend']=True
    try:run(q,'funding_failure')
    except FundingError as e:failure=str(e)
    else:raise AssertionError('funding failure must not mint financing')
    q=deepcopy(P);q.update(g=0,dom_growth=0,over_growth=0,dom1=27.2,over1=4.3)
    zz=run(q);assert all(z['maintenance']>0 for z in zz)
    return dict(registered_not_paid=a,old_receivable='cash only',no_instant_tax_refund='pass',zero_dividend_failure=failure,zero_growth_maintenance=zz[-1]['maintenance'],exit=ex,gain_exit=gain,insolvent_exit=low)

def future_surplus_tests():
    """Counterfactual extra cash inside the SAME continuing-business step; no added legal pool.
    Treasury yield is zero, isolating principal rather than income capitalization.
    Positive asset shock is diagnostic, not a forecast source of free financing.
    """
    answers={}
    for kind in ['base','cycle','structural','optimistic']:
        p=deepcopy(P);p.update(yield_cash=0,years=145)
        if kind=='structural':p.update(dom_growth=.02,over_growth=.06,capital_factor=1.4,own=.55,release=.15)
        if kind=='optimistic':p.update(dom_growth=.06,over_growth=.18)
        rows=run(p,kind)
        for at in [5,12,25]:
            st=deepcopy(rows[at-1]['state_close']);st['cs']+=1.05;st['ce']+=1.05
            delta=[]
            for x in rows[at:]:
                st,z=step(st,x,p)
                delta.append(dict(t=z['t'],incremental_distribution=z['distribution']-x['distribution'],remaining_extra_cash=z['parent_cash']+z['source_cash_budget']-x['parent_cash']-x['source_cash_budget'],incremental_minority_paid=z['minority_paid']-x['minority_paid']))
            assert abs(delta[-1]['remaining_extra_cash'])<1e-5
            assert sum(z['incremental_distribution'] for z in delta)>0
            answers[kind+'_year'+str(at)]=dict(injected_cash=1.05,rows=delta,paid_to_common=sum(z['incremental_distribution'] for z in delta),paid_to_minority=sum(z['incremental_minority_paid'] for z in delta),remaining_cash=delta[-1]['remaining_extra_cash'])
    return answers

def residual_income():
    result={}
    for name,roe0,cost in [('low',.15,.105),('high',.17,.095)]:
        b=25.68354446951+.002955818*26.91;pv=b;rows=[]
        for t in range(1,21):
            roe=roe0 if t<=10 else roe0+(cost-roe0)*(t-10)/10
            earn=b*roe;dist=earn*(.5 if t<=10 else .7);ri=earn-cost*b;pv+=ri/(1+cost)**t
            rows.append(dict(t=t,book_open=b,roe=roe,profit=earn,distribution=dist,residual_income=ri,book_close=b+earn-dist));b+=earn-dist
        result[name]=dict(pv_per_share=pv/1.660018183,rows=rows,terminal_excess_return=0.)
    return result

def main():
    out=dict(units='CNY billion, million tonnes, CNY per share',scope='Source account is economic remittance budget, NOT a legal entity. Only listed parent has statutory profits/reserves.',tests=tests(),scenarios={},sensitivities={})
    for kind in ['base','cycle','structural','optimistic']:
        p=deepcopy(P)
        if kind=='structural':p.update(dom_growth=.02,over_growth=.06,capital_factor=1.4,own=.55,release=.15)
        if kind=='optimistic':p.update(dom_growth=.06,over_growth=.18)
        rows=run(p,kind);out['scenarios'][kind]=dict(parameters=p,rows=rows,low=value(rows,.105),high=value(rows,.095),mid=value(rows,.10))
    changes=[('unit_minus10','unit_factor',.9),('capital_plus25','capital_factor',1.25),('lag50','lag',.5),('release10','release',.1),('cash_minus2','cash_s',2.35),('upstream_capacity60','upstream_capacity',.6),('upstream_capacity40','upstream_capacity',.4),('remittance_friction10','remittance_friction',.10),('foreign_tax_fade15','foreign_tax_fade',.15),('nci10','nci',.10),('parent_legal_zero','ret_p',0.),('maintenance_plus10','maintenance_factor',1.1),('policy_half','upstream_policy_scale',.5),('parent_registration2bn','registered_parent',2.),('parent_net_settlement2bn','cash_p',1.),('parent_own_half','own',.375),('bank_interest5','interest',.05),('source_cash_shortfall','cash_s',.35)]
    for name,key,val in changes:
        p=deepcopy(P);p[key]=val;rows=run(p)
        base=out['scenarios']['base']['rows'];effective=[z['t'] for z,b in zip(rows,base) if abs(z['distribution_per_share']-b['distribution_per_share'])>1e-10]
        out['sensitivities'][name]=dict(parameters=p,changed={key:val},rows=rows,low=value(rows,.105),high=value(rows,.095),effective_distribution_years=effective)
    # Method bridge: same economic operating budget; no artificial minority cash injection.
    p=deepcopy(P);p.update(foreign_tax_fade=0.,remittance_friction=0.,upstream_capacity=1.)
    rr=run(p);out['method_only_new']=dict(parameters=p,rows=rr,low=value(rr,.105),high=value(rr,.095))
    # Principal recoverability: same ongoing economics, no treasury yield, remove 1.05 initial excess.
    p=deepcopy(P);p['yield_cash']=0.;a=run(p);p['cash_s']-=1.05;b=run(p)
    out['principal_recovery']=dict(with_surplus_rows=a,without_surplus_rows=b,incremental_pv={str(r):value(a,r)['pv']-value(b,r)['pv'] for r in [.095,.105]},initial_group_principal=1.05,common_principal_ceiling=1.05/(P['shares']+P['options']))
    assert all(0<=v<=out['principal_recovery']['common_principal_ceiling']+1e-8 for v in out['principal_recovery']['incremental_pv'].values())
    out['convergence']={}
    for name,v in {**out['scenarios'],**out['sensitivities']}.items():
        kinds=name if name in out['scenarios'] else 'base';p=v['parameters'];h={}
        for n in [65,85,105,145]:
            q=deepcopy(p);q['years']=n;rr=run(q,kinds);h[str(n)]=dict(low=value(rr,.105),high=value(rr,.095),last_growth=rr[-1]['distribution_per_share']/rr[-2]['distribution_per_share']-1)
            if n==145:extended=rr
        out['convergence'][name]=dict(horizons=h,full_rows_146=extended,delta105_145=h['105']['low']['pv']-h['145']['low']['pv'])
        assert abs(h['105']['low']['pv']-h['145']['low']['pv'])<.001
        assert abs(h['145']['last_growth']-.02)<.0001
    out['future_surplus_realization']=future_surplus_tests()
    out['independent_economic_view']=residual_income()
    path=Path(__file__).with_name('2026-Q3-output.json');path.write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({k:{side:v[side] for side in ['low','high','mid']} for k,v in out['scenarios'].items()},indent=2))
if __name__=='__main__':main()

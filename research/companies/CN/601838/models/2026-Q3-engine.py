#!/usr/bin/env python3
"""成都银行 Q3 owner model. Stdlib, CNY bn (shares bn), deterministic stdout JSON.
Annual windows begin at cutoff. No market prices. Assumed refinancing is not a commitment.
"""
import json, math
S=4.238435356
A0=1498.724641
E0=93.150335
INIT=dict(A=A0,E=E0,D=1074.078584,W=294.295722,PE=92.980988,AT=11.,T=26.2,RE=45.141166,SR=9.443398,GR=19.470453)

def params(t,case='base'):
    fade=min(1,max(0,(t-5)/10))
    g=.06*(1-fade)+.03*fade
    nim=.0165*(1-fade)+.0155*fade
    cc=.0050
    x=dict(g=g,dg=g,wg=g,nim=nim,cc=cc,cir=.24,tax=.16,at_rate=.0228 if t<=3 else .03,t_rate=.03,spread=0.,liq=1.,capital=.092,roll=True,parent_profit_gap=.02,wcapacity_ratio=.20,release=min(1,max(0,(t-5)/10)))
    if case=='core_low': x.update(nim=nim-.0003,cc=.0055)
    if case=='core_high': x.update(nim=nim+.0003,cc=.0045)
    if case=='cyclical':
        if t<=3:x.update(g=[.02,.03,.04][t-1],dg=[0,.02,.04][t-1],wg=.02,nim=[.015,.0153,.0158][t-1],cc=[.010,.009,.007][t-1],liq=1.25,spread=.002,wcapacity_ratio=None)
    if case=='structural':x.update(g=.02,dg=.02,wg=.01,nim=.0135,cc=.009,cir=.29,capital=.10,liq=1.3,spread=.003,wcapacity_ratio=.15)
    if case=='optimistic':x.update(g=.08*(1-fade)+.03*fade,dg=.08*(1-fade)+.03*fade,wg=.08*(1-fade)+.03*fade,nim=.0175*(1-fade)+.0163*fade,cc=.004,cir=.235)
    if case=='nim_minus10bp':x['nim']-=.001
    if case=='funding_stress':x.update(dg=-.04 if t==1 else (.02 if t<=3 else g),wg=0 if t<=3 else g,liq=1.3,spread=.006 if t<=3 else .002,roll=False,wcapacity_ratio=None)
    if case=='slow_release':x['release']=min(1,max(0,(t-10)/15))
    if case=='tax20':x['tax']=.20
    if case=='parent_gap_stress':x['parent_profit_gap']=.20
    if case=='capital90':x['capital']=.09
    if case=='capital100':x['capital']=.10
    if case=='earnings_power':x.update(g=0,dg=0,wg=0,nim=.0160,cc=.005,release=1)
    return x

def advance(s,x,t,toy=False):
    """Same balance-sheet, capital, legal-payment and funding chain for formal and toy cases."""
    a,e,d,w,at,tier=s['A'],s['E'],s['D'],s['W'],s['AT'],s['T']
    scale0=100 if toy else A0
    gap=0 if toy else s['E']-s['PE']
    deduction=0 if toy else 1.120146
    rwa_g=.5 if toy else 1060.159861/A0
    rwa_p=.5 if toy else 1043.559058/A0
    other_g=0 if toy else 12.740759/A0
    other_p=0 if toy else 12.324414/A0
    dep=d*(1+x['dg']); wcap=w*(1+x['wg'])
    if not toy and x['wcapacity_ratio'] is not None:wcap=max(wcap,x['wcapacity_ratio']*a*(1+x['g']))
    def at_asset(anew):
        z=anew/scale0; avg=(a+anew)/2
        atn=0 if toy else (11*z if x['roll'] else 11.)
        nominal=26.2 if t<=6 else (14.9 if t==7 else 0.)
        qualify=[0.,26.2,26.2,23.94,18.70,13.46,8.22,2.98][min(t,7)] if t<=7 else 0.
        tn=0 if toy else (26.2*z if x['roll'] else nominal)
        qt=tn if x['roll'] else qualify
        # NIM applied to earning assets at starting equity structure. Surplus common capital
        # reduces wholesale funding and earns the avoided funding cost; no second asset add-on.
        surplus=e-E0/A0*a if not toy else 0
        nii=avg*.94*x['nim']+surplus*.017
        nonint=avg*.0012
        rev=nii+nonint
        expense=rev*x['cir']+avg*.0002
        loss=avg*.60*x['cc']+avg*.00007
        extra=(at+atn)/2*0 + (tier+tn)/2*(x['t_rate']-.03)+w*x['spread']
        pre=rev-expense-loss-extra
        net=pre-max(pre,0)*x['tax']
        coupon=(at+atn)/2*x['at_rate']
        p=net-coupon
        if toy:p=x['profit'];net=p;coupon=0
        profit_gap=0 if toy else x['parent_profit_gap']*z
        parent_profit=p-profit_gap
        endgap=gap+profit_gap
        # Prior accumulated losses must be covered before statutory appropriation.
        reserve_base=max(0,net-profit_gap+min(0,s['RE']))
        sradd=min(max(0,.5*(10 if toy else S)-s['SR']),reserve_base*.1)
        gr_required=0 if toy else max(0,19.470453/A0*anew-s['GR'])
        grneed=min(gr_required,max(0,s['RE']+parent_profit-sradd))
        legal=max(0,s['RE']+parent_profit-sradd-grneed)
        # Book equity required by BOTH legal bank and consolidated capital layers.
        req=max(x['capital']*rwa_p*anew+endgap+deduction*z,
                (.102*rwa_p*anew-atn)+endgap+deduction*z,
                (.135*rwa_p*anew-atn-qt-other_p*anew)+endgap+deduction*z,
                x['capital']*rwa_g*anew-(0 if toy else .675043*z),
                .102*rwa_g*anew-atn-(0 if toy else .118678*z)-(0 if toy else .675043*z),
                .135*rwa_g*anew-atn-qt-other_g*anew-(0 if toy else .118678*z)-(0 if toy else .675043*z))
        if toy:req=.1*rwa_p*anew
        cap=e+p-req
        parent_asset_proxy=anew if toy else anew*(1491.509746/1497.052011)
        cash=max(0,(.116-.06966*x['liq']*1.2)*parent_asset_proxy)
        funding=e+p+atn+tn+dep+wcap-anew
        maximum=min(cap,legal,cash,funding)
        if toy:maximum=min(cap,legal,funding)
        target=max(0,.30*p)
        if toy:target=p
        target=max(target,max(0,cap)*x['release'])
        div=max(0,min(target,maximum))
        en=e+p-div
        wn=anew-en-atn-tn-dep
        return dict(A=anew,E=en,PE=en-endgap,D=dep,W=wn,AT=atn,T=tn,RE=s['RE']+parent_profit-sradd-grneed-div,SR=s['SR']+sradd,GR=s['GR']+grneed,
                    parent_asset_proxy=parent_asset_proxy,parent_profit=parent_profit,qualifying_t2_bonds=qt,profit=p,net=net,coupon=coupon,nii=nii,revenue=rev,expense=expense,credit_loss=loss,financing_extra=extra,
                    dividend=div,required_equity=req,capital_headroom=cap-div,legal_before=legal,funding_before=funding,cash_buffer=cash,maximum=maximum,
                    parent_cet=(en-endgap-deduction*z)/(rwa_p*anew),group_cet=(en+(0 if toy else .675043*z))/(rwa_g*anew),
                    parent_t1=(en-endgap-deduction*z+atn)/(rwa_p*anew),parent_total=(en-endgap-deduction*z+atn+qt+other_p*anew)/(rwa_p*anew),
                    group_t1=(en+(0 if toy else .675043*z)+atn+(0 if toy else .118678*z))/(rwa_g*anew),
                    group_total=(en+(0 if toy else .675043*z)+atn+(0 if toy else .118678*z)+qt+other_g*anew)/(rwa_g*anew),
                    rwa_parent=rwa_p*anew,rwa_group=rwa_g*anew,liquidity_proxy=.116/(.06966*x['liq']),sr_transfer=sradd,gr_transfer=grneed)
    desired=a*(1+x['g']); out=at_asset(desired)
    if out['maximum'] < -1e-8:
        lo=a*.85; hi=desired
        if at_asset(lo)['maximum'] < -1e-8:raise ValueError('No feasible <=15% runoff path')
        for _ in range(80):
            mid=(lo+hi)/2
            if at_asset(mid)['maximum']>=0:lo=mid
            else:hi=mid
        out=at_asset(lo)
    out['asset_growth']=out['A']/a-1
    out['desired_growth']=x['g']
    out['new_at1_net']=out['AT']-at;out['new_t2_net']=out['T']-tier
    out['wholesale_net']=out['W']-w;out['deposit_net']=out['D']-d
    out['assets_change']=out['A']-a
    out['funds_change']=out['profit']-out['dividend']+out['new_at1_net']+out['new_t2_net']+out['wholesale_net']+out['deposit_net']
    assert abs(out['assets_change']-out['funds_change'])<1e-7*max(1,out['A'])
    assert abs(out['E']-e-out['profit']+out['dividend'])<1e-7*max(1,e)
    assert out['capital_headroom']>=-1e-7*max(1,e)
    # Accumulated deficit can persist legally; it blocks distributions, not the state.
    assert out['dividend']<=max(0,s['RE']+out['parent_profit']-out['sr_transfer']-out['gr_transfer'])+1e-7
    assert out['W']>=-1e-7
    assert out['W']<=wcap+1e-7*max(1,wcap)
    out['year']=t
    return out

def path(case,n=400):
    s=dict(INIT);rows=[]
    for t in range(1,n+1):s=advance(s,params(t,case),t);rows.append(s)
    return rows

def value(rows,k,initial=E0,shares=S):
    # No arbitrary liquidation or added book value in DDM; numerically converge tail.
    pv=sum(r['dividend']/(1+k)**r['year'] for r in rows)
    ri=initial; prev=initial
    for r in rows:
        ri+=(r['profit']-k*prev)/(1+k)**r['year'];prev=r['E']
    residual=rows[-1]['E']/(1+k)**len(rows)
    assert abs(ri-pv-residual)<1e-7*max(1,initial)
    tv=sum(r['dividend']/(1+k)**(r['year']-5) for r in rows[5:])/shares
    return dict(ddm=pv/shares,residual_income=ri/shares,finite_equity_residual=residual/shares,year5_value=tv,
                year5_terminal_share_of_pv=tv/(1+k)**5/(pv/shares),distributions=[r['dividend']/shares for r in rows[:5]])

def tests():
    s=dict(A=100.,E=10.,D=80.,W=10.,AT=0.,T=0.,RE=10.,SR=5.,GR=0.)
    x=params(1);x.update(g=0,dg=0,wg=0,profit=10,release=1)
    rows=[]
    for t in range(1,401):s=advance(s,x,t,True);rows.append(s)
    v=value(rows,.1,10,1)
    assert abs(v['ddm']-100)<1e-9
    assert abs(rows[0]['E']-10)<1e-12 and abs(rows[0]['W']-10)<1e-12
    loss_tests=[]
    for reserve,expected_div,expected_sr in [(5.,3.,0.),(0.,2.7,.3)]:
        start=dict(A=100.,E=10.,D=80.,W=10.,AT=0.,T=0.,RE=-5.,SR=reserve,GR=0.)
        loss_x=dict(x,profit=4.)
        first=advance(start,loss_x,1,True)
        second=advance(first,loss_x,2,True)
        assert abs(first['RE']+1)<1e-12 and first['dividend']==0 and first['sr_transfer']==0
        assert abs(second['dividend']-expected_div)<1e-12
        assert abs(second['sr_transfer']-expected_sr)<1e-12 and abs(second['RE'])<1e-12
        loss_tests.append(dict(opening_RE=-5.,annual_profit=4.,opening_SR=reserve,
                               year1_RE=first['RE'],year1_dividend=first['dividend'],year1_SR_transfer=first['sr_transfer'],
                               year2_RE=second['RE'],year2_dividend=second['dividend'],year2_SR_transfer=second['sr_transfer']))
    return dict(same_chain_constant_dividend=v['ddm'],hand_expected=100.,cash_and_capital_assertions=True,
                same_chain_loss_recovery=loss_tests)

def main():
    cases=['base','core_low','core_high','cyclical','structural','optimistic','nim_minus10bp','funding_stress','slow_release','tax20','earnings_power','capital90','capital100','parent_gap_stress']
    result={'units':'CNY billion; shares billion','shares':S,'initial':INIT,'tests':tests(),'cases':{}}
    for c in cases:
        rows=path(c)
        result['cases'][c]={'values':{str(k):value(rows,k) for k in [.105,.11,.115]},'years':rows,'convergence':{str(n):value(rows[:n],.11)['ddm'] for n in [50,100,200,400]}}
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

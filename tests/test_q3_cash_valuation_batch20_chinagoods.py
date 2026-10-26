#!/usr/bin/env python3
"""Independent literal re-entry, no formal model imports or parameter/output reads.
Reads output ONLY in optional comparison stage after this script writes own results.
Amounts billion CNY, annual end October26, first year2027.
"""
import json
from pathlib import Path

def independent_maturity(state,discount,growth,case):
    # Literal economic ledger. Does not read any official model file or output.
    pc,sc,pl,sl,pr,sr,debt,receivable,cp,cs,paycapital=state['balance']
    m,d,pay,t=state['earnings'];sharecount=5.483559226
    oc,ic,ol,il,orr,irr,orec,irec=state['pools']
    cap_total=.5 if case=='sub_reserve_cap_0_5bn' else (1. if case=='sub_reserve_cap_1bn' else (2. if case=='sub_reserve_cap_2bn' else 3.))
    lease=.69151935555*1.05**10;hotel=.51990495872*1.02**10
    protect=paycapital-.2;remaining_capital=max(0,ic-irec);pending=0.;value10=0.
    delay=5 if case=='sub_capital_return_delayed_5y' else 1
    landscale=2 if case=='land_renewal_double' else 1
    # Cohort accounting: original balance, years left at valuation, current renewal cost.
    cohorts=[{'left':10,'amort':2./20,'net':1.,'renewal':2.},
             {'left':15,'amort':2./25,'net':1.2,'renewal':1.5},
             {'left':30,'amort':4.75/40,'net':3.5625,'renewal':3.5}]
    initial_da=.75*1.02**9+.08
    physical_da0=initial_da-.29875
    gap=physical_da0-(.45*1.02**9+.08)
    rows=[]
    for year in range(11,241):
        step=year-10;f=(1+growth)**step
        parentfloor=.8*f;subfloor=.2*f
        landpayment=0.;landamort=0.
        for c in cohorts:
            if c['left']==0:
                cost=c['renewal']*landscale*1.02**year
                landpayment+=cost;c.update(left=40,amort=cost/40,net=cost)
            amort=min(c['net'],c['amort']);landamort+=amort;c['net']-=amort;c['left']-=1
        physical_da=physical_da0*f
        da=physical_da+landamort
        upkeep=physical_da-gap*max(0,3-step)/3
        normalized_parent=(m+.17+.03)*f
        subprofit=(d+pay+t-.012)*f
        parentprofit_operating=normalized_parent+(.29875*f-landamort)*.75
        totalgrowth=(normalized_parent+subprofit)*growth/.12
        subgrowth=d*f*growth/.4+paycapital*growth+2.*1.03**10*(1+growth)**(step-1)*growth
        parentgrowth=totalgrowth-subgrowth
        payaddition=paycapital*growth;paycapital+=payaddition;protect+=payaddition
        cp+=upkeep+parentgrowth+landpayment-da;cs+=subgrowth
        lp=lease*.15;hp=hotel*.10;ld=lp-lease*growth;hd=hp-hotel*growth
        lease*=1+growth;hotel*=1+growth
        alloc=min(max(cap_total/3-orr,0),max(0,subprofit+min(ol,0))*.1);ol+=subprofit-alloc;orr+=alloc
        subfree=subprofit-subgrowth;oc+=subfree
        new=min(max(0,ol-protect),max(0,oc-subfloor-orec));ol-=new
        received_op=orec if case=='upstream_delay_1y' else new
        orec=new if case=='upstream_delay_1y' else 0.
        received_inv=irec;irec=0.
        oc-=received_op;ic-=received_inv;received=received_op+received_inv
        injection=max(0,subfloor-oc);oc+=injection
        sc=oc+ic;sl=ol+il;sr=orr+irr;receivable=orec+irec
        interest=debt*.03*.75
        pc+=parentprofit_operating+da-upkeep-parentgrowth-landpayment+ld+hd+received-interest-injection
        needed=max(0,parentfloor-pc)/(.98875)
        extra_interest=needed*.01125;interest+=extra_interest;pc+=needed-extra_interest;debt+=needed
        assert debt<=8*f+1e-7
        repaid=min(max(0,pc-parentfloor),debt);pc-=repaid;debt-=repaid
        legalprofit=parentprofit_operating+lp+hp+new-interest
        alloc=min(max(sharecount*.5-pr,0),max(0,legalprofit+min(pl,0))*.1);pl+=legalprofit-alloc;pr+=alloc
        pending=min(pending,max(0,pc-parentfloor))
        ordinary=min(max(0,pl),max(0,pc-parentfloor-pending));pl-=ordinary;pc-=ordinary
        capital_return=0.
        if step>=delay:
            capital_return=min(remaining_capital,max(0,ic-irec));remaining_capital-=capital_return
            ic-=capital_return;sc-=capital_return;pc+=capital_return;pending+=capital_return
        if remaining_capital<1e-9 and ic<1e-9 and irec<1e-9:il=irr=0.
        sl=ol+il;sr=orr+irr
        if year==15:pc+=.14850607920;pending+=.14850607920
        special=min(pending,max(0,pl),max(0,pc-parentfloor));pc-=special;pl-=special;pending-=special
        div=ordinary+special;value10+=div/(1+discount)**step
        rows.append({'year':year,'dps':div/sharecount,'parent_cash':pc,'sub_cash':sc,'parent_legal':pl,'sub_legal':sl,'debt':debt,'parent_operating_capital':cp,'sub_operating_capital':cs,'land_cash':landpayment,'new_sub_declaration':new,'spv_capital_return':capital_return,'ordinary_dividend':ordinary,'special_dividend':special,'service_cash':oc,'spv_cash':ic,'service_legal':ol,'spv_legal':il,'service_reserve':orr,'spv_reserve':irr,'service_receivable':orec,'spv_receivable':irec,'parent_capital_injection':injection})
    assert remaining_capital<1e-8
    return value10,rows

def reconstruct(kind='base'):
    shares=5.483559226
    pc=2.62860596978-1.60;sc=.31908907089
    oc=.2;ic=.31908907089-.2;ol=il=orr=irr=orec=irec=0.
    cap_total=.5 if kind=='sub_reserve_cap_0_5bn' else (1. if kind=='sub_reserve_cap_1bn' else (2. if kind=='sub_reserve_cap_2bn' else 3.))
    if kind=='spv_opening_legal_loss_1_5bn':il=-1.5
    debt=3.16491319407;original_debt=3.16491319407
    legal=10.91945666804;reserve=2.41770218353;sl=sr=receivable=0.
    rent=3.10*.45*.75;digital=.14;payment=.025;trade=.03;wc=2.
    mg=[.025]*10;capscale=1.;loss=0.;lag=False;extra=0.
    if kind=='rent_growth_minus_2pp_y2_on':mg=[.025]+[.005]*9
    if kind=='capex_overrun_20pct_y1_y5':capscale=1.2
    if kind=='property_asset_loss_10pct_y1':loss=1.13
    if kind=='upstream_delay_1y':lag=True
    if kind=='extra_net_payment_1bn_y1':extra=1.
    fg=[.40,.25,.15,.05,.025,.025,.025,.025,.025,.025]
    pr=[0,0,.10,.10,.10,.15,.15,.15,.15,.10]
    ur=[0,0,0,.10,.10,.15,.15,.15,.15,.20]
    dg=[.10]*5+[.08,.06,.05,.04,.03];pg=[.20]*5+[.15,.10,.08,.05,.03]
    cap=[2.45,2.05,1.33,.3,.1,0,0,0,0,0];completion=[1,.5,.1]+[0]*7
    project=[0,0,0,.04,.10,.14,.16,.17,.17,.17]
    pda=[0,0,0,.02,.05,.07,.08,.08,.08,.08]
    fees=[1.5,1.,.5]+[0]*7
    pcwc=[.3,.2,-.25,-.25]+[0]*6
    otherpayment=[.15,.10]+[0]*8;swc=[.15,.05]+[0]*8
    oldsale=[.3,.5,.2]+[0]*7;oldsaleprofit=[.08,.10,.04]+[0]*7
    newsale=[0,0,.8,1.7,1.]+[0]*5;newsaleprofit=[0,0,.1,.25,.15]+[0]*5
    rows=[];protected=0.;cp=21.528;cs=2.50
    for i in range(10):
        if i:
            rent*=1+mg[i];digital*=1+dg[i];payment*=1+pg[i];trade*=1.03
        oldlegal,oldreserve=legal,reserve
        finp=1.17544289071*(1-sum(fg[:i]))
        fins=(1.62111182267-.66436108531)*(1-sum(fg[:i]))
        fundp=.335*(1-sum(ur[:i]));funds=(1.37111541374-.102918559)*(1-sum(ur[:i]))
        ip=.02*(finp+fundp);isub=.02*(fins+funds)
        repp=1.17544289071*fg[i]+(3.61962308727-loss)*pr[i]+.335*ur[i]
        reps=(1.62111182267-.66436108531)*fg[i]+(1.37111541374-.102918559)*ur[i]
        if i==9:reps+=.66436108531+.102918559
        lease=.69151935555*1.05**i;hotel=.51990495872*1.02**i
        assocprofit=lease*.18+hotel*.10;assocdiv=lease*.13+hotel*.08
        capcash=(cap[i]+completion[i])*capscale
        draw=min(capcash*.35,max(0,8-debt));interest=(debt+.5*draw)*.03*.75
        debt+=draw;pc+=draw
        pp=rent+project[i]+.75*fees[i]+newsaleprofit[i]+.03+oldsaleprofit[i]+assocprofit+ip-interest-(loss if i==0 else 0)
        op=digital+payment+trade-.012;iprof=isub;sp=op+iprof
        oa=min(max(cap_total/3-orr,0),max(0,op+min(ol,0))*.1);orr+=oa;ol+=op-oa
        ia=min(max(cap_total*2/3-irr,0),max(0,iprof+min(il,0))*.1);irr+=ia;il+=iprof-ia
        twc=.03*wc;wc+=twc
        cp+=capcash+rent*mg[i]/.4-.30*1.02**i;cs+=digital*dg[i]/.4+payment*.25+twc
        oc+=op-digital*dg[i]/.4-payment*.25-twc-swc[i];ic+=iprof+reps;protected+=payment*.25
        od=min(max(ol-protected,0),max(oc-.2-orec,0),max(op*.75,0))
        idiv=min(max(il,0),max(ic-irec,0),max(iprof*.75,0))
        if i==9:
            od=min(max(ol-protected,0),max(oc-.2-orec,0));idiv=min(max(il,0),max(ic-irec,0))
        ol-=od;il-=idiv
        og=orec if lag else od;ig=irec if lag else idiv
        orec=od if lag else 0.;irec=idiv if lag else 0.
        oc-=og;ic-=ig;inject=max(.2-oc,0);oc+=inject
        declare=od+idiv;got=og+ig;receivable=orec+irec;sc=oc+ic;sl=ol+il;sr=orr+irr
        pp+=declare
        alloc=min(max(shares*.5-reserve,0),max(0,pp+min(legal,0))*.1)
        legal+=pp-alloc;reserve+=alloc
        pf=rent+project[i]-.25*fees[i]+newsale[i]+.03+(.75-.45)*1.02**i-rent*mg[i]/.4-capcash+oldsale[i]-pcwc[i]-otherpayment[i]+assocdiv+ip+repp+(.45 if i==1 else 0)+(.50 if i==2 else 0)-interest-inject-(.060 if i==1 else 0)-(extra if i==0 else 0)
        pc+=pf+got
        common=pp-declare-assocprofit+sp+assocprofit
        target=max(common*.55,0)
        if i==9:pc-=debt;debt=0;target=max(pc-.8,0)
        short=max(.8-pc,0);ei=short/(1-.5*.03*.75)*.5*.03*.75
        if ei:
            pc-=ei;pp-=ei;common-=ei;interest+=ei
            alloc=min(max(shares*.5-oldreserve,0),max(0,pp+min(oldlegal,0))*.1)
            legal=oldlegal+pp-alloc;reserve=oldreserve+alloc;target=0
        emergency=max(.8-pc,0)
        if debt+emergency>8+1e-9:raise ValueError('insolvent')
        pc+=emergency;debt+=emergency
        dividend=min(target,max(legal,0),max(pc-.8,0));pc-=dividend;legal-=dividend
        if i>=4:
            rep=min(max(pc-.8,0),max(debt-original_debt,0));pc-=rep;debt-=rep
        rows.append({'year':i+1,'dividend':dividend,'dps':dividend/shares,'parent_cash':pc,'sub_cash':sc,'debt':debt,'parent_legal':legal,'sub_legal':sl,'service_cash':oc,'spv_cash':ic,'service_legal':ol,'spv_legal':il,'service_reserve':orr,'spv_reserve':irr,'service_receivable':orec,'spv_receivable':irec,'parent_capital_injection':inject})
    endpoints=[]
    for r,g in [(.095,.02),(.085,.025)]:
        state={'balance':[pc,sc,legal,sl,reserve,sr,debt,receivable,cp,cs,.20+protected],'earnings':[rent,digital,payment,trade],'pools':[oc,ic,ol,il,orr,irr,orec,irec]}
        tv10,mature=independent_maturity(state,r,g,kind)
        tv5=sum(rows[j]['dividend']/(1+r)**(j-4) for j in range(5,10))+tv10/(1+r)**5
        pv=sum(rows[j]['dividend']/(1+r)**(j+1) for j in range(5))+tv5/(1+r)**5
        endpoints.append({'pv':pv/shares,'tv5':tv5/shares,'tv10':tv10/shares,'mature_annual':mature})
    return {'annual':rows,'low':endpoints[0],'high':endpoints[1]}


ROOT=Path(__file__).resolve().parents[1]/'research/companies/CN/600415/models'
def test_chinagoods_independent_literal_pools_land_and_all_mature_states():
 names=['base','rent_growth_minus_2pp_y2_on','capex_overrun_20pct_y1_y5','property_asset_loss_10pct_y1','upstream_delay_1y','extra_net_payment_1bn_y1','land_renewal_double','sub_capital_return_delayed_5y','sub_reserve_cap_0_5bn','sub_reserve_cap_1bn','sub_reserve_cap_2bn','spv_opening_legal_loss_1_5bn']
 b={n:reconstruct(n) for n in names}
 a=json.loads((ROOT/'2026-Q3-output.json').read_text())
 for n in b:
  for side in ['low','high']:
   for k in ['pv','tv5','tv10']:assert abs(b[n][side][k]-a['scenarios'][n][side][k])<1e-9
   for row,formal in zip(b[n][side]['mature_annual'],a['scenarios'][n][side]['terminal_detail']['annual']):
    vals=dict(zip(a['mature_columns'],formal))
    for k in row:assert abs(row[k]-vals[k])<1e-9
  for x,y in zip(b[n]['annual'],a['scenarios'][n]['annual']):
   for k in ['dps','parent_cash','sub_cash','debt','parent_legal','sub_legal','service_cash','spv_cash','service_legal','spv_legal','service_reserve','spv_reserve','service_receivable','spv_receivable','parent_capital_injection']:assert abs(x[k]-y[k])<1e-9

def test_chinagoods_actual_functions_segregated_capital_and_land_convergence():
 import runpy,copy
 m=runpy.run_path(str(ROOT/'2026-Q3.py'));assert all(v=='pass' for v in m['self_tests']().values())
 p=copy.deepcopy(m['P']);rows=m['simulate'](p)
 assert abs(rows[0]['parent_capital_injection']-.06825)<1e-9
 assert abs(rows[-1]['service_cash']-.2)<1e-9 and rows[-1]['spv_legal']==0
 for cap in [.5,1,2,3,1e6]:
  q=dict(p,sub_reserve_cap=cap);rr=m['simulate'](q)
  for rate,g in [(.095,.02),(.085,.025)]:
   v=m['value'](rr,q,rate,g);base=m['value'](rows,p,rate,g)
   assert abs(v['pv']-base['pv'])<1e-10
 for rate,g in [(.095,.02),(.085,.025)]:
  a=m['value'](rows,p,rate,g);b=m['value'](rows,dict(p,mature_last_year=300),rate,g)
  for k in ['pv','tv5']:assert abs(a[k]-b[k])<1e-5
  assert a['terminal_detail']['annual']==b['terminal_detail']['annual'][:230]
  annual=[dict(zip(m['MATURE_COLUMNS'],r)) for r in a['terminal_detail']['annual']]
  assert annual[0]['spv_cash']==0 and annual[0]['spv_legal']==0
  assert annual[0]['service_cash']>0 and annual[0]['spv_capital_return']>3
  renewal=next(r for r in annual if r['year']==21)
  assert renewal['land_cash']>3 and renewal['dps']==0 and renewal['borrowing']>0

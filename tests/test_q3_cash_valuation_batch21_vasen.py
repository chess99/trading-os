"""Independent literal economic loop for adopted core and -1pp margin.
No production code, imports, AST or result data used as calculation inputs.
Amounts CNY bn; nominal capital, shareholder claim and cash are separate.
"""
import json
from pathlib import Path

def literal(margin_shift,jv_net=.30):
    shares0=1.571867988;capital=1.592037988;treasury=.02017
    weights=[.46,.19,.23,.12]
    cash=[.25,.10,.12,.08];retained=[.45,.18,.20,.10]
    nwc=[.16,.07,.08,.04]
    mother_cash=1.45;mother_retained=.75;consolidated_retained=2.32064890364
    oldrev=4.95;rows=[]
    for year in range(1,241):
        if year==1:rev=4.9; margin=.147
        elif year<=5:
            rev=oldrev*(1+[.02,.03,.03,.025][year-2]);margin=[.148,.149,.15,.15][year-2]
        elif year<=10:
            rev=oldrev*(1+.025+(.015-.025)*(year-5)/5);margin=.15+(.14-.15)*(year-5)/5
        else:rev=oldrev*1.015; margin=.14
        margin+=margin_shift;scale=rev/4.9
        settlement=.30 if year==1 else .20 if year==2 else 0
        mother_cash-=settlement
        parent_profit=-.12*scale+mother_cash*.012
        # Before exempt dividends parent taxable income negative; no immediate loss tax credit.
        assert parent_profit<0
        mother_cash+=parent_profit;group_profit=parent_profit
        subdeclared=[]
        for i,w in enumerate(weights):
            cash[i]+=settlement*w
            operating_aftertax=rev*margin*w
            interest_aftertax=cash[i]*.012*.85
            profit=operating_aftertax+interest_aftertax
            target_nwc=rev*(.35/4.9)*w
            incremental_fixed=max(0,rev-oldrev)*.6*w
            commitment=(.10 if year==1 else .05 if year==2 else 0)*w
            # Maintenance exactly equals depreciation, so only incremental cash investment remains.
            cash[i]+=profit-incremental_fixed-commitment-(target_nwc-nwc[i]);nwc[i]=target_nwc
            retained[i]+=profit # original mature reserve already equals fixed registered half
            floor=.30*scale*w
            assert cash[i]>=floor-1e-9
            declared=min(retained[i],max(0,cash[i]-floor))
            cash[i]-=declared;retained[i]-=declared
            mother_cash+=declared;parent_profit+=declared;group_profit+=profit;subdeclared.append(declared)
        nonop_profit=0
        if year==1:mother_cash-=.00304348433
        if year==5:mother_cash+=jv_net;nonop_profit=jv_net-.36784975989
        if year==8:mother_cash+=.35;nonop_profit=.35-.555418655
        if year==6:mother_cash+=.03
        mother_retained+=parent_profit+nonop_profit
        consolidated_retained+=group_profit+nonop_profit
        floor=.25*scale;available=max(0,mother_cash-floor)
        assert mother_cash>=floor-1e-9
        if year<=5:
            ordinary=max(0,min(.8*max(0,group_profit),consolidated_retained,mother_retained,available))
            mother_retained-=ordinary;mother_cash-=ordinary;consolidated_retained-=ordinary
            extra=max(0,min(.2*max(0,mother_cash-floor),consolidated_retained,mother_retained,mother_cash-floor))
            mother_retained-=extra;mother_cash-=extra;consolidated_retained-=extra
        else:
            ordinary=max(0,min(available,consolidated_retained,mother_retained));extra=0
            mother_retained-=ordinary;mother_cash-=ordinary;consolidated_retained-=ordinary
        returned=0
        if year>=12 and mother_retained>=-1e-12:
            returned=min(max(0,mother_cash-floor),max(0,capital-.50),capital-treasury)
            mother_cash-=returned;capital-=returned
        distribution=ordinary+extra+returned
        rows.append({'year':year,'D':distribution,'dps':distribution/shares0,'parent_cash':mother_cash,'parent_retained':mother_retained,'sub_cash':cash[:],'sub_retained':retained[:],'upstream':subdeclared,'capital':capital,'capital_return':returned})
        oldrev=rev
    vals=[]
    for rate in [.1,.085]:
        first=sum(x['dps']/(1+rate)**x['year'] for x in rows[:5])
        tv=sum(x['dps']/(1+rate)**(x['year']-5) for x in rows[5:])
        vals.append({'r':rate,'PV':first+tv/(1+rate)**5,'TV5':tv,'first5PV':first})
    return {'rows':rows,'values':vals}

ROOT=Path(__file__).resolve().parents[1]/'research/companies/CN/002372/models'

def test_vasen_independent_literal_cash_legal_margin_and_tax():
 result={name:literal(shift,cash) for name,shift,cash in [('base',0.,.30),('margin_minus_1pp',-.01,.30),('jv_extra_tax_zero_basis_boundary',0.,.225),('jv_extra_tax_half_proceeds_basis',0.,.2625)]}
 # Read comparison targets only after completing every economic calculation.
 target=json.loads((ROOT/'2026-Q3-output.json').read_text())
 errors={}
 for name,case in result.items():
     t=target['scenarios'][name];maximum=0
     for i,x in enumerate(case['rows']):
         y=t['annual'][i]
         values=[abs(x['D']-y['distribution']),abs(x['parent_cash']-y['parent']['cash']),abs(x['parent_retained']-y['parent']['retained']),abs(x['capital']-y['parent']['registered_capital'])]
         for j in range(4):values += [abs(x['sub_cash'][j]-y['subsidiaries'][j]['cash']),abs(x['sub_retained'][j]-y['subsidiaries'][j]['legal_retained'])]
         maximum=max(maximum,*values)
     for i,x in enumerate(case['values']):
         assert abs(x['PV']-t['valuation'][i]['pv'])<1e-9
         assert abs(x['TV5']-t['valuation'][i]['tv5'])<1e-9
     assert maximum<1e-8;errors[name]=maximum

def test_vasen_actual_functions_registration_capital_and_original_holder():
 import runpy,copy
 m=runpy.run_path(str(ROOT/'2026-Q3.py'));m['tests']();d=m['boundary_diagnostics']()
 for z in d.values():assert z['status']=='infeasible' and z['pv'] is None and z['tv5'] is None
 assert d['positive_cash_floor']['opening_cash']>0
 rows=m['path'](m['BUDGET']);old=rows[10];new=rows[11]
 assert new['capital_return']>.8
 assert abs(old['parent']['capital']-new['parent']['capital']-new['capital_return'])<1e-9
 assert abs(new['current_outstanding_shares']/1.571867988-new['shares_per_initial_share'])<1e-10
 assert abs(new['distribution']/1.571867988-new['dps'])<1e-10
 assert abs(new['parent']['reserve']-.796038994)<1e-10
 for row in rows:
  for e,cap in zip(row['subsidiaries'],[.32,.10,.08,.06]):
   assert e['reserve']<=cap*.5+1e-9
   assert e['cash']-e['payable']>=.30*(row['revenue']/4.9)*[.46,.19,.23,.12][row['subsidiaries'].index(e)]-1e-7
 extended=m['path'](m['BUDGET'],300)
 assert extended[:240]==rows
 for r in [.10,.085]:
  for k in ['pv','tv5']:assert abs(m['value'](extended,r)[k]-m['value'](rows,r)[k])<1e-6

def test_vasen_registered_not_paid_in_and_unknown_opening_budget():
 import runpy,copy
 m=runpy.run_path(str(ROOT/'2026-Q3.py'))
 e=dict(re=0.,reserve=5.,registered_capital=20.,paid_capital=10.)
 assert m['accrue_legal'](e,10.)==1. and e['re']==9.
 b=copy.deepcopy(m['BUDGET']);b['subs_paid_ratio']=[.5]*4
 assert [r['dps'] for r in m['path'](b)]==[r['dps'] for r in m['path'](m['BUDGET'])]
 b=copy.deepcopy(m['BUDGET']);b.update(opening_reserve_full=False,subs_legal_opening=[0.]*4)
 z=m['value'](m['path'](b),.10)
 assert round(z['pv'],5)==4.76975  # Published diagnostic at five-decimal display precision, not independent proof.
 assert m['path'](b)[0]['dps']<m['path'](m['BUDGET'])[0]['dps']

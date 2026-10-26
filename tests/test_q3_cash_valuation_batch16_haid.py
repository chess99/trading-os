"""Independent literal reconstruction from research assumptions, not formal source/AST/JSON inputs.
Only after computing results does this program load formal output for comparison.
"""
import json
from pathlib import Path

def rebuild(unit=1,capfactor=1,delay=.2,sweep=.25,registered0=5,shield=.15):
    # Literal source-budget inputs: BN CNY, million tonnes.
    mother_money=3.; subsidiaries_money=4.35; borrowing=3.; mother_re=2.5; subsidiaries_re=6.;statutory=2.
    registered=registered0;parent_statutory=.831874985;group_re=19.1646404088;investment=22.67663922194; old_distribution=0.;intercompany=0.
    shares=1.657062365; domestic=27.2;foreign=4.3;previous_scale=31.5/33.3
    output=[];loss_carry=0.
    for year in range(1,67):
        olddom,oldfor=domestic,foreign
        if year==1: domestic,foreign=28.5,4.8
        else:
            decay=1 if year<=5 else max(0,(12-year)/7)
            domestic=domestic*(1.02+.03*decay);foreign=foreign*(1.02+.13*decay)
        size=(domestic+foreign)/33.3
        retained=(domestic-olddom)*(450 if year<=5 else 900)/1000*capfactor
        retained+=(foreign-oldfor)*(1200 if year<=5 else 1500)/1000*capfactor
        retained+=.5*max(0,size-previous_scale)/.15;previous_scale=size
        operating=(domestic*105+foreign*220)*unit/1000+.5*size
        mother_result=.75*size+.02*mother_money+.03*intercompany*(1-.25)
        sub_before_interest=operating-.75*size+.02*subsidiaries_money-.035*borrowing
        sub_tax_income=sub_before_interest/(1-shield) if sub_before_interest>0 else sub_before_interest
        usable=max(0,sub_tax_income-loss_carry)
        coupon=.03*intercompany
        current_tax_credit=min(coupon,usable)*shield
        loss_carry=max(0,loss_carry-sub_tax_income+coupon)
        subsidiary_result=sub_before_interest-coupon+current_tax_credit
        prior_sub_re=subsidiaries_re;prior_parent_re=mother_re
        mother_re+=mother_result;subsidiaries_re+=subsidiary_result
        issued_sub_capital=.95*max(0,retained)*.30;registered+=issued_sub_capital
        reserve=min(max(0,subsidiary_result+min(0,prior_sub_re))*.1,max(0,.50*registered-statutory))
        statutory+=reserve;subsidiaries_re-=reserve;investment+=retained
        mother_money+=mother_result-.05*retained
        subsidiaries_money+=subsidiary_result-.95*retained+issued_sub_capital
        mother_money-=issued_sub_capital*.95
        if year==1:mother_money+=.002955818*26.91;shares+=.002955818
        mother_money+=.95*old_distribution;subsidiaries_money-=old_distribution
        loan_return=min(intercompany,max(0,subsidiaries_money-2.5*size))
        subsidiaries_money-=loan_return;mother_money+=loan_return;intercompany-=loan_return
        amortize=min(borrowing,.4 if year<=5 else max(0,subsidiaries_money-2.5*size)*.5,max(0,subsidiaries_money-2.5*size))
        subsidiaries_money-=amortize;borrowing-=amortize
        advance=min(max(0,2.5*size-subsidiaries_money),max(0,mother_money-.8*size))
        mother_money-=advance;subsidiaries_money+=advance;intercompany+=advance
        draw=max(0,2.5*size-subsidiaries_money)
        assert borrowing+draw<=5+1e-9
        borrowing+=draw;subsidiaries_money+=draw
        uncommitted=max(0,subsidiaries_money-2.5*size)
        remittance_share=[.35,.50,.65,.75,.85][year-1] if year<=5 else 1.
        declaration=min(max(0,subsidiary_result)*remittance_share+sweep*max(0,uncommitted-max(0,subsidiary_result)),max(0,subsidiaries_re),uncommitted)
        payout=declaration*(1-delay);old_distribution=declaration-payout
        subsidiaries_money-=payout;subsidiaries_re-=declaration;mother_money+=payout*.95;mother_re+=declaration*.95
        parent_provision=min(max(0,mother_result+.95*declaration+min(prior_parent_re,0))*.1,max(0,.5*(shares+.000075557)-parent_statutory))
        parent_statutory+=parent_provision;mother_re-=parent_provision
        common_result=mother_result+.95*subsidiary_result
        legal=min(max(0,mother_re),max(0,group_re+common_result));funds=max(0,mother_money-.8*size)
        ordinary=min(max(0,common_result)*(.5 if year<=5 else .7),legal,funds)
        extra=min(sweep*max(0,funds-ordinary),max(0,legal-ordinary),max(0,funds-ordinary)) if year>5 else 0
        paid=ordinary+extra;mother_money-=paid;mother_re-=paid;group_re+=common_result-paid
        output.append(dict(year=year,distribution=paid/shares,mother_money=mother_money,subsidiaries_money=subsidiaries_money,mother_re=mother_re,subsidiaries_re=subsidiaries_re,borrowing=borrowing))
    result={}
    for key,r in [('low',.105),('high',.095)]:
        # Backward recursion, distinct from formal forward summation.
        continuation=output[-1]['distribution']/(r-.02)
        year5=None
        for q in reversed(output[:-1]):
            if q['year']==5:year5=continuation
            continuation=(q['distribution']+continuation)/(1+r)
        result[key]=dict(pv=continuation,tv5=year5)
    result['first5']=[q['distribution'] for q in output[:5]]
    result['year5_cash']=output[4];result['all_rows']=output
    return result

# Independent nonzero-loan arithmetic, before formal results are accessed.
def loan_tax_check(after_tax_operating,old_loss):
    pretax=after_tax_operating/.85 if after_tax_operating>0 else after_tax_operating
    credit=.15*min(.03,max(pretax-old_loss,0))
    return dict(credit=credit,loss=max(old_loss-pretax+.03,0),group=after_tax_operating-.0075+credit)
loan_cases={}
for name,income,loss,credit,closing,profit in [('zero',0,0,0,.03,-.0075),('partial',.0085,0,.0015,.02,.0025),('full',.085,0,.0045,0,.082),('prior_loss',.085,.2,0,.13,.0775)]:
    case=loan_tax_check(income,loss)
    assert abs(case['credit']-credit)<1e-12 and abs(case['loss']-closing)<1e-12 and abs(case['group']-profit)<1e-12
    loan_cases[name]=case


ROOT=Path(__file__).resolve().parents[1]/'research/companies/CN/002311/models'

def test_haid_literal_units_capital_remittance_tax():
    calc={'base':rebuild(),'unit_minus10':rebuild(unit=.9),'capital_plus25':rebuild(capfactor=1.25),'remittance_lag50':rebuild(delay=.5),'release10':rebuild(sweep=.1),'paid_capital_double':rebuild(registered0=10),'no_sub_interest_tax_credit':rebuild(shield=0)}
    formal=json.loads((ROOT/'2026-Q3-output.json').read_text())
    for name,res in calc.items():
        expected=formal['scenarios']['base'] if name=='base' else formal['sensitivities'][name]
        for side in ['low','high']:
            for k in ['pv','tv5']:assert abs(res[side][k]-expected[side][k])<1e-9
        for a,b in zip(res['all_rows'],expected['rows']):
            for x,y in [('distribution','distribution_per_share'),('mother_money','parent_cash'),('subsidiaries_money','sub_cash'),('mother_re','parent_legal_retained'),('subsidiaries_re','sub_legal_retained'),('borrowing','debt')]:assert abs(a[x]-b[y])<1e-8

def test_haid_actual_handcases_and_closure():
    import runpy
    m=runpy.run_path(str(ROOT/'2026-Q3.py'));m['tests']()
    o=json.loads((ROOT/'2026-Q3-output.json').read_text())
    for k,v in o['horizon_convergence'].items():
        for side in ['low','high']:
            for measure in ['pv','tv5']:assert abs(v['delta_65_minus_105'][side][measure])<1e-4
        assert len(v['full_extended_rows'])==106
        assert all(abs(x['cash_identity_error'])<1e-7 for x in v['full_extended_rows'])
    for r in o['scenarios']['base']['rows']:
        assert r['sub_reserve']<=r['sub_paid_capital']*.5+1e-8
        assert abs(r['parent_subscription']+r['minority_subscription']-r['new_registered_capital'])<1e-9

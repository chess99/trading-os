#!/usr/bin/env python3
"""Independent Decimal reconstruction. No production imports or intermediate production balances.
Only comparison at END reads 2026-Q3-output.json. Literal inputs from source/assumption notes.
"""
from decimal import Decimal as D, getcontext
from pathlib import Path
import json
getcontext().prec=38
Z=D(0); O=D(1)
def V(xs): return [D(str(x)) for x in xs]
def nonnegative(x):return max(Z,x)
def run(case):
    dom,foreign,other=V([9.1,10.2,.55]); prior=dom+foreign+other
    cash=sum(V([4.49024886743,2.23031437318,.39761027038,.20,-.10]));bank=sum(V([2.00141580513,.028259]))
    mother_cash=D('1'); retained=D('1.97762124926');reserve=D('.4109457595')
    source_ret=V([0,0]); unpaid=Z; rows=[];other_unremitted=Z; share=D('.925527012')
    dm=V([.135,.138,.14,.14,.14]);fm=V([.085,.088,.09,.09,.09]);r=D('.0975');g=D('.015');roic=D('.13')
    if case=='core_low':
        dm=V([.132,.134,.136,.136,.136]);fm=V([.082,.084,.086,.086,.086]);r=D('.105');g=D('.01');roic=D('.12')
    if case=='export_margin_minus_100bp':fm=[x-D('.01') for x in fm]
    for t in range(5):
        opening=cash;opening_bank=bank;opening_mother=mother_cash
        dom*=O+V([-.02,.02,.03,.03,.02])[t];foreign*=O+V([.04,.05,.05,.04,.03])[t];other*=O+V([0,.02,.02,.02,.02])[t]
        sales=dom+foreign+other
        operating=(dom*dm[t]+foreign*fm[t]+other*D('.14'))*D('.78')*D('.982')
        profit=operating+cash*D('.016')*D('.78')-bank*D('.035')*D('.78')
        depreciation=V([.55,.60,.65,.69,.72])[t];capex=V([1.50,1.55,1.30,1,.75])[t]
        wc=(sales-prior)*D('.08')+(D('.1') if t==0 else Z)
        flow=profit+depreciation-capex-wc
        reinvest=nonnegative(capex-depreciation+wc)
        declarations=[];source_rows=[]
        for k in range(2):
            subprofit=D('.5')*([dom/D('9.1')*dm[t]/D('.135'),foreign/D('10.2')*fm[t]/D('.085')][k])
            hold=D('.1')*nonnegative(subprofit+min(Z,source_ret[k])) if k==0 else Z
            source_ret[k]+=subprofit-hold
            capacity=nonnegative(subprofit-reinvest*D('.2'))
            declared=min(nonnegative(source_ret[k]),nonnegative(subprofit)*V([.8,.75])[k],capacity)
            source_ret[k]-=declared;declarations.append(declared);source_rows.append({'profit':subprofit,'declared':declared,'unremitted':source_ret[k]})
        declared=sum(declarations);collected=declared+unpaid;unpaid=Z
        mother_own=D('.22')*sales/D('19.85');friction=declarations[1]*D('.03')
        other_unremitted+=operating-mother_own-sum(x['profit'] for x in source_rows)
        mother_profit=mother_own+declared-friction
        charge=min(nonnegative(D('.925637012')/2-reserve),nonnegative(mother_profit+min(retained,Z))/10)
        retained+=mother_profit-charge;reserve+=charge
        inject=V([.15,.05,0,0,0])[t];hq=V([.25,.32,.34,.278,0])[t];cancel=D('.00087168') if t==0 else Z
        mother_cash+=mother_own+collected-friction-inject-hq-cancel
        cash+=flow-friction-cancel;floor=sales*D('.075')+D('1.20')
        repayment=min(bank,nonnegative(cash-floor),V([.4,.4,.4,.4,.42967480513])[t]);cash-=repayment;bank-=repayment
        # These tested core paths require neither mother nor group incremental borrowing.
        assert mother_cash>=D('.4') and cash>=floor
        distribution=min(profit*D('.6'),nonnegative(retained),nonnegative(mother_cash-D('.4')),nonnegative(cash-floor))
        retained-=distribution;mother_cash-=distribution;cash-=distribution
        rows.append({'year':t+1,'revenue':sales,'common_operating_profit':operating,'common_economic_profit':profit,
         'pre_dividend_fcf':flow,'debt_repayment':repayment,'new_debt':Z,'dividend':distribution,'cash_end':cash,'debt_end':bank,
         'parent_profit':mother_profit,'parent_cash_end':mother_cash,'parent_legal_retained_end':retained,
         'parent_statutory_reserve_end':reserve,'subsidiary_declared_dividends':declared,'minimum_operating_cash':floor,
         'sources':source_rows})
        assert abs(cash-(opening+flow-friction-cancel-repayment-distribution))<D('1e-30')
        assert abs(mother_cash-(opening_mother+mother_own+collected-friction-inject-hq-cancel-distribution))<D('1e-30')
        prior=sales
    # Rebuild terminal principal routes from independent ending state, not production cash.
    extra=cash-bank-floor;remaining=extra;claims=D('2.6');sub_start=source_ret[:];mother_head=nonnegative(mother_cash-D('.4'))
    source_ret.append(max(Z,other_unremitted)*D('.5'));sub_start=source_ret[:]
    f_pv=Z;release=[]
    for t in range(1,7):
        target=extra/6;interest=remaining*D('.016')*D('.78')*D('.985')
        pc=min(mother_head,target);mother_head-=pc
        claim=min(claims,D('2.6')/6,target-pc);claims-=claim;need=target-pc-claim
        declared=Z;fees=Z
        for k in range(3):
            amount=min(source_ret[k],sub_start[k]/6,nonnegative(need));source_ret[k]-=amount;declared+=amount
            fees+=amount*(D('.03') if k else Z);need-=amount
        income=declared-fees+interest
        reserve_add=min(nonnegative(D('.925637012')/2-reserve),nonnegative(income+min(retained,Z))/10)
        retained+=income-reserve_add;reserve+=reserve_add
        payment=target+interest-fees
        diversion=max(Z,need,payment-retained)
        reserve_add=min(nonnegative(D('.925637012')/2-reserve),nonnegative(diversion+min(retained,Z))/10)
        retained+=diversion-reserve_add-payment;reserve+=reserve_add;remaining-=target
        assert retained>=0 and diversion<D('1e-30')
        f_pv+=payment/(O+r)**t
        release.append({'year':t,'principal':target,'interest':interest,'claims':claim,'declared':declared,'diversion':diversion,'payment':payment,'retained':retained})
    op_tv=operating*(O+g)*(O-g/roic)/(r-g)
    terminal=(op_tv+f_pv)/share
    value=sum(row['dividend']/share/(O+r)**row['year'] for row in rows)+terminal/(O+r)**5
    return {'value':value,'terminal':terminal,'financial_bridge':f_pv,'rows':rows,'release':release}

def convert(x):
    if isinstance(x,D):return float(x)
    if isinstance(x,dict):return {k:convert(v) for k,v in x.items()}
    if isinstance(x,list):return [convert(v) for v in x]
    return x

def main():
    here=Path(__file__).resolve().parent
    independent={k:run(k) for k in ['base','core_low','export_margin_minus_100bp']}
    production=json.loads((here/'2026-Q3-output.json').read_text())
    comparison={}
    for k,ind in independent.items():
        actual=production['tests']['export_margin_minus_100bp']['full_output'] if k.startswith('export_') else production['scenarios'][k]
        diffs={}
        for a,b in zip(ind['rows'],actual['rows']):
            for field,x in a.items():
                if isinstance(x,D):diffs[f"year{a['year']}_{field}"]=float(x)-b[field]
        diffs['value']=float(ind['value'])-actual['value_per_share'];diffs['terminal']=float(ind['terminal'])-actual['terminal_per_share']
        assert max(abs(v) for v in diffs.values())<1e-10,(k,diffs)
        comparison[k]={'max_absolute_difference':max(abs(v) for v in diffs.values()),'checks':len(diffs),'all_differences':diffs}
    data={'method':'independent Decimal recurrence from literal input assumptions; production read only for end comparison','independent_results':convert(independent),'comparisons':comparison,
          'dominant_parameter_value_change':float(independent['export_margin_minus_100bp']['value']-independent['base']['value'])}
    (here/'independent-recompute-output.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(comparison,ensure_ascii=False,indent=2));print('PASS independent economic cash, parent/source and endpoint chains')
if __name__=='__main__':main()

# Transport/runtime-only lease propagation. No economic values/assertions changed.
import os as _lease_os, sys as _lease_sys, json as _lease_json, subprocess as _lease_subprocess
if _lease_sys.flags.optimize:
    raise RuntimeError('Optimization disables economic assertions; refusing execution')
_lease_spec=_lease_json.loads(_lease_os.environ.get('TRADING_OS_LEASE_SPEC','[]'))
_lease_fds=tuple(row['fd'] for row in _lease_spec)
for _lease_row in _lease_spec:
    _lease_stat=_lease_os.fstat(_lease_row['fd'])
    if (_lease_stat.st_dev,_lease_stat.st_ino)!=(_lease_row['dev'],_lease_row['ino']) or _lease_stat.st_nlink!=1:
        raise RuntimeError('Inherited engineering lease identity changed')
if _lease_fds and not getattr(_lease_subprocess,'_q3_lease_installed',False):
    _lease_original_popen=_lease_subprocess.Popen
    def _lease_popen(*args,**kwargs):
        kwargs['pass_fds']=tuple(sorted(set(kwargs.get('pass_fds',()))|set(_lease_fds)))
        return _lease_original_popen(*args,**kwargs)
    _lease_subprocess.Popen=_lease_popen
    _lease_subprocess._q3_lease_installed=True

#!/usr/bin/env python3
"""Manual literal reconstruction. Does not import production or read its inputs/output.
Numbers transcribed from original disclosures; comparisons occur only after calculation.
"""
import json

def calculate(kind='volume',r=.095,g=.025,scale=1.,extra=0.,cycle=False,upstream=.75,parent_start=100.,parent_earn=.55,friction=.02,voluntary=0.,n_years=480,cutday=29,trade_through=29,fee_rate=.001,cancel_year=1,loan_repay=.5,loan_allowance=0.,recovery=.8,buyback=0.,buy_price=None,refinance=1.,source_profit_access=1.,employee_transfer=True,exercise=True,fund_end=11,fund_recovery=.8,matched_locked=0.,matched_unlock_year=6,matched_recovery=1.,matched_fee=0.,first_maturity=None):
    dated=[(8,.000697833,.19997683436),(15,.000689500,.19237993188),(16,.000222000,.06101918500),(19,.000186700,.04999361640),(21,.003488624,.79999853850),(22,.002271000,.49994674870),(28,.000871300,.19998299442),(29,.000233800,.05367262500)]
    active=[z for z in dated if z[0]<=min(cutday,trade_through)]
    outgoing=sum(z[2] for z in active);units=.010945162+sum(z[1] for z in active)
    fee=outgoing*fee_rate
    debtbase=39.897579+16.871100+76.354823+52.737747+4.064886
    net=369.813786+62.779978+.629346-1.646355-debtbase-90.-15.-1.632147
    missing=sum(z[2]*(cutday-z[0])/365*.02 for z in active)
    cash_a=parent_start*(1+.02*cutday/365)-outgoing-fee-missing
    cash_b=(net-parent_start)*(1+.02*cutday/365)
    retained=145.440692-4.598335875*1.411-loan_allowance
    reserve=2.313325;optreserve=0.;capitalreserve=166.987461;registered=4.627249686;issued=4.627249686
    stockcost=3.30315513838+outgoing+fee
    emp=.028319044;empbasis=6.932212;options=.000519738
    receivable=.008228;face=132.661171;impair=loan_allowance;source_re=0.
    owninvest=8.490108;otherinvest=13.148849+11.824729-owninvest
    loan_debt=debtbase;matched=debtbase
    equity=386.880990-outgoing-fee+net*.02*cutday/365-missing
    operatingcapital=386.880990-net-13.148849-11.824729
    minority_equity=36.335776;minority_cash=15.;minority_capital=21.335776
    fund=0.;commitment=.4;previous=0.;present=0.;fifth=0.;D=[];years=[]
    for t in range(1,n_years+1):
        a0,b0,ret0=cash_a,cash_b,retained
        if kind=='volume':
            if t<=5:
                normal=[78.,87.01,96.78,106.60,115.10][t-1]*scale;invest=[42.,44.,45.,46.,47.][t-1]*scale
            elif t<=10:
                gr=[.06,.05,.04,.03,.03][t-6];ret=[.16,.15,.14,.13,.12][t-6]
                normal=previous*(1+gr);invest=(normal-previous)/ret
            else:normal=previous*(1+g);invest=normal*g/.12
        else:
            normal=78.*scale if t==1 else previous*(1+(.10 if t<=5 else .03 if t<=10 else g))
            invest=normal*(.5 if t<=5 else (.03 if t<=10 else g)/.12)
        previous=normal
        if t<=5:invest+=extra
        loss=20 if cycle and t==1 else 15 if cycle and t==2 else 0
        earn=normal-loss;fcf=earn-invest
        np=earn*.07/.93;ni=(invest-(min(commitment,max(0.,invest),.4) if t==1 else 0.))*.07/.93;ny=minority_cash*.02
        nd=max(0.,np-ni+ny);minority_cash+=np-ni+ny-nd;minority_equity+=np+ny-nd;minority_capital+=ni
        previous_debt=loan_debt;previous_match=matched
        matured=min(loan_debt,(56.768679 if first_maturity is None else first_maturity) if t==1 else debtbase*.1)
        borrowing=matured*refinance;payable=matured-borrowing
        unavailable=min(matched,debtbase*matched_locked) if t<matched_unlock_year else 0.
        disposed=min(max(0.,matched-unavailable),max(0.,matched-loan_debt+payable))
        gross_match=disposed*matched_recovery;fee_match=gross_match*matched_fee
        pretax_match=gross_match-disposed-fee_match;tax_match=max(0.,pretax_match)*.25
        gain_match=pretax_match-tax_match;receipt_match=gross_match-fee_match-tax_match
        matched-=disposed;debtinterest=previous_debt*.025;matchinterest=previous_match*.025
        interest_difference=matchinterest-debtinterest;income_match=interest_difference-max(0.,interest_difference)*.20
        agross=(a0-(buyback*.25 if t==1 else 0.))*.025;bgross=b0*.025;taxa=max(0.,agross)*.2;taxb=max(0.,bgross)*.2
        ay=agross-taxa;by=bgross-taxb
        cash_a+=ay+.55*fcf;cash_b+=by+.45*fcf
        called=min(commitment,max(0.,invest),.4) if t==1 else 0.
        commitment-=called;fund+=called;operatingcapital+=invest-called
        cash_a-=called*.45;cash_b+=called*.45
        fg=ft=ff=fn=fb=0.
        if t==fund_end:
            fb=fund;gross=fund*fund_recovery;ff=gross*friction;pre=gross-fund-ff;ft=max(0.,pre)*.25
            fg=pre-ft;fn=gross-ff-ft;fund=0.;cash_a+=fn
        source_re+=.45*earn+by
        sale_a=sale_b=ga=gb=sfee=stax=0.
        if 6<=t<=10:
            sale_a=owninvest/(11-t);sale_b=otherinvest/(11-t)
            owninvest-=sale_a;otherinvest-=sale_b
            for which,cost in [('a',sale_a),('b',sale_b)]:
                gross=cost*recovery;cost_fee=gross*friction;profit=gross-cost-cost_fee;tax=max(0.,profit)*.25
                cash=gross-cost_fee-tax;sfee+=cost_fee;stax+=tax
                if which=='a':cash_a+=cash;ga=profit-tax
                else:cash_b+=cash;gb=profit-tax
            source_re+=gb
        cash_a+=(receipt_match+income_match)*.55;cash_b+=(receipt_match+income_match)*.45
        source_re+=(gain_match+income_match)*.45
        paid_a=min(payable*.55,max(0.,cash_a));paid_b=min(payable*.45,max(0.,cash_b))
        cash_a-=paid_a;cash_b-=paid_b;loan_debt-=paid_a+paid_b
        missing_debt=payable-paid_a-paid_b
        if missing_debt>1e-7:
            lp=parent_earn*earn+ay+ga+fg+(gain_match+income_match)*.55
            available=max(0.,lp+min(0.,retained));stat=min(available*.1,max(0.,registered*.5-reserve));opt=available*voluntary
            state=dict(year=t,operating_profit=earn,reinvestment=invest,opening_debt_face=previous_debt,scheduled_maturity=matured,new_borrowing=borrowing,net_debt_due=payable,actual_parent_principal_paid=paid_a,actual_source_principal_paid=paid_b,unpaid_principal=missing_debt,debt_face=loan_debt,parent_cash=cash_a,source_cash=cash_b,matched_remaining_cost=matched,matched_remaining_tax_basis=matched,matched_restricted_cost=unavailable,matched_disposed_basis=disposed,matched_gross_proceeds=gross_match,matched_realisation_expense=fee_match,matched_realisation_tax=tax_match,matched_realised_gain_after_tax=gain_match,matched_interest_net=income_match,parent_legal_profit=lp,parent_retained=retained+lp-stat-opt,parent_statutory_reserve=reserve+stat,parent_optional_reserve=optreserve+opt,source_budget_retained=source_re,internal_loan_face=face,internal_loan_allowance=impair,dividend_receivable=receivable,remaining_parent_financial_cost=owninvest,remaining_source_financial_cost=otherinvest,fund_cost=fund,common_operating_capital=operatingcapital,common_equity=equity+earn+ay+by+ga+gb+fg+gain_match+income_match,nci_cash=minority_cash,nci_equity=minority_equity,dividend=0.,necessary_operating_liquidity=90.)
            return dict(feasible=False,PV=None,TV5=None,D=D,rows=years,tail_PV_upper_bound=None,failure_state=state)
        principal=min(face,max(0.,cash_b-receivable)*loan_repay) if t>=6 else 0.
        face-=principal;cash_b-=principal;cash_a+=principal
        reversed_impairment=min(impair,principal);impair-=reversed_impairment
        proposed=max(0.,.22*earn if t<=5 else cash_b-receivable)
        declared=min(proposed,max(0.,source_re)*source_profit_access,max(0.,cash_b-receivable))
        source_re-=declared;receivable+=declared
        received=min(max(0.,cash_b),receivable*(upstream if t<=5 else 1.))
        cash_b-=received;cash_a+=received;receivable-=received
        legal=parent_earn*earn+ay+declared+ga+reversed_impairment+fg+(gain_match+income_match)*.55
        base=max(0.,legal+min(0.,retained));required=min(base*.1,max(0.,registered*.5-reserve));optional=base*voluntary
        retained+=legal-required-optional;reserve+=required;optreserve+=optional
        bought=costbuy=feebuy=cancel=ret_charge=0.
        if t==1 and buyback:
            costbuy=buyback;feebuy=buyback*fee_rate;bought=buyback/buy_price
            if cash_a<costbuy+feebuy:return {'feasible':False,'PV':None,'TV5':None,'D':D,'rows':years}
            cash_a-=costbuy+feebuy;units+=bought;stockcost+=costbuy+feebuy
        if t==cancel_year:
            cancel=units;issued-=cancel;registered-=cancel
            premium=max(0.,stockcost-cancel);used=min(capitalreserve,premium);capitalreserve-=used
            ret_charge=premium-used;retained-=ret_charge;units=0.;stockcost=0.
        transferred=emp_cash=emp_cost=option_issue=option_cash=0.
        if employee_transfer and t<=5:
            transferred=min(emp,.008081586 if t==1 else emp/(6-t));emp_cost=empbasis*transferred/emp if emp else 0.
            emp_cash=transferred*158.42;emp-=transferred;empbasis-=emp_cost
            cash_a+=emp_cash;capitalreserve+=emp_cash-emp_cost
        if exercise and t==1:
            option_issue=options;options=0.;option_cash=option_issue*(15854459.09/56437)
            cash_a+=option_cash;issued+=option_issue;registered+=option_issue;capitalreserve+=option_cash-option_issue
        diluted=issued-units+options;eligible=issued-units-emp
        target=[8.5,9.5,10.5,12.,13.][t-1]*eligible if t<=5 else max(0.,fcf+ay+by)+max(0.,a0+b0)/5
        pay=min(max(0.,target),max(0.,cash_a),max(0.,retained))
        cash_a-=pay;retained-=pay;each=pay/eligible
        equity+=earn+ay+by+ga+gb+fg+gain_match+income_match-pay-costbuy-feebuy+emp_cash+option_cash
        if min(cash_a,cash_b,minority_cash)<-1e-7:return {'feasible':False,'PV':None,'TV5':None,'D':D,'rows':years}
        present+=each/(1+r)**t
        if t>5:fifth+=each/(1+r)**(t-5)
        else:D.append(each)
        years.append(dict(year=t,normal_operating_profit=normal,operating_profit=earn,reinvestment=invest,cycle_loss=loss,common_owner_cash=fcf,opening_parent_cash=a0,opening_source_cash=b0,
          parent_interest_gross=agross,source_interest_gross=bgross,financial_income_tax=taxa+taxb,parent_own_cash=.55*fcf-called*.45,source_own_cash=.45*fcf+called*.45,source_profit=.45*earn,source_budget_retained=source_re,source_restricted_budget=0.,
          opening_parent_retained=ret0,parent_legal_profit=legal,new_dividend_declaration=declared,dividend_receipt=received,dividend_receivable=receivable,statutory_addition=required,voluntary_addition=optional,parent_statutory_reserve=reserve,parent_optional_reserve=optreserve,parent_retained=retained,
          loan_face=face,loan_allowance=impair,loan_carrying=face-impair,loan_repayment=principal,loan_allowance_reversal=reversed_impairment,internal_debt=face,parent_subsidiary_cost=105.393005,parent_subsidiary_impairment=6.669403,parent_subsidiary_carrying=98.723602,
          financial_cost_sold=sale_a+sale_b,financial_gross_proceeds=(sale_a+sale_b)*recovery,financial_gain=ga+gb,financial_sale_tax=stax,financial_sale_cost=sfee,
          fund_call=called,fund_uncalled=commitment,fund_remaining_cost=fund,fund_sale_basis=fb,fund_net_receipt=fn,fund_sale_gain=fg,fund_sale_fee=ff,fund_sale_tax=ft,remaining_parent_financial_cost=owninvest,remaining_source_financial_cost=otherinvest,
          registered=registered,issued=issued,employee_transfer_quantity=transferred,employee_transfer_receipt=emp_cash,employee_transfer_cost=emp_cost,remaining_employee_treasury_cost=empbasis,option_issue=option_issue,option_exercise_receipt=option_cash,
          repurchased_uncancelled=units,employee_treasury_legal=emp,option_claims=options,effective_dividend_budget_shares=eligible,diluted_economic_shares=diluted,cancelled=cancel,repurchase_cash=costbuy,repurchase_fee=feebuy,parent_capital_reserve=capitalreserve,cancellation_retained_charge=ret_charge,
          dividend=pay,dps=each,desired_dividend=target,dividend_shortfall=max(0.,target-pay),parent_cash=cash_a,source_cash=cash_b,common_financial_cash=cash_a+cash_b,matched_opening_cost=previous_match,matched_remaining_tax_basis=matched,matched_restricted_cost=unavailable,matched_disposed_basis=disposed,matched_gross_proceeds=gross_match,matched_realisation_expense=fee_match,matched_realisation_tax=tax_match,matched_realised_gain_after_tax=gain_match,matched_interest_net=income_match,parent_debt_face=loan_debt*.55,source_debt_face=loan_debt*.45,parent_matched_cost=matched*.55,source_matched_cost=matched*.45,actual_parent_principal_paid=paid_a,actual_source_principal_paid=paid_b,net_debt_due=payable,unpaid_principal=missing_debt,debt_face=loan_debt,debt_repayment=matured,new_borrowing=borrowing,matched_financial_asset=matched,debt_interest=debtinterest,matched_asset_income=matchinterest,
          necessary_operating_liquidity=90.,capital_payable=1.632147,capital_payable_matched_cash=1.632147,nci_profit=np,nci_reinvestment=ni,nci_distribution=nd,nci_cash=minority_cash,nci_equity=minority_equity,nci_operating_capital=minority_capital,common_operating_capital=operatingcapital,common_equity=equity,
          group_gross_liquidity=cash_a+cash_b+matched+90+15+1.632147,pv_distribution=each/(1+r)**t))
    bound=(max(0.,normal)*(1+g)/(r-g)+max(0.,cash_a+cash_b)+owninvest+otherinvest+fund+max(0.,matched-loan_debt))/max(1e-9,diluted)/(1+r)**len(years)
    return dict(PV=present,TV5=fifth,D=D,feasible=True,rows=years,tail_PV_upper_bound=bound)

CASES={'financing_delay':{'refinance':0.,'matched_locked':.8,'matched_unlock_year':6,'matched_recovery':.8,'matched_fee':.02},'financing_distribution_cut':{'refinance':0.,'matched_locked':.8,'matched_unlock_year':6,'matched_recovery':.8,'matched_fee':.02,'first_maturity':130.},'financing_failure':{'refinance':0.,'matched_locked':1.,'matched_unlock_year':6,'first_maturity':189.926135},'base':{},'core_low':{'r':.10,'g':.02},'core_high':{'r':.09,'g':.03},'cycle':{'cycle':True},'structural':{'r':.105,'g':.015,'scale':.70,'extra':10},'optimistic':{'r':.09,'g':.03,'scale':1.15},'capital_plus10':{'extra':10},'upstream_stress':{'parent_start':40,'upstream':.25,'source_profit_access':.5},'loan_slow':{'loan_repay':.10},'loan_not_repaid':{'loan_repay':0.},'loan_allowance':{'loan_allowance':.473575},'fees_30bp':{'fee_rate':.003},'no_refinancing':{'refinance':0},'reserve_10pct':{'voluntary':.10},'sale_recovery60':{'recovery':.60},'fund_delay_loss':{'fund_end':14,'fund_recovery':0.},'cancellation_delayed':{'cancel_year':3},'no_future_incentive_settlement':{'employee_transfer':False,'exercise':False},'pre_last_trade':{'trade_through':28},'old_fact_same_date':{'trade_through':0},'september_cutoff':{'cutday':0}}
def main():
    out={}
    for kind in ['volume','earnings']:
        results={k:calculate(kind=kind,**v) for k,v in CASES.items()}
        v=results['base'];reference=v['PV']*1.095-v['D'][0]
        remain=20-3.30315513838-sum([.19997683436,.19237993188,.061019185,.0499936164,.7999985385,.4999467487,.19998299442,.053672625])
        for ratio in [.8,1.,1.2]:results['conditional_repurchase_'+str(ratio)]=calculate(kind=kind,buyback=remain,buy_price=reference*ratio)
        results['tail240']=calculate(kind=kind,n_years=240)
        out[kind]=results
    print(json.dumps(out,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()

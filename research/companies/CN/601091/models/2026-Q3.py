#!/usr/bin/env python3
"""沈鼓独立年度预算。Python stdlib; all literals embedded; CNY bn, shares bn.
Accounts are explicit modeled payout sources, NOT purported unpublished legal statements.
300 complete rolling 12-month years: numerical horizon, not a promised corporate life.
"""
import json, math
from copy import deepcopy
SHARES=3.110002589
OWN={'P':1.,'T':.868041,'W':.868041*.45,'A':.868041,'N':1.,'E':1.}
CAP={'P':3.110002589,'T':.20855,'W':.2,'A':.05,'N':1.337711799,'E':.1}
CASH={'P':1.5,'T':3.4,'W':.3,'A':.5,'N':.5,'E':.84007771304}
RE={'P':.295361896472,'T':.8,'W':.1,'A':.25,'N':-.98,'E':.15}
RES={'P':.030272963548,'T':.05,'W':.01,'A':.025,'N':0.,'E':.01}
FLOOR={'P':.25,'T':2.5,'W':.25,'A':.3,'N':.35,'E':.4}
# Absolute source-currency values scaled to bn, not supplied through external files.
FACTS={'q3_revenue':7.56210751432,'q3_cost':5.87688469779,'q3_parent_np':.49446884269,
'q3_adjusted_np':.43624041201,'q3_ocf':-.87154048601,'q3_capex':.08937849339,
'q3_cash':7.04007771304,'q3_cash_equivalents':6.36895388378,'q3_common_equity':7.10967444401,
'q3_minority_equity':.67573196051,'q3_contract_liabilities':10.6008737759,
'q3_receivables':3.90745643845,'q3_inventory':8.50444420611,'q3_contract_assets':1.01449937998,
'q3_payables':5.67544772039,'q3_notes_payable':2.29248198048,'q3_longterm_employees':.18024890961,
'q3_lease_noncurrent':.00683172665,'q3_current_noncurrent_due':.04152088481,
'h1_parent_cash_equiv':.26747349824,'h1_parent_re':.31328936834,'h1_parent_reserve':.01234549168,
'h1_parent_np':.17927471868,'h1_parent_dividend_receivable':.12980772723,
'h1_parent_investment_income_cash':.06880116279,'h1_parent_ocf':-.12167092088,
'fy_parent_dividend_investment_income':.13339090162,'fy_parent_total_investment_income':.17467060253,
'fy_parent_investment_income_cash':.1157358,'fy_parent_np':.1234549168,
'fy_parent_re':.13401464966,'fy_parent_reserve':.01234549168,
'fy_nuclear_equity':.3969467,'fy_nuclear_registered_capital':1.337711799,'fy_nuclear_np':.0083236,
'fy_turbine_group_np':.51466586599,'fy_recip_np':.0656272,'fy_service_np':.123198,
'fy_export_np':.1207526,'state_exclusive_capital':.0886183,'ipo_net_proceeds':1.2606165,
'project_total':2.1988717,'historic_parent_loan_yingkou':.80178639268,
'historic_parent_cost_nuclear':1.415143,'historic_parent_loan_nuclear':.06154493196}
STATE=.0886183
N=300

def reserve_step(re,res,capital,profit):
    # loss-first: only profit left AFTER offsetting opening accumulated losses is eligible.
    restored=min(max(profit,0.),max(-re,0.))
    contribution=min(max(0.,profit-restored)*.10,max(0.,capital*.5-res))
    return re+profit-contribution,res+contribution,contribution,restored

def payment(re,res,capital,profit,cash,floor,request):
    r,s,added,lossfilled=reserve_step(re,res,capital,profit)
    paid=max(0.,min(request,max(r,0.),max(cash-floor,0.)))
    return {'re':r-paid,'reserve':s,'appropriation':added,'loss_offset':lossfilled,'paid':paid,'cash':cash-paid}

def simulate(kind='base',after5=None,re_bound='base',cash_scale=1.,rate=.095,margin_shift=0.,parent_cash_shift=0.,rd_expense_fraction=.5,prior_project_credit=.0626394,impairment=0.,payout_delay=0,horizon=300):
    cash=deepcopy(CASH);re=deepcopy(RE);res=deepcopy(RES);loans={k:0. for k in CASH};loans['N']=.06154493196
    # Redistribute within observed group cash, not conjure new financing.
    cash['P']+=parent_cash_shift;cash['T']-=parent_cash_shift
    if re_bound=='low':
        re.update(T=0.,W=0.,A=0.,E=0.,N=-1.10,P=.20);res.update(T=0.,W=0.,A=0.,E=0.,N=0.,P=.01234549168)
    if re_bound=='high':
        re.update(T=1.5,W=.1599257,A=.322686,E=.209542,N=-.940765099,P=.45)
        res.update(T=.104275,W=.1,A=.025,E=.05,N=0.)
    common=FACTS['q3_common_equity']-STATE;minority=FACTS['q3_minority_equity'];netcapital=common+minority+STATE-sum(cash.values())
    parent_ar=.12168522723 # H1 declared net balance above legacy external AR; Q3 timing uncertain, sensitivity below.
    # This is already P income. It is a matching T payable; receipt never re-enters profit.
    debt=0.;rows=[];previous_rev={'T':6.187,'W':.943,'A':1.636,'N':1.081,'E':.941,'P':.333}
    new_asset={k:0. for k in CASH}
    for y in range(1,horizon+1):
        path=kind if y<=5 or after5 is None else after5
        oldcash=sum(cash.values());oldcommon=common;oldminority=minority;oldcapital=netcapital;olddebt=debt
        if y<=5:
            growth=(1.035**(y-1)); fade=1.
        elif y<=10:
            growth=1.035**4*1.025**(y-5);fade=1.
        else:
            growth=1.035**4*1.025**5*1.01**(y-10);fade=1.
        rev={'T':6.65*growth,'W':.96*growth,'A':1.70*growth,'N':1.13*growth,'E':1.00*growth,'P':.34*growth}
        # E is the export transfer-margin source: its revenue is a subset, not added to consolidated sales.
        margins={'T':.062,'W':.07,'A':.088,'N':.025,'E':.12,'P':-.28}
        if path=='cyclical':
            f={1:.86,2:.9,3:.96}.get(y,1.);rev={k:v*f for k,v in rev.items()}
            if y<=3:margins={k:v-(.012 if k!='P' else .025) for k,v in margins.items()}
        if path=='structural':
            rev={k:v*(.88 if k!='A' else .97) for k,v in rev.items()}
            margins.update(T=.039,W=.045,A=.069,N=.010,E=.07,P=-.32)
        if path=='optimistic':
            rev={k:v*(1.03**min(y,8)) for k,v in rev.items()};margins.update(T=.071,W=.08,A=.095,N=.045,E=.14)
        if path=='continuation_low':
            margins={k:v-(.004 if k!='P' else .01) for k,v in margins.items()}
        if path=='continuation_high':
            margins={k:v+(.004 if k!='P' else .01) for k,v in margins.items()}
        if path=='auxiliary':
            # Independent normalized earnings/capital route: peer equipment margin contraction;
            # lower sales but no extrapolation of company's 2025 unusually high export mix.
            rev={k:v*growth for k,v in {'T':6.30,'W':.94,'A':1.64,'N':1.08,'E':.94,'P':.33}.items()};margins.update(T=.059,W=.065,A=.087,N=.021,E=.115,P=-.28)
        for k in margins:
            if k!='P':margins[k]+=margin_shift
        floor={k:FLOOR[k]*(rev[k]/({'T':6.65,'W':.96,'A':1.7,'N':1.13,'E':1.,'P':.34}[k]))*cash_scale for k in CASH}
        floor['P']+=STATE
        # Floor includes bill/bond collateral and invoice/payroll seasonality. No second debt haircut.
        rd={'P':.25337*rd_expense_fraction/4 if y<=4 else 0.,'T':.56678*rd_expense_fraction/4 if y<=4 else 0.,'W':0.,'A':0.,'N':0.,'E':0.}
        # Actual project entity, 36/48-month schedules; credit already capitalized 2025 works.
        credit_p=prior_project_credit*(.0352703/.0626394)
        credit_n=prior_project_credit*(.0273691/.0626394)
        project={'P':(.25337*(1-rd_expense_fraction)+.2693959-credit_p)/4 if y<=4 else 0.,
                 'T':(.8213258/3 if y<=3 else 0.)+(.56678*(1-rd_expense_fraction)+.135)/4*(y<=4),
                 'N':(.153-credit_n)/3 if y<=3 else 0.,'W':0.,'A':0.,'E':0.}
        dep={};capex={};wc={};external={};funding={k:0. for k in CASH};repay={k:0. for k in CASH}
        for k in CASH:
            maintenance=({'P':.025,'T':.10,'W':.02,'A':.025,'N':.035,'E':.005}[k])*growth
            # Legacy and commissioned capacity maintained indefinitely; new depreciation is not free FCF.
            if path=='auxiliary':maintenance*=1.1
            dep[k]=maintenance+new_asset[k]/12
            capex[k]=dep[k]+project[k]
            new_asset[k]+=project[k]
            wc_weights=({'P':.05,'T':.10,'W':.14,'A':.12,'N':.30,'E':.30} if path=='auxiliary' else {'P':.05,'T':.08,'W':.12,'A':.12,'N':.25,'E':.25})
            wc[k]=(rev[k]-previous_rev[k])*wc_weights[k]
            # Collection shock is released by actual following-year recoveries, not terminal cancellation.
            delays={1:.35,2:.15,3:-.25,4:-.25} if path=='cyclical' else ({1:.25,2:.15} if path=='structural' else {1:.12,2:-.06,3:-.06})
            wc[k]+=delays.get(y,0.)*({'T':.6,'E':.3,'N':.1}.get(k,0.))
            # Run down opening liabilities once, not a second net-cash subtraction.
            legacy_payment=(.04152088481*(y==1)+.00683172665/4*(y<=4)+.04447081124/5*(y<=5)+.18024890961/15*(y<=15))
            wc[k]+=legacy_payment*({'P':.3,'T':.7}.get(k,0.))
            # Deposit income only on funds above operating minimum; no standalone cash add-back.
            deposit=max(cash[k]-floor[k],0.)*.012
            external[k]=rev[k]*margins[k]-rd[k]*.85+deposit
        loan_interest={k:loans[k]*.03 for k in CASH}
        for k in ('T','W','A','N','E'):
            external[k]-=loan_interest[k];external['P']+=loan_interest[k]
        external['P']-=debt*.05
        noncash_impairment=impairment if y==1 else 0.
        external['P']-=noncash_impairment
        for k in CASH:cash[k]+=external[k]+dep[k]-capex[k]-wc[k]
        cash['P']+=noncash_impairment
        # Loans: projected ordinary related-party funding, NOT completed capital increases; ownership fixed.
        for k in ('T','W','A','N','E'):
            need=max(floor[k]-cash[k],0.)
            if need:cash[k]+=need;cash['P']-=need;loans[k]+=need;funding[k]=need
            repay[k]=min(loans[k],max(cash[k]-floor[k],0.)*.5)
            cash[k]-=repay[k];cash['P']+=repay[k];loans[k]-=repay[k]
        assert sum(loans.values())<=.25+1e-9, 'Internal funding budget exhausted'
        borrowing=0.;repaid_external=0.
        oldreceipt=0.
        if y==1:
            oldreceipt=min(parent_ar,max(cash['T']-floor['T'],0.));cash['T']-=oldreceipt;cash['P']+=oldreceipt;parent_ar-=oldreceipt
        elif parent_ar>0:
            oldreceipt=min(parent_ar,max(cash['T']-floor['T'],0.));cash['T']-=oldreceipt;cash['P']+=oldreceipt;parent_ar-=oldreceipt
        # Complete actual cash upstream in same budget year; declared and cash fields remain distinct.
        legal_profit=deepcopy(external);paid={};appropriations={};loss_offsets={};begin_re=deepcopy(re);begin_res=deepcopy(res)
        for k in ('W','A','N','E','T','P'):
            if k=='P':
                borrowing=max(floor['P']-cash['P'],0.)
                assert borrowing<1e-9, 'No assumed external financing authority/capacity'
                debt+=borrowing;cash['P']+=borrowing
                repaid_external=min(debt,max(cash['P']-floor['P'],0.));debt-=repaid_external;cash['P']-=repaid_external
                econ=max(sum(external[z]*OWN[z] for z in CASH),0.)
                request=econ*[.1,.15,.2,.25,.30][y-1] if y<=5 else max(cash[k]-floor[k],0.)*min(1.,max(.1,.4+.15*(y-6-payout_delay)))
                if debt>1e-10:request=0.
            else:request=max(cash[k]-floor[k],0.)*(.30 if y<=5 else min(1.,max(.3,.45+.15*(y-6-payout_delay))))
            q=payment(re[k],res[k],CAP[k],legal_profit[k],cash[k],floor[k],request)
            re[k]=q['re'];res[k]=q['reserve'];cash[k]=q['cash'];paid[k]=q['paid'];appropriations[k]=q['appropriation'];loss_offsets[k]=q['loss_offset']
            if k in ('W','A'):
                frac=.45 if k=='W' else 1.;cash['T']+=paid[k]*frac;legal_profit['T']+=paid[k]*frac
            elif k in ('N','E','T'):
                frac=.868041 if k=='T' else 1.;cash['P']+=paid[k]*frac;legal_profit['P']+=paid[k]*frac
        group_profit=sum(external.values());ordinary_profit=sum(external[k]*OWN[k] for k in CASH)
        # Small residual/noncore operations sit in parent-source net margin, not extra net-asset value.
        minority_paid=paid['W']*.55+paid['T']*(1-.868041)
        common+=ordinary_profit-paid['P'];minority+=group_profit-ordinary_profit-minority_paid
        netcapital+=sum(capex.values())-sum(dep.values())+sum(wc.values())-noncash_impairment
        assert abs(sum(cash.values())-(oldcash+group_profit+noncash_impairment+sum(dep.values())-sum(capex.values())-sum(wc.values())-paid['P']-minority_paid+debt-olddebt))<1e-7*max(1.,sum(cash.values()))
        assert abs(sum(cash.values())+netcapital-debt-(common+minority+STATE))<1e-7*max(1.,abs(common))
        assert abs(common-(oldcommon+ordinary_profit-paid['P']))<1e-9*max(1.,abs(common))
        for k in CASH:
            assert cash[k]>=floor[k]-1e-8
            assert abs(re[k]-(begin_re[k]+legal_profit[k]-appropriations[k]-paid[k]))<1e-8*max(1.,abs(re[k]))
            assert res[k]<=CAP[k]*.5+1e-8 and paid[k]>=0
        row={'year':y,'period_start_year':2025+y,'period_end_year':2026+y,'path':path,'revenue_sources':rev,
             'consolidated_sales_proxy':sum(v for k,v in rev.items() if k!='E'),'normalized_external_net_profit':external,
             'project_incremental_rd_pretax':rd,'capex':capex,'depreciation':dep,'change_working_capital':wc,
             'legal_profit_including_new_declarations':legal_profit,'opening_re':begin_re,'opening_reserve':begin_res,
             'reserve_appropriation':appropriations,'loss_offset':loss_offsets,'actual_paid':paid,
             'legacy_dividend_principal_received':oldreceipt,'legacy_dividend_receivable_end':parent_ar,
             'cash_end':deepcopy(cash),'operating_cash_floor':floor,'re_end':deepcopy(re),'reserve_end':deepcopy(res),
             'internal_loans_end':deepcopy(loans),'new_internal_loans':funding,'loan_principal_repayment':repay,
             'noncash_asset_impairment':noncash_impairment,'external_debt_end':debt,'external_borrowing':borrowing,'external_principal_repayment':repaid_external,
             'ordinary_profit':ordinary_profit,'minority_profit':group_profit-ordinary_profit,'minority_paid':minority_paid,
             'ordinary_equity_open':oldcommon,'ordinary_equity_end':common,'minority_equity_end':minority,
             'net_non_cash_operating_capital_end':netcapital,'dividend_per_share':paid['P']/SHARES,
             'residual_income':ordinary_profit-rate*oldcommon,'fully_diluted_shares':SHARES}
        rows.append(row);previous_rev=rev
    # Numerical stationary tail: every entity remains operating, maintains capacity and pays legally.
    g=.01
    ratios=[rows[-i]['dividend_per_share']/rows[-i-1]['dividend_per_share'] for i in range(1,5)]
    assert max(abs(x-(1+g)) for x in ratios)<1e-6,ratios
    assert rows[-1]['external_debt_end']<1e-7
    # Affine growing balances: fixed historical capital/reserves remain fixed, not forced to grow.
    errors={}
    for field in ('cash_end','re_end','operating_cash_floor','change_working_capital','ordinary_equity_end','minority_equity_end','net_non_cash_operating_capital_end'):
        end=rows[-1][field];keys=end.keys() if isinstance(end,dict) else (None,)
        for key in keys:
            seq=[z[field][key] if key is not None else z[field] for z in rows[-4:]]
            d=[seq[i+1]-seq[i] for i in range(3)]
            error=max(abs(d[i+1]-1.01*d[i])/max(1.,abs(d[i+1])) for i in range(2))
            errors[field+':'+str(key)]=error
            assert error<1e-7,(field,key,error)
    for k in CASH:
        assert abs(rows[-1]['reserve_end'][k]-rows[-2]['reserve_end'][k])<1e-9
        assert rows[-1]['internal_loans_end'][k]<1e-9
    assert rows[-1]['legacy_dividend_receivable_end']<1e-9
    tail=rows[-1]['dividend_per_share']*(1+g)/(rate-g)
    dcf=sum(r['dividend_per_share']/(1+rate)**r['year'] for r in rows)+tail/(1+rate)**horizon
    tv5=sum(r['dividend_per_share']/(1+rate)**(r['year']-5) for r in rows[5:])+tail/(1+rate)**(horizon-5)
    pv5=sum(r['dividend_per_share']/(1+rate)**r['year'] for r in rows[:5])
    ri=(FACTS['q3_common_equity']-STATE+sum(r['residual_income']/(1+rate)**r['year'] for r in rows))/SHARES
    ri_tail_correction=(tail-rows[-1]['ordinary_equity_end']/SHARES)/(1+rate)**horizon
    assert abs(ri+ri_tail_correction-dcf)<1e-8
    assert abs(pv5+tv5/(1+rate)**5-dcf)<1e-10
    return {'parameters':{'kind':kind,'after5':after5,'re_bound':re_bound,'cash_scale':cash_scale,'discount_rate':rate,'margin_shift':margin_shift,'parent_cash_shift':parent_cash_shift,'rd_expense_fraction':rd_expense_fraction,'prior_project_credit':prior_project_credit,'impairment':impairment,'payout_delay':payout_delay},
            'terminal_state_convergence_errors':errors,'horizon_years':horizon,'value':dcf,'year5_terminal':tv5,'pv_first5':pv5,'tv_present_value_share':1-pv5/dcf,
            'residual_income_value':ri+ri_tail_correction,'numerical_tail_pv':tail/(1+rate)**horizon,
            'first5':[r['dividend_per_share'] for r in rows[:5]],'years':rows}

def fixtures():
    # All fixtures call the PRODUCTION functions, literal expectations independently calculated.
    a=payment(-10,1,100,6,20,3,50);assert a['paid']==0 and a['re']==-4 and a['reserve']==1
    b=payment(-10,1,100,16,20,3,50);assert abs(b['paid']-5.4)<1e-12 and abs(b['reserve']-1.6)<1e-12
    c=payment(0,49,100,30,40,5,99);assert c['paid']==29 and c['reserve']==50
    d=payment(20,0,100,0,2,1,10);assert d['paid']==1 and d['re']==19
    e=payment(.13401464966,.01234549168,3.110002589,.17927471868,.26747349824,.25,1.)
    assert abs(e['paid']-.01747349824)<1e-12
    assert abs(e['appropriation']-.017927471868)<1e-12
    assert abs(.868041*.45-.39061845)<1e-12
    assert abs((1-.868041)+.868041-1)<1e-12
    assert abs(FACTS['q3_cash']-FACTS['q3_cash_equivalents']-.67112382926)<1e-12
    return {'production_loss_first':True,'reserve_50pct_cap':True,'cash_not_re':True,'actual_parent_scaled_fixture':e,'recip_economic_ownership':.39061845}

def main():
    cases={
      'base':simulate(),
      'core_low':simulate(after5='continuation_low',rate=.10),
      'core_high':simulate(after5='continuation_high',rate=.09),
      'cyclical':simulate('cyclical'),
      'structural':simulate('structural'),
      'optimistic':simulate('optimistic'),
      'auxiliary_normalized_capital':simulate('auxiliary'),
      'legal_capacity_low':simulate(re_bound='low'),
      'legal_capacity_high':simulate(re_bound='high'),
      'cash_floor_plus25pct':simulate(cash_scale=1.25),
      'cash_floor_minus15pct':simulate(cash_scale=.85),
      'margin_minus1pp':simulate(margin_shift=-.01),
      'parent_cash_minus_300m':simulate(parent_cash_shift=-.3),
      'rd_expense_70pct':simulate(rd_expense_fraction=.7),
      'prior_project_credit_zero':simulate(prior_project_credit=0.),
      'idle_assets_impairment_400m':simulate(impairment=.4),
      'payout_normalization_delay5':simulate(payout_delay=5)}
    for name,case in cases.items():
        params=dict(case['parameters']);params['rate']=params.pop('discount_rate')
        longer=simulate(**params,horizon=500)
        error=abs(longer['value']-case['value'])
        assert error<1e-8
        case['horizon_500_value']=longer['value'];case['horizon_300_500_absolute_difference']=error
    for k in ('core_low','core_high'):
        # Same complete base Y5 state; only discount rate and post-Y5 future differ.
        assert cases[k]['first5']==cases['base']['first5']
        for field in ('cash_end','re_end','reserve_end','internal_loans_end','ordinary_equity_end','minority_equity_end'):
            assert cases[k]['years'][4][field]==cases['base']['years'][4][field]
    result={'currency':'CNY','amount_unit':'CNY billion','shares_unit':'billion','model_as_of':'2026-10-28T16:16:00+00:00',
      'annual_period':'October 29 to following October 28; each row is a complete prospective 12 months',
      'source_facts':FACTS,'entity_name':{'P':'沈鼓集团母公司净来源（含小额组合净贡献）','T':'沈阳透平本部','W':'沈鼓往复机','A':'沈鼓安检','N':'沈鼓核电泵业','E':'沈鼓进出口'},
      'ownership':OWN,'registered_capital':CAP,'opening_cash_estimates':CASH,'opening_re_estimates':RE,
      'opening_reserve_estimates':RES,'tests':fixtures(),'cases':cases}
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()

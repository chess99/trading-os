"""Supor; CNY billion and billion shares; no market price input. Python standard library."""
import json, copy, math
from pathlib import Path
CUTOFF='2026-10-26T06:00:00+00:00'
# Fully diluted forecast uses outstanding option notices; see sourcefacts.md.
BASE=dict(dom=[16*(1.025)**i for i in range(5)],exp=[7*(1.02)**i for i in range(5)],dm=[.095]*5,em=[.047]*5,capex=[.24]*5,da=[.16]*5,wc=[.06]*5,payout=.85,upstream=.90,receipt=.90,settlement=[.15]*5,opening_excess=1.60142209873-.01786188461+.0004462727,opening_parent=.50,parent_ur=1.093300754,parent_reserve=.330789524,sub_reserve_rate=.10,parent_np_ratio=.022,finance_yield=.02,debt_rate=.05,shares=.796964626,issuance=[.00102317,.0010115,.0010345,.0005215,0],issue_cash=[(.000480780*36.49+.000542390*37.89),(.000498500*37.89+.000513000*38.82),(.000513000*38.82+.000521500*31.21),(.000521500*31.21),0],options=True,terminal_roic=.25)
# Options are conditional budget, never assumed completed as of cutoff.
class ForecastRows(list):
    """Keep explicit economic inputs with this path; serialization remains a list."""
    pass

BASE.update(parent_registered_start=.799518446,parent_registered_target=.796964626,
 registered_catchup_year=1,parent_paid=.796964626,source_earnings_opening=0.,
 tail_source_buffer=0.,tail_settlement=.15,
 financing_limit=.20,tail_horizon=240)

# Tail cash realization is an ECONOMIC budget, never a synthetic法人 legal account.
# Existing source assets include cash and the mother's payable; neither creates new group cash.
BASE.update(realization_years=5,realization_delay=0,buffer_maturity=10,
 source_legacy_capacity=None,legacy_capacity_ratio=1.,capital_gross=0.,capital_year=8,
 capital_fee=.02,capital_tax_rate=.25,capital_tax_basis=.15,release_fee=0.,
 injections=[],strict_realization=True,legacy_realization_friction=0.,remittance_tax_rate=0.)

class RealizationError(ValueError):pass

def capital_return(gross,registered,book_cost,tax_basis,fee_rate,tax_rate,ownership=1.):
    """Conditional pro-rata paid capital cancellation; no approval/transaction fact asserted.
    gross is total company return and equal nominal cancelled capital in this diagnostic.
    Parent's ownership percentage is unchanged, but nominal units and investment basis shrink.
    """
    if not (0<=gross<=registered and 0<=ownership<=1 and 0<=tax_basis):
        raise ValueError('capital return exceeds real nominal capital or invalid rights')
    fraction=gross/registered if registered else 0.
    book_reduction=book_cost*fraction*ownership
    received=gross*ownership;fee=received*fee_rate
    tax=max(0.,received-tax_basis)*tax_rate
    return dict(gross=received,fee=fee,tax=tax,net_cash=received-fee-tax,
      book_cost_reduction=book_reduction,book_gain=received-book_reduction,
      parent_legal_gain=received-book_reduction-fee-tax,
      remaining_registered=registered-gross,remaining_nominal_units=registered-gross,
      ownership=ownership,minority_gross=gross*(1-ownership))

def forecast(a,years=5,g=.02,roic=.25):
    p=a['opening_parent'];s=a['opening_excess']-p;ur=a['parent_ur'];res=a['parent_reserve']
    ic=2.451173958;rec=0.;subur=a['source_earnings_opening'];debt=0.
    equity=5.459076363+.0004462727;shares=a['shares'];registered=a['parent_registered_start'];paid=a['parent_paid']
    rows=ForecastRows();rows.assumptions=copy.deepcopy(a)
    legacy_capacity=a.get('source_legacy_capacity')
    if legacy_capacity is None:legacy_capacity=(a['opening_excess']-p+ic)*a.get('legacy_capacity_ratio',1.)
    legacy_capacity-=a.get('capital_gross',0.)
    if legacy_capacity< -1e-12:raise ValueError('capital recovery and ordinary old capacity double count')
    buffers=[];held_source=held_parent=0.;injection_floors=[]
    child_registered=.610;child_book=.65416348354
    begin=6+a.get('realization_delay',0);length=a.get('realization_years',5);finish=begin+length-1
    for i in range(years):
        y=i+1;injected=0.
        if y==6:held_source=max(0.,s-rec);held_parent=p
        for inj in a.get('injections',[]):
            if inj['year']==y:
                amt=inj['amount'];injected+=amt
                if inj['location']=='source':s+=amt
                else:p+=amt
                # This is independently disclosed rights capacity, NOT automatic income from cash.
                capacity=inj.get('ordinary_capacity',0.)
                if capacity and inj['location']!='source':raise ValueError('cash injection is not mother legal profit')
                if y<6:legacy_capacity+=capacity
                else:subur+=capacity
                if y>=6:injection_floors.append((y,amt,inj['location']))
        equity+=injected
        start=p+s;oldrec=rec
        if y==6:
            # Capacity is an explicitly bounded forecast, not a source legal balance.
            subur+=legacy_capacity
        if i<5:
            domestic=a['dom'][i];export=a['exp'][i];op=domestic*a['dm'][i]+export*a['em'][i]
            da=a['da'][i];capex=a['capex'][i];wc=a['wc'][i];retain=capex-da+wc
        else:
            factor=(1+g)**(i-4);domestic=a['dom'][-1]*factor;export=a['exp'][-1]*factor
            op=(a['dom'][-1]*a['dm'][-1]+a['exp'][-1]*a['em'][-1])*factor
            da=a['da'][-1]*factor;retain=op*g/roic;capex=da+retain;wc=0.
        finance=start*a['finance_yield']-debt*a['debt_rate']+(a.get('restricted_interest',0.) if i<5 else 0.)
        legacy_source_fee=(held_source/length*a.get('legacy_realization_friction',0.)) if begin<=y<=finish else 0.
        legacy_parent_fee=(held_parent/length*a.get('legacy_realization_friction',0.)) if begin<=y<=finish else 0.
        profit=op+finance-legacy_source_fee-legacy_parent_fee;fcf=profit-retain
        parent_profit=op*a['parent_np_ratio']+p*a['finance_yield']-legacy_parent_fee;sub_profit=profit-parent_profit
        restored=sum(b for due,b in buffers if due==y);subur+=restored
        eligible=max(0.,min(sub_profit,subur+sub_profit))
        buffer=eligible*(a['sub_reserve_rate'] if i<10 else a['tail_source_buffer'])
        buffers.append((y+a.get('buffer_maturity',10),buffer));subur+=sub_profit-buffer
        parent_cf=parent_profit-retain*a['parent_np_ratio'];sub_cf=fcf-parent_cf
        issue=a['issuance'][i] if a['options'] and i<5 else 0.;proceeds=a['issue_cash'][i] if a['options'] and i<5 else 0.
        if y==a['registered_catchup_year']:registered=a['parent_registered_target']
        shares+=issue;paid+=issue;registered+=issue
        settle=min(ic,a['settlement'][i] if i<5 else a['tail_settlement']);ic-=settle
        fraction=1. if y<begin else max(0.,(finish-y)/length)
        source_floor=(held_source*fraction if y>=6 else 0.)
        parent_floor=(held_parent*fraction if y>=6 else 0.)
        for birth,amt,loc in injection_floors:
            floor=amt*max(0.,(birth+1-y)/2.)
            if loc=='source':source_floor+=floor
            else:parent_floor+=floor
        cap=dict(gross=0.,fee=0.,tax=0.,net_cash=0.,book_cost_reduction=0.,book_gain=0.,parent_legal_gain=0.,remaining_registered=child_registered,remaining_nominal_units=child_registered,ownership=1.,minority_gross=0.)
        if y==a.get('capital_year',8) and a.get('capital_gross',0.):
            cap=capital_return(a['capital_gross'],child_registered,child_book,a['capital_tax_basis'],a['capital_fee'],a['capital_tax_rate'])
            child_registered=cap['remaining_registered'];child_book-=cap['book_cost_reduction']
        available_source=max(0.,s+sub_cf+settle-oldrec-cap['gross']-source_floor)
        if i<5:
            declaration=max(0.,min(a['upstream']*max(0.,sub_profit-buffer),subur,available_source));fee=0.
        else:
            # All necessary capital is already deducted. Uncommitted surplus gets a finite
            # implementation window, not an eternal percentage-of-profit retention target.
            rate=a.get('release_fee',0.)
            declaration=max(0.,min(subur/(1+rate),available_source/(1+rate)));fee=declaration*rate
        subur-=declaration+fee
        gross_declaration=declaration
        remittance_tax=declaration*a.get('remittance_tax_rate',0.) if i>=5 else 0.
        declaration-=remittance_tax
        cash_receipt=oldrec+declaration*a['receipt'];rec=declaration*(1-a['receipt'])
        p+=parent_cf+cash_receipt+proceeds-settle+cap['net_cash']
        s+=sub_cf-cash_receipt+settle-cap['gross']-fee-remittance_tax
        legalprofit=parent_profit+declaration+cap['parent_legal_gain']
        eligible=max(0.,min(legalprofit,ur+legalprofit))
        reserve=min(eligible*.10,max(0.,registered*.5-res));res+=reserve;ur+=legalprofit-reserve
        borrow=max(0.,-(p+s))
        if debt+borrow>a['financing_limit']+1e-12:raise ValueError('finite operating funding exceeded')
        debt+=borrow;s+=borrow
        if p< -1e-9 or s< -1e-9:raise ValueError('entity cash shortfall; no automatic cross-entity cash sweep')
        target=profit*a['payout'] if i<5 else max(0.,p-parent_floor)
        div=max(0.,min(target,ur,p-parent_floor,p+s)) if debt<=0 else 0.
        p-=div;ur-=div
        economic_cost=cap['fee']+cap['tax']+fee+remittance_tax
        equity+=profit-economic_cost+proceeds-div
        assert min(p,s)>=-1e-8
        assert abs((p+s)-(start+fcf+proceeds-div+borrow-economic_cost))<1e-7
        assert abs(cash_receipt+rec-oldrec-declaration)<1e-7
        source_extra=max(0.,s-rec);mother_extra=p
        overdue=max(0.,source_extra-source_floor)+max(0.,mother_extra-parent_floor) if i>=5 else 0.
        # Source restored buffer/old capacity may be temporarily binding; don't conceal
        # material failures by letting unplanned surplus remain forever in terminal value.
        if a.get('strict_realization',True) and y>=finish+1 and overdue>1e-7:
            raise RealizationError(f'year {y}: overdue true surplus {overdue:.12g}; source economic or mother legal capacity insufficient')
        rows.append(dict(year=y,dom=domestic,export=export,operating_profit=op,financial_profit=finance,
          common_profit=profit-economic_cost,da=da,capex=capex,wc=wc,fcf=fcf-economic_cost,
          subs_profit=sub_profit-fee,subs_declaration=declaration,source_gross_declaration=gross_declaration,source_remittance_tax=remittance_tax,source_earnings_budget=subur,
          source_profit_buffer=buffer,source_buffer_restored=restored,parent_own_profit=parent_profit,
          parent_profit=legalprofit,parent_reserve=res,parent_reserve_add=reserve,parent_ur=ur,
          dividend=div,dps=div/shares,parent_cash=p,subs_cash=s,upstream_receipt=cash_receipt,
          dividend_receivable=rec,intercompany_payable=ic,settlement=settle,issuance=issue,
          issue_cash=proceeds,shares=shares,registered_capital=registered,paid_capital=paid,
          debt=debt,common_equity=equity,excess_cash=p+s,normal_settlement_cash=rec,
          true_extra_cash=source_extra+mother_extra,source_cash_floor=source_floor,
          parent_cash_floor=parent_floor,overdue_extra_cash=overdue,capital_return=cap,
          child_registered=child_registered,child_book_cost=child_book,source_transfer_fee=fee,
          economic_cost=economic_cost,legacy_source_fee=legacy_source_fee,legacy_parent_fee=legacy_parent_fee,injected_cash=injected))
    return rows

def valuation(rows,k,g,roic):
    a=rows.assumptions;future=forecast(a,a['tail_horizon'],g,roic)
    divpv=sum(x['dps']/(1+k)**x['year'] for x in future[:5])
    tv=sum(x['dps']/(1+k)**(x['year']-5) for x in future[5:]);tvpv=tv/(1+k)**5
    return dict(k=k,g=g,roic=roic,terminal_per_share=tv,current_per_share=divpv+tvpv,
      terminal_pv_ratio=tvpv/(divpv+tvpv),explicit_rows=future[:5],tail_rows=future[5:],
      terminal_method='finite economic surplus realization; actual mother legal/cash payments; no asset addback',
      max_overdue=max(x['overdue_extra_cash'] for x in future),final_true_extra=future[-1]['true_extra_cash'])

def scenario_assumptions():
    cases={'base':copy.deepcopy(BASE)}
    cyc=copy.deepcopy(BASE);cyc.update(dom=[14.8,15.5]+BASE['dom'][2:],exp=[6.2,6.5]+BASE['exp'][2:],dm=[.088,.092]+[.095]*3,em=[.035,.04]+[.047]*3,wc=[.30,.15,-.15,.06,.06],receipt=.65,settlement=[.40,.15,.15,.15,.15]);cases['cycle']=cyc
    bear=copy.deepcopy(BASE);bear.update(dom=[14.5*(.99)**i for i in range(5)],exp=[5.8*(.97)**i for i in range(5)],dm=[.07]*5,em=[.025]*5,capex=[.28]*5,wc=[.2,.15,.10,.1,.1],receipt=.60,upstream=.65,settlement=[.6,.3,.3,.3,.3],options=False,terminal_roic=.15);cases['structural']=bear
    bull=copy.deepcopy(BASE);bull.update(dom=[16.2*(1.04)**i for i in range(5)],exp=[7.3*(1.04)**i for i in range(5)],dm=[.10]*5,em=[.06]*5,capex=[.30]*5,wc=[.10]*5,receipt=.95);cases['upside']=bull
    return cases

def evaluate(a,params):
    rows=forecast(a)
    try:vals=[valuation(rows,k,g,a['terminal_roic']) for k,g in params]
    except (ValueError,AssertionError) as e:
        diagnostic=copy.deepcopy(a);diagnostic['strict_realization']=False
        samples=[]
        for k,g in params:
            try:
                rr=forecast(diagnostic,40,g,a['terminal_roic'])
                samples.append({'k':k,'g':g,'rows':rr,'max_extra':max(r['true_extra_cash'] for r in rr)})
            except (ValueError,AssertionError) as e2:samples.append({'error':str(e2)})
        return dict(status='infeasible_or_unsubstantiated_realization',reason=str(e),assumptions=a,rows=rows,diagnostic=samples,valuations=None)
    return dict(status='feasible',assumptions=a,rows=rows,valuations=vals)

def run():
    params=[(.095,.015),(.085,.02)];out={'information_cutoff':CUTOFF,'units':'CNY billion; billion shares; per-share CNY','cases':{},'sensitivities':{}}
    for name,a in scenario_assumptions().items():
        out['cases'][name]=evaluate(a,params if name!='structural' else [(.105,0),(.095,.005)])
    first=out['cases']['base']['rows'][0]
    out['auxiliary']={'method':'normalized operating owner-cash multiple plus opening surplus','low':((first['operating_profit']-.14)*13+BASE['opening_excess'])/.800555296,'high':((first['operating_profit']-.14)*16+BASE['opening_excess'])/.800555296}
    variants={
      'domestic_margin_minus_1pp':dict(dm=[x-.01 for x in BASE['dm']]),
      'no_option_exercise':dict(options=False),
      'governance_delay_3years':dict(realization_delay=3),
      'realization_8years':dict(realization_years=8),
      'realization_3years':dict(realization_years=3),
      'parent_opening_extra_cash_zero':dict(opening_parent=0.),
      'existing_acceptance_settlement_switch_year3':dict(wc=[.06,.06,.06+1.5776-(.770+.09891+.256443),.06,.06]),
      'restricted_CD_interest_2pct':dict(restricted_interest=.770*.02),
      'terminal_roic_15pct':dict(terminal_roic=.15),
      'registered_june_no_catchup':dict(registered_catchup_year=10000),
      'mother_statutory_lower_budget':dict(parent_reserve=.28337509762),
      'mother_registered_double_paid':dict(parent_registered_start=1.593929252,parent_registered_target=1.593929252),
      'source_buffer_zero':dict(sub_reserve_rate=0.,tail_source_buffer=0.),
      'source_buffer_ten_pct_rolling_10years':dict(tail_source_buffer=.10),
      'source_buffer_15year_maturity':dict(buffer_maturity=15),
      'source_profit_declaration_half_first5':dict(upstream=.45),
      'source_receipt_half':dict(receipt=.45),
      'horizon_320':dict(tail_horizon=320),
      'ordinary_old_capacity_0bn':dict(source_legacy_capacity=0.),
      'ordinary_old_capacity_0_5bn':dict(source_legacy_capacity=.5),
      'ordinary_old_capacity_1bn':dict(source_legacy_capacity=1.),
      'ordinary_old_capacity_3bn_delay3':dict(source_legacy_capacity=3.,realization_delay=3),
      'ordinary_old_capacity_2bn_delay3_release8':dict(source_legacy_capacity=2.,realization_delay=3,realization_years=8),
      'conditional_shaoxing_capital_return':dict(capital_gross=.2),
      'conditional_capital_tax_basis_zero':dict(capital_gross=.2,capital_tax_basis=0.),
      'conditional_capital_tax_basis_0_1bn':dict(capital_gross=.2,capital_tax_basis=.1),
      'old_surplus_realization_friction_5pct':dict(legacy_realization_friction=.05),
      'old_surplus_realization_friction_15pct':dict(legacy_realization_friction=.15),
      'source_remittance_effective_tax_2pct':dict(remittance_tax_rate=.02),
      'capital_not_approved_ordinary_capacity_restored':dict(capital_gross=0.),
      'capital_not_approved_ordinary_capacity_not_restored':dict(capital_gross=0.,source_legacy_capacity=BASE['opening_excess']-BASE['opening_parent']+2.451173958-.2),
      'conditional_capital_fee_10pct':dict(capital_gross=.2,capital_fee=.10),
      'tail_transfer_friction_2pct':dict(release_fee=.02),
      'tail_transfer_friction_5pct':dict(release_fee=.05),
      'no_new_external_funding':dict(financing_limit=0.),
    }
    for name,change in variants.items():
        a=copy.deepcopy(BASE);a.update(change);out['sensitivities'][name]=evaluate(a,params)
    out['capacity_delivery_stress']={}
    for stress in ['ordinary_old_capacity_3bn_delay3','ordinary_old_capacity_2bn_delay3_release8']:
        out['capacity_delivery_stress'][stress]={}
        for name,a in scenario_assumptions().items():
            a.update(variants[stress])
            out['capacity_delivery_stress'][stress][name]=evaluate(a,params if name!='structural' else [(.105,0),(.095,.005)])
    # Preserve familiar reporting keys, while all numeric rows come from this one chain.
    out['sensitivity_domestic_margin_minus_1pp']=out['sensitivities']['domestic_margin_minus_1pp']['valuations']
    out['no_option_exercise']=out['sensitivities']['no_option_exercise']['valuations']
    out['terminal_roic_15pct']=out['sensitivities']['terminal_roic_15pct']['valuations']
    return out

def tests():
    a=copy.deepcopy(BASE);a.update(dom=[1]*5,exp=[0]*5,dm=[1]*5,em=[0]*5,capex=[0]*5,da=[0]*5,wc=[0]*5,payout=1,upstream=1,receipt=1,settlement=[0]*5,opening_excess=0,opening_parent=0,parent_ur=100,parent_reserve=.5,sub_reserve_rate=0,parent_np_ratio=1,finance_yield=0,shares=1,options=False,parent_registered_start=1.,parent_registered_target=1.,parent_paid=1.,tail_settlement=0.,tail_horizon=400,source_legacy_capacity=0)
    rr=forecast(a);v=valuation(rr,.1,0,.25);assert abs(v['current_per_share']-10)<1e-10
    a['parent_np_ratio']=0;a['receipt']=0;a['parent_ur']=0
    rr=forecast(a);assert rr[0]['dps']==0 and abs(rr[1]['dps']-1)<1e-12 and rr[1]['parent_profit']==1.
    q=copy.deepcopy(a);q.update(dom=[10.,0.,0.,0.,0.],parent_np_ratio=1.,receipt=1.,upstream=1.,parent_ur=0.,parent_reserve=5.,parent_registered_start=20.,parent_registered_target=20.,parent_paid=10.,shares=10.,sub_reserve_rate=.1)
    counter=forecast(q)[0];assert counter['parent_reserve_add']==1. and counter['dividend']==9.
    option=forecast(BASE)[0]
    assert abs(option['shares']-BASE['shares']-BASE['issuance'][0])<1e-12
    assert abs(option['registered_capital']-BASE['parent_registered_target']-BASE['issuance'][0])<1e-12
    assert option['issue_cash']==BASE['issue_cash'][0]
    without=copy.deepcopy(BASE);without['options']=False
    assert forecast(without)[0]['issue_cash']==0 and forecast(without)[0]['shares']==BASE['shares']
    q['parent_reserve']=10.;assert forecast(q)[0]['parent_reserve_add']==0.
    q.update(parent_reserve=5.,dom=[-.5,.3,.3,0.,0.],opening_excess=1.,opening_parent=1.)
    loss=forecast(q);assert [round(x['dividend'],8) for x in loss[:3]]==[0.,0.,.09]
    q.update(parent_np_ratio=0.,opening_parent=0.);source=forecast(q);assert [round(x['subs_declaration'],8) for x in source[:3]]==[0.,0.,.09]
    q=copy.deepcopy(a);q.update(dom=[1,0,0,0,0],receipt=0,parent_np_ratio=0,parent_ur=0,parent_reserve=.5)
    old=forecast(q);assert old[1]['upstream_receipt']==1 and old[1]['parent_profit']==0
    q=copy.deepcopy(BASE);q.update(capex=[20.]*5,payout=0.)
    try:forecast(q)
    except ValueError:pass
    else:raise AssertionError('unfunded required investment accepted')
    cap=capital_return(.2,.610,.65416348354,.15,.02,.25)
    assert abs(cap['parent_legal_gain']-(.2-.65416348354*.2/.610-.004-.0125))<1e-12
    assert abs(cap['remaining_registered']-.410)<1e-12
    half=capital_return(.2,.610,.65416348354,.075,.02,.25,.5)
    assert abs(half['net_cash']-cap['net_cash']/2)<1e-12
    try:capital_return(.7,.61,.654,.15,.02,.25)
    except ValueError:pass
    else:raise AssertionError('cancelled more than real registered capital')
    # Production chain: cash-rich, profit-poor capital return cannot become mother dividend.
    q=copy.deepcopy(BASE);q.update(dom=[0]*5,exp=[0]*5,capex=[0]*5,da=[0]*5,wc=[0]*5,opening_excess=.2,opening_parent=0,parent_ur=0,finance_yield=0,settlement=[0]*5,tail_settlement=0,options=False,capital_gross=.2,source_legacy_capacity=.2,strict_realization=False)
    caprows=forecast(q,12,0,.25)
    assert caprows[7]['capital_return']['gross']==.2 and caprows[7]['parent_profit']<0
    assert sum(x['dividend'] for x in caprows)==0
    # Cash without economic/legal distribution rights is explicitly infeasible, not worth zero.
    q=copy.deepcopy(BASE);q.update(dom=[0]*5,exp=[0]*5,capex=[0]*5,da=[0]*5,wc=[0]*5,opening_excess=1,opening_parent=0,parent_ur=0,finance_yield=0,settlement=[0]*5,tail_settlement=0,options=False,source_legacy_capacity=0)
    try:forecast(q,20,0,.25)
    except RealizationError as e:no_rights=str(e)
    else:raise AssertionError('cash with no distribution capacity accepted')
    return dict(hand_value=v['current_per_share'],registered_paid_test=counter,loss_first_mother=[x['dividend'] for x in loss[:3]],loss_first_source=[x['subs_declaration'] for x in source[:3]],old_receivable_not_profit='passed',no_unlimited_funding='passed',capital_return=cap,half_ownership=half,capital_receipt_not_parent_profit='passed',missing_distribution_rights=no_rights)


def capacity_thresholds():
    out={}
    for name,a in scenario_assumptions().items():
        params=[(.105,0),(.095,.005)] if name=='structural' else [(.095,.015),(.085,.02)]
        out[name]=[]
        for k,g in params:
            lo=0.;hi=a['opening_excess']-a['opening_parent']+2.451173958
            for _ in range(25):
                mid=(lo+hi)/2;b=copy.deepcopy(a);b['source_legacy_capacity']=mid
                try:forecast(b,240,g,a['terminal_roic'])
                except RealizationError:lo=mid
                else:hi=mid
            out[name].append(dict(k=k,g=g,minimum_economic_old_capacity=hi,default_capacity=a['opening_excess']-a['opening_parent']+2.451173958,headroom=a['opening_excess']-a['opening_parent']+2.451173958-hi))
    return out

def all_birth_years():
    """Marginal actual-money tests, not attribution/FIFO of ordinary existing payments.
    Inject additional SOURCE cash with separately assumed ordinary delivery capacity;
    inject MOTHER cash with NO new legal profit. Existing production legal gates remain.
    The conservative test adds 1bn to every single year independently, all four paths.
    """
    summary={};failures=[]
    for name,a in scenario_assumptions().items():
        params=[(.105,0),(.095,.005)] if name=='structural' else [(.095,.015),(.085,.02)]
        for idx,(k,g) in enumerate(params):
            base=forecast(a,244,g,a['terminal_roic']);records=[]
            zero=copy.deepcopy(a);zero['finance_yield']=0.;zero_base=forecast(zero,244,g,a['terminal_roic'])
            for loc in ['source','mother']:
                for birth in range(1,241):
                    b=copy.deepcopy(a);b['injections']=[dict(year=birth,location=loc,amount=1.,ordinary_capacity=1. if loc=='source' else 0.)]
                    horizon=max(12,birth+4)
                    try:rr=forecast(b,horizon,g,a['terminal_roic'])
                    except (ValueError,AssertionError) as e:
                        failures.append(dict(path=name,index=idx,birth=birth,location=loc,error=str(e)));continue
                    deadline=max(11,birth+2)
                    cashdiff=rr[deadline-1]['excess_cash']-base[deadline-1]['excess_cash']
                    trueextra=rr[deadline-1]['true_extra_cash']
                    # Additional interest is real income, not counted as recovery of principal.
                    extra_payments=sum((r['dividend']-base[j]['dividend']) for j,r in enumerate(rr))
                    extra_interest=sum((r['financial_profit']-base[j]['financial_profit']) for j,r in enumerate(rr))
                    remaining=rr[-1]['excess_cash']-base[horizon-1]['excess_cash']
                    identity_error=abs(extra_payments+remaining-1.-extra_interest)
                    assert identity_error<1e-7
                    paid_by_deadline=sum(rr[j]['dividend']-base[j]['dividend'] for j in range(deadline))
                    z=copy.deepcopy(b);z['finance_yield']=0.;zr=forecast(z,horizon,g,a['terminal_roic'])
                    zero_cashdiff=zr[deadline-1]['excess_cash']-zero_base[deadline-1]['excess_cash']
                    zero_paid=sum(zr[j]['dividend']-zero_base[j]['dividend'] for j in range(deadline))
                    if trueextra>1e-7 or paid_by_deadline<1.-1e-7 or abs(zero_cashdiff)>1e-7 or abs(zero_paid-1.)>1e-7:
                        failures.append(dict(path=name,index=idx,birth=birth,location=loc,deadline=deadline,cashdiff=cashdiff,trueextra=trueextra))
                    records.append(dict(birth=birth,location=loc,deadline=deadline,remaining_incremental_cash=cashdiff,actual_marginal_payment=extra_payments,incremental_financial_income=extra_interest,identity_error=identity_error,paid_by_deadline=paid_by_deadline,zero_yield_remaining_principal=zero_cashdiff,zero_yield_actual_marginal_payment=zero_paid))
            summary[f'{name}/{idx}']=dict(tests=len(records),max_absolute_remaining=max(abs(x['remaining_incremental_cash']) for x in records),records=records)
    return dict(paths=summary,failures=failures,all_passed=not failures)

# Transport-only deterministic full-payload packing. All economic functions above are unchanged.
import base64, gzip, hashlib, io, argparse

def pack_full_output(result):
    raw=json.dumps(result,ensure_ascii=False,indent=2).encode('utf-8')
    stream=io.BytesIO()
    with gzip.GzipFile(filename='',mode='wb',fileobj=stream,compresslevel=9,mtime=0) as zipped:
        zipped.write(raw)
    compressed=stream.getvalue()
    return dict(wrapper_schema='trading-os-full-json-gzip-base64-v1',
      content_description='Complete unmodified full research model output; summary is an index, not a replacement.',
      information_cutoff=result['information_cutoff'],encoding='utf-8',compression='gzip',gzip_mtime=0,
      canonical_json_serialization='json.dumps(result, ensure_ascii=False, indent=2); UTF-8; no trailing newline',
      uncompressed_bytes=len(raw),uncompressed_sha256=hashlib.sha256(raw).hexdigest(),
      compressed_bytes=len(compressed),compressed_sha256=hashlib.sha256(compressed).hexdigest(),
      expand_command='python 2026-Q3.py --expand 2026-Q3-output.expanded.json',
      default_expand_target='2026-Q3-output.expanded.json',
      summary=dict(cases={name:dict(status=case['status'],
        value_range=([v['current_per_share'] for v in case['valuations']] if case['valuations'] else None),
        terminal_year5=([v['terminal_per_share'] for v in case['valuations']] if case['valuations'] else None),
        first_five_distributions=[r['dps'] for r in case['rows']]) for name,case in result['cases'].items()},
        birth_test_count=sum(p['tests'] for p in result['birth_year_marginal_tests']['paths'].values()),
        birth_test_failures=len(result['birth_year_marginal_tests']['failures']),
        complete_top_level_keys=list(result)),
      full_payload_gzip_base64=base64.b64encode(compressed).decode('ascii'))

def expand_output(wrapper_path,target):
    wrapper=json.loads(Path(wrapper_path).read_text(encoding='utf-8'))
    if wrapper.get('wrapper_schema')!='trading-os-full-json-gzip-base64-v1':
        raise ValueError('not a recognized complete output wrapper')
    compressed=base64.b64decode(wrapper['full_payload_gzip_base64'],validate=True)
    if len(compressed)!=wrapper['compressed_bytes'] or hashlib.sha256(compressed).hexdigest()!=wrapper['compressed_sha256']:
        raise ValueError('compressed payload length or SHA256 mismatch')
    raw=gzip.decompress(compressed)
    if len(raw)!=wrapper['uncompressed_bytes'] or hashlib.sha256(raw).hexdigest()!=wrapper['uncompressed_sha256']:
        raise ValueError('expanded payload length or SHA256 mismatch')
    json.loads(raw)  # Validate complete JSON before writing, never truncate economic fields.
    destination=Path(target)
    if destination.resolve()==Path(wrapper_path).resolve():
        raise ValueError('expansion target must not overwrite the packed input')
    destination.write_bytes(raw)
    return dict(path=str(destination),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Regenerate the substantive model and all tests, or expand its complete packed output.')
    parser.add_argument('--expand',nargs='?',const='2026-Q3-output.expanded.json',metavar='TARGET',help='Validate and expand the sibling packed output; no valuation recomputation.')
    args=parser.parse_args()
    output_path=Path(__file__).with_name('2026-Q3-output.json')
    if args.expand is not None:
        print(json.dumps(expand_output(output_path,args.expand),ensure_ascii=False))
    else:
        result=run();result['tests']=tests();result['minimum_old_capacity_thresholds']=capacity_thresholds()
        result['birth_year_marginal_tests']=all_birth_years()
        output_path.write_text(json.dumps(pack_full_output(result),ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({n:([v['current_per_share'] for v in c['valuations']] if c['valuations'] else c['reason']) for n,c in result['cases'].items()}))
        print('birth failures',len(result['birth_year_marginal_tests']['failures']))
        print(json.dumps(result['minimum_old_capacity_thresholds']))

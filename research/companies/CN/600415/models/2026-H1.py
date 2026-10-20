"""600415: CNY 100m throughout; shares in 100m. Offline, standard library.
A conditional model, not management guidance. All contract flows are explicit.
"""
import json, math
from pathlib import Path
S=54.83559226
STUB_NET=-1.5 # estimated July1-Sept12 net operating/project cash, no new price data
CASH=23.9335+9.3111+5.2181+1-15.4659+STUB_NET # old dividend excluded from future holder cash
DEBT=32.8577
NCI=.8742
OPERATING_CASH=8. # parent floor3 is included, not another deduction
PREPAID=74.71204
DPS=[.10,.15,.20,.25,.30]
# Book investment excludes the RMB1bn? No: 1 *100m structured deposit already in CASH.
BOOK_INV=91.283481-1
# Three separately valued pools, no associated earnings in operating cash.
INV={'liquid_stock':10.430369,'frozen':7.672796,'other':BOOK_INV-10.430369-7.672796}

def pv(cf,r):return sum(v/(1+r)**t for t,v in cf)
def cap(c,r,g):
    assert r>g
    return c*(1+g)/(r-g)

def model(r=.09,g=.015,market=24.5,other_rent=5.,opex=10.5,digital=.8,sale_share=.5,sale_price=1.4,new_rent=850,cap_overrun=0,collection_delay=0,inv_delay=10):
    # Operating starting cash: income tax considers D&A; maintenance includes land reserve.
    da=7.2; maintenance=3.5
    investment_recovery=INV['liquid_stock']*.85+INV['frozen']*.25+INV['other']*.85
    # Principal recovered only once at year10. Income distributions are modeled separately.
    inv_cf=[(t,1.) for t in range(1,inv_delay+1)]+[(inv_delay,investment_recovery)]
    inv_now=pv(inv_cf,r)
    # Old digital-market residual capital15.9242, Hangzhou7.3085 and new service-trade59.7533.
    # Remove unspent finance allowance6.65 from service-trade investment; interest in holder budget.
    old_cap=[8,6,1.9242,0,0]
    hz_cap=[2.5,2.5,2.3085,0,0]
    new_cap=[12,16,16,9.103269,0]
    # T1/T2 saleable office117401.56m2*16000; remaining T3/T7 at book0.7732/0.65;
    # Hangzhou sale pool5.5814 /0.8; deduct starting home advances5.4176 once.
    old_hz_gross=117401.56*16000/1e8+.773177/.65+5.5814/.8
    old_hz_net=old_hz_gross*.9-5.417623
    old_sale=[old_hz_net*.2,old_hz_net*.4,old_hz_net*.4,0,0]
    # 443000m2 above ground excludes basement. Sale/lease mix is explicit research assumption.
    new_sale=44.3*sale_share*sale_price*.90
    sale_schedule=[0,0,new_sale*.25,new_sale*.50,new_sale*.25]
    new_cf6=443000*(1-sale_share)*new_rent/1e8*.55+.35 # service-trade new land auxiliary netcash
    retained_rent=[0,0,new_cf6*.15,new_cf6*.55,new_cf6]
    # Old T1 hotel + Hangzhou retained offices modest netcash0.3 after full completion.
    retained_old=[0,0,.1,.2,.3]
    # Remaining initial-fee liability: assume recurring prepay1.5 years of market revenue.
    recurring_open=market*1.5
    initial_open=PREPAID-recurring_open
    assert initial_open>=0
    initial_release=[initial_open*.5,initial_open*.3,initial_open*.2,0,0]
    # Renewals staggered: temporary collection deficit, recovered by year3; not extra initial-fee deduction.
    recurring_bal=recurring_open
    rows=[];cash=CASH;debt=DEBT;parent_cash=20.1448-15.4659+STUB_NET
    parent_profit_reserve=103.3388; statutory=24.1776
    previous_cash=cash; previous_debt=debt
    core_cf=[]; project_cf=[]
    parent_borrow_total=0
    for i in range(5):
        t=i+1;gr=(1.025)**t
        rev=(market+other_rent)*gr
        cost=opex*(1.02)**t
        dep=da*(1.02)**t
        maint=maintenance*(1.02)**t
        recurring_ebit=rev-cost-dep
        recurring_nopat=recurring_ebit*.75
        operating=recurring_nopat+dep-maint+digital*(1.08)**t
        # End recurring prepayment targets recover from first-year 20% shortfall over 3 years.
        target=market*1.5*gr-market*([.20,.10,0,0,0][i])
        d_recurring=target-recurring_bal;recurring_bal=target
        initial_tax=initial_release[i]*.25
        cf_core=operating+d_recurring-initial_tax
        capex=(old_cap[i]+hz_cap[i]+new_cap[i])*(1+cap_overrun)
        sales=old_sale[i]+sale_schedule[i]
        if collection_delay:
            allsale=[old_sale[j]+sale_schedule[j] for j in range(5)]
            sales=allsale[i-collection_delay] if i>=collection_delay else 0
        cf_project=sales+retained_rent[i]+retained_old[i]-capex
        core_cf.append((t,cf_core));project_cf.append((t,cf_project))
        # Solve debt and same-year interest jointly, assuming new loans drawn midyear.
        dividend=DPS[i]*S
        commitment=3.828 if t==2 else 0
        upstream=min(.25*max(0,operating),.25*max(0,recurring_nopat)+digital*(1.08)**t)
        group_before_interest=cash+cf_core+cf_project+1-dividend-commitment
        parent_before_interest=parent_cash+.75*cf_core+upstream+.9*sales+.9*(retained_rent[i]+retained_old[i])-.9*capex+1-dividend-commitment
        opening_interest=debt*.03
        net_incremental_interest=.5*.03*.75
        borrowing=max(0,(8-group_before_interest+opening_interest*.75)/(1-net_incremental_interest),(3-parent_before_interest+opening_interest*.75)/(1-net_incremental_interest))
        interest=.03*(debt+.5*borrowing)
        cash=group_before_interest-interest*.75+borrowing
        parent_cash=parent_before_interest-interest*.75+borrowing
        debt+=borrowing
        pborrow=borrowing;parent_borrow_total+=pborrow
        # Conservative legal-capacity check: credit no future profit; deduct all dividends
        # and gross group interest (conservatively all charged to parent), without tax shield.
        parent_profit_reserve-=dividend+interest
        legal_income=0
        assert abs(interest-.03*(previous_debt+.5*borrowing))<1e-10
        assert cash>=8-1e-9 and parent_cash>=3-1e-9
        assert parent_cash<=cash+1e-8
        # Parent funding is a share of group debt plus existing intercompany cash, not extra group asset.
        rows.append(dict(year=t,revenue=rev,ebit=recurring_ebit,nopat=recurring_nopat,da=dep,maintenance=maint,digital_cash=digital*1.08**t,operating=operating,recurring_prepaid=recurring_bal,recurring_prepaid_change=d_recurring,initial_release=initial_release[i],initial_tax=initial_tax,core_cf=cf_core,capex=capex,sales=sales,new_property_cash=retained_rent[i]+retained_old[i],project_cf=cf_project,investment_dividend=1,interest=interest,investment_commitment=commitment,subsidiary_upstream=upstream,dividend=dividend,borrow=borrowing,cash=cash,debt=debt,parent_cash=parent_cash,parent_borrow=pborrow,parent_future_profit_credited=0,parent_interest_capacity_debit=interest,parent_distributable_profit=parent_profit_reserve,statutory_reserve=statutory))
        assert abs(cash-previous_cash-(cf_core+cf_project+1-interest*.75-dividend+borrowing-commitment))<1e-8
        assert abs(debt-previous_debt-borrowing)<1e-8
        assert parent_profit_reserve>=0
        previous_cash=cash;previous_debt=debt
    # Terminal: growth constrained by maintenance+land reserve and mature renewals.
    core6=rows[-1]['operating']*(1+g)
    # Additional working capital needed for permanent growth: prepaid benefit held flat in terminal.
    # Renewal reserve represented as explicit future expenditure, not vanished financial savings.
    renewal_pv=20*(1.02)**21/(1+r)**21/(1-(1.02/(1+r))**20)
    core_tv=core6/(r-g)-renewal_pv*(1+r)**5
    project_tv=(new_cf6+.3)*(1+g)/(r-g)
    sales_after5=0
    if collection_delay:
        allsale=[old_sale[j]+sale_schedule[j] for j in range(5)]
        sales_after5=pv([(j+1,allsale[5-collection_delay+j]) for j in range(collection_delay)],r)
        project_tv+=sales_after5
    op_value=pv(core_cf,r)+core_tv/(1+r)**5
    project_value=pv(project_cf,r)+project_tv/(1+r)**5
    # Any unspent commitment must create an asset. Base allocates3.828 to portfolio paid inyear2,
    # recover at80% atyear10; frozen8.95 uncalled not included base, separate stress.
    commitment_cf=[(2,-3.828),(inv_delay,3.828*.8)]
    commitment_value=pv(commitment_cf,r)
    equity=op_value+project_value+inv_now+commitment_value+CASH-OPERATING_CASH-DEBT-NCI
    debt5=debt
    inv5=pv([(t-5,v) for t,v in inv_cf+[(inv_delay,3.828*.8)] if t>5],r)
    terminal=core_tv+project_tv+inv5+cash-OPERATING_CASH-debt5-NCI
    return dict(params=dict(r=r,g=g,market=market,other_rent=other_rent,opex=opex,digital=digital,sale_share=sale_share,sale_price=sale_price,new_rent=new_rent,cap_overrun=cap_overrun,collection_delay=collection_delay,inv_delay=inv_delay),renewal_pv=renewal_pv,core_value=op_value,project_value=project_value,investment_value=inv_now,commitment_value=commitment_value,equity_value=equity,per_share=equity/S,terminal_equity_per_share=terminal/S,terminal_core=core_tv,terminal_project=project_tv,terminal_investments=inv5,terminal_cash=cash,terminal_debt=debt5,initial_fee_remaining=initial_open,core_terminal_pv_share=core_tv/(1+r)**5/op_value,rows=rows,parent_funding_total=parent_borrow_total,remaining_budget=sum(old_cap)+sum(hz_cap)+sum(new_cap),investment_recovery=investment_recovery,initial_cash=CASH,necessary_operating_cash=OPERATING_CASH,initial_excess_cash=CASH-OPERATING_CASH,terminal_excess_cash=cash-OPERATING_CASH)

def run():
    base=model();low=model(r=.095,g=.01);high=model(r=.085,g=.02)
    stress={
      'rent_minus_10pct':model(market=22.05),
      'construction_plus_20pct':model(cap_overrun=.2),
      'sale_delayed_2y':model(collection_delay=2),
      'sale_mix_30pct':model(sale_share=.3),
      'investment_recovery_year15':model(inv_delay=15),
      'structural':model(r=.10,g=0,market=20,other_rent=4,opex=10.5,digital=.4,sale_share=.3,sale_price=1.1,new_rent=650,cap_overrun=.2),
      'optimistic':model(r=.085,g=.02,market=27,other_rent=5.5,digital=1.5,sale_share=.6,sale_price=1.6,new_rent=1000)
    }
    # Auxiliary rent capitalization uses same recurring cash but no perpetual first fees.
    recurring=base['rows'][0]['operating']
    auxiliary={str(mult):(recurring*mult+base['project_value']+base['investment_value']+base['commitment_value']+CASH-OPERATING_CASH-DEBT-NCI)/S for mult in (13,16)}
    assert abs(pv([(1,110)],.1)-100)<1e-10
    assert abs(cap(10,.1,0)-100)<1e-10
    assert abs(sum(x['initial_release'] for x in base['rows'])-base['initial_fee_remaining'])<1e-9
    assert len(DPS)==5 and all(x>=0 for x in DPS)
    assert low['per_share']<base['per_share']<high['per_share']
    assert stress['rent_minus_10pct']['per_share']<base['per_share']
    out={'units':'CNY 100m and shares100m','shares':S,'base':base,'low':low,'high':high,'sensitivity':stress,'auxiliary':auxiliary,'distributions_per_share':DPS,'value_range':{'low':round(low['per_share'],2),'high':round(high['per_share'],2)},'return_terminal_range':{'low':round(low['terminal_equity_per_share'],2),'high':round(high['terminal_equity_per_share'],2)}}
    Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ['value_range','return_terminal_range','auxiliary']},ensure_ascii=False))
    print('base',base['per_share'],'budget',base['remaining_budget'],'parentfund',base['parent_funding_total'])
    print('cash/debt',[(round(x['cash'],2),round(x['debt'],2),round(x['parent_cash'],2),round(x['parent_borrow'],2)) for x in base['rows']])
if __name__=='__main__':run()

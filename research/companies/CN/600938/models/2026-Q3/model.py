"""CN600938 static economic author object. Units RMB million / million boe.
NOT EXECUTED. Reads only its frozen inputs.json; no network, third-party packages or old-model imports.
The coordinator must separately admit the exact frozen command before execution.
Budgets are conditional economics, not individual legal/tax/project certifications.
"""
import json
import sys
import traceback
from copy import deepcopy
from pathlib import Path

SHARES = 47529.953984
AS_OF = '2026-10-31T05:35:00+00:00'
# H1 bond book amounts/rates; Q3 scale is a budget, not reported tranche balances.
BONDS_H1 = [(2033,2025,.055),(2041,3383,.0575),(2042,3378,.05),
 (2043,3359,.0425),(2029,6780,.02875),(2049,3392,.033),
 (2044,3354,.04875),(2028,1024,.074),(2032,2451,.07875),
 (2035,3132,.05875),(2037,5664,.064),(2039,4768,.075),
 (2045,2038,.042),(2028,6799,.04375)]
BASE = dict(
 cash0=311773., parent_cash0=25000., domestic_cash_share=.70,
 parent_legal0=150000., domestic_legal0=300000., foreign_legal0=30000.,
 parent_undistributable=5564.,
 initial_declared_gross=15000., share_capital=75180.,
 domestic_investment_basis=36629., foreign_investment_basis=178542.,
 domestic_profit_share=.70, appropriation=0., remittance_cost=.02,
 declare_rate=.55, current_receipt_rate=.80, freeze_receipts_years=0,
 dividend_policy=.45, parent_fee=300., cash_floor=60000., parent_floor=10000.,
 restricted_deposit=0., restricted_deposit_years=0, general_yield=.015,
 bank0=6161., bank_rate=.035, bond_scale=50839./51547.,
 bank_repay=[1085,1133,821,516,400,400,1806],
 lease0=9500., lease_rate=.05, lease_repay=[2600,2000,1600,1200,900,700,500],
 refinance_fraction=0., refinance_rate=.045, financing_tax=.28,
 other_claims=2922.+2501., minority_cash_adjustment=0.,
 aro0=121400., fund0=8122., aro_carry=.04, fund_yield=.015,
 aro_tax=.20, new_aro_per_boe=10., new_fund_first5=5000.,
 legacy_aro_uncovered_fraction=.50, aro_recognition='construction',
 aro_asset_producing0=60000., aro_asset_wip0=12000., aro_book_tax_rate=.28,
 aro_paid_first5=[1000,1500,2500,3500,5000],
 resource_initial=7400.-(593.7+65.)*(757.6/777.3), pud_initial=3213.,
 producing_book0=501055.+20000., wip0=168756.,
 legacy_future_capital=520000., legacy_cost_multiplier=1.,
 legacy_cash_schedule=[110000,115000,100000,80000,60000,25000,15000,10000,3000,2000],
 find_cash=20000., find_unit_cost=35., find_years=10, appraisal_lag=2,
 develop_unit_cost=135., development_lag=3,
 after5_find_unit_cost=None, after5_develop_unit_cost=None,
 investment_ceiling=[130000,135000,138000,142000,145000],
 exploration_expensed_share=11000./19256., failed_extra_capital=0.,
 production=[805,821,837,854,871], oil=[78,73,70,70,71],
 gas=[7.8,7.7,7.6,7.6,7.7], scale_to_consolidated=757.6/777.3,
 tail_decline=.105, plateau_years=3, fixed_operating_cost=3000.,
 incremental_cost=[5500,6500,7500,8500,11000],
 domestic_oil_share=.68, domestic_gas_share=.70, domestic_cit=.25,
 domestic_resource_tax=.06, domestic_levy_coverage=1.,
 foreign_oil_retention=.65, domestic_gas_retention=.70, foreign_gas_retention=.60,
 oil0=66.47, gas0=7.95, liquid_sales0=589.2, gas_sales0=984., production0=757.6,
 fx=7., psc_liquid_share=.15, psc_cost_dollars=30., psc_cap_fraction=.50,
 normal_adjustment_tax=.28, equity_impairment_tax=0.,
 noncash_writeoff=6708., operating_impairment=2368.,
 working_add=3000., deferred_tax=[2000,1500,1000,500,0,-1000,-1000,-1000,-1000,-1000],
 associate_cash=250., associate_exit_year=10, associate_value=25000.,
 associate_exit_fraction=.95, associate_basis=25000.,
 arctic_loan=9145., arctic_loan_recovery=.25, arctic_loan_year=14,
 arctic_equity_cash=0., arctic_equity_year=15,
 arctic_equity_basis=10000., arctic_equity_reference_basis=10000.,
 capital_return=False, domestic_exit_delay=3, foreign_exit_delay=5,
 domestic_exit_cost=.05, foreign_exit_cost=.15, parent_exit_delay=1,
 parent_exit_cost=.03, discount=.0925, max_resource_years=75,
 financial_tail_years=50,
)


def normal_bridge(p):
    t=p['normal_adjustment_tax']; net=1-t
    items={'reported_parent_np':122082., 'remove_net_finance':823*net,
      'remove_other_investment_loss':471*net, 'remove_equity_method_loss':472.,
      'remove_fair_value_gain':-682*net, 'remove_other_income':-599*net,
      'remove_asset_disposal_gain':-5*net, 'remove_net_nonoperating_gain':-526*net,
      'remove_equity_impairment':1441*(1-p['equity_impairment_tax'])}
    items['normal_operating_nopat']=sum(items.values())
    items['reported_cfo_rebuild']=sum([122148,3809,9,79771,6708,-682,823,940,
                                     1886,1067,-616,1,-2158,-4664])
    items['cash_finding_reclassification']={str(e):(209042+e)-(111555-(19256-e))-19256
                                          for e in [8000,11000,15000]}
    return items


def levy(price):
    # Excess progressive levy, NOT a rate times the whole oil price.
    return sum(max(0.,min(price-hi,5.))*rate for hi,rate in
               [(65,.20),(70,.25),(75,.30),(80,.35)])+max(0.,price-85)*.40


def psc_entitlement(price,p):
    unsaturated=.5+.5*min(.75,p['psc_cost_dollars']/price)-.02
    return p['psc_cap_fraction']*.855+(1-p['psc_cap_fraction'])*unsaturated


def physical_to_net(price,p):
    oil_weight=p['liquid_sales0']/p['production0']
    return 1+oil_weight*p['psc_liquid_share']*(psc_entitlement(price,p)/psc_entitlement(p['oil0'],p)-1)


def new_state(p):
    child=p['cash0']-p['parent_cash0']; w=p['domestic_cash_share']
    declared=p['initial_declared_gross']
    return dict(dc=child*w,fc=child*(1-w),pc=p['parent_cash0'],
      dl=p['domestic_legal0'],
      fl=p['foreign_legal0']+p['arctic_equity_basis']-p['arctic_equity_reference_basis'],
      pl=p['parent_legal0'],reserve=0.,
      dp=declared*w,fp=declared*(1-w),bank=p['bank0'],lease=p['lease0'],
      bonds=[dict(year=y-2026,amount=a*p['bond_scale'],rate=r,rolled=False) for y,a,r in BONDS_H1],
      aro=p['aro0'],fund=p['fund0'],wc=0.,pd=p['resource_initial']-p['pud_initial'],
      pud=p['pud_initial'],appraised=0.,appraised_book=0.,find_queue=[],dev_queue=[],
      producing_book=p['producing_book0'],wip=p['wip0'],legacy_paid=0.,
      aro_asset_book=p['aro_asset_producing0'],
      dbasis=p['domestic_investment_basis'],fbasis=p['foreign_investment_basis'],
      associates_carry=p['associate_basis'],loan_carry=p['arctic_loan'],
      arctic_equity_carry=p['arctic_equity_basis'],
      legacy_aro_added=0.,new_resource_aro_added=0.,
      remittance_cost=p['remittance_cost'],undistributable=p['parent_undistributable'],
      cap=p['share_capital'],d_closed=False,f_closed=False,resource_end=None,
      parent_return_done=False,first_capital_event=None,resource_consumed=0.,
      new_found=0.,new_commissioned=0.,total_investment=0.,dividends=0.,
      capital_paid=0.,economic_failures=[],rows=[])


def resources(y,s,p):
    """Pay/identify/appraise/develop/commission once, consuming reference-net resources.
    WIP is not depreciated before commission. New retirement assets enter with liability.
    """
    commissioned=0.; new_aro=0.; legacy_aro=0.; discovery_aro=0.
    ready=[q for q in s['dev_queue'] if q['ready']==y]
    s['dev_queue']=[q for q in s['dev_queue'] if q['ready']!=y]
    for q in ready:
        s['pd']+=q['units']; s['producing_book']+=q['book']; s['wip']-=q['book']
        s['aro_asset_book']+=q.get('aro_book',0.)
        commissioned+=q['units']
        added=q['aro_pending'];new_aro+=added
        s['producing_book']+=added;s['aro_asset_book']+=added
        if q['new']:
            discovery_aro+=added;s['new_commissioned']+=q['units']
        else:legacy_aro+=added
    matured=[q for q in s['find_queue'] if q['ready']==y]
    s['find_queue']=[q for q in s['find_queue'] if q['ready']!=y]
    for q in matured:
        s['appraised']+=q['units'];s['appraised_book']+=q['book']
    exploration=p['find_cash'] if y<=p['find_years'] else 0.
    expensed=exploration*p['exploration_expensed_share']
    if exploration:
        find_cost=(p['after5_find_unit_cost'] or p['find_unit_cost']) if y>5 else p['find_unit_cost']
        found=exploration/find_cost;s['new_found']+=found
        s['find_queue'].append(dict(ready=y+p['appraisal_lag'],units=found,book=exploration-expensed))
    ceiling=p['investment_ceiling'][min(y-1,4)]
    # Post-program only already identified resources can receive development money.
    legacy=0.; legacy_units=0.
    unit_existing=p['legacy_future_capital']/p['pud_initial']*p['legacy_cost_multiplier']
    legacy_due=max(0.,sum(p['legacy_cash_schedule'][:min(y,len(p['legacy_cash_schedule']))])-s['legacy_paid'])
    if legacy_due>0:
        legacy=min(legacy_due,max(0.,s['pud'])*unit_existing,
                   max(0.,p['legacy_future_capital']-s['legacy_paid']),max(0.,ceiling-exploration))
        legacy_units=legacy/unit_existing;s['pud']-=legacy_units;s['legacy_paid']+=legacy
        if legacy_units:
            old_wip=p['wip0']*legacy_units/p['pud_initial']
            s['wip']+=legacy
            old_aro=p['aro_asset_wip0']*legacy_units/p['pud_initial']
            added=queue_development(s,p,y+1,legacy_units,legacy+old_wip,False,old_aro)
            new_aro+=added;legacy_aro+=added
    available=max(0.,ceiling-exploration-legacy)
    dev_cost=(p['after5_develop_unit_cost'] or p['develop_unit_cost']) if y>5 else p['develop_unit_cost']
    development=min(available,s['appraised']*dev_cost)
    new_units=development/dev_cost
    if new_units:
        carried=s['appraised_book']*new_units/s['appraised']
        s['appraised']-=new_units;s['appraised_book']-=carried
        s['wip']+=development+carried
        added=queue_development(s,p,y+p['development_lag'],new_units,development+carried,True,0.)
        new_aro+=added;discovery_aro+=added
    if y<=5: target=p['production'][y-1]*p['scale_to_consolidated']
    else:
        tail=max(0,y-5-p['plateau_years'])
        target=p['production'][-1]*p['scale_to_consolidated']*(1-p['tail_decline'])**tail
    used=min(target,max(0.,s['pd'])); before=s['pd']
    dda=s['producing_book']*used/before if before>0 else 0.
    aro_dda=s['aro_asset_book']*used/before if before>0 else 0.
    s['aro_asset_book']-=aro_dda
    s['pd']-=used;s['producing_book']-=dda;s['resource_consumed']+=used
    oil=p['oil'][min(y-1,4)];gas=p['gas'][min(y-1,4)]
    production=used*physical_to_net(oil,p);scale=used/p['production0']
    writeoff=min(max(0.,s['producing_book']),p['noncash_writeoff']*scale)
    s['producing_book']-=writeoff
    impairment=min(max(0.,s['producing_book']),p['operating_impairment']*scale)
    s['producing_book']-=impairment
    # ARO-associated asset writeoffs carry no extra cash deduction before actual settlement.
    before_losses=s['producing_book']+writeoff+impairment
    aro_loss=s['aro_asset_book']*(writeoff+impairment)/before_losses if before_losses>0 else 0.
    s['aro_asset_book']-=aro_loss
    all_cash=exploration+legacy+development+p['failed_extra_capital']
    # Failed extra spending creates no resources and no depreciable asset; expensed immediately.
    s['total_investment']+=all_cash
    s['legacy_aro_added']+=legacy_aro;s['new_resource_aro_added']+=discovery_aro
    resource_left=s['pd']+s['pud']+sum(q['units'] for q in s['dev_queue'])
    return dict(production=production,reference_production=used,target=target,scale=scale,
      dda=dda,aro_asset_dda=aro_dda,aro_asset_loss=aro_loss,
      writeoff=writeoff,impairment=impairment,expensed_finding=expensed,
      investment=all_cash,exploration=exploration,legacy=legacy,development=development,
      unused_ceiling=max(0.,ceiling-all_cash),commissioned=commissioned,new_aro=new_aro,
      legacy_new_aro=legacy_aro,discovery_new_aro=discovery_aro,
      resource_left=resource_left,oil=oil,gas=gas)


def queue_development(s,p,ready,units,book,is_new,old_aro):
    """Same construction accounting for initial PUD and later discoveries.
    Recognized ARO is NONCASH WIP, not a second development cash expense.
    Existing ARO/old WIP remain untouched; only the net uncovered initial-PUD share is added.
    """
    fraction=1. if is_new else p['legacy_aro_uncovered_fraction']
    obligation=units*p['new_aro_per_boe']*fraction
    if p['aro_recognition'] not in ('construction','commission'):
        raise ValueError('Unknown construction obligation timing')
    immediate=obligation if p['aro_recognition']=='construction' else 0.
    s['wip']+=immediate
    s['dev_queue'].append(dict(ready=ready,units=units,book=book+immediate,new=is_new,
      aro_book=old_aro+immediate,aro_pending=obligation-immediate))
    return immediate


def realize_arctic_equity(y,s,p):
    """Net cash proceeds once; realize proceeds less remaining book basis, not cash minus cost twice."""
    if y!=p['arctic_equity_year']:return 0.,0.
    proceeds=p['arctic_equity_cash'];profit=proceeds-s['arctic_equity_carry']
    s['arctic_equity_carry']=0.
    return proceeds,profit


def operating(y,r,s,p):
    scale=r['scale'];normal=normal_bridge(p)['normal_operating_nopat'];net=.72
    dom=lambda price:(1-p['domestic_resource_tax'])*price-p['domestic_levy_coverage']*levy(price)
    # PSC net entitlement already includes government profit share/royalty and government-paid CIT.
    # Keep the remaining overseas bucket separate; do not tax/subtract PSC government share twice.
    psc_ratio=psc_entitlement(r['oil'],p)/psc_entitlement(p['oil0'],p)
    oil_change=p['liquid_sales0']*scale*p['fx']*(
      p['domestic_oil_share']*(dom(r['oil'])-dom(p['oil0']))*(1-p['domestic_cit'])+
      (1-p['domestic_oil_share']-p['psc_liquid_share'])*(r['oil']-p['oil0'])*p['foreign_oil_retention']+
      p['psc_liquid_share']*(r['oil']*psc_ratio-p['oil0']))
    gas_ret=p['domestic_gas_share']*p['domestic_gas_retention']+(1-p['domestic_gas_share'])*p['foreign_gas_retention']
    gas_change=p['gas_sales0']*scale*p['fx']*(r['gas']-p['gas0'])*gas_ret
    extra=p['incremental_cost'][min(y-1,4)]*scale
    # Base normal NOPAT already includes recurring parent administration and base exploration/writeoffs.
    raw=(normal*scale+oil_change+gas_change-extra-p['fixed_operating_cost']*(1-scale)
       -(r['dda']-79771*scale)*net
       -(r['expensed_finding']-11000*scale)*net
       -(r['writeoff']-6708*scale)*net
       -(r['impairment']-2368*scale)*net-p['failed_extra_capital']*net)
    # No automatic current tax refund on an operating loss. Unused loss credits excluded, reported.
    nopat=raw if raw>=0 else raw/net
    attributable=122082./122148.
    noncash=(r['dda']+r['writeoff']+r['impairment'])*attributable
    wcadd=p['working_add'] if y<=5 else -min(s['wc'],max(0.,p['working_add']*(1-scale)))
    s['wc']+=wcadd
    timing=p['deferred_tax'][y-1] if y<=len(p['deferred_tax']) else 0.
    aro_noncash_tax=(r['aro_asset_dda']+r['aro_asset_loss'])*p['aro_book_tax_rate']
    free=nopat+noncash+r['expensed_finding']+p['failed_extra_capital']-wcadd+timing-r['investment']-aro_noncash_tax
    return dict(nopat=nopat,operating_free=free,oil_change=oil_change,gas_change=gas_change,
                working_cash=wcadd,cash_tax_timing=timing,unrecognized_loss_tax=max(0.,-raw)*(.28/.72),
                aro_noncash_tax_reversal=aro_noncash_tax,
                current_tax_capacity=max(0.,nopat)*(.28/.72)+aro_noncash_tax)


def bank_principal_due(year,remaining,p):
    """Same actual maturity rule for payment and the preceding cash reservation.
    A stale schedule cannot create debt; an unpaid post-schedule balance is due next year.
    """
    scheduled=p['bank_repay'][year-1] if year<=len(p['bank_repay']) else remaining
    return min(remaining,scheduled)


def debt_step(y,s,p):
    bank_interest=s['bank']*p['bank_rate'];lease_interest=s['lease']*p['lease_rate']
    bond_interest=sum(b['amount']*b['rate'] for b in s['bonds'])
    bank_pay=bank_principal_due(y,s['bank'],p)
    lease_pay=min(s['lease'],p['lease_repay'][y-1] if y<=len(p['lease_repay']) else s['lease'])
    s['bank']-=bank_pay;s['lease']-=lease_pay
    due=[b for b in s['bonds'] if b['year']==y]
    s['bonds']=[b for b in s['bonds'] if b['year']!=y]
    due_total=sum(b['amount'] for b in due)
    refi=sum(b['amount'] for b in due if not b['rolled'])*p['refinance_fraction']
    if refi:
        s['bonds'].append(dict(year=y+5,amount=refi,rate=p['refinance_rate'],rolled=True))
    return dict(bank_pay=bank_pay,lease_pay=lease_pay,bond_pay=due_total-refi,
      refinancing=refi,bank_interest=bank_interest,lease_interest=lease_interest,bond_interest=bond_interest)


def add_legal(s,which,profit,appropriation):
    key=which+'l';old=s[key]
    # Prior losses must first be covered; no appropriation from a loss-making accumulated balance.
    eligible=max(0.,min(max(profit,0.),old+profit))
    reserved=eligible*appropriation;s[key]+=profit-reserved
    if which=='d':s['reserve']+=reserved
    return reserved


def settle(s,which,desired,p,floor):
    ck=which+'c';pk=which+'p';paid=min(desired,s[pk],max(0.,s[ck]-floor))
    s[ck]-=paid;s[pk]-=paid;s['pc']+=paid*(1-p['remittance_cost'])
    return paid


def declare(s,which,desired,p,floor):
    ck=which+'c';lk=which+'l';pk=which+'p'
    amount=min(max(s[lk],0.),max(0.,s[ck]-floor-s[pk]),max(0.,desired))
    s[lk]-=amount;s[pk]+=amount;s['pl']+=amount*(1-p['remittance_cost'])
    return amount


def parent_distribute(s,desired,floor):
    parent_net_assets=s['pc']+(s['dp']+s['fp'])*(1-s['remittance_cost'])+s['dbasis']+s['fbasis']
    net_asset_headroom=max(0.,parent_net_assets-s['cap']-s['undistributable'])
    amount=min(max(0.,s['pl']),net_asset_headroom,max(0.,s['pc']-floor),max(0.,desired))
    s['pl']-=amount;s['pc']-=amount;s['dividends']+=amount
    return amount


def parent_liquidity_floor(y,s,p,closed,scale):
    """Actual A/B fee-before-receipt floor; no capital-exit trigger or free child funding."""
    years=max(1,p['freeze_receipts_years']-y+1)
    operating=0. if closed else p['parent_floor']*min(1.,scale)
    return max(operating,p['parent_fee']*years)


def annual(y,s,p,r,op,closed):
    opening_general=s['dc']+s['fc']+s['pc'];opening_fund=s['fund']
    opening_parent_cash=s['pc']
    opening_accounts={k:s[k] for k in ['dc','fc','pc','dl','fl','pl','dp','fp','aro','fund']}
    opening_payables=s['dp']+s['fp'];w=p['domestic_profit_share']
    di=0. if s['d_closed'] else s['dc']*p['general_yield']
    fi=0. if s['f_closed'] else s['fc']*p['general_yield']
    pi=s['pc']*p['general_yield'];fund_income=s['fund']*p['fund_yield']
    s['fund']+=fund_income;s['aro']+=r.get('new_aro',0.)
    aro_unwind=s['aro']*p['aro_carry'];s['aro']+=aro_unwind
    if closed:aro_payment=s['aro']
    elif y<=5:aro_payment=min(s['aro'],p['aro_paid_first5'][y-1])
    else:
        fraction=r['reference_production']/max(1.,r['resource_left']+r['reference_production'])
        aro_payment=min(s['aro'],s['aro']*fraction)
    s['aro']-=aro_payment;fund_used=min(s['fund'],aro_payment);s['fund']-=fund_used
    general_aro=aro_payment-fund_used
    funding=0. if closed else (p['new_fund_first5'] if y<=5 else r.get('new_aro',0.))
    s['fund']+=funding
    fund_release=0.
    if closed and s['aro']<1e-7:fund_release=s['fund'];s['fund']=0.
    debt=debt_step(y,s,p)
    gross_dinterest=debt['bank_interest']+debt['lease_interest']*w
    gross_finterest=debt['bond_interest']+debt['lease_interest']*(1-w)
    gross_interest=gross_dinterest+gross_finterest
    tax_capacity=op.get('current_tax_capacity',max(0.,op['nopat'])*(.28/.72))
    financing_tax_cash=min(tax_capacity,gross_interest*p['financing_tax'])
    taxnet=1-financing_tax_cash/gross_interest if gross_interest else 1.
    dinterest=gross_dinterest*taxnet;finterest=gross_finterest*taxnet
    aro_tax=min(aro_payment*p['aro_tax'],max(0.,tax_capacity-financing_tax_cash))
    dprincipal=debt['bank_pay']+debt['lease_pay']*w
    fprincipal=debt['bond_pay']+debt['lease_pay']*(1-w)
    investment_cash=0.;investment_profit=0.;arctic_cash=0.
    if p['associate_exit_year'] is None or y<=p['associate_exit_year']:
        investment_cash=p['associate_cash'];investment_profit=investment_cash
    if p['associate_exit_year'] is not None and y==p['associate_exit_year']:
        proceeds=p['associate_value']*p['associate_exit_fraction']
        investment_cash+=proceeds;investment_profit+=proceeds-p['associate_basis']
        s['associates_carry']=0.
    if y==p['arctic_loan_year']:
        recovered=p['arctic_loan']*p['arctic_loan_recovery']
        arctic_cash+=recovered;investment_profit-=p['arctic_loan']-recovered;s['loan_carry']=0.
    equity_cash,equity_profit=realize_arctic_equity(y,s,p)
    arctic_cash+=equity_cash;investment_profit+=equity_profit
    common_extra=-general_aro+aro_tax-funding+fund_release
    scale=r.get('scale',0.)
    parent_cost=p['parent_fee']
    # Allocate baseline parent administration out of operating subsidiaries, not twice from group NOPAT.
    restored_parent_cost=p['parent_fee']*scale
    dprofit=(op['nopat']+restored_parent_cost)*w+di+fund_income*w-dinterest-aro_unwind*.72*w
    fprofit=(op['nopat']+restored_parent_cost)*(1-w)+fi+fund_income*(1-w)-finterest-aro_unwind*.72*(1-w)+investment_profit
    s['dc']+=(op['operating_free']+restored_parent_cost+common_extra)*w+di-dinterest-dprincipal
    s['fc']+=(op['operating_free']+restored_parent_cost+common_extra)*(1-w)+fi-finterest-fprincipal+investment_cash+arctic_cash
    s['pc']+=pi-parent_cost;s['pl']+=pi-parent_cost
    parent_cash_before_receipts=s['pc']
    if y==1:s['dc']-=p['other_claims']
    minority_d=0. if s['d_closed'] else p['minority_cash_adjustment']*w
    minority_f=0. if s['f_closed'] else p['minority_cash_adjustment']*(1-w)
    s['dc']-=minority_d;s['fc']-=minority_f
    appropriation=add_legal(s,'d',dprofit,p['appropriation']);add_legal(s,'f',fprofit,0.)
    if min(s['dc'],s['fc'],s['pc']) < -1e-6:
        s['economic_failures'].append(dict(year=y,reason='Entity cash financing shortfall',
          event='after_external_costs_before_receipts',dc=s['dc'],fc=s['fc'],pc=s['pc'],
          opening_parent_cash=opening_parent_cash,parent_interest=pi,parent_admin_cost=parent_cost,
          declared_unpaid_gross=s['dp']+s['fp'],receipts_frozen=y<=p['freeze_receipts_years']))
        return None
    debtleft=s['bank']+s['lease']+sum(b['amount'] for b in s['bonds'])
    # Resource closure does not start a corporate capital-return program.
    next_bank=bank_principal_due(y+1,s['bank'],p)
    next_bond=sum(b['amount'] for b in s['bonds'] if b['year']==y+1)
    unprovided=max(0.,s['aro']-s['fund'])
    operating_floor=0. if closed else p['cash_floor']*min(1.,scale)
    blocked=p['restricted_deposit'] if y<=p['restricted_deposit_years'] else 0.
    dfloor=operating_floor*w+unprovided*w+(s['bank']+s['lease']*w if closed else next_bank)+blocked
    ffloor=operating_floor*(1-w)+unprovided*(1-w)+(sum(b['amount'] for b in s['bonds'])+s['lease']*(1-w) if closed else next_bond)
    old_d=s['dp'];old_f=s['fp'];old_paid=0.;new_paid=0.
    can_collect=y>p['freeze_receipts_years']
    if can_collect:
        old_paid+=settle(s,'d',old_d,p,dfloor);old_paid+=settle(s,'f',old_f,p,ffloor)
    extra=opening_extra_quota(y,opening_accounts,p,r,op,dprincipal+dinterest,fprincipal+finterest,closed)
    d_ordinary=max(dprofit,0.)*p['declare_rate'];f_ordinary=max(fprofit,0.)*p['declare_rate']
    d_desired=d_ordinary+extra['d']['extra_intent']
    f_desired=f_ordinary+extra['f']['extra_intent']
    dd=declare(s,'d',d_desired,p,dfloor);fd=declare(s,'f',f_desired,p,ffloor)
    if can_collect:
        new_paid+=settle(s,'d',dd*p['current_receipt_rate'],p,dfloor)
        new_paid+=settle(s,'f',fd*p['current_receipt_rate'],p,ffloor)
    # Test parent investment carrying amounts AFTER child declarations, BEFORE parent dividends.
    # This is a separate-company legal-profit impairment, not a second group cash expense.
    physical_book=s['producing_book']+s['wip']+s['appraised_book']+sum(q['book'] for q in s['find_queue'])
    dnav=max(0.,s['dc']-s['dp']+w*(physical_book+s['fund']-s['aro'])-s['bank']-s['lease']*w)
    fnav=max(0.,s['fc']-s['fp']+(1-w)*(physical_book+s['fund']-s['aro'])
             -sum(b['amount'] for b in s['bonds'])-s['lease']*(1-w)
             +s['associates_carry']+s['loan_carry']+s['arctic_equity_carry'])
    parent_impairment=max(0.,s['dbasis']-dnav)+max(0.,s['fbasis']-fnav)
    s['dbasis']=min(s['dbasis'],dnav);s['fbasis']=min(s['fbasis'],fnav);s['pl']-=parent_impairment
    # Asset-realization valuation is separate; actual A/B never enters a capital-exit program.
    cap_paid=0.;exit_cost=0.;events=[]  # No automatic corporate exit in A/B.
    policy_profit=dprofit+fprofit+pi-parent_cost
    ordinary_expected=max(0.,policy_profit)*p['dividend_policy']
    expected=ordinary_expected+extra['parent']['extra_intent']
    parent_floor=parent_liquidity_floor(y,s,p,closed,scale)
    div=parent_distribute(s,expected,parent_floor)+cap_paid
    final_general=s['dc']+s['fc']+s['pc'];leak=(old_paid+new_paid)*p['remittance_cost']
    # Cash conservation: internal dividends cancel, only leak/common payments consume consolidated cash.
    external=(op['operating_free']+restored_parent_cost+di+fi+pi+fund_income-parent_cost
      -dinterest-finterest-dprincipal-fprincipal-aro_payment+aro_tax+investment_cash+arctic_cash
      -(p['other_claims'] if y==1 else 0.)-minority_d-minority_f-leak-div-exit_cost)
    residual=(final_general+s['fund'])-(opening_general+opening_fund+external)
    if abs(residual)>1e-5:raise ValueError(('cash conservation',y,residual))
    row=dict(year=y,production=r.get('production',0.),reference_production=r.get('reference_production',0.),
      oil=r.get('oil',None),gas=r.get('gas',None),resource_left=r.get('resource_left',0.),
      investment=r.get('investment',0.),exploration=r.get('exploration',0.),legacy=r.get('legacy',0.),
      development=r.get('development',0.),unused_ceiling=r.get('unused_ceiling',0.),
      dda=r.get('dda',0.),new_aro=r.get('new_aro',0.),**op,
      legacy_new_aro=r.get('legacy_new_aro',0.),discovery_new_aro=r.get('discovery_new_aro',0.),
      investment_cash_receipts=investment_cash,arctic_cash_receipts=arctic_cash,
      minority_cash_deduction=minority_d+minority_f,
      arctic_equity_cash=equity_cash,arctic_equity_realized_profit=equity_profit,
      arctic_equity_carry=s['arctic_equity_carry'],
      dprofit=dprofit,fprofit=fprofit,policy_profit=policy_profit,appropriation=appropriation,
      parent_investment_impairment=parent_impairment,parent_domestic_investment_basis=s['dbasis'],parent_foreign_investment_basis=s['fbasis'],
      domestic_cash=s['dc'],foreign_cash=s['fc'],parent_cash=s['pc'],domestic_legal=s['dl'],
      foreign_legal=s['fl'],parent_legal=s['pl'],statutory_accumulated=s['reserve'],
      declared=dd+fd,received_gross=old_paid+new_paid,receivable_net=(s['dp']+s['fp'])*(1-p['remittance_cost']),
      general_cash=final_general,aro=s['aro'],aro_paid=aro_payment,aro_tax_cash=aro_tax,
      fund=s['fund'],funding=funding,fund_income=fund_income,aro_unwind=aro_unwind,
      debt=debtleft,debt_cash=debt,bank_principal_remaining=s['bank'],
      next_bank_cash_floor=next_bank,domestic_cash_floor=dfloor,foreign_cash_floor=ffloor,
      dividend_and_capital=div,per_share=div/SHARES,
      financing_tax_cash=financing_tax_cash,
      opening_parent_cash=opening_parent_cash,parent_interest=pi,parent_admin_cost=parent_cost,
      parent_cash_before_receipts=parent_cash_before_receipts,parent_cash_floor=parent_floor,
      capital_events=events,exit_cost=exit_cost,resource_closed=closed,cash_residual=residual,
      opening_extra_quota=extra,child_ordinary_intent=d_ordinary+f_ordinary,
      parent_ordinary_intent=ordinary_expected,parent_extra_intent=extra['parent']['extra_intent'],
      general_interest=di+fi+pi,internal_remittance_leak=leak,
      old_payables=opening_payables,new_payables=s['dp']+s['fp'])
    s['rows'].append(row);return row


def cash_power_crosscheck(price,gas,extra_resource_capital,life,discount,aro_tax,release_delay,friction, historical_aro_reclass=0.,capital_interest_overlap=0.):
    """Second method: normalized AFTER-resource-investment operating cash, finite capitalization.
    It is not a second holder path or an audited PV10 roll-forward. NAV bridge is separately bounded.
    Legacy debt cash is discounted by its schedule; no duplicate face-value deduction.
    Future new ARO net economic cost is expensed once, NOT called a disappearing funded asset.
    """
    p=deepcopy(BASE);d=discount
    dom=lambda z:(1-p['domestic_resource_tax'])*z-levy(z)
    ratio=psc_entitlement(price,p)/psc_entitlement(p['oil0'],p)
    oil_delta=589.2*7*(.68*(dom(price)-dom(66.47))*.75
                       +(.32-.15)*(price-66.47)*.65+.15*(price*ratio-66.47))
    gas_delta=984*7*(gas-7.95)*(.70*.70+.30*.60)
    # Scope is explicit: paid new discoveries plus the unrecognized initial-PUD portion.
    # This annualized economic-cost method is coarser than the primary construction/payment timing.
    discovery_aro_annual=p['find_cash']/p['find_unit_cost']*p['new_aro_per_boe']
    legacy_aro_annual=p['pud_initial']*p['legacy_aro_uncovered_fraction']*p['new_aro_per_boe']/life
    items=dict(reported_2025_cfo_less_cash_capital=97487.,normalize_working_capital=7438.,
      remove_temporary_cash_tax_benefit=-2953.,
      bounded_historical_aro_reclassification=historical_aro_reclass,
      bounded_capitalized_interest_overlap=capital_interest_overlap,
      future_discovery_aro_net_economic_cost=-discovery_aro_annual*(1-aro_tax),
      future_legacy_pud_aro_net_economic_cost=-legacy_aro_annual*(1-aro_tax),
      nonlinear_oil_price=oil_delta,gas_price=gas_delta,
      additional_replacement_resource_cash=-extra_resource_capital)
    cash=sum(items.values());op_value=cash*sum(1/(1+d)**y for y in range(1,life+1))
    ds=new_state(p);financing_pv=0.;debt_rows=[]
    for y in range(1,25):
        z=debt_step(y,ds,p)
        payment=z['bank_pay']+z['lease_pay']+z['bond_pay']
        payment+=(z['bank_interest']+z['lease_interest']+z['bond_interest'])*.72
        financing_pv+=payment/(1+d)**y;debt_rows.append(dict(year=y,cash=payment))
    existing_aro_net=p['aro0']*(1-aro_tax)-p['fund0']
    financial_net=p['cash0']-p['other_claims']-financing_pv-existing_aro_net
    operating_buffer=min(60000.,max(0.,financial_net))
    surplus=max(0.,financial_net-operating_buffer)
    liquid_value=surplus*(1-friction)/(1+d)**release_delay
    liquid_value+=operating_buffer*(1-friction)/(1+d)**life+min(0.,financial_net)
    associated=p['associate_value']*p['associate_exit_fraction']/(1+d)**p['associate_exit_year']
    associated+=p['associate_cash']*sum(1/(1+d)**y for y in range(1,p['associate_exit_year']+1))
    loan=p['arctic_loan']*p['arctic_loan_recovery']/(1+d)**p['arctic_loan_year']
    return dict(method='finite_normal_operating_cash_capitalization',cash_bridge=items,
      normal_annual_operating_cash=cash,life=life,discount=d,operating_value=op_value,
      financing_cash_pv=financing_pv,financing_rows=debt_rows,
      existing_aro_net_claim=existing_aro_net,financial_net_before_access=financial_net,
      access_delay=release_delay,access_cost=friction,financial_access_value=liquid_value,
      associates_value=associated,loan_value=loan,
      current_value_per_share=(op_value+liquid_value+associated+loan)/SHARES,
      source_classification_bound={'ARO_usage_0_to_573':historical_aro_reclass,'capitalized_interest_0_to_651':capital_interest_overlap},
      limits='10-15 years cash requires paid reserve replacement. Financial access is a bounded diagnostic, not proof of immediate legal dividends; no averaging with main method.')


CAPITAL_DEFAULTS=dict(policy='A',extra_release_rate=0.,
    asset_domestic_ordinary_delay=1,asset_foreign_ordinary_delay=2,
    asset_domestic_capital_delay=3,asset_foreign_capital_delay=5,
    asset_domestic_capital_cost=.05,asset_foreign_capital_cost=.15,
    asset_parent_capital_delay=1,asset_parent_capital_cost=.03,
    asset_common_fee_years=6,
    asset_general_yield=.015)


def eligible_quota(cash,legal,payable,restricted,buffer,rate):
    q=min(max(0.,legal),max(0.,cash-payable-restricted-buffer))
    return dict(cash_open=cash,legal_open=legal,payable_open=payable,
                restricted_open=restricted,buffer_open=buffer,qualified_open=q,extra_intent=rate*q)


def opening_extra_quota(y,o,p,r,op,ddebt,fdebt,closed):
    """One forecast-year funding window; only balances actually present at OPENING.
    Current resource capex/working investment is already in operating_free.
    Full net ARO reserve and operating cushion are additional liquidity, NOT expenses.
    """
    w=p['domestic_profit_share'];scale=r.get('scale',0.)
    core_cash=op['operating_free']+p['parent_fee']*scale
    aro_reserve=max(0.,o['aro']+r.get('new_aro',0.)-o['fund'])
    base=0. if closed else p['cash_floor']*min(1.,scale)
    dgap=max(0.,ddebt-core_cash*w);fgap=max(0.,fdebt-core_cash*(1-w))
    db=base*w+aro_reserve*w+dgap;fb=base*(1-w)+aro_reserve*(1-w)+fgap
    frozen=max(0,p['freeze_receipts_years']-y+1)
    # Parent must pay current fee and retain one next fee; no forecast child cash here.
    pb=max((0. if closed else p['parent_floor']*min(1.,scale)),p['parent_fee']*(frozen+2))
    blocked=p['restricted_deposit'] if y<=p['restricted_deposit_years'] else 0.
    rate=p['extra_release_rate']
    out={'d':eligible_quota(o['dc'],o['dl'],o['dp'],blocked,db,rate),
         'f':eligible_quota(o['fc'],o['fl'],o['fp'],0.,fb,rate),
         'parent':eligible_quota(o['pc'],o['pl'],0.,0.,pb,rate)}
    out['d'].update(operating_cushion=base*w,aro_reserve=aro_reserve*w,
                    one_year_net_funding_gap=dgap,forecast_debt_cash=ddebt,forecast_operating_cash=core_cash*w)
    out['f'].update(operating_cushion=base*(1-w),aro_reserve=aro_reserve*(1-w),
                    one_year_net_funding_gap=fgap,forecast_debt_cash=fdebt,forecast_operating_cash=core_cash*(1-w))
    out['parent'].update(fee_years=frozen+2,forecast_child_cash_counted=0.)
    return out


def holding_asset(amount,delay,cost,yield_rate,discount):
    """Financial asset quote, not a booked or declared shareholder distribution."""
    return amount*(1+yield_rate)**delay*(1-cost)/(1+discount)**delay


def financial_rights_quote(s,p):
    """Source/time-specific net financial asset quote, NOT an actual issuer distribution.
    Current parent cash is classified before future subsidiary gains are realized.
    Unknown classification is a conditional net-asset range, not an invented legal route.
    """
    live_claims=s['aro']+s['bank']+s['lease']+sum(b['amount'] for b in s['bonds'])
    live_assets=s['fund']+s['associates_carry']+s['loan_carry']+s['arctic_equity_carry']
    if abs(live_claims)>1e-6 or abs(live_assets)>1e-6:
        return dict(status='asset_bridge_unresolved',reason='Unsettled claims/assets cannot be omitted',
                    unsettled_claims=live_claims,unsettled_assets=live_assets,value=None)
    g=p['asset_general_yield'];k=p['discount'];leak=p['remittance_cost']
    horizon=p['asset_common_fee_years'];fee=p['parent_fee']
    child={};events=[];pending_net=0.
    for which in ['d','f']:
        cash=s[which+'c'];pay=s[which+'p'];legal=s[which+'l'];basis=s[which+'basis']
        if cash+1e-7<pay:
            return dict(status='asset_bridge_unresolved',reason='Declared child claim exceeds cash',entity=which,value=None)
        netcash=max(0.,cash-pay);ordinary=min(netcash,max(0.,legal));capital=netcash-ordinary
        tag='domestic' if which=='d' else 'foreign'
        od=p['asset_'+tag+'_ordinary_delay'];cd=p['asset_'+tag+'_capital_delay'];cc=p['asset_'+tag+'_capital_cost']
        if cd<od:raise ValueError('Capital realization cannot precede this specified ordinary-source event')
        # Paying ordinary cash may reduce the value of the parent's remaining investment.
        # That loss is recognized AT this receipt event, not delayed to improve parent profits.
        impairment=max(0.,basis-capital*(1+g)**od) if ordinary>0 else 0.
        remaining_basis=basis-impairment
        child[which]=dict(cash=cash,declared_payable=pay,legal=legal,ordinary_principal=ordinary,
            capital_principal=capital,parent_basis=basis,ordinary_event_impairment=impairment,
            ordinary_delay=od,capital_delay=cd,capital_cost=cc)
        if pay:
            net=pay*(1-leak);pending_net+=net
            events.append(dict(year=1,priority=0,source=which+'_declared_receivable',cash=net,
                profit_change=0.,book_reduction=net,kind='declared',principal=pay))
            if g:
                income=pay*g*(1-leak)
                events.append(dict(year=1,priority=1,source=which+'_interest_on_cash_awaiting_payment',
                    cash=income,profit_change=income,book_reduction=0.,kind='ordinary',principal=pay*g))
        if ordinary:
            proceeds=ordinary*(1+g)**od*(1-leak)
            events.append(dict(year=od,priority=2,source=which+'_ordinary_profit_cash',cash=proceeds,
                profit_change=proceeds-impairment,book_reduction=impairment,kind='ordinary',principal=ordinary))
        if capital:
            proceeds=capital*(1+g)**cd*(1-cc)
            events.append(dict(year=cd,priority=3,source=which+'_capital_realization',cash=proceeds,
                profit_change=proceeds-remaining_basis,book_reduction=remaining_basis,kind='capital',principal=capital))
        elif remaining_basis>1e-7:
            raise ValueError('No remaining child cash but parent basis was not impaired')
    # Common fee horizon is fixed by the selected financial-management budget, independent of unknown size.
    # Only already-declared, cash-backed P is allowed to finance fees after its stated year-one receipt.
    total_reserve=fee*sum((1+g)**(-i) for i in range(1,horizon+1))
    first_fee=fee/(1+g) if horizon else 0.
    opening_reserve=max(first_fee,total_reserve-pending_net/(1+g)) if horizon else 0.
    opening_reserve=max(0.,opening_reserve)
    later_reserve=max(0.,(total_reserve-opening_reserve)*(1+g)) if horizon else 0.
    later_reserve=min(pending_net,later_reserve)
    if s['pc']+1e-7<opening_reserve:
        return dict(status='conditional_access_funding_unresolved',value=None,
            reason='Selected cost-first asset-access budget lacks first-period own funding; not proof of group asset worthlessness',
            parent_cash=s['pc'],minimum_opening_fee_reserve=opening_reserve,
            declared_cash_available_only_after_first_fee=pending_net,common_fee_years=horizon,
            gross_group_financial_assets=s['pc']+s['dc']+s['fc'],
            no_free_parent_funding=True,operating_path_failure=False)
    # A small capacity ledger, not a law/approval simulator. Quoted claims are removed from free capacity
    # at their source date; capital claims retain their own further wait. Unknown stays protected in NAV.
    ledger=dict(legal=s['pl'],capital=s['cap'],undistributable=s['undistributable'],
        other_book=s['dbasis']+s['fbasis']+pending_net,protected_unknown_cash=0.,fee_account=opening_reserve,
        same_date_pending_cash=0.)
    pieces=[];fee_rows=[];capacity_rows=[]
    def allocate(amount,year,source):
        if amount< -1e-7:raise ValueError('Negative net source after common-fee earmark')
        amount=max(0.,amount)
        nav=amount+ledger['same_date_pending_cash']+ledger['other_book']+ledger['protected_unknown_cash']+ledger['fee_account']
        headroom=max(0.,nav-ledger['capital']-ledger['undistributable'])
        ordinary=min(amount,max(0.,ledger['legal']),headroom)
        ledger['legal']-=ordinary;amount-=ordinary
        if ordinary:
            pieces.append(dict(source=source,source_year=year,right='existing_or_realized_ordinary_profit',
                amount=ordinary,extra_delay=0,value_at_boundary=ordinary/(1+k)**year))
        offset=min(ledger['capital'],max(0.,-ledger['legal'])) if amount else 0.
        ledger['capital']-=offset;ledger['legal']+=offset
        remaining_nav=amount+ledger['same_date_pending_cash']+ledger['other_book']+ledger['protected_unknown_cash']+ledger['fee_account']
        known=min(amount,max(0.,ledger['capital']),max(0.,remaining_nav-ledger['undistributable']))
        ledger['capital']-=known;amount-=known
        if known:
            delay=p['asset_parent_capital_delay'];cost=p['asset_parent_capital_cost']
            pieces.append(dict(source=source,source_year=year,right='known_capital_capacity_at_source_date',
                amount=known,extra_delay=delay,cost=cost,
                value_at_boundary=holding_asset(known,delay,cost,g,k)/(1+k)**year))
        if amount:
            ledger['protected_unknown_cash']+=amount
            pieces.append(dict(source=source,source_year=year,right='conditional_unclassified_financial_asset',
                amount=amount,extra_delay=None,value_at_boundary=amount/(1+k)**year,
                access_route='not quantified; net-financial-asset reference plus explicit price range, not an actual payment'))
        capacity_rows.append(dict(year=year,source=source,nav_before_source_allocation=nav,
            ordinary_headroom=headroom,ordinary=ordinary,known_capital=known,unknown=amount,
            capital_loss_offset=offset,legal_after=ledger['legal'],capital_after=ledger['capital'],
            protected_equity=ledger['undistributable'],other_book_after=ledger['other_book']))
    # No unrealized child gain can modify this current-parent decision.
    allocate(s['pc']-opening_reserve,0,'current_parent_own_cash')
    events.sort(key=lambda e:(e['year'],e['priority'],e['source']))
    final_event=max([horizon]+[e['year'] for e in events])
    reserve_still_needed=later_reserve
    for year in range(1,final_event+1):
        if year<=horizon:
            opening=ledger['fee_account'];interest=opening*g
            ledger['fee_account']+=interest-fee;ledger['legal']+=interest-fee
            if ledger['fee_account']< -1e-6:
                return dict(status='conditional_access_funding_unresolved',value=None,
                    reason='Common fee cash fails before same-year receipts',failed_year=year,
                    fee_account=ledger['fee_account'],capacity_rows=capacity_rows,fee_rows=fee_rows,
                    gross_group_financial_assets=s['pc']+s['dc']+s['fc'],operating_path_failure=False)
            fee_rows.append(dict(year=year,opening=opening,interest=interest,fee=fee,
                before_receipts=ledger['fee_account'],declared_receipt_fee_funding=0.))
        arriving=[z for z in events if z['year']==year]
        # Same annual date: recognize ALL contemporaneous gains/losses before any allocation.
        ledger['other_book']-=sum(e['book_reduction'] for e in arriving)
        ledger['legal']+=sum(e['profit_change'] for e in arriving)
        ledger['same_date_pending_cash']=sum(e['cash'] for e in arriving)
        for e in arriving:
            ledger['same_date_pending_cash']-=e['cash']
            earmark=min(e['cash'],reserve_still_needed) if e['kind']=='declared' and year==1 else 0.
            reserve_still_needed-=earmark;ledger['fee_account']+=earmark
            if earmark:fee_rows[-1]['declared_receipt_fee_funding']+=earmark
            allocate(e['cash']-earmark,year,e['source'])
        if year<=horizon:fee_rows[-1]['closing_after_receipts']=ledger['fee_account']
    if abs(ledger['fee_account'])>1e-6 or abs(reserve_still_needed)>1e-6:
        raise ValueError('Common fee funding does not reconcile')
    known_value=sum(z['value_at_boundary'] for z in pieces if z['right']!='conditional_unclassified_financial_asset')
    unknown_value=sum(z['value_at_boundary'] for z in pieces if z['right']=='conditional_unclassified_financial_asset')
    unknown_nominal=sum(z['amount'] for z in pieces if z['right']=='conditional_unclassified_financial_asset')
    estimate=known_value+unknown_value
    return dict(status='source_specific_financial_asset_reference_with_conditional_unknown',value=estimate,
        value_definition='Known source-specific rights plus unclassified net-financial-asset reference; unknown not certified cash access',
        actual_dividends_or_capital_payments_created=0.,corporate_entities_closed=False,
        parent_fee_reserve=opening_reserve,common_fee_years=horizon,
        declared_receipts_earmarked_for_later_fees=later_reserve,
        common_fee_asset_cost_at_boundary=opening_reserve+later_reserve/(1+k),
        fee_reserve_rows=fee_rows,fee_reserve_ending=ledger['fee_account'],
        child_principals=child,source_events=events,source_pieces=pieces,parent_capacity_rows=capacity_rows,
        parent_unknown_classification_principal=unknown_nominal,unknown_classification_estimate=unknown_value,
        unknown_nominal_time_basis='Sum of source-event amounts; inspect source years, not an H-date book balance',
        known_rights_value=known_value,classification_diagnostic_range=[known_value,estimate],
        classification_diagnostic_scope='Fixed common-fee/source-allocation price sensitivity only; not a re-simulated legal or financing path',
        unknown_materiality_flag=unknown_value>max(estimate,1.)*.05,
        unknown_specific_incremental_cost_budget=None,unknown_amount_triggers_common_fee_extension=False,
        permanent_principal_retention_income_reference=max(0.,(s['dc']+s['fc'])*g*(1-leak)+s['pc']*g-fee),
        permanent_principal_retention_income_capitalization_reference=max(0.,(s['dc']+s['fc'])*g*(1-leak)+s['pc']*g-fee)/k,
        retention_reference_limit='Different governance assumption, not A actual dividends or certified legal lower bound.',
        nominal_cash_before_fee_reserve=s['pc']+s['dc']+s['fc'],
        internal_receivable_principal_not_added_twice=s['dp']+s['fp'],
        debt_face_deducted_again=0.,fund_added_again=0.,future_operating_fcfe_added_again=0.,
        interpretive_limit='Conditional source-group asset estimate, not automatic liquidation; classification uncertainty requires materiality review.')


def resource_asset_run(p):
    if p['capital_return']:raise ValueError('A/B may not call the old automatic capital-exit program')
    s=new_state(p);closed=False;closure=None;first5=None;failed=None
    complete=deepcopy({k:v for k,v in s.items() if k!='rows'})
    settlement_boundary=None
    for y in range(1,p['max_resource_years']+30):
        if not closed:
            r=resources(y,s,p);op=operating(y,r,s,p)
            no_pipeline=not s['dev_queue'] and not s['find_queue'] and y>p['find_years']
            exhausted=r['reference_production']<1e-8 and no_pipeline
            uneconomic=op['operating_free']<0 and r['investment']<1e-8 and no_pipeline
            if exhausted or uneconomic:
                closed=True;s['resource_end']=y
                writeoff=s['producing_book']+s['wip']+s['appraised_book']
                op['nopat']-=writeoff;op['operating_free']+=s['wc'];s['wc']=0.
                closure=dict(year=y,reason='uneconomic' if uneconomic else 'resource_exhaustion',
                    unproduced=s['pd']+s['pud']+s['appraised'],book_writeoff=writeoff)
                s['producing_book']=s['wip']=s['appraised_book']=0.
        else:
            r=dict(production=0.,reference_production=0.,scale=0.,resource_left=0.,new_aro=0.)
            op=dict(nopat=0.,operating_free=0.,current_tax_capacity=0.,working_cash=0.,cash_tax_timing=0.)
        row=annual(y,s,p,r,op,closed)
        if row is None:
            failed=dict(year=y,state=deepcopy({k:v for k,v in s.items() if k!='rows'}),resource_step=r,operating_step=op)
            break
        complete=deepcopy({k:v for k,v in s.items() if k!='rows'})
        if y==5:first5=deepcopy(complete)
        debt=s['bank']+s['lease']+sum(b['amount'] for b in s['bonds'])
        investment_carry=s['associates_carry']+s['loan_carry']+s['arctic_equity_carry']
        if closed and debt<1e-7 and s['aro']<1e-7 and investment_carry<1e-7:
            settlement_boundary=y;break
        if not closed and y>=p['max_resource_years']:
            s['economic_failures'].append(dict(year=y,reason='Resource visibility exhausted; no forced corporate or field closure'))
            break
    if settlement_boundary is None and not s['economic_failures']:
        s['economic_failures'].append(dict(year=y,reason='Financial boundary unresolved'))
    quote=None if s['economic_failures'] else financial_rights_quote(s,p)
    valid=quote is not None and quote['value'] is not None and first5 is not None
    last=s['rows'][-1]['year'] if s['rows'] else 0;k=p['discount']
    pv5=sum(z['dividend_and_capital']/(1+k)**z['year'] for z in s['rows'] if z['year']<=5)
    later=sum(z['dividend_and_capital']/(1+k)**(z['year']-5) for z in s['rows'] if z['year']>5)
    asset5=quote['value']/(1+k)**(last-5) if valid else None
    value5=later+asset5 if valid else None;value0=pv5+value5/(1+k)**5 if valid else None
    inventory=s['pd']+s['pud']+s['appraised']+sum(q['units'] for q in s['find_queue']+s['dev_queue'])
    conservation=p['resource_initial']+s['new_found']-s['resource_consumed']-inventory
    # Exact cash identity provides the financing-after cash-to-assets bridge; NOT a second valuation sum.
    startcash=p['cash0']+p['fund0']
    cashbridge=dict(start_general_plus_fund=startcash,
        operating_after_resource_capital=sum(z['operating_free'] for z in s['rows']),
        restored_parent_operating_allocation=sum(p['parent_fee']*(z['reference_production']/p['production0']) for z in s['rows']),
        actual_parent_fees=-sum(z['parent_admin_cost'] for z in s['rows']),
        actual_general_deposit_income=sum(z['general_interest'] for z in s['rows']),
        actual_fund_income=sum(z['fund_income'] for z in s['rows']),
        actual_aro_paid=-sum(z['aro_paid'] for z in s['rows']),aro_cash_tax=sum(z['aro_tax_cash'] for z in s['rows']),
        actual_financing_principal_and_net_interest=-sum(z['debt_cash']['bank_pay']+z['debt_cash']['lease_pay']+z['debt_cash']['bond_pay']
            +z['debt_cash']['bank_interest']+z['debt_cash']['lease_interest']+z['debt_cash']['bond_interest']-z['financing_tax_cash'] for z in s['rows']),
        actual_internal_transfer_cost=-sum(z['internal_remittance_leak'] for z in s['rows']),
        actual_owner_cash=-sum(z['dividend_and_capital'] for z in s['rows']),
        investment_and_arctic_cash=sum(z['investment_cash_receipts']+z['arctic_cash_receipts'] for z in s['rows']),
        minority_cash_deduction=-sum(z['minority_cash_deduction'] for z in s['rows']),
        other_initial_claims=-p['other_claims'] if s['rows'] else 0.,
        closing_general_plus_fund=complete['dc']+complete['fc']+complete['pc']+complete['fund'])
    movement=sum(v for k,v in cashbridge.items() if k not in ['start_general_plus_fund','closing_general_plus_fund'])
    cashbridge['reconciliation_error']=startcash+movement-cashbridge['closing_general_plus_fund']
    cashbridge['scope']='Complete rows only; failed partial year is not included'
    latercash=year5_cash_reconciliation(s['rows'],first5,complete,p) if first5 else None
    return dict(status='computed_conditional' if valid else 'unresolved',method='finite_resource_cash_plus_financial_asset_rights',
        as_of=AS_OF,parameters=p,distributions_per_share=[z['per_share'] for z in s['rows'][:5]],
        current_value_per_share=value0/SHARES if valid else None,year5_value_per_share=value5/SHARES if valid else None,
        year5_bridge=dict(pv_first5_cash_at_current=pv5,pv_later_actual_cash_at_Y5=later,
                         financial_assets_at_boundary_to_Y5=asset5,year5_total=value5,
                         separate_future_fcfe_PV_added=0.,separate_starting_cash_added=0.),
        year5_state=first5,financial_asset_quote=quote,cash_to_asset_bridge=cashbridge,
        year5_to_boundary_cash_reconciliation=latercash,
        closure=closure,financial_settlement_boundary=settlement_boundary,
        entities_remain_unclosed=not s['d_closed'] and not s['f_closed'] and not s['parent_return_done'],
        rows=s['rows'],last_complete_year=last,last_complete_state=complete,failed_event_snapshot=failed,
        economic_failures=s['economic_failures'],reference_resource_conservation_error=conservation,
        minimum_parent_cash_year_end=min((z['parent_cash'] for z in s['rows']),default=p['parent_cash0']),
        minimum_parent_cash_before_receipts=min([p['parent_cash0']]+[z['parent_cash_before_receipts'] for z in s['rows']]
            +([failed['state']['pc']] if failed else [])),
        quote_classification_value_range_per_share=None if not valid else
            [(pv5+(later+a/(1+k)**(last-5))/(1+k)**5)/SHARES for a in quote['classification_diagnostic_range']])


def year5_cash_reconciliation(rows,start,end,p):
    rr=[z for z in rows if z['year']>5]
    parts=dict(opening_general_plus_fund=start['dc']+start['fc']+start['pc']+start['fund'],
        operating_after_all_resource_capital=sum(z['operating_free'] for z in rr),
        parent_allocation_restore=sum(p['parent_fee']*z['reference_production']/p['production0'] for z in rr),
        parent_cost=-sum(z['parent_admin_cost'] for z in rr),
        deposit_and_fund_income=sum(z['general_interest']+z['fund_income'] for z in rr),
        aro_actual_cash_and_tax=sum(-z['aro_paid']+z['aro_tax_cash'] for z in rr),
        debt_principal_and_after_tax_interest=-sum(z['debt_cash']['bank_pay']+z['debt_cash']['lease_pay']+z['debt_cash']['bond_pay']
            +z['debt_cash']['bank_interest']+z['debt_cash']['lease_interest']+z['debt_cash']['bond_interest']-z['financing_tax_cash'] for z in rr),
        investment_recovery_and_income=sum(z['investment_cash_receipts']+z['arctic_cash_receipts'] for z in rr),
        minority_cash=-sum(z['minority_cash_deduction'] for z in rr),
        remittance_cost=-sum(z['internal_remittance_leak'] for z in rr),
        owner_distributions=-sum(z['dividend_and_capital'] for z in rr),
        closing_general_plus_fund=end['dc']+end['fc']+end['pc']+end['fund'])
    parts['reconciliation_error']=sum(v for key,v in parts.items() if key!='closing_general_plus_fund')-parts['closing_general_plus_fund']
    parts['valuation_note']='Reconciliation only. Do not PV these items and add the closing cash again.'
    return parts


def configured(changes=None):
    p=deepcopy(BASE);p.update(CAPITAL_DEFAULTS)
    if changes:p.update(changes)
    return p


def empty_asset_state(cash=100.,legal=0.,capital=100.):
    p=configured(dict(cash0=cash,parent_cash0=cash,parent_legal0=legal,share_capital=capital,
        initial_declared_gross=0.,domestic_legal0=0.,foreign_legal0=0.,
        domestic_investment_basis=0.,foreign_investment_basis=0.,bank0=0.,lease0=0.,bond_scale=0.,
        aro0=0.,fund0=0.,associate_basis=0.,arctic_loan=0.,arctic_equity_basis=0.,arctic_equity_reference_basis=0.,
        parent_undistributable=0.,producing_book0=0.,wip0=0.,resource_initial=0.,pud_initial=0.,
        aro_asset_producing0=0.,aro_asset_wip0=0.))
    s=new_state(p);return s


def capital_fixtures():
    p=configured(dict(parent_fee=0.,discount=.10,asset_general_yield=0.,asset_parent_capital_delay=2,
                      asset_parent_capital_cost=.05,asset_common_fee_years=2))
    a=financial_rights_quote(empty_asset_state(),p)
    b=financial_rights_quote(empty_asset_state(100.,100.,0.),p)
    unclassified=financial_rights_quote(empty_asset_state(100.,0.,0.),p)
    f=configured(dict(parent_fee=1.,discount=.10,asset_general_yield=.02,asset_parent_capital_delay=2,
                      asset_parent_capital_cost=.05,asset_common_fee_years=2))
    c=financial_rights_quote(empty_asset_state(),f)
    # Child cash cannot create the parent's opening liquidity or pay its prefunded fees.
    zero_parent=empty_asset_state(0.,0.,100.);zero_parent.update(dc=100.,dl=100.,dbasis=100.)
    d=financial_rights_quote(zero_parent,f)
    return dict(no_legal_profit_but_known_capital=a,ordinary_financial_asset=b,unclassified_equity_asset=unclassified,waiting_fees=c,
        no_free_parent_funding=d,mixed_rights=mixed_rights_fixtures(),
        retained_Y6_cash_value_at_current=a['value']/1.1**6,
        retained_Y6_expected_once=95./1.1**8,
        retained_Y6_wrong_double_count=100./1.1**6+95./1.1**8,
        quota=eligible_quota(100.,100.,20.,10.,30.,.10),
        quota_no_legal=eligible_quota(100.,0.,20.,10.,30.,.10),
        quota_parent_no_cash=eligible_quota(0.,100.,0.,0.,0.,.10))


def mixed_rights_fixtures():
    p=configured(dict(parent_fee=0.,discount=.10,asset_general_yield=0.,asset_parent_capital_delay=2,
        asset_parent_capital_cost=0.,asset_domestic_capital_delay=3,asset_domestic_capital_cost=0.,
        remittance_cost=0.,asset_common_fee_years=2))
    one=empty_asset_state(100.,100.,100.);one.update(dc=100.,dl=0.,dbasis=100.)
    two=empty_asset_state(100.,0.,100.);two.update(dc=100.,dl=0.,dbasis=0.)
    protected=deepcopy(one);protected['undistributable']=50.
    basis=empty_asset_state(0.,0.,100.);basis.update(dc=100.,dl=100.,dbasis=100.)
    eps0=empty_asset_state(102.,0.,100.);eps1=empty_asset_state(102.,0.,99.999)
    fee_p=deepcopy(p);fee_p.update(parent_fee=1.)
    funded=empty_asset_state(1.,3.,0.);funded.update(dc=2.,dp=2.,dbasis=0.)
    return dict(current_ordinary_plus_later_cost_return=financial_rights_quote(one,p),
        current_capital_plus_later_gain=financial_rights_quote(two,p),
        protected_nav=financial_rights_quote(protected,p),
        child_ordinary_requires_parent_basis_impairment=financial_rights_quote(basis,p),
        unknown_zero=financial_rights_quote(eps0,fee_p),
        unknown_epsilon=financial_rights_quote(eps1,fee_p),
        declared_receipt_funds_later_fees=financial_rights_quote(funded,fee_p))


def nonzero_policy_fixture(policy):
    p=configured(dict(policy=policy,extra_release_rate=0. if policy=='A' else .10,
        cash0=150.,parent_cash0=50.,domestic_cash_share=1.,domestic_profit_share=1.,
        parent_legal0=50.,domestic_legal0=100.,foreign_legal0=0.,initial_declared_gross=0.,
        parent_undistributable=0.,share_capital=0.,domestic_investment_basis=0.,foreign_investment_basis=0.,
        bank0=0.,lease0=0.,bond_scale=0.,aro0=0.,fund0=0.,aro_carry=0.,fund_yield=0.,aro_tax=0.,
        aro_paid_first5=[0.,0.],new_fund_first5=0.,general_yield=0.,parent_fee=1.,other_claims=0.,
        minority_cash_adjustment=0.,producing_book0=0.,wip0=0.,associate_cash=0.,associate_basis=0.,
        associate_exit_year=100,arctic_loan=0.,arctic_equity_basis=0.,arctic_equity_reference_basis=0.,
        remittance_cost=0.,cash_floor=0.,parent_floor=0.))
    s=new_state(p)
    for y in [1,2]:
        r=dict(production=1.,reference_production=1.,scale=1.,resource_left=10.,new_aro=0.,investment=6.)
        annual(y,s,p,r,dict(nopat=20.,operating_free=14.,current_tax_capacity=0.),False)
    return dict(rows=s['rows'],ending={k:v for k,v in s.items() if k!='rows'},parameters=p)


def new_json(path,value):
    raw=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    with path.open('xb') as out:out.write(raw)


def validate_capital_results(payload):
    h=payload['hand_fixtures']
    assert abs(h['no_legal_profit_but_known_capital']['value']-95./1.1**2)<1e-8
    assert h['no_legal_profit_but_known_capital']['actual_dividends_or_capital_payments_created']==0.
    assert abs(h['ordinary_financial_asset']['value']-100.)<1e-8
    assert abs(h['unclassified_equity_asset']['value']-100.)<1e-8
    assert h['unclassified_equity_asset']['classification_diagnostic_range']==[0.,100.]
    assert h['unclassified_equity_asset']['parent_unknown_classification_principal']==100.
    assert abs(h['waiting_fees']['value']-((100.*1.02**2-1.02-1.)*.95/1.1**2))<1e-8
    assert h['no_free_parent_funding']['value'] is None
    assert abs(h['retained_Y6_cash_value_at_current']-h['retained_Y6_expected_once'])<1e-8
    assert h['quota']['qualified_open']==40. and h['quota']['extra_intent']==4.
    assert h['quota_no_legal']['extra_intent']==0. and h['quota_parent_no_cash']['extra_intent']==0.
    mix=h['mixed_rights'];a=1/1.1**3;b=1/1.1**2
    assert abs(mix['current_ordinary_plus_later_cost_return']['value']-(100.+100.*a*b))<1e-8
    assert abs(mix['current_capital_plus_later_gain']['value']-(100.*b+100.*a))<1e-8
    assert mix['protected_nav']['parent_capacity_rows'][0]['ordinary']==50.
    assert abs(mix['child_ordinary_requires_parent_basis_impairment']['value']-100./1.1**3)<1e-8
    z=mix['unknown_zero'];e=mix['unknown_epsilon']
    assert z['common_fee_years']==e['common_fee_years']==2
    assert z['common_fee_asset_cost_at_boundary']==e['common_fee_asset_cost_at_boundary']==2.
    assert abs((e['value']-z['value'])-.001*(1-b))<1e-8
    assert abs(mix['declared_receipt_funds_later_fees']['value']-1/1.1)<1e-8
    assert mix['declared_receipt_funds_later_fees']['parent_fee_reserve']==1.
    assert mix['declared_receipt_funds_later_fees']['declared_receipts_earmarked_for_later_fees']==1.
    assert mix['declared_receipt_funds_later_fees']['fee_reserve_rows'][0]['before_receipts']==0.

    expected={'A':[(9.,105.76,49.24),(9.,109.21,50.79)],
              'B':[(13.8,97.76,52.44),(14.044,91.734,58.422)]}
    for label in ['A','B']:
        rr=payload['policy_fixtures'][label]['rows'];assert len(rr)==2
        for row,(paid,dc,pc) in zip(rr,expected[label]):
            assert abs(row['dividend_and_capital']-paid)<1e-8,(label,row['year'],'D')
            assert abs(row['domestic_cash']-dc)<1e-8 and abs(row['parent_cash']-pc)<1e-8
            assert row['parent_admin_cost']==1. and row['investment']==6.
    for name,result in payload['paths'].items():
        assert result['entities_remain_unclosed'],(name,'automatic corporate closure')
        assert abs(result['reference_resource_conservation_error'])<1e-6,(name,'resource conservation')
        assert abs(result['cash_to_asset_bridge']['reconciliation_error'])<1e-5,(name,'cash reconciliation')
        if result['year5_to_boundary_cash_reconciliation']:
            assert abs(result['year5_to_boundary_cash_reconciliation']['reconciliation_error'])<1e-5
        for row in result['rows']:
            assert not row['capital_events'] and row['exit_cost']==0.
            assert abs(row['cash_residual'])<1e-5
            if result['parameters']['policy']=='A':assert row['parent_extra_intent']==0.
        if result['status']=='computed_conditional':
            d=result['parameters']['discount'];v5=result['year5_value_per_share']
            dd=result['distributions_per_share'];assert len(dd)==5
            assert abs(sum(v/(1+d)**(i+1) for i,v in enumerate(dd))+v5/(1+d)**5-result['current_value_per_share'])<1e-8
            q=result['financial_asset_quote']
            assert q['future_operating_fcfe_added_again']==0. and q['debt_face_deducted_again']==0.
            assert abs(q['fee_reserve_ending'])<1e-6
    assert len(payload['paths'])==9

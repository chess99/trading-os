#!/usr/bin/env python3
"""Zijin 2026-Q3. CNY billion; copper/lithium kt, gold tonnes.
Finite, recoverable reserve constrained operating model + two-level financing.
No security quotation is an input. All assumptions are in this file.
"""
import json, math, copy
from pathlib import Path
CUTOFF='2026-10-29T11:05:00Z'
# name, metal, look-through equity, 2027..31 saleable output (100% project),
# recoverable inventory at start 2027, maximum years, resource-charge-exclusive accounting unit cost (including DA),
# depreciation/unit, sustaining/unit, five-year development capital (100% project, bn)
# Reserve caps are research budgets, not new company reserve certifications.
MINES=[
 ('巨龙','cu',.5816,[300,330,350,350,350],17000,40,31000,5000,6000,[1.2,.8,.6,.4,.4]),
 ('塞紫金上带','cu',1,[180,190,200,200,195],2300,14,24000,4500,6000,[1,1,1,.6,.5]),
 ('塞紫铜','cu',.63,[125,135,145,150,150],5000,24,39000,6000,7500,[1,1,1,.8,.5]),
 ('科卢韦齐','cu',.67,[115,110,100,85,70],500,6,34000,4000,5000,[.2,.2,.1,.1,0]),
 ('多宝山铜山','cu',1,[108,115,120,125,125],2500,30,30000,5000,6000,[1,1.2,1,.8,.5]),
 ('紫金山','cu',1,[85,80,70,60,50],450,8,29000,4000,5000,[.1,.1,.1,0,0]),
 ('朱诺','cu',.5359,[38,65,76,76,76],1800,25,33000,5000,6500,[1,.3,.2,.2,.2]),
 ('其他控股铜矿','cu',.76,[80,85,90,90,90],1300,18,34000,5000,6500,[.7,.8,.8,.6,.4]),
 # Only direct Kamoa equity. Indirect Ivanhoe holding remains a separate financial asset.
 ('卡莫阿直接','cu',.396,[350,420,480,500,500],14500,35,44000,9000,10000,[6,4,3,2,2]),
 ('阿瑞那二期','cu',1,[0,0,0,20,70],2300,30,36000,6000,7000,[2,2.5,2.5,1.5,.5]),
 ('武里蒂卡','au',.5897,[8.8,9,9,9,9],130,15,265,35,55,[.2,.2,.2,.2,.2]),
 ('阿基姆','au',.85,[8,9,10,10,10],177,22,400,50,80,[.6,.7,.7,.4,.3]),
 ('罗斯贝尔','au',.8075,[8,8.5,9,9,9],145,22,350,45,70,[.5,.7,.7,.4,.3]),
 ('诺顿','au',.85,[8,8,8,8,8],94,14,430,55,80,[.3,.3,.3,.3,.3]),
 ('瑞果多','au',.85,[7,8,9,10,10],76,16,310,40,65,[.5,.6,.6,.3,.2]),
 ('泽拉夫尚','au',.595,[6,6,6,6,6],62,12,280,35,60,[.2,.3,.3,.2,.1]),
 ('奥罗拉','au',.85,[5,5.5,6,6,6],75,20,320,50,75,[.4,.4,.4,.3,.2]),
 # Domestic/associated gold basket covers Longnan, Shanxi, Serbia associated gold and other assets.
 # 0.836 is H1 residual attributable output / residual gross output, recomputed in notes.
 ('其他金矿及伴生金','au',.8388361627233438,[46,47,49,50,50],780,22,290,40,65,[2,2.5,2.5,2,1.5]),
 # Chifeng 25.85% ownership * 82.28% underlying mine economics; no full-consolidation windfall.
 ('赤峰矿山','au',.2585*.8228,[15,16,17,18,18],210,18,400,45,75,[.8,.9,.9,.7,.5]),
 ('拉果措','li',.63,[25,30,35,40,40],1800,30,55000,7000,9000,[.5,.5,.4,.3,.2]),
 ('3Q','li',1,[25,30,35,40,40],1500,30,50000,7000,9000,[.5,.5,.4,.3,.2]),
 ('湘源','li',1,[40,45,50,50,50],1000,25,60000,6000,9000,[.4,.4,.3,.3,.2]),
 ('马诺诺','li',.549,[30,55,75,90,100],2800,30,55000,7000,10000,[2,1.5,1,.5,.4]),
 ('藏格锂','li',.262,[14,15,15,15,15],400,25,30000,3000,5000,[.1,.1,.1,.1,.1]),
]
BASE={'gold':850.,'copper':80000.,'lithium':90000.,'inflation':.015,'tax':.24,
      'royalty':.055,'cost_real_growth':.003,'upstream_fraction':.65,
      'equity_rate':.095,'ordinary_debt_rate':.033,'deposit_rate':.015,
      'payout_first5':.35,'payout_later':.70,'scenario':'base', 'price_shift':1.,
      'cost_shift':1.,'volume_shift':1.,'growth_shift':1.,'reserve_shift':1.,
      'subcash_factor':.78,'subdebt_factor':.75,'assets_factor':1.,'acquisition_prepaid':0.,'convert_2029':False}
# Share counts are billion shares, money CNY billion. No stock quotation input.
ISSUED=26.590798241
TRANSFERRED=.0729368
TREASURY_ORIGINAL=.077474592
TREASURY_REMAINING=.004537792
ESOP_PRICE=18.56
ESOP_RECEIVABLE=TRANSFERRED*ESOP_PRICE
TREASURY_COST=2.499993348
TRANSFER_COST=TREASURY_COST*TRANSFERRED/TREASURY_ORIGINAL
REMAINING_COST=TREASURY_COST-TRANSFER_COST
OTHER_TREASURY_OBLIGATION=3.434374064-TREASURY_COST # old 2025 plan, not physical 2026 treasury shares
OPTIONS=.0262
# 11.15 last formally announced; .38+.42 subsequently paid distributions.
OPTION_BUDGET_PRICE=11.15-.38-.42
SHARES=ISSUED-TREASURY_REMAINING+OPTIONS
EMPLOYEE_CASH=ESOP_RECEIVABLE+OPTIONS*OPTION_BUDGET_PRICE

# Includes an accounting allocation of existing aggregate overhead, NOT a grant-date FV.
# H1 expense annualized is a disclosed historical scale proxy. Core operating profit/total
# overhead unchanged; cash overhead is lower by the noncash allocation. 0/2x and incremental
# expense sensitivities explicitly expose this unknown allocation. No tax shield assumed.
SBC_ANNUAL_PROXY=.142533175*2

def capital_opening():
    return dict(issued=ISSUED, treasury_shares=TREASURY_REMAINING,
        participating=ISSUED-TREASURY_REMAINING, registered=2.657753314,
        paid_up=2.659079824, transfer_shares=TRANSFERRED, transfer_receivable=ESOP_RECEIVABLE,
        issuer_cash_receipt_confirmed=False, transfer_cost=TRANSFER_COST,
        transfer_capital_surplus=ESOP_RECEIVABLE-TRANSFER_COST,
        capital_surplus=31.787211892+ESOP_RECEIVABLE-TRANSFER_COST,
        treasury_cost=REMAINING_COST, old_plan_treasury_obligation=OTHER_TREASURY_OBLIGATION,
        total_treasury_contra_equity=REMAINING_COST+OTHER_TREASURY_OBLIGATION,
        net_equity_delta=ESOP_RECEIVABLE, repeated_repurchase_cash=0.,
        sbc_fair_value_disclosed=False)

def option_conditions(revenue_growth, revenue_peer_threshold, roe, roe_peer_threshold, debt_ratio, personal_grade, registration, tranche):
    required=.15 if tranche==2 else .20
    return revenue_growth>=max(required,revenue_peer_threshold) and roe>=max(.12,roe_peer_threshold) and debt_ratio<=.65 and personal_grade in ('A','B') and registration

def option_quantity(p):
    # Explicit company/individual/registration conditions; non-market failure cancels options,
    # never already issued ordinary shares. Two remaining tranches each 13.1 million.
    return .0131*sum(bool(p[k]) and option_conditions(.25,.20,.16,.15,.60,'B',p['option_registration'],n) for k,n in [('option_tranche2_eligible',2),('option_tranche3_eligible',3)])

def economic_shares(p):
    return ISSUED-TREASURY_REMAINING+option_quantity(p)+(TREASURY_REMAINING if p['future_talent_approved'] else 0.)

def sbc_budget(p,t):
    # Existing compensation is explicitly allocated inside original overhead, with parent expense.
    # Not legal accounting certification; actual allocation/grant FV remains unknown.
    return SBC_ANNUAL_PROXY*p['sbc_scale']*([1,1,10/12][t-1] if t<=3 else 0.)

# Parent debt + fully owned offshore CB liability plus residual project debt share.
PARENT_DEBT=10.326890067+22.075727251+20.929911054+43.254379669
GROUP_BOOK_DEBT=35.207599259+27.941847860+41.904209712+64.633685387+.222222739-.012086635 # H1 current stream proxy removed; operating stream already budgeted
CB_BOOK=12.9+8.6 # Q3 does not disaggregate; bounded by H1 liability and Q3 equity components.
CB_REDEMPTION=1.9996*7.0+1.5*7.0
# Kamoa Holding owns 80% of operating mine; balance-sheet ownership is 49.5%,
# not the 39.6% mine output interest. Shareholder loans are deducted then Zijin receivable added.
# H1 official USD bn facilities; USD/CNY budget 7.0. Holding shareholder loan credit uses Zijin H1 note.
JV_NET_DEBT=(.907076+.916897+.315435+.075532+.066728-.129481+2.744807)*.495*7-9.284632475
# Existing fair-value financial assets (not operating investments), plus non-modelled associates.
NONOPERATING_ASSOCIATES=3.242001754+1.175240077+(4.741664751+.440994803)*.262+.388460245+.288414821+.141983058
# Broad 80% common-equity realization budget, not false full ownership of consolidated assets.
FINANCIAL_ASSETS=(13.141995727+15.006467342+2.694675079)*.8+NONOPERATING_ASSOCIATES-.7-(3.333987700-1.425577447)
ACQUISITION_CASH=10.006048855+.310902731*29.82*.88
CHIFENG_NET_CASH=(6.033056952-.251781916-.535727062-(.152391571-.03824932403)-.13372439190)*.2585+.310902731*29.82*.88*.2585

def discount(flows,rate,start=0):
    return sum(x/(1+rate)**(i+1-start) for i,x in enumerate(flows) if i+1>start)

def opening_working_capital(p):
    """CNY bn, gross operating assets and full operating liabilities, no financial cash.
    Q3 portfolio extrapolation from H1 classifications is a budget, not entity books.
    Return already-attributable balances; allocation weights do NOT apply ownership again.
    """
    otherrecv=2.800034148*(1.094374969+.465326341+.312074438+.266809092+.160161779+.044211951)/2.797925563*(2.599948332/2.632822474)
    credits=16.651045373*(2.688336151+.346533218+.164714794)/12.864421972+2.282698797
    otherpay=21.156049581*(1.078060299+.355987996+.247136406+.091444914+.059062153+.021550445+1.533692043)/18.820476801
    group=[42.754136300+2.534952840,
           .324010380+10.660402860+2.794538393+4.521585137+.980121539+otherrecv,
           credits,
           4.235909080+25.620193503+.083310800+9.192728852+4.632754598+11.647992231+1.385224566+otherpay]
    group=[x*p['opening_attribution'] for x in group]
    weights={m[0]:m[2]*m[3][0]*{'cu':80000/1e6,'au':850/1000,'li':90000/1e6}[m[1]] for m in MINES if m[0] not in ['卡莫阿直接','赤峰矿山'] and m[3][0]>0}
    total=sum(weights.values());pools=[]
    for name,w in weights.items():pools.append(dict(name=name,amounts=[x*.7*w/total for x in group],source='Q3 consolidated allocated budget'))
    pools.append(dict(name='other_portfolio',amounts=[x*.3 for x in group],source='Q3 consolidated allocated budget'))
    # Acquisition purchase price stays deducted; these are the purchased operating assets,
    # not a second purchase-price refund. Chifeng was not in Q3 Zijin consolidation.
    ch=[2.95676764874,.49038183890+.15324441149+.08862002860,.12693579640,
        .71621775592+.00619034963+.09190486870+1.02873171310+.35399633733+.00065816909]
    pools.append(dict(name='赤峰矿山',amounts=[x*.2585*.8228 for x in ch],source='Chifeng H1; underlying attribution budget'))
    # Kamoa Holding official Q2 USD table: exclude cash, loans, facilities, PPE and mine rights.
    # Operating assets/liabilities use direct mine economics 39.6%; holding debt remains 49.5%.
    jv=[.706997+.019490,.282478+.465589+.019193+.003127,1.151629,.659045+.009366+.069805]
    pools.append(dict(name='卡莫阿直接',amounts=[x*7*.396 for x in jv],source='Ivanhoe official Q2 Kamoa gross table'))
    return pools


def operations(p):
    working_capital={m[0]:0. for m in MINES}
    recovery_due={}
    opening_pools=opening_working_capital(p)
    opening_due={}
    opening_done=set()
    chifeng_stream_remaining=p['chifeng_stage1_remaining_oz']*.0000311034768
    remaining={m[0]:m[4]*p['reserve_shift']*(.85 if m[1]=='li' else 1) for m in MINES}
    result=[]
    for t in range(1,p['horizon']+1):
        inflation=(1+p['inflation'])**(t-1)
        shift=p['price_shift']; volume=p['volume_shift']; costshift=p['cost_shift']; capshift=p['growth_shift']
        if p['scenario']=='cyclical':
            shift*= [0.80,.85,.95][t-1] if t<=3 else 1
            volume*=.90 if t<=2 else (0.95 if t==3 else 1)
            capshift*=1.15 if t<=3 else 1
        if p['scenario']=='structural' and t>=2:
            # Overseas water/power/royalty/permit costs worsen permanently; no mean reversion.
            shift*=.85; costshift*=1.20; volume*=.85; capshift*=1.25
        if p['scenario']=='upside':
            shift*=1.12; volume*=1.06 if t>=3 else 1; capshift*=1.12
        sums={'profit':0.,'fcf':0.,'revenue':0.,'da':0.,'sustain':0.,'growth':0.,'nwc':0.,'nwc_recovery':0.,'nwc_loss':0.,'nwc_balance':0.,'contingent_consideration':0.,'cu':0.,'au':0.,'li':0.}
        detail=[]
        for name,metal,own,qs,reserve,life,cost,da,sustain,cap in MINES:
            qplan=(qs[t-1] if t<=5 else qs[-1]*(.995**(t-5))) if t<=life else 0
            q=min(remaining[name],qplan*volume)
            remaining[name]-=q
            # Capacity commissioning may lag but sunk/committed construction is not cancelled.
            development=cap[t-1]*capshift if t<=5 else 0
            # USD50m fixed La Arena II consideration is INCLUDED in year-4 total capital,
            # not a second debt claim. Construction component alone takes capex stress.
            contingent=.35 if name=='阿瑞那二期' and t==4 else 0.
            if contingent: development=(cap[t-1]-contingent)*capshift+contingent
            if contingent and p['arena_extra_payment']: development+=contingent
            unit=p[{'cu':'copper','au':'gold','li':'lithium'}[metal]]*inflation*shift
            denom=1000 if metal=='au' else 1e6
            revenue=q*unit/denom
            account_cost=q*cost*inflation*(1+p['cost_real_growth'])**(t-1)*costshift/denom
            depreciation=q*da*inflation/denom
            maintenance=q*sustain*inflation*costshift/denom
            tax=p['tax']+(.06 if p['scenario']=='structural' and t>=2 else 0)
            ebit=revenue-account_cost-revenue*p['royalty']
            profit=ebit*(1-tax) if ebit>0 else ebit # no fictitious immediate loss-tax refund
            wc=(.015*revenue if t<=5 else 0)
            working_capital[name]+=wc
            ending=q>0 and (remaining[name]<=1e-10 or t==life)
            if ending: recovery_due[name]=min(p['horizon'],t+p['nwc_recovery_delay'])
            released=working_capital[name] if recovery_due.get(name)==t else 0.
            recovery=released*p['nwc_recovery_fraction']
            loss=released-recovery
            working_capital[name]-=released
            # Nominal historic cost is tax basis; no gain and no immediate loss refund.
            # Recovery is cash principal, not profit. Fees/writeoffs are expensed once.
            profit-=loss
            # Chifeng Wassa stream: true effective interest .2585*.62*.90, not
            # the aggregate gold basket .2585*.8228. No unverified immediate tax shield.
            stream_loss=0.;stream_stage1=0.;stream_stage2=0.
            if name=='赤峰矿山':
                wassa_q=q*p['chifeng_wassa_fraction']
                phase1_output=min(wassa_q,chifeng_stream_remaining/.105)
                stream_stage1=phase1_output*.105
                chifeng_stream_remaining=max(0,chifeng_stream_remaining-stream_stage1)
                stream_stage2=(wassa_q-phase1_output)*.055
                stream_loss=(stream_stage1*.8+stream_stage2*.7)*unit/1000*(.2585*.62*.90)/own
                profit-=stream_loss
            fcf=profit+loss+depreciation-maintenance-development-wc+recovery
            for key,val in [('profit',profit),('fcf',fcf),('revenue',revenue),('da',depreciation),('sustain',maintenance),('growth',development),('nwc',wc),('nwc_recovery',recovery),('nwc_loss',loss),('nwc_balance',working_capital[name]),('contingent_consideration',contingent),(metal,q)]: sums[key]+=val*own
            detail.append({'mine':name,'gross_output':q,'ownership':own,'attributable_profit':profit*own,'attributable_fcf':fcf*own,'remaining_recoverable':remaining[name],'nwc_addition':wc*own,'nwc_tax_basis_released':released*own,'nwc_recovery':recovery*own,'nwc_loss':loss*own,'nwc_closing_balance':working_capital[name]*own,'contingent_consideration':contingent*own,'chifeng_stream_cash_loss':stream_loss*own,'chifeng_stream_stage1_delivery_tonnes':stream_stage1,'chifeng_stream_stage2_delivery_tonnes':stream_stage2,'chifeng_stream_stage1_remaining_tonnes':chifeng_stream_remaining if name=='赤峰矿山' else 0.})
        # Silver/molybdenum/zinc/potash/refining/Longking; excludes any income on separately valued securities.
        # Q3 sulphur-price windfall excluded. Projects fade; no perpetual commodity franchise.
        other_scale=1 if t<=5 else max(0,(26-t)/21)
        otherprofit=(8.0+min(t-1,4)*.5)*inflation*other_scale
        othercap=(1.8 if t<=5 else .6)*inflation*other_scale
        overhead=7.5*inflation*(1 if t<=5 else max(.15,(41-t)/36)) if t<=40 else 0.
        # Otherprofit is NET of Buritica silver-stream encumbrance. Memo gross bridge
        # uses silver CNY10/g, 95% foregone spot receipt; no debt deduction as well.
        buritica=next(x for x in detail if x['mine']=='武里蒂卡')['gross_output']
        stream=buritica*1.84*.021*10/1000*.95*.5897*(1+p['inflation'])**(t-1)
        stream_extra=stream*(1-p['tax']) if p['stream_extra_deduction'] else 0.
        sums['stream_cash_encumbrance_in_other_budget']=stream
        sums['other_profit_before_stream_budget']=otherprofit+stream*(1-p['tax'])
        otherprofit-=stream_extra
        sums['profit']+=otherprofit-overhead
        sums['fcf']+=otherprofit-othercap-overhead
        sums['growth']+=othercap
        sums['year']=2026+t;sums['details']=detail
        # Existing net operating capital rotates through the business, then unwinds at
        # each allocated unit's closure. It is not another opening cash balance or debt.
        for item in detail:
            if item['gross_output']>0 and (item['remaining_recoverable']<=1e-10 or t==next(m[5] for m in MINES if m[0]==item['mine'])):
                opening_due[item['mine']]=min(p['horizon'],t+p['opening_delay'])
        opening_due['other_portfolio']=min(p['horizon'],26+p['opening_delay'])
        settlements=[];opening_cash=0.;opening_loss=0.
        for k,pool in enumerate(opening_pools):
            if k in opening_done:continue
            if opening_due.get(pool['name'])==t:
                inv,rec,taxcredit,pay=pool['amounts']
                loss=inv*p['opening_inventory_haircut']+rec*p['opening_receivable_haircut']+taxcredit*p['opening_tax_haircut']
                gross=inv+rec+taxcredit;net=gross-loss-pay
                opening_cash+=net;opening_loss+=loss;opening_done.add(k)
                settlements.append(dict(name=pool['name'],gross_tax_basis=gross,gross_realization=gross-loss,full_liabilities_paid=pay,realization_loss=loss,net_cash=net))
        opening_capex_extra=(21.156049581*11.418690352/18.820476801*.78 if t==1 and p['opening_capex_outside_budget'] else 0.)
        sums['fcf']-=opening_capex_extra;sums['growth']+=opening_capex_extra
        sums['opening_capex_extra']=opening_capex_extra
        sums['opening_capex_payable_inside_budget']=(21.156049581*11.418690352/18.820476801*.78 if t==1 else 0.)
        sums['new_construction_cash_excluding_opening_payables']=sums['growth']-sums['opening_capex_payable_inside_budget']-opening_capex_extra
        assert sums['new_construction_cash_excluding_opening_payables']>=-1e-9
        sums['opening_nwc_settlements']=settlements
        sums['opening_nwc_cash']=opening_cash;sums['opening_nwc_loss']=opening_loss
        sums['opening_nwc_gross_balance']=sum(sum(x['amounts'][:3]) for k,x in enumerate(opening_pools) if k not in opening_done)
        sums['opening_nwc_liability_balance']=sum(x['amounts'][3] for k,x in enumerate(opening_pools) if k not in opening_done)
        sums['profit']-=opening_loss # no loss-tax refund; principal is not profit
        sums['fcf']+=opening_cash # gross haircut, liabilities FULL, never haircut net debt
        sbc=sbc_budget(p,t)
        sums['sbc_inside_original_overhead']=sbc
        actual_sbc=sbc
        if not p['esop_performance_pass'] and t==3:actual_sbc=-2*SBC_ANNUAL_PROXY*p['sbc_scale']
        if not p['esop_performance_pass'] and t>3:actual_sbc=0.
        actual_sbc*=1+p['sbc_incremental_fraction']
        sums['sbc_incremental_expense']=actual_sbc-sbc
        sums['profit']+=sbc-actual_sbc
        sums['fcf']+=sbc # noncash inside original overhead; reversal itself creates no cash
        sums['sbc_total_expense']=actual_sbc
        sums['cash_overhead']=overhead-sbc
        sums['sbc_cash_tax_deduction']=0.
        result.append(sums)
    return result

# Model facts and conditional budgets are explicitly separate.
PARENT_REGISTERED=2.657753314 # September securities return, p1; not paid-up share capital
PARENT_PAID_UP=2.659079824 # Q3 parent balance sheet p17
PARENT_SURPLUS_TOTAL=1.316465612 # p18; statutory/discretionary split not independently disclosed
BASE.update(upstream_friction=.03, upstream_delay=0, asset_realization_year=3,
            asset_haircut=.03, parent_statutory_budget=PARENT_SURPLUS_TOTAL,
            extra_cash_release=.65, extra_cash_cycle=3, final_delay=2,closure_year=40,closure_cost=8.,jv_interest_rate=.075,nwc_recovery_fraction=.98,nwc_recovery_delay=0,arena_extra_payment=False,stream_extra_deduction=False,opening_attribution=.78,opening_inventory_haircut=.05,opening_receivable_haircut=.02,opening_tax_haircut=.20,opening_delay=0,opening_capex_outside_budget=False,chifeng_wassa_fraction=.35,chifeng_stage1_remaining_oz=240000-213807.41)

BASE.update(horizon=40,esop_collection_year=1, future_talent_approved=False, option_tranche2_eligible=True, option_tranche3_eligible=True, option_registration=True, option_budget_price=OPTION_BUDGET_PRICE, sbc_scale=1., sbc_incremental_fraction=0., esop_performance_pass=True, esop_failure_sale_proceeds=0., esop_failure_tax_rate=.24)

def legal_profit(re,statutory,registered,new_profit,discretionary_rate=0):
    """PRC parent only. Cash receipts/capital proceeds are deliberately not arguments."""
    eligible=max(0,new_profit-max(0,-re))
    provision=min(max(0,registered*.5-statutory),eligible*.1)
    discretionary=eligible*discretionary_rate
    return re+new_profit-provision-discretionary,statutory+provision,provision,discretionary

def liquidation(cash,noncash,external_debt,cost,haircut,ownership=1.,basis=0.,tax=.24):
    proceeds=noncash*(1-haircut)
    gain=proceeds-basis
    income_tax=max(0,gain)*tax
    resources=max(0,cash+proceeds)
    cost_paid=min(cost,resources);resources-=cost_paid
    tax_paid=min(income_tax,resources);resources-=tax_paid
    paid=min(external_debt,resources);resources-=paid
    # This waterfall is a valuation convention, not a statutory priority opinion.
    # All obligations survive as explicit shortfalls; insolvency never means cancelled liabilities.
    total_shortfall=(cost-cost_paid)+(income_tax-tax_paid)+(external_debt-paid)
    return {'gross_noncash_proceeds':proceeds,'disposal_gain':gain,'tax':income_tax,
            'exit_cost_paid':cost_paid,'exit_cost_shortfall':cost-cost_paid,
            'tax_paid':tax_paid,'tax_shortfall':income_tax-tax_paid,
            'creditor_paid':paid,'creditor_shortfall':external_debt-paid,
            'total_obligation_shortfall':total_shortfall,'feasible':total_shortfall<1e-8,
            'equity':resources*ownership if total_shortfall<1e-8 else 0.}

def capital_reduction(cash,debt,return_amount,registered,shares):
    # A cash return may not leave unpaid external creditors in this hand-case exit route.
    assert cash>=debt+return_amount and 0<=return_amount<=registered
    ratio=return_amount/registered if registered else 0
    return cash-debt-return_amount,registered-return_amount,shares*(1-ratio)

def finance(ops,p,opening=None):
    o=opening or {}; custom=opening is not None
    pc=o.get('parent_cash',6.119465016)
    sc=o.get('sub_cash',(76.776449446-6.119465016)*p['subcash_factor']-ACQUISITION_CASH+p['acquisition_prepaid']+CHIFENG_NET_CASH)
    pd=o.get('parent_debt',PARENT_DEBT)
    sd=o.get('sub_debt',(GROUP_BOOK_DEBT-PARENT_DEBT-CB_BOOK)*p['subdebt_factor']+CB_REDEMPTION+JV_NET_DEBT)
    re=o.get('parent_re',14.622428427)
    sr=o.get('statutory',p['parent_statutory_budget']); reg=o.get('registered',PARENT_REGISTERED)
    shares=o.get('shares',ISSUED-TREASURY_REMAINING); cb=o.get('cb',CB_REDEMPTION)
    assets=o.get('assets',FINANCIAL_ASSETS*p['assets_factor'])
    pending=[]; rows=[]
    capstate=capital_opening()
    apic=capstate['capital_surplus']; paidup=capstate['paid_up']; treasury=TREASURY_REMAINING
    receivable=ESOP_RECEIVABLE; treasury_cost=REMAINING_COST
    esop_dividends=0.; esop_failure_processed=False
    for i,op in enumerate(ops):
        t=i+1; pc0,sc0,pd0,sd0=pc,sc,pd,sd
        reserve=o.get('min_cash',3.); submin=o.get('min_cash',15.)
        if not custom and t>5:
            submin=max(submin,(p['closure_cost']*(1+p['inflation'])**(p['closure_year']-1) if t<=p['closure_year'] else 0)+sum(max(0,-x['fcf']) for x in ops[i+1:]))
        # Sinking liquidity is required by the finite exit, not a perpetual reserve.
        pi=pd*p['ordinary_debt_rate']
        premium=0. if custom else JV_NET_DEBT/((GROUP_BOOK_DEBT-PARENT_DEBT-CB_BOOK)*p['subdebt_factor']+JV_NET_DEBT)*max(0,p['jv_interest_rate']-p['ordinary_debt_rate'])
        si=max(0,sd-cb)*(p['ordinary_debt_rate']+premium)+(.139972 if cb>10.5 and not custom else 0)
        deposit=(pc+sc)*p['deposit_rate']; totalprofit=op['profit']-pi-si+deposit
        fcf=op['fcf']-pi-si+deposit
        direct=o.get('direct',0) if custom else min(2.,max(0,op['profit']*.06))
        sbc=0. if custom else op['sbc_total_expense']
        subprofit=op['profit']+sbc-direct-si+sc0*p['deposit_rate']
        pc+=direct-pi+pc0*p['deposit_rate'];sc+=op['fcf']-direct-si+sc0*p['deposit_rate']
        closure_payment=0.
        if not custom and t==p['closure_year'] and t<len(ops):
            closure_payment=p['closure_cost']*(1+p['inflation'])**(t-1)
            sc-=closure_payment;fcf-=closure_payment
        # Economic remittance budget, NOT a consolidated statutory profits account.
        # Extra retained financial cash can be released on a bounded 3-year cycle,
        # conditional on lawful investee dividends. No foreign Chinese reserve fiction.
        budget=max(0,subprofit)*p['upstream_fraction']
        extra=0
        if not custom and t>5 and t%p['extra_cash_cycle']==0:
            extra=max(0,sc-submin-sd-budget)*p['extra_cash_release']
        declaration=min(budget+extra,max(0,sc-submin))
        friction=declaration*p['upstream_friction']; net=declaration-friction
        sc-=declaration
        pending.append((t+p['upstream_delay'],net))
        receipt=sum(v for due,v in pending if due==t)
        pending=[x for x in pending if x[0]>t]
        pc+=receipt
        # New declaration is income; collecting prior years' dividends is cash only.
        new_parent_profit=direct-pi+pc0*p['deposit_rate']+net-sbc
        conversion=0.; equity_cash=0.; realized=0.; asset_loss=0.
        option_issued=0.; option_cash=0.; treasury_transfer=0.; talent_cash=0.; esop_collection=0.
        if not custom:
            apic+=sbc
            if t==p['esop_collection_year']:
                esop_collection=receivable; receivable=0.; equity_cash+=esop_collection
            if t==1:
                # End-2027 budget: both eligible tranches registered before first modeled dividend.
                # Eligibility windows open Dec2026/Dec2027. This is not current issued capital.
                option_issued=option_quantity(p); option_cash=option_issued*p['option_budget_price']
                shares+=option_issued;paidup+=option_issued*.1
                apic+=option_cash-option_issued*.1;equity_cash+=option_cash
                if p['future_talent_approved']:
                    treasury_transfer=treasury;talent_cash=treasury_transfer*ESOP_PRICE
                    shares+=treasury_transfer;treasury=0.
                    apic+=talent_cash-treasury_cost;treasury_cost=0.;equity_cash+=talent_cash
                if option_issued:reg=ISSUED*.1+option_issued*.1
            pc+=equity_cash
        # Issuer receives only excess sale gain on a failed plan; shares stay issued/in circulation.
        esop_excess=0.;esop_refund=0.;esop_sale=0.;esop_tax=0.
        if not custom and t==4 and not p['esop_performance_pass']:
            esop_sale=p['esop_failure_sale_proceeds']
            esop_refund=min(ESOP_RECEIVABLE,esop_sale)
            esop_excess=max(0,esop_sale-esop_refund)
            esop_tax=esop_excess*p['esop_failure_tax_rate']
            net_excess=esop_excess-esop_tax
            pc+=net_excess;totalprofit+=net_excess;fcf+=net_excess;new_parent_profit+=net_excess
            esop_failure_processed=True
        if t==3 and not custom:
            amount=1.9996*7
            sd-=amount;cb-=amount
            if p['convert_2029']:
                conversion=amount; shares+=.836031904;reg+=.0836031904;paidup+=.0836031904;apic+=amount-.0836031904
            else:pd+=amount
        if t==5 and not custom:sd-=10.5;cb-=10.5;pd+=10.5
        if t==p['asset_realization_year'] and not custom:
            # Disposal at 97% of already attributable financial carrying budget.
            # Principal does not create parent dividend profit; non-positive gain gets no tax refund.
            realized=assets*(1-p['asset_haircut']);asset_loss=assets-realized
            sc+=realized;assets=0
            totalprofit-=asset_loss # disposal loss is not a cash outflow a second time
        re,sr,provision,discretionary=legal_profit(re,sr,reg,new_parent_profit)
        payout=p['payout_first5'] if t<=5 else p['payout_later']
        if p['scenario']=='structural' and t>=2:payout=.1 if t<=5 else (.4 if pd+sd-pc-sc<30 else 0)
        desired=max(0,totalprofit-friction)*payout
        # After year 5, route returned accumulated profits promptly when legal parent capacity permits.
        if not custom and extra>0 and pd+sd<1e-8:desired+=extra*(1-p['upstream_friction'])
        legal_cap=max(0,re-(0 if custom else 2.))
        cap=o.get('borrowing_cap',0) if custom else min(10,max(0,190-pd-sd))
        pm=max(0,reserve-pc);sm=max(0,submin-sc);mandatory=pm+sm
        if mandatory>cap+1e-8:raise AssertionError('Zero-dividend funding shortfall')
        pc+=pm;pd+=pm;sc+=sm;sd+=sm
        available=max(0,pc-reserve)+cap-mandatory
        if not custom and t>5:
            available=max(0,pc-reserve-pd/(len(ops)-t+1))
        dividend=min(desired,legal_cap,available)
        borrow=max(0,dividend+reserve-pc);pd+=borrow;pc+=borrow-dividend;re-=dividend
        repay=min(max(0,sd-cb),max(0,sc-submin));sd-=repay;sc-=repay
        repay=min(pd,max(0,pc-reserve));pd-=repay;pc-=repay
        external=pd+sd-pd0-sd0+conversion
        # Include declared but unpaid intra-group cash separately; it remains subsidiary payable/parent receivable.
        prior_pending=sum(v for due,v in pending if due>t)+receipt-net
        pending_now=sum(v for due,v in pending)
        assert abs(pc+sc+pending_now-(pc0+sc0+prior_pending)-(fcf-friction+realized+external+equity_cash-dividend))<1e-7
        assert min(pc,sc,pd,sd)>=-1e-7 and dividend<=legal_cap+1e-8
        if not custom:esop_dividends+=dividend/shares*TRANSFERRED
        rows.append(dict(capital=dict(issued=ISSUED+(option_quantity(p) if not custom and t>=1 else 0)+(.836031904 if not custom and p['convert_2029'] and t>=3 else 0),
          treasury_shares=treasury,treasury_cost=treasury_cost,old_plan_treasury_obligation=OTHER_TREASURY_OBLIGATION,
          transfer_receivable=receivable,esop_collection=esop_collection,option_issued=option_issued,
          option_cash=option_cash,talent_transfer=treasury_transfer,talent_cash=talent_cash,
          paid_up=paidup,capital_surplus=apic,sbc_expense=sbc,sbc_tax_deduction=0.,
          esop_dividends_cumulative=esop_dividends,esop_failure_sale=esop_sale,esop_failure_refund=esop_refund,
          esop_failure_excess=esop_excess,esop_failure_tax=esop_tax,esop_failure_processed=esop_failure_processed,
          equity_financing_cash=equity_cash),year=op['year'],shares=shares,profit=totalprofit-friction,fcf=fcf-friction,
          upstream_declared=net,upstream=receipt,upstream_friction=friction,extra_cash_release=extra,
          dividend=dividend,dps=dividend/shares,desired_dividend=desired,legal_cap=legal_cap,
          parent_cash=pc,sub_cash=sc,parent_debt=pd,sub_debt=sd,parent_re=re,
          registered_capital=reg,statutory_reserve_budget=sr,reserve_provision=provision,
          new_parent_profit=new_parent_profit,old_receipts=receipt-(net if p['upstream_delay']==0 else 0),
          interest=pi+si,deposit=deposit,new_borrowing=mandatory+borrow,net_claim=pd+sd-pc-sc,
          assets=assets,realized_principal=realized,asset_loss=asset_loss,conversion=conversion,closure_payment=closure_payment,
          outstanding_declared_dividends=pending_now))
    return rows

def nav_value(fcfs,rate,closure,liquidity,net_claim,assets,shares,equity_proceeds=0,asset_year=0,delay=0,closure_year=None):
    n=len(fcfs)
    project=discount(fcfs,rate)-closure/(1+rate)**(closure_year or n)-liquidity+liquidity/(1+rate)**(n+delay)
    return (project-net_claim+assets/(1+rate)**asset_year+equity_proceeds/(1+rate))/shares,project

def values(ops,rows,p):
    r=p['equity_rate'];wacc=r-.01;n=len(rows);delay=p['final_delay']
    closure=p['closure_cost']*(1+p['inflation'])**(p['closure_year']-1)
    initial_cash=6.119465016+(76.776449446-6.119465016)*p['subcash_factor']-ACQUISITION_CASH+p['acquisition_prepaid']+CHIFENG_NET_CASH
    claim=PARENT_DEBT+(GROUP_BOOK_DEBT-PARENT_DEBT-CB_BOOK)*p['subdebt_factor']+CB_REDEMPTION+JV_NET_DEBT-initial_cash
    assets=FINANCIAL_ASSETS*p['assets_factor']*(1-p['asset_haircut'])
    if not p['convert_2029']:
        # All conditional options settle before first modeled distribution. The common
        # fully-diluted capitalization and proceeds are used in both methods.
        nav,project=nav_value([x['fcf'] for x in ops],wacc,closure,18,claim,assets,economic_shares(p),0,p['asset_realization_year'],delay,p['closure_year'])
        nav+=sum(row['capital']['equity_financing_cash']/(1+wacc)**(i+1) for i,row in enumerate(rows))/economic_shares(p)
        friction_pv=discount([x['upstream_friction'] for x in rows],wacc)/economic_shares(p)
        nav-=friction_pv
        nav+=sum((row['capital']['esop_failure_excess']-row['capital']['esop_failure_tax'])/(1+wacc)**(i+1) for i,row in enumerate(rows))/economic_shares(p)
        anchor=0;node_shares=economic_shares(p);node_claim=claim;nav_node=nav
    else:
        # Conversion is later than first holder cash. Value remaining operating assets
        # at the actual 2029 post-conversion cash/debt/share node; do not deduct converted
        # principal again or pretend post-conversion shares existed in 2027/28.
        anchor=3;node=rows[2];node_shares=node['shares']
        project=discount([x['fcf'] for x in ops[3:]],wacc)-closure/(1+wacc)**(p['closure_year']-3)-18+18/(1+wacc)**(n+delay-3)
        node_claim=node['parent_debt']+node['sub_debt']-node['parent_cash']-node['sub_cash']-node['outstanding_declared_dividends']
        future_assets=node['assets']*(1-p['asset_haircut'])/(1+wacc)**max(0,p['asset_realization_year']-3)
        future_capital=sum(row['capital']['equity_financing_cash']/(1+wacc)**(i-2) for i,row in enumerate(rows) if i>=3)
        future_excess=sum((row['capital']['esop_failure_excess']-row['capital']['esop_failure_tax'])/(1+wacc)**(i-2) for i,row in enumerate(rows) if i>=3)
        friction_at_node=discount([x['upstream_friction'] for x in rows[3:]],wacc)
        nav_node=(project-node_claim+future_assets+future_capital+future_excess-friction_at_node)/node_shares
        nav=discount([x['dps'] for x in rows[:3]],wacc)+nav_node/(1+wacc)**3
        friction_pv=friction_at_node/node_shares/(1+wacc)**3
    last=rows[-1]
    exit=liquidation(last['parent_cash']+last['sub_cash']+last['outstanding_declared_dividends'],last['assets'],last['parent_debt']+last['sub_debt'],closure if p['closure_year']==n else 0,p['asset_haircut'],basis=last['assets'])
    if not exit['feasible']:raise AssertionError('Exit obligations unpaid: equity path not feasible '+json.dumps(exit))
    # Full finite holder cash: every future retained financial dollar has dated realization,
    # equity extinguishes after final payout; no negative shareholder payment or perpetuity.
    d=[x['dps'] for x in rows]+[0.]*delay
    d[-1]+=exit['equity']/last['shares']
    full=discount(d,r);tv=discount(d,r,start=5);first5=discount(d[:5],r)
    return dict(current=full,auxiliary_nav=nav,terminal_year5=tv,first5_dividend_pv=first5,
       terminal_pv_fraction=(full-first5)/full,auxiliary_ddm=full,project_pv=project,
       remittance_friction_pv_per_share=friction_pv,initial_net_claim=claim,nav_anchor_year=2026+anchor,nav_anchor_shares=node_shares,nav_anchor_net_claim=node_claim,nav_anchor_value=nav_node,
       liquidation=exit,liquidation_year=2026+n+delay,post_liquidation_shares=0,
       g_terminal=0,all_holder_cash=d)

def run(p):
    ops=operations(p);rows=finance(ops,p);v=values(ops,rows,p)
    return dict(parameters=p,capital_opening=capital_opening(),values=v,opening_working_capital=opening_working_capital(p),operations=ops,financing=rows,five_year_dps=[x['dps'] for x in rows[:5]])

def tests():
    assert legal_profit(0,5,20,10)==(9,6,1,0) # paid-in 10 irrelevant
    assert legal_profit(-8,0,20,10)==(1.8,.2,.2,0)
    assert legal_profit(0,10,20,10)==(10,10,0,0)
    assert legal_profit(0,10,22,10)==(9,11,1,0)
    assert liquidation(2,10,8,1,.2,.6,10)['equity']==.6
    assert liquidation(2,10,11,1,.2,.6,10)['equity']==0
    assert liquidation(2,10,11,1,.2,.6,10)['creditor_shortfall']==2
    assert capital_reduction(20,5,5,10,100)==(10,5,50)
    p=dict(BASE,ordinary_debt_rate=0,deposit_rate=0,upstream_fraction=1,payout_first5=1,upstream_friction=0)
    o=dict(parent_cash=0,sub_cash=0,parent_debt=0,sub_debt=0,parent_re=0,shares=2,assets=0,cb=0,min_cash=0,registered=0,statutory=0)
    a=finance([dict(profit=10,fcf=10,year=2027)],p,o)[0];assert a['dps']==5
    b=finance([dict(profit=10,fcf=6,year=2027)],p,o)[0];assert b['dividend']==6
    lag=finance([dict(profit=10,fcf=10,year=2027),dict(profit=0,fcf=0,year=2028)],dict(p,upstream_delay=1),o)
    assert lag[0]['new_parent_profit']==10 and lag[0]['dividend']==0 and lag[1]['new_parent_profit']==0 and lag[1]['dividend']==0 and lag[1]['old_receipts']==10
    try:finance([dict(profit=-15,fcf=-15,year=2027)],p,dict(o,borrowing_cap=10))
    except AssertionError:pass
    else:raise AssertionError('funding failure concealed')
    assert abs(nav_value([10],.1,0,0,0,0,2)[0]-50/11)<1e-12
    loss_ops=operations(dict(BASE,gold=0,copper=0,lithium=0,tax=.24))
    untaxed_loss_ops=operations(dict(BASE,gold=0,copper=0,lithium=0,tax=0))
    assert all(abs(a['profit']-b['profit'])<1e-10 for a,b in zip(loss_ops,untaxed_loss_ops))
    assert liquidation(10,0,3,1,0,basis=0)['equity']==liquidation(0,10,3,1,0,basis=10)['equity']==6
    assert liquidation(0,0,0,10,0)['total_obligation_shortfall']==10
    assert not liquidation(0,0,0,10,0)['feasible']
    assert liquidation(0,10,0,0,0,basis=0,tax=2)['tax_shortfall']==10
    assert liquidation(2,0,3,5,0)['total_obligation_shortfall']==6
    check=operations(BASE)
    assert abs(sum(x['nwc'] for x in check)-sum(x['nwc_recovery']+x['nwc_loss'] for x in check))<1e-9
    assert check[-1]['nwc_balance']==0
    for x in check:
        assert abs(x['nwc_balance']-sum(z['nwc_closing_balance'] for z in x['details']))<1e-9
    assert check[-1]['opening_nwc_gross_balance']==check[-1]['opening_nwc_liability_balance']==0
    assert abs(sum(x['details'][18]['chifeng_stream_stage1_delivery_tonnes'] for x in check)-(240000-213807.41)*.0000311034768)<1e-9
    capital_tests()
    return dict(capital_current_input_handcases=True,capital_cash_and_equity_conservation=True,option_gate_failures=True,esop_failure_no_cancellation=True,opening_nwc_principal_and_full_liabilities=True,chifeng_stream_phase_transition=True,nwc_principal_recovered=True,all_exit_shortfalls_retained=True,passed=True,registered_not_paid_up=True,loss_first=True,full_reserve=True,conversion_threshold=True,old_receipt_not_profit=True,creditors_first=True,gross_asset_haircut=True,shares_cancelled=True,no_fictitious_funding=True,no_loss_tax_refund=True,principal_once=True)

def capital_tests():
    opening=capital_opening()
    assert abs(opening['transfer_receivable']-1.353707008)<1e-12
    assert abs(opening['participating']-26.586260449)<1e-12
    assert abs(opening['transfer_cost']+opening['treasury_cost']-2.499993348)<1e-12
    assert abs(opening['transfer_capital_surplus']+opening['transfer_cost']-opening['net_equity_delta'])<1e-12
    assert opening['registered']==2.657753314 and opening['issued']==26.590798241
    assert option_conditions(.25,.20,.16,.15,.60,'B',True,3)
    for args in [(.19,.18,.16,.15,.60,'B',True,3),(.25,.26,.16,.15,.60,'B',True,2),(.25,.20,.11,.10,.60,'B',True,2),(.25,.20,.16,.17,.60,'B',True,2),(.25,.20,.16,.15,.66,'B',True,2),(.25,.20,.16,.15,.60,'C',True,2),(.25,.20,.16,.15,.60,'B',False,2)]:
        assert not option_conditions(*args)
    assert option_quantity(dict(BASE,option_tranche2_eligible=False,option_tranche3_eligible=False))==0
    assert abs(option_quantity(dict(BASE,option_tranche3_eligible=False))-.0131)<1e-12
    assert option_quantity(dict(BASE,option_registration=False))==0
    # Same real finance chain, actual current numbers, all operating flows remain untouched.
    o=operations(BASE)
    a=finance(o,BASE);b=finance(o,dict(BASE,esop_collection_year=3))
    assert abs(a[0]['capital']['esop_collection']-1.353707008)<1e-12
    assert b[0]['capital']['esop_collection']==0 and abs(b[0]['capital']['transfer_receivable']-1.353707008)<1e-12
    assert b[2]['capital']['transfer_receivable']==0
    assert abs(a[0]['capital']['issued']-26.616998241)<1e-12 and abs(a[0]['shares']-26.612460449)<1e-12
    assert abs(a[0]['capital']['option_cash']-.27117)<1e-12
    assert a[0]['capital']['talent_transfer']==0
    z=dict(BASE,option_registration=False);zr=finance(operations(z),z)
    assert zr[0]['capital']['option_issued']==zr[0]['capital']['option_cash']==0
    assert zr[0]['registered_capital']==2.657753314
    f=dict(BASE,esop_performance_pass=False,esop_failure_sale_proceeds=1.6)
    fr=finance(operations(f),f)
    assert abs(fr[3]['capital']['esop_failure_refund']-1.353707008)<1e-12
    assert abs(fr[3]['capital']['esop_failure_excess']-.246292992)<1e-12
    assert fr[3]['shares']==a[3]['shares'] # market resale, not cancellation
    assert abs(sum(x['capital']['sbc_expense'] for x in fr))<1e-12
    t=dict(BASE,future_talent_approved=True);tr=finance(operations(t),t)
    assert tr[0]['capital']['treasury_shares']==0 and tr[0]['capital']['issued']==a[0]['capital']['issued']
    assert abs(tr[0]['capital']['talent_cash']-.08422141952)<1e-12
    for p,rows in [(BASE,a),(f,fr),(t,tr),(z,zr)]:
        previous=opening['capital_surplus'];paidup=opening['paid_up'];tc=opening['treasury_cost']
        previous_reg=opening['registered']; cumulative=0
        for r in rows:
            c=r['capital'];flow=c['option_cash']+c['talent_cash'];cost_released=tc-c['treasury_cost']
            assert abs(c['capital_surplus']-previous-(c['sbc_expense']+flow-(c['paid_up']-paidup)-cost_released))<1e-8
            assert abs(r['shares']-(c['issued']-c['treasury_shares']))<1e-10
            assert c['transfer_receivable']>=0 and c['treasury_shares']>=0
            previous=c['capital_surplus'];paidup=c['paid_up'];tc=c['treasury_cost']

CASES={'chifeng_wassa45':dict(BASE,chifeng_wassa_fraction=.45),'chifeng_stream_phase2':dict(BASE,chifeng_stage1_remaining_oz=0),'opening_capex_outside_budget':dict(BASE,opening_capex_outside_budget=True),'opening_slow_stress':dict(BASE,opening_attribution=.70,opening_inventory_haircut=.15,opening_receivable_haircut=.05,opening_tax_haircut=.50,opening_delay=3),'opening_high_recovery':dict(BASE,opening_attribution=.82,opening_inventory_haircut=.02,opening_receivable_haircut=.01,opening_tax_haircut=.10),'opening_delay3':dict(BASE,opening_delay=3),'nwc_delay2':dict(BASE,nwc_recovery_delay=2),'nwc_recovery90':dict(BASE,nwc_recovery_fraction=.9),'nwc_recovery100':dict(BASE,nwc_recovery_fraction=1.),'arena_payment_outside_capex':dict(BASE,arena_extra_payment=True),'stream_outside_other_budget':dict(BASE,stream_extra_deduction=True),'reserve_minus20':dict(BASE,reserve_shift=.8),'growth_plus25':dict(BASE,growth_shift=1.25),'base':BASE,'base_terminal_low':dict(BASE,equity_rate=.10),'base_terminal_high':dict(BASE,equity_rate=.09),
 'core_low':dict(BASE,gold=810,copper=77000,lithium=85000,equity_rate=.10,subcash_factor=.74,subdebt_factor=.79,assets_factor=.95),
 'core_high':dict(BASE,gold=890,copper=83000,lithium=95000,equity_rate=.09,subcash_factor=.82,subdebt_factor=.71,assets_factor=1.05),
 'cyclical':dict(BASE,scenario='cyclical'),'structural':dict(BASE,scenario='structural',upstream_fraction=.5,equity_rate=.105),
 'upside':dict(BASE,scenario='upside',equity_rate=.09),'gold_minus_100':dict(BASE,gold=750),'copper_minus_10000':dict(BASE,copper=70000),
 'upstream_minus20pct':dict(BASE,upstream_fraction=.52),'acquisition_A_prepaid':dict(BASE,acquisition_prepaid=10.006048855),
 'conversion_2029':dict(BASE,convert_2029=True),'remittance_delay_1':dict(BASE,upstream_delay=1),
 'remittance_friction_8pct':dict(BASE,upstream_friction=.08),'assets_year5_haircut10':dict(BASE,asset_realization_year=5,asset_haircut=.1),
 'unknown_statutory_zero':dict(BASE,parent_statutory_budget=0),'extra_release_5yr_40pct':dict(BASE,extra_cash_cycle=5,extra_cash_release=.4),
 'closure_early10':dict(BASE,closure_year=30),'zero_deposit_yield':dict(BASE,deposit_rate=0),'refinancing_5pct':dict(BASE,ordinary_debt_rate=.05,jv_interest_rate=.09),'final_delay5':dict(BASE,final_delay=5),'no_friction_immediate_asset':dict(BASE,upstream_friction=0,asset_haircut=0,asset_realization_year=1,final_delay=0)}
# Additional conditional capital paths; no changes to original operating assumptions.
CASES.update(tail_settlement80=dict(BASE,horizon=80),tail_settlement160=dict(BASE,horizon=160),esop_collection_late=dict(BASE,esop_collection_year=3),
    talent_future_approved=dict(BASE,future_talent_approved=True),
    options_company_fail=dict(BASE,option_tranche2_eligible=False,option_tranche3_eligible=False),
    options_individual_fail_half=dict(BASE,option_tranche3_eligible=False),
    options_registration_fail=dict(BASE,option_registration=False),
    options_formal_unadjusted_price=dict(BASE,option_budget_price=11.15),
    sbc_zero_allocation=dict(BASE,sbc_scale=0.),sbc_double_allocation=dict(BASE,sbc_scale=2.),
    sbc_additional_not_in_overhead=dict(BASE,sbc_incremental_fraction=1.),
    esop_assessment_fail_no_excess=dict(BASE,esop_performance_pass=False,esop_failure_sale_proceeds=1.),
    esop_assessment_fail_excess=dict(BASE,esop_performance_pass=False,esop_failure_sale_proceeds=1.6))

if __name__=='__main__':
    out=dict(cutoff=CUTOFF,units='CNY billion; shares billion',tests=tests(),capital_opening=capital_opening(),cases={})
    for name,p in CASES.items():
        try:out['cases'][name]=run(p)
        except AssertionError as e:out['cases'][name]={'infeasible':str(e)}
    print(json.dumps(out,ensure_ascii=False,indent=2))

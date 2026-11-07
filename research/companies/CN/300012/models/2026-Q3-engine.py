"""华测检测：人民币十亿元/十亿股。仅母公司使用法定账；子公司为经济上划预算，非虚构法律主体。标准库。"""
import json
from pathlib import Path
SHARES=1.682828214
BRIDGE={'cash_equivalents':.61314537045,'trading_financial_assets':.36761189194,'other_current_financial_assets_estimate':.28,'noncurrent_financial_assets':.01011858241,'operating_cash':-.45,'common_attribution_reserve':-.03,'interest_debt_reserve':-.067,'legacy_acquisition_payable_reserve':-.06524846766}
CASH=sum(BRIDGE.values())
E=[1.30,1.43,1.54,1.65,1.75]; INV=[.76,.77,.76,.70,.68]
DPS=[.23,.26,.29,.32,.35]


def legal_step(retained,reserve,registered,profit,requested,cash,continue_reserve=False):
    # Losses are absorbed before allocation; paid-in capital is not the threshold.
    allocable=max(0,profit+min(0,retained))
    reserve_add=.1*allocable if continue_reserve or reserve<.5*registered else 0.
    available=retained+profit-reserve_add
    paid=min(max(0,requested),max(0,available),max(0,cash))
    return {'retained':available-paid,'reserve':reserve+reserve_add,'reserve_add':reserve_add,'paid':paid,'cash':cash-paid,'available_profit':available}


def dispose(asset_proceeds,basis,cost,tax_rate,ownership):
    gain=asset_proceeds-basis-cost
    tax=max(0,gain)*tax_rate
    return {'cash':(asset_proceeds-cost-tax)*ownership,'profit':(gain-tax)*ownership,'principal':basis*ownership,'tax':tax*ownership}


def capital_repayment(cash,registered,paid_capital,shares,repayment):
    # Pro-rata paid capital reduction; each original holder owns same fraction of fewer shares.
    amount=min(repayment,cash,paid_capital,registered)
    ratio=1-amount/registered
    return {'cash':cash-amount,'registered':registered-amount,'paid_capital':paid_capital-amount,'shares':shares*ratio,'paid':amount}


def owner_cash_step(retained,reserve,registered,profit,requested,cash,continue_reserve=False,
                    sale=None,capital_return=0.,paid_capital=None,shares=None,capital_authorized=False):
    # A real payer's sale profit and principal are separate. Capital reduction needs authorization.
    disposal=dispose(**sale) if sale else {'cash':0.,'profit':0.,'principal':0.,'tax':0.}
    result=legal_step(retained,reserve,registered,profit+disposal['profit'],requested,cash+disposal['cash'],continue_reserve)
    paid_capital=registered if paid_capital is None else paid_capital
    shares=registered if shares is None else shares
    reduction=capital_repayment(result['cash'],registered,paid_capital,shares,capital_return) if capital_authorized else {'cash':result['cash'],'registered':registered,'paid_capital':paid_capital,'shares':shares,'paid':0.}
    result.update({'cash':reduction['cash'],'capital_paid':reduction['paid'],'ending_registered':reduction['registered'],'ending_shares':reduction['shares'],'sale':disposal})
    return result

def calc(k=.09, terminal_g=.03, roi=.15, e_scale=1.,investment_scale=1.,
         factors=(1,1,1,1,1),tail_g=(.05,.045,.04,.035,.03),years=400,
         upstream_scale=1.,cash_delay=.10,friction=.005,continue_reserve=False,
         parent_loss=0.,parent_net_extra_payment=0.,opening_parent_cash=.15,
         realized_principal_years=5, legal=True):
    assert years>=20 and k>terminal_g and 0<=cash_delay<1
    # Actual H1 parent figures less the already-paid August interim dividend.
    retained=2.96728214377-.084141411; reserve=.48845025728; registered=SHARES
    parent_cash=opening_parent_cash; subsidiaries_cash=CASH-parent_cash
    receivable=.21451912125  # accrued old dividends; never parent earnings on receipt
    rows=[]; earnings=0.; opening_release=0.; cumulative_sub_retained_earnings=0.; opcapital=8.39990558255-CASH
    for t in range(1,years+1):
        if t<=5:
            earnings=E[t-1]*e_scale*factors[t-1]; inv=INV[t-1]*investment_scale
        else:
            growth=tail_g[t-6] if t<=10 else terminal_g
            prev=earnings; earnings*=1+growth; inv=(earnings-prev)/roi if t<=10 else earnings*terminal_g/roi
        fcf=earnings-inv
        group_start=parent_cash+subsidiaries_cash
        interest_p=parent_cash*.015; interest_s=subsidiaries_cash*.015
        parent_cash+=interest_p; subsidiaries_cash+=interest_s
        # Own net operating contribution and direct operating profit, distinct budgets.
        own_profit=(.40+.04*(t-1))*e_scale*factors[t-1] if t<=5 else earnings*.32
        own_net=([.20,.22,.24,.26,.28][t-1]*e_scale*factors[t-1]-[.04,.03,.03,.03,.03][t-1]*investment_scale) if t<=5 else .25*fcf
        own_profit-=parent_loss if t<=3 else 0
        extra=parent_net_extra_payment if t<=3 else 0
        # Additional legal-entity loss is also an economic loss; extra internal settlement is not.
        loss=parent_loss if t<=3 else 0
        fcf-=loss
        own_net-=loss+extra
        parent_cash+=own_net; subsidiaries_cash+=fcf-own_net
        sub_earnings=max(0,earnings-(own_profit+loss))
        if t<=5:
            declared=min([.30,.32,.36,.40,.44][t-1]*e_scale*factors[t-1]*upstream_scale,.85*sub_earnings)
            requested_transfer=[.23,.25,.28,.31,.34][t-1]*upstream_scale
        else:
            # Economy-level solvency/profitability budget; not any subsidiary's legal reserve.
            requested_transfer=max(0,subsidiaries_cash)*(1-cash_delay)
            # Earlier forecast earnings can support later special declarations. This is an
            # economic feasibility envelope, NOT a consolidated statutory profit pool.
            declared=min(.85*sub_earnings*upstream_scale+interest_s+cumulative_sub_retained_earnings/realized_principal_years,requested_transfer)
        cumulative_sub_retained_earnings+=sub_earnings+interest_s-declared
        assert cumulative_sub_retained_earnings>=-1e-9
        receivable+=declared
        transfer=min(max(0,requested_transfer),max(0,subsidiaries_cash),max(0,receivable))
        transfer_cost=transfer*(friction if t>5 else 0)
        subsidiaries_cash-=transfer;parent_cash+=transfer-transfer_cost;receivable-=transfer
        profit=own_profit+declared+interest_p-transfer_cost
        if t==6: opening_release=max(0,group_start)
        if t<=5: requested=DPS[t-1]*SHARES
        else:
            # All new FCFE is targeted for payment after ramp; accrued extra principal released over 5 years.
            ramp=min(1,.5+.1*(t-5))
            release=opening_release/realized_principal_years if t<6+realized_principal_years else 0
            requested=max(0,fcf)*ramp+release
            # Clear cash that was delayed, not an endless synthetic legal reserve.
            if t>=6+realized_principal_years: requested=max(requested,max(0,parent_cash))
        if legal:
            step=owner_cash_step(retained,reserve,registered,profit,requested,parent_cash,continue_reserve)
        else:
            step={'retained':retained+profit-requested,'reserve':reserve,'reserve_add':0.,'paid':min(requested,max(0,parent_cash)),'available_profit':retained+profit}
            step['cash']=parent_cash-step['paid']
        retained=step['retained'];reserve=step['reserve'];parent_cash=step['cash']
        group_end=parent_cash+subsidiaries_cash
        expected=group_start+interest_p+interest_s+fcf-transfer_cost-step['paid']
        assert abs(group_end-expected)<1e-7*max(1,abs(expected))
        feasible=parent_cash>=-1e-10 and subsidiaries_cash>=-1e-10
        # No fictitious borrowing; infeasible operation remains visible even with dividends zero.
        opcapital+=inv
        rows.append({'year':t,'earnings':earnings,'investment':inv,'fcf':fcf,'operating_capital':opcapital,
            'parent_own_profit':own_profit,'parent_net_operating_cash':own_net,'new_dividend_income':declared,'cumulative_sub_earnings_not_declared_economic_only':cumulative_sub_retained_earnings,
            'dividend_receivable_end':receivable,'actual_upstream_gross':transfer,'transfer_friction':transfer_cost,
            'cash_interest':interest_p+interest_s,'parent_profit':profit,'statutory_reserve_add':step['reserve_add'],
            'statutory_reserve_end':reserve,'parent_retained_end':retained,'parent_cash_end':parent_cash,
            'subsidiary_economic_cash_end':subsidiaries_cash,'group_extra_cash_end':group_end,
            'requested_distribution':requested,'distribution':step['paid'],'dps':step['paid']/SHARES,'feasible':feasible})
    value=sum(x['dps']/(1+k)**x['year'] for x in rows)
    tv5=sum(x['dps']/(1+k)**(x['year']-5) for x in rows[5:])
    return {'value_per_share':value,'terminal_share_y5':tv5,'dps':[x['dps'] for x in rows[:5]],
        'terminal_pv_share':tv5/(1+k)**5/value,'feasible':all(x['feasible'] for x in rows),
        'years':years,'annual':rows,'parameters':{'k':k,'g':terminal_g,'roi':roi,'e_scale':e_scale,'investment_scale':investment_scale,'upstream_scale':upstream_scale,'cash_delay':cash_delay,'friction':friction,'continue_reserve':continue_reserve}}


def build():
    scenarios={'base':{},'core_low':{'k':.095,'terminal_g':.025,'roi':.14},'core_high':{'k':.085,'terminal_g':.03,'roi':.16},
     'cycle_weak':{'factors':(.85,.9,.95,1,1),'investment_scale':1.05},
     'structural_weak':{'k':.10,'terminal_g':.015,'roi':.10,'e_scale':.8,'investment_scale':1.15,'tail_g':(.02,)*5,'upstream_scale':.75,'cash_delay':.25,'friction':.02},
     'optimistic':{'k':.085,'terminal_g':.035,'roi':.18,'e_scale':1.1,'investment_scale':.95},
     'sensitivity_roi12':{'roi':.12},'sensitivity_k10':{'k':.10},'sensitivity_upstream70':{'upstream_scale':.7},
     'sensitivity_cash_delay40':{'cash_delay':.4},'sensitivity_friction2pct':{'friction':.02},
     'sensitivity_continue_reserve':{'continue_reserve':True},'sensitivity_parent_loss':{'parent_loss':.25},
     'sensitivity_internal_payment':{'parent_net_extra_payment':.10},'sensitivity_parent_cash0':{'opening_parent_cash':0.},
     'sensitivity_release10':{'realized_principal_years':10}}
    out={'units':'CNY billion and billion shares; per-share CNY','shares_bn':SHARES,'bridge_bn':BRIDGE,'net_extra_financial_assets_bn':CASH,'cases':{n:calc(**p) for n,p in scenarios.items()}}
    out['convergence']={str(n):{tag:{k:v for k,v in calc(years=n,**scenarios[tag]).items() if k in ['value_per_share','terminal_share_y5']} for tag in ['base','core_low','core_high','structural_weak']} for n in [200,400,600]}
    out['same_economics_law_only']={n:{'with_legal':out['cases'][n]['value_per_share'],'without_parent_legal':calc(legal=False,**p)['value_per_share']} for n,p in scenarios.items()}
    # Independent capital/earnings crosscheck: same capital obligation, maturity at year 5.
    cap5=8.39990558255-CASH+sum(INV)
    out['residual_income_crosscheck']={}
    for tag,k,g,roe in [('low',.095,.025,.14),('high',.085,.03,.16)]:
        c=out['cases']['base']; cash5=c['annual'][4]['group_extra_cash_end']
        # Financial principal payable over five years at 1.5% yield, not instantly realizable at par.
        v_fin=sum((cash5/5*(1.015)**i)/(1+k)**i for i in range(1,6))
        op=cap5*(roe-g)/(k-g)
        pv=sum(x['dps']/(1+k)**x['year'] for x in c['annual'][:5])+(op+v_fin)/SHARES/(1+k)**5
        out['residual_income_crosscheck'][tag]={'value_per_share':pv,'capital5':cap5,'op_value_y5':op,'realizable_financial_value_y5':v_fin}
    return out

if __name__=='__main__':
    print(json.dumps(build(),ensure_ascii=False,indent=2))

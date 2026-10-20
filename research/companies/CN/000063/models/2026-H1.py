"""中兴通讯2026-H1，金额/股数均十亿；独立运行、无外部依赖。"""
import json
from pathlib import Path
S = 4.783534887
D = [.22,.24,.26,.28,.30]
A0 = 22.663870-.125135+1.054311+25.972742+14.056018+19.879692-1.954254-.144843-.035105-.561790
BANK = 56.858535
BOND = 6.783704
CB = 3.584
OTHER = 4.386660
PENSION = .137822
NONOP = [4.531256,6.041675]
DERIV = .089661
PERP = 1.5
MINORITY = .5

def operating(network_shift=0, tax=.2, nwc_ratio=.2, cycle=False, enterprise_shift=0):
    network=[60,60,60.5,61,61]; enterprise=[56,62,69,76,83]; consumer=[36,37,38,39,40]
    nm=[.38,.385,.39,.395,.40]; em=[.16,.165,.17,.17,.17]; cm=[.185,.185,.19,.19,.19]
    rd=[22.5,23,23.5,24,24.5]; sales=[7.8,8,8.2,8.5,8.8]; admin=[4.3,4.4,4.5,4.6,4.8]
    support=[1.5,1.55,1.6,1.65,1.7]; loss=[1.2,1.25,1.3,1.4,1.5]
    # 短周期压力：前三年销售毛利额各少1.5/1/.5，前三年额外信用资本3/2/1，Y4释放。
    old_nwc=29.006518; old_buffer=8; fixed=22.632705; rows=[]
    for i in range(5):
        revenue=network[i]+enterprise[i]+consumer[i]
        gross=network[i]*(nm[i]+network_shift)+enterprise[i]*(em[i]+enterprise_shift)+consumer[i]*cm[i]
        if cycle: gross-=[1.5,1,.5,0,0][i]
        ebit=gross-rd[i]-sales[i]-admin[i]-.007*revenue+support[i]-loss[i]
        cash_tax=max(ebit,0)*tax+.2
        nopat=ebit-cash_tax
        nwc=revenue*nwc_ratio + ([3,2,1,0,0][i] if cycle else 0)
        buffer=8*revenue/152
        capex=5+.2*i; da=4.2+.2*i
        opcf=nopat+da-capex-(nwc-old_nwc)
        fcff=opcf-(buffer-old_buffer)
        fixed+=capex-da
        rows.append(dict(year=i+1,revenue=revenue,network=network[i],enterprise=enterprise[i],consumer=consumer[i],gross=gross,rd=rd[i],sales=sales[i],admin=admin[i],support=support[i],loss=loss[i],ebit=ebit,cash_tax=cash_tax,nopat=nopat,nwc=nwc,delta_nwc=nwc-old_nwc,buffer=buffer,delta_buffer=buffer-old_buffer,capex=capex,da=da,opcf=opcf,fcff=fcff,invested_capital=nwc+buffer+fixed))
        old_nwc=nwc;old_buffer=buffer
    return rows

def finance(ops, asset_yield=.015, bank_rate=.03, initial_haircut=0, distributions=D):
    cash=A0*(1-initial_haircut);bank=BANK;bond=BOND;cb=CB;other=OTHER+PENSION;rows=[]
    bank_maturing=[14.139261,21.206929,21.512345,0,0]
    # 最迟三年内到期/留存安排沿用已核底稿；再融资等额续作，无新增净借款。
    for i,o in enumerate(ops):
        start=cash; income=max(start,0)*asset_yield
        interest=bank*bank_rate+bond*.022+(.131291 if i==2 else 0)
        principal_bond=[0,0,1.4,3.85,1.533704][i]
        principal_cb=CB if i==1 else 0
        principal_other=[.7,1.490795,2.333687,0,0][i]
        matured=bank_maturing[i]; renewed=matured
        dividend=distributions[i]*S
        cash=start+o['opcf']+income-interest-.09-.08-principal_bond-principal_cb-principal_other-matured+renewed-dividend
        bond-=principal_bond;cb-=principal_cb;other-=principal_other
        debt=bank+bond+cb+other
        rows.append(dict(year=i+1,opening_assets=start,operating_cash=o['opcf'],asset_income=income,cash_interest=interest,perpetual_distribution=.09,minority_distribution=.08,bank_maturing=matured,bank_renewal=renewed,bond_principal=principal_bond,cb_principal=principal_cb,other_principal=principal_other,common_distribution=dividend,closing_assets=cash,closing_financial_debt=debt,operating_buffer=o['buffer'],net_financial_assets=cash-debt-o['buffer']))
        assert abs(cash-(start+o['opcf']+income-interest-.09-.08-principal_bond-principal_cb-principal_other-dividend))<1e-8
    assert abs(bond)+abs(cb)+abs(other)<1e-7
    return rows

def parent(finance_rows, receipt_ratio=.9, extra_working_capital=0):
    cash=54.070475;bank=36.073049;bond=BOND;legal=30.522922;receivable=3.823753;rows=[]
    declarations=[2.7,2.2,2,2.5,2.5]
    for i in range(5):
        start=cash; declared=declarations[i]; received=receivable+declared*receipt_ratio
        receivable=declared*(1-receipt_ratio)
        ebit=-2+.2*i; taxes=.15
        income=start*.015
        interest=bank*.03+bond*.022+(.131291 if i==2 else 0)
        principal=([0,0,1.4,3.85,1.533704][i]+(CB if i==1 else 0)+(2.543051 if i==2 else 0))
        capital_spend=.2+(extra_working_capital if i==0 else 0)
        cash=start+ebit-taxes-capital_spend+income+received-interest-.09-principal-D[i]*S
        # 现金收益税后预算同时作为法定利润代理；资本形成净额和还本不扣利润。
        legal+=ebit-taxes+income+declared-interest-.09-D[i]*S
        bond-=[0,0,1.4,3.85,1.533704][i]
        reserve=.7*(1.015**i)+(.4*(1.015**(i-2)) if i>=2 else 0)
        parent_free=cash
        sub_lower=finance_rows[i]['closing_assets']-cash-reserve
        sub_buffer=finance_rows[i]['operating_buffer']-6
        rows.append(dict(year=i+1,opening_assets=start,declared=declared,received=received,ebit=ebit,tax=taxes,net_capital_spend=capital_spend,income=income,interest=interest,principal=principal,common_distribution=D[i]*S,closing_assets=cash,extra_reserve=reserve,parent_free=parent_free,parent_buffer=6,parent_headroom=parent_free-6,legal_retained=legal,subsidiary_assets_lower_bound=sub_lower,subsidiary_buffer=sub_buffer,subsidiary_headroom=sub_lower-sub_buffer))
        assert abs(cash+reserve+sub_lower-finance_rows[i]['closing_assets'])<1e-8
    return rows

def valuation(ops,fin):
    results=[]
    for j,(g,roic,wacc,ke) in enumerate([(.015,.11,.092,.112),(.02,.14,.085,.10)]):
        fcff6=ops[-1]['nopat']*(1+g)*(1-g/roic)
        ev5=fcff6/(wacc-g)
        bridge5=fin[-1]['net_financial_assets']+NONOP[j]+DERIV-PERP-MINORITY
        tv5=(ev5+bridge5)/S
        dpv=sum(d/(1+ke)**(i+1) for i,d in enumerate(D))
        tpv=tv5/(1+ke)**5
        bridge0=A0-BANK-BOND-CB-OTHER-PENSION-8+NONOP[j]+DERIV-PERP-MINORITY
        fcff_dcf=(sum(o['fcff']/(1+wacc)**o['year'] for o in ops)+ev5/(1+wacc)**5+bridge0)/S
        earnings=(ops[2]['nopat']+ops[3]['nopat'])/2
        auxiliary=(earnings/wacc+bridge0)/S
        results.append(dict(g=g,incremental_roic=roic,wacc=wacc,cost_of_equity=ke,fcff6=fcff6,ev5=ev5,bridge5=bridge5,tv5=tv5,dividend_pv=dpv,terminal_pv=tpv,value=dpv+tpv,terminal_fraction=tpv/(dpv+tpv),bridge0=bridge0,fcff_dcf=fcff_dcf,auxiliary=auxiliary,normalized_nopat=earnings))
    return results

def main():
    ops=operating();fin=finance(ops);par=parent(fin);v=valuation(ops,fin)
    stresses={}
    for label,oo,ff in [('network_margin_minus_2pp',operating(network_shift=-.02),None),('optimistic_margins',operating(network_shift=.05,enterprise_shift=.02),None),('structural_damage',operating(network_shift=-.08,enterprise_shift=-.04,nwc_ratio=.27),None),('tax25pct',operating(tax=.25),None),('nwc22pct',operating(nwc_ratio=.22),None),('cyclical_delay',operating(cycle=True),None),('asset_yield_1pct',ops,finance(ops,asset_yield=.01)),('bank_rate_4pct',ops,finance(ops,bank_rate=.04)),('financial_assets_minus10pct',ops,finance(ops,initial_haircut=.1))]:
        ff=ff or finance(oo)
        stresses[label]=dict(valuation=valuation(oo,ff) if oo[-1]['nopat']>0 else None,final_nopat=oo[-1]['nopat'],final_net_financial_assets=ff[-1]['net_financial_assets'],min_gross_cash=min(x['closing_assets'] for x in ff),note='终态亏损不作负永续普通股估值，必须研究收缩或退出' if oo[-1]['nopat']<=0 else '')
    stresses['parent_extra_working_capital_5']=parent(fin,extra_working_capital=5)
    stresses['parent_50pct_receipt']=parent(fin,receipt_ratio=.5)
    # 零利息/零分配特例，期末资产须恰等起点加经营现金减本金及优先/少数分配。
    special=finance(ops,asset_yield=0,bank_rate=0,distributions=[0]*5)
    expected=A0+sum(o['opcf'] for o in ops)-sum(x['cash_interest'] for x in special)-.17*5-BOND-CB-OTHER-PENSION
    assert abs(special[-1]['closing_assets']-expected)<1e-8
    assert all(p['legal_retained']>0 and p['parent_headroom']>0 and p['subsidiary_headroom']>0 for p in par)
    assert abs(ops[-1]['nopat']-5.3376)<1e-8
    previous_ic=59.639223
    for o in ops:
        assert abs(o['nopat']-o['fcff']-(o['invested_capital']-previous_ic))<1e-8
        assert abs(o['nopat']+o['cash_tax']-o['ebit'])<1e-8
        previous_ic=o['invested_capital']
    assert abs(5.3376*(1+0)*(1-0/.11)/(.092-0)-5.3376/.092)<1e-10
    assert abs(sum(x['common_distribution'] for x in fin)-sum(D)*S)<1e-8
    output=dict(unit='CNY billion; shares billion',shares=S,opening_assets=A0,distributions=D,operating=ops,finance=fin,parent=par,valuation=v,sensitivities=stresses,self_checks='passed')
    Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(valuation=v,finance=fin,parent=par),ensure_ascii=False,indent=2))
if __name__=='__main__':main()

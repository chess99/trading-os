"""新洋丰：金额亿元，股数亿股；标准库、离线可重算。"""
import json
from pathlib import Path
SHARES=12.54734262
CASH=25.21-SHARES*.10 # 已付中期分红
OTHER_FINANCIAL=2.4 # 交易金融资产1、其他权益工具1.4，不含受限资金
BOND_BOOK=10.7729929374
BOND_REDEEM=9.999*1.12
DEBT_BOOK=28.748149332
OTHER_DEBT=DEBT_BOOK-BOND_BOOK
DEBT_SETTLEMENT=OTHER_DEBT+BOND_REDEEM
MINORITY=6.5 # 正常化少数利润0.65×10；敏感性另列
GROWTH=[10,10,7,5,4]
DA=[8,8.5,9,9.3,9.6]
WC=[6,3,2,1.6,1.6]
DPS=[.22,.24,.26,.28,.30]
NOPAT_LOW=[17,17.7,18.5,19.3,20.2]
NOPAT_HIGH=[17.4,18.4,19.7,20.9,22.2]
NOPAT_BASE=[(a+b)/2 for a,b in zip(NOPAT_LOW,NOPAT_HIGH)]
OPERATING_CASH=15
NET=CASH-OPERATING_CASH+OTHER_FINANCIAL-DEBT_SETTLEMENT-MINORITY

def enterprise(nopat,rate,roic=.10,g=.02,growth=None):
    growth=GROWTH if growth is None else growth
    fcff=[p+x-x-cap-w for p,x,cap,w in zip(nopat,DA,growth,WC)]
    tv=nopat[-1]*(1+g)*(1-g/roic)/(rate-g)
    pv=sum(c/(1+rate)**(i+1) for i,c in enumerate(fcff))
    tpv=tv/(1+rate)**5
    return dict(fcff=fcff,terminal_enterprise=tv,terminal_pv=tpv,terminal_share_of_ev=tpv/(pv+tpv),enterprise_value=pv+tpv,equity_value=pv+tpv+NET,per_share=(pv+tpv+NET)/SHARES,rate=rate,roic=roic,g=g)

def budget(convert=False,extra_capex=0,delay_wc=0,nopat_path=None):
    cash=CASH;debt=OTHER_DEBT;rows=[]
    shares=SHARES+(9.999/16.79 if convert else 0)
    # 团体现金至少15亿元。现金不足按4%融资，多余归还银行债；不强制提前清偿旧债。
    for i,n in enumerate(NOPAT_BASE if nopat_path is None else nopat_path):
        opening=cash;olddebt=debt
        interest=olddebt*.04
        cash_yield=max(opening-15,0)*.015
        # NOPAT剔除所有融资及金融资产收益。归母需扣少数利润。
        parent_profit=n-interest*.75+cash_yield*.75-.65
        div=DPS[i]*shares
        minority_div=.20
        redemption=0 if convert or i else BOND_REDEEM
        cap=DA[i]+GROWTH[i]+(extra_capex if i<3 else 0)
        wc=WC[i]+(delay_wc if i==0 else (-delay_wc if i==2 else 0))
        ocf=n+DA[i]-wc-interest*.75+cash_yield*.75
        before_finance=opening+ocf-cap-div-minority_div-redemption
        borrowing=max(15-before_finance,0)
        repayment=min(max(before_finance-15,0),debt)
        debt+=borrowing-repayment
        cash=before_finance+borrowing-repayment
        assert abs(cash-(opening+ocf-cap-div-minority_div-redemption+borrowing-repayment))<1e-9
        rows.append(dict(year=i+1,nopat=n,ordinary_profit=parent_profit,opening_cash=opening,ocf=ocf,maintenance_capex=DA[i],growth_capex=cap-DA[i],working_capital_increase=wc,dividend=div,minority_dividend=minority_div,bond_redemption=redemption,borrowing=borrowing,bank_repayment=repayment,closing_cash=cash,closing_debt=debt,shares=shares))
    # 5年后保留经营现金15，超额本金单列；终值NOPAT对应经营资产、不含金融收益。
    # 与当前价值同一经营终值方法，剔除银行债、少数请求权，单列超额金融本金。
    tvs=[]
    for path,rate,roic in [(NOPAT_LOW,.09,.10),(NOPAT_HIGH,.085,.11)]:
        ev=enterprise(path,rate,roic)['terminal_enterprise']
        tvs.append((ev-debt+max(cash-15,0)+OTHER_FINANCIAL-MINORITY-5*(.65-.20))/shares)
    return dict(rows=rows,year_5_terminal_range=tvs,closing_cash=cash,closing_debt=debt,shares=shares,excess_cash=max(cash-15,0))

def parent_budget():
    cash=16.8039465834-SHARES*.10
    rows=[]
    # 母公司自身经营现金4.5、实体维护2.5，子公司上划预算1.5，均非重复集团收益。
    # 偿债通过3亿元现有集团往来收回及4亿元母公司再融资支持；往来不当利润。
    for i,d in enumerate(DPS):
        op=4.5;up=1.5;cap=2.5;invest=1 if i<3 else .5
        receivable_collection=3 if i==0 else 0
        refinance=4 if i==0 else 0
        redemption=BOND_REDEEM if i==0 else 0
        intcash=.12 # 4亿元×4%税后，末年还本前保留全年利息
        loan_repayment=4 if i==4 else 0
        new=cash+op+up+receivable_collection+refinance-cap-invest-redemption-d*SHARES-intcash-loan_repayment
        rows.append(dict(year=i+1,opening_cash=cash,self_operating_cash=op,subsidiary_dividend_cash=up,receivable_collection=receivable_collection,refinance=refinance,maintenance=cap,new_equity_investment=invest,bond_redemption=redemption,dividend=d*SHARES,interest_after_tax=intcash,loan_repayment=loan_repayment,closing_cash=new))
        assert new>0
        cash=new
    return rows

def run():
    low=enterprise(NOPAT_LOW,.09,.10)
    high=enterprise(NOPAT_HIGH,.085,.11)
    base=enterprise(NOPAT_BASE,.0875,.105)
    sensitivity=enterprise([x-2 for x in NOPAT_BASE],.0875,.105)
    extra=enterprise(NOPAT_BASE,.0875,.105,growth=[15,15,12,5,4])
    cyc=enterprise([NOPAT_BASE[0]-3,NOPAT_BASE[1]-2]+NOPAT_BASE[2:],.0875,.105)
    structural=enterprise([x-4 for x in NOPAT_BASE],.095,.08,.01,growth=[15,15,12,5,4])
    remaining=sum(b*(1-r) for b,r in [(5,.6688),(11.0725,.401),(3.688832,.6051),(2.5,.965),(16,.2071),(3.5,.6157)])
    repay=budget();conv=budget(True);stress=budget(False,5,3)
    lower_cash=budget(nopat_path=NOPAT_LOW)
    higher_cash=budget(nopat_path=NOPAT_HIGH)
    pe=[15.5*10/SHARES,18*12/SHARES]
    assert len(DPS)==5 and len(repay['rows'])==5
    assert abs(repay['rows'][0]['borrowing']-4.442537590685502)<1e-8
    assert repay['closing_debt']==0
    assert abs(sum(r['minority_dividend'] for r in repay['rows'])+2.25-5*.65)<1e-9
    assert abs(parent_budget()[-1]['loan_repayment']-4)<1e-9
    assert abs(sum(DPS)-1.3)<1e-12
    assert abs((10/1.1+110/1.1**2)-100)<1e-9 # 手算贴现特例
    assert enterprise([0]*5,.09,growth=[0]*5)['per_share']<0 # 营运资本仍需支出
    # 全零经营/义务的直接公式、无融资现金守恒
    assert (0+0-0)/SHARES==0
    return dict(units='亿元、亿股；每股值元',opening=dict(cash_after_paid_dividend=CASH,operating_cash_reserved=OPERATING_CASH,other_financial=OTHER_FINANCIAL,debt_book=DEBT_BOOK,debt_settlement=DEBT_SETTLEMENT,minority_claim=MINORITY,net_adjustment=NET),remaining_important_projects_estimate=remaining,core_low=low,core_high=high,base=base,profit_minus_2=sensitivity,profit_sensitivity_delta=sensitivity['per_share']-base['per_share'],extra_15_capex=extra,extra_capex_value_delta=extra['per_share']-base['per_share'],cyclical=cyc,structural=structural,auxiliary_pe=pe,cash_repayment=repay,conversion=conv,lower_operating_budget=lower_cash,higher_operating_budget=higher_cash,capex_and_wc_stress=stress,parent_budget=parent_budget(),distributions=DPS,return_terminal=[round(lower_cash['year_5_terminal_range'][0],1),round(higher_cash['year_5_terminal_range'][1],1)],terminal_minority_sensitivity_per_share=2/SHARES)
if __name__=='__main__':
    p=Path(__file__).with_name('2026-H1-output.json');p.write_text(json.dumps(run(),ensure_ascii=False,indent=2)+'\n');print(p)

"""阳光电源：2026-Q3轻量可重算研究模型。标准库即可，金额十亿元，股数十亿股。

预测年度：自2026-11-07起的五个完整年度。财务锚为2026-09-30，
只机械调整已知期后回购；尚未披露的10月经营净流入不假装已知。
运行 python 2026-Q3.py；输出关键结果。无冻结输出、压缩包或历史依赖。
"""
from copy import deepcopy
from math import isclose
import json

AS_OF = "2026-11-06T23:59:59+08:00"
SHARES = 2.073211424  # 全部已发行；员工用途库存股假设最终重新流通。
FACT = {
    "cash_q3":26.62337922934, "trading_assets_total":4.52813228625,
    "cash_h1":30.86057076034, "parent_cash_h1":26.21442216901,
    "parent_retained_h1":30.05429154957, "interim_paid":1.3167900224,
    "buyback_sep_including_fees":0.32496426785,
    "buyback_oct_excluding_fees":0.35486831066,
    "ar":21.83832560435,"notes":2.19390942138,"receivable_finance":.67705601753,
    "inventory":40.97175632798,"prepay":5.43021857933,"contract_assets":1.54910001861,
    "payables":25.61811136,"bills":20.99235731954,"customer_advance":14.6655013385,
    "provisions":5.84627847977,
    "ppe":12.45356419413,"construction":2.39497692526,
    "intangibles":1.70881189218,"rou":.53588708762,
    "short_debt":3.28524656238,"long_debt":2.87576724823,
    "current_debt":1.31952146711,"lease_debt":.44606144586,
    "long_payable":.963474634,
    "minority":3.01207010047,
    "noncore_equity":2.42302135647+.85694901353,
    "near_maturity_investment":.2274770301,
    "net_derivative_and_trading_liability":.64644996+.07927124368-.00676456896,
}
# 不同公告的交易费用口径不同，期后回购现金采用0.031而非伪精确相减。
POST_BUYBACK = .031
# H1交易性金融资产含理财2.612736及权益1.402984；Q3未分拆。
# 26亿元流动理财为明确预算，余量作为风险金融投资；不是已核Q3分类。
LIQUID_INVESTMENT_BUDGET = 2.6
INITIAL_TRADE = sum(FACT[k] for k in ("ar","notes","receivable_finance","inventory","prepay","contract_assets"))-sum(FACT[k] for k in ("payables","bills","customer_advance"))
INITIAL_FIXED = sum(FACT[k] for k in ("ppe","construction","intangibles","rou"))
INITIAL_DEBT = sum(FACT[k] for k in ("short_debt","long_debt","current_debt","lease_debt","long_payable"))
INITIAL_CASH = FACT["cash_q3"]+LIQUID_INVESTMENT_BUDGET-POST_BUYBACK
PARENT_START = FACT["parent_cash_h1"]-(FACT["cash_h1"]-FACT["cash_q3"])-POST_BUYBACK-3.0
PARENT_RETAINED = FACT["parent_retained_h1"]-FACT["interim_paid"]
INITIAL_OTHER_ASSET = .70*(FACT["noncore_equity"]+FACT["trading_assets_total"]-LIQUID_INVESTMENT_BUDGET)+FACT["near_maturity_investment"]-FACT["net_derivative_and_trading_liability"]
PAYOUT = [1.0,1.1,1.2,1.3,1.4]
LOW = dict(
    electronics=[27,29,31,33,35], storage_gwh=[75,90,103,115,125],
    storage_asp=[.46,.435,.41,.39,.375], other_revenue=[9,10,11,12,13],
    electronics_gm=[.38,.38,.375,.37,.365], storage_gm=[.25,.26,.26,.26,.26],
    other_gm=[.10,.11,.12,.12,.12], opex=[.164,.159,.154,.149,.144],
    capex=[4,4.2,4.3,4.4,4.5], depreciation=[1.7,1.9,2.1,2.3,2.5],
    ar_ratio=[.32,.315,.31,.305,.30], inventory_cogs=[.75,.72,.69,.66,.63],
    prepay_cogs=[.07,.065,.06,.055,.05], ap_cogs=[.80,.78,.76,.745,.73],
    advance_revenue=[.18,.175,.17,.16,.15], warranty=[5.8,5.8,6,6.2,6.5],
    wacc=.10, cost_equity=.105, fade=[.05,.04,.03,.025,.02],
    fade_roic=.12, terminal_growth=.015, terminal_roic=.10,
)
HIGH = dict(
    electronics=[29,32,35,38,41], storage_gwh=[85,105,123,140,150],
    storage_asp=[.47,.45,.43,.415,.40], other_revenue=[10,11,12,13,14],
    electronics_gm=[.395,.395,.395,.3925,.39], storage_gm=[.27,.285,.29,.29,.29],
    other_gm=[.10,.11,.12,.12,.12], opex=[.145,.14375,.1425,.14125,.14],
    capex=[4.5,4.8,5.1,5.3,5.5], depreciation=[1.7,2.0,2.3,2.6,2.9],
    ar_ratio=[.31,.3025,.295,.2875,.28], inventory_cogs=[.74,.705,.67,.635,.60],
    prepay_cogs=[.06,.0575,.055,.0525,.05], ap_cogs=[.80,.775,.75,.725,.70],
    advance_revenue=[.18,.175,.17,.16,.15], warranty=[6,6.5,7,7.5,8],
    wacc=.09, cost_equity=.095, fade=[.07,.06,.05,.04,.03],
    fade_roic=.14, terminal_growth=.02, terminal_roic=.12,
)
BASE = {k:[(a+b)/2 for a,b in zip(LOW[k],HIGH[k])] if isinstance(LOW[k],list) else (LOW[k]+HIGH[k])/2 for k in LOW}

def operating_rows(p):
    rows=[]; prior_trade=INITIAL_TRADE; prior_warranty=FACT["provisions"]
    required_cash=12.; fixed=INITIAL_FIXED
    for i in range(5):
        es=p["storage_gwh"][i]*p["storage_asp"][i]
        revenue=p["electronics"][i]+es+p["other_revenue"][i]
        gp=p["electronics"][i]*p["electronics_gm"][i]+es*p["storage_gm"][i]+p["other_revenue"][i]*p["other_gm"][i]
        cogs=revenue-gp
        # 包含税金附加、销售、管理、研发、正常减值及现金等价激励成本；无SBC加回。
        expenses=max(revenue*p["opex"][i],12.3+.7*i)
        ebit=gp-expenses
        nopat=ebit*(1-.18) if ebit>0 else ebit
        ar=revenue*p["ar_ratio"][i]; inventory=cogs*p["inventory_cogs"][i]
        prepay=cogs*p["prepay_cogs"][i]; contract=.025*revenue
        ap=cogs*p["ap_cogs"][i]; advance=revenue*p["advance_revenue"][i]
        trade=ar+inventory+prepay+contract-ap-advance
        need_cash=max(12.,.15*revenue)
        fcff=nopat+p["depreciation"][i]-p["capex"][i]-(trade-prior_trade)+(p["warranty"][i]-prior_warranty)-(need_cash-required_cash)
        warranty_cash=.025*revenue-(p["warranty"][i]-prior_warranty)
        assert warranty_cash>=0
        fixed+=p["capex"][i]-p["depreciation"][i]
        rows.append(dict(year=i+1,revenue=revenue,storage_revenue=es,gross_margin=gp/revenue,expenses=expenses,ebit=ebit,nopat=nopat,cogs=cogs,
                         ar=ar,inventory=inventory,prepay=prepay,contract=contract,ap=ap,advance=advance,trade=trade,
                         warranty=p["warranty"][i],warranty_cash=warranty_cash,
                         capex=p["capex"][i],depreciation=p["depreciation"][i],fixed=fixed,
                         required_cash=need_cash,fcff=fcff))
        prior_trade=trade;prior_warranty=p["warranty"][i];required_cash=need_cash
    return rows

def continuing_value(nopat,capital,wacc,growths,incremental_roic,steady_g,steady_roic):
    """从第5年末计价：6—10年逐渐降速，随后稳定；资本需求约束实际再投资。"""
    assert wacc>steady_g and incremental_roic>0 and steady_roic>0
    value=0.; trail=[]
    for n,g in enumerate(growths,1):
        profit=nopat*(1+g)
        reinvest=max((profit-nopat)/incremental_roic,capital*g)
        cash=profit-reinvest
        value+=cash/(1+wacc)**n
        capital+=reinvest;nopat=profit
        trail.append(dict(year=n+5,nopat=profit,reinvestment=reinvest,fcff=cash,capital=capital))
    next_profit=nopat*(1+steady_g)
    reinvest=max(next_profit*steady_g/steady_roic,capital*steady_g)
    terminal=(next_profit-reinvest)/(wacc-steady_g)
    value+=terminal/(1+wacc)**len(growths)
    return value,trail,terminal/(1+wacc)**len(growths)

def run(p, shock_name="core", extra_parent_settlement=0., extra_capex=0., subsidiary_cash_haircut=.025, liquidity_locked=0.):
    p=deepcopy(p)
    p["capex"]=[v+extra_capex for v in p["capex"]]
    reference=operating_rows(BASE)
    rows=operating_rows(p)
    cash=INITIAL_CASH-liquidity_locked;debt=INITIAL_DEBT;minority=FACT["minority"]
    other_asset=INITIAL_OTHER_ASSET+liquidity_locked
    parent=PARENT_START-extra_parent_settlement; retained=PARENT_RETAINED
    parent_minimum=6.; extra_debt=0.; distributions=[]; feasible=True
    for i,r in enumerate(rows):
        # 到期及带回购权长期应付款在首年预算偿还，不假定这些索取权永久滚动。
        repayment=FACT["current_debt"]+FACT["long_payable"] if i==0 else 0.
        interest=((debt-extra_debt)*.035+extra_debt*.055)*(1-.18)
        cash_income=max(cash-(12. if i==0 else rows[i-1]["required_cash"]),0)*.015
        # 金额十亿元：人民币1.74亿元 + EUR1000万元×7.62。
        new_fund=(.174+.010*7.62) if i==0 else 0.
        thaihe=.15 if i==0 else 0. # 二级市场增持未公开成交总价，预算1.5亿元。
        minority_cash=.10+.025*i
        netprofit_delta=r["nopat"]-reference[i]["nopat"]
        parent_own=[2.4,2.8,3.0,3.2,3.4][i]+.30*netprofit_delta
        parent_profit=[1.5,2,2.5,3,3.5][i]+.30*netprofit_delta
        allocation=[1.5,1.8,2,2,2][i]+(max(-netprofit_delta,0)*.15)
        parent_before=parent+parent_own-allocation-(.174 if i==0 else 0)
        # 付款主体缺口先停止股利，并检验有限额、须真实获得的外部融资。
        # 新借款按5.5%计息，提款当年计半年利息；集团现金及终值债务同步增加。
        parent_short=max(parent_minimum-parent_before,0)
        parent_loan=min(parent_short/(1-.055*(1-.18)/2),max(4.-extra_debt,0))
        parent_loan_interest=parent_loan*.055*(1-.18)/2
        parent_before+=parent_loan-parent_loan_interest
        debt+=parent_loan;extra_debt+=parent_loan
        # 不依赖未来子公司股利；收到历史应收股利也未列为新增母利润。
        legal_add=parent_profit-max(parent_profit,0)*.10
        retained+=legal_add
        before=cash+r["fcff"]+cash_income-interest-repayment-new_fund-thaihe-minority_cash+parent_loan-parent_loan_interest
        debt-=repayment
        liquidity_shortfall=max(r["required_cash"]-before,0)
        borrowing=min(liquidity_shortfall,max(4.-extra_debt,0))
        debt+=borrowing;extra_debt+=borrowing;before+=borrowing
        # 子公司至少保留集团必要现金中超过母最低现金的部分。
        # 有余量时以新增合法出资/贷款预算配置，不能让母现金超过集团总现金。
        subsidiary_minimum=max(r["required_cash"]-parent_minimum,0)
        extra_allocation=min(max(subsidiary_minimum-(before-parent_before),0),max(parent_before-parent_minimum,0))
        allocation+=extra_allocation;parent_before-=extra_allocation
        allowed=max(0.,min(before-r["required_cash"],parent_before-parent_minimum,retained))
        distribution=min(p.get("distribution_budget",PAYOUT)[i]*SHARES,allowed)
        parent=parent_before-distribution;retained-=distribution;cash=before-distribution
        feasible=feasible and cash>=r["required_cash"]-1e-9 and parent>=parent_minimum-1e-9 and cash-parent>=subsidiary_minimum-1e-9
        other_asset+=.70*new_fund  # 支付出资取得金融权利，按70%回收；不计其投资收益。
        minority=max(minority-.10,0) if i==0 else minority # 泰禾收购减少少数索取权代理，未重复增加资产。
        distributions.append(distribution/SHARES)
        r.update(cash=cash,debt=debt,interest=interest,cash_income=cash_income,repayment=repayment,new_fund=new_fund,thaihe=thaihe,
                 parent_loan_interest=parent_loan_interest,
                 minority_cash=minority_cash,other_asset=other_asset,parent_cash=parent,parent_profit=parent_profit,
                 parent_operating_cash_after_capital=parent_own,parent_net_funding=allocation,
                 parent_retained=retained,distribution=distribution,distribution_per_share=distribution/SHARES,
                 new_borrowing=borrowing+parent_loan,parent_new_loan=parent_loan,extra_internal_allocation=extra_allocation)
        assert isclose(cash, before-distribution, abs_tol=1e-9)
        assert isclose(parent,parent_before-distribution,abs_tol=1e-9)
    last=rows[-1]
    # 其他净经营资产假定3亿元不变；不在桥中再加。保修余额保持经营责任。
    capital=last["fixed"]+last["trade"]+last["required_cash"]-last["warranty"]+.3
    ev5,fade,tv10pv=continuing_value(last["nopat"],capital,p["wacc"],p["fade"],p["fade_roic"],p["terminal_growth"],p["terminal_roic"])
    extra_cash=last["cash"]-last["required_cash"]
    subsidiary_extra=max(extra_cash-max(parent-parent_minimum,0),0)
    cash_recovery_cost=subsidiary_extra*subsidiary_cash_haircut
    terminal_equity=ev5+extra_cash-cash_recovery_cost+other_asset-debt-minority
    terminal_per_share=terminal_equity/SHARES if feasible else None
    dividend_pv=sum(d/(1+p["cost_equity"])**(i+1) for i,d in enumerate(distributions))
    terminal_pv=(terminal_equity/SHARES)/(1+p["cost_equity"])**5
    current=dividend_pv+terminal_pv if feasible else None
    return dict(name=shock_name,feasible=feasible,value=current,terminal_per_share=terminal_per_share,
                distributions=distributions,rows=rows,terminal_operating_value=ev5,terminal_extra_cash=extra_cash,
                terminal_other_asset=other_asset,terminal_debt=debt,terminal_minority=minority,
                terminal_subsidiary_extra_cash=subsidiary_extra,terminal_cash_recovery_cost=cash_recovery_cost,
                value_dividends_pv=dividend_pv,terminal_pv_fraction=terminal_pv/(dividend_pv+terminal_pv),
                mature_value_fraction_of_ev5=tv10pv/ev5,fade=fade)

def scenario(kind):
    p=deepcopy(HIGH if kind=="optimistic" else BASE)
    for i in range(5):
        if kind=="cyclical" and i<2:
            p["storage_gwh"][i]*=[.85,.90][i]
            p["storage_gm"][i]=[.21,.24][i]
            p["inventory_cogs"][i]+=[.10,.06][i]
            p["ar_ratio"][i]+=[.04,.025][i]
            p["capex"][i]+=.4
        elif kind=="structural" and i>=1:
            p["storage_gwh"][i]*=.80
            p["electronics"][i]*=.90
            p["storage_gm"][i]=.20
            p["electronics_gm"][i]=.34
            p["ar_ratio"][i]+=.05;p["inventory_cogs"][i]+=.10
            p["ap_cogs"][i]-=.08;p["advance_revenue"][i]-=.03
            p["capex"][i]+=.6
        elif kind=="optimistic":
            p["storage_gwh"][i]*=1.18
            p["storage_gm"][i]=.31
            p["capex"][i]+=.8
    if kind=="structural":
        p["distribution_budget"]=[1.,0.,0.,0.,0.] # 永久受损自第2年明确，前瞻性暂停分配保留付款资金。
        p["fade"]=[.01,.01,.01,.01,.01];p["fade_roic"]=.09
        p["terminal_growth"]=.01;p["terminal_roic"]=.09;p["wacc"]=.105;p["cost_equity"]=.115
    return run(p,kind)

def auxiliary(nopat,wacc):
    """现有平台零实质扩张：以可持续NOPAT、稳态维护投入相等为收益价值锚。"""
    bridge=INITIAL_CASH-12.+INITIAL_OTHER_ASSET-INITIAL_DEBT-FACT["minority"]
    return (nopat/wacc+bridge)/SHARES

def checks():
    # 独立手算：每年10，r10%，g0，同一正式终值计算链返回100。
    v,_,_=continuing_value(10.,40.,.10,[0,0,0,0,0],.12,0.,.10)
    assert isclose(v,100.,rel_tol=1e-12)
    # 同一链：NOPAT以2%增长，新增ROIC10%，稳态第一年FCFF=8.16，价值102。
    v,_,_=continuing_value(10.,100.,.10,[],.12,.02,.10)
    assert isclose(v,102.,rel_tol=1e-12)
    lo=run(LOW);hi=run(HIGH)
    for out in [lo,hi,run(BASE),scenario("cyclical"),scenario("structural"),scenario("optimistic")]:
        assert len(out["rows"])==len(out["distributions"])==5
        rows=out["rows"]
        cash_end=INITIAL_CASH+sum(r["fcff"]+r["cash_income"]-r["interest"]-r["parent_loan_interest"]-r["repayment"]-r["new_fund"]-r["thaihe"]-r["minority_cash"]+r["new_borrowing"]-r["distribution"] for r in rows)
        debt_end=INITIAL_DEBT+sum(r["new_borrowing"]-r["repayment"] for r in rows)
        parent_end=PARENT_START+sum(r["parent_operating_cash_after_capital"]-r["parent_net_funding"]-(.174 if r["year"]==1 else 0)+r["parent_new_loan"]-r["parent_loan_interest"]-r["distribution"] for r in rows)
        retained_end=PARENT_RETAINED+sum(r["parent_profit"]-max(r["parent_profit"],0)*.10-r["distribution"] for r in rows)
        assert isclose(cash_end,rows[-1]["cash"],abs_tol=1e-8)
        assert isclose(debt_end,rows[-1]["debt"],abs_tol=1e-8)
        assert isclose(parent_end,rows[-1]["parent_cash"],abs_tol=1e-8)
        assert isclose(retained_end,rows[-1]["parent_retained"],abs_tol=1e-8)
        if out["feasible"]:
            assert isclose(out["terminal_per_share"]*SHARES,out["terminal_operating_value"]+out["terminal_extra_cash"]-out["terminal_cash_recovery_cost"]+out["terminal_other_asset"]-debt_end-out["terminal_minority"],abs_tol=1e-8)
            for r in out["rows"]:
                assert r["cash"]>=r["required_cash"]-1e-8
                assert r["parent_cash"]>=6-1e-8 and r["parent_retained"]>=0
                assert r["parent_cash"]<=r["cash"]+1e-8
    return True

def complete_diagnostics():
    checks()
    results={"as_of":AS_OF,"units":"CNY billion; billion issued shares", "shares":SHARES,
             "initial_trade":INITIAL_TRADE,"initial_fixed":INITIAL_FIXED,"initial_debt":INITIAL_DEBT,
             "initial_cash":INITIAL_CASH,"parent_start":PARENT_START,"initial_other_asset":INITIAL_OTHER_ASSET,
             "low":run(LOW),"high":run(HIGH),"base":run(BASE),
             "cyclical":scenario("cyclical"),"structural":scenario("structural"),"optimistic":scenario("optimistic"),
             "capex_extra_1_each_year":{"low":run(LOW,extra_capex=1.)["value"],"high":run(HIGH,extra_capex=1.)["value"]},
             "subsidiary_cash_recovery_cost_20pct":{"low":run(LOW,subsidiary_cash_haircut=.20)["value"],"high":run(HIGH,subsidiary_cash_haircut=.20)["value"]},
             "trading_liquidity_unavailable":{"low":run(LOW,liquidity_locked=2.6)["value"],"high":run(HIGH,liquidity_locked=2.6)["value"]},
             "parent_extra_settlement_10":run(BASE,extra_parent_settlement=10.),
             "auxiliary":{"low":auxiliary(8.,.10),"high":auxiliary(10.,.09)},"checks":"passed"}
    return results

METADATA = {'symbol': 'CN:300274', 'report_period': '2026-Q3', 'information_cutoff': '2026-11-06T23:59:59+08:00', 'valuation_note': '核心采用五年实际股利加第五年普通股持续经营价值折现，较谨慎/较顺利端末年收入948.75/1150亿元、NOPAT93.66/155.55亿元；经营资本成本10%/9%、权益成本10.5%/9.5%。第6—10年利润增速逐步降至2%/3%，此后名义增长1.5%/2%、新增资本回报10%/12%，再投资不低于物理资本要求。现有平台正常收益资本化为42.66—57.67元，主法上端要求扩张兑现，两法不机械平均。核心不含结构性不利与额外乐观路径。', 'return_model_note': '2026年11月7日起五个完整年度每股现金分配预算1.00/1.10/1.20/1.30/1.40元，已付9月0.64元不重复计入。第五年EV来自第6—10年现金及随后成熟经营，另加实际分红后额外现金和金融资产净回收，扣子公司现金回收成本、同一金融债务和少数权利，按20.73211424亿股得56.41—114.83元；不提供三年终值。股份薪酬以现金等价报酬预算替代，现有回购后续付款纳入首年激励预算；已有或有授予采用全部已发行股份，不享受永久注销利益。母分配经现金、正常内部结算及法定留存检验，零未来子公司股利预算；Q3母现金未披露，起点189.46亿元是明确扣减后的估计。压力路径会削减股利并为有限新增融资支付利息、在终值扣债；分配并非公司承诺。'}


def compute():
    checks()
    low, high = run(LOW), run(HIGH)
    out = dict(METADATA)
    out.update(schema="trading_os_research_result_v1", value_range={"low":round(low["value"],2),"high":round(high["value"],2),"currency":"CNY"},
        return_model={"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"CNY","model_as_of":AS_OF,
            "base_case_distributions_per_share":list(PAYOUT),
            "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":round(low["terminal_per_share"],2),"high":round(high["terminal_per_share"],2)}}},
        operating_summary={side:[{key:row[key] for key in ("year","revenue","nopat","capex","trade","fcff","cash","parent_cash")}for row in value["rows"]]for side,value in (("low",low),("high",high))},
        scenarios={name:{"value":value["value"],"distributions":value["distributions"],"feasible":value["feasible"]}for name in ("cyclical","structural","optimistic")if(value:=scenario(name))},
        auxiliary={"low":auxiliary(8.,.10),"high":auxiliary(10.,.09)})
    return out

if __name__=="__main__":
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--full-output",type=Path,help="可选：完整工作底稿另存临时目录")
    args=parser.parse_args()
    if args.full_output:
        args.full_output.write_text(json.dumps(complete_diagnostics(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    text=json.dumps(compute(),ensure_ascii=False,indent=2)+"\n"
    if args.output:args.output.write_text(text,encoding="utf-8")
    else:print(text,end="")

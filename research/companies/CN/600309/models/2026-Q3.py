"""重算当前采用路径；长尾逐年状态在内存中生成，不进入常规交付。"""
import importlib.util,json,argparse
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("financial_engine",HERE/"2026-Q3-engine.py")
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
METADATA={'symbol': 'CN:600309', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T20:30:00+08:00', 'valuation_note': '方法一（主方法）实际普通股现金分配折现，ke11%/9.5%、Y6后EBIT95%/105%，前五年全部状态相同；约88%—91%现值来自Y5以后。来源为有证据边界的经济上划预算而非伪造法定余额；持续经营保留必要资本并释放额外金融现金。方法二独立分部增量资本回报26.74—52.09元，不机械平均。永久能力减半仅分配压力诊断，有限退出不另加核心。 现金及融资敏感性：释放Y16/Y21/Y31为40.54/35.69/27.96元，20/40/60%超额派发36.68/41.94/44.21元；每年续贷池流失10%在Y6福建资金不足，后期一次收缩与利率压力另算。', 'return_model_note': '五年D为实际普通股现金分配预算；TV5由同一Y5完整状态之后的持续现金流折现，已付现金不再加回；股数31.30471626亿，母与子少数资本同步，无未来上市增发或回购假设。科化Y12起有条件返还不超过19.86亿元本金并支付2%费用；母成本同步冲减而非增加利润、少数同比例、必要资本保留。母单体法定容量和各来源经济上划预算分层，境外不套中国储备或亏损结转。资本回收诊断区分本金、损益、费用税和少数，不强制关闭持续盈利资产。资金失败PV/TV双null；600年仅为数值收敛。'}

def compute():

    low=engine.run(**engine.SCENARIOS["low"])
    high=engine.run(**engine.SCENARIOS["high"])
    base=engine.run(**engine.SCENARIOS["base"])
    assert all(x["failure"] is None for x in (low,high,base))
    assert low["states5"]==base["states5"]==high["states5"]
    values={"low":round(low["pv"],2),"high":round(high["pv"],2),"currency":"CNY"}
    distributions=[round(x,9)for x in base["d5"]]
    terminal={"low":round(low["tv5"],9),"high":round(high["tv5"],9)}
    for x in (low,high,base):
        recomputed=sum(v/(1+x["rate"])**(i+1)for i,v in enumerate(x["d5"]))+x["tv5"]/(1+x["rate"])**5
        assert abs(recomputed-x["pv"])<1e-9

    out=dict(METADATA)
    out.update(schema="trading_os_research_result_v1",value_range=values,
        return_model={"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"CNY","model_as_of":METADATA["information_cutoff"],
            "base_case_distributions_per_share":distributions,"base_case_terminal_equity_value_range_per_share":{"year_5":terminal}})
    return out

if __name__=="__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--output",type=Path);args=parser.parse_args()
    text=json.dumps(compute(),ensure_ascii=False,indent=2)+"\n"
    if args.output:args.output.write_text(text,encoding="utf-8")
    else:print(text,end="")

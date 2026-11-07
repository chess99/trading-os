"""重算当前采用路径；长尾逐年状态在内存中生成，不进入常规交付。"""
import importlib.util,json,argparse
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("financial_engine",HERE/"2026-Q3-engine.py")
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
METADATA={'symbol': 'CN:600018', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-30T07:26:16+00:00', 'valuation_note': '主法按服务现金与完整资本/权益链估值，核心8%—9%折现；独立资本生产率法检验并保留差异，不平均。压力包络不冒充核心区间。', 'return_model_note': '未来五个持有年每股税前普通股现金0.23/0.24/0.25/0.24/0.24元，受年度利润政策、母现金与RE限制；第五年末价值来自同一路径第六年以后权益现金。2026年10月15日已付分红不重复计入。无证券现价，未计算交易IRR。'}

def compute():

    low=engine.run("volume","core_low",480)
    high=engine.run("volume","core_high",480)
    base=engine.run("volume","base",480)
    assert all(x["failure"] is None for x in (low,high,base))
    values={"low":low["present_value"],"high":high["present_value"],"currency":"CNY"}
    distributions=base["first_five"]
    terminal={"low":low["y5"],"high":high["y5"]}
    assert distributions==low["first_five"]==high["first_five"]

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

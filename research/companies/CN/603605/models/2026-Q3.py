"""当前可读计算入口；正常输出只含采用结果，详细路径按需写入临时目录。"""
from pathlib import Path
import argparse, importlib.util, json, sys
HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE / "2026-Q3"))
import calculation

def main():
    if not __debug__ or sys.flags.optimize: raise RuntimeError("数学核验需要启用断言")
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--details", type=Path)
    args = parser.parse_args()
    data = json.loads((HERE / "2026-Q3-input.json").read_text(encoding="utf-8"))
    values, holder, details = calculation.calculate(data["financial_inputs"])
    result = {"schema": "trading_os_research_result_v1", "symbol": data["symbol"], "report_period": "2026-Q3",
              "information_cutoff": data["information_cutoff"], "value_range": values,
              "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY",
                  "model_as_of": data["information_cutoff"], **holder},
              "valuation_note": data["valuation_note"], "return_model_note": data["return_model_note"]}
    if args.details:
        path = args.details.resolve()
        if path.is_relative_to(HERE): raise ValueError("详细过程输出应写入临时目录")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(details, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))

if __name__ == "__main__": main()

"""Recompute the adopted company model from readable current inputs."""
from pathlib import Path
import json
import sys

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
SOURCE = HERE / "2026-Q3"
sys.path.insert(0, str(SOURCE))
import model


data = json.loads((SOURCE / "inputs.json").read_text(encoding="utf-8"))
model.validate_inputs(data)
model.formal_kernel_cases()
cases = {}
for name in ("base", "core_low", "core_high"):
    config = dict(data["base"])
    config.update(data["scenarios"][name])
    cases[name] = model.evaluate(name, data["facts"], config)
    model.verify_production_result(cases[name], data["facts"], config)
value_range = {"low": round(cases["core_low"]["main"]["per_share"], 2), "high": round(cases["core_high"]["main"]["per_share"], 2), "currency": "CNY"}
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": "2026-10-31T00:00:00+00:00", "base_case_distributions_per_share": [round(x, 6) for x in cases["base"]["forward_distributions_per_share"]], "base_case_terminal_equity_value_range_per_share": {h: {k: round(v[k], 2) for k in ("low", "high")} for h, v in cases["base"]["terminal_equity_ranges"].items()}}

PUBLICATION = {'symbol': 'CN:603195', 'report_period': '2026-Q3', 'valuation_note': '主方法为经营自由现金流折现加净金融资产，基准约 31.78 元；辅助正常化成熟经营收益约 30.18 元，不机械平均。核心范围不是所有压力路径包络；结构损伤主方法约 20.44 元。没有可靠现价，不判断安全边际、错价或当前收益率。', 'return_model_note': '五笔为 2027—2031 年六月支付的条件预算，不含 2026 年已付 1.90 元。目标是上年归母利润的 80%，受母公司留存和现金、集团资金约束；依赖 2026 年子公司新宣派约 19.82 亿元及之后约 18—22 亿元、一般滞后一年到账。第三、五年终点为 2029、2031 年 10 月 31 日，按届时经营状态及扣除已付股息后的净金融财富重新估值，终点资本成本 10%—8.5%；不是未来交易价格或股息承诺。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

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
import projection
import dates


data = json.loads((SOURCE / "inputs.json").read_text(encoding="utf-8"))
conditional = json.loads((SOURCE / "conditional-inputs.json").read_text(encoding="utf-8"))
settings = json.loads((SOURCE / "settings.json").read_text(encoding="utf-8"))
actual = model.build_output(data)
projected = projection.conditional_output(model, data, actual, conditional)
timing = dates.date_bridge(settings, actual, projected, data)
value_range = {**timing["current_value"], "currency": "CNY"}
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": data["identity"]["cutoff"], "base_case_distributions_per_share": timing["base_timing"]["distributions"], "base_case_terminal_equity_value_range_per_share": {"year_5": timing["terminal_value"]}}

PUBLICATION = {'symbol': 'CN:600350', 'report_period': '2026-Q3', 'valuation_note': '方法一为有限收费权重估普通净资产主法，方法二为正常化普通盈利有限年金辅法，不平均。当前桥从研究估计2026年末普通权益出发，以8.5%—10%普通权益成本按实际61天折回，并在同一成本下计同批未来资本损伤；原整笔权益用道路资产率折回的近似不再直接采用。', 'return_model_note': '固定中心五年名义D；未来每年6月18日支付仅为假设，年度接口按10月31日周年末现金桶近似，不是逐日回报。2031年末有限资产终值按61天和普通权益成本回推到2031年10月31日五周年，不额外加期间CFO；晚付边界按周年重分D，五周年后未付D只计入cum-right终值。年度预算不证明6月月内现金，结构资金缺口后的终值未采用。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

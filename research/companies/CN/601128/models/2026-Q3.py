"""Recompute the adopted company model from readable current inputs."""
from pathlib import Path
import json
import sys

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
SOURCE = HERE / "2026-Q3"
sys.path.insert(0, str(SOURCE))
import producer as model
from datetime import datetime


data = json.loads((SOURCE / "inputs.json").read_text(encoding="utf-8"))
as_of = "2026-10-31T23:59:59+08:00"
base = model.project(data, datetime.fromisoformat(as_of).date(), "unpaid", "base_conversion")
values = model.value_case(data, base)
assert not model.audit(base)
value_range = {"low": round(min(x["current_value_per_share"] for x in values), 2), "high": round(max(x["current_value_per_share"] for x in values), 2), "currency": "CNY"}
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": as_of, "base_case_distributions_per_share": [x["dps"] for x in base["rows"][:5]], "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": min(x["terminal_5_per_share"] for x in values), "high": max(x["terminal_5_per_share"] for x in values)}}}

PUBLICATION = {'symbol': 'CN:601128', 'report_period': '2026-Q3', 'valuation_note': '资本约束普通股现金/剩余收益一致主法，条件转股、截止未付且持有人享有0.13股利，Ke11.5%—10.5%、成熟g3%。主法原值5.3094—6.1563元；辅助正常化盈利/必要资本法5.60—6.44元。完整赎回替代6.52—7.60元单列，不取高值或与压力情景拼区间。终值现值占约84.7%—86.5%，资本返还速度和资金效用为条件预算；无本次可核报价，不给错价结论。', 'return_model_note': '本接口采用截至2026-10-31T23:59:59+08:00每股0.13元中期股利尚未支付且该持有人享有该笔分配权的条件转股基准；登记和实际支付未被证实。0.13包含首窗总D，不另加。未来五窗D均为真实现金预算，2028转股发生于第二窗内，转换前分红调整转价，期末股数约4,889.535490百万股。第五年终值由同一分配后普通权益、股份及后续五年经营/资本过渡形成，不复制当前价值。转股没有新增现金，其后返还资本承担正常融资替代成本。后期高派息及10%余量返还速度是资本配置条件而非承诺；paid试算不是纯时间敏感性，未采用其差值量化0.13日期风险。主法5.3094—6.1563元、Y5终值7.751276091349804—8.769333149421309元；完整数值见model-output.json及report.md。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

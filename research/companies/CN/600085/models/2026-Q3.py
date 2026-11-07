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
import targeted_model


data = json.loads((SOURCE / "inputs.json").read_text(encoding="utf-8"))
result = model.simulate(data, next(x for x in data["scenarios"] if x["id"] == "base"))
values = result["valuation_by_rate"]
targeted_data = json.loads((SOURCE / "targeted-inputs.json").read_text(encoding="utf-8"))
weak = targeted_model.simulate(targeted_data, next(x for x in targeted_data["scenarios"] if x["id"] == "slow_demand"))
recovery = model.simulate(data, next(x for x in data["scenarios"] if x["id"] == "recovery_with_restock"))
# Published operating bounds include slow demand and funded recovery.
value_range = {"low": round(min(x["current_value_per_share"] for x in weak["valuation_by_rate"]), 1), "high": round(max(x["current_value_per_share"] for x in recovery["valuation_by_rate"]), 1), "currency": "CNY"}
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": "2026-10-31T23:59:59+08:00", "base_case_distributions_per_share": result["dividends_per_share_year1_to5"], "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": min(x["year5_value_per_share"] for x in values), "high": max(x["year5_value_per_share"] for x in values)}}}

PUBLICATION = {'symbol': 'CN:600085', 'report_period': '2026-Q3', 'valuation_note': '核心区间覆盖慢需求自主留存及持续亏损负担、base部分修复、修复并补库三类条件；来自已存结果的8.755761702981367与14.565965575397684元端点按一位小数呈现，不是单base权益折现率带、概率区间或硬底。联合不利事件仍可突破。主辅法不平均，未使用现价或市场倍数。', 'return_model_note': '仅使用原v2同一base、2026-11-01起五个持有年度的精确D及2031-10-31同状态Y5，非宽经营区间的混合支付路径。10%档实际D+Y5隐含10.337173661864464元，与主值11.96067097337413元的-1.6234973115096663元资本时点差保留。method是接口标识，本次没有计算IRR；不得将压力D与base Y5拼接。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

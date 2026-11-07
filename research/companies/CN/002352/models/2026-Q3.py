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
import fixtures

data = json.loads((SOURCE / "inputs.json").read_text(encoding="utf-8"))
model.validate_inputs(data)
fixtures.run_closed_form_fixtures(model)
zero = model.project(data, label="base-no-option-exercise")
full = model.project(data, label="base-all-options-exercised", exercise_all_options=True)
exercise = full["current_main"]["per_share"] < zero["current_main"]["per_share"]
base = full if exercise else zero
low = model.project(model.changed(data, {"capital.maintenance_to_da": 1.05, "capital.enterprise_discount_rate": .0925}), label="core-low", exercise_all_options=exercise, domestic_margin_shift=-.002)
high = model.project(model.changed(data, {"capital.maintenance_to_da": .95, "capital.enterprise_discount_rate": .0875}), label="core-high", exercise_all_options=exercise, domestic_margin_shift=.002)
value_range = {"low": low["current_main"]["per_share"], "high": high["current_main"]["per_share"], "currency": "CNY"}
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": data["information_cutoff"], "base_case_distributions_per_share": base["base_five_year_distributions_per_share"], "base_case_terminal_equity_value_range_per_share": {"year_5": base["year5_terminal_range_per_share"]}}

PUBLICATION = {'symbol': 'CN:002352', 'report_period': '2026-Q3', 'valuation_note': '主法为租后经营FCFF减NCI后折现，加普通股归属超额现金和非经营投资、减非租赁债。基准9%经营折现、2%成熟增长、12%增量ROIC，当前26.97431754580144元；核心低/高分别为国内毛利−/+20bp、维护105%/95%折旧、经营折现9.25%/8.75%。辅法正常普通股收益资本化29.87380598988566元，10%权益成本、14%正常权益ROIC，比主法高10.75%，不机械平均。主法终端现值占经营价值56.29%；结构不利16.770555462487994元并非下界。物业交易未交割不纳入基准，量价、正常毛利、资本回报及现金桥均为有条件研究估计。正文两位小数展示，结构化字段保留保存结果原精度。', 'return_model_note': '同一无额外期权行权base、估值日2026-10-31，未来五个持有年截至相应10月31日并在期末支付。D按正常普通股NOPAT扣非租赁税后息、加现金税后息的45%/50%/50%/50%/50%预算，55%上划；先子公司宣派收现、再母体法定储备及现金/RE约束，实际分配逐年从集团和母体现金扣除。历史已除权0.49元与回购不计未来D。第五年终值仍沿同一base经营与资本路径，仅剩余经营折现率9.25%/8.75%形成两端；加D后归属超额现金33597.16770434619百万元及投资18953.0747587394百万元，减非租赁债46988.015022976百万元，租赁现金与两层NCI均已归属处理。净在外5090.758878百万股；17.466709百万期权另测全行权并同步加现金后价值稍高，基准按无新增行权，属于小额内在价值近似而非完整期权时间价值。未来股数固定、无额外回购或净融资；正常续贷是假设。终值保留后续增长再投资、维护及续租，不重复保留已派D，不输出动态IRR或三年终值。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

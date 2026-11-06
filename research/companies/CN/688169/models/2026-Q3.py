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
import copy


data = json.loads((SOURCE / "inputs.json").read_text(encoding="utf-8"))
roles = {"primary_economic_base", "core_bounded_operating_path_not_law_fact", "core_conditional_execution_success"}
results = [model.run_scenario(data, s) for s in model.scenario_set(data) if s["role"] in roles]
base = next(x for x in results if x["scenario_id"] == "base")
value_range = {"low": round(min(x["method1_operating_cash_state_dcf_per_share"] for x in results), 2), "high": round(max(x["method1_operating_cash_state_dcf_per_share"] for x in results), 2), "currency": "CNY"}
base_config = next(x for x in data["scenarios"] if x["id"] == "base")
terminal = []
current = []
for spec in data["assumption_bounds"]["year5_base_rate_cases"]:
    config = copy.deepcopy(base_config)
    config.update(equity_discount=spec["equity_discount"], wacc=spec["wacc"])
    present, year5, year10 = model.value_existing_rows(base["annual_rows"], config, base["cutoff_state_estimate"])
    terminal.append(year5)
    current.append(present)
value_range = {"low": round(min(current), 2), "high": round(max(current), 2), "currency": "CNY"}
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": data["information_cutoff"], "base_case_distributions_per_share": base["five_year_distributions_per_share"], "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": min(terminal), "high": max(terminal)}}}

PUBLICATION = {'symbol': 'CN:688169', 'report_period': '2026-Q3', 'valuation_note': '方法一经营FCFF DCF为主，方法二正常化所有者经营收益为辅。核心仅采用base完整经营、资本、股份及分配路径，WACC 11%/9%、终端增长2%形成两端，原数152.21157614212802/187.39324202978892元作分位展示舍入；中点167.59元，辅助138.05元，不平均。核心不拼95.74—241.12的替代经营路径；严重境外压力66.39/44.58两法差32.86%，来自恢复持续期和近期收益锚不同，不是清算底。约49%终端净账面资本代理回报及可回收金融本金均有条件。', 'return_model_note': '五个完整前瞻年度止于2027—2031年10月31日；D为受母现金/法定RE及集团现金约束后的普通股实际现金预算，不含公开市场回购。五项数值与第五年211.64497235273882—250.67245913711844元终值沿同一base经营及分配后现金/股份状态，两端仅改变WACC为11%/9%。当前发行259,588,001股、专户3,013,028股，最终完全稀释预算261,105,601股；实际D按年度参与股，未来认购/专户出售与股数配对。第五年金融池204.69亿元已扣全部已付D、金融债务10.05亿元只扣一次；有限已承诺SBC在第五年后无加回，未来滚动激励保留为成本。预算非公司承诺，金融本金回收、库存及海外通行条件是经济限制；不输出三年终值或现价IRR。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

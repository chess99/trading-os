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
import bridge
import state_fields


data = json.loads((SOURCE / "inputs.json").read_text(encoding="utf-8"))
parameters = json.loads((SOURCE / "bridge-inputs.json").read_text(encoding="utf-8"))
case = json.loads(json.dumps(model.run_case(data, "base")))
state = {"name": "base", "group": "main"}
for key, path in state_fields.FIELD_MAP.items():
    value = case
    for component in path:
        value = value[component]
    state[key] = value
state["giga_holding"] = [{k: v for k, v in h.items() if k != "normal_parent_profit"} for h in case["giga"]["holding"]]
state["giga_forward_fiscal"] = {y: case["giga"]["fiscal"][y] for y in ("2036", "2037")}
state["initial_q3_cxmt_ownership_witness"] = case["cxmt"]["adopted_ownership"]
state["cxmt_cutoff_financial_rights"] = case["cxmt"]["cutoff_nonoperating_rights"]
state["cxmt_year5_financial_state"] = {k: case["cxmt"]["holding"][4][k] for k in state_fields.CX5_KEYS}
state["source_warnings"] = case["warnings"]
state["funding_flags"] = {"issuer": case["issuer_funding_distribution_feasible"], "cxmt": case["cxmt_financing_budget_feasible"], "combined": case["funding_distribution_feasible"]}
state["giga_normalization_fiscal_2031"] = case["giga"]["fiscal"]["2031"]
result = bridge.patch_state(state, parameters)
value_range = {"low": round(result["conditional_current_parameter_interval_per_share"][0], 2), "high": round(result["conditional_current_parameter_interval_per_share"][1], 2), "currency": "CNY"}
return_model = result["return_model"]

PUBLICATION = {'symbol': 'CN:603986', 'report_period': '2026-Q3', 'valuation_note': '核心为十年归母经营现金DCF加税后金融资产桥；兆易要求回报9%—11%、长鑫10%—12%，成熟名义增长2.5%。198.01—248.60元基于同一采用经营路径及选定初始会计可行归属的条件滚动，不是全域资产边界或情景包络。中心220.05元；本业终值现值占48.64%。高ROIC通过费用研发、持续前瞻资本与营运投入解释而不钳位。辅助为前五年现金加H5正常化零增长EPV，保留全部H5现金capex，中心184.68元，条件参照170.42—202.02元；不是价值底线、不与主法平均。未使用现价作锚或声称可靠错价。', 'return_model_note': '同一基准五期普通股实际现金预算3.912785127228979/4.171801833325321/4.16414091652796/4.201160745972369/4.520428509830042元，年末现金桶为2027—2031年10月31日。第五年价值276.09447178582985—333.36014009039917元，来自剩余经营DCF、已扣上述分配的集团现金、其他投资及税后长鑫权利，扣债务与匹配税负，除707.770627百万股。母体现金/可分留存、子公司宣派与到账、上划税、基金实缴、条件A/H工具及行权缴款分别递推；不假设第五年出售长鑫或集中返本。股数与分配是显式预算，H奖励新发及550万A期权代理另有范围；不含实时IRR，也不提供未独立研究的三年终值。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

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
model.same_function_tests()
definitions = model.scenario_definitions(data["assumptions"])
results = {d["name"]: model.simulate(data, d) for d in definitions if d["name"] in ("base", "core_low", "core_high")}
fixed = [x["dividend"] for x in results["base"]["rows"][:5]]
for source, target in (("core_low", "holder_low"), ("core_high", "holder_high")):
    definition = copy.deepcopy(next(x for x in definitions if x["name"] == source))
    definition["name"] = target
    results[target] = model.simulate(data, definition, fixed_first_five_dividends=fixed)
result = model.build_contract(data, results)
value_range = {**result["value_range"]}
for k in ("low", "high"): value_range[k] = round(value_range[k], 2)
return_model = result["return_model"]
return_model["base_case_distributions_per_share"] = [round(x, 6) for x in return_model["base_case_distributions_per_share"]]
return_model["base_case_terminal_equity_value_range_per_share"]["year_5"] = {k: round(v, 2) for k, v in return_model["base_case_terminal_equity_value_range_per_share"]["year_5"].items()}

PUBLICATION = {'symbol': 'CN:600563', 'report_period': '2026-Q3', 'valuation_note': '核心为既有重要供应商地位延续、增长逐步放缓且每年投入足额增长资金的经营路径，不含永久竞争损伤的所有情景端点。十年经营自由现金流及稳定期为主法，另加普通股超额金融资产；核心资本成本9%—10%、稳态名义增长2.5%，增销资金系数1.00—1.15，终值现值占经营价值约50.1%—59.1%。基准78.90元，正常无增长经营收益资本化辅助64.57元，主辅经营价值差21.5%反映增长持续期，不机械平均。初期产能、维护寿命、税务消耗及混合日期金融分类仍是关键不确定性。', 'return_model_note': '五个十二个月截至2027—2031年10月底；现金分配按前期正常利润约45%预算并受母公司法定利润代理及实际资金约束，不含2026年已付2.3元。长期CD最早2027年11月到期，首年不释放。第5年80.69—121.34元由两条经营端点使用同一基准五次D后，独立估计其后经营价值并加派息后净金融资产；低/高经营价值138.59/224.14亿元、派息后资产桥42.96/48.87亿元，股数2.25亿，无未宣布融资回购或稀释。现存及新增设备维护、经营周转与常备现金继续进入第6年及稳定期；未分配资金不作为已收现金。每股价值以分呈现，年度D保留六位小数。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

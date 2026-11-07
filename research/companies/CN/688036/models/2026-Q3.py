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


assumptions = json.loads((SOURCE / "assumptions.json").read_text(encoding="utf-8"))
facts = json.loads((SOURCE / "facts.json").read_text(encoding="utf-8"))["facts"]
common = assumptions["common"]
scenario = next(x for x in assumptions["scenarios"] if x["id"] == "base")
initial, bridge = model.make_cutoff(facts, scenario, common)
annual = [{k: v[i] for k, v in scenario["series"].items()} for i in range(8)]
result = model.attach_valuations(model.simulate(initial, annual, scenario["parameters"], common, "base"), common)
model.validate_result(result, common)
value_range = {**{k: round(v["per_share"], 2) for k, v in result["core_value_range"].items()}, "currency": "CNY"}
return_model = result["return_model"]

PUBLICATION = {'symbol': 'CN:688036', 'report_period': '2026-Q3', 'valuation_note': '主方法为八年经营DCF加额外净金融资产、减金融债务及NCI，基准中点35.5114元；核心两端仅同base经营状态采用经营折现11.5%/g1.5%与10.0%/g2.5%，终端资本同步增长。辅助正常化经营收益资本化中心31.9744元，Y3 NOPAT26亿元、10—13倍，并处理爬坡及一次资本回收；资本变动集中Y3折现是明示近似。结构弱12.0934元、较好61.1391元为完整替代路径，不拼核心范围。基准末期约33%、较好约56%的ROIC主要来自低净营运资本及供应商/应计融资，非新增投资实证。未采集当前交易价或输出IRR。', 'return_model_note': 'Y1为2026-11-01至2027-10-31，五项为2027—2031年10月31日年度近似支付的实际普通股分红预算，支付意愿40%升至60%，经过集团资金、母现金、母RE及毛额往来清偿约束。Y5范围41.35881780502276—48.87084895579969元来自同base Y5状态后的Y6—Y8及稳态经营DCF，加分红后额外现金/金融资产、减债务/NCI；不复制当前价值。完全稀释分母为已完成H发行后1,237,832,845股，未验证超配不计入。净募资原币为估计29亿港元，base FX0.91、半收半待收为条件预算；已付D已从Y5现金扣除，必要现金及保证金不另加作冗余资产。不提交未经独立研究的三年终值或现价IRR。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

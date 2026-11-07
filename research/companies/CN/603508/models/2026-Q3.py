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
result = model.build_all(data)
value_range = {"low": round(result["value_range_raw"][0], 2), "high": round(result["value_range_raw"][1], 2), "currency": "CNY"}
holder = result["return_model_raw"]
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": data["information_cutoff"].replace("Z", "+00:00"), "base_case_distributions_per_share": [round(x, 4) for x in holder["distributions"]], "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": round(holder["year5_low"], 2), "high": round(holder["year5_high"], 2)}}}

PUBLICATION = {'symbol': 'CN:603508', 'report_period': '2026-Q3', 'valuation_note': '核心采用归母经营FCFF折现加互斥净金融资产，基准20.83元；低/高端资本成本10%/9%、主要产品毛利较基准低/高0.5个百分点、NWC72%/68%、少数超额金融资产80/20百万元。核心经营路径保留列控缓增、安防/高铁有限扩展，研发10.2%，维护资本约等于正常化折旧、增长生产资本为新增收入20%；Y6—10渐降至1.5%长期增长并缓降毛利。零增长盈利资本化辅助为15.96—17.94元，不与DCF平均。金融收益不再进入经营价值，物业收益与资产不双计。少数金融资产0—115百万元诊断使基准价值20.96—20.66元；周期18.98、结构12.14、乐观22.27均不拼进核心区间。资本成本是企业风险判断而非个人目标回报。', 'return_model_note': '五年实际现金分配预算0.8673/0.9138/0.9563/0.9936/1.0268元，按目标、母体现金及可分配利润取低。60%正常化归母净利仅为研究预算，正式政策分母是有条件的可供分配利润且非2026以后无条件承诺；法定公积按FY25/H1实际不续提。母体资金减少及两年上划延迟压力使Y2实际D降至0.4086元。Y5基准经营价值7670.56百万元加已扣实付分红的归母金融资产1979.70百万元，以381274377股计算并对相同经营状态采用10%/9%资本成本，终值24.12—26.66元。无新增稀释、无回购现金分配、无重复计入截止前股利。留存金融现金只按税后1.5%收益滚动，故D及Y5终值折现不必等于当前经营FCFF加金融资产，不能称法律最大派息上界；现金仍属于股东但低收益滞留有兑现代价。 按同一基准9.5%资本成本折现，五年实际分配加同状态第五年权益的现值，比当前经营资产法低约429.18百万元，即约1.13元/股、5.4%。这衡量所设低收益留存与兑现时点的经济影响，不是将留存金融资产视为不存在。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

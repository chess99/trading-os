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
from scenarios import configurations


data = json.loads((SOURCE / "inputs.json").read_text(encoding="utf-8"))
result = model.analyze(data, configurations(data)["base"])
assert result["all_funding_feasible"]
value_range = {**{k: round(v["per_share"], 1) for k, v in result["endpoints"].items()}, "currency": "CNY"}
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": data["information_cutoff"], "base_case_distributions_per_share": result["dps"], "base_case_terminal_equity_value_range_per_share": {"year_5": {k: round(v["per_share_year5"], 1) for k, v in result["endpoints"].items()}}}

PUBLICATION = {'symbol': 'CN:600570', 'report_period': '2026-Q3', 'valuation_note': '当前普通股核心价值7.1—9.8元，主法为软件现金DCF、Ant股东现金DCF及净金融资产桥；两端对应折现率、Ant Y6或Y11开始释放、投资实现及少数/期权参数。辅助正常化盈利资本化约9.6—12.3元，不机械平均。', 'return_model_note': '五年为截止后连续十二个月。已付2026中期0.05元不重复进入未来D；主路径未来股数约19.026463亿股，现有已成就期权余量执行及待批注销均配对现金，当前合理价值含概率性非主批次权利估计，而持有人基准是其余批次不执行的指定条件，不是概率加权股数；同经营有/无当前权利扣减、无新增及全部条件执行的成套桥已分别列示，不因期满自动消除索偿，也不虚构现金赎回。旧较紧注销数仅为未核数量敏感。Y5终值来自当期后续软件经营、Ant资本/分配状态及分配后金融现金，减剩余少数；不复制当前价值，不列三年终值。分配须母现金与法定利润可行，基准依赖首年2亿元长存单提前动用、理财兑现及指定主期权认购款；赎回条款和完整母现金滚动尚未核实，因此这不是无条件分配预测。母缓冲不足与真正预算负现金分别列示，不可行压力路径不采用原分红/终值。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

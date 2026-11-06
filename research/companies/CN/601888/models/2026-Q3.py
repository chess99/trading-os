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
cases = {name: model.run_case(data, name) for name in ("base", "core_low", "core_high")}
result = model.assemble(data, cases)
value_range = {**{k: round(v, 2) if k != "currency" else v for k, v in result["value_range"].items()}}
return_model = result["return_model"]

PUBLICATION = {'symbol': 'CN:601888', 'report_period': '2026-Q3', 'valuation_note': '采纳温和海南恢复、完整付租及持续资本占用。主法十年现金租金经营DCF加同口径普通股资产桥，中枢28.82元；辅助正常化法29.09元，共享假设不构成独立证明。核心25.65—32.05元为同一经营路径合理毛利、周转、税、金融归属和9.5%—10.5%折现参数组合，非全部情景包络；Base长期增长2%、增量ROIC10%，当前经营终值贡献51.60%。', 'return_model_note': '同一Base年度经营和实际可行D1—D5；每股0.40元待付已包含首年一次，未来日期为预测，年度现金目标为普通股正常利润40%，受母体现金和可分留存约束。第五年富余金融资产304.14亿元、普通股银行债14.98亿元、联营18.24亿元及其他义务0.392亿元构成307.01亿元净桥；以同Base第6—10年现金重新估计T5为33.266335—36.367363元，已扣五年分红、不假设本金全部返还。股数2,077,796,644股，无未宣布融资。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

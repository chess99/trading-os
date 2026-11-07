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
base = model.evaluate(data, "base")
low = model.evaluate(data, "base", {"terminal_growth": .015})
value_range = {"low": round(low["method_one"]["per_eligible_share"], 2), "high": round(base["method_one"]["per_eligible_share"], 2), "currency": "CNY"}
shares = base["method_one"]["asset_bridge"]["eligible_shares"]
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": data["information_cutoff"], "base_case_distributions_per_share": [x["actual_D"] / shares for x in base["same_base_D_path"]["rows"][:5]], "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low["same_base_Y5_equity_after_D"]["per_eligible_share"], "high": base["same_base_Y5_equity_after_D"]["per_eligible_share"]}}}

PUBLICATION = {'symbol': 'CN:688029', 'report_period': '2026-Q3', 'valuation_note': '主法经营现金流DCF，辅助Y3正常化经营收益资本化。核心下端为已运行Base r10%/g1.5%/终端增量ROIC18%，上端为同Base g2.5%；不是弱情景或全部敏感性包络。主导Base主/辅为49.41184853541838/47.18103495917835元。采用普通股最终分享经营与金融本金的条件资产权利口径，依据实际分红及归属记录；同一零金融收益留存政策D1–5+Y5现值8140092647.194962—8469124226.356373元，比对应资产权利值低751423972.0334854元。该差额不能忽略、重复扣除或被解读为已证明Y5全释放。旧H1核心39.3—45.7是政策现值，不能直接称本次Q3上调；18%相对旧11%—13%是预算差异而非财报证明。', 'return_model_note': 'Y1为截至2027-10-31的完整十二个月，依次至2031-10-31；分配为预算，目标归母经营NOPAT50%，同时受母体现金、集团归属现金及母RE约束，不含2026-10-23已付0.50元。Y5按原Y6–8及终端剩余经营值，加D已付后的归母液态池、非液态本金和Y1实际基金call形成资产；不再扣已清借款/经营现金/股利/已call基金。低高端仅g1.5%/2.5%变化，同一D和金融状态。基准现有可分配186606016股固定，无新增股权融资或库存股再发；已发行187847422股、库存1241406股未注销，全部现有发行股参与的Base当前主值49.0853060436989、Y5为62.10083772169305元作为稀释条件。额外金融留存收益0，D+Y5回折不同于当前资产权利核心；Y5本金是条件经济权利，不是宣派、全部释放或成交价格承诺。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

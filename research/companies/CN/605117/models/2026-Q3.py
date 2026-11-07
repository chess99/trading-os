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
model.validate_input(data)
results = {s["id"]: model.run_scenario(data, s) for s in data["scenarios"] if s["id"] in ("base", "core_lower", "core_upper")}
value_range = {"low": round(results["core_lower"]["primary"]["valuation"]["value_per_share"], 3), "high": round(results["core_upper"]["primary"]["valuation"]["value_per_share"], 1), "currency": "CNY"}
return_model = model.make_return_model(data, results["base"])["return_model"]

PUBLICATION = {'symbol': 'CN:605117', 'report_period': '2026-Q3', 'valuation_note': '主法为经营现金DCF加同日可归属净金融桥，base67.4493400720127元；辅法按90%正常化规模、独立毛利、2.5%增长及同一资本义务得43.815075171801986元，低35.04%，不平均。主法七年后接三年有限过渡，成熟增长3%、新增容量/资本2.2x，维护与库存/采购信用持续支付，隐含成熟回报24.7553%而非实证项目ROI。核心下端采用量增倍率85%、毛利−1点、转嫁25%、折现10.5%、成熟回报18%；上端110%、毛利+0.5点、转嫁75%、折现9%、成熟回报25%，对应原全精度53.864252608212475—75.89990948134691元。核心是采纳的继续扩张路径，不包含全部结构风险；结构竞争主法33.38625093905745元。无时点市场价格或可靠错价结论。', 'return_model_note': '五个持有年度现金分配来自同base经营、65%派现目标和母体可分利润/现金预算，年度末依次2027—2031年10月31日；不含2026-10-14已付1.60元或公开市场回购。第三、第五年终值分别从当年分配后独立经营/金融状态生成剩余经营DCF及金融桥，第三年未由第五年折算。完全权利1273.295010百万股与期权现金及库存股未来重授配对，未假设未知H股。低/高终值条件为折现10.5%/9%、成熟增长2.5%/3%、成熟回报18%/25%；低端隐含容量资本1.730x属1.8—2.6常规范围外额外成本压力。D已从终值金融余额扣除，终值非未来市场价格承诺；两套等待预算不进入核心。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

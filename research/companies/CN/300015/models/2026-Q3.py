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


def calculate(name):
    raw = model.simulate(name)
    return {"value": raw["value_per_share"], "distributions": raw["distributions"], "terminal": raw["terminal5"]}
low, high = calculate("core_low"), calculate("core_high")
base = calculate("base")
terminal_low, terminal_high = calculate("terminal_low"), calculate("terminal_high")
assert base["distributions"] == terminal_low["distributions"] == terminal_high["distributions"]
value_range = {"low": round(low["value"], 2), "high": round(high["value"], 2), "currency": "CNY"}
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": model.ASOF, "base_case_distributions_per_share": [round(x, 3) for x in base["distributions"]], "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": round(terminal_low["terminal"], 2), "high": round(terminal_high["terminal"], 2)}}}

PUBLICATION = {'symbol': 'CN:300015', 'report_period': '2026-Q3', 'valuation_note': '地区成熟度主法基准3.95267785，患者费用成本入口3.84279370，不平均。核心国内增长4.5%—5.5%、折现9.5%—10.5%，十五年衰减至名义1.5%，仍付维护增长资本。英国合同与真实税差/付款主体照实；受限毛息税、FVTPL/FVOCI/权益法账面与现金及专项总认缴2亿元封顶分别闭合。快/慢合法返还约4.48684/3.46326元，治理政策重要，非永久锁现金。', 'return_model_note': '未来5个连续12个月每股实付.18/.195/.21/.225/.24，普通在外股数92.68201556亿、排除未注销库存股，不重复计历史回购/7月D。Y5同一基准全部母/医院/欧洲英国/巴西hold/基金/税/债权状态分叉，后续权益值4.55318037—5.70436232元；不是当前区间复制。资本出资或借款归属、已确认put与现实股权、利润/资本回收均分开。未来法人余额属约束预算非法律认证。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

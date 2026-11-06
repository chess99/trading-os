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
import terminal
import math


data = json.loads((SOURCE / "inputs.json").read_text(encoding="utf-8"))
observations = json.loads((SOURCE / "observed-inputs.json").read_text(encoding="utf-8"))
base = model.evaluate_case(model.case_input(data, "base"), observations)
assert not base["funding_infeasible"]
projection = terminal.project({"results": [base], "terminal_date": data["terminal_date"]}, data, observations, {"inputs": {}, "code": {}})
values = [x["current_EV_plus_NFA_per_share"] for x in base["valuation"]["valuation_parameter_grid"]]
value_range = {"low": math.floor(min(values)), "high": math.ceil(max(values)), "currency": "CNY"}
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": "2026-10-31T12:30:00+00:00", "base_case_distributions_per_share": [x["per_share"] for x in base["dividends"]], "base_case_terminal_equity_value_range_per_share": {"year_5": {k: round(v, 2) for k, v in projection["selected_same_path_Y5_range_per_share"].items()}}}

PUBLICATION = {'symbol': 'CN:603369', 'report_period': '2026-Q3', 'valuation_note': '主要采用经营现金流EV加当前风险税后金融净资产，基准27.588522026993694元；正常化商品盈利法辅助检验28.949759878178046元。基准参数边界分别24.20—31.36及25.82—32.34元，核心取24—32元；要求回报10.5%、成熟名义增长1%、增量资本回报10%，保留成熟维护和项目尾部。两法共享经营条件，不是独立需求证据。结构性弱路径20.68/21.57元及较好增长32.85/33.83元另列；核心带不是损失下限或交易建议。条件D+Y5不与当前价值法拼接，不统一折价留存资产。', 'return_model_note': '基准2027—2031年6月末预算支付五次现金D，依次为1.1331681767929014、1.1580619660394447、1.2216019662651108、1.2856029926056016、1.3445325062411466元/股，排除2026年已付分红；年度接口汇总这五次付款，并非公司已承诺日期。母法定利润、付款前母17.5亿元及集团25亿元现金保留门槛共同约束，子股利仅实际收到时增加母现金。当前及预测完全稀释股数1,246,800,037股，不预设增发、回购、新授股；原期权到期或条件不满足，不冒称注销登记完成。终点2031-10-31基准Y5中心33.57386428724403元，继续经营EV308.1407587757163亿元加剩余NFA110.45819357997208亿元，已经扣未来五次D；未付资产仍属股东，不作保证清算价。主Y5区间29.13—38.16元独立估第五年经营权利：同一前五年经营/D/期末NFA不变，要求回报9.5%—11.5%、增长0%—2%、增量资本回报8%—12%、维护/折摊100%—110%。低端组合11.5%/2%/8%/110%，高端9.5%/2%/12%/100%；未来利润窗口2031年11—12月加2032年1—10月，增长净投资含固定资本及基酒，原项目尾款另扣一次。NFA固定以基准金融回收及1.5%留存收益为条件；金融85%回收、结构性弱和较好增长另列，不能拼接。辅助正常商品盈利9—12倍的Y5范围31.92—39.71元另列，不与主法端点混合。区间是条件参数敏感性非概率/损失下限，不能由当前24—32元机械推导；不输出动态IRR。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

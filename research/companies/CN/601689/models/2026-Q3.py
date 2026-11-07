"""Recompute the adopted company model from readable current inputs."""
from pathlib import Path
import json
import sys

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
SOURCE = HERE / "2026-Q3"
sys.path.insert(0, str(SOURCE))
import engine as model


data = json.loads((SOURCE / "inputs.json").read_text(encoding="utf-8"))
case = model.make_case(data, "base")
projection = model.project(case)
values = [model.value_projection(projection, rate) for rate in data["shared"]["discount_rates"]]
value_range = {"low": round(min(x["value_per_share"] for x in values), 2), "high": round(max(x["value_per_share"] for x in values), 2), "currency": "CNY"}
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": data["information_cutoff"], "base_case_distributions_per_share": values[0]["distributions_per_share"], "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": min(x["year5_value_per_share_after_D5"] for x in values), "high": max(x["year5_value_per_share_after_D5"] for x in values)}}}

PUBLICATION = {'symbol': 'CN:601689', 'report_period': '2026-Q3', 'valuation_note': '主方法为十年分业务经营DCF，核心明确采纳有限恢复，同一经营/资本路径在10.5%与8.5%折现率下得到18.3943—25.5153元，按分显示18.39—25.52；9.5%中心21.4391元。终端名义增长2.5%，维护回归折旧并继续付固定资本/NWC/最低现金增长。周期延迟16.39—22.98、结构低回报7.26—10.10另列，不并入核心包络。辅助为独立正常化无增长收益与必要资本检验11.52—13.16；主要差距来自规模、盈利恢复、维护阶段和完成支出，不平均、不取低。基准第5年后经营价值占78.75%，第10年后永续占57.38%；核心不是全部经营不确定性区间或现金保底。', 'return_model_note': '五个滚动周年从2026-11-01起，现金支付日依次为2027—2031年10月31日；自然年2027—2031经营预算近似相应周年，不另加两月stub。D1用FY26归母23亿元预算的30%，以后滞后一期，并受母体RE、股利实收、母体及集团现金约束。TV5为2031-10-31支付D5后的同一base，第6—10年及后续经营现金折现，加该日超额现金100.6710亿元及金融资产6.1250亿元，减银行52.5219亿元、租赁5.5494亿元及NCI0.7513亿元，除固定普通股1,737,835,580；不重复加母体现金/内部应收或已付D。TV5为26.952174200638986—35.127942713566284元，不复制当前值。超额现金不是当日承诺特别派现；30%分配、正常续债、不额外偿债或特别分配是资本配置预算。未完成H股不计入；负子利润差截零与专户利息合并简化在实际路径未成为D边际，触及边界须修正。不输出三年终值或现价IRR。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

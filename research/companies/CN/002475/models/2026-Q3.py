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
case = next(x for x in data["cases"] if x["id"] == "base")
result = model.compute_case(data, case)
lower = model.compute_case(data, next(x for x in data["cases"] if x["id"] == "structural_customer_pressure"))
upper = model.compute_case(data, next(x for x in data["cases"] if x["id"] == "engineering_upside"))
# Adopted report bounds include the stated operating/return-on-capital paths.
value_range = {"low": round(lower["current_value_range_per_share"][0], 2), "high": round(upper["current_value_range_per_share"][1], 2), "currency": "CNY"}
return_model = result["return_model"]
low, high = return_model["base_case_terminal_equity_value_range_per_share"]["year_5"]
return_model["base_case_terminal_equity_value_range_per_share"]["year_5"] = {"low": low, "high": high}

PUBLICATION = {'symbol': 'CN:002475', 'report_period': '2026-Q3', 'valuation_note': '主方法为100%合并经营FCFF折现，加金融和联营价值、减全部债务及完整NCI与未发行员工权利。下端取结构性客户/资本压力路径与WACC10.5%，上端取有证据工程上侧与8.5%；是明确采用的相容经营范围，非12诊断极值、概率置信区间或所有风险包络。base成本范围29.73—40.73另列，中点34.42；14年预测、成熟g2.5%，base经营终值现值占46.57%。辅法为截止正常能力资本化锚，基准23.47元，未逐前瞻情景重新正常化，不平均两法。正常滚债、可回收本金、周转恢复及税率/维护预算仍是条件。', 'return_model_note': '唯一base未来五个11月1日至次年10月31日窗口实际普通股D。首窗口含截止已宣告Q3权利，10月H1旧权不再计D，回购不作现金分配。Y5以同一base余期经营及联营批次/等待尾，加当时金融资产，减实际债务、完整NCI及仍未发行员工权利，除当时在外8.006022714十亿股；行权实缴与股份同时记入，库存未注销、第三年重授属预算。五D已从现金移除，不与19.24—44.34多经营当前范围拼链；Y5范围45.65934483571306—58.39794643458823元仅改变base经营WACC8.5—10.5%。母体RE、法定提取、上划实收及最低现金约束分配，年度融资可行不代表全部现实限制已证实。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

"""Recompute the adopted company model from readable current inputs."""
from pathlib import Path
import json
import sys

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
SOURCE = HERE / "2026-Q3"
sys.path.insert(0, str(SOURCE))
import bank_model as model


data = json.loads((SOURCE / "inputs.json").read_text(encoding="utf-8"))
forecast = model.simulate(data, "base", {})
cycle = model.terminal_cycle(forecast, data)
endpoints = [model.price_forecast(forecast, cycle, data, rate) for rate in data["policy"]["ke_core"]]
low, high = endpoints
value_range = {"low": low["current"]["value"], "high": high["current"]["value"], "currency": "CNY"}
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": data["cutoff"], "base_case_distributions_per_share": forecast["holder_D"], "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low["year5"]["value"], "high": high["year5"]["value"]}}}

PUBLICATION = {'symbol': 'CN:601166', 'report_period': '2026-Q3', 'valuation_note': '核心为普通股剩余收益，端点只改变同一基准、无进一步转股融资路径的股权成本10.5%/9.5%，长期增长均2.5%；不以结构弱和较好路径拼核心区间。辅助采用独立H1原始利率及全年费用构造零增长正常化收益，并经母行上划与留存现金释放桥兑现，当前值30.070218274428168—33.49778274195721元。RI与同路径DDM仅是代数校核，不替代辅助方法。未用市场价格拟合或混入个人安全边际。', 'return_model_note': '五项普通现金严格对应2026年11月至2031年10月的五个Nov—Oct窗口，2月/6月为预算支付月份、每笔只记一次，2026年已付历史股利排除。第五年末价值来自同一基准2031年10月末之后的过渡及成熟经营状态，不复制当前价值。基准普通股21,162,864,665股，可转债按2027年109%含末息正常融资兑付、此后不再转股；转换诊断才增加股数，原2612百万元转换权不重复增值。普通账面权益和CET1扣减桥分开，母行RE已含9M利润。分配受准备、上一日历年母行利润原则、资本及资金约束；成熟期需正常上划和融资。所有未来现金为条件预算，月度记账标签不代表已宣派日期；按年度汇总分配与主法月折现的时间粒度不同。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))

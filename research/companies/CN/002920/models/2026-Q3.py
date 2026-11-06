"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core_value_range', 'low']}, 'high': {'path': ['core_value_range', 'high']}, 'distributions': {'path': ['return_model', 'base_case_distributions_per_share'], 'take': 5}, 'terminal_low': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'low']}, 'terminal_high': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'high']}}
METADATA = {'symbol': 'CN:002920', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T22:30:00+00:00', 'valuation_note': '核心为20年实际普通股现金分配折现及继续经营终值，9%—10%资本成本对应同一基准经营、付款、股数及Y5全状态。收入由346.41亿元TTM起步，前五年增8%、10%、10%、8%、7%；经营利润率7.8%逐步至8.3%再衰减至7.5%，稳态增长2%。资本开支、NWC、收入4%的必要现金和少数经济权益独立处理。辅助企业FCFF中值57.42元，核心中值55.49元。周期弱47.07元、结构弱14.08元、较乐观82.63元不混入核心区间；极端融资失败全PV/TV为null。未使用行情或历史倍数锚。', 'return_model_note': '未来五年D为0.294226、1.577523、1.783644、1.958844、2.105552元，来自母公司利润与真实现金预算的较低可行值，不把集团FCFF、回购或留存当作已收分配。Y5 TV73.865386—83.739034元，从同一基准Y5全部资产、债务、现金、母公司留存及股数继续折现Y6—20付款与尾期权益。长期必要现金在经营资本内，已派股利从现金扣除。基准分母596809294股，含库存股潜在重新参与；期权按内在续存值是否高于84.85元行权价联动现金与股数，乐观路径上限599551694股，H股不预设发行。法定利润只在真实母公司核验，子公司经济余项不虚构法定储备、不预算上划；有限投资回收区分本金、损益与税费。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))

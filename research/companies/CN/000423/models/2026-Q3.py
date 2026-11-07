"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['base_low', 'value']}, 'high': {'path': ['base_high', 'value']}, 'distributions': {'path': ['tail_source_buffer_scenarios', 'base', 'rows'], 'column': 'dps', 'take': 5}, 'terminal_low': {'path': ['year5_low', 'value']}, 'terminal_high': {'path': ['year5_high', 'value']}}
METADATA = {'symbol': 'CN:000423', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T07:00:00+00:00', 'valuation_note': '核心为十年经营预测及后续真实母付款，资本成本8.5%—9.5%；必要流动性按收入增长，尾期每五年实现余资、来源扣1%摩擦，利润与本金分列且母付款仍受法定容量约束。辅助为第三年经营利润16—19倍及现金桥。经营预测不变，尾期经济实现预算修正，不构成法律批准。', 'return_model_note': '五个年度DPS保持原完整精度；第五年价值重算第六年以后现金。0.639802980bn已发行减0.000385869bn库存股，参与股份0.639417111bn。尾期收入比例必要现金、五年有限余资实现及1%来源摩擦，无集团现金终值加回、无本金计利润、无额外融资；首五年真实母法律容量保持。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))

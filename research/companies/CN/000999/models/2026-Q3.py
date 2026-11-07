"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['summary', 'core_low', 'value_per_share'], 'round': 2}, 'high': {'path': ['summary', 'core_high', 'value_per_share'], 'round': 2}, 'distributions': {'path': ['summary', 'base', 'dps'], 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['summary', 'terminal_low', 'terminal5_per_share'], 'round': 2}, 'terminal_high': {'path': ['summary', 'terminal_high', 'terminal5_per_share'], 'round': 2}}
METADATA = {'symbol': 'CN:000999', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T07:05:00+00:00', 'valuation_note': '长期普通股现金折现为主，核心增长2%—3%、资本成本9%—10%、成熟增长1.5%、增量资本回报12%—15%；真实母法定账、子集团经济上划预算，五年滚动释放新增闲钱并计摩擦。辅助正常化经营收益资本化24.84—28.70元；严重无融资路径不输出可实现估值。', 'return_model_note': '截至2027—2031年10月26日五个滚动年度，固定16.64217858亿股。第5年4.648555元包含约3.492987元特别返还预算，非已宣派事实；母股利受实际利润和现金约束，子集团上划为注明条件的经济预算，未合成法律主体。旧股利收现不重复确认利润；非经营本金只处置回收一次，必要资本继续经营。第五年23.03—26.27元为基准五年已付现金后第6年以后的持续现金现值；不另重复加留存现金、金融收益或少数权益。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))

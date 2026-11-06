"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'base', 'low', 'value_per_share'], 'round': 1}, 'high': {'path': ['cases', 'base', 'high', 'value_per_share'], 'round': 0}, 'distributions': {'path': ['cases', 'base', 'rows'], 'column': 'dps', 'take': 5}, 'terminal_low': {'path': ['cases', 'base', 'low', 'year5_per_share']}, 'terminal_high': {'path': ['cases', 'base', 'high', 'year5_per_share']}}
METADATA = {'symbol': 'CN:002415', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T06:21:46+00:00', 'valuation_note': '十年实际分红与经营/金融尾部折现；r10%—9%、g2%、ROIC15%，额外净替换为收入0.7%，持续现金80%当年及20%延3年95%实现。金融存量按位置、内部本金及法律容量有限回收。重大场景和12项敏感性完整重算，不混入核心。', 'return_model_note': '五个年度窗口采用2027—2031经营能力近似，排除已付2026中期0.55元，无回购与融资稀释承诺。第五年终值独立来自第6—10年现金及第十年剩余权益，非当前PV复制。未来经营、资金归集和股利均为条件预算。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))

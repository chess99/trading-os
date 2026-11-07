"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['outputs', 'core_low', 'current_value'], 'round': 2}, 'high': {'path': ['outputs', 'core_high', 'current_value'], 'round': 2}, 'distributions': {'path': ['outputs', 'base', 'rows'], 'column': 'dps', 'take': 5, 'round_items': [3, 4, 4, 4, 4]}, 'terminal_low': {'path': ['base_terminal_range', 0], 'round': 2}, 'terminal_high': {'path': ['base_terminal_range', 1], 'round': 2}}
METADATA = {'symbol': 'CN:000895', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T21:05:30+00:00', 'valuation_note': '主法为实际股利折现加独立第五年经营与金融权益桥，核心采用温和修复路径合理量价/投入范围，不混入结构与乐观情景。资本成本8.5%—9.5%、长期增长0.5%—1.5%、增量回报13%—18%；辅助零增长法12.50—15.92元。', 'return_model_note': '五个完整周年的实际分红为经济预算，非决议承诺。同一基准经营与已分配后金融资产下第五年终值16.67—20.42元；终值经营现金剥离金融收益和债息，再加归普通股本金净桥。34.64661213亿完全稀释股数不变，无回购增发假设。母体H1余额仅为预算锚；保留负损益、先弥亏、法定公积及偿债主体限制，不把合并现金当即刻可分。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))

"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core_low', 'current_value'], 'round': 2}, 'high': {'path': ['core_high', 'current_value'], 'round': 2}, 'distributions': {'path': ['base', 'rows'], 'column': 'dps', 'take': 5}, 'terminal_low': {'path': ['core_low', 'terminal_per_share']}, 'terminal_high': {'path': ['core_high', 'terminal_per_share']}}
METADATA = {'symbol': 'CN:600660', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T00:00:00+08:00', 'valuation_note': '核心为实际五年普通股分配加第五年持续经营和金融权益价值；资本成本9%—10%，长期增长2.5%、增量资本回报15%。必要维护与折旧一致，新增金融现金逐批实现。辅助EV/NOPAT为40.43—46.91元，不机械平均。', 'return_model_note': '五年为截止日起连续12个月，历史股利排除；A/H共26.09743532亿股不稀释。新宣派、既存应收到账、母公司10%实际公积政策和现金容量分开。第五年终值由第6—10年经营现金及永续现金逐批归集预算，加分配后金融本金净实现值、减全部债务；经营价值不含金融利息。正常每年90%现金当期、10%延后三年按97%净实现，非法律承诺或即时特别分红；无三年终值。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))

"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'core_low', 'value_per_share'], 'round': 2}, 'high': {'path': ['cases', 'core_high', 'value_per_share'], 'round': 2}, 'distributions': {'path': ['cases', 'base', 'annual'], 'column': 'dps', 'take': 5}, 'terminal_low': {'path': ['cases', 'core_low', 'terminal_share_y5']}, 'terminal_high': {'path': ['cases', 'core_high', 'terminal_share_y5']}}
METADATA = {'symbol': 'CN:300012', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-21T19:21:00+08:00', 'valuation_note': '主方法按实际普通股现金及跨层实现折现；资本成本8.5%—9.5%、长期增长2.5%—3%、新增资本回报14%—16%。辅助剩余收益8.87—12.53元。结构性不利与乐观情景不混入核心区间。', 'return_model_note': '五年普通股每股现金0.23/0.26/0.29/0.32/0.35元；第五年末价值由第6年后母公司实际支付折现。16.82828214亿股不变，盈利已归普通股；起点额外金融资产6.5862737714亿元及后续收益仅经未来分配实现，不再另加本金。母公司真实单体法定账与有历史依据的子公司经济上划预算分别滚动；境外转款采用条件性摩擦预算，不套用内地公积规则。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))

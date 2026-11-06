"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'core_low', 'value_per_share'], 'round': 1}, 'high': {'path': ['scenarios', 'core_high', 'value_per_share'], 'round': 1}, 'distributions': {'path': ['scenarios', 'base', 'rows'], 'column': 'dividend_per_share', 'take': 5, 'round_items': [5, 6, 6, 6, 6]}, 'terminal_low': {'path': ['base_terminal_range_per_share', 'low'], 'round': 6}, 'terminal_high': {'path': ['base_terminal_range_per_share', 'high'], 'round': 6}}
METADATA = {'symbol': 'CN:603816', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T11:53:16+00:00', 'valuation_note': '主方法五年普通股实际分配及独立第五年经济权益折现，辅助第一年正常化盈利资本化并扣超折旧资本投入。核心组合共享需求恢复及项目付款路径，资本成本9.0%—10.5%、长期增长1.0%—1.5%、增量回报12%—14%，不混入严重结构情景。', 'return_model_note': '五年现金分配取意向、母公司可分利润、母现金与集团剩余现金较小值。第五年终值以同一基准经营和现金状态独立测算，额外金融本金分六年释放并扣债务、必要资本与摩擦；未来股数925527012股仅纳入明确待注销股份并扣退股款。已分配现金不再计入终值，无三年终值。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))

"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['value_range', 'low']}, 'high': {'path': ['value_range', 'high']}, 'distributions': {'path': ['holder', 'base_case_distributions_per_share'], 'take': 5}, 'terminal_low': {'path': ['holder', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'low']}, 'terminal_high': {'path': ['holder', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'high']}}
METADATA = {'symbol': 'CN:000333', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-30T02:30:00+00:00', 'valuation_note': '分业务经营与资本需求主法，核心69.03—89.72元；独立NOPAT/增量ROIC辅法72.57元，同一普通股现金实现桥，不取均值。', 'return_model_note': '五年现金来自同一基准状态，第五年后权益从完整现金/债/权益/股数状态继续经营，长期无尾期本金强制回收。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))

"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'capital_return_250m_year', 'central', 'all_financial_excess_released_by_year']}, 'high': {'path': ['scenarios', 'base', 'valuation_endpoints', 1, 'value_per_share'], 'round': 1}, 'distributions': {'path': ['base_return_model', 'base_case_distributions_per_share'], 'take': 5}, 'terminal_low': {'path': ['base_return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'low']}, 'terminal_high': {'path': ['base_return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'high']}}
METADATA = {'symbol': 'CN:688475', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T10:00:00+00:00', 'valuation_note': '核心精算16.96278608486765/19.745789628841536，同一经营路径及资本实现预算，10.5%/9.5%折现。辅助成熟盈利法另列，不平均。', 'return_model_note': '前五年为原持有人实际分配，完整float；TV5按同一轨迹后续股利与按比例资本退款折现，退款同步注销股份，以原787.5m股权益归一，无本金重复计价。母法律账与非母经济上划预算分开，受托赋睿仅合同收益权。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))

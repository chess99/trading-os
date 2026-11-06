"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['value_range', 'low']}, 'high': {'path': ['value_range', 'high']}, 'distributions': {'path': ['return_model', 'base_case_distributions_per_share'], 'take': 5}, 'terminal_low': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'low']}, 'terminal_high': {'path': ['return_model', 'base_case_terminal_equity_value_range_per_share', 'year_5', 'high']}}
METADATA = {'symbol': 'CN:920982', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T02:25:00+00:00', 'valuation_note': '主法独立分产品正常化经营及实际付款主体现金递推；辅法独立可持续投入资本回报，不采用证券报价或市场倍数。核心低/高经营路径不与辅助区间平均。结构性降价+超支路径真实融资缺口后fail-closed，不输出虚构清算底。', 'return_model_note': '同一基准逐年状态继续计算Y5后普通股现金，10.5%—11.5%折现区间；已派现金实际扣除。新增3.607243百万股Y1登记、50万库存股无分红且Y2条件转售，绩效期权未达标不稀释。65%余现释放和逐主体资金路径是预算而非既定授权，并有完整敏感性。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
